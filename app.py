import os
import sys
import io
import time
import shutil
import json
import requests
from flask import Flask, jsonify, request, send_from_directory, render_template_string, Response
from config import INPUT_FOLDER, PUBLISHED_FOLDER, DRAFTS_FILE, SERPAPI_KEY, OPENAI_API_KEY
from helpers.local_queue import load_drafts, save_drafts, add_draft, update_draft, mark_draft_published, delete_draft, get_pending_drafts
from helpers.agent_tools import run_parallel_ai_pipeline, audit_hashtag_engagement_virality
from helpers.web_search_engine import search_web_hybrid
from helpers.schedule_calculator import get_calculated_schedule_for_new_post
from helpers.post_scheduler import schedule_or_publish_to_instagram
from helpers.account_analytics import fetch_and_analyze_account_posts
from openai import OpenAI
from PIL import Image

app = Flask(__name__, static_folder='static')
openai_client = OpenAI(api_key=OPENAI_API_KEY)

VALID_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.jfif', '.gif')

os.makedirs(INPUT_FOLDER, exist_ok=True)
os.makedirs(PUBLISHED_FOLDER, exist_ok=True)

def resize_image_for_analysis(image_path, max_size=(512, 512)):
    with Image.open(image_path) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail(max_size)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=80)
        buffer.seek(0)
        return buffer

@app.route('/input_file/<path:filename>')
def serve_input_file(filename):
    return send_from_directory(INPUT_FOLDER, filename)

@app.route('/published_file/<path:filename>')
def serve_published_file(filename):
    return send_from_directory(PUBLISHED_FOLDER, filename)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload any image from any folder on user's computer into ./input folder."""
    os.makedirs(INPUT_FOLDER, exist_ok=True)
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part in request'}), 400
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'}), 400

    try:
        img_bytes = file.read()
        if not img_bytes:
            return jsonify({'success': False, 'error': 'Uploaded file is empty (0 bytes)'}), 400

        img = Image.open(io.BytesIO(img_bytes))
        
        orig_ext = os.path.splitext(file.filename)[1].lower()
        if orig_ext not in VALID_EXTENSIONS:
            orig_ext = ".jpg"

        raw_name = os.path.splitext(os.path.basename(file.filename))[0]
        safe_name = "".join([c for c in raw_name if c.isalnum() or c in ('-', '_')]).strip()
        if not safe_name:
            safe_name = "photo"

        timestamp_suffix = int(time.time() * 1000) % 1000000
        filename = f"{safe_name}_{timestamp_suffix}{orig_ext}"
        save_path = os.path.join(INPUT_FOLDER, filename)

        with open(save_path, "wb") as f:
            f.write(img_bytes)

        print(f"[Upload] Successfully saved photo to input folder: {filename} ({len(img_bytes)} bytes)")
        return jsonify({'success': True, 'filename': filename})

    except Exception as e:
        print(f"[Upload Error] {e}")
        return jsonify({'success': False, 'error': f'Failed to process image file: {str(e)}'}), 500

@app.route('/api/items', methods=['GET'])
def get_items():
    os.makedirs(INPUT_FOLDER, exist_ok=True)
    os.makedirs(PUBLISHED_FOLDER, exist_ok=True)

    input_files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(VALID_EXTENSIONS)] if os.path.exists(INPUT_FOLDER) else []
    published_files = [f for f in os.listdir(PUBLISHED_FOLDER) if f.lower().endswith(VALID_EXTENSIONS)] if os.path.exists(PUBLISHED_FOLDER) else []
    drafts = load_drafts()
    drafts_by_file = {d['image_filename']: d for d in drafts}

    items = []
    for f in input_files:
        d = drafts_by_file.get(f)
        items.append({
            'filename': f,
            'image_url': f'/input_file/{f}',
            'status': d.get('status') if d else 'unprocessed',
            'draft': d,
            'is_published': False
        })

    for f in published_files:
        d = drafts_by_file.get(f)
        items.append({
            'filename': f,
            'image_url': f'/published_file/{f}',
            'status': 'published',
            'draft': d,
            'is_published': True
        })

    return jsonify({'items': items, 'input_count': len(input_files), 'published_count': len(published_files)})

@app.route('/api/generate', methods=['POST'])
def generate_post():
    data = request.json or {}
    target_filename = data.get('filename')
    user_hint = data.get('user_hint', '').strip()
    
    if target_filename:
        files = [target_filename]
    else:
        files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(VALID_EXTENSIONS)] if os.path.exists(INPUT_FOLDER) else []

    results = []
    for filename in files:
        image_path = os.path.join(INPUT_FOLDER, filename)
        if not os.path.exists(image_path):
            continue

        try:
            img_buffer = resize_image_for_analysis(image_path)
            
            # Autonomous 3-Pass Pipeline Execution with User Hint & Live Instagram Engagement Audit
            pipeline_res = run_parallel_ai_pipeline(img_buffer, user_description=user_hint)
            
            pending = get_pending_drafts()
            sched_time = get_calculated_schedule_for_new_post(pending)

            draft = add_draft(
                image_filename=filename,
                image_path=image_path,
                desc_analysis=pipeline_res['desc_json'],
                web_report=pipeline_res['report'],
                caption=pipeline_res['caption'],
                scheduled_time=sched_time,
                image_user_description=user_hint
            )
            draft['telemetry'] = pipeline_res['telemetry']
            draft['keywords'] = pipeline_res.get('keywords', [])
            draft['hashtag_breakdown'] = pipeline_res.get('hashtag_breakdown', [])
            draft['user_hint'] = user_hint
            results.append(draft)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    return jsonify({'success': True, 'drafts': results})

@app.route('/api/account_analytics', methods=['GET'])
def get_account_analytics():
    """Fetches real published Instagram posts via Graph API & returns deep analytics."""
    analytics_data = fetch_and_analyze_account_posts(limit=50)
    return jsonify(analytics_data)

@app.route('/api/search_hashtags', methods=['POST'])
def search_hashtags():
    data = request.json or {}
    keyword = data.get('keyword', '').strip()
    if not keyword:
        return jsonify({'success': False, 'error': 'Missing keyword'}), 400

    try:
        snippets, engine_used = search_web_hybrid(f"site:instagram.com top hashtags and engagement for {keyword} toy photography", max_results=5)
        web_info = "\n".join(snippets)

        prompt = f"""Keywords: {keyword}
Search Info: {web_info}

Analyze and return EXACTLY 5 high-impact viral Instagram hashtags starting with # (always include #nendography).
Return ONLY JSON: {{"hashtags": ["#nendography", "#tag2", "#tag3", "#tag4", "#tag5"]}}
"""
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=200
        )
        data_res = json.loads(response.choices[0].message.content)
        hashtags = data_res.get("hashtags", [])[:5]

        breakdown = audit_hashtag_engagement_virality(hashtags, keyword, "Anime", web_report=web_info)

        return jsonify({'success': True, 'hashtags': hashtags, 'hashtag_str': " ".join(hashtags), 'hashtag_breakdown': breakdown, 'engine_used': engine_used})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/update_draft', methods=['POST'])
def update_draft_endpoint():
    data = request.json or {}
    draft_id = data.get('id')
    caption = data.get('caption')
    scheduled_time = data.get('scheduled_time')

    if not draft_id:
        return jsonify({'success': False, 'error': 'Missing draft ID'}), 400

    ok = update_draft(draft_id, new_caption=caption, new_scheduled_time=scheduled_time)
    return jsonify({'success': ok})

@app.route('/api/delete_item', methods=['POST'])
def delete_item_endpoint():
    """Permanently delete an image file from ./input/ or ./published/ and remove draft entry."""
    data = request.json or {}
    filename = data.get('filename')
    if not filename:
        return jsonify({'success': False, 'error': 'Missing filename'}), 400

    input_path = os.path.join(INPUT_FOLDER, filename)
    published_path = os.path.join(PUBLISHED_FOLDER, filename)
    
    if os.path.exists(input_path):
        try: os.remove(input_path)
        except Exception: pass
        
    if os.path.exists(published_path):
        try: os.remove(published_path)
        except Exception: pass

    drafts = load_drafts()
    target_draft = next((d for d in drafts if d.get('image_filename') == filename), None)
    if target_draft:
        delete_draft(target_draft['id'])

    print(f"[Delete] Permanently cleared photo: {filename}")
    return jsonify({'success': True, 'deleted_filename': filename})

@app.route('/api/publish_now', methods=['POST'])
def publish_now():
    data = request.json or {}
    draft_id = data.get('id')
    if not draft_id:
        return jsonify({'success': False, 'error': 'Missing draft ID'}), 400

    drafts = load_drafts()
    target = next((d for d in drafts if d.get('id') == draft_id), None)
    if not target:
        return jsonify({'success': False, 'error': 'Draft not found'}), 404

    try:
        pub_id = schedule_or_publish_to_instagram(
            image_path=target['image_path'],
            caption=target['caption'],
            scheduled_time_iso=None
        )
        mark_draft_published(target['id'])

        if os.path.exists(target['image_path']):
            dest = os.path.join(PUBLISHED_FOLDER, target['image_filename'])
            shutil.move(target['image_path'], dest)

        return jsonify({'success': True, 'published_id': pub_id, 'mode': 'Immediate Publish'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/publish', methods=['POST'])
def publish_schedule():
    data = request.json or {}
    draft_id = data.get('id')
    if not draft_id:
        return jsonify({'success': False, 'error': 'Missing draft ID'}), 400

    drafts = load_drafts()
    target = next((d for d in drafts if d.get('id') == draft_id), None)
    if not target:
        return jsonify({'success': False, 'error': 'Draft not found'}), 404

    try:
        pub_id = schedule_or_publish_to_instagram(
            image_path=target['image_path'],
            caption=target['caption'],
            scheduled_time_iso=target['scheduled_time']
        )
        mark_draft_published(target['id'])

        if os.path.exists(target['image_path']):
            dest = os.path.join(PUBLISHED_FOLDER, target['image_filename'])
            shutil.move(target['image_path'], dest)

        return jsonify({'success': True, 'published_id': pub_id, 'mode': 'Scheduled Peak Publish'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/')
def index():
    return Response(HTML_TEMPLATE, mimetype='text/html', headers={'Content-Type': 'text/html; charset=utf-8'})

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Instagram Studio - Agent Harness Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-dark: #090d16;
            --card-bg: rgba(22, 30, 46, 0.75);
            --card-border: rgba(255, 255, 255, 0.08);
            --accent-purple: #8b5cf6;
            --accent-pink: #ec4899;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-yellow: #f59e0b;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-main);
            min-height: 100vh;
            background-image: 
                radial-gradient(at 0% 0%, rgba(139, 92, 246, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(236, 72, 153, 0.12) 0px, transparent 50%);
            background-attachment: fixed;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.25rem 2.5rem;
            background: rgba(15, 23, 42, 0.8);
            backdrop-filter: blur(16px);
            border-bottom: 1px solid var(--card-border);
            position: sticky;
            top: 0;
            z-index: 50;
        }

        .brand { display: flex; align-items: center; gap: 0.75rem; }

        .brand-logo {
            width: 40px; height: 40px;
            background: linear-gradient(135deg, var(--accent-purple), var(--accent-pink));
            border-radius: 12px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.25rem;
            box-shadow: 0 0 20px rgba(236, 72, 153, 0.4);
        }

        .brand-title {
            font-family: 'Outfit', sans-serif;
            font-size: 1.35rem; font-weight: 700;
            background: linear-gradient(to right, #ffffff, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .header-badges { display: flex; align-items: center; gap: 1rem; }

        .btn-analytics {
            background: linear-gradient(135deg, #10b981, #3b82f6);
            color: #ffffff; padding: 0.45rem 1rem; border-radius: 20px;
            font-size: 0.85rem; font-weight: 600; cursor: pointer;
            border: none; outline: none; transition: transform 0.2s;
            display: flex; align-items: center; gap: 0.4rem;
        }

        .btn-analytics:hover { transform: translateY(-2px); }

        .status-badge {
            display: flex; align-items: center; gap: 0.5rem;
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: #34d399;
            padding: 0.4rem 0.85rem;
            border-radius: 20px;
            font-size: 0.85rem; font-weight: 500;
        }

        .status-dot {
            width: 8px; height: 8px;
            background-color: #34d399;
            border-radius: 50%;
            box-shadow: 0 0 8px #34d399;
        }

        main { max-width: 1300px; margin: 2rem auto; padding: 0 1.5rem; }

        .dashboard-grid {
            display: grid;
            grid-template-columns: 340px 1fr;
            gap: 2rem;
        }

        @media (max-width: 900px) { .dashboard-grid { grid-template-columns: 1fr; } }

        .card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            transition: border-color 0.2s ease;
        }

        .server-status-banner {
            display: none;
            background: rgba(239, 68, 68, 0.2);
            border: 1px solid rgba(239, 68, 68, 0.5);
            color: #fca5a5;
            padding: 0.75rem 1rem;
            border-radius: 10px;
            margin-bottom: 1rem;
            font-size: 0.85rem;
            line-height: 1.4;
        }

        .section-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 1.25rem;
        }

        .section-title {
            font-family: 'Outfit', sans-serif;
            font-size: 1.15rem; font-weight: 600;
            display: flex; align-items: center; gap: 0.5rem;
        }

        .btn {
            display: inline-flex; align-items: center; justify-content: center;
            gap: 0.5rem; padding: 0.65rem 1.25rem; border-radius: 10px;
            font-weight: 600; font-size: 0.9rem; cursor: pointer;
            transition: all 0.2s ease; border: none; outline: none;
        }

        .btn-upload {
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            color: #ffffff;
            width: 100%;
            margin-bottom: 1rem;
            padding: 0.75rem;
            box-shadow: 0 4px 15px rgba(59, 130, 246, 0.35);
        }

        .btn-upload:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(139, 92, 246, 0.5);
        }

        .btn-now {
            background: linear-gradient(135deg, #f59e0b, #ef4444);
            color: #ffffff;
            box-shadow: 0 4px 15px rgba(245, 158, 11, 0.35);
        }

        .btn-now:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(239, 68, 68, 0.5);
        }

        .btn-schedule {
            background: linear-gradient(135deg, var(--accent-purple), var(--accent-pink));
            color: #ffffff;
            box-shadow: 0 4px 15px rgba(139, 92, 246, 0.35);
        }

        .btn-schedule:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(236, 72, 153, 0.5);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.06);
            color: var(--text-main);
            border: 1px solid var(--card-border);
        }

        .btn-secondary:hover { background: rgba(255, 255, 255, 0.12); }

        .btn-danger {
            background: rgba(239, 68, 68, 0.15);
            color: #fca5a5;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .btn-danger:hover { background: rgba(239, 68, 68, 0.3); }

        .photo-list {
            display: flex; flex-direction: column; gap: 0.85rem;
            max-height: 65vh; overflow-y: auto; padding-right: 0.25rem;
        }

        .photo-item {
            display: flex; align-items: center; gap: 1rem; padding: 0.75rem;
            border-radius: 12px; background: rgba(255, 255, 255, 0.03);
            border: 1px solid transparent; cursor: pointer; transition: all 0.2s ease;
            position: relative;
        }

        .photo-item:hover, .photo-item.active {
            background: rgba(139, 92, 246, 0.12);
            border-color: rgba(139, 92, 246, 0.4);
        }

        .photo-thumb {
            width: 56px; height: 56px; border-radius: 8px;
            object-fit: cover; background-color: #000;
        }

        .photo-info { flex: 1; overflow: hidden; }

        .photo-name {
            font-size: 0.9rem; font-weight: 500;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }

        .photo-del-btn {
            background: rgba(239, 68, 68, 0.2);
            color: #fca5a5;
            border: 1px solid rgba(239, 68, 68, 0.4);
            border-radius: 6px; padding: 0.25rem 0.5rem;
            font-size: 0.75rem; cursor: pointer;
            transition: all 0.2s ease;
        }

        .photo-del-btn:hover { background: rgba(239, 68, 68, 0.5); color: #fff; }

        .badge {
            display: inline-block; padding: 0.2rem 0.5rem; border-radius: 6px;
            font-size: 0.75rem; font-weight: 600; margin-top: 0.25rem;
        }

        .badge-unprocessed { background: rgba(156, 163, 175, 0.15); color: #d1d5db; }
        .badge-ready { background: rgba(59, 130, 246, 0.15); color: #93c5fd; }
        .badge-published { background: rgba(16, 185, 129, 0.15); color: #6ee7b7; }

        .editor-container { display: flex; flex-direction: column; gap: 1.5rem; }

        .preview-header {
            display: flex; align-items: center; justify-content: space-between;
            padding-bottom: 1rem; border-bottom: 1px solid var(--card-border);
        }

        .image-preview-large {
            width: 100%; max-height: 380px; object-fit: contain;
            border-radius: 12px; background: #000; border: 1px solid var(--card-border);
        }

        .telemetry-panel {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--card-border);
            border-radius: 12px; padding: 0.85rem 1.25rem;
            display: flex; justify-content: space-between; align-items: center;
            font-size: 0.85rem; color: var(--text-muted);
        }

        .telemetry-item { display: flex; align-items: center; gap: 0.4rem; }
        .telemetry-val { color: #a7f3d0; font-weight: 600; }

        .hashtag-search-box {
            background: rgba(15, 23, 42, 0.4);
            border: 1px dashed var(--card-border);
            border-radius: 12px; padding: 1rem;
            display: flex; flex-direction: column; gap: 0.75rem;
        }

        .hashtag-search-row { display: flex; gap: 0.5rem; }

        .hashtag-search-row input {
            flex: 1; background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--card-border); border-radius: 8px;
            padding: 0.6rem 0.85rem; color: #fff; outline: none; font-size: 0.9rem;
        }

        .hashtag-pills { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem; }

        .hashtag-pill {
            background: rgba(139, 92, 246, 0.2);
            border: 1px solid rgba(139, 92, 246, 0.4);
            color: #c084fc; padding: 0.35rem 0.75rem; border-radius: 20px;
            font-size: 0.85rem; font-weight: 500;
        }

        .hashtag-rationale-list {
            display: flex; flex-direction: column; gap: 0.6rem; margin-top: 0.75rem;
            background: rgba(0, 0, 0, 0.3); padding: 1rem; border-radius: 10px;
            font-size: 0.82rem; border: 1px solid rgba(255, 255, 255, 0.08);
        }

        .hashtag-rationale-card {
            background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 8px; padding: 0.65rem 0.85rem; display: flex; flex-direction: column; gap: 0.25rem;
        }

        .hashtag-card-header {
            display: flex; justify-content: space-between; align-items: center;
        }

        /* Analytics Modal Styling */
        .modal-backdrop {
            display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            background: rgba(0, 0, 0, 0.75); backdrop-filter: blur(8px);
            z-index: 100; justify-content: center; align-items: center;
        }

        .modal-container {
            background: #0f172a; border: 1px solid var(--card-border);
            border-radius: 20px; width: 90%; max-width: 900px; max-height: 85vh;
            overflow-y: auto; padding: 2rem; box-shadow: 0 20px 50px rgba(0,0,0,0.6);
            display: flex; flex-direction: column; gap: 1.5rem;
        }

        .modal-header {
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid var(--card-border); padding-bottom: 1rem;
        }

        .analytics-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem;
        }

        .stat-card {
            background: rgba(255, 255, 255, 0.03); border: 1px solid var(--card-border);
            border-radius: 12px; padding: 1rem; text-align: center;
        }

        .stat-val { font-size: 1.5rem; font-weight: 700; color: #a7f3d0; margin-top: 0.25rem; }

        .recent-posts-list {
            display: flex; flex-direction: column; gap: 0.75rem; max-height: 250px; overflow-y: auto;
        }

        .recent-post-item {
            background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05);
            padding: 0.75rem; border-radius: 8px; display: flex; justify-content: space-between; align-items: center;
            font-size: 0.85rem;
        }

        .form-group { display: flex; flex-direction: column; gap: 0.5rem; }

        label {
            font-size: 0.85rem; font-weight: 600; color: var(--text-muted);
            text-transform: uppercase; letter-spacing: 0.05em;
        }

        textarea, input[type="text"], input[type="datetime-local"] {
            width: 100%; background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--card-border); border-radius: 10px;
            padding: 0.85rem; color: var(--text-main); font-family: inherit;
            font-size: 0.95rem; line-height: 1.5; outline: none;
            transition: border-color 0.2s ease;
        }

        textarea:focus, input[type="text"]:focus, input[type="datetime-local"]:focus {
            border-color: var(--accent-purple);
            box-shadow: 0 0 10px rgba(139, 92, 246, 0.2);
        }

        textarea { resize: vertical; min-height: 180px; }

        .action-bar { display: flex; gap: 1rem; justify-content: flex-end; margin-top: 1rem; }

        .empty-state { text-align: center; padding: 4rem 2rem; color: var(--text-muted); }
        .empty-icon { font-size: 3rem; margin-bottom: 1rem; opacity: 0.5; }

        .spinner {
            width: 18px; height: 18px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-top-color: #fff; border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }

        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>

    <header>
        <div class="brand">
            <div class="brand-logo">📸</div>
            <div class="brand-title">AI Instagram Studio</div>
        </div>
        <div class="header-badges">
            <button class="btn-analytics" onclick="openAnalyticsModal()">📊 Account Analytics</button>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>Connected: @skynendography</span>
            </div>
        </div>
    </header>

    <main>
        <div class="dashboard-grid">
            
            <!-- Left Sidebar: Photo Gallery -->
            <div class="card" id="leftCard">
                <div id="serverStatusBanner" class="server-status-banner">
                    [!] Server Offline / Connection Lost<br>
                    Please double click start_ui.bat to launch the Web Server!
                </div>

                <label for="fileUploadInput" class="btn btn-upload" style="cursor: pointer; display: flex;">
                    <span id="uploadBtnText">UPLOAD PHOTO TO QUEUE</span>
                </label>
                <input type="file" id="fileUploadInput" accept="image/*" style="position: absolute; width: 1px; height: 1px; opacity: 0; overflow: hidden; z-index: -1;">

                <div class="section-header">
                    <div class="section-title">Photos Queue</div>
                    <button class="btn btn-secondary" onclick="loadItems()" style="padding: 0.4rem 0.75rem; font-size: 0.8rem;">Refresh</button>
                </div>
                <div class="photo-list" id="photoList"></div>
            </div>

            <!-- Right Content: Post Editor & AI Assistant -->
            <div class="card" id="editorCard">
                <div id="emptyState" class="empty-state">
                    <div class="empty-icon">🎨</div>
                    <h3>Select a photo from the left queue</h3>
                    <p style="margin-top: 0.5rem; font-size: 0.9rem;">Choose an image or upload a new one to generate AI captions and publish to Instagram.</p>
                </div>

                <div id="editorContent" class="editor-container" style="display: none;">
                    <div class="preview-header">
                        <div>
                            <h2 id="currentFileName" style="font-family: 'Outfit', sans-serif; font-size: 1.25rem;">_MG_7648.png</h2>
                            <span id="currentStatusBadge" class="badge badge-unprocessed">Unprocessed</span>
                        </div>
                        <button class="btn btn-secondary" id="btnAiGen" onclick="generateAiContent()">
                            <span id="genBtnText">Generate AI Caption (Max 5 Viral Hashtags)</span>
                        </button>
                    </div>

                    <!-- Additional Context Input Box -->
                    <div class="form-group" style="background: rgba(139, 92, 246, 0.08); padding: 1rem; border-radius: 12px; border: 1px solid rgba(139, 92, 246, 0.2);">
                        <label style="color: #c084fc;">💡 Additional Context / Character Hint (Optional)</label>
                        <input type="text" id="userContextInput" placeholder="e.g., Hatsune Miku Racing 2023 / Genshin Impact Hutao / Custom Figure...">
                        <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.25rem;">If AI misidentifies the figure, type the exact character/series name here before clicking Generate!</div>
                    </div>

                    <!-- Telemetry Metrics Panel -->
                    <div class="telemetry-panel" id="telemetryPanel" style="display: none;">
                        <div class="telemetry-item">Tokens: <span class="telemetry-val" id="telTokens">0</span></div>
                        <div class="telemetry-item">Latency: <span class="telemetry-val" id="telLatency">0ms</span></div>
                        <div class="telemetry-item">Cost: <span class="telemetry-val" id="telCost">$0.0000</span></div>
                        <div class="telemetry-item">Search: <span class="telemetry-val" id="telEngine">SerpAPI / Hybrid</span></div>
                    </div>

                    <img id="imagePreview" class="image-preview-large" src="" alt="Preview">

                    <!-- Live Instagram Engagement Audit Panel -->
                    <div class="hashtag-search-box">
                        <label>Live Instagram Hashtag Engagement & Virality Audit</label>
                        <div class="hashtag-search-row">
                            <input type="text" id="hashtagSearchKeyword" placeholder="Keywords auto-extracted from photo...">
                            <button class="btn btn-secondary" id="btnSearchHashtag" onclick="searchViralHashtags()">Audit Hashtag Engagement</button>
                        </div>
                        <div id="hashtagResultsContainer" style="display: none;">
                            <div style="font-size: 0.85rem; color: var(--text-muted);">Top 5 Audited Virality Hashtags:</div>
                            <div class="hashtag-pills" id="hashtagPills"></div>
                            
                            <!-- Live Engagement Audit List -->
                            <div class="hashtag-rationale-list" id="hashtagRationaleList"></div>

                            <button class="btn btn-secondary" onclick="applyHashtagsToCaption()" style="margin-top: 0.5rem; font-size: 0.8rem;">Apply These 5 Hashtags to Caption</button>
                        </div>
                    </div>

                    <div class="form-group">
                        <label>Instagram Caption & Hashtags (@skynendography Natural Voice)</label>
                        <textarea id="captionText" placeholder="Click 'Generate AI Caption' or write your custom post content..."></textarea>
                    </div>

                    <div class="form-group">
                        <label>Scheduled Post Time (Optimal Peak Window)</label>
                        <input type="datetime-local" id="scheduleInput">
                    </div>

                    <!-- Action Bar with Separated Buttons for Immediate Publish vs Peak Schedule -->
                    <div class="action-bar">
                        <button class="btn btn-danger" onclick="deleteCurrentItem()">Delete Photo</button>
                        <button class="btn btn-secondary" onclick="saveDraftOnly()">Save Draft</button>
                        <button class="btn btn-now" id="btnPublishNow" onclick="publishPostNow()">
                            <span id="pubNowBtnText">Publish Immediately</span>
                        </button>
                        <button class="btn btn-schedule" id="btnSchedule" onclick="publishPostSchedule()">
                            <span id="schedBtnText">Schedule for Peak Time</span>
                        </button>
                    </div>
                </div>
            </div>

        </div>
    </main>

    <!-- Analytics Dashboard Modal -->
    <div class="modal-backdrop" id="analyticsModal">
        <div class="modal-container">
            <div class="modal-header">
                <h2 style="font-family: 'Outfit', sans-serif;">📊 @skynendography Analytics & Live Feed</h2>
                <button class="btn btn-secondary" onclick="closeAnalyticsModal()">Close ✕</button>
            </div>

            <div class="analytics-grid" id="analyticsSummaryGrid">
                <div class="stat-card"><div>Total Posts Analyzed</div><div class="stat-val" id="statTotalPosts">0</div></div>
                <div class="stat-card"><div>Total Likes</div><div class="stat-val" id="statTotalLikes">0</div></div>
                <div class="stat-card"><div>Avg Likes / Post</div><div class="stat-val" id="statAvgLikes">0</div></div>
                <div class="stat-card"><div>Avg Comments / Post</div><div class="stat-val" id="statAvgComments">0</div></div>
            </div>

            <div style="font-size: 0.9rem; font-weight: 600; margin-top: 0.5rem;">📱 Recent Published Posts Live Feed</div>
            <div class="recent-posts-list" id="recentPostsFeed"></div>

            <div style="font-size: 0.9rem; font-weight: 600; margin-top: 0.5rem;">🔥 Top Hashtags Ranking by Average Likes</div>
            <div class="hashtag-pills" id="topHashtagRanking"></div>

            <div style="font-size: 0.85rem; color: #a7f3d0; background: rgba(16, 185, 129, 0.1); padding: 0.85rem; border-radius: 10px; border: 1px solid rgba(16, 185, 129, 0.3);" id="styleVerdictBox">
                Loading style performance verdict...
            </div>
        </div>
    </div>

    <script>
        var currentItems = [];
        var selectedItem = null;
        var foundHashtagStr = "";

        async function loadItems() {
            try {
                const res = await fetch('/api/items');
                if (!res.ok) throw new Error("HTTP " + res.status);
                const data = await res.json();
                currentItems = data.items || [];
                var banner = document.getElementById('serverStatusBanner');
                if (banner) banner.style.display = 'none';
                renderPhotoList();
            } catch (err) {
                console.error("loadItems error:", err);
                var banner = document.getElementById('serverStatusBanner');
                if (banner) banner.style.display = 'block';
            }
        }

        async function openAnalyticsModal() {
            const modal = document.getElementById('analyticsModal');
            modal.style.display = 'flex';

            try {
                const res = await fetch('/api/account_analytics');
                const data = await res.json();
                if (data.success) {
                    document.getElementById('statTotalPosts').innerText = data.summary.total_posts;
                    document.getElementById('statTotalLikes').innerText = data.summary.total_likes.toLocaleString();
                    document.getElementById('statAvgLikes').innerText = data.summary.avg_likes_per_post;
                    document.getElementById('statAvgComments').innerText = data.summary.avg_comments_per_post;

                    const feedContainer = document.getElementById('recentPostsFeed');
                    feedContainer.innerHTML = '';
                    data.recent_posts.forEach(p => {
                        const div = document.createElement('div');
                        div.className = 'recent-post-item';
                        div.innerHTML = `
                            <div style="flex: 1; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; padding-right: 1rem;">
                                ${p.caption ? p.caption.slice(0, 70) + '...' : 'No caption'}
                            </div>
                            <div style="display: flex; gap: 1rem; align-items: center;">
                                <span style="color: #ec4899;">❤️ ${p.like_count}</span>
                                <span style="color: #93c5fd;">💬 ${p.comments_count}</span>
                                <a href="${p.permalink}" target="_blank" style="color: #c084fc; text-decoration: none;">View ↗</a>
                            </div>
                        `;
                        feedContainer.appendChild(div);
                    });

                    const tagContainer = document.getElementById('topHashtagRanking');
                    tagContainer.innerHTML = '';
                    data.hashtag_roi.forEach(t => {
                        const span = document.createElement('span');
                        span.className = 'hashtag-pill';
                        span.innerText = `${t.tag} (${t.avg_likes} avg likes)`;
                        tagContainer.appendChild(span);
                    });

                    document.getElementById('styleVerdictBox').innerText = '💡 Content Verdict: ' + data.style_comparison.verdict;
                } else {
                    alert('Failed to load analytics: ' + data.error);
                }
            } catch (err) {
                console.error('Analytics load error:', err);
            }
        }

        function closeAnalyticsModal() {
            document.getElementById('analyticsModal').style.display = 'none';
        }

        async function uploadPhoto(input) {
            console.log("[Studio UI] uploadPhoto triggered:", input ? input.files : null);
            if (!input || !input.files || input.files.length === 0) return;
            const file = input.files[0];
            console.log("[Studio UI] File selected:", file.name, file.size);

            const btnText = document.getElementById('uploadBtnText');
            if (btnText) btnText.innerHTML = '<div class="spinner"></div> UPLOADING PHOTO...';

            try {
                const formData = new FormData();
                formData.append('file', file);

                const res = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });

                if (!res.ok) {
                    const text = await res.text();
                    throw new Error("Server HTTP " + res.status + ": " + text);
                }

                const data = await res.json();
                console.log("[Studio UI] Response:", data);

                if (data.success) {
                    alert("[SUCCESS] Uploaded: " + data.filename);
                    await loadItems();
                    const found = currentItems.find(i => i.filename === data.filename);
                    if (found) {
                        selectItem(found);
                    } else if (currentItems.length > 0) {
                        selectItem(currentItems[currentItems.length - 1]);
                    }
                } else {
                    alert("Upload error: " + (data.error || "Unknown error"));
                }
            } catch (err) {
                console.error("[Studio UI Error]", err);
                alert("Upload failed: " + err.message);
            } finally {
                if (btnText) btnText.innerText = "UPLOAD PHOTO TO QUEUE";
                if (input) input.value = "";
            }
        }

        function renderPhotoList() {
            const container = document.getElementById('photoList');
            if (!container) return;
            container.innerHTML = '';

            if (!currentItems || currentItems.length === 0) {
                container.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 2rem 0;">No photos in ./input folder</div>';
                return;
            }

            currentItems.forEach(item => {
                const div = document.createElement('div');
                div.className = "photo-item " + (selectedItem && selectedItem.filename === item.filename ? 'active' : '');
                div.onclick = function() { selectItem(item); };

                let badgeClass = 'badge-unprocessed';
                let badgeText = 'Unprocessed';
                if (item.is_published) {
                    badgeClass = 'badge-published';
                    badgeText = 'Published';
                } else if (item.draft) {
                    badgeClass = 'badge-ready';
                    badgeText = 'Draft Ready';
                }

                div.innerHTML = `
                    <img src="${item.image_url}" class="photo-thumb" alt="${item.filename}">
                    <div class="photo-info">
                        <div class="photo-name">${item.filename}</div>
                        <span class="badge ${badgeClass}">${badgeText}</span>
                    </div>
                    <button class="photo-del-btn" title="Delete Photo" onclick="event.stopPropagation(); deleteSpecificItem('${item.filename}')">🗑️</button>
                `;
                container.appendChild(div);
            });
        }

        function renderHashtagBreakdown(breakdown) {
            const container = document.getElementById('hashtagRationaleList');
            if (!container) return;
            container.innerHTML = '';
            if (!breakdown || breakdown.length === 0) return;

            breakdown.forEach(item => {
                const card = document.createElement('div');
                card.className = 'hashtag-rationale-card';
                card.innerHTML = `
                    <div class="hashtag-card-header">
                        <span style="color: #c084fc; font-weight: 700; font-size: 0.9rem;">${item.tag}</span>
                        <span style="color: #34d399; font-weight: 600; font-size: 0.78rem; background: rgba(16,185,129,0.15); padding: 0.15rem 0.5rem; border-radius: 12px;">${item.score}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.78rem; color: #a7f3d0;">
                        <span>Tier: ${item.tier}</span>
                        <span>Est: ${item.engagement_est}</span>
                    </div>
                    <div style="font-size: 0.76rem; color: var(--text-muted); margin-top: 0.15rem;">${item.reason}</div>
                `;
                container.appendChild(card);
            });
        }

        function selectItem(item) {
            selectedItem = item;
            renderPhotoList();

            document.getElementById('emptyState').style.display = 'none';
            document.getElementById('editorContent').style.display = 'flex';

            document.getElementById('currentFileName').innerText = item.filename;
            document.getElementById('imagePreview').src = item.image_url;

            const badge = document.getElementById('currentStatusBadge');
            if (item.is_published) {
                badge.className = 'badge badge-published';
                badge.innerText = 'Published';
            } else if (item.draft) {
                badge.className = 'badge badge-ready';
                badge.innerText = 'Draft Ready';
            } else {
                badge.className = 'badge badge-unprocessed';
                badge.innerText = 'Unprocessed';
            }

            const draft = item.draft;
            if (draft) {
                document.getElementById('captionText').value = draft.caption || '';
                if (draft.scheduled_time) {
                    const dt = new Date(draft.scheduled_time);
                    const formatted = new Date(dt.getTime() - (dt.getTimezoneOffset() * 60000)).toISOString().slice(0, 16);
                    document.getElementById('scheduleInput').value = formatted;
                }
                if (draft.user_hint) {
                    document.getElementById('userContextInput').value = draft.user_hint;
                } else {
                    document.getElementById('userContextInput').value = '';
                }
                if (draft.keywords && draft.keywords.length > 0) {
                    document.getElementById('hashtagSearchKeyword').value = draft.keywords.join(' ');
                }
                if (draft.hashtag_breakdown) {
                    renderHashtagBreakdown(draft.hashtag_breakdown);
                    document.getElementById('hashtagResultsContainer').style.display = 'block';
                }
                if (draft.telemetry) {
                    document.getElementById('telemetryPanel').style.display = 'flex';
                    document.getElementById('telTokens').innerText = draft.telemetry.total_tokens || '0';
                    document.getElementById('telLatency').innerText = (draft.telemetry.total_latency_ms || 0) + 'ms';
                    document.getElementById('telCost').innerText = '$' + (draft.telemetry.total_cost_usd || 0.0002);
                    document.getElementById('telEngine').innerText = draft.telemetry.search_engine || 'Hybrid';
                }
            } else {
                document.getElementById('captionText').value = '';
                document.getElementById('scheduleInput').value = '';
                document.getElementById('userContextInput').value = '';
                document.getElementById('hashtagSearchKeyword').value = '';
                document.getElementById('telemetryPanel').style.display = 'none';
                document.getElementById('hashtagResultsContainer').style.display = 'none';
            }
        }

        async function generateAiContent() {
            if (!selectedItem) return;

            const userHint = document.getElementById('userContextInput').value.trim();

            const btn = document.getElementById('btnAiGen');
            const btnText = document.getElementById('genBtnText');
            btn.disabled = true;
            btnText.innerHTML = '<div class="spinner"></div> Running Autonomous 3-Pass AI Pipeline...';

            try {
                const res = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: selectedItem.filename, user_hint: userHint })
                });
                const data = await res.json();
                if (data.success && data.drafts && data.drafts.length > 0) {
                    const newDraft = data.drafts[0];
                    selectedItem.draft = newDraft;
                    selectItem(selectedItem);
                } else {
                    alert('Failed to generate AI content: ' + (data.error || 'Unknown error'));
                }
            } catch (err) {
                alert('Error generating AI content: ' + err.message);
            } finally {
                btn.disabled = false;
                btnText.innerText = 'Generate AI Caption (Max 5 Viral Hashtags)';
                loadItems();
            }
        }

        async function searchViralHashtags() {
            const kw = document.getElementById('hashtagSearchKeyword').value.trim();
            if (!kw) {
                alert('Please enter a keyword to research hashtags.');
                return;
            }

            const btn = document.getElementById('btnSearchHashtag');
            btn.disabled = true;
            btn.innerText = 'Auditing Instagram Virality...';

            try {
                const res = await fetch('/api/search_hashtags', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ keyword: kw })
                });
                const data = await res.json();
                if (data.success && data.hashtags) {
                    foundHashtagStr = data.hashtag_str;
                    const pillsContainer = document.getElementById('hashtagPills');
                    pillsContainer.innerHTML = '';
                    data.hashtags.forEach(tag => {
                        const span = document.createElement('span');
                        span.className = 'hashtag-pill';
                        span.innerText = tag;
                        pillsContainer.appendChild(span);
                    });
                    if (data.hashtag_breakdown) {
                        renderHashtagBreakdown(data.hashtag_breakdown);
                    }
                    document.getElementById('hashtagResultsContainer').style.display = 'block';
                } else {
                    alert('Hashtag search failed: ' + (data.error || 'Unknown error'));
                }
            } catch (err) {
                alert('Error searching hashtags: ' + err.message);
            } finally {
                btn.disabled = false;
                btn.innerText = 'Audit Hashtag Engagement';
            }
        }

        function applyHashtagsToCaption() {
            if (!foundHashtagStr) return;
            const textarea = document.getElementById('captionText');
            let text = textarea.value.trim();
            
            const lines = text.split('\\n');
            let mainLines = [];
            for (let l of lines) {
                if (!l.trim().startsWith('#')) {
                    mainLines.push(l);
                }
            }
            textarea.value = mainLines.join('\\n').trim() + '\\n\\n' + foundHashtagStr;
            alert('Updated caption with top 5 viral hashtags!');
        }

        async function saveDraftOnly() {
            if (!selectedItem || !selectedItem.draft) return;
            const caption = document.getElementById('captionText').value;
            const schedInput = document.getElementById('scheduleInput').value;
            const schedIso = schedInput ? new Date(schedInput).toISOString() : null;

            await fetch('/api/update_draft', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: selectedItem.draft.id, caption: caption, scheduled_time: schedIso })
            });
            alert('Draft saved successfully!');
            loadItems();
        }

        async function deleteSpecificItem(filename) {
            if (!confirm('Permanently delete photo ' + filename + ' from Queue?')) return;

            try {
                const res = await fetch('/api/delete_item', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: filename })
                });
                const data = await res.json();
                if (data.success) {
                    if (selectedItem && selectedItem.filename === filename) {
                        selectedItem = null;
                        document.getElementById('emptyState').style.display = 'block';
                        document.getElementById('editorContent').style.display = 'none';
                    }
                    await loadItems();
                } else {
                    alert('Delete failed: ' + data.error);
                }
            } catch (err) {
                alert('Error deleting item: ' + err.message);
            }
        }

        async function deleteCurrentItem() {
            if (!selectedItem) return;
            await deleteSpecificItem(selectedItem.filename);
        }

        async function publishPostNow() {
            if (!selectedItem || !selectedItem.draft) {
                alert('Please generate AI content first.');
                return;
            }
            if (!confirm('Publish this post IMMEDIATELY to Instagram?')) return;

            const btn = document.getElementById('btnPublishNow');
            const btnText = document.getElementById('pubNowBtnText');
            btn.disabled = true;
            btnText.innerHTML = '<div class="spinner"></div> Publishing Immediately...';

            try {
                await saveDraftOnly();
                const res = await fetch('/api/publish_now', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: selectedItem.draft.id })
                });
                const data = await res.json();
                if (data.success) {
                    alert('Success! Post published IMMEDIATELY to Instagram feed (ID: ' + data.published_id + ')');
                    selectedItem = null;
                    document.getElementById('emptyState').style.display = 'block';
                    document.getElementById('editorContent').style.display = 'none';
                    loadItems();
                } else {
                    alert('Failed to publish: ' + data.error);
                }
            } catch (err) {
                alert('Error publishing post: ' + err.message);
            } finally {
                btn.disabled = false;
                btnText.innerText = 'Publish Immediately';
            }
        }

        async function publishPostSchedule() {
            if (!selectedItem || !selectedItem.draft) {
                alert('Please generate AI content first.');
                return;
            }
            if (!confirm('SCHEDULE this post for Peak Time on Instagram?')) return;

            const btn = document.getElementById('btnSchedule');
            const btnText = document.getElementById('schedBtnText');
            btn.disabled = true;
            btnText.innerHTML = '<div class="spinner"></div> Scheduling for Peak Time...';

            try {
                await saveDraftOnly();
                const res = await fetch('/api/publish', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: selectedItem.draft.id })
                });
                const data = await res.json();
                if (data.success) {
                    alert('Success! Post scheduled for Peak Time on Instagram (ID: ' + data.published_id + ')');
                    selectedItem = null;
                    document.getElementById('emptyState').style.display = 'block';
                    document.getElementById('editorContent').style.display = 'none';
                    loadItems();
                } else {
                    alert('Failed to schedule: ' + data.error);
                }
            } catch (err) {
                alert('Error scheduling post: ' + err.message);
            } finally {
                btn.disabled = false;
                btnText.innerText = 'Schedule for Peak Time';
            }
        }

        document.addEventListener('DOMContentLoaded', function() {
            var leftCard = document.getElementById('leftCard');
            if (leftCard) {
                leftCard.addEventListener('dragover', function(e) {
                    e.preventDefault();
                    leftCard.style.borderColor = '#8b5cf6';
                });
                leftCard.addEventListener('dragleave', function(e) {
                    e.preventDefault();
                    leftCard.style.borderColor = 'var(--card-border)';
                });
                leftCard.addEventListener('drop', function(e) {
                    e.preventDefault();
                    leftCard.style.borderColor = 'var(--card-border)';
                    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                        var input = document.getElementById('fileUploadInput');
                        if (input) {
                            uploadPhoto({ files: e.dataTransfer.files });
                        }
                    }
                });
            }

            var uploadInput = document.getElementById('fileUploadInput');
            if (uploadInput) {
                uploadInput.addEventListener('change', function() {
                    uploadPhoto(this);
                });
            }

            loadItems();
            setInterval(loadItems, 3000);
        });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    print("\n==================================================")
    print(" [LAUNCH] AI Instagram Studio Web Dashboard")
    print(" [URL] http://localhost:5000")
    print("==================================================\n")
    app.run(host='0.0.0.0', port=5000, debug=False)

import os
import json
import uuid
from datetime import datetime
from config import DRAFTS_FILE

def load_drafts():
    if not os.path.exists(DRAFTS_FILE):
        return []
    try:
        with open(DRAFTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading drafts: {e}")
        return []

def save_drafts(drafts):
    with open(DRAFTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(drafts, f, ensure_ascii=False, indent=2)

def add_draft(image_filename, image_path, desc_analysis, web_report, caption, scheduled_time, image_user_description=""):
    drafts = load_drafts()
    # Check if a draft for this file already exists and is pending
    for d in drafts:
        if d.get("image_filename") == image_filename and d.get("status") == "pending":
            print(f"Draft for {image_filename} already exists. Updating existing draft.")
            d["desc_analysis"] = desc_analysis
            d["web_report"] = web_report
            d["caption"] = caption
            d["scheduled_time"] = scheduled_time
            d["updated_at"] = datetime.now().isoformat()
            save_drafts(drafts)
            return d

    draft = {
        "id": f"draft_{uuid.uuid4().hex[:8]}",
        "image_filename": image_filename,
        "image_path": image_path,
        "image_user_description": image_user_description,
        "desc_analysis": desc_analysis,
        "web_report": web_report,
        "caption": caption,
        "scheduled_time": scheduled_time,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    drafts.append(draft)
    save_drafts(drafts)
    return draft

def get_pending_drafts():
    drafts = load_drafts()
    return [d for d in drafts if d.get("status") == "pending"]

def update_draft(draft_id, new_caption=None, new_scheduled_time=None):
    drafts = load_drafts()
    for d in drafts:
        if d.get("id") == draft_id:
            if new_caption is not None:
                d["caption"] = new_caption
            if new_scheduled_time is not None:
                d["scheduled_time"] = new_scheduled_time
            d["updated_at"] = datetime.now().isoformat()
            save_drafts(drafts)
            return True
    return False

def mark_draft_published(draft_id):
    drafts = load_drafts()
    for d in drafts:
        if d.get("id") == draft_id:
            d["status"] = "published"
            d["published_at"] = datetime.now().isoformat()
            save_drafts(drafts)
            return True
    return False

def delete_draft(draft_id):
    drafts = load_drafts()
    drafts = [d for d in drafts if d.get("id") != draft_id]
    save_drafts(drafts)

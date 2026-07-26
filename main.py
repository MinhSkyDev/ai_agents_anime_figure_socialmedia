import os
import sys
import argparse
import io
import shutil
from PIL import Image

# Reconfigure stdout for Windows console to handle emojis without crashing
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import INPUT_FOLDER, PUBLISHED_FOLDER, DRAFTS_FILE
from helpers.ai_utils import analyze_image, web_context_report, generate_social_post
from helpers.schedule_calculator import get_calculated_schedule_for_new_post
from helpers.local_queue import get_pending_drafts, add_draft, mark_draft_published, delete_draft, update_draft
from helpers.post_scheduler import schedule_or_publish_to_instagram

def resize_image_for_analysis(image_path, max_size=(1024, 1024)):
    """Opens local image and resizes it in memory for OpenAI API vision analysis."""
    with Image.open(image_path) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail(max_size)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        return buffer

def generate_drafts():
    """Scans input folder and generates AI captions & optimal schedules into drafts.json."""
    if not os.path.exists(INPUT_FOLDER):
        os.makedirs(INPUT_FOLDER, exist_ok=True)
        print(f"[INFO] Created input folder at {INPUT_FOLDER}. Please place photos there.")
        return []

    valid_exts = ('.jpg', '.jpeg', '.png', '.webp')
    image_files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(valid_exts)]

    if not image_files:
        print(f"[INFO] No image files found in {INPUT_FOLDER}")
        return []

    print(f"\n[INFO] Found {len(image_files)} image(s) in {INPUT_FOLDER}. Processing AI pipeline...\n")
    
    generated_drafts = []
    pending_drafts = get_pending_drafts()

    for filename in image_files:
        image_path = os.path.join(INPUT_FOLDER, filename)
        
        # Check if draft already generated
        already_drafted = False
        for p in pending_drafts:
            if p.get("image_filename") == filename:
                print(f"[SKIP] Draft already exists for {filename}")
                generated_drafts.append(p)
                already_drafted = True
                break

        if already_drafted:
            continue

        print(f"--------------------------------------------------")
        print(f"[PROCESSING] {filename}")
        try:
            # 1. Vision Analysis
            print("  |-- 1. Running GPT-4o Vision Analysis...")
            img_buffer = resize_image_for_analysis(image_path)
            image_user_description = f"Toy photography photo named {filename}"
            desc_json = analyze_image(img_buffer, image_user_description)

            # 2. SerpAPI Lore Search
            print("  |-- 2. Searching Google & Lore via SerpAPI...")
            report, _ = web_context_report(desc_json, image_user_description)

            # 3. Social Post Generation
            print("  |-- 3. Generating Instagram Caption & Hashtags...")
            post_content = generate_social_post(desc_json, report)

            # 4. Calculate Optimal Schedule
            print("  |-- 4. Calculating Optimal Posting Schedule...")
            pending_current = get_pending_drafts()
            scheduled_time = get_calculated_schedule_for_new_post(pending_current)

            # 5. Save Draft
            draft = add_draft(
                image_filename=filename,
                image_path=image_path,
                desc_analysis=desc_json,
                web_report=report,
                caption=post_content,
                scheduled_time=scheduled_time,
                image_user_description=image_user_description
            )
            generated_drafts.append(draft)
            print(f"[OK] Draft created for {filename}! Suggested Schedule: {scheduled_time}")

        except Exception as e:
            print(f"[FAIL] Failed to process {filename}: {e}")

    return generated_drafts

def safe_print(text):
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', errors='replace').decode('ascii'))

def display_preview():
    """Displays terminal preview of generated drafts for user review."""
    pending = get_pending_drafts()
    if not pending:
        print("\n[INFO] No pending drafts to preview.")
        return

    print("\n==================================================")
    print("      DRAFT POSTS PREVIEW (DUYET BAI DANG)")
    print("==================================================\n")

    for idx, d in enumerate(pending, 1):
        print(f"--------------------------------------------------")
        print(f"BAI NHAP #{idx} | ID: {d['id']}")
        print(f"File anh: {d['image_filename']}")
        print(f"Lich dang de xuat: {d['scheduled_time']}")
        print(f"--------------------------------------------------")
        print(f"CAPTION & HASHTAGS:\n")
        safe_print(d['caption'])
        print(f"--------------------------------------------------\n")

def interactive_preview():
    """Interactive CLI to review, edit, approve or skip drafts."""
    while True:
        pending = get_pending_drafts()
        if not pending:
            print("\n[INFO] Tat ca bai nhap da duoc xu ly hoac danh sach nhap trong!")
            break

        display_preview()
        print("TUY CHON DANG CHO BAN:")
        print("   [P] Dang/Len lich bai dau tien len Instagram")
        print("   [E] Sua Caption bai dau tien")
        print("   [D] Xoa bai nhap dau tien")
        print("   [Q] Thoat (Giu nguyen bai nhap de xem sau)")
        
        choice = input("\nNhap lua chon cua ban [P/E/D/Q]: ").strip().lower()

        if choice == 'p':
            target = pending[0]
            print(f"\n[POSTING] Dang tien hanh dang bai {target['image_filename']} len Instagram...")
            try:
                pub_id = schedule_or_publish_to_instagram(
                    image_path=target['image_path'],
                    caption=target['caption'],
                    scheduled_time_iso=target['scheduled_time']
                )
                mark_draft_published(target['id'])
                
                # Move image to published folder
                if os.path.exists(target['image_path']):
                    dest = os.path.join(PUBLISHED_FOLDER, target['image_filename'])
                    shutil.move(target['image_path'], dest)
                    print(f"[MOVED] Da di chuyen {target['image_filename']} sang {PUBLISHED_FOLDER}")
                
                print(f"[OK] Hoan tat dang bai! ID: {pub_id}\n")
            except Exception as e:
                print(f"[FAIL] Loi dang bai: {e}\n")

        elif choice == 'e':
            target = pending[0]
            print(f"\n[EDIT] Chinh sua Caption cho {target['image_filename']}:")
            print("Nhap Caption moi (Nhap END o dong moi de hoan tat):")
            lines = []
            while True:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            new_caption = "\n".join(lines).strip()
            if new_caption:
                update_draft(target['id'], new_caption=new_caption)
                print("[OK] Da cap nhat Caption moi!\n")

        elif choice == 'd':
            target = pending[0]
            delete_draft(target['id'])
            print(f"[DELETED] Da xoa bai nhap {target['image_filename']}\n")

        elif choice == 'q':
            print("[EXIT] Da thoat giao dien Preview. Bai nhap cua ban da duoc luu an toan trong drafts.json.")
            break
        else:
            print("Lua chon khong hop le, vui long thu lai.")

def main():
    parser = argparse.ArgumentParser(description="AI Instagram Auto-Poster & Draft Manager")
    parser.add_argument('--generate-only', action='store_true', help='Only generate drafts from input folder without interactive preview')
    parser.add_argument('--preview-only', action='store_true', help='Only open interactive preview of existing drafts')
    args = parser.parse_args()

    if args.preview_only:
        interactive_preview()
    elif args.generate_only:
        generate_drafts()
        display_preview()
    else:
        generate_drafts()
        display_preview()

if __name__ == '__main__':
    main()
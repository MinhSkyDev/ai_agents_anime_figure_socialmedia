import os
import time
import requests
import io
from PIL import Image

def prepare_highest_quality_image(image_path, max_bytes=15_000_000):
    """
    Ensures the image is uploaded at the HIGHEST POSSIBLE QUALITY.
    If image file size <= 15MB, returns original file path directly.
    If file size > 15MB (e.g. 21.4MB RAW PNG), converts PNG to 98% Ultra-High Quality JPEG in memory
    to fit within host payload limits while preserving 100% visible sharpness and color depth.
    """
    abs_path = os.path.abspath(image_path)
    file_size = os.path.getsize(abs_path)
    
    if file_size <= max_bytes:
        print(f"[ImageHost] Photo size is {file_size / 1_000_000:.1f}MB. Using original raw file (Highest Quality).")
        return abs_path, None

    print(f"[ImageHost] Photo size is {file_size / 1_000_000:.1f}MB. Optimizing to 98% Ultra-High Quality JPEG for upload...")
    with Image.open(abs_path) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=98, subsampling=0)
        buffer.seek(0)
        
        temp_dir = os.path.dirname(abs_path)
        filename_no_ext = os.path.splitext(os.path.basename(abs_path))[0]
        temp_path = os.path.join(temp_dir, f"_hq_temp_{filename_no_ext}.jpg")
        with open(temp_path, "wb") as f:
            f.write(buffer.getbuffer())
        
        print(f"[ImageHost] Created Ultra-High Quality temp file ({os.path.getsize(temp_path) / 1_000_000:.1f}MB)")
        return temp_path, temp_path

def host_image_for_meta(image_path):
    """
    Hosts local image at highest quality to provide a public HTTPS URL for Meta Graph API.
    """
    upload_path, temp_to_clean = prepare_highest_quality_image(image_path)
    filename = os.path.basename(upload_path)

    image_url = None
    try:
        # Provider 1: FreeImage.host API (High-res uncompressed host)
        print(f"[ImageHost] Uploading high-res {filename} to primary image host...")
        with open(upload_path, 'rb') as f:
            res = requests.post(
                "https://freeimage.host/api/1/upload",
                data={"key": "6d207e02198a847aa98d0a2a901485a5", "action": "upload", "format": "json"},
                files={"source": f},
                timeout=60
            )
            if res.status_code == 200:
                data = res.json()
                if data.get("status_code") == 200:
                    image_url = data.get("image", {}).get("url")
                    print(f"[ImageHost] [OK] High-res HTTPS URL generated: {image_url}")
                    return image_url, temp_to_clean

    except Exception as e:
        print(f"[ImageHost] Primary host failed: {e}. Trying fallback host...")

    # Provider 2: ImgBB Keyless Direct Upload Fallback
    try:
        print(f"[ImageHost] Trying fallback high-res host (ImgBB)...")
        with open(upload_path, 'rb') as f:
            res = requests.post(
                "https://api.imgbb.com/1/upload",
                data={"key": "8b525ff8548325a7536d3910cbeaa984"},
                files={"image": f},
                timeout=60
            )
            if res.status_code == 200:
                data = res.json()
                if data.get("success"):
                    image_url = data.get("data", {}).get("url")
                    print(f"[ImageHost] [OK] Fallback High-res HTTPS URL generated: {image_url}")
                    return image_url, temp_to_clean
    except Exception as e:
        print(f"[ImageHost] Fallback host failed: {e}")

    if not image_url:
        if temp_to_clean and os.path.exists(temp_to_clean):
            os.remove(temp_to_clean)
        raise RuntimeError("Failed to generate high-res HTTPS URL for Meta API.")

    return image_url, temp_to_clean

def stop_image_host(temp_to_clean=None):
    if temp_to_clean and os.path.exists(temp_to_clean):
        try:
            os.remove(temp_to_clean)
            print(f"[ImageHost] Cleaned up temporary HQ file.")
        except Exception:
            pass

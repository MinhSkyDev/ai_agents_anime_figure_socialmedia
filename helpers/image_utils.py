import requests, io
from PIL import Image
import logging

def download_and_resize(url, max_size=1024, max_bytes=1_000_000):
    resp = requests.get(url)
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content))
    if img.mode == "RGBA":
        img = img.convert("RGB")
    if len(resp.content) > max_bytes or max(img.size) > max_size:
        ratio = min(max_size / max(img.size), 1)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    buffer.seek(0)
    return buffer

import time
import requests
from datetime import datetime, timedelta
from config import ACCESS_TOKEN, IG_USER_ID, PAGE_ID
from helpers.image_host import host_image_for_meta, stop_image_host

GRAPH_BASE = "https://graph.facebook.com/v18.0"

def get_page_access_token():
    if not PAGE_ID or not ACCESS_TOKEN:
        return None
    url = f"{GRAPH_BASE}/{PAGE_ID}"
    res = requests.get(url, params={'fields': 'access_token', 'access_token': ACCESS_TOKEN})
    if res.status_code == 200:
        return res.json().get('access_token')
    return ACCESS_TOKEN

def wait_for_container_ready(container_id, max_retries=12, delay=5):
    """Poll Instagram container status until status_code is FINISHED."""
    url = f"{GRAPH_BASE}/{container_id}"
    params = {'fields': 'status_code,status', 'access_token': ACCESS_TOKEN}
    
    for attempt in range(max_retries):
        res = requests.get(url, params=params)
        if res.status_code == 200:
            data = res.json()
            status_code = data.get('status_code')
            print(f"[Instagram] Container {container_id} status: {status_code} (attempt {attempt+1}/{max_retries})")
            if status_code == 'FINISHED':
                return True
            elif status_code == 'ERROR':
                raise RuntimeError(f"Instagram Media Container processing failed: {data}")
        time.sleep(delay)
    
    raise TimeoutError("Timed out waiting for Instagram Media Container to finish processing.")

def schedule_or_publish_to_instagram(image_path, caption, scheduled_time_iso=None):
    """
    Creates an Instagram Media Container and publishes or schedules it via Meta Graph API.
    - Highest Image Quality preserved.
    - Handles scheduled_publish_time container parameter correctly.
    """
    # 1. Host local image to get direct public HTTPS URL
    public_url, temp_to_clean = host_image_for_meta(image_path)

    try:
        is_scheduled = False
        scheduled_timestamp = None

        if scheduled_time_iso:
            try:
                dt = datetime.fromisoformat(scheduled_time_iso)
                now = datetime.now(dt.tzinfo)
                # Instagram API requirement: scheduled time must be at least 15 min in the future
                if dt > now + timedelta(minutes=15):
                    is_scheduled = True
                    scheduled_timestamp = int(dt.timestamp())
                    print(f"[Instagram] Schedule mode active. Target timestamp: {scheduled_timestamp} ({dt.strftime('%Y-%m-%d %H:%M:%S %Z')})")
            except Exception as e:
                print(f"[Instagram] Schedule parsing fallback to immediate post: {e}")

        # 2. Create Instagram Container
        container_url = f"{GRAPH_BASE}/{IG_USER_ID}/media"
        container_params = {
            'image_url': public_url,
            'caption': caption,
            'access_token': ACCESS_TOKEN
        }

        # Meta API Requirement: scheduled_publish_time must be sent during container creation
        if is_scheduled and scheduled_timestamp:
            container_params['scheduled_publish_time'] = scheduled_timestamp

        print(f"[Instagram] Creating Media Container at Meta Graph API...")
        c_res = requests.post(container_url, data=container_params)
        if c_res.status_code != 200:
            raise RuntimeError(f"Failed to create Instagram Container: {c_res.status_code} {c_res.text}")
        
        container_id = c_res.json().get('id')
        print(f"[Instagram] ✅ Container created! ID: {container_id}")

        # 3. Wait for Media Container to finish processing
        wait_for_container_ready(container_id)

        # 4. Publish or Schedule
        if is_scheduled:
            print(f"[SUCCESS] [Instagram] Post scheduled on Meta servers! It will automatically go live at {scheduled_time_iso}")
            return container_id
        else:
            print(f"[Instagram] Executing immediate publish call...")
            publish_url = f"{GRAPH_BASE}/{IG_USER_ID}/media_publish"
            publish_params = {
                'creation_id': container_id,
                'access_token': ACCESS_TOKEN
            }
            p_res = requests.post(publish_url, data=publish_params)
            if p_res.status_code != 200:
                raise RuntimeError(f"Failed to publish Instagram post: {p_res.status_code} {p_res.text}")
            published_id = p_res.json().get('id')
            print(f"[SUCCESS] [Instagram] Post published live to feed! Media ID: {published_id}")
            return published_id

    finally:
        stop_image_host(temp_to_clean)
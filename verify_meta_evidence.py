import os
import requests
from dotenv import load_dotenv

load_dotenv()

access_token = os.getenv("FB_ACCESS_TOKEN")
page_id = os.getenv("FB_PAGE_ID")
ig_user_id = os.getenv("IG_USER_ID")

print("=== META GRAPH API LIVE EVIDENCE DIAGNOSTIC ===\n")

# 1. Debug Access Token & Permissions
token_debug_url = f"https://graph.facebook.com/debug_token"
res_token = requests.get(token_debug_url, params={"input_token": access_token, "access_token": access_token})

if res_token.status_code == 200:
    token_data = res_token.json().get("data", {})
    print("1. ACCESS TOKEN STATUS & PERMISSIONS:")
    print(f"   - Is Valid: {token_data.get('is_valid')}")
    print(f"   - App ID: {token_data.get('app_id')}")
    print(f"   - Expires At: {token_data.get('expires_at')} (0 means long-lived token / no expiry)")
    print(f"   - Granted Scopes/Permissions: {token_data.get('scopes')}\n")

# 2. Instagram Account Metadata Verification
ig_url = f"https://graph.facebook.com/v18.0/{ig_user_id}"
res_ig = requests.get(ig_url, params={
    "fields": "id,username,name,profile_picture_url,media_count,followers_count",
    "access_token": access_token
})

if res_ig.status_code == 200:
    ig_data = res_ig.json()
    print("2. INSTAGRAM ACCOUNT LIVE DATA:")
    print(f"   - IG User ID: {ig_data.get('id')}")
    print(f"   - Username: @{ig_data.get('username')}")
    print(f"   - Name: {ig_data.get('name')}")
    print(f"   - Media Count: {ig_data.get('media_count')}")
    print(f"   - Followers Count: {ig_data.get('followers_count')}\n")

# 3. Facebook Page Token & Publishing Capability
page_url = f"https://graph.facebook.com/v18.0/{page_id}"
res_page = requests.get(page_url, params={
    "fields": "id,name,access_token,tasks",
    "access_token": access_token
})

if res_page.status_code == 200:
    page_data = res_page.json()
    print("3. FACEBOOK PAGE PUBLISHING STATUS:")
    print(f"   - Page ID: {page_data.get('id')}")
    print(f"   - Page Name: {page_data.get('name')}")
    print(f"   - Administrative Tasks: {page_data.get('tasks')}\n")

print("=== END DIAGNOSTIC ===")

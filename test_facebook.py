import os
from dotenv import load_dotenv
import requests

# Load environment variables from .env
load_dotenv()

# Facebook and Instagram API setup
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
IG_USER_ID = os.getenv("IG_USER_ID")
ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN")

# Base URLs
FB_GRAPH_BASE = "https://graph.facebook.com/v15.0"


def get_page_access_token(page_id):
    url = f'https://graph.facebook.com/v18.0/{page_id}'
    params = {
        'fields': 'access_token',
        'access_token': ACCESS_TOKEN
    }
    response = requests.get(url, params=params)
    data = response.json()
    if 'access_token' in data:
        return data['access_token']
    else:
        raise Exception(f"Could not fetch page access token: {data}")

def test_facebook_page():
    """Test Facebook Page API Access."""
    print("Testing Facebook Page API Access...")
    fb_feed_url = f"{FB_GRAPH_BASE}/{FB_PAGE_ID}/feed?access_token={get_page_access_token(FB_PAGE_ID)}"
    response = requests.get(fb_feed_url)

    if response.status_code == 200:
        print("✅ Facebook Page API is working!")
        print(f"Recent Posts: {response.json().get('data', [])}")
    else:
        print("❌ Facebook Page API failed.")
        print(f"Error: {response.status_code}, {response.json()}")

def test_instagram_account():
    """Test Instagram Business Account API Access."""
    print("Testing Instagram Business Account API Access...")
    ig_media_url = f"{FB_GRAPH_BASE}/{IG_USER_ID}/media?access_token={ACCESS_TOKEN}"
    response = requests.get(ig_media_url)

    if response.status_code == 200:
        print("✅ Instagram API is working!")
        print(f"Recent Media: {response.json().get('data', [])}")
    else:
        print("❌ Instagram API failed.")
        print(f"Error: {response.status_code}, {response.json()}")

if __name__ == "__main__":
    print("Starting API Validation Tests...\n")
    print(FB_PAGE_ID)
    if not all([FB_PAGE_ID, IG_USER_ID, ACCESS_TOKEN]):
        print("❌ Missing environment variables. Ensure FB_PAGE_ID, IG_USER_ID, and FB_ACCESS_TOKEN are set in the .env file.")
    else:
        test_facebook_page()
        print("\n")
        test_instagram_account()

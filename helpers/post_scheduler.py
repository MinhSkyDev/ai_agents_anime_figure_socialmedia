from datetime import datetime
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.page import Page
from facebook_business.adobjects.iguser import IGUser
from config import FB_APP_ID, FB_APP_SECRET, ACCESS_TOKEN, IG_USER_ID, PAGE_ID
import logging
import requests

def init_facebook():
    page_token = requests.get(f"https://graph.facebook.com/v18.0/{PAGE_ID}?fields=access_token&access_token={ACCESS_TOKEN}").json().get("access_token")
    FacebookAdsApi.init(FB_APP_ID, FB_APP_SECRET, page_token)

def schedule_post(post_text, image_url, scheduled_time):
    ig_media = IGUser(IG_USER_ID).create_media(params={"image_url": image_url, "caption": post_text})
    IGUser(IG_USER_ID).create_media_publish(params={"creation_id": ig_media.get('id'), "scheduled_publish_time": int(scheduled_time.timestamp()), "published": False})
    Page(PAGE_ID).create_feed(params={"message": post_text, "link": image_url, "scheduled_publish_time": int(scheduled_time.timestamp()), "published": False})
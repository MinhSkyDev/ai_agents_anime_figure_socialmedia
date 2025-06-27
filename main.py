import logging
from datetime import datetime, timedelta
from helpers.sheet_utils import fetch_image_url, archive_image_data, fetch_image_description
from helpers.image_utils import download_and_resize
from helpers.ai_utils import analyze_image, web_context_report, generate_social_post, plan_post_timing
from helpers.post_scheduler import init_facebook, schedule_post
from helpers.email_utils import send_email

logging.basicConfig(level=logging.INFO)

def run_daily_workflow():
    try:
        url = fetch_image_url()
        image_user_description = fetch_image_description()
        img_buffer = download_and_resize(url)
        desc = analyze_image(img_buffer, image_user_description)
        report, _ = web_context_report(desc, image_user_description)
        print(report)
        post_content = generate_social_post(desc, report)

        #Social Media Post
        scheduled_time = datetime.now() + timedelta(hours=1)
        init_facebook()
        schedule_post(post_content, url, scheduled_time)
        archive_image_data(url)

        #Summarize - Send Email
        summary = f"URL: {url}\n\nDesc: {desc}\n\nPost:\n{post_content}"
        send_email(summary)
    except Exception as e:
        logging.exception("Workflow failed")

if __name__ == '__main__':
    run_daily_workflow()
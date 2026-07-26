import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FOLDER = os.path.join(BASE_DIR, 'input')
PUBLISHED_FOLDER = os.path.join(BASE_DIR, 'published')
DRAFTS_FILE = os.path.join(BASE_DIR, 'drafts.json')

# Create directories if they do not exist
os.makedirs(INPUT_FOLDER, exist_ok=True)
os.makedirs(PUBLISHED_FOLDER, exist_ok=True)

# AI & Search Keys
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
SERPAPI_KEY = os.getenv('SERPAPI_KEY')

# Meta / Instagram API Credentials
FB_APP_ID = os.getenv('FB_APP_ID')
FB_APP_SECRET = os.getenv('FB_APP_SECRET')
ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
IG_USER_ID = os.getenv('IG_USER_ID')
PAGE_ID = os.getenv('FB_PAGE_ID')

# Timezone for scheduling
TIMEZONE = 'Asia/Ho_Chi_Minh'
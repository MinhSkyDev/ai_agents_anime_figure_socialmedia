🤖 AI Toy Photography Post Scheduler

An automated AI workflow to analyze toy figure images, enrich them with anime/manga context, generate compelling Instagram captions with hashtags, and schedule posts via Meta Graph API.

---

📌 Features

- 🧠 Image Analysis – Detects toy type, characters, origin anime/manga/game, mood, and scene story.
- 🌐 Web Context Enrichment – Uses SerpAPI to extract deep contextual info from fan sites, wikis, and plot summaries.
- 📝 Instagram Caption Generation – Uses OpenAI to generate chain-of-thought captions with emoji, storylines, and relevant hashtags.
- 🕖 Post Scheduling – Automatically schedules posts to Facebook and Instagram via Meta Graph API.
- 📊 Google Sheets Integration – Fetch and archive image URLs from a spreadsheet.
- ✉️ Email Summary – Sends post summary reports to your email daily.

```plaintext
├── main.py                        # Main workflow script
├── config.py                      # Environment variables and constants
├── prompts/
│   ├── analysis_few_shot.txt     # Image analysis few-shot examples
│   ├── analyze_follow_up.txt     # Image follow-up prompt template
│   ├── generation_prompt.txt     # Instagram caption generation prompt
│   └── plan_post_timing.txt      # Caption planning prompt
├── helpers/
│   ├── ai_utils.py               # OpenAI, SerpAPI interaction
│   ├── image_utils.py            # Image download & resize
│   ├── sheet_utils.py            # Google Sheets integration
│   ├── email_utils.py            # Email summary utility
│   └── post_scheduler.py         # Facebook & Instagram posting
```

⚙️ Requirements

- Python 3.9+
- API Keys:
  - OpenAI API Key
  - SerpAPI Key
  - Google Service Account JSON
  - Meta Graph API credentials

Install dependencies:

pip install -r requirements.txt

---

🚀 Usage

python main.py

By default, it processes the next image URL from Google Sheets, generates content, and sends an email summary. You can uncomment the scheduler block in main.py to run this daily.

---

🔒 Environment Variables

Create a .env file with:

OPENAI_API_KEY=your_openai_key
SERPAPI_KEY=your_serpapi_key
GOOGLE_SERVICE_ACCOUNT_JSON=path/to/service.json
SPREADSHEET_ID=your_sheet_id
FB_APP_ID=your_fb_app_id
FB_APP_SECRET=your_fb_secret
FB_ACCESS_TOKEN=your_long_lived_token
IG_USER_ID=your_ig_user_id
FB_PAGE_ID=your_fb_page_id
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
EMAIL_USER=your@email.com
EMAIL_PASS=your_email_password

---

🧪 Example Output

Generated Caption:

🌸 A quiet moment before the storm.  
Even the smallest heroes carry the biggest burdens.  
#TOMsenpainoticeme #toyphotography #nendoroid #nendography #vietnamesenendoroid #animevibes

---

📬 Credits

Created by Minh Quang Le  
Uses OpenAI GPT-4o, SerpAPI, and Meta Graph API.

---

📄 License

MIT License

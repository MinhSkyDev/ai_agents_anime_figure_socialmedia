# PROJECT CONTEXT: AI Instagram Studio (@skynendography)

## 📌 Project Overview
**AI Instagram Studio** is a specialized, production-ready AI Agent Harness and Web Studio designed for toy & anime figure photography content creation and publishing on Instagram (@skynendography).

---

## 🏗️ Architecture & Core Components

### 1. 🤖 Autonomous 3-Pass AI Pipeline (`helpers/agent_tools.py`)
- **Pass 1: Vision Agent (Character Recognition)**
  - Analyzes figure photo + optional user hint to predict exact character, anime/game series, outfit, pose, and figure line (Nendoroid, Scale, Figma).
- **Pass 2: 2-Stage Autonomous Web Search Agent (`helpers/web_search_engine.py`)**
  - **Stage 1 (Lore Query)**: Searches `myfigurecollection.net`, `goodsmile.info`, and wikis for official figure specifications, franchise lore, and release details.
  - **Stage 2 (Hashtags Query)**: Searches active collector hashtags and Instagram explore trends.
  - **Hybrid Dual Engine**: Primary `SerpAPI` (Google Search Indexing) + zero-latency `DuckDuckGo` fallback.
- **Pass 3: Copywriter Synthesis (Human Collector Voice)**
  - Writes in an **Authentic Human Collector Voice** (strictly forbidding robotic AI buzzwords like *"electric energy"*, *"miniature perfection"*, *"high-octane"*).
  - Structure: 1-Liner Casual Hook + 2-Sentence Photo Story + 1-Sentence CTA Question + Exactly 5 Viral Hashtags (<250 chars).

### 2. 🛡️ Harness Evaluator & Telemetry (`helpers/harness.py`)
- **Hashtag Evaluator**: Evaluates and sanitizes caption hashtags to guarantee strictly 5 high-impact hashtags.
- **5-Tier Credibility Rationale Breakdown**:
  - `🔥 Character Core Anchor`: Search-intent tag for character fans.
  - `🌐 Niche Community Core`: High-engagement collector tag.
  - `🚀 Explore Discovery`: Broad category tag for Instagram Explore algorithm.
  - `🏷️ Brand & Line Tag`: Official manufacturer hashtag.
  - `⚡ Micro-Niche High-Win`: Low competition tag ensuring top search rank.
- **Telemetry Logger**: Records prompt/completion tokens, latency (ms), estimated cost (USD), and search engine used.

### 3. 📤 Post Scheduler & Ultra-Quality Image Host
- **Image Host (`helpers/image_host.py`)**: Converts >15MB raw images to 98% Ultra-High Quality JPEG (`subsampling=0`) in memory, ensuring 100% visible sharpness and zero file size rejection.
- **Post Scheduler (`helpers/post_scheduler.py`)**: Integrates Meta Graph API (`/{ig-user-id}/media`). Separates Immediate Publish vs Scheduled Peak Time Publish (passes `scheduled_publish_time` during container creation).

### 4. 💻 Web Dashboard (`app.py`)
- Flask Web Dashboard (`http://localhost:5000`) with responsive glassmorphism dark UI.
- **Key Features**:
  - Drag & drop image upload into `./input/`.
  - **`💡 Additional Context / Character Hint (Optional)`** field to override AI guesses for custom/rare figures.
  - Interactive Hashtag Research & Rationale Panel.
  - **`🗑️ Delete Photo`** button on each item in Photo Queue.
  - Separated **Publish Immediately** vs **Schedule for Peak Time** buttons.

---

## 🛠️ Key File Sitemap & Responsibilities

| File Path | Role & Description |
| :--- | :--- |
| `app.py` | Main Flask server, API endpoints, and complete Web UI template |
| `config.py` | Environment config, API keys (OpenAI, Meta Graph, SerpAPI, ImgBB) |
| `helpers/agent_tools.py` | Autonomous 3-Pass AI Pipeline & Human Copywriter Agent |
| `helpers/web_search_engine.py` | Hybrid Search Engine (SerpAPI + DuckDuckGo fallback) |
| `helpers/post_scheduler.py` | Meta Graph API Instagram Publishing & Peak Schedule Calculator |
| `helpers/image_host.py` | Ultra-High Quality Image Upload Manager |
| `helpers/harness.py` | Harness Evaluator & Telemetry Logger |
| `helpers/local_queue.py` | Local draft queue database manager (`data/drafts.json`) |
| `prompts/generation_prompt.txt` | System prompt with Human Collector tone rules & AI buzzword blacklist |
| `run_studio.py` | 1-Click Python launcher |
| `start_ui.bat` | 1-Click Windows batch launcher |

---

## 🔌 Web API Endpoints

- `GET /api/items`: Returns queue items from `./input/` and `./published/` with draft state.
- `POST /api/upload`: Uploads external photo to `./input/`.
- `POST /api/generate`: Runs 3-Pass AI Pipeline (accepts optional `user_hint`).
- `POST /api/search_hashtags`: Researches top 5 hashtags with 5-Tier rationale.
- `POST /api/update_draft`: Saves updated caption/schedule time.
- `POST /api/delete_item`: Permanently deletes photo file and draft entry.
- `POST /api/publish_now`: Publishes post IMMEDIATELY to Instagram.
- `POST /api/publish`: Schedules post for Peak Time on Instagram.

---

## 🚀 How to Run & Maintain

Double-click **`start_ui.bat`** (or run `python run_studio.py` in terminal).
The web dashboard opens at `http://localhost:5000`.

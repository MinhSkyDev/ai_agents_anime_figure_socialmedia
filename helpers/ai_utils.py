from openai import OpenAI
from config import OPENAI_API_KEY, SERPAPI_KEY
from serpapi import GoogleSearch
import base64
import json
import logging

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_image(buffer, image_user_description):
    with open('prompts/analysis_few_shot.txt', 'r', encoding='utf-8') as f:
        examples = f.read()

    with open('prompts/analyze_follow_up.txt', 'r', encoding='utf-8') as f:
        follow_up_prompt = f.read()

    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    user_context_prompt = f"The user provided the following context for the image: {image_user_description}"

    # Optimized image_url with detail="low" to reduce vision token costs by ~80%
    messages = [
        {"role": "system", "content": examples},
        {"role": "user", "content": user_context_prompt},
        {"role": "user", "content": [
            {"type": "text", "text": follow_up_prompt},
            {"type": "image_url", "image_url": {
                "url": f"data:image/jpeg;base64,{encoded}",
                "detail": "low"  # Fast, low-cost vision evaluation (only 85 tokens!)
            }}
        ]}
    ]

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=1500
    )

    return response.choices[0].message.content

def web_context_report(image_desc_json, image_user_description):
    import time
    from serpapi import GoogleSearch

    def search_snippets(query):
        try:
            search = GoogleSearch({'q': query, 'api_key': SERPAPI_KEY})
            results = search.get_dict().get('organic_results', [])[:5]
            snippets = [r.get('snippet') for r in results if 'snippet' in r]
            return snippets
        except Exception:
            return []

    try:
        image_desc = json.loads(image_desc_json)
    except json.JSONDecodeError as e:
        return f"Error parsing JSON: {e}", []

    toy_type = image_desc.get("toy_type", "")
    brand_series = image_desc.get("brand_or_series", "")
    characters = image_desc.get("characters", "")
    origin = image_desc.get("origin_anime_manga_game", "")
    storyline = image_desc.get("possible_storyline", "")

    if not any([toy_type, brand_series, characters, origin, storyline]):
        return "Insufficient data in JSON for meaningful queries.", []

    # Optimized targeted queries (2 searches instead of 4 to save API calls)
    searches = [
        f"{characters} {origin} {brand_series} lore character details",
        f"best instagram hashtags for {characters} {origin} {toy_type}"
    ]

    all_snippets = []
    for q in searches:
        snippets = search_snippets(q)
        all_snippets.extend(snippets)

    unique_snippets = list(dict.fromkeys(all_snippets))
    report = '\n'.join(unique_snippets[:8])

    return report, unique_snippets

def extract_keywords_from_vision_output(image_desc_json):
    """Automatically extracts keywords from Vision JSON output to drive hashtag research."""
    try:
        data = json.loads(image_desc_json)
        char = data.get("characters", "").strip()
        origin = data.get("origin_anime_manga_game", "").strip()
        toy = data.get("toy_type", "").strip()
        keywords = [k for k in [char, origin, toy] if k]
        return " ".join(keywords) if keywords else "anime figure toy photography"
    except Exception:
        return "toy photography anime figure"

def generate_social_post(image_desc, report):
    with open('prompts/generation_prompt.txt', encoding='utf-8') as f:
        base_prompt = f.read()
    prompt = base_prompt.format(image_desc=image_desc, report=report)

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=1500,
        temperature=0.85
    )
    return resp.choices[0].message.content

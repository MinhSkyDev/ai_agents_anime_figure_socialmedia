from openai import OpenAI
from config import OPENAI_API_KEY, SERPAPI_KEY
from serpapi import GoogleSearch
import base64
import logging

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_image(buffer, image_user_description):
    with open('prompts/analysis_few_shot.txt', 'r', encoding='utf-8') as f:
        examples = f.read()

    with open('prompts/analyze_follow_up.txt', 'r', encoding='utf-8') as f:
        follow_up_prompt = f.read()

    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

    # Combine user description into the prompt
    user_context_prompt = f"The user provided the following context for the image: {image_user_description}"

    # Construct the messages for the API
    messages = [
        {"role": "system", "content": examples},
        {"role": "user", "content": user_context_prompt},
        {"role": "user", "content": [
            {"type": "text", "text": follow_up_prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}}
        ]}
    ]

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=2200
    )

    return response.choices[0].message.content

def web_context_report(image_desc_json, image_user_description):
    from config import SERPAPI_KEY
    import time
    from serpapi import GoogleSearch
    import json

    def search_snippets(query):
        search = GoogleSearch({'q': query, 'api_key': SERPAPI_KEY})
        results = search.get_dict().get('organic_results', [])[:7]
        snippets = [r.get('snippet') for r in results if 'snippet' in r]
        return snippets

    try:
        # Attempt to parse the JSON
        image_desc = json.loads(image_desc_json)
    except json.JSONDecodeError as e:
        # Return an error message if JSON parsing fails
        print(image_desc_json)
        return f"Error parsing JSON: {e}", []

    # Extract relevant fields with fallback to empty strings
    toy_type = image_desc.get("toy_type", "")
    brand_series = image_desc.get("brand_or_series", "")
    characters = image_desc.get("characters", "")
    origin = image_desc.get("origin_anime_manga_game", "")
    storyline = image_desc.get("possible_storyline", "")

    # Ensure at least one critical field is populated to proceed
    if not any([toy_type, brand_series, characters, origin, storyline]):
        return "Insufficient data in JSON for meaningful queries.", []

    # Base query combining user context and extracted JSON fields
# Condensed base query construction
    base_queries = {
        "brand_character_details": f"Brand/Series: {brand_series}.",
        "characters" : f"{characters}",
        "storyline_and_context": f"Storyline: {storyline}. Origin: {origin}.",
        "mood_and_emotion": f"Mood/Emotion: Based on {storyline}, cultural references, and user description: {image_user_description}."
    }

    # Targeted queries for three API calls
    searches = [
        f"{base_queries['brand_character_details']}",                                        # Brand, series, and character info
        f"Who is {base_queries['characters']}",                                              # Characters
        f"{base_queries['storyline_and_context']} storyline plot and cultural references",   # Storyline and cultural relevance
        f"{base_queries['mood_and_emotion']} mood, emotion, and fan discussions",            # Mood, emotion, and fan context
    ]


    all_snippets = []
    for idx, q in enumerate(searches):
        snippets = search_snippets(q)
        all_snippets.extend(snippets)
        time.sleep(1.5)  # Rate limiting to avoid API restrictions

    # Deduplicate and consolidate results
    unique_snippets = list(dict.fromkeys(all_snippets))
    report = '\n'.join(unique_snippets[:10])  # Limit to 10 concise snippets

    return report, unique_snippets

def generate_social_post(image_desc, report):
    with open('prompts/generation_prompt.txt') as f:
        base_prompt = f.read()
    prompt = base_prompt.format(image_desc=image_desc, report=report)

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=2200,
        temperature=0.9,  # Encourages more creative and varied outputs
        top_p=0.95,       # Allows more diverse word choices by sampling from the top 95% of probabilities
        frequency_penalty=0.2,  # Slightly discourages repetition within the response
        presence_penalty=0.6,   # Encourages introducing new ideas or concepts
    )
    return resp.choices[0].message.content

def plan_post_timing(image_desc):
    with open('prompts/plan_post_timing.txt', 'r', encoding='utf-8') as f:
        template = f.read()
    prompt = template.format(image_desc=image_desc)

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=500,
        temperature=0.6
    )

    return resp.choices[0].message.content

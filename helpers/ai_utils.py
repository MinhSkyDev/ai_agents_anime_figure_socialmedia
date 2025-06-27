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

def web_context_report(image_desc, image_user_description):
    from config import SERPAPI_KEY
    import time

    def search_snippets(query):
        search = GoogleSearch({'q': query, 'api_key': SERPAPI_KEY})
        results = search.get_dict().get('organic_results', [])[:5]
        snippets = [r.get('snippet') for r in results if 'snippet' in r]
        return snippets

    # Base search: extract keywords from the image description
    user_context_prompt = f"The user provided the following context for the image: {image_user_description}"
    base_query = image_desc + '\n' + user_context_prompt

    # Targeted searches to enrich context
    searches = [
        f"{base_query} anime name and brand",                      # Get brand/series name
        f"{base_query} what happens in the anime",                 # Plot or scenario
        f"{base_query} character background and storyline",        # Deeper character info
        f"{base_query} fan discussion or reddit thread summary",   # Emotional tone or fan view
    ]

    all_snippets = []
    for q in searches:
        snippets = search_snippets(q)
        all_snippets.extend(snippets)
        time.sleep(1.2)  # avoid hitting SerpAPI too fast

    # Deduplicate and combine
    unique_snippets = list(dict.fromkeys(all_snippets))
    report = '\n'.join(unique_snippets[:10])  # limit to 10 to keep it concise

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

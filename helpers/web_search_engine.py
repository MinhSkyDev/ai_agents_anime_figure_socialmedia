import requests
import urllib.parse
import re
from config import SERPAPI_KEY
from serpapi import GoogleSearch

def search_web_custom_engine(query: str, max_results: int = 5):
    """
    Fallback Custom Web Search Engine using keyless DuckDuckGo HTML scraping.
    Does not require SerpAPI key or quota.
    """
    try:
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        data = {"q": query}
        res = requests.post(url, headers=headers, data=data, timeout=8)

        if res.status_code == 200:
            # Extract snippet texts using regex parsing from DuckDuckGo HTML results
            snippets = re.findall(r'<a class="result__snippet[^">]*>(.*?)</a>', res.text, re.DOTALL)
            clean_snippets = []
            for s in snippets[:max_results]:
                clean_text = re.sub(r'<[^>]+>', '', s).strip()
                if clean_text:
                    clean_snippets.append(clean_text)
            if clean_snippets:
                return clean_snippets
    except Exception as e:
        print(f"[CustomSearchEngine] Scraper error: {e}")

    return []

def search_web_hybrid(query: str, max_results: int = 5):
    """
    Hybrid Web Search Strategy:
    1. Tries SerpAPI first.
    2. If SerpAPI fails, has 429 quota error, or is unavailable -> Fallbacks to Custom Search Engine.
    Returns: (snippets_list, engine_used_name)
    """
    if SERPAPI_KEY:
        try:
            search = GoogleSearch({'q': query, 'api_key': SERPAPI_KEY})
            dict_res = search.get_dict()
            if 'organic_results' in dict_res:
                results = dict_res.get('organic_results', [])[:max_results]
                snippets = [r.get('snippet') for r in results if 'snippet' in r]
                if snippets:
                    return snippets, "SerpAPI"
        except Exception as e:
            print(f"[HybridSearch] SerpAPI quota or error: {e}. Falling back to Custom Search Engine...")

    # Fallback to Custom Search Engine
    custom_snippets = search_web_custom_engine(query, max_results)
    return custom_snippets, "Custom Engine (DuckDuckGo)"

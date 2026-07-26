import time
import re
import json
from pydantic import BaseModel, Field
from typing import List, Optional

class VisionAnalysisSchema(BaseModel):
    toy_type: str = Field(default="Figure", description="Type of toy or figure")
    brand_or_series: str = Field(default="", description="Brand or series name")
    characters: str = Field(default="", description="Character name")
    origin_anime_manga_game: str = Field(default="", description="Origin anime/manga/game")
    possible_storyline: str = Field(default="", description="Suggested scenario")

class PostContentSchema(BaseModel):
    caption: str = Field(..., description="Post caption text")
    hashtags: List[str] = Field(default_factory=list, description="List of hashtags")

class TelemetryLogger:
    def __init__(self):
        self.logs = []

    def record(self, step_name: str, prompt_tokens: int, completion_tokens: int, latency_ms: float, search_engine_used: str = "N/A"):
        # GPT-4o pricing: $2.50 per 1M input tokens, $10.00 per 1M output tokens
        input_cost = (prompt_tokens / 1_000_000) * 2.50
        output_cost = (completion_tokens / 1_000_000) * 10.00
        total_cost = input_cost + output_cost

        entry = {
            "step": step_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "latency_ms": round(latency_ms, 2),
            "estimated_cost_usd": round(total_cost, 6),
            "search_engine": search_engine_used,
            "timestamp": time.time()
        }
        self.logs.append(entry)
        return entry

def evaluate_and_sanitize_hashtags(caption_text: str, max_hashtags: int = 5) -> tuple[str, List[str]]:
    """
    Harness Evaluator: Extracts all hashtags from text, trims to exactly max_hashtags (5),
    and reconstructs the clean caption text.
    """
    lines = caption_text.split('\n')
    text_lines = []
    extracted_tags = []

    for l in lines:
        tags = re.findall(r'#\w+', l)
        if tags:
            for t in tags:
                if t.lower() not in [et.lower() for et in extracted_tags]:
                    extracted_tags.append(t)
        else:
            text_lines.append(l)

    # Trim to max 5 hashtags
    sanitized_tags = extracted_tags[:max_hashtags]

    clean_caption = "\n".join(text_lines).strip()
    if sanitized_tags:
        clean_caption += "\n\n" + " ".join(sanitized_tags)

    return clean_caption, sanitized_tags

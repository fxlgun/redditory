from typing import Dict, Tuple
import os
import json
from pydantic import BaseModel, Field
from typing import List

from logger_config import setup_logger
logger = setup_logger(__name__)

# Configuration
CAPTION_PROVIDER = os.environ.get("CAPTION_PROVIDER", "gemini").lower()
GEMINI_MODEL_DEFAULT = "gemini-2.0-flash"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR KEY HERE")


class CaptionResponse(BaseModel):
    caption: str = Field(description="Instagram caption")
    hashtags: List[str] = Field(description="List of hashtag keywords")
    postworthy: bool = Field(description="True if meme-worthy content")


_gemini_client = None


def _init_gemini_client():
    global _gemini_client
    if _gemini_client:
        return _gemini_client
    try:
        from google.genai import Client
        _gemini_client = Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Gemini init failed: {e}")
        _gemini_client = None
    return _gemini_client


def _generate_with_gemini(prompt: str, model_name: str):
    client = _init_gemini_client()
    if client is None:
        raise RuntimeError("Gemini client unavailable")

    config = {
        "response_mime_type": "application/json",
        "response_json_schema": CaptionResponse.model_json_schema(),
    }

    resp = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=config,
    )

    parsed = CaptionResponse.model_validate_json(resp.text)
    caption = parsed.caption.strip()
    hashtags = " ".join(f"#{h.lstrip('#')}" for h in parsed.hashtags)
    postworthy = parsed.postworthy
    return caption, hashtags, postworthy


def generate_caption(post: Dict) -> Tuple[str, str, bool]:
    title = post.get("title", "") or ""
    text = (post.get("text") or "")[:900]
    subreddit = post.get("subreddit", "")

    prompt = f"""
Write IG caption for “Fielding Set”.

Rules:
- Hinglish meme-tone
- Max 250 characters
- 1 hook, 1 punchline
- No links, no Reddit mentions
- No hashtags inside caption

Return JSON:
- caption
- hashtags: 6-12 relevant IG tags without '#' prefix and some viral ones that will boost engagement.
- postworthy: false if boring, non-meme, political, announcement posts, or people posting if they are looking for something, discard these immediately and send postworthy as false, also too serious posts including strong sexual themes, keep a strong moderation, the page should be mature and funny and hence you should determine the postworthiness accordingly.

Content:
Title: {title}
Body: {text}
Source: {subreddit}
"""

    try:
        return _generate_with_gemini(prompt, GEMINI_MODEL_DEFAULT)
    except Exception as e:
        logger.warning(f"Caption fallback: {e}")
        return (
            "Fielding Set: what would you do? 🤔",
            "#FieldingSet #desidating #relationships",
            False
        )

import math
import time
from typing import Dict, Any

from logger_config import setup_logger

logger = setup_logger(__name__)

# subreddit weights
SUBREDDIT_WEIGHT = {
    
    "indiansocial": 0.6,
} #provide weights


def normalize_engagement(votes: int, comments: int) -> float:
    v = max(votes, 0)
    c = max(comments, 0)
    # log-scale
    nv = math.log10(v + 10) / math.log10(1000 + 10)  # ~0..1 for 0-1000+
    nc = math.log10(c + 1) / math.log10(100 + 1)     # ~0..1 for 0-100+
    return 0.7 * nv + 0.3 * nc


def recency_score(timestamp_utc: float) -> float:
    if not timestamp_utc:
        return 0.5
    now = time.time()
    age_hours = (now - timestamp_utc) / 3600

    if age_hours <= 24:
        return 1.0
    elif age_hours <= 48:
        return 0.7
    elif age_hours <= 72:
        return 0.4
    else:
        return 0.2


def length_score(text: str) -> float:
    n = len(text or "")
    if n < 80:
        return 0.4
    elif n <= 600:
        return 1.0
    elif n <= 1200:
        return 0.7
    else:
        return 0.3


def subreddit_weight(subreddit: str) -> float:
    return SUBREDDIT_WEIGHT.get(subreddit, 0.5)


def compute_final_score(post: Dict[str, Any]) -> float:
    stats = post.get("stats", {})
    votes = int(stats.get("votes", post.get("score", 0)) or 0)
    comments = int(stats.get("comments", 0) or 0)
    text = post.get("text", "")
    ts = post.get("timestamp_utc") or 0
    sub = post.get("subreddit", "")

    eng = normalize_engagement(votes, comments)
    rec = recency_score(float(ts))
    ln = length_score(text)
    sw = subreddit_weight(sub)

    final_score = (
        0.4 * eng +
        0.25 * rec +
        0.2 * ln +
        0.15 * sw
    )
    final_score = round(final_score, 4)
    
    logger.debug(f"Scored post (sub={sub}): engagement={eng:.3f}, recency={rec:.3f}, length={ln:.3f}, weight={sw:.3f} -> final={final_score}")
    return final_score

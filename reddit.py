import requests
import re
import html
from typing import List, Dict, Any

USER_AGENT = "FieldingSetBot/1.0"
DEFAULT_LIMIT = 10

ENDPOINTS = [
    ("hot", "hot.json?limit={limit}"),
    ("top", "top.json?t=day&limit={limit}")
]


def get_json(url: str):
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": USER_AGENT})
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return {}


def extract_post_data(post, subreddit, origin):
    data = post.get("data", {})

    reddit_id = data.get("id", "")
    fullname = data.get("name", "")
    title = data.get("title", "")
    text = data.get("selftext", "") or ""
    permalink = "https://reddit.com" + data.get("permalink", "")
    author = data.get("author", "")

    score = data.get("score", 0)
    comments = data.get("num_comments", 0)
    created = data.get("created_utc", None)

    image_url = None
    has_image = False

    # Source image
    url_override = data.get("url_overridden_by_dest")
    if isinstance(url_override, str) and url_override.startswith("http"):
        image_url = url_override
        has_image = True

    # Fallback preview
    if not has_image:
        try:
            image_url = data["preview"]["images"][0]["source"]["url"].replace("&amp;", "&")
            has_image = True
        except:
            pass

    return {
        "id": reddit_id,
        "fullname": fullname,
        "title": title,
        "text": text,
        "timestamp_utc": created,
        "stats": {"votes": score, "comments": comments, "shares": 0},
        "posted": False,
        "permalink": permalink,
        "subreddit": subreddit,
        "author": author,
        "score": score,
        "origin": origin,
        "type": "image" if has_image else "text",
        "image_url": image_url,
        "has_image": has_image,
    }


def fetch_subreddit_posts(subreddit: str, limit: int = DEFAULT_LIMIT):
    results = {}
    for origin, ep in ENDPOINTS:
        url = f"https://www.reddit.com/r/{subreddit}/{ep.format(limit=limit)}"
        data = get_json(url)
        children = data.get("data", {}).get("children", [])
        for post in children:
            pdata = extract_post_data(post, subreddit, origin)
            if pdata["id"]:
                results[pdata["id"]] = pdata
    return list(results.values())

def fetch_popular_posts(subreddits: List[str], limit: int = DEFAULT_LIMIT): 
    all_posts = [] 
    for sub in subreddits: 
        all_posts.extend(fetch_subreddit_posts(sub, limit)) 
    return all_posts

def clean_comment_text(text: str, op_user: str):
    text = html.unescape(text or "")
    text = re.sub(fr"\b{re.escape(op_user)}\b", "you", text, flags=re.IGNORECASE)
    text = re.sub(r"u\/[A-Za-z0-9_-]+", "someone", text, flags=re.IGNORECASE)
    text = re.sub(r"\bOP\b", "you", text, flags=re.IGNORECASE)
    text = re.sub(r"&gt;|>", "", text)
    return text.strip()


def fetch_top_comments(permalink: str, limit: int = 4):
    url = permalink + ".json?sort=top&limit=20"
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": USER_AGENT})
        if r.status_code != 200:
            return []

        data = r.json()
        post_author = data[0]["data"]["children"][0]["data"].get("author", "")

        comments = data[1]["data"]["children"]
        out = []

        for c in comments:
            if c["kind"] != "t1": 
                continue

            raw_body = c["data"].get("body", "")
            cleaned = clean_comment_text(raw_body, op_user=post_author)
            ups = c["data"].get("ups", 0)

            if len(cleaned) >= 25:
                out.append({"body": cleaned, "ups": ups})

        out.sort(key=lambda x: x["ups"], reverse=True)
        return out[:limit]

    except:
        return []

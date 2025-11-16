import csv
csv.field_size_limit(10_000_000)

import os
from typing import List, Dict, Any, Optional

CSV_FILE = "reddit_posts.csv"

FIELDS = [
    "id", "fullname", "title", "text", "timestamp_utc",
    "votes", "comments", "shares", "posted", "permalink",
    "subreddit", "score", "origin", "type", "final_score",
    "has_image", "image_url", "discarded"
]


def ensure_file_exists():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()


def read_all():
    ensure_file_exists()
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_all(rows):
    ensure_file_exists()
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def add_posts(posts: List[Dict[str, Any]]):
    rows = read_all()
    ids = {r["id"] for r in rows}
    new = []

    for p in posts:
        if p["id"] in ids: 
            continue
        st = p.get("stats", {})
        new.append({
            "id": p["id"],
            "fullname": p.get("fullname", ""),
            "title": p.get("title", ""),
            "text": p.get("text", ""),
            "timestamp_utc": p.get("timestamp_utc", ""),
            "votes": st.get("votes", 0),
            "comments": st.get("comments", 0),
            "shares": st.get("shares", 0),
            "posted": "False",
            "permalink": p.get("permalink", ""),
            "subreddit": p.get("subreddit", ""),
            "score": p.get("score", 0),
            "origin": p.get("origin", ""),
            "type": p.get("type", ""),
            "final_score": p.get("final_score", ""),
            "has_image": str(p.get("has_image", False)),
            "image_url": p.get("image_url", ""),
            "discarded": str(p.get("discarded", False)),
        })

    write_all(rows + new)
    return new


def mark_posted(pid):
    rows = read_all()
    changed = False
    for r in rows:
        if r["id"] == pid:
            r["posted"] = "True"
            changed = True
    if changed: write_all(rows)
    return changed


def mark_discarded(post_id: str) -> bool:
    rows = read_all()
    updated = False
    for r in rows:
        if r["id"] == post_id:
            r["discarded"] = "True"
            updated = True
    if updated:
        write_all(rows)
    return updated


def safe_float(v):
    try:
        return float(v)
    except:
        return 0.0


def get_unposted(limit: Optional[int] = None, min_score: float = 0.0):
    rows = read_all()

    def is_unposted(r):
        return (
            r.get("posted", "").lower() != "true"
            and r.get("discarded", "false").lower() != "true"
            and safe_float(r.get("final_score")) >= min_score
        )

    unposted = [r for r in rows if is_unposted(r)]
    unposted.sort(key=lambda r: safe_float(r.get("final_score")), reverse=True)

    return unposted

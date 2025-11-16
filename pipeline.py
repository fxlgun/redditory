import os
from pathlib import Path
import random
from typing import List, Tuple

import csv_store
from reddit import fetch_popular_posts, fetch_top_comments
from scorer import compute_final_score
from caption import generate_caption
from render import render_post_image
from instagram import InstagramClient


SUBREDDITS = [
    "indiasocial"
] #list of subredddits

PER_SUBREDDIT_LIMIT = 10
MIN_FINAL_SCORE = 0.6
POSTS_PER_RUN = 1
OUTPUT_DIR = "out_images"


def ensure_output_dir():
    Path(OUTPUT_DIR).mkdir(exist_ok=True)


def fetch_and_store_if_needed():
    """Fetch only when CSV has zero usable posts left."""
    unposted = csv_store.get_unposted(min_score=MIN_FINAL_SCORE)
    if not unposted:
        print("📭 Fetching new data from Reddit…")
        posts = fetch_popular_posts(SUBREDDITS, PER_SUBREDDIT_LIMIT)
        for p in posts:
            p["final_score"] = compute_final_score(p)
            p.setdefault("discarded", False)
        csv_store.add_posts(posts)
        print(f"📌 Stored {len(posts)} posts")
        unposted = csv_store.get_unposted(min_score=MIN_FINAL_SCORE)
    return unposted


def build_post_content(row: dict):
    post = {
        "id": row["id"],
        "title": row["title"],
        "text": row["text"],
        "subreddit": row["subreddit"],
        "permalink": row["permalink"],
        "image_url": row["image_url"] if str(row.get("has_image")).lower() == "true" else None,
    }

    img_paths: List[str] = []
    first_slide = os.path.join(OUTPUT_DIR, f"{post['id']}_1.jpg")
    render_post_image(post, first_slide)
    img_paths.append(first_slide)

    # Fetch comments (OPTION A: optional, not required to post)
    comments = fetch_top_comments(post["permalink"], limit=15)
    comments = [c for c in comments if len(c["body"]) >= 25][:8]

    for idx, c in enumerate(comments, start=2):
        slide_data = {
            "id": f"{post['id']}_{idx}",
            "title": "Comment",
            "text": c["body"],
            "subreddit": post["subreddit"],
            "image_url": None,
        }
        slide_path = os.path.join(OUTPUT_DIR, f"{post['id']}_{idx}.jpg")
        render_post_image(slide_data, slide_path)
        img_paths.append(slide_path)

    caption, hashtags, postworthy = generate_caption(post)
    if not postworthy:
        print(f"🗑 AI flagged {post['id']} as NOT postworthy")
        return None

    full_caption = f"{caption}\n\n{hashtags}"
    return img_paths, full_caption


def main():
    ensure_output_dir()
    posted = 0
    attempts = 0
    max_attempts = 10

    ig = InstagramClient()

    while posted < POSTS_PER_RUN and attempts < max_attempts:
        attempts += 1

        candidates = fetch_and_store_if_needed()
        if not candidates:
            print("❌ No candidates available after fetch")
            break

        row = random.choice(candidates)
        print(f"🎯 Trying post {row['id']} — {row['title'][:40]}…")

        result = build_post_content(row)
        if not result:
            csv_store.mark_discarded(row["id"])
            continue

        img_paths, caption = result
        print(f"📤 Uploading {len(img_paths)} slides…")

        try:
            if len(img_paths) > 1:
                ig.album_upload(img_paths, caption)
            else:
                ig.upload_photo(img_paths[0], caption)
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            continue

        csv_store.mark_posted(row["id"])
        posted += 1
        print(f"✅ Posted {posted}/{POSTS_PER_RUN}")

    print("✨ Pipeline complete ✨")


if __name__ == "__main__":
    main()

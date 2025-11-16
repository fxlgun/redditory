# redditory

Redditory is a small pipeline that fetches popular Reddit posts from configured subreddits, ranks them, renders Instagram-ready images, generates captions via an LLM, and uploads them to Instagram.

This README documents how the pipeline works, where data comes from, environment configuration, and how to modify/extend behavior.

**Quick Summary**
- Fetch posts from Reddit (public JSON endpoints)
- Store posts in a local CSV (`reddit_posts.csv`) as the source-of-truth
- Score posts with `scorer.py` to determine post-worthiness
- Render Instagram images with `render.py` (Pillow)
- Generate captions with `caption.py` (supports Gemini by default; Anthropic/Claude can be used)
- Upload images using `instagrapi` via `instagram.py`
- Logging configured in `logger_config.py` (console + rotating file logs)

**Quickstart**
- Ensure Python 3.10+ is installed
- Recommended packages (install into a venv):

```bash
python -m pip install requests pillow instagrapi google-genai pydantic
```

- Set required environment variables (example for bash):

```bash
export IG_USERNAME="your_instagram_username"
export IG_PASSWORD="your_instagram_password"
# For Gemini (Google) captioning (optional):
export GEMINI_API_KEY="your_gemini_api_key"
```

- Run the pipeline:

```bash
python pipeline.py
```

Notes: the pipeline will create `out_images/` and `reddit_posts.csv` automatically.

**Files and Responsibilities**
- `pipeline.py` : Orchestrator. Ensures output directories exist, triggers fetch/store, selects candidates, builds images/captions, and uploads to Instagram. Key configuration values live here: `SUBREDDITS`, `PER_SUBREDDIT_LIMIT`, `MIN_FINAL_SCORE`, `POSTS_PER_RUN`, `OUTPUT_DIR`.
- `reddit.py` : Fetches posts and top comments from Reddit using the public JSON endpoints (no OAuth). Extracts post fields, detects image URLs, and returns structured objects.
- `csv_store.py` : Simple CSV backing store (`reddit_posts.csv`) that keeps all fetched posts and their state (`posted`, `discarded`, `final_score`, etc.). Acts as persistence across runs.
- `scorer.py` : Computes a `final_score` for ranking posts using engagement, recency, text length, and subreddit weight. Modify weights here to change ranking behavior.
- `caption.py` : Generates captions using an LLM. By default it uses Gemini (Google GenAI). It supports switching to Anthropic/Claude via `CAPTION_PROVIDER=claude`. It validates/normalizes the LLM output and returns `(caption, hashtags, postworthy_bool)`.
- `render.py` : Renders square Instagram images using PIL. Handles full-image and text+image layouts, smart truncation, logo watermarking, and per-slide generation for comments.
- `instagram.py` : Thin wrapper around `instagrapi.Client`. Handles session saving (`insta_session.json`) and exposes `upload_photo` and `album_upload`.
- `logger_config.py` : Centralized logger setup. Logs to console (INFO) and file under `logs/redditory_<timestamp>.log` (DEBUG).

**How the pipeline works (step-by-step)**
1. `main()` in `pipeline.py` ensures `out_images/` exists and constructs an `InstagramClient`.
2. It iteratively tries to post up to `POSTS_PER_RUN` posts (default: `1`).
3. For each attempt it calls `fetch_and_store_if_needed()`:
	 - Checks `csv_store.get_unposted(min_score=MIN_FINAL_SCORE)` for available candidates.
	 - If none are found, it calls `reddit.fetch_popular_posts(SUBREDDITS, PER_SUBREDDIT_LIMIT)` which fetches `hot` and `top (day)` endpoints for each subreddit.
	 - Each fetched post is scored with `compute_final_score()` and added to `reddit_posts.csv` by `csv_store.add_posts()`.
	 - `get_unposted()` returns rows where `posted != True`, `discarded != True`, and `final_score >= MIN_FINAL_SCORE`.
4. `pipeline.py` picks a random candidate row and calls `build_post_content(row)`:
	 - Builds a `post` dict with core fields.
	 - Renders the first slide using `render_post_image(post, out_images/<id>_1.jpg)`.
	 - Optionally fetches top comments via `reddit.fetch_top_comments(permalink)`, filters them, and renders each comment as additional slides.
	 - Calls `generate_caption(post)` to produce `(caption, hashtags, postworthy)`.
	 - If `postworthy` is False, the post is marked discarded.
5. If content passes, pipeline uploads either as a carousel (`album_upload`) or single photo (`upload_photo`) via `instagrapi`.
6. On success `csv_store.mark_posted(id)` sets `posted=True`. Images are kept in `out_images/` (pipeline may delete them in future—currently they are left).
7. Loop continues until `POSTS_PER_RUN` posts are posted or `max_attempts` is reached.

**Where the data comes from**
- Reddit data: scraped from endpoints like `https://www.reddit.com/r/<subreddit>/hot.json` and `.../top.json?t=day`.
	- This is unauthenticated public JSON access. If Reddit changes their public endpoints or rate-limits, the fetch may fail.
- LLM captions: Gemini (Google GenAI) by default. Optionally Anthropic/Claude if configured.
- Instagram upload: `instagrapi` authenticates with provided IG credentials.
- Storage: `reddit_posts.csv` stores all posts and metadata.

**Important configuration & how to modify behavior**
- `pipeline.py` (primary knobs):
	- `SUBREDDITS`: list of subreddits to scrape. Edit this list to add/remove sources.
	- `PER_SUBREDDIT_LIMIT`: number of posts to request per subreddit and endpoint.
	- `MIN_FINAL_SCORE`: float threshold (0..1) to consider a post for posting.
	- `POSTS_PER_RUN`: how many posts to publish each run.
	- `OUTPUT_DIR`: directory for rendered images.

- `scorer.py`: change weighting or scoring functions to alter how posts are ranked (e.g., increase recency weight to prefer newer posts).
- `csv_store.py`: The CSV schema is defined in `FIELDS`. You can manually edit `reddit_posts.csv` to adjust specific rows if desired; the code is tolerant to missing values but will attempt to parse `final_score` as float.

**Environment variables**
- `IG_USERNAME` and `IG_PASSWORD` (required for real uploads)
- `GEMINI_API_KEY` (optional; required if using Gemini provider)


3. The `caption.py` module will attempt to call Anthropic and parse JSON out of Claude's response. If the Anthropic SDK or API key is missing, the pipeline logs a helpful message and falls back to a safe default caption instead of failing the whole run.

**Logging & debugging**
- Logs are created by `logger_config.py` under the `logs/` directory: `logs/redditory_<timestamp>.log`.
- Console output is INFO level; the log file captures DEBUG for more verbose troubleshooting (network fetches, scoring diagnostics, caption fallback details).
- If you see problems with posting, check `logs/` first for stack traces and network issues.

**CSV storage (`reddit_posts.csv`)**
- Acts as the canonical list of posts known to the pipeline.
- Columns: `id, fullname, title, text, timestamp_utc, votes, comments, shares, posted, permalink, subreddit, score, origin, type, final_score, has_image, image_url, discarded`.
- Interactions:
	- `add_posts(posts)`: appends new posts (skips ids already present)
	- `get_unposted(limit, min_score)`: returns candidate rows not yet posted or discarded and above `min_score`
	- `mark_posted(id)`: sets `posted=True`
	- `mark_discarded(id)`: sets `discarded=True`

Manual edits are allowed but be careful with CSV encoding/format.

**Safety and moderation**
- `caption.py` contains rules to detect non-postworthy content and the pipeline will mark such posts as discarded when the LLM indicates so.
- The code also performs basic comment cleanup (`reddit.clean_comment_text`) to avoid accidentally including user mentions/OP handles.

**Common tasks / examples**
- Run only fetch & store (no posting):
	- Temporarily set `POSTS_PER_RUN=0` in `pipeline.py` and run `python pipeline.py` to populate `reddit_posts.csv`.
- Preview images for a given row:
	- Run `render.render_post_image(row, 'out_images/preview.jpg')` in a Python REPL after importing the module.
- Dry-run captioning:
	- Set `IG_USERNAME`/`IG_PASSWORD` to dummy values and comment out upload calls in `pipeline.py`, or simply observe `generate_caption` outputs by calling it in a REPL.

**Troubleshooting**
- Rate limits / failures fetching Reddit JSON:
	- Reddit may throttle frequent requests. Reduce `PER_SUBREDDIT_LIMIT` or add sleeps between requests.
	- Check `USER_AGENT` in `reddit.py` if Reddit requires a more descriptive agent.
- Instagram login failures:
	- `instagrapi` may require login challenges; try manual login and let the client dump `insta_session.json`.
- LLM failures:
	- If Gemini/Anthropic calls fail, `caption.py` falls back to a default caption. Check logs for the exact error.

**Extending the project**
- Add tests: introduce a small test harness that runs `render_post_image` on sample posts and asserts file output exists.
- Add a `requirements.txt` or `pyproject.toml` to pin dependencies.
- Add a `--dry-run` CLI flag to `pipeline.py` to skip uploads and only render + caption for faster iteration.

**Contact & next steps**
If you want, I can:
- Add a `requirements.txt` and a convenience `run.sh` that sets example env vars for development.
- Add a `--dry-run` / `--limit` CLI interface to `pipeline.py`.
- Add more structured tests for rendering and captioning.

---

Project files referenced above:
- `pipeline.py`, `reddit.py`, `csv_store.py`, `scorer.py`, `caption.py`, `render.py`, `instagram.py`, `logger_config.py`

Thank you — tell me which next step you'd like: add `requirements.txt`, implement a `--dry-run` flag, or wire up automated tests? 

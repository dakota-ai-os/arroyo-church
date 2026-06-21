#!/usr/bin/env python3
"""
Weekly sermon -> blog-post generator (the CONTENT half of the blog pipeline).

Reads the latest sermon from data/sermons.json, pulls its YouTube auto-caption
transcript (yt-dlp), and asks Claude (Opus 4.8, structured output) to write a
genuinely useful, SEO-aware post -- real title, original summary + application,
scripture references, a video embed, tasteful (not stuffed) local relevance, a
meta description, a few meaningful tags, and internal links.

Output: blog-drafts/<date>-<slug>.html (paste-ready) + .json (the fields).
Idempotent: skips if a draft already exists for the latest sermon's video id,
so the weekly run only generates when a NEW sermon appears.

Runs on Dakota's Mac (residential IP) -- NOT GitHub Actions -- because YouTube
blocks yt-dlp transcript downloads from datacenter IPs.

Requires: ANTHROPIC_API_KEY (env), yt-dlp on PATH, `pip install anthropic`.
"""

import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import anthropic

REPO = Path(__file__).resolve().parent.parent
DRAFTS = REPO / "blog-drafts"
SERMONS_FILE = REPO / "data" / "sermons.json"

sermons = json.loads(SERMONS_FILE.read_text(encoding="utf-8"))
videos = sermons.get("videos") or []
if not videos:
    sys.exit("no latest sermon in data/sermons.json")
v = videos[0]
series = sermons.get("series") or {}
video_id = v["id"]
video_url = f"https://www.youtube.com/watch?v={video_id}"
today = date.today().isoformat()

DRAFTS.mkdir(parents=True, exist_ok=True)

# ---- idempotency: skip if a draft already references this video id ----
def already_done() -> bool:
    for f in DRAFTS.glob("*.json"):
        try:
            if json.loads(f.read_text(encoding="utf-8")).get("videoId") == video_id:
                return True
        except Exception:
            continue
    return False

if already_done():
    print(f'Draft already exists for {video_id} ("{v.get("title")}") -- nothing to do.')
    sys.exit(0)

# ---- transcript via yt-dlp auto-captions ----
def clean_vtt(vtt: str) -> str:
    seen, out = set(), []
    for raw in vtt.splitlines():
        if not raw or "-->" in raw or re.fullmatch(r"\d+", raw) or re.match(r"(WEBVTT|Kind:|Language:)", raw):
            continue
        t = re.sub(r"<[^>]+>", "", raw).replace("&nbsp;", " ").strip()
        if not t or t in seen:        # drop rolling-duplicate caption lines
            continue
        seen.add(t)
        out.append(t)
    return " ".join(out)

VTT = Path("/tmp/ac_sermon.en.vtt")
transcript = ""
try:
    for stale in Path("/tmp").glob("ac_sermon.*"):
        stale.unlink()
except Exception:
    pass
try:
    subprocess.run(
        ["yt-dlp", "--quiet", "--no-warnings", "--skip-download", "--write-auto-sub",
         "--sub-lang", "en", "--sub-format", "vtt", "-o", "/tmp/ac_sermon.%(ext)s", video_url],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    transcript = clean_vtt(VTT.read_text(encoding="utf-8"))
except Exception as e:
    print(f"transcript fetch failed: {e}", file=sys.stderr)

if len(transcript) < 400:
    sys.exit("transcript too short/empty -- aborting so we don't write a thin post")

# ---- generate with Claude (Opus 4.8, structured output) ----
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string", "description": "Human, search-friendly post title (not a keyword string). ~50-65 chars."},
        "metaDescription": {"type": "string", "description": "SEO meta description, 150-160 chars, compelling and specific."},
        "slug": {"type": "string", "description": "url slug, lowercase-hyphenated, no dates"},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "3-5 meaningful tags (e.g. scripture book, series, topic). NOT a list of cities."},
        "bodyHtml": {"type": "string", "description": "The post body as clean HTML (h2/h3/p/blockquote/ul). Includes the video embed near the top and internal-link CTAs near the end."},
    },
    "required": ["title", "metaDescription", "slug", "tags", "bodyHtml"],
}

SYSTEM = """You are the content writer for Arroyo Church, a non-denominational, Bible-teaching church in Livermore, CA (Tri-Valley, San Francisco Bay Area). Mission: "to know and show the love of Jesus." You turn a Sunday sermon transcript into a genuinely useful blog post that helps real readers AND ranks well for local search -- WITHOUT keyword stuffing or thin/duplicate content (Google penalizes that).

Write a post that:
- Opens with a strong, human hook drawn from the sermon (an illustration or the central question), then states the main idea.
- Gives an ORIGINAL summary and life application in your own words (do NOT paste the transcript; synthesize it). ~600-900 words.
- Cites the specific scripture passages the sermon covered, quoted accurately.
- Includes a short closing "takeaway" or reflection question.
- Embeds the sermon video near the top using EXACTLY this markup (real id substituted): <div class="sermon-embed" style="position:relative;padding-bottom:56.25%;height:0;margin:1.5rem 0;border-radius:14px;overflow:hidden"><iframe src="https://www.youtube.com/embed/VIDEO_ID" title="Watch the sermon" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0" allow="accelerometer;autoplay;clipboard-write;encrypted-media;gyroscope;picture-in-picture" allowfullscreen loading="lazy"></iframe></div>
- Mentions Livermore / the Tri-Valley ONCE, naturally, in a closing invitation -- never sprinkled through the body.
- Ends with two internal-link CTAs: <a href="/messages">Watch more sermons</a> and <a href="/plan-your-visit">Plan your visit</a>.
- bodyHtml uses semantic tags (h2, h3, p, blockquote, ul/li). No <html>/<head>/<body> wrapper, no inline color styles except the embed block above.
Tone: warm, clear, pastoral, never clickbait. Theologically careful -- if the transcript is ambiguous on a name or reference, keep it general rather than guessing."""

USER = f"""Sermon to write up:
- Title: {v.get('title')}
- Series: {series.get('title') or '(standalone)'}{(' -- ' + series['blurb']) if series.get('blurb') else ''}
- YouTube video id: {video_id}
- Watch URL: {video_url}

Transcript (auto-captions; may misrender names/scripture -- correct obvious errors, keep uncertain references general):
\"\"\"
{transcript[:60000]}
\"\"\"

Write the blog post. Substitute the real video id ({video_id}) into the embed markup."""

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
resp = client.messages.create(
    model="claude-opus-4-8",
    max_tokens=8000,
    system=SYSTEM,
    output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    messages=[{"role": "user", "content": USER}],
)

text = next((b.text for b in resp.content if b.type == "text"), None)
if not text:
    sys.exit(f"no text block in response; stop_reason={resp.stop_reason}")
post = json.loads(text)

slug = re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", (post.get("slug") or v.get("title") or "sermon").lower()))[:70]
base = DRAFTS / f"{today}-{slug}"

(base.with_suffix(".json")).write_text(
    json.dumps({**post, "videoId": video_id, "videoUrl": video_url,
                "series": series.get("title"), "generated": today}, indent=2) + "\n",
    encoding="utf-8",
)
(base.with_suffix(".html")).write_text(
    f"""<!-- PASTE-READY DRAFT -- review, then in Squarespace create a blog post and:
     - Title: {post['title']}
     - SEO Description (Post Settings -> SEO): {post['metaDescription']}
     - URL slug: {slug}
     - Tags: {', '.join(post['tags'])}
     - Body: paste everything below this comment. -->
{post['bodyHtml']}
""",
    encoding="utf-8",
)

print(f'Wrote {base.with_suffix(".html").name} / .json -- "{post["title"]}"')

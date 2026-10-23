#!/usr/bin/env python3
"""Regression tests for the sermon-notes link in blog drafts (blog_notes_link.py + generate_blog.py).
Run:  python3 scripts/test_blog_notes_link.py

No network, no API, no git: generate_blog.py runs from a temp copy of the repo with a fake
`anthropic` module and a fake `yt-dlp`, so nothing lands in the real blog-drafts/."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import blog_notes_link as b

TMP = Path(tempfile.mkdtemp(prefix="blog-notes-test-"))

failures = []
def check(name, cond):
    print(("  ok    " if cond else "  FAIL  ") + name)
    if not cond:
        failures.append(name)


print("which Sunday, and whether to link it")
SUN = date(2026, 10, 18)
check("a Sunday is its own week", b.sunday_on_or_before(SUN) == SUN)
check("Monday and Saturday belong to the Sunday before",
      b.sunday_on_or_before(date(2026, 10, 19)) == SUN and b.sunday_on_or_before(date(2026, 10, 24)) == SUN)

def index(*weeks):
    f = TMP / f"idx-{'_'.join(weeks)}.json"
    f.write_text(json.dumps({"weeks": [{"service": w, "file": f"{w}.json"} for w in weeks]}))
    return f
IDX = index("2026-10-04", "2026-10-11", "2026-10-18", "2026-12-20")
calls = []
def yt(day, streamed=False):
    def lookup(vid):
        calls.append(vid)
        return (day, streamed)
    return lookup
def plan(env=None, lookup=None, idx=IDX, today=None):
    return b.notes_link("x", env or {}, idx, today=today, lookup=lookup or yt(None))

n = plan({"BLOG_SERVICE_DATE": "2026-10-04"}, lookup=yt(date(2026, 10, 14)))
check("BLOG_SERVICE_DATE wins, without asking YouTube",
      n.service == date(2026, 10, 4) and n.source == "BLOG_SERVICE_DATE" and n.add and not n.warnings and not calls)
try:
    plan({"BLOG_SERVICE_DATE": "10/04/2026"})
    check("a malformed BLOG_SERVICE_DATE raises", False)
except ValueError:
    check("a malformed BLOG_SERVICE_DATE raises", True)
n = plan(lookup=yt(SUN, streamed=True))
check("the Sunday livestream: its own day, linked, no warning",
      n.service == SUN and n.add and not n.warnings and n.url.endswith("?week=2026-10-18"))
n = plan(lookup=yt(date(2026, 10, 14)))
check("an upload on Wednesday: back to its Sunday (why late re-uploads need the override)",
      n.service == date(2026, 10, 11) and n.add and not n.warnings)
n = plan(lookup=yt(date(2026, 12, 24), streamed=True))
check("a Christmas Eve stream with no notes of its own: NO link, though the Sunday before has notes",
      n.service == date(2026, 12, 20) and not n.add and len(n.warnings) == 1
      and "streamed Thu 2026-12-24, not a Sunday" in n.warnings[0])
n = plan(lookup=yt(date(2026, 12, 24), streamed=True), idx=index("2026-12-20", "2026-12-24"))
check("...and with its own notes: that date",
      n.service == date(2026, 12, 24) and n.add and not n.warnings and "Thursday" in n.source)
n = plan(lookup=lambda v: None, today=date(2026, 10, 14))
check("YouTube has no date (the 10/4 catch-up run on 10/14): the most recent Sunday, WITH a warning",
      n.service == date(2026, 10, 11) and n.add and len(n.warnings) == 1
      and "YouTube gave no date" in n.warnings[0] and "fix the link's ?week= date" in n.warnings[0])
check("...a Sunday counts as the most recent Sunday",
      plan(lookup=lambda v: None, today=SUN).service == SUN)
n = plan(lookup=yt(date(2026, 10, 25), streamed=True))
check("a week with no web notes (guest speaker, no outline): NO link, and the warning says how to add it",
      not n.add and len(n.warnings) == 1 and "no web notes for 2026-10-25" in n.warnings[0]
      and f'add <a href="{n.url}">Sermon notes</a>' in n.warnings[0])
n = plan(lookup=lambda v: None, today=date(2026, 10, 28))
check("...a guessed week with no notes says it was a guess",
      not n.add and len(n.warnings) == 1 and "(a guess: YouTube gave no date" in n.warnings[0])
n = plan(lookup=yt(SUN, streamed=True), idx=TMP / "missing.json")
check("unreadable index: linked, but flagged to check by hand",
      n.add and len(n.warnings) == 1 and "unreadable" in n.warnings[0])

print("youtube_date")
real_run = b.subprocess.run
def fake_run(stdout, exc=None):
    def run(*a, **k):
        if exc:
            raise exc
        return types.SimpleNamespace(stdout=stdout)
    return run
try:
    # the real shape, from R2h61C2DHGk (10/18): stream start, a later processing time, a UTC upload date
    b.subprocess.run = fake_run("1792343143 1792392618 20261019 was_live\n")
    check("a stream: its start, in church time (the upload date says Monday)",
          b.youtube_date("x") == (SUN, True))
    b.subprocess.run = fake_run("1792371600 1792371600 20261019 was_live\n")   # 2026-10-19 01:00 UTC
    check("church time, not UTC (Sunday 6pm PDT)", b.youtube_date("x") == (SUN, True))
    b.subprocess.run = fake_run("NA 1791139625 20261004 not_live\n")          # 4GUueAPp7uw (10/4)
    check("an upload: its publish time, not a stream", b.youtube_date("x") == (date(2026, 10, 4), False))
    b.subprocess.run = fake_run("NA NA 20261018\n")
    check("no timestamps: the upload date", b.youtube_date("x") == (SUN, False))
    b.subprocess.run = fake_run("", exc=subprocess.CalledProcessError(1, "yt-dlp"))
    check("yt-dlp failing: None (the caller falls back)", b.youtube_date("x") is None)
finally:
    b.subprocess.run = real_run

print("notes index")
idx = TMP / "index.json"
idx.write_text(json.dumps({"weeks": [{"service": "2026-10-18", "file": "2026-10-18.json"}]}))
check("a published week is listed", b.notes_listed(SUN, idx) is True)
check("an unpublished week is not", b.notes_listed(date(2026, 10, 11), idx) is False)
check("no index: unknown", b.notes_listed(SUN, TMP / "missing.json") is None)

print("add_notes_link")
URL = b.notes_url(SUN)
check("links the notes page directly with ?week= (Squarespace's /sermon-notes redirect drops it)",
      URL == "https://links.arroyochurch.com/notes/?week=2026-10-18")
drafts = sorted((REPO / "blog-drafts").glob("*.json"))
LINK = f'<a href="{URL}">Sermon notes</a>'
bad = []
for f in drafts:
    body = json.loads(f.read_text(encoding="utf-8"))["bodyHtml"]
    out = b.add_notes_link(body, URL)
    head, _, tail = body.rpartition('<a href="/plan-your-visit">')
    sep = head[head.rfind("</a>") + 4:]                # whatever separated the two links
    if out.count(URL) != 1 or out != head + LINK + sep + '<a href="/plan-your-visit">' + tail \
            or b.add_notes_link(out, URL) != out:
        bad.append(f.name)
check(f"every real draft ({len(drafts)}): one link, between the two CTAs, same separator, "
      f"nothing else changed, idempotent" + (f" -- failed: {bad}" if bad else ""), drafts and not bad)
check("no Plan-your-visit link: right after Watch more sermons",
      b.add_notes_link('<p><a href="/messages">Watch more sermons</a></p>', URL)
      == f'<p><a href="/messages">Watch more sermons</a> &middot; {LINK}</p>')
check("no CTA line at all: its own closing paragraph",
      b.add_notes_link("<p>Amen.</p>", URL) == f"<p>Amen.</p><p>{LINK}</p>")

print("generate_blog.py end to end (temp repo, fake model + fake yt-dlp)")
SAMPLE = REPO / "blog-drafts" / "2026-10-18-can-god-restore-a-broken-relationship-ephesians-2.json"
fake_post = {k: v for k, v in json.loads(SAMPLE.read_text(encoding="utf-8")).items()
             if k in ("title", "metaDescription", "slug", "tags", "bodyHtml")}
repo = TMP / "repo"
(repo / "scripts").mkdir(parents=True)
(repo / "data" / "sermon-notes").mkdir(parents=True)
for name in ("generate_blog.py", "blog_notes_link.py"):
    shutil.copy(HERE / name, repo / "scripts" / name)
shutil.copy(REPO / "data" / "sermons.json", repo / "data" / "sermons.json")
shutil.copy(idx, repo / "data" / "sermon-notes" / "index.json")
fake = TMP / "fake"
fake.mkdir()
(fake / "post.json").write_text(json.dumps(fake_post))
(fake / "anthropic.py").write_text(
    "import json, os, types\n"
    "class Anthropic:\n"
    "    def __init__(self, *a, **k): self.messages = self\n"
    "    def create(self, **k):\n"
    "        text = open(os.path.join(os.path.dirname(__file__), 'post.json')).read()\n"
    "        return types.SimpleNamespace(content=[types.SimpleNamespace(type='text', text=text)], stop_reason='end_turn')\n")
(fake / "yt-dlp").write_text('#!/bin/sh\n[ -n "$FAKE_YT" ] || exit 1\necho "$FAKE_YT"\n')  # unset: yt-dlp fails
(fake / "yt-dlp").chmod(0o755)
transcript = TMP / "transcript.txt"
transcript.write_text("So let me pray. " * 60)

def gen(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("BLOG_", "ANTHROPIC_"))}
    env.update(PYTHONPATH=str(fake), PATH=f"{fake}:{env.get('PATH', '')}", BLOG_VIDEO_TITLE="Test sermon",
               BLOG_SERIES_TITLE="Grace for You", BLOG_TRANSCRIPT_FILE=str(transcript), **extra)
    r = subprocess.run([sys.executable, str(repo / "scripts" / "generate_blog.py")],
                       capture_output=True, text=True, env=env, timeout=60)
    return r.returncode, r.stdout + r.stderr

def drafts_for(vid):
    out = []
    for f in (repo / "blog-drafts").glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("videoId") == vid:
            out.append((d, f.with_suffix(".html").read_text(encoding="utf-8")))
    return out

rc, log = gen(BLOG_VIDEO_ID="TESTVID0001", BLOG_SERVICE_DATE="2026-10-18")
d, html = (drafts_for("TESTVID0001") or [({}, "")])[0]
check("override run: draft written, notes linked in the closing line", rc == 0 and
      f'Watch more sermons</a> &bull; {LINK} &bull; <a href="/plan-your-visit">' in html)
check("...the paste header names the link, no warning for a published week",
      f"Sermon notes link (in the closing line, week from BLOG_SERVICE_DATE): {URL}" in html and "WARNING" not in html)
check("...the .json keeps videoId (idempotency) and records serviceDate + notesUrl",
      d.get("videoId") == "TESTVID0001" and d.get("serviceDate") == "2026-10-18" and d.get("notesUrl") == URL
      and d.get("bodyHtml", "").count(URL) == 1)
rc, log = gen(BLOG_VIDEO_ID="TESTVID0001", BLOG_SERVICE_DATE="2026-10-18")
check("...a rerun for the same video still skips", rc == 0 and "Draft already exists" in log
      and len(drafts_for("TESTVID0001")) == 1)
rc, log = gen(BLOG_VIDEO_ID="TESTVID0002", FAKE_YT="NA NA 20261014")   # a Wednesday upload
d, html = (drafts_for("TESTVID0002") or [({}, "")])[0]
check("no override: the video's YouTube date picks the Sunday; a week with no notes gets NO link",
      rc == 0 and d.get("serviceDate") == "2026-10-11" and d.get("notesUrl") is None
      and "links.arroyochurch.com/notes" not in d.get("bodyHtml", "x")
      and "Sermon notes link: NONE added" in html and "WARNING: no web notes for 2026-10-11" in html
      and "-- NOT linked" in log and "WARNING: no web notes" in log)
rc, log = gen(BLOG_VIDEO_ID="TESTVID0004")                              # yt-dlp fails
d, html = (drafts_for("TESTVID0004") or [({}, "")])[0]
check("YouTube unreachable: the guess is flagged in the log and the paste header",
      rc == 0 and d and "YouTube gave no date" in html and "YouTube gave no date" in log)
rc, log = gen(BLOG_VIDEO_ID="TESTVID0003", BLOG_SERVICE_DATE="2026-1018")
check("a malformed BLOG_SERVICE_DATE stops before transcribing or calling the model",
      rc != 0 and "is not YYYY-MM-DD" in log and not drafts_for("TESTVID0003"))

shutil.rmtree(TMP, ignore_errors=True)
print()
if failures:
    print(f"{len(failures)} FAILED")
    sys.exit(1)
print("all passed")

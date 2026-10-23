#!/usr/bin/env python3
"""
Links each weekly sermon-recap draft to that Sunday's web sermon notes
(https://links.arroyochurch.com/notes/?week=YYYY-MM-DD, published by sermon_notes_sync.py).

Pure helpers, kept out of generate_blog.py because that script transcribes and calls the
Anthropic API as soon as it runs; test_blog_notes_link.py checks these offline.

Always link links.arroyochurch.com directly, never arroyochurch.com/sermon-notes: Squarespace's
redirect drops the ?week= part, so every post would open on the latest week instead.
"""

import json
import re
import subprocess
from datetime import date, datetime, timedelta
from typing import NamedTuple
from zoneinfo import ZoneInfo

NOTES_PAGE = "https://links.arroyochurch.com/notes/"
CHURCH_TZ = ZoneInfo("America/Los_Angeles")   # service dates are church time, wherever the Mac is


def notes_url(service: date) -> str:
    return f"{NOTES_PAGE}?week={service.isoformat()}"


def sunday_on_or_before(d: date) -> date:
    """The Sunday on or before d (d itself on a Sunday). Notes weeks are keyed by Sunday."""
    return d - timedelta(days=(d.weekday() + 1) % 7)


LIVE = {"is_live", "was_live", "post_live"}         # yt-dlp live_status values for a livestream


def youtube_date(video_id: str):
    """(date, streamed) YouTube has for the video, in church time: when the livestream started
    (release_timestamp), else its publish time, else its upload date; streamed = it was a
    livestream (live_status), not an upload. None when yt-dlp cannot say (offline, a bot check,
    private, not processed yet) -- the caller falls back."""
    try:
        out = subprocess.run(
            ["yt-dlp", "--skip-download", "--no-playlist", "--quiet", "--no-warnings",
             "--print", "%(release_timestamp)s %(timestamp)s %(upload_date)s %(live_status)s",
             f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, timeout=120, check=True,
        ).stdout.split()
    except Exception:
        return None
    streamed = len(out) > 3 and out[3] in LIVE
    for ts in out[:2]:                                   # epoch seconds, or "NA"
        if ts.isdigit():
            return datetime.fromtimestamp(int(ts), CHURCH_TZ).date(), streamed
    if len(out) > 2 and re.fullmatch(r"\d{8}", out[2]):  # YYYYMMDD
        return datetime.strptime(out[2], "%Y%m%d").date(), streamed
    return None


def notes_listed(service: date, index_file):
    """Is this week in the web notes index (data/sermon-notes/index.json, which run-blog.sh's
    git pull keeps fresh)? None when the index is missing or unreadable."""
    try:
        weeks = json.loads(index_file.read_text(encoding="utf-8")).get("weeks") or []
    except Exception:
        return None
    return any(isinstance(w, dict) and w.get("service") == service.isoformat() for w in weeks)


class NotesLink(NamedTuple):
    service: date        # the week the link points at
    source: str          # where that date came from (for the log and the paste header)
    url: str
    add: bool            # False: the draft gets no link -- the warnings say why
    warnings: tuple      # one-line WARNINGs for the log and the paste header; often empty


def notes_link(video_id, env, index_file, today=None, lookup=youtube_date) -> NotesLink:
    """Which week's notes the draft links, and whether it links them at all. The week, in order:
      1. BLOG_SERVICE_DATE=YYYY-MM-DD -- always wins. Set it when YouTube's date is not the day it
         was preached: a re-upload, or a recording posted after the following Sunday.
      2. YouTube's date for the video (stream start, else upload), back to its Sunday. A stream
         on another day (Christmas Eve, Good Friday) links notes of its own date when the index
         has them, else nothing: the Sunday before is a different sermon.
      3. The most recent Sunday in church time (today, when today is a Sunday) -- a guess, so it
         comes with a WARNING (it is wrong for a catch-up run on an older sermon).
    No link when the index says that week has no notes (a guest speaker, an outline that never
    came): the notes page would show another sermon's notes under this recap. The WARNING says
    how to add it by hand if they go up later. Same rule as the YouTube SERMON NOTES block.
    A malformed BLOG_SERVICE_DATE raises ValueError: a typo must not quietly link the wrong week."""
    raw = (env.get("BLOG_SERVICE_DATE") or "").strip()
    guessed = False
    if raw:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            raise ValueError(f"BLOG_SERVICE_DATE={raw!r} is not YYYY-MM-DD")
        service, source = date.fromisoformat(raw), "BLOG_SERVICE_DATE"
    else:
        yt = lookup(video_id) if video_id else None
        if yt:
            day, streamed = yt
            service, source = sunday_on_or_before(day), "the video's YouTube date"
            if streamed and day != service:              # a livestream on a weekday
                if notes_listed(day, index_file):
                    service, source = day, f"the stream date (a {day:%A} service with its own notes)"
                else:
                    return NotesLink(service, source, notes_url(service), False, (
                        f"WARNING: streamed {day:%a %Y-%m-%d}, not a Sunday, and no web notes for that "
                        f"date -- no Sermon notes link added (the {service} notes are a different "
                        "sermon's). If this service gets its own notes, add the link by hand.",))
        else:
            service, source = sunday_on_or_before(today or datetime.now(CHURCH_TZ).date()), "the most recent Sunday"
            guessed = True
    url = notes_url(service)
    listed = notes_listed(service, index_file)
    if listed is False:
        return NotesLink(service, source, url, False, (
            f"WARNING: no web notes for {service} in data/sermon-notes/index.json"
            f"{' (a guess: YouTube gave no date for this video)' if guessed else ''} -- no Sermon "
            f'notes link added. If that week\'s notes go up later, add <a href="{url}">Sermon notes</a> '
            "to the closing line before publishing.",))
    warnings = []
    if guessed:
        warnings.append(f"WARNING: YouTube gave no date for this video, so the notes week is a guess (the "
                        f"most recent Sunday, {service}) -- if the sermon is older, fix the link's ?week= "
                        "date before publishing.")
    if listed is None:
        warnings.append("WARNING: data/sermon-notes/index.json is unreadable -- the Sermon notes link "
                        "went in unchecked; open it and make sure it shows that week before publishing.")
    return NotesLink(service, source, url, True, tuple(warnings))


# The closing CTA line the prompt asks for: <a href="/messages">Watch more sermons</a> SEP
# <a href="/plan-your-visit">Plan your visit</a>. SEP varies by week (&middot;, &bull;,
# &nbsp;|&nbsp;, &mdash;), so it is captured and reused around the new link.
CTA = re.compile(r'(<a href="/messages">[^<]*</a>)([^<]{0,40}?)(?=<a href="/plan-your-visit">)')
MESSAGES_LINK = re.compile(r'<a href="(?:https?://(?:www\.)?arroyochurch\.com)?/messages/?">[^<]*</a>')


def add_notes_link(body_html: str, url: str) -> str:
    """Add a 'Sermon notes' link for the week to the draft body, deterministically (the model is
    never asked for it): between 'Watch more sermons' and 'Plan your visit' with the same
    separator; else right after the last /messages link; else as its own closing paragraph.
    Running it twice is a no-op."""
    if url in body_html:
        return body_html
    link = f'<a href="{url}">Sermon notes</a>'
    out, n = CTA.subn(lambda m: f"{m.group(1)}{m.group(2)}{link}{m.group(2)}", body_html, count=1)
    if n:
        return out
    last = None
    for last in MESSAGES_LINK.finditer(body_html):
        pass
    if last:
        return f"{body_html[:last.end()]} &middot; {link}{body_html[last.end():]}"
    return f"{body_html}<p>{link}</p>"

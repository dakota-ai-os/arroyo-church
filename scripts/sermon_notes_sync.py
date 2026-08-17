#!/usr/bin/env python3
"""
Sermon notes email  ->  shared Apple Note.  Unattended.

Josh emails the week's sermon notes to av@arroyochurch.com. This pulls the most
recent one and replaces the body of a shared Apple Note so it's current before
Sunday service.

WHY THIS EXISTS / WHY LAUNCHD:
This replaces a Cowork task that worked but re-prompted for Apple Notes access
EVERY run. macOS ties an Automation grant to the identity of the requesting
process; Cowork's helper identity isn't stable across runs, so TCC treated each
Sunday as a brand-new requester. A launchd agent running this script is a stable
identity -- approve once and macOS remembers it (same as com.arroyo.blog, which
has run unattended for weeks).

CONFIG -- ~/.config/arroyo/gmail.env (chmod 600, OUTSIDE the repo):
    GMAIL_USER=av@arroyochurch.com
    GMAIL_APP_PASSWORD=xxxxxxxxxxxxxxxx      # Google app password, not the login password
    SERMON_SENDER=josh@arroyochurch.com      # who sends the notes
    NOTE_ID=x-coredata://.../ICNote/pNNNN    # STABLE id of the note (title changes weekly)
    LOOKBACK_DAYS=8                          # optional; how far back to search

SAFETY: the note is only ever rewritten when a matching email with a non-empty
body is found. No email, or an empty one, means the note is left completely
alone -- it will never be blanked. The previous body is archived to
~/.config/arroyo/note-backups/ before every write.
"""

import email
import email.utils
import html
import imaplib
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from pathlib import Path

CONFIG = Path.home() / ".config" / "arroyo" / "gmail.env"
BACKUPS = Path.home() / ".config" / "arroyo" / "note-backups"


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def load_config():
    if not CONFIG.exists():
        sys.exit(f"ERROR: {CONFIG} not found. See the header of this file for the required keys.")
    cfg = {}
    for line in CONFIG.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        cfg[k.strip()] = v.strip().strip('"').strip("'")
    for required in ("GMAIL_USER", "GMAIL_APP_PASSWORD", "SERMON_SENDER", "NOTE_ID"):
        if not cfg.get(required):
            sys.exit(f"ERROR: {required} missing from {CONFIG}")
    cfg.setdefault("LOOKBACK_DAYS", "8")
    return cfg


def _clean_pw(pw):
    """Google shows app passwords in 4-char groups; copying from the browser often
    yields NON-BREAKING spaces (U+00A0), which imaplib cannot ascii-encode. Keep
    only alphanumerics -- app passwords are 16 lowercase letters."""
    return re.sub(r"[^A-Za-z0-9]", "", pw)


def fetch_latest(cfg):
    """Newest email from SERMON_SENDER within LOOKBACK_DAYS. Returns (subject, date, text) or None."""
    since = (datetime.now(timezone.utc) - timedelta(days=int(cfg["LOOKBACK_DAYS"]))).strftime("%d-%b-%Y")
    M = imaplib.IMAP4_SSL("imap.gmail.com")
    try:
        M.login(cfg["GMAIL_USER"], _clean_pw(cfg["GMAIL_APP_PASSWORD"]))
        M.select("INBOX", readonly=True)  # readonly: never marks Josh's mail as read
        # MUST filter on subject: Josh's newest email is often unrelated (worship-night
        # graphics, etc). Grabbing "latest from Josh" would overwrite the note with that.
        subj_key = cfg.get("SUBJECT_CONTAINS", "Sermon Notes")
        typ, data = M.search(None, f'(FROM "{cfg["SERMON_SENDER"]}" SUBJECT "{subj_key}" SINCE {since})')
        ids = data[0].split() if typ == "OK" and data and data[0] else []
        if not ids:
            return None
        typ, raw = M.fetch(ids[-1], "(RFC822)")  # last id = newest
        if typ != "OK":
            return None
        msg = email.message_from_bytes(raw[0][1])
    finally:
        try:
            M.close()
        except Exception:
            pass
        M.logout()

    subject = str(make_header(decode_header(msg.get("Subject", "") or "")))
    try:
        when = email.utils.parsedate_to_datetime(msg.get("Date"))
    except Exception:
        when = datetime.now(timezone.utc)

    text, html_body = "", ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart" or part.get_filename():
                continue
            try:
                payload = part.get_payload(decode=True) or b""
                body = payload.decode(part.get_content_charset() or "utf-8", "replace")
            except Exception:
                continue
            if part.get_content_type() == "text/plain" and not text:
                text = body
            elif part.get_content_type() == "text/html" and not html_body:
                html_body = body
    else:
        payload = msg.get_payload(decode=True) or b""
        body = payload.decode(msg.get_content_charset() or "utf-8", "replace")
        if msg.get_content_type() == "text/html":
            html_body = body
        else:
            text = body

    if not text and html_body:
        text = re.sub(r"<br\s*/?>|</p>", "\n", html_body, flags=re.I)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)

    # Josh re-sends corrections ("Disregard the first email...this one is the truth").
    # Those are replies, so drop the quoted original or it gets duplicated into the note.
    text = re.split(r"^On .+ wrote:\s*$", text, maxsplit=1, flags=re.M)[0]
    text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith(">"))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return (subject, when, text) if text else None


def run_osascript(script, timeout=90):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"osascript exited {r.returncode}")
    return r.stdout.strip()


PREAMBLE = re.compile(
    r"^\s*(disregard|ignore|sorry|oops|correction|use this|this one|please use|my bad)\b", re.I)


def split_title_and_body(text):
    """Josh's SUBJECT is 'Sermon Notes 8/16/26' -- the sermon TITLE is the first real
    line of the body. Corrections open with chatter ("Disregard the first email...this
    one is the truth : )"), so skip leading preamble lines before taking the title."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if PREAMBLE.match(line) and len(line) < 120:
            i += 1
            continue
        break
    title = lines[i].strip() if i < len(lines) else ""
    return title, "\n".join(lines[i + 1:]).strip()


def sunday_from_subject(subject, fallback):
    """'Sermon Notes 8/16/26' -> the service date. Byline uses the SERVICE date, not the
    date Josh happened to send the email (he writes them days ahead)."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", subject or "")
    if m:
        mo, d, y = (int(x) for x in m.groups())
        y += 2000 if y < 100 else 0
        try:
            return datetime(y, mo, d)
        except ValueError:
            pass
    return fallback


def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1:'st',2:'nd',3:'rd'}.get(n % 10, 'th')}"


def tidy_points(body):
    """Josh's plaintext arrives as '   1.\n\n   Learn who...' (Google Docs paste). Rejoin a
    lone list marker with the text beneath it so the note reads as clean numbered points."""
    out, lines, i = [], body.splitlines(), 0
    while i < len(lines):
        cur = lines[i].strip()
        if re.fullmatch(r"\d+\.", cur):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                out.append(f"{cur} {lines[j].strip()}")
                i = j + 1
                continue
        out.append(cur)
        i += 1
    joined = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    # Gmail hard-wraps at ~76 cols, so a single scripture quote arrives split across lines.
    # Unwrap each blank-line-delimited block back into one line, matching how the note reads.
    blocks = [" ".join(x.strip() for x in b.splitlines() if x.strip())
              for b in re.split(r"\n\s*\n", joined)]
    return "\n\n".join(b for b in blocks if b)


def key_takeaway(title, body):
    """One-sentence summary, same Anthropic key the blog pipeline uses. Best-effort:
    if the API is unreachable the note still gets written, just without this line."""
    env = Path.home() / ".config" / "arroyo" / "anthropic.env"
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key and env.exists():
        for line in env.read_text().splitlines():
            if line.strip().startswith("ANTHROPIC_API_KEY"):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        log("WARNING: no Anthropic key found -- skipping KEY TAKEAWAY")
        return ""
    try:
        import anthropic
        msg = anthropic.Anthropic(api_key=key).messages.create(
            model="claude-opus-4-8", max_tokens=300,
            messages=[{"role": "user", "content":
                "Write ONE sentence (max 40 words) summarising this sermon, in EXACTLY this "
                "house style: a short declarative thesis, then an em-dash, then a "
                "comma-separated list of gerund phrases.\n"
                "Example of the required style: \"Healthy relationships take wisdom \u2014 "
                "knowing who to trust, speaking and listening like Christ, discerning when "
                "to confront, giving people room, and letting love cover offenses instead "
                "of stirring up strife.\"\n"
                "Do NOT use imperative commands ('Invest', 'Speak', 'Build'). Do NOT add "
                "quotes, a label, or any preamble. Output only the sentence.\n\n"
                f"Title: {title}\n\n{body[:6000]}"}])
        return " ".join(msg.content[0].text.split()).strip('"')
    except Exception as e:
        log(f"WARNING: KEY TAKEAWAY generation failed ({e}) -- continuing without it")
        return ""


def header_image_tag(note_id):
    """Return the <img> tag for the series graphic, keeping it alive across rewrites.

    Notes stores an image pasted in the UI as an INLINE base64 data URI, which the body
    getter exposes. But an image written back BY APPLESCRIPT is not re-exposed that way --
    the next read returns a bare placeholder. So a naive read-modify-write looks fine the
    first Sunday and then silently deletes the graphic the second. (Verified on a scratch
    note: attachments 1 -> 0.)

    Fix: cache the graphic on disk. Refresh the cache whenever the note DOES expose a real
    base64 image -- which is exactly what happens after someone pastes a new series graphic
    in -- and otherwise re-inject the cached copy. The graphic changes once per sermon
    series, so this self-heals without anyone touching the automation.
    """
    cache = Path.home() / ".config" / "arroyo" / "sermon-note-header.txt"
    try:
        body = run_osascript(f'tell application "Notes" to return body of note id "{note_id}"', timeout=240)
        m = re.search(r"<img\b[^>]*src=\"data:image/[^\"]+\"[^>]*>", body)
        if m:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(m.group(0), encoding="utf-8")
            log(f"series graphic found in note ({len(m.group(0)):,} bytes) -- cache refreshed")
            return m.group(0)
    except Exception as e:
        log(f"WARNING: could not read note for the graphic ({e})")

    if cache.exists():
        tag = cache.read_text(encoding="utf-8")
        log(f"re-injecting cached series graphic ({len(tag):,} bytes)")
        return tag
    log("WARNING: no series graphic available -- writing the note without it")
    return ""


def update_note(note_id, subject, when, text):
    """Rebuild the shared note: sermon title, byline, preserved image, standing
    instruction line, KEY TAKEAWAY, then Josh's points."""
    esc = lambda x: html.escape(x, quote=False)

    title, points = split_title_and_body(text)
    service = sunday_from_subject(subject, when)
    points = tidy_points(points)
    # the note uses straight quotes throughout; Josh's email mixes curly and straight
    points = points.translate(str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'"}))
    takeaway = key_takeaway(title, points)
    img = header_image_tag(note_id)

    log(f'title="{title}"  service={service:%Y-%m-%d}  takeaway={"yes" if takeaway else "no"}')

    byline = f"Pastor Josh Smith | {service:%B} {ordinal(service.day)}, {service:%Y}"
    instruct = ("*To save and edit this note, click on the share button at the top, press "
                "\u201ccopy\u201d then, create a new note and paste the text into your new note")

    parts = [
        f"<div><b><h1>{esc(title)}</h1></b></div>",
        f"<div><b>{esc(byline)}</b><br></div>",
    ]
    if img:
        parts.append(f"<div>{img}<br></div>")
    # instruction line is ITALIC; KEY TAKEAWAY is plain (NOT bold) -- matches the house format
    parts.append(f"<div><i>{esc(instruct)}</i></div><div><br></div>")
    if takeaway:
        parts.append(f"<div>KEY TAKEAWAY: {esc(takeaway)}</div><div><br></div>")
    for line in points.splitlines():
        if not line.strip():
            parts.append("<div><br></div>")
        elif re.match(r"^\d+\.\s", line.strip()):
            parts.append(f"<div><h2>{esc(line.strip())}</h2></div>")   # numbered points are headings
        else:
            parts.append(f"<div>{esc(line)}</div>")
    body = "".join(parts)

    tmp = Path("/tmp/arroyo-sermon-note.html")
    tmp.write_text(body, encoding="utf-8")

    BACKUPS.mkdir(parents=True, exist_ok=True)
    quoted = note_id.replace('"', '\\"')
    try:
        prev = run_osascript(f'tell application "Notes" to return body of note id "{quoted}"', timeout=180)
        if prev:
            stamp = BACKUPS / f"{datetime.now():%Y-%m-%d-%H%M%S}.html"
            stamp.write_text(prev, encoding="utf-8")
            log(f"backed up previous note ({len(prev)} bytes) -> {stamp}")
    except Exception as e:
        log(f"WARNING: could not back up existing note ({e})")

    run_osascript(f'''
        set theHTML to (read (POSIX file "{tmp}") as «class utf8»)
        tell application "Notes" to set body of note id "{quoted}" to theHTML
    ''', timeout=240)
    return title


def main():
    cfg = load_config()
    log(f"looking for mail from {cfg['SERMON_SENDER']} (last {cfg['LOOKBACK_DAYS']} days)")

    found = fetch_latest(cfg)
    if not found:
        log("no matching sermon-notes email found -- leaving the note untouched.")
        return 0

    subject, when, text = found
    log(f'found "{subject}" ({when:%a %b %d %H:%M}) -- {len(text)} chars')

    title = update_note(cfg["NOTE_ID"], subject, when, text)
    log(f'updated the shared Apple Note -> retitled "{title}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())

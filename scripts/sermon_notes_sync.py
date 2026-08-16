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
        typ, data = M.search(None, f'(FROM "{cfg["SERMON_SENDER"]}" SINCE {since})')
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

    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return (subject, when, text) if text else None


def run_osascript(script, timeout=90):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"osascript exited {r.returncode}")
    return r.stdout.strip()


def update_note(note_id, subject, when, text):
    """Replace the note body. Content is passed via a temp FILE, never interpolated
    into AppleScript source -- an apostrophe or quote in Josh's notes would
    otherwise break the script (or worse)."""
    esc = lambda s: html.escape(s, quote=False)
    lines = "".join(f"<div>{esc(l) if l.strip() else '<br>'}</div>" for l in text.splitlines())
    # Notes derives a note's TITLE from the first line of its body. The shared note is
    # retitled to that week's sermon each Sunday, so emit the sermon title first and the
    # rename happens for free. The note is found by ID, so retitling can't break lookup.
    title = subject.strip() or f"Sermon Notes {when:%b %-d}"
    body = (
        f"<div><b>{esc(title)}</b></div><div><br></div>"
        f"{lines}"
    )

    tmp = Path("/tmp/arroyo-sermon-note.html")
    tmp.write_text(body, encoding="utf-8")

    BACKUPS.mkdir(parents=True, exist_ok=True)
    quoted = note_id.replace('"', '\\"')

    try:
        prev = run_osascript(f'tell application "Notes" to return body of note id "{quoted}"')
        if prev:
            stamp = BACKUPS / f"{datetime.now():%Y-%m-%d-%H%M%S}.html"
            stamp.write_text(prev, encoding="utf-8")
            log(f"backed up previous note body -> {stamp}")
    except Exception as e:
        log(f"WARNING: could not back up existing note ({e})")

    run_osascript(f'''
        set theHTML to (read (POSIX file "{tmp}") as «class utf8»)
        tell application "Notes" to set body of note id "{quoted}" to theHTML
    ''')
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

#!/usr/bin/env python3
"""
Sermon notes email  ->  shared Apple Note.  Unattended.

The week's preacher emails sermon material to av@arroyochurch.com. This pulls the
most recent one and replaces the body of a shared Apple Note so it's current before
Sunday service.

TWO SENDERS, TWO FORMATS (both handled):
  * Josh sends a Google-Docs OUTLINE  -- subject "Sermon Notes 9/13/26"
  * A guest sends a SLIDE LIST        -- subject "Slides" (Cristian Ayquipa, 2026-09-06)
Sender and subject are both allowlists (see allowed_senders / allowed_subjects), and
anything matched only by a loose keyword like "slides" must also cite scripture
(looks_like_sermon) before it is allowed to overwrite the note.

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
import time
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from pathlib import Path

INSTRUCT_COLOR = "#AF52DE"   # Apple system purple; change here to restyle the notice

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


def _csv(cfg, key, fallback):
    """Comma-separated config value -> lowercased list. Falls back to the old single-value
    key so an un-migrated gmail.env keeps working."""
    raw = cfg.get(key) or fallback
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def allowed_senders(cfg):
    """Who may set the note. Josh preaches most weeks, but guests preach too (Cristian
    Ayquipa, John 15, 2026-09-06) and they send from their OWN church address -- a
    single-sender filter silently skips those weeks and the note goes stale.

    SERMON_SENDERS accepts full addresses AND bare domains ("@arroyochurch.com"), so a
    new guest needs no config change. Sender alone is deliberately NOT enough to pass:
    Josh also emails graphics and announcements from the same address, so the subject
    allowlist below still has to match."""
    return _csv(cfg, "SERMON_SENDERS", cfg["SERMON_SENDER"] + ",@arroyochurch.com")


def allowed_subjects(cfg):
    """Subject keywords that mark an email as THE sermon material.

    "slides" is here because guests send a deck rather than an outline -- but it is a
    generic word, so anything matched only by a loose keyword must also pass the
    scripture gate in looks_like_sermon(). "sermon notes"/"sermon outline" are
    unambiguous and skip that gate."""
    return _csv(cfg, "SUBJECT_KEYWORDS",
                cfg.get("SUBJECT_CONTAINS", "Sermon Notes") + ",sermon outline,slides,sermon")


STRICT_SUBJECTS = ("sermon notes", "sermon outline")

# Book chapter:verse -- the cheapest reliable "this is sermon material" signal.
SCRIPTURE_ANYWHERE = re.compile(r"\b(?:[1-3]\s*)?[A-Z][a-z]{2,}\s+\d{1,3}:\d{1,3}")


def looks_like_sermon(subject, text):
    """Guard for the loose keywords. An unambiguous subject passes on its own; anything
    else must actually cite scripture. Stops an announcements deck subject-lined "Slides"
    from overwriting the note with graphics chatter."""
    s = (subject or "").lower()
    if any(k in s for k in STRICT_SUBJECTS):
        return True
    return bool(SCRIPTURE_ANYWHERE.search(text or ""))


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
        M.select("INBOX", readonly=True)  # readonly: never marks the sender's mail as read
        # Filter in Python rather than with an IMAP query. The allowlists are now
        # multi-sender AND multi-subject, and IMAP's prefix-notation OR nests horribly
        # past two terms. The mailbox holds ~12 messages a week, so scanning headers is
        # cheaper than getting the query wrong.
        #
        # MUST still filter on subject: the newest email from a preacher is often
        # unrelated (worship-night graphics, announcement decks). "Latest from Josh"
        # would overwrite the note with that.
        typ, data = M.search(None, f"(SINCE {since})")
        ids = data[0].split() if typ == "OK" and data and data[0] else []
        senders, subjects = allowed_senders(cfg), allowed_subjects(cfg)

        best = None                                   # (datetime, message-id) of the winner
        for mid in ids:
            typ, hdr = M.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if typ != "OK" or not hdr or not hdr[0]:
                continue
            h = email.message_from_bytes(hdr[0][1])
            frm = str(make_header(decode_header(h.get("From", "") or ""))).lower()
            sub = str(make_header(decode_header(h.get("Subject", "") or "")))
            addr = email.utils.parseaddr(frm)[1]
            if not any(addr == s or addr.endswith(s) for s in senders):
                continue
            if not any(k in sub.lower() for k in subjects):
                continue
            try:
                when_h = email.utils.parsedate_to_datetime(h.get("Date"))
                if when_h.tzinfo is None:
                    when_h = when_h.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if best is None or when_h > best[0]:
                best = (when_h, mid)

        if best is None:
            return None
        typ, raw = M.fetch(best[1], "(RFC822)")
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


# A correction line is also recognised by WHAT IT SAYS, not just how it opens. Josh typo'd
# "Disreagrd" on 2026-08-20 and the opener list missed it, so the preamble became the sermon
# title. Phrase matching survives misspellings of the first word.
PREAMBLE_HINT = re.compile(
    r"(last|previous|first|other)\s+email|real\s+outline|correct(ed)?\s+(one|outline)|"
    r"below\s+is\s+the|here\s+is\s+the\s+(real|right|correct)",
    re.I,
)
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
        if (PREAMBLE.match(line) or PREAMBLE_HINT.search(line)) and len(line) < 160:
            i += 1
            continue
        break
    title = lines[i].strip() if i < len(lines) else ""
    return title, "\n".join(lines[i + 1:]).strip()


# ---------------------------------------------------------------- guest slide decks
# Josh sends a Google-Docs OUTLINE: a lone "N." marker on its own line, text indented
# beneath, main-vs-sub told apart by the numbering run (see parse_structure).
#
# A guest sends a SLIDE LIST instead -- "N. <slide text>" all on one line, where N is the
# slide number, not an outline level. Cristian Ayquipa, 2026-09-06:
#     1. Title- STAYING CONNECTED
#     4. Point 1- PRUNING IS PART OF
#     STAYING CONNECTED
# Run that through parse_structure and you get eleven "main points" -- the deck's slide
# numbers -- and no real structure. The actual outline lives in the "Title-"/"Point N-"
# labels, so detect the shape and parse those instead.

SLIDE_LINE   = re.compile(r"^\s*(\d{1,2})\.\s+(\S.*)$")
SLIDE_TITLE  = re.compile(r"^title\s*[-–:]\s*(.+)$", re.I)
SLIDE_POINT  = re.compile(r"^point\s*(\d+)\s*[-–:]\s*(.*)$", re.I)
BARE_REF     = re.compile(r"^\s*(?:[1-3]\s*)?[A-Z][a-z]{2,}\s+\d{1,3}:\d{1,3}(?:\s*[-–]\s*\d{1,3})?\s*$")
BULLET       = re.compile(r"^\s*[-•–]\s+(\S.*)$")


def looks_like_slides(text):
    """True when the body is a slide list rather than an outline. Requires several
    inline-numbered lines forming a run from 1, so a stray '1. something' in prose
    cannot flip a normal outline into slide mode."""
    nums = [int(m.group(1)) for m in
            (SLIDE_LINE.match(l) for l in text.splitlines()) if m]
    return len(nums) >= 4 and nums[0] == 1 and nums == sorted(nums)


def parse_slides(text):
    """Slide list -> (title, blocks) in the same vocabulary parse_structure emits.

    Slide numbers are dropped -- they are deck bookkeeping, not outline levels. A slide
    carrying "Point N-" becomes a main heading (its text may wrap onto the slide's later
    lines); everything else becomes content under the current point."""
    # group the flat lines into slides
    slides, cur = [], None
    for line in text.splitlines():
        m = SLIDE_LINE.match(line)
        if m:
            if cur is not None:
                slides.append(cur)
            cur = [m.group(2).strip()]
        elif cur is not None and line.strip():
            cur.append(line.strip())
    if cur is not None:
        slides.append(cur)

    title, blocks = "", []
    for slide in slides:
        head = slide[0]

        mt = SLIDE_TITLE.match(head)
        if mt and not title:
            title = " ".join([mt.group(1).strip()] + slide[1:]).strip()
            continue

        mp = SLIDE_POINT.match(head)
        if mp:
            # a Point slide is ONE heading; its wrapped remainder belongs to the heading
            body = " ".join([mp.group(2).strip()] + slide[1:]).strip()
            blocks.append(("main", f"{mp.group(1)}. {body}"))
            continue

        # ordinary content slide
        i = 0
        while i < len(slide):
            ln = slide[i]
            mb = BULLET.match(ln)
            if mb:
                blocks.append(("sub", mb.group(1).strip()))
                i += 1
                continue
            if ln[:1] in '"“':
                # A verse is hard-wrapped by Gmail, so rejoin until the closing quote,
                # then pull in the reference that follows on its own line. House style
                # keeps them as one block: "quote" -Book c:v
                quote, i = [ln], i + 1
                while not quote[-1].rstrip().endswith(('"', '”')) and i < len(slide):
                    quote.append(slide[i]); i += 1
                q = " ".join(quote)
                if i < len(slide) and BARE_REF.match(slide[i]):
                    q = f"{q} -{slide[i].strip()}"
                    i += 1
                blocks.append(("text", q))
                continue
            # Only a slide's FIRST line can head the ones under it, and a line ending in
            # a full stop is a statement, not a heading -- that keeps "THE TRUE VINE" and
            # "3 WAYS TO STAY CONNECTED" as headings while the three-line framing
            # ("JESUS IS THE SOURCE.") stays body text.
            if i == 0 and not ln.rstrip().endswith(".") \
                    and _is_subheading(ln) and not BARE_REF.match(ln):
                blocks.append(("subhead", ln))
            else:
                blocks.append(("text", ln))
            i += 1

    if not title:                      # no explicit "Title-" label; fall back to slide 1
        title = slides[0][0].strip() if slides else ""
    return title, blocks


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


SCRIPTURE_REF = re.compile(r"[-\u2013]\s*(?:[1-3]\s*)?[A-Z][a-z]+\s+\d+:\d")


def _is_subheading(text):
    """A flush-left line that is NOT scripture -- e.g. '3 Ways to Communicate Like Christ'.
    Scripture is flush-left too, but it opens with a quote and carries a -Book c:v citation."""
    t = text.strip()
    return (len(t) < 80
            and not t[:1] in '"\u201c\u2018\''
            and not SCRIPTURE_REF.search(t))


def parse_structure(body):
    """Turn Josh's Google-Docs plaintext into typed blocks.

    The hard part: MAIN points and SUB points are indistinguishable by indentation --
    both arrive as '   N.' on their own line followed by indented text. The only reliable
    signal is the NUMBERING SEQUENCE: main points run 1,2,3,4,5 monotonically, while a
    sub-list restarts at 1 and then main resumes where it left off. So track the expected
    main number; anything that doesn't continue that run is a sub-point.
    """
    lines, items, i = body.splitlines(), [], 0
    while i < len(lines):
        raw = lines[i]
        cur = raw.strip()
        if not cur:
            i += 1
            continue
        m = re.fullmatch(r"(\d+)\.", cur)
        if m:                                   # lone list marker; text follows below
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            txt = []
            while j < len(lines) and lines[j].strip():
                txt.append(lines[j].strip())
                j += 1
            items.append(("num", int(m.group(1)), " ".join(txt)))
            i = j
        else:                                   # prose block (Gmail hard-wraps it)
            txt, j = [cur], i + 1
            while j < len(lines) and lines[j].strip():
                txt.append(lines[j].strip())
                j += 1
            items.append(("flush" if not raw.startswith(" ") else "ind", None, " ".join(txt)))
            i = j

    # A plain "does this continue the main run?" test is not enough: a sub-list of three
    # items reaches 3 exactly when the next MAIN point is also 3, which swaps them. So track
    # the sub-list's own run too -- stay in the nested list only while its numbering keeps
    # incrementing, then fall back and re-test against the main run.
    out, expected, sub_n, in_sub = [], 1, 0, False
    for kind, num, text in items:
        if kind == "num":
            if in_sub and num == sub_n + 1:
                out.append(("sub", text))
                sub_n = num
                continue
            in_sub = False
            if num == expected:
                out.append(("main", f"{num}. {text}"))
                expected += 1
            elif num == 1 and expected > 1:     # numbering restarted => nested list opens
                in_sub, sub_n = True, 1
                out.append(("sub", text))
            else:
                out.append(("sub", text))
        elif _is_subheading(text):
            out.append(("subhead", text))
        else:
            out.append(("text", text))
    return out


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


# ── UI-driven editing ────────────────────────────────────────────────────────────────────
# Notes' AppleScript `set body` replaces EVERYTHING, which destroys the series graphic (an
# image can only be attached through a real UI paste). So the weekly text is written by
# selecting ONLY the text around the image and pasting over it. The image is never selected,
# so it is never touched, moved, or re-created.
#
# The clipboard must carry the public.html flavour: an RTF paste silently drops font colour
# (verified -- the purple notice came back black), while HTML preserves colour, italics,
# headings and lists.

def set_clipboard_html(html, plain=""):
    from AppKit import NSPasteboard, NSPasteboardTypeHTML, NSPasteboardTypeString
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    # Without an explicit charset Notes decodes the HTML as Windows-1252, so curly quotes
    # and em-dashes arrive as mojibake ("â€œcopyâ€").
    doc = '<meta charset="utf-8">' + html
    pb.setString_forType_(doc, NSPasteboardTypeHTML)
    pb.setString_forType_(plain or re.sub(r"<[^>]+>", " ", html), NSPasteboardTypeString)


def clipboard_has_image():
    """True if the clipboard holds image data. SAFETY GATE: after selecting a text region we
    copy it and check -- if an image came along, the selection is wrong and we abort rather
    than paste over the graphic."""
    from AppKit import NSPasteboard
    types = [str(t).lower() for t in NSPasteboard.generalPasteboard().types()]
    return any(k in t for t in types for k in ("tiff", "png", "image"))


def blocks_before_image(body_html):
    """How many top-level blocks precede the <img> -- i.e. which visual line the image sits on.
    None when the note has no image."""
    m = re.search(r"<img\b", body_html)
    if not m:
        return None
    return len(re.findall(r"<div|<h1|<h2|<ol|<ul|<p\b", body_html[:m.start()]))

INSTRUCT_MARK = "To save and edit this note"
NOTE_PROMPT = "<div><i>Write some notes here</i></div><div><br></div>"


def protected_blocks(body_html):
    """How many leading blocks the automation must NOT touch.

    The graphic and the "*To save and edit this note..." notice are both permanent -- the
    banner changes only when Dakota swaps the series by hand, and the notice never changes at
    all. Leaving the notice in place is what lets it stay PURPLE: Notes strips font colour on
    every paste, so the only way to keep colour is to never overwrite the line.

    Returns the number of blocks from the top through the last protected one, or None when
    there is no graphic (first run / graphic removed).
    """
    blocks = re.findall(r"<(?:div|h1|h2|ol|ul)\b.*?</(?:div|h1|h2|ol|ul)>", body_html, re.S)
    img_i = next((i for i, b in enumerate(blocks) if "<img" in b), None)
    if img_i is None:
        return None
    last = img_i
    # The notice sits under the graphic, but a UI paste can leave several empty blocks
    # between them, so scan generously rather than assuming it is adjacent.
    for j in range(img_i + 1, min(img_i + 12, len(blocks))):
        if INSTRUCT_MARK in re.sub(r"<[^>]+>", "", blocks[j]):
            last = j
            break
    return last + 1


def _ui(script, timeout=120):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200])
    return r.stdout.strip()


def _focus_note(note_id):
    # A wide window keeps the title/byline on one visual line each, so the arrow-key line
    # count used below stays accurate.
    _ui(
        'tell application "Notes"\n'
        '  activate\n'
        '  show note id "' + note_id + '"\n'
        'end tell\n'
        'delay 1.5\n'
        'tell application "System Events" to tell process "Notes"\n'
        '  set frontmost to true\n'
        '  delay 0.6\n'
        '  try\n'
        '    set size of front window to {1500, 950}\n'
        '    set position of front window to {30, 30}\n'
        '  end try\n'
        'end tell\n'
        'delay 0.8\n'
    )


def _keys(lines):
    body = "\n".join("  " + l for l in lines)
    _ui('tell application "System Events" to tell process "Notes"\n'
        '  set frontmost to true\n'
        '  delay 0.4\n' + body + '\nend tell\n')


def replace_around_image(note_id, header_html, body_html, skip_lines):
    """Rewrite the text ABOVE and BELOW the graphic without ever selecting the graphic.

    Layout assumed (img_line is derived from the note itself, not hardcoded):
        line 1            title      <- replaced
        line 2            byline     <- replaced
        line img_line     IMAGE      <- untouched
        line img_line+1.. body text  <- replaced

    The lower region is done FIRST: replacing it cannot shift the position of anything above
    it, whereas doing the header first could change the wrap and move the image.
    """
    up, down = "key code 126", "key code 125"

    # ---------- lower region: from the line after the image, to the end ----------
    _keys(['keystroke "a" using {command down}', "delay 0.3", up, "delay 0.3"]
          + [down + "\n  delay 0.15" for _ in range(skip_lines)]
          + ["delay 0.3",
             'key code 125 using {command down, shift down}',
             "delay 0.4",
             'keystroke "c" using {command down}', "delay 0.6"])
    if clipboard_has_image():
        raise RuntimeError("ABORT: the lower selection included the graphic -- nothing written")
    set_clipboard_html(body_html)
    _keys(['keystroke "v" using {command down}', "delay 1.2"])

    # ---------- upper region: the first two lines (title + byline) ----------
    _keys(['keystroke "a" using {command down}', "delay 0.3", up, "delay 0.3",
           'key code 125 using {shift down}', "delay 0.2",
           'key code 125 using {shift down}', "delay 0.4",
           'keystroke "c" using {command down}', "delay 0.6"])
    if clipboard_has_image():
        raise RuntimeError("ABORT: the header selection included the graphic")
    set_clipboard_html(header_html)
    _keys(['keystroke "v" using {command down}', "delay 1.2"])


def update_note(note_id, subject, when, text):
    """Refresh the shared note's text, leaving the series graphic untouched.

    If the note has an image, only the text regions around it are replaced (via UI
    selection + HTML paste) -- the graphic is never selected, so it is never moved,
    re-created or lost. Dakota swaps the series banner by hand every few weeks and the
    automation must not interfere with it.

    With no image present, fall back to a plain AppleScript body write.
    """
    esc = lambda x: html.escape(x, quote=False)

    if looks_like_slides(text):
        log("body looks like a guest slide deck -- using the slide parser")
        title, blocks = parse_slides(text)
    else:
        title, rest = split_title_and_body(text)
        blocks = parse_structure(rest)
    service = sunday_from_subject(subject, when)
    straighten = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
    blocks = [(k, v.translate(straighten)) for k, v in blocks]
    takeaway = key_takeaway(title, "\n".join(v for _, v in blocks))
    log(f'title="{title}"  service={service:%Y-%m-%d}  takeaway={"yes" if takeaway else "no"}')

    byline = f"Pastor Josh Smith | {service:%B} {ordinal(service.day)}, {service:%Y}"
    instruct = ("*To save and edit this note, click on the share button at the top, press "
                "“copy” then, create a new note and paste the text into your new note")

    # snapshot before touching anything
    BACKUPS.mkdir(parents=True, exist_ok=True)
    quoted = note_id.replace('"', '\\"')
    # Wake Notes before asking it anything. On 2026-08-30 the 07:00 run hit AppleEvent
    # timeouts on every call: launchd fires into a session where Notes has been idle for
    # hours, and the first Apple event can outlast the timeout while it comes back.
    try:
        run_osascript('tell application "Notes" to activate', timeout=60)
        time.sleep(3)
    except Exception as e:
        log(f"WARNING: could not activate Notes ({e})")

    prev = ""
    read_ok = False
    for attempt in (1, 2, 3):
        try:
            prev = run_osascript(f'tell application "Notes" to return body of note id "{quoted}"', timeout=240)
            read_ok = True
            (BACKUPS / f"{datetime.now():%Y-%m-%d-%H%M%S}.html").write_text(prev, encoding="utf-8")
            break
        except Exception as e:
            log(f"WARNING: could not read/back up the note, attempt {attempt}/3 ({e})")
            if attempt < 3:
                time.sleep(10)

    keep_notice = bool(prev) and INSTRUCT_MARK in prev

    header_html = (f"<div><b><h1>{esc(title)}</h1></b></div>"
                   f"<div><b>{esc(byline)}</b></div>")

    # The notice is only emitted when the note does not already carry one. When it IS
    # present it lives inside the protected zone and is never overwritten -- that is what
    # preserves its purple, since Notes drops font colour on every paste.
    parts = []
    if not keep_notice:
        parts += [f'<div><i><span style="color:{INSTRUCT_COLOR}">{esc(instruct)}</span></i></div>',
                  "<div><br></div>"]
    if keep_notice:
        parts.append("<div><br></div>")   # the protected notice sits directly above
    if takeaway:
        parts.append(f"<div>KEY TAKEAWAY: {esc(takeaway)}</div><div><br></div>")
    i, seen_main = 0, False
    while i < len(blocks):
        kind, val = blocks[i]
        if kind == "sub":                      # indented, normal weight -- a real list is
            group = []                          # the only indentation Notes preserves
            while i < len(blocks) and blocks[i][0] == "sub":
                group.append(blocks[i][1]); i += 1
            def _li(g):
                # Dakota's original bolded the label and left the quote regular:
                #   **Understand the weight of your words:** "Death and life..."
                lbl, sep, rest = g.partition(":")
                if sep and len(lbl) < 60 and '"' not in lbl:
                    return f"<li><b>{esc(lbl)}:</b>{esc(rest)}</li>"
                return f"<li>{esc(g)}</li>"
            parts.append("<ol>" + "".join(_li(g) for g in group) + "</ol>")
            parts.append("<div><br></div>")   # blank line after a list, so the next main
            continue                          # point is not flush against the sub-points
        if kind == "main":
            if seen_main:            # close out the previous point before starting the next
                parts.append(NOTE_PROMPT)
            seen_main = True
            parts.append(f"<div><h2>{esc(val)}</h2></div><div><br></div>")
        elif kind == "subhead":
            parts.append(f"<div><h2>{esc(val)}</h2></div><div><br></div>")
        elif val.lstrip().startswith('"'):
            # Scripture: indent it so quotes read as distinct from Josh's teaching. Notes
            # only honours indentation it can model as a list (<blockquote> is silently
            # flattened to a plain div), so use a bulleted list. Consecutive verses are
            # grouped into ONE block so they read together, with a single blank line after.
            quotes = []
            while i < len(blocks) and blocks[i][0] not in ("main", "subhead", "sub") \
                    and blocks[i][1].lstrip().startswith('"'):
                quotes.append(blocks[i][1]); i += 1
            parts.append("".join(f"<div>{esc(q)}</div>" for q in quotes) + "<div><br></div>")
            parts.append("<div><br></div>")
            continue
        else:
            parts.append(f"<div>{esc(val)}</div><div><br></div>")
        i += 1
    if seen_main:                 # ...and after the final point
        parts.append(NOTE_PROMPT)
    body_html = "".join(parts)

    skip = protected_blocks(prev) if prev else None
    before = attachment_count(note_id)

    if skip:
        kept = "graphic + purple notice" if keep_notice else "graphic"
        log(f"protecting the first {skip} lines ({kept}); editing only around them")
        _focus_note(note_id)
        replace_around_image(note_id, header_html, body_html, skip)
        after = attachment_count(note_id)
        if before is not None and after is not None and after < before:
            raise RuntimeError(f"the graphic was lost ({before} -> {after} attachments)")
        if before is None or after is None:
            log("WARNING: could not count attachments -- graphic NOT verified, check by hand")
        else:
            log(f"graphic intact ({after} attachment) and verified")
    elif not read_ok:
        # 2026-08-30: Notes was unresponsive at 07:00, so the read above timed out and prev
        # stayed "". protected_blocks() was never consulted, skip fell to None, and control
        # reached the plain-body branch below -- which `set body`s over EVERYTHING and
        # destroyed the series graphic. A failed read is NOT evidence that the graphic is
        # absent, so it must never authorise the destructive write. Fail closed: a skipped
        # Sunday is recoverable, a deleted graphic is not (it can only be re-pasted by hand).
        raise RuntimeError(
            "could not read the note (Notes unresponsive) -- refusing the full-body write "
            "that would delete the series graphic. Re-run once Notes responds.")
    else:
        log("no graphic in the note -- plain body write")
        tmp = Path("/tmp/arroyo-sermon-note.html")
        tmp.write_text(header_html + body_html, encoding="utf-8")
        run_osascript(
            'set theHTML to (read (POSIX file "' + str(tmp) + '") as «class utf8»)\n'
            'tell application "Notes" to set body of note id "' + quoted + '" to theHTML',
            timeout=240)
    return title


def attachment_count(note_id):
    """Attachment count, or None when Notes would not answer.

    None (not 0) on failure: a failed query used to read as "zero attachments", which made
    the `after < before` guard below unfireable and let the run log "graphic intact" without
    having verified anything.
    """
    try:
        return int(run_osascript(
            f'tell application "Notes" to return count of attachments of note id "{note_id}"', timeout=180))
    except Exception:
        return None


def main():
    cfg = load_config()
    log(f"looking for mail from {'/'.join(allowed_senders(cfg))} "
        f"subject~{'|'.join(allowed_subjects(cfg))} (last {cfg['LOOKBACK_DAYS']} days)")

    found = fetch_latest(cfg)
    if not found:
        log("no matching sermon-notes email found -- leaving the note untouched.")
        return 0

    subject, when, text = found
    if not looks_like_sermon(subject, text):
        log(f'found "{subject}" but it cites no scripture and the subject is not an '
            f"explicit sermon-notes one -- treating it as unrelated, note left untouched.")
        return 0
    log(f'found "{subject}" ({when:%a %b %d %H:%M}) -- {len(text)} chars')

    title = update_note(cfg["NOTE_ID"], subject, when, text)
    log(f'updated the shared Apple Note -> retitled "{title}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())

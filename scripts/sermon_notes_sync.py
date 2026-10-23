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
  Optional extra Gmail mailboxes to read (none configured; av@ is the only one):
    GMAIL_USER_2=someone@arroyochurch.com
    GMAIL_APP_PASSWORD_2=xxxxxxxxxxxxxxxx
    GMAIL_MAILBOX_2=[Gmail]/All Mail         # default INBOX; All Mail still finds it once read/archived
  Add one with `bash scripts/add-gmail-account.sh someone@arroyochurch.com` -- it asks for
  the app password at a hidden prompt, tests the login, and writes these three lines.
  Built 2026-10-17 to read dakota@, where Josh had been sending the notes. Dropped
  2026-10-19: dakota@ has no Gmail to read, so Josh sends to av@ again. If an outline lands
  in dakota@ anyway, forward it to av@ FROM dakota@ (forwards are unwrapped and dated by the
  original; mail from outside @arroyochurch.com is ignored).

SAFETY: the note is only ever rewritten when a matching email with a non-empty
body is found. No email, or an empty one, means the note is left completely
alone -- it will never be blanked. The previous body is archived to
~/.config/arroyo/note-backups/ before every write.

WEB COPY (2026-10-23): the same outline is also published as JSON to the PUBLIC site repo
(data/sermon-notes/, served by GitHub Pages) so the website can show the notes -- Android and
anyone else without the shared Note. The page holds each week back until Sunday 06:45 church
time (release_at). It is written from a dedicated clone (see publish_web), never the working
repo, and keeps its own marker, so the web copy and the Note stand down independently.
WEB_NOTES=0 in gmail.env turns it off. `--web-only` publishes just the web copy (to seed the
page, or after a hand fix); `--force` redoes both.
"""

import email
import email.utils
import fcntl
import html
import imaplib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import hashlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from email.header import decode_header, make_header
from pathlib import Path

CHURCH_TZ = ZoneInfo("America/Los_Angeles")   # service dates are church time, wherever the Mac is

INSTRUCT_COLOR = "#AF52DE"   # Apple system purple; change here to restyle the notice

CONFIG = Path.home() / ".config" / "arroyo" / "gmail.env"
BACKUPS = Path.home() / ".config" / "arroyo" / "note-backups"
STATE = Path.home() / ".config" / "arroyo" / "last-written.txt"
WEB_STATE = Path.home() / ".config" / "arroyo" / "web-published.txt"     # same format, web copy only
OUTLINE_CACHE = Path.home() / ".config" / "arroyo" / "outline-cache.json"   # {version: KEY TAKEAWAY}

# Exit code meaning "the GUI session was not usable; try again later." The runner treats
# this as a quiet retry, NOT a failure, so a dark-wake attempt never raises an alarm.
EX_TEMPFAIL = 75


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


def accounts(cfg):
    """Every mailbox to search: (user, app password, mailbox). The primary account is
    GMAIL_USER (av@, which also sends the failure alerts); GMAIL_USER_2, _3 ... add more.

    Why more than one (2026-10-17): Josh was sending the notes to dakota@arroyochurch.com,
    so this was built to read dakota@ directly. It was never connected -- dakota@ has no
    Gmail -- so since 2026-10-19 Josh sends to av@ and av@ is the only mailbox. The rules
    below that mention dakota@ still guard any extra mailbox added later. A copy that lands
    elsewhere gets forwarded to av@ (unwrapped by strip_forward_header)."""
    out = [(cfg["GMAIL_USER"], cfg["GMAIL_APP_PASSWORD"], cfg.get("GMAIL_MAILBOX") or "INBOX")]
    n = 2
    while cfg.get(f"GMAIL_USER_{n}"):
        pw = cfg.get(f"GMAIL_APP_PASSWORD_{n}")
        if not pw:
            sys.exit(f"ERROR: GMAIL_USER_{n} is set but GMAIL_APP_PASSWORD_{n} is missing from {CONFIG}")
        out.append((cfg[f"GMAIL_USER_{n}"], pw, cfg.get(f"GMAIL_MAILBOX_{n}") or "INBOX"))
        n += 1
    return out


def content_hash(text):
    """Fingerprint of an outline's words, ignoring whitespace, quote style and case, so the
    same outline arriving again (a forward, a duplicate) is recognised as the same."""
    t = (text or "").replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    return hashlib.sha1(re.sub(r"\s+", " ", t).strip().lower().encode("utf-8")).hexdigest()[:12]


def marker_says_current(marker, service, when, text=None):
    """True when the note already carries this outline for this service.

    The marker (last-written.txt) is "<service date>|<sent time>|<content fingerprint>".
    * Same fingerprint -> the same outline arrived again (a forward, a re-run): stand down.
    * Different text sent LATER than what was published -> republish (a correction; the
      Saturday attempts run 20:00, 21:30 and 23:00, so a late fix still lands).
    * Older text -> stand down.
    A bare date (written before 2026-10-17) stands down as before."""
    svc, stamp, digest = ((marker or "").strip().split("|") + ["", ""])[:3]
    if svc != service:
        return False
    if not stamp:
        return True
    if digest and text is not None and digest == content_hash(text):
        return True
    try:
        return when <= datetime.fromisoformat(stamp)
    except (ValueError, TypeError):
        return True


def marker_value(service, when, text=""):
    return f"{service}|{when.isoformat()}|{content_hash(text)}"


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

# Book chapter:verse -- the cheapest reliable "this is sermon material" signal. It names REAL
# Bible books (2026-10-17 review): the old "any Capitalised word + n:n" pattern matched clock
# times, so a reply like "see you Sunday 9:30" counted as scripture.
BIBLE_BOOKS = (
    r"Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|Samuel|Kings|Chronicles|"
    r"Ezra|Nehemiah|Esther|Job|Psalms?|Proverbs|Ecclesiastes|Song of Solomon|Song of Songs|"
    r"Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|"
    r"Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|Matthew|Mark|Luke|John|Acts|Romans|"
    r"Corinthians|Galatians|Ephesians|Philippians|Colossians|Thessalonians|Timothy|Titus|"
    r"Philemon|Hebrews|James|Peter|Jude|Revelations?|Phillipians|Phillippians|"
    # common abbreviations, with or without a period (a guest wrote "-Eph 1:13-14")
    r"Gen|Exod?|Lev|Num|Deut|Josh|Judg|Sam|Kgs|Chr|Chron|Neh|Esth|Pss?|Psa|Prov|Eccl|Eccles|"
    r"Isa|Jer|Lam|Ezek|Dan|Hos|Obad|Mic|Nah|Hab|Zeph|Hag|Zech|Mal|Matt|Mt|Mk|Lk|Jn|Rom|Cor|"
    r"Gal|Eph|Phil|Col|Thess|Tim|Tit|Phlm|Heb|Jas|Pet|Rev")
# chapter:verse, but not a clock time: a verse never starts with 0 ("8:00") or carries am/pm.
_CV = r"\d{1,3}:(?!0)\d{1,3}(?!\d)(?!\s*[ap]\.?m\b)"
SCRIPTURE_ANYWHERE = re.compile(rf"\b(?:[1-3]\s*)?(?:{BIBLE_BOOKS})\.?\s+{_CV}")
BIBLE_REF_START = re.compile(rf"^\s*(?:[1-3]\s*)?(?:{BIBLE_BOOKS})\.?\s+{_CV}")
REF_LINE = re.compile(rf"^\s*[-\u2013]\s*(?:[1-3]\s*)?(?:{BIBLE_BOOKS})\.?\s+\d")   # "-Ephesians 2:10" on its own line


def scripture_refs(text):
    """Distinct 'Book c:v' citations in a body."""
    return {re.sub(r"\s+", "", m.group(0)).lower() for m in SCRIPTURE_ANYWHERE.finditer(text or "")}


def is_substantive(text, allow_slides=True):
    """True when a body is an actual OUTLINE: a guest slide deck, two or more distinct verse
    citations, one citation in a body of real length, or two or more numbered main points.

    One citation used to be enough. That let a thread reply that mentions a verse ("the
    Ephesians 2:14 slide is ready") replace the outline -- the 9/12 failure -- and reading
    any busy mailbox (dakota@ was planned 2026-10-17) puts every reply-all in front of the job."""
    text = text or ""
    if allow_slides and looks_like_slides(text):
        return True
    refs = scripture_refs(text)
    if len(refs) >= 2:
        return True
    lines = [l for l in text.splitlines() if l.strip()]
    if refs and len(lines) >= 6 and len(text) >= 300:
        return True
    _, rest = split_title_and_body(text)
    return sum(1 for kind, _ in parse_structure(rest) if kind == "main") >= 2


def looks_like_sermon(subject, text):
    """Guard applied to every candidate email, after its quoted history is stripped.

    2026-09-12: an explicit subject used to pass ON ITS OWN. Josh replied inside the
    outline's thread ("Re: Sermon Notes for 9/13/26" -- "Yes EJ has them all...") and that
    84-char reply, being newer and subject-matched, replaced the real outline in the shared
    note. A subject is no longer evidence of content: every candidate must be substantive.
    A reply's numbered to-do list is not a guest slide deck, so replies don't get that path."""
    return is_substantive(text, allow_slides=not REPLY_SUBJECT.match(subject or ""))


def _clean_pw(pw):
    """Google shows app passwords in 4-char groups; copying from the browser often
    yields NON-BREAKING spaces (U+00A0), which imaplib cannot ascii-encode. Keep
    only alphanumerics -- app passwords are 16 lowercase letters."""
    return re.sub(r"[^A-Za-z0-9]", "", pw)


GMAIL_FORWARD = re.compile(r"^-{5,}\s*Forwarded message\s*-{5,}[ \t]*$", re.M | re.I)
APPLE_FORWARD = re.compile(r"^(?:>[ \t]?)?Begin forwarded message:[ \t]*$", re.M)
FORWARD_HEADER_LINE = re.compile(r"^\s*(?:From|Subject|Date|Sent|To|Cc|Bcc|Reply-To|Resent-\w+):\s", re.I)
FORWARD_SUBJECT = re.compile(r"^\s*(?:fwd?|fw)\s*:", re.I)
REPLY_SUBJECT = re.compile(r"^\s*re\s*:", re.I)


def _drop_header_block(lines):
    """Skip the From/Subject/Date/To block that opens a forwarded message: everything up to the
    first blank line, so a wrapped 'To:' or 'Cc:' continuation can't become the title."""
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and FORWARD_HEADER_LINE.match(lines[i]):
        while i < len(lines) and lines[i].strip():
            i += 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    return lines[i:]


def _unwrap_once(text):
    m = GMAIL_FORWARD.search(text)
    if m:
        return "\n".join(_drop_header_block(text[m.end():].splitlines())), True
    m = APPLE_FORWARD.search(text)
    if not m:
        return text, False
    lines = [re.sub(r"^>[ \t]?", "", l) for l in text[m.end():].splitlines()]
    return "\n".join(_drop_header_block(lines)), True


def strip_forward_header(text):
    """Return a forwarded email's forwarded content, or the text unchanged.

    * Gmail forwards are unquoted and open with a '---------- Forwarded message ---------'
      line, then a From/Date/Subject/To block.
    * Apple Mail forwards (2026-10-11 and 10-17: how Dakota forwards Josh's notes to av@)
      quote EVERYTHING one level with '>' under '> Begin forwarded message:'. strip_reply()
      drops '>' lines, so the outline vanished and the forward was skipped. Unquote one level.
    Either way, keep only what follows the header block, or that block (or the forwarder's
    own 'FYI' and signature above it) would become the note's title. Repeated for a forward
    of a forward (a guest's notes, forwarded by Josh, forwarded by Dakota)."""
    # Mail arrives with CRLF line endings; '$' under re.M stops before '\n', not '\r'.
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    for _ in range(3):
        text, unwrapped = _unwrap_once(text)
        if not unwrapped:
            break
    return text


_FWD_DATE_FORMATS = ("%a, %b %d, %Y %I:%M %p", "%a, %b %d, %Y %I:%M:%S %p", "%B %d, %Y %I:%M:%S %p",
                     "%B %d, %Y %I:%M %p", "%a, %d %b %Y %H:%M:%S", "%a, %d %b %Y %H:%M")


def forward_sent_date(text):
    """When the FORWARDED message was sent, from its Date:/Sent: header line, or None.
    A forward's own date is when Dakota forwarded it, which can be days later -- even after
    that Sunday's service -- and would file an old outline under the next Sunday."""
    text = (text or "").replace("\r\n", "\n")
    m = GMAIL_FORWARD.search(text) or APPLE_FORWARD.search(text)
    if not m:
        return None
    for line in text[m.end():].splitlines()[:12]:
        line = re.sub(r"^>[ \t]?", "", line).strip()
        d = re.match(r"(?:Date|Sent):\s*(.+)$", line, re.I)
        if not d:
            continue
        raw = d.group(1).strip()
        try:
            dt = email.utils.parsedate_to_datetime(raw)
            if dt:
                return dt if dt.tzinfo else dt.replace(tzinfo=CHURCH_TZ)
        except (TypeError, ValueError):
            pass
        clean = re.sub(r"\s+(?!AM$|PM$)[A-Z]{2,4}$", "", raw.replace(" at ", " ").replace("\u202f", " "))   # drop "PDT", keep "PM"
        for fmt in _FWD_DATE_FORMATS:
            try:
                return datetime.strptime(clean, fmt).replace(tzinfo=CHURCH_TZ)
            except ValueError:
                continue
    return None


def forward_sender(text):
    """Who wrote the FORWARDED message: the From: value ('Name <addr>') of the innermost
    forwarded block, or None. Walks the same blocks strip_forward_header() unwraps, so the
    author matches the content that gets published (Cristian's notes, forwarded by Josh,
    forwarded by Dakota -> Cristian). A block with no From: line gives None: the forwarder
    is never the author."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    sender = None
    for _ in range(3):
        m, quoted = GMAIL_FORWARD.search(text), False
        if not m:
            m, quoted = APPLE_FORWARD.search(text), True
        if not m:
            break
        lines = text[m.end():].splitlines()
        if quoted:
            lines = [re.sub(r"^>[ \t]?", "", l) for l in lines]
        i, sender = 0, None
        while i < len(lines) and not lines[i].strip():
            i += 1
        while i < len(lines) and lines[i].strip():            # the header block only
            f = re.match(r"\s*From:\s*(.+)$", lines[i].replace("*", ""), re.I)   # Gmail may bold "*From:*"
            if f:
                sender = f.group(1).strip()
                break
            i += 1
        text, _ = _unwrap_once(text)
    return sender


def original_sender(envelope_from, subject, body):
    """The outline's author as a From value, or None. For a forward (Dakota forwards Josh's
    mail to av@) that is the forwarded message's From: line, NOT the envelope -- otherwise
    every forwarded week would be credited to Dakota."""
    body = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    if GMAIL_FORWARD.search(body) or APPLE_FORWARD.search(body):
        return forward_sender(body)
    if FORWARD_SUBJECT.match(subject or ""):
        return None                       # "Fwd:" with no readable block: author unknown
    return envelope_from or None


SPEAKERS = {"josh@arroyochurch.com": "Pastor Josh Smith"}          # address -> byline name
# Josh by NAME too, from any address (a second church address, his own Gmail forwarded by Dakota):
# without this the Note's byline would read "Josh Smith" where it has always read "Pastor Josh Smith".
JOSH_NAMES = re.compile(r"^(?:pastor\s+)?josh(?:ua)?\s+smith$", re.I)
_NAME_PARTICLES = {"de", "del", "della", "da", "di", "la", "le", "van", "von", "der", "den", "du", "dos", "das"}
_NOT_A_PERSON = re.compile(r"\b(?:arroyo|church|av|office|team|staff|admin|info|media|ministry|ministries|"
                           r"worship|pastors|support|noreply|no-reply|communications?)\b", re.I)


def _name_word(w):
    """One capitalised name word: "Cristian", "O'Neil", "J.", and any script -- "Jos\u00e9", "Zo\u00eb"
    (an ASCII-only test dropped every guest with an accent in their name)."""
    return w[:1].isalpha() and not w[:1].islower() and all(ch.isalpha() or ch in "'\u2019-." for ch in w)


def speaker_for(sender):
    """Byline name for a From value, or None.

    Josh (his address, or the display name "Josh Smith") -> "Pastor Josh Smith". Anyone else ->
    their display name when it reads like a person's name (2-4 capitalised words, e.g. "Cristian
    Ayquipa"); a bare address, a first name alone or a mailbox name ("Arroyo AV") gives None --
    the web page then shows no speaker rather than a wrong one, and the Note falls back to
    Pastor Josh Smith."""
    if not sender:
        return None
    name, addr = email.utils.parseaddr(sender)
    if addr.lower() in SPEAKERS:
        return SPEAKERS[addr.lower()]
    words = " ".join(name.replace("*", "").split()).strip("\"' ").split()
    if JOSH_NAMES.match(" ".join(words)):
        return "Pastor Josh Smith"
    if not 2 <= len(words) <= 4 or _NOT_A_PERSON.search(" ".join(words)):
        return None
    if not (_name_word(words[0]) and _name_word(words[-1])):
        return None
    if any(not _name_word(w) and w.lower() not in _NAME_PARTICLES for w in words[1:-1]):
        return None
    return " ".join(words)


def strip_reply(text):
    """Drop quoted history so only what the sender newly wrote remains. Josh sends
    corrections as replies ("Disregard the first email..."), so the quoted original must
    go or it would be duplicated into the note."""
    text = strip_forward_header(text or "")
    # Gmail sometimes wraps the attribution: "On Sat, Oct 17 ... Josh Smith <" / "josh@... wrote:"
    text = re.split(r"^On .+(?:\n.+)?wrote:\s*$", text, maxsplit=1, flags=re.M)[0]
    # Outlook-style replies don't quote with '>': cut at their separator or From:/Sent: block
    text = re.split(r"^(?:_{10,}|-{3,}\s*Original Message\s*-{3,})\s*$|^From: .+\n(?:Sent|Date): ",
                    text, maxsplit=1, flags=re.M | re.I)[0]
    text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith(">"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def message_text(msg):
    """Plain-text body of an email (falling back to its HTML), quoted history removed."""
    return strip_reply(message_body(msg))


def message_body(msg):
    """Plain-text body of an email (falling back to its HTML), untouched."""
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
    return text


def _opens_with_correction(text):
    first = next((l.strip() for l in (text or "").splitlines() if l.strip()), "")
    return bool(PREAMBLE.match(first) or PREAMBLE_HINT.search(first))


def _replaces(reply_text, base_text):
    """A reply replaces the week's outline only if it IS a corrected outline: it opens like
    Josh's corrections ("Disregard the first email...") or carries at least as much scripture
    as the outline and half its length. A chatty reply-all that names two verses doesn't."""
    if _opens_with_correction(reply_text):
        return True
    return (len(scripture_refs(reply_text)) >= max(2, len(scripture_refs(base_text)))
            and len(reply_text) >= 0.5 * len(base_text))


def choose_candidate(candidates):
    """Pick the email to publish from (datetime, subject, text, sender) tuples, or None.
    Returns (subject, datetime, text, sender). The sender (the outline's author, see
    original_sender) rides along at the END so older 3-tuples still work; it is then None.

    Only emails that carry an outline qualify. Then:
    1. The WEEK: the upcoming Sunday first, then the nearest earlier week, future weeks last
       (an outline sent early for Christmas Eve or for next week must not displace this one).
    2. Within the week: the newest ORIGINAL (not "Re:", not "Fwd:"); a newer "Re:" replaces it
       only when it is a real corrected outline (see _replaces) -- every reply-all in Josh's
       thread can reach the job (it did when Josh cc'd av@), and a reply once replaced the outline
       (9/12). With no original, a reply that opens like a correction, else a forward (Dakota's
       deliberate copy), else the newest reply."""
    qualified = []
    for c in sorted(candidates, key=lambda c: c[0], reverse=True):
        when, subject, text = c[:3]
        if text and looks_like_sermon(subject, text):
            qualified.append((when, subject, text, c[3] if len(c) > 3 else None))
        else:
            log(f'skipping "{subject}" ({when:%a %b %d %H:%M}) -- {len(text or "")} chars with no '
                f"sermon outline once quoted text is stripped")
    if not qualified:
        return None

    up = upcoming_sunday()

    def week(c):
        return sunday_from_subject(c[1], c[0]).date()

    def week_rank(w):
        return (0, 0) if w == up else (1, (up - w).days) if w < up else (2, (w - up).days)

    best = min({week(c) for c in qualified}, key=week_rank)
    wk = [c for c in qualified if week(c) == best]                    # newest first
    originals = [c for c in wk if not REPLY_SUBJECT.match(c[1] or "") and not FORWARD_SUBJECT.match(c[1] or "")]
    replies = [c for c in wk if REPLY_SUBJECT.match(c[1] or "")]
    forwards = [c for c in wk if FORWARD_SUBJECT.match(c[1] or "")]
    if originals:
        pick = originals[0]
        newer = [r for r in replies if r[0] > pick[0] and _replaces(r[2], pick[2])]
        if newer:
            pick = newer[0]
    else:
        pick = ([r for r in replies if _opens_with_correction(r[2])] or forwards or replies)[0]
    when, subject, text, sender = pick
    return subject, when, text, sender


def fetch_latest(cfg):
    """Newest email within LOOKBACK_DAYS, across every configured mailbox, that is from an
    allowed sender, has an allowed subject AND actually carries an outline.
    Returns (subject, date, text, sender) or None.

    A mailbox that can't be read (wrong app password, IMAP off) is logged and skipped so the
    others still count -- but if nothing qualifies AND a mailbox failed, this raises, so the
    runner emails an alert instead of quietly leaving last week's note up."""
    since = (datetime.now(timezone.utc) - timedelta(days=int(cfg["LOOKBACK_DAYS"]))).strftime("%d-%b-%Y")
    parsed, failed = [], []
    boxes = accounts(cfg)
    owners = {u.lower() for u, _, _ in boxes}
    for n, (user, pw, mailbox) in enumerate(boxes):
        try:
            got = _fetch_mailbox(cfg, user, pw, mailbox, since, owners, strict_only=n > 0)
            log(f"{user} [{mailbox}]: {len(got)} subject-matched email(s)")
            parsed += got
        except Exception as e:
            failed.append(user)
            log(f"WARNING: could not read {user} [{mailbox}]: {type(e).__name__}: {str(e)[:160]}")
    picked = choose_candidate(parsed)
    if failed and (picked is None or sunday_from_subject(picked[0], picked[1]).date() < upcoming_sunday()):
        # Josh's notes may be sitting in the mailbox that failed; an older outline found
        # elsewhere must not mask that (it would leave last week's note up, silently).
        raise RuntimeError(f"could not read {', '.join(failed)} and found no outline for "
                           f"{upcoming_sunday()} elsewhere -- check that mailbox's app password / IMAP access")
    return picked


def upcoming_sunday(now=None):
    """The next service date: today if it is Sunday, otherwise the coming Sunday (church time)."""
    today = (now or datetime.now(CHURCH_TZ)).date()
    return today + timedelta(days=(6 - today.weekday()) % 7)


def _fetch_mailbox(cfg, user, pw, mailbox, since, owners=(), strict_only=False):
    """(datetime, subject, text, sender) for every allowed-sender, allowed-subject email in one
    mailbox. sender is the outline's author (original_sender), for the byline.

    strict_only (every mailbox after av@): only "sermon notes"/"sermon outline" subjects count.
    dakota@ is a busy inbox where loose words like "sermon" also hit mail such as a "November
    sermon calendar" that lists three passages."""
    # timeout: a half-open connection used to block forever, and launchd will not start the
    # next attempt while this one still runs.
    M = imaplib.IMAP4_SSL("imap.gmail.com", timeout=60)
    try:
        M.login(user, _clean_pw(pw))
        # readonly: never marks the sender's mail as read. Quoted, because "[Gmail]/All Mail"
        # has a space in it.
        typ, _ = M.select(f'"{mailbox}"', readonly=True)
        if typ != "OK":
            raise RuntimeError(f"could not open mailbox {mailbox!r}")
        # Filter in Python rather than with an IMAP query. The allowlists are
        # multi-sender AND multi-subject, and IMAP's prefix-notation OR nests horribly
        # past two terms.
        #
        # MUST still filter on subject: the newest email from a preacher is often
        # unrelated (worship-night graphics, announcement decks). "Latest from Josh"
        # would overwrite the note with that.
        senders = allowed_senders(cfg)
        subjects = list(STRICT_SUBJECTS) if strict_only else allowed_subjects(cfg)
        # dakota@ is a busy inbox, so when every allowed sender shares one domain, let the
        # server narrow to that domain first (a substring match; the exact check is below).
        domains = {s.split("@")[-1] for s in senders}
        query = f'(SINCE {since} FROM "{domains.pop()}")' if len(domains) == 1 else f"(SINCE {since})"
        typ, data = M.search(None, query)
        ids = data[0].split() if typ == "OK" and data and data[0] else []

        candidates = []                               # (datetime, message-id)
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
            # Mail FROM any mailbox the job reads never counts, unless it is a forward (Dakota's
            # deliberate "publish this" copy to av@): dakota@'s All Mail holds Dakota's sent
            # replies and drafts, he also writes from av@, and av@ mails its failure alerts to itself.
            if addr in owners and not FORWARD_SUBJECT.match(sub):
                continue
            if not any(k in sub.lower() for k in subjects):
                continue
            try:
                when_h = email.utils.parsedate_to_datetime(h.get("Date"))
                if when_h.tzinfo is None:
                    when_h = when_h.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            candidates.append((when_h, mid))

        # Read EVERY subject-matched email, not just the newest: the newest is often a reply
        # in the outline's own thread, and only the bodies can tell an outline from chatter.
        # A week holds a handful of these at most.
        parsed = []
        for when_h, mid in candidates:
            typ, raw = M.fetch(mid, "(BODY.PEEK[])")
            if typ != "OK" or not raw or not raw[0]:
                continue
            msg = email.message_from_bytes(raw[0][1])
            subject = str(make_header(decode_header(msg.get("Subject", "") or "")))
            body = message_body(msg)
            # A forward is dated by the message it carries (Dakota may forward days later).
            when_c = (forward_sent_date(body) or when_h) if FORWARD_SUBJECT.match(subject) else when_h
            # ...and credited to the message it carries (the byline names the preacher).
            sender = original_sender(str(make_header(decode_header(msg.get("From", "") or ""))), subject, body)
            parsed.append((when_c, subject, strip_reply(body), sender))
    finally:
        for step in (M.close, M.logout):     # either can raise after a failed login
            try:
                step()
            except Exception:
                pass

    return parsed


def run_osascript(script, timeout=90):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"osascript exited {r.returncode}")
    return r.stdout.strip()


class SessionNotReady(RuntimeError):
    """The Mac is awake enough to run launchd but not to script Notes."""


def gui_session_ready():
    """Why this exists: every failed Sunday run (8/23, 8/30, 9/6) has the same shape --
    the IMAP fetch succeeds and then every AppleEvent to Notes times out. That is Power
    Nap. launchd fires the job during a DARK WAKE, where the network is up but there is
    no usable GUI session, so Notes can neither be scripted nor brought to the front and
    osascript simply blocks until our timeout. Three symptoms, one cause.

    Probing costs ~0.2s on a healthy session and turns a 2-6 minute hang into an
    immediate, unambiguous 'not now'. Returns None when ready, else the reason."""
    try:
        ioreg = subprocess.run(["ioreg", "-n", "Root", "-d1", "-r"],
                               capture_output=True, text=True, timeout=15).stdout
        if "CGSSessionScreenIsLocked" in ioreg:
            return "the screen is locked -- UI scripting cannot drive Notes"
    except Exception as e:
        log(f"WARNING: could not read lock state ({e}); continuing to the Notes probe")

    try:
        console = subprocess.run(["stat", "-f", "%Su", "/dev/console"],
                                 capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception:
        console = ""
    if console in ("", "root"):
        return f"no logged-in GUI session (/dev/console owned by {console or 'nobody'})"

    # Cheap AppleEvent. A healthy session answers in well under a second; a dark wake
    # never answers at all, which is exactly what the 120s and 240s hangs were.
    try:
        subprocess.run(["osascript", "-e", 'tell application "Notes" to count notes'],
                       capture_output=True, text=True, timeout=20, check=True)
    except subprocess.TimeoutExpired:
        return "Notes did not answer a trivial AppleEvent within 20s (dark wake / Power Nap)"
    except subprocess.CalledProcessError as e:
        return f"Notes refused a trivial AppleEvent: {(e.stderr or '').strip()[:120]}"
    return None


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
    # No date in the subject (Josh's 10/9 email was just "Sermon Notes"): the service is the
    # Sunday on or after the day it was sent, in local time. Returning the send date itself
    # put "October 9th" in the byline of a Friday email.
    # A Sunday send after service (it ends ~11:30) is next week's outline.
    sent = fallback.astimezone(CHURCH_TZ) if fallback.tzinfo else fallback
    sunday = sent.date() + timedelta(days=(6 - sent.weekday()) % 7)
    if sent.weekday() == 6 and sent.hour >= 12:
        sunday += timedelta(days=7)
    return datetime(sunday.year, sunday.month, sunday.day)


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


LONE_MARKER = re.compile(r"(?m)^\s*\d+\.\s*$")
SUB_MARK = re.compile(r"^\s*(?:[-\u2022\u2013]|#\s*\d+[.):]?)\s*(\S.*)$")   # "-What is sin? ..." / "#1 Same citizenship: ..."
AUTHOR_NUM = re.compile(r"^\s*(?:#\s*\d+[.):]?|\d+[.)])\s+")                 # Josh's own "1." / "#1" on a heading
LIST_COUNT = re.compile(r"^\s*([2-9]|two|three|four|five|six|seven|eight|nine)\s+[A-Za-z]+s\b", re.I)   # "2 Reasons", "Three Truths"
WORD_NUM = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
QUOTE_OPEN = "\"'\u201c\u201d\u2018\u2019"


def parse_unnumbered(body):
    """Josh's outline WITHOUT lone 'N.' markers (from 2026-10-11 on): each point is a short
    heading followed by its scripture, a heading like "2 Reasons ..." introduces a list, and list
    items are bare short lines or start with '-' or '#1'. Without this, parse_structure() made
    every line an h2 and emitted no "Write some notes here" prompts (those follow main points).

    Per paragraph: scripture -> text; a short line (or a single '#1 ...' line) followed by
    scripture -> numbered main point, unless a counted list ("2 Reasons") still expects items;
    '-'/'#N' lines -> sub items (split out even when they share a paragraph with their
    heading); short lines inside a list -> sub items; any other short line -> a list heading.
    A counted list ends after its count; an uncounted one at the next main point."""
    paras = []
    for para in re.split(r"\n\s*\n", body or ""):
        lines = [l.strip() for l in para.splitlines() if l.strip()]
        if not lines:
            continue
        marked = [bool(SUB_MARK.match(l)) and not REF_LINE.match(l) for l in lines]   # "-Ephesians 2:10" is a citation
        if all(marked):
            if len(lines) == 1:
                paras.append(("bullet1", lines[0]))
            else:
                paras += [("bullet", SUB_MARK.match(l).group(1)) for l in lines]
        elif len(lines) > 1 and not marked[0] and all(marked[1:]):   # "4 Reasons ...\n#1 ...\n#2 ..."
            paras.append(("para", lines[0]))
            paras += [("bullet", SUB_MARK.match(l).group(1)) for l in lines[1:]]
        else:
            paras.append(("para", " ".join(lines)))

    def is_scripture(t):
        return t[:1] in QUOTE_OPEN or bool(SCRIPTURE_REF.search(t)) or bool(BIBLE_REF_START.match(t))

    out, n = [], 0
    in_list, left = False, None            # left = items a counted list still expects

    def sub(t):
        nonlocal in_list, left
        out.append(("sub", t))
        if left is not None:
            left -= 1
            if left <= 0:
                in_list, left = False, None

    def main(t):
        nonlocal n, in_list, left
        n += 1
        out.append(("main", f"{n}. {AUTHOR_NUM.sub('', t)}"))
        in_list, left = False, None

    for i, (kind, t) in enumerate(paras):
        nxt = paras[i + 1] if i + 1 < len(paras) else None
        verse_next = bool(nxt) and nxt[0] == "para" and is_scripture(nxt[1])
        counted = in_list and left is not None
        if kind == "bullet":
            sub(t)
        elif kind == "bullet1":
            if verse_next and not counted:
                main(t)
            else:
                sub(SUB_MARK.match(t).group(1))
        elif is_scripture(t):
            out.append(("text", t))
        elif len(t) < 90 and counted:
            sub(t)
        elif verse_next and len(t) < 90 and not t.rstrip().endswith("."):
            main(t)
        elif len(t) < 90 and in_list:
            sub(t)
        elif len(t) < 90:
            out.append(("subhead", t))
            m = LIST_COUNT.match(t)
            in_list = True
            left = (int(m.group(1)) if m.group(1).isdigit() else WORD_NUM[m.group(1).lower()]) if m else None
        else:
            out.append(("text", t))
    return out


TAKEAWAY_META = re.compile(
    r"\b(I need|I can(?:no|['’])t|I['’]?m unable|I am unable|unable to|could you|"
    r"please (?:share|provide)|provide (?:the|more)|sermon (?:text|content)|as an AI|"
    r"here(?: is|['’]s) (?:a|the|one))\b", re.I)


def takeaway_problem(s):
    """Why the model's KEY TAKEAWAY must not be published, or None when it is fine.

    2026-09-12: handed an 84-char reply instead of an outline, the model asked for the
    sermon content -- and that request was printed in the shared note as the KEY TAKEAWAY.
    Anything that is not one house-style sentence is dropped; the note is written without it."""
    if not s:
        return "empty"
    if "?" in s:
        return "contains a question"
    if TAKEAWAY_META.search(s):
        return "reads as a reply to us, not a summary"
    if "—" not in s and " – " not in s:
        return "missing the em-dash the house style requires"
    if len(s.split()) > 60:
        return f"{len(s.split())} words (limit 60)"
    return None


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
        # Bounded (2026-10-23): this now runs before the GUI probe, so a dark wake waits on it.
        # The SDK default is a 600s read timeout with 2 retries -- ~30 min that could swallow the
        # next scheduled attempt (launchd never overlaps runs). One sentence takes seconds.
        msg = anthropic.Anthropic(api_key=key, timeout=60, max_retries=1).messages.create(
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
        out = " ".join(msg.content[0].text.split()).strip('"')
        problem = takeaway_problem(out)
        if problem:
            log(f"WARNING: KEY TAKEAWAY rejected ({problem}) -- continuing without it: {out[:120]!r}")
            return ""
        return out
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
        # `show note` does not move keyboard focus. On 2026-10-11 it stayed in the note LIST,
        # so the select/copy/paste keystrokes below walked the list instead of editing the
        # note -- and the run still logged success. Put focus in the body explicitly (the
        # body is the only text area in the window: splitter group > scroll area > text area).
        'tell application "System Events" to tell process "Notes"\n'
        '  repeat with sa in (scroll areas of splitter group 1 of window 1)\n'
        '    if (count of text areas of sa) > 0 then\n'
        '      set value of attribute "AXFocused" of (text area 1 of sa) to true\n'
        '      exit repeat\n'
        '    end if\n'
        '  end repeat\n'
        'end tell\n'
        'delay 0.5\n'
    )


def _keys(lines):
    # Keystrokes go to whatever has keyboard focus, so refuse to send any unless Notes is in
    # front AND the focus is the note body. Fail closed: nothing typed, nothing pasted.
    body = "\n".join("    " + l for l in lines)
    _ui('tell application "System Events"\n'
        '  tell process "Notes" to set frontmost to true\n'
        '  delay 0.4\n'
        '  if (name of (first process whose frontmost is true)) is not "Notes" then '
        'error "Notes is not frontmost -- refusing to send keystrokes"\n'
        '  tell process "Notes"\n'
        '    if role of (value of attribute "AXFocusedUIElement") is not "AXTextArea" then '
        'error "keyboard focus is not in the note body -- refusing to send keystrokes"\n'
        + body + '\n  end tell\nend tell\n')


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


def strip_markdown_emphasis(text):
    """Drop the asterisks Josh uses for bold, so they don't reach the shared note.

    2026-09-20: he wrote the outline as "*Walk in His Will *" / "*#1 Walk in unity *",
    and the note published the asterisks literally -- in its title, every point heading,
    and mid-sentence in '*"Abba,* Father."'. Apple Notes has no markdown, so an asterisk
    from the email is never anything but a stray character. The purple instruction line
    keeps its leading "*" because the script writes that line itself; it never comes
    through here."""
    text = (text or "").replace("*", "")
    return "\n".join(re.sub(r"[ \t]{2,}", " ", l).rstrip() for l in text.splitlines())


# ── one parse, two outputs ───────────────────────────────────────────────────────────────
# The same outline feeds the shared Note (update_note) and the web copy (publish_web), so it is
# parsed ONCE into a plain dict. Block kinds: "main" (a numbered point), "subhead", "sub"
# (consecutive subs are one ordered list), "quote" (scripture: the paragraph opens with a double
# quote) and "para". The parsers emit "text" for the last two; update_note() always told them
# apart by that opening quote, and build_outline() now records the same decision in the kind.

def outline_version(title, blocks):
    """Fingerprint of the parsed outline (12 hex): changes whenever what readers see changes."""
    raw = json.dumps([title, [list(b) for b in blocks]], ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def cached_takeaway(version, title, body):
    """key_takeaway(), at most once per distinct outline.

    The web copy can go out on Saturday and the Note on Sunday (a dark wake, a locked screen),
    and the model words the sentence differently on every call -- the two would disagree. So
    the sentence is kept by outline version (last ~10). An empty result (API down, sentence
    rejected) is NOT cached, so a later run can still get one."""
    try:
        cache = json.loads(OUTLINE_CACHE.read_text(encoding="utf-8"))
        cache = cache if isinstance(cache, dict) else {}
    except (OSError, ValueError):
        cache = {}
    if cache.get(version):
        log("KEY TAKEAWAY reused from the outline cache")
        return cache[version]
    out = key_takeaway(title, body)
    if out:
        cache.pop(version, None)
        cache[version] = out                               # newest last; keep the last 10
        try:
            OUTLINE_CACHE.parent.mkdir(parents=True, exist_ok=True)
            tmp = OUTLINE_CACHE.with_suffix(".tmp")
            tmp.write_text(json.dumps(dict(list(cache.items())[-10:]), ensure_ascii=False, indent=1),
                           encoding="utf-8")
            tmp.replace(OUTLINE_CACHE)
        except OSError as e:
            log(f"WARNING: could not save the outline cache ({e})")
    return out


def build_outline(subject, when, text, sender=None):
    """Parse an outline email ONCE into what both the Note and the web copy render:
    {"title", "service" (a date), "blocks" [(kind, text)], "takeaway" ("" when none),
     "speaker" (or None), "format" ("outline" | "slides"), "version"}."""
    text = strip_markdown_emphasis(text)

    slides = looks_like_slides(text)
    if slides:
        log("body looks like a guest slide deck -- using the slide parser")
        title, blocks = parse_slides(text)
    else:
        title, rest = split_title_and_body(text)
        if LONE_MARKER.search(rest):
            blocks = parse_structure(rest)
        else:
            log("no 'N.' markers -- using the unnumbered-outline parser")
            blocks = parse_unnumbered(rest)
    service = sunday_from_subject(subject, when).date()
    straighten = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
    blocks = [(k, v.translate(straighten)) for k, v in blocks]
    blocks = [(("quote" if v.lstrip().startswith('"') else "para") if k == "text" else k, v) for k, v in blocks]
    version = outline_version(title, blocks)
    takeaway = cached_takeaway(version, title, "\n".join(v for _, v in blocks))
    speaker = speaker_for(sender)
    log(f'title="{title}"  service={service:%Y-%m-%d}  speaker={speaker or "unknown"}  '
        f'takeaway={"yes" if takeaway else "no"}')
    return {"title": title, "service": service, "blocks": blocks, "takeaway": takeaway,
            "speaker": speaker, "format": "slides" if slides else "outline", "version": version}


def update_note(note_id, outline):
    """Refresh the shared note's text from build_outline()'s dict, leaving the series graphic
    untouched.

    If the note has an image, only the text regions around it are replaced (via UI
    selection + HTML paste) -- the graphic is never selected, so it is never moved,
    re-created or lost. Dakota swaps the series banner by hand every few weeks and the
    automation must not interfere with it.

    With no image present, fall back to a plain AppleScript body write.
    """
    esc = lambda x: html.escape(x, quote=False)
    title, blocks, takeaway = outline["title"], outline["blocks"], outline["takeaway"]
    service = outline["service"]

    # The preacher when the email says who it is (a guest); otherwise Josh, as it always read.
    byline = (f"{outline.get('speaker') or 'Pastor Josh Smith'} | "
              f"{service:%B} {ordinal(service.day)}, {service:%Y}")
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
        elif kind == "quote":
            # Scripture: indent it so quotes read as distinct from Josh's teaching. Notes
            # only honours indentation it can model as a list (<blockquote> is silently
            # flattened to a plain div), so use a bulleted list. Consecutive verses are
            # grouped into ONE block so they read together, with a single blank line after.
            # ("quote" = a paragraph opening with a double quote; build_outline decides.)
            quotes = []
            while i < len(blocks) and blocks[i][0] == "quote":
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


def verify_title(note_id, title, tries=5):
    """Raise unless the note's name (Notes derives it from the first body line) is now `title`."""
    def norm(x): return re.sub(r"\s+", " ", (x or "")).strip().lower()
    name = ""
    for _ in range(tries):
        try:
            name = run_osascript(f'tell application "Notes" to return name of note id "{note_id}"', timeout=60)
        except Exception as e:
            name = f"<unreadable: {e}>"
        if norm(name) == norm(title):
            log(f'verified: the note now reads "{name}"')
            return
        time.sleep(2)
    raise RuntimeError(f'write not confirmed: the note is titled "{name}", expected "{title}"')


# ── web copy ─────────────────────────────────────────────────────────────────────────────
# The website shows the notes too. Each week is published as JSON to the PUBLIC site repo,
# which GitHub Pages serves (with Access-Control-Allow-Origin: *) at WEB_BASE:
#   index.json        {"updated", "weeks": [{service, title, speaker, release_at, file}]}
#                     newest service first, one entry per service date, every week ever
#                     published (the page's archive lists them all -- never trimmed)
#   <service>.json    {service, title, speaker, release_at, published_at, takeaway, format,
#                      version, blocks: [{kind, text}]}
# The field names are a contract with the page -- do not rename them. The page shows a week
# only from its release_at (Sunday 06:45 church time), so publishing on Saturday is fine.

WEB_BASE = "https://dakota-ai-os.github.io/arroyo-church/data/sermon-notes/"
PUBLISH_DIR = Path.home() / "Library" / "Application Support" / "arroyo" / "notes-publish"
PUBLISH_REMOTE = "git@github.com:dakota-ai-os/arroyo-church.git"
PUBLISH_SSH = "ssh -i /Users/dakotayates/.ssh/dakota_ai_os -o IdentitiesOnly=yes"   # the working repo's key
NOTES_SUBDIR = "data/sermon-notes"
WORKING_REPO = Path(__file__).resolve().parent.parent


def web_enabled(cfg):
    """WEB_NOTES=0 in gmail.env turns the web copy off. Default on."""
    return str(cfg.get("WEB_NOTES", "1")).strip().lower() not in ("0", "false", "no", "off")


def release_at(service):
    """When a week goes public: 06:45 church time on its service date, with that day's
    offset (PDT in July, PST in November -- zoneinfo picks it)."""
    return datetime(service.year, service.month, service.day, 6, 45, tzinfo=CHURCH_TZ).isoformat()


SIG_DELIM = re.compile(r"^--(?:\s|$)")                                      # "-- " signature delimiter
SIG_END = re.compile(r"^(?:Sent from my\b|Get Outlook for\b)", re.I)        # mail-app footers
PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]\d{4}(?!\d)")
EMAIL_ADDR = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")


def public_blocks(blocks):
    """The blocks that may go into the PUBLIC repo, where git history keeps them for good.

    Everything after the title reaches the outline, sign-off included, and the Note has always
    shown that (it can be edited by hand; public history needs a rewrite). So for the web only:
    stop at a '-- ' signature delimiter or a 'Sent from my iPhone' footer, and drop any block
    carrying a phone number or an email address (a signature the forward/reply stripping
    missed). Each drop is logged by name. The Note keeps rendering the full blocks unchanged."""
    masked = lambda t: EMAIL_ADDR.sub("[email]", PHONE.sub("[phone]", t))[:80]   # not into the log either
    out = []
    for kind, text in blocks:
        t = text.strip()
        if (SIG_DELIM.match(t) and not SCRIPTURE_ANYWHERE.search(t)) or SIG_END.match(t):
            log(f"WARNING: web copy stops at a signature/footer block: {masked(t)!r}")
            break
        if PHONE.search(t) or EMAIL_ADDR.search(t):
            log(f"WARNING: web copy drops a block with a phone number or email address: {masked(t)!r}")
            continue
        out.append((kind, text))
    return out


def week_doc(outline, published_at):
    """One week's <service>.json, in contract order."""
    return {"service": outline["service"].isoformat(), "title": outline["title"],
            "speaker": outline["speaker"], "release_at": release_at(outline["service"]),
            "published_at": published_at, "takeaway": outline["takeaway"] or None,
            "format": outline["format"], "version": outline["version"],
            "blocks": [{"kind": k, "text": t} for k, t in public_blocks(outline["blocks"])]}


def index_entry(doc):
    return {"service": doc["service"], "title": doc.get("title"), "speaker": doc.get("speaker"),
            "release_at": doc.get("release_at"), "file": f"{doc['service']}.json"}


def merge_index(index, entry):
    """The index's weeks with `entry` in: one per service date (a republished week replaces
    its old entry), newest first. Every week is kept: the page's archive lists the whole index
    (2026-10-23; it was capped at 52 before the archive existed). ~150 bytes a week, so even
    20 years of Sundays is a small file. Old <service>.json files are never deleted either --
    _publish_locked's `git clean` only removes UNTRACKED leftovers of a run that died."""
    weeks = [w for w in (index or {}).get("weeks") or []
             if isinstance(w, dict) and w.get("service") and w["service"] != entry["service"]]
    return sorted(weeks + [entry], key=lambda w: w["service"], reverse=True)


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_week_files(outline, out_dir, now=None):
    """Write <service>.json and merge it into index.json, both in out_dir (the index is read
    from out_dir, i.e. the publish clone -- never the network). Returns True if either changed.

    Republishing an identical outline (a --force, a lost marker) keeps the old timestamps, so
    the files come out byte-identical and there is nothing to commit."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now(CHURCH_TZ)).isoformat(timespec="seconds")
    week_path, index_path = out_dir / f"{outline['service'].isoformat()}.json", out_dir / "index.json"

    doc = week_doc(outline, stamp)
    old = _read_json(week_path)
    if isinstance(old, dict) and {k: v for k, v in old.items() if k != "published_at"} == \
            {k: v for k, v in doc.items() if k != "published_at"}:
        doc["published_at"] = old.get("published_at") or stamp

    index = _read_json(index_path)
    if not isinstance(index, dict) or not isinstance(index.get("weeks"), list):
        # Missing or hand-broken: rebuild from the week files rather than drop every older week.
        if index_path.exists():
            log("WARNING: index.json is unreadable -- rebuilding it from the week files")
        index = {"weeks": [index_entry(d) for d in map(_read_json, sorted(out_dir.glob("????-??-??.json")))
                           if isinstance(d, dict) and d.get("service")]}
    weeks = merge_index(index, index_entry(doc))
    new_index = {"updated": index.get("updated") if weeks == index["weeks"] and index.get("updated") else stamp,
                 "weeks": weeks}

    changed = False
    for path, data in ((week_path, doc), (index_path, new_index)):
        out = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if not path.exists() or path.read_text(encoding="utf-8") != out:
            path.write_text(out, encoding="utf-8")
            changed = True
    return changed


def _git(args, cwd=None, timeout=60):
    """git in the PUBLISH clone -- never the working repo. Raises with git's own message.
    GIT_CEILING_DIRECTORIES stops git from walking up to some other repo if the clone is
    missing; stdin is closed and prompts are off, so nothing can wait for a human."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_CEILING_DIRECTORIES=str(PUBLISH_DIR.parent))
    r = subprocess.run(["git", *args], cwd=str(cwd or PUBLISH_DIR), env=env, capture_output=True,
                       text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed ({r.returncode}): {' '.join((r.stderr or r.stdout).split())[:300]}")
    return r.stdout


def _check_publish_path():
    target = PUBLISH_DIR.resolve()
    if target == WORKING_REPO or WORKING_REPO in target.parents:
        raise RuntimeError(f"refusing to publish from {PUBLISH_DIR}: it is inside the working repo")


def _discard_clone():
    """Throw the publish clone away so the next _ensure_clone() starts fresh. It holds nothing
    of value -- every attempt hard-resets it to origin/main -- but the path is still checked.
    Renamed first, then deleted: a run killed mid-delete leaves a stray '.discard' folder
    (swept next time), never a half-deleted clone at PUBLISH_DIR."""
    _check_publish_path()
    if PUBLISH_DIR.resolve().name != "notes-publish":
        raise RuntimeError(f"refusing to delete {PUBLISH_DIR}: not the publish clone")
    trash = PUBLISH_DIR.with_name(PUBLISH_DIR.name + ".discard")
    shutil.rmtree(trash, ignore_errors=True)
    if PUBLISH_DIR.exists():
        PUBLISH_DIR.rename(trash)
    shutil.rmtree(trash, ignore_errors=True)


def _sweep_stale_locks(max_age=600):
    """Delete git *.lock files left in the clone by a git that was killed. subprocess.run's
    timeout SIGKILLs git, so it never removes its own index.lock / ref locks, and every later
    git call would then fail with 'File exists' -- forever, on an unattended job. publish_web
    holds the notes-publish.lock flock, so no other publish is using the clone; the age test
    only spares a lock that an orphaned child of a just-killed git might still be writing."""
    cutoff = time.time() - max_age
    for lock in (PUBLISH_DIR / ".git").rglob("*.lock"):
        try:
            if lock.is_file() and lock.stat().st_mtime < cutoff:
                lock.unlink()
                log(f"WARNING: removed a stale git lock from the publish clone: {lock.relative_to(PUBLISH_DIR)}")
        except OSError:
            pass


def _ensure_clone():
    """The dedicated publish clone, created on first use (shallow; it only ever needs the tip).
    A clone too broken to name its remote is thrown away and cloned again; one that names a
    DIFFERENT remote is refused (something else is using the folder -- a human should look)."""
    _check_publish_path()
    shutil.rmtree(PUBLISH_DIR.with_name(PUBLISH_DIR.name + ".discard"), ignore_errors=True)
    if PUBLISH_DIR.is_dir() and not (PUBLISH_DIR / ".git").exists() and not any(PUBLISH_DIR.iterdir()):
        PUBLISH_DIR.rmdir()                                   # a clone killed before it began
    if (PUBLISH_DIR / ".git").is_dir():
        _sweep_stale_locks()
        try:
            url = _git(["remote", "get-url", "origin"]).strip()
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            log(f"WARNING: the publish clone is broken ({e}) -- discarding it and cloning again")
            _discard_clone()
    if not (PUBLISH_DIR / ".git").is_dir():
        if PUBLISH_DIR.exists():
            raise RuntimeError(f"{PUBLISH_DIR} exists but is not a git clone -- move it aside and re-run")
        PUBLISH_DIR.parent.mkdir(parents=True, exist_ok=True)
        log(f"creating the publish clone at {PUBLISH_DIR}")
        _git(["clone", "--depth", "1", "--branch", "main", "--config", f"core.sshCommand={PUBLISH_SSH}",
              PUBLISH_REMOTE, str(PUBLISH_DIR)], cwd=PUBLISH_DIR.parent, timeout=300)
        url = _git(["remote", "get-url", "origin"]).strip()
    if url != PUBLISH_REMOTE:
        raise RuntimeError(f"the publish clone points at {url!r}, not {PUBLISH_REMOTE}")
    _git(["config", "core.sshCommand", PUBLISH_SSH])


# How long publish_web may keep STARTING attempts. A run that is still busy when the next
# launchd slot comes round makes launchd skip that slot (Sunday's are 75 and 60 min apart, and
# 09:00 is the last-chance alert), so a stuck publish gives up and leaves it to the next attempt.
PUBLISH_BUDGET = 8 * 60


def publish_web(outline, cfg):
    """Publish one week to the website. Returns True when a commit was pushed, False when the
    site already had exactly this (or WEB_NOTES=0). Raises when it could not publish.

    Runs in a DEDICATED clone (PUBLISH_DIR), never the working repo: the working copy holds
    Dakota's uncommitted work, and an unattended job must never commit or reset that. The
    clone is ours alone (a flock on notes-publish.lock keeps a hand-run --web-only out of a
    scheduled run's way), so every attempt starts from a hard reset to origin/main. The daily
    YouTube-sync Action also commits to main; a push it beat is rejected -- refetch, rewrite
    the files on top of its commit, and retry (3 attempts). Any OTHER git failure before the push means the clone itself
    is damaged (a lock or a half-written ref from a killed git): it is thrown away and cloned
    again, once per run, so the web copy never stays broken until someone fixes it by hand."""
    if not web_enabled(cfg):
        log("WEB_NOTES=0 in gmail.env -- web copy not published")
        return False
    _check_publish_path()
    PUBLISH_DIR.parent.mkdir(parents=True, exist_ok=True)
    with open(PUBLISH_DIR.with_name(PUBLISH_DIR.name + ".lock"), "w") as held:
        try:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)   # released when we exit, even if killed
        except OSError:
            raise RuntimeError("another publish is using the clone right now -- the next attempt retries")
        return _publish_locked(outline)


def _publish_locked(outline):
    _ensure_clone()
    svc = outline["service"].isoformat()
    deadline = time.monotonic() + PUBLISH_BUDGET
    attempt, recloned = 0, False
    while True:
        if time.monotonic() > deadline:
            raise RuntimeError(f"still not published after {PUBLISH_BUDGET // 60} min -- giving up; "
                               f"the next attempt retries")
        step = "fetch"
        try:
            _git(["fetch", "--depth", "1", "origin", "+main:refs/remotes/origin/main"], timeout=120)
            step = "prepare"
            _git(["reset", "--hard", "origin/main"])
            # Leftovers of a run that died mid-write. UNTRACKED files only: every committed week survives.
            _git(["clean", "-fdq", "--", NOTES_SUBDIR])
            write_week_files(outline, PUBLISH_DIR / NOTES_SUBDIR)
            _git(["add", "--", NOTES_SUBDIR])
            if not _git(["status", "--porcelain", "--", NOTES_SUBDIR]).strip():
                log(f"web copy for {svc} is already on the site -- nothing to push")
                return False
            _git(["commit", "-q", "-m", f"Sermon notes {svc}: {outline['title']}", "--", NOTES_SUBDIR])
        except (RuntimeError, subprocess.TimeoutExpired, OSError) as e:
            # A fetch that TIMED OUT is the network, not the clone: a fresh clone would only
            # time out too. Anything else gets one fresh clone before the run gives up.
            if recloned or (step == "fetch" and isinstance(e, subprocess.TimeoutExpired)):
                raise
            log(f"WARNING: git failed in the publish clone ({e}) -- discarding it and cloning again")
            _discard_clone()
            _ensure_clone()
            recloned = True
            continue
        attempt += 1
        try:
            _git(["push", "origin", "HEAD:main"], timeout=120)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            log(f"WARNING: push failed, attempt {attempt}/3 ({e})")
            if attempt == 3:
                raise
            time.sleep(5 * attempt)
            continue
        log(f"web copy published: {WEB_BASE}{svc}.json (public {release_at(outline['service'])})")
        return True


def _mark_web_published(service, when, text, outline, final=False):
    """Record the web copy as done -- unless it went out WITHOUT a KEY TAKEAWAY (API down, or
    a sentence takeaway_problem() rejected). Then the marker is held back, so the next attempt
    rebuilds the outline, asks again (empty results are never cached) and republishes once a
    sentence exists; until then the republish is byte-identical and commits nothing. Otherwise
    a later Note write could get a sentence the web copy never would. `final`: the last
    attempt of the week marks it regardless -- nothing retries after it."""
    if not outline["takeaway"] and not final:
        log(f"WARNING: the web copy for {service} has no KEY TAKEAWAY yet -- not marked done, "
            f"so the next attempt retries it")
        return
    WEB_STATE.parent.mkdir(parents=True, exist_ok=True)
    WEB_STATE.write_text(marker_value(service, when, text), encoding="utf-8")


def church_now():
    return datetime.now(CHURCH_TZ)


def main():
    cfg = load_config()
    args = sys.argv[1:]
    force, web_only = "--force" in args, "--web-only" in args
    web_on = web_enabled(cfg)
    now = church_now()
    last_chance = now.weekday() == 6 and now.hour >= 9 and not web_only   # the Sunday 09:00 attempt

    log(f"looking for mail from {'/'.join(allowed_senders(cfg))} "
        f"subject~{'|'.join(allowed_subjects(cfg))} (last {cfg['LOOKBACK_DAYS']} days)")

    # The mail is read BEFORE the GUI probe (2026-10-23). The probe used to come first so a
    # dark wake cost ~0.2s, but the web copy needs no GUI, and a dark wake has the network
    # (the IMAP fetch succeeded in every 8/23-9/6 failure) -- so it can still publish the web
    # copy. A mail failure during a dark wake keeps the quiet 75 it always had (the probe
    # used to exit before the fetch), except on the last attempt, which nothing retries.
    try:
        found = fetch_latest(cfg)
    except Exception:
        not_ready = None if (web_only or last_chance) else gui_session_ready()
        if not_ready:
            log(f"GUI session not usable: {not_ready}")
            log("the mail could not be read either -- skipping this attempt; a later attempt will retry.")
            return EX_TEMPFAIL
        raise
    up = upcoming_sunday()
    already = STATE.read_text(encoding="utf-8").strip() if STATE.exists() else ""
    found_svc = sunday_from_subject(found[0], found[1]).date() if found else None
    if last_chance and already.partition("|")[0] != up.isoformat() and found_svc != up:
        # Exit non-zero so the runner emails an alert instead of leaving last week's note up.
        raise RuntimeError(f"no sermon outline for today ({up}) reached the job -- the shared note "
                           f"still shows {already.partition('|')[0] or 'an older week'}")
    if not found:
        log("no matching sermon-notes email found -- leaving the note untouched.")
        return 0
    if found_svc < up and not web_only:
        # The note is for the coming service; republishing an older week never helps.
        log(f'newest outline is for {found_svc} ("{found[0]}"), not {up} -- leaving the note untouched.')
        return 0

    subject, when, text, sender = found
    if not looks_like_sermon(subject, text):
        log(f'found "{subject}" but it cites no scripture and the subject is not an '
            f"explicit sermon-notes one -- treating it as unrelated, note left untouched.")
        return 0
    log(f'found "{subject}" ({when:%a %b %d %H:%M}) -- {len(text)} chars')
    service = found_svc.isoformat()

    if web_only:
        # Seeding the page, or re-publishing after a hand fix: the web copy only, for the newest
        # outline even if its Sunday has passed. No GUI probe, no Note, no Note marker.
        if not web_on:
            log("WEB_NOTES=0 in gmail.env -- web publishing is off; nothing published.")
            return 1
        outline = build_outline(subject, when, text, sender)
        publish_web(outline, cfg)
        _mark_web_published(service, when, text, outline)
        return 0

    # Several attempts are scheduled per week so a single bad wake cannot lose the Sunday.
    # Rewriting an already-current note is wasted work AND another pass over the series
    # graphic, so once a service date is written the remaining attempts stand down. The web
    # copy keeps its own marker: a dark wake can publish it while the Note waits for a GUI.
    note_done = not force and marker_says_current(already, service, when, text)
    web_mark = WEB_STATE.read_text(encoding="utf-8").strip() if WEB_STATE.exists() else ""
    web_done = not web_on or (not force and marker_says_current(web_mark, service, when, text))
    if note_done and web_done:
        log(f"note{' and web copy' if web_on else ''} already written for {service} -- nothing to do "
            f"(pass --force to rewrite).")
        return 0

    outline = build_outline(subject, when, text, sender)

    web_failed = None
    if not web_on:
        log("WEB_NOTES=0 in gmail.env -- web copy skipped")
    elif web_done:
        log(f"web copy already published for {service}")
    else:
        try:
            publish_web(outline, cfg)
            _mark_web_published(service, when, text, outline, final=last_chance)
        except Exception as e:
            # Never blocks the Note: log it, carry on, and fail the run at the end.
            web_failed = f"{type(e).__name__}: {e}"
            log(f"ERROR: the web copy was NOT published for {service} -- {web_failed}")

    if note_done:
        log(f"note already written for {service} -- nothing to do for the note (pass --force to rewrite it).")
        return 1 if web_failed else 0

    not_ready = gui_session_ready()
    if not_ready:
        log(f"GUI session not usable: {not_ready}")
        log("skipping the note without touching it; a later attempt will retry.")
        # Exit code when the web copy ALSO failed (decided 2026-10-23): 75 means "nothing went
        # wrong that a later attempt won't redo", and the next attempt does retry the web copy
        # (its marker was not written) -- so it stays a quiet 75, logged loudly above, and a
        # failure that persists alerts on the first attempt that has a GUI. The Sunday 09:00
        # attempt is the last one: nothing retries after it, so there it exits 1 and alerts.
        if web_failed and last_chance:
            log("this was the last attempt of the week and the web copy failed -- exiting 1 to alert")
            return 1
        if web_failed:
            log("the web copy failed too -- the next attempt retries both (quiet retry)")
        return EX_TEMPFAIL

    if already.partition("|")[0] == service and not force:
        log(f"a newer outline for {service} arrived ({when:%a %b %d %H:%M}) -- republishing it")

    title = update_note(cfg["NOTE_ID"], outline)
    # update_note() can return normally without having changed anything (2026-10-11: its
    # keystrokes went to the note list). Read the note back before recording the week as
    # done, so a silent miss exits non-zero (alert) and the next attempt retries.
    verify_title(cfg["NOTE_ID"], title)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(marker_value(service, when, text), encoding="utf-8")
    log(f'updated the shared Apple Note -> retitled "{title}" (service {service})')
    if web_failed:
        log("the note is written, but the web copy FAILED (see the ERROR above) -- exiting 1 to alert")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

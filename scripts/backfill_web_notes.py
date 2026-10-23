#!/usr/bin/env python3
"""
Backfill the website's sermon-notes archive from saved Apple Note bodies.

The web copy (sermon_notes_sync.publish_web) started 2026-10-23, so the earlier weeks of the
series exist only in the shared Note's backups: every Note write first saves the body it is about
to replace to ~/.config/arroyo/note-backups/<run time>.html -- i.e. the PREVIOUS week's notes.
This turns those bodies back into the dict build_outline() returns and publishes it through the
job's own code path (write_week_files / publish_web), so the JSON matches the page's contract and
the signature/contact filter applies.

    python3 scripts/backfill_web_notes.py --dry-run DIR   # week files + index into DIR, no git
    python3 scripts/backfill_web_notes.py                 # publish each week (one commit each)
    --force    also overwrite a week the live index already lists (default: skip it)

A dry run reads DIR/index.json as "the live index", so seed DIR with a copy of the live files
first. Never touches the job's weekly markers (last-written.txt, web-published.txt) or its
takeaway cache, and never calls the model: each week's KEY TAKEAWAY is the one the Note showed.
"""

import argparse
import html
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sermon_notes_sync as s

# (backup file, expected title, service date). The backup is named for the run that REPLACED
# the week, so it lands 6-7 days after the service. 2026-10-04 had no notes (outdoor service);
# 2026-10-18 is the first week the job published itself and is never backfilled.
WEEKS = (
    ("2026-09-19-200020.html", "Grace That Keeps Giving", date(2026, 9, 13)),
    ("2026-09-27-064517.html", "Walk in His Will", date(2026, 9, 20)),
    ("2026-10-11-064112.html", "Grow in What You Know", date(2026, 9, 27)),
    ("2026-10-17-200016.html", "What Does it Mean to be Saved?", date(2026, 10, 11)),
)


# ── Note HTML -> outline: update_note() run backwards ────────────────────────────────────
# A Note body is a flat run of <div>s and <ol>s. update_note() writes <h1> title, a bold byline
# "Pastor Josh Smith | September 13th, 2026", the purple "*To save and edit this note..." notice,
# "KEY TAKEAWAY: ...", then the blocks. Notes re-serialises what was pasted, and some weeks were
# edited by hand, so the real files vary: the 9/13 Note has <span style="font-size: 24px/18px">
# instead of <h1>/<h2>, the 9/20 one has <h3> subheads and no "Write some notes here" prompts,
# 10/11's byline is an <h1>, and quotes are stored as '&quot' with no semicolon.

BLOCK = re.compile(r"<(div|ol|ul|p|h[1-6])\b[^>]*>(.*?)</\1\s*>", re.S | re.I)
LI = re.compile(r"<li\b[^>]*>(.*?)</li\s*>", re.S | re.I)
FONT_PX = re.compile(r"font-size:\s*(\d+)px", re.I)
BYLINE = re.compile(r"^(?P<who>\S.*?)\s*\|\s*(?P<month>[A-Z][a-z]+)\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?,?\s+"
                    r"(?P<year>\d{4})$")
PROMPT_TEXT = re.sub(r"<[^>]+>", "", s.NOTE_PROMPT)               # "Write some notes here"
TAKEAWAY_LEAD = "KEY TAKEAWAY:"
LABEL_ONLY = re.compile(r'^[^"]{1,59}:$')                          # "The Holy Spirit was promised:"
STRAIGHTEN = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})   # as build_outline() does


def _text(fragment):
    """A block's visible text: tags and images out, entities decoded ('&quot' too -- Notes drops
    the semicolon), curly quotes straightened, Josh's asterisks dropped, whitespace collapsed."""
    t = re.sub(r"<br\s*/?>", " ", fragment, flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ").translate(STRAIGHTEN)
    return " ".join(s.strip_markdown_emphasis(t).split())


def _level(tag, inner):
    """'list', 'h1', 'h2', 'h3' or 'div'. Notes writes a heading as <h1>-<h3> inside the div, or
    (older Notes, the 9/13 backup) as a bold span: 24px = title, 18px = heading."""
    if tag in ("ol", "ul"):
        return "list"
    m = re.match(r"h([1-6])$", tag) or re.search(r"<h([1-6])\b", inner, re.I)
    if m:
        return f"h{min(int(m.group(1)), 3)}"
    px = max(map(int, FONT_PX.findall(inner)), default=0)
    return "h1" if px >= 22 else "h2" if px >= 17 else "div"


def note_tokens(body_html):
    """[(level, text)] per non-empty block, or ('list', [item, ...]) per list. Image-only and
    <br>-only blocks are empty and drop out. Anything outside a recognised block raises -- a
    shape this has never seen (e.g. nested divs) must be looked at, not silently skipped."""
    toks, pos = [], 0
    for m in BLOCK.finditer(body_html):
        gap = body_html[pos:m.start()]
        if re.sub(r"<br\s*/?>|\s", "", gap, flags=re.I):
            raise ValueError(f"unexpected markup between blocks: {gap.strip()[:80]!r}")
        pos = m.end()
        tag, inner = m.group(1).lower(), m.group(2)
        level = _level(tag, inner)
        text = [t for t in map(_text, LI.findall(inner)) if t] if level == "list" else _text(inner)
        if text:
            toks.append((level, text))
    if re.sub(r"<br\s*/?>|\s", "", body_html[pos:], flags=re.I):
        raise ValueError(f"unexpected markup after the last block: {body_html[pos:].strip()[:80]!r}")
    return toks


VERSE_SEP = " · "                                                  # between two verses folded into one point


def _fold_labels(items):
    """One list's items as 'sub' texts. A bare label item followed by scripture items is ONE
    point: the 9/20 Note split "The Holy Spirit was promised:" and its verse into separate <li>s,
    which would number 3 truths as 7 items. Folded, it reads like update_note()'s own
    <li><b>Label:</b> rest</li>, and the page bolds the label the same way. A label with two
    verses (Romans 8:14 and 8:15) keeps a visible VERSE_SEP between them, so one citation never
    runs straight into the next verse's first word."""
    out, folding = [], False
    for t in items:
        if out and (folding or LABEL_ONLY.match(out[-1])) and s.SCRIPTURE_ANYWHERE.search(t):
            out[-1] += (VERSE_SEP if folding else " ") + t
            folding = True
        else:
            out.append(t)
            folding = False
    return out


def note_to_outline(body_html):
    """A saved Note body -> build_outline()'s dict (format "outline").

    Main points vs subheads: update_note() renders BOTH as <h2>, but it writes the "Write some
    notes here" prompt before every main point after the first and after the last one. So an
    <h2> straight after a prompt is a main point, and so is the first <h2> before the first
    prompt (the first one numbered "N." if any -- a slide deck can open with a subhead); every
    other <h2> sits inside a section and is a subhead. A Note with no prompts at all (9/20's,
    edited by hand) falls back to Josh's numbering: an <h2> that opens "N." is a main point.
    <h3> is always a subhead. Main points are renumbered 1..n like the parsers do."""
    toks = [(lv, t) for lv, t in note_tokens(body_html) if lv == "list" or s.INSTRUCT_MARK not in t]
    if len(toks) < 2 or toks[0][0] == "list":
        raise ValueError("no title")
    title, (lv, by), rest = toks[0][1], toks[1], toks[2:]
    m = BYLINE.match(by) if lv != "list" else None
    if not m:
        raise ValueError(f"no 'Speaker | Month Dth, YYYY' byline under the title (got {str(by)[:60]!r})")
    service = datetime.strptime(f"{m['month']} {m['day']} {m['year']}", "%B %d %Y").date()

    is_prompt = lambda tok: tok[0] != "list" and tok[1] == PROMPT_TEXT
    prompts = [i for i, tok in enumerate(rest) if is_prompt(tok)]
    lead = [i for i, (lv, t) in enumerate(rest[:prompts[0]] if prompts else []) if lv in ("h1", "h2")]
    first_main = next((i for i in lead if s.AUTHOR_NUM.match(rest[i][1])), lead[0] if lead else None)

    blocks, takeaway, after_prompt, n = [], "", False, 0
    for i, (lv, t) in enumerate(rest):
        if is_prompt((lv, t)):
            after_prompt = True
            continue
        if lv == "list":
            blocks += [("sub", x) for x in _fold_labels(t)]
        elif t.startswith(TAKEAWAY_LEAD) and not takeaway:
            takeaway = t[len(TAKEAWAY_LEAD):].strip()
        elif lv in ("h1", "h2") and (after_prompt or i == first_main if prompts else s.AUTHOR_NUM.match(t)):
            n += 1
            blocks.append(("main", f"{n}. {s.AUTHOR_NUM.sub('', t)}"))
        elif lv in ("h1", "h2", "h3"):
            blocks.append(("subhead", t))
        else:
            blocks.append(("quote" if t.startswith('"') else "para", t))
        after_prompt = False
    return {"title": title, "service": service, "blocks": blocks, "takeaway": takeaway,
            "speaker": m["who"], "format": "outline", "version": s.outline_version(title, blocks)}


# Obvious typos in the original outlines, fixed for the public web copy only (the Apple Note backups
# are untouched; 2026-10-23). Each must match exactly once, so a changed backup fails loudly.
# Left as written on purpose: a missing quote mark (9/20, 10/11) and 9/27 citing Eph 1:15-17 twice.
TYPO_FIXES = {
    date(2026, 9, 13): [("Graces gives you a new identity", "Grace gives you a new identity")],
    date(2026, 9, 27): [("if your son asks for] a fish", "if your son asks for a fish")],
    date(2026, 10, 11): [('"1As for you', '"As for you'), ("and sins 2in which", "and sins in which"),
                         ("disobedient. 3All of us", "disobedient. All of us"),
                         ("all have sinned ?", "all have sinned?")],
}


def _fix_typos(o):
    blocks = list(o["blocks"])
    for old, new in TYPO_FIXES.get(o["service"], ()):
        hits = [i for i, (_, t) in enumerate(blocks) if old in t]
        if len(hits) != 1 or blocks[hits[0]][1].count(old) != 1:
            raise ValueError(f"{o['service']}: typo fix {old!r} matched {len(hits)} blocks, expected exactly 1")
        k, t = blocks[hits[0]]
        blocks[hits[0]] = (k, t.replace(old, new))
    o["blocks"] = blocks
    o["version"] = s.outline_version(o["title"], blocks)
    return o


def load_week(backup, title, service):
    """Parse one backup and check it is the week the table says (title and byline date)."""
    o = note_to_outline((s.BACKUPS / backup).read_text(encoding="utf-8"))
    if o["title"] != title or o["service"] != service:
        raise ValueError(f'{backup}: reads "{o["title"]}" / {o["service"]}, expected "{title}" / {service}')
    if not any(k == "main" for k, _ in o["blocks"]):
        raise ValueError(f"{backup}: no main points found")
    return _fix_typos(o)


def _https_context():
    """A verifying TLS context that has CA certificates. python.org's macOS Python (the one on
    PATH and in run-sermon-notes.sh) ships none until its 'Install Certificates.command' is run,
    so a bare urlopen fails CERTIFICATE_VERIFY_FAILED -- it did, 2026-10-23. Use certifi's bundle
    (installed in that Python), else the default store, topped up from macOS's /etc/ssl/cert.pem
    when it is empty. Verification itself is never turned off."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
        if not ctx.cert_store_stats()["x509_ca"] and Path("/etc/ssl/cert.pem").exists():
            ctx.load_verify_locations("/etc/ssl/cert.pem")
        return ctx


def live_services(dry_dir=None):
    """Service dates the live index already lists. A dry run reads DIR/index.json (seed it from
    the site); a real run reads the site itself (cache-busted) and fails closed if it can't --
    better no backfill than an overwrite nobody asked for."""
    if dry_dir is not None:
        path = Path(dry_dir) / "index.json"
        if not path.exists():
            s.log(f"WARNING: {path} not found -- the dry run is not seeded with the live index")
            return set()
        idx = s._read_json(path)
    else:
        url = f"{s.WEB_BASE}index.json?cb={int(time.time())}"
        try:
            with urllib.request.urlopen(url, timeout=30, context=_https_context()) as r:
                idx = json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as e:   # network, TLS, HTTP status, bad JSON
            raise RuntimeError(f"could not read the live index.json ({e}) -- refusing to guess "
                               f"what is already published") from e
    weeks = idx.get("weeks") if isinstance(idx, dict) else None
    if not isinstance(weeks, list):
        raise RuntimeError("the live index.json is unreadable -- refusing to guess what is already published")
    return {w.get("service") for w in weeks if isinstance(w, dict)}


def summary(o):
    count = lambda kind: sum(1 for k, _ in o["blocks"] if k == kind)
    return (f'{o["service"]}  "{o["title"]}"  {o["speaker"]}  main={count("main")} subhead={count("subhead")} '
            f'sub={count("sub")} quote={count("quote")} para={count("para")} '
            f'takeaway={"yes" if o["takeaway"] else "no"}  version={o["version"]}')


def main(argv=None):
    ap = argparse.ArgumentParser(description="Backfill web sermon notes from Apple Note backups.")
    ap.add_argument("--dry-run", metavar="DIR", help="write the week files + index into DIR; no git")
    ap.add_argument("--force", action="store_true", help="overwrite weeks the live index already lists")
    args = ap.parse_args(argv)

    outlines = [load_week(*w) for w in WEEKS]          # every week parses and checks out, or nothing goes
    live = set() if args.force else live_services(args.dry_run)
    todo = []
    for o in outlines:
        s.log(summary(o))
        if o["service"].isoformat() in live:
            s.log(f"SKIP {o['service']}: already in the live index (pass --force to overwrite it)")
        else:
            todo.append(o)
    if not todo:
        s.log("nothing to backfill")
        return 0

    if args.dry_run:
        for o in todo:
            s.write_week_files(o, args.dry_run)
            s.log(f"dry run: wrote {Path(args.dry_run) / (o['service'].isoformat() + '.json')}")
        return 0
    cfg = s.load_config()
    if not s.web_enabled(cfg):
        s.log("WEB_NOTES=0 in gmail.env -- web publishing is off; nothing published")
        return 1
    for o in todo:                                      # one commit per week; a failure stops here,
        s.publish_web(o, cfg)                           # and a re-run skips the weeks already live
    return 0


if __name__ == "__main__":
    sys.exit(main())

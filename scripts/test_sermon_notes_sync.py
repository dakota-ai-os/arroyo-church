#!/usr/bin/env python3
"""Regression tests for sermon_notes_sync.py.  Run:  python3 scripts/test_sermon_notes_sync.py

No network, no Notes, no API, no git. Pins the 2026-09-12 incident: a chatty thread reply replaced
the real outline in the shared note, and the model's request for more content was published
as the KEY TAKEAWAY. Also pins that CORRECTIONS (which Josh sends as replies) still win."""
import atexit
import fcntl
import json
import os
import shutil
import sys
import tempfile
import time
import types
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sermon_notes_sync as s

s.log = lambda msg: None   # keep test output readable

# Sandbox: every file the script keeps state in points at a temp dir, and the model is faked,
# so no test can touch ~/.config/arroyo, the publish clone, or the Anthropic API.
TMP = Path(tempfile.mkdtemp(prefix="sermon-notes-test-"))
atexit.register(shutil.rmtree, TMP, True)
s.STATE, s.WEB_STATE = TMP / "last-written.txt", TMP / "web-published.txt"
s.OUTLINE_CACHE, s.BACKUPS = TMP / "outline-cache.json", TMP / "note-backups"
s.PUBLISH_DIR = TMP / "notes-publish"
TAKEAWAY_CALLS = []
REAL_KEY_TAKEAWAY = s.key_takeaway
FAKE_TAKEAWAY = "Grace keeps giving — giving peace, giving identity, and giving forgiveness."
s.key_takeaway = lambda title, body: TAKEAWAY_CALLS.append(title) or FAKE_TAKEAWAY

OUTLINE = """Grace That Keeps Giving

   1.

   Grace gives you peace

“Paul, an apostle of Christ Jesus by the will of God, To God’s holy people in Ephesus” -Ephesians 1:1-2

   2.

   Graces gives you a new identity

   ”Praise be to the God and Father of our Lord Jesus Christ” -Ephesians 1:3-6

   3.

   Grace gives you forgiveness

”In him we have redemption through his blood, the forgiveness of sins” -Ephesians 1:7-8a
"""

# The actual 9/12 15:53 reply, Apple Mail quoting style.
REPLY = """Yes EJ has them all…he can send them if you need 

The series title is Grace for You 

> On Sep 12, 2026, at 3:32 PM, Dakota Yates <av@arroyochurch.com> wrote:
> 
> Do we have series title slide for this?
> 
>> On Sep 12, 2026, at 10:38 AM, Josh Smith <josh@arroyochurch.com> wrote:
>> 
>> Grace That Keeps Giving 
>> Grace gives you peace 
>> "Paul, an apostle of Christ Jesus" -Ephesians 1:1-2
"""

# A correction, Gmail quoting style: new outline on top, original quoted below.
CORRECTION = """Disregard the first email, this one is correct

Grace That Keeps Giving

1. Grace gives you peace
"Grace and peace to you" -Ephesians 1:2

2. Grace gives you forgiveness
"In him we have redemption" -Ephesians 1:7

On Sat, Sep 12, 2026 at 10:38 AM Josh Smith <josh@arroyochurch.com> wrote:
> Grace That Keeps Giving
> "Paul, an apostle" -Ephesians 1:1-2
"""

# Verbatim from the shared note on 2026-09-13 06:31.
REFUSAL = ("I need the sermon content to write an accurate summary, but only the title and series "
           "name were provided. Could you share the actual sermon text or main points? Once you do, "
           "I'll craft a single sentence in your exact house style—a declarative thesis followed "
           "by an em-dash and a comma-separated list of gerund phrases.")

GOOD = ("Healthy relationships take wisdom — knowing who to trust, speaking and listening like "
        "Christ, discerning when to confront, giving people room, and letting love cover offenses "
        "instead of stirring up strife.")


def at(h, m):
    return datetime(2026, 9, 12, h, m, tzinfo=timezone.utc)


failures = []
def check(name, cond):
    print(("  ok    " if cond else "  FAIL  ") + name)
    if not cond:
        failures.append(name)


print("selection")
reply_text = s.strip_reply(REPLY)
check("reply strips down to only its new lines", "Paul, an apostle" not in reply_text and "EJ" in reply_text)
check("stripped reply is NOT a sermon (the 9/12 bug)",
      not s.looks_like_sermon("Re: Sermon Notes for 9/13/26", reply_text))
check("real outline IS a sermon", s.looks_like_sermon("Sermon Notes for 9/13/26", s.strip_reply(OUTLINE)))

picked = s.choose_candidate([
    (at(10, 38), "Sermon Notes for 9/13/26", s.strip_reply(OUTLINE)),
    (at(15, 53), "Re: Sermon Notes for 9/13/26", reply_text),
])
check("newer chatty reply loses to the earlier real outline",
      picked is not None and picked[0] == "Sermon Notes for 9/13/26")

corr = s.strip_reply(CORRECTION)
check("correction keeps its new outline, drops the quoted original",
      "Ephesians 1:7" in corr and "Paul, an apostle" not in corr)
picked = s.choose_candidate([
    (at(10, 38), "Sermon Notes for 9/13/26", s.strip_reply(OUTLINE)),
    (at(16, 0), "Re: Sermon Notes for 9/13/26", corr),
])
check("a newer CORRECTION reply still wins (corrections arrive as replies)",
      picked is not None and picked[2] == corr)

check("no candidates -> None", s.choose_candidate([]) is None)
check("only chatter -> None, so the note is left untouched",
      s.choose_candidate([(at(15, 53), "Re: Sermon Notes for 9/13/26", reply_text)]) is None)
check("loose subject still needs scripture",
      not s.looks_like_sermon("Slides", "Worship night graphics attached, see you Sunday"))

print("takeaway")
check("the refusal that was published is rejected", s.takeaway_problem(REFUSAL) is not None)
check("a real house-style takeaway is accepted", s.takeaway_problem(GOOD) is None)
check("empty is rejected", s.takeaway_problem("") is not None)
check("no em-dash is rejected", s.takeaway_problem("Grace gives peace, identity and forgiveness.") is not None)

print("mailboxes (2026-10-17: Josh sends to dakota@)")
base = {"GMAIL_USER": "av@x.com", "GMAIL_APP_PASSWORD": "pw1"}
check("primary only -> one INBOX mailbox", s.accounts(base) == [("av@x.com", "pw1", "INBOX")])
two = dict(base, GMAIL_USER_2="dakota@x.com", GMAIL_APP_PASSWORD_2="pw2", GMAIL_MAILBOX_2="[Gmail]/All Mail")
check("a second account is read from All Mail",
      s.accounts(two) == [("av@x.com", "pw1", "INBOX"), ("dakota@x.com", "pw2", "[Gmail]/All Mail")])

print("marker: stand down vs republish a later correction")
from datetime import timedelta
sent = datetime(2026, 10, 16, 14, 29, tzinfo=timezone(timedelta(hours=-7)))
check("other week -> not current", not s.marker_says_current("2026-10-11", "2026-10-18", sent))
check("old bare-date marker for this week -> stand down", s.marker_says_current("2026-10-18", "2026-10-18", sent))
m = s.marker_value("2026-10-18", sent)
check("same email again -> stand down", s.marker_says_current(m, "2026-10-18", sent))
check("NEWER outline the same night -> republish",
      not s.marker_says_current(m, "2026-10-18", sent + timedelta(hours=7)))
check("older email -> stand down", s.marker_says_current(m, "2026-10-18", sent - timedelta(days=1)))

print("forwards")
orig_t = datetime(2026, 10, 9, 21, 29, tzinfo=timezone.utc)
fwd_t = datetime(2026, 10, 11, 13, 38, tzinfo=timezone.utc)
picked = s.choose_candidate([(fwd_t, "Fwd: Sermon Notes", OUTLINE), (orig_t, "Sermon Notes", OUTLINE)])
check("the original beats a newer forward of it", picked is not None and picked[0] == "Sermon Notes")
picked = s.choose_candidate([(fwd_t, "Fwd: Sermon Notes", OUTLINE)])
check("a forward still counts when it is the only copy", picked is not None)
gmail_fwd = ("FYI see below\n\n---------- Forwarded message ---------\nFrom: Josh Smith <josh@x.com>\n"
             "Date: Fri, Oct 9, 2026 at 2:29 PM\nSubject: Sermon Notes\nTo: Dakota <dakota@x.com>\n\n" + OUTLINE)
title, _ = s.split_title_and_body(s.strip_reply(gmail_fwd))
check("Gmail forward header (and the FYI above it) never becomes the title",
      title == OUTLINE.splitlines()[0].strip())

print("Apple Mail forward + unnumbered outline (shape of 2026-10-17)")
APPLE_FWD = ("\nDakota Yates\n\n555.555.5555\nexample.com\n\n￼\n\n> Begin forwarded message:\n> \n"
             "> From: Josh <josh@x.com>\n> Subject: Sermon Notes\n> Date: October 15, 2026 at 4:36:52 PM PDT\n"
             "> To: Dakota <dakota@x.com>, ej@x.com\n> \n> How God Restores\n> \n> No one is beyond repair \n> \n"
             "> ”Therefore, remember that formerly you were far away” -Ephesians 2:11-13\n> \n"
             "> Peace with God brings peace with others   \n> \n> ”For he himself is our peace” -Ephesians 2:14-18\n> \n"
             "> 2 Reasons Peace Spreads\n> \n> The record is torn up \n> \n> Your sin is seen  \n> \n"
             "> Jesus brings us together \n> \n> “Consequently, you are no longer foreigners” -Ephesians 2:19-22\n> \n> \n"
             "> 4 Reasons for Togetherness\n> \n> #1 Same citizenship: heaven \n> #2 Same family: children of God\n> \n")
body = s.strip_reply(APPLE_FWD)
title, rest = s.split_title_and_body(body)
check("the forward is unwrapped: title is the outline's first line", title == "How God Restores")
check("an unwrapped forward counts as sermon content", s.looks_like_sermon("Fwd: Sermon Notes", body))
check("no 'N.' markers -> the unnumbered parser is the one used", not s.LONE_MARKER.search(rest))
kinds = [k for k, _ in s.parse_unnumbered(rest)]
check("points, verses, list headings and items come out in sermon order",
      kinds == ["main", "text", "main", "text", "subhead", "sub", "sub", "main", "text", "subhead", "sub", "sub"])
mains = [v for k, v in s.parse_unnumbered(rest) if k == "main"]
check("main points are numbered 1-3", mains == ["1. No one is beyond repair", "2. Peace with God brings peace with others",
                                                "3. Jesus brings us together"])
check("'#1' items lose their marker", ("sub", "Same citizenship: heaven") in s.parse_unnumbered(rest))
LAST_WEEK = ("Saved from sin\n\n“As for you, you were dead” -Ephesians 2:1-3\n\nTruths About Sin\n\n"
             "-What is sin? To miss the mark\n\n-Why have all sinned? Sin surrounds us\n\nSaved by grace\n\n"
             "“But because of his great love” -Ephesians 2:4-5\n\n“For it is by grace” -Ephesians 2:6-9\n\n"
             "Saved for good works\n\n“For we are God’s workmanship” -Ephesians 2:10\n\n"
             "Clarification and Motivation\n\n-CLARIFICATION: saved TO do good works\n\n-MOTIVATION: gratitude and trust")
check("10/11 shape parses the way it was restated by hand",
      [k for k, _ in s.parse_unnumbered(LAST_WEEK)] ==
      ["main", "text", "subhead", "sub", "sub", "main", "text", "text", "main", "text", "subhead", "sub", "sub"])
check("the numbered Google-Docs format still uses the old parser", s.LONE_MARKER.search(s.split_title_and_body(OUTLINE)[1]))

print("review 2026-10-17: replies must never replace the outline")
check("a clock time is not scripture", not s.looks_like_sermon("Re: Sermon Notes", "Got them, see you Sunday 9:30"))
check("a reply citing ONE verse is not an outline",
      not s.looks_like_sermon("Re: Sermon Notes for 10/18/26", "Got it, I'll put Ephesians 2:14 on the lower third"))
check("a real outline still qualifies", s.looks_like_sermon("Sermon Notes", s.strip_reply(APPLE_FWD)))
reply_t = datetime(2026, 10, 18, 4, 0, tzinfo=timezone.utc)   # Sat 9 PM Pacific, after the outline
picked = s.choose_candidate([(reply_t, "Re: Sermon Notes", "Yes the Ephesians 2:14 slide is ready"),
                             (orig_t, "Sermon Notes for 10/18/26", OUTLINE)])
check("a later one-verse reply loses to the outline", picked is not None and picked[0] == "Sermon Notes for 10/18/26")
last_wk = datetime(2026, 10, 3, 20, 0, tzinfo=timezone.utc)
this_fwd = datetime(2026, 10, 17, 1, 3, tzinfo=timezone.utc)     # Fri 6 PM Pacific
picked = s.choose_candidate([(last_wk, "Sermon Notes", OUTLINE), (this_fwd, "Fwd: Sermon Notes", OUTLINE)])
check("this week's forward beats LAST week's original", picked is not None and picked[0] == "Fwd: Sermon Notes")
wrapped = ("---------- Forwarded message ---------\nFrom: Josh <josh@x.com>\nDate: Fri, Oct 9, 2026\n"
           "Subject: Sermon Notes\nTo: Dakota Yates <dakota@x.com>, EJ <ej@x.com>,\n Arroyo AV <av@x.com>\n\n" + OUTLINE)
check("a wrapped To: line never becomes the title",
      s.split_title_and_body(s.strip_reply(wrapped))[0] == OUTLINE.splitlines()[0].strip())
check("upcoming Sunday from a Saturday", s.upcoming_sunday(datetime(2026, 10, 17, 20, 0)).isoformat() == "2026-10-18")
check("upcoming Sunday on a Sunday is today", s.upcoming_sunday(datetime(2026, 10, 18, 8, 0)).isoformat() == "2026-10-18")

print("review 2026-10-17: outline shapes")
counted = ("2 Truths About the Spirit\n\nThe Spirit was promised:\n\n“I will give you a new heart” -Ezekiel 36:26-27\n\n"
           "The Spirit seals you\n\n“You were marked in him with a seal” -Ephesians 1:13-14\n\n"
           "Walk by the Spirit\n\n“Since we live by the Spirit” -Galatians 5:25")
k = [x for x, _ in s.parse_unnumbered(counted)]
check("items of a counted list stay items even when a verse follows",
      k == ["subhead", "sub", "text", "sub", "text", "main", "text"])
hashed = ("#1 Walk in unity\n\n“Make every effort to keep the unity” -Ephesians 4:3\n\n"
          "#2 Walk in love\n\n“Walk in the way of love” -Ephesians 5:2")
check("a lone '#1 heading' before a verse is a main point",
      [v for x, v in s.parse_unnumbered(hashed) if x == "main"] == ["1. Walk in unity", "2. Walk in love"])
joined = "Saved for good works\n\n“For we are God’s workmanship” -Ephesians 2:10\n\n4 Reasons\n#1 One\n#2 Two\n#3 Three\n#4 Four"
check("a heading and its '#' items in one paragraph are split",
      [x for x, _ in s.parse_unnumbered(joined)] == ["main", "text", "subhead", "sub", "sub", "sub", "sub"])
numbered = "1. No one is beyond repair\n\n“Therefore, remember” -Ephesians 2:11"
check("an author-numbered heading is not double-numbered",
      s.parse_unnumbered(numbered)[0] == ("main", "1. No one is beyond repair"))

print("second review 2026-10-17")
up = s.upcoming_sunday()
d = f"{up.month}/{up.day}/{up.year % 100}"
nxt = up + timedelta(days=7)
dn = f"{nxt.month}/{nxt.day}/{nxt.year % 100}"
base_t = datetime(up.year, up.month, up.day, 0, 0, tzinfo=timezone.utc) - timedelta(days=3)
two_verse_reply = "Slides for Ephesians 2:11-13 and Ephesians 2:14-18 are loaded in ProPresenter. Thanks!"
picked = s.choose_candidate([(base_t + timedelta(days=1), f"Re: Sermon Notes {d}", two_verse_reply),
                             (base_t, f"Sermon Notes {d}", OUTLINE)])
check("a two-verse reply-all does not replace the outline", picked is not None and picked[0] == f"Sermon Notes {d}")
correction = "Disregard the first email, this one is the truth\n\n" + OUTLINE
picked = s.choose_candidate([(base_t + timedelta(days=1), f"Re: Sermon Notes {d}", correction),
                             (base_t, f"Sermon Notes {d}", OUTLINE)])
check("a reply that opens like a correction still replaces it", picked is not None and picked[0].startswith("Re:"))
picked = s.choose_candidate([(base_t - timedelta(days=1), f"Sermon Notes {dn}", OUTLINE),
                             (base_t, f"Sermon Notes {d}", OUTLINE)])
check("an outline sent early for NEXT week doesn't displace this Sunday's", picked is not None and picked[0] == f"Sermon Notes {d}")
check("abbreviated references count", len(s.scripture_refs("-Eph 1:13-14 and -Rom 8:1 and -Ezek. 36:26")) == 3)
check("names with clock times are not verses", s.scripture_refs("Call times: John 8:00, Daniel 6:30pm") == set())
outlook = "Thanks Josh, got it!\n\n________________________________\nFrom: Josh Smith\nSent: Friday\n\n" + OUTLINE
check("an Outlook reply is cut at its separator", s.strip_reply(outlook) == "Thanks Josh, got it!")
wrapped_attr = "Sounds good\n\nOn Sat, Oct 17, 2026 at 9:02 PM Josh Smith <\njosh@x.com> wrote:\n\n" + OUTLINE
check("a wrapped Gmail attribution is cut", s.strip_reply(wrapped_attr) == "Sounds good")
nested = ("> Begin forwarded message:\n> \n> From: Josh <josh@x.com>\n> Subject: Fwd: Notes\n> \n"
          "> Here are Cristian's notes for Sunday\n> \n> ---------- Forwarded message ---------\n"
          "> From: Cristian <c@x.com>\n> Date: Thu, Oct 15, 2026 at 9:00 AM\n> \n> " + OUTLINE.replace("\n", "\n> "))
check("a forward of a forward unwraps to the outline",
      s.split_title_and_body(s.strip_reply(nested))[0] == OUTLINE.splitlines()[0].strip())
check("Apple Mail forward date is read", s.forward_sent_date(APPLE_FWD).strftime("%Y-%m-%d %H:%M") == "2026-10-15 16:36")
gm = "x\n---------- Forwarded message ---------\nFrom: J <j@x.com>\nDate: Fri, Oct 9, 2026 at 2:29 PM\nSubject: S\n\nbody"
check("Gmail forward date is read", s.forward_sent_date(gm).strftime("%Y-%m-%d %H:%M") == "2026-10-09 14:29")
mk = s.marker_value("2026-10-18", sent, OUTLINE)
check("the same outline again (even sent later) stands down",
      s.marker_says_current(mk, "2026-10-18", sent + timedelta(hours=5), OUTLINE))
check("different text sent later republishes",
      not s.marker_says_current(mk, "2026-10-18", sent + timedelta(hours=5), correction))
cite = "Saved for good works\n\n“For we are God’s workmanship”\n-Ephesians 2:10\n\nNext point\n\n“Verse” -Ephesians 2:11"
check("a '-Book c:v' line on its own stays with its verse",
      [k for k, _ in s.parse_unnumbered(cite)] == ["main", "text", "main", "text"])
check("'40 Days of Prayer' doesn't open a 40-item list",
      [k for k, _ in s.parse_unnumbered("40 Days of Prayer\n\nPray honestly\n\n“Verse” -Psalm 62:8")] ==
      ["subhead", "main", "text"])

print("service date with no date in the subject")
check("Sunday-afternoon email -> NEXT Sunday",
      s.sunday_from_subject("Sermon Notes", datetime(2026, 10, 18, 22, 0, tzinfo=timezone.utc)).date().isoformat() == "2026-10-25")
fri = datetime(2026, 10, 9, 21, 29, tzinfo=timezone.utc)     # Fri 2:29 PM Pacific
check("Friday email -> that Sunday", s.sunday_from_subject("Sermon Notes", fri).date().isoformat() == "2026-10-11")
sun = datetime(2026, 10, 11, 13, 30, tzinfo=timezone.utc)    # Sun 6:30 AM Pacific
check("Sunday-morning email -> the same Sunday", s.sunday_from_subject("Re: Sermon Notes", sun).date().isoformat() == "2026-10-11")
check("a dated subject still wins", s.sunday_from_subject("Sermon Notes for 10/18/26", fri).date().isoformat() == "2026-10-18")

print("parse_structure: Josh's lone-'N.' Google-Docs outline")
_, rest = s.split_title_and_body(OUTLINE)
check("points and verses alternate", [k for k, _ in s.parse_structure(rest)] == ["main", "text"] * 3)
check("main points carry their number", [v for k, v in s.parse_structure(rest) if k == "main"] ==
      ["1. Grace gives you peace", "2. Graces gives you a new identity", "3. Grace gives you forgiveness"])
SUBLIST = ("   1.\n\n   Point one\n\n   2.\n\n   Point two\n\n   1.\n\n   Understand the weight of your words: x\n\n"
           "   2.\n\n   Second sub\n\n   3.\n\n   Third sub\n\n   3.\n\n   Point three\n\n3 Ways to Communicate Like Christ\n")
check("a 3-item sub-list followed by main point 3 is not swapped with it",
      s.parse_structure(SUBLIST) == [("main", "1. Point one"), ("main", "2. Point two"),
                                     ("sub", "Understand the weight of your words: x"), ("sub", "Second sub"),
                                     ("sub", "Third sub"), ("main", "3. Point three"),
                                     ("subhead", "3 Ways to Communicate Like Christ")])

# 10/25: a counted heading with "#1"/"#2" questions under it. "#2 ..." was 69 characters, so the old
# length-only test made it a gold subhead while the 89-character "#1 ..." stayed body text.
OCT25 = ("   1.\n\n   Grace get you to go even if it means suffering\n\n\u201cVerse one\u201d -Ephesians 3:1-3, 13\n\n"
         "   2.\n\n   Grace gets the worst sinners to go share the Savior\n\n\u201cVerse two\u201d -Ephesians 3:4-9\n\n"
         "2 Questions About Sinners Sharing the Savior Answered\n\n"
         "#1 Why can the worst sinners share the Savior? Grace is about His love not your worthiness\n\n"
         "#2 Why should the Savior be shared? The Savior is boundless in riches\n\n"
         "   3.\n\n   By grace you can go to God freely and confidently\n\n\u201cVerse three\u201d -Ephesians 3:12\n")
check("10/25: the counted heading is a subhead; its '#1'/'#2' questions are body text, not headings",
      [k for k, _ in s.parse_structure(OCT25)] == ["main", "text", "main", "text", "subhead", "text", "text", "main", "text"])
check("a two-sentence line or a '#N'/'-' item is never a subheading",
      not s._is_subheading("#2 Why should the Savior be shared? The Savior is boundless in riches")
      and not s._is_subheading("Grace is free. It is not cheap") and not s._is_subheading("- a bullet")
      and s._is_subheading("2 Questions About Sinners Sharing the Savior Answered")
      and s._is_subheading("3 Ways to Communicate Like Christ"))
check("unnumbered: a short two-sentence line is body text, not a subhead",
      ("text", "Why go? Because grace sends us") in s.parse_unnumbered("Why go? Because grace sends us\n\nGo boldly\n\n\u201cVerse\u201d -Acts 1:8"))

print("parse_slides: a guest's slide deck (shape of Cristian Ayquipa, 2026-09-06)")
SLIDES = ("1. Title- STAYING CONNECTED\n2. THE TRUE VINE\n“I am the true vine, and my Father\nis the gardener.”\n"
          "John 15:1\n3. JESUS IS THE SOURCE.\nWE ARE THE BRANCHES.\n4. Point 1- PRUNING IS PART OF\nSTAYING CONNECTED\n"
          "5. 3 WAYS TO STAY CONNECTED\n- Pray: talk to Him\n- Read\n- Gather\n")
check("a slide list is detected, an outline is not", s.looks_like_slides(SLIDES) and not s.looks_like_slides(OUTLINE))
st, sb = s.parse_slides(SLIDES)
check("the 'Title-' slide is the title", st == "STAYING CONNECTED")
check("slide numbers dropped; headings, verse + ref, framing, point, list",
      sb == [("subhead", "THE TRUE VINE"),
             ("text", "“I am the true vine, and my Father is the gardener.” -John 15:1"),
             ("text", "JESUS IS THE SOURCE."), ("text", "WE ARE THE BRANCHES."),
             ("main", "1. PRUNING IS PART OF STAYING CONNECTED"), ("subhead", "3 WAYS TO STAY CONNECTED"),
             ("sub", "Pray: talk to Him"), ("sub", "Read"), ("sub", "Gather")])

print("build_outline: one parse feeds the Note and the web copy")
KINDS = {"main", "subhead", "sub", "para", "quote"}
o = s.build_outline("Sermon Notes for 10/25/26", orig_t, OUTLINE)
check("shape", set(o) == {"title", "service", "blocks", "takeaway", "speaker", "format", "version"})
check("lone-N. outline: title, service date, format",
      o["title"] == "Grace That Keeps Giving" and o["service"] == date(2026, 10, 25) and o["format"] == "outline")
check("lone-N. outline: verses become 'quote' blocks", [k for k, _ in o["blocks"]] == ["main", "quote"] * 3)
check("quotes are straightened (a right-quote opener still counts as scripture)",
      o["blocks"][3][1].startswith('"Praise be') and not any(c in v for _, v in o["blocks"] for c in "“”’"))
check("version is a 12-hex fingerprint", len(o["version"]) == 12 and int(o["version"], 16) >= 0)
check("no sender -> no speaker", o["speaker"] is None)
ou = s.build_outline("Fwd: Sermon Notes", s.forward_sent_date(APPLE_FWD), s.strip_reply(APPLE_FWD))
check("unnumbered outline: the parser's 'text' splits into quote/sub as the Note renders it",
      [k for k, _ in ou["blocks"]] == ["main", "quote", "main", "quote", "subhead", "sub", "sub", "main", "quote",
                                       "subhead", "sub", "sub"] and ou["service"] == date(2026, 10, 18))
osl = s.build_outline("Slides", orig_t, SLIDES)
check("slide deck: format 'slides', prose framing is 'para'",
      osl["format"] == "slides" and osl["title"] == "STAYING CONNECTED" and
      [k for k, _ in osl["blocks"]] == ["subhead", "quote", "para", "para", "main", "subhead", "sub", "sub", "sub"])
check("every block kind is in the web contract",
      all(k in KINDS for x in (o, ou, osl) for k, _ in x["blocks"]))
check("markdown asterisks never reach the blocks",
      "*" not in "".join(v for _, v in s.build_outline("Sermon Notes", orig_t, OUTLINE.replace("Grace gives you peace",
                                                                                               "*Grace gives you peace*"))["blocks"]))

print("KEY TAKEAWAY: at most one model call per distinct outline")
TAKEAWAY_CALLS.clear()
s.OUTLINE_CACHE.unlink(missing_ok=True)
a1 = s.build_outline("Sermon Notes for 10/25/26", orig_t, OUTLINE)
a2 = s.build_outline("Sermon Notes for 10/25/26", orig_t + timedelta(days=1), OUTLINE)   # e.g. Sat web, Sun Note
check("the same outline twice -> one call, same sentence",
      len(TAKEAWAY_CALLS) == 1 and a1["takeaway"] == a2["takeaway"] == FAKE_TAKEAWAY)
s.build_outline("Sermon Notes for 10/25/26", orig_t, CORRECTION)
check("a different outline -> a new call", len(TAKEAWAY_CALLS) == 2)
real_kt = s.key_takeaway
s.key_takeaway = lambda t, b: TAKEAWAY_CALLS.append(t) or ""
s.build_outline("Slides", orig_t, SLIDES); s.build_outline("Slides", orig_t, SLIDES)
check("an empty takeaway is not cached (a later run may still get one)", len(TAKEAWAY_CALLS) == 4)
s.key_takeaway = real_kt
for n in range(12):
    s.cached_takeaway(f"{n:012x}", "t", "b")
cache = json.loads(s.OUTLINE_CACHE.read_text())
check("the cache keeps only the last 10", len(cache) == 10 and f"{11:012x}" in cache and f"{0:012x}" not in cache)

print("KEY TAKEAWAY: the API call is bounded (it now runs before the GUI probe)")
seen_kw = {}
class _FakeAnthropic:
    def __init__(self, **kw):
        seen_kw.update(kw)
        self.messages = types.SimpleNamespace(create=lambda **k: types.SimpleNamespace(
            content=[types.SimpleNamespace(text=FAKE_TAKEAWAY)]))
keep_mod, keep_env = sys.modules.get("anthropic"), os.environ.get("ANTHROPIC_API_KEY")
sys.modules["anthropic"], os.environ["ANTHROPIC_API_KEY"] = types.SimpleNamespace(Anthropic=_FakeAnthropic), "test-not-a-key"
try:
    got = REAL_KEY_TAKEAWAY("t", "b")
finally:
    if keep_mod is None:
        sys.modules.pop("anthropic", None)
    else:
        sys.modules["anthropic"] = keep_mod
    if keep_env is None:
        os.environ.pop("ANTHROPIC_API_KEY", None)
    else:
        os.environ["ANTHROPIC_API_KEY"] = keep_env
check("60s timeout and one retry, not the SDK's 600s x 3 tries",
      seen_kw.get("timeout") == 60 and seen_kw.get("max_retries") == 1 and got == FAKE_TAKEAWAY)

print("speaker: who preached")
JOSH = "Josh Smith <josh@arroyochurch.com>"
check("Josh's address -> Pastor Josh Smith", s.speaker_for(JOSH) == "Pastor Josh Smith"
      and s.speaker_for("josh@arroyochurch.com") == "Pastor Josh Smith")
check("direct email: the envelope sender", s.original_sender(JOSH, "Sermon Notes 10/25/26", OUTLINE) == JOSH)
apple_josh = APPLE_FWD.replace("josh@x.com", "josh@arroyochurch.com")
check("Apple Mail forward: the forwarded From:, not Dakota",
      s.speaker_for(s.original_sender("Dakota Yates <av@arroyochurch.com>", "Fwd: Sermon Notes", apple_josh))
      == "Pastor Josh Smith")
gmail_josh = gmail_fwd.replace("josh@x.com", "josh@arroyochurch.com")
check("Gmail forward: the forwarded From:, not Dakota",
      s.speaker_for(s.original_sender("Dakota Yates <av@arroyochurch.com>", "Fwd: Sermon Notes", gmail_josh))
      == "Pastor Josh Smith")
check("Gmail's bolded '*From:*' line is read",
      s.forward_sender("---------- Forwarded message ---------\n*From:* *Josh Smith* <josh@arroyochurch.com>\n\nx")
      == "Josh Smith <josh@arroyochurch.com>")
check("a guest -> their name", s.speaker_for("Cristian Ayquipa <cristian@vinechurch.org>") == "Cristian Ayquipa")
check("a guest's notes forwarded twice -> the guest (innermost From:)",
      s.original_sender("Dakota Yates <av@arroyochurch.com>", "Fwd: Fwd: Notes", nested) == "Cristian <c@x.com>")
check("'Fwd:' with no readable block -> unknown, never the forwarder",
      s.original_sender("Dakota Yates <av@arroyochurch.com>", "Fwd: Sermon Notes", OUTLINE) is None)
check("a mailbox name, a lone first name or a bare address is not a speaker",
      s.speaker_for("Arroyo AV <av@arroyochurch.com>") is None and s.speaker_for("Cristian <c@x.com>") is None
      and s.speaker_for("guest@vinechurch.org") is None and s.speaker_for(None) is None)
check("names with particles / titles survive", s.speaker_for("Maria de la Cruz <m@x.org>") == "Maria de la Cruz"
      and s.speaker_for("Pastor Cristian Ayquipa <c@x.org>") == "Pastor Cristian Ayquipa")
check("accented guest names are names (review 2026-10-23)",
      s.speaker_for("Jos\u00e9 Garc\u00eda <j@x.org>") == "Jos\u00e9 Garc\u00eda"
      and s.speaker_for("Cristi\u00e1n Ayquipa <c@x.org>") == "Cristi\u00e1n Ayquipa"
      and s.speaker_for("Zo\u00eb Smith <z@x.org>") == "Zo\u00eb Smith")
check("Josh from another address, by name -> Pastor Josh Smith (the Note's byline never loses 'Pastor')",
      s.speaker_for("Josh Smith <pastorjosh@arroyochurch.com>") == "Pastor Josh Smith"
      and s.speaker_for("Joshua Smith <joshua@gmail.example>") == "Pastor Josh Smith"
      and s.speaker_for("Pastor Josh Smith <p@arroyochurch.com>") == "Pastor Josh Smith")
check("'Last, First' is still not read as a name", s.speaker_for('"Ayquipa, Cristian" <c@x.org>') is None)
picked = s.choose_candidate([(orig_t, "Sermon Notes for 10/18/26", OUTLINE, "Cristian Ayquipa <c@x.org>")])
check("choose_candidate carries the sender at the end", picked is not None and picked[3] == "Cristian Ayquipa <c@x.org>")
check("...and a 3-tuple still works (sender None)",
      s.choose_candidate([(orig_t, "Sermon Notes for 10/18/26", OUTLINE)])[3] is None)


def render_note(outline):
    """What update_note() would paste (header, body), with Notes fully stubbed out."""
    got, keep = {}, {n: getattr(s, n) for n in ("run_osascript", "attachment_count", "_focus_note",
                                                "replace_around_image")}
    prev = '<div><img src="data:image/png;base64,AAAA"></div><div><i>*To save and edit this note</i></div>'
    s.run_osascript = lambda script, timeout=90: prev if "return body" in script else ""
    s.attachment_count = lambda nid: 1
    s._focus_note = lambda nid: None
    s.replace_around_image = lambda nid, h, b, skip: got.update(header=h, body=b)
    sleep, s.time.sleep = s.time.sleep, (lambda x: None)
    try:
        s.update_note("x-coredata://test", outline)
    finally:
        s.time.sleep = sleep
        for n, f in keep.items():
            setattr(s, n, f)
    return got


print("the Note's byline")
check("no speaker -> Pastor Josh Smith, as before",
      "<b>Pastor Josh Smith | October 25th, 2026</b>" in render_note(o)["header"])
check("a guest -> the guest's name",
      "<b>Cristian Ayquipa | October 25th, 2026</b>" in
      render_note(s.build_outline("Sermon Notes for 10/25/26", orig_t, OUTLINE, "Cristian Ayquipa <c@x.org>"))["header"])
nb = render_note(osl)["body"]
check("quote / para / sub still render as before (verse block, plain div, ordered list with bold label)",
      '<div>"I am the true vine, and my Father is the gardener." -John 15:1</div>' in nb
      and "<div>JESUS IS THE SOURCE.</div>" in nb and "<ol><li><b>Pray:</b> talk to Him</li><li>Read</li>" in nb)

print("web copy: release time across DST")
check("July Sunday -> PDT", s.release_at(date(2026, 7, 12)) == "2026-07-12T06:45:00-07:00")
check("November Sunday -> PST", s.release_at(date(2026, 11, 8)) == "2026-11-08T06:45:00-08:00")
check("fall-back Sunday (clocks change at 2am) -> PST", s.release_at(date(2026, 11, 1)) == "2026-11-01T06:45:00-08:00")
check("spring-forward Sunday -> PDT", s.release_at(date(2026, 3, 8)) == "2026-03-08T06:45:00-07:00")

print("web copy: index merge / dedupe / cap")
wk = lambda svc, t="t": {"service": svc, "title": t, "speaker": None, "release_at": "x", "file": f"{svc}.json"}
merged = s.merge_index({"weeks": [wk("2026-10-18"), wk("2026-10-11")]}, wk("2026-10-25"))
check("newest first", [w["service"] for w in merged] == ["2026-10-25", "2026-10-18", "2026-10-11"])
merged = s.merge_index({"weeks": merged}, wk("2026-10-18", "fixed"))
check("a republished week replaces its entry",
      [w["service"] for w in merged] == ["2026-10-25", "2026-10-18", "2026-10-11"] and merged[1]["title"] == "fixed")
many = {"weeks": [wk((date(2025, 1, 5) + timedelta(weeks=n)).isoformat()) for n in range(60)]}
kept = s.merge_index(many, wk("2026-10-25"))
check("never capped: every week stays, newest first (the page's archive lists them all)",
      len(kept) == 61 and kept[0]["service"] == "2026-10-25" and kept[-1]["service"] == "2025-01-05"
      and [w["service"] for w in kept] == sorted((w["service"] for w in kept), reverse=True))
check("junk entries are dropped", s.merge_index({"weeks": ["x", {}, None]}, wk("2026-10-25")) == [wk("2026-10-25")])

out_dir = TMP / "web-files"
t0 = datetime(2026, 10, 24, 20, 0, tzinfo=s.CHURCH_TZ)
o_josh = s.build_outline("Sermon Notes for 10/25/26", orig_t, OUTLINE, JOSH)
check("first write changes files", s.write_week_files(o_josh, out_dir, now=t0))
doc = json.loads((out_dir / "2026-10-25.json").read_text())
idx = json.loads((out_dir / "index.json").read_text())
check("week file: contract fields, in order",
      list(doc) == ["service", "title", "speaker", "release_at", "published_at", "takeaway", "format", "version", "blocks"])
check("week file: values", doc["service"] == "2026-10-25" and doc["speaker"] == "Pastor Josh Smith"
      and doc["release_at"] == "2026-10-25T06:45:00-07:00" and doc["published_at"] == "2026-10-24T20:00:00-07:00"
      and doc["takeaway"] == FAKE_TAKEAWAY and doc["blocks"][0] == {"kind": "main", "text": "1. Grace gives you peace"})
check("index: contract fields", list(idx) == ["updated", "weeks"] and
      idx["weeks"] == [{"service": "2026-10-25", "title": "Grace That Keeps Giving", "speaker": "Pastor Josh Smith",
                        "release_at": "2026-10-25T06:45:00-07:00", "file": "2026-10-25.json"}])
check("the same outline again -> files byte-identical (nothing to commit)",
      not s.write_week_files(o_josh, out_dir, now=t0 + timedelta(hours=3)))
s.write_week_files(s.build_outline("Sermon Notes for 10/18/26", orig_t, CORRECTION), out_dir, now=t0)
idx = json.loads((out_dir / "index.json").read_text())
check("another week merges in, newest first", [w["service"] for w in idx["weeks"]] == ["2026-10-25", "2026-10-18"])
(out_dir / "index.json").write_text("{not json")
s.write_week_files(o_josh, out_dir, now=t0)
idx = json.loads((out_dir / "index.json").read_text())
check("a broken index.json is rebuilt from the week files", [w["service"] for w in idx["weeks"]] == ["2026-10-25", "2026-10-18"])
none_t = dict(o_josh, takeaway="")
s.write_week_files(none_t, out_dir, now=t0)
check("no takeaway -> null", json.loads((out_dir / "2026-10-25.json").read_text())["takeaway"] is None)

print("web copy: signatures and contact details stay out of the public repo")
SIGNED = OUTLINE + ("\nJosh Smith\nLead Pastor | Arroyo Church\n(925) 555-0123\njosh@arroyochurch.com\n\n"
                    "Sent from my iPhone\n")
o_signed = s.build_outline("Sermon Notes for 10/25/26", orig_t, s.strip_reply(SIGNED), JOSH)
logged, keep_log = [], s.log
s.log = logged.append
try:
    web = s.week_doc(o_signed, "x")["blocks"]
finally:
    s.log = keep_log
check("the Note's blocks still carry the sign-off (the Note is unchanged)",
      any("555-0123" in v for _, v in o_signed["blocks"]) and "555-0123" in render_note(o_signed)["body"])
check("the web copy drops the phone/email block and stops at 'Sent from my iPhone'",
      [(b["kind"], b["text"]) for b in web] == list(o_josh["blocks"]))
check("...each drop is logged, with the number and address masked",
      len(logged) == 2 and all("WARNING" in m for m in logged) and "[phone]" in logged[0]
      and not any("555" in m or "josh@" in m for m in logged))
check("a '-- ' signature delimiter ends the web copy; '-- Ephesians 2:13' does not",
      s.public_blocks([("main", "1. A"), ("para", "-- Ephesians 2:13"), ("subhead", "-- Josh Smith Lead Pastor"),
                       ("para", "Thanks")]) == [("main", "1. A"), ("para", "-- Ephesians 2:13")])
check("scripture references are not phone numbers",
      s.public_blocks([("quote", '"For God so loved the world" -John 3:16-18'), ("sub", "Romans 12:1-2, 1 Cor 13:4-7")])
      == [("quote", '"For God so loved the world" -John 3:16-18'), ("sub", "Romans 12:1-2, 1 Cor 13:4-7")])

print("web copy: publish_web with git mocked (no network)")


class FakeGit:
    """Enough of git for publish_web: a 'remote' copy of data/sermon-notes that reset restores,
    status diffs against, and push replaces -- optionally rejecting the first N pushes."""
    def __init__(self, reject=0, remote=s.PUBLISH_REMOTE):
        self.calls, self.origin, self.staged, self.reject, self.remote = [], {}, None, reject, remote
        self.fail = {}                                     # {git subcommand: [exception, ...]}, one per call

    def notes(self):
        d = s.PUBLISH_DIR / s.NOTES_SUBDIR
        return {p.name: p.read_text() for p in d.glob("*.json")} if d.exists() else {}

    def __call__(self, args, cwd=None, timeout=60):
        where = Path(cwd or s.PUBLISH_DIR)
        assert s.WORKING_REPO not in [where, *where.parents], f"git ran in the working repo: {args}"
        assert timeout, "every git call needs a timeout"
        self.calls.append(list(args))
        cmd = args[0]
        if self.fail.get(cmd):
            raise self.fail[cmd].pop(0)
        if cmd == "clone":
            (s.PUBLISH_DIR / ".git").mkdir(parents=True)
        elif args[:2] == ["remote", "get-url"]:
            return self.remote + "\n"
        elif cmd == "reset":
            d = s.PUBLISH_DIR / s.NOTES_SUBDIR
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True)
            for name, body in self.origin.items():
                (d / name).write_text(body)
        elif cmd == "status":
            return "" if self.notes() == self.origin else " M data/sermon-notes/index.json\n"
        elif cmd == "commit":
            self.staged = self.notes()
        elif cmd == "push":
            if self.reject:
                self.reject -= 1
                raise RuntimeError("git push failed (1): ! [rejected] HEAD -> main (fetch first)")
            self.origin = dict(self.staged)
        return ""

    def count(self, cmd):
        return sum(1 for c in self.calls if c[0] == cmd)


real_git, real_sleep = s._git, s.time.sleep
s.time.sleep = lambda x: None
cfg_on = {"WEB_NOTES": "1"}
try:
    fg = s._git = FakeGit()
    check("first publish clones, commits and pushes", s.publish_web(o_josh, cfg_on) is True
          and fg.count("clone") == 1 and fg.count("push") == 1)
    clone = next(c for c in fg.calls if c[0] == "clone")
    check("the clone is shallow, of the site repo, with the deploy key",
          "--depth" in clone and s.PUBLISH_REMOTE in clone and f"core.sshCommand={s.PUBLISH_SSH}" in clone)
    check("each attempt starts from fetch + hard reset to origin/main",
          [c[0] for c in fg.calls[3:6]] == ["fetch", "reset", "clean"] and fg.calls[4] == ["reset", "--hard", "origin/main"])
    check("only data/sermon-notes is added and committed",
          ["add", "--", "data/sermon-notes"] in fg.calls
          and next(c for c in fg.calls if c[0] == "commit")[-2:] == ["--", "data/sermon-notes"])
    check("commit message", ["commit", "-q", "-m", "Sermon notes 2026-10-25: Grace That Keeps Giving", "--",
                             "data/sermon-notes"] in fg.calls)
    check("the pushed index lists the week", '"2026-10-25"' in fg.origin.get("index.json", ""))
    n = len(fg.calls)
    check("republishing the identical outline pushes nothing", s.publish_web(o_josh, cfg_on) is False
          and fg.count("commit") == 1 and fg.count("clone") == 1)
    fg.reject = 1
    check("a push the YouTube-sync Action beat is retried on a fresh reset",
          s.publish_web(s.build_outline("Sermon Notes for 11/1/26", orig_t, OUTLINE), cfg_on) is True
          and fg.count("push") == 3 and [c[0] for c in fg.calls[n:]].count("reset") == 3)
    fg.reject = 3
    try:
        s.publish_web(s.build_outline("Sermon Notes for 11/8/26", orig_t, OUTLINE), cfg_on)
        check("three rejected pushes raise", False)
    except RuntimeError:
        check("three rejected pushes raise", True)
    fg = s._git = FakeGit()
    check("WEB_NOTES=0 -> no git at all", s.publish_web(o_josh, {"WEB_NOTES": "0"}) is False and not fg.calls)
    s._git = FakeGit(remote="git@github.com:someone/else.git")
    try:
        s.publish_web(o_josh, cfg_on)
        check("a clone pointing elsewhere is refused", False)
    except RuntimeError:
        check("a clone pointing elsewhere is refused", True)
    real_dir, s.PUBLISH_DIR = s.PUBLISH_DIR, s.WORKING_REPO / "notes-publish"
    fg = s._git = FakeGit()
    try:
        s.publish_web(o_josh, cfg_on)
        check("a publish dir inside the working repo is refused before any git", False)
    except RuntimeError:
        check("a publish dir inside the working repo is refused before any git", not fg.calls)
    s.PUBLISH_DIR = real_dir
finally:
    s._git, s.time.sleep = real_git, real_sleep


def raises(fn, exc=Exception):
    try:
        fn()
    except exc as e:
        return e
    return None


print("web copy: the publish clone heals itself (review 2026-10-23)")
s.time.sleep = lambda x: None
try:
    shutil.rmtree(s.PUBLISH_DIR, ignore_errors=True)
    fg = s._git = FakeGit()
    s.publish_web(o_josh, cfg_on)
    stale = s.PUBLISH_DIR / ".git" / "index.lock"
    fresh = s.PUBLISH_DIR / ".git" / "refs" / "remotes" / "origin" / "main.lock"
    fresh.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("")
    fresh.write_text("")
    os.utime(stale, (time.time() - 3600, time.time() - 3600))
    s.publish_web(o_josh, cfg_on)
    check("a stale lock left by a killed git is swept; a fresh one is left alone", not stale.exists() and fresh.exists())
    fresh.unlink()

    fg.fail = {"reset": [RuntimeError("git reset failed (128): Unable to create '.git/index.lock': File exists.")]}
    check("git failing before the push (a damaged clone): thrown away, re-cloned, and the week still publishes",
          s.publish_web(s.build_outline("Sermon Notes for 11/15/26", orig_t, OUTLINE), cfg_on) is True
          and fg.count("clone") == 2 and '"2026-11-15"' in fg.origin["index.json"])
    fg.fail = {"commit": [RuntimeError("boom"), RuntimeError("boom again")]}
    e = raises(lambda: s.publish_web(s.build_outline("Sermon Notes for 11/22/26", orig_t, OUTLINE), cfg_on))
    check("...but only once per run: a second failure raises", isinstance(e, RuntimeError) and fg.count("clone") == 3)
    fg.fail = {"fetch": [s.subprocess.TimeoutExpired(["git", "fetch"], 120)]}
    e = raises(lambda: s.publish_web(s.build_outline("Sermon Notes for 11/29/26", orig_t, OUTLINE), cfg_on))
    check("a fetch that times out (the network, not the clone) raises without re-cloning",
          isinstance(e, s.subprocess.TimeoutExpired) and fg.count("clone") == 3)
    fg.fail = {"remote": [RuntimeError("git remote failed (128): fatal: not a git repository")]}
    s.publish_web(o_josh, cfg_on)
    check("a clone too broken to name its remote is re-cloned", fg.count("clone") == 4)

    s._discard_clone()
    s.PUBLISH_DIR.mkdir()
    s.publish_web(o_josh, cfg_on)
    check("an empty folder (a clone killed before it began) is replaced by a clone",
          (s.PUBLISH_DIR / ".git").is_dir() and fg.count("clone") == 5)
    s._discard_clone()
    s.PUBLISH_DIR.mkdir()
    (s.PUBLISH_DIR / "someone-elses-file").write_text("x")
    e = raises(lambda: s.publish_web(o_josh, cfg_on))
    check("a non-empty folder that is not a clone is refused, never deleted",
          isinstance(e, RuntimeError) and (s.PUBLISH_DIR / "someone-elses-file").exists())
    shutil.rmtree(s.PUBLISH_DIR)
    (s.PUBLISH_DIR.with_name("notes-publish.discard") / "x").mkdir(parents=True)
    s.publish_web(o_josh, cfg_on)
    check("a '.discard' folder left by a run killed mid-delete is swept",
          not s.PUBLISH_DIR.with_name("notes-publish.discard").exists())

    keep_budget, s.PUBLISH_BUDGET = s.PUBLISH_BUDGET, -1
    e = raises(lambda: s.publish_web(s.build_outline("Sermon Notes for 12/6/26", orig_t, OUTLINE), cfg_on))
    s.PUBLISH_BUDGET = keep_budget
    check("past the time budget no new attempt starts (the next launchd slot is not swallowed)",
          isinstance(e, RuntimeError) and "giving up" in str(e))
    with open(s.PUBLISH_DIR.with_name("notes-publish.lock"), "w") as other:
        fcntl.flock(other, fcntl.LOCK_EX)
        n = len(fg.calls)
        e = raises(lambda: s.publish_web(o_josh, cfg_on))
    check("a publish already running (a hand-run --web-only) is left alone, no git at all",
          isinstance(e, RuntimeError) and "another publish" in str(e) and len(fg.calls) == n)
    real_dir, s.PUBLISH_DIR = s.PUBLISH_DIR, TMP / "something-else"
    e = raises(s._discard_clone)
    s.PUBLISH_DIR = real_dir
    check("_discard_clone only ever deletes a folder named notes-publish", isinstance(e, RuntimeError))
finally:
    s._git, s.time.sleep = real_git, real_sleep

seen = {}
real_run = s.subprocess.run
s.subprocess.run = lambda cmd, **kw: seen.update(cmd=cmd, **kw) or type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
try:
    s._git(["status"])
finally:
    s.subprocess.run = real_run
check("_git runs in the publish clone, with a timeout, no stdin and no prompts",
      seen["cwd"] == str(s.PUBLISH_DIR) and seen["timeout"] and seen["stdin"] == s.subprocess.DEVNULL
      and seen["env"]["GIT_TERMINAL_PROMPT"] == "0" and seen["env"]["GIT_CEILING_DIRECTORIES"] == str(s.PUBLISH_DIR.parent))

print("main(): the web copy and the Note stand down independently")
UP = s.upcoming_sunday()
UP_SUBJ = f"Sermon Notes {UP.month}/{UP.day}/{UP.year % 100}"
PREV = UP - timedelta(days=7)
PREV_SUBJ = f"Sermon Notes {PREV.month}/{PREV.day}/{PREV.year % 100}"
SENT = datetime(UP.year, UP.month, UP.day, tzinfo=timezone.utc) - timedelta(days=3)
SAT_NIGHT = datetime(2026, 10, 24, 20, 0, tzinfo=s.CHURCH_TZ)
SUN_0930 = datetime(2026, 10, 25, 9, 30, tzinfo=s.CHURCH_TZ)    # the last attempt of the week
THIS_WEEK = (UP_SUBJ, SENT, OUTLINE, JOSH)


def run_main(found, gui=None, web_exc=None, argv=(), cfg=None, now=SAT_NIGHT, fetch_exc=None):
    """main() with mail, GUI, git and Notes faked. Returns (exit code or exception, calls)."""
    calls = {"publish": [], "note": [], "gui": 0, "takeaways": []}
    conf = {"GMAIL_USER": "av@x.com", "GMAIL_APP_PASSWORD": "pw", "SERMON_SENDER": "josh@arroyochurch.com",
            "NOTE_ID": "n", "LOOKBACK_DAYS": "8", **(cfg or {})}

    def fetch(c):
        if fetch_exc:
            raise fetch_exc
        return found

    def gui_probe():
        calls["gui"] += 1
        return gui

    def publish(outline, c):
        calls["publish"].append(outline["service"].isoformat())
        calls["takeaways"].append(outline["takeaway"])
        if web_exc:
            raise web_exc
        return True

    def note(nid, outline):
        calls["note"].append(outline["service"].isoformat())
        return outline["title"]

    fakes = {"load_config": lambda: conf, "fetch_latest": fetch, "gui_session_ready": gui_probe,
             "publish_web": publish, "update_note": note, "verify_title": lambda nid, t: None,
             "church_now": lambda: now}
    keep = {n: getattr(s, n) for n in fakes}
    argv_keep, sys.argv = sys.argv, ["sermon_notes_sync.py", *argv]
    for n, f in fakes.items():
        setattr(s, n, f)
    try:
        rc = s.main()
    except Exception as e:
        rc = e
    finally:
        sys.argv = argv_keep
        for n, f in keep.items():
            setattr(s, n, f)
    return rc, calls


def markers():
    return tuple(p.read_text().partition("|")[0] if p.exists() else None for p in (s.STATE, s.WEB_STATE))


def clear_markers():
    s.STATE.unlink(missing_ok=True)
    s.WEB_STATE.unlink(missing_ok=True)


clear_markers()
rc, c = run_main(THIS_WEEK)
check("a new week: web copy published, then the Note, both markers written",
      rc == 0 and c["publish"] == [UP.isoformat()] and c["note"] == [UP.isoformat()] and markers() == (UP.isoformat(),) * 2)
TAKEAWAY_CALLS.clear()
rc, c = run_main(THIS_WEEK)
check("the next attempt stands down: no publish, no GUI probe, no Note, no model call",
      rc == 0 and not c["publish"] and not c["note"] and c["gui"] == 0 and not TAKEAWAY_CALLS)
s.STATE.unlink()
rc, c = run_main(THIS_WEEK)
check("web current, Note missing -> only the Note", rc == 0 and not c["publish"] and c["note"] and c["gui"] == 1)
s.WEB_STATE.unlink()
rc, c = run_main(THIS_WEEK)
check("Note current, web missing -> only the web copy, without a GUI probe",
      rc == 0 and c["publish"] and not c["note"] and c["gui"] == 0 and markers()[1] == UP.isoformat())
clear_markers()
rc, c = run_main(THIS_WEEK, gui="dark wake")
check("dark wake: the web copy still publishes, the Note waits (75), only the web marker is written",
      rc == s.EX_TEMPFAIL and c["publish"] and not c["note"] and markers() == (None, UP.isoformat()))
rc, c = run_main(THIS_WEEK)
check("...and the next attempt writes only the Note", rc == 0 and not c["publish"] and c["note"])
clear_markers()
rc, c = run_main(THIS_WEEK, web_exc=RuntimeError("push refused"))
check("a web failure never blocks the Note, but the run exits 1 (alert)",
      rc == 1 and c["note"] and markers() == (UP.isoformat(), None))
rc, c = run_main(THIS_WEEK, web_exc=RuntimeError("push refused"))
check("...the next attempt retries just the web copy and still alerts", rc == 1 and c["publish"] and not c["note"])
clear_markers()
rc, c = run_main(THIS_WEEK, gui="dark wake", web_exc=RuntimeError("push refused"))
check("web failure in a dark wake on Saturday -> quiet 75 (the next attempt retries both)",
      rc == s.EX_TEMPFAIL and markers() == (None, None))
rc, c = run_main(THIS_WEEK, gui="dark wake", web_exc=RuntimeError("push refused"), now=SUN_0930)
check("...but on the Sunday 09:00 last attempt it exits 1 (nothing retries after it)", rc == 1)
clear_markers()
rc, c = run_main(THIS_WEEK, cfg={"WEB_NOTES": "0"})
check("WEB_NOTES=0: no web copy, no web marker, the Note as before",
      rc == 0 and not c["publish"] and c["note"] and markers() == (UP.isoformat(), None))
rc, c = run_main(THIS_WEEK, cfg={"WEB_NOTES": "0"})
check("WEB_NOTES=0: once the Note is written the run stands down", rc == 0 and not c["publish"] and not c["note"])
rc, c = run_main(THIS_WEEK, cfg={"WEB_NOTES": "0"}, argv=["--web-only"])
check("WEB_NOTES=0 + --web-only: refuses (exit 1), publishes nothing", rc == 1 and not c["publish"])
check("web_enabled defaults on", s.web_enabled({}) and not s.web_enabled({"WEB_NOTES": "off"}))
clear_markers()
old_week = (PREV_SUBJ, SENT - timedelta(days=7), OUTLINE, JOSH)
rc, c = run_main(old_week)
check("an older week is never republished by the schedule (web or Note)", rc == 0 and not c["publish"] and not c["note"])
rc, c = run_main(old_week, argv=["--web-only"])
check("--web-only publishes the newest outline even for a past week; no GUI, no Note, no Note marker",
      rc == 0 and c["publish"] == [PREV.isoformat()] and c["gui"] == 0 and not c["note"]
      and markers() == (None, PREV.isoformat()))
run_main(THIS_WEEK)
rc, c = run_main(THIS_WEEK, argv=["--force"])
check("--force redoes both", rc == 0 and c["publish"] and c["note"])
clear_markers()
rc, c = run_main(None, now=SUN_0930)
check("the Sunday 09:00 alert still fires when today's outline never arrived",
      isinstance(rc, RuntimeError) and "no sermon outline for today" in str(rc))
rc, c = run_main(None, fetch_exc=RuntimeError("could not read av@"), gui="dark wake")
check("mail unreadable in a dark wake -> the quiet 75 it always was", rc == s.EX_TEMPFAIL)
rc, c = run_main(None, fetch_exc=RuntimeError("could not read av@"))
check("mail unreadable with a usable GUI -> raises (alert), as before", isinstance(rc, RuntimeError))
rc, c = run_main(None, fetch_exc=RuntimeError("could not read av@"), gui="dark wake", now=SUN_0930)
check("mail unreadable on the last attempt -> raises even in a dark wake", isinstance(rc, RuntimeError))


print("main(): a web copy without its KEY TAKEAWAY is retried (review 2026-10-23)")
kt = s.key_takeaway
try:
    clear_markers()
    s.OUTLINE_CACHE.unlink(missing_ok=True)
    s.key_takeaway = lambda t, b: ""                       # API down / sentence rejected
    rc, c = run_main(THIS_WEEK)
    check("published without a takeaway: the web copy is NOT marked done (the Note is, as before)",
          rc == 0 and c["takeaways"] == [""] and c["note"] and markers() == (UP.isoformat(), None))
    s.key_takeaway = kt
    rc, c = run_main(THIS_WEEK)
    check("...the next attempt asks again, republishes with the sentence and marks it; no Note rewrite",
          rc == 0 and c["takeaways"] == [FAKE_TAKEAWAY] and not c["note"] and markers() == (UP.isoformat(),) * 2)
    clear_markers()
    s.OUTLINE_CACHE.unlink(missing_ok=True)
    s.key_takeaway = lambda t, b: ""
    rc, c = run_main(THIS_WEEK, now=SUN_0930)
    check("...but the last attempt of the week marks it regardless (nothing retries after it)",
          rc == 0 and markers()[1] == UP.isoformat())
    clear_markers()
    rc, c = run_main(THIS_WEEK, argv=["--web-only"])
    check("--web-only without a takeaway: published, not marked", rc == 0 and c["publish"] and markers() == (None, None))
finally:
    s.key_takeaway = kt

print("backfill: a saved Note body back into an outline (backfill_web_notes, 2026-10-23)")
import backfill_web_notes as bf
NOTICE = ('<div><i><span style="color:#AF52DE">*To save and edit this note, click on the share button at the top, '
          'press “copy” then, create a new note and paste the text into your new note</span></i></div>')
IMG = '<div><img src="data:image/png;base64,AAAA"><br></div>'


def note_html(outline):
    """The shared Note as update_note() leaves it: header, graphic, purple notice, body."""
    got = render_note(outline)
    return got["header"] + IMG + NOTICE + got["body"]


o_guest = dict(o, speaker="Cristian Ayquipa")
for name, fx in (("lone-N. outline", o), ("unnumbered outline: subheads + labelled subs", ou),
                 ("slide deck: opens with a subhead, para framing", osl), ("no takeaway", dict(o, takeaway="")),
                 ("a guest", o_guest)):
    back = bf.note_to_outline(note_html(fx))
    check(f"round trip, {name}: same title, date, blocks, takeaway, version",
          back["title"] == fx["title"] and back["service"] == fx["service"] and back["blocks"] == list(fx["blocks"])
          and back["takeaway"] == fx["takeaway"] and back["version"] == fx["version"] and back["format"] == "outline")
check("round trip: the byline gives the speaker back",
      bf.note_to_outline(note_html(o))["speaker"] == "Pastor Josh Smith"
      and bf.note_to_outline(note_html(o_guest))["speaker"] == "Cristian Ayquipa")

# Notes' own re-serialisation, shaped like the real 9/13, 10/11 and 10/18 backups: span-size headings,
# a byline inside <h3>, <font> on the notice, '&quot' with no semicolon, &nbsp;, a label in <b>, a list
# split in two by a blank line, curly quotes.
SERIALISED = ('<div><b><span style="font-size: 24px">Grace That Keeps Giving</span></b></div>\n'
              '<div><b><h3>Pastor Josh Smith | September 13th, 2026</h3></b><br></div>\n<div><br></div>\n'
              + NOTICE.replace('<span style="color:#AF52DE">', '<font color="#AF52DE">').replace("</span>", "</font>")
              + "\n" + IMG + "\n<div>KEY TAKEAWAY: Grace never stops giving.</div>\n"
              '<div><b><span style="font-size: 18px">1. Grace gives you peace</span></b></div>\n<div><br></div>\n'
              '<div>&quotGrace and peace to you&quot -Ephesians 1:2</div>\n<div><br></div>\n'
              '<div><i>Write some notes here</i><br></div>\n<div><br></div>\n'
              '<div><h2>2. Saved from sin</h2></div>\n<div><b><h2>Truths About Sin</h2></b></div>\n'
              '<ol>\n<li><b>CLARIFICATION:</b> not by works</li>\n<li> Growth&nbsp;only comes from God<b><br></b></li>\n</ol>\n'
              '<div><br></div>\n<ol>\n<li>Second list</li>\n</ol>\n<div>Josh’s teaching line.</div>\n'
              '<div><i>Write some notes here</i><br></div>\n')
back = bf.note_to_outline(SERIALISED)
check("Notes' serialisation: title, byline date + speaker, takeaway; notice, image and prompts dropped",
      back["title"] == "Grace That Keeps Giving" and back["service"] == date(2026, 9, 13)
      and back["speaker"] == "Pastor Josh Smith" and back["takeaway"] == "Grace never stops giving.")
check("Notes' serialisation: main after a prompt, subhead inside a section, subs, quote, para",
      back["blocks"] == [("main", "1. Grace gives you peace"), ("quote", '"Grace and peace to you" -Ephesians 1:2'),
                         ("main", "2. Saved from sin"), ("subhead", "Truths About Sin"),
                         ("sub", "CLARIFICATION: not by works"), ("sub", "Growth only comes from God"),
                         ("sub", "Second list"), ("para", "Josh's teaching line.")])
# The 9/20 backup: no prompts at all, an <h3> subhead, and each label split from its verse(s) into its own <li>.
NO_PROMPTS = ('<div><b><h1>Walk in His Will</h1></b></div>\n<div><b>Pastor Josh Smith | September 20th, 2026</b><br></div>\n'
              '<div><b><h2>1. Walk in unity</h2></b></div>\n<div>&quotVerse one&quot -Ephesians 1:10</div>\n'
              '<div><b><h2>2. Walk by the Holy Spirit</h2></b></div>\n'
              '<div><u><h3>3 Truths About Walking by the Holy Spirit</h3></u><b><h3><br></h3></b></div>\n'
              '<ol>\n<li><b>The Holy Spirit was promised</b>: </li>\n<li>&quotA new heart&quot -Ezekiel 36:26-27</li>\n</ol>\n'
              '<div><br></div>\n<ol>\n<li><b>Every Christian is sealed</b>: </li>\n<li>For those who are led&quot -Romans 8:14</li>\n'
              '<li>We cry, &quotAbba, Father.&quot -Romans 8:15</li>\n</ol>\n<div><b><h2>Unnumbered, so a subhead</h2></b></div>\n')
check("no prompts (9/20): numbered <h2> = main, <h3> = subhead, a bare label folds in its verses, "
      "two verses kept apart by a visible separator",
      bf.note_to_outline(NO_PROMPTS)["blocks"] ==
      [("main", "1. Walk in unity"), ("quote", '"Verse one" -Ephesians 1:10'), ("main", "2. Walk by the Holy Spirit"),
       ("subhead", "3 Truths About Walking by the Holy Spirit"),
       ("sub", 'The Holy Spirit was promised: "A new heart" -Ezekiel 36:26-27'),
       ("sub", 'Every Christian is sealed: For those who are led" -Romans 8:14 · We cry, "Abba, Father." -Romans 8:15'),
       ("subhead", "Unnumbered, so a subhead")])
check("fails closed: no byline under the title",
      isinstance(raises(lambda: bf.note_to_outline("<div><h1>T</h1></div><div><h2>1. A</h2></div>")), ValueError))
check("fails closed: markup it has never seen (nested divs) is not skipped",
      isinstance(raises(lambda: bf.note_to_outline(SERIALISED.replace("<div>Josh’s teaching line.</div>",
                                                                       "<div><div>Josh’s teaching line.</div></div>"))),
                 ValueError))

print("backfill: the command (dry run and publish, git and network faked)")
keep_weeks, TAKEAWAY_CALLS[:] = bf.WEEKS, []
o_nov = dict(o_josh, service=date(2026, 11, 1))
s.BACKUPS.mkdir(parents=True, exist_ok=True)
(s.BACKUPS / "2026-10-31-200000.html").write_text(note_html(o_josh), encoding="utf-8")
(s.BACKUPS / "2026-11-07-200000.html").write_text(note_html(o_nov), encoding="utf-8")
bf.WEEKS = (("2026-10-31-200000.html", o_josh["title"], date(2026, 10, 25)),
            ("2026-11-07-200000.html", o_nov["title"], date(2026, 11, 1)))
dry = TMP / "backfill-dry"
dry.mkdir()
(dry / "index.json").write_text(json.dumps({"updated": "x", "weeks": [wk("2026-11-01", "live already")]}))
(dry / "2026-11-01.json").write_text("LIVE")
clear_markers()
cache_before = s.OUTLINE_CACHE.read_bytes() if s.OUTLINE_CACHE.exists() else None
try:
    check("dry run: exit 0", bf.main(["--dry-run", str(dry)]) == 0)
    doc = json.loads((dry / "2026-10-25.json").read_text())
    check("dry run: the week file is the job's contract, blocks and takeaway from the Note",
          list(doc) == ["service", "title", "speaker", "release_at", "published_at", "takeaway", "format", "version", "blocks"]
          and [(b["kind"], b["text"]) for b in doc["blocks"]] == list(o_josh["blocks"])
          and doc["takeaway"] == FAKE_TAKEAWAY and doc["speaker"] == "Pastor Josh Smith" and doc["version"] == o_josh["version"])
    check("dry run: a week already in the live index is skipped, not overwritten",
          (dry / "2026-11-01.json").read_text() == "LIVE"
          and [w["service"] for w in json.loads((dry / "index.json").read_text())["weeks"]] == ["2026-11-01", "2026-10-25"]
          and json.loads((dry / "index.json").read_text())["weeks"][0]["title"] == "live already")
    check("no weekly markers, no takeaway cache write, no model call",
          markers() == (None, None) and not TAKEAWAY_CALLS
          and (s.OUTLINE_CACHE.read_bytes() if s.OUTLINE_CACHE.exists() else None) == cache_before)
    bf.main(["--dry-run", str(dry), "--force"])
    check("--force overwrites the live week", json.loads((dry / "2026-11-01.json").read_text())["service"] == "2026-11-01")
    bf.WEEKS = (("2026-10-31-200000.html", "Some Other Title", date(2026, 10, 25)),)
    empty = TMP / "backfill-empty"
    check("a backup that is not the week the table says is refused, and nothing is written",
          isinstance(raises(lambda: bf.main(["--dry-run", str(empty)])), ValueError) and not empty.exists())

    bf.WEEKS = (("2026-10-31-200000.html", o_josh["title"], date(2026, 10, 25)),
                ("2026-11-07-200000.html", o_nov["title"], date(2026, 11, 1)))

    class Resp:
        def __init__(self, body): self.body = body
        def read(self): return self.body.encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    urls, contexts, published, live_body = [], [], [], json.dumps({"weeks": [{"service": "2026-10-25"}]})
    keep_net = (bf.urllib.request.urlopen, s.publish_web, s.load_config)

    def fake_urlopen(url, timeout=None, context=None):
        urls.append(url)
        contexts.append(context)
        if isinstance(live_body, Exception):
            raise live_body
        return Resp(live_body)

    bf.urllib.request.urlopen = fake_urlopen
    s.publish_web = lambda outline, cfg: published.append(outline["service"].isoformat()) or True
    s.load_config = lambda: {"WEB_NOTES": "1"}
    try:
        check("publish: only the weeks the live index lacks go through publish_web",
              bf.main([]) == 0 and published == ["2026-11-01"] and urls[0].startswith(s.WEB_BASE + "index.json?cb="))
        # 2026-10-23: python.org's Python has no CA bundle of its own, so a bare urlopen failed
        # CERTIFICATE_VERIFY_FAILED on every real run. The read must carry a verifying context WITH certs.
        ctx = contexts[0]
        check("the live index is read with a verifying TLS context that has CA certificates",
              isinstance(ctx, bf.ssl.SSLContext) and ctx.verify_mode == bf.ssl.CERT_REQUIRED and ctx.check_hostname
              and ctx.cert_store_stats()["x509_ca"] > 0)
        published.clear()
        check("publish --force: every week, without reading the live index",
              bf.main(["--force"]) == 0 and published == ["2026-10-25", "2026-11-01"] and len(urls) == 1)
        published.clear()
        s.load_config = lambda: {"WEB_NOTES": "0"}
        check("publish with WEB_NOTES=0: exit 1, nothing published", bf.main(["--force"]) == 1 and not published)
        live_body = "{not json"
        check("an unreadable live index refuses the publish",
              isinstance(raises(lambda: bf.main([])), RuntimeError) and not published)
        live_body = bf.urllib.error.URLError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
        e = raises(lambda: bf.main([]))
        check("a network/TLS failure reading the index refuses the publish with a clear error, not a traceback",
              isinstance(e, RuntimeError) and "live index.json" in str(e) and not published)
        check("...and still no weekly markers", markers() == (None, None))
    finally:
        bf.urllib.request.urlopen, s.publish_web, s.load_config = keep_net
finally:
    bf.WEEKS = keep_weeks

print()
if failures:
    print(f"{len(failures)} FAILED")
    sys.exit(1)
print("all passed")

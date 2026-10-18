#!/usr/bin/env python3
"""Regression tests for sermon_notes_sync.py.  Run:  python3 scripts/test_sermon_notes_sync.py

No network, no Notes, no API. Pins the 2026-09-12 incident: a chatty thread reply replaced
the real outline in the shared note, and the model's request for more content was published
as the KEY TAKEAWAY. Also pins that CORRECTIONS (which Josh sends as replies) still win."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sermon_notes_sync as s

s.log = lambda msg: None   # keep test output readable

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

print()
if failures:
    print(f"{len(failures)} FAILED")
    sys.exit(1)
print("all passed")

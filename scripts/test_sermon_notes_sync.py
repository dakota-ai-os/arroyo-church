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

print()
if failures:
    print(f"{len(failures)} FAILED")
    sys.exit(1)
print("all passed")

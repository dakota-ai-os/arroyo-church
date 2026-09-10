#!/bin/bash
# Sunday sermon-notes runner — invoked by launchd (com.arroyo.sermonnotes).
#
# Mirrors run-blog.sh. launchd hands over a bare environment, so PATH is set
# explicitly. Config (incl. the Gmail app password) lives OUTSIDE the repo at
# ~/.config/arroyo/gmail.env so it is never committed.
#
# The Apple Notes Automation grant is tied to THIS process identity, which is
# stable across runs — that is the whole point of moving off Cowork, which
# re-prompted every week.
#
# WHY THIS RUNS SEVERAL TIMES A WEEK (2026-09-09):
# The first three unattended Sunday runs all failed the same way — 8/23 hung with no
# exit code at all, 8/30 and 9/6 died on AppleEvent timeouts. Cause: Power Nap. launchd
# fires during a DARK WAKE, where the network is up (so the IMAP fetch succeeds) but
# there is no usable GUI session, so Notes can neither be scripted nor fronted. The
# script now probes for that in ~0.2s and exits EX_TEMPFAIL (75) without touching the
# note; several attempts are scheduled so one bad wake cannot lose the Sunday, and a
# written service date makes the later attempts stand down.
set -uo pipefail

REPO="/Users/dakotayates/ai-os/ventures/arroyo-church-redesign"
LOG="$HOME/Library/Logs/arroyo-sermon-notes.log"
export PATH="/Library/Frameworks/Python.framework/Versions/3.13/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

# Failures used to be silent — the note simply stayed stale and nobody knew until
# Sunday morning. Mail the operator instead, reusing the Gmail creds already present.
alert() {
  local subject="$1" body="$2"
  python3 - "$subject" "$body" <<'PY' >> "$LOG" 2>&1 || log "WARNING: alert email failed"
import os, smtplib, sys
from email.message import EmailMessage
from pathlib import Path
cfg = {}
for line in (Path.home()/".config"/"arroyo"/"gmail.env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1); cfg[k.strip()] = v.strip()
user, pw = cfg.get("GMAIL_USER"), cfg.get("GMAIL_APP_PASSWORD", "").replace(" ", " ")
if not user or not pw:
    sys.exit("alert: no creds")
m = EmailMessage()
m["From"], m["To"], m["Subject"] = user, user, sys.argv[1]
m.set_content(sys.argv[2])
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
    s.login(user, pw); s.send_message(m)
print("alert email sent")
PY
}

log "=== run start ==="
if [ ! -f "$HOME/.config/arroyo/gmail.env" ]; then
  log "ERROR: ~/.config/arroyo/gmail.env missing. Aborting."
  alert "Arroyo sermon notes FAILED" "gmail.env is missing on the Mac; the note was not updated."
  exit 1
fi

# caffeinate: the 8/23 run logged a start and then nothing at all — no traceback, no exit
# code — which is what a process being killed by the machine going back to sleep looks
# like. -i blocks idle sleep, -m keeps the disk up, -s covers AC power.
caffeinate -ims python3 "$REPO/scripts/sermon_notes_sync.py" >> "$LOG" 2>&1
code=$?
log "exit code $code"

if [ "$code" -eq 75 ]; then
  log "GUI session not usable — quiet retry, no alarm raised."
elif [ "$code" -ne 0 ]; then
  alert "Arroyo sermon notes FAILED (exit $code)" \
"The Sunday sermon-notes job failed on $(hostname).

Exit code: $code
Log:       $LOG

Last 25 log lines:
$(tail -25 "$LOG")"
fi

log "=== run end ==="
exit $code

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
set -uo pipefail

REPO="/Users/dakotayates/ai-os/ventures/arroyo-church-redesign"
LOG="$HOME/Library/Logs/arroyo-sermon-notes.log"
export PATH="/Library/Frameworks/Python.framework/Versions/3.13/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

log "=== run start ==="
if [ ! -f "$HOME/.config/arroyo/gmail.env" ]; then
  log "ERROR: ~/.config/arroyo/gmail.env missing. Aborting."
  exit 1
fi

python3 "$REPO/scripts/sermon_notes_sync.py" >> "$LOG" 2>&1
code=$?
log "exit code $code"
log "=== run end ==="
exit $code

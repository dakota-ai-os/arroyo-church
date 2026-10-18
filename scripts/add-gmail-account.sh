#!/bin/bash
# Add (or replace) a mailbox the sermon-notes job reads, e.g. dakota@arroyochurch.com.
#
#   bash scripts/add-gmail-account.sh dakota@arroyochurch.com
#
# You need a Google APP PASSWORD for that account (not its login password):
# sign in as that account at https://myaccount.google.com/apppasswords (2-Step Verification
# must be on), create one named "Arroyo sermon notes", and paste it at the hidden prompt.
#
# The password is read with `read -s` (never echoed, never on a command line), the IMAP login
# and mailbox are tested BEFORE anything is saved, and ~/.config/arroyo/gmail.env stays chmod 600.
# It writes GMAIL_USER_n / GMAIL_APP_PASSWORD_n / GMAIL_MAILBOX_n, reusing n if the address is
# already there. Mailbox defaults to "[Gmail]/All Mail" so read or archived mail still counts;
# override with MAILBOX=INBOX bash scripts/add-gmail-account.sh ...
set -euo pipefail

ADDR="${1:-}"
[ -n "$ADDR" ] || { echo "usage: bash $0 you@arroyochurch.com"; exit 1; }
ENV_FILE="$HOME/.config/arroyo/gmail.env"
[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE (the primary av@ setup must exist first)"; exit 1; }
MAILBOX="${MAILBOX:-[Gmail]/All Mail}"

printf 'App password for %s (typing is hidden): ' "$ADDR"
read -rs PW
echo
[ -n "$PW" ] || { echo "nothing entered -- no changes made"; exit 1; }

PY=$(cat <<'PYEOF'
import imaplib, os, re, sys
from pathlib import Path
addr, mailbox, env_path = sys.argv[1], sys.argv[2], Path(sys.argv[3])
pw = re.sub(r"[^A-Za-z0-9]", "", sys.stdin.read())
try:
    M = imaplib.IMAP4_SSL("imap.gmail.com")
    M.login(addr, pw)
    typ, _ = M.select(f"\"{mailbox}\"", readonly=True)
    M.logout()
    if typ != "OK":
        sys.exit(f"Logged in, but could not open mailbox {mailbox!r} -- no changes made.")
except imaplib.IMAP4.error as e:
    sys.exit(f"Gmail refused the login for {addr}: {e}\n"
             "Check the app password, that 2-Step Verification is on, and that IMAP is enabled "
             "(Gmail settings > Forwarding and POP/IMAP). No changes made.")
lines = env_path.read_text().splitlines()
users = {}
for l in lines:
    m = re.match(r"\s*GMAIL_USER_(\d+)\s*=\s*(.*)", l)
    if m:
        users[int(m.group(1))] = m.group(2).strip().strip("\"'").lower()
n = next((k for k, v in users.items() if v == addr.lower()), max(users, default=1) + 1)
keys = (f"GMAIL_USER_{n}", f"GMAIL_APP_PASSWORD_{n}", f"GMAIL_MAILBOX_{n}")
kept = [l for l in lines if not re.match(rf"\s*({'|'.join(keys)})\s*=", l)]
kept += [f"{keys[0]}={addr}", f"{keys[1]}={pw}", f"{keys[2]}={mailbox}"]
old = os.umask(0o077)
env_path.write_text("\n".join(kept) + "\n")
os.umask(old)
env_path.chmod(0o600)
print(f"Login OK. Saved {addr} as mailbox #{n} ({mailbox}). The sermon-notes job reads it from the next run.")
PYEOF
)
printf '%s' "$PW" | python3 -c "$PY" "$ADDR" "$MAILBOX" "$ENV_FILE"
unset PW

# Church-computer helper for Arroyo sermon thumbnails — read me

Two jobs here: **(1)** upscale a screenshot of Pastor Josh, and **(2)** help Dakota
decide the thumbnail text, the YouTube video title, and the description.
Full guides: `HOW-TO-UPSCALE.md` (upscaling) and `../COPY-PROMPT.md` (the text).

## 1) Upscale a screenshot

When Dakota asks you to upscale a screenshot:
1. Make sure setup is done: `pip install pillow requests`, and a `.env` file *in this
   folder* with a real `KIE_API_KEY`. If the key is missing, **ask Dakota for it** and
   write it into `.env` — never invent or guess a key.
2. Run: `python3 upscale.py <screenshot-path>` → saves `<name>_upscaled.png`
   next to it (~30 seconds, ~$0.04).
3. Report the saved path back to him.

**Do NOT** crop, reframe, or cut out the pastor — keep the whole screenshot; Dakota
composes it in Canva (template: **"⚙️ Thumbnail Template — Transformational Stories"**).

## 2) Decide the text (thumbnail vs. video title vs. description)

They do **different jobs**, so they get **different text** — don't reuse the same words.
Full prompt + a worked example are in `../COPY-PROMPT.md`. The rules:

- **Thumbnail** = a short **benefit HOOK** — 2–4 words, ALL CAPS, one accent word. NOT the
  full sermon title. (e.g. `FORGIVE ANYWAY`, not "Forgiving Despite Your Feelings".)
- **YouTube title field** = a fuller, **searchable** line (~55–70 chars) including the
  scripture passage + "Arroyo Church". Different wording from the thumbnail.
- **Description (first line)** = one keyword-rich sentence naming the passage and the
  felt-need promise.

When Dakota gives you the sermon title + scripture (+ a one-line gist if he has it),
offer **3 hook options, 3 YouTube-title options, and a description first line** — warm and
clear, never clickbait, never sensationalizing scripture.

# Church-computer screenshot upscaler — read me

This folder turns a low-res livestream screenshot of Pastor Josh into a high-res,
sharp image for the Arroyo YouTube thumbnail. Full guide: `HOW-TO-UPSCALE.md`.

**When Dakota asks you to upscale a screenshot:**
1. Make sure setup is done: `pip install pillow requests`, and a `.env` file *in this
   folder* with a real `KIE_API_KEY`. If the key is missing, **ask Dakota for it** and
   write it into `.env` — never invent or guess a key.
2. Run: `python3 upscale.py <screenshot-path>` → saves `<name>_upscaled.png`
   next to it (~30 seconds, ~$0.04).
3. Report the saved path back to him.

**Do NOT** crop, reframe, or cut out the pastor — keep the whole screenshot; Dakota
composes it in Canva (template: **"⚙️ Thumbnail Template — Transformational Stories"**).

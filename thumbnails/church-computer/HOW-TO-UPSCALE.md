# Upscaling a sermon screenshot (church computer)

**Goal:** turn a low-res screenshot of Pastor Josh from the livestream into a
high-resolution, sharp image to use in the Canva thumbnail template.

This folder is self-contained — it does **not** need Dakota's `ai-os` repo. It
only needs Python, two pip packages, and the kie.ai API key.

---

## One-time setup

1. **Python 3** is installed (check: `python3 --version`).
2. Install the two dependencies:
   ```bash
   pip install pillow requests
   ```
3. **Add the kie.ai API key.** Copy `.env.example` to `.env` in this folder and
   paste the key after `KIE_API_KEY=`. (Ask Dakota for the key, or get one at
   https://kie.ai/api-key.) The `.env` file stays on this computer — never commit it.

---

## Each week (the actual job)

1. **Grab a screenshot** of Josh preaching from the stream — a clear, front-facing
   moment where he isn't moving (the upscaler sharpens what's there; it can't fix motion
   blur). Use the livestream itself, not a phone/Instagram/Shorts screenshot — the script
   does not remove captions, mute icons or app buttons. Save it as a PNG (or JPG)
   anywhere on this computer.
2. **Upscale it:**
   ```bash
   cd path/to/thumbnails/church-computer
   python3 upscale.py /path/to/screenshot.png
   ```
   It prints progress and, after ~70 seconds, saves
   `screenshot_upscaled.png` next to the original (2× size, lightly sharpened, full
   frame, real background kept). Costs ~$0.05. For a very small screenshot add
   `--factor 4`.
3. **Use it in Canva:** upload `screenshot_upscaled.png` to Canva, drop it onto the
   **"⚙️ Thumbnail Template — Transformational Stories"** design, position the pastor,
   change the hook text, export 1280×720, and set it as the YouTube thumbnail.

---

## If you are Claude Code on this computer

When Dakota gives you a sermon screenshot and asks to upscale it:

1. Make sure setup is done: `pillow` + `requests` installed, and `.env` (in this
   folder) has a real `KIE_API_KEY`. If the key is missing, **ask Dakota for it** and
   write it into `.env` — do not guess or invent one.
2. Run: `python3 <this-folder>/upscale.py <the screenshot path>`
3. Report the saved `..._upscaled.png` path back to him. If it errors, show him the
   message (usually a missing key or no network).
4. If a Canva connector is available to you here, you may also upload the result to
   his Canva folder **"Arroyo — Pastor Photos (high-res)"** and confirm it landed. Import
   it by URL (`upload-asset-from-url`, then `move-item-to-folder`); files sent through the
   direct-upload tool (`create-upload-url`) could not be moved into that folder on
   2026-10-01. If there's no connector, just hand him the file to upload manually.

**Never** swap in an AI "enhance" model or retouch his face. Generative upscalers
redraw Josh's face (open his eyes, restyle his hair, smooth his skin), and he stops
looking like himself. That's why this uses Topaz.

**Do not** crop, cut out, or reframe the pastor — the script keeps the whole
screenshot on purpose (Dakota composes it in Canva).

---

## What it does under the hood

`upscale.py` → hosts the screenshot on kie's temp store → runs kie.ai **Topaz Image
Upscale** (`topaz/image-upscale`: true super-resolution that sharpens the existing
pixels instead of redrawing them, so Josh still looks like Josh) → downloads the result
→ applies a light sharpening pass → saves a **lossless PNG** (Canva re-compresses JPEGs
and softens them, so PNG matters). No cutout, no background swap — that's all done in
Canva.

Until 2026-10-01 this used Nano Banana 2, a generative image editor. In a side-by-side
check against the original frames it changed his eyes, hair and skin every time.

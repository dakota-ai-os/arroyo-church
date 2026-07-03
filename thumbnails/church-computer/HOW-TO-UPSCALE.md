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
   moment. Save it as a PNG (or JPG) anywhere on this computer.
2. **Upscale it:**
   ```bash
   cd path/to/thumbnails/church-computer
   python3 upscale.py /path/to/screenshot.png
   ```
   It prints progress and, after ~30 seconds, saves
   `screenshot_upscaled.png` next to the original (high-res, sharpened, full frame,
   real background kept). Costs ~$0.04.
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
   his Canva and confirm it landed. If not, just hand him the file to upload manually.

**Do not** crop, cut out, or reframe the pastor — the script keeps the whole
screenshot on purpose (Dakota composes it in Canva).

---

## What it does under the hood

`upscale.py` → hosts the screenshot on kie's temp store → runs kie.ai **Nano Banana 2**
(image enhance/upscale, keeping the full frame) → downloads the result → applies a
sharpening pass → saves a **lossless PNG** (Canva re-compresses JPEGs and softens them,
so PNG matters). No cutout, no background swap — that's all done in Canva.

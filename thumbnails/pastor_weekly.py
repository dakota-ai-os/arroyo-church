#!/usr/bin/env python3
"""Weekly pastor prep for the Transformational Stories thumbnail.

Picks the NEXT screenshot from pastor-library/ (rotation), upscales + sharpens it,
and hosts it as a LOSSLESS PNG (so Canva doesn't soften it on upload), printing the
URL for the scheduled task to upload into Canva:
  FULL - upscaled/enhanced + sharpened, with the real stage background (no cutout)

(The series GREEN background is a static asset already in Canva; it doesn't change
week to week, so it's not regenerated here.)

Run:  python3 thumbnails/pastor_weekly.py
The scheduled task reads the printed *_URL line, uploads it to Canva, and moves it
into the "Arroyo — Pastor Photos (high-res)" folder.
Add more screenshots any time by dropping PNGs into pastor-library/.
"""
import sys, os, json, glob, subprocess
from datetime import date
sys.path.insert(0, "/Users/dakotayates/ai-os/tools/media-gen")
from PIL import Image, ImageFilter
from kie_client import KieClient

HERE  = os.path.dirname(os.path.abspath(__file__))
LIB   = os.path.join(HERE, "pastor-library")
OUT   = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
STATE = os.path.join(HERE, "rotation.json")

shots = sorted(f for f in glob.glob(os.path.join(LIB, "*.png"))
               if not os.path.basename(f).startswith("._"))
if not shots:
    sys.exit("[error] no screenshots in pastor-library/ — drop some PNGs in there.")

state = json.load(open(STATE)) if os.path.exists(STATE) else {}
idx = state.get("next", 0) % len(shots)
src = shots[idx]

c = KieClient()

# Upscale/enhance via Nano Banana, keep his real background
PROMPT = (
    "Enhance and upscale this photo of the man to a high-resolution, crisp, clean image for a YouTube "
    "thumbnail. Reframe to waist-up, prominent and centered. Keep his EXACT face, hair, beard, clothing, "
    "pose and microphone, and keep his real church-stage background. Improve sharpness, clarity, lighting "
    "and detail; reduce noise and motion blur. Photorealistic and natural - do NOT change his identity or "
    "add anything. No text, no checkerboard."
)
raw_url = c.generate_image(PROMPT, model="nano-banana-2", aspect_ratio="16:9",
                           resolution="2K", image_paths=[src])[0]

# Download, sharpen (counters AI softness), and save LOSSLESS so Canva keeps it crisp
raw_path = os.path.join(OUT, "pastor_raw.png")
subprocess.run(["curl", "-s", "-o", raw_path, raw_url], check=True)
sharp = Image.open(raw_path).convert("RGB").filter(
    ImageFilter.UnsharpMask(radius=3, percent=170, threshold=2))

# FULL (sharpened PNG) — no cutout; you compose from full photos in Canva
full_path = os.path.join(OUT, "pastor_full.png")
sharp.save(full_path)
full_url = c.upload_file(full_path)

# advance rotation
json.dump({"next": (idx + 1) % len(shots), "last_used": os.path.basename(src)},
          open(STATE, "w"), indent=2)

today = date.today().isoformat()
print("USED_SCREENSHOT:", os.path.basename(src))
print("FULL_NAME:", f"Pastor {today}")
print("FULL_URL:", full_url)

#!/usr/bin/env python3
"""Weekly pastor prep for the Transformational Stories thumbnail.

Picks the NEXT screenshot from pastor-library/ (rotation), then produces three
versions and hosts each, printing their URLs for the scheduled task to upload
into Canva:
  1. FULL      - upscaled/enhanced, with the real stage background
  2. CUTOUT    - transparent background (rembg)
  3. FEATHERED - left/right edges faded to transparent (blend-ready)

Run:  python3 thumbnails/pastor_weekly.py
The scheduled task reads the printed *_URL lines and uploads them to Canva.
Add more screenshots any time by dropping PNGs into pastor-library/.
"""
import sys, os, json, glob, subprocess
sys.path.insert(0, "/Users/dakotayates/ai-os/tools/media-gen")
import numpy as np
from PIL import Image
from rembg import remove
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

# 1) FULL — upscale/enhance, keep his real background
PROMPT = (
    "Enhance and upscale this photo of the man to a high-resolution, crisp, clean image for a YouTube "
    "thumbnail. Reframe to waist-up, prominent and centered. Keep his EXACT face, hair, beard, clothing, "
    "pose and microphone, and keep his real church-stage background. Improve sharpness, clarity, lighting "
    "and detail; reduce noise and motion blur. Photorealistic and natural - do NOT change his identity or "
    "add anything. No text, no checkerboard."
)
full_url = c.generate_image(PROMPT, model="nano-banana-2", aspect_ratio="16:9",
                            resolution="2K", image_paths=[src])[0]

full_path = os.path.join(OUT, "pastor_full.png")
subprocess.run(["curl", "-s", "-o", full_path, full_url], check=True)
img = Image.open(full_path).convert("RGBA")

# 2) CUTOUT — transparent background
cut_path = os.path.join(OUT, "pastor_cutout.png")
remove(img).save(cut_path)
cutout_url = c.upload_file(cut_path)

# 3) FEATHERED — left/right edges fade to transparent
W, H = img.size
xn = np.mgrid[0:H, 0:W][1] / W
fw = 0.13
alpha = (np.minimum(np.clip(xn / fw, 0, 1), np.clip((1 - xn) / fw, 0, 1)) * 255).astype("uint8")
arr = np.array(img); arr[..., 3] = alpha
feath_path = os.path.join(OUT, "pastor_feathered.png")
Image.fromarray(arr, "RGBA").save(feath_path)
feathered_url = c.upload_file(feath_path)

# advance rotation
json.dump({"next": (idx + 1) % len(shots), "last_used": os.path.basename(src)},
          open(STATE, "w"), indent=2)

print("USED_SCREENSHOT:", os.path.basename(src))
print("FULL_URL:", full_url)
print("CUTOUT_URL:", cutout_url)
print("FEATHERED_URL:", feathered_url)

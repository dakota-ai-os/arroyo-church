#!/usr/bin/env python3
"""Upscale + sharpen a sermon screenshot for the Arroyo thumbnail.

Self-contained: talks to kie.ai's Topaz Image Upscale model directly (no ai-os repo
needed). Keeps the whole frame + real background — just makes it high-resolution
and crisp.

Why Topaz (since 2026-10-01): it's true super-resolution, so it sharpens the pixels
that are already there. The old model (Nano Banana 2) re-drew Josh's face — opened
his eyes, restyled his hair, smoothed his skin — and he stopped looking like himself.
Topaz can't invent detail, so a motion-blurred frame stays a little soft: pick a
sharp, front-facing moment.

It does NOT remove captions, play/mute icons or app buttons from phone or social
screenshots — use a clean livestream frame, or hand those to Claude on Dakota's Mac.

  python3 upscale.py <screenshot.png> [output.png] [--factor 2|4]

Setup (once):
  pip install pillow requests
  Put your key in a `.env` file next to this script:  KIE_API_KEY=sk-...
  (or export KIE_API_KEY=...). Get a key at https://kie.ai/api-key

Output: a high-res, lightly sharpened PNG (default: <screenshot>_upscaled.png).
Then upload it to Canva and drop it on the thumbnail template.
"""
import sys, os, time, json, base64, pathlib
import requests
from PIL import Image, ImageFilter

BASE = "https://api.kie.ai"
UPLOAD_HOSTS = ["https://kieai.redpandaai.co/api/file-base64-upload",
                "https://api.kie.ai/api/file-base64-upload"]
MODEL = "topaz/image-upscale"
MAX_INPUT = 10 * 1024 * 1024          # Topaz rejects inputs over 10 MB
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def load_key():
    key = os.environ.get("KIE_API_KEY")
    if not key:
        envf = pathlib.Path(__file__).resolve().parent / ".env"
        if envf.exists():
            for line in envf.read_text().splitlines():
                if line.strip().startswith("KIE_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        sys.exit("KIE_API_KEY not set. Put `KIE_API_KEY=...` in a .env file next to this "
                 "script (or export it). Get a key at https://kie.ai/api-key")
    return key


def main():
    args, factor = sys.argv[1:], "2"
    if "--factor" in args:
        i = args.index("--factor")
        factor = args[i + 1] if i + 1 < len(args) else ""
        del args[i:i + 2]
    if factor not in ("1", "2", "4"):
        sys.exit("--factor must be 1, 2 or 4")
    if not args:
        sys.exit("usage: python3 upscale.py <screenshot.png> [output.png] [--factor 2|4]")
    src = args[0]
    if not os.path.exists(src):
        sys.exit(f"not found: {src}")
    if os.path.getsize(src) > MAX_INPUT:
        sys.exit("screenshot is over 10 MB — save it as a JPG (or a smaller PNG) and try again")
    out = args[1] if len(args) > 1 else os.path.splitext(src)[0] + "_upscaled.png"
    s = requests.Session(); s.headers.update({"Authorization": f"Bearer {load_key()}"})

    # 1) host the screenshot (kie's models need a URL, not a local file).
    #    Bigger uploads sometimes drop with an SSL error, so each host gets a few tries.
    mime = MIME.get(os.path.splitext(src)[1].lower(), "image/png")
    b64 = base64.b64encode(pathlib.Path(src).read_bytes()).decode()
    payload = {"base64Data": f"data:{mime};base64,{b64}", "uploadPath": "images",
               "fileName": os.path.basename(src)}
    url = None
    for attempt in range(3):
        for host in UPLOAD_HOSTS:
            try:
                r = s.post(host, json=payload, timeout=180).json()
                u = (r.get("data") or {}).get("downloadUrl")
                if u and (r.get("success") or r.get("code") == 200):
                    url = u; break
            except Exception:
                continue
        if url:
            break
        time.sleep(3)
    if not url:
        sys.exit("upload to kie failed (check network / API key)")
    print("· uploaded screenshot", flush=True)

    # 2) create the upscale job
    body = {"model": MODEL, "input": {"image_url": url, "upscale_factor": factor}}
    r = s.post(BASE + "/api/v1/jobs/createTask", json=body, timeout=30).json()
    if r.get("code") != 200:
        sys.exit(f"createTask failed: {r.get('msg')}")
    task = (r.get("data") or {}).get("taskId")
    if not task:
        sys.exit("createTask returned no taskId")
    print(f"· job {task} running…", flush=True)

    # 3) poll to completion (~70s)
    result_url, deadline, wait = None, time.time() + 420, 3.0
    while time.time() < deadline:
        r = s.get(BASE + "/api/v1/jobs/recordInfo", params={"taskId": task}, timeout=30).json()
        if r.get("code") == 200:
            d = r.get("data") or {}
            state = str(d.get("state") or "").lower()
            if state == "success":
                parsed = json.loads(d.get("resultJson") or "{}")
                urls = parsed.get("resultUrls") or []
                if urls:
                    result_url = urls[0]; break
                sys.exit("job succeeded but returned no image URL")
            if state == "fail":
                sys.exit(f"job failed: {d.get('failMsg') or d.get('failCode')}")
        time.sleep(wait); wait = min(wait * 1.5, 15)
    if not result_url:
        sys.exit("timed out waiting for the upscale")

    # 4) download, sharpen LIGHTLY (Dakota found 160% showed skin texture), save LOSSLESS
    #    (Canva softens JPEGs, so keep PNG)
    tmp = out + ".raw"
    with s.get(result_url, stream=True, timeout=120) as g:
        g.raise_for_status()
        with open(tmp, "wb") as fh:
            for ch in g.iter_content(1 << 16):
                fh.write(ch)
    img = Image.open(tmp).convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.6, percent=50, threshold=2))
    img.save(out)
    os.remove(tmp)
    print(f"✓ saved {out}  ({img.width}×{img.height})")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Arroyo Church - sermon thumbnail generator.

One screenshot of Josh + a short hook -> a finished 1280x720 YouTube thumbnail PNG,
on a locked per-series template.

Two stages:
  1) RELIGHT  - kie.ai / Nano Banana 2 lifts Josh off the raw stage frame and drops
                him onto a brand background (per-series "mood"), keeping his likeness.
  2) COMPOSE  - Pillow overlays the brand type (Impact display + Avenir UI), the
                scripture ref, and the white Arroyo logo. Pixel-identical every week.

Per-series look (eyebrow text, accent color, lighting mood) lives in series.json.

Examples
--------
  # full run from a screenshot (costs ~$0.04 for the relight)
  python3 make_thumb.py --src frames/2026-06-29.png --series transformational-stories \
      --l1 FORGIVE --l2 ANYWAY --ref "MATTHEW 18:21-22" \
      --out out/2026-06-29-forgive-anyway.png

  # re-run the overlay only, reusing an already-rendered scene (free, instant)
  python3 make_thumb.py --scene out/scene_12345678.jpg --series transformational-stories \
      --l1 FORGIVE --l2 ANYWAY --ref "MATTHEW 18:21-22" --out out/test.png
"""
import sys, os, json, argparse, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE  = os.path.dirname(os.path.abspath(__file__))
MEDIA = "/Users/dakotayates/ai-os/tools/media-gen"   # kie_client lives here
sys.path.insert(0, MEDIA)

W, H = 1280, 720
FONT = {"display": "/System/Library/Fonts/Supplemental/Impact.ttf",
        "ui":      "/System/Library/Fonts/Avenir Next.ttc"}
WHITE = (255, 255, 255); FOAM = (191, 231, 238); TEAL = (95, 194, 212)


def load_series(key):
    cfg = json.load(open(os.path.join(HERE, "series.json")))
    if key not in cfg:
        sys.exit(f"[error] series '{key}' not in series.json. Known: {', '.join(cfg)}")
    return cfg[key]


def relight(src, mood):
    """Send the raw frame to Nano Banana 2; return a local path to the brand scene."""
    if not src or not os.path.exists(src):
        sys.exit(f"[error] --src screenshot not found: {src}")
    from kie_client import KieClient
    prompt = (
        "Using this photo of the man, create a cinematic professional church-sermon thumbnail scene. "
        "Keep his EXACT face, beard, hairstyle, clothing, pose and the microphone exactly as in the "
        "original - do NOT change his identity, features, or proportions. Position him on the RIGHT "
        f"third of a wide 16:9 frame, waist-up prominent. Replace the entire background with {mood}. "
        "Keep the LEFT side darker and emptier as negative space for text. Photorealistic, crisp, high "
        "resolution. Absolutely NO text, NO logos, NO checkerboard, NO transparency - a fully solid "
        "filled background."
    )
    urls = KieClient().generate_image(
        prompt, model="nano-banana-2", image_paths=[src],
        aspect_ratio="16:9", resolution="2K", download_to=os.path.join(HERE, "out"))
    scene = urls[0]
    if str(scene).startswith("http"):          # some responses return a URL, not a local file
        dst = os.path.join(HERE, "out", "scene_%d.jpg" % (abs(hash(scene)) % 10**8))
        subprocess.run(["curl", "-s", "-o", dst, scene], check=True)
        scene = dst
    return scene


def _font(kind, size):
    return ImageFont.truetype(FONT[kind], size)


def _spaced(draw, xy, text, fnt, fill, track):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + track


def _bezier(p0, p1, p2, p3, n=160):
    out = []
    for i in range(n + 1):
        u = i / n; a = 1 - u
        out.append((a**3*p0[0] + 3*a*a*u*p1[0] + 3*a*u*u*p2[0] + u**3*p3[0],
                    a**3*p0[1] + 3*a*a*u*p1[1] + 3*a*u*u*p2[1] + u**3*p3[1]))
    return out


def compose(scene, out, eyebrow, accent, l1, l2, ref, logo):
    bg = Image.open(scene).convert("RGB")
    r = max(W / bg.width, H / bg.height)
    bg = bg.resize((round(bg.width * r), round(bg.height * r)), Image.LANCZOS)
    lx = (bg.width - W) // 2; ly = (bg.height - H) // 2
    img = bg.crop((lx, ly, lx + W, ly + H)).convert("RGBA")

    # left scrim for text legibility (reused on every series)
    xs = np.mgrid[0:H, 0:W][1]
    sc = np.zeros((H, W, 4)); sc[..., 3] = np.clip(1 - xs / 560, 0, 1) ** 1.5 * 150
    img = Image.alpha_composite(img, Image.fromarray(sc.astype("uint8"), "RGBA"))

    # faint river-line (brand tie)
    gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(gl).line(_bezier((-40, 690), (300, 520), (560, 470), (900, 250)),
                            fill=TEAL + (70,), width=8, joint="curve")
    img = Image.alpha_composite(img, gl.filter(ImageFilter.GaussianBlur(6)))

    d = ImageDraw.Draw(img); accent = tuple(accent)
    d.rectangle([46, 90, 90, 93], fill=accent)
    _spaced(d, (102, 80), eyebrow, _font("ui", 21), accent, 5)
    for t, yy, col in [(l1, 214, WHITE), (l2, 350, accent)]:
        d.text((49, yy + 4), t, font=_font("display", 140), fill=(0, 0, 0))   # drop shadow
        d.text((46, yy),     t, font=_font("display", 140), fill=col)
    if ref:
        _spaced(d, (50, 500), ref, _font("ui", 23), FOAM, 3)
    if logo and os.path.exists(logo):
        lg = Image.open(logo).convert("RGBA"); lh = 58
        lg = lg.resize((round(lg.width * lh / lg.height), lh), Image.LANCZOS)
        img.alpha_composite(lg, (48, 648))

    img.convert("RGB").save(out)
    return out


def main():
    ap = argparse.ArgumentParser(description="Arroyo sermon thumbnail generator")
    ap.add_argument("--src", help="raw screenshot of Josh (e.g. frames/2026-06-29.png)")
    ap.add_argument("--series", default="transformational-stories", help="key in series.json")
    ap.add_argument("--l1", required=True, help="thumbnail hook, line 1 (white)")
    ap.add_argument("--l2", required=True, help="thumbnail hook, line 2 (accent color)")
    ap.add_argument("--ref", default="", help="scripture ref, e.g. 'MATTHEW 18:21-22'")
    ap.add_argument("--out", required=True, help="output PNG path (e.g. out/2026-06-29-forgive.png)")
    ap.add_argument("--logo", default=os.path.join(HERE, "assets", "logo-white.png"))
    ap.add_argument("--scene", default="", help="reuse a pre-rendered scene; skips the paid relight")
    a = ap.parse_args()

    s = load_series(a.series)
    scene = a.scene if a.scene else relight(a.src, s["mood"])
    out = compose(scene, a.out, s["eyebrow"], s["accent"], a.l1, a.l2, a.ref, a.logo)
    print("[ok]", out)


if __name__ == "__main__":
    main()

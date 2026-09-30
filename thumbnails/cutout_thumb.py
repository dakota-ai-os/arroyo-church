#!/usr/bin/env python3
"""Code-rendered sermon thumbnail: text layered BEHIND a cutout of the pastor.

The house style since 2026-09-13 (see the thumbnail-pipeline memory): a real stage frame, no AI
relight; the stage wood wall, softened, as the backdrop; a rembg cutout of the pastor placed large on
the right with his head near the top; a two-line Impact hook on the left (white / gold) that tucks
slightly behind him; a gold eyebrow with series + passage; the white logo bottom-left.

    python3 cutout_thumb.py --src frame.png --l1 "STUCK?" --l2 "GOD CAN" \
        --eyebrow "GRACE FOR YOU · EPHESIANS 1:15-23" --out out/josh_2026-09-27/thumb.png

Tuning knobs: --head-w (pastor's head width in px), --face-x (where his face centre lands),
--head-top (px from the top edge to the top of his head), --wall (x0,y0,x1,y1 of clean wall in the
source frame to build the backdrop from; defaults to the band left of the pastor).
"""
import argparse, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1280, 720
IMPACT = "/System/Library/Fonts/Supplemental/Impact.ttf"
AVENIR = "/System/Library/Fonts/Avenir Next.ttc"
WHITE, GOLD = (255, 255, 255), (227, 189, 106)


def cutout(src):
    """rembg isnet mask, cleaned: keep the largest blob + a 6px edge so stray alpha can't show through letters."""
    from rembg import remove, new_session
    import cv2
    rgba = remove(src, session=new_session("isnet-general-use"))
    a = np.array(rgba.split()[-1])
    solid = (a > 40).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(solid)
    keep = (lab == (1 + np.argmax(st[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    keep = cv2.dilate(keep, np.ones((13, 13), np.uint8))          # ~6px edge around the main blob
    a = (a * keep).astype(np.uint8)
    rgba.putalpha(Image.fromarray(a))
    return rgba, a


def head_box(alpha):
    """Top of the person and the width of the head, measured ~0.6 head-heights below the crown."""
    rows = np.where(alpha.max(axis=1) > 128)[0]
    top = int(rows[0])
    probe = []
    for y in range(top + 10, min(top + 260, alpha.shape[0])):
        xs = np.where(alpha[y] > 128)[0]
        if len(xs): probe.append((y, xs[0], xs[-1]))
    # the head is the narrow run before the shoulders widen; take the median width of the first ~120px
    widths = [x1 - x0 for _, x0, x1 in probe[:120]]
    hw = int(np.median(widths))
    y, x0, x1 = probe[min(60, len(probe) - 1)]
    return top, hw, (x0 + x1) / 2


def tame_red(img, k):
    """Stage lights push bright skin (forehead) pink. Pull the red channel back toward g/b, but only in
    the brighter, redder pixels, so shadows, lips and the sweater keep their colour."""
    if k <= 0: return img
    arr = np.array(img.convert("RGB")).astype(np.float32)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    excess = np.clip(r - (g + b) / 2 - 18, 0, None)
    w = k * np.clip((lum - 0.35) / 0.3, 0, 1)
    arr[..., 0] = r - w * excess
    arr[..., 2] = b + w * excess * 0.05
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def soften_skin(img, amount=0.7, sharpen=45):
    """The 'balanced' treatment Dakota approved: gentle bilateral smoothing, light sharpen (not 170%)."""
    import cv2
    arr = np.array(img.convert("RGB"))
    smooth = cv2.bilateralFilter(arr, 7, 40, 7)
    out = Image.fromarray((arr * (1 - amount) + smooth * amount).astype(np.uint8))
    return out.filter(ImageFilter.UnsharpMask(radius=1.6, percent=sharpen, threshold=2))


def spaced(draw, xy, text, font, fill, track):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + track
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--l1", required=True); ap.add_argument("--l2", required=True)
    ap.add_argument("--eyebrow", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--head-w", type=int, default=200)
    ap.add_argument("--face-x", type=int, default=950)
    ap.add_argument("--head-top", type=int, default=34)
    ap.add_argument("--wall", default="")
    ap.add_argument("--wall-src", default="", help="image to cut the backdrop wall from (default: --src)")
    ap.add_argument("--mirror", action="store_true", help="widen the wall crop with its own mirror image")
    ap.add_argument("--wall-bright", type=float, default=0.8)
    ap.add_argument("--tame-red", type=float, default=0.0, help="0..1, calm pink stage-light highlights on skin")
    ap.add_argument("--smooth", type=float, default=0.7, help="0..1 skin smoothing blend; keep low on real video frames")
    ap.add_argument("--sharpen", type=int, default=45, help="UnsharpMask percent")
    ap.add_argument("--overlap", type=int, default=22, help="px the text may run behind the pastor")
    a = ap.parse_args()

    src = Image.open(a.src).convert("RGB")
    person, alpha = cutout(src)
    top, hw, cx = head_box(alpha)
    s = a.head_w / hw
    print(f"crown y={top}  head width={hw}px  face x={cx:.0f}  scale={s:.2f}")

    # --- backdrop: the real stage wall, softened like depth of field ---
    if a.wall:
        wx0, wy0, wx1, wy1 = map(int, a.wall.split(","))
    else:
        xs = np.where(alpha.max(axis=0) > 128)[0]
        wx0, wy0, wx1, wy1 = 0, 0, max(200, int(xs[0]) - 20), int(src.height * 0.5)
    wsrc = Image.open(a.wall_src).convert("RGB") if a.wall_src else src
    wall = wsrc.crop((wx0, wy0, wx1, wy1))
    if a.mirror:
        wide = Image.new("RGB", (wall.width * 2, wall.height))
        wide.paste(wall, (0, 0)); wide.paste(wall.transpose(Image.FLIP_LEFT_RIGHT), (wall.width, 0))
        wall = wide
    k = max(W / wall.width, H / wall.height)
    wall = wall.resize((int(wall.width * k) + 1, int(wall.height * k) + 1), Image.LANCZOS)
    plate = wall.crop((0, 0, W, H)).filter(ImageFilter.GaussianBlur(5))
    plate = ImageEnhance.Brightness(plate).enhance(a.wall_bright)

    # left scrim so the type reads
    scrim = Image.new("L", (W, H))
    sd = ImageDraw.Draw(scrim)
    for x in range(W):
        sd.line([(x, 0), (x, H)], fill=int(150 * max(0.0, 1 - x / 760) ** 1.3))
    plate = Image.composite(Image.new("RGB", (W, H), (8, 6, 4)), plate, scrim)

    # --- pastor layer, scaled and placed ---
    pw, ph = int(src.width * s), int(src.height * s)
    pl = person.resize((pw, ph), Image.LANCZOS)
    rgb = soften_skin(tame_red(pl.convert("RGB"), a.tame_red), a.smooth, a.sharpen)
    rgb.putalpha(pl.split()[-1])
    ox = int(a.face_x - cx * s)
    oy = int(a.head_top - top * s)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.paste(rgb, (ox, oy), rgb)                                    # paste clips off-canvas parts
    mask = np.array(layer.split()[-1])

    # --- type: as big as fits before running more than `overlap` px behind him ---
    d = ImageDraw.Draw(plate)
    x0 = 44
    def left_edge(y0, y1):
        cols = np.where(mask[max(0, y0):min(H, y1)].max(axis=0) > 128)[0]
        return int(cols[0]) if len(cols) else W
    size = 330
    while size > 90:
        f = ImageFont.truetype(IMPACT, size)
        b1, b2 = d.textbbox((0, 0), a.l1, font=f), d.textbbox((0, 0), a.l2, font=f)
        lh = int(size * 0.94)
        y1 = 108
        y2 = y1 + lh
        fits = (x0 + b1[2] <= left_edge(y1, y1 + lh) + a.overlap and
                x0 + b2[2] <= left_edge(y2, y2 + lh) + a.overlap and y2 + b2[3] < H - 96)
        if fits: break
        size -= 4
    print(f"Impact {size}pt  line1 {b1[2]}px  line2 {b2[2]}px")
    for text, yy, col in ((a.l1, y1, WHITE), (a.l2, y2, GOLD)):
        d.text((x0 + 6, yy + 7), text, font=f, fill=(0, 0, 0))     # hard drop shadow, as on 9/20
        d.text((x0, yy), text, font=f, fill=col)

    if a.eyebrow:
        ef = ImageFont.truetype(AVENIR, 22, index=2)                   # Avenir Next Demi Bold
        d.line([(x0, 64), (x0 + 42, 64)], fill=GOLD, width=3)
        spaced(d, (x0 + 56, 50), a.eyebrow.upper(), ef, GOLD, 3)

    logo = Image.open(os.path.join(HERE, "assets", "logo-white.png")).convert("RGBA")
    lw = 104; logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
    plate.paste(logo, (x0, H - logo.height - 26), logo)

    out = plate.convert("RGBA"); out.alpha_composite(layer)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    out.convert("RGB").save(a.out, "PNG", optimize=True)
    print("wrote", a.out, os.path.getsize(a.out) // 1024, "KB")


if __name__ == "__main__":
    main()

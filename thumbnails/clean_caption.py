#!/usr/bin/env python3
"""Remove a burned-in Shorts/Reels caption from a video frame without touching anything else.

    python3 clean_caption.py frame.png out.png --word "to you" [--band 0.50,0.62]

Nano Banana 2 (kie) is asked for a caption-free copy of the frame, but only its pixels UNDER
the caption letters are used: the plate is aligned to the frame with ECC (the caption rows
masked out), and pasted inside a dilated mask of the white letters, colour-matched to the real
pixels around them with a local low-frequency correction. The face is never repainted -- NB2
changes Josh's likeness (rejected 2026-09-28), so outside the letters every pixel is the frame's
own. Recipe proven 2026-10-01 and 10-25 (see the thumbnail-pipeline memory); promoted from a
session scratchpad 2026-11-27 because Shorts became a regular photo source.

--band is the caption's vertical extent as fractions of the frame height (default: found by
looking for a row band of large white blobs between 40% and 75% of the height).
"""
import argparse, hashlib, sys
from pathlib import Path
import cv2
import numpy as np

sys.path.insert(0, str(Path.home() / "ai-os" / "tools" / "media-gen"))


def caption_mask(img, band=None):
    """White caption letters: bright, low-saturation blobs at least 16 px tall in the caption rows.
    Small white things (shirt buttons, a mic's ring) are left out by the height test."""
    H, W = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    white = ((hsv[..., 2] > 225) & (hsv[..., 1] < 40)).astype(np.uint8)
    lo, hi = (int(band[0] * H), int(band[1] * H)) if band else (int(.40 * H), int(.75 * H))
    zone = np.zeros_like(white); zone[lo:hi] = 1
    n, lab, st, _ = cv2.connectedComponentsWithStats(white * zone)
    keep = np.zeros_like(white)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_HEIGHT] >= 16 and st[i, cv2.CC_STAT_AREA] >= 60:
            keep[lab == i] = 1
    if not band and keep.any():                 # tighten to the rows the letters actually use
        rows = np.where(keep.any(axis=1))[0]
        lo, hi = max(0, rows[0] - 20), min(H, rows[-1] + 20)
        keep[:lo] = 0; keep[hi:] = 0
    return cv2.dilate(keep, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))), (lo, hi)


def nb2_plate(frame_path, word, out_path):
    from kie_client import KieClient
    k = KieClient()
    data = Path(frame_path).read_bytes()
    url = k.upload_file(frame_path, file_name=hashlib.sha256(data).hexdigest()[:16] + ".png")
    prompt = (f'Remove only the white caption text "{word}" from this photo. Rebuild what is behind '
              'the letters (clothing, hands, microphone, wall, people) so it looks untouched. Change '
              'nothing else at all: same framing, same person, same face, same colors and lighting.')
    urls = k.generate_image(prompt, image_input=[url], output_format="png", quiet=True)
    k.download(urls[0], out_path)


def align(plate, frame, mask):
    """ECC affine of plate onto frame, ignoring the caption rows."""
    g = lambda im: cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    valid = (1 - cv2.dilate(mask, np.ones((61, 61), np.uint8))).astype(np.uint8)
    warp = np.eye(2, 3, dtype=np.float32)
    cc, warp = cv2.findTransformECC(g(frame), g(plate), warp, cv2.MOTION_AFFINE,
                                    (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), valid, 5)
    H, W = frame.shape[:2]
    return cv2.warpAffine(plate, warp, (W, H), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP), cc


def colour_match(plate, frame, mask, sigma=20):
    """Shift the plate toward the frame with a smooth correction learned on a ring around the mask."""
    ring = (cv2.dilate(mask, np.ones((41, 41), np.uint8)) - mask).astype(np.float32)
    diff = (frame.astype(np.float32) - plate.astype(np.float32)) * ring[..., None]
    num = cv2.GaussianBlur(diff, (0, 0), sigma)
    den = cv2.GaussianBlur(ring, (0, 0), sigma)[..., None] + 1e-4
    return np.clip(plate.astype(np.float32) + num / den, 0, 255)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frame"); ap.add_argument("out")
    ap.add_argument("--word", required=True, help="the caption text, for the NB2 prompt")
    ap.add_argument("--band", default="", help="caption rows as fractions of height, e.g. 0.50,0.62")
    ap.add_argument("--plate", default="", help="reuse an NB2 plate already downloaded")
    ap.add_argument("--blur", type=float, default=1.0, help="mask edge softness (px sigma)")
    a = ap.parse_args()
    frame = cv2.imread(a.frame)
    mask, (lo, hi) = caption_mask(frame, tuple(map(float, a.band.split(","))) if a.band else None)
    if not mask.any():
        sys.exit("no caption letters found -- pass --band")
    plate_path = a.plate or str(Path(a.out).with_suffix(".nb2.png"))
    if not a.plate:
        nb2_plate(a.frame, a.word, plate_path)
    plate = cv2.imread(plate_path)
    plate = cv2.resize(plate, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LANCZOS4)
    plate, cc = align(plate, frame, mask)
    plate = colour_match(plate, frame, mask)
    m = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), a.blur)[..., None]
    out = frame.astype(np.float32) * (1 - m) + plate * m
    cv2.imwrite(a.out, np.clip(out, 0, 255).astype(np.uint8))
    changed = int((m[..., 0] > 0.01).sum())
    print(f"ecc {cc:.4f}  caption rows {lo}-{hi}  pixels replaced {changed} "
          f"({100 * changed / mask.size:.2f}% of the frame)  -> {a.out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Measure skin tone on a face: python3 facelab.py image ...  (median LAB a*, b*, chroma, hue).
The approved 2026-10-01 photos of Josh measure a=12 b=14-16, hue 47-51; stream frames come in
pink-red (hue ~16). Use it to check a thumbnail's --skin-hue result, not to guess."""
import sys, os, cv2, numpy as np
import Vision
from Foundation import NSURL
for p in sys.argv[1:]:
    h = Vision.VNImageRequestHandler.alloc().initWithURL_options_(NSURL.fileURLWithPath_(os.path.abspath(p)), None)
    q = Vision.VNDetectFaceRectanglesRequest.alloc().init(); h.performRequests_error_([q], None)
    bb = max(q.results(), key=lambda r: r.boundingBox().size.width).boundingBox()
    im = cv2.imread(p); H, W = im.shape[:2]
    x0, x1 = int((bb.origin.x + .22 * bb.size.width) * W), int((bb.origin.x + .78 * bb.size.width) * W)
    y1, y0 = int((1 - bb.origin.y - .15 * bb.size.height) * H), int((1 - bb.origin.y - .8 * bb.size.height) * H)
    lab = cv2.cvtColor(im[y0:y1, x0:x1], cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(float)
    a, b = lab[:, 1] - 128, lab[:, 2] - 128
    print(os.path.basename(p)[:44].ljust(44), f'a {np.median(a):.1f}  b {np.median(b):.1f}  chroma {np.median(np.hypot(a, b)):.1f}  hue {np.median(np.degrees(np.arctan2(b, a))):.0f}')

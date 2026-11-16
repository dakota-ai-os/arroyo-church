#!/usr/bin/env python3
"""Rank sermon frames for a thumbnail: python3 score_frames.py frames_dir scores.json
Apple Vision face-capture quality per frame (OpenCV here has no haarcascades). Prints the top 25."""
import sys, os, json
import Vision
from Foundation import NSURL
d = sys.argv[1]; out = []
for fn in sorted(os.listdir(d)):
    if not fn.lower().endswith(('.jpg', '.png')): continue
    h = Vision.VNImageRequestHandler.alloc().initWithURL_options_(NSURL.fileURLWithPath_(os.path.abspath(os.path.join(d, fn))), None)
    q = Vision.VNDetectFaceCaptureQualityRequest.alloc().init()
    lm = Vision.VNDetectFaceLandmarksRequest.alloc().init()
    h.performRequests_error_([q, lm], None)
    faces = q.results() or []
    if not faces: continue
    f = max(faces, key=lambda r: r.boundingBox().size.width); bb = f.boundingBox()
    yaw = None; lf = lm.results() or []
    if lf:
        g = max(lf, key=lambda r: r.boundingBox().size.width)
        yaw = float(g.yaw()) if g.yaw() is not None else None
    out.append(dict(f=fn, q=float(f.faceCaptureQuality() or 0), w=float(bb.size.width), h=float(bb.size.height),
                    x=float(bb.origin.x), y=float(bb.origin.y), yaw=yaw, n=len(faces)))
json.dump(out, open(sys.argv[2], 'w'))
for r in sorted(out, key=lambda r: -r['q'])[:25]: print(r)

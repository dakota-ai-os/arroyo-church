#!/usr/bin/env python3
"""Transcribe a sermon stream: python3 transcribe.py audio.m4a transcript.txt transcript-ts.txt
faster-whisper small, cpu int8, VAD on (~6 min for an 80-min stream). The -ts file has one
[H:MM:SS] line per segment, for chapters and fact-checking."""
import sys, time
from faster_whisper import WhisperModel
src, out_txt, out_ts = sys.argv[1:4]
t0 = time.time()
model = WhisperModel("small", device="cpu", compute_type="int8")
segs, info = model.transcribe(src, vad_filter=True, language="en")
plain, ts = [], []
for s in segs:
    plain.append(s.text.strip())
    m, sec = divmod(int(s.start), 60); h, m = divmod(m, 60)
    ts.append(f"[{h}:{m:02d}:{sec:02d}] {s.text.strip()}")
open(out_txt, "w").write(" ".join(plain) + "\n")
open(out_ts, "w").write("\n".join(ts) + "\n")
print(f"duration {info.duration:.0f}s, {len(ts)} segments, {time.time()-t0:.0f}s elapsed")

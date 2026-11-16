#!/usr/bin/env python3
"""Pin chapter boundaries to the word: python3 words.py audio "t0|t1|phrase|phrase2" ...
Transcribes each [t0,t1] clip with word timestamps and prints where each phrase starts."""
import sys, subprocess, re, tempfile, os
from faster_whisper import WhisperModel
m = WhisperModel("small", device="cpu", compute_type="int8")
src = sys.argv[1]
clip = os.path.join(tempfile.mkdtemp(), "clip.wav")
clean = lambda s: re.sub(r"[^a-z0-9' -]", "", s.lower()).strip()
for spec in sys.argv[2:]:
    t0, t1, *keys = spec.split('|')
    t0, t1 = float(t0), float(t1)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t0), '-to', str(t1), '-i', src, '-ac', '1', '-ar', '16000', clip], check=True)
    segs, _ = m.transcribe(clip, word_timestamps=True, language='en')
    words = [(w.start + t0, clean(w.word)) for s in segs for w in s.words]
    txt = ' '.join(w for _, w in words)
    for k in keys:
        kw = k.split()
        for i in range(len(words) - len(kw) + 1):
            if [w for _, w in words[i:i + len(kw)]] == kw:
                s = words[i][0]; print(f'{k!r}: {int(s // 60)}:{s % 60:05.2f}'); break
        else:
            print(f'{k!r}: NOT FOUND in: {txt[:220]}')

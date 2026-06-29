# Arroyo sermon thumbnails

**Automated + manual.** A weekly job preps the pastor image and drops it into Canva;
you do the final composite in Canva (full control) and upload to YouTube.

```
Thu 8:37am  pastor_weekly.py  →  next screenshot → upscale + cutout + feathered → into Canva Uploads
Sunday      you, in Canva     →  open template → drop pastor in → edit hook → export 1280×720 → YouTube
```

## The weekly automation

- **Scheduled task** `arroyo-pastor-thumbnail` (Claude Code → Scheduled), runs Thursdays.
  It runs `pastor_weekly.py`, then uploads the 3 results into your Canva **Uploads**.
- **`pastor_weekly.py`** — picks the **next** screenshot from `pastor-library/` (rotation
  tracked in `rotation.json`), then produces and hosts three versions:
  1. **FULL** — upscaled/enhanced, real stage background
  2. **CUTOUT** — transparent background (rembg)
  3. **FEATHERED** — left/right edges faded to transparent (blend-ready)
- Runs on your Mac when Claude Code is open (or next launch). Uses `tools/media-gen`
  (kie.ai) for the upscale and `rembg` for the cutout.

## Your Sunday step (~2 min, any computer, no install)

1. In Canva, duplicate **"⚙️ Thumbnail Template — Transformational Stories"**.
2. From **Uploads**, drag the pastor (feathered or cutout) onto the right.
3. Change the hook text (Brixton, `#f47524`), tweak scripture/eyebrows.
4. Export 1280×720 → set as the YouTube thumbnail.

## Rotating his image week to week

`pastor-library/` holds the screenshots; each week the job uses the next one.
**Add more** by dropping PNGs into `pastor-library/` (or hand them to Claude) — they
join the rotation automatically.

## Text strategy

See `COPY-PROMPT.md` — thumbnail = a short benefit **hook**; the YouTube title field
is a separate, longer, searchable line.

## Files

- `pastor_weekly.py` — the weekly pastor-prep script (the live pipeline)
- `pastor-library/` — Josh screenshots (rotation source)
- `rotation.json` — which screenshot is next
- `COPY-PROMPT.md` — how to write the hook + YouTube title
- `assets/` — Arroyo logos (`logo-white.png` / `logo-black.png`)
- `make_thumb.py` — an earlier *fully*-automated PIL compositor (kept for reference;
  the Canva-template flow above is what we use now)
- `out/`, `frames/` — scratch (git-ignored)
```

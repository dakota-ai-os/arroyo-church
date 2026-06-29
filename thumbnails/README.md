# Arroyo sermon thumbnails

Turn one screenshot of Josh + a short hook into a finished, on-brand 1280×720
YouTube thumbnail — the same look every week, a new photo every week.

```
screenshot ──▶ RELIGHT (Nano Banana 2) ──▶ COMPOSE (Pillow: type + logo) ──▶ out/*.png ──▶ upload
   frames/        Josh onto brand bg            locked per-series template
```

## Weekly steps (~3 minutes)

1. **Grab a frame** of Josh preaching (a clear gesture/teaching moment). Drop it in
   `frames/` — e.g. `frames/2026-06-29.png`. Pull it from last week's recording so
   the thumbnail is built ahead of Sunday (see "Timing" below).
2. **Decide the text.** Ask Claude (see `COPY-PROMPT.md`) for the thumbnail hook +
   the YouTube title. They are *different* on purpose — hook on the image, full
   searchable title in the YouTube field.
3. **Render:**
   ```bash
   cd thumbnails
   python3 make_thumb.py --src frames/2026-06-29.png --series transformational-stories \
       --l1 FORGIVE --l2 ANYWAY --ref "MATTHEW 18:21-22" \
       --out out/2026-06-29-forgive-anyway.png
   ```
   First run does the paid relight (~$0.04). To tweak only the text/layout, re-run
   with `--scene out/scene_xxxx.jpg` to reuse the rendered scene (free, instant).
4. **Review** `out/…png`, then upload it as the YouTube thumbnail and paste the
   chosen title + description into the video.

## Timing — fresh photo, no Sunday scramble

The only per-week inputs are a **screenshot** and a **title**, both knowable before
Sunday. Recommended: pull the frame from **last week's** recording and build the
thumbnail Thursday. (Josh preaching is Josh preaching — nobody can tell it's last
week.) If you'd rather use *this* week's frame, grab it after the service and run
the one command — ~2 minutes.

## The look

- **Fixed skeleton (every series):** Josh relit on the right, brand type on the
  left, scripture ref, white Arroyo logo bottom-left, 1280×720. Bottom-right is left
  clear for YouTube's duration / LIVE badge.
- **Per-series skin (`series.json`):** `eyebrow` text, `accent` color (RGB — drives
  the eyebrow, the line-2 word, the hairline), and `mood` (the relight lighting
  prompt). Add a series by copying a block in `series.json` and giving it a new key.
- **Fonts:** Impact (display) + Avenir Next (UI), from the system. Swappable in
  `make_thumb.py` (`FONT`).

## Adding a new series

1. Add a block to `series.json` (new key = playlist slug; set `eyebrow`, `accent`, `mood`).
2. (Optional) preview the mood by rendering one sermon with `--series <new-key>`.
That's the only "design" step — every sermon in the series then reuses it.

## Notes / roadmap

- `frames/` and `out/` are git-ignored (raw + regenerable images). The logos and
  scripts are committed.
- Relight quirk: Nano Banana sometimes returns a URL instead of a saved file; the
  script handles that automatically (curl fallback).
- **Cut-out library (optional, later):** for full control of the background we can
  keep transparent PNG cut-outs of Josh (Canva's 1-click background remover, or a
  matting lib) and composite locally instead of relighting — not needed today.
- **Auto-copy (optional, later):** a `copy.py` could call the Anthropic API (key at
  `~/.config/arroyo/anthropic.env`, same as the blog job) to draft the hook + title
  automatically. For now Claude does it interactively via `COPY-PROMPT.md`.
- **GitHub Action (optional, later):** mirror the blog/sync jobs to render on a
  schedule once a `frames/` + title source is wired in.

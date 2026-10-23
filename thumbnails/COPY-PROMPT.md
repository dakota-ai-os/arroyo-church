# Deciding the text — thumbnail hook vs. YouTube title

The thumbnail and the YouTube title field do **different jobs**, so they get
**different text**. Putting the same words in both wastes the title's search value.

| Surface | Job | Rule |
|---|---|---|
| **Thumbnail** | The *click trigger* — read in <1s on a phone | 2–4 word **benefit hook**, NOT the full sermon title. One word gets the accent color. |
| **YouTube title field** | The *search/SEO + context* line | Fuller, keyword-rich. Include the felt-need phrasing + scripture + church/series. ~55–70 chars. |
| **Description (1st line)** | Reinforce + keywords | One sentence that restates the promise and names the passage. |

**Hard rule:** never put the full sentence sermon title on the thumbnail (that's the
title-slide anti-pattern). The thumbnail says the *hook*; the title field says the *headline*.

## The full description — standard blocks, in this order

Real ones: `out/youtube-desc-YYYY-MM-DD.txt` (gitignored, Dakota's Mac). Each block is an ALL-CAPS heading line, its
content on the next line(s), one blank line between blocks.

1. First line (above) + a short gist paragraph
2. `WHAT PASTOR JOSH COVERS` — the numbered points, each with its passages
3. `KEY TAKEAWAY`
4. `SCRIPTURE IN THIS MESSAGE` — refs separated by ` | `
5. `SERIES` — skip for a standalone message
6. `READ THE FULL RECAP` — the blog post URL (the `BLOG_URL` token until it's published)
7. `SERMON NOTES` — `https://links.arroyochurch.com/notes/?week=YYYY-MM-DD`, the Sunday it was
   preached: copy the blog draft `.json`'s `notesUrl` (no draft yet: that Sunday's date, if
   `data/sermon-notes/index.json` lists it). Link links.arroyochurch.com directly: the
   arroyochurch.com/sermon-notes redirect drops `?week=`. Open it once: it must show that week,
   not "We couldn't find notes for…". `notesUrl` is null when that week has no notes (guest
   speaker, no outline): skip the block then, as the blog draft does.
8. `CHAPTERS` — when timestamps are known (redo them if the team trims the video)
9. `NEW HERE? PLAN YOUR VISIT` + the links list (Website, Give, All our links, Instagram, Facebook)
10. `JOIN US IN PERSON`, the closing paragraph, then the hashtags

```
READ THE FULL RECAP
https://www.arroyochurch.com/arroyoblog/<slug>

SERMON NOTES
https://links.arroyochurch.com/notes/?week=2026-10-18
```

**Length: YouTube caps the description at 5,000 characters.** Measure the final text, with the
real blog URL in place (~75–90 chars; the `BLOG_URL` token is 8) and the SERMON NOTES block in
(68 chars with its blank line). A draft that has the SERMON NOTES block but still holds the
token must be ≤ ~4,900 (a 90-char URL then lands at ~4,982). Trim `WHAT PASTOR JOSH COVERS`
first, never the link blocks.

## The prompt (paste the sermon info; Claude returns the copy)

> You are writing YouTube copy for an Arroyo Church (Livermore, CA) sermon.
> Sermon title: «raw title»
> Scripture: «passage»     Series: «series»     One-line gist (optional): «...»
>
> Return:
> 1. **Thumbnail hook** — 3 options, each 2–4 words, ALL CAPS, a felt-need benefit
>    or tension (not the literal title). For each, mark which single word takes the
>    accent color, and split it into line 1 / line 2 for the template.
> 2. **YouTube title** — 3 options, ~55–70 chars, search-friendly, include the
>    passage and "Arroyo Church"; the strongest first.
> 3. **Description first line** — 1 sentence, keyword-rich.
> Keep it warm and clear, never clickbait-y or sensational. Don't sensationalize
> scripture.

## Worked example — "Forgiving Despite Your Feelings" (Matthew 18:21–22)

**Thumbnail hook**
- `FORGIVE` / `ANYWAY`  — accent: ANYWAY   ← used in the comp
- `FORGIVE` / `FIRST`   — accent: FIRST
- `SEVENTY` / `TIMES SEVEN` — accent: SEVEN (leans into the passage)

**YouTube title**
1. `How to Forgive When You Don't Feel Like It | Matthew 18 | Arroyo Church`
2. `Forgiving Despite Your Feelings — Matthew 18:21–22 | Arroyo Church`
3. `Why Forgiveness Isn't a Feeling | Matthew 18 | Arroyo Church Livermore`

**Description first line**
`Pastor Josh on Matthew 18:21–22 — how to forgive someone when your feelings haven't caught up yet.`

→ Feed the chosen hook into `make_thumb.py` as `--l1` / `--l2` / `--ref`; paste the
chosen title + description into YouTube.

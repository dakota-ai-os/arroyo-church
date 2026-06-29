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

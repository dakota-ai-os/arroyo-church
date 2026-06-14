# Arroyo Church — Squarespace Reskin Guide

**Goal:** Bring the "River in the Desert" redesign look into your **existing Squarespace 7.1 site** without moving, renaming, or deleting any page — so **zero SEO is lost**.

**Who this is for:** A non-developer following click-by-click steps. No coding experience needed. The only "code" is copy-paste into two boxes Squarespace gives you.

---

## ⛪ Read this first — why this is SEO-safe

We are **reskinning**, not rebuilding. Every page keeps its exact URL, title, meta description, structured data, and place in your sitemap, because we never remove or move a page — we only change how it *looks*. Concretely, all of this stays 100% intact and Squarespace keeps managing it for you:

| SEO asset | Stays untouched? |
|---|---|
| Page URLs (`/about`, `/give`, `/team`, `/messages`, `/connect`, `/plan-your-visit`) | ✅ Yes |
| Per-page SEO titles & meta descriptions | ✅ Yes |
| Structured data (`Church` / `LocalBusiness` schema → your Google map listing) | ✅ Yes |
| The entire blog (`/arroyoblog` + ~20 posts + ~150 keyword tag pages) | ✅ Yes — **do not touch it** |
| Google Analytics (`G-YQ1G7DZBLE`) | ✅ Yes |
| Sitemap, robots.txt, canonical tags | ✅ Yes (auto-managed) |
| Domain authority & backlinks | ✅ Yes (same domain) |

**Nothing in this guide edits a URL, a page title, a meta description, or the blog.** If you ever feel unsure, the safe rule is: *changing how a section looks = safe; deleting or renaming a page = stop and ask.*

> You can hand this whole table to your SEO company as proof that the refresh doesn't disturb their work.

---

## The plan in 5 parts

1. **Brand setup** (colors + fonts) — native Squarespace, ~15 min
2. **Turn on scroll animations** — native Squarespace, ~2 min
3. **Paste the Custom CSS** — one box, the visual polish, ~5 min
4. **Add the live countdown** (optional) — one Code block, ~5 min
5. **Section-by-section refresh notes** — rebuild the *look* of each page with native blocks

Do them in order. After each part, click **Save** and look at your site — nothing here is destructive, and you can undo any step.

---

## Part 1 — Brand setup (colors & fonts)

This single step does ~60% of the visual transformation, site-wide, with zero code.

### Colors
1. In the editor, go to **Design → Colors** (or **Site Styles → Colors**).
2. Open the **palette editor** and set these five colors (the redesign palette):

   | Role | Hex |
   |---|---|
   | Dark (deep water) | `#0D2530` |
   | Darkest (night) | `#0A161C` |
   | Bright accent (river teal) | `#2E8FA3` |
   | Light accent (desert gold) | `#C89A3E` |
   | Lightest (paper) | `#FAF7F0` |

3. Squarespace generates section "themes" (Lightest, Light, Bright, Dark, Darkest) from these. You'll assign them per section in Part 5. As a default: **light/paper** background for most content sections, **dark** for the hero and the closing call-to-action.

### Fonts
1. Go to **Design → Fonts** (or **Site Styles → Fonts**).
2. Choose an **Assigned font pack**, then set:
   - **Headings:** `Fraunces` (an elegant serif — gives the "editorial" feel). If Fraunces isn't in the picker, use **`Playfair Display`** as the backup.
   - **Paragraphs / body:** `Manrope` (you already use this — keep it).
3. Bump **Heading weight** to a light/regular weight (300–400) for the airy display look, and turn on **italic** styling where Squarespace offers it for emphasis.

✅ **After Part 1:** your whole site already reads as the new brand — warm paper backgrounds, teal/gold accents, serif headlines.

---

## Part 2 — Turn on scroll animations (native, free)

Squarespace 7.1 has built-in scroll-reveal animations — this replaces most of the custom JavaScript from the prototype with **zero risk**.

1. Go to **Design → Animations**.
2. Set the style to **Fade** or **Fade & Scale**.
3. Set intensity/complexity to **Detailed**.
4. Save.

Now every section and image gently reveals as visitors scroll — the core "engaging scroll" feel, handled by Squarespace itself.

> Want a specific section to animate differently? In the editor, click a section → **Animations** tab → pick a per-section effect.

---

## Part 3 — Paste the Custom CSS

This adds the polish Squarespace's panels can't do: button gradients, card hover-lift, the desert→river gradient on the "why Arroyo" section, the countdown styling, and a scroll-progress bar.

1. Go to **Design → Custom CSS** (or **Website → Website Tools → Custom CSS**).
2. Open the file **`custom-css.css`** (in this same folder), copy **everything**, and paste it into the box.
3. Click **Save**.

The CSS is commented and scoped to your real page IDs. It only *adds* visual styling — it never hides content. If one effect looks off against your live sections, you can delete that one commented block; the rest keeps working. (This is the part most likely to need a little tuning once it's on your live pages — see "Refining" at the bottom.)

---

## Part 4 — Live "Next Gathering" countdown (optional)

A countdown to Sunday 10 AM is a nice engagement touch. It's the one genuinely dynamic piece, so it needs a small code snippet — placed in a **Code block**, which is the safest, most contained way (it lives in one spot and can't affect anything else).

1. Edit your **home page** → add a **section** (or use the existing one under the hero).
2. Add a **Code block** (`+` → **Code**).
3. Open **`code-block-countdown.html`** (this folder), copy everything, paste it into the Code block.
4. Save.

> Code blocks require the **Business plan or higher**. If you're on a lower plan, skip this — everything else still works. (Your site already runs custom analytics + structured data, which means you're almost certainly on Business+ already.)

---

## Part 5 — Section-by-section refresh notes

You don't need to rebuild pages from scratch — just refresh the *look* using native blocks. Here's the target for each, mapped to the redesign:

### Home (`/home`)
- **Hero:** Keep your existing **video background** (`ArroyoChurch_WebsiteBanner.mp4`) — it's already there and it's perfect. Set the section theme to **Dark**, headline in Fraunces: *"A river in the desert."* Two buttons: **Plan Your Visit** (primary/gold) + **Watch a Sermon** (secondary/outline).
- **Countdown strip** (Part 4) directly below.
- **"Who we are"** — two-column section: mission text + the three values (Knowing / Showing / Bay Area) as a 3-up of native **summary/auto-layout cards**.
- **"Why Arroyo"** — a full-width section with the Isaiah 43 verse; the Custom CSS applies the desert→river gradient background here.

### About / Beliefs (`/about`)
- Lead with the mission statement.
- Put the **6 beliefs** (Gospel, Trinity, Bible, Humanity, Eternity, Church) in an **Accordion block** — native, collapsible, matches the prototype's expandable cards.
- Put the **5 values** as stacked cards or an accordion.

### Team (`/team`)
- Use an **image grid / gallery** (or summary blocks) for the 6 staff: photo + name + role. Native hover zoom + the Custom CSS hover-lift gives the interactive feel.
- Elder board below as a simpler 4-up grid.

### Sermons (`/messages`)
- Keep it pointed at YouTube. Use a **Video block** for the latest sermon + a grid of links to the **Current Series** and **Podcast** playlists (see note below).
- ⚠️ **Don't replace your blog.** The sermon write-ups at `/arroyoblog` are doing major SEO work — leave them exactly as is. You can add a "Read sermon recaps" button linking to the blog.

### Connect (`/connect`)
- Connect-group photo + copy + **Join a Group** button (links to your existing Church Center form).
- 3 ministry cards (Connect Groups / Children's / Women's).
- Keep the existing **prayer-request form** — it's a native form, leave it wired up.

### Give (`/give`)
- 3 cards: Cash / Stock / Crypto, linking to your existing `donate.overflow.co` URLs. The Custom CSS styles them as the gold-accented hover cards.

### Plan Your Visit (`/plan-your-visit`)
- Service time + address + the **round building** note, the 3-step "what to expect," the FAQ as an **Accordion block**, and your existing map.

---

## Refining the look

The native settings (Parts 1–2) and the countdown (Part 4) will look right immediately. The **Custom CSS** (Part 3) is the part that sometimes needs small tweaks against your live sections, because every Squarespace layout is slightly different.

If something looks off after pasting, the fastest path: take a screenshot of the section, and the values to adjust are clearly labeled in `custom-css.css` (each block has a `/* TUNE: ... */` note). It's normal to do one or two rounds of small adjustments to get it pixel-perfect.

---

## What you are NOT doing (the safety list)

To keep SEO fully intact, never do any of these as part of the refresh:
- ❌ Change a page's **URL slug**
- ❌ Edit a page's **SEO title or description** (SEO Settings panel)
- ❌ Delete or unpublish the **blog** or any blog post / tag page
- ❌ Remove the **Code Injection** that holds your structured data + analytics
- ❌ Disconnect or change the **domain**

Styling, colors, fonts, animations, rearranging blocks within a page, swapping images — all safe.

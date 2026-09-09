# Arroyo Church on Google — Business Profile, Paid Ads, Ad Grant

Source of truth for the church's Google presence. Written 2026-09-09 from a live audit
(signed in as av@arroyochurch.com). Shareable page: see the artifact link in the session
that created this file; this markdown is the canonical copy.

## 1. What exists today (audit, 2026-09-09)

### Google accounts — who owns what
| Account | Business Profile | Google Ads | Analytics | Google for Nonprofits |
|---|---|---|---|---|
| av@arroyochurch.com (church) | **Owns the verified profile** (location id 17879649240172433098) | none | none | none (not enrolled) |
| joshuadsmith23@gmail.com (Josh) | — | 449-822-2113 **(Cancelled)** | GA account "Google Ads Account" (a177307349), no property | — |
| karerecycling@gmail.com (Dakota, personal) | — | 992-891-2628 (Dakota's own, paused) | "KotaApps" (personal) | — |
| Site tag | — | — | GA4 `G-YQ1G7DZBLE` is installed on arroyochurch.com via Squarespace; **owner unknown** | — |

Decision: everything new (Ads account, Ad Grants, Google for Nonprofits) lives under
**av@arroyochurch.com**. Ad Grants requires the same login for Google for Nonprofits and
the grant account. Do not reuse Josh's cancelled account or Dakota's personal one.

### IRS status (public record, ProPublica/IRS BMF)
Arroyo Church · EIN **94-1347079** · 945 Concannon Blvd, Livermore CA 94550-6482 ·
501(c)(3), ruling date 2019-08, contributions deductible (Pub 78), foundation code 10 (church).
The church is in the IRS database → Goodstack (Google's verifier) can match it.

### Business Profile — state
- Verified. 5.0 ★ · 50 reviews · every review answered (good). Profile strength "Looks good".
- Categories: Church (primary) · Christian church · Non-denominational church. Keep.
- Description: 291 of 750 chars, says "a new church", no Tri-Valley / service-time / ministry keywords.
- Hours: Sun 10:00–11:30 · Mon closed · Tue–Fri 10–4 · Sat closed. Special hours: none.
- **Worship service hours added 2026-09-09 (Sunday 10:00–11:30 AM) — pending Google review.**
- Opening date: not set. Services: none. Posts: **never posted**. Q&A: none. Chat: off.
- Attributes: wheelchair entrance/parking/restroom + restroom (added by Google). "From the business": none.
- Photos: cover + logo + a handful; Google flags "add interior photo".
- Contact: (925) 694-0426 · arroyochurch.com · FB / IG / YouTube linked.
- Service area: Livermore, Pleasanton, Dublin, San Ramon.
- Performance: 939 interactions Apr–Sep 2026 (~190/mo); ~536 profile views/mo.
- **Phone mismatch (NAP):** profile + site body say (925) 694-0426, but the Church JSON-LD schema on the
  standalone pages (`.source_pages/arroyo_about.html`, `arroyo_messages.html`) and Yelp still say (925) 642-1516.

### Local competition ("church in livermore ca", 2026-09-09)
Map pack: Cornerstone Fellowship (4.5 · 122) · CrossWinds (4.7 · 79) · New Beginnings (5.0 · 27).
Blue Oaks Church (Pleasanton) is buying a Sponsored local ad. Arroyo (5.0 · 50) is not in the
3-pack for the generic query. Levers: review velocity, posts, photos, Q&A, description keywords.

### Keyword demand (Keyword Planner, Livermore+Pleasanton+Dublin+San Ramon, Aug 2025–Jul 2026)
Local church terms each show 100–1K searches/mo, competition **Low**. Bid data unavailable
(account has no spend history). Industry benchmarks put nonprofit/church CPCs at ~$1–3.

## 2. Business Profile — changes

### Done (2026-09-09, all pending Google review unless noted)
- Worship service hours: Sunday 10:00–11:30 AM.
- Description replaced with Dakota's copy ("bible-based Christian church…"). Google rejects URLs in descriptions, so the
  last line reads "Plan your visit on our website. We would love to save you a seat."
- Opening date: September 2023.
- Website link now carries UTM tags (`utm_source=google&utm_medium=organic&utm_campaign=gbp`).
- Services added: Sunday Worship Service · Kids Ministry · Students & Youth · Connect Groups · Prayer · Baptism · Online Sermons & Livestream.
- 9 photos uploaded from the website (worship gathering, lobby banner, Josh preaching, outdoor tent, 5 team headshots).
- Posts published: (1) What to expect — Sign up → /plan-your-visit, lobby photo; (2) Connect groups — Learn more → /connect,
  worship-gathering photo. The Monday sermon recap is left to the sermon→blog pipeline (add a GBP post step there).
- Phone consolidated to (925) 694-0426: the site-wide Church JSON-LD (Squarespace HEADER injection) now carries it, plus
  a real logo + hero image instead of the placeholder paths. Yelp still needs a manual edit (needs the Yelp for Business login).
- Conversion tracking LIVE on arroyochurch.com (commit 09fb874): `acTrack()` fires GA4 events on every form success
  (`plan_visit_submit`, `join_group_submit`, `connect_class_submit`, `prayer_request_submit`, `connect_tag_submit`) and on
  `call_click` / `directions_click` / `watch_live_click`. Next: mark them as key events in GA4 `G-YQ1G7DZBLE` and import into Ads.

### Proposed — need Dakota's go (public-facing copy)
**Description (replace; ~560/750 chars):**
> Arroyo Church is a non-denominational Christian church in Livermore, CA, serving families across
> the Tri-Valley — Livermore, Pleasanton, Dublin, and San Ramon. We gather Sundays at 10:00 AM at
> 945 Concannon Blvd (the round building) for worship, Bible teaching, and real community. Kids
> ministry meets on Sundays, and connect groups meet during the week for men, women, couples, moms,
> young adults, and students. Whether you grew up in church or haven't been in years, you're welcome
> here — come as you are. Plan your visit at arroyochurch.com.

**Services (custom, under Church):** Sunday Worship Service · Kids Ministry · Students/Youth ·
Connect Groups · Prayer · Baptism · Online Sermons & Livestream.

**Q&A seed (owner asks + answers):** service time · kids · what to wear · parking · denomination (SBC) ·
worship style · online option. (Copy in section 6.)

**Posts (weekly):** first three drafted (section 6). Ongoing: Monday sermon-recap post fed by the
existing sermon→blog automation; event posts as they come.

**Website link with UTM:** `https://www.arroyochurch.com/?utm_source=google&utm_medium=organic&utm_campaign=gbp`

### Facts confirmed by Dakota (2026-09-09)
- Phone is (925) 694-0426. Tue–Fri 10–4 are real office hours. Church opened September 2023.
- Denomination line for Q&A: "We are a Christian church part of the SBC, centered on knowing and showing the love of Jesus."
- Worship style: blends contemporary and traditional — new songs and hymns that have been around for decades.
- Instagram is all Reels and Facebook photo URLs are not fetchable from the page, so photos came from the website only.

### Still open
- **Q&A:** moot. Google discontinued Business Profile Q&A on 2025-11-03 (phased out from 2025-12-03); Gemini "Ask Maps" now
  answers from the profile, reviews, photos, and website. So the Q&A copy belongs on the website FAQ (/plan-your-visit already
  has an FAQ block) and in posts. To add: the SBC line and the worship-style line.
- **Sermon-recap post** — wire into the weekly sermon→blog automation (draft text + YouTube link → GBP post).
- **Yelp phone** (925) 642-1516 → 694-0426: needs the Yelp for Business login.

### Weekly rhythm (15 min)
Post once (sermon recap) · answer reviews within 48h · ask 3 people for a review (QR in bulletin,
"Ask for reviews" link) · add 1–2 photos · monthly: read Performance + Ads search terms.

## 3. Paid Google Ads — $125/mo

**Account:** Google Ads customer ID **974-189-2062** was created under av@arroyochurch.com on 2026-09-09 (the "New Google
Ads Account" button creates the shell immediately). Its signup wizard (business info → campaign → payment) is still
unfinished; billing must be entered by Dakota. Claude builds the real campaign paused; Dakota flips it on.

**Goal — yes, set one.** Campaign goal = Leads. Primary conversion = **Plan a Visit form submit**.
Secondary = Join a Group submit, Directions click, Call click. Bidding: **Maximize Clicks with a
$2.50 max-CPC cap** for the first 30–60 days ($4/day is too little for Smart Bidding to learn),
then switch to **Maximize Conversions** once ~15 conversions land in 30 days.

**Campaign:** Search only (no Display, no search partners) · location = 10-mile radius around
945 Concannon Blvd, "presence" targeting · English · all days · landing page
`https://www.arroyochurch.com/plan-your-visit` (already titled "Plan Your Visit | Churches Near Livermore CA").

**Ad groups / keywords (phrase + exact):**
1. Church in Livermore — church in livermore · churches in livermore ca · livermore church ·
   churches near me · church near me · sunday church service livermore
2. Non-denominational / Christian — non denominational church livermore · christian church livermore ·
   bible church livermore · non denominational churches near me · christian churches near me · family church livermore
3. Tri-Valley neighbors (lower bids) — church pleasanton · churches in pleasanton ca · church dublin ca ·
   church san ramon · non denominational church pleasanton · christian church dublin ca

**Negatives:** catholic, mormon, lds, jehovah, kingdom hall, orthodox, episcopal, lutheran,
presbyterian, methodist, adventist, mosque, synagogue, temple, jobs, hiring, wedding venue,
rental, thrift, food bank, daycare, preschool, funeral, obituary, church's chicken, churchill.

**Responsive search ad:** headlines — Church in Livermore, CA · Sundays at 10 AM · Arroyo Church |
Livermore · Come As You Are · Non-Denominational Church · Kids Ministry Every Sunday · Plan Your
Visit Today · Bible Teaching, Real People · Serving the Tri-Valley · New to Church? Start Here ·
Connect Groups All Week · 945 Concannon Blvd, Livermore. Descriptions — "Welcoming
non-denominational church in Livermore. Worship, Bible teaching, kids ministry." · "Sundays at 10 AM
at 945 Concannon Blvd. Plan your visit and we'll save you a seat." · "Looking for a church near
Livermore, Pleasanton or Dublin? You're welcome here, as you are." · "Real community, kids programs
and connect groups for every stage of life. Come see us."
Assets: sitelinks (Plan Your Visit · Watch a Sermon · Kids Ministry · Connect Groups), callouts
(Sundays 10 AM · Kids Programs · Free Parking · Come As You Are), call asset, location asset (GBP link).

**Budget math:** $125/mo = $4.11/day. At $1.50–2.50 CPC → 50–80 clicks/mo. At a 5% form rate →
2–4 visit requests/mo, ~$30–50 each. It is a test, not the volume lever; the Ad Grant is.

**Conversion tracking (site change, deploy per CLAUDE.md runbook):** fire events from the success
handlers in `squarespace/footer-injection.html` (plan-a-visit + join-a-group forms) and on the
Watch Live / call / directions clicks. Preferred: GA4 events on `G-YQ1G7DZBLE` marked as key events
and imported into Ads (needs the property owner to add av@ as editor). Fallback: Google Ads
conversion snippet directly.

## 4. Google Ad Grant ($10,000/mo in Search ads)

**Status 2026-09-09 (evening):** Google for Nonprofits request **SUBMITTED** under av@arroyochurch.com (Dakota confirmed
EIN 94-1347079 and completed the contact/terms steps). Goodstack replies to av@arroyochurch.com within 2–14 business days;
watch for verifications@mail.goodstack.org. Context for any Goodstack question: the church operated as **East Hills Church**
before relaunching as Arroyo Church in September 2023 (Facebook posts from 2020 carry the East Hills logo), which is why the
EIN's ruling date is 2019 and Goodstack shows an older Oakland mailing address. Have the IRS determination letter or EIN letter
ready under the East Hills name if asked. After approval: Activate products → Google Ad Grants.

**Eligibility check:** 501(c)(3) in the IRS database ✔ · own domain on HTTPS ✔ · substantial
original content ✔ · no AdSense on the site ✔ · not a school/hospital/government ✔. Religious
organizations are eligible; Google for Nonprofits requires agreeing to its non-discrimination
policy — Josh should read the terms before accepting.

**Steps (Dakota clicks the parts Claude cannot: account creation, EIN, terms):**
1. google.com/nonprofits → Get started → Continue as **av@arroyochurch.com** → United States →
   org details: Arroyo Church · EIN 94-1347079 · 945 Concannon Blvd, Livermore CA 94550 ·
   arroyochurch.com · contact name/email/phone → accept terms → submit.
2. Goodstack verifies (3–5 business days). Watch av@ inbox for verifications@mail.goodstack.org;
   they may ask for the 2019 IRS determination letter or the EIN letter (CP-575 / 147C). Have PDFs ready.
3. Approved → Google for Nonprofits → Activate products → **Google Ad Grants** → Get started →
   enter website, answer the pre-qualification questions → Activate. Google reviews (typically < 1 week).
4. Accept the email invitation to the new **Ad Grants Ads account** (separate from the paid one).
   Claude builds campaigns to policy: Search only · Maximize Conversions (Smart Bidding required; no
   $2 CPC cap under Smart Bidding) · conversion tracking with ≥1 conversion/mo · ≥5% CTR every
   month · geo-targeted · ≥2 sitelinks · no single-word or overly generic keywords · $329/day cap.
5. Keep it alive: monthly CTR/conversion check, annual program survey.

**How paid + grant fit:** grant ads show below paid ads. Paid $125 buys the top slot on the 5–10
highest-intent local keywords; the grant covers the long tail (life-moment searches, sermon topics,
"what to expect at church", seasonal Easter/Christmas).

**Bonus inside Google for Nonprofits:** Google Workspace for Nonprofits (free Business Starter — if
arroyochurch.com mail is on Workspace this can zero the bill) and the YouTube Nonprofit Program.

## 5. What Dakota has to do (Claude can't)
1. Approve the profile copy in section 2 (description, services, Q&A, posts).
2. Answer: phone, office hours, year founded. Send 10–15 photos.
3. Create the Google Ads account under av@ and add billing (~10 min). Claude then builds the campaign paused.
4. Sit with Claude through the Google for Nonprofits sign-up (EIN + terms) and find the IRS letter PDF.
5. GA4 replaced 2026-09-09: new Analytics account "Arroyo Church" (a407495086) / property "arroyochurch.com"
   (p553508954) / web stream 15749987659 / **measurement ID G-W3RLM6P1H0**, owned by av@arroyochurch.com. Swapped into
   Squarespace (Settings → Developer Tools → External API Keys → Google Analytics) replacing the agency-owned G-YQ1G7DZBLE.
   Live site confirmed serving G-W3RLM6P1H0. GA4's Events hub only lets you star an event as a key event after it has been
   received, so: once `plan_visit_submit`, `join_group_submit`, `call_click`, `directions_click`, `watch_live_click` show up under
   Admin → Events → Recent events, star them. Then link GA4 ↔ Ads 974-189-2062 (Admin → Product links) once the Ads wizard is done.

## 6. Copy bank

**Q&A seeds**
- What time is the Sunday service? — Sundays at 10:00 AM. Doors open at 9:30. It runs about 65 minutes.
- Is there something for kids? — Yes. Kids ministry meets during the Sunday service. Check in at the kids desk when you arrive.
- What should I wear? — Whatever you're comfortable in. Most people are casual.
- Where do I park? — Free parking on site at 945 Concannon Blvd. The worship center is the round building.
- What denomination is Arroyo Church? — Non-denominational Christian church, centered on knowing and showing the love of Jesus.
- Can I watch online? — Yes. Sundays at 10 AM at youtube.com/@arroyochurch/live; past messages are on the channel.
- How long is the service? — About 65 minutes.

**First three posts**
1. Sermon recap (Monday): "This Sunday, Pastor Josh [title]. Missed it? Watch the full message: [YouTube link]. Join us next Sunday at 10 AM — 945 Concannon Blvd." Button: Learn more → sermon URL.
2. What to expect: "New to Arroyo? Sundays at 10 AM, about 65 minutes, kids ministry during service, free parking. Come as you are. Plan your visit and we'll save you a seat." Button: Sign up → /plan-your-visit.
3. Connect groups: "You were created for community. Connect groups meet all week — men, women, couples, moms, young adults, students. Find yours." Button: Learn more → /connect.

## 7. Maintenance
- Update this file when accounts are created (add account IDs), when the grant is approved, and when bidding changes.
- Decision to log: 2026-09-09 — all Google properties consolidated under av@arroyochurch.com; paid Ads is a $125/mo top-slot test, Ad Grant is the volume lever.

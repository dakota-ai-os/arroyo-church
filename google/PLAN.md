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
- Hours: Sun **9:30**–11:30 (doors open 9:30, confirmed by Dakota 2026-09-28; was 10:00) · Mon closed · Tue–Fri 10–4 · Sat closed. Special hours: none.
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
  2026-09-13: the service runs about 55 minutes, not 65 (Dakota). **Superseded 2026-09-30: Josh says it's about 70 minutes; all live copy moved to 70.** The copy bank below is corrected. The live
  "What to expect" post was edited to 55 on 9/13 and to 70 on 9/30 (shows Pending while Google reviews each edit).
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
- (2026-09-28) Sunday doors open 9:30 AM; service 10:00 AM. The building is wheelchair accessible. Dakota granted full
  permission to publish the site/hero-video photos on Apple Maps (Apple's upload attests rights from everyone pictured).
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

**Account:** Google Ads customer ID **974-189-2062**, created under av@arroyochurch.com on 2026-09-09. Billing entered by
Dakota the same day (Mastercard ••••3144, "Arroyo Church" payments profile). Claude builds the campaign paused; Dakota flips it on.

**Build log (2026-09-09) — PUBLISHED and PAUSED. Live campaign "Search - Church in Livermore", campaignId 24229326228
(the wizard draft was 281499211207158 / draftId 10213248828).** Settings as spec'd: Search only (partners + Display off),
Maximize Clicks with a $2.50 max-CPC cap, 10 mi radius around 945 Concannon Blvd (**Presence** only), English, EU political
ads = No, AI Max off, budget **$4.11/day**, goal "Submit lead forms". Three ad groups, each with the same 12-headline /
4-description RSA (paths `Livermore/Visit`, ad strength "Average" pre-launch):
1. **Church in Livermore** — the 12 Livermore keywords (phrase + exact). Eligible once the campaign is enabled.
2. **Christian / Bible church** — the 12 non-denominational/Christian/Bible keywords. Google flagged all of them under
   *"Religious belief in personalized advertising"*; an **exception review was requested** in the wizard and they sit at
   "Under review". If Google declines, drop them — ad group 1's phrase-match keywords already cover those searches.
3. **Tri-Valley neighbors** — the 12 Pleasanton/Dublin/San Ramon keywords (no flag). No lower bid: Maximize Clicks ignores
   ad-group bids, so "lower bids" for this group means a bid adjustment later, not a max CPC.
Campaign-level: **26 negative keywords** (the list below, broad match); assets attached at campaign level = 4 sitelinks
(Connect Groups → /connect, View Sermons → /messages, Our Team → /team, About Arroyo Church → /about), 4 callouts
(Sundays at 10 AM · Kids Programs · Free Parking · Come As You Are), call asset (925) 694-0426 — all "Pending / Under review".
Gotchas hit: the wizard's Budget step threw Google's "Confirm it's you" re-auth (Dakota completed it; the draft showed
"Changes failed to save" until a reload, and the EU-political-ads answer had to be re-selected); publishing dropped the
wizard's asset associations (the assets existed in the library but weren't attached — re-attached via Campaign → Assets →
+ → "Use existing"); the wizard builds only one ad group (2 and 3 added from Ad groups → +, which pre-fills the RSA copy
from group 1); the campaign was live for ~2 minutes between Publish and Pause (no spend recorded).
**Conversion tracking (LIVE 2026-09-09):** Google tag **AW-18441276047**, conversion action "Submit lead form"
(ctId 7756266707, event label `mHR9CNP5vPIcEI-VvtlE`). `squarespace/footer-injection.html` (commit 9c6e3e5, deployed)
calls `gtag('config','AW-18441276047')` on Squarespace's existing gtag loader and fires
`gtag('event','conversion',{send_to:'AW-18441276047/mHR9CNP5vPIcEI-VvtlE'})` from `acTrack()` on `plan_visit_submit`
and `join_group_submit` (the GA4 events still fire too). Verified on the live page (dataLayer carries the AW config).
The action shows "Inactive" in Ads until the first real submission arrives. **GA4 ↔ Ads linked** (Analytics
a407495086/p553508954 → Ads 974-189-2062, auto-tagging on, personalized advertising on; data appears within 24 h).
**Location asset (2026-09-09):** the Business Profile is auto-linked in Ads (Data manager → Google Business Profile → "av@arroyochurch.com, 1 location, Used in location asset"); the campaign's location asset is set to **All locations**, so the ad can show with the map pin + address the way Blue Oaks' sponsored listing does. Google-tag diagnostics say "some pages not tagged" — stale crawl; the footer tag is site-wide and this clears on its own.
**ENABLED 2026-09-09 ~8:00 PM PT on Dakota's instruction** (status Eligible, bid strategy learning). **Check 2026-09-10 ~2 PM:**
campaign Enabled / Eligible (Learning), optimization score 90.1%, all three ads Eligible, first click recorded on day 1.
Two follow-ups: (1) DONE 2026-09-10: Click-to-Call terms accepted (Admin → Account settings; Dakota authorized, Claude saved) — the
call-terms banner is gone and the (925) 694-0426 call asset can serve; (2) DONE 2026-09-10: the Tri-Valley ad (adId 824112396709) got three more headlines — "Church Near Pleasanton",
"Church Near Dublin, CA", "Minutes from San Ramon" — now 15/15 headlines; ad strength went Poor → Good in the editor. Watch: keyword policy review (group 2), asset review, first
conversion, and the search-terms report weekly.
**Copy deltas vs the spec below (applied in the build):** headline "Non-Denominational Church" → "Bible-Based Christian
Church" and description 1 → "Welcoming Bible-based Christian church in Livermore. Worship, teaching and kids ministry."
(matches the approved SBC profile copy); description 3 trimmed to "Searching for a church near Livermore, Pleasanton or
Dublin? You're welcome as you are." (90-char cap). Sitelinks: the wizard's real-page set above replaces
"Plan Your Visit / Watch a Sermon / Kids Ministry / Connect Groups" (Plan Your Visit is already the landing page; there is
no kids page to link).
**Still to do after publish (the wizard only builds one ad group):** rename "Ad group 1" → "Church in Livermore"; add ad
groups 2 and 3 from Campaign → Ad groups → +, same RSA copy, group 3 with a $1.50 max CPC; add the campaign-level
negative list; add the location asset once GBP is linked (Assets → Location); create the "Form submissions" conversion
action's tag and wire its AW-id/label into `acTrack()`; link GA4 a407495086/p553508954 ↔ Ads.

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
3. DONE 2026-09-09: Ads account 974-189-2062 + billing (Dakota), campaign built by Claude and **enabled the same evening** on Dakota's go — now spending up to $4.11/day.
4. Sit with Claude through the Google for Nonprofits sign-up (EIN + terms) and find the IRS letter PDF.
5. GA4 replaced 2026-09-09: new Analytics account "Arroyo Church" (a407495086) / property "arroyochurch.com"
   (p553508954) / web stream 15749987659 / **measurement ID G-W3RLM6P1H0**, owned by av@arroyochurch.com. Swapped into
   Squarespace (Settings → Developer Tools → External API Keys → Google Analytics) replacing the agency-owned G-YQ1G7DZBLE.
   Live site confirmed serving G-W3RLM6P1H0. GA4's Events hub only lets you star an event as a key event after it has been
   received, so: once `plan_visit_submit`, `join_group_submit`, `call_click`, `directions_click`, `watch_live_click` show up under
   Admin → Events → Recent events, star them. Then link GA4 ↔ Ads 974-189-2062 (Admin → Product links) once the Ads wizard is done.

## 5b. Yelp (2026-09-09; split into two pages 2026-09-17)

**Accounts:** Yelp for Business login = **av@arroyochurch.com** (changed from josh@easthillschurch.com on 2026-09-10 and verified
via the confirmation email; Dakota entered the password for the re-auth step). Account profile renamed to **Arroyo Church Team** (shows as "Arroyo Church T., Manager" in review replies) on 2026-09-10; password unchanged per Dakota. The public "Meet the Manager" section still shows Josh S., Lead Pastor — that's separate and intended. Managed listings: **Arroyo Church** `73urM3xpc70b8Og0olohgg`
(**`yelp.com/biz/arroyo-church-livermore-2`** since 2026-09-18; `arroyo-church-dublin` redirects to it) and the old **East Hills
Church** page `rVgGFgmFdc1T3c0fja9N_A` (`yelp.com/biz/east-hills-church-oakland-2`, shown as CLOSED since 2026-09-18). ⚠️ The
unsuffixed `yelp.com/biz/arroyo-church-livermore` belongs to the OLD page and now lands on the closed East Hills page — never
share it. See the split below.

**Fixed on the claimed listing on 2026-09-09 (was "East Hills Church, 12000 Campus Dr, Oakland", 7 reviews, 4.4★; reversed on
2026-09-17, see below):** name → Arroyo Church ·
address → 945 Concannon Blvd, Livermore, CA 94550 (map pin verified) · phone → (925) 694-0426 (was blank) · website →
arroyochurch.com (was easthillschurch.com) · hours Open-24-hours-every-day → Mon closed, Tue–Fri 10–4, Sat closed, Sun 10:00–11:30 ·
Specialties → the approved Bible-based description + the worship-style line (no URL; Yelp rejects URLs/phones in copy) ·
History → "Established 2023" + East Hills → Arroyo lineage · Meet the Manager → Josh S., Lead Pastor bio · deleted all **19
business-uploaded** old photos (Oakland estate, East Hills logo) · uploaded **8** current site photos with captions. All changes
saved live (Yelp says it reviews name/address edits against the website; nothing has bounced). Logo placement is a paid Yelp add-on
($1/day) — skipped. **Can't fix:** the ~17 user-uploaded East Hills-era photos (kids choir, fellowship hall) — owners can only
flag them; Yelp orders photos by engagement so the new ones will mix in.

**Duplicate listing → now the Livermore page (2026-09-17).** Strategy changed 2026-09-12: do NOT ask Yelp to merge. Renaming the
Oakland page put its 1-star review and ~17 member photos on Arroyo, and Apple Maps shows Yelp's photos/reviews. Instead: the
former duplicate `73urM3xpc70b8Og0olohgg` (yelp.com/biz/arroyo-church-dublin; its pin sat at Regal Hacienda Crossings, Dublin,
where the church once met) becomes Arroyo's clean page, and the old page goes back to East Hills Church, Oakland, marked Moved.

**Done on `73urM3xpc70b8Og0olohgg` (2026-09-17):** claimed under av@ (no text code needed) · phone (925) 642-1516 → 694-0426 ·
hours Mon closed, Tue–Fri 10–4, Sat closed, Sun 10–11:30 · Specialties + History + Meet the Manager (Josh S.) copied from the old
page · amenity Open to All · 8 site photos uploaded with ACCURATE captions (verified on the public page): Chris Rogers (Worship
Pastor), Emily Fountain (Children's Ministry Director), Josh Smith (Lead Pastor) headshot + preaching, Elijah Merrell (Media
Coordinator), Kelly Patchin (Elder), lobby "Community at Arroyo Church", tent "Arroyo Church at a community event". The earlier
captions on the old page were mismatched (e.g., Emily's headshot captioned as Josh preaching). **Pending moderators:** remove
"Regal Theater" — it's stored in `addressLine3`, which neither the owner dashboard nor the public suggest-edit form can edit;
submitted as an owner note via yelp.com Suggest an edit.

**Done on the old page `rVgGFgmFdc1T3c0fja9N_A` (2026-09-17):** Dakota deleted the 8 Arroyo photos, then Claude restored the
page with Dakota's OK: name → East Hills Church · address → 12000 Campus Dr, Oakland, CA 94619 · website → https://www.easthillschurch.com
(it 301s to arroyochurch.com) · Specialties and Meet the Manager → the original East Hills text · History → "Established 1987",
East Hills Community Church (formerly Melrose Baptist) → relaunched as Arroyo Church in Livermore in 2023. The phone stays
(925) 694-0426 because Yelp requires one. The hours still show Arroyo's office hours, because the original "Open 24 hours" wasn't
real. The page keeps its 7 reviews and 19 member photos.

**Moved request filed (2026-09-17):** yelp.com → Suggest an edit → Is this your business: Yes → Business Closed or Moved → Moved to
New Location → search "Arroyo Church" near Livermore, CA → Select the 945 Concannon page (`73urM3xpc70b8Og0olohgg`) · contact
av@arroyochurch.com · note (270 chars): the Oakland location closed, the church was renamed Arroyo Church (CA name amendment filed
Jan 2023) and meets at 945 Concannon Blvd, easthillschurch.com redirects to arroyochurch.com, and the selected page is the current
listing. Yelp accepted it for moderation, and the old page now shows "Yelpers report this location has closed" while it's reviewed.
**Watch for:** Yelp's email to av@. If the moderators merge the pages instead of closing the old one, the fallback is to report the
1-star review as a conflict of interest.

**Status 2026-09-18:** moderators removed "Regal Theater" — the Livermore page now reads 945 Concannon Blvd, Livermore, CA 94550
(phone 694-0426, 5.0 from 1 review, 8 photos) and Yelp re-slugged it to `arroyo-church-livermore-2`. The old page's title now
says CLOSED, its hours are hidden, and it still shows "Yelpers report this location has closed" with no "moved to" link, so Yelp
is treating it as closed rather than linking the two pages — fine for our purpose, and nothing was merged.

## 5c. Apple Business / Apple Maps (in progress)

Apple Maps' place card for Arroyo pulls reviews and photos from Yelp and showed the old (925) 642-1516 number. The fix is to verify
the church in Apple Business, then set the phone, hours and photos there.

- **Org verification:** the EIN was rejected ("business ID isn't recognized"), so we switched to domain validation plus the
  Venture Church Network group-exemption letter as the supporting document.
- **Domain verified 2026-09-17:** TXT record `apple-domain-verification=QBsg0osKnfMBx5sz` at host `@`, added under Squarespace
  Domains → arroyochurch.com → DNS → Custom records, then Apple Business → Settings → Domains → Verify → Check Records. Leave the
  record in place. The DNS lives in the domain owner's Squarespace account (Josh Smith's) — Dakota's own login gets "Access Denied"
  on the DNS page, and Squarespace makes the owner account re-confirm with Google before it will save a record. If this comes up
  again: **a domain-manager invite went to Dakota Yates / dakota@arroyochurch.com on 2026-09-17** (Domains → Permissions → Invite
  domain manager, sent from the owner account) and **accepted the same day** — dakota@arroyochurch.com now opens
  `account.squarespace.com/domains/managed/arroyochurch.com/dns/dns-settings` directly and can edit DNS without Josh. The domain
  doesn't show in that account's Domains list, so use the URL above. Note Squarespace re-asks the owner to confirm with Google before every protected action here.
- **Org verification sent 2026-09-17:** method 1 Domain Validation (arroyochurch.com), method 2 "Other" = the Venture Church
  Network group-exemption letter (`~/Desktop/IRS Letter Signed - 2025.pdf`) with a 467-character description covering the group
  exemption and the Jan 2023 name change. Apple shows the org as **In Review** (up to 5 business days) and emails the result to
  av@arroyochurch.com. Apple Organization ID 406431513582.
- **After verification:** phone → (925) 694-0426, hours, cover photo and current photos. Apple takes days to weeks to publish.
- **Blocked 2026-09-22 (case 102971677900):** deployment_support@apple.com wrote that the enrolling Apple Account's name must be
  a real person's name, not the church's. Fix at account.apple.com → Personal Information → Name (first + last) on
  av@arroyochurch.com, then reply to Sheldon on that case to restart the review. The organization name in Apple Business stays
  "Arroyo Church"; this is only the person's account name.
- **APPROVED 2026-09-28** (Sheldon, case 102971677900; org verified email the same morning). Place claimed the same day:
  Brands → Locations → Add → the existing "Arroyo Church, 945 Concannon Blvd" place (no new location), Apple location id
  **1554160566452356452**, brand "Arroyo Church" (owned, Church, https://www.arroyochurch.com). The claim took the "Done" path
  (no phone call to the old number). Location status **In Review, up to 5 days**. Set during the claim: website
  https://www.arroyochurch.com, hours Sun 10:00–11:30 AM · Mon closed · Tue–Fri 10:00 AM–4:00 PM · Sat closed (matches GBP + Yelp).
  After the claim: About text saved (483 chars, "Arroyo Church is a Bible-based Christian church in Livermore…"),
  logo uploaded (white river "A" on navy #0D2530, 1024², rendered from the arroyo-app glyph path) → In Review.
  **Locked until the location review clears:** Phone (still +1 925-642-1516 — change to 694-0426 first thing) and Actions.
  **Held for Dakota:** cover photo + gallery (the upload attests the church has rights from everyone pictured), Good to Know
  (Parking Lot / Nonprofit / Good for Kids ready; free parking + wheelchair access unconfirmed). Photo set, checked for kids/QR
  codes/trademarks/Apple minimums (cover ≥1600×1040, gallery ≥720×960, logo ≥1024²): session scratchpad `apple-photos/final-v2/`.
  Apple Business sessions expire quickly; Dakota has to sign back in (Claude never types Apple credentials).
- **Finished 2026-09-28 (after Dakota's OK):** cover photo (Sunday crowd outside the round building, 1904×1071, also set at brand
  level) and 9 gallery photos (worship from the back, band, Josh teaching, Connect Center, after-service group, welcome tent,
  building front, sanctuary, drone) — all "In Review, up to 3 days". The three 1280×720 building shots were refused ("smaller than
  720 x 960px") and re-sent as 1707×960 resizes. Good to Know: Wheelchair Accessible, Good for Kids, Nonprofit, Free
  Self-Parking, Parking Lot. Hours changed to **Sun 9:30–11:30 AM** on Apple, GBP (pending Google review ≤10 min; GBP's separate
  "Worship service" hours stay Sun 10:00–11:30) and the Yelp Livermore page (saved). Still waiting on Apple: location
  verification → then set phone to +1 925-694-0426 and consider Actions.
- **Status 2026-09-29:** Google (Sun 9:30–11:30 live, 5.0 / 52 reviews), Yelp Livermore page (Sun 9:30–11:30, 694, no Regal)
  and the site schema all agree. Apple location still "In Review" (sent 9/28, up to 5 days); the public Apple Maps card is
  unchanged (642-1516, no About/photos/logo yet). **Google Ads: advertiser verification due 2026-10-29 or the account pauses**
  (email to av@ 9/29; verification can take up to 7 business days — start it this week; any ID upload is Dakota's).
- **Branded Mail (Apple): not yet — decided 2026-09-29.** Apple needs DMARC p=quarantine/reject with pct=100 and DKIM on all
  mail; ours is `v=DMARC1; p=none` and there is NO SPF record. Only Google Workspace sends as @arroyochurch.com (DKIM d=
  arroyochurch.com passes); Planning Center sends from its own domains, so its mail would never be branded. The logo would show
  only on staff one-to-one mail read in iPhone Mail / iCloud web. Plan: (1) add TXT @ `v=spf1 include:_spf.google.com ~all`
  (keep the apple-domain-verification TXT); (2) set the single _dmarc TXT to `v=DMARC1; p=none; pct=100;
  rua=mailto:av@arroyochurch.com` (it's inside Squarespace's Email Campaigns preset — keep the squarespace._domainkey CNAME);
  (3) ask Josh what else sends as the domain; (4) ~2 weeks of clean reports → `p=quarantine`; (5) then Branded Mail. Steps 1–2
  await Dakota's go. Full research: workflow wf_f4bffad0-877 (session transcripts).
- **Done 2026-09-29 (Dakota's go):**
  - DNS (Squarespace Domains, saved as Dakota's domain-manager login after he entered Squarespace's emailed code): added TXT @
    `v=spf1 include:_spf.google.com ~all` (the apple-domain-verification TXT stays); removed the view-only "Squarespace Email
    Campaigns" preset and re-added its records as custom: CNAME `squarespace._domainkey` → `squarespace-domainkey.squarespace-mail.com`
    and TXT `_dmarc` = `v=DMARC1; p=none; pct=100; rua=mailto:av@arroyochurch.com`. Verified on the authoritative NS and 1.1.1.1;
    MX, A, Google DKIM and the site unchanged. Delivery unchanged (still p=none). DMARC aggregate reports now land in av@
    (receive-only mailbox — fine). **Next: read the reports ~2026-10-13; if only Google sends as the domain → p=quarantine → Branded Mail.**
    Josh confirmed (9/29): everything sends through Gmail except his **Squarespace Email Campaigns** newsletters (sender
    Josh Smith <josh@arroyochurch.com>, verified in Squarespace — no "verify" prompt; 20 sent, latest 9/12, about every 1–3 weeks).
    Squarespace signs them through the `squarespace._domainkey` CNAME (kept), and its DNS guide asks for no SPF include, so no DNS
    change is needed. **Gate before p=quarantine:** the DMARC reports must include at least one newsletter sent after 9/29 and show
    it passing DKIM aligned to arroyochurch.com; if Josh hasn't sent one by ~10/13, wait for his next send.
  - **DMARC report review done early, 2026-10-03** (22 reports, Sep 30–Oct 2; parsed files in the session scratchpad):
    - **Volume:** ~7 report emails a day. Senders: Yahoo (one per hosted domain: aol, att, sbcglobal, ymail, rocketmail…),
      Google, Comcast, Microsoft, GoDaddy, Mail.Ru, Amazon SES. Dakota asked to stop them on 10/3.
    - **Results:** 936 messages, 934 pass.
      - Google Workspace: 35/35 pass (DKIM `google` + SPF, both aligned).
      - **Josh's Squarespace newsletter went out Oct 1:** 891 deliveries (Mailgun 161.38.201.94/.95), all pass via aligned
        DKIM d=arroyochurch.com, selector `squarespace`. **The 9/29 gate is met.**
      - Forwarded copies: 8/8 pass.
    - **One unknown sender fails:** SendGrid 167.89.17.35 (rDNS o1.email.abusepreventionsystems.com), 2 messages with From
      @arroyochurch.com, signed only by abusepreventionsystems.com. Abuse Prevention Systems = **MinistrySafe** (child-safety
      training/background checks); likely a staff account sending invites "from" a church address.
    - **Under p=quarantine those emails would go to spam.** Before any quarantine/Branded Mail step: confirm with staff and
      change that sender's From (or set up its domain authentication).
    - **Recommendation:** drop `rua=` (stop the emails) and stay at p=none unless Branded Mail becomes worth it. Re-add `rua` for
      ~2 weeks before tightening.
    - **Done 2026-10-03 (Dakota's go; he entered Squarespace's emailed code):** `_dmarc` TXT changed to `v=DMARC1; p=none;
      pct=100` (rua removed). Verified on the authoritative NS (ns-cloud-d4.googledomains.com) and 8.8.8.8. 1.1.1.1 still had the
      old copy cached (TTL 4 h). SPF, MX, the `squarespace` and `google` DKIM records and the Apple verification TXT are unchanged.
      Reports already in flight (Yahoo/Microsoft run ~2 days behind) may trickle in through ~Oct 5–6, then stop. To re-enable,
      add `; rua=mailto:av@arroyochurch.com` back.
  - Google Ads advertiser verification submitted: EU political ads = No; Dun & Bradstreet task = legal name "Arroyo Church",
    945 Concannon Blvd, Livermore CA 94550-6482 (prefilled from the payments profile). The form also prefilled D-U-N-S
    145043643 of unknown origin (no public D&B record for Arroyo Church; Sunset Community Church is the only Livermore church
    D&B lists) — cleared it and submitted without, since it's optional. Required tasks done; Google review 1–10 days.
    Ad disclosure reads "Ads funded by Arroyo Church". Optional "confirm affiliation" task unlocks later.
- **Status 2026-09-30:** Apple approved the logo, cover and most gallery photos; one gallery photo came back "Not Approved".
  Signing in to Apple Business in Chrome was flaky (the SMS code to ••78 never arrived; Safari worked), and web sessions drop
  after ~30 min idle. Still to do on Apple once Dakota is signed in: phone → +1 (925) 694-0426, find and replace the rejected
  photo, About "about 55 minutes" → 70, and Josh's ask for a cover **with people** (pick: the baptism group waving on the lawn;
  more people shots for the gallery; skip any with a QR code or identifiable kids).
- **Apple done 2026-09-30 (later, Dakota signed in on Chrome):** location now **Verified**; Phone unlocked and set to
  +1 (925) 694-0426; About "about 55 minutes" → 70 (only that word); cover → the baptism group waving on the lawn (Josh asked for
  people; adults only, faces sit in the 2.5:1 crop band); 6 people photos added (couple outside, two friends at the entrance,
  two men waving in the lobby, three men talking outside, baptism in the dome, baptism on the lawn) → gallery 14. All "Sent for
  review on Sep 30" (≤5 business days). The rejected photo was `gallery-04-connect-center.jpg` ("Doesn't Meet Standards"; a big
  "Connect Center" banner + church logo in frame); Apple removed it itself. Skip frames dominated by signs/logos. The Oct 3
  scheduled check now verifies all of this instead of editing.
- **Apple Action added 2026-09-30 (Dakota's go):** primary action **Services** →
  `https://www.arroyochurch.com/plan-your-visit?utm_source=apple&utm_medium=organic&utm_campaign=apple_maps` (Apple review ≤3
  days). Apple offers no "Plan a visit"/"Learn more" label — the church category's list is Schedule, Services, Availability,
  Quote, Tickets, Activities, Pricing, Shows, Events, Parking, Careers, Gift Card. "Services" reads as worship services on a
  church card, and the page answers that (Sunday 10 AM, what to expect, save-a-seat form). Apple's Action URL guidelines allow
  UTM parameters (and `source=Apple Maps`); they ban GCLID, SSO/login trackers and tokens. In GA4, Apple Maps visits show as
  source `apple` / medium `organic` / campaign `apple_maps`. (Precedent: Local Church, Holtsville NY, a claimed church, uses
  the same "Services" action → its /planyourvisit page.)
- **Apple Maps ratings — researched 2026-09-30 (workflow wf_d592c082-23c, 4 research angles + 2 adversarial checks):**
  Apple's own ratings are thumbs up/down per category (no written reviews from Apple; written Yelp snippets can still appear).
  Churches CAN carry Apple ratings (verified on Local Church, Holtsville NY: 100% from 4; Notre Dame Church, North Caldwell NJ:
  100% from 1) but it's rare. Most Tri-Valley churches show Yelp or nothing. Arroyo's card shows no ratings at all right now.
  No Apple setting turns ratings on or off, and Insights shows no ratings. Apple publishes no minimum count (web cards show from
  1). How Apple picks Apple vs Yelp is undocumented. Apple is matched to the new Livermore Yelp page but shows no Yelp stars;
  don't promise they'll return. Rating happens in the Maps app (iPhone/iPad/Mac), not on maps.apple.com: iOS 26+ → the
  thumbs-up button on the card; older iOS/Mac → "Rate". There's no link that opens the rating sheet directly. Third-party
  reports (9to5Mac 2020, MacRumors 2021) say Apple may only offer rating to people who have been there; Apple doesn't confirm.
  **Our Apple Business showcase Action list includes "Rate Us"** (also Add to Favorites, Add to Guide, Call Now, Get
  Directions, More Info, Save as Contact, Services, Share This Place). It opens Apple's Rate this Place sheet. Not created.
  Rules: asking plainly is fine, but no rewards/raffles for ratings (Apple Business Terms ban incentives) and never ask for Yelp
  reviews (Yelp's "Don't Ask for Reviews" policy; it filters solicited reviews).
- **Check 2026-10-01:**
  - **Dakota's iPhone, in the Maps app:** Arroyo's card has no thumbs-up. The ••• menu has Directions, Call, Website, Delete
    from Places, Add to Guides, Add a Note, Favorite, Pin, Download Map, Share and Report an Issue, but **no "Add Your Photos"**.
    Apple's iOS 26 guide: you rate with the Like button, add photos via ••• → Add Your Photos, and "If you don't see ratings
    categories or the Rate button, you can't rate the location… you can't add a photo." So his phone isn't offered rating
    for Arroyo. The link from chat had opened the maps.apple.com web card, which never has rating controls.
  - **Category is not the gate:** across 184 religious place cards pulled from Apple's public data, 19 carry Apple ratings,
    including US churches with categories like ours (Holy Apostles NYC; Grace Cathedral SF; Notre Dame Church NJ and Local
    Church NY also have `nonprofit_organization`).
  - **Still unknown:** whether the block is his phone (visit history or settings) or our listing. Control test: open Costco
    Livermore (Apple rating 84% from 134) in Maps → ••• → is "Add Your Photos" there? If yes there but not for us, it's our
    listing (ask Apple Business support). If no, it's the phone (retest at church on Sunday).
  - **Public card (maps.apple.com data):** the new cover, (925) 694-0426, About "70 minutes" and 10 owner photos are live. Not
    live: the Services action (QUICK_LINK = 0, in review) and **hours** (BUSINESS_HOURS = 0, even though set in Apple Business;
    Local Church's card has no hours either, Trinity NYC's does). Apple still stores the old 642-1516 as `altTelephone`; the
    main phone is right.
  - **Rate Us showcase:** Dakota said yes; not built yet because Apple Business signed out. Hold it if the control test shows
    Arroyo-specific blocking.
  - **Control test result (same day):** Dakota's phone CAN rate. Costco Livermore's card shows a "Rate This Place — Visited 2
    weeks ago" row with thumbs up/down, a thumbs-up in the bottom bar (+ ☆ 👍 •••) and "Add Photos" in •••. Arroyo shows none
    of these, even though he's there every Sunday. So Apple isn't offering rating for our listing. The maps.apple.com data
    doesn't say why: our layout has the same rating/questionnaire modules as Costco and the rated churches, so the decision is
    made server-side when the app asks. Possible causes, unconfirmed: Apple holds rating while the location is "In Review", or
    Maps' visit history skips places of worship (a sensitive category), so the visit-based "Rate This Place" never appears for a
    church. **Decision:** build the Rate Us showcase anyway (Dakota's yes) as the real test. If Apple approves it and the card
    shows a working "Rate this Place" button, announce it. If the button reverts to a Maps default, rating is off for our
    listing → swap the showcase to a plan-your-visit message and ask Apple Business support (Dakota's OK before sending).
  - **Showcase submitted 2026-10-01 (id 1828880345077909452, status In Review):**
    - Heading: "Been to Arroyo on a Sunday?"
    - Body: "If you felt welcome here, give us a thumbs-up. It helps neighbors find a church home."
    - Photo: the two men waving at the entrance (G4, from the Asset Gallery; square crop). Alt text: "Two Arroyo Church members
      smiling and waving hello at the church entrance".
    - Action: Rate Us, which the list shows as **"Recommend This Place"** (internal value RATE_THIS_PLACE).
    - Runs 10/02/2026–11/30/2026, leaving December open for a Christmas Eve showcase. Apple: "generally published within 15
      minutes, but it may take up to 3 days".
    - Gotchas: a start date of today fails with "Showcase must provide sufficient lead time", so start tomorrow at the earliest.
      After Save the app bounced to the empty /showcases/welcome page, and the showcase only appeared in the Scheduled list on a
      reload a minute later.
    - **To check once it's live:** on an iPhone, does Arroyo's card show the showcase with a working Recommend/Rate button?
- **Service length is ~70 minutes (Josh, 2026-09-30).** Changed everywhere it appeared: the site footer (5 lines, commit 4340984;
  the first save that day did NOT persist, so it was redeployed and checked with curl), the /plan-your-visit FAQ accordion, the
  scheduled "What to Wear to Church" post (Oct 3, 7 AM; only "55" → "70" changed in place, still Scheduled, same author/URL), and
  the GBP "What to expect" post (Pending while Google reviews the edit). No other copy mentions a length: the GBP description,
  the Yelp page, all 40 published posts and all 29 scheduled/draft posts are clean. Apple's About was changed the same day.
- **Site schema aligned 2026-09-28 (Dakota's explicit go):** HEADER code injection (Church JSON-LD) Sunday `closes` 12:00 → 11:30,
  a 2-character in-place edit (opens was already 09:30). Verified live on / and /plan-your-visit; footer untouched. Every listing
  and the site now agree: Sun 9:30–11:30 AM, Tue–Fri 10–4 office hours, Mon/Sat closed, (925) 694-0426.
- **Fixed 2026-09-23:** the Apple Account was named "Arroyo Church" (First: Arroyo / Last: Church). Changed at account.apple.com →
  Personal Information → Name to **Dakota Yates**, and replied to case 102971677900 from av@ asking Apple to continue the review.
- **Check 2026-09-23:** Apple Maps has DROPPED the Yelp ratings block — no 4.4 (7), no 1-star review on the card. Two
  Yelp-sourced photo tiles remain and the phone still reads (925) 642-1516, which the claimed place card will fix.
- **Check 2026-09-18:** no decision email yet (only "verification is in review", Sep 17). The Apple Maps card (place id
  `IBF83C24354FA29B3`) is unchanged: phone (925) 642-1516, Yelp 4.4 (7) with the 1-star, and its Yelp rating links to
  `yelp.com/biz/rVgGFgmFdc1T3c0fja9N_A` — Apple is still matched to the old, now-closed page until it re-reads Yelp.

## 6. Copy bank

**Q&A seeds**
- What time is the Sunday service? — Sundays at 10:00 AM. Doors open at 9:30. It runs about 70 minutes.
- Is there something for kids? — Yes. Kids ministry meets during the Sunday service. Check in at the kids desk when you arrive.
- What should I wear? — Whatever you're comfortable in. Most people are casual.
- Where do I park? — Free parking on site at 945 Concannon Blvd. The worship center is the round building.
- What denomination is Arroyo Church? — Non-denominational Christian church, centered on knowing and showing the love of Jesus.
- Can I watch online? — Yes. Sundays at 10 AM at youtube.com/@arroyochurch/live; past messages are on the channel.
- How long is the service? — About 70 minutes.

**First three posts**
1. Sermon recap (Monday): "This Sunday, Pastor Josh [title]. Missed it? Watch the full message: [YouTube link]. Join us next Sunday at 10 AM — 945 Concannon Blvd." Button: Learn more → sermon URL.
2. What to expect: "New to Arroyo? Sundays at 10 AM, about 70 minutes, kids ministry during service, free parking. Come as you are. Plan your visit and we'll save you a seat." Button: Sign up → /plan-your-visit.
3. Connect groups: "You were created for community. Connect groups meet all week — men, women, couples, moms, young adults, students. Find yours." Button: Learn more → /connect.

## 7. Maintenance
- Update this file when accounts are created (add account IDs), when the grant is approved, and when bidding changes.
- Decision to log: 2026-09-09 — all Google properties consolidated under av@arroyochurch.com; paid Ads is a $125/mo top-slot test, Ad Grant is the volume lever.

### 2026-09-11 — the ad landing page had no form (fixed)
Dakota checked the live ad URL and found `/plan-your-visit` had **no Plan-a-Visit form**. Cause: the page
hid Squarespace's native form block and pointed visitors at the home-page form instead, and that CTA
rendered as plain text because `.btn-gold` is scoped to `.ac-sec`, which interior pages don't have. Every
paid click was landing on a page with nothing to fill in.

Fixed in `squarespace/footer-injection.html` (commits 1e8e9e3 + 781b634, both deployed):
- `buildVisitPageForm()` inserts the REAL form inline, same markup and same `wireVisitForm` submit path as
  the home page, source `visit_page` → Worker → **Planning Center form 1216871**, labelled "Plan Your Visit page".
- Verified the routing without creating a junk record: a POST with `source: visit_page` and a malformed
  email returns `error:"email"` (reached the visit form, phone optional), while a bogus source returns
  `error:"missing"` (fell through to Next Steps). The two differ, so the token resolves correctly.
- **Conversion gap also fixed:** `acTrack`'s event map had no `visit_page` (nor `events_rsvp`), so both fell
  through to `form_submit`, which does NOT fire the Google Ads conversion — only `plan_visit_submit` and
  `join_group_submit` do. A paid click that filled the form reached Planning Center but counted as zero
  conversions, on the exact page the ads point at. Both sources now map to `plan_visit_submit`.
- Checked live on desktop and at 390px: form renders, fields stack full width, nothing overflows, no
  console errors, native block hidden, one copy only, bottom CTA anchors to `#ac-visit-form`.

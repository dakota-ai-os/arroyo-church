// Auto-sync the church's PUBLIC events from Planning Center Calendar into data/events.json.
//
// Runs in GitHub Actions (Node 20+), every 30 minutes (.github/workflows/sync-events.yml). Staff enter an
// event in PC Calendar and set Settings > Church Center > Visibility = Published (Featured also works);
// the next run puts it on arroyochurch.com/events and the home page's "Coming up" strip.
//
// THE REPO IS PUBLIC, so data/events.json is public. The token belongs to an admin, so the API hands
// back private events too (baby showers, leader trainings, internal dinners). Everything below exists
// to make sure only Church Center events ever reach the file, and the Action log prints counts and the
// names of kept (public) events only — never anything about a dropped one.
//
// Auth: a Personal Access Token as HTTP Basic (Application ID = username, Secret = password), from the
// Actions secrets PC_EVENTS_APP_ID + PC_EVENTS_SECRET. Missing secrets = log it and exit 0 without
// touching the file. Any API error, or a response that does not look like the documented shape, stops
// WITHOUT writing, so the last-good JSON stays (same rule as sync-youtube.mjs). PC being down (network,
// 5xx, rate limit after retries) exits 0 with a warning; anything a human must fix (401/403, other 4xx,
// a changed response shape) exits 1. A clean answer with zero public events IS written: un-publishing
// an event in PC must take it off the site.
//
// API: https://api.planningcenteronline.com/calendar/v2 (JSON:API), docs at
// https://api.planningcenteronline.com/calendar/v2/documentation (vertices "event", "event_instance",
// "event_time"). Pinned to X-PCO-API-Version 2026-06-22, the newest stable (non-beta) version. Every
// field used here is in it; 2022-07-07 is the version that made recurrence_description the long human
// text (the old short one became compact_recurrence_description), so nothing older is safe. 2026-10-19
// is beta: do not use.
//
// PUBLIC FILTER (kept only if ALL hold; the first three also go to the server as where[] params, and
// are checked again here, so a param the server ignores can never leak anything):
//   Event.visible_in_church_center === true   "true indicates the event Church Center visibility is set
//                                             to 'Published'; false ... 'Hidden'"
//   Event.link_only === false                 "true indicates the event is published to Church Center
//                                             through the link only"
//   EventInstance.kind === 'standard'         "The type of event: standard or blockout. Only available
//                                             when requested with the ?fields param" (so we ask for it)
//   its event request is NOT pending/rejected PC: until an approver approves an event request, "that
//                                             event cannot be shared publicly to iCal feeds, kiosks, or
//                                             Church Center" (planningcenter.com/changelog/calendar/
//                                             8952772301723-new-event-request-forms). A second query with
//                                             the documented scope `event_request_pending_rejected`
//                                             ("filter to instances whose event is pending or rejected")
//                                             lists them; every instance AND event it returns is dropped.
//                                             If that query fails, nothing is written.
// Missing or null counts as a fail. NOT used: Event.approval_status (A/P/R). The docs do not say what it
// approves, and the list endpoint's scopes split "approved" ("instances whose rooms and resources are
// approved") from "event_request_approved" ("instances whose event is approved"); the event-request
// scope is the one that matches Church Center.
//
// Output, sorted by start (times are ISO UTC; format them in America/Los_Angeles):
//   { updated, events: [ { id, eventId, name, summary, description, starts, ends, allDay, location, image,
//                          url, registerUrl, featured, recurrence, ics } ] }
//   One row per INSTANCE (id = instance id; instances of one event share eventId). The site folds rows
//   with the same name + time of day into one card with "More dates" (acEvFold in footer-injection.html).
//   A recurring series keeps only its next SERIES_ROWS instances (the next one + 3 more dates, all the
//   card shows), so 24 monthly Connect Classes are 4 rows; a multi-date event with no recurrence (say
//   Foundations class on Nov 1, Nov 15, Dec 6) keeps every date, up to ONE_OFF_ROWS.
//   starts/ends the PUBLIC times, from ONE source (see publicTimes): published_starts_at/_ends_at when
//               they carry an explicit UTC offset and sit inside the scheduled span, else the instance's
//               widget-visible EventTimes, else starts_at/ends_at. ends is null when missing or equal
//   summary     plain text (Event.summary, else the rich description with the HTML stripped), capped
//               at ~600 chars, or null. It is TEXT: render it with textContent, never innerHTML.
//   description the Church Center description in full, as plain TEXT (see descriptionText): the instance's
//               `description`, else the event's — both documented as "A rich text public-facing summary of the
//               event" (the instance one "Only available when requested with the ?fields param", so it is in
//               INSTANCE_FIELDS). Paragraphs are separated by a blank line, list items start "• ", a link keeps
//               its text plus "(https://…)" (http/https only), capped at ~3000 chars, or null. The site's
//               event details panel renders it with textContent (footer-injection.html, acEvDescNodes).
//   location    the instance's own location text, or null
//   image/url/registerUrl  http(s) URLs only, else null. url = the Church Center event page
//   recurrence  the API's recurrence description ("Monthly on the 4th Sunday"), or null
//   ics         "data/events/ics/<id>.ics", the row's calendar file (see CALENDAR FILES below), or null
// Window: instances starting in the next ~6 months (WINDOW_DAYS).
//
// The file is rewritten only when the events change ("updated" = when they last changed), so the Action
// does not commit every 30 minutes. If PC image URLs turn out to be signed (expires_at / signature
// params), a new signature alone does not count as a change. A stored URL near its expiry is replaced
// only when PC now hands out one that lasts meaningfully longer, so a URL that expires on a fixed
// boundary can never make the Action commit on every run.
//
// CALENDAR FILES (RFC 5545), written beside data/events.json on every successful run (see writeCalendars):
//   data/events/ics/<row id>.ics  one event each; the site's "Add to calendar" > Apple / Other link. It has to be a hosted
//                                 https file (iOS Safari will not open a data: URI), and GitHub Pages serves .ics as
//                                 text/calendar, so iPhone and Mac Safari open "Add to Calendar".
//   data/events.ics               every row, a feed people subscribe to (webcal://...). Their calendar app re-reads it on
//                                 its own schedule (REFRESH-INTERVAL / X-PUBLISHED-TTL are only hints) and so picks up edits
//                                 and un-publishing. It holds upcoming rows only: an event leaves it (and subscribers'
//                                 calendars) once it ends.
// Each is rewritten only when its bytes change, and a row that is no longer public loses its file.
//
// Test: node scripts/test-sync-events.mjs (fixture responses, no network, no token).

import { readFileSync, writeFileSync, renameSync, mkdirSync, readdirSync, unlinkSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const API = 'https://api.planningcenteronline.com/calendar/v2';
export const API_VERSION = '2026-06-22';
export const WINDOW_DAYS = 183;
export const SERIES_ROWS = 4;    // a recurring series: the next instance + 3 more dates
export const ONE_OFF_ROWS = 12;  // a multi-date event with no recurrence: every date, up to this
const DAY = 86400000;
const HOUR = 3600000;
const PER_PAGE = 100;            // the documented maximum
const MAX_PAGES = 25;            // 2,500 instances; far past anything real, stops a runaway loop
const SUMMARY_MAX = 600;
const DESCRIPTION_MAX = 3000;
const SLACK = 60000;             // rounding allowance when checking public times against the schedule
const REFRESH_BEFORE = 12 * HOUR; // a stored signed image URL this close to expiring may be replaced...
const REFRESH_GAIN = HOUR;       // ...but only by one that lasts at least this much longer
const OUT_FILE = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'data', 'events.json');
export const HELD_BACK_SCOPE = 'event_request_pending_rejected';

// Sparse fieldsets. kind, image_url and description only come back when asked for by name, and once
// fields[EventInstance] is sent, ONLY the listed fields (and relationships) come back, so these lists
// are the whole contract.
const INSTANCE_FIELDS = [
  'all_day_event', 'church_center_url', 'compact_recurrence_description', 'description', 'ends_at',
  'image_url', 'kind', 'location', 'name', 'published_ends_at', 'published_starts_at', 'recurrence',
  'recurrence_description', 'starts_at', 'event', 'event_times',
];
const EVENT_FIELDS = [
  'name', 'summary', 'description', 'image_url', 'registration_url', 'featured',
  'visible_in_church_center', 'link_only',
];
const TIME_FIELDS = ['starts_at', 'ends_at', 'visible_on_widget_and_ical'];

// ---- fetch ----

// The main query (heldBack false) or the pending/rejected event-request query (heldBack true). Both use
// the same window and where[] params; the held-back one only needs ids.
export function firstPageUrl(now, { heldBack = false } = {}) {
  const q = new URLSearchParams({
    filter: heldBack ? 'future,' + HELD_BACK_SCOPE : 'future',
    order: 'starts_at',
    per_page: String(PER_PAGE),
    'where[starts_at][lte]': iso(now.getTime() + WINDOW_DAYS * DAY),
    'where[kind]': 'standard',
    'where[event][visible_in_church_center]': 'true',
    'where[event][link_only]': 'false',
  });
  if (heldBack) {
    q.set('fields[EventInstance]', 'event');
  } else {
    q.set('include', 'event,event_times');
    q.set('fields[EventInstance]', INSTANCE_FIELDS.join(','));
    q.set('fields[Event]', EVENT_FIELDS.join(','));
    q.set('fields[EventTime]', TIME_FIELDS.join(','));
  }
  return API + '/event_instances?' + q;
}

const wait = ms => new Promise(r => setTimeout(r, ms));

// transient = PC is down or busy (retrying later is the fix); anything else needs a human
function pcError(message, transient) {
  const e = new Error(message);
  e.transient = transient;
  return e;
}

async function errorDetail(r) {
  try {
    const e = ((await r.json()).errors || [])[0] || {};
    const t = [e.title, e.detail].filter(Boolean).join(': ');
    return t ? ' (' + t + ')' : '';
  } catch {
    return '';
  }
}

async function getJson(url, { fetchImpl, auth, sleep }) {
  for (let attempt = 1; ; attempt++) {
    let r;
    try {
      r = await fetchImpl(url, {
        headers: { Authorization: auth, Accept: 'application/json', 'X-PCO-API-Version': API_VERSION },
      });
    } catch (e) {
      if (attempt < 3) { await sleep(2000 * attempt); continue; }
      throw pcError('network error talking to Planning Center: ' + e.message, true);
    }
    if (r.ok) return r.json();
    // 429 = rate limit (PC sends Retry-After), 5xx = their side; both are worth a short retry
    const busy = r.status === 429 || r.status >= 500;
    if (busy && attempt < 3) {
      const secs = Number(r.headers?.get?.('retry-after')) || 2 * attempt;
      await sleep(Math.min(secs, 30) * 1000);
      continue;
    }
    const hint = r.status === 401 || r.status === 403 ? ' — check the PC_EVENTS_APP_ID / PC_EVENTS_SECRET secrets' : '';
    throw pcError('Planning Center answered ' + r.status + (await errorDetail(r)) + hint, busy);
  }
}

// Every page of one query, plus a map of the included resources ("Event:<id>" -> resource).
async function fetchPages(url, { fetchImpl, auth, sleep }) {
  const data = [];
  const included = new Map();
  let pages = 0;
  while (url) {
    // the credentials go with every request, so never follow a link anywhere but the Calendar API
    if (!url.startsWith(API + '/')) throw pcError('refusing to follow a next link outside ' + API, false);
    if (++pages > MAX_PAGES) throw pcError('more than ' + MAX_PAGES + ' pages of instances; stopping', false);
    const body = await getJson(url, { fetchImpl, auth, sleep });
    if (!body || !Array.isArray(body.data)) throw pcError('unexpected response: no data array', false);
    data.push(...body.data);
    for (const r of body.included || []) if (r && r.type && r.id != null) included.set(r.type + ':' + r.id, r);
    url = body.links?.next || null;
  }
  return { data, included, pages };
}

export function fetchInstances({ fetchImpl = fetch, auth, now = new Date(), sleep = wait }) {
  return fetchPages(firstPageUrl(now), { fetchImpl, auth, sleep });
}

// Instances (and their events) whose event request is pending or rejected. Church Center hides them.
export async function fetchHeldBack({ fetchImpl = fetch, auth, now = new Date(), sleep = wait }) {
  const { data } = await fetchPages(firstPageUrl(now, { heldBack: true }), { fetchImpl, auth, sleep });
  const instanceIds = new Set();
  const eventIds = new Set();
  for (const i of data) {
    if (i?.type !== 'EventInstance' || i.id == null) throw pcError('held-back query: unexpected resource', false);
    instanceIds.add(String(i.id));
    const ref = i.relationships?.event?.data;
    if (ref && ref.id != null) eventIds.add(String(ref.id));
  }
  return { instanceIds, eventIds };
}

// The filter is only as good as the fields it reads, so a response that is not the documented shape
// stops the run (keeping last-good) rather than quietly writing a short or empty list. A requested field
// comes back on every resource (null when empty); one without it means PC dropped the fieldset (say, on
// a next-page link). Every instance must point at an event that came back in `included`: the server's
// where[] params mean each one should be public, so a missing one is a broken response, not a filter.
export function checkShape(data, included) {
  for (const i of data) {
    if (i?.type !== 'EventInstance') throw pcError('unexpected resource type in the instance list', false);
    if (!i.attributes || !('kind' in i.attributes)) {
      throw pcError('instances came back without `kind` (fields[EventInstance] not honored?)', false);
    }
    const ref = i.relationships?.event?.data;
    if (!ref || ref.type !== 'Event' || ref.id == null) {
      throw pcError('an instance came back without its event relationship', false);
    }
    const e = included.get('Event:' + ref.id);
    if (!e) throw pcError('an instance\'s event is missing from `included` (include=event not honored?)', false);
    if (!e.attributes || !('visible_in_church_center' in e.attributes) || !('link_only' in e.attributes)) {
      throw pcError('events came back without their visibility fields (fields[Event] not honored?)', false);
    }
  }
}

// ---- the public filter (see the header for the doc wording) ----

export function isPublic(instance, event) {
  const a = instance?.attributes || {};
  const e = event?.attributes || {};
  return !!event
    && e.visible_in_church_center === true
    && e.link_only === false
    && a.kind === 'standard';
}

// ---- shaping ----

function clean(s) {
  if (typeof s !== 'string') return null;
  const t = s.replace(/\s+/g, ' ').trim();
  return t || null;
}

// PC's saved locations come back with a space before each comma ("Arroyo Church  - 945 Concannon Blvd. , Livermore , CA").
// The church's own saved location becomes plain "Arroyo Church": the panel adds the street address under that name and
// icsLocation expands it, so keeping PC's copy showed the address twice.
export const cleanLocation = s => {
  const t = clean(s);
  if (t && /^arroyo church\b/i.test(t) && /\b945 concannon\b/i.test(t)) return 'Arroyo Church';
  return t && t.replace(/ ,/g, ',');
};

const iso = t => new Date(t).toISOString().replace(/\.000Z$/, 'Z');

// A timestamp with an explicit zone ("…Z" / "…-07:00" / "…-0700") -> ms; anything else -> null. A
// wall-clock value with no zone would be read in the machine's own zone (UTC on Actions, Pacific on a
// Mac), so it is never trusted.
export function utcTime(s) {
  if (typeof s !== 'string') return null;
  const v = s.trim();
  if (!/^\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d(\.\d+)?)?(Z|[+-]\d\d:?\d\d)$/i.test(v)) return null;
  const t = Date.parse(v.replace(/([+-]\d\d)(\d\d)$/, '$1:$2'));
  return isNaN(t) ? null : t;
}

// The times Church Center shows, from ONE source so a start and an end never mix:
//   1. published_starts_at / published_ends_at — documented only as "Publicly visible start/end time"
//      (type string, unlike starts_at's "UTC time ..."), so used only with an explicit zone, and only
//      inside [starts_at, ends_at] (public times are part of the scheduled span, which can include
//      setup and teardown)
//   2. the instance's EventTimes with visible_on_widget_and_ical === true (documented UTC), earliest
//      start to latest end, held to the same span
//   3. starts_at / ends_at ("UTC time at which the event instance starts/ends")
export function publicTimes(a, eventTimes = []) {
  const s = utcTime(a.starts_at);
  const e = utcTime(a.ends_at);
  const fits = (x, y) => s !== null && x !== null && x >= s - SLACK && (e === null || x <= e + SLACK)
    && (y === null || (y >= x && (e === null || y <= e + SLACK)));
  const pick = (x, y, source) => ({ starts: x, ends: y !== null && y > x ? y : null, source });

  const ps = utcTime(a.published_starts_at);
  const pe = utcTime(a.published_ends_at);
  const peUnreadable = clean(a.published_ends_at) !== null && pe === null;
  if (ps !== null && !peUnreadable && fits(ps, pe)) return pick(ps, pe, 'published');

  const vis = eventTimes.filter(t => t.visible === true);
  if (vis.length && vis.every(t => t.starts !== null && (t.endsRaw === null || t.ends !== null))) {
    const vs = Math.min(...vis.map(t => t.starts));
    const ends = vis.map(t => t.ends).filter(x => x !== null);
    const ve = ends.length ? Math.max(...ends) : null;
    if (fits(vs, ve)) return pick(vs, ve, 'times');
  }

  return s === null ? null : pick(s, e, 'scheduled');
}

function eventTimesOf(instance, included) {
  const refs = instance.relationships?.event_times?.data;
  if (!Array.isArray(refs)) return [];
  return refs.map(r => included.get('EventTime:' + r?.id)).filter(Boolean).map(t => {
    const x = t.attributes || {};
    return {
      visible: x.visible_on_widget_and_ical,
      starts: utcTime(x.starts_at),
      ends: utcTime(x.ends_at),
      endsRaw: clean(x.ends_at),
    };
  });
}

// http(s) only: a staff-typed "javascript:" link must never become an href on the site
function httpUrl(u) {
  const s = clean(u);
  if (!s || /\s/.test(s)) return null;
  if (/^https?:\/\//i.test(s)) return s;
  if (/^(www\.)?[a-z0-9-]+(\.[a-z0-9-]+)+([/?#]|$)/i.test(s)) return 'https://' + s; // "example.com/x"
  return null;
}

// The named entities a rich-text editor writes: all of Latin-1 (U+00A0-U+00FF, in code-point order: &eacute; &deg;
// &frac12; &laquo; ...) plus the common typography and symbols. Case matters (&Eacute; vs &eacute;); a name that only
// matches in lower case falls back to it (&AMP;). No prototype, so "&constructor;" stays text. Anything else stays as typed.
const LATIN1 = ('nbsp iexcl cent pound curren yen brvbar sect uml copy ordf laquo not shy reg macr deg plusmn sup2 sup3 acute '
  + 'micro para middot cedil sup1 ordm raquo frac14 frac12 frac34 iquest Agrave Aacute Acirc Atilde Auml Aring AElig Ccedil '
  + 'Egrave Eacute Ecirc Euml Igrave Iacute Icirc Iuml ETH Ntilde Ograve Oacute Ocirc Otilde Ouml times Oslash Ugrave Uacute '
  + 'Ucirc Uuml Yacute THORN szlig agrave aacute acirc atilde auml aring aelig ccedil egrave eacute ecirc euml igrave iacute '
  + 'icirc iuml eth ntilde ograve oacute ocirc otilde ouml divide oslash ugrave uacute ucirc uuml yacute thorn yuml').split(' ');
const ENTITIES = Object.assign(Object.create(null), Object.fromEntries(LATIN1.map((k, i) => [k, String.fromCharCode(0xA0 + i)])), {
  amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', shy: '',
  ndash: '–', mdash: '—', hellip: '…', lsquo: '‘', rsquo: '’', sbquo: '‚', ldquo: '“',
  rdquo: '”', bdquo: '„', lsaquo: '‹', rsaquo: '›', bull: '•', prime: '′', Prime: '″',
  dagger: '†', Dagger: '‡', permil: '‰', frasl: '⁄', euro: '€', trade: '™',
  ensp: '\u2002', emsp: '\u2003', thinsp: '\u2009', zwnj: '\u200C', zwj: '\u200D', lrm: '\u200E', rlm: '\u200F',
  OElig: 'Œ', oelig: 'œ', Scaron: 'Š', scaron: 'š', Yuml: 'Ÿ', fnof: 'ƒ', circ: 'ˆ',
  tilde: '˜', minus: '−', le: '≤', ge: '≥', ne: '≠', asymp: '≈', infin: '∞',
  larr: '←', rarr: '→', uarr: '↑', darr: '↓', harr: '↔', hearts: '♥', star: '☆',
  check: '✓', cross: '✗', starf: '★',
});

function decodeEntities(s) {
  return s.replace(/&(#x[0-9a-f]+|#\d+|[a-z][a-z0-9]*);/gi, (m, k) => {
    if (k[0] === '#') {
      const n = k[1] === 'x' || k[1] === 'X' ? parseInt(k.slice(2), 16) : parseInt(k.slice(1), 10);
      return n > 0 && n <= 0x10ffff && (n < 0xD800 || n > 0xDFFF) ? String.fromCodePoint(n) : ''; // no lone surrogate
    }
    return ENTITIES[k] ?? ENTITIES[k.toLowerCase()] ?? m;
  });
}

// Rich text -> plain text: one line per paragraph / break / list item.
export function plainText(html) {
  if (typeof html !== 'string') return null;
  const t = decodeEntities(html
    .replace(/<(script|style)\b[\s\S]*?<\/\1\s*>/gi, ' ')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(p|div|li|h[1-6]|blockquote|tr)\s*>/gi, '\n')
    .replace(/<[^>]*>/g, ''))
    .split('\n')
    .map(line => line.replace(/[^\S\n]+/g, ' ').trim())
    .filter(Boolean)
    .join('\n');
  return t || null;
}

function cap(s, n) {
  if (!s || s.length <= n) return s;
  const cut = s.slice(0, n);
  const at = cut.lastIndexOf(' ');
  return (at > n * 0.6 ? cut.slice(0, at) : cut).replace(/[\s,;:.–—-]+$/, '') + '…';
}

// The Church Center description (rich text = HTML) -> plain text the site renders with textContent and a calendar file can
// carry. Only the markup's text and shape survive:
//   - script / style / template / noscript / iframe / object / svg / math / head / title / textarea / select are dropped
//     WITH their content (an unclosed one drops everything after it), and so are comments; every other tag is removed and
//     its text kept
//   - <p>, <div>, headings, <blockquote>, <ul>/<ol>, <dl>, <pre>, <table>, <hr>, ... = a paragraph break (one blank line);
//     <br>, <dt>/<dd> and the end of a table row = a line break (two <br>s in a row = a blank line, the way Trix-style
//     editors write a paragraph); a <pre> keeps its own line breaks
//   - <li> = a line starting "• "; a break or paragraph inside one item is a space, so the item stays one line
//   - <a href="https://…">text</a> = "text (https://…)", or just the URL when the text is the URL; a link to anything but
//     http(s) (mailto:, tel:, javascript:, a relative path) keeps its text only
//   - a ">" or "<" inside a quoted attribute value (title="a > b") is not the end of the tag
//   - entities decoded exactly once ("&amp;lt;" stays the text "&lt;"), spaces collapsed, zero-width spaces dropped
//   - capped at DESCRIPTION_MAX on a line or word boundary ("…"); null when nothing is left
// A string with no markup at all keeps its own line breaks; its entities are decoded too (PC stores rich text, so a
// typed "&" arrives as "&amp;" with or without tags around it).
const DROPPED = 'script|style|template|noscript|iframe|object|svg|math|head|title|textarea|select';
const DROP_BLOCK = new RegExp('<(' + DROPPED + ')\\b[^>]*>[\\s\\S]*?<\\/\\1\\s*>', 'gi');
const DROP_REST = new RegExp('<(' + DROPPED + ')\\b[\\s\\S]*$', 'i');
// a tag with its quoted values whole; one way to match, and bounded so a run of broken tags stays fast
const QUOTED_TAG = /<[a-z](?:[^>"']|"[^"]{0,8192}"|'[^']{0,8192}'){0,1024}>/gi;
const LINK = /<a\b([^>]*)>([\s\S]*?)<\/a\s*>/gi;
const ATTR = /([^\s"'>\/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?/g;  // name[=value], one at a time
const TAG = /<\/?[a-z][^>]*>|<![^>]*>|<\?[^>]*>/gi;                      // a lone "<" in text ("ages 3 < 5") is not a tag
const BLOCK = /<\/?(p|div|h[1-6]|blockquote|ul|ol|dl|pre|table|thead|tbody|tfoot|caption|section|article|header|footer|aside|nav|main|address|details|summary|figure|figcaption|fieldset|center|hr)\b[^>]*>/gi;
const IN_ITEM = /<li\b[^>]*>[\s\S]*?(?=<\/li\s*>|<li\b|<\/?(?:ul|ol)\b|$)/gi;      // one list item's own content
const MARK = /[\uE000\uE001]/g;                                           // private-use: stand-ins for links while tags go
const CONTROL = /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g;

const oneLine = s => s.replace(/\s+/g, ' ').trim();
const bareUrl = u => u.toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/+$/, '');

// the href attribute itself (not data-href, not "href=" inside another attribute's quoted value)
function linkHref(attrs) {
  const m = [...attrs.matchAll(ATTR)].find(a => a[1].toLowerCase() === 'href');
  if (!m) return null;
  const u = decodeEntities(m[2] ?? m[3] ?? m[4] ?? '').trim();
  return /^https?:\/\/[^\s<>"'`]+$/i.test(u) && !/[\x00-\x1f\x7f]/.test(u) ? u : null;
}

// Cuts at the last line break (else word break) before n, never inside a surrogate pair, and adds "…".
function capText(s, n) {
  if (s.length <= n) return s;
  let cut = s.slice(0, n);
  if (/[\uD800-\uDBFF]$/.test(cut)) cut = cut.slice(0, -1);
  const line = cut.lastIndexOf('\n');
  const word = cut.search(/\s\S*$/);
  const at = line > n * 0.8 ? line : word > n * 0.6 ? word : -1;
  return (at > 0 ? cut.slice(0, at) : cut).replace(/[\s,;:.\u2013\u2014\u2022-]+$/, '') + '\u2026';
}

export function descriptionText(html) {
  if (typeof html !== 'string') return null;
  let s = html.replace(MARK, '');
  if (/<[a-z!?/]/i.test(s)) {
    const links = [];
    s = s.replace(/<pre\b[^>]*>[\s\S]*?<\/pre\s*>/gi, pre => pre.replace(/\r\n?|\n/g, '<br>'))
      .replace(/\s+/g, ' ')                        // in markup, a raw line break is only a space
      .replace(/<!--[\s\S]*?-->/g, '')
      .replace(QUOTED_TAG, tag => tag.replace(/"[^"]*"|'[^']*'/g, q => q.replace(/[<>]/g, ' ')))
      .replace(DROP_BLOCK, ' ')
      .replace(DROP_REST, ' ');
    const gt = s.lastIndexOf('>') + 1;                       // a "<" with no ">" after it is text (and the scans stay linear)
    s = (s.slice(0, gt) + s.slice(gt).replace(/</g, '&lt;'))
      .replace(LINK, (m, attrs, inner) => {
        const url = linkHref(attrs);
        if (!url) return inner;
        const text = oneLine(decodeEntities(inner.replace(TAG, ' ')));
        links.push(!text || bareUrl(text) === bareUrl(url) ? url : text + ' (' + url + ')');
        return '\uE000' + (links.length - 1) + '\uE001';
      })
      .replace(IN_ITEM, li => li.replace(/<br\b[^>]*>|<\/?(?:p|div|h[1-6]|blockquote|pre)\b[^>]*>/gi, ' '))
      .replace(/<br\b[^>]*>/gi, '\n')
      .replace(/<li\b[^>]*>/gi, '\n\u2022 ')
      .replace(/<\/(?:li|tr)\s*>|<(?:dt|dd)\b[^>]*>/gi, '\n')
      .replace(/<\/t[dh]\s*>/gi, ' ')                  // table cells side by side
      .replace(BLOCK, '\n\n')
      .replace(TAG, '');
    // decode the text between the link stand-ins only: a link's text was decoded once already, and an entity that
    // decodes to a stand-in character can never pose as one
    s = s.split(/\uE000(\d+)\uE001/).map((part, k) => (k % 2 ? links[+part] : decodeEntities(part))).join('');
  } else s = decodeEntities(s);
  const text = s.replace(/\r\n?/g, '\n')
    .replace(/[\u200B\uFEFF\uE000\uE001]/g, '')
    .replace(CONTROL, '')
    .split('\n')
    .map(line => line.replace(/[^\S\n]+/g, ' ').trim())
    .filter(line => line !== '\u2022')               // an empty list item
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/(\u2022 [^\n]*)\n\n(?=\u2022 )/g, '$1\n')   // a nested list's breaks: its items stay one list
    .trim();
  return text ? capText(text, DESCRIPTION_MAX) : null;
}

// PC sets `recurrence` only on a recurring instance; recurrence_description is the long human text.
function isRecurring(a) {
  const kind = clean(a.recurrence);
  return !!kind && !/^none$/i.test(kind);
}

function recurrenceText(a) {
  if (!isRecurring(a)) return null;
  const text = [a.recurrence_description, a.compact_recurrence_description, a.recurrence]
    .map(clean)
    .find(t => t && t.length <= 80 && !/^(none|does not repeat)$/i.test(t));
  return text ? text[0].toUpperCase() + text.slice(1) : null;
}

function toRow(instance, event, included) {
  const a = instance.attributes || {};
  const e = event.attributes || {};
  const name = clean(a.name) || clean(e.name);
  const times = publicTimes(a, eventTimesOf(instance, included));
  if (!name || !times) return null;
  return {
    row: {
      id: String(instance.id),
      eventId: String(event.id),
      name,
      summary: cap(plainText(e.summary) || plainText(a.description) || plainText(e.description), SUMMARY_MAX),
      description: descriptionText(a.description) || descriptionText(e.description),
      starts: iso(times.starts),
      ends: times.ends === null ? null : iso(times.ends),
      allDay: a.all_day_event === true,
      location: cleanLocation(a.location),
      image: httpUrl(a.image_url) || httpUrl(e.image_url),
      url: httpUrl(a.church_center_url),
      registerUrl: httpUrl(e.registration_url),
      featured: e.featured === true,
      recurrence: recurrenceText(a),
      ics: icsPath(String(instance.id)),
    },
    source: times.source,
    recurring: isRecurring(a),
  };
}

const byStart = (x, y) => x.starts.localeCompare(y.starts) || x.name.localeCompare(y.name) || x.id.localeCompare(y.id);

// Raw API pages -> the public, capped, sorted list. `held` = fetchHeldBack's ids; `stats` (optional)
// collects counts for the log.
export function buildEvents(data, included, now = new Date(), { held, stats = {} } = {}) {
  const from = now.getTime();
  const until = from + WINDOW_DAYS * DAY;
  const groups = new Map(); // eventId -> { recurring, rows }
  Object.assign(stats, { heldBack: 0, timed: 0, timedFallback: 0 });
  for (const instance of data) {
    if (instance?.type !== 'EventInstance') continue;
    const ref = instance.relationships?.event?.data;
    const event = ref && ref.type === 'Event' ? included.get('Event:' + ref.id) : null;
    if (!isPublic(instance, event)) continue;
    if (held && (held.instanceIds.has(String(instance.id)) || held.eventIds.has(String(event.id)))) {
      stats.heldBack++;
      continue;
    }
    const built = toRow(instance, event, included);
    if (!built) continue;
    const { row } = built;
    if (Date.parse(row.ends || row.starts) < from || Date.parse(row.starts) > until) continue;
    if (!row.allDay) {
      stats.timed++;
      if (built.source !== 'published') stats.timedFallback++;
    }
    const g = groups.get(row.eventId) || { recurring: false, rows: [] };
    g.recurring = g.recurring || built.recurring;
    g.rows.push(row);
    groups.set(row.eventId, g);
  }
  const out = [];
  for (const g of groups.values()) out.push(...g.rows.sort(byStart).slice(0, g.recurring ? SERIES_ROWS : ONE_OFF_ROWS));
  return out.sort(byStart);
}

// ---- change detection ----

const SIGNING = /^(expires_at|expires|signature|key-pair-id|policy|x-amz-.+)$/i;

function unsigned(u) {
  try {
    const x = new URL(u);
    for (const k of [...x.searchParams.keys()]) if (SIGNING.test(k)) x.searchParams.delete(k);
    return x.toString();
  } catch {
    return u;
  }
}

// When a signed URL stops working (ms epoch), or null if it is not signed
export function urlExpiry(u) {
  try {
    const p = new Map([...new URL(u).searchParams].map(([k, v]) => [k.toLowerCase(), v]));
    const n = Number(p.get('expires_at') || p.get('expires'));
    if (n > 0) return n < 1e12 ? n * 1000 : n;
    const d = (p.get('x-amz-date') || '').match(/^(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)Z$/);
    const life = Number(p.get('x-amz-expires'));
    if (d && life > 0) return Date.UTC(+d[1], d[2] - 1, +d[3], +d[4], +d[5], +d[6]) + life * 1000;
  } catch { /* not a URL */ }
  return null;
}

const comparable = list => JSON.stringify((list || []).map(e => ({ ...e, image: e.image && unsigned(e.image) })));

export function sameEvents(a, b) {
  return comparable(a) === comparable(b);
}

// True when a stored signed image URL is about to expire (or has) AND PC now hands out one for the same
// image that lasts at least REFRESH_GAIN longer (or is not signed at all). Comparing against the fresh
// URL is what stops a commit loop when PC keeps serving the same soon-to-expire URL.
export function imageRefreshDue(oldList, newList, now) {
  const old = new Map((oldList || []).map(e => [e && e.id, e]));
  return (newList || []).some(e => {
    const o = e && e.image ? old.get(e.id) : null;
    if (!o || !o.image || unsigned(o.image) !== unsigned(e.image)) return false;
    const was = urlExpiry(o.image);
    if (was === null || was - now.getTime() > REFRESH_BEFORE) return false;
    const fresh = urlExpiry(e.image);
    return fresh === null || fresh >= was + REFRESH_GAIN;
  });
}

function readOld(file) {
  try {
    const old = JSON.parse(readFileSync(file, 'utf8'));
    return old && Array.isArray(old.events) ? old : null;
  } catch {
    return null; // missing or unreadable: write a fresh one
  }
}

// ---- calendar files (RFC 5545) ----
//   Times     timed rows in UTC ("...Z"); all-day rows as DATE values in Los Angeles calendar days, DTEND the day AFTER
//             the last one (RFC 5545 makes it exclusive). The day logic is acEvNorm's in footer-injection.html, so the file
//             and the card agree on the date: an all-day row stamped at UTC midnight is read in UTC.
//   LOCATION  PC's own text, with a bare "Arroyo Church" expanded to the street address; left out when PC has none.
//   DESCRIPTION  the description (else the summary), a blank line, then "Details: <our /events#event-<id> panel>" and "Register: <link>"
//             when present. Both are plain text built here, so the same PC text always gives the same bytes.
//   URL       the registration link, else the Church Center page.
//   TRANSP    all-day rows are TRANSPARENT, so a day-long event does not mark someone busy all day.
//   DTSTAMP / LAST-MODIFIED  when this sync first wrote the event as it now stands: read back from the existing file and
//             kept while nothing else in it changes, so a quiet run leaves every byte alone and the Action commits nothing.
//   SEQUENCE  that stamp in minutes since 2026-01-01, so every restamp raises it (3.8.7.4) and a calendar that already
//             holds the event can tell the newer copy; derived, not stored, so it is as byte-stable as the stamp.
// The site builds its Google and Outlook links from the same fields (acEvCalData in footer-injection.html).

export const ICS_DIR = 'data/events/ics/';   // the row's `ics` path, relative to the repo root (= the Pages site root)
const TIME_ZONE = 'America/Los_Angeles';
const CHURCH_ADDRESS = 'Arroyo Church, 945 Concannon Blvd, Livermore, CA 94550';
const SAFE_ID = /^[A-Za-z0-9_-]{1,64}$/;    // PC ids are digits; anything else never becomes a file name
const CAL_HEAD = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Arroyo Church//Events//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH'];
const FEED_HEAD = [
  ...CAL_HEAD, 'NAME:Arroyo Church', 'X-WR-CALNAME:Arroyo Church', 'X-WR-TIMEZONE:' + TIME_ZONE,
  'X-WR-CALDESC:Upcoming events at Arroyo Church in Livermore\\, CA', 'REFRESH-INTERVAL;VALUE=DURATION:PT6H',
  'X-PUBLISHED-TTL:PT6H',
];
const STAMP = /\r\nDTSTAMP:(\d{8}T\d{6}Z)\r\n/;
const UTC_MIDNIGHT = /T(00:00|23:59)(:\d\d(\.\d+)?)?(Z|[+-]00:?00)$/; // acUtcMid in footer-injection.html
const SEQ_EPOCH = Date.UTC(2026, 0, 1);

export const icsPath = id => (SAFE_ID.test(id) ? ICS_DIR + id + '.ics' : null);

// TEXT values (3.3.11): backslash, semicolon, comma and line breaks escaped; other control characters dropped.
export function icsText(s) {
  return String(s)
    .replace(/\r\n?/g, '\n')
    .replace(/[\x00-\x08\x0b-\x1f\x7f]/g, '')
    .replace(/[;,\\]/g, c => '\\' + c)
    .replace(/\n/g, '\\n');
}

// Content lines over 75 octets fold onto continuation lines that start with one space, the space counted (3.1). Splits
// fall between characters, never inside a multi-byte UTF-8 one (an emoji's surrogate pair stays whole too).
export function icsFold(line) {
  const out = [];
  let cur = '';
  let size = 0;
  for (const ch of line) {
    const n = Buffer.byteLength(ch);
    if (size + n > 75) { out.push(cur); cur = ' '; size = 1; }
    cur += ch;
    size += n;
  }
  out.push(cur);
  return out.join('\r\n');
}

const icsUtc = t => new Date(t).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
const laDayFmt = new Intl.DateTimeFormat('en-CA', { timeZone: TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit' });
function laDay(t) {
  const p = {};
  for (const x of laDayFmt.formatToParts(new Date(t))) p[x.type] = x.value;
  return p.year + p.month + p.day;
}
const utcDay = t => new Date(t).toISOString().slice(0, 10).replace(/-/g, '');
const nextDay = d => utcDay(Date.UTC(+d.slice(0, 4), +d.slice(4, 6) - 1, +d.slice(6, 8) + 1));

// An all-day row -> [first day, the day after its last] as YYYYMMDD. PC stores an all-day day as Los Angeles midnight to
// 23:59:59; the end steps back a second first, so an end AT midnight does not add a day.
export function allDayDates(row) {
  const s = Date.parse(row.starts);
  const e = row.ends ? Date.parse(row.ends) : NaN;
  const day = UTC_MIDNIGHT.test(row.starts) ? utcDay : laDay;
  const first = day(s);
  let last = e > s ? day(e - 1000) : first;
  if (last < first) last = first;
  return [first, nextDay(last)];
}

export const icsLocation = loc => (loc && /^arroyo church$/i.test(loc.trim()) ? CHURCH_ADDRESS : loc || null);

// The event's own panel on our site (2026-10-24: Dakota found the Church Center page a dead end). A calendar entry's
// "Details" link and URL go there; only a row without a usable id falls back to Church Center.
export const EVENT_PAGE = 'https://www.arroyochurch.com/events#event-';
export const eventPage = row => (typeof row.id === 'string' && /^[A-Za-z0-9_-]{1,64}$/.test(row.id) ? EVENT_PAGE + row.id : row.url || null);

export function icsDescription(row) {
  const page = eventPage(row);
  const links = [page && 'Details: ' + page, row.registerUrl && 'Register: ' + row.registerUrl].filter(Boolean);
  return [row.description || row.summary, links.join('\n')].filter(Boolean).join('\n\n') || null;
}

// A stamp (YYYYMMDDTHHMMSSZ) -> its SEQUENCE: whole minutes since SEQ_EPOCH, never below 0 (0 for an unreadable stamp).
export function icsSequence(stamp) {
  const m = /^(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)Z$/.exec(stamp);
  if (!m) return 0;
  return Math.max(0, Math.floor((Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]) - SEQ_EPOCH) / 60000));
}

// One row -> its VEVENT's content lines (unfolded), stamped `stamp` (YYYYMMDDTHHMMSSZ).
export function icsEvent(row, stamp) {
  const lines = ['BEGIN:VEVENT', 'UID:' + row.id + '@arroyochurch.com', 'DTSTAMP:' + stamp, 'LAST-MODIFIED:' + stamp,
    'SEQUENCE:' + icsSequence(stamp)];
  if (row.allDay) {
    const [first, end] = allDayDates(row);
    lines.push('DTSTART;VALUE=DATE:' + first, 'DTEND;VALUE=DATE:' + end);
  } else {
    lines.push('DTSTART:' + icsUtc(Date.parse(row.starts)));
    if (row.ends) lines.push('DTEND:' + icsUtc(Date.parse(row.ends)));  // no end in PC: none invented
  }
  lines.push('SUMMARY:' + icsText(row.name));
  const loc = icsLocation(row.location);
  if (loc) lines.push('LOCATION:' + icsText(loc));
  const desc = icsDescription(row);
  if (desc) lines.push('DESCRIPTION:' + icsText(desc));
  const url = row.registerUrl || eventPage(row);     // http(s), no whitespace: a URI value, never escaped
  if (url) lines.push('URL:' + url);
  if (row.allDay) lines.push('TRANSP:TRANSPARENT');
  lines.push('END:VEVENT');
  return lines;
}

export const calendarText = (head, vevents) => [...head, ...vevents.flat(), 'END:VCALENDAR'].map(icsFold).join('\r\n') + '\r\n';

function readText(file) {
  try {
    return readFileSync(file, 'utf8');
  } catch {
    return null;
  }
}

function writeAtomic(file, text) {
  writeFileSync(file + '.tmp', text);
  renameSync(file + '.tmp', file);
}

// Writes each row's file and the feed when their bytes change; deletes the .ics of any row no longer in the list.
export function writeCalendars(events, { icsDir, feedFile, now }) {
  const stampNow = icsUtc(now.getTime());
  mkdirSync(icsDir, { recursive: true });
  mkdirSync(dirname(feedFile), { recursive: true });
  const keep = new Set();
  const vevents = [];
  let written = 0;
  let removed = 0;
  for (const row of events) {
    if (!row.ics || !SAFE_ID.test(row.id)) continue;
    const name = row.id + '.ics';
    const file = join(icsDir, name);
    keep.add(name);
    const old = readText(file);
    const was = old && (old.match(STAMP) || [])[1];
    let lines = was ? icsEvent(row, was) : null;
    if (!lines || calendarText(CAL_HEAD, [lines]) !== old) {
      lines = icsEvent(row, stampNow);
      writeAtomic(file, calendarText(CAL_HEAD, [lines]));
      written++;
    }
    vevents.push(lines);
  }
  for (const name of readdirSync(icsDir)) {
    if (/\.ics$/i.test(name) && !keep.has(name)) {
      unlinkSync(join(icsDir, name));
      removed++;
    }
  }
  const feed = calendarText(FEED_HEAD, vevents);
  if (readText(feedFile) !== feed) {
    writeAtomic(feedFile, feed);
    written++;
  }
  return { written, removed };
}

// ---- main ----

export async function run({
  env = process.env, fetchImpl = fetch, now = new Date(), outFile = OUT_FILE, sleep = wait, log = console.log,
  icsDir = join(dirname(outFile), 'events', 'ics'), feedFile = join(dirname(outFile), 'events.ics'),
} = {}) {
  const id = (env.PC_EVENTS_APP_ID || '').trim();
  const secret = (env.PC_EVENTS_SECRET || '').trim();
  if (!id || !secret) {
    log('sync-events: PC_EVENTS_APP_ID / PC_EVENTS_SECRET are not set — skipping, data/events.json left as it is.');
    return { status: 'skipped' };
  }
  const auth = 'Basic ' + Buffer.from(id + ':' + secret).toString('base64');

  const { data, included, pages } = await fetchInstances({ fetchImpl, auth, now, sleep });
  checkShape(data, included);
  const held = await fetchHeldBack({ fetchImpl, auth, now, sleep });
  const stats = {};
  const events = buildEvents(data, included, now, { held, stats });
  log(`sync-events: ${data.length} instance(s) over ${pages} page(s) -> ${events.length} public row(s)`
    + (events.length ? ': ' + [...new Set(events.map(e => e.name))].join(' | ') : ''));
  if (stats.heldBack) {
    log(`sync-events: ${stats.heldBack} instance(s) held back: event request pending or rejected.`);
    if (!events.length) log('sync-events: warning: every published event is held back. If that is wrong, PC may have ignored the `' + HELD_BACK_SCOPE + '` scope.');
  }
  if (stats.timedFallback) {
    log(`sync-events: note: ${stats.timedFallback} of ${stats.timed} timed instance(s) had no usable published time (no UTC offset, or outside the schedule); used the public event times or the scheduled span.`);
  }
  if (events.some(e => e.image && urlExpiry(e.image) !== null && urlExpiry(e.image) - now.getTime() < 2 * REFRESH_BEFORE)) {
    log('sync-events: warning: PC image URLs expire within a day; the site may briefly show a broken image around each expiry. Consider hosting the images.');
  }

  const old = readOld(outFile);
  let status = 'unchanged';
  if (old && sameEvents(old.events, events) && !imageRefreshDue(old.events, events, now)) {
    log('sync-events: no change.');
  } else {
    const out = { updated: iso(now.getTime()), events };
    mkdirSync(dirname(outFile), { recursive: true });
    writeFileSync(outFile + '.tmp', JSON.stringify(out, null, 2) + '\n');
    renameSync(outFile + '.tmp', outFile);
    log('sync-events: wrote ' + outFile);
    status = 'written';
  }
  // checked on every run, not only when events.json changed: the first run after this shipped had no files yet
  const calendars = writeCalendars(events, { icsDir, feedFile, now });
  if (calendars.written || calendars.removed) {
    log(`sync-events: calendar files: ${calendars.written} written, ${calendars.removed} removed.`);
  }
  return { status, events, calendars };
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href;
if (isMain) {
  run().catch(e => {
    if (e.transient) {
      // PC down or busy: nothing for a human to do, the next run retries. Exit 0 so a long outage does
      // not send a failure email every 30 minutes; the warning still shows on the run.
      console.log('::warning::sync-events: Planning Center unavailable (' + e.message + ') — keeping the last-good data/events.json; the next run retries.');
      process.exit(0);
    }
    console.error('sync-events failed:', e.message, '— keeping the last-good data/events.json');
    process.exit(1);
  });
}

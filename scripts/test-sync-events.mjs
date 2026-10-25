// Tests for scripts/sync-events.mjs. Plain node, no dependencies, no network, no token:
//   node scripts/test-sync-events.mjs
// The fixture is shaped like real Planning Center Calendar responses (JSON:API, two pages, included
// events and event times) and mixes the church's real public events with the private ones that must
// never reach the public data/events.json. The private ones are in the fixture as if the server had
// ignored the where[] params, so the script's own filter is what keeps them out. A second fixture
// answers the pending/rejected event-request query. The calendar tests read the .ics files a run writes beside the JSON.
// The results must not depend on the machine's time zone: run it under TZ=UTC and TZ=America/Los_Angeles.

import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, rmSync, readFileSync, writeFileSync, existsSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import {
  run, buildEvents, plainText, descriptionText, isPublic, firstPageUrl, urlExpiry, publicTimes, utcTime, imageRefreshDue,
  icsText, icsFold, icsEvent, icsDescription, icsSequence, allDayDates, calendarText, writeCalendars, cleanLocation,
  API, API_VERSION, WINDOW_DAYS, SERIES_ROWS, HELD_BACK_SCOPE,
} from './sync-events.mjs';

const NOW = new Date('2026-10-24T16:00:00Z');
const CC = 'https://arroyo-church-434989.churchcenter.com';
const EP = 'https://www.arroyochurch.com/events#event-';
const ENV = { PC_EVENTS_APP_ID: 'app-id-123', PC_EVENTS_SECRET: 'sekrit-value-456' };
const PRIVATE = ["Mom's Group", 'Team Arroyo Thanksgiving', 'Ramos Baby Shower', 'Connect Group Leader', 'Building closed', 'Visibility unknown', 'Fall Festival'];

// ---- fixture builders (every requested field present, as PC returns them) ----

function ev(id, attributes) {
  return {
    type: 'Event', id: String(id),
    attributes: {
      name: null, summary: null, description: null, image_url: null, registration_url: null,
      featured: false, visible_in_church_center: true, link_only: false, ...attributes,
    },
    relationships: { calendar: { data: { type: 'Calendar', id: '1' } }, owner: { data: { type: 'Person', id: '77' } } },
    links: { self: `${API}/events/${id}` },
  };
}

function inst(id, eventId, attributes, timeIds = []) {
  return {
    type: 'EventInstance', id: String(id),
    attributes: {
      all_day_event: false, church_center_url: `${CC}/calendar/event/${id}`, compact_recurrence_description: null,
      description: null, ends_at: null, image_url: null, kind: 'standard', location: null, name: null,
      published_ends_at: null, published_starts_at: null, recurrence: null, recurrence_description: null,
      starts_at: null, ...attributes,
    },
    relationships: {
      event: { data: { type: 'Event', id: String(eventId) } },
      event_times: { data: timeIds.map(t => ({ type: 'EventTime', id: String(t) })) },
    },
    links: { self: `${API}/event_instances/${id}` },
  };
}

const time = (id, starts, ends, visible) => ({
  type: 'EventTime', id: String(id),
  attributes: { starts_at: starts, ends_at: ends, visible_on_widget_and_ical: visible },
});

// all-day instance: PC stores local midnight in UTC (PDT = 07:00Z, PST after Nov 1 = 08:00Z)
const allDay = (start, end) => ({ all_day_event: true, starts_at: start, ends_at: end, published_starts_at: start, published_ends_at: end });
const monthly = { recurrence: 'Monthly', recurrence_description: 'Monthly on the 4th Sunday', compact_recurrence_description: 'Monthly' };
const connect = (id, day, extra = {}, timeIds = []) => inst(id, 2, {
  name: 'Connect class', starts_at: `${day}T19:00:00Z`, ends_at: `${day}T21:00:00Z`,
  published_starts_at: `${day}T19:30:00Z`, published_ends_at: `${day}T20:45:00Z`, ...monthly, ...extra,
}, timeIds);

const PNO_IMG = 'https://images.planningcenterusercontent.com/v1/transform?bucket=resources-production&key=uploads%2Fpno.jpg&expires_at=1893456000&signature=abc123';

const EVENTS = {
  baptisms: ev(1, { name: 'Baptisms' }),
  connect: ev(2, { name: 'Connect class', summary: 'New to Arroyo? Start here.' }),
  foundations: ev(3, { name: 'Foundations class', registration_url: 'arroyo-church-434989.churchcenter.com/registrations/events/2840001' }),
  mens: ev(4, { name: "Men's Event", registration_url: 'javascript:alert(1)' }),
  worship: ev(5, { name: 'Worship Night', summary: '  An evening of   worship and prayer.  ' }),
  moms: ev(6, { name: "Mom's Group", visible_in_church_center: false, description: '<p>Our secret plans</p>' }),
  thanksgiving: ev(7, { name: 'Team Arroyo Thanksgiving', visible_in_church_center: false }),
  shower: ev(8, { name: 'Ramos Baby Shower', link_only: true }),                 // published, but link-only
  blockout: ev(9, { name: 'Building closed' }),                                    // its instance is a blockout
  leaders: ev(10, { name: 'Connect Group Leader Appreciation and Training', visible_in_church_center: false }),
  womens: ev(11, { name: "Women's Event", approval_status: 'P' }),                 // rooms pending: still shows
  pno: ev(12, {
    name: 'Parents Night Out', featured: true, image_url: PNO_IMG,
    registration_url: `${CC}/registrations/events/2850002`,
    description: '<p>Drop the kids off for a night of games &amp; pizza.</p><p>Ages 3&ndash;10.<br>Free &#8212; just RSVP.</p>'
      + '<ul><li>Dinner at 5:30</li><li>Movie at 7</li></ul><p>Questions? <a href="https://www.arroyochurch.com/kids">Our kids page</a></p><script>alert(1)</script>',
  }),
  unknown: ev(13, { name: 'Visibility unknown', visible_in_church_center: null }),
  festival: ev(14, { name: 'Fall Festival', approval_status: 'A' }),             // published, but its event request is pending
};

const PAGE1_DATA = [
  inst(101, 1, allDay('2026-10-25T07:00:00Z', '2026-10-26T06:59:59Z')),
  inst(201, 2, { name: 'Connect class', starts_at: '2026-10-25T18:00:00Z', ends_at: '2026-10-25T20:00:00Z', published_starts_at: '2026-10-25T18:30:00Z', published_ends_at: '2026-10-25T19:45:00Z', location: ' Arroyo Church, Room 4 ', ...monthly }),
  inst(601, 6, { name: "Mom's Group", starts_at: '2026-10-27T17:00:00Z', ends_at: '2026-10-27T18:30:00Z', recurrence: 'Weekly', recurrence_description: 'Weekly on Tuesday' }),
  inst(301, 3, { name: 'Foundations class', starts_at: '2026-11-01T19:00:00Z', ends_at: '2026-11-01T20:30:00Z', published_starts_at: '2026-11-01T19:00:00Z', published_ends_at: '2026-11-01T20:30:00Z' }),
  inst(602, 6, { name: "Mom's Group", starts_at: '2026-11-03T18:00:00Z', ends_at: '2026-11-03T19:30:00Z', recurrence: 'Weekly', recurrence_description: 'Weekly on Tuesday' }),
  inst(401, 4, allDay('2026-11-07T08:00:00Z', '2026-11-08T07:59:59Z')),
  inst(901, 9, { kind: 'blockout', name: 'Building closed', starts_at: '2026-11-10T08:00:00Z', ends_at: '2026-11-11T07:59:59Z' }),
  inst(302, 3, { name: 'Foundations class', starts_at: '2026-11-15T19:00:00Z', ends_at: '2026-11-15T20:30:00Z', published_starts_at: '2026-11-15T19:00:00Z', published_ends_at: '2026-11-15T20:30:00Z' }),
  inst(501, 5, allDay('2026-11-18T08:00:00Z', '2026-11-19T07:59:59Z')),
  inst(801, 8, { name: 'Ramos Baby Shower', starts_at: '2026-11-21T22:00:00Z', ends_at: '2026-11-22T00:00:00Z', location: '123 Private Ln' }),
  connect(202, '2026-11-22'),
  inst(1401, 14, { name: 'Fall Festival', starts_at: '2026-11-28T18:00:00Z', ends_at: '2026-11-28T22:00:00Z', location: 'Festival Field' }),
];
const PAGE2_DATA = [
  inst(701, 7, { name: 'Team Arroyo Thanksgiving', starts_at: '2026-11-24T02:00:00Z', ends_at: '2026-11-24T04:00:00Z' }),
  inst(1402, 14, { name: 'Fall Festival', starts_at: '2026-12-05T18:00:00Z', ends_at: '2026-12-05T22:00:00Z' }), // not in the held-back answer: dropped by event id
  // wall-clock published times with no zone: never trusted, falls back to the scheduled span
  inst(303, 3, { name: 'Foundations class', starts_at: '2026-12-06T19:00:00Z', ends_at: '2026-12-06T20:30:00Z', published_starts_at: '2026-12-06T11:00:00', published_ends_at: '2026-12-06T12:30:00' }),
  inst(1101, 11, allDay('2026-12-09T08:00:00Z', '2026-12-10T07:59:59Z')),
  inst(1001, 10, { name: 'Connect Group Leader Appreciation and Training', starts_at: '2026-12-12T17:00:00Z', ends_at: '2026-12-12T20:00:00Z' }),
  inst(1301, 13, { name: 'Visibility unknown', starts_at: '2026-12-13T17:00:00Z' }),
  // no usable published time: the widget-visible event time wins over setup/teardown
  connect(203, '2026-12-27', { starts_at: '2026-12-27T18:30:00Z', published_starts_at: '2026-12-27T11:30:00', published_ends_at: null }, [2031, 2032, 2033]),
  connect(204, '2027-01-24'),
  // published times with an explicit offset are fine (5pm PST = 01:00Z next day)
  inst(1201, 12, { name: 'Parents Night Out', starts_at: '2027-02-13T00:30:00Z', ends_at: '2027-02-13T04:30:00Z', published_starts_at: '2027-02-12T17:00:00-08:00', published_ends_at: '2027-02-12T20:00:00-0800', location: 'Arroyo Church Kids Wing' }),
  connect(205, '2027-02-28'),                                                    // 5th of the series: capped
  connect(206, '2027-03-28'),
  connect(209, '2027-06-27'),                                                    // past the window
];
const TIMES = [
  time(2031, '2026-12-27T18:30:00Z', '2026-12-27T19:30:00Z', false),            // setup
  time(2032, '2026-12-27T19:30:00Z', '2026-12-27T20:45:00Z', true),
  time(2033, '2026-12-27T20:45:00Z', '2026-12-27T21:00:00Z', false),            // teardown
];

const PAGE1 = {
  links: { self: firstPageUrl(NOW), next: `${API}/event_instances?filter=future&include=event%2Cevent_times&offset=12&order=starts_at&per_page=100` },
  data: PAGE1_DATA,
  included: [EVENTS.baptisms, EVENTS.connect, EVENTS.moms, EVENTS.foundations, EVENTS.mens, EVENTS.blockout, EVENTS.worship, EVENTS.shower, EVENTS.festival],
  meta: { total_count: 24, count: 12, next: { offset: 12 }, parent: { id: '555', type: 'Organization' } },
};
const PAGE2 = {
  links: { self: PAGE1.links.next },
  data: PAGE2_DATA,
  included: [EVENTS.thanksgiving, EVENTS.festival, EVENTS.foundations, EVENTS.womens, EVENTS.leaders, EVENTS.unknown, EVENTS.connect, EVENTS.pno, ...TIMES],
  meta: { total_count: 24, count: 12, parent: { id: '555', type: 'Organization' } },
};
// the event_request_pending_rejected answer: ids only (fields[EventInstance]=event)
const HELD = {
  links: { self: firstPageUrl(NOW, { heldBack: true }), next: null },
  data: [{ type: 'EventInstance', id: '1401', relationships: { event: { data: { type: 'Event', id: '14' } } } }],
  included: [],
  meta: { total_count: 1, count: 1 },
};
const NO_HELD = { links: { next: null }, data: [], included: [], meta: { total_count: 0, count: 0 } };

const row = r => ({ summary: null, description: null, ends: null, allDay: false, location: null, image: null, url: `${CC}/calendar/event/${r.id}`, registerUrl: null, featured: false, recurrence: null, ics: `data/events/ics/${r.id}.ics`, ...r });
const KEYS = ['id', 'eventId', 'name', 'summary', 'description', 'starts', 'ends', 'allDay', 'location', 'image', 'url', 'registerUrl', 'featured', 'recurrence', 'ics'];
const ordered = r => Object.fromEntries(KEYS.map(k => [k, r[k]]));
const CONNECT = { eventId: '2', name: 'Connect class', summary: 'New to Arroyo? Start here.', recurrence: 'Monthly on the 4th Sunday' };
const FOUNDATIONS = { eventId: '3', name: 'Foundations class', registerUrl: 'https://arroyo-church-434989.churchcenter.com/registrations/events/2840001' };

const PNO_SUMMARY = 'Drop the kids off for a night of games & pizza.\nAges 3–10.\nFree — just RSVP.\nDinner at 5:30\nMovie at 7\nQuestions? Our kids page';
const PNO_DESCRIPTION = 'Drop the kids off for a night of games & pizza.\n\nAges 3–10.\nFree — just RSVP.\n\n• Dinner at 5:30\n• Movie at 7\n\nQuestions? Our kids page (https://www.arroyochurch.com/kids)';

const EXPECTED = [
  row({ id: '101', eventId: '1', name: 'Baptisms', starts: '2026-10-25T07:00:00Z', ends: '2026-10-26T06:59:59Z', allDay: true }),
  row({ id: '201', ...CONNECT, starts: '2026-10-25T18:30:00Z', ends: '2026-10-25T19:45:00Z', location: 'Arroyo Church, Room 4' }),
  row({ id: '301', ...FOUNDATIONS, starts: '2026-11-01T19:00:00Z', ends: '2026-11-01T20:30:00Z' }),
  row({ id: '401', eventId: '4', name: "Men's Event", starts: '2026-11-07T08:00:00Z', ends: '2026-11-08T07:59:59Z', allDay: true }),
  row({ id: '302', ...FOUNDATIONS, starts: '2026-11-15T19:00:00Z', ends: '2026-11-15T20:30:00Z' }),
  row({ id: '501', eventId: '5', name: 'Worship Night', summary: 'An evening of worship and prayer.', starts: '2026-11-18T08:00:00Z', ends: '2026-11-19T07:59:59Z', allDay: true }),
  row({ id: '202', ...CONNECT, starts: '2026-11-22T19:30:00Z', ends: '2026-11-22T20:45:00Z' }),
  row({ id: '303', ...FOUNDATIONS, starts: '2026-12-06T19:00:00Z', ends: '2026-12-06T20:30:00Z' }),
  row({ id: '1101', eventId: '11', name: "Women's Event", starts: '2026-12-09T08:00:00Z', ends: '2026-12-10T07:59:59Z', allDay: true }),
  row({ id: '203', ...CONNECT, starts: '2026-12-27T19:30:00Z', ends: '2026-12-27T20:45:00Z' }),
  row({ id: '204', ...CONNECT, starts: '2027-01-24T19:30:00Z', ends: '2027-01-24T20:45:00Z' }),
  row({ id: '1201', eventId: '12', name: 'Parents Night Out', summary: PNO_SUMMARY, description: PNO_DESCRIPTION, starts: '2027-02-13T01:00:00Z', ends: '2027-02-13T04:00:00Z', location: 'Arroyo Church Kids Wing', image: PNO_IMG, registerUrl: `${CC}/registrations/events/2850002`, featured: true }),
].map(ordered);

// ---- a fake fetch that serves the fixture and records every request ----
// A first-page URL is recognised by the window param the script always sends (fixture next links lack
// it); the held-back query by its event-request scope.

const failure = (status, body = {}) => ({ ok: false, status, headers: { get: () => null }, json: async () => body });

function fakeFetch(pages = [PAGE1, PAGE2], { held = [HELD], failWith } = {}) {
  const calls = [];
  const impl = async (url, init) => {
    calls.push({ url, headers: init?.headers || {} });
    const u = new URL(url);
    const isHeld = (u.searchParams.get('filter') || '').includes('event_request');
    if (failWith) {
      const r = failWith(calls.length, isHeld);
      if (r) return r;
    }
    const list = isHeld ? held : pages;
    const page = u.searchParams.has('where[starts_at][lte]') ? list[0] : list.find((p, i) => i > 0 && p.links.self === url);
    if (!page) return failure(404, { errors: [{ title: 'Not Found' }] });
    return { ok: true, status: 200, headers: { get: () => null }, json: async () => structuredClone(page) };
  };
  return { impl, calls };
}

const quiet = { log: () => {}, sleep: async () => {} };
const allIncluded = () => new Map([...PAGE1.included, ...PAGE2.included].map(r => [r.type + ':' + r.id, r]));
const heldIds = { instanceIds: new Set(['1401']), eventIds: new Set(['14']) };

// ---- tiny harness ----

const tests = [];
const test = (name, fn) => tests.push({ name, fn });
const tmp = mkdtempSync(join(tmpdir(), 'sync-events-test-'));
let n = 0;
// a fresh folder per run, since the calendar files land beside the JSON (events/ics/*.ics + events.ics)
const outPath = () => { const d = join(tmp, `run-${++n}`); mkdirSync(d); return join(d, 'events.json'); };
const icsDirOf = file => join(dirname(file), 'events', 'ics');
const feedOf = file => join(dirname(file), 'events.ics');
const icsFiles = file => (existsSync(icsDirOf(file)) ? readdirSync(icsDirOf(file)).sort() : []);
const readIcs = (file, id) => readFileSync(join(icsDirOf(file), id + '.ics'), 'utf8');
// a calendar file -> its unfolded content lines (CRLF + one space = a fold)
const unfold = text => text.replace(/\r\n /g, '').split('\r\n').filter(Boolean);
const prop = (text, name) => (unfold(text).find(l => l.startsWith(name + ':') || l.startsWith(name + ';')) || null);
const allSnapshot = file => Object.fromEntries([...icsFiles(file).map(f => [f, readFileSync(join(icsDirOf(file), f), 'utf8')]), ['feed', existsSync(feedOf(file)) ? readFileSync(feedOf(file), 'utf8') : null]]);

// ---- tests ----

test('public filter: exactly the published, standard, non-link-only, approved events, sorted', () => {
  const out = buildEvents([...PAGE2_DATA, ...PAGE1_DATA], allIncluded(), NOW, { held: heldIds }); // shuffled: still sorted
  assert.deepEqual(out, EXPECTED);
});

test('no private event name, place or id leaks into the output', () => {
  const json = JSON.stringify(buildEvents([...PAGE1_DATA, ...PAGE2_DATA], allIncluded(), NOW, { held: heldIds }));
  for (const word of [...PRIVATE, 'Private Ln', 'Festival Field', 'secret plans', '"601"', '"801"', '"901"', '"701"', '"1001"', '"1301"', '"1401"', '"1402"']) {
    assert.ok(!json.includes(word), 'leaked: ' + word);
  }
});

test('a pending event request is dropped by instance AND by event id', () => {
  const included = allIncluded();
  const names = held => buildEvents([...PAGE1_DATA, ...PAGE2_DATA], included, NOW, { held }).map(e => e.id);
  assert.ok(names({ instanceIds: new Set(), eventIds: new Set() }).includes('1401'), 'fixture sanity: visible without the held-back list');
  assert.ok(!names({ instanceIds: new Set(['1401']), eventIds: new Set() }).includes('1401'));
  const byEvent = names({ instanceIds: new Set(), eventIds: new Set(['14']) });
  assert.ok(!byEvent.includes('1401') && !byEvent.includes('1402'));
});

test('a series keeps its next few dates; a multi-date one-off keeps every date', () => {
  const out = buildEvents([...PAGE1_DATA, ...PAGE2_DATA], allIncluded(), NOW, { held: heldIds });
  const connect = out.filter(e => e.eventId === '2');
  assert.equal(connect.length, SERIES_ROWS, '6 Connect classes in the window -> ' + SERIES_ROWS);
  assert.deepEqual(connect.map(e => e.id), ['201', '202', '203', '204']);
  assert.deepEqual(out.filter(e => e.eventId === '3').map(e => e.starts.slice(0, 10)), ['2026-11-01', '2026-11-15', '2026-12-06'], 'Foundations: all three dates');
  // a weekly series cannot flood the list
  const weekly = Array.from({ length: 26 }, (_, k) => inst(5000 + k, 50, { name: 'Prayer', starts_at: new Date(NOW.getTime() + (k + 1) * 7 * 86400000).toISOString(), recurrence: 'Weekly', recurrence_description: 'Weekly on Wednesday' }));
  assert.equal(buildEvents(weekly, new Map([['Event:50', ev(50, { name: 'Prayer' })]]), NOW).length, SERIES_ROWS);
});

test('isPublic is strict: missing, null or wrong-typed fields fail closed', () => {
  const i = inst(1, 1, {});
  assert.equal(isPublic(i, ev(1, {})), true);
  assert.equal(isPublic(i, null), false);
  assert.equal(isPublic(i, ev(1, { visible_in_church_center: 'true' })), false);
  assert.equal(isPublic(i, ev(1, { link_only: null })), false);
  const noKind = inst(1, 1, {}); delete noKind.attributes.kind;
  assert.equal(isPublic(noKind, ev(1, {})), false);
  assert.equal(isPublic(inst(1, 1, { kind: 'blockout' }), ev(1, {})), false);
  assert.equal(isPublic(i, ev(1, { featured: true, visible_in_church_center: false })), false);
});

test('public times: explicit zone only, inside the schedule, start and end from one source', () => {
  const sched = { starts_at: '2026-10-25T18:00:00Z', ends_at: '2026-10-25T20:00:00Z' };
  const at = s => Date.parse(s);
  const t = (a, times) => { const r = publicTimes({ ...sched, ...a }, times); return r && [new Date(r.starts).toISOString(), r.ends && new Date(r.ends).toISOString(), r.source]; };
  assert.deepEqual(t({ published_starts_at: '2026-10-25T18:30:00Z', published_ends_at: '2026-10-25T19:45:00Z' }), ['2026-10-25T18:30:00.000Z', '2026-10-25T19:45:00.000Z', 'published']);
  assert.deepEqual(t({ published_starts_at: '2026-10-25T11:30:00-07:00', published_ends_at: '2026-10-25T12:45:00-0700' }), ['2026-10-25T18:30:00.000Z', '2026-10-25T19:45:00.000Z', 'published'], 'offset forms');
  // no zone: never parsed in the machine's zone; falls back to the scheduled span
  assert.deepEqual(t({ published_starts_at: '2026-10-25T11:30:00', published_ends_at: '2026-10-25T12:45:00' }), ['2026-10-25T18:00:00.000Z', '2026-10-25T20:00:00.000Z', 'scheduled']);
  // outside the span (a misread zone): rejected
  assert.equal(t({ published_starts_at: '2026-10-25T11:30:00Z', published_ends_at: '2026-10-25T12:45:00Z' })[2], 'scheduled');
  assert.equal(t({ published_starts_at: '2026-10-26T01:30:00Z', published_ends_at: null })[2], 'scheduled');
  // a good start with an unreadable end does not borrow the scheduled (teardown) end
  assert.deepEqual(t({ published_starts_at: '2026-10-25T18:30:00Z', published_ends_at: '7:45pm' }), ['2026-10-25T18:00:00.000Z', '2026-10-25T20:00:00.000Z', 'scheduled']);
  // a published start with no end at all: no end
  assert.deepEqual(t({ published_starts_at: '2026-10-25T18:30:00Z' }), ['2026-10-25T18:30:00.000Z', null, 'published']);
  // event times: the visible ones only
  const times = [
    { visible: false, starts: at('2026-10-25T18:00:00Z'), ends: at('2026-10-25T18:30:00Z'), endsRaw: 'x' },
    { visible: true, starts: at('2026-10-25T18:30:00Z'), ends: at('2026-10-25T19:45:00Z'), endsRaw: 'x' },
  ];
  assert.deepEqual(t({ published_starts_at: 'garbage' }, times), ['2026-10-25T18:30:00.000Z', '2026-10-25T19:45:00.000Z', 'times']);
  assert.equal(t({}, [{ visible: true, starts: at('2026-10-27T18:30:00Z'), ends: null, endsRaw: null }])[2], 'scheduled', 'event time outside the span');
  assert.equal(publicTimes({ starts_at: '2026-10-25 18:00' }), null, 'no usable time at all: no row');
  assert.equal(utcTime('2026-10-25T18:00:00'), null);
  assert.equal(utcTime('2026-10-25'), null);
  assert.equal(utcTime('2026-10-25T18:00:00.000Z'), at('2026-10-25T18:00:00Z'));
});

test('plainText strips tags, scripts and entities', () => {
  assert.equal(plainText('<p>Hi &amp; welcome</p><ul><li>One</li><li>Two&nbsp;&nbsp;items</li></ul>'), 'Hi & welcome\nOne\nTwo items');
  assert.equal(plainText('<style>p{}</style><b>Bold</b> &#x1F64F; &rsquo;'), 'Bold 🙏 ’');
  assert.equal(plainText('<p> </p>'), null);
  assert.equal(plainText(null), null);
});

test('description: paragraphs, line breaks, list items, links as text (url), entities decoded once', () => {
  assert.equal(descriptionText('<div>Join us for worship.<br><br>Bring a friend &amp; a chair.</div><ul><li>Kids welcome</li><li><p>Snacks</p></li></ul>'),
    'Join us for worship.\n\nBring a friend & a chair.\n\n• Kids welcome\n• Snacks');
  assert.equal(descriptionText('<p>Sign up <a href="https://x.churchcenter.com/registrations/events/1?a=1&amp;b=2">here</a>.</p>'),
    'Sign up here (https://x.churchcenter.com/registrations/events/1?a=1&b=2).', 'href entities decoded');
  assert.equal(descriptionText('<p>Visit <a href="https://www.arroyochurch.com/">www.arroyochurch.com</a></p>'), 'Visit https://www.arroyochurch.com/', 'text = the URL: once');
  assert.equal(descriptionText("<p><a href='http://example.com/a' title=\"x\"><b>Bold</b> link</a></p>"), 'Bold link (http://example.com/a)', 'single quotes, http, inner tags');
  // only http(s) links survive as URLs; anything else keeps its text and nothing else
  assert.equal(descriptionText('<p>Email <a href="mailto:josh@arroyochurch.com">Josh</a>, call <a href="tel:+19256940426">us</a>, <a href="javascript:alert(1)">click</a>, <a href="/plan-your-visit">plan</a>, <a data-href="https://evil.example/">x</a></p>'),
    'Email Josh, call us, click, plan, x');
  assert.equal(descriptionText('<p>&lt;script&gt;alert(1)&lt;/script&gt; &amp;lt;b&amp;gt; &#x1F64F; &rsquo;&nbsp;&nbsp;end</p>'), '<script>alert(1)</script> &lt;b&gt; 🙏 ’ end', 'decoded exactly once, as text');
  assert.equal(descriptionText('<p>Ages 3 < 5 &amp; up</p>'), 'Ages 3 < 5 & up', 'a lone < is text, not a tag');
  assert.equal(descriptionText('<h2>Schedule</h2><ol><li>Dinner</li><li>Games</li></ol><table><tr><td>Fri</td><td>6pm</td></tr></table><hr><blockquote>Quote</blockquote>'),
    'Schedule\n\n• Dinner\n• Games\n\nFri 6pm\n\nQuote');
  assert.equal(descriptionText('<ul><li>One<ul><li>Sub</li></ul></li><li>Two</li><li> </li></ul>'), '• One\n• Sub\n• Two', 'nested list stays one list; empty item dropped');
  assert.equal(descriptionText('<p>Line\n   wrapped   in\tthe source</p>'), 'Line wrapped in the source', 'raw line breaks in markup are spaces');
});

test('description: scripts, styles, comments and other inert blocks go with their content', () => {
  assert.equal(descriptionText('<p>Hi</p><script>alert("x")</script><style>p{color:red}</style><!-- note --><noscript>n</noscript><iframe src="https://x">f</iframe><svg><text>s</text></svg><p>there</p>'), 'Hi\n\nthere');
  assert.equal(descriptionText('<p>Kept</p><SCRIPT type="text/javascript">never closed <p>gone'), 'Kept', 'an unclosed script drops the rest');
  assert.equal(descriptionText('<p onclick="alert(1)" style="x">Text</p><img src=x onerror=alert(1)>'), 'Text');
  // a stand-in character smuggled in (raw or as an entity) can never turn into a link or leak through
  const pu = String.fromCharCode(0xE000) + '0' + String.fromCharCode(0xE001);
  assert.equal(descriptionText('<p>' + pu + ' &#xE000;0&#xE001; <a href="https://ok.example/">ok</a></p>'), '0 0 ok (https://ok.example/)');
  assert.equal(descriptionText('<p>zero' + String.fromCharCode(0x200B) + 'width' + String.fromCharCode(0xFEFF) + '</p>'), 'zerowidth');
});

test('description: list items, <pre>, <dl> and quoted ">" keep their shape', () => {
  assert.equal(descriptionText('<ul><li>Dinner<br>at 5:30</li><li><p>Para one</p><p>Para two</p></li><li>B</li></ul>'),
    '• Dinner at 5:30\n• Para one Para two\n• B', 'a break inside an item is a space: one list, no stray paragraph');
  assert.equal(descriptionText('<p>Times:</p><pre>Fri 6pm\nSat 9am\n\nSun 10am</pre><p>after</p>'), 'Times:\n\nFri 6pm\nSat 9am\n\nSun 10am\n\nafter', '<pre> keeps its lines');
  assert.equal(descriptionText('<dl><dt>When</dt><dd>Friday</dd><dt>Where<dd>Hall</dl>'), 'When\nFriday\nWhere\nHall', 'dt/dd on their own lines');
  assert.equal(descriptionText('<p><a title="a > b" href="https://ok.example/">ok</a> after <span title="<b>">x</span></p>'), 'ok (https://ok.example/) after x', '">" inside a quoted value');
  assert.equal(descriptionText('<p><a title="x href=https://evil.example/">no</a> <a data-href="https://evil.example/" HREF="https://good.example/">yes</a></p>'),
    'no yes (https://good.example/)', 'only the href attribute itself counts');
});

test('description: named entities beyond the basics; text without tags is decoded too', () => {
  assert.equal(descriptionText('<p>Caf&eacute; 50&deg; &frac12; &times;2 &laquo;q&raquo; &euro;5 &pound;3 &sect;1 &Eacute;&EACUTE; co&shy;op x&ensp;y&emsp;z&thinsp;w</p>'),
    'Café 50° ½ ×2 «q» €5 £3 §1 Éé coop x y z w');
  assert.equal(descriptionText('<p>&constructor; &toString; &bogus; &#xD800; &#0;</p>'), '&constructor; &toString; &bogus;', 'unknown names stay text; no prototype keys, no lone surrogate');
  assert.equal(descriptionText('Games &amp; pizza &mdash; RSVP\n\nAges 5&ndash;10'), 'Games & pizza — RSVP\n\nAges 5–10');
  assert.equal(descriptionText('Fish &amp;amp; chips'), 'Fish &amp; chips', 'still decoded exactly once');
});

test('description: broken markup stays fast and its leftovers stay text', () => {
  const t0 = Date.now();
  const runs = ['<p>' + 'a'.repeat(60000) + '>x', '<p title="a" '.repeat(5000), '<a x="'.repeat(3000), '<li>'.repeat(20000) + 'x'];
  for (const html of runs) assert.ok(descriptionText(html).length <= 3001);
  assert.ok(Date.now() - t0 < 2000, `took ${Date.now() - t0}ms`);
  assert.equal(descriptionText('<p>Tail</p> 3 <b'), 'Tail\n\n3 <b', 'a "<" with no ">" after it is text');
});

test('description: plain text keeps its own breaks; empty is null; long is capped', () => {
  assert.equal(descriptionText('Plain line one\r\nline two\n\n\n\nPara   two  '), 'Plain line one\nline two\n\nPara two');
  for (const empty of ['', '   ', '<p> </p>', '<p><br></p><div>&nbsp;</div>', '<script>x</script>', null, undefined, 42, {}]) {
    assert.equal(descriptionText(empty), null, JSON.stringify(empty));
  }
  const long = descriptionText('<p>' + 'word '.repeat(1000) + '</p><p>tail</p>');
  assert.ok(long.length <= 3001 && long.endsWith('word…') && !long.includes('tail'), long.slice(-20));
  const paras = descriptionText(Array.from({ length: 60 }, (_, k) => `<p>Paragraph ${k} ${'x'.repeat(40)}.</p>`).join(''));
  assert.ok(paras.length <= 3001 && /\.\n\nParagraph \d+ x+…$|x+\.…$/.test(paras.slice(-80)) && paras.endsWith('…'), paras.slice(-60));
  assert.ok(!/[\uD800-\uDBFF]…$/.test(descriptionText('🙏'.repeat(2000))), 'never ends on half an emoji');
});

test('description: the instance text, else the event text; null when neither has one', () => {
  const included = new Map([
    ['Event:1', ev(1, { name: 'A', description: '<p>Event text</p>' })],
    ['Event:2', ev(2, { name: 'B', summary: 'Short summary' })],
  ]);
  const out = buildEvents([
    inst(1, 1, { starts_at: '2026-11-01T17:00:00Z', description: '<p>Instance <b>text</b></p>' }),
    inst(2, 1, { starts_at: '2026-11-02T17:00:00Z', description: '<p> </p>' }),
    inst(3, 2, { starts_at: '2026-11-03T17:00:00Z' }),
  ], included, NOW);
  assert.deepEqual(out.map(r => [r.id, r.description, r.summary]), [
    ['1', 'Instance text', 'Instance text'],
    ['2', 'Event text', 'Event text'],
    ['3', null, 'Short summary'],
  ]);
  assert.deepEqual(Object.keys(out[0]), KEYS, 'description sits right after summary');
});

test('long summaries are capped on a word boundary', () => {
  const included = new Map([['Event:1', ev(1, { name: 'Long', summary: 'word '.repeat(300) })]]);
  const [r] = buildEvents([inst(1, 1, { starts_at: '2026-11-01T17:00:00Z' })], included, NOW);
  assert.ok(r.summary.length <= 601 && r.summary.endsWith('word…'), r.summary.slice(-20));
});

test('requests: documented filters, includes, fields, window, the held-back query, auth headers', async () => {
  const f = fakeFetch();
  const r = await run({ env: ENV, fetchImpl: f.impl, now: NOW, outFile: outPath(), ...quiet });
  assert.equal(r.status, 'written');
  assert.equal(f.calls.length, 3, 'page 1, page 2 (links.next), then the held-back query');
  const q = Object.fromEntries(new URL(f.calls[0].url).searchParams);
  assert.equal(new URL(f.calls[0].url).origin + new URL(f.calls[0].url).pathname, API + '/event_instances');
  assert.equal(q.filter, 'future');
  assert.equal(q.include, 'event,event_times');
  assert.equal(q.order, 'starts_at');
  assert.equal(q.per_page, '100');
  assert.equal(q['where[kind]'], 'standard');
  assert.equal(q['where[event][visible_in_church_center]'], 'true');
  assert.equal(q['where[event][link_only]'], 'false');
  assert.equal(Date.parse(q['where[starts_at][lte]']), NOW.getTime() + WINDOW_DAYS * 86400000);
  for (const f2 of ['kind', 'published_starts_at', 'published_ends_at', 'image_url', 'description', 'church_center_url', 'event', 'event_times']) {
    assert.ok(q['fields[EventInstance]'].split(',').includes(f2), 'fields[EventInstance] has ' + f2);
  }
  for (const f2 of ['visible_in_church_center', 'link_only', 'featured', 'registration_url', 'summary']) {
    assert.ok(q['fields[Event]'].split(',').includes(f2), 'fields[Event] has ' + f2);
  }
  assert.deepEqual(q['fields[EventTime]'].split(',').sort(), ['ends_at', 'starts_at', 'visible_on_widget_and_ical']);
  const h = Object.fromEntries(new URL(f.calls[2].url).searchParams);
  assert.equal(h.filter, 'future,' + HELD_BACK_SCOPE);
  for (const k of ['where[starts_at][lte]', 'where[kind]', 'where[event][visible_in_church_center]', 'where[event][link_only]', 'order', 'per_page']) {
    assert.equal(h[k], q[k], 'held-back query uses the same ' + k);
  }
  for (const c of f.calls) {
    assert.equal(c.headers.Authorization, 'Basic ' + Buffer.from('app-id-123:sekrit-value-456').toString('base64'));
    assert.equal(c.headers['X-PCO-API-Version'], API_VERSION);
  }
});

test('writes the expected file, then leaves it alone when nothing changed', async () => {
  const file = outPath();
  await run({ env: ENV, fetchImpl: fakeFetch().impl, now: NOW, outFile: file, ...quiet });
  const first = readFileSync(file, 'utf8');
  const parsed = JSON.parse(first);
  assert.deepEqual(Object.keys(parsed), ['updated', 'events']);
  assert.equal(parsed.updated, '2026-10-24T16:00:00Z');
  assert.deepEqual(parsed.events, EXPECTED);
  const later = new Date(NOW.getTime() + 30 * 60000);
  const r = await run({ env: ENV, fetchImpl: fakeFetch().impl, now: later, outFile: file, ...quiet });
  assert.equal(r.status, 'unchanged');
  assert.equal(readFileSync(file, 'utf8'), first, 'byte-identical, so the Action commits nothing');
});

test('approving a held-back event request publishes it on the next run', async () => {
  const file = outPath();
  await run({ env: ENV, fetchImpl: fakeFetch().impl, now: NOW, outFile: file, ...quiet });
  const r = await run({ env: ENV, fetchImpl: fakeFetch([PAGE1, PAGE2], { held: [NO_HELD] }).impl, now: NOW, outFile: file, ...quiet });
  assert.equal(r.status, 'written');
  assert.deepEqual(r.events.filter(e => e.eventId === '14').map(e => e.id), ['1401', '1402']);
});

test('a re-signed image URL alone is not a change; a real edit is', async () => {
  const file = outPath();
  await run({ env: ENV, fetchImpl: fakeFetch().impl, now: NOW, outFile: file, ...quiet });
  const resigned = structuredClone(PAGE2);
  resigned.included.find(e => e.type === 'Event' && e.id === '12').attributes.image_url = PNO_IMG.replace('1893456000', '1893999999').replace('abc123', 'zzz999');
  let r = await run({ env: ENV, fetchImpl: fakeFetch([PAGE1, resigned]).impl, now: NOW, outFile: file, ...quiet });
  assert.equal(r.status, 'unchanged');
  const renamed = structuredClone(PAGE2);
  renamed.data.find(i => i.id === '1201').attributes.name = 'Parents Night Out (Valentine’s)';
  r = await run({ env: ENV, fetchImpl: fakeFetch([PAGE1, renamed]).impl, now: NOW, outFile: file, ...quiet });
  assert.equal(r.status, 'written');
  assert.equal(JSON.parse(readFileSync(file, 'utf8')).events.at(-1).name, 'Parents Night Out (Valentine’s)');
});

test('a stored signed image URL near expiry is refreshed only by one that lasts longer', async () => {
  const file = outPath();
  const soon = Math.floor(NOW.getTime() / 1000) + 3600;
  const old = { updated: '2026-10-20T00:00:00Z', events: EXPECTED.map(e => e.image ? { ...e, image: PNO_IMG.replace('1893456000', String(soon)) } : e) };
  writeFileSync(file, JSON.stringify(old, null, 2) + '\n');
  const r = await run({ env: ENV, fetchImpl: fakeFetch().impl, now: NOW, outFile: file, ...quiet });
  assert.equal(r.status, 'written');
  assert.equal(JSON.parse(readFileSync(file, 'utf8')).events.at(-1).image, PNO_IMG);
  assert.equal(urlExpiry(PNO_IMG), 1893456000 * 1000);
  assert.equal(urlExpiry('https://x.s3.amazonaws.com/a.jpg?X-Amz-Date=20261024T160000Z&X-Amz-Expires=3600'), Date.parse('2026-10-24T17:00:00Z'));
  assert.equal(urlExpiry('https://example.com/a.jpg'), null);
});

test('no commit loop when PC keeps serving the same soon-to-expire image URL', async () => {
  // expires on a fixed boundary 6h after the first run; PC hands out that same URL every time
  const eod = Math.floor(Date.parse('2026-10-24T22:00:00Z') / 1000);
  const img = PNO_IMG.replace('1893456000', String(eod));
  const page2 = structuredClone(PAGE2);
  page2.included.find(e => e.type === 'Event' && e.id === '12').attributes.image_url = img;
  const file = outPath();
  const statuses = [];
  for (let k = 0; k < 6; k++) {
    const now = new Date(NOW.getTime() + k * 30 * 60000);
    statuses.push((await run({ env: ENV, fetchImpl: fakeFetch([PAGE1, page2]).impl, now, outFile: file, ...quiet })).status);
  }
  assert.deepEqual(statuses, ['written', 'unchanged', 'unchanged', 'unchanged', 'unchanged', 'unchanged']);
  // after the boundary, PC's next URL lasts a day longer: replaced once, then quiet again
  const page2b = structuredClone(page2);
  page2b.included.find(e => e.type === 'Event' && e.id === '12').attributes.image_url = PNO_IMG.replace('1893456000', String(eod + 86400)).replace('abc123', 'next');
  const after = new Date('2026-10-24T22:13:00Z');
  assert.equal((await run({ env: ENV, fetchImpl: fakeFetch([PAGE1, page2b]).impl, now: after, outFile: file, ...quiet })).status, 'written');
  assert.equal((await run({ env: ENV, fetchImpl: fakeFetch([PAGE1, page2b]).impl, now: new Date(after.getTime() + 1800000), outFile: file, ...quiet })).status, 'unchanged');
  assert.equal(imageRefreshDue([{ id: '1', image: img }], [{ id: '1', image: img }], new Date(eod * 1000 + 60000)), false, 'expired, but nothing better on offer');
});

test('missing secrets: skip, exit cleanly, never touch the file or the network', async () => {
  const file = outPath();
  writeFileSync(file, '{"updated":"x","events":[]}\n');
  const f = fakeFetch();
  for (const env of [{}, { PC_EVENTS_APP_ID: 'a' }, { PC_EVENTS_APP_ID: ' ', PC_EVENTS_SECRET: 's' }]) {
    const r = await run({ env, fetchImpl: f.impl, now: NOW, outFile: file, ...quiet });
    assert.equal(r.status, 'skipped');
  }
  assert.equal(f.calls.length, 0);
  assert.equal(existsSync(icsDirOf(file)), false, 'no calendar files either');
  assert.equal(existsSync(feedOf(file)), false);
  assert.equal(readFileSync(file, 'utf8'), '{"updated":"x","events":[]}\n');
  const fresh = outPath();
  await run({ env: {}, fetchImpl: f.impl, now: NOW, outFile: fresh, ...quiet });
  assert.equal(existsSync(fresh), false);
});

test('API errors keep the last-good file, never echo the secret, and say whether a human is needed', async () => {
  const file = outPath();
  writeFileSync(file, 'LAST GOOD');
  const cases = [
    [() => failure(401, { errors: [{ title: 'Unauthorized' }] }), false],
    [() => failure(403, {}), false],
    [() => ({ ok: false, status: 503, headers: { get: () => null }, json: async () => { throw new Error('html'); } }), true],
    [() => failure(429, {}), true],
    [() => { throw new Error('ECONNRESET'); }, true],
    [() => ({ ok: true, status: 200, headers: { get: () => null }, json: async () => ({ errors: [] }) }), false],
    // the main query works but the held-back query fails: still nothing written
    [(k, isHeld) => (isHeld ? failure(503) : null), true],
    [(k, isHeld) => (isHeld ? failure(400, { errors: [{ title: 'Bad filter' }] }) : null), false],
  ];
  for (const [failWith, transient] of cases) {
    const f = fakeFetch(undefined, { failWith });
    await assert.rejects(run({ env: ENV, fetchImpl: f.impl, now: NOW, outFile: file, ...quiet }), e => {
      assert.ok(!e.message.includes('sekrit') && !e.message.includes('app-id-123'), e.message);
      assert.equal(e.transient, transient, e.message);
      return true;
    });
  }
  assert.equal(readFileSync(file, 'utf8'), 'LAST GOOD');
  assert.equal(existsSync(icsDirOf(file)), false, 'a failed run writes no calendar files');
  assert.equal(existsSync(feedOf(file)), false);
});

test('retries a 429 after Retry-After, then succeeds', async () => {
  const waits = [];
  const base = fakeFetch();
  let first = true;
  const impl = async (url, init) => {
    if (first) { first = false; return { ok: false, status: 429, headers: { get: h => (h === 'retry-after' ? '7' : null) }, json: async () => ({}) }; }
    return base.impl(url, init);
  };
  const r = await run({ env: ENV, fetchImpl: impl, now: NOW, outFile: outPath(), log: () => {}, sleep: async ms => { waits.push(ms); } });
  assert.equal(r.status, 'written');
  assert.deepEqual(waits, [7000]);
});

test('never sends credentials to a next link off the Calendar API', async () => {
  const evil = structuredClone(PAGE1);
  evil.links.next = 'https://evil.example.com/steal?x=1';
  const f = fakeFetch([evil]);
  const file = outPath();
  await assert.rejects(run({ env: ENV, fetchImpl: f.impl, now: NOW, outFile: file, ...quiet }), /outside/);
  assert.equal(f.calls.length, 1);
  assert.ok(f.calls.every(c => c.url.startsWith(API + '/')));
  assert.equal(existsSync(file), false);
});

test('a broken response shape fails instead of writing a short or empty list', async () => {
  const one = () => { const p = structuredClone(PAGE1); p.links.next = null; return p; };
  const noKind = one(); for (const i of noKind.data) delete i.attributes.kind;
  const noIncluded = one(); noIncluded.included = [];
  const noVisibility = one(); delete noVisibility.included[0].attributes.visible_in_church_center;
  const noRelationships = one(); for (const i of noRelationships.data) delete i.relationships;
  const orphan = one(); orphan.data.push(inst(4041, 404, { name: 'Orphan instance', starts_at: '2027-01-05T17:00:00Z' }));
  // page 2 without its included events, or without the fieldset (a next link that dropped params)
  const page2NoIncluded = structuredClone(PAGE2); page2NoIncluded.included = [];
  const page2NoKind = structuredClone(PAGE2); for (const i of page2NoKind.data) delete i.attributes.kind;
  const cases = [[noKind], [noIncluded], [noVisibility], [noRelationships], [orphan], [PAGE1, page2NoIncluded], [PAGE1, page2NoKind]];
  for (const pages of cases) {
    const file = outPath();
    await assert.rejects(run({ env: ENV, fetchImpl: fakeFetch(pages).impl, now: NOW, outFile: file, ...quiet }), e => e.transient === false);
    assert.equal(existsSync(file), false);
  }
});

test('un-publishing everything empties the list (it is not treated as an error)', async () => {
  const file = outPath();
  await run({ env: ENV, fetchImpl: fakeFetch().impl, now: NOW, outFile: file, ...quiet });
  const r = await run({ env: ENV, fetchImpl: fakeFetch([NO_HELD], { held: [NO_HELD] }).impl, now: NOW, outFile: file, ...quiet });
  assert.equal(r.status, 'written');
  assert.deepEqual(JSON.parse(readFileSync(file, 'utf8')).events, []);
});

test('the log names kept events only', async () => {
  const lines = [];
  await run({ env: ENV, fetchImpl: fakeFetch().impl, now: NOW, outFile: outPath(), log: l => lines.push(l), sleep: async () => {} });
  const text = lines.join('\n');
  for (const word of PRIVATE) assert.ok(!text.includes(word), 'log leaked: ' + word);
  assert.match(text, /held back: event request pending or rejected/);
  assert.match(text, /Parents Night Out/);
});

// ---- calendar files ----

test('calendar text: escaping and control characters', () => {
  assert.equal(icsText('Back\\slash; semi, comma\nline\r\nCRLF\rCR'), 'Back\\\\slash\\' + '; semi\\, comma\\nline\\nCRLF\\nCR');
  assert.equal(icsText('tab\tok\u0007bell\u0000nul'), 'tab\tokbellnul', 'HTAB kept, other controls dropped');
  assert.equal(icsText('Pizza & “quotes” — fine: 🙏'), 'Pizza & “quotes” — fine: 🙏');
});

test('folding: 75 octets max, never inside a UTF-8 character, unfolds to the original', () => {
  const cases = [
    'DESCRIPTION:' + 'a'.repeat(200),
    'SUMMARY:' + 'é'.repeat(80),                                  // 2-byte chars across every fold
    'DESCRIPTION:' + 'x'.repeat(62) + '🙏🏽 Café niño ' + '漢字'.repeat(40) + ' 👨‍👩‍👧 end', // fold lands inside the emoji run
    'LOCATION:' + 'b'.repeat(66),                                 // exactly 75: no fold
    'LOCATION:' + 'b'.repeat(67),                                 // 76: one fold
  ];
  for (const line of cases) {
    const folded = icsFold(line);
    const parts = folded.split('\r\n');
    for (const [k, p] of parts.entries()) {
      const bytes = Buffer.from(p, 'utf8');
      assert.ok(bytes.length <= 75, `line ${k} is ${bytes.length} octets`);
      assert.equal(bytes.toString('utf8'), p, 'each physical line is whole UTF-8');
      assert.ok(!p.includes('�'));
      if (k > 0) assert.equal(p[0], ' ', 'continuations start with one space');
      if (k > 0) assert.ok(bytes.length > 1, 'no empty continuation');
    }
    assert.equal(folded.replace(/\r\n /g, ''), line);
  }
  assert.equal(icsFold('LOCATION:' + 'b'.repeat(66)).includes('\r\n'), false);
  assert.equal(icsFold('LOCATION:' + 'b'.repeat(67)).split('\r\n').length, 2);
  // a continuation never splits a surrogate pair either
  const folded = icsFold('X:' + '🙏'.repeat(60));
  for (const p of folded.split('\r\n')) assert.ok(!/[\uD800-\uDBFF]$/.test(p) && !/^ ?[\uDC00-\uDFFF]/.test(p));
});

test('all-day dates: Los Angeles days, exclusive end, multi-day, across DST, UTC-midnight stamps', () => {
  const d = (starts, ends) => allDayDates({ starts, ends, allDay: true });
  assert.deepEqual(d('2026-10-25T07:00:00Z', '2026-10-26T06:59:59Z'), ['20261025', '20261026'], 'one PDT day');
  assert.deepEqual(d('2026-11-07T08:00:00Z', '2026-11-08T07:59:59Z'), ['20261107', '20261108'], 'one PST day');
  assert.deepEqual(d('2026-11-06T08:00:00Z', '2026-11-09T07:59:59Z'), ['20261106', '20261109'], 'Fri-Sun');
  assert.deepEqual(d('2026-10-31T07:00:00Z', '2026-11-02T07:59:59Z'), ['20261031', '20261102'], 'across the Nov 1 DST change');
  assert.deepEqual(d('2026-12-31T08:00:00Z', '2027-01-02T08:00:00Z'), ['20261231', '20270102'], 'end AT midnight adds no day; year rollover');
  assert.deepEqual(d('2026-12-24T00:00:00Z', '2026-12-25T00:00:00Z'), ['20261224', '20261225'], 'UTC-midnight stamp read in UTC (as the site does)');
  assert.deepEqual(d('2026-11-18T08:00:00Z', null), ['20261118', '20261119'], 'no end: one day');
});

test('event fields: UTC times, location, description, URL, all-day transparency', () => {
  const pno = { ...EXPECTED.find(e => e.id === '1201'), location: 'Arroyo Church' };
  const l = icsEvent(pno, '20261024T160000Z');
  assert.deepEqual(l.slice(0, 7), ['BEGIN:VEVENT', 'UID:1201@arroyochurch.com', 'DTSTAMP:20261024T160000Z', 'LAST-MODIFIED:20261024T160000Z', 'SEQUENCE:427200', 'DTSTART:20270213T010000Z', 'DTEND:20270213T040000Z']);
  assert.ok(l.includes('SUMMARY:Parents Night Out'));
  assert.ok(l.includes('LOCATION:Arroyo Church\\, 945 Concannon Blvd\\, Livermore\\, CA 94550'), 'bare "Arroyo Church" expanded');
  assert.ok(l.includes('DESCRIPTION:Drop the kids off for a night of games & pizza.\\n\\nAges 3–10.\\nFree — just RSVP.\\n\\n• Dinner at 5:30\\n• Movie at 7\\n\\nQuestions? Our kids page (https://www.arroyochurch.com/kids)\\n\\nDetails: ' + EP + '1201\\nRegister: ' + CC + '/registrations/events/2850002'), 'the description, not the summary');
  assert.ok(l.includes('URL:' + CC + '/registrations/events/2850002'), 'URL = the registration link');
  assert.ok(!l.includes('TRANSP:TRANSPARENT'));
  // a room name stays as PC has it; no location in PC = no LOCATION line
  assert.ok(icsEvent(EXPECTED[1], 'x').includes('LOCATION:Arroyo Church\\, Room 4'));
  const bap = icsEvent(EXPECTED[0], '20261024T160000Z');
  assert.ok(!bap.some(x => x.startsWith('LOCATION')), 'no invented location');
  assert.ok(bap.includes('DTSTART;VALUE=DATE:20261025') && bap.includes('DTEND;VALUE=DATE:20261026') && bap.includes('TRANSP:TRANSPARENT'));
  assert.ok(bap.includes('DESCRIPTION:Details: ' + EP + '101') && bap.includes('URL:' + EP + '101'));
  // no end in PC: no DTEND invented; no url either: no DESCRIPTION / URL
  const bare = icsEvent({ id: '9', name: 'Bare', starts: '2026-11-01T19:00:00Z', ends: null, allDay: false, location: null, summary: null, url: null, registerUrl: null }, 'x');
  assert.deepEqual(bare.slice(4), ['SEQUENCE:0', 'DTSTART:20261101T190000Z', 'SUMMARY:Bare', 'DESCRIPTION:Details: ' + EP + '9', 'URL:' + EP + '9', 'END:VEVENT']);
  const none = icsEvent({ id: '../x', name: 'Bare', starts: '2026-11-01T19:00:00Z', ends: null, allDay: false, location: null, summary: null, url: null, registerUrl: null }, 'x');
  assert.ok(!none.some(x => x.startsWith('DESCRIPTION') || x.startsWith('URL')), 'no usable id and no url: no DESCRIPTION / URL');
  // the whole file: CRLF only, folded, valid frame
  const text = calendarText(['BEGIN:VCALENDAR', 'VERSION:2.0'], [l]);
  assert.ok(!/[^\r]\n/.test(text) && text.endsWith('END:VCALENDAR\r\n'));
  assert.ok(text.split('\r\n').every(x => Buffer.byteLength(x) <= 75));
});

test('DESCRIPTION: the description, else the summary, then the Details / Register lines', () => {
  const base = { id: '7', url: CC + '/calendar/event/7', registerUrl: null };
  assert.equal(icsDescription({ ...base, summary: 'Short', description: 'Long one.\n\n• Item' }), 'Long one.\n\n• Item\n\nDetails: ' + EP + '7');
  assert.equal(icsDescription({ ...base, summary: 'Short', description: null }), 'Short\n\nDetails: ' + EP + '7');
  assert.equal(icsDescription({ ...base, summary: 'Short' }), 'Short\n\nDetails: ' + EP + '7', 'a row from before the field existed');
  assert.equal(icsDescription({ ...base, url: null, summary: null, description: null }), 'Details: ' + EP + '7');
  assert.equal(icsDescription({ ...base, id: undefined, summary: 'Short' }), 'Short\n\nDetails: ' + CC + '/calendar/event/7', 'no usable id: Church Center fallback');
  assert.equal(icsDescription({ ...base, id: undefined, url: null, summary: null, description: null }), null);
  const line = icsEvent({ ...base, name: 'X', starts: '2026-11-01T19:00:00Z', ends: null, allDay: false, location: null, summary: null, description: 'A, b; c\\d\n\nnext' }, 'x').find(x => x.startsWith('DESCRIPTION:'));
  assert.equal(line, 'DESCRIPTION:A\\, b\\; c\\\\d\\n\\nnext\\n\\nDetails: ' + EP + '7', 'escaped as TEXT');
});

test('SEQUENCE: the stamp in minutes since 2026-01-01, so a later stamp always gets a higher one', () => {
  assert.equal(icsSequence('20261024T160000Z'), 427200);
  assert.equal(icsSequence('20261024T160059Z'), 427200, 'whole minutes');
  assert.equal(icsSequence('20261024T160100Z'), 427201);
  assert.equal(icsSequence('20260101T000000Z'), 0);
  assert.equal(icsSequence('20251231T235959Z'), 0, 'never below 0');
  assert.equal(icsSequence('x'), 0, 'unreadable stamp');
  assert.ok(icsSequence('20991231T235959Z') < 2 ** 31, 'an RFC 5545 INTEGER for decades');
});

test('a run writes one file per public row + the feed, and nothing for a private or held-back event', async () => {
  const file = outPath();
  const r = await run({ env: ENV, fetchImpl: fakeFetch().impl, now: NOW, outFile: file, ...quiet });
  assert.deepEqual(r.calendars, { written: EXPECTED.length + 1, removed: 0 });
  assert.deepEqual(icsFiles(file), EXPECTED.map(e => e.id + '.ics').sort());
  assert.deepEqual(JSON.parse(readFileSync(file, 'utf8')).events.map(e => e.ics), EXPECTED.map(e => `data/events/ics/${e.id}.ics`));
  const feed = readFileSync(feedOf(file), 'utf8');
  const all = feed + icsFiles(file).map(f => readFileSync(join(icsDirOf(file), f), 'utf8')).join('');
  for (const word of [...PRIVATE, 'Private Ln', 'Festival Field', 'UID:601@', 'UID:801@', 'UID:901@', 'UID:701@', 'UID:1001@', 'UID:1301@', 'UID:1401@', 'UID:1402@']) {
    assert.ok(!all.includes(word), 'leaked into a calendar file: ' + word);
  }
  // the feed: calendar name, zone, refresh hints, every row once, in order
  for (const h of ['X-WR-CALNAME:Arroyo Church', 'X-WR-TIMEZONE:America/Los_Angeles', 'REFRESH-INTERVAL;VALUE=DURATION:PT6H', 'X-PUBLISHED-TTL:PT6H', 'METHOD:PUBLISH', 'CALSCALE:GREGORIAN']) {
    assert.ok(unfold(feed).includes(h), 'feed has ' + h);
  }
  assert.deepEqual(unfold(feed).filter(x => x.startsWith('UID:')), EXPECTED.map(e => `UID:${e.id}@arroyochurch.com`));
  assert.equal(unfold(feed).filter(x => x === 'BEGIN:VEVENT').length, EXPECTED.length);
  // a single-event file: the same VEVENT the feed carries, no feed-only headers
  const one = readIcs(file, '1201');
  assert.equal(unfold(one)[0], 'BEGIN:VCALENDAR');
  assert.ok(!one.includes('X-WR-CALNAME'));
  const vevent = t => t.slice(t.indexOf('BEGIN:VEVENT'), t.indexOf('END:VEVENT') + 10);
  assert.ok(feed.includes(vevent(one)));
  assert.equal(prop(one, 'DTSTAMP'), 'DTSTAMP:20261024T160000Z');
  for (const f of icsFiles(file)) {
    const t = readFileSync(join(icsDirOf(file), f), 'utf8');
    assert.ok(!/[^\r]\n/.test(t), f + ': CRLF only');
    assert.ok(t.split('\r\n').every(x => Buffer.byteLength(x) <= 75), f + ': folded');
  }
});

test('calendar files are byte-stable across runs: no commit every 30 minutes', async () => {
  const file = outPath();
  await run({ env: ENV, fetchImpl: fakeFetch().impl, now: NOW, outFile: file, ...quiet });
  const first = allSnapshot(file);
  for (let k = 1; k <= 3; k++) {
    const r = await run({ env: ENV, fetchImpl: fakeFetch().impl, now: new Date(NOW.getTime() + k * 30 * 60000), outFile: file, ...quiet });
    assert.equal(r.status, 'unchanged');
    assert.deepEqual(r.calendars, { written: 0, removed: 0 });
  }
  assert.deepEqual(allSnapshot(file), first);
});

test('editing one event re-stamps only that file (and the feed); the others keep their bytes', async () => {
  const file = outPath();
  await run({ env: ENV, fetchImpl: fakeFetch().impl, now: NOW, outFile: file, ...quiet });
  const before = allSnapshot(file);
  const moved = structuredClone(PAGE1);
  Object.assign(moved.data.find(i => i.id === '301').attributes, { location: 'Arroyo Church' });
  const later = new Date('2026-10-25T03:13:00Z');
  const r = await run({ env: ENV, fetchImpl: fakeFetch([moved, PAGE2]).impl, now: later, outFile: file, ...quiet });
  assert.equal(r.status, 'written');
  assert.deepEqual(r.calendars, { written: 2, removed: 0 });
  const after = allSnapshot(file);
  for (const f of Object.keys(before)) if (f !== '301.ics' && f !== 'feed') assert.equal(after[f], before[f], f + ' untouched');
  assert.equal(prop(after['301.ics'], 'DTSTAMP'), 'DTSTAMP:20261025T031300Z');
  assert.equal(prop(after['301.ics'], 'LAST-MODIFIED'), 'LAST-MODIFIED:20261025T031300Z');
  assert.equal(prop(before['301.ics'], 'SEQUENCE'), 'SEQUENCE:427200');
  assert.equal(prop(after['301.ics'], 'SEQUENCE'), 'SEQUENCE:427873', 'the edit raised SEQUENCE');
  assert.equal(prop(after['301.ics'], 'LOCATION'), 'LOCATION:Arroyo Church\\, 945 Concannon Blvd\\, Livermore\\, CA 94550');
  assert.ok(after.feed.includes('DTSTAMP:20261025T031300Z') && after.feed.includes('DTSTAMP:20261024T160000Z'));
});

test('adding descriptions: events.json changes once; only an event WITH a description gets a new calendar file', async () => {
  const file = outPath();
  const first = await run({ env: ENV, fetchImpl: fakeFetch().impl, now: NOW, outFile: file, ...quiet });
  // put the folder back the way the previous sync left it: no description key, calendar files built from the summary
  const old = first.events.map(({ description, ...rest }) => rest);
  writeFileSync(file, JSON.stringify({ updated: '2026-10-24T16:00:00Z', events: old }, null, 2) + '\n');
  writeCalendars(old, { icsDir: icsDirOf(file), feedFile: feedOf(file), now: NOW });
  const before = allSnapshot(file);
  assert.ok(!unfold(before['1201.ics']).some(x => x.includes('• Dinner')), 'fixture sanity: the old file carries the summary');
  const later = new Date('2026-10-25T03:13:00Z');
  const r = await run({ env: ENV, fetchImpl: fakeFetch().impl, now: later, outFile: file, ...quiet });
  assert.equal(r.status, 'written', 'the new field is a one-time change to events.json');
  assert.deepEqual(r.calendars, { written: 2, removed: 0 }, 'Parents Night Out (the one with a description) + the feed');
  const after = allSnapshot(file);
  for (const f of Object.keys(before)) if (f !== '1201.ics' && f !== 'feed') assert.equal(after[f], before[f], f + ' keeps its bytes');
  assert.ok(unfold(after['1201.ics']).some(x => x.startsWith('DESCRIPTION:') && x.includes('• Dinner at 5:30')));
  // and from then on, quiet
  const again = await run({ env: ENV, fetchImpl: fakeFetch().impl, now: new Date(later.getTime() + 1800000), outFile: file, ...quiet });
  assert.equal(again.status, 'unchanged');
  assert.deepEqual(again.calendars, { written: 0, removed: 0 });
  assert.deepEqual(allSnapshot(file), after);
});

test('un-publishing an event deletes its file and drops it from the feed; other files are left alone', async () => {
  const file = outPath();
  await run({ env: ENV, fetchImpl: fakeFetch().impl, now: NOW, outFile: file, ...quiet });
  writeFileSync(join(icsDirOf(file), 'README.txt'), 'not ours');
  writeFileSync(join(icsDirOf(file), '999.ics'), 'a stale file from an old run');
  const hidden = structuredClone(PAGE2);
  hidden.included.find(e => e.type === 'Event' && e.id === '12').attributes.visible_in_church_center = false;
  const r = await run({ env: ENV, fetchImpl: fakeFetch([PAGE1, hidden]).impl, now: NOW, outFile: file, ...quiet });
  assert.deepEqual(r.calendars, { written: 1, removed: 2 }, 'the feed rewritten; 1201.ics and the stale 999.ics removed');
  assert.ok(!icsFiles(file).includes('1201.ics') && !icsFiles(file).includes('999.ics'));
  assert.ok(icsFiles(file).includes('README.txt'));
  assert.ok(!readFileSync(feedOf(file), 'utf8').includes('Parents Night Out'));
  // everything un-published: an empty (still valid-framed) feed and no event files
  const r2 = await run({ env: ENV, fetchImpl: fakeFetch([NO_HELD], { held: [NO_HELD] }).impl, now: NOW, outFile: file, ...quiet });
  assert.equal(r2.calendars.removed, EXPECTED.length - 1);
  assert.deepEqual(icsFiles(file), ['README.txt']);
  assert.ok(!readFileSync(feedOf(file), 'utf8').includes('BEGIN:VEVENT'));
});

test("PC saved locations: the church's own becomes plain 'Arroyo Church'; others lose the space before each comma", () => {
  assert.equal(cleanLocation('Arroyo Church  - 945 Concannon Blvd. , Livermore , CA 94550'), 'Arroyo Church');
  assert.equal(cleanLocation('Arroyo Church Kids Wing'), 'Arroyo Church Kids Wing');
  assert.equal(cleanLocation('Lester J. Knott Park , Livermore , CA'), 'Lester J. Knott Park, Livermore, CA');
  assert.equal(cleanLocation('  '), null);
  assert.equal(cleanLocation(null), null);
});

test('an id that is not a safe file name gets no file and no ics path', async () => {
  const page = { links: { next: null }, data: [inst('../../x', 1, { name: 'Odd id', starts_at: '2026-11-01T17:00:00Z' })], included: [EVENTS.baptisms] };
  const file = outPath();
  const r = await run({ env: ENV, fetchImpl: fakeFetch([page], { held: [NO_HELD] }).impl, now: NOW, outFile: file, ...quiet });
  assert.equal(r.events.length, 1);
  assert.equal(r.events[0].ics, null);
  assert.deepEqual(icsFiles(file), []);
  assert.ok(!readFileSync(feedOf(file), 'utf8').includes('Odd id'));
  // writeCalendars on its own refuses it too, even with a forged ics path
  const dir = join(tmp, 'forged');
  writeCalendars([{ ...r.events[0], ics: 'data/events/ics/x.ics' }], { icsDir: join(dir, 'ics'), feedFile: join(dir, 'feed.ics'), now: NOW });
  assert.deepEqual(readdirSync(join(dir, 'ics')), []);
});

// ---- run ----

let failed = 0;
for (const t of tests) {
  try {
    await t.fn();
    console.log('ok   ' + t.name);
  } catch (e) {
    failed++;
    console.log('FAIL ' + t.name + '\n     ' + (e.stack || e.message).split('\n').slice(0, 6).join('\n     '));
  }
}
rmSync(tmp, { recursive: true, force: true });
console.log(`\n${tests.length - failed}/${tests.length} passed (TZ=${process.env.TZ || Intl.DateTimeFormat().resolvedOptions().timeZone})`);
if (failed) process.exit(1);

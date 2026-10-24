// Tests for scripts/sync-events.mjs. Plain node, no dependencies, no network, no token:
//   node scripts/test-sync-events.mjs
// The fixture is shaped like real Planning Center Calendar responses (JSON:API, two pages, included
// events and event times) and mixes the church's real public events with the private ones that must
// never reach the public data/events.json. The private ones are in the fixture as if the server had
// ignored the where[] params, so the script's own filter is what keeps them out. A second fixture
// answers the pending/rejected event-request query.
// The results must not depend on the machine's time zone: run it under TZ=UTC and TZ=America/Los_Angeles.

import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
  run, buildEvents, plainText, isPublic, firstPageUrl, urlExpiry, publicTimes, utcTime, imageRefreshDue,
  API, API_VERSION, WINDOW_DAYS, SERIES_ROWS, HELD_BACK_SCOPE,
} from './sync-events.mjs';

const NOW = new Date('2026-10-24T16:00:00Z');
const CC = 'https://arroyo-church-434989.churchcenter.com';
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
  moms: ev(6, { name: "Mom's Group", visible_in_church_center: false }),
  thanksgiving: ev(7, { name: 'Team Arroyo Thanksgiving', visible_in_church_center: false }),
  shower: ev(8, { name: 'Ramos Baby Shower', link_only: true }),                 // published, but link-only
  blockout: ev(9, { name: 'Building closed' }),                                    // its instance is a blockout
  leaders: ev(10, { name: 'Connect Group Leader Appreciation and Training', visible_in_church_center: false }),
  womens: ev(11, { name: "Women's Event", approval_status: 'P' }),                 // rooms pending: still shows
  pno: ev(12, {
    name: 'Parents Night Out', featured: true, image_url: PNO_IMG,
    registration_url: `${CC}/registrations/events/2850002`,
    description: '<p>Drop the kids off for a night of games &amp; pizza.</p><p>Ages 3&ndash;10.<br>Free &#8212; just RSVP.</p><script>alert(1)</script>',
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

const row = r => ({ summary: null, ends: null, allDay: false, location: null, image: null, url: `${CC}/calendar/event/${r.id}`, registerUrl: null, featured: false, recurrence: null, ...r });
const KEYS = ['id', 'eventId', 'name', 'summary', 'starts', 'ends', 'allDay', 'location', 'image', 'url', 'registerUrl', 'featured', 'recurrence'];
const ordered = r => Object.fromEntries(KEYS.map(k => [k, r[k]]));
const CONNECT = { eventId: '2', name: 'Connect class', summary: 'New to Arroyo? Start here.', recurrence: 'Monthly on the 4th Sunday' };
const FOUNDATIONS = { eventId: '3', name: 'Foundations class', registerUrl: 'https://arroyo-church-434989.churchcenter.com/registrations/events/2840001' };

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
  row({ id: '1201', eventId: '12', name: 'Parents Night Out', summary: 'Drop the kids off for a night of games & pizza.\nAges 3–10.\nFree — just RSVP.', starts: '2027-02-13T01:00:00Z', ends: '2027-02-13T04:00:00Z', location: 'Arroyo Church Kids Wing', image: PNO_IMG, registerUrl: `${CC}/registrations/events/2850002`, featured: true }),
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
const outPath = () => join(tmp, `events-${++n}.json`);

// ---- tests ----

test('public filter: exactly the published, standard, non-link-only, approved events, sorted', () => {
  const out = buildEvents([...PAGE2_DATA, ...PAGE1_DATA], allIncluded(), NOW, { held: heldIds }); // shuffled: still sorted
  assert.deepEqual(out, EXPECTED);
});

test('no private event name, place or id leaks into the output', () => {
  const json = JSON.stringify(buildEvents([...PAGE1_DATA, ...PAGE2_DATA], allIncluded(), NOW, { held: heldIds }));
  for (const word of [...PRIVATE, 'Private Ln', 'Festival Field', '"601"', '"801"', '"901"', '"701"', '"1001"', '"1301"', '"1401"', '"1402"']) {
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

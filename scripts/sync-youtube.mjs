// Auto-sync the latest sermons + podcast episodes from YouTube into data/*.json.
//
// Runs in GitHub Actions (Node 20+). KEY-FREE by default: it reads YouTube's public
// per-playlist RSS feeds (no API key, no quota, no CORS issue server-side). If a
// YT_API_KEY secret is present, it ALSO auto-detects the *newest* series playlist via
// the Data API (so a brand-new sermon series is picked up with zero manual edits).
//
// Failure handling: if a feed is empty or errors, the script exits non-zero WITHOUT
// writing, so the previously-committed JSON (last-good) is preserved.
//
// Config via env (all optional): SERIES_PLAYLIST_ID, PODCAST_PLAYLIST_ID, YT_API_KEY.
//
// Sermon dates. Each sermon in data/sermons.json is {id, title, published, service} (additive: older
// readers still take {id, title}):
//   published = the RSS <published> time, exactly as YouTube reports it (ISO, UTC)
//   service   = the Sunday it was preached, YYYY-MM-DD in America/Los_Angeles, decided in this order:
//     1. data/sermon-dates.json  { "<videoId>": "YYYY-MM-DD" }  — a hand-kept override that wins over
//        everything. Plain JSON, no comments; {} means none. Add a line for a LATE upload, e.g. a
//        standalone 10/4 sermon uploaded 10/14 would otherwise read as 10/11.
//     2. with YT_API_KEY, a livestream's liveStreamingDetails.actualStartTime (its LA date)
//     3. otherwise the Sunday on or before the RSS published time in LA. The edited sermon video goes
//        up late Sunday night or just after midnight (the 10/18 one: 2026-10-19T06:50:18Z = Sun 11:50pm
//        PT), and an upload later that week still lands on its own Sunday.
// The home page's sermon cards show this date and link that week's notes (links.arroyochurch.com/notes/
// ?week=<service>), and the notes page matches each week's video by it. Sermons are listed newest
// service first (then newest upload). Two sermons on the same Sunday print a warning naming both ids.
// Note: a late upload dated back by the override file sorts BELOW the newer week, so it is never
// videos[0] and the daily blog run (scripts/generate_blog.py) will not draft it on its own. Draft it
// by hand with BLOG_VIDEO_ID, BLOG_VIDEO_TITLE and BLOG_SERVICE_DATE (see that script).

import { writeFileSync, mkdirSync, readFileSync, existsSync } from 'node:fs';

const CHANNEL_ID = 'UCH8pQEu1LJ3INkPyzT4Pndg';                                   // @arroyochurch
const SERIES_PLAYLIST_ID  = process.env.SERIES_PLAYLIST_ID  || 'PLSIHs6mCX_TU'; // current series "Transformational Stories" (update per new series, or set YT_API_KEY to auto-detect)
const PODCAST_PLAYLIST_ID = process.env.PODCAST_PLAYLIST_ID || 'PLqCyakXjbp1M974oafBq-gB2Nywu0liuX';
const API_KEY = process.env.YT_API_KEY || '';
const MAX = 6; // how many videos to carry per section

function decode(s) {
  return (s || '')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&apos;/g, "'")
    .trim();
}

function parseFeed(xml) {
  // feed-level <title> (the playlist's own title) is the first <title> before any <entry>
  const head = xml.split('<entry>')[0];
  const feedTitle = decode((head.match(/<title>([\s\S]*?)<\/title>/) || [])[1] || '');
  const entries = [];
  const re = /<entry>([\s\S]*?)<\/entry>/g;
  let m;
  while ((m = re.exec(xml))) {
    const e = m[1];
    const id = (e.match(/<yt:videoId>([^<]+)<\/yt:videoId>/) || [])[1];
    const title = (e.match(/<title>([\s\S]*?)<\/title>/) || [])[1];
    const published = (e.match(/<published>([^<]+)<\/published>/) || [])[1] || '';
    const desc = (e.match(/<media:description>([\s\S]*?)<\/media:description>/) || [])[1] || '';
    if (id && title) entries.push({ id, title: decode(title), published, descLen: desc.length });
  }
  return { feedTitle, entries };
}

async function feed(playlistId) {
  const r = await fetch('https://www.youtube.com/feeds/videos.xml?playlist_id=' + playlistId);
  if (!r.ok) throw new Error('RSS ' + r.status + ' for playlist ' + playlistId);
  return parseFeed(await r.text());
}

// Optional: with an API key, pick the most recently-created playlist (= current series).
async function resolveSeriesPlaylistId() {
  if (!API_KEY) return SERIES_PLAYLIST_ID;
  try {
    const url = 'https://www.googleapis.com/youtube/v3/playlists?part=snippet&channelId='
      + CHANNEL_ID + '&maxResults=50&key=' + API_KEY;
    const r = await fetch(url);
    if (!r.ok) return SERIES_PLAYLIST_ID;
    const data = await r.json();
    const exclude = /podcast|worship night|music|shorts|clips|highlights/i;
    const cand = (data.items || [])
      .filter(p => p.id !== PODCAST_PLAYLIST_ID && !exclude.test(p.snippet?.title || ''))
      .sort((a, b) => new Date(b.snippet.publishedAt) - new Date(a.snippet.publishedAt));
    return cand.length ? cand[0].id : SERIES_PLAYLIST_ID;
  } catch {
    return SERIES_PLAYLIST_ID;
  }
}

// Standalone / one-off sermons (guest speakers, weeks between series) are in NO series
// playlist, so the playlist feed alone silently misses them. Full sermons carry the long
// structured description (~2.7-2.9k chars); every short, clip and podcast episode on this
// channel is under ~550. That gap is the discriminator, and it needs no API key.
const SERMON_MIN_DESC = Number(process.env.SERMON_MIN_DESC || 1200);
const NOT_A_SERMON = /podcast|worship night/i;

async function channelSermons() {
  try {
    const r = await fetch('https://www.youtube.com/feeds/videos.xml?channel_id=' + CHANNEL_ID);
    if (!r.ok) return [];
    return parseFeed(await r.text()).entries
      .filter(e => e.descLen >= SERMON_MIN_DESC && !NOT_A_SERMON.test(e.title));
  } catch {
    return [];   // never let this optional pass break the sync
  }
}

function mergeSermons(playlistEntries, channelEntries) {
  const seen = new Map();
  for (const e of [...playlistEntries, ...channelEntries]) if (!seen.has(e.id)) seen.set(e.id, e);
  return [...seen.values()];
}

// ---- service dates (see the header) ----
const YMD = /^\d{4}-\d{2}-\d{2}$/;
const LA_DAY = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Los_Angeles', year: 'numeric', month: '2-digit', day: '2-digit',
});

// An ISO instant -> its calendar date in Livermore, YYYY-MM-DD ('' if unparseable)
function laYmd(iso) {
  const t = Date.parse(iso || '');
  if (isNaN(t)) return '';
  const p = Object.fromEntries(LA_DAY.formatToParts(new Date(t)).map(x => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}`;
}

// YYYY-MM-DD -> the Sunday on or before it (noon UTC keeps the arithmetic clear of DST)
function sundayOnOrBefore(ymd) {
  if (!YMD.test(ymd || '')) return '';
  const d = new Date(ymd + 'T12:00:00Z');
  d.setUTCDate(d.getUTCDate() - d.getUTCDay());
  return d.toISOString().slice(0, 10);
}

// data/sermon-dates.json; a missing file is normal, a broken one is reported and ignored (never fails the sync)
function dateOverrides() {
  const f = 'data/sermon-dates.json';
  if (!existsSync(f)) return {};
  try {
    const raw = JSON.parse(readFileSync(f, 'utf8')) || {};
    const out = {};
    for (const [id, d] of Object.entries(raw)) {
      if (YMD.test(String(d))) out[id] = String(d);
      else console.warn(`sermon-dates.json: ignoring ${id} -> ${JSON.stringify(d)} (want YYYY-MM-DD)`);
    }
    return out;
  } catch (e) {
    console.warn('sermon-dates.json unreadable, ignoring it:', e.message);
    return {};
  }
}

// With an API key: { videoId: LA date the stream actually started } for the ids that were livestreams
async function streamDates(ids) {
  if (!API_KEY || !ids.length) return {};
  try {
    const url = 'https://www.googleapis.com/youtube/v3/videos?part=liveStreamingDetails&id='
      + ids.slice(0, 50).join(',') + '&key=' + API_KEY;
    const r = await fetch(url);
    if (!r.ok) return {};
    const out = {};
    for (const v of (await r.json()).items || []) {
      const day = laYmd(v.liveStreamingDetails?.actualStartTime);
      if (day) out[v.id] = day;
    }
    return out;
  } catch {
    return {};
  }
}

async function datedSermons(entries) {
  const manual = dateOverrides();
  const streams = await streamDates(entries.map(e => e.id));
  const dated = entries
    .map(({ id, title, published }) => ({
      id, title, published,
      service: manual[id] || streams[id] || sundayOnOrBefore(laYmd(published)),
    }))
    .sort((a, b) => (b.service || '').localeCompare(a.service || '')
      || (Date.parse(b.published) || 0) - (Date.parse(a.published) || 0));
  // Two sermons on one Sunday is almost always a late upload read as the following week: the site would
  // show two pills with the same date and send the late one's notes button to the wrong week. Say so in
  // the Action log, naming both ids, unless the override file already settled it.
  const byDay = new Map();
  for (const v of dated) {
    if (!v.service) continue;
    const other = byDay.get(v.service);
    if (other && !(manual[v.id] && manual[other.id])) {
      console.warn(`sermon dates: ${other.id} and ${v.id} both read as ${v.service}. If one was uploaded `
        + `late, add its real Sunday to data/sermon-dates.json.`);
    } else if (!other) byDay.set(v.service, v);
  }
  return dated;
}

async function main() {
  const today = new Date().toISOString().slice(0, 10);

  // ---- Sermons (current series) ----
  const seriesId = await resolveSeriesPlaylistId();
  const s = await feed(seriesId);
  const [sTitle, ...rest] = (s.feedTitle || '').split(/:\s*/);
  let blurb = rest.join(': ');
  if (blurb && !/[.!?]$/.test(blurb)) blurb += '.';
  const videos = (await datedSermons(mergeSermons(s.entries, await channelSermons()))).slice(0, MAX);

  // If the newest message is a standalone (not in the series playlist), the series bar would
  // mislabel it and "Watch the Series" would point at a playlist that does not contain it.
  const standalone = videos.length && !s.entries.some(e => e.id === videos[0].id);
  const series = standalone
    ? {
        title: 'Latest Messages',
        blurb: 'The newest teaching from Arroyo, including standalone messages.',
        playlistUrl: 'https://www.youtube.com/@arroyochurch/videos',
      }
    : {
        title: sTitle || 'Current Series',
        blurb: blurb || 'A new message every Sunday.',
        playlistUrl: 'https://www.youtube.com/playlist?list=' + seriesId,
      };

  const sermons = { series, videos, updated: today };

  // ---- Podcasts ----
  const p = await feed(PODCAST_PLAYLIST_ID);
  const podcasts = {
    playlistUrl: 'https://www.youtube.com/playlist?list=' + PODCAST_PLAYLIST_ID,
    videos: p.entries.slice(0, MAX).map(({ id, title }) => ({ id, title })),
    updated: today,
  };

  if (!sermons.videos.length || !podcasts.videos.length) {
    throw new Error('a feed returned 0 videos — keeping last-good JSON');
  }

  mkdirSync('data', { recursive: true });
  writeFileSync('data/sermons.json', JSON.stringify(sermons, null, 2) + '\n');
  writeFileSync('data/podcasts.json', JSON.stringify(podcasts, null, 2) + '\n');
  console.log(`OK: series="${sermons.series.title}" (${seriesId}) sermons=${sermons.videos.length} podcasts=${podcasts.videos.length}`);
}

main().catch(e => { console.error('sync-youtube failed:', e.message); process.exit(1); });

/**
 * Arroyo Church — "Get Connected" relay (Cloudflare Worker).
 *
 * Receives on-site form POSTs from arroyochurch.com (the home "Join a Group"
 * form AND the /connect-tag digital connect card), validates + anti-spam, and
 * creates a Planning Center People form submission (form 1206123) using a
 * Personal Access Token held SERVER-SIDE. The token never reaches the browser.
 *
 * Confirmed working against the live API 2026-06-21 (HTTP 201).
 *
 * ── Request body (all clients) ──
 *   { first, last, email, phone,           // person fields
 *     nextSteps: ["<option id>", ...],     // multi-select "What's your next step?"
 *     group: "<option id>",                // only when "join a group" is selected
 *     team:  ["<option id>", ...],         // only when "start serving" is selected (forward-compat; see TEAM_OPTIONS)
 *     intents: ["new","class",...],        // intent TOKENS for the free-text mirror (see INTENT_LABELS)
 *     message: "...",                       // free text / prayer request
 *     website, turnstileToken }             // honeypot + Turnstile
 *   Legacy: the home form may send {group} with no nextSteps — handled below.
 *
 * ── Secrets (set as ENCRYPTED secrets, never plaintext vars) ──
 *   PC_APP_ID         Planning Center PAT — Application ID
 *   PC_SECRET         Planning Center PAT — Secret
 *   TURNSTILE_SECRET  (optional) Cloudflare Turnstile secret key. If set, the
 *                     form's Turnstile token is verified. Omit to skip for now.
 *
 * ── Confirmed field map for form 1206123 "Next Steps At Arroyo" ──
 *   (Re-verified 2026-07-22 by reading the LIVE public form at
 *    https://arroyo-church-434989.churchcenter.com/people/forms/1206123 — every option id
 *    below is rendered by PC itself as input#checkbox_<option id>.)
 *   Phone (text)             9974695 -> value = phone string
 *   "What's your next step?"  9567926 -> CHECKBOXES. Emit one entry per selected option,
 *                                        value = the option id as a SCALAR STRING. Never an array.
 *        10625856 "I placed my faith in Jesus today"
 *        10558271 "I want to attend the next Connect Class"
 *        10558272 "I want to join a Connect Group"
 *        10648022 "I want to get baptized"
 *        10558273 "I want to start serving"
 *        10558274 "I want to talk to a pastor"   (exists in PC; deliberately unused here)
 *   "Join a Connect Group"   9567985 -> value = option id (only with next-step "join a group")
 *        10558346 Couples Mon 7p · 10558347 Men Tue 6:30p · 10558348 Women Wed 6p
 *        10558349 Moms · 10558350 RecConnect · 10558351 Young Adults Thu 7p · 10558352 Students
 *   "Which team"             9568011 -> value = option id (only with next-step "start serving")
 *        Option ids UNCONFIRMED — TEAM_OPTIONS below is a placeholder whitelist; the
 *        front end does NOT send team yet. Confirm ids in PC, then enable the picker.
 *   Message (text)           9630046 -> value = text (also the prayer-request channel)
 *   Name/email/phone also written to the person profile via person_attributes.
 */

const PC_BASE = "https://api.planningcenteronline.com/people/v2/forms";

const ALLOWED_ORIGINS = new Set([
  "https://www.arroyochurch.com",
  "https://arroyochurch.com",
]);

const F_PHONE = "9974695", F_NEXT = "9567926", F_GROUP = "9567985", F_TEAM = "9568011", F_MESSAGE = "9630046";
const NEXT_STEP_JOIN = "10558272";  // "I want to join a Connect Group"
const NEXT_STEP_SERVE = "10558273"; // "I want to start serving"
// Whitelists — any option id not listed here is silently ignored (defends against tampering).
// Verified 2026-07-22 against the live public form (arroyo-church-434989.churchcenter.com/people/forms/1206123).
// 10558274 ("I want to talk to a pastor") is NOT offered by the connect tag (prayer stays a
// free-text message there by design) but IS used by the /connect Questions-&-Prayer form, which
// replaced a native Squarespace form that only ever emailed.
const VALID_NEXT_STEPS = new Set(["10625856","10558271","10558272","10558273","10648022","10558274"]);
const GROUP_OPTIONS = new Set(["10558346","10558347","10558348","10558349","10558350","10558351","10558352"]);
// CONFIRMED 2026-07-22 against the live form (these were previously an unverified placeholder).
const TEAM_OPTIONS = new Set(["10558402","10558403","10558404","10558405","10558406"]);

// Labels for the free-text mirror (see messageOut below). Keyed by an intent TOKEN, not by
// option id, because (a) two different buttons legitimately map to the same PC option
// ("I'm new here" and "Attend Connect Class" both -> 10558271) and we still want to know
// which was tapped, and (b) some intents ("prayer") have no PC option at all.
// Whitelisted server-side so a tampered client can't inject arbitrary text into PC.
const INTENT_LABELS = {
  decision: "Made a decision for Jesus today",
  new:      "First time here",
  class:    "Wants to attend the Connect Class",
  group:    "Wants to join a Connect Group",
  serve:    "Wants to start serving",
  baptism:  "Wants to get baptized",
  prayer:   "Needs prayer",
  pastor:   "Wants to talk to a pastor",
  question: "Has a question",
};

// ── Destination Planning Center forms ────────────────────────────────────────────────────
// Verified 2026-07-29 by listing the account's forms through the People API. The account has
// four forms; these are the two this site writes to. (1219524 "Arroyo Young Adults" and 1229432
// "Connect Class" are not written to — the latter has NO custom fields, so routing the site's
// Connect Class signup there would silently drop the extra interests + message.)
const FORMS = {
  // "Next Steps At Arroyo" — the rich intake form (next-step checkboxes, group, team, message).
  nextsteps: { id: "1206123", phone: F_PHONE, message: F_MESSAGE, requirePhone: true },
  // "Plan Your Visit". Phone 10213186 is a plain single-line TEXT field, deliberately NOT PC's
  // structured "phone_number" profile field: PC forbids assigning number/location on a
  // FormSubmissionValue, so a structured phone field can never be populated by the API and would
  // always render blank (this is the same reason 1206123 uses the text field 9974695). Swapped
  // 2026-07-29 — do not "upgrade" it back to a phone_number field.
  visit:     { id: "1216871", phone: "10213186", message: "9657927", requirePhone: false },
};

// Which on-site form a submission came from. The client sends a `source` TOKEN only; the human
// label is resolved SERVER-side (never trust client-supplied text) and written into the PC
// message, so the church can always tell which form was filled in. `form` picks the destination.
const SOURCES = {
  home_visit:    { form: "visit",     label: "Plan a Visit — home page" },
  events_rsvp:   { form: "visit",     label: "Event RSVP — events page" },
  visit_page:    { form: "visit",     label: "Plan Your Visit page" },
  connect_tag:   { form: "nextsteps", label: "Connect Tag — chair tap" },
  join_group:    { form: "nextsteps", label: "Join a Group — home page" },
  connect_class: { form: "nextsteps", label: "Connect Class signup" },
  next_steps:    { form: "nextsteps", label: "Next Steps page" },
  connect_group: { form: "nextsteps", label: "Connect Group page" },
  prayer:        { form: "nextsteps", label: "Questions / Prayer — connect page" },
};

function cors(origin) {
  const allow = ALLOWED_ORIGINS.has(origin) ? origin : "https://www.arroyochurch.com";
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}
function json(body, status, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...cors(origin) },
  });
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(origin) });

    if (request.method !== "POST") return json({ success: false, error: "method" }, 405, origin);
    if (!ALLOWED_ORIGINS.has(origin)) return json({ success: false, error: "origin" }, 403, origin);

    let b;
    try { b = await request.json(); } catch { return json({ success: false, error: "bad_json" }, 400, origin); }

    // Honeypot: real users never fill the hidden "website" field. Pretend success, submit nothing.
    if (b.website) return json({ success: true }, 200, origin);

    // Turnstile — best-effort, NOT a hard gate. The invisible Managed-mode challenge can silently
    // fail to produce a token on some mobile browsers (verified 2026-07-23: a real iPhone never got
    // a token in 20s), and blocking a genuine visitor is worse than the occasional naive-bot
    // submission the honeypot doesn't catch. So: if a token IS present, verify it and reject when
    // it's invalid (that's bot-shaped); if NO token is present, fall through and rely on the honeypot.
    if (env.TURNSTILE_SECRET && b.turnstileToken) {
      const ok = await verifyTurnstile(env.TURNSTILE_SECRET, b.turnstileToken, request.headers.get("CF-Connecting-IP"));
      if (!ok) return json({ success: false, error: "captcha" }, 403, origin);
    }

    // Resolve WHICH on-site form this is and therefore which PC form it writes to.
    // Unknown/absent source => the historical default (Next Steps), so an older cached page keeps
    // working during the window where the site and the worker aren't deployed atomically.
    const src = Object.prototype.hasOwnProperty.call(SOURCES, String(b.source || ""))
      ? SOURCES[String(b.source)]
      : null;
    const target = FORMS[src ? src.form : "nextsteps"];

    let first = (b.first || "").trim();
    let last = (b.last || "").trim();
    // Some forms collect a single "Your name" box rather than first/last — split it.
    if (!first && b.name) {
      const parts = String(b.name).trim().split(/\s+/);
      first = parts.shift() || "";
      last = last || parts.join(" ");
    }
    const email = (b.email || "").trim();
    const phone = (b.phone || "").trim();
    const message = (b.message || "").toString().trim();

    // Selected next-steps (multi-select), whitelisted + de-duped.
    let steps = Array.isArray(b.nextSteps) ? b.nextSteps.map(String).filter((s) => VALID_NEXT_STEPS.has(s)) : [];
    // Backward-compat: the legacy home "Join a Group" form sends {group} with NO nextSteps array.
    // (The home + worker deploys aren't atomic, so this fallback closes the regression window.)
    if (steps.length === 0 && b.group && GROUP_OPTIONS.has(String(b.group))) steps.push(NEXT_STEP_JOIN);
    steps = [...new Set(steps)];

    // Email is required EXCEPT for a prayer-only capture (no next-steps, just a message) — don't
    // gate a vulnerable ask behind an email. first + last + phone are always required.
    const prayerOnly = steps.length === 0 && !!message;
    if (!first) return json({ success: false, error: "missing" }, 422, origin);
    // Phone is only mandatory on the forms that actually ask for it as required (the Next Steps
    // family). The Plan-a-Visit / Events forms mark phone optional, so don't reject those.
    if (target.requirePhone && (!last || !phone)) return json({ success: false, error: "missing" }, 422, origin);
    if (!prayerOnly && !email) return json({ success: false, error: "missing" }, 422, origin);
    if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return json({ success: false, error: "email" }, 422, origin);

    // ── Free-text mirror ────────────────────────────────────────────────────────────────
    // The Message field (9630046) is a plain string and is empirically confirmed to land, so
    // restate the selections into it. Two reasons: (1) if PC ever silently drops the checkbox
    // answers again, the church still SEES what the person asked for instead of it being
    // invisible for a month; (2) it's the only channel for intents with no PC option.
    const intents = Array.isArray(b.intents)
      ? [...new Set(b.intents.map(String).filter((i) => Object.prototype.hasOwnProperty.call(INTENT_LABELS, i)))]
      : [];
    const labels = intents.map((i) => INTENT_LABELS[i]);
    const header = [];
    // ALWAYS record which on-site form produced this submission — several site forms share one
    // PC form, so without this the church can't tell a visit RSVP from a next-step request.
    if (src) header.push("Submitted via: " + src.label);
    if (labels.length) header.push("Next steps: " + labels.join(" · "));
    // If the destination form has no Phone field, keep the number visible in the submission body
    // (it is always written to the person's profile too).
    if (!target.phone && phone) header.push("Phone: " + phone);
    const head = header.join("\n");
    const messageOut = head ? head + (message ? "\n\n" + message : "") : message;

    const values = [];
    if (target.phone && phone) values.push({ form_field_id: target.phone, value: phone });
    // Multi-select checkbox: emit ONE FormSubmissionValue per selected option, each with a
    // SCALAR STRING value = the option id. NEVER send an array here.
    // History: a prior revision sent the whole array as a single entry ({"value":["10648022"]}).
    // PC accepted it (HTTP 201) and stored every other scalar value in the same payload — so
    // people and messages kept arriving — but the array never resolved to a FormFieldOption and
    // "What brought you in" came back blank. For a SINGLE selection the shape below is
    // byte-identical to the payload confirmed working end-to-end in the original build.
    // The checkbox/group/team fields belong to "Next Steps At Arroyo" only. Sending another
    // form's field ids would be silently discarded by PC (values referencing fields on a
    // different form are dropped), so scope them to that destination.
    if (target.id === FORMS.nextsteps.id) {
      steps.forEach((id) => values.push({ form_field_id: F_NEXT, value: id }));
      if (steps.includes(NEXT_STEP_JOIN) && b.group && GROUP_OPTIONS.has(String(b.group))) {
        values.push({ form_field_id: F_GROUP, value: String(b.group) });
      }
      if (steps.includes(NEXT_STEP_SERVE) && Array.isArray(b.team)) {
        const teams = b.team.map(String).filter((t) => TEAM_OPTIONS.has(t));
        teams.forEach((t) => values.push({ form_field_id: F_TEAM, value: t })); // same rule: never an array
      }
    }
    if (messageOut && target.message) values.push({ form_field_id: target.message, value: messageOut.slice(0, 2000) });

    const person_attributes = {
      first_name: first,
      last_name: last,
      phone_numbers_attributes: [{ location: "Mobile", number: phone }],
    };
    // Prayer-only submissions create a person with NO email. Verify PC accepts this in the
    // go/no-go test (a no-email submission); if PC 422s, require email here even for prayer-only.
    if (email) person_attributes.emails_attributes = [{ location: "Home", address: email }];

    const payload = {
      data: {
        type: "FormSubmission",
        attributes: {
          person_attributes,
          form_submission_values_attributes: values,
        },
      },
    };

    let pcRes;
    try {
      pcRes = await fetch(`${PC_BASE}/${target.id}/form_submissions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Basic " + btoa(`${env.PC_APP_ID}:${env.PC_SECRET}`),
        },
        body: JSON.stringify(payload),
      });
    } catch {
      return json({ success: false, error: "upstream" }, 502, origin);
    }

    if (pcRes.status === 201 || pcRes.status === 200) return json({ success: true }, 200, origin);

    // Log server-side (visible in `wrangler tail` / dashboard logs); never leak to the client.
    console.log("PC submit failed", pcRes.status, await pcRes.text().catch(() => ""));
    return json({ success: false, error: "submit_failed" }, 502, origin);
  },
};

async function verifyTurnstile(secret, token, ip) {
  if (!token) return false;
  try {
    const form = new FormData();
    form.append("secret", secret);
    form.append("response", token);
    if (ip) form.append("remoteip", ip);
    const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body: form });
    const d = await r.json();
    return !!d.success;
  } catch {
    return false;
  }
}

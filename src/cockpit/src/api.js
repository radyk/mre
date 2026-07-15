// Thin API client for the cockpit. All calls hit RELATIVE paths so the same
// build works behind the Vite dev proxy, behind the API itself, or against the
// test fixture server (same-origin). Every response is the versioned envelope
// {api_version, data} | {api_version, error}; this unwraps it.
//
// Config comes from the URL query string:
//   ?schedule=<id>   the schedule to render (else the first base schedule)
//   ?api=<baseUrl>   optional absolute API base (default: same origin / proxy)
//   ?ask=<question>  optional: auto-run one question after load (demo/harness)

const params = new URLSearchParams(location.search);
export const CONFIG = {
  base: params.get("api") || "",
  scheduleId: params.get("schedule") || "",
  autoAsk: params.get("ask") || "",
};

async function envelope(path, opts) {
  const res = await fetch(CONFIG.base + path, opts);
  let body;
  try { body = await res.json(); } catch { body = null; }
  if (!res.ok || (body && body.error)) {
    const msg = body?.error?.message || `HTTP ${res.status}`;
    throw new Error(`${path}: ${msg}`);
  }
  return body.data;
}

export function listSchedules() {
  return envelope("/schedules");
}

export async function resolveScheduleId() {
  if (CONFIG.scheduleId) return CONFIG.scheduleId;
  const { schedules } = await listSchedules();
  if (!schedules || !schedules.length) {
    throw new Error("no schedules registered — solve one first (POST /submissions/{id}/solve)");
  }
  return schedules[0].id;
}

export function getSchedule(id) {
  return envelope(`/schedules/${id}`);
}

export function getScheduleMeta(id) {
  // grade lives in the certificate store, not the schedule document.
  return envelope(`/schedules/${id}/meta`).catch(() => null);
}

export function getScheduleInteraction(id) {
  // The Tier-0 legality payload (contract 1.3, R-T1d), served on its OWN
  // endpoint so it never sits inside first-paint. Fetched in the background
  // after the board renders; a 404 (pool member / pre-1.3) is not an error —
  // the board stays Tier-0-green-only. Returns the {interaction, ...} envelope
  // data or null on absence.
  return envelope(`/schedules/${id}/interaction`).catch(() => null);
}

export function getScheduleAlternatives(id) {
  // The Tier-1 ghost payload (forced alternatives + pool, R-T1a). Fetched in
  // the background alongside the interaction payload; a 404 (none built) is not
  // an error — the drag surface renders Tier-0 shading with no ghosts.
  return envelope(`/schedules/${id}/alternatives`).catch(() => null);
}

export function priceOpAlternatives(id, opId, opts = {}) {
  // ON-DEMAND pricing (session 3.3 CU1, R-T1a K'): the planner grabbed an op the
  // precomputed batch didn't cover — price every eligible machine for it right
  // now. Returns 202 {op_id, pool_id, status:"pricing"}; the results land in the
  // /alternatives pool (appended), which the caller re-fetches to fade the
  // ghosts in. Idempotent under repeated grabs.
  return envelope(`/schedules/${id}/alternatives/op/${opId}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(opts),
  }).catch(() => null);
}

export function getAlternativeMember(id, memberIndex) {
  // The full solved document behind one priced ghost (session 3.3 CU4): fetched
  // lazily on a drop-onto-ghost so the complete moved-set (not just the dropped
  // bar) can be traced. A 409 (infeasible verdict — no document) or any error
  // is not fatal: the caller falls back to the single-bar trace.
  return envelope(`/schedules/${id}/alternatives/${memberIndex}`).catch(() => null);
}

export function postSandbox(id, pin) {
  // The Tier-2 pinned re-solve (R-DP1/R-T1c) behind a dropped bar: pin one op at
  // (machine + time as displayed), re-solve the surroundings under the budget,
  // return the classified outcome + the moved-set (R-DP7). Synchronous up to the
  // budget — the caller shows a countdown and never blocks its own board.
  return envelope(`/schedules/${id}/sandbox`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(pin),
  });
}

export function postAccept(id, pin) {
  // Accept a dropped bar's verdict (CU1, R-DP7): pin the op and MINT A NEW
  // proposed schedule version — the base is never mutated. Records one
  // planner_edit Decision (authority mandatory). Returns
  // {schedule_id, parent_schedule_id, status:"proposed", decision}. Synchronous
  // behind the sandbox budget; the caller then rebinds the board to schedule_id.
  return envelope(`/schedules/${id}/accept`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(pin),
  });
}

export function postPublish(id) {
  // Publish a proposed version (CU1): proposed → published, superseding the
  // prior version (invalidating its pools). The explicit second act after
  // accept. Returns {schedule_id, status:"published", superseded:[...]}.
  return envelope(`/schedules/${id}/publish`, { method: "POST" });
}

export function ask(id, question, useLlm = false) {
  // `llm` is honored by the server ONLY when ANTHROPIC_API_KEY is set, and the
  // LLMRenderer itself fails closed (no key / package / validation failure →
  // deterministic template render, never an error, never unvalidated prose). The
  // cockpit sends it true only in the dev build (see main.js); the production
  // build always renders templates. See src/cockpit/README.md.
  return envelope(`/schedules/${id}/ask`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, llm: !!useLlm }),
  });
}

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

export function ask(id, question) {
  return envelope(`/schedules/${id}/ask`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

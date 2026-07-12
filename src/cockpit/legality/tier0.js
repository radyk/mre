// Tier-0 legality arithmetic — the client-side "can this op land here?" map
// (docs/07 Phase 3 Tier-0; docs/04 R-DP6). PURE and framework-free: no DOM, no
// vis-timeline, no fetch. It consumes a contract-1.3 schedule document + its
// interaction payload (GET /schedules/{id}/interaction) and computes, for one
// operation:
//
//   * eligible resource ROWS (capability) — every row, each marked legal or
//     dim-by-capability;
//   * LEGAL TIME REGIONS per eligible row — calendar-open windows ∩ the
//     precedence/release floor ∩ window-fit for the op's remaining duration;
//   * the SEMANTIC ANCHOR set — calendar openings, adjacency edges (a
//     neighbour bar's edges), predecessor-finish floors, the release floor,
//     and ghost placements when supplied.
//
// Two consumers share this output: 3.2b's shading + magnets, and the
// screenshot harness. It never touches vis geometry — only canonical times.
//
// EPISTEMICS (R-DP6): dim = PROVEN illegal by canonical arithmetic (never
// wrong). Green = provably-not-illegal by these cheap rules (NOT a full-model
// guarantee). So the conservative-error direction is fixed: this library may
// UNDER-offer green (omit a legal region), but must NEVER green a
// proven-illegal spot — capability, closed calendar, precedence floor, and
// window-fit are all subtractive here. Occupancy is NOT subtracted from
// legality (a fit-but-displace is amber, still legal); it is reported
// separately so the caller can shade amber.

const MIN = 60000;                       // ms per minute
const OPEN_KINDS = new Set(["regular", "overtime"]);
const ms = (iso) => (iso == null ? null : Date.parse(iso));
const iso = (t) => (t == null ? null : new Date(t).toISOString());

// Merge a list of {start,end} ms intervals into sorted, non-overlapping,
// coalesced (touching intervals joined) intervals.
function mergeIntervals(intervals) {
  const xs = intervals.filter((w) => w.end > w.start).sort((a, b) => a.start - b.start);
  const out = [];
  for (const w of xs) {
    const last = out[out.length - 1];
    if (last && w.start <= last.end) last.end = Math.max(last.end, w.end);
    else out.push({ start: w.start, end: w.end });
  }
  return out;
}

// Latest start t (ms) within `openWindows` such that the cumulative OPEN
// capacity from t to the end of the last window is ≥ durationMs. Returns null
// when the total open capacity is < durationMs (nothing fits, even resumable).
// Used for the window-fit floor of a RESUMABLE op (it may pause across
// closures, but still needs enough total open time ahead of its start).
function latestStartForRemaining(openWindows, durationMs) {
  let need = durationMs;
  for (let i = openWindows.length - 1; i >= 0; i--) {
    const w = openWindows[i];
    const cap = w.end - w.start;
    if (cap >= need) return w.end - need;      // start inside this window
    need -= cap;                                // consume it whole, keep walking
  }
  return null;                                  // total capacity < duration
}

// Build a reusable context from the main schedule document and its interaction
// payload (the {operations, precedence_edges} block). Times are pre-parsed to
// ms so computeTier0 is cheap enough to call on every pointer grab.
export function buildContext(doc, interaction) {
  const resources = doc.resources || [];
  const openByResource = new Map();
  const closuresByResource = new Map();
  for (const r of resources) {
    const open = [], closed = [];
    for (const w of r.calendar_windows || []) {
      if (OPEN_KINDS.has(w.kind)) open.push({ start: ms(w.start), end: ms(w.end) });
      else if (w.kind === "closure") closed.push({ start: ms(w.start), end: ms(w.end) });
    }
    openByResource.set(r.resource_id, mergeIntervals(open));
    closuresByResource.set(r.resource_id, mergeIntervals(closed));
  }

  // occupancy + assignment ends, keyed by resource and by operation.
  const occByResource = new Map();
  const endByOp = new Map();
  for (const a of doc.assignments || []) {
    const chunks = a.chunks || [];
    if (!chunks.length) continue;
    const s = ms(chunks[0].start), e = ms(chunks[chunks.length - 1].end);
    endByOp.set(a.operation_ref, e);
    if (!occByResource.has(a.resource_id)) occByResource.set(a.resource_id, []);
    occByResource.get(a.resource_id).push({ start: s, end: e, operation_ref: a.operation_ref });
  }

  const opFacts = new Map();
  for (const o of (interaction?.operations) || []) opFacts.set(o.operation_ref, o);

  // predecessors of each successor, with their min lags (ms).
  const predsBySucc = new Map();
  for (const e of (interaction?.precedence_edges) || []) {
    if (!predsBySucc.has(e.successor_ref)) predsBySucc.set(e.successor_ref, []);
    predsBySucc.get(e.successor_ref).push({
      predecessor_ref: e.predecessor_ref, min_lag_ms: (e.min_lag_min || 0) * MIN,
    });
  }

  const horizonEnd = doc.horizon?.end ? ms(doc.horizon.end)
    : Math.max(0, ...[...openByResource.values()].flat().map((w) => w.end));

  return {
    resources, openByResource, closuresByResource, occByResource,
    endByOp, opFacts, predsBySucc, horizonEnd,
    resourceName: (rid) => (resources.find((r) => r.resource_id === rid)?.external_name) || rid,
  };
}

// The global start floor for an op: the later of its release floor and every
// predecessor's finish + min_lag. Predecessor finishes are read from the
// incumbent placement (each predecessor bar's end); an unplaced predecessor
// contributes nothing (Tier-0 can't floor against a bar that isn't there).
function startFloor(op, ctx) {
  let floor = op.earliest_start != null ? ms(op.earliest_start) : null;
  const preds = ctx.predsBySucc.get(op.operation_ref) || [];
  const finishes = [];
  for (const p of preds) {
    const end = ctx.endByOp.get(p.predecessor_ref);
    if (end == null) continue;
    const f = end + p.min_lag_ms;
    finishes.push(f);
    floor = floor == null ? f : Math.max(floor, f);
  }
  return { floor, predecessor_finishes: finishes };
}

// Legal START regions for `op` on one resource row. Returns [] when the row is
// closed for long enough / floored out / too short to fit (all four dims).
function legalRegionsOnRow(op, resourceId, floor, ctx) {
  const open = ctx.openByResource.get(resourceId) || [];
  const durationMs = ((op.setup_min || 0) + (op.working_min || 0)) * MIN;
  const lo = floor == null ? -Infinity : floor;
  const regions = [];

  if (op.resumable) {
    // Resumable: may pause across closures. Legal to START at t iff there is ≥
    // duration cumulative OPEN capacity from t to the horizon. The latest such
    // start is the window-fit ceiling; below it, any open sub-window ≥ floor is
    // legal.
    const latest = latestStartForRemaining(open, durationMs);
    if (latest == null) return [];                 // won't fit even resumable
    for (const w of open) {
      const a = Math.max(w.start, lo), b = Math.min(w.end, latest);
      if (a <= b) regions.push({ start: a, end: b });
    }
  } else {
    // Non-resumable: needs a single contiguous open window holding the whole
    // duration, from a start ≥ floor.
    for (const w of open) {
      const a = Math.max(w.start, lo), b = w.end - durationMs;
      if (a <= b) regions.push({ start: a, end: b });
    }
  }
  return regions;
}

// Compute the full Tier-0 result for one operation (by operation_ref).
// `opts.ghosts` (optional) is a list of pre-priced ghost placements
// [{resource_id, start, ...}] surfaced by Tier-1 — passed straight into the
// anchor set (strongest snap target, R-DP3) when supplied.
export function computeTier0(opRef, ctx, opts = {}) {
  const op = ctx.opFacts.get(opRef);
  if (!op) throw new Error(`no interaction facts for operation ${opRef}`);
  const eligible = new Set(op.eligible_resource_ids || []);
  const { floor, predecessor_finishes } = startFloor(op, ctx);
  const durationMs = ((op.setup_min || 0) + (op.working_min || 0)) * MIN;

  const rows = [];
  const calendar_openings = [];
  const adjacency_edges = [];
  for (const r of ctx.resources) {
    const rid = r.resource_id;
    const isEligible = eligible.has(rid);
    const row = {
      resource_id: rid,
      external_name: r.external_name || rid,
      eligible: isEligible,
      reason: isEligible ? null : "capability",       // dim reason (R-DP2 hover)
      legal_regions: isEligible
        ? legalRegionsOnRow(op, rid, floor, ctx).map((w) => ({ start: iso(w.start), end: iso(w.end) }))
        : [],
      // occupancy is NOT a legality subtraction (fit-but-displace is amber);
      // reported so the caller can shade amber over these spans.
      occupied: (ctx.occByResource.get(rid) || [])
        .filter((o) => o.operation_ref !== opRef)
        .map((o) => ({ start: iso(o.start), end: iso(o.end), operation_ref: o.operation_ref })),
    };
    rows.push(row);
    if (!isEligible) continue;
    for (const w of ctx.openByResource.get(rid) || []) calendar_openings.push({ resource_id: rid, at: iso(w.start) });
    for (const o of ctx.occByResource.get(rid) || []) {
      if (o.operation_ref === opRef) continue;
      adjacency_edges.push({ resource_id: rid, at: iso(o.end), kind: "trailing" });
      adjacency_edges.push({ resource_id: rid, at: iso(o.start), kind: "leading" });
    }
  }

  return {
    operation_ref: opRef,
    duration_min: Math.round(durationMs / MIN),
    resumable: !!op.resumable,
    floor: iso(floor),
    rows,
    anchors: {
      release_floor: op.earliest_start != null ? iso(ms(op.earliest_start)) : null,
      predecessor_finishes: predecessor_finishes.map(iso),
      calendar_openings,
      adjacency_edges,
      ghosts: opts.ghosts || [],
    },
  };
}

// Convenience point-check (3.2b mid-drag refusal, R-DP2): is `startIso` a legal
// start for `opRef` on `resourceId`? Returns {legal, reason}. Conservative:
// legal only if the point falls inside a computed legal region.
export function isLegalStart(opRef, resourceId, startIso, ctx) {
  const op = ctx.opFacts.get(opRef);
  if (!op) return { legal: false, reason: "unknown_operation" };
  if (!(op.eligible_resource_ids || []).includes(resourceId)) return { legal: false, reason: "capability" };
  const { floor } = startFloor(op, ctx);
  const t = ms(startIso);
  if (floor != null && t < floor) return { legal: false, reason: "precedence_floor" };
  const regions = legalRegionsOnRow(op, resourceId, floor, ctx);
  const hit = regions.some((w) => t >= w.start && t <= w.end);
  return hit ? { legal: true, reason: null } : { legal: false, reason: "calendar_or_window_fit" };
}

// Semantic magnets (R-DP3) — PURE, framework-free (no DOM, no vis). Given the
// Tier-0 anchor set for the grabbed op and a candidate start time on a target
// row, snap the candidate to the nearest SEMANTIC anchor within its capture
// radius: ghost placements first (strongest — a solved, vouched-for target),
// then calendar openings, adjacency edges, the predecessor/release floor, and a
// coarse time grid only as the open-space fallback (R-DP3). Alt disables all of
// it. Radii are feel tokens (feel.snap.*), converted from px to a time distance
// by the caller (the zoom-dependent px→minutes factor) so a token means the
// same on-screen distance at any zoom.
//
// The result names WHICH anchor caught it (for the click-to-anchor cue and the
// tuning panel), so the caller can render the snap visibly DURING the drag —
// the planner watches the bar click to the anchor before release (R-DP3),
// preserving R-DP1 literalness (the bar lands exactly where it snapped).

const MIN = 60000;

// Build the flat, typed candidate-anchor list for one target row from a Tier-0
// result (computeTier0 output) + the ghosts on that row. Each anchor is
// {type, time_ms, radius_px, meta?}. Only anchors ON the target row participate
// (an anchor on another machine can't catch a drag on this one).
export function anchorsForRow(tier0, resourceId, feel, ghosts = []) {
  const out = [];
  const push = (type, iso, radius_px, meta) => {
    if (iso == null) return;
    const t = Date.parse(iso);
    if (Number.isNaN(t)) return;
    out.push({ type, time_ms: t, radius_px, meta });
  };
  // ghosts on this row — strongest
  for (const g of ghosts) {
    if (g.resource_id === resourceId && g.start) {
      push("ghost", g.start, feel.snap.ghost_px, g);
    }
  }
  const a = tier0.anchors || {};
  for (const c of a.calendar_openings || []) {
    if (c.resource_id === resourceId) push("calendar", c.at, feel.snap.calendar_px);
  }
  for (const e of a.adjacency_edges || []) {
    if (e.resource_id === resourceId) push("adjacency", e.at, feel.snap.adjacency_px, { kind: e.kind });
  }
  for (const f of a.predecessor_finishes || []) push("predecessor", f, feel.snap.predecessor_px);
  if (a.release_floor) push("predecessor", a.release_floor, feel.snap.predecessor_px, { release: true });
  return out;
}

// Snap a candidate start (ms) on a row to the best anchor. `pxToMin` converts a
// px radius to a minute tolerance at the current zoom (from geometry). Returns
// {time_ms, anchor|null, snapped:boolean}. Alt (altKey) disables snapping and
// returns the raw candidate. In open space (no anchor caught it) the coarse
// grid rounds to feel.snap.grid_step_min when within grid_px.
export function snap(candidateMs, anchors, feel, pxToMin, altKey = false) {
  if (altKey) return { time_ms: candidateMs, anchor: null, snapped: false };

  let best = null, bestScore = Infinity;
  for (const anc of anchors) {
    const tolMin = anc.radius_px * pxToMin;
    const distMin = Math.abs(anc.time_ms - candidateMs) / MIN;
    if (distMin > tolMin) continue;
    // score: normalized distance shaped by falloff, then anchor priority. A
    // ghost inside its (larger) radius beats a calendar edge even a bit closer,
    // because ghosts are the only vouched-for targets (R-DP3/R-DP6).
    const norm = Math.pow(distMin / Math.max(tolMin, 1e-6), feel.snap.falloff);
    const score = norm + PRIORITY[anc.type];
    if (score < bestScore) { bestScore = score; best = anc; }
  }
  if (best) return { time_ms: best.time_ms, anchor: best, snapped: true };

  // open-space coarse grid fallback
  const step = feel.snap.grid_step_min * MIN;
  const gridMs = Math.round(candidateMs / step) * step;
  const gridTolMin = feel.snap.grid_px * pxToMin;
  if (Math.abs(gridMs - candidateMs) / MIN <= gridTolMin) {
    return { time_ms: gridMs, anchor: { type: "grid", time_ms: gridMs }, snapped: true };
  }
  return { time_ms: candidateMs, anchor: null, snapped: false };
}

// Anchor priority (lower = preferred). Ghosts win, grid loses; the ordering
// encodes R-DP3's "ghost placements (strongest), calendar openings, adjacency
// edges, predecessor-finish floors; coarse grid only as fallback".
const PRIORITY = {
  ghost: 0,
  calendar: 0.15,
  adjacency: 0.2,
  predecessor: 0.25,
  grid: 1.0,
};

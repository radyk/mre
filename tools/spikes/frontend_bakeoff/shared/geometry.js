// Shared geometry + semantic-snap core for the frontend bake-off SPIKE.
// Both candidates import this so the comparison is fair: identical time<->pixel
// mapping and identical snap logic. Candidates differ ONLY in the rendering
// host (Candidate A: SVG + dnd-kit; Candidate B: vis-timeline). Framework-free.

export const LAYOUT = {
  gutter: 140, // px reserved for row labels on the left
  header: 46, // px reserved for the time axis on top
  rowH: 30, // px per resource lane
  pxPerHour: 14, // horizontal scale (whole 4-day window fits ~1480px, no scroll)
  magnetPx: 7, // snap radius in pixels (~30 min at this scale)
};

export async function loadFixture() {
  const [schedule, anchors] = await Promise.all([
    fetch("schedule.json").then((r) => r.json()),
    fetch("anchors.json").then((r) => r.json()),
  ]);
  return buildModel(schedule, anchors);
}

const ms = (iso) => new Date(iso).getTime();

export function buildModel(schedule, anchors) {
  const win = {
    start: ms(anchors.visible_window.start),
    end: ms(anchors.visible_window.end),
  };
  // rows: real resource lanes, in fixture order, with Tier-0 legality from anchors.
  const legalityByRes = Object.fromEntries(
    anchors.rows.map((r) => [r.resource_id, r]),
  );
  const rows = schedule.resources.map((L, i) => ({
    index: i,
    resource_id: L.resource_id,
    name: L.external_name || L.resource_id.slice(0, 8),
    facility: L.facility,
    windows: L.calendar_windows
      .filter((w) => ms(w.end) > win.start && ms(w.start) < win.end)
      .map((w) => ({ start: ms(w.start), end: ms(w.end), kind: w.kind })),
    legality: legalityByRes[L.resource_id]?.legality || "dim",
    reason: legalityByRes[L.resource_id]?.reason || "",
  }));
  const rowIndex = Object.fromEntries(rows.map((r) => [r.resource_id, r.index]));

  // bars: every real assignment overlapping the window (density is real).
  const bars = [];
  for (const a of schedule.assignments) {
    const s = ms(a.chunks[0].start);
    const e = ms(a.chunks[a.chunks.length - 1].end);
    if (e <= win.start || s >= win.end) continue;
    if (!(a.resource_id in rowIndex)) continue;
    bars.push({
      id: a.assignment_id,
      op: a.operation_ref,
      resource_id: a.resource_id,
      row: rowIndex[a.resource_id],
      start: s,
      end: e,
      wo: (a.work_orders || []).join(","),
      isGrab: a.operation_ref === anchors.grab.operation_ref,
    });
  }

  const grab = {
    ...anchors.grab,
    startMs: ms(anchors.grab.start),
    endMs: ms(anchors.grab.end),
    row: rowIndex[anchors.grab.resource_id],
    durMs: ms(anchors.grab.end) - ms(anchors.grab.start),
  };

  const ghosts = anchors.ghosts.map((g) => ({
    ...g,
    startMs: ms(g.start),
    endMs: ms(g.end),
    row: rowIndex[g.resource_id],
  }));

  // Flat snap-target table (semantic targets injected per-drag in the real
  // product; here precomputed from static anchors — interim-A scope).
  const targets = [];
  targets.push({
    time: ms(anchors.predecessor_finish.finish),
    kind: "predecessor_finish",
    label: "predecessor finish",
  });
  const addOpenings = (list) =>
    (list || []).forEach((iso) =>
      targets.push({ time: ms(iso), kind: "calendar_opening", label: "shift open" }),
    );
  addOpenings(anchors.calendar_openings.own_row);
  Object.values(anchors.calendar_openings.by_ghost_row || {}).forEach(addOpenings);
  const addAdj = (list) =>
    (list || []).forEach((b) => {
      targets.push({ time: ms(b.end), kind: "adjacency", label: "abut neighbour" });
      targets.push({ time: ms(b.start), kind: "adjacency", label: "abut neighbour" });
    });
  addAdj(anchors.adjacency_edges.own_row);
  Object.values(anchors.adjacency_edges.by_ghost_row || {}).forEach(addAdj);
  ghosts.forEach((g) =>
    targets.push({ time: g.startMs, kind: "ghost", label: g.cost_label, row: g.row }),
  );

  return { win, rows, rowIndex, bars, grab, ghosts, targets, grid: (anchors.grid_fallback_minutes || 30) * 60000 };
}

// ---- time <-> pixel -------------------------------------------------------
export function timeToX(t, model) {
  const hours = (t - model.win.start) / 3600000;
  return LAYOUT.gutter + hours * LAYOUT.pxPerHour;
}
export function xToTime(x, model) {
  const hours = (x - LAYOUT.gutter) / LAYOUT.pxPerHour;
  return model.win.start + hours * 3600000;
}
export function boardWidth(model) {
  return timeToX(model.win.end, model) + 24;
}
export function boardHeight(model) {
  return LAYOUT.header + model.rows.length * LAYOUT.rowH;
}
export function rowY(i) {
  return LAYOUT.header + i * LAYOUT.rowH;
}

// ---- the semantic snap ----------------------------------------------------
// rawTime: the pointer-derived start time. alt=true disables snapping (free).
// Returns { time, snappedTo } where snappedTo is the winning target's kind or
// "grid" or "free".
export function snapTime(rawTime, model, { alt = false } = {}) {
  if (alt) return { time: rawTime, snappedTo: "free" };
  const magnetMs = (LAYOUT.magnetPx / LAYOUT.pxPerHour) * 3600000;
  // On ties (e.g. a ghost start that coincides with a shift opening), the more
  // meaningful target wins: priced ghost > predecessor finish > neighbour > opening.
  const PRIO = { ghost: 0, predecessor_finish: 1, adjacency: 2, calendar_opening: 3 };
  let best = null;
  for (const tgt of model.targets) {
    const d = Math.abs(tgt.time - rawTime);
    if (d > magnetMs) continue;
    const cand = { d, p: PRIO[tgt.kind] ?? 9, tgt };
    if (!best || d < best.d - 60000 || (Math.abs(d - best.d) <= 60000 && cand.p < best.p)) best = cand;
  }
  if (best) return { time: best.tgt.time, snappedTo: best.tgt.kind, target: best.tgt };
  // coarse 30-min grid fallback
  const g = model.grid;
  return { time: Math.round(rawTime / g) * g, snappedTo: "grid" };
}

// Tier-1 ghosts (CU2, R-T1a). Two sources rendered UNIFIED, source-distinguished
// only SUBTLY (a border style), each wearing its price or its "not feasible this
// horizon" verdict:
//   * forced_alternative — the priced road not taken (a targeted re-solve with
//     the incumbent machine forbidden); the realistic distinct-rate source.
//   * pool               — a near-optimal placement (the cheap options).
// Epistemics (R-DP6): a ghost is a complete solved schedule's vouched-for
// placement — the only pre-release known-feasible target. So ghosts are the
// strongest magnet (magnets.js) and, dropped onto, resolve near-instantly from
// the vouching schedule (no fresh solve).
//
// buildGhostIndex() folds an /alternatives payload (and optionally a pool
// payload) into a per-target-op list the controller looks up on grab. Infeasible
// verdicts are kept — "not feasible this horizon" is a renderable answer — but
// carry no placement, so they render as a row-level verdict chip, not a bar.
//
// Labels track pan/zoom and stay legible at every zoom (the C1 drift assertion
// extends to ghost labels, per the brief): the price/verdict rides an overlay
// tag centered on the ghost bar, same discipline as the citation overlay.

const ms = (iso) => Date.parse(iso);

// Fold the /alternatives payload → { opRef: [ghost, ...] }. A ghost is
// { source, resource_id, start, end, verdict, delta_pct, forbidden_resource_id }.
export function buildGhostIndex(alternatives, pool) {
  const index = new Map();
  const add = (opRef, ghost) => {
    if (!index.has(opRef)) index.set(opRef, []);
    index.get(opRef).push(ghost);
  };
  for (const m of alternatives?.members || []) {
    const lab = m.label || {};
    const op = lab.target_operation_ref;
    if (!op) continue;
    const p = lab.placement;
    add(op, {
      source: "forced_alternative",
      verdict: m.verdict,
      delta_pct: m.objective_delta_pct,
      forbidden_resource_id: lab.forbidden_resource_ref,
      resource_id: p?.resource_id || lab.alternative_resource_ref || null,
      start: p?.start || null,
      end: p?.end || null,
      // planner vocabulary (session 3.3 CU2) + the member index that lets a
      // drop lazy-fetch the ghost's full solved document (session 3.3 CU4).
      work_orders: p?.work_orders || [],
      member_index: m.member_index,
    });
  }
  // pool members (optional, same shape via a per-op placement projection)
  for (const g of pool?.ghosts || []) {
    if (!g.operation_ref) continue;
    add(g.operation_ref, {
      source: "pool", verdict: "priced", delta_pct: g.delta_pct ?? null,
      resource_id: g.resource_id, start: g.start, end: g.end,
    });
  }
  return index;
}

// A concise price/verdict label. Priced ghosts show the signed delta; a zero
// delta reads "same cost" (honesty armor — a free alternative is a real thing).
export function ghostLabel(ghost) {
  if (ghost.verdict === "infeasible_this_horizon") return "not feasible this horizon";
  const d = ghost.delta_pct;
  if (d == null) return "priced";
  if (Math.abs(d) < 1e-6) return "same cost";
  return `${d > 0 ? "+" : "−"}${Math.abs(d).toFixed(2)}%`;
}

// Render the placeable ghosts for the grabbed op into the ghost layer, plus
// their overlay labels into the label layer (kept legible / tracking). Returns
// the drawn ghost descriptors (with their rects) for hit-testing on drop.
export function renderGhosts(barLayer, labelLayer, ghosts, geometry, win) {
  barLayer.replaceChildren();
  labelLayer.replaceChildren();
  const winStart = ms(win.start), winEnd = ms(win.end);
  const drawn = [];

  for (const g of ghosts) {
    if (g.verdict === "infeasible_this_horizon" || !g.start || !g.resource_id) continue;
    const rect = geometry.barRect(g.resource_id, ms(g.start), ms(g.end));
    if (!rect) continue;
    // cull if fully outside the window
    if (ms(g.end) <= winStart || ms(g.start) >= winEnd) continue;

    const bar = document.createElement("div");
    bar.className = `ghost-bar src-${g.source}`;
    // planner vocabulary end-to-end (CU2): the ghost names its work order(s), so
    // hover reads "WO-1234 · +0.30%", never a bare bar.
    const wos = (g.work_orders || []).filter(Boolean);
    if (wos.length) bar.title = `${wos.join(", ")} · ${ghostLabel(g)}`;
    Object.assign(bar.style, {
      left: `${rect.x}px`, width: `${rect.width}px`,
      top: `${rect.top + 3}px`, height: `${rect.height - 6}px`,
    });
    barLayer.appendChild(bar);

    const tag = document.createElement("div");
    tag.className = `ghost-tag src-${g.source}` +
      (g.delta_pct > 0 ? " worse" : g.delta_pct < 0 ? " better" : " same");
    tag.textContent = ghostLabel(g);
    tag.style.left = `${rect.x + rect.width / 2}px`;
    tag.style.top = `${rect.top}px`;
    labelLayer.appendChild(tag);

    drawn.push({ ...g, rect });
  }
  return drawn;
}

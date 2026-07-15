// The gesture controller (3.2b) — the state machine behind the drag surface,
// tying together the Tier-0 legality library (tier0.js), the shading (CU1),
// ghosts (CU2), magnets (CU3), the sandbox card (CU4) and change traces (CU5).
//
// It owns a single overlay mounted in vis's center container (the same layer
// discipline as the citation overlay, so everything tracks pan/zoom) and a
// phase machine:
//
//   idle → grabbed → dragging → (tentative → verdict) | return-home → idle
//
// Two entry paths drive the SAME transitions: real pointer events (for use) and
// programmatic hooks grab()/dragTo()/drop()/discard() (for the deterministic
// harness — the pointer handlers just call these). Latency is measured where
// the ruling puts the bar: grab→shade (sub-100ms, CU1) and drop→verdict (the
// budget, CU4).
//
// R-DP1 literalness: the pin is (machine + time) exactly as snapped/displayed.
// R-DP2 commit-or-return: dim refuses mid-drag; release over dim returns home.
// R-DP7 no silent change: the dropped bar is tentative until discard; every
// consequence is traced; accept is stubbed disabled (no publish workflow yet).

import { buildContext, computeTier0, isLegalStart } from "../../legality/tier0.js";
import { renderShade } from "./shade.js";
import { buildGhostIndex, renderGhosts } from "./ghosts.js";
import { anchorsForRow, snap } from "./magnets.js";
import { renderTraces } from "./traces.js";
import { createDeltaCard } from "./sandboxui.js";
import { applyFeel, makeFeel } from "./feel.js";

const MIN = 60000;
const ms = (iso) => Date.parse(iso);

export function createGestureController(board, geometry, opts) {
  const { doc, interaction, api, scheduleId } = opts;
  const feel = opts.feel || makeFeel();
  applyFeel(feel);

  const ctx = buildContext(doc, interaction);
  const timeline = board.timeline;

  // --- planner-vocabulary + incumbent indexes --------------------------
  const asgByOp = new Map();          // op -> assignment (incumbent placement)
  const asgById = new Map();          // assignment_id -> assignment
  for (const a of doc.assignments || []) {
    asgByOp.set(a.operation_ref, a);
    asgById.set(a.assignment_id, a);
  }
  const nameOf = (rid) => board.resourceName(rid);
  const woOf = (opRef) => (asgByOp.get(opRef)?.work_orders || [])[0] || null;
  const durationMinOf = (opRef) => {
    const f = ctx.opFacts.get(opRef);
    return f ? (f.setup_min || 0) + (f.working_min || 0) : 0;
  };
  const incumbentOf = (opRef) => {
    const a = asgByOp.get(opRef);
    if (!a || !a.chunks?.length) return null;
    return { resource_id: a.resource_id, start_ms: ms(a.chunks[0].start) };
  };

  // --- ghosts (CU2) ----------------------------------------------------
  let ghostIndex = new Map();
  let lastAlternatives = opts.alternatives || null;   // for member-doc lookups (CU4)
  function setAlternatives(alternatives, pool) {
    if (alternatives) lastAlternatives = alternatives;
    ghostIndex = buildGhostIndex(alternatives, pool);
  }
  setAlternatives(opts.alternatives, opts.pool);

  // On-demand coverage (session 3.3 CU1): ops we've already fired pricing for,
  // so a repeated grab never re-fires. Covered ops (ghosts already present) and
  // single-eligibility ops (nothing to price) are never candidates.
  const pricingRequested = new Set();
  const ONDEMAND_POLL_MS = 1200, ONDEMAND_MAX_POLLS = 12;

  // --- overlay layers (all in center container, all track pan/zoom) ----
  const root = document.createElement("div");
  root.className = "drag-overlay";
  const layers = {};
  for (const name of ["shade", "ghosts", "traces", "tentative"]) {
    const el = document.createElement("div");
    el.className = `drag-layer drag-${name}`;
    root.appendChild(el);
    layers[name] = el;
  }
  const ghostLabels = document.createElement("div");
  ghostLabels.className = "drag-layer drag-ghost-labels";
  root.appendChild(ghostLabels);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "drag-layer drag-trace-svg");
  root.appendChild(svg);
  const reasonTip = document.createElement("div");
  reasonTip.className = "drag-reason hidden";
  root.appendChild(reasonTip);
  // The on-demand pricing shimmer (CU1): shown while a grabbed-but-uncovered
  // op's alternatives are priced server-side, so their absence is never silent.
  const pricingTip = document.createElement("div");
  pricingTip.className = "drag-pricing hidden";
  root.appendChild(pricingTip);
  timeline.dom.centerContainer.appendChild(root);
  // the overlay only intercepts pointer events while a gesture is active
  root.style.pointerEvents = "none";

  // --- state -----------------------------------------------------------
  const S = {
    phase: "idle",
    op: null,               // grabbed operation_ref
    tier0: null,            // computeTier0 result for the grabbed op
    opGhosts: [],           // ghosts for the grabbed op
    drawnGhosts: [],        // ghost descriptors with rects (hit-testing)
    target: null,           // {resource_id, time_ms, legal, reason, anchor}
    result: null,           // last sandbox result
    traces: [],             // drawn moved-set
    grabToShadeMs: null,
    dropToVerdictMs: null,
  };

  // --- the delta card (CU4) --------------------------------------------
  const card = createDeltaCard(board.host.parentElement || board.host, {
    onDiscard: discard,
    onNavigate: (opRef) => navigateToOp(opRef),
  });

  // ---------------------------------------------------------------------
  // Rendering — one redraw() called on every pan/zoom so the whole surface
  // tracks the board (the C1 discipline, extended to ghosts + traces).
  // ---------------------------------------------------------------------
  function redraw() {
    const win = board.getWindow();
    if (S.phase === "idle") return;
    // The Tier-0 legality overlays (shade + ghosts) answer the "where can it go"
    // question — they belong to the grab/drag phase only. Once the bar is
    // dropped (tentative/verdict), the wash is cleared and must NOT be repainted
    // by a pan/zoom redraw, leaving only tentative bar + traces + card (CU1).
    const asking = S.phase === "grabbed" || S.phase === "dragging";
    if (asking && S.tier0) renderShade(layers.shade, S.tier0, geometry, win);
    if (asking) S.drawnGhosts = renderGhosts(layers.ghosts, ghostLabels, S.opGhosts, geometry, win);
    if (S.target) renderCarry();
    if (S.phase === "verdict" && S.result?.moves?.length) {
      S.traces = renderTraces(layers.traces, svg, S.result.moves, durationMinOf, geometry, win);
    }
  }

  function renderCarry() {
    const t = S.target;
    const dur = durationMinOf(S.op) * MIN;
    const rect = geometry.barRect(t.resource_id, t.time_ms, t.time_ms + dur);
    layers.tentative.replaceChildren();
    if (!rect) return;
    const el = document.createElement("div");
    const tentative = S.phase === "tentative" || S.phase === "verdict";
    el.className = "carry-bar" +
      (tentative ? " tentative" : t.legal ? " legal" : " dim");
    Object.assign(el.style, {
      left: `${rect.x}px`, width: `${rect.width}px`,
      top: `${rect.top + 3}px`, height: `${rect.height - 6}px`,
    });
    el.textContent = woOf(S.op) || "";
    layers.tentative.appendChild(el);
  }

  timeline.on("rangechange", redraw);
  timeline.on("rangechanged", redraw);
  timeline.on("changed", redraw);
  window.addEventListener("resize", redraw);

  // ---------------------------------------------------------------------
  // Transitions
  // ---------------------------------------------------------------------
  function grab(opRef) {
    if (!ctx.opFacts.get(opRef)) return false;   // no Tier-0 facts → not grabbable
    cancelSilently();
    const t0 = performance.now();
    S.phase = "grabbed";
    S.op = opRef;
    S.opGhosts = ghostIndex.get(opRef) || [];
    S.tier0 = computeTier0(opRef, ctx, { ghosts: S.opGhosts });
    // shade + ghosts, immediately (no network — the payload is prefetched)
    const win = board.getWindow();
    renderShade(layers.shade, S.tier0, geometry, win);
    S.drawnGhosts = renderGhosts(layers.ghosts, ghostLabels, S.opGhosts, geometry, win);
    // start the carry at the incumbent placement
    const inc = incumbentOf(opRef);
    if (inc) S.target = { resource_id: inc.resource_id, time_ms: inc.start_ms, legal: true, reason: null, anchor: null };
    renderCarry();
    root.classList.add("active");
    S.grabToShadeMs = +(performance.now() - t0).toFixed(2);   // CU1 latency
    // Coverage (session 3.3 CU1): the Tier-1 promise fails silently for an
    // uncovered op. If this multi-eligible op has no ghosts yet, price its
    // alternatives on demand (async) with a shimmer so absence is never silent.
    maybePriceOnDemand(opRef);
    return true;
  }

  // Is `opRef` a candidate for on-demand pricing? Only when it's multi-eligible
  // (>1 eligible row → a cross-machine move exists to price) and carries no
  // ghosts yet (the precomputed batch missed it).
  function isUncovered(opRef) {
    if ((ghostIndex.get(opRef) || []).length) return false;
    const rows = S.tier0?.rows || [];
    return rows.filter((r) => r.eligible).length > 1;
  }

  // Fire on-demand pricing for a grabbed, uncovered op and fade its ghosts in
  // when priced (CU1). Never re-fires (pricingRequested); shows a shimmer while
  // in flight and a one-line "no cheaper alternative" note if the priced roads
  // all cost more or are infeasible — so the answer is always visible.
  function maybePriceOnDemand(opRef) {
    if (!api.priceOpAlternatives || !api.getAlternatives) return;
    if (pricingRequested.has(opRef) || !isUncovered(opRef)) return;
    pricingRequested.add(opRef);
    showPricing("pricing alternatives…");
    api.priceOpAlternatives(scheduleId, opRef, {}).then((r) => {
      if (r === null) { hidePricing(); return; }   // endpoint absent — stay quiet-green
      pollForGhosts(opRef, 0);
    });
  }

  function pollForGhosts(opRef, tries) {
    // stop polling if the planner moved on to another op / released the grab
    if (S.op !== opRef || (S.phase !== "grabbed" && S.phase !== "dragging")) {
      hidePricing();
      return;
    }
    api.getAlternatives(scheduleId).then((alt) => {
      if (alt) {
        setAlternatives(alt, null);
        const ghosts = ghostIndex.get(opRef) || [];
        if (ghosts.length) {
          // priced → fade the ghosts in for the still-grabbed op
          S.opGhosts = ghosts;
          S.tier0 = computeTier0(opRef, ctx, { ghosts });
          const win = board.getWindow();
          renderShade(layers.shade, S.tier0, geometry, win);
          S.drawnGhosts = renderGhosts(layers.ghosts, ghostLabels, S.opGhosts, geometry, win);
          layers.ghosts.classList.add("fade-in");
          hidePricing();
          return;
        }
      }
      if (tries + 1 >= ONDEMAND_MAX_POLLS) {
        showPricing("no cheaper alternative found", /*fade*/ true);
        return;
      }
      setTimeout(() => pollForGhosts(opRef, tries + 1), ONDEMAND_POLL_MS);
    });
  }

  function showPricing(text, fade = false) {
    pricingTip.textContent = text;
    pricingTip.classList.remove("hidden");
    pricingTip.classList.toggle("shimmer", !fade);
    if (fade) setTimeout(hidePricing, 2200);
  }
  function hidePricing() { pricingTip.classList.add("hidden"); pricingTip.classList.remove("shimmer"); }

  // Move the carry to a candidate (resource, time): snap, legality, dim-refuse.
  function dragTo(resourceId, timeMs, altKey = false) {
    if (S.phase !== "grabbed" && S.phase !== "dragging") return;
    S.phase = "dragging";
    const pxToMin = geometry.pxToMinutes(1) || 1;
    const anchors = anchorsForRow(S.tier0, resourceId, feel, S.opGhosts);
    const snapped = snap(timeMs, anchors, feel, pxToMin, altKey);
    let t = snapped.time_ms;
    const legality = isLegalStart(S.op, resourceId, new Date(t).toISOString(), ctx);
    let legal = legality.legal, reason = legality.reason;

    // dim-refuse with boundary pinning (the 3.0b-proven behavior): over a dim
    // spot, pin the carry at the nearest legal boundary on this row instead of
    // letting it sit illegally. Still flagged dim (cursor + reason) until it is
    // actually over green.
    if (!legal) {
      const pinned = nearestLegalBoundary(resourceId, t);
      if (pinned != null) t = pinned;
    }
    S.target = { resource_id: resourceId, time_ms: t, legal, reason, anchor: snapped.anchor };
    renderCarry();
    root.classList.toggle("refusing", !legal);
    if (!legal) showReason(resourceId, t, reason);
    else reasonTip.classList.add("hidden");
  }

  function drop() {
    if (S.phase !== "dragging" && S.phase !== "grabbed") return;
    const t = S.target;
    if (!t || !t.legal) return returnHome(t?.reason || "not a legal placement");

    // dropped ONTO a ghost? (snapped to a ghost anchor, or coincident with a
    // drawn ghost on this row) → near-instant card from the vouching schedule.
    const ghost = ghostAt(t.resource_id, t.time_ms);
    if (ghost) return dropOnGhost(ghost);

    // otherwise a Tier-2 sandbox re-solve (R-T1c) behind the tentative bar.
    S.phase = "tentative";
    clearLegalityOverlays();             // the drop answered "where" — clear the wash (CU1)
    renderCarry();                       // promote carry → tentative style
    card.showPending(feel.sandbox.budget_s, feel.sandbox.countdown_tick_ms);
    const t0 = performance.now();
    const pin = {
      pin_op_id: S.op, pin_resource_id: t.resource_id,
      pin_start_iso: new Date(t.time_ms).toISOString(),
      budget_s: feel.sandbox.budget_s,
    };
    return api.postSandbox(scheduleId, pin).then((result) => {
      S.dropToVerdictMs = +(performance.now() - t0).toFixed(2);
      applyResult(result);
      return result;
    }).catch((e) => {
      returnHome(`sandbox error: ${e.message || e}`);
    });
  }

  // Drop onto a ghost: the placement is a complete solved schedule's vouched-for
  // spot, so its price is known — render the card immediately (near-instant, no
  // fresh solve, R-T1c). Then (session 3.3 CU4) lazy-fetch the ghost's own
  // member document and diff it against the incumbent to trace the FULL
  // moved-set — every op that solved schedule displaced, not just the dropped
  // bar — showing "consequences loading…" until it lands (R-DP7: never silence).
  function dropOnGhost(ghost) {
    const opRef = S.op;
    const inc = incumbentOf(opRef);
    const result = {
      outcome: "verdict", status: "GHOST", feasible: true, within_budget: true,
      delta_pct: ghost.delta_pct, delta_abs: null,
      message: "from a vouched-for alternative (no re-solve needed)",
      moves: [{
        operation_ref: opRef,
        from_resource: inc?.resource_id, to_resource: ghost.resource_id,
        from_start: inc ? new Date(inc.start_ms).toISOString() : ghost.start,
        to_start: ghost.start,
        start_delta_min: inc ? Math.round((ms(ghost.start) - inc.start_ms) / MIN) : 0,
        resource_changed: inc ? inc.resource_id !== ghost.resource_id : true,
        pinned: true,
      }],
      pin: { operation_ref: opRef, resource_id: ghost.resource_id, start: ghost.start },
    };
    S.target = { resource_id: ghost.resource_id, time_ms: ms(ghost.start), legal: true, reason: null, anchor: null };
    S.phase = "tentative";
    clearLegalityOverlays();             // the drop answered "where" — clear the wash (CU1)
    S.dropToVerdictMs = 0;               // near-instant path

    const loadable = ghost.source === "forced_alternative"
      && ghost.member_index != null && api.getAlternativeMember;
    result.consequences_pending = loadable;
    applyResult(result);
    if (loadable) fetchGhostConsequences(opRef, ghost);
    return Promise.resolve(result);
  }

  // CU4: pull the ghost's full solved schedule and diff it against the
  // incumbent → the complete moved-set (ghost-of-old + motion line for every
  // displaced op), then re-render traces + card. A failed/absent fetch keeps
  // the single-bar trace already on screen (never silence, never a lie).
  function fetchGhostConsequences(opRef, ghost) {
    api.getAlternativeMember(scheduleId, ghost.member_index).then((memberDoc) => {
      // ignore if the gesture moved on (discarded / new grab / different op)
      if (!memberDoc || S.op !== opRef || S.phase !== "verdict") return;
      const moves = movedSetFromDoc(memberDoc, opRef, ghost);
      if (!moves.length) return;
      S.result = { ...S.result, moves, consequences_pending: false };
      S.traces = renderTraces(layers.traces, svg, moves, durationMinOf, geometry, board.getWindow());
      card.showResult(S.result, { nameOf, woOf });
    });
  }

  // Diff a ghost's member document (a complete solved schedule) against the
  // incumbent → moves old→new for every op it placed differently, in the same
  // shape the sandbox moved-set uses. The dropped op leads (pinned).
  function movedSetFromDoc(memberDoc, pinnedOp, ghost) {
    const moves = [];
    for (const a of memberDoc.assignments || []) {
      const op = a.operation_ref;
      const newRid = a.resource_id, newStart = a.chunks?.[0]?.start;
      const old = asgByOp.get(op);
      if (!old || !newStart) continue;
      const oldRid = old.resource_id, oldStart = old.chunks?.[0]?.start;
      if (!oldStart) continue;
      const delta = Math.round((ms(newStart) - ms(oldStart)) / MIN);
      const changed = newRid !== oldRid || Math.abs(delta) >= 1;
      const isPin = op === pinnedOp;
      if (!changed && !isPin) continue;
      moves.push({
        operation_ref: op, from_resource: oldRid, to_resource: newRid,
        from_start: oldStart, to_start: newStart, start_delta_min: delta,
        resource_changed: newRid !== oldRid, pinned: isPin,
      });
    }
    moves.sort((a, b) =>
      (a.pinned ? 0 : 1) - (b.pinned ? 0 : 1)
      || Math.abs(b.start_delta_min) - Math.abs(a.start_delta_min));
    return moves;
  }

  function applyResult(result) {
    S.result = result;
    const returnHome_ = result.outcome === "no_verdict" || !result.feasible;
    if (returnHome_) {
      card.showResult(result, { nameOf, woOf });
      return returnHome(result.message, /*keepCard*/ true);
    }
    S.phase = "verdict";
    renderCarry();                        // tentative bar stays put (R-DP1)
    S.traces = renderTraces(layers.traces, svg, result.moves || [], durationMinOf, geometry, board.getWindow());
    card.showResult(result, { nameOf, woOf });
  }

  // Release over dim / no verdict: the bar goes home ANIMATED with the reason
  // (R-DP2/R-DP7a — never teleports). Here "animated" = a brief class the CSS
  // transitions; the carry then clears.
  function returnHome(reason, keepCard = false) {
    root.classList.add("returning");
    reasonTip.classList.add("hidden");
    const inc = incumbentOf(S.op);
    if (inc && S.target) { S.target = { resource_id: inc.resource_id, time_ms: inc.start_ms, legal: true }; renderCarry(); }
    setTimeout(() => {
      root.classList.remove("returning", "refusing", "active");
      if (!keepCard) card.hide();
      clearOverlays();
      S.phase = "idle"; S.op = null; S.tier0 = null; S.target = null;
    }, 260);
    return { returned: true, reason };
  }

  function discard() {
    root.classList.remove("active", "refusing", "returning");
    card.hide();
    clearOverlays();
    S.phase = "idle"; S.op = null; S.tier0 = null; S.target = null;
    S.result = null; S.traces = [];
  }

  function cancelSilently() {
    clearOverlays();
    S.phase = "idle"; S.op = null; S.tier0 = null; S.target = null;
  }

  function clearOverlays() {
    for (const el of Object.values(layers)) el.replaceChildren();
    ghostLabels.replaceChildren();
    layers.ghosts.classList.remove("fade-in");
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    reasonTip.classList.add("hidden");
    hidePricing();
  }

  // Clear ONLY the Tier-0 legality overlays (shade + ghosts + the refusal
  // reason), keeping the tentative bar, traces, and card. Used on the
  // drop→tentative transition (CU1): the drop has answered "where can it go",
  // so the green/amber/dim wash and the ghost bars retire.
  function clearLegalityOverlays() {
    layers.shade.replaceChildren();
    layers.ghosts.replaceChildren();
    layers.ghosts.classList.remove("fade-in");
    ghostLabels.replaceChildren();
    S.drawnGhosts = [];
    reasonTip.classList.add("hidden");
    hidePricing();
    root.classList.remove("refusing");
  }

  // ---------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------
  function nearestLegalBoundary(resourceId, timeMs) {
    const row = S.tier0.rows.find((r) => r.resource_id === resourceId);
    if (!row || !row.legal_regions.length) return null;
    let best = null, bestD = Infinity;
    for (const r of row.legal_regions) {
      for (const edge of [ms(r.start), ms(r.end)]) {
        const d = Math.abs(edge - timeMs);
        if (d < bestD) { bestD = d; best = edge; }
      }
      if (timeMs >= ms(r.start) && timeMs <= ms(r.end)) return timeMs; // already legal
    }
    return best;
  }

  function ghostAt(resourceId, timeMs, tolMin = 30) {
    for (const g of S.opGhosts) {
      if (g.resource_id !== resourceId || !g.start) continue;
      if (Math.abs(ms(g.start) - timeMs) / MIN <= tolMin) return g;
    }
    return null;
  }

  function showReason(resourceId, timeMs, reason) {
    const text = REASONS[reason] || reason || "illegal here";
    reasonTip.textContent = text;
    const rect = geometry.barRect(resourceId, timeMs, timeMs + durationMinOf(S.op) * MIN);
    if (rect) {
      reasonTip.style.left = `${rect.x}px`;
      reasonTip.style.top = `${rect.top - 4}px`;
    }
    reasonTip.classList.remove("hidden");
  }

  function navigateToOp(opRef) {
    board.select(opRef);
    // pulse the bar's trace, if present
    for (const el of layers.traces.querySelectorAll(`[data-op="${opRef}"]`)) {
      el.classList.add("pulse");
      setTimeout(() => el.classList.remove("pulse"), 900);
    }
  }

  // ---------------------------------------------------------------------
  // Pointer wiring — drives the SAME transitions for real use. Guarded so a
  // plain click still selects (the ask panel's deictic scope). A drag begins
  // only after the pointer leaves the grab bar's slop radius.
  // ---------------------------------------------------------------------
  let down = null;
  function onPointerDown(ev) {
    const target = geometry.eventToTarget(ev);
    const props = safeProps(ev);
    const itemId = props?.item;
    if (itemId == null || !asgById.has(itemId)) return;   // not a bar
    down = { x: ev.clientX, y: ev.clientY, op: asgById.get(itemId).operation_ref, moved: false };
    // Still the board from the very first pixel: suppress vis's built-in
    // pan/zoom the instant the pointer lands on a bar, before any movement can
    // start a Hammer pan (3.2c). A plain click that never becomes a drag simply
    // restores it on pointerup below — vis tap-selection is unaffected.
    board.setPanZoom(false);
  }
  function onPointerMove(ev) {
    if (!down) return;
    if (!down.moved && Math.hypot(ev.clientX - down.x, ev.clientY - down.y) < 5) return;
    if (!down.moved) { down.moved = true; grab(down.op); root.style.pointerEvents = "auto"; }
    const t = geometry.eventToTarget(ev);
    if (t && t.resource_id != null && t.time_ms != null) dragTo(t.resource_id, t.time_ms, ev.altKey);
    ev.preventDefault();
  }
  function onPointerUp(ev) {
    const wasDown = !!down;
    if (down && down.moved) { drop(); ev.preventDefault(); ev.stopPropagation(); }
    down = null; root.style.pointerEvents = "none";
    // pan/zoom resumes the instant the drag ends — a dropped/tentative bar no
    // longer owns the cursor, so the user is free to pan the board again (3.2c).
    if (wasDown) board.setPanZoom(true);
  }
  const center = timeline.dom.centerContainer;
  center.addEventListener("pointerdown", onPointerDown, true);
  window.addEventListener("pointermove", onPointerMove, true);
  window.addEventListener("pointerup", onPointerUp, true);

  function safeProps(ev) { try { return timeline.getEventProperties(ev); } catch { return null; } }

  // ---------------------------------------------------------------------
  // Public surface (used by main/interaction + the harness).
  // ---------------------------------------------------------------------
  return {
    feel, ctx, redraw, setAlternatives,
    grab, dragTo, drop, discard, returnHome,
    // programmatic drop straight to a target (harness convenience): grab, drag
    // to the target, drop — the full path, no pointer math.
    dropAt(opRef, resourceId, startIso, altKey = false) {
      grab(opRef);
      dragTo(resourceId, ms(startIso), altKey);
      return drop();
    },
    // probes for the screenshot harness / standing regressions
    state: () => ({
      phase: S.phase, op: S.op,
      grabToShadeMs: S.grabToShadeMs, dropToVerdictMs: S.dropToVerdictMs,
      target: S.target && { ...S.target },
      ghosts: S.drawnGhosts.map((g) => ({ source: g.source, resource_id: g.resource_id, label: g.label || null, delta_pct: g.delta_pct })),
      result: S.result && { outcome: S.result.outcome, delta_pct: S.result.delta_pct, moves: (S.result.moves || []).length },
      traces: S.traces.length,
    }),
    tier0For: (opRef) => computeTier0(opRef, ctx, { ghosts: ghostIndex.get(opRef) || [] }),
    ghostsFor: (opRef) => ghostIndex.get(opRef) || [],
    // drift probe for ghost labels (the C1 discipline, extended): tag center vs
    // ghost bar center, both read from the DOM.
    ghostDriftProbe() {
      const base = geometry.base();
      const bars = [...layers.ghosts.querySelectorAll(".ghost-bar")];
      const tags = [...ghostLabels.querySelectorAll(".ghost-tag")];
      return bars.map((b, i) => {
        const rb = b.getBoundingClientRect(), tg = tags[i]?.getBoundingClientRect();
        const bcx = rb.left + rb.width / 2 - base.left;
        const tcx = tg ? tg.left + tg.width / 2 - base.left : null;
        return {
          barCx: +bcx.toFixed(1),
          tagCx: tcx == null ? null : +tcx.toFixed(1),
          driftPx: tcx == null ? null : +Math.abs(tcx - bcx).toFixed(1),
          legible: !!tags[i] && (tags[i].textContent || "").length >= 3,
        };
      });
    },
  };
}

const REASONS = {
  capability: "this machine can't run this operation",
  precedence_floor: "a predecessor hasn't finished yet",
  calendar_or_window_fit: "closed here, or won't fit before close",
  calendar: "the machine is closed here",
  window_fit: "won't fit in the open time here",
};

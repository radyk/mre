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
  const { api } = opts;
  // Mutable across an accepted edit: accept rebinds the whole surface to the new
  // schedule version so a SEQUENTIAL edit sandboxes against it (CU1).
  let doc = opts.doc;
  let interaction = opts.interaction;
  let scheduleId = opts.scheduleId;
  const authority = opts.authority || "dev-planner";
  // Self-heal seam (session 3.8 CU3): a live drop/accept that 409s "superseded"
  // means this session is holding a stale id — route forward to the live
  // successor instead of a raw "sandbox error" / silent return-home.
  const onSuperseded = opts.onSuperseded || null;
  function handleSuperseded() {
    if (onSuperseded) { onSuperseded(scheduleId); return true; }
    return false;
  }
  const feel = opts.feel || makeFeel();
  applyFeel(feel);

  let ctx = buildContext(doc, interaction);
  const timeline = board.timeline;

  // --- planner-vocabulary + incumbent indexes --------------------------
  const asgByOp = new Map();          // op -> assignment (incumbent placement)
  const asgById = new Map();          // assignment_id -> assignment
  function rebuildAsgIndex() {
    asgByOp.clear(); asgById.clear();
    for (const a of doc.assignments || []) {
      asgByOp.set(a.operation_ref, a);
      asgById.set(a.assignment_id, a);
    }
  }
  rebuildAsgIndex();
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

  // --- the delta card (CU4 + CU1 accept/publish) -----------------------
  const card = createDeltaCard(board.host.parentElement || board.host, {
    onDiscard: discard,
    onNavigate: (opRef) => navigateToOp(opRef),
    onAccept: accept,
    onPublish: publish,
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
  const reduceMotion = () =>
    typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

  // R-M1d: fade ghosts in with their labels — BOTH layers together, so a label
  // never pops independently of its bar. Retriggered by removing + reflowing.
  function fadeGhosts() {
    for (const el of [layers.ghosts, ghostLabels]) {
      el.classList.remove("ghost-fade");
      void el.offsetWidth;
      el.classList.add("ghost-fade");
    }
  }

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
    if (S.drawnGhosts.length) fadeGhosts();   // R-M1d: ghosts fade in (labels with bars)
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
  // ghosts yet (the precomputed batch missed it). Works BEFORE a grab: if the op
  // isn't the currently-grabbed one, its eligibility is computed on the fly
  // (tier0For) so pricing can fire on pointer-DOWN (CU4 dial b) — buying back the
  // reaction time before the drag even starts.
  function isUncovered(opRef) {
    if ((ghostIndex.get(opRef) || []).length) return false;
    const rows = (S.op === opRef && S.tier0)
      ? S.tier0.rows
      : (computeTier0(opRef, ctx, { ghosts: ghostIndex.get(opRef) || [] }).rows || []);
    return rows.filter((r) => r.eligible).length > 1;
  }

  // Fire on-demand pricing for an uncovered op and fade its ghosts in when priced
  // (CU1/CU4). Never re-fires (pricingRequested). ``eager`` (pointer-down, CU4
  // dial b) primes silently in the background — no shimmer until an actual grab —
  // so a pre-price that the planner never follows through on stays invisible.
  function maybePriceOnDemand(opRef, { eager = false } = {}) {
    if (!api.priceOpAlternatives || !api.getAlternatives) return;
    if (pricingRequested.has(opRef) || !isUncovered(opRef)) return;
    pricingRequested.add(opRef);
    S.priceFiredAt = S.priceFiredAt || {};
    S.priceFiredAt[opRef] = performance.now();
    if (!eager) showPricing("pricing alternatives…");
    api.priceOpAlternatives(scheduleId, opRef, {}).then((r) => {
      if (r === null) { hidePricing(); return; }   // endpoint absent — stay quiet-green
      pollForGhosts(opRef, 0, eager);
    });
  }

  function pollForGhosts(opRef, tries, eager = false) {
    // An EAGER (pre-grab) prime keeps polling regardless of grab state — it is
    // filling the cache for a grab that may come. A grab-time poll stops if the
    // planner moved on / released.
    if (!eager && (S.op !== opRef || (S.phase !== "grabbed" && S.phase !== "dragging"))) {
      hidePricing();
      return;
    }
    api.getAlternatives(scheduleId).then((alt) => {
      if (alt) {
        setAlternatives(alt, null);
        const ghosts = ghostIndex.get(opRef) || [];
        if (ghosts.length) {
          // record time-to-ghosts (CU4 measurement) from the fire instant
          const t0 = (S.priceFiredAt || {})[opRef];
          if (t0 != null) {
            S.priceToGhostsMs = S.priceToGhostsMs || {};
            S.priceToGhostsMs[opRef] = +(performance.now() - t0).toFixed(2);
          }
          // if the op is grabbed right now, fade its ghosts in; otherwise the
          // cache is warmed for when it IS grabbed (eager prime, CU4 dial b).
          if (S.op === opRef && (S.phase === "grabbed" || S.phase === "dragging")) {
            S.opGhosts = ghosts;
            S.tier0 = computeTier0(opRef, ctx, { ghosts });
            const win = board.getWindow();
            renderShade(layers.shade, S.tier0, geometry, win);
            S.drawnGhosts = renderGhosts(layers.ghosts, ghostLabels, S.opGhosts, geometry, win);
            fadeGhosts();   // R-M1d: on-demand ghosts fade in too, labels WITH bars
          }
          hidePricing();
          return;
        }
      }
      if (tries + 1 >= ONDEMAND_MAX_POLLS) {
        if (!eager) showPricing("no cheaper alternative found", /*fade*/ true);
        return;
      }
      setTimeout(() => pollForGhosts(opRef, tries + 1, eager), ONDEMAND_POLL_MS);
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
      if (e && e.superseded && handleSuperseded()) return;
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
      const isPin = op === pinnedOp;
      // R-DP8 CU2: a standing-pinned op is a held commitment — never a moved
      // consequence. Structurally excluded here (unless it IS the dropped op).
      if (old.standing_pin && !isPin) continue;
      const oldRid = old.resource_id, oldStart = old.chunks?.[0]?.start;
      if (!oldStart) continue;
      const delta = Math.round((ms(newStart) - ms(oldStart)) / MIN);
      const changed = newRid !== oldRid || Math.abs(delta) >= 1;
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

  // Release over dim / no verdict: the bar goes home as a REJECTION (R-M1a) —
  // a FAST snap-back (no settling ease, so it reads as "refused" not "placed")
  // plus a brief, subtle arrival shake. The reason stays in the text channels
  // (card / the mid-drag reason), never the animation. Under reduced motion the
  // snap is instant and the shake is dropped — the meaning survives via the text.
  function returnHome(reason, keepCard = false) {
    root.classList.add("returning");
    reasonTip.classList.add("hidden");
    const m = feel.motion || {};
    const reduce = reduceMotion();
    const snapMs = reduce ? 0 : (m.reject_dur_ms ?? 200);
    const shakeMs = reduce ? 0 : (m.reject_shake_dur_ms ?? 140);
    const inc = incumbentOf(S.op);
    // Move the EXISTING carry element back home so the snap-back actually
    // transitions (a fresh render would teleport). Keep S.target consistent so a
    // stray redraw lands the carry at home, not the dropped spot.
    const bar = layers.tentative.querySelector(".carry-bar");
    if (inc) {
      S.target = { resource_id: inc.resource_id, time_ms: inc.start_ms, legal: true };
      const dur = durationMinOf(S.op) * MIN;
      const home = geometry.barRect(inc.resource_id, inc.start_ms, inc.start_ms + dur);
      if (bar && home) {
        bar.classList.remove("legal", "dim", "tentative");
        if (!reduce) { bar.classList.add("rejecting"); void bar.offsetWidth; }
        bar.style.left = `${home.x}px`;
        bar.style.top = `${home.top + 3}px`;
        if (!reduce) setTimeout(() => { if (bar.isConnected) bar.classList.add("reject-shake"); }, snapMs);
      } else {
        renderCarry();
      }
    }
    setTimeout(() => {
      root.classList.remove("returning", "refusing", "active");
      if (!keepCard) card.hide();
      clearOverlays();
      S.phase = "idle"; S.op = null; S.tier0 = null; S.target = null;
    }, snapMs + shakeMs + 30);
    return { returned: true, reason };
  }

  // Accept the verdict (CU1, R-DP7): pin the op server-side, minting a NEW
  // proposed schedule version (the base is never mutated) + a planner_edit
  // Decision. On success the board REBINDS to the new version — the traced bars
  // settle into their new positions (a legible transition, never a reload) — and
  // the controller rebinds too, so a sequential edit sandboxes against it.
  function accept() {
    if (S.phase !== "verdict" || !S.op || !S.target) return Promise.resolve(null);
    if (!api.postAccept || !api.getSchedule) return Promise.resolve(null);
    S.phase = "accepting";
    // The pin is the drop exactly as displayed (R-DP1) — read from the gesture
    // state, not the server echo, so accept never depends on the sandbox payload
    // carrying it back.
    const pin = {
      pin_op_id: S.op,
      pin_resource_id: S.target.resource_id,
      pin_start_iso: new Date(S.target.time_ms).toISOString(),
      authority,
    };
    S.acceptToDoneMs = null;
    const t0 = performance.now();
    // R-M1b/c: the dropped op is OWN PLACEMENT (never moves → pin-lock); the
    // other displaced ops are the REFLOW set (simultaneous eased, highlighted).
    // Captured from the verdict moved-set BEFORE the traces are cleared.
    const droppedOp = S.op;
    const movedOps = new Set(((S.result && S.result.moves) || [])
      .map((mv) => mv.operation_ref).filter((op) => op !== droppedOp));
    return api.postAccept(scheduleId, pin).then((res) =>
      api.getSchedule(res.schedule_id).then((newDoc) => {
        // the traces pointed old→new all along; the REFLOW settles the real bars
        // there (R-M1b) — one instance of the reflow class, unified with 3.4's
        // accept-rebind; the dropped bar pin-locks in place (R-M1c).
        board.rebind(newDoc, { pinnedOp: droppedOp, movedOps, motion: feel.motion });
        clearTraces();
        layers.tentative.replaceChildren();   // the committed board bar (pin-lock) now stands for it
        return rebindController(res.schedule_id, newDoc).then(() => {
          S.acceptToDoneMs = +(performance.now() - t0).toFixed(2);
          S.phase = "accepted";
          S.acceptedId = res.schedule_id;
          card.showAccepted({ newScheduleId: res.schedule_id, decision: res.decision });
          if (opts.onVersionChange) opts.onVersionChange(res.schedule_id, "proposed");
          return res;
        });
      })
    ).catch((e) => {
      S.phase = "verdict";
      if (e && e.superseded && handleSuperseded()) return;
      // R-M1a (4.0c): a refused accept must be LOUD, never a silent bar-goes-home.
      // Render the authored refusal on the card (it shakes), then snap the bar
      // home as a rejection — but KEEP the card so the reason stays on screen.
      const reason = (e && (e.rawMessage || e.message)) || String(e);
      card.showRefused({ reason });
      returnHome(reason, /*keepCard*/ true);
    });
  }

  // Publish the accepted version (CU1): proposed → published, superseding the
  // prior version. The explicit second act.
  function publish() {
    if (S.phase !== "accepted" || !S.acceptedId || !api.postPublish) return Promise.resolve(null);
    S.phase = "publishing";
    return api.postPublish(S.acceptedId).then((res) => {
      S.phase = "published";
      card.showPublished({ scheduleId: res.schedule_id, superseded: res.superseded });
      if (opts.onVersionChange) opts.onVersionChange(res.schedule_id, "published");
      return res;
    }).catch((e) => {
      S.phase = "accepted";
      card.showAccepted({ newScheduleId: S.acceptedId, decision: null });
    });
  }

  // Rebind the whole gesture surface to a new schedule version: fetch its Tier-0
  // interaction payload (so legality + snapping recompute against the new
  // placements) and its priced ghosts, and rebuild the incumbent indexes. Leaves
  // the board (already rebound) settling its bars.
  function rebindController(newId, newDoc) {
    scheduleId = newId;
    doc = newDoc;
    rebuildAsgIndex();
    const iP = api.getInteraction ? api.getInteraction(newId) : Promise.resolve(null);
    const aP = api.getAlternatives ? api.getAlternatives(newId) : Promise.resolve(null);
    return Promise.all([iP, aP]).then(([ip, alt]) => {
      interaction = (ip && ip.interaction) || interaction;
      ctx = buildContext(doc, interaction);
      pricingRequested.clear();
      setAlternatives(alt || null, null);
    });
  }

  function clearTraces() {
    layers.traces.replaceChildren();
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    S.traces = [];
  }

  function discard() {
    root.classList.remove("active", "refusing", "returning");
    card.hide();
    clearOverlays();
    if (board.clearMotionClasses) board.clearMotionClasses();  // clear a prior pin-lock (R-M1c)
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
    layers.ghosts.classList.remove("ghost-fade");
    ghostLabels.classList.remove("ghost-fade");
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
    layers.ghosts.classList.remove("ghost-fade");
    ghostLabels.classList.remove("ghost-fade");
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
    // CU4 dial (b): fire on-demand pricing on pointer-DOWN — before the drag
    // threshold is even crossed — so the K per-machine solves are already in
    // flight by the time the bar lifts, buying back reaction time. Eager =
    // silent (no shimmer until an actual grab). Dedup'd, so grab() is a no-op.
    maybePriceOnDemand(down.op, { eager: true });
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
    grab, dragTo, drop, discard, returnHome, accept, publish,
    scheduleId: () => scheduleId,
    // programmatic drop straight to a target (harness convenience): grab, drag
    // to the target, drop — the full path, no pointer math.
    dropAt(opRef, resourceId, startIso, altKey = false) {
      grab(opRef);
      dragTo(resourceId, ms(startIso), altKey);
      return drop();
    },
    // probes for the screenshot harness / standing regressions
    state: () => ({
      phase: S.phase, op: S.op, acceptedId: S.acceptedId || null,
      grabToShadeMs: S.grabToShadeMs, dropToVerdictMs: S.dropToVerdictMs,
      acceptToDoneMs: S.acceptToDoneMs || null,
      priceToGhostsMs: (S.priceToGhostsMs || {})[S.op] || null,
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
  // solver-pruned rows the payload names (contract 1.4, R-DP6): a
  // capability-eligible machine the solver still refuses a literal for.
  no_calendar_window: "no open calendar window this horizon",
  wip_fixed: "this operation is already running and can't be moved",
};

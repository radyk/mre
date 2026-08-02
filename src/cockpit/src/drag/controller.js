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
  // Session 4B.28 Item 4(a) — A CHUNK PIECE IS PART OF ITS OPERATION.
  //
  // 4B.20 split a chunked bar into one vis item PER CHUNK (`<id>~c0`, `~c1`, …).
  // `onPointerDown` tested `asgById.has(itemId)` and a piece id is not an
  // assignment id, so the gesture never started and vis's own Hammer pan took
  // the drag instead: pulling a split bar PANNED THE BOARD. Silent, and the one
  // outcome the ruling forbids by name. Every piece now resolves to its
  // assignment, so a grab on any piece is a grab on the operation.
  const asgByItem = new Map();        // item id (whole OR piece) -> assignment
  function rebuildAsgIndex() {
    asgByOp.clear(); asgById.clear(); asgByItem.clear();
    for (const a of doc.assignments || []) {
      asgByOp.set(a.operation_ref, a);
      asgById.set(a.assignment_id, a);
      asgByItem.set(a.assignment_id, a);
      const n = (a.chunks || []).length;
      if (n > 1) {
        for (let i = 0; i < n; i += 1) asgByItem.set(`${a.assignment_id}~c${i}`, a);
      }
    }
  }
  const chunkCountOf = (opRef) => ((asgByOp.get(opRef) || {}).chunks || []).length;
  const isChunked = (opRef) => chunkCountOf(opRef) > 1;
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
  // R-DP9 (CU2): a brief "already here" cue for a no-op drop (a drop within snap
  // tolerance of the incumbent). Calmer than a refusal — no shake, no card.
  const noopTip = document.createElement("div");
  noopTip.className = "drag-noop hidden";
  root.appendChild(noopTip);
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
    result: null,           // last sandbox result (beat two)
    traces: [],             // drawn moved-set
    grabToShadeMs: null,
    dropToVerdictMs: null,
    // R-T2 two-beat (Session 4B.3b)
    ghost: null,            // beat-one FeasibilityGhost
    cardContext: null,      // CU2: the open card as ask-panel context (or null)
    correlationId: null,    // links beat one → beat two
    dropToGhostMs: null,    // grab→drop→feasibility ghost latency
    contradiction: null,    // {infeasible, moved} if beat two contradicted beat one
    askWhyContext: null,    // the sandbox context an "ask why" hands off
    // Session 4B.23: beat one's THREE-state verdict as this gesture saw it —
    // "possible" | "impossible" | "undetermined" | "failed" | null. And, when a
    // beat could not be completed at all, the AUTHORED cause plus the raw
    // technical string (which is for whoever is debugging, never for the card).
    beatOne: null,
    beatOneError: null,
    failure: null,          // {beat, what, technical, status} — a visible failure
  };

  // --- the delta card (CU4 + CU1 accept/publish + R-T2 ask-why) --------
  const card = createDeltaCard(board.host.parentElement || board.host, {
    onDiscard: discard,
    onNavigate: (opRef) => navigateToOp(opRef),
    onAccept: accept,
    onPublish: publish,
    onAskWhy: (result) => askWhy(result),
    // Session 4B.23: "Try again" on a FAILURE (a beat we could not complete) or
    // on beat two's `no_verdict`. Both are statements about our budget, so the
    // one honest affordance is another attempt at the SAME pin — never a
    // reinterpretation of the gesture.
    onRetry: () => retryLastGesture(),
    // Session 4B.24 clause (4): TWO CEREMONIES, wired to TWO callbacks. The card
    // can offer the search's improvement beside the move's price, and clicking
    // one can never commit the other.
    onSearchDeeper: () => searchDeeper(),
    onAcceptSearch: () => acceptSearch(),
  });

  // ---------------------------------------------------------------------
  // Session 4B.5 CU2 — THE OPEN DELTA CARD as conversational context.
  //
  // A priced card on screen is the top of the ask panel's resolution ladder: while
  // it is open, "this move" / "these orders" / "the delta" are about IT, and the
  // `open-card` route reads back exactly this payload rather than re-deriving
  // anything. So the payload is the CARD'S OWN CONTENT, assembled here where the
  // card is rendered — one place, one set of numbers, no second derivation to
  // drift.
  //
  // It is published on exactly the transitions that change what is on screen, and
  // CLEARED on every one that takes the card away (discard, accept, publish,
  // return-home, a fresh grab). A stale card would answer confidently about a
  // move the planner can no longer see, which is the failure class this whole
  // session is about.
  // ---------------------------------------------------------------------
  function cardContextFrom(result) {
    if (!result) return null;
    const pin = (result.moves || []).find((m) => m.pinned) || null;
    const rid = pin ? pin.to_resource : (result.pin && result.pin.resource_id);
    const opRef = (pin && pin.operation_ref)
      || (result.pin && result.pin.operation_ref) || S.op;
    const startIso = pin ? pin.to_start : (result.pin && result.pin.start);
    return {
      open: true,
      operation_ref: opRef || null,
      order: (opRef && woOf(opRef)) || null,
      machine: (rid && nameOf(rid)) || null,
      when: startIso ? _cardWhen(startIso) : null,
      outcome: result.outcome || null,
      feasible: result.feasible !== false,
      message: result.message || "",
      correlation_id: result.correlation_id || S.correlationId || null,
      cost_delta_abs: result.cost_delta_abs ?? null,
      attribution: result.attribution || "unavailable",
      reopt_delta_abs: result.reopt_delta_abs ?? null,
      move_delta_abs: result.move_delta_abs ?? null,
      attribution_note: result.attribution_note || "",
      cost_lines: result.cost_lines || null,
      affected_orders: result.affected_orders || [],
      lateness_delta_min: result.lateness_delta_min ?? 0,
      // the moved-set COUNT includes the pinned op, exactly as the card's own
      // line items do — the answer subtracts it to say "what else moved".
      moves: (result.moves || []).length,
      no_committed_work_changes: result.no_committed_work_changes !== false,
      dominant_driver: result.dominant_driver || null,
    };
  }

  function _cardWhen(iso) {
    const t = Date.parse(iso);
    if (Number.isNaN(t)) return null;
    return new Date(t).toLocaleString(undefined,
      { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  function publishCard(result) {
    const ctxCard = cardContextFrom(result);
    S.cardContext = ctxCard;
    if (opts.onCardChange) opts.onCardChange(ctxCard);
  }

  function clearCard() {
    if (S.cardContext === null) return;
    S.cardContext = null;
    if (opts.onCardChange) opts.onCardChange(null);
  }

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
    layers.tentative.replaceChildren();
    const tentative = S.phase === "tentative" || S.phase === "verdict";
    const cls = "carry-bar" + (tentative ? " tentative" : t.legal ? " legal" : " dim");

    // Item 4(a): THE PIECES MOVE AS ONE. A chunked operation carries one ghost
    // per chunk, RIGIDLY OFFSET from the incumbent — the whole job travels
    // together and the planner sees every piece it would take with it. It is a
    // preview of the GESTURE, and deliberately not a claim about where the
    // pauses would land: re-deriving those is the solver's job and is exactly
    // what this session cannot price. The carry says so in its own label.
    const a = asgByOp.get(S.op);
    const chunks = (a && a.chunks) || [];
    if (chunks.length > 1) {
      const home = ms(chunks[0].start);
      const shift = t.time_ms - home;
      chunks.forEach((c, i) => {
        const rect = geometry.barRect(t.resource_id, ms(c.start) + shift,
                                      ms(c.end) + shift);
        if (!rect) return;
        const el = document.createElement("div");
        el.className = `${cls} carry-piece${i === 0 ? " carry-first" : ""}`;
        Object.assign(el.style, {
          left: `${rect.x}px`, width: `${rect.width}px`,
          top: `${rect.top + 3}px`, height: `${rect.height - 6}px`,
        });
        el.textContent = i === 0 ? (woOf(S.op) || "") : "";
        layers.tentative.appendChild(el);
      });
      return;
    }

    const dur = durationMinOf(S.op) * MIN;
    const rect = geometry.barRect(t.resource_id, t.time_ms, t.time_ms + dur);
    if (!rect) return;
    const el = document.createElement("div");
    el.className = cls;
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
    clearCard();                 // CU2: a fresh gesture retires the previous card
    S.lastDropWasNoop = false;   // R-DP9: reset the no-op flag each fresh grab
    S.lastDropWasDeclined = null;
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
    if (!t || !t.legal) {
      // A TIER-0 REFUSAL — the calendar/eligibility answer, and a PRODUCT
      // ANSWER: the plant says no and says why. Session 4B.23: this used to snap
      // home with `reasonTip` hidden by `returnHome` itself, so the reason a
      // planner saw mid-drag vanished at the exact moment they let go — the
      // release, which is when they are looking for the answer. The card now
      // carries it, in the same register as a proven-impossible beat one,
      // because they are the same kind of statement.
      const why = REASONS[t?.reason] || t?.reason || "not a legal placement";
      card.showImpossible({ reason: why });
      publishCard(null);
      return returnHome(why, /*keepCard*/ true);
    }

    // R-DP9 (CU2): a drop within snap tolerance of the op's INCUMBENT placement
    // is a NO-OP — nothing to commit. Settle home with an "already here" cue; no
    // sandbox call, no zero-delta Decision, no standing pin for an unchanged
    // placement (a commitment that commits nothing still constrains every future
    // solve and pollutes the edit narrative — docs/04 R-DP9).
    if (isNoOpDrop(t)) return noOpReturn();

    // Item 4(a): A CHUNKED OPERATION DECLINES, VISIBLY, AND IN THE ASK PATH'S
    // OWN WORDS. The pricer holds every other placement and moves one bar; a
    // split operation's pauses are placements the solver made around calendar
    // closures, and a local shift cannot re-derive them. So there is no price to
    // report, and reporting one anyway would be the confident-wrong class.
    //
    // It is checked HERE — from the row, before any request — for 4B.30's
    // reason: a decline that costs a ~6.5s model build first is a decline that
    // reads as a failure. And it is a DECLINE, not a refusal: the copy says the
    // limit is ours, because a planner told "it can't go there" would act on a
    // claim about their plant that nobody has tested.
    if (isChunked(S.op)) return declineChunked(t);

    // dropped ONTO a ghost? (snapped to a ghost anchor, or coincident with a
    // drawn ghost on this row) → near-instant card from the vouching schedule.
    const ghost = ghostAt(t.resource_id, t.time_ms);
    if (ghost) return dropOnGhost(ghost);

    // otherwise the R-T2 TWO-BEAT sandbox behind the tentative bar.
    S.phase = "tentative";
    clearLegalityOverlays();             // the drop answered "where" — clear the wash (CU1)
    renderCarry();                       // promote carry → tentative style
    return twoBeat(t);
  }

  // R-T2 two-beat interaction (Session 4B.3b):
  //   BEAT ONE — a first-feasible feasibility ghost (no money, R-T2(1)); the
  //     carry bar reads the R-M1 ghost register while it prices (R-T2(2)).
  //   BEAT TWO — the priced, budgeted re-solve; it SUPERSEDES the ghost visibly
  //     (R-T2(3)). A beat-two contradiction (infeasible / materially moved) is
  //     SHOWN via R-M1 semantics, never silently reconciled (R-T2(4)).
  function twoBeat(t) {
    const pin = {
      pin_op_id: S.op, pin_resource_id: t.resource_id,
      pin_start_iso: new Date(t.time_ms).toISOString(),
    };
    S.ghost = null; S.correlationId = null; S.contradiction = null;
    // BEAT ONE — feasibility ghost. The carry wears the ghost register; the card
    // shows a NON-MONETARY "pricing…" state.
    markCarryGhost(true);
    card.showPricing(feel.sandbox.feasibility_budget_s, feel.sandbox.countdown_tick_ms);
    const t0 = performance.now();
    S.beatOne = null; S.beatOneError = null; S.failure = null;
    // Session 4B.23: remember the gesture so "Try again" can re-run THIS pin.
    // `returnHome` clears S.op/S.target on its way out, and a retry that had to
    // re-read them would silently retry nothing.
    S.lastGesture = { op: S.op, target: { ...t } };
    if (!api.postFeasibility) return _beatTwo(pin, t, t0, null);   // degrade: skip beat one
    return api.postFeasibility(scheduleId, { ...pin, budget_s: feel.sandbox.feasibility_budget_s })
      .then((ghost) => {
        S.dropToGhostMs = +(performance.now() - t0).toFixed(2);
        if (ghost === null) return _beatTwo(pin, t, t0, null);   // endpoint absent
        S.ghost = ghost;
        S.correlationId = ghost.correlation_id;
        const verdict = feasibilityVerdict(ghost);
        S.beatOne = verdict;
        if (verdict === "impossible") {
          // PROVEN impossible — a REFUSAL, and a refusal is a product answer
          // about the PLANT. Beat two has nothing to price. The card SAYS SO and
          // STAYS (`keepCard`): the bar snapping home with no card is exactly the
          // silence Session 4B.23 exists to end.
          markCarryGhost(false);
          card.showImpossible({ reason: ghost.message, beat: "one" });
          publishCard(null);
          return returnHome(ghost.message || "this placement isn't possible",
                            /*keepCard*/ true);
        }
        // POSSIBLE **and** UNDETERMINED both go on to pricing (Session 4B.23,
        // Item 5(b)). UNDETERMINED means the CHECK ran out of budget — it is a
        // statement about us, never about the plant — so refusing the gesture on
        // it would be asserting something we did not compute. Beat two is the
        // one that decides, and it is given the chance to.
        return _beatTwo(pin, t, t0, ghost);
      }).catch((e) => {
        if (e && e.superseded && handleSuperseded()) return;
        // Beat one FAILED (transport / server). Pricing anyway is right — beat
        // two is the authority — but it is no longer silent: the pending card
        // says the feasibility check did not answer.
        S.beatOne = "failed";
        S.beatOneError = failureCause(e);
        return _beatTwo(pin, t, t0, null);
      });
  }

  // "Try again" (Session 4B.23): re-run the LAST gesture's own pin. Offered only
  // where the failure was OURS — a beat that could not be completed, or beat
  // two's `no_verdict`. It replays the identical (op, resource, time); it never
  // re-derives a target, because a retry that quietly moved the bar somewhere
  // else would be a second gesture wearing the first one's label.
  function retryLastGesture() {
    const g = S.lastGesture;
    if (!g || !g.op || !g.target) return Promise.resolve(null);
    card.hide(); clearCard();
    return dropAtGesture(g.op, g.target.resource_id, g.target.time_ms);
  }

  function dropAtGesture(opRef, resourceId, timeMs) {
    grab(opRef);
    dragTo(resourceId, timeMs, /*altKey*/ true);
    return drop();
  }

  // Beat one's THREE states (Session 4B.23). The server sends `verdict`
  // explicitly; an OLDER server sends only `feasible` + `status`, and the status
  // is what distinguishes the two false cases — so the fallback reads THAT and
  // never collapses UNKNOWN into "impossible". `feasible` alone is not enough to
  // author a sentence about the plant, on either side of the wire.
  function feasibilityVerdict(ghost) {
    if (ghost.verdict === "possible" || ghost.verdict === "impossible"
        || ghost.verdict === "undetermined") return ghost.verdict;
    if (ghost.feasible) return "possible";
    return ghost.status === "INFEASIBLE" ? "impossible" : "undetermined";
  }

  // A transport/server failure, mapped to an AUTHORED planner sentence. No raw
  // error string ever reaches a planner surface (the "Failed to fetch" that once
  // surfaced as a chat turn); the raw text is kept on `state()` and the console
  // for whoever is debugging, which is not the planner.
  function failureCause(e) {
    const raw = String((e && e.message) || e || "");
    const status = e && e.status;
    let what;
    if (status >= 500) what = "the scheduler hit an error while working on it";
    else if (status >= 400) what = "the scheduler turned the request down";
    else what = "the connection to the scheduler dropped";
    try { console.warn("[sandbox]", raw); } catch { /* no console */ }
    return { what, technical: raw, status: status || null };
  }

  function _beatTwo(pin, t, t0, ghost) {
    // BEAT TWO — the priced re-solve. Show the countdown for the (longer) budget,
    // carrying forward what beat one did or did not manage to say.
    card.showPending(feel.sandbox.budget_s, feel.sandbox.countdown_tick_ms,
                     { beatOne: S.beatOne, beatOneError: S.beatOneError });
    const pin2 = { ...pin, budget_s: feel.sandbox.budget_s,
                   correlation_id: S.correlationId || undefined };
    return api.postSandbox(scheduleId, pin2).then((result) => {
      S.dropToVerdictMs = +(performance.now() - t0).toFixed(2);
      applyResultTwoBeat(result, ghost);
      return result;
    }).catch((e) => {
      if (e && e.superseded && handleSuperseded()) return;
      markCarryGhost(false);
      // A FAILURE, not a refusal: we could not PRICE this move. The plant said
      // nothing at all, so nothing may be claimed on its behalf. The card names
      // WHICH beat failed and offers a retry — and it STAYS while the bar goes
      // home, because a bar returning with no card is indistinguishable from a
      // refusal, a timeout and a crash.
      const cause = failureCause(e);
      S.failure = { beat: "two", ...cause };
      card.showFailure({ beat: "two", ...cause });
      publishCard(null);
      return returnHome("beat two could not price this placement",
                        /*keepCard*/ true);
    });
  }

  // The carry bar's ghost register during beat one (R-T2(2)): the "not yet real"
  // look, distinct from the tentative-committed style. Consumes the R-M1 ghost
  // fade timing tokens.
  function markCarryGhost(on) {
    const bar = layers.tentative.querySelector(".carry-bar");
    if (bar) bar.classList.toggle("pricing-ghost", !!on);
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
      publishCard(S.result);              // CU2: the consequences landed — resend
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
      publishCard(result);                // CU2: a refusal is card content too
      return returnHome(result.message, /*keepCard*/ true);
    }
    S.phase = "verdict";
    renderCarry();                        // tentative bar stays put (R-DP1)
    S.traces = renderTraces(layers.traces, svg, result.moves || [], durationMinOf, geometry, board.getWindow());
    card.showResult(result, { nameOf, woOf });
    publishCard(result);
  }

  // BEAT TWO applied over BEAT ONE (R-T2). The priced result SUPERSEDES the
  // feasibility ghost visibly; a CONTRADICTION (beat two infeasible, or the same
  // op materially relocated) is SHOWN via R-M1 semantics (R-T2(4)), never
  // silently reconciled.
  function applyResultTwoBeat(result, ghost) {
    S.result = result;
    markCarryGhost(false);
    const verdict = ghost ? beatTwoContradicts(ghost, result) : { infeasible: false, moved: false };
    S.contradiction = verdict.infeasible || verdict.moved
      ? { infeasible: verdict.infeasible, moved: verdict.moved } : null;

    const returnHome_ = result.outcome === "no_verdict" || !result.feasible;
    if (returnHome_) {
      // CONTRADICTION (infeasible): beat one said possible, beat two proved not —
      // SHOW it as an R-M1 rejection with the reason (R-T2(4)).
      card.showResult(result, { nameOf, woOf });
      publishCard(result);                // CU2: a refusal is card content too
      return returnHome(result.message, /*keepCard*/ true);
    }

    S.phase = "verdict";
    // CONTRADICTION (moved): the ghost showed one placement, beat two settled the
    // op materially elsewhere → the ghost VISIBLY RELOCATES before the card lands.
    const relocate = verdict.moved;
    const land = () => {
      renderCarry();                      // tentative bar stays at the pin (R-DP1)
      S.traces = renderTraces(layers.traces, svg, result.moves || [], durationMinOf, geometry, board.getWindow());
      // R-T2(3): the priced card SUPERSEDES the ghost — a perceivable transition.
      card.showResult(result, { nameOf, woOf },
                      { detailOpen: feel.sandbox.detail_open, superseded: true });
      publishCard(result);
    };
    if (relocate && !reduceMotion()) {
      const bar = layers.tentative.querySelector(".carry-bar");
      if (bar) {
        bar.classList.add("relocating");
        setTimeout(() => { if (bar.isConnected) bar.classList.remove("relocating"); land(); },
                   feel.sandbox.supersede_ms || 260);
        return;
      }
    }
    land();
  }

  // R-T2(4) detector — the JS mirror of sandbox.beat_two_contradicts. Beat two
  // contradicts beat one when it proves the placement infeasible (beat one
  // relaxed the committed work) OR places the SAME op materially elsewhere.
  function beatTwoContradicts(ghost, result) {
    const gFeasible = !!ghost.feasible;
    const rFeasible = !!result.feasible && result.outcome !== "no_verdict";
    const infeasible = gFeasible && !rFeasible;
    let moved = false;
    if (gFeasible && rFeasible) {
      const gPin = (ghost.placement || []).find((p) => p.pinned);
      const rPin = result.pin || {};
      if (gPin) {
        const sameRes = gPin.resource_id === rPin.resource_id;
        const shift = (gPin.start && rPin.start)
          ? Math.abs(ms(rPin.start) - ms(gPin.start)) / MIN : 0;
        moved = !sameRes || shift >= 1;
      }
    }
    return { infeasible, moved, contradicts: infeasible || moved };
  }

  // R-T2 "ask why" affordance (CU2): hand a SECOND-ORDER question (alternatives /
  // causal depth) off to the conversational layer WITH the sandbox context. The
  // interpreter/explainer reads a persisted snapshot, not this live sandbox
  // context (the 4B.3a R-AI1 rolling-explainer debt — see docs/04), so until that
  // connector lands the affordance ships but routes to a graceful NAMED-DEBT
  // response rather than a broken hand-off. The context is stashed on the hook so
  // a future conversational bridge can consume it without re-deriving anything.
  function askWhy(result) {
    const ctx = {
      operation_ref: result?.pin?.operation_ref || S.op,
      correlation_id: result?.correlation_id || S.correlationId,
      dominant_driver: result?.dominant_driver || null,
      cost_delta_abs: result?.cost_delta_abs ?? null,
    };
    S.askWhyContext = ctx;
    // Session 4B.3c CU4: the conversational bridge is wired (the R-AI1
    // rolling-explainer connector is retired). If the host handled the ask
    // (returned truthy), we're done; otherwise fall through to the tip.
    if (opts.onAskWhy && opts.onAskWhy(ctx)) return ctx;
    // Fallback when no bridge is available (or it couldn't compose a question):
    // point the planner at the ask panel — the answer lives there now.
    reasonTip.textContent =
      "Ask “why is this on this machine?” in the panel — the conversational "
      + "layer answers it, grounded in this run's evidence.";
    reasonTip.classList.remove("hidden");
    setTimeout(() => reasonTip.classList.add("hidden"), 4200);
    return ctx;
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
      if (!keepCard) { card.hide(); clearCard(); }
      clearOverlays();
      S.phase = "idle"; S.op = null; S.tier0 = null; S.target = null;
    }, snapMs + shakeMs + 30);
    return { returned: true, reason };
  }

  // "SEARCH DEEPER" (Session 4B.24, R-T2 amendment clause 5) — THE INCUMBENT IS
  // AUDITED, NOT ENSHRINED. A deliberate act, off the gesture path, that runs the
  // deterministic seeded search at a real budget and reports what it found. It
  // applies nothing: an improvement is an OFFER with its own affected list and
  // its own accept (clause 4).
  //
  // It is deliberately slow — measured at 40 to 77 seconds per deterministic unit
  // on a 386-bar board — and that is the reason it is a button rather than
  // something every drag silently pays for.
  function searchDeeper(opts = {}) {
    if (!api.postAudit) return Promise.resolve(null);
    S.audit = { running: true, result: null, error: null };
    card.showSearching(opts.searchDeeperScale || null);
    return api.postAudit(scheduleId, opts).then((res) => {
      S.audit = { running: false, result: res, error: null };
      card.showAudit(res);
      return res;
    }).catch((e) => {
      // A failure of OURS. It says nothing about whether the plan can be
      // improved, and the copy must not let it be read as "the incumbent held".
      const cause = failureCause(e);
      S.audit = { running: false, result: null, error: cause };
      card.showAudit({ searched: false, sentence:
        `I could not run a deeper search — ${cause.what}. That says nothing `
        + `about whether this plan can be improved.` });
      return null;
    });
  }

  // Clause (4): ACCEPTING IS TWO CEREMONIES. This one commits the SEARCH's
  // schedule — work the planner never gestured at — and it is reachable only from
  // the audit's own offer. `accept()` below commits the planner's move and can
  // never reach this.
  function acceptSearch(opts = {}) {
    const found = S.audit && S.audit.result && S.audit.result.offer;
    if (!found || !api.postAuditAccept || !api.getSchedule) {
      return Promise.resolve(null);
    }
    // R-BK1: the audit is a PORTFOLIO, so the accept must re-solve at the seed
    // that WON — accepting an offer found by seed 44 while re-solving at the
    // portfolio's seed0 would mint a schedule that is not the one on the card.
    // `expect_delta_abs` hands the promise back so the server can prove the two
    // are the same object, to the cent, or refuse.
    const promise = { seed: found.seed, expect_delta_abs: found.delta_abs };
    return api.postAuditAccept(scheduleId, { ...promise, ...opts, authority })
      .then((res) => api.getSchedule(res.schedule_id).then((newDoc) => {
        board.rebind(newDoc, { motion: feel.motion });
        return rebindController(res.schedule_id, newDoc).then(() => {
          S.audit = { running: false, result: null, error: null };
          card.showAuditAccepted(res);
          return res;
        });
      }));
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
          clearCard();           // CU2: accepted — the priced proposal is gone
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
    clearCard();                 // CU2: dismissed — nothing to read back
    clearOverlays();
    if (board.clearMotionClasses) board.clearMotionClasses();  // clear a prior pin-lock (R-M1c)
    S.phase = "idle"; S.op = null; S.tier0 = null; S.target = null;
    S.result = null; S.traces = [];
    S.beatOne = null; S.beatOneError = null; S.failure = null;
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
    noopTip.classList.add("hidden");
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
  // R-DP9 — IS THIS DROP THE PLACEMENT IT ALREADY HAS?
  //
  // SESSION 4B.28 ITEM 4(b): THE TOLERANCE WAS SCALED BY THE ZOOM AND IT ATE
  // REAL MOVES. It read `grid_px * pxToMinutes(1)`, which is 8 PIXELS expressed
  // in minutes — about 240 minutes at the default 30-day view. So a deliberate
  // four-hour drag on a fully zoomed-out board was classified as "already here",
  // settled home, and priced nothing. 4B.23 lost three verification gestures to
  // exactly that, and to a planner it is indistinguishable from the silent-pan
  // defect Item 4(a) fixes.
  //
  // THE TOLERANCE IS FOR CLICK JITTER, NOT FOR INTENT. Jitter is a property of
  // the hand and the mouse; it does not get larger because the board is zoomed
  // out. So it is a FIXED constant in WORKING MINUTES (`feel.snap.noop_tol_min`)
  // and the zoom cannot touch it. A planner who nudges a bar by fifteen minutes
  // at any zoom now gets a price, which is the whole point of the gesture.
  function noOpToleranceMin() {
    const tol = feel.snap && feel.snap.noop_tol_min;
    return typeof tol === "number" && tol >= 0 ? tol : 5;
  }
  function isNoOpDrop(t) {
    const inc = incumbentOf(S.op);
    if (!inc || t.resource_id !== inc.resource_id) return false;
    return Math.abs(t.time_ms - inc.start_ms) / MIN <= noOpToleranceMin();
  }

  // Settle the carry gently home (no reject-shake — this is "already here", not a
  // refusal) and show the cue. NO card, NO sandbox, NO Decision (R-DP9).
  function noOpReturn() {
    reasonTip.classList.add("hidden");
    S.lastDropWasNoop = true;
    const reduce = reduceMotion();
    const snapMs = reduce ? 0 : (feel.motion?.reject_dur_ms ?? 200);
    const inc = incumbentOf(S.op);
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
      }
    }
    // Item 4(b), second half: A NO-OP SAYS SO. 4B.23 made "nothing on this board
    // reverts in silence" the law for failures; a drop that changed nothing is
    // the same promise on a quieter register. It stays a TIP and not a card
    // because R-DP9 rules this calmer than a refusal — no shake, no card — and
    // the tolerance is now small enough that only real jitter reaches it.
    showNoOp(`that's where it already sits — within ${noOpToleranceMin()} `
             + "minutes of its current start, so there is nothing to price");
    setTimeout(() => {
      root.classList.remove("active", "refusing", "returning");
      clearOverlays();
      S.phase = "idle"; S.op = null; S.tier0 = null; S.target = null;
    }, snapMs + 30);
    return { returned: true, noop: true, reason: "already here" };
  }

  function showNoOp(text) {
    noopTip.textContent = text || "already here — nothing to change";
    noopTip.classList.remove("hidden");
    setTimeout(() => noopTip.classList.add("hidden"), 2400);
  }

  // Item 4(a): the chunked decline. A card, so it is impossible to miss, and it
  // STAYS while the bar goes home (`keepCard`) — 4B.23's law: a bar returning
  // with no card is indistinguishable from a refusal, a timeout and a crash.
  function declineChunked(t) {
    const n = chunkCountOf(S.op);
    const machine = nameOf(t.resource_id);
    S.lastDropWasDeclined = "chunked";
    card.showDeclined({
      what: `${woOf(S.op) || "this operation"} runs in ${n} pieces on ${machine} `
          + "around calendar closures, and I can't re-place split work as one "
          + "move yet — the pauses are placements the solver made, and shifting "
          + "the bar wouldn't tell me where the new ones go.",
      limit: "That is a limit of mine, not a ruling about your plant: I am not "
           + "telling you the move is impossible, I am telling you I can't "
           + "price it.",
    });
    publishCard(null);
    return returnHome("a split operation cannot be priced as one move",
                      /*keepCard*/ true);
  }

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
    // Item 4(a): resolve a CHUNK PIECE to its assignment. Item 4(c): the op
    // comes from the item under the POINTER and from nothing else — never from
    // the board's current selection, which may be a different bar entirely.
    const hit = itemId == null ? null : asgByItem.get(itemId);
    if (!hit) return;                                     // not a bar
    down = { x: ev.clientX, y: ev.clientY, op: hit.operation_ref, moved: false };
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
    searchDeeper, acceptSearch,
    scheduleId: () => scheduleId,
    // programmatic drop straight to a target (harness convenience): grab, drag
    // to the target, drop — the full path, no pointer math.
    dropAt(opRef, resourceId, startIso, altKey = false) {
      grab(opRef);
      dragTo(resourceId, ms(startIso), altKey);
      return drop();
    },
    retry: () => retryLastGesture(),   // Session 4B.23: the harness's retry seam
    // probes for the screenshot harness / standing regressions
    state: () => ({
      phase: S.phase, op: S.op, acceptedId: S.acceptedId || null,
      noop: S.lastDropWasNoop || false,   // R-DP9 (CU2): the last drop was a no-op
      // Session 4B.28 Item 4: the no-op tolerance ACTUALLY IN FORCE (minutes,
      // zoom-independent since 4(b)) and whether the last drop was DECLINED for
      // a limit of ours rather than refused by the plant. Both are read by the
      // harness, and the tolerance is exposed because the defect it replaces was
      // invisible precisely because nothing reported the number.
      noopToleranceMin: noOpToleranceMin(),
      declined: S.lastDropWasDeclined || null,
      chunked: S.op ? isChunked(S.op) : null,
      grabToShadeMs: S.grabToShadeMs, dropToVerdictMs: S.dropToVerdictMs,
      acceptToDoneMs: S.acceptToDoneMs || null,
      priceToGhostsMs: (S.priceToGhostsMs || {})[S.op] || null,
      target: S.target && { ...S.target },
      ghosts: S.drawnGhosts.map((g) => ({ source: g.source, resource_id: g.resource_id, label: g.label || null, delta_pct: g.delta_pct })),
      result: S.result && {
        outcome: S.result.outcome, delta_pct: S.result.delta_pct,
        moves: (S.result.moves || []).length,
        // CU1 (Session 4B.5): the priced total and its attribution, so the
        // harness can assert that the two DRAWN parts sum to the headline
        // (decomposition-sums, read off the rendered card).
        cost_delta_abs: S.result.cost_delta_abs ?? null,
        attribution: S.result.attribution || "unavailable",
        reopt_delta_abs: S.result.reopt_delta_abs ?? null,
        move_delta_abs: S.result.move_delta_abs ?? null,
      },
      traces: S.traces.length,
      // R-T2 two-beat (Session 4B.3b): the beat-one ghost + correlation + any
      // beat-two contradiction, for the harness to assert the two beats.
      correlationId: S.correlationId || null,
      dropToGhostMs: S.dropToGhostMs,
      feasibilityGhost: S.ghost && {
        feasible: !!S.ghost.feasible, correlation_id: S.ghost.correlation_id,
        placement: (S.ghost.placement || []).length,
        // Session 4B.23: the THREE-state verdict, resolved the way the branch
        // resolved it (server field, else derived from `status`).
        verdict: feasibilityVerdict(S.ghost), status: S.ghost.status || null,
      },
      contradiction: S.contradiction,
      askWhyContext: S.askWhyContext,
      // Session 4B.23: what beat one managed to say, and — when a beat could not
      // be completed at all — the failure the planner was shown. `technical` is
      // the raw string; it lives HERE and in the console, never on the card.
      beatOne: S.beatOne,
      failure: S.failure && { ...S.failure },
      // Session 4B.23 Item 4: is a delta card on screen? A refusal / failure /
      // no-verdict card OUTLIVES the gesture (phase goes back to idle while the
      // card stays), so "phase !== idle" is no longer the whole answer to "is
      // there uncommitted state here". Read from the DOM, so it cannot drift
      // from what the planner is actually looking at.
      cardOpen: !!(card.el && !card.el.classList.contains("hidden")),
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

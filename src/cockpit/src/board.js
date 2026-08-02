// The board (CU3): a READ-ONLY vis-timeline over a contract-1.2 schedule
// document. Resources are rows, assignments are bars in the planner's own
// vocabulary (external_name / work_orders — never canonical UUIDs on screen),
// bars are colored by the lateness signal of their DEMAND (per-Demand, never
// per-WorkPackage), calendar closures are shaded, and there are NO drag
// handlers (editable:false everywhere) — read-only is the law until interim-B.
//
// It exposes an imperative surface the ask panel drives (CU4):
//   highlight(citedRefs)  glow the cited bars + lanes; clear on empty
//   select(operationRef)   the shared selection (a clicked bar)
//   onSelect(cb)           fired when a bar is clicked → deictic ask scope
// plus a tiny harness hook (window.__cockpit) for the Playwright screenshots.
import { Timeline } from "vis-timeline/standalone";
import { DataSet } from "vis-data";
import "vis-timeline/styles/vis-timeline-graph2d.min.css";
import { capacityBands, shiftBoundaries } from "../legality/capacity.js";
import { rowUtilization } from "../legality/rowstats.js";
import { createMarkers } from "./markers.js";
import { createHoverCards } from "./hovercards.js";

const ms = (iso) => new Date(iso).getTime();
const MIN_MS = 60000;

// Lateness bands (minutes). Colors live in tokens.css; only the NUMERIC
// thresholds are here (feel-iteration tunes the hue via tokens, the band via
// this one const). lateness_min > 0 is past due; the tight band is "early, but
// inside one working day of the due date".
const BANDS = { tightMin: -1440 };
function latenessBand(latenessMin) {
  if (latenessMin == null) return "ontime";
  if (latenessMin > 0) return "late";
  if (latenessMin > BANDS.tightMin) return "tight";
  return "ontime";
}

export function createBoard(hostEl, initialDoc, boardOpts = {}) {
  // ``doc`` is mutable: an accepted edit REBINDS the board to the new schedule
  // version (rebind() below), with bars animating to their new positions rather
  // than a destroy/recreate (R-DP7 legible settle). Every closure reads the
  // live ``doc``.
  let doc = initialDoc;
  // --- planner-vocabulary lookups --------------------------------------
  const resById = new Map(doc.resources.map((r) => [r.resource_id, r]));
  const nameOf = (rid) => resById.get(rid)?.external_name || rid.slice(0, 8);
  // per-Demand lateness, keyed by the external work_order the bars carry.
  const latenessByWO = new Map();
  const demandToWO = new Map();
  function rebuildDemandLookups() {
    latenessByWO.clear();
    demandToWO.clear();
    for (const so of doc.service_outcomes || []) {
      if (so.work_order != null) latenessByWO.set(so.work_order, so.lateness_min);
      if (so.demand_ref) demandToWO.set(so.demand_ref, so.work_order);
    }
  }
  rebuildDemandLookups();

  // --- groups (rows) in document order, each carrying a row-label strip -
  // (CU4): utilization over the VISIBLE window (recomputed live on pan/zoom),
  // booked-through, and next-open-gap. The absolute two come from the document
  // (server-computed via row_intelligence over the solver's own windows); util
  // is recomputed client-side from the SAME arithmetic (rowstats.js), never DOM.
  const fmtClock = (iso) => (iso == null ? "—" : new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
  }));
  // vis-timeline renders a group's `content` as HTML only when it's a DOM node
  // (a string is escaped to text), so the strip is built as an element.
  function rowStripEl(r, utilPct) {
    const util = utilPct == null ? "—" : `${Math.round(utilPct * 100)}%`;
    const bt = r.booked_through ? fmtClock(r.booked_through) : "—";
    const gap = r.next_open_gap ? fmtClock(r.next_open_gap) : "—";
    const utilCls = utilPct == null ? "" : utilPct >= 0.85 ? "hot" : utilPct >= 0.5 ? "warm" : "cool";
    const el = document.createElement("div");
    el.innerHTML =
      `<div class="row-name"></div>`
      + `<div class="row-strip">`
      + `<span class="rs-util ${utilCls}" title="utilization over the visible window">${util}</span>`
      + `<span class="rs-sep">·</span>`
      + `<span class="rs-booked" title="booked through">▉ ${bt}</span>`
      + `<span class="rs-gap" title="next open gap">◷ ${gap}</span>`
      + `</div>`;
    el.querySelector(".row-name").textContent = nameOf(r.resource_id);
    return el;
  }
  const groups = new DataSet(
    doc.resources.map((r, i) => ({ id: r.resource_id, content: rowStripEl(r, null), order: i })),
  );

  // --- bars + calendar backgrounds -------------------------------------
  const opToItem = new Map();   // operation_ref -> item id (first piece for splits)
  const itemToOp = new Map();   // the inverse, kept in step by addAssignmentItems
  const woToItems = new Map();  // work_order    -> [item id,...]
  const items = new DataSet();
  const occByRes = new Map();   // resource_id -> [{start,end} ms] (CU1/CU4 occupancy)
  const splitPieceToAssignment = new Map();  // piece item id -> assignment (splits)

  // Setup segment (CU5): the fraction of a bar the setup phase occupies, exposed
  // as an inline CSS var so the bar renders a distinct leading setup portion —
  // the first visual appearance of setup on the board.
  function setupFrac(a, s, e) {
    const su = a.phases && a.phases.setup;
    if (!su || e <= s) return 0;
    const f = (ms(su.end) - s) / (e - s);
    return Math.max(0, Math.min(1, f));
  }
  function barStyle(a, s, e) {
    const f = setupFrac(a, s, e);
    return f > 0 ? `--setup-frac:${f.toFixed(4)};` : "";
  }
  function barTitle(a, label) {
    return `${label} · ${nameOf(a.resource_id)} · op ${a.op_seq}`
      + (a.standing_pin ? " · committed (accepted edit)" : "")
      + ((a.chunks || []).length > 1 ? ` · ${a.chunks.length} pieces (split)` : "");
  }

  // OCCUPANCY IS PER CHUNK, NEVER THE MERGED SPAN (Session 4B.20, the
  // merged-span ruling). This used to push one interval per assignment,
  // chunks[0].start -> chunks[last].end, which on a split operation claims the
  // machine is busy through its pauses. It fed two surfaces: the row-strip
  // utilization % and the open-idle capacity bands.
  //
  // MEASURED, NOT ASSUMED: on the pinned world this changed NOTHING — every
  // pause there falls wholly inside a closure, so intersecting the span with
  // the open windows (rowstats.js) recovered the working minutes exactly
  // (CUT-01: 5981 either way). The board was RIGHT, and right by a property of
  // the data that nothing enforces. A pause that straddles open time — a
  // min_chunk split mid-shift, a preemption — would have inflated the strip
  // and hidden real idle capacity from the bands. Per-chunk occupancy makes it
  // right by construction instead.
  function pushOccupancy(resourceId, chunks) {
    const list = occByRes.get(resourceId);
    for (const c of chunks) list.push({ start: ms(c.start), end: ms(c.end) });
  }

  // THE ONE PLACE A BAR IS BUILT (Session 4B.28).
  //
  // This used to exist TWICE: once here for the first render and once inside
  // rebind(), which only ever knew about single-chunk bars. 4B.20 made a chunked
  // operation render as one item PER CHUNK (`<id>~c0`, `~c1`, …) and rebind was
  // not taught — so an accepted edit on a board with any split operation called
  // `items.update({id: assignment_id, …})` against an id that is not an item,
  // which vis-data INSERTS. The result was a phantom merged bar spanning the
  // pauses, sitting on top of the pieces that were still there. One builder, one
  // remover, and the shape of the rebuild is the same shape as the build.
  function itemIdsFor(assignmentId, chunkCount) {
    if (chunkCount <= 1) return [assignmentId];
    const out = [];
    for (let i = 0; i < chunkCount; i += 1) {
      out.push(`${assignmentId}~c${i}`);
      if (i > 0) out.push(`${assignmentId}~link${i}`);
    }
    return out;
  }

  function removeAssignmentItems(assignmentId) {
    // Remove by PREFIX rather than by a remembered chunk count: the count may
    // have changed (a re-solve can re-chunk), and a stale piece left behind is
    // exactly the phantom this function exists to prevent.
    const doomed = [];
    for (const it of items.get()) {
      const id = String(it.id);
      if (id === assignmentId || id.startsWith(`${assignmentId}~`)) doomed.push(it.id);
    }
    if (doomed.length) items.remove(doomed);
    for (const [pieceId] of [...splitPieceToAssignment]) {
      if (String(pieceId).startsWith(`${assignmentId}~`)) {
        splitPieceToAssignment.delete(pieceId);
      }
    }
  }

  // Build (or rebuild) every item for one assignment and register its lookups.
  // `extraCls` carries the transient R-M1 motion classes a rebind adds.
  function addAssignmentItems(a, extraCls = "") {
    const chunks = a.chunks || [];
    if (!chunks.length) return;
    const s = ms(chunks[0].start);
    const e = ms(chunks[chunks.length - 1].end);
    const wos = a.work_orders || [];
    const { band, label } = barVisual(a);
    // R-DP8 CU2 + CU5: the pin/lock indicator family — a standing commitment (an
    // accepted, still-held pin, or a THAWED one since 4B.28) wears the persistent
    // marker; siblings in the family (transient pin-lock, reflow) come in via
    // `extraCls`.
    const pinCls = a.standing_pin ? " standing-pin" : "";
    // Session 4B.3a CU2: a rolling bar's commitment_state — a COMMITTED (frozen-
    // front) bar is static/locked (R-M1 committed-drop semantics), an
    // ACTIVE_WINDOW bar renders as today's normal bar. None on a monolithic bar.
    // R-F1: this is what makes a thaw VISIBLE — the bar restyles from committed
    // to pinned in the same repaint that changes who holds it.
    const commitCls = a.commitment_state === "committed" ? " committed"
      : a.commitment_state === "active_window" ? " active-window" : "";
    const suffix = `${pinCls}${commitCls}${extraCls ? ` ${extraCls}` : ""}`;

    if (chunks.length <= 1) {
      // the common case: ONE range item, id = assignment_id (identity preserved).
      items.add({
        id: a.assignment_id, group: a.resource_id, start: s, end: e,
        type: "range", className: `bar late-${band}${suffix}`, editable: false,
        style: barStyle(a, s, e), content: label, title: barTitle(a, label),
      });
      opToItem.set(a.operation_ref, a.assignment_id);
      itemToOp.set(a.assignment_id, a.operation_ref);
      for (const w of wos) {
        if (!woToItems.has(w)) woToItems.set(w, []);
        woToItems.get(w).push(a.assignment_id);
      }
      return;
    }
    // split/chunked op (CU5): one piece per chunk, visually linked as ONE job
    // (kinship styling + a dashed connector across each pause). The first
    // piece anchors the op for citation/selection; every piece maps back to
    // the op so a click on any piece scopes the whole job.
    const firstId = `${a.assignment_id}~c0`;
    opToItem.set(a.operation_ref, firstId);
    itemToOp.set(firstId, a.operation_ref);
    chunks.forEach((c, i) => {
      const cs = ms(c.start), ce = ms(c.end);
      const edge = i === 0 ? "chunk-first" : i === chunks.length - 1 ? "chunk-last" : "chunk-mid";
      const pieceId = `${a.assignment_id}~c${i}`;
      items.add({
        id: pieceId, group: a.resource_id, start: cs, end: ce,
        type: "range",
        className: `bar late-${band}${suffix} chunk-piece ${edge}`, editable: false,
        style: i === 0 ? barStyle(a, cs, ce) : "",
        content: i === 0 ? label : "", title: barTitle(a, label),
      });
      splitPieceToAssignment.set(pieceId, a);
      for (const w of wos) {
        if (!woToItems.has(w)) woToItems.set(w, []);
        woToItems.get(w).push(pieceId);
      }
      // dashed kinship connector across the pause before this piece.
      if (i > 0) {
        const prevEnd = ms(chunks[i - 1].end);
        if (cs > prevEnd) {
          items.add({
            id: `${a.assignment_id}~link${i}`, group: a.resource_id,
            type: "background", start: prevEnd, end: cs, className: "chunk-link",
          });
        }
      }
    });
  }

  let minT = Infinity, maxT = -Infinity;
  for (const a of doc.assignments) {
    const chunks = a.chunks || [];
    if (!chunks.length) continue;
    minT = Math.min(minT, ms(chunks[0].start));
    maxT = Math.max(maxT, ms(chunks[chunks.length - 1].end));
    if (!occByRes.has(a.resource_id)) occByRes.set(a.resource_id, []);
    pushOccupancy(a.resource_id, chunks);
    addAssignmentItems(a);
  }

  const pad = 6 * 3600000;
  const win = { start: minT - pad, end: maxT + pad };
  const bandSpan = { start: minT, end: maxT };

  // --- capacity-state backgrounds (CU1) --------------------------------
  // Per-row banding for off-shift / closure / planned-maintenance / overtime /
  // open-idle, computed over the DATA span from the row's flattened calendar
  // windows + occupancy (capacity.js). Rendered as vis background items so they
  // track pan/zoom natively. Booked regular time is NOT banded — the bar covers
  // it. (Unplanned/observed downtime is deliberately absent — no doorway yet.)
  const capIds = [];
  function renderCapacityBands() {
    if (capIds.length) { items.remove(capIds); capIds.length = 0; }
    for (const r of doc.resources) {
      const occ = occByRes.get(r.resource_id) || [];
      for (const [bi, b] of capacityBands(r.calendar_windows, occ, bandSpan).entries()) {
        if (b.end <= bandSpan.start || b.start >= bandSpan.end) continue;
        const id = `cap-${r.resource_id}-${bi}`;
        items.add({
          id, group: r.resource_id, type: "background",
          start: b.start, end: b.end, className: `cap-${b.kind}`,
        });
        capIds.push(id);
      }
    }
  }
  renderCapacityBands();

  // --- the timeline (read-only) ----------------------------------------
  const timeline = new Timeline(hostEl, items, groups, {
    stack: false,
    editable: false,              // READ-ONLY — no drag handlers (interim-A law)
    selectable: true,
    zoomable: true, moveable: true,
    zoomMin: 4 * 3600000,
    min: win.start - 24 * 3600000, max: win.end + 24 * 3600000,
    // NB: the initial window is set via setWindow() below, NOT as start/end
    // options. vis defers revealing the root (visibility:hidden) until an
    // initial range-change completes when start/end are given as options; for a
    // static window that range-change never fires and the board stays blank.
    groupOrder: (a, b) => a.order - b.order,
    orientation: { axis: "top" },
    margin: { item: 4, axis: 6 },
    format: {
      minorLabels: { hour: "HH:mm", weekday: "ddd D" },
      majorLabels: { hour: "ddd D MMM", day: "MMM YYYY" },
    },
  });

  // set the initial window explicitly (see the start/end note above) and
  // redraw once layout has settled so the overlay tracks the painted geometry.
  timeline.setWindow(win.start, win.end, { animation: false });

  // --- time-anchor markers + shift ticks (CU2/CU1) ---------------------
  // Session 4B.28 Item 1(a): the frozen boundary is a real handle when — and
  // only when — a host installed a mover. A read-only deep link, a superseded
  // version and a monolithic board all pass nothing and get the 4B.3a marker
  // exactly as it was.
  const markers = createMarkers(timeline, {
    onBoundaryMove: boardOpts.onBoundaryMove || null,
    // The board must be perfectly still under a boundary drag for the same
    // reason it is under a bar drag (3.2c): vis's own Hammer pan would slide the
    // axis out from under the handle being dragged along it.
    onDragStart: () => setPanZoom(false),
    onDragEnd: () => setPanZoom(true),
  });
  // now-line from the run's reference date (the 3.3b epoch) — never wall clock;
  // absent when the run is "now"-anchored (reference_date null).
  markers.setNow(doc.reference_date || null);
  // Session 4B.3a CU2: the rolling frozen-front boundary — a labeled vertical
  // marker at the frozen_until timestamp; work left of it is committed/locked.
  markers.setFrozen(doc.rolling ? doc.rolling.frozen_until : null);
  // shift boundaries: the union of every row's regular shift edges in span.
  function refreshShiftTicks() {
    const set = new Set();
    for (const r of doc.resources)
      for (const t of shiftBoundaries(r.calendar_windows, bandSpan.start, bandSpan.end)) set.add(t);
    markers.setShiftBoundaries([...set].sort((a, b) => a - b));
  }
  refreshShiftTicks();

  // --- row-label strip: live utilization over the visible window (CU4) --
  // Booked-through + next-gap are server-computed (document); utilization is the
  // one window-relative number, recomputed here from the SAME arithmetic
  // (rowstats.js) over the visible window — never off the DOM.
  const openWinsByRes = new Map();
  for (const r of doc.resources) {
    const open = [];
    for (const w of r.calendar_windows || [])
      if (w.kind === "regular" || w.kind === "overtime") open.push([ms(w.start), ms(w.end)]);
    openWinsByRes.set(r.resource_id, open);
  }
  // ---------------------------------------------------------------------
  // DOWNTIME COMPRESSION (Session 4B.28 Item 2(b)).
  //
  // At demo density the board is mostly night. Nights, weekends and plant
  // closures occupy the majority of the axis while carrying no work, so working
  // time — the thing a planner is reading — is squeezed into a fraction of the
  // pixels. Compression collapses spans where NOTHING CAN RUN so working time
  // dominates the view.
  //
  // MECHANISM CHOSEN: vis-timeline's own `hiddenDates`, NOT a custom scale.
  //
  // The requirement that decided it is the drop mapping. Every pixel↔instant
  // conversion in this cockpit goes through `timeline.body.util.toScreen` /
  // `.toTime` (geometry.js is the ONE place that reads vis's layout), and vis's
  // DateUtil applies hidden ranges INSIDE those two functions. So R-DP9's
  // tolerance arithmetic, 4B.23's time mapping and the drag's pin all stay exact
  // under compression for free, with no second coordinate system to keep in
  // step. A custom scale would have meant re-deriving that mapping by hand — and
  // a drop that lands minutes off is a worse defect than an un-compressed board.
  //
  // WHAT IS COMPRESSED: only spans where EVERY row is closed. Hidden dates are a
  // property of the AXIS, not of a row, so compressing a span one machine is
  // working through would hide real work. The intersection is the only honest
  // set, and on this plant it is exactly the nights, weekends and plant-wide
  // closures the feature is about.
  const COMPRESS_MIN_SPAN_MIN = 120;   // shorter gaps are not worth a fold
  let compressed = false;
  let foldRanges = [];

  // Spans inside the data window where no row has an open (regular/overtime)
  // window. Computed from the SAME `openWinsByRes` the row strips measure
  // utilization against — one definition of "open", two consumers.
  function computeFoldRanges() {
    const open = [];
    for (const wins of openWinsByRes.values()) {
      for (const [s, e] of wins) {
        if (e > bandSpan.start && s < bandSpan.end) {
          open.push([Math.max(s, bandSpan.start), Math.min(e, bandSpan.end)]);
        }
      }
    }
    open.sort((a, b) => a[0] - b[0]);
    const merged = [];
    for (const iv of open) {
      const last = merged[merged.length - 1];
      if (last && iv[0] <= last[1]) last[1] = Math.max(last[1], iv[1]);
      else merged.push([iv[0], iv[1]]);
    }
    const out = [];
    let cursor = bandSpan.start;
    for (const [s, e] of merged) {
      if (s - cursor >= COMPRESS_MIN_SPAN_MIN * MIN_MS) out.push([cursor, s]);
      cursor = Math.max(cursor, e);
    }
    if (bandSpan.end - cursor >= COMPRESS_MIN_SPAN_MIN * MIN_MS) {
      out.push([cursor, bandSpan.end]);
    }
    return out;
  }

  function setCompressed(on) {
    const want = !!on;
    if (want === compressed) return compressed;
    if (want && !foldRanges.length) foldRanges = computeFoldRanges();
    compressed = want;
    timeline.setOptions({
      hiddenDates: compressed
        ? foldRanges.map(([s, e]) => ({ start: s, end: e }))
        : [],
    });
    hostEl.classList.toggle("compressed", compressed);
    // The fold marks are what stop a fold reading as adjacency: two bars either
    // side of a collapsed night are NOT neighbours, and with the span at zero
    // width nothing else on screen would say so.
    markers.setFolds(compressed ? foldRanges : []);
    requestAnimationFrame(() => {
      timeline.redraw(); renderOverlay(); markers.redraw(); refreshRowStrips();
    });
    try { localStorage.setItem("mre-compress", compressed ? "1" : "0"); }
    catch { /* private mode — the choice simply does not persist */ }
    return compressed;
  }

  function refreshRowStrips() {
    const w = timeline.getWindow();
    const lo = w.start.getTime(), hi = w.end.getTime();
    for (const r of doc.resources) {
      const occ = (occByRes.get(r.resource_id) || []).map((o) => [o.start, o.end]);
      const util = rowUtilization(openWinsByRes.get(r.resource_id) || [], occ, lo, hi);
      groups.update({ id: r.resource_id, content: rowStripEl(r, util) });
    }
  }
  timeline.on("rangechanged", refreshRowStrips);

  // Item 2(b): restore the planner's own linear/compressed choice BEFORE the
  // chrome paints its toggle, so the button never disagrees with the board for
  // a frame. LINEAR is the default: compression is a reading aid, and a board
  // that folded its own ruler before anyone asked would be showing a stranger a
  // scale they did not choose.
  try {
    if (localStorage.getItem("mre-compress") === "1") setCompressed(true);
  } catch { /* private mode — linear, which is the default anyway */ }

  requestAnimationFrame(() => {
    timeline.redraw(); renderOverlay(); markers.redraw(); refreshRowStrips();
  });

  // --- band index for the downtime hover (CU3) -------------------------
  const bandsByRes = new Map();
  function rebuildBandIndex() {
    bandsByRes.clear();
    for (const r of doc.resources)
      bandsByRes.set(r.resource_id, capacityBands(r.calendar_windows, occByRes.get(r.resource_id) || [], bandSpan));
  }
  rebuildBandIndex();
  function bandAt(resourceId, timeMs) {
    for (const b of bandsByRes.get(resourceId) || [])
      if (timeMs >= b.start && timeMs < b.end) return b;
    return null;
  }
  // minutes from a closure/off-shift band's end until the row's next open
  // (regular/overtime) window — "reopens in …". null when none in span.
  function reopenMinutes(resourceId, band) {
    const opens = (openWinsByRes.get(resourceId) || []).map(([s]) => s).filter((s) => s >= band.end).sort((a, b) => a - b);
    return opens.length ? Math.round((opens[0] - band.start) / MIN_MS) : null;
  }
  // Contract 1.12 (Session 4B.14 Item 4): the R-C3 interruptibility pair the
  // solver applied, straight off the assignment. Absent on a pre-1.12 document,
  // and the card simply omits the row rather than guessing a default — a card
  // that said "splittable: no" about an operation whose spec never said so
  // would be the same confident-wrong class this session is about.
  function opSpecFor(a) {
    if (!a || (a.splittable == null && a.min_chunk_min == null)) return null;
    return { splittable: a.splittable ?? null, min_chunk_min: a.min_chunk_min ?? null };
  }

  // job facts for a bar (or a split piece) → the job hover card.
  function jobFor(itemId) {
    const a = doc.assignments.find((x) => x.assignment_id === itemId)
      || splitPieceToAssignment.get(itemId);
    if (!a) return null;
    const wo = (a.work_orders || [])[0] || null;
    const so = doc.service_outcomes.find((s) => s.work_order === wo);
    const lateness = so ? so.lateness_min : null;
    const status = latenessBand(lateness);
    // Session 4A.3 CU5a: the tooltip carries the bar's own span + its lateness/slack
    // figure — the two facts a planner reads a bar for. Span from the chunks (a
    // split op's first-start → last-end).
    const chunks = a.chunks || [];
    const start = chunks.length ? chunks[0].start : null;
    const end = chunks.length ? chunks[chunks.length - 1].end : null;
    // Session 4B.14 Item 4 — RUN TIME AND ELAPSED SPAN, SEPARATELY.
    //
    // After 4B.13's chunk fix these genuinely differ: ORD-000011 is 1,501
    // working minutes across a 5,821-minute span, and that difference IS the
    // answer to half the "why is there a gap" questions. Conflating them is the
    // confusion the merged bar used to create, so they are two labelled facts
    // here and never one. Splittable / min_chunk travel with them because they
    // are what decides whether an operation can take a short window — the fact
    // that decided ORD-000013's op20, and that a planner previously had to
    // count pixels to confirm.
    const runMin = chunks.reduce((n, c) => n + (c.working_min || 0), 0) || null;
    const spanMin = (start != null && end != null)
      ? Math.round((end - start) / MIN_MS) : null;
    const op = opSpecFor(a);
    return {
      order: wo, qty: so?.quantity ?? null, uom: so?.quantity_uom ?? null,
      due: so?.due ?? null, customer: so?.customer_name ?? null,
      opSeq: a.op_seq, status, standingPin: !!a.standing_pin,
      resourceName: nameOf(a.resource_id),
      start, end, latenessMin: lateness,
      runMin, spanMin, chunkCount: chunks.length,
      splittable: op?.splittable ?? null, minChunkMin: op?.min_chunk_min ?? null,
    };
  }
  const hoverCards = createHoverCards(hostEl, timeline, {
    jobFor, bandAt, reopenMinutes, resourceName: nameOf,
  });

  // --- pan/zoom suppression (3.2c) -------------------------------------
  // vis owns a built-in Hammer pan/zoom on the center container: a horizontal
  // drag shifts the whole window. That fights a bar drag — dragging a bar
  // sideways would pan the board out from under the cursor. The gesture
  // controller disables vis's moveable/zoomable for the duration of a bar drag
  // (grab→release) and restores it the instant the drag ends. vis re-checks
  // options.moveable on every panmove (Range._onDrag), so toggling the option
  // mid-gesture reliably halts the window — no Hammer surgery needed.
  let panZoomEnabled = true;
  function setPanZoom(enabled) {
    if (panZoomEnabled === enabled) return;
    panZoomEnabled = enabled;
    timeline.setOptions({ moveable: enabled, zoomable: enabled });
  }

  // --- citation overlay (the 3.0b always-on overlay, productionized) ----
  // A positioned layer mounted INSIDE vis's centerContainer that carries a
  // legible tag centered on each cited bar. It exists for two reasons: narrow
  // bars clip their in-bar label (the 3.0 lesson), and it TRACKS vis's own
  // pan/zoom so the tag never drifts off its bar — the standing C1 regression
  // (CU5) asserts tag-vs-bar center = 0.0px, so a vis-timeline version bump that
  // broke item geometry would trip a test, not the demo. Read-only: it draws,
  // it never edits.
  const overlayEl = document.createElement("div");
  overlayEl.className = "cite-overlay";
  timeline.dom.centerContainer.appendChild(overlayEl);
  let citedBars = [];  // item ids currently tagged

  function itemRect(itemId) {
    const it = timeline.itemSet?.items?.[itemId];
    const box = it?.dom?.box;
    if (!box) return null;
    const base = timeline.dom.centerContainer.getBoundingClientRect();
    const r = box.getBoundingClientRect();
    if (r.width <= 0) return null;      // off-window / not rendered
    return { cx: r.left + r.width / 2 - base.left, top: r.top - base.top, height: r.height };
  }

  function renderOverlay() {
    overlayEl.querySelectorAll(".cite-tag").forEach((n) => n.remove());
    for (const id of citedBars) {
      const rc = itemRect(id);
      if (!rc) continue;
      const a = doc.assignments.find((x) => x.assignment_id === id);
      const tag = document.createElement("div");
      tag.className = "cite-tag";
      tag.dataset.item = id;      // identity, not text (bars can share a work_order)
      tag.textContent = (a?.work_orders || []).join(", ") || "cited";
      tag.style.left = `${rc.cx}px`;
      tag.style.top = `${rc.top - 9}px`;
      overlayEl.appendChild(tag);
    }
  }
  timeline.on("rangechange", renderOverlay);
  timeline.on("rangechanged", renderOverlay);
  timeline.on("changed", renderOverlay);
  window.addEventListener("resize", renderOverlay);

  // --- CU4 surface: selection + highlight ------------------------------
  // SELECTION HAS MORE THAN ONE LISTENER SINCE 4B.28. It was a single `selectCb`
  // and `onSelect` overwrote it — so the job panel subscribing would have
  // silently unsubscribed the ask panel's deictic scope, and "why is this one
  // late?" would have lost its subject with nothing on screen to say so. A list,
  // and every subscriber is notified.
  const selectCbs = [];
  const notifySelect = (payload) => {
    for (const cb of selectCbs) {
      try { cb(payload); } catch { /* one listener must never break another */ }
    }
  };
  let selectedItem = null;

  // The shared-selection payload (planner vocabulary — work_order + resource
  // external_name, never canonical ids). One builder so a bar CLICK and a
  // programmatic select() notify the ask panel identically (the deictic seam).
  // Resolves a split-op piece back to its assignment (the whole job is scoped).
  function assignmentFor(itemId) {
    return doc.assignments.find((x) => x.assignment_id === itemId)
      || splitPieceToAssignment.get(itemId) || null;
  }
  function selectionPayload(itemId) {
    const a = assignmentFor(itemId);
    if (!a) return null;
    return {
      operation_ref: a.operation_ref,
      work_orders: a.work_orders || [],
      resource_id: a.resource_id,
      resource_name: nameOf(a.resource_id),
      // Session 4B.14 Item 5(d): WHICH operation of the order is selected. The
      // ask panel forwarded only {order, machine}, so the server never learned
      // it and an order-level question fell back to the order's FIRST operation
      // — which is how a question asked with ORD-000013 selected on PAINT-01
      // came back about CUT-01, with no bridging sentence.
      op_seq: a.op_seq ?? null,
    };
  }

  // The selected order's due + release markers (CU2): scope the time anchors to
  // just the bar the planner clicked. Release = the order's release floor from
  // the Tier-0 interaction facts (earliest_start) when loaded; due from the
  // service outcome. Cleared on an empty / calendar selection.
  function scopeOrderMarkers(itemId) {
    const a = itemId ? assignmentFor(itemId) : null;
    if (!a) { markers.setOrder(null); return; }
    const wo = (a.work_orders || [])[0] || null;
    const so = doc.service_outcomes.find((s) => s.work_order === wo);
    let release = null;
    const facts = interactionPayload?.operations?.find((o) => o.operation_ref === a.operation_ref);
    if (facts && facts.earliest_start) release = facts.earliest_start;
    markers.setOrder({ due: so?.due ?? null, release, label: wo || "" });
  }

  timeline.on("select", (props) => {
    const itemId = props.items && props.items[0];
    if (!itemId || String(itemId).startsWith("cal-") || String(itemId).startsWith("cap-")) return;
    setSelected(itemId);
    scopeOrderMarkers(itemId);
    const payload = selectionPayload(itemId);
    if (payload) notifySelect(payload);
  });

  function setSelected(itemId) {
    if (selectedItem === itemId) return;
    if (selectedItem) toggleClass(selectedItem, "selected", false);
    selectedItem = itemId;
    if (itemId) toggleClass(itemId, "selected", true);
  }

  function toggleClass(itemId, cls, on) {
    const it = items.get(itemId);
    if (!it) return;
    const classes = new Set((it.className || "").split(/\s+/).filter(Boolean));
    on ? classes.add(cls) : classes.delete(cls);
    items.update({ id: itemId, className: [...classes].join(" ") });
  }

  let laneItems = [];
  function clearHighlight() {
    for (const it of items.get()) {
      if (String(it.id).startsWith("cal-") || String(it.id).startsWith("citelane-")) continue;
      if ((it.className || "").includes("cited")) toggleClass(it.id, "cited", false);
    }
    if (laneItems.length) { items.remove(laneItems); laneItems = []; }
    citedBars = [];
    renderOverlay();
  }

  // Glow the cited bars + lanes. citedRefs = {operations, resources, demands}
  // — exactly the refs the answer already cites (surfaced by the API, not
  // recomputed here). The evidence architecture, made spatial.
  function highlight(citedRefs) {
    clearHighlight();
    if (!citedRefs) return;
    const barIds = new Set();
    for (const op of citedRefs.operations || []) {
      const id = opToItem.get(op); if (id) barIds.add(id);
    }
    for (const d of citedRefs.demands || []) {
      const wo = demandToWO.get(d);
      for (const id of woToItems.get(wo) || []) barIds.add(id);
    }
    for (const id of barIds) toggleClass(id, "cited", true);
    // lanes: the resources the cited work actually RUNS on. Shade the whole
    // lane across the window.
    //
    // Session 4B.14 Item 5(c): the priced ALTERNATIVES ("the other press") come
    // in on their own channel now and are shaded distinctly. Fusing them here
    // is what made an answer about two bars on CUT-01 report four lanes, two of
    // which carry no work at all — an empty machine shaded as if it were part
    // of the evidence.
    const shadeLane = (rid, cls) => {
      if (!resById.has(rid)) return false;
      const lid = `citelane-${rid}`;
      items.add({ id: lid, group: rid, type: "background", start: win.start, end: win.end, className: cls });
      laneItems.push(lid);
      return true;
    };
    for (const rid of citedRefs.resources || []) shadeLane(rid, "cited-lane");
    for (const rid of citedRefs.alternatives || []) shadeLane(rid, "cited-lane cited-alt");
    citedBars = [...barIds];
    renderOverlay();
    return {
      bars: [...barIds],
      lanes: (citedRefs.resources || []).filter((r) => resById.has(r)),
      alternatives: (citedRefs.alternatives || []).filter((r) => resById.has(r)),
    };
  }

  // Tier-0 interaction payload (contract 1.3, delivered by interaction.js after
  // first paint). Stored here as the seam the Tier-0 legality library (CU2) and
  // the 3.2b drag surface consume; the read-only board itself does not use it.
  let interactionPayload = null;

  // The per-bar lateness band + label, factored so rebind() re-derives them.
  function barVisual(a) {
    const wos = a.work_orders || [];
    const lateness = wos.map((w) => latenessByWO.get(w))
      .filter((v) => v != null)
      .reduce((m, v) => (m == null || v > m ? v : m), null);
    const band = latenessBand(lateness);
    const label = wos.join(", ") || nameOf(a.resource_id);
    return { band, label };
  }

  // Rebind the board to a NEW schedule version (an accepted edit). The op set is
  // unchanged — a pin edit only MOVES placements — so each new assignment is
  // re-stamped with the OLD bar's id (keyed by operation_ref) and the bars
  // animate to their new group/time via a DataSet update (R-DP7: a legible
  // settle, never a teleport-reload). Selection + citation lookups read the live
  // ``doc``, so they follow automatically.
  function reduceMotion() {
    return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  }
  // Clear any lingering R-M1 motion classes (pin-lock / reflow-moved) from the
  // bars — called at the start of a rebind and on discard so a prior edit's
  // confirmation never bleeds into the next gesture.
  function clearMotionClasses() {
    for (const it of items.get()) {
      const cn = it.className || "";
      if (cn.includes("pin-lock")) toggleClass(it.id, "pin-lock", false);
      if (cn.includes("reflow-moved")) toggleClass(it.id, "reflow-moved", false);
    }
  }

  function rebind(newDoc, opts = {}) {
    // R-M1b/c: `movedOps` are the bars the re-solve displaced (REFLOW —
    // simultaneous, highlighted); `pinnedOp` is the dropped bar (OWN PLACEMENT —
    // never moves, static pin-lock). `motion` carries the feel durations.
    const { movedOps = null, pinnedOp = null, motion = {} } = opts;
    const reduce = reduceMotion();
    const reflowDur = motion.reflow_dur_ms ?? 340;
    const highlightDur = motion.reflow_highlight_dur_ms ?? 600;
    const pinlockDur = motion.pinlock_dur_ms ?? 220;
    clearMotionClasses();

    const oldIdByOp = new Map(doc.assignments.map((a) => [a.operation_ref, a.assignment_id]));
    for (const a of newDoc.assignments) {
      const oldId = oldIdByOp.get(a.operation_ref);
      if (oldId) a.assignment_id = oldId;   // preserve stable board identity
    }
    const oldAssignmentIds = doc.assignments.map((a) => a.assignment_id);
    doc = newDoc;
    rebuildDemandLookups();
    opToItem.clear(); woToItems.clear(); itemToOp.clear();
    for (const id of oldAssignmentIds) removeAssignmentItems(id);

    // R-M1b: enable the SIMULTANEOUS reflow transition for the reflow window only
    // (never staggered — one class, every bar moves at once). The pin-locked bar
    // is EXCLUDED from the transition in CSS (:not(.pin-lock)) so OWN PLACEMENT
    // snaps to its committed spot instead of sliding (R-M1c).
    if (!reduce) hostEl.classList.add("reflowing");

    // Bake the motion class into the same build that repositions each bar, so
    // the pin-lock exclusion is in place BEFORE vis moves the pinned bar (else it
    // would start sliding before the class lands). pin-lock = OWN PLACEMENT
    // (static, persists); reflow-moved = a one-shot highlight on a displaced bar.
    const highlightIds = [];
    for (const a of doc.assignments) {
      let extra = "";
      if (pinnedOp && a.operation_ref === pinnedOp) extra = "pin-lock";
      else if (movedOps && movedOps.has(a.operation_ref)) {
        extra = "reflow-moved";
        highlightIds.push(a.operation_ref);
      }
      addAssignmentItems(a, extra);
    }
    // the reflow highlight is a one-shot — retire the class once it has faded.
    // Keyed by operation_ref, not assignment id, because on a chunked bar the
    // item that carries the class is a PIECE and the assignment id is not an
    // item at all (the phantom-bar defect, from the other side).
    for (const op of highlightIds) {
      const id = opToItem.get(op);
      if (id) setTimeout(() => toggleClass(id, "reflow-moved", false), highlightDur + 60);
    }

    // the new version may have moved bars → occupancy changed. Rebuild the row
    // context (bands, band index, strips) from the live doc so the planner
    // surface stays truthful after an accept (Session 4.2). Single-chunk bars
    // only on the edit path; split rendering is untouched.
    occByRes.clear();
    for (const a of doc.assignments) {
      const ch = a.chunks || []; if (!ch.length) continue;
      if (!occByRes.has(a.resource_id)) occByRes.set(a.resource_id, []);
      pushOccupancy(a.resource_id, ch);   // per chunk, never the span (4B.20)
    }
    renderCapacityBands(); rebuildBandIndex(); refreshShiftTicks();
    // Session 4B.28 Item 1: a boundary move is a rebind whose ONLY change is the
    // boundary and who holds what. The marker has to follow the document or the
    // board would show the new authority against the old line.
    markers.setFrozen(doc.rolling ? doc.rolling.frozen_until : null);

    requestAnimationFrame(() => {
      timeline.redraw(); renderOverlay(); markers.redraw(); refreshRowStrips();
      if (!reduce) setTimeout(() => hostEl.classList.remove("reflowing"), reflowDur + 60);
    });
  }

  return {
    timeline, items, groups,
    win,
    host: hostEl,
    resourceName: nameOf,
    rebind,
    clearMotionClasses,
    currentDoc() { return doc; },
    // Harness probes (R-M1 motion end-states): a bar's current group+start (to
    // assert post-reflow positions) and its className (to assert the pin-lock /
    // reflow-moved motion classes), keyed by operation_ref.
    placementOf(opRef) {
      const id = opToItem.get(opRef); if (!id) return null;
      const it = items.get(id); if (!it) return null;
      return { group: it.group, start: new Date(it.start).toISOString() };
    },
    motionOf(opRef) {
      const id = opToItem.get(opRef); if (!id) return "";
      return (items.get(id)?.className) || "";
    },
    setInteraction(payload) { interactionPayload = payload; },
    getInteraction() { return interactionPayload; },
    // pan/zoom suppression during a bar drag (3.2c). The gesture controller
    // calls setPanZoom(false) on grab and setPanZoom(true) on release so the
    // board stays completely still under the cursor while a bar is being moved.
    setPanZoom,
    isPanZoomEnabled() { return panZoomEnabled; },
    // Item 2(b): the compression toggle. A planner verifying a calendar claim
    // needs the LINEAR view — "is there really nothing between these two bars?"
    // is unanswerable on a folded ruler — so the toggle is not optional chrome.
    setCompressed,
    isCompressed() { return compressed; },
    // Harness probe for the exactness guard: the folds in force, plus a
    // round-trip of a known instant through vis's own conversion under whatever
    // mode is active. A drop that lands minutes off surfaces here.
    compressionProbe(sampleMs) {
      const t = sampleMs == null ? bandSpan.start : sampleMs;
      let x = null, back = null;
      try {
        x = timeline.body.util.toScreen(new Date(t));
        back = timeline.body.util.toTime(x).getTime();
      } catch { /* a vis bump — reported as nulls, never thrown */ }
      return {
        compressed, folds: foldRanges.length,
        x: x == null ? null : +x.toFixed(2),
        roundTripErrMs: back == null ? null : Math.abs(back - t),
      };
    },
    onSelect(cb) { if (typeof cb === "function") selectCbs.push(cb); },
    select(operationRef) {
      const id = opToItem.get(operationRef);
      if (!id) return;
      timeline.setSelection([id]);
      setSelected(id);
      scopeOrderMarkers(id);
      // vis emits 'select' only on user interaction, not on setSelection — so a
      // programmatic select must notify the shared-selection callback itself,
      // or the ask panel's deictic scope would silently miss it (CU3).
      const payload = selectionPayload(id);
      if (payload) notifySelect(payload);
    },
    highlight,
    clearHighlight,
    fit() { timeline.setWindow(win.start, win.end, { animation: false }); },
    // Pointer/keyboard zoom path (Session 4.3 CU5): the board chrome's +/−
    // buttons drive vis's own zoom (Ctrl+wheel / trackpad pinch unchanged).
    zoomIn(pct = 0.5) { timeline.zoomIn(pct); },
    zoomOut(pct = 0.5) { timeline.zoomOut(pct); },
    setWindow(startIso, endIso) { timeline.setWindow(new Date(startIso), new Date(endIso), { animation: false }); renderOverlay(); },
    getWindow() { const w = timeline.getWindow(); return { start: w.start.toISOString(), end: w.end.toISOString() }; },
    // C1 drift probe (CU5 standing regression): for each cited bar, the overlay
    // tag's rendered center-x vs the vis-RENDERED bar's center-x, both measured
    // independently from the DOM. 0.0px means the overlay tracks vis's transform;
    // a version bump that broke item geometry surfaces here as nonzero drift.
    overlayProbe() {
      const base = timeline.dom.centerContainer.getBoundingClientRect();
      const tagById = new Map(
        [...overlayEl.querySelectorAll(".cite-tag")].map((el) => {
          const r = el.getBoundingClientRect();
          return [el.dataset.item, { cx: r.left + r.width / 2 - base.left, text: el.textContent, legible: (el.textContent || "").length >= 3 }];
        }),
      );
      const out = citedBars.map((id) => {
        const rc = itemRect(id);
        const a = doc.assignments.find((x) => x.assignment_id === id);
        const label = (a?.work_orders || []).join(", ");
        const tag = tagById.get(id) || null;   // matched by identity, not text
        return {
          bar: id, label,
          visBarCx: rc ? +rc.cx.toFixed(1) : null,
          tagCx: tag ? +tag.cx.toFixed(1) : null,
          legible: !!tag && tag.legible,
          driftPx: rc && tag ? +Math.abs(tag.cx - rc.cx).toFixed(1) : null,
        };
      });
      return { window: this.getWindow(), cited: out };
    },
    // --- Session 4B.28 Item 3: THE WHOLE JOB, from ONE derivation --------
    //
    // The job panel states working time, span, chunk count, status and the
    // lateness badge for every operation of an order. Every one of those is
    // ALREADY derived here — `jobFor` for the per-bar facts, `latenessBand` for
    // the badge, `doc.rolling.beyond_horizon` for the tray. So the panel is
    // handed those, and does not compute a single quantity of its own. 4B.21's
    // one-definition discipline: five of the last six category fusions were a
    // name written once by whoever needed a number.
    jobOf(itemIdOrOpRef) {
      const id = opToItem.get(itemIdOrOpRef) || itemIdOrOpRef;
      return jobFor(id);
    },
    // Every operation of an order, document order (op_seq), each with the same
    // facts the hover card states about a single bar.
    jobRowsForOrder(workOrder) {
      if (!workOrder) return [];
      const key = String(workOrder).toUpperCase();
      const rows = [];
      for (const a of doc.assignments || []) {
        const wos = (a.work_orders || []).map((w) => String(w).toUpperCase());
        if (!wos.includes(key)) continue;
        const itemId = opToItem.get(a.operation_ref);
        const job = itemId ? jobFor(itemId) : null;
        if (!job) continue;
        rows.push({
          operation_ref: a.operation_ref,
          op_seq: a.op_seq ?? null,
          machine: nameOf(a.resource_id),
          resource_id: a.resource_id,
          start: job.start, end: job.end,
          runMin: job.runMin, spanMin: job.spanMin,
          chunkCount: job.chunkCount,
          band: job.status,
          latenessMin: job.latenessMin,
          // The FOUR dispositions a placed bar can wear, never fused: the
          // rolling commitment state and the planner's own pin are different
          // facts about who may move it (4B.21, on the authority axis).
          commitmentState: a.commitment_state || null,
          standingPin: !!a.standing_pin,
          splittable: job.splittable, minChunkMin: job.minChunkMin,
        });
      }
      rows.sort((x, y) => (x.op_seq ?? 0) - (y.op_seq ?? 0));
      return rows;
    },
    // Tray entries for the same order — admitted work with no bar to draw. A
    // part-placed order must read as ONE job, so the panel shows these beside
    // the placed rows with their disposition named rather than leaving a gap.
    trayRowsForOrder(workOrder) {
      const tray = (doc.rolling && doc.rolling.beyond_horizon) || [];
      if (!workOrder) return [];
      const key = String(workOrder).toUpperCase();
      return tray
        .filter((t) => String(t.work_order || "").toUpperCase() === key)
        .map((t) => ({
          work_order: t.work_order, due: t.due || null,
          demand_ref: t.demand_ref,
          earliest: t.earliest_window_estimate || null,
          disposition: "beyond-horizon",
        }));
    },
    serviceOutcomeFor(workOrder) {
      if (!workOrder) return null;
      const key = String(workOrder).toUpperCase();
      return (doc.service_outcomes || []).find(
        (s) => String(s.work_order || "").toUpperCase() === key) || null;
    },
    // Scroll the board to a bar and flash it — the panel's row-click navigation.
    revealOp(opRef, { flashMs = 900 } = {}) {
      const id = opToItem.get(opRef);
      if (!id) return false;
      const it = items.get(id);
      if (!it) return false;
      const w = timeline.getWindow();
      const span = w.end.getTime() - w.start.getTime();
      const centre = new Date(it.start).getTime();
      timeline.setWindow(centre - span / 2, centre + span / 2, { animation: true });
      toggleClass(id, "row-flash", true);
      setTimeout(() => toggleClass(id, "row-flash", false), flashMs);
      return true;
    },

    // --- Session 4.2 planner-surface probes (harness) ------------------
    markers,
    hoverCards,
    // count of each capacity-band kind currently in the DataSet (CU1).
    capacityProbe() {
      const out = {};
      for (const it of items.get())
        if (String(it.id).startsWith("cap-")) {
          const k = (it.className || "").replace("cap-", "");
          out[k] = (out[k] || 0) + 1;
        }
      return out;
    },
    // the row-strip facts + live utilization for a resource by external name (CU4).
    rowStatsProbe(externalName) {
      const r = doc.resources.find((x) => nameOf(x.resource_id) === externalName);
      if (!r) return null;
      const w = timeline.getWindow();
      const occ = (occByRes.get(r.resource_id) || []).map((o) => [o.start, o.end]);
      const util = rowUtilization(openWinsByRes.get(r.resource_id) || [], occ,
        w.start.getTime(), w.end.getTime());
      return { util, booked_through: r.booked_through, next_open_gap: r.next_open_gap };
    },
    // marker overlay probe (CU2): now-line drift + which markers/ticks are drawn.
    markerProbe() { return markers.probe(); },
    // Session 4B.3a CU2: the sliced-world probe — the rolling block + the count of
    // each commitment_state currently on the board (committed / active_window).
    rollingProbe() {
      const states = {};
      for (const a of doc.assignments) {
        const k = a.commitment_state || "none";
        states[k] = (states[k] || 0) + 1;
      }
      return { rolling: doc.rolling || null, states,
               tray: (doc.rolling && doc.rolling.beyond_horizon) || [] };
    },
    _debug: { opToItem, woToItems, itemToOp, doc },
  };
}

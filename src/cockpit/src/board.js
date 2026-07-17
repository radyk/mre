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

export function createBoard(hostEl, initialDoc) {
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

  let minT = Infinity, maxT = -Infinity;
  for (const a of doc.assignments) {
    const chunks = a.chunks || [];
    if (!chunks.length) continue;
    const s = ms(chunks[0].start);
    const e = ms(chunks[chunks.length - 1].end);
    minT = Math.min(minT, s); maxT = Math.max(maxT, e);
    if (!occByRes.has(a.resource_id)) occByRes.set(a.resource_id, []);
    occByRes.get(a.resource_id).push({ start: s, end: e });
    const wos = a.work_orders || [];
    const lateness = wos.map((w) => latenessByWO.get(w))
      .filter((v) => v != null)
      .reduce((m, v) => (m == null || v > m ? v : m), null);
    const band = latenessBand(lateness);
    const label = wos.join(", ") || nameOf(a.resource_id);
    // R-DP8 CU2 + CU5: the pin/lock indicator family — a standing commitment (an
    // accepted, still-held pin) wears the persistent marker; siblings in the
    // family (transient pin-lock, reflow) are added later by rebind().
    const pinCls = a.standing_pin ? " standing-pin" : "";

    if (chunks.length <= 1) {
      // the common case: ONE range item, id = assignment_id (identity preserved).
      items.add({
        id: a.assignment_id, group: a.resource_id, start: s, end: e,
        type: "range", className: `bar late-${band}${pinCls}`, editable: false,
        style: barStyle(a, s, e), content: label, title: barTitle(a, label),
      });
      opToItem.set(a.operation_ref, a.assignment_id);
      for (const w of wos) {
        if (!woToItems.has(w)) woToItems.set(w, []);
        woToItems.get(w).push(a.assignment_id);
      }
    } else {
      // split/chunked op (CU5): one piece per chunk, visually linked as ONE job
      // (kinship styling + a dashed connector across each pause). The first
      // piece anchors the op for citation/selection; every piece maps back to
      // the op so a click on any piece scopes the whole job.
      const firstId = `${a.assignment_id}~c0`;
      opToItem.set(a.operation_ref, firstId);
      chunks.forEach((c, i) => {
        const cs = ms(c.start), ce = ms(c.end);
        const edge = i === 0 ? "chunk-first" : i === chunks.length - 1 ? "chunk-last" : "chunk-mid";
        const pieceId = `${a.assignment_id}~c${i}`;
        items.add({
          id: pieceId, group: a.resource_id, start: cs, end: ce,
          type: "range",
          className: `bar late-${band}${pinCls} chunk-piece ${edge}`, editable: false,
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
  const markers = createMarkers(timeline);
  // now-line from the run's reference date (the 3.3b epoch) — never wall clock;
  // absent when the run is "now"-anchored (reference_date null).
  markers.setNow(doc.reference_date || null);
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
  // job facts for a bar (or a split piece) → the job hover card.
  function jobFor(itemId) {
    const a = doc.assignments.find((x) => x.assignment_id === itemId)
      || splitPieceToAssignment.get(itemId);
    if (!a) return null;
    const wo = (a.work_orders || [])[0] || null;
    const so = doc.service_outcomes.find((s) => s.work_order === wo);
    const lateness = so ? so.lateness_min : null;
    const status = latenessBand(lateness);
    return {
      order: wo, qty: so?.quantity ?? null, uom: so?.quantity_uom ?? null,
      due: so?.due ?? null, customer: so?.customer_name ?? null,
      opSeq: a.op_seq, status, standingPin: !!a.standing_pin,
      resourceName: nameOf(a.resource_id),
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
  let selectCb = null;
  let selectedItem = null;
  const itemToOp = new Map([...opToItem].map(([op, it]) => [it, op]));

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
    if (payload && selectCb) selectCb(payload);
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
    // lanes: the chosen + alternative resources the answer prices ("the other
    // press"). Shade the whole lane across the window.
    for (const rid of citedRefs.resources || []) {
      if (!resById.has(rid)) continue;
      const lid = `citelane-${rid}`;
      items.add({ id: lid, group: rid, type: "background", start: win.start, end: win.end, className: "cited-lane" });
      laneItems.push(lid);
    }
    citedBars = [...barIds];
    renderOverlay();
    return { bars: [...barIds], lanes: (citedRefs.resources || []).filter((r) => resById.has(r)) };
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
    doc = newDoc;
    rebuildDemandLookups();
    opToItem.clear(); woToItems.clear(); itemToOp.clear();

    // R-M1b: enable the SIMULTANEOUS reflow transition for the reflow window only
    // (never staggered — one class, every bar moves at once). The pin-locked bar
    // is EXCLUDED from the transition in CSS (:not(.pin-lock)) so OWN PLACEMENT
    // snaps to its committed spot instead of sliding (R-M1c).
    if (!reduce) hostEl.classList.add("reflowing");

    // Bake the motion class into the same update that repositions each bar, so
    // the pin-lock exclusion is in place BEFORE vis moves the pinned bar (else it
    // would start sliding before the class lands). pin-lock = OWN PLACEMENT
    // (static, persists); reflow-moved = a one-shot highlight on a displaced bar.
    const highlightIds = [];
    for (const a of doc.assignments) {
      const s = ms(a.chunks[0].start);
      const e = ms(a.chunks[a.chunks.length - 1].end);
      const { band, label } = barVisual(a);
      let cn = `bar late-${band}`;
      if (a.standing_pin) cn += " standing-pin";   // R-DP8 CU2: persistent marker
      if (pinnedOp && a.operation_ref === pinnedOp) cn += " pin-lock";
      else if (movedOps && movedOps.has(a.operation_ref)) { cn += " reflow-moved"; highlightIds.push(a.assignment_id); }
      items.update({
        id: a.assignment_id, group: a.resource_id, start: s, end: e,
        type: "range", className: cn, editable: false,
        content: label,
        title: `${label} · ${nameOf(a.resource_id)} · op ${a.op_seq}`
          + (a.standing_pin ? " · committed (accepted edit)" : ""),
      });
      opToItem.set(a.operation_ref, a.assignment_id);
      itemToOp.set(a.assignment_id, a.operation_ref);
      for (const w of (a.work_orders || [])) {
        if (!woToItems.has(w)) woToItems.set(w, []);
        woToItems.get(w).push(a.assignment_id);
      }
    }
    // the reflow highlight is a one-shot — retire the class once it has faded.
    for (const id of highlightIds) setTimeout(() => toggleClass(id, "reflow-moved", false), highlightDur + 60);

    // the new version may have moved bars → occupancy changed. Rebuild the row
    // context (bands, band index, strips) from the live doc so the planner
    // surface stays truthful after an accept (Session 4.2). Single-chunk bars
    // only on the edit path; split rendering is untouched.
    occByRes.clear();
    for (const a of doc.assignments) {
      const ch = a.chunks || []; if (!ch.length) continue;
      if (!occByRes.has(a.resource_id)) occByRes.set(a.resource_id, []);
      occByRes.get(a.resource_id).push({ start: ms(ch[0].start), end: ms(ch[ch.length - 1].end) });
    }
    renderCapacityBands(); rebuildBandIndex(); refreshShiftTicks();

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
    onSelect(cb) { selectCb = cb; },
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
      if (payload && selectCb) selectCb(payload);
    },
    highlight,
    clearHighlight,
    fit() { timeline.setWindow(win.start, win.end, { animation: false }); },
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
    _debug: { opToItem, woToItems, itemToOp, doc },
  };
}

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

const ms = (iso) => new Date(iso).getTime();

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

export function createBoard(hostEl, doc) {
  // --- planner-vocabulary lookups --------------------------------------
  const resById = new Map(doc.resources.map((r) => [r.resource_id, r]));
  const nameOf = (rid) => resById.get(rid)?.external_name || rid.slice(0, 8);
  // per-Demand lateness, keyed by the external work_order the bars carry.
  const latenessByWO = new Map();
  const demandToWO = new Map();
  for (const so of doc.service_outcomes || []) {
    if (so.work_order != null) latenessByWO.set(so.work_order, so.lateness_min);
    if (so.demand_ref) demandToWO.set(so.demand_ref, so.work_order);
  }

  // --- groups (rows) in document order ---------------------------------
  const groups = new DataSet(
    doc.resources.map((r, i) => ({ id: r.resource_id, content: nameOf(r.resource_id), order: i })),
  );

  // --- bars + calendar backgrounds -------------------------------------
  const opToItem = new Map();   // operation_ref -> item id
  const woToItems = new Map();  // work_order    -> [item id,...]
  const items = new DataSet();

  let minT = Infinity, maxT = -Infinity;
  for (const a of doc.assignments) {
    const s = ms(a.chunks[0].start);
    const e = ms(a.chunks[a.chunks.length - 1].end);
    minT = Math.min(minT, s); maxT = Math.max(maxT, e);
    const wos = a.work_orders || [];
    // worst (largest) lateness across the bar's demands drives its color.
    const lateness = wos
      .map((w) => latenessByWO.get(w))
      .filter((v) => v != null)
      .reduce((m, v) => (m == null || v > m ? v : m), null);
    const band = latenessBand(lateness);
    const label = wos.join(", ") || nameOf(a.resource_id);
    items.add({
      id: a.assignment_id, group: a.resource_id, start: s, end: e,
      type: "range", className: `bar late-${band}`, editable: false,
      content: label, title: `${label} · ${nameOf(a.resource_id)} · op ${a.op_seq}`,
    });
    opToItem.set(a.operation_ref, a.assignment_id);
    for (const w of wos) {
      if (!woToItems.has(w)) woToItems.set(w, []);
      woToItems.get(w).push(a.assignment_id);
    }
  }

  // calendar closures / overtime as background shading (regular = default).
  for (const r of doc.resources) {
    for (const [wi, w] of (r.calendar_windows || []).entries()) {
      if (w.kind === "regular") continue;
      if (ms(w.end) <= minT || ms(w.start) >= maxT) continue; // cull off-window
      items.add({
        id: `cal-${r.resource_id}-${wi}`, group: r.resource_id, type: "background",
        start: ms(w.start), end: ms(w.end), className: `cal-${w.kind}`,
      });
    }
  }

  const pad = 6 * 3600000;
  const win = { start: minT - pad, end: maxT + pad };

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
  requestAnimationFrame(() => { timeline.redraw(); renderOverlay(); });

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

  timeline.on("select", (props) => {
    const itemId = props.items && props.items[0];
    if (!itemId || String(itemId).startsWith("cal-")) return;
    setSelected(itemId);
    const a = doc.assignments.find((x) => x.assignment_id === itemId);
    if (a && selectCb) {
      selectCb({
        operation_ref: a.operation_ref,
        work_orders: a.work_orders || [],
        resource_id: a.resource_id,
        resource_name: nameOf(a.resource_id),
      });
    }
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

  return {
    timeline, items, groups,
    win,
    host: hostEl,
    resourceName: nameOf,
    setInteraction(payload) { interactionPayload = payload; },
    getInteraction() { return interactionPayload; },
    // pan/zoom suppression during a bar drag (3.2c). The gesture controller
    // calls setPanZoom(false) on grab and setPanZoom(true) on release so the
    // board stays completely still under the cursor while a bar is being moved.
    setPanZoom,
    isPanZoomEnabled() { return panZoomEnabled; },
    onSelect(cb) { selectCb = cb; },
    select(operationRef) { const id = opToItem.get(operationRef); if (id) { timeline.setSelection([id]); setSelected(id); } },
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
    _debug: { opToItem, woToItems, itemToOp, doc },
  };
}

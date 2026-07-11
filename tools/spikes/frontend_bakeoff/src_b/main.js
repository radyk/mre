// Candidate B — library: vis-timeline.
// The two questions the spike must answer (see VERDICT.md):
//   Q1 Can vis-timeline host per-drag DYNAMIC overlays — Tier-0 shading and
//      priced ghosts injected at grab time?  (approach: background items +
//      className'd range items added to the DataSet on grab.)
//   Q2 Can its snap accept per-drag SEMANTIC targets, not just a static grid?
//      (approach: the onMoving(item, cb) hook overrides item.start with our
//      shared snapTime before committing — the library's only per-drag seam.)
import { Timeline } from "vis-timeline/standalone";
import { DataSet } from "vis-data";
import "vis-timeline/styles/vis-timeline-graph2d.min.css";
import {
  loadFixture, LAYOUT, snapTime,
} from "/shared/geometry.js";

// candidate-B-specific item styling (kept out of the shared sheet)
const style = document.createElement("style");
style.textContent = `
  .vis-timeline { border: 0; font-size: 11px; }
  .vis-labelset .vis-label, .vis-foreground .vis-group { border-color: var(--grid); }
  .vis-panel.vis-left { color: var(--muted); }
  .vis-item { border-radius: 3px; }
  .vis-item.bar { background: var(--bar); border-color: var(--bar); color: var(--bar-ink); }
  .vis-item.grabitem { background: var(--grab); border-color: var(--grab); color: #fff; font-weight: 700; }
  .vis-item.grabitem.dropped {
    background: repeating-linear-gradient(45deg, rgba(176,108,240,.25) 0 5px, rgba(176,108,240,.6) 5px 7px);
    border-style: dashed;
  }
  .vis-item.ghostitem {
    background: var(--ghost-fill, rgba(53,201,194,.14)); border: 1.6px dashed var(--ghost);
    color: var(--ghost); font-weight: 700;
  }
  .vis-item.vis-background.legal-green { background: var(--green-fill); }
  .vis-item.vis-background.legal-amber { background: var(--amber-fill); }
  .vis-item.vis-background.legal-dim   { background: var(--dim-fill); }
  .vis-time-axis .vis-text { color: var(--muted); }
  .vis-time-axis .vis-grid.vis-minor { border-color: var(--grid); }
`;
document.head.appendChild(style);

const statusEl = document.getElementById("status");
const ms = (iso) => new Date(iso).getTime();
const fmt = (t) => new Date(t).toLocaleString("en-US", { weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" });

let model, timeline, items, groups, phase = "idle", latency = null, tentative = null, altOn = false;
let t0 = 0;
const GRAB_ID = "__grab";

function legalClass(leg) { return leg === "green" ? "legal-green" : leg === "amber" ? "legal-amber" : "legal-dim"; }

function ghostByRow(row) { return model.ghosts.find((g) => g.row === row); }

function applySnap(startMs) {
  const s = snapTime(startMs, model, { alt: altOn });
  return s;
}

function setStatus() {
  let s = `phase: <b>${phase}</b>`;
  if (latency !== null) s += ` · grab→shade <b>${latency}ms</b>`;
  if (tentative) {
    s += ` · snapped:<b>${tentative.snappedTo}</b> · ${fmt(tentative.time)}`;
    if (tentative.deltaCost != null) s += ` · <b>${tentative.deltaCost >= 0 ? "+" : "-"}$${Math.abs(tentative.deltaCost)}</b>`;
  }
  statusEl.innerHTML = s;
}

// ---- dynamic overlays injected at grab (Q1) ------------------------------
function addOverlays() {
  // Tier-0 shading: one background item per group spanning the window.
  const bg = model.rows.map((r) => ({
    id: `bg-${r.index}`, group: r.index, type: "background",
    start: model.win.start, end: model.win.end, className: legalClass(r.legality),
  }));
  // Ghosts: dashed range items with the priced label as content.
  const gh = model.ghosts.map((g, i) => ({
    id: `gh-${i}`, group: g.row, start: g.startMs, end: g.endMs,
    type: "range", className: "ghostitem", content: g.cost_label,
  }));
  items.add([...bg, ...gh]);
}
function removeOverlays() {
  const ids = model.rows.map((r) => `bg-${r.index}`).concat(model.ghosts.map((_, i) => `gh-${i}`));
  items.remove(ids);
}

function beginGrab() {
  t0 = performance.now();
  latency = null;
  phase = "grabbing";
  addOverlays();
  tentative = { time: model.grab.startMs, row: model.grab.row, snappedTo: "origin", deltaCost: 0 };
  requestAnimationFrame(() => { latency = +(performance.now() - t0).toFixed(1); setStatus(); });
  setStatus();
}

function moveTo(startMs, row) {
  const snap = applySnap(startMs);
  const g = ghostByRow(row);
  const deltaCost = g && Math.abs(g.startMs - snap.time) < 45 * 60000 ? g.cost_delta : null;
  tentative = { time: snap.time, row, snappedTo: snap.snappedTo, deltaCost };
  items.update({ id: GRAB_ID, group: row, start: snap.time, end: snap.time + model.grab.durMs });
  setStatus();
}

function drop() {
  phase = "dropped";
  items.update({ id: GRAB_ID, className: "grabitem dropped" });
  setStatus();
}

function reset() {
  phase = "idle"; latency = null; tentative = null; altOn = false;
  removeOverlays();
  items.update({ id: GRAB_ID, className: "grabitem", group: model.grab.row, start: model.grab.startMs, end: model.grab.endMs });
  setStatus();
}

async function main() {
  model = await loadFixture();

  groups = new DataSet(model.rows.map((r) => ({ id: r.index, content: r.name })));
  const barItems = model.bars
    .filter((b) => !b.isGrab)
    .map((b) => ({ id: b.id, group: b.row, start: b.start, end: b.end, type: "range", className: "bar", editable: false }));
  barItems.push({
    id: GRAB_ID, group: model.grab.row, start: model.grab.startMs, end: model.grab.endMs,
    type: "range", className: "grabitem", content: (model.grab.work_orders || []).join(","),
    editable: { updateTime: true, updateGroup: true },
  });
  items = new DataSet(barItems);

  timeline = new Timeline(document.getElementById("tl"), items, groups, {
    stack: false,
    // Only the grab item is editable: global editable object + overrideItems
    // so the per-item editable:false on bars and editable:{...} on grab win.
    editable: { updateTime: true, updateGroup: true, overrideItems: true, add: false, remove: false },
    itemsAlwaysDraggable: { item: true, range: true }, // drag without pre-selecting
    selectable: true,
    min: model.win.start, max: model.win.end,
    start: model.win.start, end: model.win.end,
    zoomable: false, moveable: true,
    groupOrder: (a, b) => a.id - b.id,
    margin: { item: 2, axis: 4 },
    // Q2: the ONLY per-drag seam vis-timeline exposes — override the time here.
    onMoving: (item, cb) => {
      if (item.id !== GRAB_ID) return cb(null);
      const snap = applySnap(+new Date(item.start));
      const row = item.group;
      item.start = new Date(snap.time);
      item.end = new Date(snap.time + model.grab.durMs);
      const g = ghostByRow(row);
      const deltaCost = g && Math.abs(g.startMs - snap.time) < 45 * 60000 ? g.cost_delta : null;
      tentative = { time: snap.time, row, snappedTo: snap.snappedTo, deltaCost };
      if (phase === "idle") beginGrab(); // grabbing began via a real pointer
      setStatus();
      cb(item);
    },
    onMove: (item, cb) => { cb(item); drop(); },
  });

  // Alt toggles snap off during a real drag.
  window.addEventListener("keydown", (e) => { if (e.key === "Alt") altOn = true; });
  window.addEventListener("keyup", (e) => { if (e.key === "Alt") altOn = false; });
  document.getElementById("reset").addEventListener("click", reset);

  setStatus();

  // harness hook (same page contract as Candidate A)
  window.__spike = {
    ready: true, candidate: "B",
    grab: () => beginGrab(),
    moveToGhost: (i) => { const g = model.ghosts[i]; moveTo(g.startMs, g.row); },
    moveToTime: (iso, opts = {}) => { altOn = !!opts.alt; moveTo(ms(iso), opts.row ?? model.grab.row); },
    setAlt: (v) => { altOn = !!v; },
    drop: () => drop(),
    reset: () => reset(),
    getState: () => ({ phase, tentative, latency }),
  };
}

main();

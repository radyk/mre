// Candidate B — vis-timeline — SESSION 3.0b EXTENSION.
// The 3.0 spike left vis-timeline GREEN-qualified on three YELLOW seams. 3.0b
// stress-tests exactly those seams against the drop ruling (docs/04 pending):
//   C1  Always-on overlay layer: a positioned layer ABOVE the vis canvas that
//       carries the priced ghost labels + tentative hatching, and TRACKS vis's
//       own pan/zoom (getWindow) without drift. Fixes the 3.0 in-bar clipping.
//   C2  Mid-drag rejection: dragging over a proven-illegal (dim) row must be
//       VISIBLY refused mid-drag (bar won't enter, cursor = not-allowed), and a
//       drop there returns the bar home. Implemented through onMoving/onMove.
//   C3  One real magnet through onMoving: shift-start anchor, tolerance radius,
//       Alt-disable, plus a proximity FALLOFF indicator — to judge whether the
//       single coarse hook can carry magnet feel.
// Nothing here ships. Original candidate_b (3.0 evidence) is left untouched.
import { Timeline } from "vis-timeline/standalone";
import { DataSet } from "vis-data";
import "vis-timeline/styles/vis-timeline-graph2d.min.css";
import { loadFixture, snapTime } from "/shared/geometry.js";

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
  .vis-item.ghostitem { background: var(--ghost-fill, rgba(53,201,194,.14)); border: 1.6px dashed var(--ghost); }
  .vis-item.vis-background.legal-green { background: var(--green-fill); }
  .vis-item.vis-background.legal-amber { background: var(--amber-fill); }
  .vis-item.vis-background.legal-dim   { background: var(--dim-fill); }
  .vis-time-axis .vis-text { color: var(--muted); }
  .vis-time-axis .vis-grid.vis-minor { border-color: var(--grid); }

  /* ---- C1: the always-on overlay layer -------------------------------- */
  .spk-overlay { position: absolute; inset: 0; pointer-events: none; overflow: hidden; z-index: 5; }
  .spk-ghostlbl {
    position: absolute; transform: translate(-50%, 0);
    font: 700 11px/1.2 ui-monospace, monospace; color: var(--ghost);
    background: rgba(10,12,18,.82); border: 1px solid var(--ghost);
    border-radius: 4px; padding: 1px 5px; white-space: nowrap;
  }
  .spk-hatch {
    position: absolute; border: 1.4px dashed var(--grab); border-radius: 3px;
    background: repeating-linear-gradient(45deg, rgba(176,108,240,.20) 0 5px, rgba(176,108,240,.5) 5px 7px);
  }
  .spk-hatch.refused { border-color: #ff5d5d; background: repeating-linear-gradient(45deg, rgba(255,93,93,.18) 0 5px, rgba(255,93,93,.42) 5px 7px); }
  .spk-caption {
    position: absolute; transform: translate(-50%, -100%);
    font: 700 10px/1.2 ui-monospace, monospace; color: #fff;
    background: var(--grab); border-radius: 3px; padding: 1px 5px; white-space: nowrap;
  }
  .spk-caption.refused { background: #ff5d5d; }
  /* C3: magnet falloff — a pull line whose opacity/thickness scales with proximity */
  .spk-magnet { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--ghost); }
  .spk-magnet.pred { background: #ffcf5d; }
  .spk-refusebanner {
    position: absolute; top: 6px; left: 50%; transform: translateX(-50%);
    font: 700 12px/1 ui-monospace, monospace; color: #fff; background: #ff5d5d;
    border-radius: 5px; padding: 4px 10px; display: none;
  }
`;
document.head.appendChild(style);

const statusEl = document.getElementById("status");
const ms = (iso) => new Date(iso).getTime();
const fmt = (t) => new Date(t).toLocaleString("en-US", { weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" });

let model, timeline, items, groups;
let phase = "idle", latency = null, tentative = null, altOn = false, refused = false;
let committed = null;               // last LEGAL {row,time} — the home for snapback
let overlayEl = null, refuseBanner = null;
let onMovingCount = 0, magnetSamples = [];  // C3 instrumentation
let dragT0 = 0;
const GRAB_ID = "__grab";

function legalClass(leg) { return leg === "green" ? "legal-green" : leg === "amber" ? "legal-amber" : "legal-dim"; }
function rowLegality(row) { return model.rows[row]?.legality || "dim"; }
function ghostByRow(row) { return model.ghosts.find((g) => g.row === row); }
function applySnap(startMs) { return snapTime(startMs, model, { alt: altOn }); }

function setStatus() {
  let s = `phase: <b>${phase}</b>`;
  if (latency !== null) s += ` · grab→shade <b>${latency}ms</b>`;
  if (refused) s += ` · <b style="color:#ff5d5d">REFUSED (illegal row)</b>`;
  if (tentative) {
    s += ` · snapped:<b>${tentative.snappedTo}</b> · ${fmt(tentative.time)}`;
    if (tentative.deltaCost != null) s += ` · <b>${tentative.deltaCost >= 0 ? "+" : "-"}$${Math.abs(tentative.deltaCost)}</b>`;
  }
  statusEl.innerHTML = s;
}

// ---- Tier-0 shading via vis background items (unchanged approach) ---------
function addShading() {
  const bg = model.rows.map((r) => ({
    id: `bg-${r.index}`, group: r.index, type: "background",
    start: model.win.start, end: model.win.end, className: legalClass(r.legality),
  }));
  // ghost BARS stay vis-native (dashed range items) — but WITHOUT content, so
  // nothing clips. The label lives in the overlay (C1).
  const gh = model.ghosts.map((g, i) => ({
    id: `gh-${i}`, group: g.row, start: g.startMs, end: g.endMs, type: "range", className: "ghostitem",
  }));
  items.add([...bg, ...gh]);
}
function removeShading() {
  const ids = model.rows.map((r) => `bg-${r.index}`).concat(model.ghosts.map((_, i) => `gh-${i}`));
  items.remove(ids);
}

// ---- C1: overlay geometry, driven ONLY by vis's public getWindow() -------
function winToX(t, width, w0, w1) { return ((t - w0) / (w1 - w0)) * width; }

function groupRects() {
  // foreground groups render in groupOrder (ascending id == row index).
  const base = timeline.dom.centerContainer.getBoundingClientRect();
  const els = timeline.dom.center.querySelectorAll(".vis-foreground .vis-group");
  return Array.from(els).map((el) => {
    const r = el.getBoundingClientRect();
    return { top: r.top - base.top, height: r.height };
  });
}

function renderOverlay() {
  if (!overlayEl) return;
  overlayEl.querySelectorAll(".spk-ghostlbl,.spk-hatch,.spk-caption,.spk-magnet").forEach((n) => n.remove());
  if (phase === "idle") return;
  const win = timeline.getWindow();
  const w0 = win.start.getTime(), w1 = win.end.getTime();
  const width = timeline.dom.centerContainer.offsetWidth;
  const rects = groupRects();
  const toX = (t) => winToX(t, width, w0, w1);

  // ghost priced labels — centred on each ghost bar, ALLOWED to overflow it.
  for (const g of model.ghosts) {
    const rc = rects[g.row]; if (!rc) continue;
    const cx = toX((g.startMs + g.endMs) / 2);
    if (cx < -40 || cx > width + 40) continue;         // culled off-screen
    const lbl = document.createElement("div");
    lbl.className = "spk-ghostlbl";
    lbl.textContent = g.cost_label;
    lbl.style.left = `${cx}px`;
    lbl.style.top = `${rc.top + rc.height / 2 - 8}px`;
    overlayEl.appendChild(lbl);
  }

  // tentative hatch + caption at the current (snapped) position.
  if (tentative && (phase === "grabbing" || phase === "dropped" || phase === "returned_home")) {
    const rc = rects[tentative.row]; if (rc) {
      const x0 = toX(tentative.time), x1 = toX(tentative.time + model.grab.durMs);
      const h = document.createElement("div");
      h.className = "spk-hatch" + (refused ? " refused" : "");
      h.style.left = `${x0}px`; h.style.top = `${rc.top + 3}px`;
      h.style.width = `${Math.max(4, x1 - x0)}px`; h.style.height = `${rc.height - 6}px`;
      overlayEl.appendChild(h);
      const cap = document.createElement("div");
      cap.className = "spk-caption" + (refused ? " refused" : "");
      cap.textContent = refused ? "refused" : `tentative · ${tentative.snappedTo}` + (tentative.deltaCost != null ? ` · +$${tentative.deltaCost}` : "");
      cap.style.left = `${(x0 + x1) / 2}px`; cap.style.top = `${rc.top + 2}px`;
      overlayEl.appendChild(cap);
    }
  }

  // C3: magnet falloff line — drawn when a snap target is within tolerance.
  if (tentative && tentative.magnet && !altOn) {
    const m = tentative.magnet;
    const mx = toX(m.time);
    if (mx >= 0 && mx <= width) {
      const line = document.createElement("div");
      line.className = "spk-magnet" + (m.kind === "predecessor_finish" ? " pred" : "");
      line.style.left = `${mx}px`;
      line.style.opacity = String(m.strength.toFixed(2));      // falloff: 0..1 by proximity
      line.style.width = `${(1 + 3 * m.strength).toFixed(1)}px`;
      overlayEl.appendChild(line);
    }
  }
}

// ---- lifecycle -----------------------------------------------------------
function beginGrab() {
  dragT0 = performance.now();
  latency = null; phase = "grabbing"; refused = false; onMovingCount = 0; magnetSamples = [];
  addShading();
  committed = { row: model.grab.row, time: model.grab.startMs };
  tentative = { time: model.grab.startMs, row: model.grab.row, snappedTo: "origin", deltaCost: 0, magnet: null };
  requestAnimationFrame(() => { latency = +(performance.now() - dragT0).toFixed(1); setStatus(); renderOverlay(); });
  setStatus(); renderOverlay();
}

// Compute the nearest snap target + falloff strength (C3). tolerance = magnetPx.
function magnetFor(rawTime) {
  if (altOn) return null;
  const tolMs = (7 / 14) * 3600000; // LAYOUT.magnetPx / pxPerHour hours -> ms (30 min)
  let best = null;
  for (const tgt of model.targets) {
    const d = Math.abs(tgt.time - rawTime);
    if (d > tolMs) continue;
    const strength = 1 - d / tolMs;                 // linear falloff 1 (on target) -> 0 (edge)
    if (!best || strength > best.strength) best = { time: tgt.time, kind: tgt.kind, strength };
  }
  return best;
}

// core move used by BOTH scripted and real-pointer paths.
function moveTo(rawStartMs, row) {
  onMovingCount++;
  const leg = rowLegality(row);
  if (leg === "dim") {
    // C2: REFUSE. The bar does not enter the illegal row — it stays at the last
    // legal committed position; only the cursor + banner change.
    refused = true;
    setCursor("not-allowed");
    if (refuseBanner) refuseBanner.style.display = "block";
    // keep tentative visually at committed (legal) spot, flagged refused
    tentative = { ...tentative, refusedRow: row };
    setStatus(); renderOverlay();
    return { accepted: false, refused: true };
  }
  refused = false;
  setCursor("grabbing");
  if (refuseBanner) refuseBanner.style.display = "none";
  const snap = applySnap(rawStartMs);
  const magnet = magnetFor(rawStartMs);
  if (magnet) magnetSamples.push({ t: performance.now(), strength: magnet.strength, kind: magnet.kind });
  const g = ghostByRow(row);
  const deltaCost = g && Math.abs(g.startMs - snap.time) < 45 * 60000 ? g.cost_delta : null;
  tentative = { time: snap.time, row, snappedTo: snap.snappedTo, deltaCost, magnet };
  committed = { row, time: snap.time };
  items.update({ id: GRAB_ID, group: row, start: snap.time, end: snap.time + model.grab.durMs });
  setStatus(); renderOverlay();
  return { accepted: true, refused: false, snappedTo: snap.snappedTo };
}

function setCursor(c) { document.body.style.cursor = c; }

function drop() {
  // Ruling: land exactly where dropped (legal) or RETURN HOME (illegal/refused).
  if (refused || rowLegality(committed.row) === "dim") {
    return returnHome();
  }
  phase = "dropped";
  items.update({ id: GRAB_ID, className: "grabitem dropped", group: committed.row, start: committed.time, end: committed.time + model.grab.durMs });
  setCursor("default");
  setStatus(); renderOverlay();
}

function returnHome() {
  phase = "returned_home";
  refused = false;
  if (refuseBanner) refuseBanner.style.display = "none";
  tentative = { time: model.grab.startMs, row: model.grab.row, snappedTo: "home", deltaCost: 0, magnet: null };
  committed = { row: model.grab.row, time: model.grab.startMs };
  items.update({ id: GRAB_ID, className: "grabitem", group: model.grab.row, start: model.grab.startMs, end: model.grab.endMs });
  setCursor("default");
  setStatus(); renderOverlay();
}

function reset() {
  phase = "idle"; latency = null; tentative = null; altOn = false; refused = false;
  onMovingCount = 0; magnetSamples = [];
  if (refuseBanner) refuseBanner.style.display = "none";
  removeShading();
  items.update({ id: GRAB_ID, className: "grabitem", group: model.grab.row, start: model.grab.startMs, end: model.grab.endMs });
  setCursor("default");
  setStatus(); renderOverlay();
}

async function main() {
  model = await loadFixture();

  groups = new DataSet(model.rows.map((r) => ({ id: r.index, content: r.name })));
  const barItems = model.bars
    .filter((b) => !b.isGrab)
    .map((b) => ({ id: b.id, group: b.row, start: b.start, end: b.end, type: "range", className: "bar", editable: false }));
  barItems.push({
    id: GRAB_ID, group: model.grab.row, start: model.grab.startMs, end: model.grab.endMs,
    type: "range", className: "grabitem", content: "", // label lives in overlay now
    editable: { updateTime: true, updateGroup: true },
  });
  items = new DataSet(barItems);

  // C1 honesty: ENABLE zoom + pan and give room beyond the window, so the
  // overlay's pan/zoom tracking is actually exercised (3.0 had a frozen window).
  const pad = 12 * 3600000;
  timeline = new Timeline(document.getElementById("tl"), items, groups, {
    stack: false,
    editable: { updateTime: true, updateGroup: true, overrideItems: true, add: false, remove: false },
    itemsAlwaysDraggable: { item: true, range: true },
    selectable: true,
    min: model.win.start - pad, max: model.win.end + pad,
    start: model.win.start, end: model.win.end,
    zoomable: true, moveable: true, zoomMin: 6 * 3600000,
    groupOrder: (a, b) => a.id - b.id,
    margin: { item: 2, axis: 4 },
    onMoving: (item, cb) => {
      if (item.id !== GRAB_ID) return cb(null);
      if (phase === "idle") beginGrab();  // grab began via a real pointer
      const res = moveTo(+new Date(item.start), item.group);
      if (!res.accepted) return cb(null); // C2: refuse — vis keeps item put
      item.start = new Date(committed.time);
      item.end = new Date(committed.time + model.grab.durMs);
      item.group = committed.row;
      cb(item);
    },
    onMove: (item, cb) => {
      // final drop: accept legal, reject (snap home) illegal.
      if (refused || rowLegality(item.group) === "dim") { cb(null); returnHome(); }
      else { cb(item); drop(); }
    },
  });

  // C1: mount the overlay INSIDE vis's centerContainer so it clips + shares origin.
  overlayEl = document.createElement("div");
  overlayEl.className = "spk-overlay";
  timeline.dom.centerContainer.appendChild(overlayEl);
  refuseBanner = document.createElement("div");
  refuseBanner.className = "spk-refusebanner";
  refuseBanner.textContent = "⃠ illegal row — drop refused";
  overlayEl.appendChild(refuseBanner);

  // C1: keep the overlay glued to vis's own pan/zoom + redraws.
  timeline.on("rangechange", renderOverlay);
  timeline.on("rangechanged", renderOverlay);
  timeline.on("changed", renderOverlay);
  window.addEventListener("resize", renderOverlay);

  window.addEventListener("keydown", (e) => { if (e.key === "Alt") { altOn = true; renderOverlay(); } });
  window.addEventListener("keyup", (e) => { if (e.key === "Alt") { altOn = false; renderOverlay(); } });
  document.getElementById("reset").addEventListener("click", reset);
  setStatus();

  // ---- harness contract (3.0b superset) ----------------------------------
  window.__spike = {
    ready: true, candidate: "B-3b",
    grab: () => beginGrab(),
    moveToGhost: (i) => { const g = model.ghosts[i]; return moveTo(g.startMs, g.row); },
    moveToTime: (iso, opts = {}) => { altOn = !!opts.alt; return moveTo(ms(iso), opts.row ?? model.grab.row); },
    moveToRow: (row, iso) => moveTo(iso ? ms(iso) : (committed?.time ?? model.grab.startMs), row),
    setAlt: (v) => { altOn = !!v; renderOverlay(); },
    drop: () => drop(),
    reset: () => reset(),
    getState: () => ({ phase, tentative, latency, refused, committed, onMovingCount, magnetSamples }),
    // C1 machine check: the TRUE drift test — overlay label center-x vs the
    // actual vis-RENDERED ghost bar center-x (not vs our own math). If the
    // overlay tracks vis's transform, these align at any zoom/pan.
    overlayProbe: () => {
      const win = timeline.getWindow();
      const base = timeline.dom.centerContainer.getBoundingClientRect();
      const width = timeline.dom.centerContainer.offsetWidth;
      const rects = groupRects();
      // all vis-rendered ghost bars, with their center x/y (relative to center).
      const visGhosts = Array.from(document.querySelectorAll(".vis-item.ghostitem")).map((el) => {
        const r = el.getBoundingClientRect();
        return { cx: (r.left + r.width / 2) - base.left, cy: (r.top + r.height / 2) - base.top };
      });
      const overlayLbls = Array.from(overlayEl.querySelectorAll(".spk-ghostlbl")).map((el) => {
        const r = el.getBoundingClientRect();
        return { cx: (r.left + r.width / 2) - base.left, cy: (r.top + r.height / 2) - base.top, text: el.textContent };
      });
      const out = [];
      for (let i = 0; i < model.ghosts.length; i++) {
        const g = model.ghosts[i];
        const rc = rects[g.row];
        const rowCy = rc ? rc.top + rc.height / 2 : null;
        // match vis ghost bar + overlay label to this ghost's row by center-y.
        const bar = rowCy == null ? null : visGhosts.filter((b) => Math.abs(b.cy - rowCy) < (rc.height / 2 + 4)).sort((a, b) => a.cy - b.cy)[0] || null;
        const lbl = rowCy == null ? null : overlayLbls.filter((b) => Math.abs(b.cy - rowCy) < (rc.height / 2 + 10)).sort((a, b) => a.cy - b.cy)[0] || null;
        out.push({
          ghost: i, row: g.row,
          label: lbl ? lbl.text : null,
          legible: !!lbl && (lbl.text || "").length >= 3,
          visBarCx: bar ? +bar.cx.toFixed(1) : null,
          labelCx: lbl ? +lbl.cx.toFixed(1) : null,
          driftPx: (bar && lbl) ? +Math.abs(lbl.cx - bar.cx).toFixed(1) : null,
        });
      }
      return { window: { start: win.start.toISOString(), end: win.end.toISOString() }, width, ghosts: out };
    },
    zoomTo: (startIso, endIso) => { timeline.setWindow(new Date(startIso), new Date(endIso), { animation: false }); renderOverlay(); return true; },
    getWindow: () => { const w = timeline.getWindow(); return { start: w.start.toISOString(), end: w.end.toISOString() }; },
    // C3 isolated-magnet probe: falloff strength to ONE specific anchor time
    // (not nearest-of-all-targets) — the honest "one real magnet" measurement.
    magnetTo: (rawIso, anchorIso) => {
      const raw = ms(rawIso), anchor = ms(anchorIso);
      const tolMs = (7 / 14) * 3600000; // magnetPx / pxPerHour hours -> ms
      const d = Math.abs(anchor - raw);
      return { d_min: +(d / 60000).toFixed(1), strength: d > tolMs ? 0 : +(1 - d / tolMs).toFixed(3), inTolerance: d <= tolMs };
    },
    // C3 granularity probe: does vis THROTTLE onMoving, or fire per pointer-move?
    // Counter is reset at grab; the harness compares calls to steps it emitted.
    onMovingCount: () => onMovingCount,
  };
}

main();

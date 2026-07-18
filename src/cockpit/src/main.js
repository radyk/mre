// Cockpit entry point (docs/07 Phase 3 interim-A). Resolves the schedule,
// fetches its contract-1.2 document + certificate grade, renders the board and
// the ask panel, and paints the top strip (version + grade). Read-only.
import "./cockpit.css";
import {
  CONFIG, resolveScheduleId, getSchedule, getScheduleMeta, resolveSuccessor,
  listSchedules,
} from "./api.js";
import { createBoard } from "./board.js";
import { createAskPanel } from "./askpanel.js";
import { wireInteraction } from "./interaction.js";
import { mountDevLedger } from "./devledger.js";
import { findNewerSchedule } from "./freshness.js";

// Rewrite the address bar to bind the given schedule version WITHOUT a reload
// (session 3.8 CU1): a live accept/publish stays in the same session, but the
// URL must name the version the board IS, so a reload never re-binds a
// now-superseded id. Other query params (api, ask) are preserved.
function setUrlSchedule(id) {
  const url = new URL(location.href);
  url.searchParams.set("schedule", id);
  history.replaceState(null, "", url);
}

// Navigate the cockpit to a different version with a full reload (session 3.8
// CU3): used for "view current" on a superseded deep link and for the live 409
// self-heal — a clean reload guarantees fresh board/interaction/ask state bound
// to the successor, never a half-rebound zombie.
function jumpToVersion(id) {
  const url = new URL(location.href);
  url.searchParams.set("schedule", id);
  location.assign(url.toString());
}

const GRADE_CLASS = {
  ACCEPTED: "g-c1", CONDITIONAL: "g-conditional", REJECTED: "g-rejected",
  C1: "g-c1", C2: "g-c2", C3: "g-c3", C0: "g-c0",
};

// Theme (Session 4.1): light is the shipped default; dark is an option. The
// attribute is stamped pre-paint by the head script in index.html (no flash);
// here we keep it in sync with the URL + localStorage and expose a chrome
// toggle. Theme choice is a tier-2-class preference — a per-deployment default
// when that layer lands; a URL/config param + this toggle for now.
function currentTheme() {
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}
function paintThemeToggle(btn, theme) {
  const to = theme === "dark" ? "light" : "dark";
  btn.textContent = theme === "dark" ? "☾ dark" : "☀ light";
  btn.title = `switch to ${to} theme`;
  btn.setAttribute("aria-label", `theme: ${theme}. switch to ${to}`);
}
function applyTheme(t) {
  const theme = t === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", theme);
  try { localStorage.setItem("mre-theme", theme); } catch { /* private mode */ }
  const url = new URL(location.href);
  url.searchParams.set("theme", theme);
  history.replaceState(null, "", url);
  const btn = document.getElementById("theme-toggle");
  if (btn) paintThemeToggle(btn, theme);
  if (window.__cockpit) window.__cockpit.theme = theme;
  return theme;
}
function toggleTheme() { return applyTheme(currentTheme() === "dark" ? "light" : "dark"); }

function paintTopStrip(el, doc, meta) {
  const shortId = doc.schedule_id.slice(0, 8);
  const grade = meta?.grade || "—";
  const costing = meta?.costing_grade ? ` / ${meta.costing_grade}` : "";
  const gcls = GRADE_CLASS[(meta?.grade || "").toUpperCase()] || "g-c0";
  el.innerHTML = `
    <span class="brand">Reasoning Cockpit</span>
    <span class="ver">contract ${doc.contract_version} · ${shortId}</span>
    <span class="status">${doc.status}</span>
    <span class="grade ${gcls}"><span class="lbl">certificate</span> ${grade}${costing}</span>
    <button class="theme-toggle" id="theme-toggle"></button>`;
  // the toggle is recreated on every repaint (version change too) — (re)bind it.
  const btn = el.querySelector("#theme-toggle");
  paintThemeToggle(btn, currentTheme());
  btn.addEventListener("click", toggleTheme);
}

// A read-only banner shown when the loaded schedule has been superseded
// (session 3.8 CU3): planner language + a one-click jump to the current
// version, never a raw "superseded" error and never an editable zombie board.
function supersededBanner(hostEl, successorId) {
  const el = document.createElement("div");
  el.className = "superseded-banner";
  el.id = "superseded-banner";
  const shortSucc = successorId ? successorId.slice(0, 8) : null;
  el.innerHTML = shortSucc
    ? `<span class="sb-msg">This plan was replaced by a newer version.</span>
       <button class="sb-jump" id="sb-jump">View current (${shortSucc}) →</button>
       <span class="sb-ro">read-only</span>`
    : `<span class="sb-msg">This plan has been superseded and is read-only.</span>
       <span class="sb-ro">read-only</span>`;
  hostEl.prepend(el);
  if (successorId) {
    el.querySelector("#sb-jump").addEventListener("click", () => jumpToVersion(successorId));
  }
  return el;
}

// The board chrome row (Session 4.3 CU1/CU5): the legend (left) + a right cluster
// holding a first-load "Ctrl+scroll to zoom" hint, the +/− zoom controls, and
// (dev only) the question-ledger dock. ONE structural row, so nothing floats over
// the legend or the ask column at any width (the SECOND occlusion incident). The
// legend is visible by default on first load (CU4). Returns { chrome, right } —
// the dev ledger docks into `right`.
function mountBoardChrome(boardHost, board) {
  const host = boardHost.parentElement;            // .board-host (position: relative)
  const chrome = document.createElement("div");
  chrome.className = "board-chrome";

  const lg = document.createElement("div");
  lg.className = "legend";
  // Two groups: the lateness signal on the bars, and the capacity-state
  // backgrounds (Session 4.2 CU1). A hatched swatch marks the hatched bands.
  lg.innerHTML = `
    <span><span class="sw" style="background: var(--bar-ontime)"></span>on time / early</span>
    <span><span class="sw" style="background: var(--bar-tight)"></span>tight</span>
    <span><span class="sw" style="background: var(--bar-late)"></span>late</span>
    <span class="lg-gap"></span>
    <span><span class="sw" style="background: var(--cap-offshift)"></span>off shift</span>
    <span><span class="sw sw-hatch-closure"></span>closure</span>
    <span><span class="sw sw-hatch-maint"></span>maintenance</span>
    <span><span class="sw" style="background: var(--cap-overtime); border:1px solid var(--standing-pin-edge)"></span>overtime</span>
    <span><span class="sw" style="background: var(--cap-openidle)"></span>open · idle</span>
    <span class="lg-gap"></span>
    <span><span class="sw sw-now"></span>now</span>
    <span><span class="sw" style="background: var(--cite-bar)"></span>cited</span>`;
  chrome.appendChild(lg);

  const right = document.createElement("div");
  right.className = "bc-right";

  // CU5: a first-load hint naming the trackpad-free zoom gesture; fades out so it
  // never becomes permanent chrome.
  const hint = document.createElement("div");
  hint.className = "board-hint";
  hint.id = "board-hint";
  hint.textContent = "Ctrl+scroll to zoom";
  right.appendChild(hint);
  setTimeout(() => hint.classList.add("fade"), 6000);
  setTimeout(() => { if (hint.isConnected) hint.remove(); }, 6600);

  // CU5: the +/− zoom controls (pointer/keyboard path; Ctrl+wheel unchanged).
  const zoom = document.createElement("div");
  zoom.className = "board-zoom";
  zoom.innerHTML = `
    <button type="button" class="bz-out" aria-label="zoom out" title="zoom out">−</button>
    <button type="button" class="bz-in" aria-label="zoom in" title="zoom in">+</button>`;
  zoom.querySelector(".bz-in").addEventListener("click", () => board.zoomIn());
  zoom.querySelector(".bz-out").addEventListener("click", () => board.zoomOut());
  right.appendChild(zoom);

  chrome.appendChild(right);
  host.appendChild(chrome);
  return { chrome, right };
}

// A dismissible "a newer schedule exists" info bar (Session 4.3 CU6): the bound
// version is valid but stale — a newer solve of the same submission exists. One
// click jumps; a dismiss keeps the current view. Distinct from the superseded
// banner (that version is dead; this one is merely older).
function newerBanner(hostEl, newId) {
  const el = document.createElement("div");
  el.className = "superseded-banner newer";
  el.id = "newer-banner";
  const short = (newId || "").slice(0, 8);
  el.innerHTML = `
    <span class="sb-msg">A newer schedule exists.</span>
    <button class="sb-jump" id="newer-jump">Open it (${short}) →</button>
    <button class="sb-dismiss" id="newer-dismiss" title="stay on this version">✕</button>`;
  hostEl.prepend(el);
  el.querySelector("#newer-jump").addEventListener("click", () => jumpToVersion(newId));
  el.querySelector("#newer-dismiss").addEventListener("click", () => el.remove());
  return el;
}

async function boot() {
  const app = document.getElementById("app");
  const strip = document.getElementById("topstrip");
  const boardHost = document.getElementById("tl");
  const askRoot = document.getElementById("ask");
  try {
    // The URL param is authoritative over the head-script's early stamp, and
    // syncs it back to localStorage + the URL (Session 4.1).
    applyTheme(CONFIG.theme || currentTheme());
    const id = await resolveScheduleId();
    const [doc, meta] = await Promise.all([getSchedule(id), getScheduleMeta(id)]);
    // The URL must always name the version the board IS — even a deep link that
    // resolved via the listing (no ?schedule=) gets its id stamped in, so a
    // later live rebind + reload stay coherent (session 3.8 CU1).
    setUrlSchedule(id);
    paintTopStrip(strip, doc, meta);
    const board = createBoard(boardHost, doc);
    const chrome = mountBoardChrome(boardHost, board);

    // A deep link to a SUPERSEDED version loads read-only behind a banner that
    // offers the current version (session 3.8 CU3) — never a raw error, never an
    // editable zombie. The gesture surface (which would 409 every drop against
    // reality) is deliberately NOT wired.
    const superseded = meta && meta.status === "superseded";

    // The live self-heal (session 3.8 CU3): any editing/asking call that 409s
    // "superseded" means a stale reference slipped through — resolve the live
    // successor and jump to it (a clean reload) rather than dead-ending.
    const onSuperseded = async (staleId) => {
      const succ = await resolveSuccessor(staleId || window.__cockpit.scheduleId);
      if (succ) jumpToVersion(succ);
      return succ;
    };

    // The dev build asks the API to use the LLM renderer (fails closed to the
    // template when no ANTHROPIC_API_KEY / on validation failure). The
    // production `vite build` the harness serves has DEV=false → always template.
    const panel = createAskPanel(askRoot, board, id, {
      useLlm: !!import.meta.env?.DEV, onSuperseded,
    });

    // harness + demo hook (read-only): drive the sixty-second script's first
    // frame from the URL (?ask=...) and expose probes for the screenshot tests.
    window.__cockpit = {
      ready: true,
      scheduleId: id,
      superseded: !!superseded,
      theme: currentTheme(),
      getTheme: currentTheme,
      setTheme: applyTheme,
      toggleTheme,
      board, panel,
      ask: (q) => panel.run(q),
      select: (opRef) => board.select(opRef),
      highlight: (refs) => board.highlight(refs),
      clearHighlight: () => board.clearHighlight(),
      setWindow: (a, b) => board.setWindow(a, b),
      getWindow: () => board.getWindow(),
      overlayProbe: () => board.overlayProbe(),
      jumpToVersion,
      doc, meta,
    };

    // CU6: expose the real dev-ledger mount for the harness (which serves the
    // production build, so the auto-mount below is skipped) — a debug seam on the
    // existing harness object, never auto-invoked in production.
    window.__cockpit.mountDevLedger = () => mountDevLedger(chrome.right);

    if (superseded) {
      supersededBanner(app, meta.successor_id || null);
      window.__cockpit.successorId = meta.successor_id || null;
    } else {
      // CU6: a stale tab should notice a newer solve of the same submission —
      // offer a one-click jump. Only for a live (non-superseded) version; the
      // listing is background work, so a failure never blocks the board.
      listSchedules().then(({ schedules }) => {
        const newerId = findNewerSchedule(id, schedules || []);
        if (newerId && newerId !== id) {
          newerBanner(app, newerId);
          window.__cockpit.newerId = newerId;
        }
      }).catch(() => {});
      // Fetch the Tier-0 interaction payload in the BACKGROUND, after first
      // paint (R-T1d) — the board is already interactive read-only; the 3.2b
      // gesture surface stands up when it arrives. Never blocks render or ask.
      // The dev build (vite dev / non-production) also mounts the feel tuning
      // panel (CU6). import.meta.env.DEV is true under `vite` and false in the
      // production `vite build` the harness serves — so tuning never ships.
      wireInteraction(id, board, window.__cockpit, {
        doc, devMode: !!import.meta.env?.DEV, onSuperseded,
        // An accepted/published edit rebinds the cockpit to the new version FULLY
        // (session 3.8 CU1): the address bar, the strip (new id + live status),
        // the ask panel target, the shared selection, and the harness hook all
        // follow the version the board now IS. No user action may be issued
        // against a superseded id from a live session.
        onVersionChange: async (newId, status) => {
          setUrlSchedule(newId);
          panel.setScheduleId(newId);
          panel.clearSelection();            // a moved op's old scope is stale
          window.__cockpit.scheduleId = newId;
          const nextMeta = await getScheduleMeta(newId).catch(() => meta);
          const nextDoc = board.currentDoc ? board.currentDoc() : doc;
          paintTopStrip(strip, { ...nextDoc, status }, nextMeta);
          window.__cockpit.versionChanged = { id: newId, status };
        },
      });
    }

    // The refusal-cluster dev panel (CU3, R-AI1(d)) — DEV-build-only, like the
    // feel tuning panel. Reads the DEV-gated /ledger/refusals; absent in the
    // production build the harness serves.
    if (import.meta.env?.DEV) mountDevLedger(chrome.right);

    if (CONFIG.autoAsk) panel.run(CONFIG.autoAsk);
  } catch (e) {
    app.querySelector(".split")?.remove();
    const err = document.createElement("div");
    err.className = "err";
    err.textContent = `cockpit could not load: ${e.message || e}`;
    app.appendChild(err);
    window.__cockpit = { ready: true, error: String(e.message || e) };
  }
}

boot();

// Cockpit entry point (docs/07 Phase 3 interim-A). Resolves the schedule,
// fetches its contract-1.2 document + certificate grade, renders the board and
// the ask panel, and paints the top strip (version + grade). Read-only.
import "./cockpit.css";
import {
  CONFIG, resolveScheduleId, getSchedule, getScheduleMeta, resolveSuccessor,
} from "./api.js";
import { createBoard } from "./board.js";
import { createAskPanel } from "./askpanel.js";
import { wireInteraction } from "./interaction.js";
import { mountDevLedger } from "./devledger.js";

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

function paintTopStrip(el, doc, meta) {
  const shortId = doc.schedule_id.slice(0, 8);
  const grade = meta?.grade || "—";
  const costing = meta?.costing_grade ? ` / ${meta.costing_grade}` : "";
  const gcls = GRADE_CLASS[(meta?.grade || "").toUpperCase()] || "g-c0";
  el.innerHTML = `
    <span class="brand">Reasoning Cockpit</span>
    <span class="ver">contract ${doc.contract_version} · ${shortId}</span>
    <span class="status">${doc.status}</span>
    <span class="grade ${gcls}"><span class="lbl">certificate</span> ${grade}${costing}</span>`;
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

function legend(hostEl) {
  const el = document.createElement("div");
  el.className = "legend";
  el.innerHTML = `
    <span><span class="sw" style="background: var(--bar-ontime)"></span>on time / early</span>
    <span><span class="sw" style="background: var(--bar-tight)"></span>tight</span>
    <span><span class="sw" style="background: var(--bar-late)"></span>late</span>
    <span><span class="sw" style="background: var(--cal-closure)"></span>closure</span>
    <span><span class="sw" style="background: var(--cite-bar)"></span>cited by the answer</span>`;
  hostEl.appendChild(el);
}

async function boot() {
  const app = document.getElementById("app");
  const strip = document.getElementById("topstrip");
  const boardHost = document.getElementById("tl");
  const askRoot = document.getElementById("ask");
  try {
    const id = await resolveScheduleId();
    const [doc, meta] = await Promise.all([getSchedule(id), getScheduleMeta(id)]);
    // The URL must always name the version the board IS — even a deep link that
    // resolved via the listing (no ?schedule=) gets its id stamped in, so a
    // later live rebind + reload stay coherent (session 3.8 CU1).
    setUrlSchedule(id);
    paintTopStrip(strip, doc, meta);
    const board = createBoard(boardHost, doc);
    legend(boardHost.parentElement);

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

    if (superseded) {
      supersededBanner(app, meta.successor_id || null);
      window.__cockpit.successorId = meta.successor_id || null;
    } else {
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
    if (import.meta.env?.DEV) mountDevLedger(app);

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

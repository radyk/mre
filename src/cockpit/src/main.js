// Cockpit entry point (docs/07 Phase 3 interim-A). Resolves the schedule,
// fetches its contract-1.2 document + certificate grade, renders the board and
// the ask panel, and paints the top strip (version + grade). Read-only.
import "./cockpit.css";
import { CONFIG, resolveScheduleId, getSchedule, getScheduleMeta } from "./api.js";
import { createBoard } from "./board.js";
import { createAskPanel } from "./askpanel.js";
import { wireInteraction } from "./interaction.js";

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
    paintTopStrip(strip, doc, meta);
    const board = createBoard(boardHost, doc);
    legend(boardHost.parentElement);
    // The dev build asks the API to use the LLM renderer (fails closed to the
    // template when no ANTHROPIC_API_KEY / on validation failure). The
    // production `vite build` the harness serves has DEV=false → always template.
    const panel = createAskPanel(askRoot, board, id, { useLlm: !!import.meta.env?.DEV });

    // harness + demo hook (read-only): drive the sixty-second script's first
    // frame from the URL (?ask=...) and expose probes for the screenshot tests.
    window.__cockpit = {
      ready: true,
      scheduleId: id,
      board, panel,
      ask: (q) => panel.run(q),
      select: (opRef) => board.select(opRef),
      highlight: (refs) => board.highlight(refs),
      clearHighlight: () => board.clearHighlight(),
      setWindow: (a, b) => board.setWindow(a, b),
      getWindow: () => board.getWindow(),
      overlayProbe: () => board.overlayProbe(),
      doc, meta,
    };

    // Fetch the Tier-0 interaction payload in the BACKGROUND, after first
    // paint (R-T1d) — the board is already interactive read-only; the 3.2b
    // gesture surface stands up when it arrives. Never blocks render or ask.
    // The dev build (vite dev / non-production) also mounts the feel tuning
    // panel (CU6). import.meta.env.DEV is true under `vite` and false in the
    // production `vite build` the harness serves — so tuning never ships.
    wireInteraction(id, board, window.__cockpit, {
      doc, devMode: !!import.meta.env?.DEV,
    });

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

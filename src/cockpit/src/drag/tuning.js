// The tuning panel (CU6) — DEV-BUILD-ONLY. The instrument for the feel
// iteration: every numeric feel token (snap radii, magnet falloff, ghost
// opacity, tentative pulse, trace styling, sandbox budget) exposed as a live
// control that hot-reloads the surface the moment it changes, plus an export
// that writes the tuned values back out. Daryn plays this; prompts don't
// (docs/07 Phase 3). It never ships in a production build — mount() no-ops
// unless import.meta.env.DEV (the caller checks) — so it cannot leak feel
// knobs into the planner's cockpit.
//
// It edits the ONE mutable feel object the controller reads (feel.js), calls
// applyFeel() to mirror the CSS-visible subset onto :root, and redraw() so an
// active gesture re-renders instantly. Export prints a paste-ready feel
// overrides object (and offers a download) — the bridge from "felt right" to a
// committed token change.

import { applyFeel } from "./feel.js";

// [path, label, min, max, step] — path is dot-notation into the feel object.
const CONTROLS = [
  ["snap.ghost_px", "snap · ghost", 0, 60, 1],
  ["snap.calendar_px", "snap · calendar", 0, 60, 1],
  ["snap.adjacency_px", "snap · adjacency", 0, 60, 1],
  ["snap.predecessor_px", "snap · predecessor", 0, 60, 1],
  ["snap.grid_px", "snap · grid", 0, 40, 1],
  ["snap.grid_step_min", "grid step (min)", 5, 120, 5],
  ["snap.falloff", "magnet falloff", 0.5, 3, 0.1],
  ["shade.green_opacity", "shade · legal (green)", 0, 1, 0.02],
  ["shade.dim_opacity", "shade · forbidden (dim)", 0, 1, 0.02],
  ["ghost.opacity", "ghost opacity", 0, 1, 0.02],
  ["ghost.infeasible_opacity", "infeasible opacity", 0, 1, 0.02],
  ["tentative.pulse_ms", "tentative pulse (ms)", 300, 2500, 50],
  ["trace.width_px", "trace width", 1, 6, 0.5],
  ["trace.ghost_of_old_opacity", "ghost-of-old opacity", 0, 1, 0.02],
  ["sandbox.budget_s", "sandbox budget (s)", 1, 60, 1],
];

const get = (obj, path) => path.split(".").reduce((o, k) => o?.[k], obj);
const set = (obj, path, v) => {
  const ks = path.split("."); const last = ks.pop();
  ks.reduce((o, k) => o[k], obj)[last] = v;
};

export function mountTuningPanel(hostEl, controller) {
  const feel = controller.feel;
  const panel = document.createElement("div");
  panel.className = "tuning-panel collapsed";
  panel.innerHTML = `
    <div class="tp-head"><button class="tp-toggle" title="feel tuning (dev only)">⚙ feel</button>
      <span class="tp-title">feel tuning · dev</span>
      <button class="tp-export" title="print + download the tuned feel overrides">export</button></div>
    <div class="tp-body"></div>`;
  const body = panel.querySelector(".tp-body");

  for (const [path, label, min, max, step] of CONTROLS) {
    const row = document.createElement("label");
    row.className = "tp-row";
    const val = get(feel, path);
    row.innerHTML = `<span class="tp-label">${label}</span>
      <input type="range" min="${min}" max="${max}" step="${step}" value="${val}">
      <output>${val}</output>`;
    const input = row.querySelector("input");
    const out = row.querySelector("output");
    input.addEventListener("input", () => {
      const v = parseFloat(input.value);
      set(feel, path, v);
      out.textContent = String(v);
      applyFeel(feel);
      controller.redraw();
    });
    body.appendChild(row);
  }

  panel.querySelector(".tp-toggle").addEventListener("click",
    () => panel.classList.toggle("collapsed"));
  panel.querySelector(".tp-export").addEventListener("click", () => exportFeel(feel));
  hostEl.appendChild(panel);
  return panel;
}

// Print a paste-ready overrides object (only the values that differ from the
// control defaults are worth pasting, but we emit the full feel for clarity)
// and offer it as a download — the bridge to a committed tokens change.
function exportFeel(feel) {
  const json = JSON.stringify(feel, null, 2);
  // eslint-disable-next-line no-console
  console.log("[feel] tuned tokens (paste into makeFeel overrides or tokens):\n" + json);
  try {
    const blob = new Blob([json], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "feel.tokens.json";
    a.click();
    URL.revokeObjectURL(a.href);
  } catch { /* headless / no DOM download — the console print is the fallback */ }
}

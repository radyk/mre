// Feel tokens — the NUMERIC interaction-feel knobs the tuning panel (CU6) edits
// live. Visual tokens (colors, the citation glow) stay in tokens.css; these are
// the *behavioral* numbers gesture/magnets/sandbox read: snap radii, per-anchor
// magnet strength, ghost opacity, tentative pulse, trace styling, the sandbox
// budget mirror. One mutable object, one source of truth — Daryn plays this,
// prompts don't (docs/07 Phase 3, "design tokens externalized from day one").
//
// The subset that is also a CSS custom property (opacity, pulse, trace width)
// is mirrored to :root by applyFeel() so CSS and JS never disagree.

export const DEFAULT_FEEL = {
  // --- magnet snap (R-DP3): per-anchor-type capture radius in PIXELS, and a
  // falloff exponent shaping how strongly the bar is pulled inside the radius.
  // Ghost placements are the strongest target; coarse grid is the fallback. ---
  snap: {
    ghost_px: 26,          // strongest — a solved, vouched-for placement
    calendar_px: 16,       // a working-window opening edge
    adjacency_px: 14,      // a neighbour bar's leading/trailing edge
    predecessor_px: 14,    // the precedence/release floor
    grid_px: 8,            // coarse time-grid fallback in open space
    grid_step_min: 30,     // the fallback grid resolution (minutes)
    falloff: 1.6,          // >1 = softer approach, harder final click
  },
  // --- ghosts (CU2) ---
  ghost: {
    opacity: 0.42,
    infeasible_opacity: 0.3,
    label_min_px: 3,       // min bar width to keep an in-bar label (overlay else)
  },
  // --- tentative bar (CU4, R-DP7a) ---
  tentative: {
    pulse_ms: 1100,        // the breathing-highlight period while awaiting verdict
    hatch_px: 6,           // hatch stripe pitch
  },
  // --- change traces (CU5, R-DP7) ---
  trace: {
    width_px: 2,
    ghost_of_old_opacity: 0.28,
    dash: "4 3",
  },
  // --- sandbox (CU4, R-T1c) — a UI mirror of the server-side budget token so
  // the countdown matches the wait. The server budget is authoritative; this
  // only paces the countdown animation. ---
  sandbox: {
    budget_s: 15.0,
    countdown_tick_ms: 100,
  },
};

// Deep-clone so each session gets its own mutable copy (the tuning panel edits
// this; a shared frozen default would be a footgun).
export function makeFeel(overrides) {
  const f = structuredClone(DEFAULT_FEEL);
  if (overrides) deepMerge(f, overrides);
  return f;
}

function deepMerge(dst, src) {
  for (const k of Object.keys(src)) {
    if (src[k] && typeof src[k] === "object" && !Array.isArray(src[k])) {
      dst[k] = dst[k] || {};
      deepMerge(dst[k], src[k]);
    } else {
      dst[k] = src[k];
    }
  }
  return dst;
}

// Mirror the CSS-visible feel numbers onto :root as custom properties so the
// stylesheet (drag.css) reads the same live values the tuning panel changes.
export function applyFeel(feel, root = document.documentElement) {
  const s = root.style;
  s.setProperty("--ghost-opacity", String(feel.ghost.opacity));
  s.setProperty("--ghost-infeasible-opacity", String(feel.ghost.infeasible_opacity));
  s.setProperty("--tentative-pulse-ms", `${feel.tentative.pulse_ms}ms`);
  s.setProperty("--tentative-hatch-px", `${feel.tentative.hatch_px}px`);
  s.setProperty("--trace-width-px", `${feel.trace.width_px}px`);
  s.setProperty("--trace-ghost-opacity", String(feel.trace.ghost_of_old_opacity));
}

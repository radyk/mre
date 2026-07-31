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
  // --- Tier-0 shading emphasis (CU5) — separate opacity multipliers for the
  // legal (green) zones and the forbidden (dim) wash. On a busy board most rows
  // are legitimately green, so the wash reads as noise; the defaults deliberately
  // let the dim + ghosts dominate over green (green damped, dim at full). Daryn
  // tunes these live; the inversion decision (emphasize forbidden) waits on his
  // verdict with the knobs. ---
  shade: {
    green_opacity: 0.5,    // legal-zone green, damped so it doesn't wash out
    dim_opacity: 1.0,      // forbidden-zone dim, full strength (dominates)
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
  // --- sandbox (CU4, R-T1c) — the budget the cockpit asks for AND the pace of
  // its countdown. NOTE (Session 4B.23): the old comment here said the server
  // budget was authoritative and this only animated a bar. That is not what the
  // code does — `_beatTwo` SENDS this value as `budget_s`, and the API honours
  // whatever the request carries, falling back to its own token only when the
  // field is absent. This number is therefore the real budget of every drag. ---
  sandbox: {
    // 15.0 until Session 4B.23. MEASURED on the dense demo board
    // (rolling-c9973708-865, 386 bars, 345 active), same pin every time:
    //
    //     budget 15s -> no_verdict  UNKNOWN   (stops at ~11s, prices nothing)
    //     budget 25s -> FEASIBLE    +$2,596.67
    //     budget 40s -> FEASIBLE    +$2,596.67
    //     budget 60s -> FEASIBLE    +$2,596.67
    //
    // 15s was calibrated on boards a seventh this size; at demo density it does
    // not reach a priceable answer, and the planner's reward for waiting the
    // full budget was "couldn't verify this placement in time". 4B.22a got its
    // card at a wall of 15.01s — right at the edge — which is why the same
    // gesture priced from a quiet script and returned nothing from a browser.
    //
    // THE BUDGET IS A CEILING, NOT A SPEND. A solve that PROVES its verdict
    // returns immediately (1.3s on the 56-bar pinned world, unchanged by this),
    // so raising it lengthens only the cases that were already failing. What it
    // costs is the worst case: ~30s to price a drag on a 386-bar board. That is
    // a real cost and it is named in docs/closeouts/4B.23.md rather than hidden.
    budget_s: 30.0,
    countdown_tick_ms: 100,
    // R-T2 beat one (Session 4B.3b): the small feasibility budget the ghost
    // paces against (server-authoritative FEASIBILITY_BUDGET_S; this only paces
    // the "pricing…" ghost's animation).
    feasibility_budget_s: 2.0,
    // R-T2 beat-two card: whether the DETAIL layer (cost decomposition +
    // operational consequences) starts expanded. The always-visible layer is
    // decision-sufficient on its own; this is a feel token (Daryn tunes it).
    detail_open: false,
    // R-T2(3): the ghost→priced-card supersession is a PERCEIVABLE transition
    // (ms). Motion tuned here, never by prompts.
    supersede_ms: 260,
  },
  // --- bar geometry (Session 3.5 token pass) — the board bar corner radius,
  // mirrored to --bar-radius so ghosts/carry/traces stay visually consistent. ---
  bars: {
    radius_px: 4,
  },
  // --- R-M1 motion (docs/04 R-M1 — MOTION CARRIES REGISTER). NAMED-BUT-
  // UNCONSUMED this session: Session 3.6 implements the animations against
  // these. The values are panel-tunable NOW (mirrored to --motion-* by
  // applyFeel) so 3.6 builds against a live surface. Semantics are FIXED by the
  // ruling; only the numbers iterate on busy_board. ---
  motion: {
    reject_dur_ms: 200,          // (a) return-home snap-back — fast, no settling
    reject_shake_amp_px: 3,      // (a) the brief "board refused" shake amplitude
    reject_shake_dur_ms: 140,    // (a) shake duration
    reflow_dur_ms: 340,          // (b) other bars, simultaneous eased transition
    reflow_highlight_dur_ms: 600, // (b) moved-bar highlight linger
    pinlock_dur_ms: 220,         // (c) committed drop pin-lock effect
    ghost_fade_dur_ms: 350,      // (d) ghost fade in/out (labels fade WITH bars)
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
  s.setProperty("--shade-green-opacity", String(feel.shade.green_opacity));
  s.setProperty("--shade-dim-opacity", String(feel.shade.dim_opacity));
  s.setProperty("--ghost-opacity", String(feel.ghost.opacity));
  s.setProperty("--ghost-infeasible-opacity", String(feel.ghost.infeasible_opacity));
  s.setProperty("--tentative-pulse-ms", `${feel.tentative.pulse_ms}ms`);
  s.setProperty("--tentative-hatch-px", `${feel.tentative.hatch_px}px`);
  s.setProperty("--trace-width-px", `${feel.trace.width_px}px`);
  s.setProperty("--trace-ghost-opacity", String(feel.trace.ghost_of_old_opacity));
  // bar geometry (3.5 token pass)
  if (feel.bars) s.setProperty("--bar-radius", `${feel.bars.radius_px}px`);
  // R-T2 (4B.3b): the ghost→priced-card supersession transition (R-T2(3)).
  if (feel.sandbox && feel.sandbox.supersede_ms != null)
    s.setProperty("--sandbox-supersede", `${feel.sandbox.supersede_ms}ms`);
  // R-M1 motion tokens (unconsumed until 3.6, but panel-tunable now — mirroring
  // them here is what makes the surface live for the 3.6 implementation).
  if (feel.motion) {
    const m = feel.motion;
    s.setProperty("--motion-reject-dur", `${m.reject_dur_ms}ms`);
    s.setProperty("--motion-reject-shake-amp", `${m.reject_shake_amp_px}px`);
    s.setProperty("--motion-reject-shake-dur", `${m.reject_shake_dur_ms}ms`);
    s.setProperty("--motion-reflow-dur", `${m.reflow_dur_ms}ms`);
    s.setProperty("--motion-reflow-highlight-dur", `${m.reflow_highlight_dur_ms}ms`);
    s.setProperty("--motion-pinlock-dur", `${m.pinlock_dur_ms}ms`);
    s.setProperty("--motion-ghost-fade-dur", `${m.ghost_fade_dur_ms}ms`);
  }
}

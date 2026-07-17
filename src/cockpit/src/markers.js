// Time-anchor markers overlay (docs/07 Session 4.2 CU2) + shift-boundary ticks
// (CU1). A positioned layer inside vis's centerContainer — the same always-on
// overlay discipline the citation tags use (board.js) — carrying VERTICAL lines
// at canonical times that track vis's pan/zoom at 0px drift.
//
//   now       the run's reference date (the 3.3b epoch, NOT wall clock) — the
//             "you are here" line. Absent when the run is "now"-anchored
//             (reference_date null): we do NOT fall back to wall clock, because a
//             wall-clock "now" on a fixed-epoch schedule is a lie.
//   due       the SELECTED/hovered order's due date (CU2 — only when scoped).
//   release   the SELECTED/hovered order's release floor (CU2 — only when scoped).
//   shift     subtle ticks at shift-start/end boundaries (CU1).
//
// Times → x via vis's own body.util.toScreen (the geometry module's timeToX),
// so a version bump that broke the axis surfaces as marker drift, not a silent
// mis-draw. Read-only: it draws, never edits.

const clsSafe = (t) => (t == null ? null : Date.parse(t));

export function createMarkers(timeline) {
  const overlay = document.createElement("div");
  overlay.className = "marker-overlay";
  timeline.dom.centerContainer.appendChild(overlay);

  let nowMs = null;              // reference-date line (persistent)
  let order = null;             // {due, release, label} for the scoped order
  let shiftTicks = [];          // ms boundaries

  const toX = (ms) => {
    try { return timeline.body.util.toScreen(new Date(ms)); } catch { return null; }
  };
  const width = () => timeline.dom.centerContainer.getBoundingClientRect().width;

  function line(cls, ms, label) {
    const x = toX(ms);
    if (x == null || x < -2 || x > width() + 2) return;
    const el = document.createElement("div");
    el.className = `marker ${cls}`;
    el.style.left = `${x}px`;
    if (label) {
      const tag = document.createElement("span");
      tag.className = "marker-label";
      tag.textContent = label;
      el.appendChild(tag);
    }
    overlay.appendChild(el);
  }

  function redraw() {
    overlay.querySelectorAll(".marker, .tick").forEach((n) => n.remove());
    // shift ticks first (behind the semantic markers).
    for (const t of shiftTicks) {
      const x = toX(t);
      if (x == null || x < -1 || x > width() + 1) continue;
      const el = document.createElement("div");
      el.className = "tick shift";
      el.style.left = `${x}px`;
      overlay.appendChild(el);
    }
    if (order) {
      if (order.release != null) line("release", order.release, `release · ${order.label}`);
      if (order.due != null) line("due", order.due, `due · ${order.label}`);
    }
    if (nowMs != null) line("now", nowMs, "now");
  }

  timeline.on("rangechange", redraw);
  timeline.on("rangechanged", redraw);
  timeline.on("changed", redraw);
  window.addEventListener("resize", redraw);

  return {
    el: overlay,
    setNow(iso) { nowMs = clsSafe(iso); redraw(); },
    // scope the due/release markers to one order (null clears them).
    setOrder(o) {
      order = o && (o.due != null || o.release != null)
        ? { due: clsSafe(o.due), release: clsSafe(o.release), label: o.label || "" }
        : null;
      redraw();
    },
    setShiftBoundaries(list) { shiftTicks = list || []; redraw(); },
    redraw,
    // harness probe: the rendered x of the now-line vs its canonical toScreen x
    // (drift), and which semantic markers are currently drawn.
    probe() {
      const now = overlay.querySelector(".marker.now");
      const nowX = now ? parseFloat(now.style.left) : null;
      const canonical = nowMs != null ? toX(nowMs) : null;
      return {
        nowMs, nowX: nowX == null ? null : +nowX.toFixed(1),
        nowDriftPx: (nowX != null && canonical != null) ? +Math.abs(nowX - canonical).toFixed(1) : null,
        due: !!overlay.querySelector(".marker.due"),
        release: !!overlay.querySelector(".marker.release"),
        ticks: overlay.querySelectorAll(".tick.shift").length,
      };
    },
  };
}

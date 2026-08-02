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

export function createMarkers(timeline, opts = {}) {
  const overlay = document.createElement("div");
  overlay.className = "marker-overlay";
  timeline.dom.centerContainer.appendChild(overlay);

  let nowMs = null;              // reference-date line (persistent)
  let order = null;             // {due, release, label} for the scoped order
  let shiftTicks = [];          // ms boundaries
  let frozenMs = null;          // rolling frozen-front boundary (Session 4B.3a CU2)
  // Session 4B.28 Item 1(a) - THE BOUNDARY IS A REAL HANDLE. When a drag host is
  // installed the frozen marker grows a grip: hover states it, drag moves it,
  // and the instant + delta render live while it moves. The COMMITTED boundary
  // is untouched until the ceremony completes, so an abandoned drag leaves
  // nothing behind.
  let drag = null;               // {ms, label} while dragging, else null
  // Session 4B.28 Item 2(b): the compression seams. A hidden range collapses to
  // ZERO width, so without a mark two bars either side of a folded night render
  // as touching - and "these two jobs are back to back" is a claim about the
  // plant that compression would be inventing. The ruler must LOOK folded where
  // it is folded, and this is what makes it look folded.
  let folds = [];                // [[startMs, endMs], ...] in real time

  const toX = (ms) => {
    try { return timeline.body.util.toScreen(new Date(ms)); } catch { return null; }
  };
  const width = () => timeline.dom.centerContainer.getBoundingClientRect().width;

  function line(cls, ms, label, extra = {}) {
    const x = toX(ms);
    const w = width();
    if (x == null || x < -2 || x > w + 2) return null;
    const el = document.createElement("div");
    el.className = `marker ${cls}`;
    el.style.left = `${x}px`;
    if (label) {
      const tag = document.createElement("span");
      tag.className = "marker-label";
      tag.textContent = label;
      // CU4: keep the full word on-screen. Near the right edge the chip is
      // anchored to the LEFT of its line, so "release · ORD-…" never clips to a
      // fragment ("…ase"); overflow-hidden on the overlay would otherwise cut it.
      if (x > w - 130) tag.classList.add("flip");
      el.appendChild(tag);
    }
    if (extra.grip) el.appendChild(makeGrip({ dragging: true, inert: true }));
    overlay.appendChild(el);
    return el;
  }

  // The grip is the ONLY part of the overlay that takes pointer events - a
  // full-height hit strip would swallow clicks on the bars behind it, and the
  // bars are the primary surface. It sits at the top of the lane stack, where a
  // boundary reads as a ruler affordance rather than a bar. `inert` builds the
  // mid-drag ECHO on the provisional line, which is decoration: exactly one grip
  // on this overlay is ever listening, and it is the persistent one.
  function makeGrip({ dragging = false, inert = false } = {}) {
    const grip = document.createElement("div");
    grip.className = "marker-grip" + (dragging ? " dragging" : "");
    grip.setAttribute("role", "slider");
    grip.setAttribute("tabindex", inert ? "-1" : "0");
    grip.setAttribute("aria-label",
      "frozen boundary - drag to commit or thaw work");
    grip.title = "Frozen boundary. Drag it earlier to thaw committed work "
               + "into pins you hold; drag it later to commit active work.";
    grip.innerHTML = `<span class="mg-bar"></span>`;
    if (!inert) attachGrip(grip);
    return grip;
  }

  // --- the boundary drag (Session 4B.28 Item 1(a)) -----------------------
  // Pointer capture on the grip, live provisional line + delta while moving,
  // and ONE callback on release. It never applies anything itself: the host
  // (boundary.js) owns the confirmation beat and the request, because a gesture
  // that both moved and committed would have no beat to put a confirmation in.
  const SNAP_MIN = 60;                       // see --boundary-snap-min
  function snapMs(ms) {
    const step = SNAP_MIN * 60000;
    return Math.round(ms / step) * step;
  }
  function fmtDelta(fromMs, toMs) {
    const mins = Math.round((toMs - fromMs) / 60000);
    if (mins === 0) return "no change";
    const sign = mins > 0 ? "+" : "\u2212";
    const a = Math.abs(mins);
    if (a >= 1440) {
      const d = a / 1440;
      return `${sign}${d % 1 === 0 ? d : d.toFixed(1)}d`;
    }
    if (a >= 60) {
      const h = a / 60;
      return `${sign}${h % 1 === 0 ? h : h.toFixed(1)}h`;
    }
    return `${sign}${a}m`;
  }
  function labelFor(toMs) {
    const when = new Date(toMs).toLocaleString(undefined, {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
      hour12: false,
    });
    return `${when} \u00b7 ${fmtDelta(frozenMs, toMs)}`;
  }
  function attachGrip(grip) {
    grip.addEventListener("pointerdown", (ev) => {
      if (frozenMs == null || !opts.onBoundaryMove) return;
      ev.preventDefault();
      ev.stopPropagation();
      try { grip.setPointerCapture(ev.pointerId); } catch { /* older engines */ }
      if (opts.onDragStart) opts.onDragStart();
      drag = { ms: frozenMs, label: labelFor(frozenMs) };
      redraw();
      const onMove = (e) => {
        const base = timeline.dom.centerContainer.getBoundingClientRect();
        let t;
        try { t = timeline.body.util.toTime(e.clientX - base.left).getTime(); }
        catch { return; }
        const s = snapMs(t);
        drag = { ms: s, label: labelFor(s) };
        redraw();
      };
      const onUp = () => {
        window.removeEventListener("pointermove", onMove, true);
        window.removeEventListener("pointerup", onUp, true);
        const landed = drag ? drag.ms : null;
        drag = null;
        redraw();
        if (opts.onDragEnd) opts.onDragEnd();
        // R-DP1's literalness on a different object: the instant handed on is
        // the SNAPPED instant that was on screen, never the raw pointer time.
        if (landed != null) opts.onBoundaryMove(new Date(landed).toISOString());
      };
      window.addEventListener("pointermove", onMove, true);
      window.addEventListener("pointerup", onUp, true);
    });
    // Keyboard parity: a boundary a planner cannot reach without a mouse is a
    // boundary half the acceptance criteria cover.
    grip.addEventListener("keydown", (ev) => {
      if (frozenMs == null || !opts.onBoundaryMove) return;
      const step = ev.shiftKey ? 24 * 3600000 : 3600000;
      let to = null;
      if (ev.key === "ArrowLeft") to = frozenMs - step;
      else if (ev.key === "ArrowRight") to = frozenMs + step;
      if (to == null) return;
      ev.preventDefault();
      opts.onBoundaryMove(new Date(snapMs(to)).toISOString());
    });
  }

  function fmtGap(ms) {
    const mins = Math.round(ms / 60000);
    if (mins >= 1440) {
      const d = mins / 1440;
      return `${d % 1 === 0 ? d : d.toFixed(1)}d closed`;
    }
    return `${Math.round(mins / 60)}h closed`;
  }

  function drawFolds() {
    for (const [s, e] of folds) {
      // A collapsed range has ONE x - its start and end map to the same screen
      // position under vis's hidden-date conversion - so the mark is centred
      // there rather than spanning anything.
      const x = toX(s);
      if (x == null || x < -8 || x > width() + 8) continue;
      const el = document.createElement("div");
      el.className = "fold-mark";
      el.style.left = `${x}px`;
      el.title = `${fmtGap(e - s)} - the calendar is folded here; `
               + "the bars either side are NOT adjacent";
      overlay.appendChild(el);
    }
  }

  // THE FROZEN MARKER IS PERSISTENT, AND THE GRIP IS WHY (Session 4B.28).
  //
  // Every other marker is torn down and rebuilt on each redraw, which is fine
  // for a line nobody touches. The grip is a POINTER TARGET, and redraw fires on
  // every pan, zoom and vis `changed` event — so a rebuilt grip can be replaced
  // between the moment a pointer is aimed at it and the moment the button goes
  // down, and the press lands on a detached node. It cost this session two
  // intermittent harness failures before it was understood; it would cost a
  // planner a boundary drag that sometimes does nothing.
  //
  // So the frozen marker + its grip are built ONCE and only REPOSITIONED. The
  // listeners are bound once with them.
  let frozenEl = null;
  function ensureFrozenEl() {
    if (frozenEl) return frozenEl;
    frozenEl = document.createElement("div");
    frozenEl.className = "marker frozen";
    const tag = document.createElement("span");
    tag.className = "marker-label";
    tag.textContent = "frozen \u25b8";
    frozenEl.appendChild(tag);
    if (opts.onBoundaryMove) frozenEl.appendChild(makeGrip());
    overlay.appendChild(frozenEl);
    return frozenEl;
  }
  function placeFrozen() {
    const el = ensureFrozenEl();
    const x = frozenMs == null ? null : toX(frozenMs);
    const w = width();
    if (x == null || x < -2 || x > w + 2) {
      el.style.display = "none";
      return;
    }
    el.style.display = "";
    el.style.left = `${x}px`;
    el.classList.toggle("frozen-was", !!drag);
    const tag = el.querySelector(".marker-label");
    if (tag) {
      tag.style.display = drag ? "none" : "";
      tag.classList.toggle("flip", x > w - 130);
    }
  }

  function redraw() {
    overlay.querySelectorAll(".marker:not(.frozen), .tick, .fold-mark")
      .forEach((n) => n.remove());
    drawFolds();
    // shift ticks first (behind the semantic markers).
    for (const t of shiftTicks) {
      const x = toX(t);
      if (x == null || x < -1 || x > width() + 1) continue;
      const el = document.createElement("div");
      el.className = "tick shift";
      el.style.left = `${x}px`;
      overlay.appendChild(el);
    }
    // the rolling frozen-front boundary: everything LEFT of it is committed/locked.
    // While a drag is live the COMMITTED boundary stays drawn (ghosted) beside
    // the provisional one, because "where it was" and "where it is going" are
    // two facts a planner is comparing, and showing only the second makes the
    // delta unverifiable on screen. The committed one is the PERSISTENT element
    // (it carries the grip); the provisional one is transient, as it should be.
    if (frozenMs != null) {
      placeFrozen();
      if (drag) {
        line("frozen-drag", drag.ms, drag.label, { grip: true, dragging: true });
      }
    } else if (frozenEl) {
      frozenEl.style.display = "none";
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
    // the rolling frozen-front boundary (Session 4B.3a CU2); null clears it.
    setFrozen(iso) { frozenMs = clsSafe(iso); redraw(); },
    // scope the due/release markers to one order (null clears them).
    setOrder(o) {
      order = o && (o.due != null || o.release != null)
        ? { due: clsSafe(o.due), release: clsSafe(o.release), label: o.label || "" }
        : null;
      redraw();
    },
    setShiftBoundaries(list) { shiftTicks = list || []; redraw(); },
    // Item 2(b): the compression seams (empty clears them).
    setFolds(list) { folds = list || []; redraw(); },
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
        frozen: !!overlay.querySelector(".marker.frozen"),
        frozenMs,
        // Session 4B.28 Item 1(a): is the boundary a real handle on this board,
        // and is a drag live? The harness asserts the grip EXISTS before it
        // asserts a drag does anything - a test that drove a handle that was
        // never rendered would pass by driving nothing.
        grip: !!(frozenEl && frozenEl.querySelector(".marker-grip")),
        dragging: drag ? { ms: drag.ms, label: drag.label } : null,
        ticks: overlay.querySelectorAll(".tick.shift").length,
        folds: folds.length,
        foldMarksDrawn: overlay.querySelectorAll(".fold-mark").length,
      };
    },
  };
}

// Change traces (CU5, R-DP7). No schedule change is a silent swap: every op the
// sandbox re-solve MOVED is drawn old → new — a faint "ghost of old" bar at the
// former placement + a motion line to the new one — held on screen until the
// edit is discarded (accept is stubbed this session). The pinned op is the
// dropped bar itself (its tentative lands at the new spot); its consequences are
// the neighbours the warm-started re-solve nudged (kept minimal by construction,
// which is what makes tracing them tractable — R-DP7 implementation note).
//
// The delta card's line items ARE these traces (R-DP7c): each trace and each
// card line carry the same data-op, so clicking a line navigates to the bar and
// pulses it. This module draws the board side; the card side lives in the
// sandbox card renderer.

const MIN = 60000;
const ms = (iso) => Date.parse(iso);

// Draw the moved-set into the trace layer (ghost-of-old bars) + an SVG overlay
// (motion lines). `durationMinOf(opRef)` gives the op's bar length so the
// ghost-of-old has the right width. Returns the drawn traces for hit-testing
// (card line → bar navigation).
export function renderTraces(barLayer, svgEl, moves, durationMinOf, geometry, win) {
  barLayer.replaceChildren();
  while (svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);
  const winStart = ms(win.start), winEnd = ms(win.end);
  const drawn = [];

  for (const mv of moves) {
    const durMs = (durationMinOf(mv.operation_ref) || 0) * MIN;
    const oldRect = geometry.barRect(mv.from_resource, ms(mv.from_start), ms(mv.from_start) + durMs);
    const newRect = geometry.barRect(mv.to_resource, ms(mv.to_start), ms(mv.to_start) + durMs);

    // ghost-of-old bar (skip if the old spot is off-window)
    if (oldRect && ms(mv.from_start) < winEnd && ms(mv.from_start) + durMs > winStart) {
      const g = document.createElement("div");
      g.className = "trace-old" + (mv.pinned ? " pinned" : "");
      g.dataset.op = mv.operation_ref;
      Object.assign(g.style, {
        left: `${oldRect.x}px`, width: `${oldRect.width}px`,
        top: `${oldRect.top + 3}px`, height: `${oldRect.height - 6}px`,
      });
      barLayer.appendChild(g);
    }

    // motion line old-center → new-center
    if (oldRect && newRect) {
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      const ax = oldRect.x + oldRect.width / 2, ay = oldRect.top + oldRect.height / 2;
      const bx = newRect.x + newRect.width / 2, by = newRect.top + newRect.height / 2;
      line.setAttribute("x1", ax); line.setAttribute("y1", ay);
      line.setAttribute("x2", bx); line.setAttribute("y2", by);
      line.setAttribute("class", "trace-line" + (mv.pinned ? " pinned" : ""));
      line.dataset.op = mv.operation_ref;
      svgEl.appendChild(line);
      _arrowhead(svgEl, ax, ay, bx, by, mv.pinned);
    }
    drawn.push({ ...mv, oldRect, newRect });
  }
  return drawn;
}

function _arrowhead(svgEl, ax, ay, bx, by, pinned) {
  const ang = Math.atan2(by - ay, bx - ax);
  const size = 6;
  for (const da of [-0.4, 0.4]) {
    const l = document.createElementNS("http://www.w3.org/2000/svg", "line");
    l.setAttribute("x1", bx); l.setAttribute("y1", by);
    l.setAttribute("x2", bx - size * Math.cos(ang - da));
    l.setAttribute("y2", by - size * Math.sin(ang - da));
    l.setAttribute("class", "trace-line" + (pinned ? " pinned" : ""));
    svgEl.appendChild(l);
  }
}

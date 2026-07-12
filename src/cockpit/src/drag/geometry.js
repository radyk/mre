// vis-timeline geometry — the ONE place the gesture surface reads vis's private
// layout. Everything else (shade, ghosts, magnets, tentative, traces) works in
// canonical coordinates (resource_id + ISO time) and asks this module to
// convert to/from pixels relative to the center container.
//
// Two conversions matter:
//   * pointer DOM event → {resource_id, time_ms}   (grab + drag target)
//   * (resource_id, time_ms) → {x, top, height}    (draw a bar on a row)
//
// It leans on vis's documented surfaces — getEventProperties(e) for the pointer
// hit-test, body.util.toScreen/toTime for the time axis — and on the group
// foreground DOM rect for row bands (the same read the citation overlay already
// relies on). Guarded throughout: a vis version bump that moved a field returns
// null rather than throwing, and the drag surface degrades (never a broken
// board). The harness geometryProbe() asserts a round-trip so a bump trips a
// test, not the demo.

const MIN = 60000;

export function createGeometry(timeline) {
  const centerContainer = timeline.dom.centerContainer;

  function base() {
    return centerContainer.getBoundingClientRect();
  }

  // pointer/mouse event → canonical {resource_id, time_ms} (null if off-board).
  function eventToTarget(ev) {
    try {
      const p = timeline.getEventProperties(ev);
      if (!p) return null;
      const t = p.time || p.snappedTime;
      return {
        resource_id: p.group ?? null,
        time_ms: t ? t.getTime() : null,
        // whether the pointer is over the data area (not the axis/labels)
        onItemArea: p.what !== "axis" && p.what !== "group-label",
      };
    } catch {
      return null;
    }
  }

  // canonical time (ms) → x in px relative to the center container left edge.
  function timeToX(timeMs) {
    try {
      return timeline.body.util.toScreen(new Date(timeMs));
    } catch {
      return null;
    }
  }

  // x (px relative to center container) → canonical time (ms).
  function xToTime(x) {
    try {
      return timeline.body.util.toTime(x).getTime();
    } catch {
      return null;
    }
  }

  // resource_id → {top, height} band (px relative to the center container).
  // Reads the group's foreground DOM rect; falls back to null when the group
  // isn't laid out (a vis bump / off-screen group).
  function rowBand(resourceId) {
    const g = timeline.itemSet?.groups?.[resourceId];
    const el = g?.dom?.foreground || g?.dom?.background;
    if (!el) return null;
    const r = el.getBoundingClientRect();
    if (r.height <= 0) return null;
    const b = base();
    return { top: r.top - b.top, height: r.height };
  }

  // full rect for a bar on a row across [startMs,endMs]: {x, width, top, height}
  // — clipped to nothing (returns null) when the row/time isn't laid out.
  function barRect(resourceId, startMs, endMs) {
    const band = rowBand(resourceId);
    if (!band) return null;
    const x0 = timeToX(startMs), x1 = timeToX(endMs);
    if (x0 == null || x1 == null) return null;
    return { x: x0, width: Math.max(2, x1 - x0), top: band.top, height: band.height };
  }

  // one pixel expressed in minutes at the current zoom — used to size snap radii
  // (a px radius) against canonical anchor times (a ms distance).
  function pxToMinutes(px) {
    const t0 = xToTime(0), t1 = xToTime(px);
    if (t0 == null || t1 == null) return null;
    return Math.abs(t1 - t0) / MIN;
  }

  // list of all currently-rendered resource rows in order, with bands — used to
  // shade every row on grab (CU1).
  function allRowBands(resourceIds) {
    const out = [];
    for (const rid of resourceIds) {
      const band = rowBand(rid);
      if (band) out.push({ resource_id: rid, ...band });
    }
    return out;
  }

  return {
    centerContainer, base, eventToTarget, timeToX, xToTime, rowBand, barRect,
    pxToMinutes, allRowBands,
    // Harness probe (standing regression): round-trip a known time through
    // toScreen→toTime and report a row band, so a vis geometry bump surfaces
    // as a failing test rather than a silently broken drag.
    probe(sampleResourceId, sampleTimeMs) {
      const x = timeToX(sampleTimeMs);
      const back = x == null ? null : xToTime(x);
      const band = rowBand(sampleResourceId);
      return {
        timeToX: x == null ? null : +x.toFixed(2),
        roundTripErrMs: back == null ? null : Math.abs(back - sampleTimeMs),
        rowBand: band ? { top: +band.top.toFixed(1), height: +band.height.toFixed(1) } : null,
      };
    },
  };
}

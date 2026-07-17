// Row-intelligence window arithmetic — the JS port of
// src/mre/modules/row_intelligence.py (docs/07 Session 4.2 CU4).
//
// The row-label strip reports, per Gantt row, utilization over the VISIBLE
// window (recomputed live as the planner pans), the moment the row is booked
// through, and its next open gap. Those numbers must be the solver's window
// arithmetic — never measured off the rendered DOM — so this file is a
// byte-for-byte port of the Python definition, and BOTH are pinned to the same
// shared numeric fixtures (tests/cockpit/fixtures/rowstats_cases.json:
// test_row_intelligence.py on the Python side, rowstats.spec.mjs here).
//
// PURE and framework-free. Intervals are [start, end] pairs in a shared minute
// (or ms — the unit is the caller's) grid; util is a fraction in [0,1] or null.

// Sort, drop empties, coalesce touching/overlapping intervals.
export function mergeWindows(windows) {
  const xs = windows.filter(([s, e]) => e > s).sort((a, b) => a[0] - b[0]);
  const out = [];
  for (const [s, e] of xs) {
    if (out.length && s <= out[out.length - 1][1]) {
      out[out.length - 1][1] = Math.max(out[out.length - 1][1], e);
    } else {
      out.push([s, e]);
    }
  }
  return out;
}

function overlap([s, e], lo, hi) {
  return Math.max(0, Math.min(e, hi) - Math.max(s, lo));
}

export function openCapacity(windows, lo, hi) {
  return mergeWindows(windows).reduce((t, w) => t + overlap(w, lo, hi), 0);
}

export function occupiedOpen(windows, occupancy, lo, hi) {
  const open = mergeWindows(windows);
  const busy = mergeWindows(occupancy);
  let total = 0;
  for (const [bs, be] of busy)
    for (const [ws, we] of open)
      total += overlap([bs, be], Math.max(ws, lo), Math.min(we, hi));
  return total;
}

// Fraction [0,1] of the window's OPEN capacity that is booked, or null when
// there is no open capacity in [lo,hi] (utilization undefined → the strip shows
// "—", never a divide-by-zero 0%).
export function rowUtilization(windows, occupancy, lo, hi) {
  const cap = openCapacity(windows, lo, hi);
  if (cap <= 0) return null;
  return Math.min(1, occupiedOpen(windows, occupancy, lo, hi) / cap);
}

// Last minute the row has work through (max occupancy end), or null when empty.
export function bookedThrough(occupancy) {
  const ends = occupancy.filter(([s, e]) => e > s).map(([, e]) => e);
  return ends.length ? Math.max(...ends) : null;
}

// Earliest instant >= fromT inside an OPEN window and not occupied — the next
// moment the row could take work — or null when none exists at/after fromT.
export function nextAvailableGap(windows, occupancy, fromT) {
  const open = mergeWindows(windows);
  const busy = mergeWindows(occupancy);
  for (const [ws, we] of open) {
    let cursor = Math.max(ws, fromT);
    if (cursor >= we) continue;
    for (const [bs, be] of busy) {
      if (be <= cursor) continue;
      if (bs > cursor) return cursor;       // a free instant before the next booking
      cursor = Math.max(cursor, be);        // booking covers cursor; advance
      if (cursor >= we) break;
    }
    if (cursor < we) return cursor;
  }
  return null;
}

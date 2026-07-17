"""Per-resource-row intelligence: utilization, booked-through, next-open-gap
(docs/07 Session 4.2 CU4).

The cockpit's row-label strip reports, for each Gantt row: how much of the
visible window's OPEN capacity is booked (utilization %), the moment the row is
booked through (its last assignment end), and the next open slot with no work on
it. Those numbers must come from the SAME window arithmetic the solver's
eligibility uses — never from measuring rendered pixels — so a row that looks
busy is provably busy by canonical minutes.

This module is the canonical definition. It operates on the ``(start_min,
end_min)`` open-window representation :func:`mre.modules.eligibility
.flatten_resource_windows` produces, plus a per-row occupancy list in the same
minute grid. The cockpit ships a byte-for-byte JS port (``legality/rowstats.js``)
for the live "over the visible window" recompute as the planner pans; the two
are pinned together by shared numeric fixtures (``tests/test_row_intelligence
.py`` on this side, ``tests/cockpit/rowstats.spec.mjs`` on the port). All
functions here are pure and ortools-free.
"""
from __future__ import annotations

from typing import Optional

Interval = tuple[int, int]


def merge_windows(windows: list[Interval]) -> list[Interval]:
    """Sort, drop empties, and coalesce touching/overlapping intervals."""
    xs = sorted((s, e) for s, e in windows if e > s)
    out: list[Interval] = []
    for s, e in xs:
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def _overlap(a: Interval, lo: int, hi: int) -> int:
    """Minutes of interval ``a`` inside [lo, hi]."""
    return max(0, min(a[1], hi) - max(a[0], lo))


def open_capacity_min(windows: list[Interval], lo: int, hi: int) -> int:
    """Total OPEN minutes within [lo, hi] (windows merged first)."""
    return sum(_overlap(w, lo, hi) for w in merge_windows(windows))


def occupied_open_min(
    windows: list[Interval], occupancy: list[Interval], lo: int, hi: int
) -> int:
    """Booked minutes within [lo, hi] that fall on OPEN capacity.

    Occupancy is intersected with the open windows so a bar bleeding over a
    closure (or a stray point outside any shift) never inflates utilization past
    100%. Both sides are merged first.
    """
    open_w = merge_windows(windows)
    busy = merge_windows(occupancy)
    total = 0
    for bs, be in busy:
        for ws, we in open_w:
            total += _overlap((bs, be), max(ws, lo), min(we, hi))
    return total


def row_utilization(
    windows: list[Interval], occupancy: list[Interval], lo: int, hi: int
) -> Optional[float]:
    """Fraction [0, 1] of the visible window's OPEN capacity that is booked, or
    ``None`` when there is no open capacity in [lo, hi] (utilization undefined —
    the strip shows "—", never a divide-by-zero 0%)."""
    cap = open_capacity_min(windows, lo, hi)
    if cap <= 0:
        return None
    return min(1.0, occupied_open_min(windows, occupancy, lo, hi) / cap)


def booked_through_min(occupancy: list[Interval]) -> Optional[int]:
    """The last minute the row has work scheduled through (max occupancy end),
    or ``None`` when the row is empty."""
    ends = [e for s, e in occupancy if e > s]
    return max(ends) if ends else None


def next_available_gap_min(
    windows: list[Interval],
    occupancy: list[Interval],
    from_min: int,
) -> Optional[int]:
    """The earliest minute ≥ ``from_min`` that is inside an OPEN window and not
    occupied — the next moment the row could take new work — or ``None`` when no
    open, unbooked minute exists at/after ``from_min`` in the flattened windows.

    Free time = open windows minus occupancy. We walk the open windows in order,
    subtracting the merged occupancy, and return the first free instant ≥
    ``from_min``.
    """
    open_w = merge_windows(windows)
    busy = merge_windows(occupancy)
    for ws, we in open_w:
        cursor = max(ws, from_min)
        if cursor >= we:
            continue
        for bs, be in busy:
            if be <= cursor:
                continue
            if bs > cursor:
                return cursor          # a free instant before the next booking
            cursor = max(cursor, be)   # this booking covers the cursor; advance
            if cursor >= we:
                break
        if cursor < we:
            return cursor
    return None

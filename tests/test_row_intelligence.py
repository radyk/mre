"""Row-intelligence window arithmetic (docs/07 Session 4.2 CU4).

Two jobs:
  1. pin the canonical definition (row_intelligence.py) against the SHARED
     numeric fixtures the cockpit's JS port (rowstats.js) also reads, so the
     visible-window utilization / booked-through / next-gap the planner sees is
     the same arithmetic on both sides (tests/cockpit/fixtures/rowstats_cases
     .json);
  2. prove the assembler surfaces booked_through / next_open_gap per row through
     the SAME flatten the solver's eligibility uses, and the 1.6 additive fields
     (calendar reason, customer_name, quantity) land truthfully.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mre.modules.row_intelligence import (
    booked_through_min,
    next_available_gap_min,
    open_capacity_min,
    row_utilization,
)

_CASES = json.loads(
    (Path(__file__).parent / "cockpit" / "fixtures" / "rowstats_cases.json").read_text()
)["cases"]


def _tuples(pairs):
    return [(int(a), int(b)) for a, b in pairs]


@pytest.mark.parametrize("case", _CASES, ids=[c["name"] for c in _CASES])
def test_rowstats_matches_shared_fixture(case):
    """Every shared case: Python produces the pinned util / booked / gap. The JS
    port asserts the SAME file (tests/cockpit/rowstats.spec.mjs)."""
    windows = _tuples(case["windows"])
    occ = _tuples(case["occupancy"])
    lo, hi = case["util_window"]

    util = row_utilization(windows, occ, lo, hi)
    if case["util"] is None:
        assert util is None
    else:
        assert util is not None
        assert round(util, 4) == pytest.approx(case["util"], abs=1e-9)

    assert booked_through_min(occ) == case["booked_through"]
    assert next_available_gap_min(windows, occ, case["gap_from"]) == case["next_gap"]


def test_open_capacity_clips_to_window():
    assert open_capacity_min([(0, 100), (200, 300)], 50, 250) == 100  # 50 + 50


def test_utilization_never_exceeds_one_when_occupancy_overflows():
    # occupancy longer than the open window is clamped to open capacity.
    assert row_utilization([(0, 100)], [(0, 500)], 0, 100) == 1.0

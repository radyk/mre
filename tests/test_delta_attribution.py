"""CU1 (Session 4B.5) — the delta card tells the truth about what it measured.

THE FOUNDER'S SPECIMEN. On schedule ``rolling-279dec02-411``, two different
gestures (ORD-38 -> MILL-01 at Jan-8 08:30, then the same order at 07:00) produced
IDENTICAL delta cards: -$11,975.83, the same four affected orders to the cent.
Both numbers were true. Neither was about the gesture. ``cost_delta_abs`` measures
the RE-SOLVE — a freshly-budgeted window optimization the incumbent had never been
given — and the card presented it where a planner reads "what my move cost".

The fix is an attribution, not a caveat. Beat two also solves the same window,
under the same budget, holding the same standing commitments, WITHOUT the
gesture's pin — the BASELINE — and the verdict splits:

    window re-optimization = baseline - incumbent   (nothing the planner did)
    your move              = pinned   - baseline    (what the planner did)

The planner's move is judged against the baseline, never against the stale
incumbent. The two parts sum EXACTLY to the total (decomposition-sums
discipline). When the baseline cannot be proven inside the budget the card says
so and shows the unsplit total with an explicit "includes window
re-optimization" line — never a silent fused number.

Two levels, as the sandbox tests already do it: the pure attribution arithmetic
and the cache key, unit-tested with no solve; then the real thing over a solved
fixture (slow), where the specimen is automated.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.modules.sandbox import (
    SANDBOX_BUDGET_S,
    UNSPLIT_NOTE,
    BaselineSolve,
    attribute_delta,
    baseline_cache_key,
    baseline_window_solve,
    clear_baseline_cache,
    sandbox_pin_resolve,
)
from mre.modules.snapshot_store import SnapshotStore
from tools.generate_erp_dataset import generate

SNAP = "snap-attr"


# ---------------------------------------------------------------------------
# The attribution arithmetic — pure, no solve
# ---------------------------------------------------------------------------

class TestAttributionArithmetic:
    def _baseline(self, total, **kw):
        return BaselineSolve(available=True, total_cost=total, **kw)

    def test_the_two_parts_sum_exactly_to_the_total(self):
        # incumbent 100,375.83 -> baseline 88,775.83 -> pinned 88,400.00
        a = attribute_delta(-11975.83, 100375.83, self._baseline(88775.83))
        assert a["attribution"] == "split"
        assert a["reopt_delta_abs"] == -11600.0     # baseline vs incumbent
        assert a["move_delta_abs"] == -375.83       # pinned vs baseline
        assert round(a["reopt_delta_abs"] + a["move_delta_abs"], 2) == -11975.83

    def test_the_move_part_is_the_remainder_so_the_sum_can_never_drift(self):
        """The re-optimization part is MEASURED and the move part is the
        REMAINDER. That ordering is deliberate: it makes a card that does not add
        up impossible, at the cost of putting any rounding residue on the move —
        which is the part measured against the fresher of the two references."""
        for total, inc, base in ((-11975.83, 100375.83, 88775.83),
                                 (0.01, 1000.0, 1000.005),
                                 (1234.56, 9999.99, 10000.0),
                                 (-0.03, 500.0, 499.99)):
            a = attribute_delta(total, inc, self._baseline(base))
            assert round(a["reopt_delta_abs"] + a["move_delta_abs"], 2) == total

    def test_a_move_that_bought_nothing_reads_as_zero_not_as_the_whole_delta(self):
        """The specimen's shape: the entire delta was re-optimization. The honest
        card says the move cost nothing — it does not credit the planner with a
        saving the solver would have found anyway."""
        a = attribute_delta(-11975.83, 100375.83, self._baseline(88400.0))
        assert a["reopt_delta_abs"] == -11975.83
        assert a["move_delta_abs"] == 0.0

    def test_an_unprovable_baseline_never_fuses_the_number_silently(self):
        a = attribute_delta(
            -11975.83, 100375.83,
            BaselineSolve(available=False, status="UNKNOWN",
                          message="the window could not be re-solved without "
                                  "your move inside the budget"))
        assert a["attribution"] == "unavailable"
        assert a["reopt_delta_abs"] is None and a["move_delta_abs"] is None
        assert a["attribution_note"]          # the card ALWAYS has a line to show

    def test_no_baseline_at_all_still_carries_the_unsplit_note(self):
        a = attribute_delta(-500.0, 1000.0, None)
        assert a["attribution"] == "unavailable"
        assert a["attribution_note"] == UNSPLIT_NOTE

    def test_no_ledger_dollars_means_no_attribution_claim(self):
        # a pool-ghost drop / a fixture with no ledger: there is no total to split
        a = attribute_delta(None, 1000.0, self._baseline(900.0))
        assert a["attribution"] == "unavailable"
        assert a["reopt_delta_abs"] is None and a["move_delta_abs"] is None

    def test_the_baseline_wall_time_is_reported_so_the_split_names_its_own_cost(self):
        a = attribute_delta(-100.0, 1000.0, self._baseline(950.0, wall_time_s=2.5))
        assert a["baseline_wall_time_s"] == 2.5


class TestBaselineCacheKey:
    """One baseline serves every card until the INCUMBENT changes. The key is
    every input that defines the baseline solve — so an accepted edit (new
    snapshot, new pin set) misses by construction, and a second gesture on the
    same board hits."""

    BASE = dict(out_dir="/d", snapshot_id="snap-1", budget_s=15.0,
                deterministic=True, standing_pins=None, restrict_op_ids=None)

    def _k(self, **over):
        return baseline_cache_key(**{**self.BASE, **over})

    def test_the_same_incumbent_is_the_same_key(self):
        assert self._k() == self._k()

    def test_the_gesture_is_not_in_the_key(self):
        # nothing about the pin reaches this function's signature at all — that
        # IS the caching property, asserted by construction.
        assert "pin_op_id" not in baseline_cache_key.__code__.co_varnames

    @pytest.mark.parametrize("field,value", [
        ("snapshot_id", "snap-2"),
        ("out_dir", "/other"),
        ("budget_s", 30.0),
        ("deterministic", False),
        ("standing_pins", [{"operation_ref": "op-1", "resource_id": "R1",
                            "start": "2026-01-05T07:00:00+00:00"}]),
        ("restrict_op_ids", {"op-1", "op-2"}),
    ])
    def test_a_different_incumbent_is_a_different_key(self, field, value):
        assert self._k(**{field: value}) != self._k()

    def test_standing_pin_order_does_not_change_the_key(self):
        p1 = {"operation_ref": "a", "resource_id": "R1", "start": "T1"}
        p2 = {"operation_ref": "b", "resource_id": "R2", "start": "T2"}
        assert self._k(standing_pins=[p1, p2]) == self._k(standing_pins=[p2, p1])


# ---------------------------------------------------------------------------
# The real thing, over a solved fixture (slow)
# ---------------------------------------------------------------------------

def _solve_fixture(tmp_path_factory, scenario: str, snap: str) -> Path:
    tmp = tmp_path_factory.mktemp(f"attr_{scenario}")
    sub = tmp / "sub"
    generate(sub, scenario=scenario, seed=7)
    out = tmp / "out"
    rc = mre_main([
        "--submission", str(sub), "--out", str(out), "--snapshot-id", snap,
        "--time-limit", "45", "--solver-workers", "1", "--solver-seed", "42",
    ])
    assert rc == 0, f"pipeline exit {rc}"
    return out


@pytest.fixture(scope="module")
def solved(tmp_path_factory):
    out = _solve_fixture(tmp_path_factory, "multi_route_distinct", SNAP)
    clear_baseline_cache()
    return out


def _assignments(out: Path, snap: str) -> list[tuple[str, str, str]]:
    """(operation_ref, resource_id, start_iso) for every incumbent placement."""
    reader = SnapshotStore(out / "snapshots").load_snapshot(snap)
    rows = []
    for a in reader.iter_entities("assignment"):
        rid = (a.get("resource_assignments") or [{}])[0].get("resource_ref")
        st = (a.get("phase_windows") or {}).get("run", [{}])[0].get("start")
        if rid and st:
            rows.append((a["operation_ref"], rid, st))
    return rows


def _resource_ids(out: Path, snap: str) -> list[str]:
    reader = SnapshotStore(out / "snapshots").load_snapshot(snap)
    return [r["id"] for r in reader.iter_entities("resource")]


def _shift(iso: str, minutes: int) -> str:
    return (datetime.fromisoformat(iso.replace("Z", "+00:00"))
            + timedelta(minutes=minutes)).isoformat()


@pytest.mark.slow
def test_the_baseline_is_a_real_proven_solve_of_the_same_window(solved):
    base = baseline_window_solve(solved, SNAP, budget_s=SANDBOX_BUDGET_S,
                                 deterministic=True, use_cache=False)
    assert base.available is True, base.message
    assert base.total_cost is not None and base.total_cost > 0
    assert base.status in ("OPTIMAL", "FEASIBLE")


@pytest.mark.slow
def test_one_baseline_serves_every_card_until_the_incumbent_changes(solved):
    """The cache is what makes the split affordable: the FIRST gesture on a board
    pays for a baseline, every later one reads it. A cache hit costs no wall time
    at all, which is the property the card's latency claim rests on."""
    clear_baseline_cache()
    first = baseline_window_solve(solved, SNAP, budget_s=SANDBOX_BUDGET_S,
                                  deterministic=True)
    assert first.cached is False
    second = baseline_window_solve(solved, SNAP, budget_s=SANDBOX_BUDGET_S,
                                   deterministic=True)
    assert second.cached is True
    assert second.total_cost == first.total_cost
    # a different incumbent (here: a different budget) is a different baseline
    third = baseline_window_solve(solved, SNAP, budget_s=SANDBOX_BUDGET_S / 3,
                                  deterministic=True)
    assert third.cached is False


@pytest.mark.slow
def test_the_founders_specimen_two_pins_one_reoptimization(solved):
    """THE SPECIMEN, AUTOMATED. Two different gestures on the SAME incumbent used
    to produce identical cards. They still share a number — and now that number
    is LABELLED as the thing they share (the window re-optimization), while the
    part that is about the gesture is reported separately and carries the whole
    difference between the two cards."""
    clear_baseline_cache()
    rows = _assignments(solved, SNAP)
    assert rows, "the fixture must have incumbent placements"
    op, rid, start = rows[0]

    a = sandbox_pin_resolve(out_dir=solved, snapshot_id=SNAP, pin_op_id=op,
                            pin_resource_id=rid, pin_start_iso=start,
                            budget_s=SANDBOX_BUDGET_S, deterministic=True)
    b = sandbox_pin_resolve(out_dir=solved, snapshot_id=SNAP, pin_op_id=op,
                            pin_resource_id=rid,
                            pin_start_iso=_shift(start, 90),
                            budget_s=SANDBOX_BUDGET_S, deterministic=True)
    for r in (a, b):
        assert r.feasible, r.message
        assert r.attribution == "split", r.attribution_note
        # decomposition-sums: the card may never claim arithmetic that does not
        # close (the same rule cost_lines follows).
        assert round(r.reopt_delta_abs + r.move_delta_abs, 2) == r.cost_delta_abs

    # (1) the re-optimization part is IDENTICAL — it is a property of the
    #     incumbent, not of the gesture. This is the number the founder saw twice.
    assert a.reopt_delta_abs == b.reopt_delta_abs

    # (2) the WHOLE difference between the two cards lives in the move part. If
    #     the two gestures cost the same, they now say so about the MOVE rather
    #     than about the plan.
    assert (round(a.cost_delta_abs - b.cost_delta_abs, 2)
            == round(a.move_delta_abs - b.move_delta_abs, 2))

    # (3) the second gesture paid nothing for its attribution — the baseline was
    #     already solved for this incumbent.
    assert b.baseline_wall_time_s == 0.0


@pytest.mark.slow
def test_a_pin_that_costs_something_shows_a_nonzero_move_part(solved):
    """A genuinely valuable (or costly) pin must move the MOVE part, not just the
    total. Searched over the fixture's own placements rather than asserted about
    one hand-picked op: what matters is that SOME gesture is attributable, and
    that when one is, the split is exact."""
    clear_baseline_cache()
    rows = _assignments(solved, SNAP)
    trivial = sandbox_pin_resolve(
        out_dir=solved, snapshot_id=SNAP, pin_op_id=rows[0][0],
        pin_resource_id=rows[0][1], pin_start_iso=rows[0][2],
        budget_s=SANDBOX_BUDGET_S, deterministic=True)
    assert trivial.attribution == "split"

    # Candidate drops, cheapest-to-describe first: a CROSS-MACHINE move (this
    # fixture's rates are distinct by design, so relocating work must reprice it),
    # then a plain delay on the incumbent machine. The alternates come from the
    # snapshot's RESOURCES, not from the incumbent's placements — this fixture
    # solves onto a single machine, so the incumbent names no alternative at all.
    resources = _resource_ids(solved, SNAP)
    candidates = []
    for op, rid, start in rows[:4]:
        for other in resources:
            if other != rid:
                candidates.append((op, other, start))
        for shift in (240, 600, 1440):
            candidates.append((op, rid, _shift(start, shift)))

    found = None
    for op, target_rid, target_start in candidates:
        r = sandbox_pin_resolve(
            out_dir=solved, snapshot_id=SNAP, pin_op_id=op,
            pin_resource_id=target_rid, pin_start_iso=target_start,
            budget_s=SANDBOX_BUDGET_S, deterministic=True)
        # an ineligible machine is a PROVEN-illegal placement, not a candidate
        if r.feasible and r.attribution == "split" \
                and abs(r.move_delta_abs) >= 0.01:
            found = r
            break
    if found is None:
        pytest.skip("no drop in this fixture's geometry priced differently from "
                    "the incumbent; the arithmetic is unit-tested separately")
    assert round(found.reopt_delta_abs + found.move_delta_abs, 2) \
        == found.cost_delta_abs
    # the re-optimization part is still the same shared number
    assert found.reopt_delta_abs == trivial.reopt_delta_abs
    # and the move part is what distinguishes this gesture from the trivial one
    assert found.move_delta_abs != trivial.move_delta_abs


@pytest.mark.slow
def test_a_trivial_pin_leaves_the_move_part_at_or_near_zero(solved):
    """Pinning an op exactly where it already is asks the solver for nothing. Any
    money in that card belongs to the window, and the split says so — the move
    part is what the planner is entitled to read as theirs."""
    clear_baseline_cache()
    op, rid, start = _assignments(solved, SNAP)[0]
    r = sandbox_pin_resolve(out_dir=solved, snapshot_id=SNAP, pin_op_id=op,
                            pin_resource_id=rid, pin_start_iso=start,
                            budget_s=SANDBOX_BUDGET_S, deterministic=True)
    assert r.attribution == "split"
    # the baseline is free to relocate this op; a trivial pin forbids it. The
    # move part is therefore >= 0 (holding it still can only cost) and small.
    assert r.move_delta_abs >= -0.005
    assert abs(r.move_delta_abs) <= abs(r.cost_delta_abs) + 0.01


@pytest.mark.slow
def test_without_a_baseline_the_card_states_the_unsplit_total_explicitly(solved):
    """The degrade path, exercised as a path and not as a comment: with the
    baseline suppressed the total is still reported, the parts are absent, and
    the card carries the authored line that keeps the number readable."""
    op, rid, start = _assignments(solved, SNAP)[0]
    r = sandbox_pin_resolve(out_dir=solved, snapshot_id=SNAP, pin_op_id=op,
                            pin_resource_id=rid, pin_start_iso=start,
                            budget_s=SANDBOX_BUDGET_S, deterministic=True,
                            baseline=False)
    assert r.feasible and r.cost_delta_abs is not None
    assert r.attribution == "unavailable"
    assert r.reopt_delta_abs is None and r.move_delta_abs is None
    assert r.attribution_note == UNSPLIT_NOTE

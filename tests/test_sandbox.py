"""Tier-2 sandbox latency budget (docs/07 Phase 3, R-T1c, session 3.2a CU4).

Two levels, per the ruling:
  * the three-outcome CLASSIFICATION logic, unit-tested without a solve
    (budget-exhausted paths simulated, never waited for);
  * the CI acceptance — a single-pin sandbox re-solve on the demo fixture
    (multi_route, deterministic) returns a VERDICT within the budget token
    (a standing latency regression: a heavy fixture fails a test before it
    fails a demo).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.modules.sandbox import (
    MAJOR_MOVE_THRESHOLD_MIN,
    SANDBOX_BUDGET_S,
    SANDBOX_FEASIBLE_UNPROVEN,
    SANDBOX_NO_VERDICT,
    SANDBOX_VERDICT,
    _annotate_move_reasons,
    _moved_set,
    classify_sandbox_outcome,
    sandbox_pin_resolve,
)
from mre.modules.snapshot_store import SnapshotStore
from tools.generate_erp_dataset import generate

SNAP = "snap-sb"


# ---------------------------------------------------------------------------
# The three-outcome classifier — pure, no solve (budget-exhaust simulated)
# ---------------------------------------------------------------------------

class TestClassification:
    def test_proven_optimal_is_a_verdict(self):
        assert classify_sandbox_outcome("OPTIMAL", 0.2, 15.0) == SANDBOX_VERDICT

    def test_proven_infeasible_is_a_verdict(self):
        # a proven-infeasible pin is the return-home verdict (R-DP2), still (1)
        assert classify_sandbox_outcome("INFEASIBLE", 3.0, 15.0) == SANDBOX_VERDICT

    def test_feasible_but_unproven_is_flagged(self):
        # ran the budget out with a solution but no optimality proof → (2)
        assert classify_sandbox_outcome("FEASIBLE", 15.0, 15.0) == SANDBOX_FEASIBLE_UNPROVEN

    def test_nothing_found_is_return_home(self):
        # budget exhausted with NO solution → (3). Simulated (wall > budget),
        # never actually waited for.
        assert classify_sandbox_outcome("UNKNOWN", 99.0, 15.0) == SANDBOX_NO_VERDICT

    def test_unknown_statuses_fail_safe_to_return_home(self):
        assert classify_sandbox_outcome("MODEL_INVALID", 1.0, 15.0) == SANDBOX_NO_VERDICT
        assert classify_sandbox_outcome("", 1.0, 15.0) == SANDBOX_NO_VERDICT

    def test_budget_is_a_design_token_not_a_constant(self):
        # the outcome is a function of the PROOF, so the same status classifies
        # the same at any budget — the token tunes the wait, not the verdict.
        for budget in (5.0, 15.0, 30.0):
            assert classify_sandbox_outcome("OPTIMAL", 0.1, budget) == SANDBOX_VERDICT
        assert SANDBOX_BUDGET_S == 15.0   # the initial token


# ---------------------------------------------------------------------------
# The delta-card "why" clause (session 3.3 CU3) — reason derivation, no solve
# ---------------------------------------------------------------------------

class _FakeSolveValues:
    def __init__(self, resource, start, end):
        self.op_resource = resource
        self.op_start_minutes = start
        self.op_end_minutes = end


class TestMoveReasons:
    """The occupancy arithmetic behind the card's one-clause 'why', tested on a
    hand-built re-solve (no solver): a forward-shifted op is annotated with what
    holds its machine right up to its start — the dropped op ('displaced by the
    dropped op') or another op ('blocked on <machine> until <time>'). Minor
    shifts, the pin itself, and non-contiguous blockers are left unannotated —
    the card must not fabricate a reason."""

    def _scenario(self):
        h = datetime(2026, 1, 1, tzinfo=timezone.utc)
        R, R2, R3 = "R", "R2", "R3"
        # incumbent: everything starts at horizon
        incumbent = {"P": (R, h), "X": (R, h), "V": (R2, h), "W": (R2, h),
                     "T": (R3, h), "U": (R3, h)}
        # new placements (minutes from horizon):
        #   P pinned 0–60; X blocked behind P → 60–120 (+60, blocker=pin)
        #   V unchanged 0–300; W blocked behind V → 300–360 (+300, blocker=V)
        #   T 0–100; U shifted to 300–360 but its machine is free 100–300
        #     (gap 200 > threshold) → NO reason invented
        sv = _FakeSolveValues(
            resource={"P": R, "X": R, "V": R2, "W": R2, "T": R3, "U": R3},
            start={"P": 0, "X": 60, "V": 0, "W": 300, "T": 0, "U": 300},
            end={"P": 60, "X": 120, "V": 300, "W": 360, "T": 100, "U": 360},
        )
        return h, incumbent, sv

    def test_reasons_are_derived_from_occupancy(self):
        h, incumbent, sv = self._scenario()
        moves = _moved_set(sv, incumbent, h, pin_op_id="P")
        _annotate_move_reasons(moves, sv, h, pin_op_id="P")
        by_op = {m["operation_ref"]: m for m in moves}

        # X moved +60, held behind the dropped op → displaced_by_drop
        assert by_op["X"]["reason"]["kind"] == "displaced_by_drop"
        # W moved +300, held behind V (not the pin) → occupancy, names V + machine
        assert by_op["W"]["reason"]["kind"] == "occupancy"
        assert by_op["W"]["reason"]["on_resource"] == "R2"
        assert by_op["W"]["reason"]["blocker_op"] == "V"
        # the pinned drop carries no "why" (it IS the drop)
        assert "reason" not in by_op["P"]
        # U shifted far but its machine was free before it → no fabricated reason
        assert "reason" not in by_op["U"]

    def test_minor_shifts_are_not_annotated(self):
        h = datetime(2026, 1, 1, tzinfo=timezone.utc)
        incumbent = {"P": ("R", h), "A": ("R", h)}
        # A shifts by less than the threshold → no reason
        small = MAJOR_MOVE_THRESHOLD_MIN - 1
        sv = _FakeSolveValues(
            resource={"P": "R", "A": "R"},
            start={"P": 0, "A": small}, end={"P": 60, "A": small + 60},
        )
        moves = _moved_set(sv, incumbent, h, pin_op_id="P")
        _annotate_move_reasons(moves, sv, h, pin_op_id="P")
        a = next(m for m in moves if m["operation_ref"] == "A")
        assert "reason" not in a


# ---------------------------------------------------------------------------
# CI latency regression on the demo fixture (slow: one pipeline solve + re-solve)
# ---------------------------------------------------------------------------

def _solve_fixture(tmp_path_factory, scenario: str, snap: str) -> Path:
    tmp = tmp_path_factory.mktemp(f"sandbox_{scenario}")
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
def solved_distinct(tmp_path_factory):
    # the non-degenerate demo fixture: distinct rates → a unique optimum that
    # PROVES fast, so a pinned re-solve returns a verdict within budget.
    return _solve_fixture(tmp_path_factory, "multi_route_distinct", SNAP)


@pytest.mark.slow
def test_single_pin_resolve_returns_a_verdict_within_budget(solved_distinct):
    """The R-T1c CI acceptance: pin one op at its displayed placement and the
    sandbox re-solve returns a VERDICT within the budget token — outcome (1).
    A heavy fixture fails here before it fails a demo."""
    result = sandbox_pin_resolve(
        out_dir=solved_distinct, snapshot_id=SNAP, budget_s=SANDBOX_BUDGET_S,
        deterministic=True,
    )
    assert result.outcome == SANDBOX_VERDICT, (
        f"sandbox returned {result.outcome} ({result.status}) in "
        f"{result.wall_time_s}s"
    )
    assert result.within_budget is True
    assert result.wall_time_s <= SANDBOX_BUDGET_S + 1.0
    assert result.feasible is True
    # session 3.3 CU5: the applied time limit is echoed so budget-vs-actual is
    # inspectable straight from the payload (= the budget in normal operation).
    assert result.applied_time_limit_s == SANDBOX_BUDGET_S
    # pinning at the incumbent placement is the latency floor: a zero-delta
    # confirmation (the surroundings need not move).
    assert result.delta_pct == 0 or result.delta_pct is None


@pytest.mark.slow
def test_moved_set_carries_the_pin_and_reports_old_and_new(solved_distinct):
    """R-DP7: a feasible re-solve returns the moved-set old → new. Pinning at
    the incumbent placement is the zero-delta floor, so the ONLY guaranteed
    member is the pinned op itself (its neighbours need not move); every move
    carries both endpoints and a start-shift, and the pinned op is flagged and
    listed first (so the delta card leads with what the planner touched)."""
    result = sandbox_pin_resolve(
        out_dir=solved_distinct, snapshot_id=SNAP, budget_s=SANDBOX_BUDGET_S,
        deterministic=True,
    )
    assert result.feasible is True
    assert result.moves, "a feasible re-solve reports its moved-set"
    assert result.moves[0]["pinned"] is True, "the pinned op leads the card"
    assert sum(m["pinned"] for m in result.moves) == 1
    for m in result.moves:
        assert m["from_resource"] and m["to_resource"]
        assert m["from_start"] and m["to_start"]
        assert isinstance(m["start_delta_min"], int)
    # the pin is echoed back for the tentative-bar identity
    assert result.pin["operation_ref"] == result.moves[0]["operation_ref"]


@pytest.mark.slow
def test_pin_at_a_specific_placement_is_honored(solved_distinct):
    """R-DP1 literalness: a pin names the op, machine, and start; the re-solve
    holds exactly that and returns a classified, within-budget outcome."""
    reader = SnapshotStore(Path(solved_distinct) / "snapshots").load_snapshot(SNAP)
    a = next(iter(reader.iter_entities("assignment")))
    op = a["operation_ref"]
    rid = (a.get("resource_assignments") or [{}])[0].get("resource_ref")
    start = (a.get("phase_windows") or {}).get("run", [{}])[0].get("start")
    result = sandbox_pin_resolve(
        out_dir=solved_distinct, snapshot_id=SNAP,
        pin_op_id=op, pin_resource_id=rid, pin_start_iso=start,
        budget_s=SANDBOX_BUDGET_S, deterministic=True,
    )
    assert result.outcome in (SANDBOX_VERDICT, SANDBOX_FEASIBLE_UNPROVEN)
    assert result.within_budget is True


@pytest.mark.slow
def test_saturated_demo_fixture_returns_a_within_budget_answer(tmp_path_factory):
    """CU4 FINDING (honest, not hidden): the SATURATED multi_route fixture is
    degenerate by design (the identical-rate R0/R1 pair — what makes the pool
    surface cross-machine ghosts). A pinned re-solve there finds the
    incumbent-cost placement (delta 0) but cannot PROVE optimality inside the
    budget, so it returns outcome (2) — a shippable, FLAGGED "≈ delta, bound
    not proven" card — WITHIN budget, never a hang. This is exactly the honest
    second outcome R-T1c designs for; the verdict regression uses the
    non-degenerate distinct fixture."""
    out = _solve_fixture(tmp_path_factory, "multi_route", "snap-sat")
    result = sandbox_pin_resolve(
        out_dir=out, snapshot_id="snap-sat", budget_s=SANDBOX_BUDGET_S,
        deterministic=True,
    )
    assert result.outcome in (SANDBOX_VERDICT, SANDBOX_FEASIBLE_UNPROVEN)
    assert result.outcome != SANDBOX_NO_VERDICT, "the demo must never hang"
    assert result.within_budget is True
    assert result.feasible is True

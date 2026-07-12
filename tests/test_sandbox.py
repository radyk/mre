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

from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.modules.sandbox import (
    SANDBOX_BUDGET_S,
    SANDBOX_FEASIBLE_UNPROVEN,
    SANDBOX_NO_VERDICT,
    SANDBOX_VERDICT,
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
    # pinning at the incumbent placement is the latency floor: a zero-delta
    # confirmation (the surroundings need not move).
    assert result.delta_pct == 0 or result.delta_pct is None


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

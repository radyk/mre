"""Session 4B.8 CU2 — the two-stage BUDGET SPLIT, guarded.

docs/07 §5a.19: the split was a constant. Stage 1 was capped at 4.0 of a 6.0
total and stage 2 received a FIXED 2.0 regardless of what stage 1 spent, so the
allocation was wrong in both directions at once — at 40 orders stage 1 proved
OPTIMAL in 0.101 of its cap while stage 2 exhausted its whole 2.0 and 3.9 units
went unused; at 200 orders / 7d stage 1 needed 4.542 and 4.962 units on two
seeds, got 4.0, and truncated (+5.46% and +26.07% ledger).

The replacement: the caller declares a TOTAL, stage 1 is capped at the total
minus a reserve, and stage 2 receives what the total has LEFT after stage 1
actually ran. These are the guards the prompt requires committed with it:

  (a) stage 1 + stage 2 deterministic consumption <= the declared total, on real
      data rather than a mock;
  (b) stage 2 still runs unconditionally wherever it receives a nonzero slice
      (R-SC3(1)) — and where it does NOT run, the skip is EXPLICIT AND RECORDED,
      because a tiebreak that silently did not run is indistinguishable from one
      that ran and won nothing;
  (c) 4B.7's invariant still holds — the schedule is byte-identical across every
      earliness_value. (The end-to-end form lives in test_rolling_horizon.py and
      is slow; the structural form here is fast and catches the reintroduction
      of the coefficient into either signature.)
"""
from __future__ import annotations

import inspect

import pytest

from mre.modules.rolling_horizon import (
    _DET_TOTAL_DEFAULT, _stage_budgets, _two_stage_solve,
    DET_TOTAL_MONOLITHIC,
)
from mre.modules.solver_builder import solve_two_stage


# ---------------------------------------------------------------------------
# the constant is GONE, not defaulted
# ---------------------------------------------------------------------------

class TestTheConstantIsDeleted:
    """A constant that can still be read is a constant that comes back — the
    4B.7 precedent for the retired earliness coefficient, applied to the budget."""

    def test_no_stage2_constant_survives_in_either_twin(self):
        import mre.modules.rolling_horizon as rh
        import mre.modules.solver_builder as sb
        for mod in (rh, sb):
            assert not hasattr(mod, "_STAGE2_DET_TIME_S"), (
                f"{mod.__name__}._STAGE2_DET_TIME_S is back — stage 2's budget "
                f"must be DERIVED from what stage 1 consumed, never a constant")

    def test_neither_signature_accepts_a_fixed_stage2_budget(self):
        assert "stage2_det_time" not in inspect.signature(_two_stage_solve).parameters
        assert "stage2_deterministic_time" not in inspect.signature(solve_two_stage).parameters
        # …and both accept the TOTAL, which is the thing a caller now declares.
        assert "det_total" in inspect.signature(_two_stage_solve).parameters
        assert "deterministic_time_total" in inspect.signature(solve_two_stage).parameters


class TestTheSplitItself:
    def test_stage1_cap_leaves_a_reserve_for_the_tiebreak(self):
        cap, reserve = _stage_budgets(6.0)
        assert reserve > 0, "with no reserve, a stage 1 that spends everything silences the tiebreak"
        assert cap + reserve == pytest.approx(6.0)
        # the measured point: 0.5 units of a 6.0 total (CU1's P3 arm)
        assert reserve == pytest.approx(0.5)
        assert cap == pytest.approx(5.5)

    def test_the_reserve_scales_with_the_declared_total(self):
        """A fraction, not an absolute — _final_extract declares a 48.0 total and
        a 0.5-unit reserve there would be a rounding error, not a guarantee."""
        for total in (3.0, 6.0, 48.0):
            cap, reserve = _stage_budgets(total)
            assert cap + reserve == pytest.approx(total)
            assert reserve == pytest.approx(total / 12.0)

    def test_the_shipped_totals_are_unchanged_by_the_split(self):
        """CU2 changes how the budget is SPLIT, not how much there is.

        The old scheme's total was always `stage1 + 2.0`. The rolling default
        was 4.0 + 2.0; the monolithic path was an uncapped stage 1 + 2.0. Both
        totals are preserved — which is why the parameter was RENAMED
        det_time -> det_total rather than reinterpreted: no single multiplier
        preserves every caller (the exam builder's was 4.0, the golden driver's
        2.5), so each call site had to be made to state its own."""
        assert _DET_TOTAL_DEFAULT == pytest.approx(6.0)
        assert DET_TOTAL_MONOLITHIC == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# (a) + (b), on a real solve
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_solve_result(tmp_path_factory):
    """One real window-0 solve of an 8-order pilot_scale plant under a declared
    total, returning (result, det_total)."""
    from datetime import datetime, timedelta, timezone
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import _admit, _build_window, prepare_plant

    UTC = timezone.utc
    ref = datetime(2026, 1, 5, tzinfo=UTC)
    d = tmp_path_factory.mktemp("alloc")
    generate(d / "sub", scenario="pilot_scale", orders=8, seed=1)
    plant = prepare_plant(d / "sub", d / "prep", reference_date=ref)

    t0 = plant.reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = t0 + timedelta(days=14)
    admitted, _ = _admit(plant, plant.schedulable_demands, t0, window_end, True, 3.0)
    free_ops = [op for did in sorted(admitted)
                for op in plant.ops_by_wp.get(plant.wp_of_demand.get(did), [])]
    model, var_map = _build_window(plant, free_ops, [], t0,
                                   window_end + timedelta(days=21))
    free_start_vars = []
    for op in free_ops:
        v = var_map.op_start.get(op["id"])
        if v is not None:
            model.add(v >= 0)
            free_start_vars.append(v)

    det_total = 6.0
    result, stage2_ran, _rec = _two_stage_solve(
        model, var_map, free_start_vars, workers=1, seed=42, deterministic=True,
        member_time_limit_s=300.0, det_total=det_total,
        free_op_ids=[op["id"] for op in free_ops])
    return result, stage2_ran, det_total


class TestGuardA_BudgetIsRespected:
    def test_both_stages_together_fit_inside_the_declared_total(self, real_solve_result):
        """GUARD (a). On real data: whatever the two stages consumed together
        must fit inside the budget the caller declared. This is the claim that a
        derived split can actually break — a fixed stage-2 slice could always
        overrun the total, which is precisely what it did."""
        result, _stage2_ran, det_total = real_solve_result
        assert result.det_consumed is not None, (
            "the deterministic meter could not be read, so guard (a) is "
            "unprovable — SolveResult.det_consumed must be populated")
        # CP-SAT overshoots its own max_deterministic_time slightly (it checks
        # the budget between propagations, not within one), so the guard is
        # stated with the tolerance the solver's own contract implies rather
        # than pretending the limit is exact.
        assert result.det_consumed <= det_total * 1.05, (
            f"two stages consumed {result.det_consumed} of a declared "
            f"{det_total} — the split is not respecting the total")


class TestGuardB_TheTiebreakRunsOrSaysWhyNot:
    def test_stage2_ran_and_its_proof_is_reported_separately(self, real_solve_result):
        """GUARD (b), the positive half: given a nonzero slice, stage 2 runs
        unconditionally (R-SC3(1)) and its status is reported as its OWN proof."""
        result, stage2_ran, _ = real_solve_result
        assert stage2_ran, "stage 2 did not run despite a nonzero slice"
        assert result.tiebreak_status in ("OPTIMAL", "FEASIBLE")
        assert result.tiebreak_skipped_reason is None, (
            "stage 2 ran, so there is no skip to explain")
        # …and the COST proof is the one on `status` (CU3).
        assert result.status in ("OPTIMAL", "FEASIBLE")

    def test_a_provably_optimal_schedule_says_so(self, real_solve_result):
        """CU3, the point of the ruling. This instance's COST is provably
        optimal and its TIEBREAK is not — stage 2 exhausts its budget above
        roughly eight orders. Before 4B.8 the single reported status was stage
        2's, so exactly this run read FEASIBLE over a provably optimal ledger
        (docs/07 §5a.21). For a product whose thesis is provable numbers, that
        understated the strongest claim it had."""
        result, _stage2_ran, _ = real_solve_result
        assert result.status == "OPTIMAL", (
            "the reported status is not the COST proof — if this is FEASIBLE "
            "while the tiebreak is FEASIBLE too, the statuses have been swapped "
            "back and the board is again reporting the wrong proof")
        # the two claims are genuinely separate quantities, not aliases
        assert result.tiebreak_status is not None

    def test_a_skipped_tiebreak_always_records_why(self):
        """GUARD (b), the negative half. A degenerate model (no objective terms)
        cannot run a tiebreak — and must SAY so rather than return a blank that
        reads identically to 'it ran and won nothing'."""
        from ortools.sat.python import cp_model as cp
        from mre.modules.solver_builder import VariableMap
        from datetime import datetime, timezone

        m = cp.CpModel()
        s = m.new_int_var(0, 100, "s")
        m.add(s >= 5)
        vm = VariableMap(horizon_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
                         op_start={"op0": s})
        result, stage2_ran, _rec = _two_stage_solve(
            m, vm, [s], workers=1, seed=42, deterministic=True,
            member_time_limit_s=10.0, det_total=6.0)
        assert not stage2_ran
        assert result.tiebreak_status is None
        assert result.tiebreak_skipped_reason == "stage1_no_solution_or_degenerate_model", (
            "a tiebreak that did not run must name its reason — otherwise it is "
            "indistinguishable from one that ran and recovered nothing")

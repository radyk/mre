"""R-SC3 two-stage FLOOR on the monolithic solve path (Session 4B.4, CU1).

R-SC3 (docs/04) says "the solver" prefers earlier starts among cost-optimal
placements — UNSCOPED. Session 4B.2d implemented the two-stage floor on the
rolling path only; the monolithic schedule of record still solved cost-only and
parked cost-equal work arbitrarily. The founder's live finding (2026-07-23): an
op sat at 14:39 behind a FREE 11:21 slot on the same machine, and dragging it
earlier cost $0.00 — the floor was simply not being applied.

`solver_builder.solve_two_stage` lifts the same shape into a shared helper the
monolithic path uses. These tests pin its three contracts directly on a small
hand-built CP-SAT model (no dataset dependency, fast):

  (a) the ORD-000038 class — a cost-equal earlier slot is TAKEN (the founder's
      gesture, automated): after the floor, the op-start sum is provably minimal,
      so no cost-equal op is parked late behind an open earlier slot;
  (b) cost-neutrality — the two-stage cost objective equals a stage-1-only
      (cost-only) solve to epsilon 0;
  (c) determinism — the same inputs give byte-identical placements run-to-run.

The end-to-end proof on real data is tests/test_defaults_reproduce_baseline.py:
the sample_data cost ledger is IDENTICAL after the two-stage regen
(24769/19429/4500/840) while placements shift to the earliest cost-optimal slot.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from mre.modules.solver_builder import VariableMap, solve_two_stage
from mre.modules.solve_runner import SolveRunner

UTC = timezone.utc
_REF = datetime(2026, 1, 1, tzinfo=UTC)


def _two_disjoint_ops_one_machine():
    """A minimal model reproducing the founder's shape: two duration-10 ops that
    must be disjoint on ONE machine, and a COST term that is start-independent
    (cost-equal wherever they sit). Cost-only, the solver may park them anywhere
    disjoint; the floor must pull them to the earliest slots. Returns
    (model, var_map, (a, b) start vars)."""
    from ortools.sat.python import cp_model as cp

    m = cp.CpModel()
    a = m.new_int_var(0, 500, "a_start")
    ea = m.new_int_var(0, 510, "a_end")
    m.add(ea == a + 10)
    b = m.new_int_var(0, 500, "b_start")
    eb = m.new_int_var(0, 510, "b_end")
    m.add(eb == b + 10)
    ia = m.new_interval_var(a, 10, ea, "ia")
    ib = m.new_interval_var(b, 10, eb, "ib")
    m.add_no_overlap([ia, ib])
    # A start-INDEPENDENT cost term (constant 7) — so every disjoint placement is
    # cost-optimal and only the floor decides where the ops sit.
    c = m.new_int_var(7, 7, "cost")
    m.minimize(c)

    vm = VariableMap(horizon_start=_REF)
    vm.op_start = {"A": a, "B": b}
    vm.op_end = {"A": ea, "B": eb}
    vm.op_assign = {"A": {}, "B": {}}
    vm.objective_terms = [c]
    return m, vm, (a, b)


def _solve(model, var_map, seed=42):
    return solve_two_stage(
        model, var_map, stage1_reporter=None, earliness_coeff_scaled=0,
        time_limit_seconds=10.0, num_search_workers=1, random_seed=seed,
    )


class TestTwoStageFloor:
    def test_a_cost_equal_earlier_slot_is_taken(self):
        """The ORD-000038 class: cost-equal ops are pulled to the earliest slots,
        so the op-start sum is the provable minimum (10 = 0 + 10 for two
        disjoint duration-10 ops). Cost-only there is no such guarantee."""
        model, vm, _ = _two_disjoint_ops_one_machine()
        result, stage2_ran = _solve(model, vm)
        assert stage2_ran, "stage 2 must run when there are free op-starts + cost terms"
        starts = result.solve_values.op_start_minutes
        assert min(starts["A"], starts["B"]) == 0
        assert starts["A"] + starts["B"] == 10, (
            f"floor did not minimise the start sum: {starts}")

    def test_b_cost_neutral_vs_stage1_only(self):
        """Two-stage cost objective == a stage-1-only (cost-only) solve, epsilon 0.
        Stage 2 only re-shuffles starts UNDER a hard cost cap, so cost cannot move."""
        # stage-1-only baseline: the plain cost solve of the same model.
        model1, vm1, _ = _two_disjoint_ops_one_machine()
        stage1 = SolveRunner(time_limit_seconds=10.0, num_search_workers=1,
                             random_seed=42).solve(model1, vm1, None)
        # two-stage on a fresh identical model.
        model2, vm2, _ = _two_disjoint_ops_one_machine()
        two_stage, _ran = _solve(model2, vm2)
        assert stage1.objective is not None and two_stage.objective is not None
        assert abs(two_stage.objective - stage1.objective) < 1e-9, (
            f"stage-2 cost {two_stage.objective} != stage-1 cost {stage1.objective}")

    def test_c_deterministic_run_to_run(self):
        """Same inputs → byte-identical placements (workers=1 + seed + the stage-2
        deterministic-time budget)."""
        m1, vm1, _ = _two_disjoint_ops_one_machine()
        r1, _ = _solve(m1, vm1)
        m2, vm2, _ = _two_disjoint_ops_one_machine()
        r2, _ = _solve(m2, vm2)
        assert r1.solve_values.op_start_minutes == r2.solve_values.op_start_minutes

    def test_stage2_skipped_without_free_starts(self):
        """With no free op-starts the helper returns the stage-1 result as-is
        (stage2_ran False) — nothing to tiebreak."""
        model, vm, _ = _two_disjoint_ops_one_machine()
        result, stage2_ran = solve_two_stage(
            model, vm, stage1_reporter=None, earliness_coeff_scaled=0,
            free_start_vars=[], time_limit_seconds=10.0,
            num_search_workers=1, random_seed=42)
        assert stage2_ran is False
        assert result.status in ("OPTIMAL", "FEASIBLE")

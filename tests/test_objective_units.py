"""The recorded solver objective is NOT the cost objective (Session 4B.6c, item 4).

Session 4B.6c measured whether a single lexicographic objective
(``BIG * cost + sum(starts)``) could replace the R-SC3 two-stage tiebreak. It
cannot (it degrades CP-SAT's search badly — see SESSION_CLOSEOUT.md), but the
code-read it required found a live seam worth pinning, and this module pins it.

THE SEAM. ``solve_two_stage`` / ``rolling_horizon._two_stage_solve`` record
STAGE 1's objective, and stage 1 minimizes ``sum(objective_terms) +
earliness_coeff_scaled * sum(free-op starts)`` whenever the plant declares a
positive ``earliness_value`` (R-SC3). That recorded number is what
``solution_pool._incumbent_objective`` reads and what
``add_objective_upper_bound`` then applies TO ``sum(objective_terms)`` ALONE.
The two quantities are in different units the moment the coefficient is
positive, so the pool's "member objective <= incumbent x (1 + X%)" bound is
looser than X% by exactly the earliness term.

These tests do NOT assert the seam is correct — they assert what it currently
DOES, numerically, so that any change to what the solver minimizes (candidate
B, a relabel, or a fix) has to come here and say so out loud.

Nothing about the money surfaces is at risk: every dollar figure the cockpit
shows is extracted from the cost LEDGER, never from this objective (the
Phase-3 exit-audit rule, asserted in ``sandbox.SandboxResult``'s own field
docs and ``sandboxui.js``). This module is about the objective's OTHER
consumer — the pool's cost bound.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

UTC = timezone.utc


def _tiny_model(coeff_positive_start: int = 20):
    """A hand-built model with a CONSTANT cost term and one free start var that
    is forced away from zero. Cost is start-independent, so any difference
    between the recorded objective and the cost objective is entirely the
    earliness term — which is the whole point."""
    from ortools.sat.python import cp_model as cp

    from mre.modules.solver_builder import VariableMap

    m = cp.CpModel()
    s = m.new_int_var(0, 100, "s_op1")
    e = m.new_int_var(0, 200, "e_op1")
    m.add(e == s + 10)
    m.add(s >= coeff_positive_start)
    cost = m.new_int_var(0, 1000, "cost")
    m.add(cost == 300)                      # start-independent by construction
    vm = VariableMap(horizon_start=datetime(2026, 7, 1, tzinfo=UTC))
    vm.op_start = {"op1": s}
    vm.op_end = {"op1": e}
    vm.objective_terms = [cost]
    m.minimize(sum(vm.objective_terms))     # what SolverBuilder.build leaves set
    return m, vm, s


COEFF = 5           # = _COST_SCALE * 0.05 $/min, pilot_scale's declared value


def test_recorded_objective_carries_the_earliness_term_monolithic():
    """solve_two_stage (the monolithic seam) records STAGE 1's objective, which
    includes ``coeff * sum(starts)``. Cost here is a constant 300 and the start
    is forced to 20, so the recorded objective is 300 + 5*20 = 400 — NOT 300."""
    from mre.modules.solver_builder import solve_two_stage

    m, vm, s = _tiny_model()
    result, stage2_ran = solve_two_stage(
        m, vm, free_start_vars=[s], earliness_coeff_scaled=COEFF,
        time_limit_seconds=10.0, num_search_workers=1, random_seed=42)

    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert result.objective == pytest.approx(400.0)
    # the COST objective at that same solution
    assert result.objective != pytest.approx(300.0)
    assert result.solve_values.op_start_minutes["op1"] == 20


def test_recorded_objective_is_the_cost_objective_at_coefficient_zero():
    """The boundary the R-SC3 ruling turns on: at coefficient 0 the priced term
    is OMITTED ENTIRELY (never multiplied by zero), so the recorded objective IS
    the cost objective and the pool's bound is in the units it expects."""
    from mre.modules.solver_builder import solve_two_stage

    m, vm, s = _tiny_model()
    result, _ = solve_two_stage(
        m, vm, free_start_vars=[s], earliness_coeff_scaled=0,
        time_limit_seconds=10.0, num_search_workers=1, random_seed=42)

    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert result.objective == pytest.approx(300.0)


def test_rolling_two_stage_returns_stage_twos_objective_not_stage_ones():
    """THE TWO COPIES DIVERGE, and this pins the divergence rather than blessing it.

    ``solver_builder.solve_two_stage`` deliberately rebuilds its result carrying
    STAGE 1's objective with stage 2's placements (``solver_builder.py:409-418``,
    so "the M6 solve_complete objective the assembler + _incumbent_objective read
    stays the COST objective"). ``rolling_horizon._two_stage_solve`` returns the
    stage-2 ``SolveResult`` WHOLE (``rolling_horizon.py:166-172``) — so its
    ``.objective`` is stage 2's, which is ``sum(free-op starts)`` in MINUTES.

    Here: cost is a constant 300, the earliness coefficient is 5, the start is
    forced to 20. Monolithic records 400 (cost + 5*20). Rolling records 20 — a
    minute count, not a cost in any units.

    ``build_rolling_view`` writes exactly this value into its M6 ``solve_complete``
    payload (``rolling_horizon.py:574-576``), and ``WindowMetric.objective``
    carries it too (``:973``), so on a rolling board the incumbent "objective"
    every downstream reader sees is a sum of start minutes. Found by the Session
    4B.6c item-4 consumer read; REPORTED, deliberately NOT fixed there."""
    from mre.modules.rolling_horizon import _two_stage_solve

    m, vm, s = _tiny_model()
    result, stage2_ran = _two_stage_solve(
        m, vm, [s], COEFF, workers=1, seed=42, deterministic=True,
        member_time_limit_s=10.0, stage1_det_time=2.0)

    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert stage2_ran is True
    assert result.objective == pytest.approx(20.0)          # sum of starts, minutes
    assert result.objective != pytest.approx(400.0)         # not stage 1's
    assert result.objective != pytest.approx(300.0)         # not the cost objective


def test_pool_cost_bound_is_looser_than_its_stated_tolerance():
    """The CONSEQUENCE, pinned as arithmetic rather than as prose.

    solution_pool computes ``int(incumbent_objective * (1 + tolerance_pct/100))``
    and hands it to ``add_objective_upper_bound``, which constrains
    ``sum(objective_terms)``. With the earliness term in the incumbent objective
    (400) but not in the bounded expression (300), a stated 5% tolerance is
    really 40%. This test states that number; it does not bless it."""
    from ortools.sat.python import cp_model as cp

    from mre.modules.solver_builder import VariableMap, add_objective_upper_bound

    recorded_objective = 400.0     # what _incumbent_objective returns (above)
    cost_objective = 300.0         # what add_objective_upper_bound constrains
    tolerance_pct = 5.0

    bound = int(recorded_objective * (1 + tolerance_pct / 100.0))
    assert bound == 420
    effective_pct = (bound - cost_objective) / cost_objective * 100.0
    assert effective_pct == pytest.approx(40.0)
    assert effective_pct > tolerance_pct

    # and the bound really is applied to the COST expression, not the recorded one
    m = cp.CpModel()
    vm = VariableMap(horizon_start=datetime(2026, 7, 1, tzinfo=UTC))
    x = m.new_int_var(0, 1000, "x")
    vm.objective_terms = [x]
    m.maximize(x)
    add_objective_upper_bound(m, vm, bound)
    solver = cp.CpSolver()
    assert solver.Solve(m) == cp.OPTIMAL
    assert solver.Value(x) == bound

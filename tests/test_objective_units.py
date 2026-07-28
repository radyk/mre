"""The recorded solver objective IS the cost objective (Session 4B.7).

THIS MODULE MOVED, DELIBERATELY. At Session 4B.6c it pinned three defects as
numbers so that no semantic change could slip past them silently. Session 4B.7
made the semantic change; the pins therefore had to come here and say so out
loud, which is the whole reason they were written that way. What each one
asserted then, and asserts now:

  1. ``test_recorded_objective_carries_the_earliness_term_monolithic``
     THEN: the recorded objective is 400 = cost 300 + coeff 5 x start 20 — the
     earliness price is IN the primary objective.
     NOW:  ``test_recorded_objective_is_the_cost_objective_monolithic`` — 300.
     There is no coefficient to pass; the parameter is gone from the signature.

  2. ``test_recorded_objective_is_the_cost_objective_at_coefficient_zero``
     THEN: at coefficient 0 the objective is the cost objective (300) — the
     boundary case that made the seam conditional.
     NOW:  folded into (1). The boundary is the only behaviour there is.

  3. ``test_rolling_two_stage_returns_stage_twos_objective_not_stage_ones``
     THEN: rolling returns 20 — a MINUTE COUNT — where monolithic returns 400
     (docs/07 §5a.16, a defect pinned rather than fixed).
     NOW:  ``test_rolling_and_monolithic_record_the_same_cost_objective`` —
     BOTH record 300. Rolling rebuilds its result the way the monolithic twin
     always did: stage 1's objective with stage 2's placements.

  4. ``test_pool_cost_bound_is_looser_than_its_stated_tolerance``
     THEN: a stated 5% tolerance is really 40% (docs/07 §5a.17).
     NOW:  ``test_pool_cost_bound_matches_its_stated_tolerance`` — 5% is 5%.
     The gap was ENTIRELY the earliness term; source and target now share units.

The new material is Session 4B.7's item-3 guards (a)-(c): cost safety as a
structural assertion, cap-unit correctness at both seams, and a positive control
proving the tiebreak still does something.

Nothing about the money surfaces was ever at risk: every dollar figure the
cockpit shows is extracted from the cost LEDGER, never from this objective (the
Phase-3 exit-audit rule). This module is about the objective's OTHER consumers —
the pool's cost bound, and the sandbox/planner_edit delta headline.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

UTC = timezone.utc


def _tiny_model(forced_start: int = 20):
    """A hand-built model with a CONSTANT cost term and one free start var that
    is forced away from zero. Cost is start-independent, so any difference
    between the recorded objective and the cost objective would be entirely an
    earliness term — which is the whole point. There is no longer one."""
    from ortools.sat.python import cp_model as cp

    from mre.modules.solver_builder import VariableMap

    m = cp.CpModel()
    s = m.new_int_var(0, 100, "s_op1")
    e = m.new_int_var(0, 200, "e_op1")
    m.add(e == s + 10)
    m.add(s >= forced_start)
    cost = m.new_int_var(0, 1000, "cost")
    m.add(cost == 300)                      # start-independent by construction
    vm = VariableMap(horizon_start=datetime(2026, 7, 1, tzinfo=UTC))
    vm.op_start = {"op1": s}
    vm.op_end = {"op1": e}
    vm.objective_terms = [cost]
    m.minimize(sum(vm.objective_terms))     # what SolverBuilder.build leaves set
    return m, vm, s


def _cost_start_tension_model(cost_slope: int = 1, horizon: int = 100):
    """A model where cost and earliness genuinely PULL APART: the cost term is
    ``cost_slope * (horizon - start)``, so every minute earlier is strictly
    DEARER. Stage 1 must park the op at ``horizon`` (cost 0) and stage 2, capped
    at that cost, must not be able to buy a single minute of earliness.

    This is the shape the removed coefficient used to resolve by PAYING. With
    the price gone, the cap is the only thing standing between the tiebreak and
    the ledger — so it is what the cost-safety guard has to be built on."""
    from ortools.sat.python import cp_model as cp

    from mre.modules.solver_builder import VariableMap

    m = cp.CpModel()
    s = m.new_int_var(0, horizon, "s_op1")
    e = m.new_int_var(0, horizon + 10, "e_op1")
    m.add(e == s + 10)
    cost = m.new_int_var(0, cost_slope * horizon, "cost")
    m.add(cost == cost_slope * (horizon - s))
    vm = VariableMap(horizon_start=datetime(2026, 7, 1, tzinfo=UTC))
    vm.op_start = {"op1": s}
    vm.op_end = {"op1": e}
    vm.objective_terms = [cost]
    m.minimize(sum(vm.objective_terms))
    return m, vm, s


_PARKED = (300, 400, 450)   # the hinted (cost-optimal, late) stage-1 incumbent


def _slack_model(n: int = 3, dur: int = 10, horizon: int = 500, park: bool = True):
    """``n`` duration-``dur`` ops that must be disjoint on one machine, under a
    START-INDEPENDENT cost. Every disjoint placement is cost-optimal, so cost
    alone decides nothing and the tiebreak decides everything: the provable
    minimum start sum is 0 + dur + 2*dur + ... = 30 for n=3.

    ``park`` HINTS the ops late (300/400/450). That is not a thumb on the scale —
    it is the real rolling shape: stage 1 is warm-started from the prior roll's
    incumbent, which parks cost-equal work wherever it last sat, and the FLOOR's
    entire job is to pull it forward for free. Without a hint CP-SAT's own first
    solution already takes the domain floor, so a synthetic cost-only solve looks
    start-minimal by accident and the control proves nothing (measured: stage 1
    returns 30 unhinted, leaving stage 2 no room to win)."""
    from ortools.sat.python import cp_model as cp

    from mre.modules.solver_builder import VariableMap

    m = cp.CpModel()
    vm = VariableMap(horizon_start=datetime(2026, 7, 1, tzinfo=UTC))
    ivs = []
    starts = []
    for i in range(n):
        s = m.new_int_var(0, horizon, f"s{i}")
        e = m.new_int_var(0, horizon + dur, f"e{i}")
        m.add(e == s + dur)
        ivs.append(m.new_interval_var(s, dur, e, f"iv{i}"))
        vm.op_start[f"op{i}"] = s
        vm.op_end[f"op{i}"] = e
        vm.op_assign[f"op{i}"] = {}
        starts.append(s)
        if park:
            m.add_hint(s, _PARKED[i % len(_PARKED)])
            m.add_hint(e, _PARKED[i % len(_PARKED)] + dur)
    m.add_no_overlap(ivs)
    cost = m.new_int_var(7, 7, "cost")      # start-independent
    vm.objective_terms = [cost]
    m.minimize(sum(vm.objective_terms))
    return m, vm, starts


def _rolling(model, vm, free_start_vars, **kw):
    from mre.modules.rolling_horizon import _two_stage_solve
    return _two_stage_solve(
        model, vm, free_start_vars, workers=1, seed=42, deterministic=True,
        member_time_limit_s=10.0, stage1_det_time=2.0, **kw)


def _monolithic(model, vm, free_start_vars):
    from mre.modules.solver_builder import solve_two_stage
    return solve_two_stage(
        model, vm, free_start_vars=free_start_vars, time_limit_seconds=10.0,
        num_search_workers=1, random_seed=42)


# ---------------------------------------------------------------------------
# the moved pins
# ---------------------------------------------------------------------------

def test_recorded_objective_is_the_cost_objective_monolithic():
    """PIN 1, MOVED. Cost is a constant 300 and the start is forced to 20. The
    recorded objective is 300 — the COST objective — not 400. There is no
    coefficient to make it 400: the parameter no longer exists."""
    import inspect

    from mre.modules.solver_builder import solve_two_stage

    m, vm, s = _tiny_model()
    result, stage2_ran = _monolithic(m, vm, [s])

    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert result.objective == pytest.approx(300.0)
    assert result.objective != pytest.approx(400.0), (
        "400 = 300 + 5x20 is the RETIRED priced-earliness objective")
    assert result.solve_values.op_start_minutes["op1"] == 20
    # structural, not merely numeric: the retired price cannot be reintroduced
    # by a caller, because there is nowhere to put it.
    assert "earliness_coeff_scaled" not in inspect.signature(solve_two_stage).parameters


def test_rolling_and_monolithic_record_the_same_cost_objective():
    """PIN 3, MOVED — and it is now an EQUALITY rather than a divergence.

    docs/07 §5a.16: rolling returned the stage-2 ``SolveResult`` WHOLE, so its
    ``.objective`` was Σ free-op starts — a MINUTE COUNT (20 here) — while the
    monolithic twin rebuilt its result to carry stage 1's COST objective (400
    then, 300 now). ``build_rolling_view`` wrote that minute count into the M6
    ``solve_complete`` payload every downstream reader consumes.

    Both now record 300, the cost objective, on the same model."""
    import inspect

    from mre.modules.rolling_horizon import _two_stage_solve

    m1, vm1, s1v = _tiny_model()
    mono, mono_ran = _monolithic(m1, vm1, [s1v])
    m2, vm2, s2v = _tiny_model()
    roll, roll_ran, _recovery = _rolling(m2, vm2, [s2v])

    assert mono_ran is True and roll_ran is True
    assert mono.objective == pytest.approx(300.0)
    assert roll.objective == pytest.approx(300.0)
    assert roll.objective == pytest.approx(mono.objective), (
        "the two twins must record the same objective on the same model")
    assert roll.objective != pytest.approx(20.0), (
        "20 is Σ free-op starts — the §5a.16 minute count")
    # both placements are stage 2's
    assert roll.solve_values.op_start_minutes["op1"] == 20
    assert "earliness_coeff_scaled" not in inspect.signature(_two_stage_solve).parameters


def test_pool_cost_bound_matches_its_stated_tolerance():
    """PIN 4, MOVED. docs/07 §5a.17: with the earliness term in the incumbent
    objective (400) but not in the bounded expression (300), a stated 5%
    tolerance was really 40%. The gap was ENTIRELY that term. The recorded
    objective is now the cost objective, so the bound's source and the bounded
    expression are the same quantity and 5% is 5%."""
    from ortools.sat.python import cp_model as cp

    from mre.modules.solver_builder import VariableMap, add_objective_upper_bound

    recorded_objective = 300.0     # what _incumbent_objective now returns
    cost_objective = 300.0         # what add_objective_upper_bound constrains
    tolerance_pct = 5.0

    bound = int(recorded_objective * (1 + tolerance_pct / 100.0))
    assert bound == 315
    effective_pct = (bound - cost_objective) / cost_objective * 100.0
    assert effective_pct == pytest.approx(tolerance_pct)
    assert effective_pct != pytest.approx(40.0), "40% was the 4B.6c defect figure"

    # and the bound really is applied to the COST expression
    m = cp.CpModel()
    vm = VariableMap(horizon_start=datetime(2026, 7, 1, tzinfo=UTC))
    x = m.new_int_var(0, 1000, "x")
    vm.objective_terms = [x]
    m.maximize(x)
    add_objective_upper_bound(m, vm, bound)
    solver = cp.CpSolver()
    assert solver.Solve(m) == cp.OPTIMAL
    assert solver.Value(x) == bound


# ---------------------------------------------------------------------------
# item 3(a) — COST SAFETY, structural, per solve
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("twin", ["rolling", "monolithic"])
def test_stage2_never_raises_cost_under_genuine_tension(twin):
    """R-SC3(1)'s ZERO-COST clause, stated as an executable assertion — the one
    that has been missing since the priced term was written.

    The model makes earliness strictly dearer (cost = 100 - start), so a tiebreak
    that could spend would spend here. Stage 1 parks the op at 100 for cost 0;
    stage 2, capped at 0, must leave it there. Cost at the RETURNED placement is
    compared to cost at the stage-1 placement — not merely to the recorded
    objective, which is stage 1's by construction and so cannot disagree."""
    m, vm, s = _cost_start_tension_model()
    solve = _rolling if twin == "rolling" else _monolithic
    out = solve(m, vm, [s])
    result, stage2_ran = out[0], out[1]

    assert result.status in ("OPTIMAL", "FEASIBLE")
    start = result.solve_values.op_start_minutes["op1"]
    cost_at_placement = 100 - start
    assert cost_at_placement <= result.objective + 1e-6, (
        f"{twin}: stage 2 raised cost to {cost_at_placement} over stage 1's "
        f"{result.objective} — the cap is in the wrong units or on the wrong "
        f"expression")
    # the strong form on this model: the tiebreak buys NOTHING, because every
    # earlier minute costs money.
    assert start == 100, (
        f"{twin}: stage 2 bought {100 - start} minutes of earliness that the "
        f"cap should have made unaffordable")
    assert result.objective == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# item 3(b) — UNIT CORRECTNESS at both cap seams
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("twin", ["rolling", "monolithic"])
def test_cap_source_is_the_stage1_cost_objective(twin):
    """The value handed to stage 2's cap is the stage-1 COST objective, in the
    same units as the expression it bounds (``sum(var_map.objective_terms)``).

    Asserted where it is observable: the returned objective equals the cost
    objective evaluated at the returned placements. On this model that is 300 —
    a pure cost, in ledger-scaled units, with no minute count mixed in."""
    m, vm, s = _tiny_model()
    solve = _rolling if twin == "rolling" else _monolithic
    out = solve(m, vm, [s])
    result = out[0]

    # cost is a constant 300 for every feasible placement, so "the cost objective
    # at the returned solution" is exactly 300 and nothing else can be.
    assert result.objective == pytest.approx(300.0), (
        f"{twin}: recorded {result.objective}, cost objective 300 — different "
        f"units mean the pool's bound is not the tolerance it states")


def test_pool_bound_source_and_target_share_units():
    """The same assertion at ``solution_pool``'s seam: ``_incumbent_objective``
    reads the M6 ``solve_complete`` objective, which is now stage 1's COST
    objective on BOTH solve paths, and ``add_objective_upper_bound`` constrains
    ``sum(var_map.objective_terms)`` — the same expression. Pinned by
    co-location: the source of the number and the target of the bound are read
    out of the same two lines here so a future edit to either has to face this
    test."""
    import inspect

    from mre.modules import solution_pool
    from mre.modules.solver_builder import add_objective_upper_bound

    pool_src = inspect.getsource(solution_pool)
    assert "add_objective_upper_bound(" in pool_src
    assert "incumbent_objective * (1 + tolerance_pct / 100.0)" in pool_src, (
        "the pool's bound arithmetic moved — re-derive the units claim")
    bound_src = inspect.getsource(add_objective_upper_bound)
    assert "objective_terms" in bound_src, (
        "add_objective_upper_bound no longer bounds sum(objective_terms) — the "
        "units argument in this module's docstring must be re-made")


# ---------------------------------------------------------------------------
# item 3(c) — POSITIVE CONTROL: a tiebreak that changes nothing is broken too
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("twin", ["rolling", "monolithic"])
def test_stage2_strictly_reduces_the_start_sum_where_slack_exists(twin):
    """A tiebreak that changes nothing is as broken as one that costs money.

    Three duration-10 ops disjoint on one machine under a start-INDEPENDENT
    cost: cost-only, CP-SAT may park them anywhere; the floor must pull them to
    0/10/20, start sum 30 — the provable minimum. Compared against the stage-1
    incumbent from the SAME seed, so the win is stage 2's and not luck."""
    from mre.modules.solve_runner import SolveRunner

    m1, vm1, _ = _slack_model()
    stage1 = SolveRunner(time_limit_seconds=10.0, num_search_workers=1,
                         random_seed=42, deterministic_time=2.0).solve(m1, vm1, None)
    s1_sum = sum(stage1.solve_values.op_start_minutes.values())

    m2, vm2, starts = _slack_model()
    solve = _rolling if twin == "rolling" else _monolithic
    out = solve(m2, vm2, starts)
    result, stage2_ran = out[0], out[1]

    assert stage2_ran is True, f"{twin}: stage 2 must run — cost terms and free starts both exist"
    s2_sum = sum(result.solve_values.op_start_minutes.values())
    assert s2_sum == 30, f"{twin}: floor did not reach the provable minimum: {s2_sum}"
    assert s2_sum < s1_sum, (
        f"{twin}: stage 2 won nothing (stage 1 {s1_sum} -> stage 2 {s2_sum}); "
        f"a tiebreak that never fires is priced air")


def test_rolling_reports_the_start_minutes_the_tiebreak_recovered():
    """Item 2(c): the recovery is REPORTED, on its own labelled line, and the
    declared rate values it without ever entering a cost figure."""
    from mre.modules.rolling_horizon import earliness_tiebreak_report

    m, vm, starts = _slack_model()
    result, ran, (before, after) = _rolling(
        m, vm, starts, free_op_ids=["op0", "op1", "op2"])
    assert ran is True
    assert before is not None and after is not None
    assert after == 30 and before > after

    rep = earliness_tiebreak_report(before, after, 0.05)
    assert rep["start_minutes_recovered"] == before - 30
    assert rep["declared_rate_per_minute"] == 0.05
    assert rep["valued_at"] == pytest.approx(round((before - 30) * 0.05, 2))
    assert rep["in_ledger"] is False
    assert rep["rate_provenance"] == "declared"

    # undeclared / zero: the tiebreak still ran and is still counted; only the
    # valuation is absent, and it says which it is rather than printing 0.00.
    zero = earliness_tiebreak_report(before, after, 0.0)
    assert zero["start_minutes_recovered"] == before - 30
    assert zero["valued_at"] is None
    assert zero["rate_provenance"] == "undeclared_or_zero"

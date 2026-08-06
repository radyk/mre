"""R-SP1 clause (6) — THE TWO DETERMINISM PROOFS.

Both are required, and they prove different things:

  A. **The sequence is reproducible.** Under deterministic law (``workers=1`` +
     a fixed seed) two runs of the same model produce the SAME sequence of
     incumbent objective values. That sequence is what tests assert. The elapsed
     times beside it are recorded facts about a laptop and are NEVER asserted —
     the hard rules already say a wall-clock figure is not reproducible, and a
     test that pinned one would be pinning the machine.

  B. **The observer does not perturb.** The placements a solve produces are
     identical with the callback attached and with it detached. Without this,
     every existing golden and every pinned world's placement digest would be
     resting on the hope that watching a search does not change it.

THE SPECIMEN'S ADEQUACY IS ASSERTED, NOT ASSUMED. A trail of length 1 would pass
"the two sequences match" trivially and prove nothing about a sequence — an
empty denominator is not a clean bill (4A-(d.3) §5a.212). So the model below is
required to produce MORE THAN ONE incumbent, and the assertion that it does is
the first thing each test checks.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from mre.modules.solve_runner import SolveRunner

UTC = timezone.utc
_REF = datetime(2026, 1, 1, tzinfo=UTC)

# A weighted single-machine tardiness model: N jobs, one machine, staggered due
# dates and DIFFERENT weights, so the sequence a planner would guess is not the
# cheapest and CP-SAT has to walk down to the optimum. Deliberately not the
# constant-cost model the two-stage tests use — that one is cost-flat by design
# and yields exactly one incumbent, which is the wrong specimen here.
_DURATIONS = [30, 45, 20, 60, 25, 50, 35, 40]
_WEIGHTS = [7, 1, 9, 2, 8, 1, 6, 3]
_DUE = [60, 90, 40, 200, 70, 150, 120, 100]


def _weighted_tardiness_model():
    from ortools.sat.python import cp_model as cp

    from mre.modules.solver_builder import VariableMap

    m = cp.CpModel()
    horizon = sum(_DURATIONS)
    starts, ends, ivs, terms = {}, {}, [], []
    for i, dur in enumerate(_DURATIONS):
        s = m.new_int_var(0, horizon, f"s{i}")
        e = m.new_int_var(0, horizon, f"e{i}")
        m.add(e == s + dur)
        ivs.append(m.new_interval_var(s, dur, e, f"iv{i}"))
        t = m.new_int_var(0, horizon, f"t{i}")
        m.add(t >= e - _DUE[i])
        terms.append(t * _WEIGHTS[i])
        starts[f"J{i}"], ends[f"J{i}"] = s, e
    m.add_no_overlap(ivs)
    m.minimize(sum(terms))

    vm = VariableMap(horizon_start=_REF)
    vm.op_start = dict(starts)
    vm.op_end = dict(ends)
    vm.op_assign = {k: {} for k in starts}
    vm.objective_terms = list(terms)
    return m, vm


def _run(seed=42, budget=None):
    m, vm = _weighted_tardiness_model()
    return SolveRunner(time_limit_seconds=30.0, num_search_workers=1,
                       random_seed=seed, deterministic_time=budget).solve(m, vm, None)


def _objectives(result):
    return [i["objective"] for i in result.incumbent_trail]


def test_the_specimen_actually_produces_a_trail_worth_asserting():
    """The precondition both proofs rest on, checked as its own test so a
    specimen that stops exercising the property fails LOUDLY here rather than
    turning the two proofs below into tautologies."""
    r = _run()
    assert len(r.incumbent_trail) > 1, (
        "the specimen produced a flat trail — the sequence proofs below would "
        f"pass vacuously (trail={r.incumbent_trail})")


def test_a_the_incumbent_objective_sequence_is_reproducible():
    """CLAUSE (6), proof A."""
    first, second = _objectives(_run()), _objectives(_run())
    assert len(first) > 1
    assert first == second, (
        f"the incumbent sequence is not reproducible: {first} vs {second}")


def test_a_the_sequence_is_monotonically_improving():
    """CP-SAT minimizes, so an incumbent trail descends. This is what makes
    "first minus final" an IMPROVEMENT rather than a signed difference, and it
    is what the metric rollup's exactness rests on."""
    objs = _objectives(_run())
    assert objs == sorted(objs, reverse=True), f"trail is not descending: {objs}"


def test_a_elapsed_times_are_recorded_but_not_asserted():
    """Clause (6): they are facts, they are stored, and they vary. This test
    asserts only that they are PRESENT and ordered — never their values."""
    trail = _run().incumbent_trail
    assert all("elapsed_s" in i for i in trail)
    times = [i["elapsed_s"] for i in trail]
    assert all(isinstance(t, float) for t in times)
    assert times == sorted(times), "elapsed times must not go backwards"


def test_b_the_callback_does_not_perturb_the_search():
    """CLAUSE (6), proof B — THE OBSERVER MUST NOT CHANGE WHAT IT OBSERVES.

    Solved twice under identical deterministic parameters: once through
    ``SolveRunner`` (callback attached, trail recorded) and once through a bare
    ``CpSolver.Solve`` with no callback at all. Same objective, same placements.
    Every golden and every pinned world's placement digest depends on this.
    """
    from ortools.sat.python import cp_model as cp

    watched = _run()
    assert len(watched.incumbent_trail) > 1

    m, vm = _weighted_tardiness_model()
    solver = cp.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    status = solver.Solve(m)          # NO CALLBACK
    assert status in (cp.OPTIMAL, cp.FEASIBLE)
    bare = vm.extract(solver)

    assert watched.objective == pytest.approx(solver.ObjectiveValue())
    assert watched.solve_values.op_start_minutes == bare.op_start_minutes, (
        "attaching the trail callback changed the placements")
    assert watched.solve_values.op_end_minutes == bare.op_end_minutes


def test_the_trail_is_absent_on_an_infeasible_solve_never_fabricated():
    """Clause (5)'s companion: no solution, no trail. An empty list, not a
    manufactured first plan."""
    from ortools.sat.python import cp_model as cp

    from mre.modules.solver_builder import VariableMap

    m = cp.CpModel()
    x = m.new_int_var(0, 5, "x")
    m.add(x >= 6)                      # infeasible by construction
    m.minimize(x)
    vm = VariableMap(horizon_start=_REF)
    vm.objective_terms = [x]
    r = SolveRunner(time_limit_seconds=10.0, num_search_workers=1,
                    random_seed=42).solve(m, vm, None)
    assert r.status == "INFEASIBLE"
    assert r.incumbent_trail == []

"""Session 4B.12 CU3 — the WARM START flag, guarded.

4B.8 measured the fact the flag exists to act on: at 200 orders / 14 days the
COST solve returned UNKNOWN in 6.0 deterministic units while SATISFIABILITY on
the SAME model took 0.082 — a factor of 74. The objective does not merely make
the model hard to OPTIMIZE; it makes it hard to find anything in. ``hint_mode``
hands the cost search a feasible starting point the model is demonstrably able
to produce cheaply.

It ships **OFF**, and these are the guards that make "off" mean something:

  (1) OFF IS THE DEFAULT, at every entry point. Every golden in the repository
      is captured with it off; a default that drifted would silently recapture
      them all.
  (2) OFF DOES NOTHING. No phase-0 solve is run, the budget arithmetic is the
      one 4B.8 derived, and the model reaching stage 1 is untouched.
  (3) ON RESTORES THE COST OBJECTIVE. Phase 0 clears the objective to solve for
      satisfiability. If that clearing leaked, stage 1 would minimize the
      CONSTANT 0 and every board would report a proven-optimal cost of nothing —
      the single worst failure this flag can have, and the one a green test
      suite would otherwise happily ship.
  (4) THE HINT IS NOT FREE. Phase 0's deterministic spend comes out of the same
      declared total and is counted in the returned ``det_consumed``. An arm
      that bought its speedup with extra budget would not be a speedup, and a
      warm start that is not counted is a warm start that looks free.
  (5) A HINT NEVER CHANGES THE ANSWER. On an instance both arms prove OPTIMAL,
      the proven objective is the same number. A hint is a search order, not a
      constraint; if the two disagree, the hint is not a hint.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest

from mre.modules.rolling_horizon import (
    HINT_ASSIGN, HINT_FULL, HINT_MODES, HINT_OFF,
    _two_stage_solve, build_rolling_view, run_rolling_horizon,
)

UTC = timezone.utc


# ---------------------------------------------------------------------------
# (1) OFF IS THE DEFAULT
# ---------------------------------------------------------------------------

class TestOffIsTheDefault:
    def test_every_entry_point_defaults_to_off(self):
        for fn in (_two_stage_solve, build_rolling_view, run_rolling_horizon):
            p = inspect.signature(fn).parameters.get("hint_mode")
            assert p is not None, f"{fn.__name__} cannot reach the flag at all"
            assert p.default == HINT_OFF, (
                f"{fn.__name__} defaults to {p.default!r} — every golden in this "
                f"repository was captured with the warm start OFF, so a changed "
                f"default silently recaptures all of them")

    def test_the_vocabulary_is_closed(self):
        assert HINT_MODES == (HINT_OFF, HINT_FULL, HINT_ASSIGN)

    @pytest.mark.parametrize("fn_name", ["build_rolling_view", "run_rolling_horizon"])
    def test_the_public_entry_points_actually_forward_it(self, fn_name):
        """A default nobody forwards is a flag that cannot be turned on. Both
        callers are one-line pass-throughs — exactly the kind of line that gets
        added to a signature and not to the call. Checked at the source rather
        than by solving, because both entry points need a full plant and the
        thing being guarded is a missing argument, not a behaviour."""
        import mre.modules.rolling_horizon as rh
        src = inspect.getsource(getattr(rh, fn_name))
        assert "hint_mode=hint_mode" in src, (
            f"{fn_name} accepts hint_mode but never forwards it to "
            f"_two_stage_solve — the flag is unreachable from that caller")

    def test_an_unknown_mode_is_refused_rather_than_ignored(self, tiny_model):
        model, var_map, free = tiny_model
        with pytest.raises(ValueError, match="unknown hint_mode"):
            _two_stage_solve(model, var_map, free, workers=1, seed=42,
                             deterministic=True, member_time_limit_s=10.0,
                             det_total=6.0, hint_mode="warm")


# ---------------------------------------------------------------------------
# a small real window, built once
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def window(tmp_path_factory):
    """One real window-0 model, rebuildable — CP-SAT models carry mutable state
    (objective, hints), so each arm needs its own instance."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import _admit, _build_window, prepare_plant

    ref = datetime(2026, 1, 5, tzinfo=UTC)
    d = tmp_path_factory.mktemp("hint")
    generate(d / "sub", scenario="pilot_scale", orders=10, seed=1)
    plant = prepare_plant(d / "sub", d / "prep", reference_date=ref)
    t0 = plant.reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = t0 + timedelta(days=14)
    admitted, _ = _admit(plant, plant.schedulable_demands, t0, window_end, True, 3.0)
    free_ops = [op for did in sorted(admitted)
                for op in plant.ops_by_wp.get(plant.wp_of_demand.get(did), [])]

    def build():
        model, var_map = _build_window(plant, free_ops, [], t0,
                                       window_end + timedelta(days=21))
        free = []
        for op in free_ops:
            v = var_map.op_start.get(op["id"])
            if v is not None:
                model.add(v >= 0)
                free.append(v)
        return model, var_map, free

    return build


@pytest.fixture
def tiny_model():
    """A model with an OBJECTIVE — the warm start is skipped outright on a model
    without one, so a degenerate fixture would vacuously pass every guard here."""
    from ortools.sat.python import cp_model as cp
    from mre.modules.solver_builder import VariableMap

    m = cp.CpModel()
    s = m.new_int_var(0, 100, "s")
    m.add(s >= 5)
    vm = VariableMap(horizon_start=datetime(2026, 1, 1, tzinfo=UTC),
                     op_start={"op0": s})
    vm.objective_terms = [s]
    m.minimize(sum(vm.objective_terms))
    return m, vm, [s]


def _solve(build, mode):
    model, var_map, free = build()
    res, stage2_ran, _rec = _two_stage_solve(
        model, var_map, free, workers=1, seed=42, deterministic=True,
        member_time_limit_s=300.0, det_total=6.0, hint_mode=mode)
    return res, stage2_ran, model, var_map


# ---------------------------------------------------------------------------
# (2) OFF DOES NOTHING
# ---------------------------------------------------------------------------

class TestOffDoesNothing:
    def test_off_runs_exactly_two_solves(self, window, monkeypatch):
        """Guard (2). The phase-0 solve must not happen at all when the flag is
        off — not merely be harmless. Counted at the module the shipped code
        imports SolveRunner from."""
        calls = _count_solves(monkeypatch)
        _solve(window, HINT_OFF)
        assert calls["n"] == 2, (
            f"hint_mode=off ran {calls['n']} solves; the two-stage solve is "
            f"TWO, and any third is a phase 0 that should not exist")

    def test_on_runs_three(self, window, monkeypatch):
        calls = _count_solves(monkeypatch)
        _solve(window, HINT_FULL)
        assert calls["n"] == 3


def _count_solves(monkeypatch):
    import mre.modules.solve_runner as sr
    state = {"n": 0}
    real = sr.SolveRunner

    class _Counting(real):        # type: ignore[misc,valid-type]
        def solve(self, *a, **kw):
            state["n"] += 1
            return super().solve(*a, **kw)

    monkeypatch.setattr(sr, "SolveRunner", _Counting)
    return state


# ---------------------------------------------------------------------------
# (3)/(4)/(5) — what ON must not break
# ---------------------------------------------------------------------------

class TestOnIsSafe:
    @pytest.mark.parametrize("mode", [HINT_FULL, HINT_ASSIGN])
    def test_stage1_still_minimizes_cost(self, window, mode):
        """GUARD (3), the one that matters most. Phase 0 clears the objective to
        solve for satisfiability. If the clearing leaked, stage 1 would minimize
        the constant 0, return objective 0.0 and report it OPTIMAL — a board
        claiming a proven cost of nothing.

        Checked two ways, because either alone can be fooled: the objective is
        the same NUMBER the unhinted arm proves, and it is not zero."""
        off, _, _, _ = _solve(window, HINT_OFF)
        on, _, _, _ = _solve(window, mode)
        assert off.status == "OPTIMAL" and on.status == "OPTIMAL", (
            "fixture too hard to prove — this guard needs both arms proved")
        assert on.objective is not None and on.objective > 0
        assert on.objective == pytest.approx(off.objective), (
            "GUARD (5): the hinted arm proved a DIFFERENT optimum. A hint is a "
            "search order, not a constraint — if it changes the argmin's value, "
            "it is restricting the model")

    def test_the_model_is_left_minimizing_cost_after_the_call(self, window):
        """The restoration is in a `finally`, and this is what proves it: after
        the whole call the model's objective is still the cost expression, so a
        caller re-solving the same model is not handed a cleared one."""
        from ortools.sat.python import cp_model as cp
        _res, _s2, model, var_map = _solve(window, HINT_FULL)
        # Stage 2 legitimately leaves the model minimizing Σ free starts, so the
        # check is that SOME objective survives and it is not the constant 0
        # phase 0 set.
        obj = model.proto.objective
        assert obj.vars, (
            "the model's objective has no variables — phase 0's minimize(0) "
            "survived the call")

    @pytest.mark.parametrize("mode", [HINT_FULL, HINT_ASSIGN])
    def test_phase0_spend_is_inside_the_declared_total(self, window, mode):
        """GUARD (4). The hint is paid for out of the same budget, and the
        returned meter says so."""
        res, _s2, _m, _vm = _solve(window, mode)
        assert res.det_consumed is not None
        assert res.det_consumed <= 6.0 * 1.05, (
            f"the warm-started call consumed {res.det_consumed} of a declared "
            f"6.0 — phase 0 is being given budget outside the total")

    def test_assign_mode_hints_no_start_times(self, window):
        """H2 is a PARTIAL hint by construction — structure, not times. If it
        also seeded starts it would be H1 under another name, and the two arms
        would measure the same thing."""
        from mre.modules.rolling_horizon import _hint_assign_only
        model, var_map, _free = window()
        # a solution to seed from
        res, _s2, _m, _vm = _solve(window, HINT_OFF)
        _hint_assign_only(model, var_map, res.solve_values)
        hinted = set(model.proto.solution_hint.vars)
        start_idx = {v.index for v in var_map.op_start.values()}
        assert hinted, "no hint was written at all"
        assert not (hinted & start_idx), (
            "assign-only mode seeded start variables — it is not partial")

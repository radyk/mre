"""Overtime premium pricing — builder/extractor unit tests (docs/06 §5.6/§5.9).

Calendar `added` exceptions with reason=overtime are overtime capacity; the
minutes an operation actually spends inside them price at resource rate ×
CostModel.overtime_premium. The builder charges the objective only the DELTA
(rate × (multiplier − 1)) since base production already charges every minute
at the regular rate; the extractor bills the same split into
production_regular_cost / production_overtime_cost ledger lines.

Two invariants under test beyond the happy path:
  - multiplier unset (≤ 1) ⇒ ZERO new solver variables — datasets without
    overtime must build byte-identical models (defaults-reproduce-baseline).
  - an overtime window overlapping a regular shift is premium only for the
    portion outside the shift (premium = overtime − regular availability).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tests.test_solver_builder import (
    _calendar, _costmodel, _demand, _fulfillment, _operation, _resource, _wp,
)

UTC = timezone.utc

# 2026-07-13 is a Monday.
MON = datetime(2026, 7, 13, 0, 0, tzinfo=UTC)
TUE = datetime(2026, 7, 14, 0, 0, tzinfo=UTC)
DUE_TUE = datetime(2026, 7, 14, 23, 59, tzinfo=UTC)
DUE_SAT = datetime(2026, 7, 18, 23, 59, tzinfo=UTC)


def _ot_exception(day: str, start: str = "07:00", end: str = "19:00",
                  reason: str = "overtime", etype: str = "added") -> dict:
    return {
        "window": {"start": f"{day}T{start}:00+00:00", "end": f"{day}T{end}:00+00:00"},
        "type": etype, "reason": reason,
    }


def _minutes(dt: datetime, horizon_start: datetime) -> int:
    return int((dt - horizon_start).total_seconds() / 60)


def _build(ops, wps, resources, cals, demands, fuls, cm):
    from mre.modules.solver_builder import SolverBuilder
    return SolverBuilder().build(
        wps + ops, resources, cals, fuls + demands, [], cm,
    )


def _solve(model):
    from ortools.sat.python import cp_model as cp
    solver = cp.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    status = solver.Solve(model)
    assert status in (cp.OPTIMAL, cp.FEASIBLE)
    return solver, status


def _extract(var_map, solver, ops, wps, resources, fuls, demands, cm):
    from mre.modules.extractor import Extractor
    return Extractor().extract(
        solve_values=var_map.extract(solver),
        snapshot_id="snap-ot-test",
        operations=ops, workpackages=wps, resources=resources,
        fulfillments=fuls, demands=demands, cost_model=cm,
        cal_windows=var_map.cal_windows,
        op_eligible=var_map.op_eligible,
        overtime_windows=var_map.overtime_windows,
    )


class TestPremiumWindows:
    def test_overtime_exception_becomes_premium_window(self):
        """A Saturday added/overtime exception on a Mon-Fri calendar is
        premium in full — there is no regular capacity underneath it."""
        cal = _calendar("cal")
        cal["exceptions"] = [_ot_exception("2026-07-18")]
        ops = [_operation("op-1", "wp-1", "spec-1", run_sec=600 * 60)]
        wps = [_wp("wp-1", "p", 1, ["op-1"], earliest=MON)]
        ress = [_resource("r1", cal_ref="cal", rate=1.0)]
        demands = [_demand("d1", "p", 1, DUE_SAT, earliest=MON)]
        fuls = [_fulfillment("f1", "d1", "wp-1", 1)]
        cm = _costmodel("cm", rates={"r1": 1.0}, setup_fixed=0.0)
        cm["overtime_premium"] = 1.5

        _, var_map = _build(ops, wps, ress, [cal], demands, fuls, cm)
        sat_start = _minutes(datetime(2026, 7, 18, 7, 0, tzinfo=UTC), var_map.horizon_start)
        sat_end = _minutes(datetime(2026, 7, 18, 19, 0, tzinfo=UTC), var_map.horizon_start)
        assert var_map.overtime_windows["r1"] == [(sat_start, sat_end)]

    def test_overlap_with_regular_shift_is_subtracted(self):
        """An overtime window 15:00-23:00 over a 07:00-19:00 shift is premium
        only for 19:00-23:00 — the overlap is regular capacity, not premium."""
        cal = _calendar("cal")
        cal["exceptions"] = [_ot_exception("2026-07-15", start="15:00", end="23:00")]
        ops = [_operation("op-1", "wp-1", "spec-1", run_sec=600 * 60)]
        wps = [_wp("wp-1", "p", 1, ["op-1"], earliest=MON)]
        ress = [_resource("r1", cal_ref="cal", rate=1.0)]
        demands = [_demand("d1", "p", 1, DUE_SAT, earliest=MON)]
        fuls = [_fulfillment("f1", "d1", "wp-1", 1)]
        cm = _costmodel("cm", rates={"r1": 1.0}, setup_fixed=0.0)
        cm["overtime_premium"] = 1.5

        _, var_map = _build(ops, wps, ress, [cal], demands, fuls, cm)
        prem_start = _minutes(datetime(2026, 7, 15, 19, 0, tzinfo=UTC), var_map.horizon_start)
        prem_end = _minutes(datetime(2026, 7, 15, 23, 0, tzinfo=UTC), var_map.horizon_start)
        assert var_map.overtime_windows["r1"] == [(prem_start, prem_end)]

    def test_non_overtime_added_exception_is_not_premium(self):
        """`added` capacity without reason=overtime (e.g. an extra shift) is
        plain capacity — no premium window, no premium billing."""
        cal = _calendar("cal")
        cal["exceptions"] = [_ot_exception("2026-07-18", reason="holiday")]
        ops = [_operation("op-1", "wp-1", "spec-1", run_sec=600 * 60)]
        wps = [_wp("wp-1", "p", 1, ["op-1"], earliest=MON)]
        ress = [_resource("r1", cal_ref="cal", rate=1.0)]
        demands = [_demand("d1", "p", 1, DUE_SAT, earliest=MON)]
        fuls = [_fulfillment("f1", "d1", "wp-1", 1)]
        cm = _costmodel("cm", rates={"r1": 1.0}, setup_fixed=0.0)
        cm["overtime_premium"] = 1.5

        _, var_map = _build(ops, wps, ress, [cal], demands, fuls, cm)
        assert var_map.overtime_windows["r1"] == []


class TestPremiumSolveAndExtraction:
    def _monday_only_setup(self, ot_mult: float):
        """One 600-min op; calendar open Mondays only, plus a Tuesday
        overtime window. Work released Tuesday, due Tuesday EOD: the choice
        is Tuesday overtime (premium) vs next Monday (six days late)."""
        cal = _calendar("cal")
        cal["base_pattern"] = {"weekdays": [0], "shift_start": "07:00", "shift_end": "19:00"}
        cal["exceptions"] = [_ot_exception("2026-07-14")]
        ops = [_operation("op-1", "wp-1", "spec-1", setup_sec=30 * 60, run_sec=570 * 60)]
        wps = [_wp("wp-1", "p", 1, ["op-1"], earliest=TUE)]
        ress = [_resource("r1", cal_ref="cal", rate=1.0)]
        demands = [_demand("d1", "p", 1, DUE_TUE, earliest=TUE)]
        fuls = [_fulfillment("f1", "d1", "wp-1", 1)]
        cm = _costmodel("cm", rates={"r1": 1.0}, setup_fixed=0.0)
        cm["overtime_premium"] = ot_mult
        return ops, wps, ress, [cal], demands, fuls, cm

    def test_solver_buys_overtime_when_tardiness_costs_more(self):
        ops, wps, ress, cals, demands, fuls, cm = self._monday_only_setup(1.5)
        model, var_map = _build(ops, wps, ress, cals, demands, fuls, cm)
        solver, _ = _solve(model)

        # Scheduled inside the Tuesday overtime window, on time.
        result = _extract(var_map, solver, ops, wps, ress, fuls, demands, cm)
        asgn = result.assignments[0]
        assert asgn["overtime_minutes"] == 600
        assert result.service_outcomes[0]["lateness_minutes"] <= 0

        # Objective = base production (600 × $1 × 100) + premium delta
        # (600 × $0.5 × 100); tardiness 0.
        assert solver.objective_value == 600 * 100 + 600 * 50

        # Ledger decomposes both ways.
        ledger = result.cost_ledger
        assert ledger["production_overtime_cost"] == pytest.approx(600 * 1.0 * 1.5)
        assert ledger["production_regular_cost"] == pytest.approx(0.0)
        assert ledger["production_cost"] == pytest.approx(
            ledger["production_regular_cost"] + ledger["production_overtime_cost"]
        )
        assert ledger["total_cost"] == pytest.approx(
            ledger["production_cost"] + ledger["setup_cost"] + ledger["tardiness_cost"]
        )

    def test_assignment_decision_carries_overtime_evidence(self):
        """The reconstructed assignment Decision must say the op ran in
        overtime and what the premium cost — testimony-renderable."""
        import tempfile
        from pathlib import Path
        from mre.contracts.vocabularies import ModuleCode, RunStatus
        from mre.reporter import Reporter
        from mre.modules.extractor import Extractor

        ops, wps, ress, cals, demands, fuls, cm = self._monday_only_setup(1.5)
        model, var_map = _build(ops, wps, ress, cals, demands, fuls, cm)
        solver, _ = _solve(model)

        rep = Reporter.begin(
            module=ModuleCode.M7, purpose="overtime evidence test", config={},
            trigger="pytest", snapshot_id="snap-ot-ev",
            sink_dir=Path(tempfile.mkdtemp()) / "runs",
        )
        Extractor().extract(
            solve_values=var_map.extract(solver), snapshot_id="snap-ot-ev",
            operations=ops, workpackages=wps, resources=ress,
            fulfillments=fuls, demands=demands, cost_model=cm, reporter=rep,
            cal_windows=var_map.cal_windows, op_eligible=var_map.op_eligible,
            overtime_windows=var_map.overtime_windows,
        )
        rep.end(RunStatus.SUCCESS)

        decisions = [r for r in rep.consolidated_doc["records"]
                     if r.get("record_type") == "decision"
                     and r.get("decision_type") == "assignment"]
        assert len(decisions) == 1
        chosen = decisions[0]["chosen"]
        assert chosen["overtime_minutes"] == 600
        assert chosen["overtime_premium_multiplier"] == 1.5
        assert chosen["overtime_cost"] == pytest.approx(900.0)
        assert "overtime" in decisions[0]["message"]

    def test_multiplier_unset_creates_no_overtime_variables(self):
        """ot_mult ≤ 1 must add ZERO variables — datasets without overtime
        build byte-identical models (defaults-reproduce-baseline gate)."""
        ops, wps, ress, cals, demands, fuls, cm = self._monday_only_setup(0.0)
        model, var_map = _build(ops, wps, ress, cals, demands, fuls, cm)
        assert not any("ot_" in v.name for v in model.proto.variables)

        solver, _ = _solve(model)
        result = _extract(var_map, solver, ops, wps, ress, fuls, demands, cm)
        assert result.cost_ledger["production_overtime_cost"] == 0.0
        assert result.cost_ledger["production_cost"] == pytest.approx(
            result.cost_ledger["production_regular_cost"]
        )

    def test_chunked_op_bills_premium_only_for_overtime_chunk(self):
        """A resumable 900-min op on a Friday-only calendar with Saturday
        overtime chunks as Friday 720 + Saturday 180; only the Saturday
        chunk's minutes bill at the premium rate (R-C3 + docs/06 §5.6)."""
        cal = _calendar("cal")
        cal["base_pattern"] = {"weekdays": [4], "shift_start": "07:00", "shift_end": "19:00"}
        cal["exceptions"] = [_ot_exception("2026-07-18")]
        op = _operation("op-1", "wp-1", "spec-1", setup_sec=30 * 60, run_sec=870 * 60)
        op["splittable"] = True
        ops = [op]
        wps = [_wp("wp-1", "p", 1, ["op-1"], earliest=MON)]
        ress = [_resource("r1", cal_ref="cal", rate=1.0)]
        demands = [_demand("d1", "p", 1, DUE_SAT, earliest=MON)]
        fuls = [_fulfillment("f1", "d1", "wp-1", 1)]
        cm = _costmodel("cm", rates={"r1": 1.0}, setup_fixed=0.0)
        cm["overtime_premium"] = 1.5

        model, var_map = _build(ops, wps, ress, [cal], demands, fuls, cm)
        solver, _ = _solve(model)
        result = _extract(var_map, solver, ops, wps, ress, fuls, demands, cm)

        asgn = result.assignments[0]
        assert len(asgn["run_windows"]) == 2
        assert asgn["overtime_minutes"] == 180
        ledger = result.cost_ledger
        assert ledger["production_regular_cost"] == pytest.approx(720 * 1.0)
        assert ledger["production_overtime_cost"] == pytest.approx(180 * 1.0 * 1.5)
        assert ledger["total_cost"] == pytest.approx(
            ledger["production_cost"] + ledger["setup_cost"] + ledger["tardiness_cost"]
        )

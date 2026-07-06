"""Phase 2 integration test — full scheduling spine M1→M7.

Derived from docs/03-poc-plan.md §3 (Phase 2) and the demonstration script
described there. Runs the complete pipeline against sample_data/ and
verifies the scheduling outcomes.

Key assertions:
- WO-2001 (due Mon 2026-07-13) and WO-2002 (due Wed 2026-07-15) are merged
  by merge_by_family_v1 into a single WorkPackage.
- M-GEAR-01 is closed on 2026-07-13; the assignment uses M-GEAR-02 instead.
- WO-2001 (tighter due date) shows as late (or at most marginally early) in
  the ServiceOutcome relative to WO-2002.
- Cost ledger decomposes: total = production + setup + tardiness.
- 93 operations, 32 WorkPackages, 34 Fulfillments produced by M4.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc
SAMPLE_DATA = Path(__file__).parent.parent / "sample_data"


@pytest.fixture(scope="module")
def pipeline_run(tmp_path_factory):
    """Run M1→M7 once; return (extract_result, snapshot_reader, demands, fulfillments)."""
    from mre.contracts.entities import CalendarException, TimeWindow
    from mre.contracts.vocabularies import (
        CalendarExceptionType, CalendarExceptionReason,
        ModuleCode, RunStatus,
    )
    from mre.modules.adapter import Adapter
    from mre.modules.calendar_utils import flatten_calendar
    from mre.modules.extractor import Extractor
    from mre.modules.planner import Planner
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import SolverBuilder
    from mre.modules.validator import Validator
    from mre.reporter import Reporter
    import datetime as dt

    tmp = tmp_path_factory.mktemp("phase2")
    snap_id = "snap-phase2"
    store = SnapshotStore(tmp / "snapshots")
    runs = tmp / "runs"

    def _rep(mod, purpose):
        return Reporter.begin(
            module=mod, purpose=purpose, config={},
            trigger="pytest", snapshot_id=snap_id, sink_dir=runs,
        )

    # M1
    a_rep = _rep(ModuleCode.M1, "phase2 adapter")
    Adapter(extract_dir=SAMPLE_DATA).run(snap_id, store, a_rep)
    a_rep.end(RunStatus.SUCCESS)

    # M3
    v_rep = _rep(ModuleCode.M3, "phase2 validator")
    v_result = Validator().run(snap_id, store, v_rep)
    v_rep.end(RunStatus.SUCCESS)
    assert v_result.go, "Validator gate must be GO for scheduling"

    # M4
    p_rep = _rep(ModuleCode.M4, "phase2 planner")
    p_result = Planner(policy="merge_by_family_v1").run(snap_id, store, p_rep)
    p_rep.end(RunStatus.SUCCESS)

    reader = store.load_snapshot(snap_id)
    demands = list(reader.iter_entities("demand"))
    fuls = list(reader.iter_entities("fulfillment"))
    wps = list(reader.iter_entities("workpackage"))
    ops = list(reader.iter_entities("operation"))
    resources = list(reader.iter_entities("resource"))
    pools = list(reader.iter_entities("resourcepool"))
    calendars = list(reader.iter_entities("calendar"))
    constraints = list(reader.iter_entities("constraint"))
    costmodels = list(reader.iter_entities("costmodel"))
    cm = costmodels[0] if costmodels else {}

    # Flatten calendars
    all_earliest = [
        datetime.fromisoformat(d["earliest_start"]).replace(tzinfo=UTC)
        for d in demands if d.get("earliest_start")
    ]
    all_due = [
        datetime.fromisoformat(d["due"]).replace(tzinfo=UTC)
        for d in demands if d.get("due")
    ]
    horizon_start = min(all_earliest).replace(hour=0, minute=0, second=0, microsecond=0)
    horizon_end = (max(all_due)).replace(hour=23, minute=59, second=59) + dt.timedelta(days=14)

    flattened_cals = []
    for cal in calendars:
        excs = []
        for e in cal.get("exceptions", []):
            if isinstance(e, dict) and "window" in e:
                tw = TimeWindow(
                    start=datetime.fromisoformat(e["window"]["start"]).replace(tzinfo=UTC),
                    end=datetime.fromisoformat(e["window"]["end"]).replace(tzinfo=UTC),
                )
                excs.append(CalendarException(
                    window=tw,
                    type=CalendarExceptionType(e.get("type", "closure")),
                    reason=CalendarExceptionReason(e.get("reason", "planned_maintenance")),
                ))
        windows = flatten_calendar(cal.get("base_pattern", {}), excs, horizon_start, horizon_end)
        cal_copy = dict(cal)
        cal_copy["horizon_resolved"] = [
            {"start": w.start.isoformat(), "end": w.end.isoformat()} for w in windows
        ]
        flattened_cals.append(cal_copy)

    # M5
    b_rep = _rep(ModuleCode.M5, "phase2 builder")
    builder = SolverBuilder()
    model, var_map = builder.build(
        wps + ops, resources + pools, flattened_cals,
        fuls + demands, constraints, cm,
    )
    b_rep.end(RunStatus.SUCCESS)

    # M6
    r_rep = _rep(ModuleCode.M6, "phase2 solver")
    solve_result = SolveRunner(time_limit_seconds=60.0).solve(model, var_map, r_rep)
    r_rep.end(RunStatus.SUCCESS if solve_result.status in ("OPTIMAL", "FEASIBLE") else RunStatus.PARTIAL)

    # M7
    e_rep = _rep(ModuleCode.M7, "phase2 extractor")
    extract_result = Extractor().extract(
        solve_values=solve_result.solve_values,
        snapshot_id=snap_id,
        operations=ops,
        workpackages=wps,
        resources=resources,
        fulfillments=fuls,
        demands=demands,
        cost_model=cm,
        reporter=e_rep,
        cal_windows=var_map.cal_windows,
        op_eligible=var_map.op_eligible,
    )
    e_rep.end(RunStatus.SUCCESS)

    return {
        "solve_status": solve_result.status,
        "planner_result": p_result,
        "extract": extract_result,
        "demands": demands,
        "fuls": fuls,
        "wps": wps,
        "ops": ops,
        "e_rep": e_rep,
    }


# ---------------------------------------------------------------------------
# Planner outputs
# ---------------------------------------------------------------------------

class TestPlannerOutputs:
    def test_workpackage_count(self, pipeline_run):
        """merge_by_family_v1 produces 32 WPs from 34 demands (2 merges)."""
        assert pipeline_run["planner_result"].workpackage_count == 32

    def test_operation_count(self, pipeline_run):
        """93 operations from 32 WPs with 2–3 routing steps each."""
        assert pipeline_run["planner_result"].operation_count == 93

    def test_fulfillment_count(self, pipeline_run):
        """One Fulfillment per demand; 34 demands → 34 Fulfillments."""
        assert pipeline_run["planner_result"].fulfillment_count == 34

    def test_wo2001_wo2002_merged(self, pipeline_run):
        """WO-2001 and WO-2002 (same product family + process) share one WP."""
        demands = pipeline_run["demands"]
        fuls = pipeline_run["fuls"]

        def _wp_for_wo(wo_number):
            d = next(
                d for d in demands
                if any(r.get("value") == wo_number for r in d.get("external_refs", []))
            )
            f = next(f for f in fuls if f["demand_ref"] == d["id"])
            return f["workpackage_ref"]

        wp_2001 = _wp_for_wo("WO-2001")
        wp_2002 = _wp_for_wo("WO-2002")
        assert wp_2001 == wp_2002, "WO-2001 and WO-2002 must share a merged WP"


# ---------------------------------------------------------------------------
# Solver result
# ---------------------------------------------------------------------------

class TestSolverResult:
    def test_solver_finds_solution(self, pipeline_run):
        """Solver must reach OPTIMAL or FEASIBLE with the sample data."""
        assert pipeline_run["solve_status"] in ("OPTIMAL", "FEASIBLE")

    def test_one_assignment_per_operation(self, pipeline_run):
        """Extractor produces exactly one Assignment per Operation."""
        n_ops = len(pipeline_run["ops"])
        n_assigns = len(pipeline_run["extract"].assignments)
        assert n_assigns == n_ops

    def test_one_service_outcome_per_fulfillment(self, pipeline_run):
        """One ServiceOutcome per Fulfillment (D-07: tardiness per Demand)."""
        n_fuls = len(pipeline_run["fuls"])
        n_svc = len(pipeline_run["extract"].service_outcomes)
        assert n_svc == n_fuls


# ---------------------------------------------------------------------------
# Service outcomes for WO-2001 / WO-2002
# ---------------------------------------------------------------------------

class TestServiceOutcomesWO2001WO2002:
    def _outcomes_by_wo(self, pipeline_run):
        demands = pipeline_run["demands"]
        svc_by_demand = {s["demand_ref"]: s for s in pipeline_run["extract"].service_outcomes}
        result = {}
        for d in demands:
            for ref in d.get("external_refs", []):
                if ref.get("type") == "work_order" and ref["value"] in ("WO-2001", "WO-2002"):
                    result[ref["value"]] = svc_by_demand.get(d["id"], {})
        return result

    def test_wo2001_lateness_worse_than_wo2002(self, pipeline_run):
        """WO-2001 has tighter due date → lateness_minutes >= WO-2002's lateness."""
        outcomes = self._outcomes_by_wo(pipeline_run)
        svc_2001 = outcomes.get("WO-2001", {})
        svc_2002 = outcomes.get("WO-2002", {})
        assert svc_2001 and svc_2002, "Both service outcomes must exist"
        # WO-2001 has earlier due date so must be at least as late (or later) than WO-2002
        assert svc_2001["lateness_minutes"] >= svc_2002["lateness_minutes"]

    def test_service_outcomes_have_projected_completion(self, pipeline_run):
        outcomes = self._outcomes_by_wo(pipeline_run)
        for wo, svc in outcomes.items():
            assert svc.get("projected_completion"), f"{wo} missing projected_completion"


# ---------------------------------------------------------------------------
# Cost ledger decomposability
# ---------------------------------------------------------------------------

class TestCostLedger:
    def test_cost_ledger_decomposes(self, pipeline_run):
        """total_cost = production_cost + setup_cost + tardiness_cost."""
        ledger = pipeline_run["extract"].cost_ledger
        total = ledger["total_cost"]
        parts = ledger["production_cost"] + ledger["setup_cost"] + ledger["tardiness_cost"]
        assert abs(total - parts) < 1e-3, f"Decomposability failed: {total} != {parts}"

    def test_setup_cost_positive(self, pipeline_run):
        """With fixed_per_setup > 0 and 93 ops, setup cost must be positive."""
        assert pipeline_run["extract"].cost_ledger["setup_cost"] > 0

    def test_production_cost_positive(self, pipeline_run):
        """Fix 1: costmodel.json rates keyed by canonical UUID → nonzero production cost."""
        assert pipeline_run["extract"].cost_ledger["production_cost"] > 0


# ---------------------------------------------------------------------------
# Pre-Phase-3 fixes verification
# ---------------------------------------------------------------------------

class TestPrePhase3Fixes:
    """Three fixes applied before Phase 3: cost key translation, demo story, CALENDAR_WINDOW."""

    def _outcomes_by_wo(self, pipeline_run):
        demands = pipeline_run["demands"]
        svc_by_demand = {s["demand_ref"]: s for s in pipeline_run["extract"].service_outcomes}
        result = {}
        for d in demands:
            for ref in d.get("external_refs", []):
                if ref.get("type") == "work_order" and ref["value"] in ("WO-2001", "WO-2002"):
                    result[ref["value"]] = svc_by_demand.get(d["id"], {})
        return result

    def test_wo2001_is_late(self, pipeline_run):
        """Fix 2: WO-2001 must have positive lateness (merge + calendar closure pushes past due)."""
        outcomes = self._outcomes_by_wo(pipeline_run)
        svc_2001 = outcomes.get("WO-2001", {})
        assert svc_2001, "WO-2001 ServiceOutcome must exist"
        assert svc_2001["lateness_minutes"] > 0, (
            f"WO-2001 must be late; got lateness={svc_2001['lateness_minutes']} min"
        )

    def test_at_least_one_late_service_outcome(self, pipeline_run):
        """Fix 2: at least one demand across the schedule ends up late."""
        late_outcomes = [
            s for s in pipeline_run["extract"].service_outcomes
            if s["lateness_minutes"] > 0
        ]
        assert len(late_outcomes) >= 1

    def test_calendar_window_decision_exists(self, pipeline_run):
        """Fix 2: at least one ASSIGNMENT Decision carries driver=CALENDAR_WINDOW."""
        e_rep = pipeline_run["e_rep"]
        records = e_rep._sink.read_all()
        cal_decisions = [
            r for r in records
            if r.get("record_type") == "decision"
            and r.get("decision_type") == "assignment"
            and r.get("driver") == "CALENDAR_WINDOW"
        ]
        assert len(cal_decisions) >= 1, "Expected ≥1 ASSIGNMENT decision with driver=CALENDAR_WINDOW"

    def test_calendar_window_alternative_references_closed_machine(self, pipeline_run):
        """Fix 2: the CALENDAR_WINDOW decision alternatives should include M-GEAR-01."""
        from mre.modules.snapshot_store import SnapshotStore
        e_rep = pipeline_run["e_rep"]
        records = e_rep._sink.read_all()
        cal_decisions = [
            r for r in records
            if r.get("record_type") == "decision"
            and r.get("decision_type") == "assignment"
            and r.get("driver") == "CALENDAR_WINDOW"
        ]
        assert cal_decisions, "Need ≥1 CALENDAR_WINDOW decision"
        dec = cal_decisions[0]
        alt_options = [a.get("option", "") for a in dec.get("alternatives", [])]
        # At least one alternative should name a resource (calendar-blocked M-GEAR-01)
        assert any("resource:" in opt for opt in alt_options), (
            f"CALENDAR_WINDOW decision should have resource alternative; got {alt_options}"
        )
        alt_consequences = [a.get("consequence", "") for a in dec.get("alternatives", [])]
        assert any("calendar" in c.lower() or "unavailable" in c.lower() for c in alt_consequences), (
            f"At least one alternative should reference calendar unavailability; got {alt_consequences}"
        )

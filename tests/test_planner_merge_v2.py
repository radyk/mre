"""Tests for Rep 4 (docs/07 Phase 1): merge_by_family_v2's feasibility + risk
gates. Not the default policy (docs/04 2026-07-12 amendment) — opt in via
--policy merge_by_family_v2.

Acceptance criteria (docs/04 2026-07-12 amendment, item 3):
  (i)   The WO-2001/WO-2002 case from the $260 unbatch verdict (docs/04
        2026-07-06) — v2 must REJECT this merge on risk (the recorded
        counterexample becomes the regression test).
  (ii)  A scenario where merging is genuinely profitable (loose due dates,
        real setup saving) — v2 must ACCEPT and the realized schedule must
        show the saving.
  (iii) The gauntlet with --policy merge_by_family_v2 solves FEASIBLE (no
        post-merge infeasibility) — slow, opt in with --runslow.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mre.contracts import (
    Demand, ProvenanceSidecar, SynthesizedProvenance, ProvenanceClass,
    CommitmentClass, DemandStatus, Quantity,
)
from mre.contracts.entities import (
    Calendar, Constraint, CostModel, OperationSpec, Process, Product,
    Resource, ResourceRequirement, ResourceRequirementMode, ResourceType,
    ProcessStatus, SetupCostBasis, TardinessWeights,
)
from mre.contracts.vocabularies import (
    ModuleCode, RunStatus, ConstraintType, ConstraintHardness, ConstraintProvenance,
)
from mre.modules.adapter import Adapter
from mre.modules.planner import Planner
from mre.modules.snapshot_store import SnapshotStore
from mre.modules.validator import Validator
from mre.reporter import Reporter

UTC = timezone.utc
SAMPLE_DATA = Path(__file__).parent.parent / "sample_data"

_UNIVERSAL = frozenset({"id", "snapshot_id", "external_refs"})


def _synth_prov(entity, snap_id: str) -> list:
    return [
        ProvenanceSidecar(
            entity_id=entity.id,
            attribute_name=attr,
            snapshot_id=snap_id,
            provenance_class=ProvenanceClass.SYNTHESIZED,
            payload=SynthesizedProvenance(generator_id="test"),
        )
        for attr in type(entity).model_fields
        if attr not in _UNIVERSAL
    ]


# ---------------------------------------------------------------------------
# (i) WO-2001/WO-2002 regression — v2 must REJECT on risk
# ---------------------------------------------------------------------------

class TestWO2001RejectedOnRisk:
    """The $260 unbatch verdict's counterexample (docs/04 2026-07-06):
    merge_by_family_v1 merges WO-2001 (due Mon 2026-07-13) with WO-2002 (due
    Wed 2026-07-15), then a planned_maintenance closure + the merged batch's
    combined duration pushes WO-2001 841 min late. v2's risk gate must catch
    this ahead of time and reject the merge."""

    @pytest.fixture(scope="class")
    def v2_run(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("merge_v2")
        store = SnapshotStore(tmp / "snapshots")
        snap_id = "snap-merge-v2"
        runs = tmp / "runs"

        def _rep(mod, purpose):
            return Reporter.begin(module=mod, purpose=purpose, config={},
                                   trigger="pytest", snapshot_id=snap_id, sink_dir=runs)

        a_rep = _rep(ModuleCode.M1, "merge v2 adapter")
        Adapter(extract_dir=SAMPLE_DATA).run(snap_id, store, a_rep)
        a_rep.end(RunStatus.SUCCESS)

        v_rep = _rep(ModuleCode.M3, "merge v2 validator")
        # Pin the reference_date to the sample_data scenario epoch (2026-07-09).
        # Unpinned, the validator defaults to datetime.now(), and once the wall
        # clock passes WO-2001's 2026-07-13 due date the demand is excluded as
        # past-due — the WO-2001/WO-2002 merge case this test exists to check
        # then silently evaporates. See docs/04 2026-07-15 (the time-bomb ruling).
        v_result = Validator().run(
            snap_id, store, v_rep, outlier_threshold_ratio=10.0,
            reference_date=datetime(2026, 7, 9, tzinfo=UTC),
        )
        v_rep.end(RunStatus.SUCCESS)

        p_rep = _rep(ModuleCode.M4, "merge v2 planner")
        p_result = Planner(policy="merge_by_family_v2").run(
            snap_id, store, p_rep, excluded_demand_ids=v_result.excluded_demand_ids,
        )
        p_rep.end(RunStatus.SUCCESS)

        reader = store.load_snapshot(snap_id)
        demands = {d["id"]: d for d in reader.iter_entities("demand")}
        fuls = list(reader.iter_entities("fulfillment"))

        def _wo(d):
            for r in d.get("external_refs", []):
                if r.get("type") == "work_order":
                    return r["value"]
            return None

        wo_to_wp = {}
        for f in fuls:
            d = demands.get(f["demand_ref"])
            if d is None:
                continue
            wo = _wo(d)
            if wo:
                wo_to_wp[wo] = f["workpackage_ref"]

        decisions = [r for r in p_rep.consolidated_doc["records"]
                     if r.get("record_type") == "decision"]
        return {
            "p_result": p_result, "wo_to_wp": wo_to_wp, "decisions": decisions,
            "demands": demands,
        }

    def test_wo2001_and_wo2002_not_merged(self, v2_run):
        wo_to_wp = v2_run["wo_to_wp"]
        assert "WO-2001" in wo_to_wp and "WO-2002" in wo_to_wp
        assert wo_to_wp["WO-2001"] != wo_to_wp["WO-2002"], (
            "v2's risk gate must reject WO-2001/WO-2002 merging into one WorkPackage"
        )

    def test_merge_rejected_decision_recorded(self, v2_run):
        rejections = [
            d for d in v2_run["decisions"]
            if d.get("chosen", {}).get("decision") == "merge_rejected"
        ]
        assert rejections, "expected at least one merge_rejected Decision"
        wo2001_id = next(
            did for did, d in v2_run["demands"].items()
            if any(r.get("value") == "WO-2001" for r in d.get("external_refs", []))
        )
        matching = [
            d for d in rejections
            if any(s["entity_id"] == wo2001_id for s in d["subjects"])
        ]
        assert matching, "WO-2001's rejected merge must be recorded"
        rec = matching[0]
        assert rec["driver"] == "COST_TRADEOFF"
        assert rec["chosen"]["gate"] == "risk"
        assert rec["chosen"]["policy"] == "merge_by_family_v2"
        assert "estimated_risk" in rec["chosen"]
        assert "estimated_benefit" in rec["chosen"]
        assert rec["chosen"]["estimated_risk"] > rec["chosen"]["estimated_benefit"]


# ---------------------------------------------------------------------------
# (ii) Profitable merge — v2 must ACCEPT and the schedule must realize it
# ---------------------------------------------------------------------------

def _build_profitable_snapshot(store: SnapshotStore, snap_id: str) -> None:
    """Two demands, same product/family, loose due dates (60/61 days out),
    small quantities, non-resumable single-op process. Feasibility is trivial
    (tiny duration vs. a full shift window) and tardiness exposure is zero
    (due dates far beyond even the merged duration) — merging is genuinely
    profitable: one setup avoided, no risk created."""
    writer = store.begin_snapshot(snap_id)
    now = datetime(2026, 7, 13, 0, 0, tzinfo=UTC)

    cal = Calendar(
        id="cal-001", snapshot_id=snap_id,
        base_pattern={"weekdays": [0, 1, 2, 3, 4, 5], "shift_start": "07:00", "shift_end": "19:00"},
    )
    res = Resource(
        id="res-001", snapshot_id=snap_id,
        resource_type=ResourceType.MACHINE, calendar_ref="cal-001",
    )
    spec = OperationSpec(
        id="spec-001", snapshot_id=snap_id,
        sequence=10, run_rate="PT10S", base_setup="PT30M", splittable=False,
        resource_requirements=[
            ResourceRequirement(mode=ResourceRequirementMode.EXPLICIT_SET,
                                resource_refs=["res-001"])
        ],
    )
    proc = Process(
        id="proc-001", snapshot_id=snap_id,
        product_ref="prod-001", operation_specs=["spec-001"],
        status=ProcessStatus.ACTIVE,
    )
    prod = Product(
        id="prod-001", snapshot_id=snap_id,
        name="Widget Profitable", unit_of_measure="EA", process_ref="proc-001",
        product_family="profitable",
    )
    dem_a = Demand(
        id="dem-A", snapshot_id=snap_id,
        product_ref="prod-001", quantity=Quantity(value=100.0, uom="EA"),
        earliest_start=now, due=now + timedelta(days=60),
        commitment_class=CommitmentClass.STANDARD, status=DemandStatus.OPEN,
    )
    dem_b = Demand(
        id="dem-B", snapshot_id=snap_id,
        product_ref="prod-001", quantity=Quantity(value=100.0, uom="EA"),
        earliest_start=now, due=now + timedelta(days=61),
        commitment_class=CommitmentClass.STANDARD, status=DemandStatus.OPEN,
    )
    cost_model = CostModel(
        id="cm-001", snapshot_id=snap_id, version=1,
        resource_rates={"res-001": 1.0},
        setup_cost_basis=SetupCostBasis(fixed_per_setup=50.0, scrap_cost_per_unit=0.0),
        tardiness_weights=TardinessWeights(base_weight=1.0, commitment_class_multipliers={"standard": 1.0}),
    )
    constraint = Constraint(
        id="con-001", snapshot_id=snap_id,
        constraint_type=ConstraintType.SETUP_TRANSITION,
        subjects=[], parameters={"transition_minutes": {}},
        provenance_class=ConstraintProvenance.POLICY, authority="test",
        hardness=ConstraintHardness.SOFT, penalty_weight=1.0,
    )

    for entity in [cal, res, spec, proc, prod, dem_a, dem_b, cost_model, constraint]:
        writer.write_entity(entity, _synth_prov(entity, snap_id))
    writer.finalize()


def _run_pipeline(tmp_path_factory, policy: str, label: str) -> dict:
    from mre.modules.calendar_utils import flatten_calendar
    from mre.modules.extractor import Extractor
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import SolverBuilder
    from mre.contracts.entities import CalendarException, TimeWindow
    from mre.contracts.vocabularies import CalendarExceptionType, CalendarExceptionReason

    tmp = tmp_path_factory.mktemp(f"profitable_{label}")
    snap_id = f"snap-profitable-{label}"
    store = SnapshotStore(tmp / "snapshots")
    runs = tmp / "runs"
    _build_profitable_snapshot(store, snap_id)

    def _rep(mod, purpose):
        return Reporter.begin(module=mod, purpose=purpose, config={},
                               trigger="pytest", snapshot_id=snap_id, sink_dir=runs)

    v_rep = _rep(ModuleCode.M3, "profitable validator")
    v_result = Validator().run(snap_id, store, v_rep)
    v_rep.end(RunStatus.SUCCESS)
    assert v_result.go

    p_rep = _rep(ModuleCode.M4, "profitable planner")
    p_result = Planner(policy=policy).run(
        snap_id, store, p_rep, excluded_demand_ids=v_result.excluded_demand_ids,
    )
    p_rep.end(RunStatus.SUCCESS)

    reader = store.load_snapshot(snap_id)
    demands = list(reader.iter_entities("demand"))
    fuls = list(reader.iter_entities("fulfillment"))
    wps = list(reader.iter_entities("workpackage"))
    ops = list(reader.iter_entities("operation"))
    edges = list(reader.iter_entities("precedenceedge"))
    resources = list(reader.iter_entities("resource"))
    pools = list(reader.iter_entities("resourcepool"))
    calendars = list(reader.iter_entities("calendar"))
    constraints = list(reader.iter_entities("constraint"))
    cm = list(reader.iter_entities("costmodel"))[0]

    all_earliest = [datetime.fromisoformat(d["earliest_start"]).replace(tzinfo=UTC) for d in demands]
    all_due = [datetime.fromisoformat(d["due"]).replace(tzinfo=UTC) for d in demands]
    horizon_start = min(all_earliest).replace(hour=0, minute=0, second=0, microsecond=0)
    horizon_end = (max(all_due)).replace(hour=23, minute=59, second=59) + timedelta(days=14)

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
                    window=tw, type=CalendarExceptionType(e.get("type", "closure")),
                    reason=CalendarExceptionReason(e.get("reason", "planned_maintenance")),
                ))
        windows = flatten_calendar(cal.get("base_pattern", {}), excs, horizon_start, horizon_end)
        cal_copy = dict(cal)
        cal_copy["horizon_resolved"] = [
            {"start": w.start.isoformat(), "end": w.end.isoformat()} for w in windows
        ]
        flattened_cals.append(cal_copy)

    b_rep = _rep(ModuleCode.M5, "profitable builder")
    model, var_map = SolverBuilder().build(
        wps + ops + edges, resources + pools, flattened_cals, fuls + demands, constraints, cm,
    )
    b_rep.end(RunStatus.SUCCESS)

    r_rep = _rep(ModuleCode.M6, "profitable solver")
    solve_result = SolveRunner(time_limit_seconds=30.0).solve(model, var_map, r_rep)
    r_rep.end(RunStatus.SUCCESS if solve_result.status in ("OPTIMAL", "FEASIBLE") else RunStatus.PARTIAL)

    e_rep = _rep(ModuleCode.M7, "profitable extractor")
    extract_result = Extractor().extract(
        solve_values=solve_result.solve_values, snapshot_id=snap_id,
        operations=ops, workpackages=wps, resources=resources,
        fulfillments=fuls, demands=demands, cost_model=cm, reporter=e_rep,
        cal_windows=var_map.cal_windows, op_eligible=var_map.op_eligible,
    )
    e_rep.end(RunStatus.SUCCESS)

    decisions = [r for r in p_rep.consolidated_doc["records"] if r.get("record_type") == "decision"]
    return {
        "p_result": p_result, "solve_status": solve_result.status,
        "extract_result": extract_result, "decisions": decisions,
    }


class TestProfitableMergeAccepted:
    @pytest.fixture(scope="class")
    def merged(self, tmp_path_factory):
        return _run_pipeline(tmp_path_factory, "merge_by_family_v2", "merged")

    @pytest.fixture(scope="class")
    def unmerged(self, tmp_path_factory):
        return _run_pipeline(tmp_path_factory, "identity_v1", "unmerged")

    def test_v2_accepts_the_merge(self, merged):
        assert merged["p_result"].merge_count == 1
        assert merged["p_result"].workpackage_count == 1

        merges = [d for d in merged["decisions"] if d["driver"] == "SETUP_AMORTIZATION"
                  and d.get("chosen", {}).get("decision") != "merge_rejected"]
        assert merges, "expected an accepted DEMAND_MERGE decision"
        assert merges[0]["chosen"]["policy"] == "merge_by_family_v2"

    def test_v2_no_rejections(self, merged):
        rejections = [d for d in merged["decisions"]
                      if d.get("chosen", {}).get("decision") == "merge_rejected"]
        assert not rejections, "a genuinely profitable merge must not be rejected"

    def test_solve_feasible_both(self, merged, unmerged):
        assert merged["solve_status"] in ("OPTIMAL", "FEASIBLE")
        assert unmerged["solve_status"] in ("OPTIMAL", "FEASIBLE")

    def test_realized_cost_lower_when_merged(self, merged, unmerged):
        """The schedule must realize the saving: one setup instead of two."""
        merged_cost = merged["extract_result"].cost_ledger["total_cost"]
        unmerged_cost = unmerged["extract_result"].cost_ledger["total_cost"]
        assert merged_cost < unmerged_cost, (
            f"merged total_cost={merged_cost} must be lower than "
            f"unmerged total_cost={unmerged_cost}"
        )


# ---------------------------------------------------------------------------
# (iii) Gauntlet solves FEASIBLE under merge_by_family_v2 (slow, --runslow)
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestGauntletFeasibleWithV2:
    def test_gauntlet_solves_feasible(self, tmp_path):
        from mre.__main__ import main

        raw_data = Path(__file__).parent.parent / "raw_data"
        plant_config = Path(__file__).parent.parent / "plant_config.json"
        out_dir = tmp_path / "gauntlet_v2"
        rc = main([
            "--raw-data", str(raw_data), "--plant-config", str(plant_config),
            "--out", str(out_dir), "--policy", "merge_by_family_v2",
            "--time-limit", "120",
        ])
        assert rc == 0

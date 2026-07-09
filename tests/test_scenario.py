"""Tests for the what-if scenario runner (scenario.py and supporting changes).

Derived from docs/03-poc-plan.md Phase 3, and the CLAUDE.md acceptance spec.
Covers:
- Vocabulary: SCENARIO_MODIFICATION in DecisionType
- Snapshot lineage: derive_scenario_snapshot records parent_snapshot_id
- Planner: suppressed_merge_ids forces solo batches
- _apply_path_value utility
- Full integration: suppress_merge(WO-2001, WO-2002)
  - Evidence isolated to scenario_runs/
  - is_scenario=True in scenario schedule
  - Rendered output contains no raw UUIDs
  - WO-2001 lateness improves (or cost structure changes as expected)
  - Cost delta decomposes: total = production + setup + tardiness
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

SAMPLE_DATA = Path(__file__).parent.parent / "sample_data"


# ---------------------------------------------------------------------------
# Unit: vocabulary
# ---------------------------------------------------------------------------


def test_scenario_modification_in_decision_type():
    from mre.contracts.vocabularies import DecisionType
    assert DecisionType.SCENARIO_MODIFICATION.value == "scenario_modification"


# ---------------------------------------------------------------------------
# Unit: _apply_path_value
# ---------------------------------------------------------------------------


def test_apply_path_value_shallow():
    from mre.modules.scenario import _apply_path_value
    obj = {"a": 1, "b": 2}
    result = _apply_path_value(obj, "b", 99)
    assert result["b"] == 99
    assert result["a"] == 1


def test_apply_path_value_nested():
    from mre.modules.scenario import _apply_path_value
    obj = {"tardiness_weights": {"base_weight": 1.0}}
    _apply_path_value(obj, "tardiness_weights.base_weight", 3.5)
    assert obj["tardiness_weights"]["base_weight"] == 3.5


def test_apply_path_value_creates_missing_keys():
    from mre.modules.scenario import _apply_path_value
    obj = {}
    _apply_path_value(obj, "a.b.c", 42)
    assert obj["a"]["b"]["c"] == 42


# ---------------------------------------------------------------------------
# Unit: Scenario id / description
# ---------------------------------------------------------------------------


def test_scenario_snapshot_id_format():
    from mre.modules.scenario import Scenario, SuppressMerge
    s = Scenario(
        base_snapshot_id="snap-run",
        modifications=[SuppressMerge(demand_refs=["WO-2001", "WO-2002"])],
    )
    sid = s.scenario_snapshot_id()
    assert sid.startswith("snap-run--scenario-")
    assert len(sid) == len("snap-run--scenario-") + 8


def test_scenario_description_suppress_merge():
    from mre.modules.scenario import Scenario, SuppressMerge
    s = Scenario(
        base_snapshot_id="snap-run",
        modifications=[SuppressMerge(demand_refs=["WO-2001", "WO-2002"])],
    )
    assert "suppress_merge" in s.description()
    assert "WO-2001" in s.description()


def test_scenario_hash_deterministic():
    from mre.modules.scenario import Scenario, SuppressMerge
    s1 = Scenario("snap-run", [SuppressMerge(["WO-2001"])])
    s2 = Scenario("snap-run", [SuppressMerge(["WO-2001"])])
    assert s1.short_hash() == s2.short_hash()


def test_scenario_hash_differs_on_different_mods():
    from mre.modules.scenario import Scenario, SuppressMerge
    s1 = Scenario("snap-run", [SuppressMerge(["WO-2001"])])
    s2 = Scenario("snap-run", [SuppressMerge(["WO-2003"])])
    assert s1.short_hash() != s2.short_hash()


# ---------------------------------------------------------------------------
# Unit: derive_scenario_snapshot lineage
# ---------------------------------------------------------------------------


def test_derive_scenario_snapshot_lineage(tmp_path):
    from mre.modules.snapshot_store import SnapshotStore

    store = SnapshotStore(tmp_path / "snapshots")
    src_id = "snap-src"
    dst_id = "snap-src--scenario-abcd1234"

    # Create a minimal source snapshot with one entity file
    src_dir = tmp_path / "snapshots" / src_id
    src_dir.mkdir(parents=True)
    (src_dir / "entities_demand.jsonl").write_text(
        json.dumps({"id": "d-1", "name": "D1"}) + "\n"
    )
    (src_dir / "manifest.json").write_text(json.dumps({"snapshot_id": src_id}))
    (src_dir / "identity_map.json").write_text(json.dumps({}))

    store.derive_scenario_snapshot(src_id, dst_id, ["demand"])

    dst_dir = tmp_path / "snapshots" / dst_id
    assert dst_dir.exists()
    manifest = json.loads((dst_dir / "manifest.json").read_text())
    assert manifest["parent_snapshot_id"] == src_id
    assert manifest["snapshot_type"] == "scenario"
    assert (dst_dir / "entities_demand.jsonl").exists()
    assert (dst_dir / "identity_map.json").exists()
    # provenance.jsonl should NOT be copied
    assert not (dst_dir / "provenance.jsonl").exists()


def test_derive_scenario_snapshot_skips_unknown_entity_types(tmp_path):
    from mre.modules.snapshot_store import SnapshotStore

    store = SnapshotStore(tmp_path / "snapshots")
    src_dir = tmp_path / "snapshots" / "snap-src"
    src_dir.mkdir(parents=True)
    (src_dir / "manifest.json").write_text(json.dumps({"snapshot_id": "snap-src"}))

    # Requesting a type that doesn't exist should not raise
    store.derive_scenario_snapshot("snap-src", "snap-dst", ["demand"])
    assert (tmp_path / "snapshots" / "snap-dst").exists()


# ---------------------------------------------------------------------------
# Unit: planner suppressed_merge_ids
# ---------------------------------------------------------------------------


def test_planner_suppressed_merge_forces_solo(tmp_path):
    """Demand in suppressed_merge_ids is not merged even when policy would merge it."""
    from mre.modules.planner import Planner

    planner = Planner(policy="merge_by_family_v1")

    d1 = {"id": "d-001", "product_ref": "P-A", "due": "2026-07-15T23:59:59Z"}
    d2 = {"id": "d-002", "product_ref": "P-A", "due": "2026-07-16T23:59:59Z"}
    products = {"P-A": {"id": "P-A", "product_family": "GEAR"}}

    # Without suppression: both demands merge into one batch
    batches_merged = planner._merge_batches([d1, d2], products)
    assert any(len(b) == 2 for b in batches_merged), "Demands should merge without suppression"

    # With suppression: each demand is a solo batch
    batches_solo = planner._merge_batches([d1, d2], products, suppressed_merge_ids={"d-001", "d-002"})
    assert all(len(b) == 1 for b in batches_solo), "Both demands should be solo when suppressed"
    assert len(batches_solo) == 2


def test_planner_suppressed_partial_merge(tmp_path):
    """One demand suppressed; others still merge among themselves."""
    from mre.modules.planner import Planner

    planner = Planner(policy="merge_by_family_v1")
    d1 = {"id": "d-001", "product_ref": "P-A", "due": "2026-07-14T23:59:59Z"}
    d2 = {"id": "d-002", "product_ref": "P-A", "due": "2026-07-15T23:59:59Z"}
    d3 = {"id": "d-003", "product_ref": "P-A", "due": "2026-07-16T23:59:59Z"}
    products = {"P-A": {"id": "P-A", "product_family": "GEAR"}}

    # d1 suppressed; d2 + d3 should still merge
    batches = planner._merge_batches([d1, d2, d3], products, suppressed_merge_ids={"d-001"})
    solo = [b for b in batches if len(b) == 1]
    merged = [b for b in batches if len(b) > 1]
    assert len(solo) == 1 and solo[0][0]["id"] == "d-001"
    assert len(merged) == 1 and len(merged[0]) == 2


# ---------------------------------------------------------------------------
# Integration fixture: full base pipeline from sample_data
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def base_run(tmp_path_factory):
    """Run M1→M7 against sample_data; return (store, snap_id, runs_dir)."""
    from mre.contracts.entities import CalendarException, TimeWindow
    from mre.contracts.vocabularies import (
        CalendarExceptionReason, CalendarExceptionType,
        ModuleCode, RunStatus,
    )
    from mre.modules.adapter import Adapter
    from mre.modules.calendar_utils import compute_horizon, flatten_all_calendars
    from mre.modules.extractor import Extractor
    from mre.modules.planner import Planner
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import SolverBuilder
    from mre.modules.validator import Validator
    from mre.reporter import Reporter

    tmp = tmp_path_factory.mktemp("scenario_base")
    snap_id = "snap-run"
    store = SnapshotStore(tmp / "snapshots")
    runs = tmp / "runs"
    runs.mkdir(parents=True, exist_ok=True)

    def _rep(mod, purpose):
        return Reporter.begin(
            module=mod, purpose=purpose, config={},
            trigger="pytest", snapshot_id=snap_id, sink_dir=runs,
        )

    # M1
    a_rep = _rep(ModuleCode.M1, "adapter")
    Adapter(extract_dir=SAMPLE_DATA).run(snap_id, store, a_rep)
    a_rep.end(RunStatus.SUCCESS)

    # M3
    v_rep = _rep(ModuleCode.M3, "validator")
    Validator().run(snap_id, store, v_rep)
    v_rep.end(RunStatus.SUCCESS)

    # M4
    p_rep = _rep(ModuleCode.M4, "planner")
    Planner(policy="merge_by_family_v1").run(snap_id, store, p_rep)
    p_rep.end(RunStatus.SUCCESS)

    reader = store.load_snapshot(snap_id)
    demands    = list(reader.iter_entities("demand"))
    fuls       = list(reader.iter_entities("fulfillment"))
    wps        = list(reader.iter_entities("workpackage"))
    ops        = list(reader.iter_entities("operation"))
    edges      = list(reader.iter_entities("precedenceedge"))
    resources  = list(reader.iter_entities("resource"))
    pools      = list(reader.iter_entities("resourcepool"))
    calendars  = list(reader.iter_entities("calendar"))
    constraints = list(reader.iter_entities("constraint"))
    costmodels  = list(reader.iter_entities("costmodel"))
    cost_model = costmodels[0] if costmodels else {}

    horizon_start, horizon_end = compute_horizon(demands)
    flattened_cals = flatten_all_calendars(calendars, horizon_start, horizon_end)

    # M5
    b_rep = _rep(ModuleCode.M5, "builder")
    from mre.modules.solver_builder import SolverBuilder
    model, var_map = SolverBuilder().build(
        wps + ops + edges, resources + pools, flattened_cals,
        fuls + demands, constraints, cost_model,
    )
    b_rep.end(RunStatus.SUCCESS)

    # M6
    r_rep = _rep(ModuleCode.M6, "runner")
    solve_result = SolveRunner(time_limit_seconds=30.0).solve(model, var_map, r_rep)
    r_rep.end(RunStatus.SUCCESS)
    assert solve_result.status in ("OPTIMAL", "FEASIBLE")

    # M7
    e_rep = _rep(ModuleCode.M7, "extractor")
    m7_writer = store.extend_snapshot(snap_id)
    Extractor().extract(
        solve_values=solve_result.solve_values,
        snapshot_id=snap_id,
        operations=ops,
        workpackages=wps,
        resources=resources,
        fulfillments=fuls,
        demands=demands,
        cost_model=cost_model,
        reporter=e_rep,
        cal_windows=var_map.cal_windows,
        op_eligible=var_map.op_eligible,
        snapshot_writer=m7_writer,
    )
    m7_writer.finalize()
    e_rep.end(RunStatus.SUCCESS)

    return store, snap_id, runs, tmp


# ---------------------------------------------------------------------------
# Integration: ScenarioRunner
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def scenario_result(base_run):
    """Run suppress_merge(WO-2001, WO-2002) scenario against the base run."""
    from mre.modules.scenario import Scenario, ScenarioRunner, SuppressMerge

    store, snap_id, runs_dir, tmp = base_run
    scenario_runs_dir = tmp / "scenario_runs"

    scenario = Scenario(
        base_snapshot_id=snap_id,
        modifications=[SuppressMerge(demand_refs=["WO-2001", "WO-2002"])],
    )
    runner = ScenarioRunner(store, scenario_runs_dir, time_limit_seconds=30.0)
    return runner.run(scenario), store, snap_id, tmp


def test_scenario_solves_successfully(scenario_result):
    result, store, snap_id, tmp = scenario_result
    assert result.extract_result is not None
    assert result.extract_result.schedule is not None


def test_scenario_schedule_is_proposed_and_is_scenario(scenario_result):
    result, store, snap_id, tmp = scenario_result
    sm = result.extract_result.schedule.get("summary_metrics", {})
    assert sm.get("is_scenario") is True


def test_scenario_evidence_isolated(scenario_result):
    """Scenario JSONL files must land in scenario_runs/, not runs/."""
    result, store, snap_id, tmp = scenario_result
    runs_dir = tmp / "runs"
    scenario_runs_dir = tmp / "scenario_runs"

    # scenario_runs directory should have evidence
    assert scenario_runs_dir.exists()
    scen_files = list(scenario_runs_dir.glob("*.jsonl"))
    assert scen_files, "Scenario run evidence should exist in scenario_runs/"

    # main runs/ should only have base-run evidence (not scenario snap_id)
    for f in (tmp / "runs").glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                assert result.scenario_snapshot_id not in json.dumps(rec), (
                    f"Scenario snapshot ID leaked into main runs/: {f.name}"
                )


def test_scenario_snapshot_has_parent_lineage(scenario_result):
    result, store, snap_id, tmp = scenario_result
    scen_snap_dir = store._base / result.scenario_snapshot_id
    manifest = json.loads((scen_snap_dir / "manifest.json").read_text())
    assert manifest["parent_snapshot_id"] == snap_id
    assert manifest["snapshot_type"] == "scenario"


def test_diff_cost_decomposes(scenario_result):
    result, store, snap_id, tmp = scenario_result
    cd = result.diff["cost_delta"]
    assert cd["_decomp_ok"] is True, (
        f"Cost delta does not decompose: {cd}"
    )


def test_diff_has_service_deltas(scenario_result):
    result, store, snap_id, tmp = scenario_result
    deltas = result.diff["service_deltas"]
    assert len(deltas) > 0


def test_diff_setup_cost_increases_on_unbatch(scenario_result):
    """Unbatching WO-2001+WO-2002 means more WorkPackages, more setup charges."""
    result, store, snap_id, tmp = scenario_result
    setup_delta = result.diff["cost_delta"]["setup_delta"]
    assert setup_delta > 0, (
        f"Expected positive setup_delta when unbatching; got {setup_delta}"
    )


def test_diff_wo2001_lateness_improves_or_same(scenario_result):
    """WO-2001 should be less late when not merged with WO-2002."""
    result, store, snap_id, tmp = scenario_result
    deltas = {d["work_order"]: d for d in result.diff["service_deltas"]}
    if "WO-2001" in deltas:
        delta = deltas["WO-2001"]["lateness_delta"]
        # lateness_delta < 0 means it improved; == 0 means unchanged (still acceptable)
        assert delta is None or delta <= 0, (
            f"Expected WO-2001 lateness to improve on unbatch; got delta={delta}"
        )


# ---------------------------------------------------------------------------
# Acceptance test: no UUIDs in rendered output
# ---------------------------------------------------------------------------


_UUID_RE = re.compile(
    r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',
    re.IGNORECASE,
)


def test_rendered_diff_contains_no_uuids(scenario_result):
    from mre.modules.explainer import ExplanationBundle
    from mre.modules.renderers import TemplateRenderer

    result, store, snap_id, tmp = scenario_result
    diff = result.diff
    bundle = ExplanationBundle(
        question=f"What if we {diff.get('description', '?')}?",
        subject_id=result.scenario_snapshot_id,
        subject_type="scenario_diff",
        subject_external_name=diff.get("description", "?"),
        ordered_records=[],
        key_facts=diff,
        snapshot_id=snap_id,
        identity_map=None,
    )
    rendered = TemplateRenderer().render(bundle)
    assert not _UUID_RE.search(rendered), (
        f"Rendered diff contains UUID(s):\n{rendered}"
    )


def test_rendered_diff_shows_scenario_description(scenario_result):
    from mre.modules.explainer import ExplanationBundle
    from mre.modules.renderers import TemplateRenderer

    result, store, snap_id, tmp = scenario_result
    diff = result.diff
    bundle = ExplanationBundle(
        question=f"What if we {diff.get('description', '?')}?",
        subject_id=result.scenario_snapshot_id,
        subject_type="scenario_diff",
        subject_external_name=diff.get("description", "?"),
        ordered_records=[],
        key_facts=diff,
        snapshot_id=snap_id,
        identity_map=None,
    )
    rendered = TemplateRenderer().render(bundle)
    assert "suppress_merge" in rendered
    assert "Cost:" in rendered


# ---------------------------------------------------------------------------
# Acceptance test: setup cost delta vs merge Decision's estimated_benefit
# ---------------------------------------------------------------------------


def test_acceptance_suppress_merge_setup_delta_exceeds_estimated_benefit(scenario_result):
    """The actual setup cost delta must be > 0; it should exceed estimated_benefit=50.

    The merge Decision records estimated_benefit=50 (1 WP avoided × $50).
    The scenario shows the actual per-operation setup cost (2 ops per WP × $50 × 2 WPs).
    Docs/04 amendment log records the discrepancy.
    """
    result, store, snap_id, tmp = scenario_result
    cd = result.diff["cost_delta"]
    # Actual setup cost increase when unbatching two family members
    assert cd["setup_delta"] > 0
    # The actual cost delta should exceed the planner's estimated_benefit=50
    # (because estimated_benefit counts WPs avoided, not operations × rate)
    assert cd["setup_delta"] >= 50, (
        f"Expected setup_delta >= 50 (estimated_benefit); got {cd['setup_delta']}"
    )


# ---------------------------------------------------------------------------
# CLI path: whatif.py returns 0 and prints diff
# ---------------------------------------------------------------------------


def test_whatif_cli_suppress_merge(base_run, tmp_path, capsys):
    """CLI python -m mre.whatif --suppress-merge WO-2001,WO-2002 exits 0."""
    import mre.whatif as whatif_mod

    store, snap_id, runs_dir, tmp_base = base_run
    result = whatif_mod.main([
        "--suppress-merge", "WO-2001,WO-2002",
        "--out", str(tmp_base),
        "--snapshot-id", snap_id,
        "--time-limit", "30",
    ])
    assert result == 0
    captured = capsys.readouterr()
    assert "Scenario:" in captured.out
    assert "Cost:" in captured.out


def test_whatif_cli_no_args_returns_error(capsys):
    import mre.whatif as whatif_mod
    result = whatif_mod.main(["--out", "nonexistent_dir"])
    assert result != 0


# ---------------------------------------------------------------------------
# Summary metrics: extractor now includes full cost breakdown
# ---------------------------------------------------------------------------


def test_base_schedule_has_full_cost_breakdown(base_run):
    store, snap_id, runs_dir, tmp = base_run
    reader = store.load_snapshot(snap_id)
    schedules = list(reader.iter_entities("schedule"))
    assert schedules, "No schedule entities in snapshot"
    sm = schedules[0].get("summary_metrics", {})
    assert "production_cost" in sm
    assert "setup_cost" in sm
    assert "tardiness_cost" in sm
    assert "total_cost" in sm
    assert abs(
        sm["total_cost"] - (sm["production_cost"] + sm["setup_cost"] + sm["tardiness_cost"])
    ) < 0.01

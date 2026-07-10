"""Solution-pool service tests (docs/07 Phase 2, session 2.2).

Written from the session acceptance spec:
- the pool populates within a bounded wall time;
- measured diversity is reported (mean Hamming from the incumbent and
  pairwise) and every produced member differs from the incumbent;
- every member's cost_summary decomposes (contract validation at parse);
- some operations have alternative positions across the pool — the Tier-1
  drag-ghost precondition;
- members stay within the objective tolerance;
- pool documents are marked (annotations.pool, contract 1.1);
- pools are invalidated when the base schedule is superseded;
- nothing is written into the base snapshot.

The messy-plant (200-order) acceptance run is slow-marked.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.contracts.schedule_document import ScheduleDocument
from mre.modules.solution_pool import warm_solution_pool
from tools.generate_erp_dataset import generate

SNAP_ID = "snap-run"


# ---------------------------------------------------------------------------
# Unit: the diversity cut and objective bound helpers
# ---------------------------------------------------------------------------

def test_start_diversity_cut_forces_a_move():
    """A model whose optimum equals the incumbent must, under the cut,
    move at least one sampled op's start."""
    from ortools.sat.python import cp_model as cp

    from mre.modules.solver_builder import VariableMap, add_start_diversity_cut
    from datetime import datetime, timezone

    m = cp.CpModel()
    vm = VariableMap(horizon_start=datetime(2026, 7, 1, tzinfo=timezone.utc))
    xs = {}
    for oid in ("op1", "op2", "op3"):
        xs[oid] = m.new_int_var(0, 100, f"s_{oid}")
        vm.op_start[oid] = xs[oid]
    m.minimize(sum(xs.values()))  # unconstrained optimum: all zero

    incumbent = {"op1": 0, "op2": 0, "op3": 0}
    n = add_start_diversity_cut(m, vm, incumbent, ["op1", "op2", "op3"])
    assert n == 3

    solver = cp.CpSolver()
    assert solver.Solve(m) == cp.OPTIMAL
    moved = [oid for oid, v in incumbent.items() if solver.Value(xs[oid]) != v]
    assert len(moved) >= 1


def test_objective_upper_bound_constrains_the_objective():
    from ortools.sat.python import cp_model as cp

    from mre.modules.solver_builder import VariableMap, add_objective_upper_bound
    from datetime import datetime, timezone

    m = cp.CpModel()
    vm = VariableMap(horizon_start=datetime(2026, 7, 1, tzinfo=timezone.utc))
    x = m.new_int_var(0, 100, "x")
    m.add(x >= 7)
    vm.objective_terms = [x]
    m.maximize(x)  # push against the bound
    add_objective_upper_bound(m, vm, 42)
    solver = cp.CpSolver()
    assert solver.Solve(m) == cp.OPTIMAL
    assert solver.Value(x) == 42


# ---------------------------------------------------------------------------
# Integration: clean_small, deterministic base
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def clean_small_pool(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("solution_pool")
    sub, out = tmp / "sub", tmp / "out"
    generate(sub, scenario="clean_small", seed=7)
    assert mre_main([
        "--submission", str(sub), "--out", str(out),
        "--time-limit", "30", "--solver-workers", "1", "--solver-seed", "0",
    ]) == 0
    snap_dir = out / "snapshots" / SNAP_ID
    before = {p.name: p.stat().st_size for p in snap_dir.iterdir()}
    result = warm_solution_pool(
        out_dir=out, snapshot_id=SNAP_ID,
        base_schedule_id="sched-base", run_id="run-base",
        k=5, tolerance_pct=10.0, member_time_limit_s=10.0, seed=99,
    )
    after = {p.name: p.stat().st_size for p in snap_dir.iterdir()}
    return result, out, before, after


class TestCleanSmallPool:
    def test_pool_ready_within_bounded_wall_time(self, clean_small_pool):
        result, _, _, _ = clean_small_pool
        assert result.status == "ready"
        produced = [m for m in result.members if m.document_path]
        assert produced, "no members produced"
        # bounded: k × member limit plus build overhead, generously
        assert result.wall_time_s < 5 * 10.0 + 30.0

    def test_every_member_differs_from_incumbent(self, clean_small_pool):
        result, _, _, _ = clean_small_pool
        for m in result.members:
            if m.document_path:
                assert m.hamming_from_incumbent >= 1

    def test_measured_diversity_reported(self, clean_small_pool):
        result, out, _, _ = clean_small_pool
        d = result.diversity
        assert d["mean_hamming_from_incumbent"] >= 1
        assert d["ops_with_alternative_positions"] >= 1
        produced = [m for m in result.members if m.document_path]
        if len(produced) >= 2:
            assert d["mean_pairwise_hamming"] is not None
        summary = json.loads((out / "pool" / "pool.json").read_text(encoding="utf-8"))
        assert summary["diversity"] == d
        assert "no-good cut" in summary["params"]["diversity_mechanism"]

    def test_members_within_tolerance_and_documents_valid(self, clean_small_pool):
        result, _, _, _ = clean_small_pool
        for m in result.members:
            if not m.document_path:
                continue
            if m.objective_delta_pct is not None:
                assert m.objective_delta_pct <= 10.0 + 1e-6
            # parsing validates the contract — cost decomposition dies at
            # construction if a member's ledger doesn't decompose
            doc = ScheduleDocument.model_validate_json(
                Path(m.document_path).read_text(encoding="utf-8"))
            assert doc.annotations.pool.pool_id == result.pool_id
            assert doc.annotations.pool.member_index == m.member_index
            assert doc.cost_summary.total == pytest.approx(
                doc.cost_summary.production_regular
                + doc.cost_summary.production_overtime
                + doc.cost_summary.setup + doc.cost_summary.tardiness,
                abs=0.02,
            )

    def test_base_snapshot_untouched(self, clean_small_pool):
        """Pool extraction must not extend the canonical snapshot."""
        _, _, before, after = clean_small_pool
        assert before == after


# ---------------------------------------------------------------------------
# Registry: pool indexing + invalidation on supersede
# ---------------------------------------------------------------------------

def test_pool_invalidated_when_schedule_superseded(tmp_path):
    from mre.api.registry import Registry

    reg = Registry(tmp_path)
    run = reg.create_run(kind="solve")
    reg.register_schedule(
        schedule_id="sched-1", run_id=run["id"], snapshot_id=run["snapshot_id"],
        status="proposed", contract_version="1.1", document_path="x.json",
    )
    reg.create_pool("pool-abc", "sched-1", params={"k": 5})
    reg.finish_pool("pool-abc", "ready", summary={"ok": True}, members=[
        {"member_index": 0, "objective": 100.0, "objective_delta_pct": 1.0,
         "hamming_from_incumbent": 3, "document_path": "m0.json"},
    ])

    pool = reg.get_pool_for_schedule("sched-1")
    assert pool["status"] == "ready"
    assert pool["members"][0]["member_index"] == 0

    reg.mark_schedule_superseded("sched-1")
    assert reg.get_schedule("sched-1")["status"] == "superseded"
    assert reg.get_pool_for_schedule("sched-1")["status"] == "invalidated"


# ---------------------------------------------------------------------------
# Acceptance at scale: the messy plant (slow)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_messy_plant_pool_acceptance(tmp_path):
    tmp = tmp_path
    sub, out = tmp / "sub", tmp / "out"
    generate(sub, scenario="messy_realistic", seed=23)
    assert mre_main([
        "--submission", str(sub), "--out", str(out),
        "--time-limit", "120", "--solver-workers", "1", "--solver-seed", "0",
    ]) == 0
    result = warm_solution_pool(
        out_dir=out, snapshot_id=SNAP_ID,
        base_schedule_id="sched-messy", run_id="run-messy",
        k=5, tolerance_pct=10.0, member_time_limit_s=30.0, seed=99,
    )
    assert result.status == "ready"
    produced = [m for m in result.members if m.document_path]
    assert produced
    assert result.wall_time_s < 5 * 30.0 + 120.0
    assert result.diversity["mean_hamming_from_incumbent"] >= 1
    assert result.diversity["ops_with_alternative_positions"] >= 1
    for m in produced:
        doc = ScheduleDocument.model_validate_json(
            Path(m.document_path).read_text(encoding="utf-8"))
        assert doc.annotations.pool.is_pool_member
        if m.objective_delta_pct is not None:
            assert m.objective_delta_pct <= 10.0 + 1e-6

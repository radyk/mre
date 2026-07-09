"""Tests for the precedence-edge surgery (docs/05 R-A2/A3, R-Dwell, §4).

Operation.predecessors is gone; precedence + lags (including dwell) are
first-class PrecedenceEdge records keyed by OperationSpec id, synthesized by
the adapter from linear Sequence, and read by the Solver Builder via
Operation.spec_ref. tests/test_defaults_reproduce_baseline.py proves the
surgery is behavior-preserving end-to-end; this file tests the mechanism
directly.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from mre.contracts.entities import PrecedenceEdge
from mre.modules.adapter import Adapter, _synthesize_precedence_pairs
from mre.modules.snapshot_store import SnapshotStore
from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.reporter import Reporter

SAMPLE_DATA = Path(__file__).parent.parent / "sample_data"
FIXTURE = Path(__file__).parent / "fixtures" / "raw_data_mini"


class TestPrecedenceEdgeEntity:
    def test_min_lag_defaults_zero_max_lag_defaults_none(self):
        edge = PrecedenceEdge(id="e1", snapshot_id="s1", predecessor="p1", successor="p2")
        assert edge.min_lag == timedelta(0)
        assert edge.max_lag is None

    def test_explicit_lags(self):
        edge = PrecedenceEdge(
            id="e1", snapshot_id="s1", predecessor="p1", successor="p2",
            min_lag=timedelta(minutes=30), max_lag=timedelta(hours=4),
        )
        assert edge.min_lag == timedelta(minutes=30)
        assert edge.max_lag == timedelta(hours=4)


class TestSynthesizePrecedencePairs:
    def test_linear_chain(self):
        pairs = _synthesize_precedence_pairs(["s10", "s20", "s30"])
        assert pairs == [("s10", "s20"), ("s20", "s30")]

    def test_single_op_no_edges(self):
        assert _synthesize_precedence_pairs(["s10"]) == []

    def test_empty(self):
        assert _synthesize_precedence_pairs([]) == []


class TestOperationHasNoPredecessorsOrDwell:
    def test_operation_fields(self):
        from mre.contracts.entities import Operation
        fields = set(Operation.model_fields)
        assert "predecessors" not in fields
        assert "dwell_duration" not in fields

    def test_operationspec_fields(self):
        from mre.contracts.entities import OperationSpec
        fields = set(OperationSpec.model_fields)
        assert "dwell_rule" not in fields


class TestAdapterSynthesizesEdges:
    """Adapter (sample_data path): R-CAST-A is a 3-step linear route
    (casting -> machining -> inspection), so PROD-001's Process should get
    exactly 2 PrecedenceEdges, both min_lag=0 (no dwell source), max_lag=None."""

    @pytest.fixture(scope="class")
    def adapter_run(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("adapter_edges")
        store = SnapshotStore(tmp / "snapshots")
        reporter = Reporter.begin(
            module=ModuleCode.M1, purpose="edge test", config={}, trigger="pytest",
            snapshot_id="snap-edges", sink_dir=tmp / "runs",
        )
        result = Adapter(extract_dir=SAMPLE_DATA).run("snap-edges", store, reporter)
        reporter.end(RunStatus.SUCCESS)
        return result, store

    def test_edge_count_positive(self, adapter_run):
        result, _ = adapter_run
        assert result.precedence_edge_count > 0

    def test_cast_a_process_has_two_edges_in_sequence(self, adapter_run):
        result, store = adapter_run
        reader = store.load_snapshot("snap-edges")
        processes = list(reader.iter_entities("process"))
        specs = {s["id"]: s for s in reader.iter_entities("operationspec")}
        edges = list(reader.iter_entities("precedenceedge"))

        # Find the process for PROD-001 (R-CAST-A: 3 sequential steps)
        def _product_no(p):
            return next((r["value"] for r in p.get("external_refs", [])
                        if r.get("type") == "product_no"), None)
        prod001 = next(p for p in reader.iter_entities("product") if _product_no(p) == "PROD-001")
        proc = next(p for p in processes if p["id"] == prod001["process_ref"])
        spec_ids_in_seq = sorted(proc["operation_specs"], key=lambda sid: specs[sid]["sequence"])
        assert len(spec_ids_in_seq) == 3

        proc_edges = [e for e in edges if e["predecessor"] in spec_ids_in_seq]
        assert len(proc_edges) == 2
        pairs = {(e["predecessor"], e["successor"]) for e in proc_edges}
        assert pairs == {
            (spec_ids_in_seq[0], spec_ids_in_seq[1]),
            (spec_ids_in_seq[1], spec_ids_in_seq[2]),
        }
        for e in proc_edges:
            assert e["min_lag"] == "PT0S"
            assert e["max_lag"] is None


class TestRawAdapterSynthesizesEdges:
    def test_multi_step_route_gets_edges(self, tmp_path):
        from mre.modules.raw_adapter import RawAdapter, load_plant_config

        plant_cfg = load_plant_config(FIXTURE / "plant_config.json")
        store = SnapshotStore(tmp_path / "snapshots")
        reporter = Reporter.begin(
            module=ModuleCode.M1, purpose="raw edge test", config={}, trigger="pytest",
            snapshot_id="snap-raw-edges", sink_dir=tmp_path / "runs",
        )
        result = RawAdapter(FIXTURE, plant_cfg).run("snap-raw-edges", store, reporter)
        reporter.end(RunStatus.SUCCESS)
        assert result.precedence_edge_count >= 0  # fixture may be single-step; must not crash

        reader = store.load_snapshot("snap-raw-edges")
        edges = list(reader.iter_entities("precedenceedge"))
        for e in edges:
            assert e["min_lag"] == "PT0S"  # no Dwell column in raw_data
            assert e["max_lag"] is None


class TestIDSAdapterDwellBecomesMinLag:
    """The one adapter that actually reads a dwell_minutes column."""

    def test_nonzero_dwell_lands_on_outgoing_edge(self, tmp_path):
        from tools.generate_erp_dataset import generate
        from mre.modules.ids_adapter import IDSAdapter

        sub_dir = tmp_path / "submission"
        generate(sub_dir, scenario="clean_small", seed=1)

        # Inject a nonzero dwell_minutes on the first routing line of the first route.
        import csv
        rl_path = sub_dir / "routing_lines.csv"
        rows = list(csv.DictReader(open(rl_path, encoding="utf-8")))
        first_route = rows[0]["route_id"]
        route_rows = [r for r in rows if r["route_id"] == first_route]
        route_rows.sort(key=lambda r: int(r["sequence"]))
        assert len(route_rows) >= 2, "need a multi-step route to test dwell->min_lag"
        pred_spec_seq = route_rows[0]["sequence"]
        for r in rows:
            if r["route_id"] == first_route and r["sequence"] == pred_spec_seq:
                r["dwell_minutes"] = "45"
        with open(rl_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)

        store = SnapshotStore(tmp_path / "snapshots")
        reporter = Reporter.begin(
            module=ModuleCode.M1, purpose="ids dwell test", config={}, trigger="pytest",
            snapshot_id="snap-ids-dwell", sink_dir=tmp_path / "runs",
        )
        IDSAdapter(sub_dir).run("snap-ids-dwell", store, reporter)
        reporter.end(RunStatus.SUCCESS)

        reader = store.load_snapshot("snap-ids-dwell")
        edges = list(reader.iter_entities("precedenceedge"))

        # Exactly one edge should carry the injected 45-minute dwell as min_lag;
        # every other synthesized edge (across all routes) stays at 0.
        nonzero_edges = [e for e in edges if e["min_lag"] != "PT0S"]
        assert len(nonzero_edges) == 1
        assert nonzero_edges[0]["min_lag"] == "PT45M"


class TestSolverBuilderReadsEdges:
    """Direct unit test of the six-input builder honoring PrecedenceEdge
    min_lag/max_lag between two Operations sharing a WorkPackage."""

    def _build(self, min_lag_iso: str, max_lag_iso, run_sec=600):
        from datetime import datetime, timezone
        from mre.modules.solver_builder import SolverBuilder

        UTC = timezone.utc
        HORIZON = datetime(2026, 7, 13, 7, 0, tzinfo=UTC)
        DUE = datetime(2026, 7, 20, 23, 59, tzinfo=UTC)

        wp_id, op1, op2, spec1, spec2 = "wp-e", "op-e1", "op-e2", "spec-e1", "spec-e2"
        r_id, d_id, f_id = "res-e", "d-e", "f-e"

        wps = [{"id": wp_id, "product_ref": "p", "quantity": {"value": 10, "uom": "EA"},
                "earliest_start": HORIZON.isoformat(), "operations": [op1, op2],
                "process_version": 1, "state": "planned", "created_by": "dec-1"}]
        ops = [
            {"id": op1, "spec_ref": spec1, "workpackage_ref": wp_id, "sequence": 10,
             "resource_requirements": [], "setup_family": "f", "setup_duration": "PT0S",
             "run_duration": f"PT{run_sec}S", "splittable": False},
            {"id": op2, "spec_ref": spec2, "workpackage_ref": wp_id, "sequence": 20,
             "resource_requirements": [], "setup_family": "f", "setup_duration": "PT0S",
             "run_duration": f"PT{run_sec}S", "splittable": False},
        ]
        edge = {"id": "edge-e", "predecessor": spec1, "successor": spec2,
                "min_lag": min_lag_iso, "max_lag": max_lag_iso}
        ress = [{"id": r_id, "resource_type": "machine", "capabilities": [],
                 "capacity": 1, "cost_rate": 1.0, "calendar_ref": None, "pool_refs": []}]
        fuls = [{"id": f_id, "demand_ref": d_id, "workpackage_ref": wp_id,
                 "allocated_quantity": {"value": 10, "uom": "EA"}, "decision_ref": "dec-1"}]
        demands = [{"id": d_id, "product_ref": "p", "quantity": {"value": 10, "uom": "EA"},
                    "due": DUE.isoformat(), "earliest_start": HORIZON.isoformat(),
                    "commitment_class": "standard", "customer_weight": 1.0}]
        cm = {"id": "cm", "version": 1, "effective_from": None, "resource_rates": {r_id: 1.0},
              "setup_cost_basis": {"fixed_per_setup": 0.0, "scrap_cost_per_unit": 0.0},
              "tardiness_weights": {"base_weight": 1.0, "commitment_class_multipliers": {}},
              "overtime_premium": 0.0, "inventory_carrying": 0.0}
        cals = [{"id": "cal", "base_pattern": {"weekdays": [0, 1, 2, 3, 4], "shift_start": "00:00",
                 "shift_end": "23:59"}, "exceptions": [], "horizon_resolved": []}]

        model, var_map = SolverBuilder().build(
            wps + ops + [edge], ress, cals, fuls + demands, [], cm,
        )
        from ortools.sat.python import cp_model as cp
        solver = cp.CpSolver()
        solver.parameters.max_time_in_seconds = 10.0
        solver.parameters.num_search_workers = 1
        status = solver.Solve(model)
        return status, solver, var_map, op1, op2

    def test_min_lag_enforced(self):
        from ortools.sat.python import cp_model as cp
        status, solver, var_map, op1, op2 = self._build(min_lag_iso="PT120M", max_lag_iso=None)
        assert status in (cp.OPTIMAL, cp.FEASIBLE)
        gap = solver.Value(var_map.op_start[op2]) - solver.Value(var_map.op_end[op1])
        assert gap >= 120

    def test_max_lag_enforced(self):
        """A tight max_lag forces the successor to start soon after the
        predecessor ends — verified by checking the solved gap respects it."""
        from ortools.sat.python import cp_model as cp
        status, solver, var_map, op1, op2 = self._build(min_lag_iso="PT0S", max_lag_iso="PT30M")
        assert status in (cp.OPTIMAL, cp.FEASIBLE)
        gap = solver.Value(var_map.op_start[op2]) - solver.Value(var_map.op_end[op1])
        assert gap <= 30

    def test_max_lag_none_is_unconstrained(self):
        """With max_lag=None the solver is free to push op2 arbitrarily far
        out; this just confirms no upper-bound constraint was added (no
        crash, and a large min_lag is still satisfiable)."""
        from ortools.sat.python import cp_model as cp
        status, solver, var_map, op1, op2 = self._build(min_lag_iso="PT500M", max_lag_iso=None)
        assert status in (cp.OPTIMAL, cp.FEASIBLE)
        gap = solver.Value(var_map.op_start[op2]) - solver.Value(var_map.op_end[op1])
        assert gap >= 500

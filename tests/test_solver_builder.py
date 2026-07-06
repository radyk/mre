"""Tests for M5 Solver Builder — derived from docs/01 §8 and docs/03 Phase 2.

The builder accepts EXACTLY six inputs (docs/01 §8.6):
  1. work_items    — WorkPackage + Operation dicts (mixed)
  2. capacity_items — Resource + ResourcePool dicts (mixed)
  3. calendars     — Calendar entities with horizon_resolved populated
  4. demand_items  — Fulfillment + Demand dicts (mixed)
  5. constraints   — list[Constraint dicts]
  6. cost_model    — CostModel dict

Returns (CpModel, VariableMap). After solve, call var_map.extract(solver) to get
SolveValues (plain-value struct, no ortools types).
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

UTC = timezone.utc
HORIZON = datetime(2026, 7, 13, 7, 0, tzinfo=UTC)
DUE_MON = datetime(2026, 7, 13, 23, 59, tzinfo=UTC)
DUE_WED = datetime(2026, 7, 15, 23, 59, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Minimal entity factories (dicts as stored by SnapshotWriter)
# ---------------------------------------------------------------------------


def _demand(did, prod_id, qty, due, earliest=None, weight=1.0, cclass="standard"):
    return {
        "id": did, "product_ref": prod_id,
        "quantity": {"value": qty, "uom": "EA"},
        "due": due.isoformat(),
        "earliest_start": earliest.isoformat() if earliest else None,
        "commitment_class": cclass, "customer_weight": weight,
    }


def _operation(oid, wp_id, spec_id, seq=10, setup_sec=60, run_sec=9000,
               family="gear"):
    return {
        "id": oid, "spec_ref": spec_id, "workpackage_ref": wp_id,
        "sequence": seq, "predecessors": [],
        "resource_requirements": [],  # no specific requirement → all resources eligible
        "setup_family": family,
        "setup_duration": f"PT{setup_sec}S",
        "run_duration": f"PT{run_sec}S",
        "dwell_duration": "PT0S", "splittable": False,
    }


def _wp(wid, prod_id, qty, ops, earliest=None, created_by="dec-1"):
    return {
        "id": wid, "product_ref": prod_id,
        "quantity": {"value": qty, "uom": "EA"},
        "earliest_start": earliest.isoformat() if earliest else None,
        "operations": ops, "process_version": 1,
        "state": "planned", "created_by": created_by,
    }


def _resource(rid, cap="gear_cutting", rate=6.0, cal_ref=None):
    return {
        "id": rid, "resource_type": "machine",
        "capabilities": [cap], "capacity": 1,
        "cost_rate": rate, "calendar_ref": cal_ref, "pool_refs": [],
    }


def _pool(pid, members, cap=2, cal_ref=None):
    return {
        "id": pid, "members": members,
        "concurrent_capacity": cap, "calendar_ref": cal_ref,
    }


def _fulfillment(fid, demand_id, wp_id, qty, dec="dec-1"):
    return {
        "id": fid, "demand_ref": demand_id, "workpackage_ref": wp_id,
        "allocated_quantity": {"value": qty, "uom": "EA"},
        "decision_ref": dec,
    }


def _calendar(cid, windows=None):
    """Return a Calendar entity dict. windows is a list of {"start": ..., "end": ...} dicts
    in horizon_resolved form. Empty list = always open (no blocking)."""
    return {
        "id": cid,
        "base_pattern": {"weekdays": [0,1,2,3,4], "shift_start": "07:00", "shift_end": "19:00"},
        "exceptions": [],
        "horizon_resolved": windows or [],
    }


def _costmodel(cmid, rates=None, setup_fixed=50.0):
    return {
        "id": cmid, "version": 1, "effective_from": None,
        "resource_rates": rates or {},
        "setup_cost_basis": {"fixed_per_setup": setup_fixed, "scrap_cost_per_unit": 0.0},
        "tardiness_weights": {
            "base_weight": 1.0,
            "commitment_class_multipliers": {"standard": 1.0, "rush": 2.0, "firm": 3.0},
        },
        "overtime_premium": 0.0, "inventory_carrying": 0.0,
    }


def _constraint(con_id, matrix=None):
    return {
        "id": con_id,
        "constraint_type": "setup_transition",
        "subjects": [], "parameters": {"transition_minutes": matrix or {}},
        "provenance_class": "policy", "authority": "test",
        "hardness": "soft", "penalty_weight": 1.0,
    }


# ---------------------------------------------------------------------------
# Six-input rule (docs/01 §8.6)
# ---------------------------------------------------------------------------


class TestSixInputRule:
    def test_build_method_has_exactly_six_non_self_params(self):
        """Entry point must accept EXACTLY six inputs, no more, no less."""
        import inspect
        from mre.modules.solver_builder import SolverBuilder
        sig = inspect.signature(SolverBuilder.build)
        params = [p for p in sig.parameters if p != "self"]
        assert len(params) == 6, (
            f"SolverBuilder.build must have 6 params, got {len(params)}: {params}"
        )

    def test_build_raises_typeerror_with_too_few_args(self):
        from mre.modules.solver_builder import SolverBuilder
        with pytest.raises(TypeError):
            SolverBuilder().build()

    def test_solver_builder_does_not_import_provenance_sidecar(self):
        """The Solver Builder must never read the provenance sidecar (docs/01 §8.6)."""
        import ast
        from pathlib import Path
        src = (Path(__file__).parent.parent /
               "src" / "mre" / "modules" / "solver_builder.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                s = ast.dump(node)
                assert "ProvenanceSidecar" not in s, \
                    "SolverBuilder must not import ProvenanceSidecar"


# ---------------------------------------------------------------------------
# VariableMap structure
# ---------------------------------------------------------------------------


def _build_one_op(r_id="res-1", wp_id="wp-1", op_id="op-1",
                  d_id="d-1", f_id="f-1", run_sec=9000):
    """Minimal build: 1 WP, 1 op, 1 resource, 1 demand/fulfillment."""
    from mre.modules.solver_builder import SolverBuilder

    wps = [_wp(wp_id, "prod-1", 200, [op_id], earliest=HORIZON)]
    ops = [_operation(op_id, wp_id, "spec-1", run_sec=run_sec)]
    ress = [_resource(r_id, rate=6.0)]
    fuls = [_fulfillment(f_id, d_id, wp_id, 200)]
    demands = [_demand(d_id, "prod-1", 200, DUE_MON, earliest=HORIZON)]
    cm = _costmodel("cm", rates={r_id: 6.0})
    con = _constraint("con")
    cals = [_calendar("cal")]

    return SolverBuilder().build(
        wps + ops,       # work_items
        ress,            # capacity_items
        cals,            # calendars
        fuls + demands,  # demand_items
        [con],           # constraints
        cm,              # cost_model
    )


class TestVariableMap:
    def test_build_returns_model_and_variable_map(self):
        from ortools.sat.python import cp_model as cp
        model, var_map = _build_one_op()
        assert isinstance(model, cp.CpModel)
        assert var_map is not None

    def test_var_map_exposes_operation_ids(self):
        _, var_map = _build_one_op(op_id="op-check")
        assert "op-check" in var_map.op_ids

    def test_var_map_exposes_horizon_start(self):
        _, var_map = _build_one_op()
        assert var_map.horizon_start is not None

    def test_two_fulfillments_yield_two_independent_tardiness_terms(self):
        """Two Fulfillments on same WP → two independent tardiness vars (D-07)."""
        from mre.modules.solver_builder import SolverBuilder
        wp_id = "wp-tard"
        op_id = "op-tard"
        r_id  = "res-tard"
        d1_id = "d-tard-1"
        d2_id = "d-tard-2"
        f1_id = "f-tard-1"
        f2_id = "f-tard-2"

        wps  = [_wp(wp_id, "prod-t", 400, [op_id], earliest=HORIZON)]
        ops  = [_operation(op_id, wp_id, "spec-t", run_sec=9000)]
        ress = [_resource(r_id)]
        demands = [
            _demand(d1_id, "prod-t", 200, DUE_MON, earliest=HORIZON),
            _demand(d2_id, "prod-t", 200, DUE_WED, earliest=HORIZON),
        ]
        fuls = [
            _fulfillment(f1_id, d1_id, wp_id, 200),
            _fulfillment(f2_id, d2_id, wp_id, 200),
        ]
        cm  = _costmodel("cm-t", rates={r_id: 6.0})
        con = _constraint("con-t")
        cals = [_calendar("cal-t")]

        _, var_map = SolverBuilder().build(
            wps + ops, ress, cals, fuls + demands, [con], cm
        )
        assert f1_id in var_map.fulfillment_ids
        assert f2_id in var_map.fulfillment_ids
        # Different variable objects (independent terms)
        assert var_map.fulfillment_ids[f1_id] != var_map.fulfillment_ids[f2_id]

    def test_var_map_extract_returns_plain_values_no_ortools(self):
        """After solve, extract() returns SolveValues with no ortools types."""
        from ortools.sat.python import cp_model as cp
        from mre.modules.solver_builder import SolverBuilder, SolveValues

        wps  = [_wp("wp-s", "prod-s", 200, ["op-s"], earliest=HORIZON)]
        ops  = [_operation("op-s", "wp-s", "spec-s", run_sec=600)]
        ress = [_resource("res-s")]
        fuls = [_fulfillment("f-s", "d-s", "wp-s", 200)]
        demands = [_demand("d-s", "prod-s", 200, DUE_WED, earliest=HORIZON)]
        cm  = _costmodel("cm-s", rates={"res-s": 6.0})
        cals = [_calendar("cal-s")]
        model, var_map = SolverBuilder().build(
            wps + ops, ress, cals, fuls + demands, [], cm
        )
        solver = cp.CpSolver()
        solver.parameters.max_time_in_seconds = 5.0
        solver.Solve(model)
        sv = var_map.extract(solver)
        assert isinstance(sv, SolveValues)
        assert "op-s" in sv.op_start_minutes
        assert isinstance(sv.op_start_minutes["op-s"], int)


# ---------------------------------------------------------------------------
# SolveValues is importable without ortools
# ---------------------------------------------------------------------------

class TestSolveValuesNoOrtools:
    def test_solve_values_importable_without_ortools(self):
        """SolveValues is a plain dataclass — no ortools dependency at import time."""
        import sys
        ortools_mods = [k for k in sys.modules if k.startswith("ortools")]
        saved = {k: sys.modules.pop(k) for k in ortools_mods}
        builder_mod = sys.modules.pop("mre.modules.solver_builder", None)
        try:
            from mre.modules.solver_builder import SolveValues
            sv = SolveValues(
                op_start_minutes={"op-1": 0},
                op_end_minutes={"op-1": 150},
                op_resource={"op-1": "res-1"},
                wp_end_minutes={"wp-1": 150},
                tardiness_minutes={"f-1": 0},
                horizon_start=HORIZON,
            )
            assert sv.op_start_minutes["op-1"] == 0
        finally:
            sys.modules.update(saved)
            if builder_mod:
                sys.modules["mre.modules.solver_builder"] = builder_mod

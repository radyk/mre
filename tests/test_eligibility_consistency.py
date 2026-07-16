"""Tier-0 payload eligibility == solver op_assign literal set (docs/04 R-DP6,
Session 4.0b — the consistency contract as a permanent regression).

The 4.0-hotfix proved an accepted drop targeted a resource the solver had no
op_assign literal for — the R-DP1 pin's machine axis was silently skipped. That
can only happen if Tier-0 GREENS a row the solver considers ineligible. R-DP6
requires green = provably-not-illegal BY THE SAME RULES the solver compiles.
These tests pin that equivalence:

  * for a SOLVED schedule, every scheduled op's payload ``eligible_resource_ids``
    equals the set of resources it has an ``op_assign`` literal for (the set the
    pin binds) — run on multi_route_distinct AND busy_board;
  * a constructed resumable op with a calendar-dead eligible resource: the
    solver prunes it (no literal), the shared derivation prunes it too, and the
    payload names WHY (``dim_reasons`` = "no_calendar_window") rather than
    greening it.

Since both consumers now draw from the shared ``eligibility`` module, parity is
structural; this guard defends the plumbing (horizon derivation, calendar
flatten, the extractor→assembler round-trip) that carries it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mre.modules.eligibility import (
    REASON_NO_CALENDAR, capability_eligible, pinnable_resources,
)
from mre.modules.solver_builder import SolverBuilder

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Unit: the shared capability resolver (the single copy)
# ---------------------------------------------------------------------------

def _res(rid, caps):
    return {"id": rid, "resource_type": "machine", "capabilities": caps,
            "capacity": 1, "cost_rate": 1.0, "calendar_ref": None, "pool_refs": []}


class TestCapabilityEligibleShared:
    def test_no_requirement_opens_all(self):
        rbi = {"R0": _res("R0", ["m"]), "R1": _res("R1", ["t"])}
        assert capability_eligible([], rbi) == ["R0", "R1"]

    def test_explicit_set_intersects_known(self):
        rbi = {"R0": _res("R0", []), "R1": _res("R1", [])}
        reqs = [{"mode": "explicit_set", "resource_refs": ["R1", "GHOST"]}]
        assert capability_eligible(reqs, rbi) == ["R1"]

    def test_empty_match_falls_back_to_all(self):
        rbi = {"R0": _res("R0", []), "R1": _res("R1", [])}
        reqs = [{"mode": "explicit_set", "resource_refs": ["GHOST"]}]
        assert capability_eligible(reqs, rbi) == ["R0", "R1"]

    def test_order_is_resource_dict_order(self):
        # The solver creates op_assign literals in this order; the shared
        # function must preserve it so variable-creation order is unchanged.
        rbi = {"Z": _res("Z", []), "A": _res("A", [])}
        assert capability_eligible([], rbi) == ["Z", "A"]


# ---------------------------------------------------------------------------
# Constructed resumable op: solver prune == payload prune, with a reason
# ---------------------------------------------------------------------------

class TestResumablePrunedRowNeverGreened:
    """A resumable op eligible on two machines, one with no in-horizon calendar
    window. The solver builds no op_assign literal for the dead machine; the
    shared derivation excludes it too and names the reason."""

    def _build(self):
        # A Monday two weeks out, derived from now() so it is ALWAYS future and
        # never rots — a hardcoded date would make _compute_horizon fall to
        # wall-clock once it passed (the 3.3b datetime.now() horizon trap).
        base = (datetime.now(UTC).replace(hour=7, minute=0, second=0, microsecond=0)
                + timedelta(days=14))
        H0 = base + timedelta(days=(7 - base.weekday()) % 7)  # next Monday on/after

        resources = [
            _res("R0", ["mill"]) | {"calendar_ref": "cal0"},
            _res("R1", ["mill"]) | {"calendar_ref": "cal1"},
        ]
        for r in resources:
            r["cost_rate"] = 5.0
        calendars = [
            {"id": "cal0", "base_pattern": {"weekdays": [0, 1, 2, 3, 4],
             "shift_start": "07:00", "shift_end": "19:00"}, "exceptions": [],
             "horizon_resolved": []},
            # cal1 never opens → R1 has no in-horizon window at all.
            {"id": "cal1", "base_pattern": {"weekdays": [],
             "shift_start": "07:00", "shift_end": "19:00"}, "exceptions": [],
             "horizon_resolved": []},
        ]
        op = {
            "id": "op-1", "spec_ref": "spec-1", "workpackage_ref": "wp-1",
            "sequence": 10,
            "resource_requirements": [{"mode": "explicit_set",
                                       "resource_refs": ["R0", "R1"]}],
            "setup_family": "mill", "setup_duration": "PT0S",
            "run_duration": "PT9000S",           # 150 working minutes
            "splittable": True, "min_chunk": "PT3600S",  # 60 → 150 ≥ 2×60 resumable
        }
        wp = {"id": "wp-1", "product_ref": "p1", "quantity": {"value": 1, "uom": "EA"},
              "earliest_start": None, "operations": ["op-1"], "process_version": 1,
              "state": "planned", "created_by": "d1"}
        demand = {"id": "dem-1", "product_ref": "p1", "quantity": {"value": 1, "uom": "EA"},
                  "due": (H0 + timedelta(days=6)).isoformat(), "earliest_start": None,
                  "commitment_class": "standard", "customer_weight": 1.0}
        ful = {"id": "f1", "demand_ref": "dem-1", "workpackage_ref": "wp-1",
               "allocated_quantity": {"value": 1, "uom": "EA"}, "decision_ref": "d1"}
        cm = {"id": "cm", "version": 1, "effective_from": None,
              "resource_rates": {"R0": 5.0, "R1": 5.0},
              "setup_cost_basis": {"fixed_per_setup": 0.0, "scrap_cost_per_unit": 0.0},
              "tardiness_weights": {"base_weight": 1.0,
                                    "commitment_class_multipliers": {"standard": 1.0}},
              "overtime_premium": 0.0, "inventory_carrying": 0.0}
        model, var_map = SolverBuilder(reference_date=H0).build(
            [wp, op], resources, calendars, [ful, demand], [], cm)
        return op, resources, var_map

    def test_solver_prunes_the_dead_machine(self):
        _, _, var_map = self._build()
        keys = set(var_map.op_assign.get("op-1", {}).keys())
        assert "R1" not in keys, "solver must not build a literal for a calendar-dead machine"
        assert "R0" in keys, "the live machine keeps its literal"

    def test_payload_matches_and_names_the_reason(self):
        op, resources, var_map = self._build()
        resources_by_id = {r["id"]: r for r in resources}
        # var_map.cal_windows IS the flatten the solver used — feed the shared
        # derivation the same windows the builder saw.
        pinnable, reasons = pinnable_resources(
            op, resources_by_id, var_map.cal_windows, wp_earliest_min=0, total_min=150,
        )
        assert set(pinnable) == set(var_map.op_assign.get("op-1", {}).keys())
        assert "R1" not in pinnable
        assert reasons.get("R1") == REASON_NO_CALENDAR, \
            "a solver-pruned row must be dimmed with an honest reason, not greened"


# ---------------------------------------------------------------------------
# Standing guard on the real fixtures (slow): payload == op_assign, every op
# ---------------------------------------------------------------------------

def _solve_and_load(tmp: Path, scenario: str, seed: int):
    from tools.generate_erp_dataset import generate
    from mre.__main__ import main as mre_main
    from mre.modules.snapshot_store import SnapshotStore

    sub = tmp / "sub"
    generate(sub, scenario=scenario, seed=seed)
    out = tmp / "out"
    rc = mre_main(["--submission", str(sub), "--out", str(out),
                   "--snapshot-id", "snap", "--time-limit", "30",
                   "--solver-workers", "1", "--solver-seed", "42"])
    assert rc == 0, f"pipeline exit {rc}"
    reader = SnapshotStore(out / "snapshots").load_snapshot("snap")
    return out, reader


def _op_assign_keys(reader):
    """Rebuild the model from the snapshot and return {op_id: {resource_ids}} —
    the literal set the R-DP1 pin binds against. op_assign membership is a
    BUILD-time property (independent of the solve result)."""
    from mre.modules.scenario import derive_base_context
    demands = list(reader.iter_entities("demand"))
    fuls = list(reader.iter_entities("fulfillment"))
    wps = list(reader.iter_entities("workpackage"))
    ops = list(reader.iter_entities("operation"))
    edges = list(reader.iter_entities("precedenceedge"))
    resources = list(reader.iter_entities("resource"))
    pools = list(reader.iter_entities("resourcepool"))
    calendars = list(reader.iter_entities("calendar"))
    constraints = list(reader.iter_entities("constraint"))
    costmodels = list(reader.iter_entities("costmodel"))
    cost_model = costmodels[0] if costmodels else {}
    return ops, resources, SolverBuilder().build(
        wps + ops + edges, resources + pools, calendars,
        fuls + demands, constraints, cost_model)


@pytest.mark.slow
@pytest.mark.parametrize("scenario,seed", [("multi_route_distinct", 7), ("busy_board", 11)])
def test_payload_eligibility_equals_solver_literals(tmp_path, scenario, seed):
    from mre.modules.schedule_assembler import build_document_from_run

    out, reader = _solve_and_load(tmp_path, scenario, seed)
    schedule = list(reader.iter_entities("schedule"))[-1]
    document = build_document_from_run(out, "snap", schedule.get("id", "guard"))
    assert document.interaction is not None, "interaction payload must be built"
    payload = {o.operation_ref: set(o.eligible_resource_ids)
               for o in document.interaction.operations}

    _, _, (model, var_map) = _op_assign_keys(reader)

    mismatches = []
    for op_ref, elig in payload.items():
        literals = set(var_map.op_assign.get(op_ref, {}).keys())
        if elig != literals:
            mismatches.append((op_ref[:8], sorted(elig - literals), sorted(literals - elig)))
    assert not mismatches, (
        f"{scenario}: payload eligible_resource_ids diverges from solver op_assign "
        f"for {len(mismatches)} ops (offered-not-pinnable / pinnable-not-offered): "
        f"{mismatches[:5]}"
    )

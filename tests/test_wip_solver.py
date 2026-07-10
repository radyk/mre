"""WIP solver semantics (docs/06 §5.13, session 2.3 CU3).

Complete operations are satisfied and off the model (capacity freed).
In-progress operations are fixed intervals on the observed resource for their
remaining duration. The amended invariant: no NEWLY scheduled op starts
before reference_date; an observed in-flight op is exempt (its remaining work
is pinned at reference_date, its observed pre-reference start is history).

The ghost-job non-regression (docs/07 standing risk) is in test_validator-
style form here: TEMPORAL_IMPOSSIBILITY still excludes a past-due unstarted
demand in the same run that honors an in-flight op with a pre-reference start.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from mre.modules.solver_builder import SolverBuilder
from tests.test_solver_builder import (
    _calendar, _costmodel, _demand, _fulfillment, _resource, _wp,
)

UTC = timezone.utc
REF = datetime(2026, 7, 13, 0, 0, tzinfo=UTC)     # midnight reference_date
SOON = datetime(2026, 7, 20, 23, 59, tzinfo=UTC)
TIGHT = datetime(2026, 7, 13, 2, 0, tzinfo=UTC)   # REF + 120 min (op2's duration)


def _wip_op(oid, wp_id, spec_id, r_id, *, status=None, remaining_min=None,
            observed_res=None, observed_start=None, seq=10, run_sec=7200):
    return {
        "id": oid, "spec_ref": spec_id, "workpackage_ref": wp_id, "sequence": seq,
        "resource_requirements": [{
            "mode": "explicit_set", "capability_ref": None,
            "resource_refs": [r_id], "count": 1,
        }],
        "setup_family": "", "setup_duration": "PT0S",
        "run_duration": f"PT{run_sec}S", "splittable": False, "min_chunk": None,
        "wip_status": status,
        "observed_start": observed_start.isoformat() if observed_start else None,
        "observed_resource_ref": observed_res,
        "remaining_duration": f"PT{remaining_min}M" if remaining_min else None,
    }


def _solve(model):
    from ortools.sat.python import cp_model as cp
    solver = cp.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = 10
    status = solver.Solve(model)
    return solver, status, cp


# ---------------------------------------------------------------------------
# Complete ops: off the model, capacity freed
# ---------------------------------------------------------------------------

def test_complete_op_has_no_variables(tmp_path):
    r = "R"
    op = _wip_op("op1", "wp1", "spec1", r, status="complete",
                 observed_res=r, observed_start=datetime(2026, 7, 12, 8, tzinfo=UTC))
    wp = _wp("wp1", "prod", 100, ["op1"], earliest=REF)
    d = _demand("d1", "prod", 100, SOON, earliest=REF)
    ful = _fulfillment("f1", "d1", "wp1", 100)
    model, vm = SolverBuilder(reference_date=REF).build(
        [wp, op], [_resource(r)], [_calendar("c")],
        [ful, d], [], _costmodel("cm"),
    )
    # satisfied → no start var, no resource assignment, off no-overlap
    assert "op1" not in vm.op_start
    assert "op1" not in vm.op_assign
    _, status, cp = _solve(model)
    assert status in (cp.OPTIMAL, cp.FEASIBLE)


def _two_wp_shared_resource(op1_status):
    """op1 (WIP under test) and op2 (a plain future op) both eligible ONLY on
    R. op1 in-flight occupies [0,240]; op1 complete frees it. op2 wants to
    start as early as possible (tardiness pressure)."""
    r = "R"
    op1 = _wip_op("op1", "wp1", "spec1", r, status=op1_status,
                  remaining_min=(240 if op1_status == "in_progress" else None),
                  observed_res=r,
                  observed_start=datetime(2026, 7, 12, 20, tzinfo=UTC))
    op2 = _wip_op("op2", "wp2", "spec2", r, run_sec=7200)   # 120 min
    wp1 = _wp("wp1", "prodA", 100, ["op1"], earliest=REF)
    wp2 = _wp("wp2", "prodB", 100, ["op2"], earliest=REF)
    d1 = _demand("d1", "prodA", 100, SOON, earliest=REF)
    # op2 is due-pressured: to be on time it must start at reference_date. In
    # the in-flight case the occupied window forces it 240 min late; in the
    # complete case the freed window lets it start on time. The ONLY variable
    # is op1's status — this is the capacity counterfactual.
    d2 = _demand("d2", "prodB", 100, TIGHT, earliest=REF)
    f1 = _fulfillment("f1", "d1", "wp1", 100)
    f2 = _fulfillment("f2", "d2", "wp2", 100)
    model, vm = SolverBuilder(reference_date=REF).build(
        [wp1, wp2, op1, op2], [_resource(r)], [_calendar("c")],
        [f1, f2, d1, d2], [], _costmodel("cm"),
    )
    return model, vm


def test_in_flight_op_occupies_capacity_pushing_others_later():
    model, vm = _two_wp_shared_resource("in_progress")
    solver, status, cp = _solve(model)
    assert status in (cp.OPTIMAL, cp.FEASIBLE)
    # op2 cannot use [0,240] (in-flight op1 occupies it) → starts at/after 240
    assert solver.Value(vm.op_start["op2"]) >= 240


def test_complete_op_frees_capacity_for_another_demand():
    """The counterfactual to the in-flight case (price-bought-something, on
    capacity): the ONLY difference is op1's status, and it lets op2 start at
    reference_date instead of being pushed 240 min later."""
    model, vm = _two_wp_shared_resource("complete")
    solver, status, cp = _solve(model)
    assert status in (cp.OPTIMAL, cp.FEASIBLE)
    assert "op1" not in vm.op_start                    # op1 off the model
    assert solver.Value(vm.op_start["op2"]) == 0       # freed window at ref date


# ---------------------------------------------------------------------------
# In-progress ops: fixed interval; successors chain from the fixed reality
# ---------------------------------------------------------------------------

def test_successor_chains_after_in_flight_remaining():
    r = "R"
    op1 = _wip_op("op1", "wp1", "spec1", r, status="in_progress",
                  remaining_min=300, observed_res=r, seq=10,
                  observed_start=datetime(2026, 7, 12, 20, tzinfo=UTC))
    op2 = _wip_op("op2", "wp1", "spec2", r, run_sec=3600, seq=20)   # 60 min
    wp = _wp("wp1", "prod", 100, ["op1", "op2"], earliest=REF)
    d = _demand("d1", "prod", 100, SOON, earliest=REF)
    ful = _fulfillment("f1", "d1", "wp1", 100)
    edge = {"id": "e1", "predecessor": "spec1", "successor": "spec2",
            "min_lag": "PT0S", "max_lag": None}
    model, vm = SolverBuilder(reference_date=REF).build(
        [wp, op1, op2, edge], [_resource(r)], [_calendar("c")],
        [ful, d], [], _costmodel("cm"),
    )
    solver, status, cp = _solve(model)
    assert status in (cp.OPTIMAL, cp.FEASIBLE)
    # op1's remaining work ends at 300; op2 (its successor) starts >= 300
    assert solver.Value(vm.op_start["op2"]) >= 300


def test_in_flight_interval_exempt_from_calendar_closure():
    """The amended invariant at the calendar clamp: an in-flight op's remaining
    work occupies the machine across a shift boundary. With reference_date at
    midnight and a 07:00 shift start, [0,240] falls in the pre-shift closure —
    the in-flight span is carved out of the blocking so the model stays
    feasible (the machine is committed-busy, not calendar-blocked)."""
    r = "R"
    # calendar open only 07:00-19:00 on the reference day → [0,420] is closed
    day = REF
    windows = [{"start": day.replace(hour=7).isoformat(),
                "end": day.replace(hour=19).isoformat()}]
    cal = _calendar("c", windows=windows)
    res = _resource(r, cal_ref="c")
    op = _wip_op("op1", "wp1", "spec1", r, status="in_progress",
                 remaining_min=240, observed_res=r,
                 observed_start=datetime(2026, 7, 12, 20, tzinfo=UTC))
    wp = _wp("wp1", "prod", 100, ["op1"], earliest=REF)
    d = _demand("d1", "prod", 100, SOON, earliest=REF)
    ful = _fulfillment("f1", "d1", "wp1", 100)
    model, vm = SolverBuilder(reference_date=REF).build(
        [wp, op], [res], [cal], [ful, d], [], _costmodel("cm"),
    )
    _, status, cp = _solve(model)
    assert status in (cp.OPTIMAL, cp.FEASIBLE)


# ---------------------------------------------------------------------------
# Ghost-job non-regression (docs/07 standing risk)
# ---------------------------------------------------------------------------

def test_temporal_impossibility_still_fires_while_in_flight_honored(tmp_path):
    """One validator run, two demands: a past-due UNSTARTED demand is excluded
    (the ghost-job fix intact); a past-due demand that is actually in_progress
    is NOT excluded (work is underway — not a ghost). The amended invariant
    must not regress the fix, and must not exclude live in-flight work."""
    from mre.contracts.vocabularies import ModuleCode, RunStatus
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.validator import Validator
    from mre.reporter import Reporter
    from mre.contracts.entities import Demand, Quantity, Product, Process, OperationSpec
    from mre.contracts.provenance import (
        ProvenanceSidecar, ProvenanceClass, DefaultedProvenance,
    )
    from mre.contracts.vocabularies import CommitmentClass, DemandStatus, ProcessStatus

    snap = "ghost-wip"
    store = SnapshotStore(tmp_path / "snapshots")
    writer = store.begin_snapshot(snap)

    def _dp(eid, attr):
        return ProvenanceSidecar(
            entity_id=eid, attribute_name=attr, snapshot_id=snap,
            provenance_class=ProvenanceClass.DEFAULTED,
            payload=DefaultedProvenance(policy="test"))

    ref = datetime(2026, 7, 13, tzinfo=UTC)
    past_due = datetime(2026, 6, 1, tzinfo=UTC)      # before reference_date

    # ghost: past-due, no WIP
    ghost = Demand(id="ghost", snapshot_id=snap, product_ref="prod",
                   quantity=Quantity(value=10, uom="EA"), due=past_due,
                   commitment_class=CommitmentClass.STANDARD,
                   status=DemandStatus.OPEN)
    # live: past-due, but an operation is in_progress on the floor
    live = Demand(id="live", snapshot_id=snap, product_ref="prod",
                  quantity=Quantity(value=10, uom="EA"), due=past_due,
                  commitment_class=CommitmentClass.STANDARD,
                  status=DemandStatus.OPEN,
                  wip_operations=[{
                      "sequence": 10, "spec_ref": "spec", "status": "in_progress",
                      "actual_start": "2026-07-01T08:00:00",
                      "actual_resource_ref": "res", "remaining_minutes": 120.0,
                      "quantity_complete": None, "source_rows": [1],
                  }])
    d_attrs = ["product_ref", "quantity", "due", "earliest_start",
               "commitment_class", "customer_weight", "customer_ref", "status",
               "wip_operations"]
    for d in (ghost, live):
        writer.write_entity(d, [_dp(d.id, a) for a in d_attrs])
    writer.finalize()

    rep = Reporter.begin(module=ModuleCode.M3, purpose="ghost/wip validate",
                         config={}, trigger="test", snapshot_id=snap,
                         sink_dir=tmp_path / "runs")
    result = Validator().run(snap, store, rep, reference_date=ref)
    rep.end(RunStatus.SUCCESS)

    assert "ghost" in result.excluded_demand_ids     # ghost-job fix intact
    assert "live" not in result.excluded_demand_ids  # in-flight work honored

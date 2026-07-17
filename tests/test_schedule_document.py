"""Schedule JSON contract tests (docs/07 Phase 2, session 2.1).

Written from the contract's rules:
- derived, not invented — every field maps to an entity / identity-map /
  evidence source;
- external names ONLY in *_name / work_order fields, UUID refs alongside;
- chunked operations carry one chunk per run window, pauses are the gaps
  (docs/05 R-C3); merged WPs list every work order;
- overtime minutes come from the assignment Decision's chosen payload;
- cost_summary must decompose exactly (dies at construction);
- assembly is deterministic (same inputs → identical document).
"""
from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from mre.contracts.schedule_document import (
    CONTRACT_VERSION, CostSummary, ScheduleDocument,
)
from mre.modules.identity_map import IdentityMap
from mre.modules.schedule_assembler import assemble_schedule_document

SNAP = "snap-t"
RUN = "run-t"


# ---------------------------------------------------------------------------
# Synthetic persisted world: one merged WP, one chunked op with a pause,
# overtime evidence, one lock, calendar with overtime + closure exceptions.
# ---------------------------------------------------------------------------

def _world() -> dict:
    demands = [
        {"id": "d-1", "snapshot_id": SNAP, "due": "2026-02-02T16:00:00+00:00",
         "customer_ref": "cust-9", "commitment_class": "standard"},
        {"id": "d-2", "snapshot_id": SNAP, "due": "2026-02-03T16:00:00+00:00",
         "customer_ref": None, "commitment_class": "standard"},
    ]
    fulfillments = [
        {"id": "f-1", "demand_ref": "d-1", "workpackage_ref": "wp-m"},
        {"id": "f-2", "demand_ref": "d-2", "workpackage_ref": "wp-m"},
    ]
    workpackages = [{"id": "wp-m", "snapshot_id": SNAP}]
    operations = [
        {"id": "op-1", "snapshot_id": SNAP, "workpackage_ref": "wp-m",
         "sequence": 10, "setup_family": "FAM-A", "setup_duration": "PT30M"},
    ]
    # Chunked: two run windows with a pause between (R-C3)
    assignments = [
        {"id": "a-1", "snapshot_id": SNAP, "operation_ref": "op-1",
         "workpackage_ref": "wp-m",
         "resource_assignments": [
             {"requirement": {"mode": "explicit_set", "resource_refs": ["r-1"]},
              "resource_ref": "r-1"}],
         "phase_windows": {
             "setup": None,
             "run": [
                 {"start": "2026-02-02T07:00:00+00:00", "end": "2026-02-02T15:00:00+00:00"},
                 {"start": "2026-02-03T07:00:00+00:00", "end": "2026-02-03T09:00:00+00:00"},
             ],
             "dwell": None,
         },
         "decision_ref": "dec-1"},
    ]
    service_outcomes = [
        {"id": "s-1", "snapshot_id": SNAP, "demand_ref": "d-1",
         "fulfillment_ref": "f-1",
         "projected_completion": "2026-02-03T09:00:00+00:00",
         "lateness": "PT2H", "tardiness_cost": 30.0},
        {"id": "s-2", "snapshot_id": SNAP, "demand_ref": "d-2",
         "fulfillment_ref": "f-2",
         "projected_completion": "2026-02-03T09:00:00+00:00",
         "lateness": "-PT30M", "tardiness_cost": 0.0},
    ]
    resources = [
        {"id": "r-1", "snapshot_id": SNAP, "resource_type": "machine",
         "calendar_ref": "cal-1", "pool_refs": []},
    ]
    calendars = [
        {"id": "cal-1", "snapshot_id": SNAP,
         "base_pattern": {"weekdays": [0, 1, 2, 3, 4],
                          "shift_start": "07:00", "shift_end": "15:00"},
         "exceptions": [
             {"window": {"start": "2026-02-02T15:00:00+00:00",
                         "end": "2026-02-02T19:00:00+00:00"},
              "type": "added", "reason": "overtime"},
             {"window": {"start": "2026-02-04T00:00:00+00:00",
                         "end": "2026-02-05T00:00:00+00:00"},
              "type": "closure", "reason": "planned_maintenance"},
         ]},
    ]
    constraints = [
        {"id": "con-1", "snapshot_id": SNAP, "constraint_type": "pinned_window",
         "subjects": ["d-1"], "parameters": {"start": "2026-02-02T07:00:00+00:00"},
         "provenance_class": "human_override", "hardness": "hard"},
    ]
    costmodels = [{"id": "cm-1", "snapshot_id": SNAP, "version": 3}]
    schedule = {
        "id": "sched-1", "snapshot_ref": SNAP, "costmodel_ref": "cm-1",
        "status": "proposed",
        "summary_metrics": {
            "total_cost": 200.0, "production_cost": 120.0,
            "production_regular_cost": 100.0, "production_overtime_cost": 20.0,
            "setup_cost": 50.0, "tardiness_cost": 30.0,
        },
    }

    imap = IdentityMap()
    imap.register("d-1", "ERP", "work_order", "WO-1001")
    imap.register("d-2", "IDS", "order_id", "WO-1002")
    imap.register("r-1", "ERP", "machine_id", "M-01")

    evidence = [
        {"record_type": "run_context_open", "module": "M3", "run_id": "rc-m3",
         "started_at": "2026-02-01T00:00:00+00:00", "purpose": "validator",
         "config_snapshot": {"reference_date": "2026-02-01T00:00:00+00:00"}},
        {"record_type": "run_context_open", "module": "M5", "run_id": "rc-m5",
         "started_at": "2026-02-01T00:00:01+00:00", "purpose": "model build",
         "config_snapshot": {"horizon_start": "2026-02-01T00:00:00+00:00",
                              "horizon_end": "2026-02-08T23:59:59+00:00"}},
        {"record_type": "run_context_open", "module": "M6", "run_id": "rc-m6",
         "started_at": "2026-02-01T00:00:02+00:00", "purpose": "solve run",
         "config_snapshot": {"time_limit": 30.0, "num_search_workers": 1,
                              "random_seed": 7}},
        {"record_type": "event", "status_text": "solve_complete", "run_id": "rc-m6",
         "payload": {"status": "OPTIMAL", "objective": 200.0, "best_bound": 200.0,
                      "gap": 0.0, "wall_time_s": 1.25}},
        {"record_type": "decision", "record_id": "dec-1", "run_id": "rc-m7",
         "decision_type": "assignment", "basis": "reconstructed",
         "chosen": {"resource_id": "r-1", "overtime_minutes": 45,
                     "production_cost": 120.0}},
    ]

    return dict(
        snapshot_id=SNAP, run_id=RUN, schedule=schedule,
        assignments=assignments, service_outcomes=service_outcomes,
        operations=operations, workpackages=workpackages,
        fulfillments=fulfillments, demands=demands, resources=resources,
        pools=[], calendars=calendars, constraints=constraints,
        costmodels=costmodels, identity_map=imap, evidence_records=evidence,
    )


@pytest.fixture()
def world() -> dict:
    return _world()


@pytest.fixture()
def doc(world) -> ScheduleDocument:
    return assemble_schedule_document(**world)


# ---------------------------------------------------------------------------
# Document header
# ---------------------------------------------------------------------------

class TestHeader:
    def test_versioned_from_day_one(self, doc):
        # 1.1 (2026-07-13): additive annotations.pool block for pool members
        assert doc.contract_version == CONTRACT_VERSION == "1.5"

    def test_pool_annotation_absent_on_ordinary_documents(self, doc):
        assert doc.annotations.pool is None

    def test_ids_and_status(self, doc):
        assert doc.schedule_id == "sched-1"
        assert doc.snapshot_id == SNAP
        assert doc.run_id == RUN
        assert doc.status.value == "proposed"

    def test_reference_date_and_horizon_from_evidence(self, doc):
        assert doc.reference_date.isoformat() == "2026-02-01T00:00:00+00:00"
        assert doc.horizon.start.isoformat() == "2026-02-01T00:00:00+00:00"
        assert doc.horizon.end.isoformat() == "2026-02-08T23:59:59+00:00"

    def test_solver_telemetry_from_evidence(self, doc):
        assert doc.solver.status == "OPTIMAL"
        assert doc.solver.objective == 200.0
        assert doc.solver.gap == 0.0
        assert doc.solver.wall_time_s == 1.25
        assert doc.solver.deterministic is True  # workers=1 + seed set

    def test_nondeterministic_when_not_pinned(self, world):
        for rec in world["evidence_records"]:
            if rec.get("module") == "M6":
                rec["config_snapshot"] = {"time_limit": 30.0}
        d = assemble_schedule_document(**world)
        assert d.solver.deterministic is False

    def test_missing_solve_complete_event_refuses_to_invent(self, world):
        world["evidence_records"] = [
            r for r in world["evidence_records"]
            if r.get("status_text") != "solve_complete"
        ]
        with pytest.raises(ValueError, match="solve_complete"):
            assemble_schedule_document(**world)


# ---------------------------------------------------------------------------
# Cost summary — must decompose exactly
# ---------------------------------------------------------------------------

class TestCostSummary:
    def test_ledger_mapped_with_costmodel_version(self, doc):
        cs = doc.cost_summary
        assert cs.total == 200.0
        assert cs.production_regular == 100.0
        assert cs.production_overtime == 20.0
        assert cs.setup == 50.0
        assert cs.tardiness == 30.0
        assert cs.costmodel_version == 3

    def test_decomposition_enforced_at_construction(self):
        with pytest.raises(ValidationError, match="does not decompose"):
            CostSummary(total=999.0, production_regular=100.0,
                        production_overtime=20.0, setup=50.0, tardiness=30.0)

    def test_assembly_dies_on_non_decomposing_ledger(self, world):
        world["schedule"]["summary_metrics"]["total_cost"] = 500.0
        with pytest.raises(ValidationError, match="does not decompose"):
            assemble_schedule_document(**world)


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------

class TestAssignments:
    def test_chunked_op_pauses_between_chunks(self, doc):
        a = doc.assignments[0]
        assert [c.chunk_seq for c in a.chunks] == [1, 2]
        assert a.chunks[0].working_min == 480
        assert a.chunks[1].working_min == 120
        # the pause is the gap between chunks, never a chunk itself (R-C3)
        assert a.chunks[0].end < a.chunks[1].start

    def test_merged_wp_lists_all_work_orders(self, doc):
        assert doc.assignments[0].work_orders == ["WO-1001", "WO-1002"]

    def test_external_name_alongside_uuid_ref(self, doc):
        a = doc.assignments[0]
        assert a.resource_id == "r-1"          # canonical ref kept
        assert a.external_name == "M-01"       # customer vocabulary
        assert a.operation_ref == "op-1"
        assert a.workpackage_ref == "wp-m"

    def test_overtime_minutes_from_decision_evidence(self, doc):
        assert doc.assignments[0].in_overtime_min == 45
        assert doc.assignments[0].decision_ref == "dec-1"

    def test_setup_phase_is_first_setup_minutes_of_first_chunk(self, doc):
        ph = doc.assignments[0].phases
        assert ph.setup is not None
        assert ph.setup.start == doc.assignments[0].chunks[0].start
        assert (ph.setup.end - ph.setup.start).total_seconds() == 30 * 60
        assert ph.teardown is None             # not modeled — always null

    def test_no_setup_phase_when_zero_duration(self, world):
        world["operations"][0]["setup_duration"] = "PT0S"
        d = assemble_schedule_document(**world)
        assert d.assignments[0].phases.setup is None

    def test_op_metadata(self, doc):
        assert doc.assignments[0].op_seq == 10
        assert doc.assignments[0].setup_family == "FAM-A"


# ---------------------------------------------------------------------------
# Service outcomes — per Demand, never per WorkPackage
# ---------------------------------------------------------------------------

class TestServiceOutcomes:
    def test_one_block_per_demand(self, doc):
        assert [s.demand_ref for s in doc.service_outcomes] == ["d-1", "d-2"]

    def test_lateness_parsed_negative_means_early(self, doc):
        by_wo = {s.work_order: s for s in doc.service_outcomes}
        assert by_wo["WO-1001"].lateness_min == 120
        assert by_wo["WO-1002"].lateness_min == -30

    def test_due_and_customer_carried(self, doc):
        s1 = doc.service_outcomes[0]
        assert s1.due.isoformat() == "2026-02-02T16:00:00+00:00"
        assert s1.customer_ref == "cust-9"
        assert s1.tardiness_cost == 30.0


# ---------------------------------------------------------------------------
# Resource lanes + calendar shading
# ---------------------------------------------------------------------------

class TestResourceLanes:
    def test_lane_with_external_name(self, doc):
        lane = doc.resources[0]
        assert lane.resource_id == "r-1"
        assert lane.external_name == "M-01"

    def test_calendar_window_kinds(self, doc):
        kinds = {w.kind for w in doc.resources[0].calendar_windows}
        assert kinds == {"regular", "overtime", "closure"}

    def test_closure_day_has_no_regular_window(self, doc):
        regs = [w for w in doc.resources[0].calendar_windows
                if w.kind == "regular"]
        assert not any(w.start.date().isoformat() == "2026-02-04" for w in regs)


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------

class TestAnnotations:
    def test_lock_rendered_visible(self, doc):
        assert len(doc.annotations.locks) == 1
        assert doc.annotations.locks[0].startswith("pinned_window[WO-1001]")

    def test_base_schedule_is_not_a_scenario(self, doc):
        assert doc.annotations.scenario.is_scenario is False
        assert doc.annotations.scenario.parent_schedule_id is None

    def test_scenario_marking_and_lineage(self, world):
        world["schedule"]["summary_metrics"]["is_scenario"] = True
        world["parent_schedule_id"] = "sched-0"
        d = assemble_schedule_document(**world)
        assert d.annotations.scenario.is_scenario is True
        assert d.annotations.scenario.parent_schedule_id == "sched-0"


# ---------------------------------------------------------------------------
# Determinism + serialization
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_inputs_identical_document(self, world):
        d1 = assemble_schedule_document(**copy.deepcopy(world))
        d2 = assemble_schedule_document(**copy.deepcopy(world))
        assert d1.model_dump(mode="json") == d2.model_dump(mode="json")

    def test_json_round_trip_validates(self, doc):
        dumped = doc.model_dump(mode="json")
        reparsed = ScheduleDocument.model_validate(dumped)
        assert reparsed.model_dump(mode="json") == dumped

    def test_timestamps_are_utc_iso(self, doc):
        dumped = doc.model_dump(mode="json")
        assert dumped["assignments"][0]["chunks"][0]["start"].endswith(
            ("+00:00", "Z"))


# ---------------------------------------------------------------------------
# Contract 1.2 — the Tier-0 interaction payload (additive)
# ---------------------------------------------------------------------------

class TestInteractionPayload:
    def test_absent_when_no_edges_supplied(self, doc):
        """Additive: a 1.1-shaped caller (no ``edges``) gets interaction=None,
        so 1.1 consumers are unaffected."""
        assert doc.interaction is None

    def _world_with_specs(self) -> dict:
        w = _world()
        # give the op a spec_ref + eligible set so the payload has substance
        w["operations"][0]["spec_ref"] = "spec-10"
        w["operations"][0]["resource_requirements"] = [
            {"mode": "explicit_set", "resource_refs": ["r-1", "r-2"]}
        ]
        w["resources"].append(
            {"id": "r-2", "snapshot_id": SNAP, "resource_type": "machine",
             "calendar_ref": "cal-1", "pool_refs": []})
        w["demands"][0]["earliest_start"] = "2026-02-01T07:00:00+00:00"
        return w

    def test_built_when_edges_supplied(self):
        w = self._world_with_specs()
        d = assemble_schedule_document(**w, edges=[])
        assert d.interaction is not None
        assert len(d.interaction.operations) == 1
        op = d.interaction.operations[0]
        assert op.operation_ref == "op-1"
        # the WHOLE eligible set, not just the chosen resource
        assert set(op.eligible_resource_ids) == {"r-1", "r-2"}
        assert op.working_min == 600  # 8h + 2h run windows
        assert op.setup_min == 30
        assert op.earliest_start is not None
        # contract 1.3: resumable is a Tier-0 window-fit input (default False)
        assert op.resumable is False

    def test_edges_expand_to_operation_instances(self):
        """Template (spec-keyed) edges resolve to instance ops via
        (workpackage_ref, spec_ref), so refs live in operation-id space."""
        w = self._world_with_specs()
        w["operations"].append(
            {"id": "op-2", "snapshot_id": SNAP, "workpackage_ref": "wp-m",
             "spec_ref": "spec-20", "sequence": 20, "setup_duration": "PT0S",
             "resource_requirements": [
                 {"mode": "explicit_set", "resource_refs": ["r-1"]}]})
        w["assignments"].append(
            {"id": "a-2", "snapshot_id": SNAP, "operation_ref": "op-2",
             "workpackage_ref": "wp-m",
             "resource_assignments": [
                 {"requirement": {"mode": "explicit_set", "resource_refs": ["r-1"]},
                  "resource_ref": "r-1"}],
             "phase_windows": {"setup": None, "run": [
                 {"start": "2026-02-03T09:00:00+00:00",
                  "end": "2026-02-03T11:00:00+00:00"}], "dwell": None}})
        edges = [{"predecessor": "spec-10", "successor": "spec-20",
                  "min_lag": "PT0S", "max_lag": None}]
        d = assemble_schedule_document(**w, edges=edges)
        assert len(d.interaction.precedence_edges) == 1
        e = d.interaction.precedence_edges[0]
        op_ids = {o.operation_ref for o in d.interaction.operations}
        assert e.predecessor_ref == "op-1" and e.successor_ref == "op-2"
        assert e.predecessor_ref in op_ids and e.successor_ref in op_ids

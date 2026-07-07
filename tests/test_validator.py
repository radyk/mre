"""Tests for M3 Validator — derived from docs/03 Phase 1 and sample_data/DEFECTS.md.

The validator runs semantic checks against a canonical snapshot and produces
the go/no-go gate. Tests assert EXACT defects are found, not just "something".
"""
import pytest
from datetime import datetime, timezone
from pathlib import Path

from mre.contracts import (
    Demand, ProvenanceSidecar, SynthesizedProvenance, ProvenanceClass,
    CommitmentClass, DemandStatus, Quantity,
)
from mre.contracts.entities import (
    Calendar, OperationSpec, Process, Product, Resource,
    ResourceRequirement, ResourceRequirementMode, ResourceType,
    ProcessStatus,
)
from mre.contracts.vocabularies import (
    ModuleCode, RunStatus, RecordTier, FindingCode, FindingSeverity, FindingDisposition,
)
from mre.modules.adapter import Adapter
from mre.modules.snapshot_store import SnapshotStore
from mre.modules.validator import Validator, ValidationResult
from mre.reporter import Reporter

SAMPLE_DATA = Path(__file__).parent.parent / "sample_data"
UTC = timezone.utc

_UNIVERSAL = frozenset({"id", "snapshot_id", "external_refs"})


def _synth_prov(entity, snap_id: str) -> list:
    """Create SynthesizedProvenance for every non-universal field of entity."""
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


@pytest.fixture(scope="module")
def validated_run(tmp_path_factory):
    """Run adapter then validator; return (ValidationResult, consolidated_doc)."""
    tmp = tmp_path_factory.mktemp("validator")
    store = SnapshotStore(tmp / "snapshots")
    snap_id = "snap-validator-test"

    adapter_reporter = Reporter.begin(
        module=ModuleCode.M1, purpose="adapter for validator test",
        config={}, trigger="pytest", snapshot_id=snap_id,
        sink_dir=tmp / "runs",
    )
    adapter = Adapter(extract_dir=SAMPLE_DATA, synthesized_generator="sample_data_gen_v1")
    adapter.run(snapshot_id=snap_id, store=store, reporter=adapter_reporter)
    adapter_reporter.end(RunStatus.SUCCESS)

    val_reporter = Reporter.begin(
        module=ModuleCode.M3, purpose="validator unit test",
        config={}, trigger="pytest", snapshot_id=snap_id,
        sink_dir=tmp / "runs",
    )
    validator = Validator()
    val_result = validator.run(
        snapshot_id=snap_id, store=store, reporter=val_reporter,
    )
    val_reporter.end(RunStatus.SUCCESS)
    return val_result, val_reporter.consolidated_doc


class TestSeededDefect3_TemporalImpossibility:
    """WO-PAST-001 ScheduleDate=2025-01-15 is in the past → TEMPORAL_IMPOSSIBILITY."""

    def test_finding_emitted(self, validated_run):
        result, doc = validated_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "TEMPORAL_IMPOSSIBILITY"]
        assert len(findings) >= 1

    def test_disposition_excluded(self, validated_run):
        """TEMPORAL_IMPOSSIBILITY demands are now excluded from planning, not merely flagged."""
        result, doc = validated_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "TEMPORAL_IMPOSSIBILITY"]
        assert all(f["disposition"] == "excluded" for f in findings)

    def test_subjects_not_empty(self, validated_run):
        result, doc = validated_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "TEMPORAL_IMPOSSIBILITY"]
        for f in findings:
            assert f["subjects"], "TEMPORAL_IMPOSSIBILITY must have non-empty subjects"


class TestSeededDefect5_StatisticalOutlier:
    """PROD-007 run_rate=150 min/unit is >10× median for gear family → STATISTICAL_OUTLIER."""

    def test_finding_emitted(self, validated_run):
        result, doc = validated_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "STATISTICAL_OUTLIER"]
        assert len(findings) >= 1

    def test_disposition_proceeded_flagged(self, validated_run):
        result, doc = validated_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "STATISTICAL_OUTLIER"]
        assert all(f["disposition"] == "proceeded_flagged" for f in findings)

    def test_evidence_mentions_family_or_rate(self, validated_run):
        result, doc = validated_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "STATISTICAL_OUTLIER"]
        assert len(findings) >= 1
        ev = findings[0]["evidence"]
        assert "family" in ev or "product_family" in ev or "run_rate" in ev

    def test_subjects_not_empty(self, validated_run):
        result, doc = validated_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "STATISTICAL_OUTLIER"]
        for f in findings:
            assert f["subjects"]


class TestProvenanceSweep:
    def test_no_provenance_gap_on_clean_snapshot(self, validated_run):
        """Snapshot written by adapter (always supplies provenance) → zero PROVENANCE_GAP."""
        result, doc = validated_run
        gaps = [r for r in doc["records"] if r.get("record_type") == "finding"
                and r["code"] == "PROVENANCE_GAP"]
        assert len(gaps) == 0, f"Unexpected PROVENANCE_GAP findings: {gaps}"


class TestGoNoGo:
    def test_go_is_true_when_no_blockers(self, validated_run):
        result, _ = validated_run
        assert result.go is True

    def test_blocker_finding_sets_go_false(self, tmp_path):
        store = SnapshotStore(tmp_path / "snap")
        snap_id = "snap-blocker-test"
        writer = store.begin_snapshot(snap_id)
        writer.finalize()

        val_reporter = Reporter.begin(
            module=ModuleCode.M3, purpose="blocker test",
            config={}, trigger="pytest", snapshot_id=snap_id,
            sink_dir=tmp_path / "runs",
        )
        val_reporter.record_finding(
            code=FindingCode.INFEASIBLE_SUBSET,
            severity=FindingSeverity.BLOCKER,
            subjects=[],
            evidence={"reason": "nothing schedulable"},
            disposition=FindingDisposition.BLOCKED,
            tier=RecordTier.HEADLINE,
        )
        validator = Validator()
        result = validator.run(
            snapshot_id=snap_id, store=store, reporter=val_reporter,
        )
        val_reporter.end(RunStatus.SUCCESS)
        assert result.go is False


class TestLowConfidenceOnDefaulted:
    def test_low_confidence_input_present(self, validated_run):
        """PROD-008 lot size = 0 → adapter emits LOW_CONFIDENCE_INPUT."""
        result, doc = validated_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "LOW_CONFIDENCE_INPUT"]
        assert len(findings) >= 1


class TestValueOutOfRange:
    def test_zero_quantity_flagged(self, tmp_path):
        """Demand with quantity=0 should be flagged VALUE_OUT_OF_RANGE."""
        store = SnapshotStore(tmp_path / "snap")
        snap_id = "snap-vrange-test"
        writer = store.begin_snapshot(snap_id)

        d = Demand(
            id="d-zero-qty", snapshot_id=snap_id,
            product_ref="prod-001",
            quantity=Quantity(value=0.0, uom="EA"),
            due=datetime(2035, 6, 1, tzinfo=UTC),
            commitment_class=CommitmentClass.STANDARD,
            status=DemandStatus.OPEN,
        )
        attrs = ["product_ref", "quantity", "due", "earliest_start",
                 "commitment_class", "customer_weight", "customer_ref", "status"]
        provenance = [
            ProvenanceSidecar(
                entity_id=d.id, attribute_name=a, snapshot_id=snap_id,
                provenance_class=ProvenanceClass.SYNTHESIZED,
                payload=SynthesizedProvenance(generator_id="test"),
            )
            for a in attrs
        ]
        writer.write_entity(d, provenance)
        writer.finalize()

        val_reporter = Reporter.begin(
            module=ModuleCode.M3, purpose="vrange test",
            config={}, trigger="pytest", snapshot_id=snap_id,
            sink_dir=tmp_path / "runs",
        )
        validator = Validator()
        validator.run(snapshot_id=snap_id, store=store, reporter=val_reporter)
        val_reporter.end(RunStatus.SUCCESS)

        findings = [
            r for r in val_reporter.consolidated_doc["records"]
            if r.get("record_type") == "finding"
            and r["code"] == "VALUE_OUT_OF_RANGE"
        ]
        assert len(findings) >= 1


class TestInfeasibleSubset:
    """Pre-solve window-fit check: operation > max shift window → excluded.

    Derived from CLAUDE.md task 2 and the Phase 2 INFEASIBLE debugging session
    (first solve failure converted to a pre-solve validator finding).
    Test scenario: qty=1, run_rate=3000 min >> 720-min shift window.
    """

    @pytest.fixture(scope="class")
    def infeasible_run(self, tmp_path_factory):
        snap_id = "snap-infeasible-test"
        tmp = tmp_path_factory.mktemp("infeasible")
        store = SnapshotStore(tmp / "snapshots")
        writer = store.begin_snapshot(snap_id)

        cal = Calendar(
            id="cal-001", snapshot_id=snap_id,
            base_pattern={
                "weekdays": ["mon", "tue", "wed", "thu", "fri", "sat"],
                "shift_start": "07:00",
                "shift_end": "19:00",
            },
        )
        res = Resource(
            id="res-001", snapshot_id=snap_id,
            resource_type=ResourceType.MACHINE,
            calendar_ref="cal-001",
        )
        opspec = OperationSpec(
            id="spec-001", snapshot_id=snap_id,
            sequence=10,
            run_rate="PT3000M",
            base_setup="PT0S",
            resource_requirements=[
                ResourceRequirement(
                    mode=ResourceRequirementMode.EXPLICIT_SET,
                    resource_refs=["res-001"],
                )
            ],
        )
        proc = Process(
            id="proc-001", snapshot_id=snap_id,
            product_ref="prod-001",
            operation_specs=["spec-001"],
            status=ProcessStatus.ACTIVE,
        )
        prod = Product(
            id="prod-001", snapshot_id=snap_id,
            name="Heavy Part",
            unit_of_measure="EA",
            process_ref="proc-001",
        )
        demand = Demand(
            id="dem-001", snapshot_id=snap_id,
            product_ref="prod-001",
            quantity=Quantity(value=1.0, uom="EA"),
            due=datetime(2035, 1, 1, tzinfo=UTC),
            commitment_class=CommitmentClass.STANDARD,
            status=DemandStatus.OPEN,
        )

        for entity in (cal, res, opspec, proc, prod, demand):
            writer.write_entity(entity, _synth_prov(entity, snap_id))
        writer.finalize()

        rep = Reporter.begin(
            module=ModuleCode.M3, purpose="infeasible subset test",
            config={}, trigger="pytest", snapshot_id=snap_id,
            sink_dir=tmp / "runs",
        )
        result = Validator().run(snapshot_id=snap_id, store=store, reporter=rep)
        rep.end(RunStatus.SUCCESS)
        return result, rep.consolidated_doc

    def test_finding_emitted(self, infeasible_run):
        _, doc = infeasible_run
        codes = [r["code"] for r in doc["records"] if r.get("record_type") == "finding"]
        assert "INFEASIBLE_SUBSET" in codes

    def test_demand_excluded(self, infeasible_run):
        result, _ = infeasible_run
        assert "dem-001" in result.excluded_demand_ids

    def test_gate_remains_go(self, infeasible_run):
        """INFEASIBLE_SUBSET is severity=ERROR (not BLOCKER) so gate stays GO."""
        result, _ = infeasible_run
        assert result.go is True

    def test_evidence_records_duration(self, infeasible_run):
        _, doc = infeasible_run
        findings = [
            r for r in doc["records"]
            if r.get("record_type") == "finding" and r.get("code") == "INFEASIBLE_SUBSET"
        ]
        assert findings
        ev = findings[0].get("evidence", {})
        assert ev.get("estimated_duration_minutes", 0) >= 3000
        assert ev.get("max_window_minutes", 0) <= 720

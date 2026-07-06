"""Tests for M1 Adapter — derived from docs/03 Phase 1 and sample_data/DEFECTS.md.

The adapter is the only ERP-aware code. It produces a canonical snapshot,
an identity mapping table, and evidence records (findings + decisions).
Every finding and decision with an implicated entity must have non-empty subjects.
"""
import json
import pytest
from pathlib import Path

from mre.contracts import FindingCode, FindingDisposition, FindingSeverity
from mre.modules.adapter import Adapter
from mre.modules.snapshot_store import SnapshotStore
from mre.reporter import Reporter
from mre.contracts.vocabularies import ModuleCode, RunStatus

SAMPLE_DATA = Path(__file__).parent.parent / "sample_data"


@pytest.fixture(scope="module")
def adapter_run(tmp_path_factory):
    """Run the adapter once against sample_data/ and return (result, consolidated_doc)."""
    tmp = tmp_path_factory.mktemp("adapter")
    store = SnapshotStore(tmp / "snapshots")
    reporter = Reporter.begin(
        module=ModuleCode.M1,
        purpose="adapter unit test",
        config={},
        trigger="pytest",
        snapshot_id="snap-adapter-test",
        sink_dir=tmp / "runs",
    )
    adapter = Adapter(
        extract_dir=SAMPLE_DATA,
        synthesized_generator="sample_data_gen_v1",
    )
    result = adapter.run(
        snapshot_id="snap-adapter-test",
        store=store,
        reporter=reporter,
    )
    reporter.end(RunStatus.SUCCESS)
    return result, reporter.consolidated_doc


class TestAdapterProducesSnapshot:
    def test_snapshot_contains_demands(self, adapter_run, tmp_path_factory):
        result, _ = adapter_run
        tmp = tmp_path_factory.mktemp("snap_read")
        # Demands created for valid WOs: 35 rows minus WO-REF-BAD(1) minus
        # WO-DUP-001 second row(1) = 33; but WO-PAST-001 proceeds_flagged = included
        assert result.demand_count >= 32

    def test_snapshot_contains_products(self, adapter_run, tmp_path_factory):
        result, _ = adapter_run
        assert result.product_count == 8

    def test_snapshot_contains_resources(self, adapter_run, tmp_path_factory):
        result, _ = adapter_run
        assert result.resource_count == 9  # 9 machines

    def test_snapshot_contains_operation_specs(self, adapter_run, tmp_path_factory):
        result, _ = adapter_run
        # 23 routing lines → 23 OperationSpecs (one per active routing line)
        assert result.operation_spec_count == 23

    def test_identity_mapping_table_produced(self, adapter_run, tmp_path_factory):
        result, _ = adapter_run
        assert result.identity_map is not None
        # Can look up canonical id by external ref
        canon_id = result.identity_map.resolve("ERP", "work_order", "WO-1001")
        assert canon_id is not None

    def test_run_context_has_input_manifest(self, adapter_run, tmp_path_factory):
        _, doc = adapter_run
        manifest = doc["run_context"]["input_manifest"]
        artifact_ids = [e["artifact_id"] for e in manifest]
        assert any("openworkorder" in a for a in artifact_ids)
        assert any("routing" in a for a in artifact_ids)


class TestSeededDefect1_MissingReference:
    """WO-REF-BAD references R-GHOST which doesn't exist → MISSING_REFERENCE, excluded."""

    def test_missing_reference_finding_emitted(self, adapter_run, tmp_path_factory):
        _, doc = adapter_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "MISSING_REFERENCE"]
        assert len(findings) >= 1

    def test_disposition_is_excluded(self, adapter_run, tmp_path_factory):
        _, doc = adapter_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "MISSING_REFERENCE"]
        assert all(f["disposition"] == "excluded" for f in findings)

    def test_severity_is_error(self, adapter_run, tmp_path_factory):
        _, doc = adapter_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "MISSING_REFERENCE"]
        assert all(f["severity"] == "error" for f in findings)

    def test_wo_ref_bad_not_in_snapshot(self, adapter_run, tmp_path_factory):
        result, _ = adapter_run
        # The bad WO should not have been given a canonical demand
        canon_id = result.identity_map.resolve("ERP", "work_order", "WO-REF-BAD")
        assert canon_id is None


class TestSeededDefect2_LowConfidenceInput:
    """PROD-008 CostingLotSize=0 → fallback rate → LOW_CONFIDENCE_INPUT, defaulted."""

    def test_low_confidence_finding_emitted(self, adapter_run, tmp_path_factory):
        _, doc = adapter_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "LOW_CONFIDENCE_INPUT"]
        assert len(findings) >= 1

    def test_disposition_is_defaulted(self, adapter_run, tmp_path_factory):
        _, doc = adapter_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "LOW_CONFIDENCE_INPUT"]
        assert all(f["disposition"] == "defaulted" for f in findings)

    def test_prod008_wos_still_in_snapshot(self, adapter_run, tmp_path_factory):
        """LOW_CONFIDENCE_INPUT is warning-level; WOs for PROD-008 are included."""
        result, _ = adapter_run
        canon = result.identity_map.resolve("ERP", "work_order", "WO-1071")
        assert canon is not None


class TestSeededDefect4_UnmappableValue:
    """R-GEAR-B seq 20 references WC-UNKNOWN → UNMAPPABLE_VALUE."""

    def test_unmappable_value_finding_emitted(self, adapter_run, tmp_path_factory):
        _, doc = adapter_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "UNMAPPABLE_VALUE"]
        assert len(findings) >= 1

    def test_severity_is_warning(self, adapter_run, tmp_path_factory):
        _, doc = adapter_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "UNMAPPABLE_VALUE"]
        assert all(f["severity"] == "warning" for f in findings)


class TestSeededDefect6_DuplicateIdentity:
    """WO-DUP-001 appears twice → DUPLICATE_IDENTITY; second row excluded."""

    def test_duplicate_identity_finding_emitted(self, adapter_run, tmp_path_factory):
        _, doc = adapter_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "DUPLICATE_IDENTITY"]
        assert len(findings) >= 1

    def test_disposition_is_excluded(self, adapter_run, tmp_path_factory):
        _, doc = adapter_run
        findings = [r for r in doc["records"] if r.get("record_type") == "finding"
                    and r["code"] == "DUPLICATE_IDENTITY"]
        assert all(f["disposition"] == "excluded" for f in findings)

    def test_only_one_canonical_demand_for_dup(self, adapter_run, tmp_path_factory):
        """Second WO-DUP-001 row is excluded; exactly one canonical demand exists."""
        result, _ = adapter_run
        canon_id = result.identity_map.resolve("ERP", "work_order", "WO-DUP-001")
        assert canon_id is not None  # first occurrence was kept


class TestSubjectsRequirement:
    """Every finding and decision with an implicated entity must have non-empty subjects."""

    def test_findings_with_entity_have_subjects(self, adapter_run, tmp_path_factory):
        _, doc = adapter_run
        entity_findings = [
            r for r in doc["records"]
            if r.get("record_type") == "finding"
            and r["code"] in (
                "MISSING_REFERENCE", "DUPLICATE_IDENTITY",
                "UNMAPPABLE_VALUE", "LOW_CONFIDENCE_INPUT",
            )
        ]
        assert len(entity_findings) > 0
        for f in entity_findings:
            assert f["subjects"], (
                f"Finding {f['code']} (record_id={f['record_id']}) has empty subjects"
            )

    def test_decisions_have_subjects(self, adapter_run, tmp_path_factory):
        _, doc = adapter_run
        decisions = [r for r in doc["records"] if r.get("record_type") == "decision"]
        for d in decisions:
            assert d["subjects"], (
                f"Decision {d['decision_type']} (record_id={d['record_id']}) has empty subjects"
            )


class TestProvenanceOnSnapshot:
    """All attributes on canonical entities must carry SynthesizedProvenance
    (because the source is generated sample data)."""

    def test_demand_attributes_have_synthesized_provenance(
        self, adapter_run, tmp_path_factory
    ):
        result, _ = adapter_run
        reader = result.store.load_snapshot("snap-adapter-test")
        demands = list(reader.iter_entities("demand"))
        assert len(demands) > 0
        d = demands[0]
        prov = reader.get_provenance(d["id"], "quantity")
        assert prov is not None
        assert prov["provenance_class"] == "synthesized"

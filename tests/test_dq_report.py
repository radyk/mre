"""Tests for the DQ report — derived from docs/03 Phase 1 milestone.

The report must be generated ENTIRELY from the evidence store, never from
raw extracts. It renders affected entities in planner vocabulary via external refs.
"""
import pytest
from pathlib import Path

from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.modules.adapter import Adapter
from mre.modules.snapshot_store import SnapshotStore
from mre.modules.validator import Validator
from mre.modules.dq_report import generate_dq_report
from mre.reporter import Reporter

SAMPLE_DATA = Path(__file__).parent.parent / "sample_data"


@pytest.fixture(scope="module")
def dq_report_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("dqreport")
    store = SnapshotStore(tmp / "snapshots")
    snap_id = "snap-dqreport-test"
    runs_dir = tmp / "runs"

    adapter_reporter = Reporter.begin(
        module=ModuleCode.M1, purpose="adapter for dq report test",
        config={}, trigger="pytest", snapshot_id=snap_id, sink_dir=runs_dir,
    )
    adapter = Adapter(extract_dir=SAMPLE_DATA, synthesized_generator="sample_data_gen_v1")
    adapter_result = adapter.run(snapshot_id=snap_id, store=store, reporter=adapter_reporter)
    adapter_reporter.end(RunStatus.SUCCESS)

    val_reporter = Reporter.begin(
        module=ModuleCode.M3, purpose="validator for dq report test",
        config={}, trigger="pytest", snapshot_id=snap_id, sink_dir=runs_dir,
    )
    validator = Validator()
    # sample_data's seeded PROD-007 outlier is 45x median, designed against the
    # original 10x threshold (see tests/test_validator.py's validated_run fixture).
    validator.run(snapshot_id=snap_id, store=store, reporter=val_reporter,
                  outlier_threshold_ratio=10.0)
    val_reporter.end(RunStatus.SUCCESS)

    report_path = tmp / "dq_report.md"
    generate_dq_report(
        adapter_doc=adapter_reporter.consolidated_doc,
        validator_doc=val_reporter.consolidated_doc,
        identity_map=adapter_result.identity_map,
        output_path=report_path,
    )
    report_text = report_path.read_text(encoding="utf-8")
    return report_text, report_path


class TestReportStructure:
    def test_report_file_exists(self, dq_report_run):
        _, path = dq_report_run
        assert path.exists()

    def test_report_is_markdown(self, dq_report_run):
        text, _ = dq_report_run
        assert "#" in text  # at least one markdown heading

    def test_report_has_findings_section(self, dq_report_run):
        text, _ = dq_report_run
        assert "finding" in text.lower() or "Finding" in text


class TestReportCoversAllSeededDefects:
    def test_missing_reference_mentioned(self, dq_report_run):
        text, _ = dq_report_run
        assert "MISSING_REFERENCE" in text

    def test_duplicate_identity_mentioned(self, dq_report_run):
        text, _ = dq_report_run
        assert "DUPLICATE_IDENTITY" in text

    def test_unmappable_value_mentioned(self, dq_report_run):
        text, _ = dq_report_run
        assert "UNMAPPABLE_VALUE" in text

    def test_low_confidence_mentioned(self, dq_report_run):
        text, _ = dq_report_run
        assert "LOW_CONFIDENCE_INPUT" in text

    def test_temporal_impossibility_mentioned(self, dq_report_run):
        text, _ = dq_report_run
        assert "TEMPORAL_IMPOSSIBILITY" in text

    def test_statistical_outlier_mentioned(self, dq_report_run):
        text, _ = dq_report_run
        assert "STATISTICAL_OUTLIER" in text


class TestReportContent:
    def test_severities_shown(self, dq_report_run):
        text, _ = dq_report_run
        # At least one severity label appears
        assert any(s in text for s in ("error", "warning", "info", "blocker"))

    def test_disposition_shown(self, dq_report_run):
        text, _ = dq_report_run
        assert any(d in text for d in ("excluded", "defaulted", "proceeded_flagged"))

    def test_planner_vocabulary_used(self, dq_report_run):
        """Report renders entities using ERP identifiers (from external_refs),
        not internal UUIDs."""
        text, _ = dq_report_run
        # ERP work order numbers should appear, not raw UUIDs
        assert "WO-REF-BAD" in text or "WO-DUP-001" in text

    def test_provenance_stats_present(self, dq_report_run):
        text, _ = dq_report_run
        # Report must include provenance composition statistics
        assert "synthesized" in text.lower() or "provenance" in text.lower()

    def test_report_from_evidence_not_raw_extracts(self, dq_report_run, tmp_path):
        """generate_dq_report must accept consolidated docs, not CSV paths."""
        import inspect
        from mre.modules import dq_report as dq_mod
        sig = inspect.signature(dq_mod.generate_dq_report)
        params = list(sig.parameters.keys())
        # Function signature should take adapter_doc and validator_doc,
        # not extract_dir or csv_path
        assert "adapter_doc" in params
        assert "validator_doc" in params
        assert "extract_dir" not in params
        assert "csv" not in " ".join(params)


class TestGoNoGoSummary:
    def test_go_nogo_result_in_report(self, dq_report_run):
        text, _ = dq_report_run
        assert "go" in text.lower() or "gate" in text.lower() or "proceed" in text.lower()

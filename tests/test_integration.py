"""Integration tests: full pipeline against sample_data/.

Asserts that all 6 seeded defects are found with exact codes and dispositions,
the go/no-go gate returns True, and a DQ report file is produced.
"""
import json
import subprocess
import sys
import pytest
from pathlib import Path

SAMPLE_DATA = Path(__file__).parent.parent / "sample_data"
REPO_ROOT = Path(__file__).parent.parent


class TestAllSixDefectsFound:
    """Run the full adapter+validator pipeline and verify all seeded defects."""

    @pytest.fixture(scope="class")
    def pipeline_run(self, tmp_path_factory):
        from mre.contracts.vocabularies import ModuleCode, RunStatus
        from mre.modules.adapter import Adapter
        from mre.modules.snapshot_store import SnapshotStore
        from mre.modules.validator import Validator
        from mre.reporter import Reporter

        tmp = tmp_path_factory.mktemp("integration")
        store = SnapshotStore(tmp / "snapshots")
        snap_id = "snap-integration"
        runs_dir = tmp / "runs"

        # M1
        a_rep = Reporter.begin(
            module=ModuleCode.M1, purpose="integration adapter",
            config={}, trigger="pytest", snapshot_id=snap_id, sink_dir=runs_dir,
        )
        adapter = Adapter(extract_dir=SAMPLE_DATA, synthesized_generator="sample_data_gen_v1")
        a_result = adapter.run(snapshot_id=snap_id, store=store, reporter=a_rep)
        a_rep.end(RunStatus.SUCCESS)

        # M3
        v_rep = Reporter.begin(
            module=ModuleCode.M3, purpose="integration validator",
            config={}, trigger="pytest", snapshot_id=snap_id, sink_dir=runs_dir,
        )
        validator = Validator()
        v_result = validator.run(snapshot_id=snap_id, store=store, reporter=v_rep)
        v_rep.end(RunStatus.SUCCESS)

        all_findings = (
            [r for r in a_rep.consolidated_doc["records"] if r["record_type"] == "finding"]
            + [r for r in v_rep.consolidated_doc["records"] if r["record_type"] == "finding"]
        )
        return {
            "adapter_doc": a_rep.consolidated_doc,
            "validator_doc": v_rep.consolidated_doc,
            "all_findings": all_findings,
            "adapter_result": a_result,
            "validator_result": v_result,
        }

    def _findings_by_code(self, pipeline_run, code: str) -> list:
        return [f for f in pipeline_run["all_findings"] if f["code"] == code]

    def test_defect1_missing_reference(self, pipeline_run):
        found = self._findings_by_code(pipeline_run, "MISSING_REFERENCE")
        assert len(found) >= 1
        assert all(f["disposition"] == "excluded" for f in found)

    def test_defect2_low_confidence_input(self, pipeline_run):
        found = self._findings_by_code(pipeline_run, "LOW_CONFIDENCE_INPUT")
        assert len(found) >= 1
        # At least one finding for defect 2 (zero lot size) has disposition=defaulted
        assert any(f["disposition"] == "defaulted" for f in found)

    def test_defect3_temporal_impossibility(self, pipeline_run):
        found = self._findings_by_code(pipeline_run, "TEMPORAL_IMPOSSIBILITY")
        assert len(found) >= 1
        assert all(f["disposition"] == "proceeded_flagged" for f in found)

    def test_defect4_unmappable_value(self, pipeline_run):
        found = self._findings_by_code(pipeline_run, "UNMAPPABLE_VALUE")
        assert len(found) >= 1

    def test_defect5_statistical_outlier(self, pipeline_run):
        found = self._findings_by_code(pipeline_run, "STATISTICAL_OUTLIER")
        assert len(found) >= 1
        assert all(f["disposition"] == "proceeded_flagged" for f in found)

    def test_defect6_duplicate_identity(self, pipeline_run):
        found = self._findings_by_code(pipeline_run, "DUPLICATE_IDENTITY")
        assert len(found) >= 1
        assert all(f["disposition"] == "excluded" for f in found)

    def test_go_nogo_is_true(self, pipeline_run):
        assert pipeline_run["validator_result"].go is True

    def test_no_blocker_findings(self, pipeline_run):
        blockers = [f for f in pipeline_run["all_findings"] if f["severity"] == "blocker"]
        assert len(blockers) == 0

    def test_all_findings_have_snapshot_id(self, pipeline_run):
        for f in pipeline_run["all_findings"]:
            assert f.get("snapshot_id") == "snap-integration"

    def test_adapter_run_context_complete(self, pipeline_run):
        ctx = pipeline_run["adapter_doc"]["run_context"]
        assert ctx["status"] == "success"
        assert ctx.get("ended_at") is not None

    def test_validator_run_context_complete(self, pipeline_run):
        ctx = pipeline_run["validator_doc"]["run_context"]
        assert ctx["status"] == "success"


class TestMainEntrypoint:
    def test_python_m_mre_runs_successfully(self, tmp_path):
        """python -m mre runs the pipeline and exits 0."""
        result = subprocess.run(
            [sys.executable, "-m", "mre",
             "--sample-data", str(SAMPLE_DATA),
             "--out", str(tmp_path)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, (
            f"mre entrypoint failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    def test_entrypoint_prints_report_path(self, tmp_path):
        result = subprocess.run(
            [sys.executable, "-m", "mre",
             "--sample-data", str(SAMPLE_DATA),
             "--out", str(tmp_path)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert "report" in result.stdout.lower() or "dq_report" in result.stdout.lower()

    def test_entrypoint_produces_report_file(self, tmp_path):
        subprocess.run(
            [sys.executable, "-m", "mre",
             "--sample-data", str(SAMPLE_DATA),
             "--out", str(tmp_path)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        report_files = list(tmp_path.rglob("*.md"))
        assert len(report_files) >= 1

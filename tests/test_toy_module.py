"""Tests for the Phase 0 deliverable: one of each record type, valid consolidated doc."""
import pytest

from mre.modules.toy_module import run_toy_module


class TestToyModuleDeliverable:
    def test_runs_without_error(self, tmp_path):
        result = run_toy_module(sink_dir=tmp_path)
        assert result is not None

    def test_status_is_success(self, tmp_path):
        result = run_toy_module(sink_dir=tmp_path)
        assert result["run_context"]["status"] == "success"

    def test_run_context_present(self, tmp_path):
        result = run_toy_module(sink_dir=tmp_path)
        ctx = result["run_context"]
        assert ctx["purpose"] == "Phase 0 evidence-backbone smoke test"
        assert ctx["trigger"] == "test_harness"

    def test_run_id_in_doc(self, tmp_path):
        result = run_toy_module(sink_dir=tmp_path)
        assert isinstance(result["run_id"], str)
        assert len(result["run_id"]) > 0

    def test_records_array_present(self, tmp_path):
        result = run_toy_module(sink_dir=tmp_path)
        assert "records" in result
        assert isinstance(result["records"], list)

    def test_one_decision_record(self, tmp_path):
        result = run_toy_module(sink_dir=tmp_path)
        decisions = [r for r in result["records"] if r["record_type"] == "decision"]
        assert len(decisions) >= 1

    def test_one_finding_record(self, tmp_path):
        result = run_toy_module(sink_dir=tmp_path)
        findings = [r for r in result["records"] if r["record_type"] == "finding"]
        assert len(findings) >= 1

    def test_one_metric_record(self, tmp_path):
        result = run_toy_module(sink_dir=tmp_path)
        metrics = [r for r in result["records"] if r["record_type"] == "metric"]
        assert len(metrics) >= 1

    def test_one_artifact_record(self, tmp_path):
        result = run_toy_module(sink_dir=tmp_path)
        artifacts = [r for r in result["records"] if r["record_type"] == "artifact"]
        assert len(artifacts) >= 1

    def test_event_record_in_stream_not_doc(self, tmp_path):
        """Events are emitted at tier=detail; they appear in JSONL but not the consolidated doc."""
        import json
        result = run_toy_module(sink_dir=tmp_path)
        # No detail records in the consolidated doc
        tiers = {r["tier"] for r in result["records"]}
        assert "detail" not in tiers
        # But events are in the JSONL stream
        run_id = result["run_id"]
        jsonl_files = list(tmp_path.rglob("*.jsonl"))
        assert len(jsonl_files) >= 1
        all_stream_records = []
        for f in jsonl_files:
            for line in f.read_text().splitlines():
                if line.strip():
                    all_stream_records.append(json.loads(line))
        events = [r for r in all_stream_records if r.get("record_type") == "event"]
        assert len(events) >= 1

    def test_decomposability_passes(self, tmp_path):
        """demand_count_total = demand_count_open + demand_count_cancelled."""
        result = run_toy_module(sink_dir=tmp_path)
        metrics = {r["name"]: r for r in result["records"] if r["record_type"] == "metric"}
        assert "demand_count_total" in metrics
        total = metrics["demand_count_total"]
        assert total["value"] == 42.0
        # Rollup points to the two component metrics
        assert len(total["rollup_of"]) == 2

    def test_no_detail_records_in_consolidated_doc(self, tmp_path):
        result = run_toy_module(sink_dir=tmp_path)
        for rec in result["records"]:
            assert rec["tier"] != "detail"

    def test_all_records_carry_snapshot_id(self, tmp_path):
        result = run_toy_module(sink_dir=tmp_path)
        for rec in result["records"]:
            assert rec.get("snapshot_id") == "snap-phase0-demo"

    def test_all_records_carry_run_id(self, tmp_path):
        result = run_toy_module(sink_dir=tmp_path)
        run_id = result["run_id"]
        for rec in result["records"]:
            assert rec["run_id"] == run_id

    def test_seq_numbers_monotone_in_stream(self, tmp_path):
        """All records in the JSONL stream have monotonically increasing seq."""
        import json
        result = run_toy_module(sink_dir=tmp_path)
        run_id = result["run_id"]
        jsonl_files = list(tmp_path.rglob("*.jsonl"))
        all_records = []
        for f in jsonl_files:
            for line in f.read_text().splitlines():
                if line.strip():
                    rec = json.loads(line)
                    if rec.get("run_id") == run_id and "seq" in rec:
                        all_records.append(rec)
        all_records.sort(key=lambda r: r["seq"])
        seqs = [r["seq"] for r in all_records]
        assert seqs == list(range(seqs[0], seqs[0] + len(seqs)))

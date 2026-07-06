"""Tests derived from docs/02 §6: Reporter verb behavior and ambient capture."""
import pytest
from datetime import datetime, timezone

from mre.contracts.vocabularies import (
    DecisionBasis, DecisionType, DriverCode, FindingCode,
    FindingDisposition, FindingSeverity, ModuleCode, RecordTier, RunStatus,
)
from mre.contracts.records import DecisionAlternative
from mre.reporter import Reporter

UTC = timezone.utc
SNAP = "snap-test"


def make_reporter(tmp_path, **kwargs) -> Reporter:
    defaults = dict(
        module=ModuleCode.M1,
        purpose="unit test",
        config={"test": True},
        trigger="pytest",
        snapshot_id=SNAP,
        sink_dir=tmp_path,
    )
    return Reporter.begin(**(defaults | kwargs))


class TestBegin:
    def test_mints_unique_run_id(self, tmp_path):
        r1 = make_reporter(tmp_path / "r1")
        r2 = make_reporter(tmp_path / "r2")
        assert r1.run_id != r2.run_id

    def test_run_id_is_nonempty_string(self, tmp_path):
        r = make_reporter(tmp_path)
        assert isinstance(r.run_id, str)
        assert len(r.run_id) > 0

    def test_captures_config_hash(self, tmp_path):
        r = make_reporter(tmp_path, config={"solver_limit": 60})
        assert isinstance(r.config_hash, str)
        assert len(r.config_hash) == 64  # SHA-256 hex

    def test_same_config_same_hash(self, tmp_path):
        r1 = make_reporter(tmp_path / "r1", config={"a": 1})
        r2 = make_reporter(tmp_path / "r2", config={"a": 1})
        assert r1.config_hash == r2.config_hash

    def test_different_config_different_hash(self, tmp_path):
        r1 = make_reporter(tmp_path / "r1", config={"a": 1})
        r2 = make_reporter(tmp_path / "r2", config={"a": 2})
        assert r1.config_hash != r2.config_hash

    def test_captures_started_at(self, tmp_path):
        before = datetime.now(UTC)
        r = make_reporter(tmp_path)
        after = datetime.now(UTC)
        assert before <= r.started_at <= after

    def test_writes_open_record_to_jsonl(self, tmp_path):
        r = make_reporter(tmp_path)
        r.end(RunStatus.SUCCESS)
        lines = (tmp_path / f"{r.run_id}.jsonl").read_text().splitlines()
        import json
        records = [json.loads(l) for l in lines if l.strip()]
        open_recs = [rec for rec in records if rec.get("record_type") == "run_context_open"]
        assert len(open_recs) == 1


class TestSeqIncrement:
    def test_seq_increments_monotonically(self, tmp_path):
        r = make_reporter(tmp_path)
        e1 = r.record_event("first")
        e2 = r.record_event("second")
        e3 = r.record_event("third")
        assert e2.seq == e1.seq + 1
        assert e3.seq == e2.seq + 1

    def test_seq_starts_at_1(self, tmp_path):
        r = make_reporter(tmp_path)
        e = r.record_event("first event")
        assert e.seq == 1

    def test_seq_is_unique_per_record(self, tmp_path):
        r = make_reporter(tmp_path)
        records = [r.record_event(f"event {i}") for i in range(5)]
        seqs = [rec.seq for rec in records]
        assert len(set(seqs)) == 5


class TestRecordDecision:
    def test_valid_decision_emitted(self, tmp_path):
        r = make_reporter(tmp_path)
        d = r.record_decision(
            decision_type=DecisionType.INTERPRETATION,
            subjects=[],
            chosen="keep",
            alternatives=[],
            driver=DriverCode.POLICY_RULE,
            basis=DecisionBasis.POLICY_APPLIED,
        )
        assert d.record_id is not None
        assert d.run_id == r.run_id

    def test_invalid_driver_raises_at_verb(self, tmp_path):
        r = make_reporter(tmp_path)
        with pytest.raises(Exception):
            r.record_decision(
                decision_type=DecisionType.INTERPRETATION,
                subjects=[],
                chosen="x",
                alternatives=[],
                driver="TOTALLY_INVALID",
                basis=DecisionBasis.OBSERVED,
            )

    def test_invalid_basis_raises_at_verb(self, tmp_path):
        r = make_reporter(tmp_path)
        with pytest.raises(Exception):
            r.record_decision(
                decision_type=DecisionType.INTERPRETATION,
                subjects=[],
                chosen="x",
                alternatives=[],
                driver=DriverCode.POLICY_RULE,
                basis="made_up_basis",
            )

    def test_decision_record_id_in_run(self, tmp_path):
        r = make_reporter(tmp_path)
        d = r.record_decision(
            decision_type=DecisionType.ASSIGNMENT,
            subjects=[],
            chosen="CNC-1",
            alternatives=[],
            driver=DriverCode.CAPACITY_BLOCKED,
            basis=DecisionBasis.RECONSTRUCTED,
        )
        r.end(RunStatus.SUCCESS)
        record_ids = [rec["record_id"] for rec in r.consolidated_doc["records"]]
        assert d.record_id in record_ids


class TestRecordFinding:
    def test_valid_finding_emitted(self, tmp_path):
        r = make_reporter(tmp_path)
        f = r.record_finding(
            code=FindingCode.MISSING_REFERENCE,
            severity=FindingSeverity.ERROR,
            subjects=[],
            evidence={"ref": "R-001"},
            disposition=FindingDisposition.EXCLUDED,
        )
        assert f.record_id is not None

    def test_invalid_code_raises_at_verb(self, tmp_path):
        r = make_reporter(tmp_path)
        with pytest.raises(Exception):
            r.record_finding(
                code="NOT_A_CODE",
                severity=FindingSeverity.ERROR,
                subjects=[],
                evidence={},
                disposition=FindingDisposition.EXCLUDED,
            )


class TestContextManager:
    def test_ends_run_on_normal_exit(self, tmp_path):
        with make_reporter(tmp_path) as r:
            r.record_event("hello")
        assert r.run_status == RunStatus.SUCCESS
        assert r.ended_at is not None

    def test_captures_exception_info(self, tmp_path):
        with pytest.raises(ValueError):
            with make_reporter(tmp_path) as r:
                raise ValueError("test error")
        assert r.exception_info is not None
        assert r.exception_info["type"] == "ValueError"
        assert "test error" in r.exception_info["message"]

    def test_run_status_failure_on_exception(self, tmp_path):
        with pytest.raises(RuntimeError):
            with make_reporter(tmp_path) as r:
                raise RuntimeError("boom")
        assert r.run_status == RunStatus.FAILURE

    def test_exception_propagates(self, tmp_path):
        with pytest.raises(ValueError):
            with make_reporter(tmp_path):
                raise ValueError("should propagate")

    def test_consolidated_doc_produced_even_after_exception(self, tmp_path):
        with pytest.raises(ValueError):
            with make_reporter(tmp_path) as r:
                r.record_event("before crash")
                raise ValueError("crash")
        assert r.consolidated_doc is not None


class TestEnd:
    def test_captures_ended_at(self, tmp_path):
        before = datetime.now(UTC)
        r = make_reporter(tmp_path)
        r.end(RunStatus.SUCCESS)
        after = datetime.now(UTC)
        assert before <= r.ended_at <= after

    def test_duration_is_positive(self, tmp_path):
        r = make_reporter(tmp_path)
        r.record_event("something")
        r.end(RunStatus.SUCCESS)
        import json
        lines = (tmp_path / f"{r.run_id}.jsonl").read_text().splitlines()
        close_recs = [
            json.loads(l) for l in lines
            if l.strip() and json.loads(l).get("record_type") == "run_context_close"
        ]
        assert close_recs[0]["duration_seconds"] >= 0

    def test_run_status_recorded(self, tmp_path):
        r = make_reporter(tmp_path)
        r.end(RunStatus.PARTIAL)
        assert r.run_status == RunStatus.PARTIAL

    def test_consolidated_doc_produced(self, tmp_path):
        r = make_reporter(tmp_path)
        r.end(RunStatus.SUCCESS)
        assert r.consolidated_doc is not None
        assert "run_id" in r.consolidated_doc
        assert "run_context" in r.consolidated_doc
        assert "records" in r.consolidated_doc


class TestRegisterInput:
    def test_input_artifact_in_manifest(self, tmp_path):
        r = make_reporter(tmp_path)
        r.register_input("extract.csv", artifact_hash="abc")
        r.end(RunStatus.SUCCESS)
        manifest = r.consolidated_doc["run_context"]["input_manifest"]
        assert any(e["artifact_id"] == "extract.csv" for e in manifest)

    def test_input_artifact_record_written(self, tmp_path):
        r = make_reporter(tmp_path)
        r.register_input("extract.csv")
        r.end(RunStatus.SUCCESS)
        records = r.consolidated_doc["records"]
        artifacts = [rec for rec in records if rec.get("record_type") == "artifact"]
        assert any(a["artifact_ref"] == "extract.csv" for a in artifacts)


class TestRegisterOutput:
    def test_output_artifact_in_manifest(self, tmp_path):
        r = make_reporter(tmp_path)
        r.register_output("result.json", artifact_hash="def")
        r.end(RunStatus.SUCCESS)
        manifest = r.consolidated_doc["run_context"]["output_manifest"]
        assert any(e["artifact_id"] == "result.json" for e in manifest)

"""Tests derived from docs/02 §7: JSONL sink crash-safety and format correctness."""
import json
import pytest

from mre.contracts.vocabularies import ModuleCode, RecordTier, RunStatus
from mre.reporter import Reporter

SNAP = "snap-sink-test"


def make_reporter(tmp_path) -> Reporter:
    return Reporter.begin(
        module=ModuleCode.M1,
        purpose="sink test",
        config={},
        trigger="pytest",
        snapshot_id=SNAP,
        sink_dir=tmp_path,
    )


class TestJsonlFormat:
    def test_each_line_is_valid_json(self, tmp_path):
        r = make_reporter(tmp_path)
        r.record_event("event one")
        r.record_event("event two")
        r.end(RunStatus.SUCCESS)
        lines = (tmp_path / f"{r.run_id}.jsonl").read_text().splitlines()
        assert len(lines) >= 2
        for line in lines:
            if line.strip():
                json.loads(line)  # must not raise

    def test_each_record_is_on_one_line(self, tmp_path):
        r = make_reporter(tmp_path)
        r.record_event("single line event", payload={"nested": {"a": 1}})
        r.end(RunStatus.SUCCESS)
        lines = (tmp_path / f"{r.run_id}.jsonl").read_text().splitlines()
        for line in lines:
            if line.strip():
                parsed = json.loads(line)
                assert isinstance(parsed, dict)

    def test_records_have_record_type_field(self, tmp_path):
        r = make_reporter(tmp_path)
        r.record_event("test")
        r.end(RunStatus.SUCCESS)
        lines = (tmp_path / f"{r.run_id}.jsonl").read_text().splitlines()
        records = [json.loads(l) for l in lines if l.strip()]
        for rec in records:
            assert "record_type" in rec

    def test_records_have_run_id(self, tmp_path):
        r = make_reporter(tmp_path)
        r.record_event("test")
        r.end(RunStatus.SUCCESS)
        lines = (tmp_path / f"{r.run_id}.jsonl").read_text().splitlines()
        records = [json.loads(l) for l in lines if l.strip()]
        for rec in records:
            assert rec.get("run_id") == r.run_id


class TestCrashSafety:
    def test_records_survive_without_end(self, tmp_path):
        """Crash-safe: records written before a crash are preserved in JSONL."""
        r = make_reporter(tmp_path)
        r.record_event("before crash", payload={"n": 1})
        r.record_event("also before crash", payload={"n": 2})
        # Simulate crash: do NOT call end()
        # The JSONL file should still be readable
        jsonl_path = tmp_path / f"{r.run_id}.jsonl"
        assert jsonl_path.exists()
        lines = jsonl_path.read_text().splitlines()
        readable = [json.loads(l) for l in lines if l.strip()]
        assert len(readable) >= 2  # at least open + 2 events

    def test_events_before_crash_are_parseable(self, tmp_path):
        r = make_reporter(tmp_path)
        for i in range(5):
            r.record_event(f"event {i}", payload={"index": i})
        # No end() — simulate crash
        lines = (tmp_path / f"{r.run_id}.jsonl").read_text().splitlines()
        records = [json.loads(l) for l in lines if l.strip()]
        events = [rec for rec in records if rec.get("record_type") == "event"]
        assert len(events) == 5

    def test_seq_numbers_recoverable_from_stream(self, tmp_path):
        r = make_reporter(tmp_path)
        for i in range(3):
            r.record_event(f"event {i}")
        # No end()
        lines = (tmp_path / f"{r.run_id}.jsonl").read_text().splitlines()
        records = [json.loads(l) for l in lines if l.strip()]
        events = [rec for rec in records if rec.get("record_type") == "event"]
        seqs = [e["seq"] for e in events]
        assert seqs == sorted(seqs)  # monotonically increasing

    def test_file_named_by_run_id(self, tmp_path):
        r = make_reporter(tmp_path)
        r.end(RunStatus.SUCCESS)
        expected_path = tmp_path / f"{r.run_id}.jsonl"
        assert expected_path.exists()


class TestMultipleRunsSeparateFiles:
    def test_two_runs_produce_two_files(self, tmp_path):
        r1 = make_reporter(tmp_path / "r1")
        r1.end(RunStatus.SUCCESS)
        r2 = make_reporter(tmp_path / "r2")
        r2.end(RunStatus.SUCCESS)
        assert (tmp_path / "r1" / f"{r1.run_id}.jsonl").exists()
        assert (tmp_path / "r2" / f"{r2.run_id}.jsonl").exists()
        assert r1.run_id != r2.run_id

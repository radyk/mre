"""Tests for M9 EvidenceIndex — derived from docs/02 §2 (L4 Index).

Covers:
- Build from JSONL streams
- entity_records / finding_occurrences primitives
- lineage_walk (direct + transitive demand chain)
- JSON persistence round-trip
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mre.modules.evidence_index import EvidenceIndex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _ctx_open(run_id: str, module: str, snap: str = "snap-test") -> dict:
    return {
        "record_type": "run_context_open",
        "run_id": run_id,
        "module": module,
        "snapshot_id": snap,
        "purpose": "test",
        "timestamp": "2026-07-06T00:00:00Z",
    }


def _ctx_close(run_id: str, status: str = "success") -> dict:
    return {
        "record_type": "run_context_close",
        "run_id": run_id,
        "status": status,
        "ended_at": "2026-07-06T00:01:00Z",
    }


def _decision(record_id: str, run_id: str, module: str, entity_id: str,
              entity_type: str = "demand", driver: str = "SETUP_AMORTIZATION",
              decision_type: str = "demand_merge", seq: int = 1) -> dict:
    return {
        "record_type": "decision",
        "record_id": record_id,
        "run_id": run_id,
        "module": module,
        "seq": seq,
        "snapshot_id": "snap-test",
        "subjects": [{"entity_id": entity_id, "entity_type": entity_type}],
        "tier": "headline",
        "message": "",
        "decision_type": decision_type,
        "driver": driver,
        "basis": "policy_applied",
        "chosen": {},
        "alternatives": [],
    }


def _finding(record_id: str, run_id: str, module: str, entity_id: str,
             code: str = "STATISTICAL_OUTLIER", severity: str = "warning",
             seq: int = 2) -> dict:
    return {
        "record_type": "finding",
        "record_id": record_id,
        "run_id": run_id,
        "module": module,
        "seq": seq,
        "snapshot_id": "snap-test",
        "subjects": [{"entity_id": entity_id, "entity_type": "product"}],
        "tier": "supporting",
        "message": "outlier",
        "code": code,
        "severity": severity,
        "disposition": "flagged",
        "disposition_detail": "high run rate",
    }


def _metric(record_id: str, run_id: str, module: str, entity_id: str,
            name: str = "lateness_minutes", value: float = 840.0,
            seq: int = 3) -> dict:
    return {
        "record_type": "metric",
        "record_id": record_id,
        "run_id": run_id,
        "module": module,
        "seq": seq,
        "snapshot_id": "snap-test",
        "subjects": [{"entity_id": entity_id, "entity_type": "demand"}],
        "tier": "supporting",
        "message": "",
        "name": name,
        "value": value,
        "unit": "minutes",
        "rollup_of": [],
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def runs_dir_simple(tmp_path) -> Path:
    """Two JSONL files: M4 with a DEMAND_MERGE decision; M7 with a metric."""
    d_id = "demand-aaa-111"
    _write_jsonl(tmp_path / "m4-run.jsonl", [
        _ctx_open("run-m4", "M4"),
        _decision("dec-001", "run-m4", "M4", d_id),
        _ctx_close("run-m4"),
    ])
    _write_jsonl(tmp_path / "m7-run.jsonl", [
        _ctx_open("run-m7", "M7"),
        _metric("met-001", "run-m7", "M7", d_id),
        _ctx_close("run-m7"),
    ])
    return tmp_path


@pytest.fixture()
def index_simple(runs_dir_simple) -> EvidenceIndex:
    return EvidenceIndex().build(runs_dir_simple)


# ---------------------------------------------------------------------------
# Build tests
# ---------------------------------------------------------------------------

class TestBuild:
    def test_build_returns_self(self, runs_dir_simple):
        idx = EvidenceIndex()
        result = idx.build(runs_dir_simple)
        assert result is idx

    def test_evidence_count(self, index_simple):
        """Two evidence records (decision + metric) loaded."""
        assert len(index_simple._all_evidence) == 2

    def test_run_registry_populated(self, index_simple):
        runs = index_simple.runs()
        run_ids = {r["run_id"] for r in runs}
        assert "run-m4" in run_ids
        assert "run-m7" in run_ids

    def test_run_registry_has_status(self, index_simple):
        runs = {r["run_id"]: r for r in index_simple.runs()}
        assert runs["run-m4"]["status"] == "success"
        assert runs["run-m7"]["module"] == "M7"

    def test_build_empty_dir(self, tmp_path):
        idx = EvidenceIndex().build(tmp_path)
        assert len(idx._all_evidence) == 0
        assert len(idx.runs()) == 0


# ---------------------------------------------------------------------------
# entity_records
# ---------------------------------------------------------------------------

class TestEntityRecords:
    def test_finds_decision(self, index_simple):
        recs = index_simple.entity_records("demand-aaa-111")
        assert any(r["record_type"] == "decision" for r in recs)

    def test_finds_metric(self, index_simple):
        recs = index_simple.entity_records("demand-aaa-111")
        assert any(r["record_type"] == "metric" for r in recs)

    def test_unknown_entity_returns_empty(self, index_simple):
        assert index_simple.entity_records("no-such-id") == []

    def test_no_duplicate_records(self, index_simple):
        recs = index_simple.entity_records("demand-aaa-111")
        ids = [r["record_id"] for r in recs]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# finding_occurrences
# ---------------------------------------------------------------------------

class TestFindingOccurrences:
    def test_empty_when_no_findings(self, index_simple):
        assert index_simple.finding_occurrences("STATISTICAL_OUTLIER") == []

    def test_finds_by_code(self, tmp_path):
        _write_jsonl(tmp_path / "m3.jsonl", [
            _ctx_open("run-m3", "M3"),
            _finding("find-001", "run-m3", "M3", "prod-001"),
            _finding("find-002", "run-m3", "M3", "prod-002"),
            _finding("find-003", "run-m3", "M3", "prod-003", code="LOW_CONFIDENCE_INPUT"),
            _ctx_close("run-m3"),
        ])
        idx = EvidenceIndex().build(tmp_path)
        results = idx.finding_occurrences("STATISTICAL_OUTLIER")
        assert len(results) == 2
        assert all(r["code"] == "STATISTICAL_OUTLIER" for r in results)

    def test_unknown_code_returns_empty(self, index_simple):
        assert index_simple.finding_occurrences("NONEXISTENT_CODE") == []


# ---------------------------------------------------------------------------
# lineage_walk
# ---------------------------------------------------------------------------

class TestLineageWalk:
    def test_walk_returns_direct_records(self, index_simple):
        recs = index_simple.lineage_walk("demand-aaa-111")
        assert len(recs) == 2  # decision + metric

    def test_walk_ordered_by_stage(self, index_simple):
        recs = index_simple.lineage_walk("demand-aaa-111")
        modules = [r["module"] for r in recs]
        assert modules == ["M4", "M7"]  # M4 stage=4 before M7 stage=7

    def test_walk_multi_entity(self, tmp_path):
        """Demand shares records with op via snapshot reader."""
        d_id = "demand-bbb"
        op_id = "op-bbb"
        _write_jsonl(tmp_path / "m4.jsonl", [
            _ctx_open("run-m4b", "M4"),
            _decision("dec-m4b", "run-m4b", "M4", d_id, seq=1),
            _ctx_close("run-m4b"),
        ])
        _write_jsonl(tmp_path / "m7.jsonl", [
            _ctx_open("run-m7b", "M7"),
            _decision("dec-m7b", "run-m7b", "M7", op_id,
                      entity_type="operation", driver="CALENDAR_WINDOW",
                      decision_type="assignment", seq=5),
            _metric("met-m7b", "run-m7b", "M7", d_id, seq=6),
            _ctx_close("run-m7b"),
        ])
        idx = EvidenceIndex().build(tmp_path)

        # Snapshot reader stub that knows demand → op via fulfillment
        class FakeReader:
            def get_entity(self, eid):
                if eid == d_id:
                    return {"id": d_id, "due": "2026-07-13T23:59:00"}
                return None
            def iter_entities(self, etype):
                if etype == "fulfillment":
                    yield {"id": "ful-bbb", "demand_ref": d_id, "workpackage_ref": "wp-bbb"}
                elif etype == "operation":
                    yield {"id": op_id, "workpackage_ref": "wp-bbb", "spec_ref": "x"}

        recs = idx.lineage_walk(d_id, snapshot_reader=FakeReader())
        types = {r["decision_type"] for r in recs if r.get("record_type") == "decision"}
        assert "demand_merge" in types
        assert "assignment" in types

    def test_walk_unknown_entity(self, index_simple):
        assert index_simple.lineage_walk("no-entity-here") == []

    def test_walk_deduplicates_shared_records(self, tmp_path):
        """A decision with two subjects should appear once in the walk."""
        d1 = "demand-d1"
        d2 = "demand-d2"
        _write_jsonl(tmp_path / "m4.jsonl", [
            _ctx_open("run-m4", "M4"),
            {
                "record_type": "decision",
                "record_id": "dec-shared",
                "run_id": "run-m4",
                "module": "M4",
                "seq": 1,
                "snapshot_id": "snap-test",
                "subjects": [
                    {"entity_id": d1, "entity_type": "demand"},
                    {"entity_id": d2, "entity_type": "demand"},
                ],
                "tier": "headline",
                "message": "",
                "decision_type": "demand_merge",
                "driver": "SETUP_AMORTIZATION",
                "basis": "policy_applied",
                "chosen": {},
                "alternatives": [],
            },
            _ctx_close("run-m4"),
        ])
        idx = EvidenceIndex().build(tmp_path)

        # Walk for d1; the shared record appears exactly once
        recs_d1 = idx.lineage_walk(d1)
        ids = [r["record_id"] for r in recs_d1]
        assert ids.count("dec-shared") == 1


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_creates_file(self, index_simple, tmp_path):
        p = tmp_path / "idx.json"
        index_simple.save(p)
        assert p.exists()

    def test_load_restores_entity_records(self, index_simple, tmp_path):
        p = tmp_path / "idx.json"
        index_simple.save(p)
        loaded = EvidenceIndex.load(p)
        recs = loaded.entity_records("demand-aaa-111")
        assert len(recs) == 2

    def test_load_restores_run_registry(self, index_simple, tmp_path):
        p = tmp_path / "idx.json"
        index_simple.save(p)
        loaded = EvidenceIndex.load(p)
        run_ids = {r["run_id"] for r in loaded.runs()}
        assert "run-m4" in run_ids

    def test_load_populates_all_evidence(self, index_simple, tmp_path):
        p = tmp_path / "idx.json"
        index_simple.save(p)
        loaded = EvidenceIndex.load(p)
        assert len(loaded._all_evidence) == len(index_simple._all_evidence)

    def test_save_is_valid_json(self, index_simple, tmp_path):
        p = tmp_path / "idx.json"
        index_simple.save(p)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "entity_records" in data
        assert "run_registry" in data

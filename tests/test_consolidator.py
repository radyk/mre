"""Tests derived from docs/02 §7: decomposability check and tier filter."""
import pytest

from mre.contracts.vocabularies import (
    DecisionBasis, DecisionType, DriverCode, ModuleCode, RecordTier, RunStatus,
)
from mre.reporter import DecomposabilityError, Reporter

SNAP = "snap-consolidator-test"


def make_reporter(tmp_path) -> Reporter:
    return Reporter.begin(
        module=ModuleCode.M1,
        purpose="consolidator test",
        config={},
        trigger="pytest",
        snapshot_id=SNAP,
        sink_dir=tmp_path,
    )


class TestDecomposability:
    def test_rollup_passes_when_sum_matches(self, tmp_path):
        r = make_reporter(tmp_path)
        m_a = r.record_metric("cost_a", 30.0, "USD", tier=RecordTier.SUPPORTING)
        m_b = r.record_metric("cost_b", 70.0, "USD", tier=RecordTier.SUPPORTING)
        r.record_metric(
            "total_cost", 100.0, "USD",
            rollup_of=[m_a.record_id, m_b.record_id],
            tier=RecordTier.HEADLINE,
        )
        r.end(RunStatus.SUCCESS)
        assert r.consolidated_doc is not None

    def test_rollup_fails_when_sum_mismatches(self, tmp_path):
        r = make_reporter(tmp_path)
        m_a = r.record_metric("cost_a", 30.0, "USD")
        m_b = r.record_metric("cost_b", 60.0, "USD")
        r.record_metric(
            "total_cost", 100.0, "USD",
            rollup_of=[m_a.record_id, m_b.record_id],
        )
        with pytest.raises(DecomposabilityError):
            r.end(RunStatus.SUCCESS)

    def test_rollup_fails_for_unknown_component_id(self, tmp_path):
        r = make_reporter(tmp_path)
        r.record_metric("total_cost", 100.0, "USD", rollup_of=["does-not-exist"])
        with pytest.raises(DecomposabilityError):
            r.end(RunStatus.SUCCESS)

    def test_metric_without_rollup_always_passes(self, tmp_path):
        r = make_reporter(tmp_path)
        r.record_metric("lone_metric", 42.0, "units")
        r.end(RunStatus.SUCCESS)
        assert r.consolidated_doc is not None

    def test_decomposability_error_names_the_metric(self, tmp_path):
        r = make_reporter(tmp_path)
        m_a = r.record_metric("part", 10.0, "USD")
        r.record_metric("wrong_total", 99.0, "USD", rollup_of=[m_a.record_id])
        with pytest.raises(DecomposabilityError, match="wrong_total"):
            r.end(RunStatus.SUCCESS)

    def test_three_level_rollup_passes(self, tmp_path):
        r = make_reporter(tmp_path)
        m1 = r.record_metric("a", 10.0, "X")
        m2 = r.record_metric("b", 20.0, "X")
        m3 = r.record_metric("c", 30.0, "X")
        r.record_metric("total", 60.0, "X", rollup_of=[m1.record_id, m2.record_id, m3.record_id])
        r.end(RunStatus.SUCCESS)
        assert r.consolidated_doc is not None


class TestTierFilter:
    def test_detail_records_excluded_from_consolidated_doc(self, tmp_path):
        r = make_reporter(tmp_path)
        r.record_event("detail event", tier=RecordTier.DETAIL)
        r.end(RunStatus.SUCCESS)
        tiers = [rec["tier"] for rec in r.consolidated_doc["records"]]
        assert "detail" not in tiers

    def test_headline_records_included(self, tmp_path):
        r = make_reporter(tmp_path)
        r.record_metric("kpi", 1.0, "X", tier=RecordTier.HEADLINE)
        r.end(RunStatus.SUCCESS)
        tiers = [rec["tier"] for rec in r.consolidated_doc["records"]]
        assert "headline" in tiers

    def test_supporting_records_included(self, tmp_path):
        r = make_reporter(tmp_path)
        r.record_event("support", tier=RecordTier.SUPPORTING)
        r.end(RunStatus.SUCCESS)
        tiers = [rec["tier"] for rec in r.consolidated_doc["records"]]
        assert "supporting" in tiers

    def test_detail_records_remain_in_jsonl(self, tmp_path):
        """Detail records are stream-only; they survive in JSONL but not the doc."""
        import json
        r = make_reporter(tmp_path)
        e = r.record_event("detail only", tier=RecordTier.DETAIL)
        r.end(RunStatus.SUCCESS)
        lines = (tmp_path / f"{r.run_id}.jsonl").read_text().splitlines()
        all_records = [json.loads(l) for l in lines if l.strip()]
        detail_in_stream = [
            rec for rec in all_records
            if rec.get("record_id") == e.record_id
        ]
        assert len(detail_in_stream) == 1

    def test_mixed_tiers_filtered_correctly(self, tmp_path):
        r = make_reporter(tmp_path)
        r.record_event("headline", tier=RecordTier.HEADLINE)
        r.record_event("supporting", tier=RecordTier.SUPPORTING)
        r.record_event("detail", tier=RecordTier.DETAIL)
        r.end(RunStatus.SUCCESS)
        tiers = {rec["tier"] for rec in r.consolidated_doc["records"]}
        assert "detail" not in tiers
        assert "headline" in tiers
        assert "supporting" in tiers


class TestRunContextInConsolidatedDoc:
    def test_run_context_present(self, tmp_path):
        r = make_reporter(tmp_path)
        r.end(RunStatus.SUCCESS)
        assert "run_context" in r.consolidated_doc

    def test_run_context_has_run_id(self, tmp_path):
        r = make_reporter(tmp_path)
        r.end(RunStatus.SUCCESS)
        assert r.consolidated_doc["run_context"]["run_id"] == r.run_id

    def test_run_context_has_status(self, tmp_path):
        r = make_reporter(tmp_path)
        r.end(RunStatus.SUCCESS)
        assert r.consolidated_doc["run_context"]["status"] == "success"

    def test_run_context_has_timing(self, tmp_path):
        r = make_reporter(tmp_path)
        r.end(RunStatus.SUCCESS)
        ctx = r.consolidated_doc["run_context"]
        assert "started_at" in ctx
        assert "ended_at" in ctx
        assert "duration_seconds" in ctx

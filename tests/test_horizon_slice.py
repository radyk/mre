"""Tests for the --horizon-days demand-selection policy and the reference_date
horizon floor (no operations may start before reference_date).

Uses the raw_data_mini fixture (reference_date 2025-03-22):
  WO-A001: CreatedDate=2025-03-20 (2 days before ref_date) → earliest_start in past
  WO-A001..A004: due 2025-03-25..28 (within 7d)  → INCLUDED
  WO-A005:       out-of-window (before ref_date)  → excluded by adapter
  WO-A006..A009: due 2025-04-01..04 (beyond 7d)  → DEFERRED by horizon-slice
"""
from __future__ import annotations

from pathlib import Path
import pytest

RAW_MINI = Path(__file__).parent / "fixtures" / "raw_data_mini"
PLANT_CFG = str(RAW_MINI / "plant_config.json")


@pytest.fixture(scope="module")
def sliced_run(tmp_path_factory):
    """Run the full pipeline with --horizon-days 7 against raw_data_mini."""
    from mre.__main__ import main
    from mre.modules.evidence_index import EvidenceIndex

    out = tmp_path_factory.mktemp("horizon_slice")
    rc = main([
        "--raw-data", str(RAW_MINI),
        "--plant-config", PLANT_CFG,
        "--out", str(out),
        "--snapshot-id", "snap-hs-test",
        "--horizon-days", "7",
        "--time-limit", "5",
    ])
    index = EvidenceIndex().build(out / "runs")
    return {"rc": rc, "out": out, "index": index}


class TestHorizonSlicePolicy:
    def test_pipeline_succeeds(self, sliced_run):
        assert sliced_run["rc"] == 0

    def test_model_simplification_decision_recorded(self, sliced_run):
        """horizon-slice must emit a MODEL_SIMPLIFICATION/POLICY_RULE decision."""
        index = sliced_run["index"]
        decs = [
            r for r in index._all_evidence
            if r.get("record_type") == "decision"
            and r.get("decision_type") == "model_simplification"
            and r.get("driver") == "POLICY_RULE"
        ]
        assert decs, "MODEL_SIMPLIFICATION/POLICY_RULE decision must be in evidence"

    def test_decision_message_mentions_cutoff(self, sliced_run):
        index = sliced_run["index"]
        decs = [
            r for r in index._all_evidence
            if r.get("record_type") == "decision"
            and r.get("decision_type") == "model_simplification"
        ]
        assert decs
        msg = decs[0].get("message", "")
        assert "7d" in msg or "7" in msg, f"Message should mention horizon days: {msg}"
        assert "2025-03-29" in msg, f"Message should mention cutoff date: {msg}"

    def test_schedule_excludes_beyond_horizon(self, sliced_run):
        """WO-A006..A009 (due April 1-4) must not appear in the schedule."""
        import csv
        csv_path = sliced_run["out"] / "schedule.csv"
        if not csv_path.exists():
            pytest.skip("schedule.csv not produced (no feasible solution)")
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        work_orders = {r["work_orders"] for r in rows}
        for wo in ("WO-A006", "WO-A007", "WO-A008", "WO-A009"):
            assert wo not in work_orders, f"{wo} must be deferred by horizon-slice"

    def test_within_horizon_demands_scheduled(self, sliced_run):
        """WO-A001 (due 2025-03-25, within 7d) must appear in the schedule."""
        import csv
        csv_path = sliced_run["out"] / "schedule.csv"
        if not csv_path.exists():
            pytest.skip("schedule.csv not produced (no feasible solution)")
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        work_orders = {r["work_orders"] for r in rows}
        assert "WO-A001" in work_orders, "WO-A001 must be scheduled (due within 7d)"


# ---------------------------------------------------------------------------
# Reference-date horizon floor: no operation may start before reference_date
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def unsliced_run(tmp_path_factory):
    """Run full pipeline WITHOUT --horizon-days; reference_date floor must apply."""
    from mre.__main__ import main
    from mre.modules.evidence_index import EvidenceIndex

    out = tmp_path_factory.mktemp("no_past_starts")
    rc = main([
        "--raw-data", str(RAW_MINI),
        "--plant-config", PLANT_CFG,
        "--out", str(out),
        "--snapshot-id", "snap-floor-test",
        "--time-limit", "5",
    ])
    return {"rc": rc, "out": out}


class TestNoPreReferenceDateStarts:
    """BUG FIX: horizon_start must be clamped to reference_date.

    WO-A001 has CreatedDate=2025-03-20, two days before reference_date 2025-03-22.
    Before the fix, horizon_start=2025-03-20 and the solver could place WO-A001
    operations as early as 2025-03-20 (in the past).
    After the fix, horizon_start=max(2025-03-20, 2025-03-22)=2025-03-22 and all
    operation starts must be >= 2025-03-22.
    """

    REFERENCE_DATE = "2025-03-22"

    def test_pipeline_succeeds(self, unsliced_run):
        assert unsliced_run["rc"] == 0

    def test_no_starts_before_reference_date(self, unsliced_run):
        import csv
        from datetime import datetime, timezone
        csv_path = unsliced_run["out"] / "schedule.csv"
        if not csv_path.exists():
            pytest.skip("schedule.csv not produced")
        ref_dt = datetime.fromisoformat(self.REFERENCE_DATE).replace(
            tzinfo=timezone.utc
        )
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        violations = [
            r for r in rows
            if datetime.fromisoformat(r["start"]) < ref_dt
        ]
        assert not violations, (
            f"{len(violations)} operation(s) start before reference_date "
            f"{self.REFERENCE_DATE}: "
            + ", ".join(f"{r['work_orders']}@{r['start']}" for r in violations[:3])
        )

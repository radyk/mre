"""IDS end-to-end harness (CLAUDE.md task 4).

For each scenario in the generator's catalog: generate -> gate -> assert the
certificate grade and every truth-manifest finding appears somewhere in the
evidence stream -> if not REJECTED, run the full pipeline and assert the
truth manifest's schedule-level properties (late set, lock respected,
priority ordering, transition honored). Deterministic via seed.

clean_large is marked slow (3000 orders) and skipped unless --runslow.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.modules.conformance import ConformanceGate
from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.reporter import Reporter
from tools.generate_erp_dataset import SCENARIOS, generate

UTC = timezone.utc


def _run_gate(submission_dir: Path, runs_dir: Path):
    reporter = Reporter.begin(
        module=ModuleCode.M0, purpose="harness gate run", config={}, trigger="test",
        snapshot_id="pre-adapter", sink_dir=runs_dir,
    )
    result = ConformanceGate().run(submission_dir, reporter)
    reporter.end(RunStatus.SUCCESS if result.go else RunStatus.PARTIAL)
    return result


def _all_findings(runs_dir: Path) -> list[dict]:
    findings = []
    for f in runs_dir.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("record_type") == "finding":
                findings.append(rec)
    return findings


def _read_schedule_csv(out_dir: Path) -> list[dict]:
    path = out_dir / "schedule.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


NON_SLOW_SCENARIOS = [s for s in SCENARIOS if not SCENARIOS[s].get("slow")]


@pytest.mark.parametrize("scenario", NON_SLOW_SCENARIOS)
class TestScenarioGateAndTruth:
    """Step 1-2 of the harness: generate -> gate -> grade + finding coverage."""

    def test_certificate_grade_matches_truth(self, tmp_path, scenario):
        sub_dir = tmp_path / "submission"
        truth = generate(sub_dir, scenario=scenario, seed=11)
        result = _run_gate(sub_dir, tmp_path / "gate_runs")
        assert result.grade == truth["expected_certificate_grade"], (
            f"{scenario}: gate said {result.grade}, truth expected "
            f"{truth['expected_certificate_grade']}"
        )

    def test_costing_grade_matches_truth(self, tmp_path, scenario):
        sub_dir = tmp_path / "submission"
        truth = generate(sub_dir, scenario=scenario, seed=11)
        result = _run_gate(sub_dir, tmp_path / "gate_runs")
        assert result.costing_grade == truth["expected_costing_grade"]

    def test_every_seeded_anomaly_has_a_finding(self, tmp_path, scenario):
        """Each seeded anomaly must produce >=1 finding of its expected code
        somewhere in the evidence stream — the gate for structural/integrity/
        quality defects, or the full pipeline run for solve-time defects
        (e.g. chunking_exam's INFEASIBLE_SUBSET, which only M3 can see)."""
        sub_dir = tmp_path / "submission"
        out_dir = tmp_path / "out"
        truth = generate(sub_dir, scenario=scenario, seed=11)
        if not truth["anomalies"]:
            pytest.skip(f"{scenario} seeds no anomalies")

        exit_code = mre_main([
            "--submission", str(sub_dir), "--out", str(out_dir),
            "--snapshot-id", "snap-harness", "--time-limit", "20",
        ])
        findings = _all_findings(out_dir / "runs")
        codes_present = {f["code"] for f in findings}

        for entry in truth["anomalies"]:
            expected = entry["expected_finding_code"]
            assert expected in codes_present, (
                f"{scenario}: anomaly '{entry['anomaly']}' expected finding "
                f"{expected}, got {sorted(codes_present)}"
            )


class TestRejectedScenario:
    def test_pipeline_stops_before_adapter(self, tmp_path):
        sub_dir = tmp_path / "submission"
        out_dir = tmp_path / "out"
        generate(sub_dir, scenario="rejected", seed=1)
        exit_code = mre_main([
            "--submission", str(sub_dir), "--out", str(out_dir),
            "--snapshot-id", "snap-rej",
        ])
        assert exit_code == 1
        assert not (out_dir / "schedule.csv").exists()
        assert (out_dir / "certificate.json").exists()
        cert = json.loads((out_dir / "certificate.json").read_text(encoding="utf-8"))
        assert cert["grade"] == "REJECTED"


class TestCleanSmallPipeline:
    def test_full_pipeline_produces_schedule(self, tmp_path):
        sub_dir = tmp_path / "submission"
        out_dir = tmp_path / "out"
        truth = generate(sub_dir, scenario="clean_small", seed=1)
        exit_code = mre_main([
            "--submission", str(sub_dir), "--out", str(out_dir),
            "--snapshot-id", "snap-clean", "--time-limit", "20",
        ])
        assert exit_code == 0
        rows = _read_schedule_csv(out_dir)
        assert len(rows) > 0


class TestMessyRealisticPipeline:
    def test_conditional_still_schedules(self, tmp_path):
        sub_dir = tmp_path / "submission"
        out_dir = tmp_path / "out"
        truth = generate(sub_dir, scenario="messy_realistic", seed=1)
        assert truth["expected_certificate_grade"] == "CONDITIONAL"
        exit_code = mre_main([
            "--submission", str(sub_dir), "--out", str(out_dir),
            "--snapshot-id", "snap-messy", "--time-limit", "30",
        ])
        assert exit_code == 0
        rows = _read_schedule_csv(out_dir)
        assert len(rows) > 0


class TestLockedPlantScenario:
    def test_lock_is_respected(self, tmp_path):
        sub_dir = tmp_path / "submission"
        out_dir = tmp_path / "out"
        truth = generate(sub_dir, scenario="locked_plant", seed=1)
        exit_code = mre_main([
            "--submission", str(sub_dir), "--out", str(out_dir),
            "--snapshot-id", "snap-locked", "--time-limit", "20",
        ])
        assert exit_code == 0

        lock = truth["lock"]
        rows = _read_schedule_csv(out_dir)
        matches = [r for r in rows
                   if r["work_orders"] == lock["order_id"] and r["machine"] == lock["resource_id"]]
        assert matches, f"no schedule row for locked order {lock['order_id']} on {lock['resource_id']}"
        locked_row = min(matches, key=lambda r: r["start"])
        assert locked_row["start"] == lock["start"], (
            f"locked order started at {locked_row['start']}, expected {lock['start']}"
        )


class TestPriorityPressureScenario:
    def test_critical_order_not_scheduled_after_standard(self, tmp_path):
        sub_dir = tmp_path / "submission"
        out_dir = tmp_path / "out"
        truth = generate(sub_dir, scenario="priority_pressure", seed=1)
        exit_code = mre_main([
            "--submission", str(sub_dir), "--out", str(out_dir),
            "--snapshot-id", "snap-pp", "--time-limit", "20",
        ])
        assert exit_code == 0

        rows = _read_schedule_csv(out_dir)
        crit_id, std_id = truth["bottleneck_orders"]
        assert truth["must_win_order_id"] == crit_id

        crit_rows = [r for r in rows if r["work_orders"] == crit_id]
        std_rows = [r for r in rows if r["work_orders"] == std_id]
        assert crit_rows and std_rows

        crit_end = max(datetime.fromisoformat(r["end"]) for r in crit_rows)
        std_end = max(datetime.fromisoformat(r["end"]) for r in std_rows)
        assert crit_end <= std_end, (
            f"critical order {crit_id} finished at {crit_end}, "
            f"after standard order {std_id} at {std_end} — priority pressure not honored"
        )


class TestTransitionHeavyScenario:
    def test_transition_gap_honored_on_shared_resources(self, tmp_path):
        sub_dir = tmp_path / "submission"
        out_dir = tmp_path / "out"
        truth = generate(sub_dir, scenario="transition_heavy", seed=1)
        exit_code = mre_main([
            "--submission", str(sub_dir), "--out", str(out_dir),
            "--snapshot-id", "snap-trans", "--time-limit", "30",
        ])
        assert exit_code == 0

        rows = _read_schedule_csv(out_dir)
        by_machine: dict[str, list[dict]] = {}
        for r in rows:
            by_machine.setdefault(r["machine"], []).append(r)

        fam_a, fam_b = truth["transition_families"]
        cross_family_minutes = 90  # from _apply_transitions in the generator
        violations = []
        for machine, m_rows in by_machine.items():
            m_rows.sort(key=lambda r: r["start"])
            for prev, cur in zip(m_rows, m_rows[1:]):
                if prev["setup_family"] == cur["setup_family"]:
                    continue
                gap_min = (
                    datetime.fromisoformat(cur["start"]) - datetime.fromisoformat(prev["end"])
                ).total_seconds() / 60.0
                if gap_min < cross_family_minutes - 1:  # 1-minute integer-rounding tolerance
                    violations.append((machine, prev, cur, gap_min))
        assert not violations, f"transition gap violated: {violations}"


class TestChunkingExamScenario:
    def test_oversized_orders_excluded_from_schedule(self, tmp_path):
        sub_dir = tmp_path / "submission"
        out_dir = tmp_path / "out"
        truth = generate(sub_dir, scenario="chunking_exam", seed=1)
        exit_code = mre_main([
            "--submission", str(sub_dir), "--out", str(out_dir),
            "--snapshot-id", "snap-chunk", "--time-limit", "20",
        ])
        assert exit_code == 0

        anomaly = next(a for a in truth["anomalies"] if a["anomaly"] == "chunking_exam")
        rows = _read_schedule_csv(out_dir)
        scheduled_orders = {r["work_orders"] for r in rows}
        for order_id in anomaly["affected_order_ids"]:
            assert order_id not in scheduled_orders, (
                f"{order_id} should have been excluded (INFEASIBLE_SUBSET) but appears in schedule.csv"
            )


@pytest.mark.slow
class TestCleanLargeScenario:
    def test_full_pipeline_at_scale(self, tmp_path):
        sub_dir = tmp_path / "submission"
        out_dir = tmp_path / "out"
        truth = generate(sub_dir, scenario="clean_large", seed=1)
        exit_code = mre_main([
            "--submission", str(sub_dir), "--out", str(out_dir),
            "--snapshot-id", "snap-large", "--time-limit", "120",
        ])
        assert exit_code == 0
        rows = _read_schedule_csv(out_dir)
        assert len(rows) > 0

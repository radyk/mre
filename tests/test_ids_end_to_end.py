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
from datetime import datetime, timedelta, timezone
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


# Feel fixtures (e.g. busy_board, docs/07 Phase 3) are hands-on cockpit boards
# with a feel_fixture.json marker and NO truth manifest, so the grade/anomaly
# assertions here have nothing to check against (a red carried since 3.2d).
# Exclude them explicitly — the same CU5 guard as test_certificate_conversation.
NON_SLOW_SCENARIOS = [s for s in SCENARIOS
                      if not SCENARIOS[s].get("slow") and not SCENARIOS[s].get("feel")]


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
            if expected is None:
                continue  # e.g. chunking_exam post-Rep-2: chunked and scheduled, no finding
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
    """Rep 2 (docs/05 R-C3): chunking_exam's oversized operations are no
    longer excluded (INFEASIBLE_SUBSET) — they are chunked and scheduled.
    This is the standing production test for the spike-2 semantic assertion
    (every derived pause aligns exactly with a calendar closure)."""

    def test_oversized_orders_are_chunked_and_scheduled(self, tmp_path):
        from mre.modules.calendar_utils import flatten_calendar
        from mre.modules.snapshot_store import SnapshotStore

        sub_dir = tmp_path / "submission"
        out_dir = tmp_path / "out"
        truth = generate(sub_dir, scenario="chunking_exam", seed=1)
        exit_code = mre_main([
            "--submission", str(sub_dir), "--out", str(out_dir),
            "--snapshot-id", "snap-chunk", "--time-limit", "20",
        ])
        assert exit_code == 0

        anomaly = next(a for a in truth["anomalies"] if a["anomaly"] == "chunking_exam")
        expected_chunks = anomaly["expected_chunk_count"]
        rows = _read_schedule_csv(out_dir)

        store = SnapshotStore(out_dir / "snapshots")
        reader = store.load_snapshot("snap-chunk")
        calendars_by_id = {c["id"]: c for c in reader.iter_entities("calendar")}
        resources_by_id = {r["id"]: r for r in reader.iter_entities("resource")}
        identity_map = reader.read_identity_map()

        for order_id in anomaly["affected_order_ids"]:
            order_rows = sorted(
                (r for r in rows if order_id in r["work_orders"].split("+")),
                key=lambda r: int(r["chunk_seq"] or "1"),
            )
            assert order_rows, f"{order_id} should be chunked and scheduled, but has no schedule.csv rows"
            assert len(order_rows) == expected_chunks, (
                f"{order_id}: expected {expected_chunks} chunks, got {len(order_rows)}"
            )
            assert all(r["chunk_seq"] for r in order_rows), f"{order_id}: chunk_seq must be set on every row"

            # Every derived pause must align exactly with a real calendar closure.
            machine_name = order_rows[0]["machine"]
            resource_id = next(
                (rid for rid, r in resources_by_id.items()
                 if identity_map and identity_map.external_refs(rid)
                 and identity_map.external_refs(rid)[0].value == machine_name),
                None,
            )
            assert resource_id is not None, f"could not resolve machine '{machine_name}' back to a resource"
            cal = calendars_by_id.get(resources_by_id[resource_id].get("calendar_ref"))
            assert cal is not None

            for prev_row, next_row in zip(order_rows, order_rows[1:]):
                gap_start = datetime.fromisoformat(prev_row["end"])
                gap_end = datetime.fromisoformat(next_row["start"])
                assert gap_end > gap_start, f"{order_id}: chunk rows must be time-ordered"
                windows = flatten_calendar(
                    cal.get("base_pattern", {}), [], gap_start - timedelta(days=1), gap_end + timedelta(days=1),
                )
                overlapping = [w for w in windows if w.start < gap_end and w.end > gap_start]
                assert not overlapping, (
                    f"{order_id}: pause [{gap_start}, {gap_end}) overlaps an open calendar "
                    f"window {overlapping} — not a real closure"
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

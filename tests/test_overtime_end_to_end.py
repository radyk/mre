"""overtime_required end-to-end harness (docs/06 §5.6/§5.9, docs/07 Phase 1).

Generate → gate → full pipeline, then assert the truth manifest's three
claims about priced overtime:
  (a) the solver uses overtime only where tardiness would cost more than the
      premium — exactly one rescue operation runs in the Saturday window,
      the slack-rich control orders use none;
  (b) the overtime ledger line appears and the cost decomposition stays
      exact (production = regular + overtime; total = production + setup +
      tardiness);
  (c) removing the overtime calendar windows makes the same demands late —
      the capacity was real and the premium bought real service.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.modules.snapshot_store import SnapshotStore
from tools.generate_erp_dataset import generate

UTC = timezone.utc

_PIPELINE_FLAGS = ["--time-limit", "30", "--solver-workers", "1", "--solver-seed", "42"]


def _run_pipeline(sub_dir: Path, out_dir: Path) -> int:
    return mre_main([
        "--submission", str(sub_dir), "--out", str(out_dir), *_PIPELINE_FLAGS,
    ])


def _snapshot(out_dir: Path):
    return SnapshotStore(out_dir / "snapshots").load_snapshot("snap-run")


def _order_lateness(reader) -> dict[str, int]:
    """external order_id → lateness_minutes from ServiceOutcomes."""
    demands = {d["id"]: d for d in reader.iter_entities("demand")}
    out: dict[str, int] = {}
    for svc in reader.iter_entities("serviceoutcome"):
        d = demands[svc["demand_ref"]]
        ext = next(e["value"] for e in d["external_refs"] if e["type"] == "order_id")
        lateness = svc["lateness"]
        # persisted as ISO-8601 duration or seconds depending on pydantic dump
        if isinstance(lateness, str):
            minutes = _iso_duration_minutes(lateness)
        else:
            minutes = float(lateness) / 60.0
        out[ext] = minutes
    return out


def _iso_duration_minutes(s: str) -> float:
    import re
    neg = s.startswith("-")
    m = re.fullmatch(
        r"-?P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?)?", s
    )
    assert m, f"unparseable duration {s!r}"
    days, hours, mins, secs = (float(g or 0) for g in m.groups())
    total = days * 1440 + hours * 60 + mins + secs / 60
    return -total if neg else total


def _decisions(out_dir: Path) -> list[dict]:
    records = []
    for f in (out_dir / "runs").glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("record_type") == "decision":
                records.append(rec)
    return records


@pytest.fixture(scope="module")
def overtime_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("overtime_required")
    sub_dir = tmp / "submission"
    out_dir = tmp / "out"
    truth = generate(sub_dir, scenario="overtime_required", seed=3)
    exit_code = _run_pipeline(sub_dir, out_dir)
    assert exit_code == 0
    return truth, sub_dir, out_dir


class TestOvertimeRequired:
    def test_certificate_grades_c2(self, overtime_run):
        _, _, out_dir = overtime_run
        cert = json.loads((out_dir / "certificate.json").read_text(encoding="utf-8"))
        assert cert["grade"] == "ACCEPTED"
        assert cert["costing_completeness_grade"] == "C2"

    def test_exactly_one_rescue_op_runs_in_the_overtime_window(self, overtime_run):
        truth, _, out_dir = overtime_run
        ot = truth["overtime"]
        sat = datetime.fromisoformat(ot["overtime_date"]).replace(tzinfo=UTC)
        with open(out_dir / "schedule.csv", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))

        saturday_rows = [
            r for r in rows
            if datetime.fromisoformat(r["start"]).replace(tzinfo=UTC).date() == sat.date()
        ]
        assert len(saturday_rows) == 1, saturday_rows
        row = saturday_rows[0]
        assert row["work_orders"] in ot["rescue_order_ids"]
        assert row["machine"] == ot["resource_id"]
        # 600 working minutes inside the 07:00-19:00 window.
        start = datetime.fromisoformat(row["start"])
        end = datetime.fromisoformat(row["end"])
        assert (end - start).total_seconds() / 60 == ot["expected_overtime_minutes"]
        assert start.hour >= 7 and end.hour <= 19

    def test_all_rescue_orders_on_time_and_controls_untouched(self, overtime_run):
        truth, _, out_dir = overtime_run
        ot = truth["overtime"]
        lateness = _order_lateness(_snapshot(out_dir))
        for oid in ot["rescue_order_ids"]:
            assert lateness[oid] <= 0, f"rescue order {oid} late by {lateness[oid]} min"
        for oid in ot["control_order_ids"]:
            assert lateness[oid] <= 0

    def test_overtime_ledger_line_appears_and_decomposes(self, overtime_run):
        truth, _, out_dir = overtime_run
        ot = truth["overtime"]
        summary = next(iter(_snapshot(out_dir).iter_entities("schedule")))["summary_metrics"]

        assert summary["production_overtime_cost"] == pytest.approx(
            ot["expected_production_overtime_cost"]
        )
        assert summary["production_cost"] == pytest.approx(
            summary["production_regular_cost"] + summary["production_overtime_cost"]
        )
        assert summary["total_cost"] == pytest.approx(
            summary["production_cost"] + summary["setup_cost"] + summary["tardiness_cost"]
        )

    def test_assignment_decision_carries_overtime_evidence(self, overtime_run):
        """Testimony-renderable: the Saturday assignment's reconstructed
        Decision names the overtime minutes and the premium paid."""
        truth, _, out_dir = overtime_run
        ot = truth["overtime"]
        overtime_decisions = [
            d for d in _decisions(out_dir)
            if isinstance(d.get("chosen"), dict) and d["chosen"].get("overtime_minutes")
        ]
        assert len(overtime_decisions) == 1
        chosen = overtime_decisions[0]["chosen"]
        assert chosen["overtime_minutes"] == ot["expected_overtime_minutes"]
        assert chosen["overtime_premium_multiplier"] == ot["premium_multiplier"]
        assert chosen["overtime_cost"] == pytest.approx(
            ot["expected_production_overtime_cost"]
        )
        assert "overtime" in overtime_decisions[0]["message"]

    def test_assignment_entity_is_authoritative_for_overtime(self, overtime_run):
        """2026-07-13 ruling (docs/01 §6.9): the persisted Assignment entity
        carries overtime_minutes with derived provenance — the entity is the
        source of truth; the Decision's chosen payload is narrative only."""
        truth, _, out_dir = overtime_run
        ot = truth["overtime"]
        reader = _snapshot(out_dir)
        assignments = list(reader.iter_entities("assignment"))
        assert assignments and all("overtime_minutes" in a for a in assignments)

        ot_assignments = [a for a in assignments if a["overtime_minutes"]]
        assert len(ot_assignments) == 1
        assert ot_assignments[0]["overtime_minutes"] == ot["expected_overtime_minutes"]

        provs = list(reader.iter_provenance_for_entity(ot_assignments[0]["id"]))
        ot_prov = [p for p in provs if p.get("attribute_name") == "overtime_minutes"]
        assert len(ot_prov) == 1
        assert ot_prov[0]["provenance_class"] == "derived"
        assert ot_prov[0]["payload"]["formula_id"] == "M7.overtime_attribution"

    def test_document_derives_in_overtime_min_from_the_entity(self, overtime_run):
        """The schedule document's in_overtime_min now comes from the entity
        attribute (Decision payload is only a pre-2.2-snapshot fallback)."""
        from mre.modules.schedule_assembler import build_document_from_run

        truth, _, out_dir = overtime_run
        ot = truth["overtime"]
        doc = build_document_from_run(out_dir, "snap-run", "run-test")
        with_ot = [a for a in doc.assignments if a.in_overtime_min > 0]
        assert len(with_ot) == 1
        assert with_ot[0].in_overtime_min == ot["expected_overtime_minutes"]

    def test_removing_overtime_windows_makes_the_same_demands_late(
        self, overtime_run, tmp_path
    ):
        """Counterfactual (c): strip the overtime exception rows and re-run —
        no overtime cost, and exactly the manifest's expected count of rescue
        demands go late. The premium bought real service."""
        import shutil

        truth, sub_dir, _ = overtime_run
        ot = truth["overtime"]
        stripped = tmp_path / "submission_no_ot"
        shutil.copytree(sub_dir, stripped)

        cal_path = stripped / "calendars.csv"
        with open(cal_path, encoding="utf-8", newline="") as f:
            dict_reader = csv.DictReader(f)
            rows = list(dict_reader)
            fieldnames = list(dict_reader.fieldnames or rows[0].keys())
        pattern_rows = [r for r in rows if r.get("row_type") != "exception"]
        assert len(pattern_rows) < len(rows), "fixture should have had exception rows"
        with open(cal_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(pattern_rows)

        out_dir = tmp_path / "out_no_ot"
        assert _run_pipeline(stripped, out_dir) == 0

        reader = _snapshot(out_dir)
        summary = next(iter(reader.iter_entities("schedule")))["summary_metrics"]
        assert summary["production_overtime_cost"] == 0.0

        lateness = _order_lateness(reader)
        late_rescues = [oid for oid in ot["rescue_order_ids"] if lateness[oid] > 0]
        assert len(late_rescues) == ot["expected_late_without_overtime_count"]
        for oid in ot["control_order_ids"]:
            assert lateness[oid] <= 0

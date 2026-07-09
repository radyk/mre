"""Rep 2 acceptance item 5c: gauntlet re-run — report the exact rescue count
from the 173 INFEASIBLE_SUBSET exclusions (raw_data + plant_config.json, the
documented window-fit exclusion count cited throughout docs/05/07). This
count comes from the Validator run against the FULL demand set — it does
not depend on --horizon-days (that CLI flag defers demands post-validation;
it does not change which operations fail the pre-solve window-fit check).

raw_adapter.py has no real data source for OperationSpec.splittable (the
ticketing extract has no such column) — R-C3's default (setup/teardown
resumable, run NOT resumable absent a declaration) means the real pipeline
is, correctly, unchanged: it would take a genuine plant declaration to make
any of these operations resumable, and inventing one would violate the
"no attribute write without a real basis" rule.

This script instead runs the measurement docs/07's exit-demo criterion asks
for: given the real gauntlet slice, IF every excluded operation's spec were
declared resumable (the counterfactual a plant conversation would actually
have — "could we chunk these?"), how many of the 173 would Rep 2 rescue,
and what — precisely — is still infeasible even chunked?

Usage:
    python tools/gauntlet_rescue_report.py
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mre.contracts.vocabularies import ModuleCode, RunStatus  # noqa: E402
from mre.modules.calendar_utils import flatten_calendar  # noqa: E402
from mre.modules.raw_adapter import RawAdapter, load_plant_config  # noqa: E402
from mre.modules.snapshot_store import SnapshotStore  # noqa: E402
from mre.modules.validator import Validator  # noqa: E402
from mre.reporter import Reporter  # noqa: E402

UTC = timezone.utc
REPO = Path(__file__).resolve().parent.parent


def _reference_datetime(cfg: dict) -> datetime:
    d = date.fromisoformat(cfg["reference_date"])
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def _run_validator(store: SnapshotStore, snap_id: str, runs_dir: Path, reference_date: datetime):
    rep = Reporter.begin(
        module=ModuleCode.M3, purpose="gauntlet rescue report", config={},
        trigger="tools", snapshot_id=snap_id, sink_dir=runs_dir,
    )
    result = Validator().run(snap_id, store, rep, reference_date=reference_date)
    rep.end(RunStatus.SUCCESS)
    findings = [
        json.loads(r.model_dump_json()) if hasattr(r, "model_dump_json") else r
        for r in rep._sink.read_all()
        if r.get("record_type") == "finding"
    ]
    infeasible = [f for f in findings if f["code"] == "INFEASIBLE_SUBSET"]
    return result, infeasible


def _mark_all_specs_resumable(snap_dir: Path) -> int:
    """Rewrite entities_operationspec.jsonl in place: splittable=true,
    min_chunk=30min for every spec. Returns the count modified."""
    path = snap_dir / "entities_operationspec.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    n = 0
    for line in lines:
        if not line.strip():
            continue
        rec = json.loads(line)
        rec["splittable"] = True
        rec["min_chunk"] = "PT30M"
        out.append(json.dumps(rec))
        n += 1
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return n


def main() -> None:
    out_dir = REPO / "mre_output" / "gauntlet_rescue"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    snap_id = "snap-rescue"
    store = SnapshotStore(out_dir / "snapshots")
    runs_dir = out_dir / "runs"

    plant_cfg = load_plant_config(REPO / "plant_config.json")
    reference_date = _reference_datetime(plant_cfg)

    a_rep = Reporter.begin(
        module=ModuleCode.M1, purpose="gauntlet rescue adapter", config={},
        trigger="tools", snapshot_id=snap_id, sink_dir=runs_dir,
    )
    RawAdapter(REPO / "raw_data", plant_cfg).run(snap_id, store, a_rep)
    a_rep.end(RunStatus.SUCCESS)

    # --- Baseline: today's real pipeline (no splittable declarations) ---
    baseline_result, baseline_findings = _run_validator(store, snap_id, runs_dir / "baseline", reference_date)
    baseline_excluded = {f["evidence"]["demand_id"] for f in baseline_findings}
    print(f"[gauntlet_rescue] baseline INFEASIBLE_SUBSET exclusions: {len(baseline_excluded)}")

    # --- Counterfactual: every OperationSpec declared resumable ---
    snap_dir = out_dir / "snapshots" / snap_id
    n_specs = _mark_all_specs_resumable(snap_dir)
    print(f"[gauntlet_rescue] marked {n_specs} OperationSpecs splittable=true (counterfactual)")

    resumable_result, resumable_findings = _run_validator(
        store, snap_id, runs_dir / "resumable", reference_date,
    )
    resumable_excluded = {f["evidence"]["demand_id"] for f in resumable_findings}

    rescued = baseline_excluded - resumable_excluded
    survivors = baseline_excluded & resumable_excluded
    newly_excluded = resumable_excluded - baseline_excluded  # should be empty

    print(f"[gauntlet_rescue] RESCUED: {len(rescued)} / {len(baseline_excluded)}")
    print(f"[gauntlet_rescue] SURVIVORS (still infeasible even chunked): {len(survivors)}")
    if newly_excluded:
        print(f"[gauntlet_rescue] WARNING: {len(newly_excluded)} demands newly excluded "
              f"that weren't before — unexpected, investigate: {sorted(newly_excluded)[:5]}")

    survivor_causes = []
    for f in resumable_findings:
        if f["evidence"]["demand_id"] in survivors:
            ev = f["evidence"]
            survivor_causes.append({
                "demand_id": ev["demand_id"],
                "estimated_duration_minutes": ev.get("estimated_duration_minutes"),
                "available_minutes_before_due": ev.get("available_minutes_before_due"),
                "elapsed_days_to_due": ev.get("elapsed_days_to_due"),
            })

    report_path = out_dir / "rescue_report.md"
    lines = [
        "# Gauntlet Rescue Report (Rep 2 acceptance item 5c)",
        "",
        f"Source: raw_data + plant_config.json, full demand set "
        f"(reference_date={plant_cfg['reference_date']}).",
        "",
        f"- Baseline INFEASIBLE_SUBSET exclusions (today's real pipeline, no splittable "
        f"declarations — unchanged): **{len(baseline_excluded)}**",
        f"- Rescued if every operation were declared resumable (counterfactual): "
        f"**{len(rescued)}**",
        f"- Survivors — genuinely unfittable even chunked: **{len(survivors)}**",
        "",
        "## Survivors and their causes",
        "",
        "| Demand | Estimated duration (min) | Available before due (min) | Days to due |",
        "|---|---|---|---|",
    ]
    for c in sorted(survivor_causes, key=lambda c: c["demand_id"]):
        lines.append(
            f"| {c['demand_id'][:12]} | {c['estimated_duration_minutes']} | "
            f"{c['available_minutes_before_due']} | {c['elapsed_days_to_due']} |"
        )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[gauntlet_rescue] report written to {report_path}")


if __name__ == "__main__":
    main()

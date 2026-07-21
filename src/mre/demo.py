"""Phase 3 demonstration script — docs/03 §4 steps 1–5.

Usage:
    python -m mre.demo               # template renderer
    python -m mre.demo --llm         # LLM renderer (requires ANTHROPIC_API_KEY)
    python -m mre.demo --out DIR     # write output to DIR instead of mre_demo_output
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc


def _sample_data_dir(name: str) -> Path:
    """Locate a committed sample-data directory.

    The sample data is repo fixture data, not packaged into the wheel, so a
    ``__file__``-relative path only resolves in a source checkout. Resolve it
    robustly instead: an explicit ``MRE_SAMPLE_DATA_ROOT`` wins; otherwise the
    source-checkout location (repo_root/<name>, three parents up) if it exists;
    otherwise the current working directory (where the test image COPYs
    sample_data/ into the pytest rootdir). (session 2.4b: the installed wheel's
    ``__file__``-relative path pointed into the venv and broke the demo.)
    """
    override = os.environ.get("MRE_SAMPLE_DATA_ROOT")
    if override:
        return Path(override) / name
    checkout = Path(__file__).resolve().parent.parent.parent / name
    if checkout.exists():
        return checkout
    return Path.cwd() / name


SAMPLE_DATA_V1 = _sample_data_dir("sample_data")
SAMPLE_DATA_V2 = _sample_data_dir("sample_data_v2")


def _sep(title: str) -> None:
    width = 70
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def run_demo(
    out_dir: Path,
    use_llm: bool = False,
) -> dict:
    """Run the full demo.  Returns a results dict for programmatic inspection."""
    from mre.contracts.entities import CalendarException, TimeWindow
    from mre.contracts.vocabularies import (
        CalendarExceptionReason, CalendarExceptionType,
        ModuleCode, RunStatus,
    )
    from mre.modules.adapter import Adapter
    from mre.modules.calendar_utils import flatten_calendar
    from mre.modules.dq_report import generate_dq_report
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.extractor import Extractor
    from mre.modules.planner import Planner
    from mre.modules.renderers import LLMRenderer, TemplateRenderer
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import SolverBuilder
    from mre.modules.validator import Validator
    from mre.reporter import Reporter
    import datetime as dt

    snap_id = "snap-demo-v1"
    snap_id_v2 = "snap-demo-v2"

    # Clear output dirs so we never read stale snapshot data.
    snap_dir = out_dir / "snapshots" / snap_id
    snap_dir_v2 = out_dir / "snapshots" / snap_id_v2
    runs_dir = out_dir / "runs"
    for d in (snap_dir, snap_dir_v2, runs_dir):
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    store = SnapshotStore(out_dir / "snapshots")

    def _rep(mod, purpose, snap=snap_id):
        return Reporter.begin(
            module=mod, purpose=purpose, config={},
            trigger="demo", snapshot_id=snap, sink_dir=runs_dir,
        )

    # ------------------------------------------------------------------
    # Step 1 — Ingest v1 + validation report
    # ------------------------------------------------------------------
    _sep("Step 1: Ingest sample_data v1 + validation report")

    a_rep = _rep(ModuleCode.M1, "demo adapter v1")
    a_result = Adapter(extract_dir=SAMPLE_DATA_V1).run(snap_id, store, a_rep)
    a_rep.end(RunStatus.SUCCESS)
    print(f"  Adapter complete.")

    v_rep = _rep(ModuleCode.M3, "demo validator v1")
    # sample_data_v1's seeded PROD-007 outlier is 45x median (SCENARIO.md), designed
    # against the original 10x threshold. The gauntlet-calibrated default (Rep 3,
    # 75.76x) is a different deployment's config; the demo keeps its own.
    v_result = Validator().run(snap_id, store, v_rep, outlier_threshold_ratio=10.0)
    v_rep.end(RunStatus.SUCCESS)

    # Write DQ report to disk; also build summary dict for programmatic use.
    dq_path = out_dir / "dq_report.md"
    generate_dq_report(
        adapter_doc=a_rep.consolidated_doc,
        validator_doc=v_rep.consolidated_doc,
        identity_map=a_result.identity_map,
        output_path=dq_path,
    )
    gate = "GO" if v_result.go else "NO-GO"
    v_records = v_rep._sink.read_all()
    v_findings = [r for r in v_records if r.get("record_type") == "finding"]
    dq: dict = {
        "gate": gate,
        "counts": {
            "blocker": v_result.blocker_count,
            "error": v_result.error_count,
            "warning": v_result.warning_count,
        },
        "findings": v_findings,
    }
    print(f"\n  Gate: {gate}")
    print(f"  Blocker findings : {v_result.blocker_count}")
    print(f"  Warning findings : {v_result.warning_count}")
    for f in v_findings[:6]:
        print(f"    [{f.get('severity')}] {f.get('code')}")

    # ------------------------------------------------------------------
    # Step 2 — Schedule (M4 → M7)
    # ------------------------------------------------------------------
    _sep("Step 2: Schedule (merge_by_family_v1 + CP-SAT)")

    reader = store.load_snapshot(snap_id)
    demands = list(reader.iter_entities("demand"))
    fuls_init: list[dict] = []  # will be re-loaded after M4

    p_rep = _rep(ModuleCode.M4, "demo planner v1")
    Planner(policy="merge_by_family_v1").run(snap_id, store, p_rep)
    p_rep.end(RunStatus.SUCCESS)

    reader = store.load_snapshot(snap_id)
    demands = list(reader.iter_entities("demand"))
    fuls = list(reader.iter_entities("fulfillment"))
    wps = list(reader.iter_entities("workpackage"))
    ops = list(reader.iter_entities("operation"))
    edges = list(reader.iter_entities("precedenceedge"))
    resources = list(reader.iter_entities("resource"))
    pools = list(reader.iter_entities("resourcepool"))
    calendars = list(reader.iter_entities("calendar"))
    constraints = list(reader.iter_entities("constraint"))
    costmodels = list(reader.iter_entities("costmodel"))
    cm = costmodels[0] if costmodels else {}

    print(f"  Demands: {len(demands)}  WPs: {len(wps)}  Ops: {len(ops)}")

    all_earliest = [
        datetime.fromisoformat(d["earliest_start"]).replace(tzinfo=UTC)
        for d in demands if d.get("earliest_start")
    ]
    all_due = [
        datetime.fromisoformat(d["due"]).replace(tzinfo=UTC)
        for d in demands if d.get("due")
    ]
    horizon_start = min(all_earliest).replace(hour=0, minute=0, second=0, microsecond=0)
    horizon_end = max(all_due).replace(hour=23, minute=59, second=59) + dt.timedelta(days=14)

    flattened_cals = []
    for cal in calendars:
        excs = []
        for e in cal.get("exceptions", []):
            if isinstance(e, dict) and "window" in e:
                tw = TimeWindow(
                    start=datetime.fromisoformat(e["window"]["start"]).replace(tzinfo=UTC),
                    end=datetime.fromisoformat(e["window"]["end"]).replace(tzinfo=UTC),
                )
                excs.append(CalendarException(
                    window=tw,
                    type=CalendarExceptionType(e.get("type", "closure")),
                    reason=CalendarExceptionReason(e.get("reason", "planned_maintenance")),
                ))
        windows = flatten_calendar(cal.get("base_pattern", {}), excs, horizon_start, horizon_end)
        cal_copy = dict(cal)
        cal_copy["horizon_resolved"] = [
            {"start": w.start.isoformat(), "end": w.end.isoformat()} for w in windows
        ]
        flattened_cals.append(cal_copy)

    b_rep = _rep(ModuleCode.M5, "demo builder v1")
    builder = SolverBuilder()
    model, var_map = builder.build(
        wps + ops + edges, resources + pools, flattened_cals,
        fuls + demands, constraints, cm,
    )
    b_rep.end(RunStatus.SUCCESS)

    r_rep = _rep(ModuleCode.M6, "demo solver v1")
    solve_result = SolveRunner(time_limit_seconds=60.0).solve(model, var_map, r_rep)
    status = solve_result.status
    r_rep.end(RunStatus.SUCCESS if status in ("OPTIMAL", "FEASIBLE") else RunStatus.PARTIAL)
    print(f"  Solver: {status}")

    e_rep = _rep(ModuleCode.M7, "demo extractor v1")
    extract_result = Extractor().extract(
        solve_values=solve_result.solve_values,
        snapshot_id=snap_id,
        operations=ops,
        workpackages=wps,
        resources=resources,
        fulfillments=fuls,
        demands=demands,
        cost_model=cm,
        reporter=e_rep,
        cal_windows=var_map.cal_windows,
        op_eligible=var_map.op_eligible,
    )
    e_rep.end(RunStatus.SUCCESS)

    ledger = extract_result.cost_ledger
    late_count = sum(1 for s in extract_result.service_outcomes if s["lateness_minutes"] > 0)
    print(f"  Assignments: {len(extract_result.assignments)}")
    print(f"  Late demands: {late_count} / {len(extract_result.service_outcomes)}")
    print(f"  Total cost: {ledger['total_cost']:.1f}  "
          f"(production={ledger['production_cost']:.1f}  "
          f"setup={ledger['setup_cost']:.1f}  "
          f"tardiness={ledger['tardiness_cost']:.1f})")

    # ------------------------------------------------------------------
    # M9: Build evidence index
    # ------------------------------------------------------------------
    index = EvidenceIndex().build(runs_dir)
    index_path = out_dir / "evidence_index.json"
    index.save(index_path)
    total_ev = len(index._all_evidence)
    print(f"\n  Evidence index: {total_ev} records, {len(index.runs())} runs")

    # ------------------------------------------------------------------
    # Step 3 — Ingest v2 snapshot (adapter-only, no solve)
    # ------------------------------------------------------------------
    _sep("Step 3: Ingest sample_data v2 (diff target)")

    a2_rep = _rep(ModuleCode.M1, "demo adapter v2", snap=snap_id_v2)
    Adapter(extract_dir=SAMPLE_DATA_V2).run(snap_id_v2, store, a2_rep)
    a2_rep.end(RunStatus.SUCCESS)
    print(f"  Adapter v2 complete (snap-demo-v2).")

    # ------------------------------------------------------------------
    # Step 4 — Answer: "Why is WO-2001 late?"
    # ------------------------------------------------------------------
    _sep("Step 4: Why is WO-2001 late?")

    explainer = Explainer(store, index, snapshot_id=snap_id)
    bundle = explainer.answer("Why is WO-2001 late?")

    renderer = LLMRenderer() if use_llm else TemplateRenderer()
    answer_text = renderer.render(bundle)
    print(answer_text)

    # ------------------------------------------------------------------
    # Step 5 — Snapshot diff: what changed in v2?
    # ------------------------------------------------------------------
    _sep("Step 5: What changed since snap-demo-v1?")

    diff_bundle = explainer.answer(f"What changed since {snap_id} vs {snap_id_v2}?")
    diff_text = TemplateRenderer().render(diff_bundle)
    print(diff_text)

    return {
        "gate": dq["gate"],
        "solve_status": status,
        "extract_result": extract_result,
        "index": index,
        "bundle": bundle,
        "diff_bundle": diff_bundle,
        "v_result": v_result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MRE Phase 3 demonstration")
    parser.add_argument("--llm", action="store_true", help="Use LLM renderer")
    parser.add_argument("--out", default="mre_demo_output")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    print(f"MRE Phase 3 Demo — output: {out_dir}")

    run_demo(out_dir, use_llm=args.llm)
    print("\nDemo complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Entry point: python -m mre

Runs the full scheduling spine:
    M1 Adapter → M3 Validator → gate check → M4 Planner →
    M5 SolverBuilder → M6 SolveRunner → M7 Extractor

Usage (sample data):
    python -m mre [--sample-data PATH] [--out PATH] [--snapshot-id ID]
                  [--policy identity_v1|merge_by_family_v1]
                  [--time-limit N] [--skip-schedule]

Usage (real data):
    python -m mre --raw-data raw_data --plant-config plant_config.json
                  [--out PATH] [--skip-schedule] [--time-limit N]
                  [--horizon-days N]

Demand-selection policies (applied after validator, before planner):
    --horizon-days N   Only schedule demands whose due date is within N days
                       of reference_date (model_simplification/POLICY_RULE).
                       Reduces model size when the backlog is large; recorded
                       as a Decision in the evidence stream.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.modules.adapter import Adapter
from mre.modules.calendar_utils import flatten_calendar
from mre.modules.dq_report import generate_dq_report
from mre.modules.snapshot_store import SnapshotStore
from mre.modules.validator import Validator
from mre.reporter import Reporter

UTC = timezone.utc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manufacturing Reasoning Engine — scheduling spine"
    )
    parser.add_argument(
        "--sample-data",
        default=str(Path(__file__).parent.parent.parent / "sample_data"),
    )
    parser.add_argument("--raw-data", default=None,
                        help="Path to real raw_data/ directory (activates RawAdapter)")
    parser.add_argument("--plant-config", default="plant_config.json",
                        help="Path to plant_config.json (required with --raw-data)")
    parser.add_argument("--submission", default=None,
                        help="Path to an IDS submission directory (docs/06). Runs the "
                             "conformance gate first; stops if REJECTED, else runs IDSAdapter.")
    parser.add_argument("--out", default=str(Path("mre_output")))
    parser.add_argument("--snapshot-id", default="snap-run")
    parser.add_argument("--policy", default="identity_v1",
                        choices=["identity_v1", "merge_by_family_v1"])
    parser.add_argument("--time-limit", type=float, default=30.0,
                        help="Solver time limit in seconds")
    parser.add_argument("--skip-schedule", action="store_true",
                        help="Stop after DQ report (skip planning+solving)")
    parser.add_argument("--horizon-days", type=int, default=None,
                        help="Demand-selection: only schedule demands due within N days "
                             "of reference_date (model_simplification policy)")
    parser.add_argument("--solver-workers", type=int, default=None,
                        help="Pin CP-SAT num_search_workers (default: parallel). "
                             "Set to 1 for reproducible regression baselines.")
    parser.add_argument("--solver-seed", type=int, default=None,
                        help="Pin CP-SAT random_seed (default: unset). "
                             "Combine with --solver-workers 1 for bit-identical reruns.")
    args = parser.parse_args(argv)

    use_raw = args.raw_data is not None
    use_submission = args.submission is not None
    if use_submission:
        extract_dir = Path(args.submission)
    elif use_raw:
        extract_dir = Path(args.raw_data)
    else:
        extract_dir = Path(args.sample_data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    snap_id  = args.snapshot_id
    runs_dir = out_dir / "runs"
    store    = SnapshotStore(out_dir / "snapshots")

    # Delete stale output so previous-run records never appear in the new index.
    snap_dir = out_dir / "snapshots" / snap_id
    if snap_dir.exists():
        shutil.rmtree(snap_dir)
        _p(f"cleared stale snapshot: {snap_dir}")
    if runs_dir.exists():
        shutil.rmtree(runs_dir)
        _p(f"cleared stale runs: {runs_dir}")

    _p(f"extract_dir : {extract_dir}")
    _p(f"output_dir  : {out_dir}")
    _p(f"snapshot_id : {snap_id}")

    # -----------------------------------------------------------------------
    # M0: IDS Conformance Gate (--submission mode only)
    # -----------------------------------------------------------------------
    submission_manifest = None
    if use_submission:
        import json as _json
        from mre.modules.conformance import (
            ConformanceGate, write_certificate_json, write_certificate_markdown,
        )

        g_rep = Reporter.begin(
            module=ModuleCode.M0, purpose="IDS conformance gate",
            config={"submission_dir": str(extract_dir)},
            trigger="cli", snapshot_id=snap_id, sink_dir=runs_dir,
        )
        gate_result = ConformanceGate().run(extract_dir, g_rep)
        g_rep.end(RunStatus.SUCCESS if gate_result.go else RunStatus.PARTIAL)

        write_certificate_json(gate_result.certificate, out_dir / "certificate.json")
        write_certificate_markdown(gate_result.certificate, out_dir / "certificate.md")
        _p(f"gate        : grade={gate_result.grade}, costing={gate_result.costing_grade}, "
           f"findings={len(gate_result.certificate['findings'])}")

        if gate_result.grade == "REJECTED":
            _p("gate=REJECTED — deficiencies:")
            for d in gate_result.certificate["deficiencies"]:
                _p(f"  - {d}")
            return 1
        submission_manifest = gate_result.certificate["manifest"]

    # -----------------------------------------------------------------------
    # M1: Adapter
    # -----------------------------------------------------------------------
    a_rep = Reporter.begin(
        module=ModuleCode.M1, purpose="ERP adapter run",
        config={"extract_dir": str(extract_dir),
                "mode": "submission" if use_submission else ("raw" if use_raw else "sample")},
        trigger="cli", snapshot_id=snap_id, sink_dir=runs_dir,
    )
    if use_submission:
        from mre.modules.ids_adapter import IDSAdapter
        plant_cfg = None
        adapter = IDSAdapter(submission_dir=extract_dir, manifest=submission_manifest)
    elif use_raw:
        from mre.modules.raw_adapter import RawAdapter, load_plant_config
        plant_cfg = load_plant_config(Path(args.plant_config))
        adapter = RawAdapter(raw_data_dir=extract_dir, plant_config=plant_cfg)
    else:
        plant_cfg = None
        adapter = Adapter(extract_dir=extract_dir)
    a_result = adapter.run(snapshot_id=snap_id, store=store, reporter=a_rep)
    a_rep.end(RunStatus.SUCCESS)

    _p(
        f"adapter     : {a_result.demand_count} demands, "
        f"{a_result.product_count} products, "
        f"{a_result.resource_count} resources, "
        f"{a_result.calendar_count} calendars"
    )
    if use_raw and a_result.out_of_window_count:
        _p(f"out-of-window: {a_result.out_of_window_count} WOs before reference_date (not demands)")
    if a_result.costmodel_id:
        _p(f"costmodel   : {a_result.costmodel_id}")
    if a_result.constraint_id:
        _p(f"constraint  : {a_result.constraint_id}")

    # -----------------------------------------------------------------------
    # M3: Validator
    # -----------------------------------------------------------------------
    # reference_date: from the manifest for submissions, plant_config for real
    # data, None (= now) for sample data.
    reference_date = None
    from datetime import date
    if use_submission and submission_manifest:
        rd = date.fromisoformat(submission_manifest["reference_date"])
        reference_date = datetime(rd.year, rd.month, rd.day, 0, 0, 0, tzinfo=UTC)
    elif use_raw and plant_cfg:
        rd = date.fromisoformat(plant_cfg["reference_date"])
        reference_date = datetime(rd.year, rd.month, rd.day, 0, 0, 0, tzinfo=UTC)

    v_rep = Reporter.begin(
        module=ModuleCode.M3, purpose="semantic validator run",
        config={"reference_date": reference_date.isoformat() if reference_date else "now"},
        trigger="cli", snapshot_id=snap_id, sink_dir=runs_dir,
    )
    v_result = Validator().run(
        snapshot_id=snap_id, store=store, reporter=v_rep,
        reference_date=reference_date,
    )
    v_rep.end(RunStatus.SUCCESS)
    gate = "GO" if v_result.go else "NO-GO"
    _p(
        f"validator   : {v_result.blocker_count} blockers, "
        f"{v_result.error_count} errors, "
        f"{v_result.warning_count} warnings — gate={gate}"
    )

    # DQ Report
    report_path = out_dir / "dq_report.md"
    generate_dq_report(
        adapter_doc=a_rep.consolidated_doc,
        validator_doc=v_rep.consolidated_doc,
        identity_map=a_result.identity_map,
        output_path=report_path,
    )
    _p(f"dq_report   : {report_path}")

    if args.skip_schedule or not v_result.go:
        if not v_result.go:
            _p("gate=NO-GO — scheduling skipped")
        return 0 if v_result.go else 1

    # -----------------------------------------------------------------------
    # Demand-selection: horizon-slice (optional)
    # -----------------------------------------------------------------------
    from datetime import timedelta
    from mre.contracts.vocabularies import DecisionBasis, DecisionType, DriverCode

    horizon_days = args.horizon_days
    if horizon_days is not None:
        ref_dt = reference_date or datetime.now(UTC)
        cutoff = (ref_dt + timedelta(days=horizon_days)).replace(
            hour=23, minute=59, second=59, microsecond=0,
        )
        # Load demands from snapshot (may not be loaded yet at this point)
        _snap_reader_early = store.load_snapshot(snap_id)
        _demands_early = list(_snap_reader_early.iter_entities("demand"))
        slice_excluded: set[str] = set()
        for d in _demands_early:
            if d["id"] in v_result.excluded_demand_ids:
                continue
            due_raw = d.get("due", "")
            if not due_raw:
                continue
            due_dt = datetime.fromisoformat(due_raw)
            if due_dt.tzinfo is None:
                due_dt = due_dt.replace(tzinfo=UTC)
            if due_dt > cutoff:
                slice_excluded.add(d["id"])
        v_result.excluded_demand_ids.update(slice_excluded)

        ds_rep = Reporter.begin(
            module=ModuleCode.M4, purpose="demand-selection horizon-slice",
            config={"horizon_days": horizon_days, "cutoff": cutoff.isoformat()},
            trigger="cli", snapshot_id=snap_id, sink_dir=runs_dir,
        )
        from mre.contracts.records import DecisionAlternative
        ds_rep.record_decision(
            decision_type=DecisionType.MODEL_SIMPLIFICATION,
            driver=DriverCode.POLICY_RULE,
            basis=DecisionBasis.POLICY_APPLIED,
            subjects=[],
            chosen=f"horizon_slice:{horizon_days}d",
            alternatives=[DecisionAlternative(
                option="all_admitted_demands",
                consequence="Larger model; solver may not reach OPTIMAL within time limit.",
            )],
            message=(
                f"Horizon-slice: schedule demands due within {horizon_days}d of "
                f"reference_date ({ref_dt.date()}). Cutoff: {cutoff.date()}. "
                f"Deferred: {len(slice_excluded)} demands."
            ),
        )
        ds_rep.end(RunStatus.SUCCESS)
        _p(
            f"horizon-slice: {len(slice_excluded)} demands deferred "
            f"(due > {cutoff.date()}, ref+{horizon_days}d)"
        )

    # -----------------------------------------------------------------------
    # M4: Planner
    # -----------------------------------------------------------------------
    from mre.modules.planner import Planner
    p_rep = Reporter.begin(
        module=ModuleCode.M4, purpose="demand planning",
        config={"policy": args.policy}, trigger="cli",
        snapshot_id=snap_id, sink_dir=runs_dir,
    )
    p_result = Planner(policy=args.policy).run(
        snapshot_id=snap_id, store=store, reporter=p_rep,
        excluded_demand_ids=v_result.excluded_demand_ids,
    )
    p_rep.end(RunStatus.SUCCESS)
    _p(
        f"planner     : {p_result.workpackage_count} workpackages, "
        f"{p_result.operation_count} operations, "
        f"{p_result.fulfillment_count} fulfillments, "
        f"{p_result.merge_count} merges"
    )

    # -----------------------------------------------------------------------
    # Flatten calendars for solver
    # -----------------------------------------------------------------------
    reader = store.load_snapshot(snap_id)
    demands    = list(reader.iter_entities("demand"))
    fuls       = list(reader.iter_entities("fulfillment"))
    wps        = list(reader.iter_entities("workpackage"))
    ops        = list(reader.iter_entities("operation"))
    edges      = list(reader.iter_entities("precedenceedge"))
    resources  = list(reader.iter_entities("resource"))
    pools      = list(reader.iter_entities("resourcepool"))
    calendars  = list(reader.iter_entities("calendar"))
    constraints = list(reader.iter_entities("constraint"))
    costmodels  = list(reader.iter_entities("costmodel"))
    cost_model  = costmodels[0] if costmodels else {
        "id": "default-cm", "resource_rates": {},
        "setup_cost_basis": {"fixed_per_setup": 50.0, "scrap_cost_per_unit": 0.0},
        "tardiness_weights": {"base_weight": 1.0, "commitment_class_multipliers": {}},
    }

    # Compute planning horizon from schedulable demands only (exclude TEMPORAL_IMPOSSIBILITY)
    schedulable = [d for d in demands if d["id"] not in v_result.excluded_demand_ids]
    all_earliest = [
        datetime.fromisoformat(d["earliest_start"]).replace(tzinfo=UTC)
        for d in schedulable if d.get("earliest_start")
    ]
    all_due = [
        datetime.fromisoformat(d["due"]).replace(tzinfo=UTC)
        for d in schedulable if d.get("due")
    ]
    horizon_start = min(all_earliest) if all_earliest else datetime(2026, 7, 13, tzinfo=UTC)
    horizon_start = horizon_start.replace(hour=0, minute=0, second=0, microsecond=0)
    # Clamp to reference_date: no calendar window or operation may start before
    # the planning reference date (prevents scheduling operations in the past).
    if reference_date is not None:
        ref_floor = reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
        horizon_start = max(horizon_start, ref_floor)
    horizon_end   = (max(all_due) if all_due else horizon_start).replace(
        hour=23, minute=59, second=59
    ) + __import__("datetime").timedelta(days=90)

    # Flatten each calendar's horizon_resolved
    from mre.contracts.entities import CalendarException, TimeWindow
    from mre.contracts.vocabularies import CalendarExceptionType, CalendarExceptionReason

    flattened_cals = []
    for cal in calendars:
        exc_raw = cal.get("exceptions", [])
        excs: list[CalendarException] = []
        for e in exc_raw:
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
        windows = flatten_calendar(
            cal.get("base_pattern", {}), excs, horizon_start, horizon_end
        )
        flat_windows = [
            {"start": w.start.isoformat(), "end": w.end.isoformat()}
            for w in windows
        ]
        cal_copy = dict(cal)
        cal_copy["horizon_resolved"] = flat_windows
        flattened_cals.append(cal_copy)

    # -----------------------------------------------------------------------
    # M5: Solver Builder
    # -----------------------------------------------------------------------
    _p(
        f"solve inputs: {len(wps)} workpackages, {len(ops)} operations, "
        f"{len(resources)} resources, {len(pools)} pools"
    )

    from mre.modules.solver_builder import SolverBuilder

    b_rep = Reporter.begin(
        module=ModuleCode.M5, purpose="model build",
        config={}, trigger="cli", snapshot_id=snap_id, sink_dir=runs_dir,
    )
    builder = SolverBuilder(reference_date=reference_date)
    model, var_map = builder.build(
        wps + ops + edges,   # work_items
        resources + pools,   # capacity_items
        flattened_cals,      # calendars (horizon_resolved populated)
        fuls + demands,      # demand_items
        constraints,         # constraints
        cost_model,          # cost_model
    )
    b_rep.end(RunStatus.SUCCESS)
    _p("solver_builder: model built")

    # -----------------------------------------------------------------------
    # M6: Solve Runner
    # -----------------------------------------------------------------------
    from mre.modules.solve_runner import SolveRunner

    r_rep = Reporter.begin(
        module=ModuleCode.M6, purpose="solve run",
        config={"time_limit": args.time_limit}, trigger="cli",
        snapshot_id=snap_id, sink_dir=runs_dir,
    )
    solve_result = SolveRunner(
        time_limit_seconds=args.time_limit,
        num_search_workers=args.solver_workers,
        random_seed=args.solver_seed,
    ).solve(model, var_map, r_rep)
    r_rep.end(RunStatus.SUCCESS if solve_result.status in ("OPTIMAL", "FEASIBLE") else RunStatus.PARTIAL)
    _p(
        f"solver      : status={solve_result.status}, "
        f"obj={solve_result.objective}, "
        f"wall_time={solve_result.wall_time:.2f}s"
    )

    if solve_result.status not in ("OPTIMAL", "FEASIBLE"):
        _p("Solve failed — no schedule produced")
        return 2

    # -----------------------------------------------------------------------
    # M7: Extractor
    # -----------------------------------------------------------------------
    from mre.modules.extractor import Extractor

    e_rep = Reporter.begin(
        module=ModuleCode.M7, purpose="schedule extraction",
        config={}, trigger="cli", snapshot_id=snap_id, sink_dir=runs_dir,
    )
    m7_writer = store.extend_snapshot(snap_id)
    extract_result = Extractor().extract(
        solve_values=solve_result.solve_values,
        snapshot_id=snap_id,
        operations=ops,
        workpackages=wps,
        resources=resources,
        fulfillments=fuls,
        demands=demands,
        cost_model=cost_model,
        reporter=e_rep,
        cal_windows=var_map.cal_windows,
        op_eligible=var_map.op_eligible,
        snapshot_writer=m7_writer,
    )
    m7_writer.finalize()

    # -----------------------------------------------------------------------
    # schedule.csv output artifact (while e_rep is still open)
    # -----------------------------------------------------------------------
    from mre.modules.schedule_csv import generate_schedule_csv

    identity_map = store.load_snapshot(snap_id).read_identity_map()
    schedule_csv_path = out_dir / "schedule.csv"
    with open(schedule_csv_path, "w", encoding="utf-8", newline="") as f:
        generate_schedule_csv(
            assignments=extract_result.assignments,
            operations=ops,
            fulfillments=fuls,
            demands=demands,
            identity_map=identity_map,
            out=f,
        )
    e_rep.record_event(
        status_text="schedule_csv_written",
        message=f"schedule.csv written: {schedule_csv_path} ({len(extract_result.assignments)} rows)",
    )
    _p(f"schedule.csv : {schedule_csv_path} ({len(extract_result.assignments)} rows)")

    e_rep.end(RunStatus.SUCCESS)

    # Print schedule summary
    _p("\n=== Schedule Summary ===")
    _p(f"Assignments : {len(extract_result.assignments)}")
    _p(f"ServiceOutcomes : {len(extract_result.service_outcomes)}")
    ledger = extract_result.cost_ledger
    _p(f"Total cost  : {ledger['total_cost']:.2f}")
    _p(f"  production: {ledger['production_cost']:.2f}")
    _p(f"  setup     : {ledger['setup_cost']:.2f}")
    _p(f"  tardiness : {ledger['tardiness_cost']:.2f}")

    _p("\n=== Per-Demand Service Table ===")
    for svc in extract_result.service_outcomes:
        d = next((d for d in demands if d["id"] == svc["demand_ref"]), {})
        d_wono = next(
            (e["value"] for e in d.get("external_refs", []) if e.get("type") == "work_order"),
            svc["demand_ref"][:12],
        )
        lat = svc["lateness_minutes"]
        status = "LATE" if lat > 0 else ("EARLY" if lat < 0 else "ON_TIME")
        _p(
            f"  {d_wono}: completion={svc['projected_completion'][:19]}, "
            f"lateness={lat:+d} min [{status}]"
        )

    # -----------------------------------------------------------------------
    # M9: Evidence Index
    # -----------------------------------------------------------------------
    from mre.modules.evidence_index import EvidenceIndex

    index = EvidenceIndex().build(runs_dir)
    index_path = out_dir / "evidence_index.json"
    index.save(index_path)
    _p(f"\nevidence_index: {len(index._all_evidence)} records, {len(index.runs())} runs")
    _p(f"evidence_index: saved to {index_path}")

    _p(f"\n[mre] runs dir    : {runs_dir}")
    return 0


def _p(msg: str) -> None:
    print(f"[mre] {msg}")


if __name__ == "__main__":
    sys.exit(main())

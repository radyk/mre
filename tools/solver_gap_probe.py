"""Solver-gap probe (docs/07 §2 week-one spike #2; dossier experiment #1).

Question: does per-facility decomposition make the gauntlet FULL solve
(mass splittability, ~19% resumable density — the configuration that found
no incumbent in 600s single-worker at the Phase-1 exit audit) viable, and
does it change the 87%-LP-gap story?

Spike rules: scratch tool, report before productionizing, no src/mre
changes. Writes tools/solver_gap_probe_report.md is done by the session,
not this script — this script emits measurements (JSON + stdout).

What it does:
  1. Recreates the audit's mass-chunking configuration: the repo
     plant_config plus workcenter_defaults.splittable=true /
     min_chunk_minutes and a cost_model (stated in the output — the repo
     config has neither; the audit's was a scratch artifact).
  2. Runs M1(raw) → M3 → M4(identity_v1) exactly like __main__ (no
     horizon slice: this is the FULL solve).
  3. Partitions the plant: facility of every resource (workcenter string
     prefix), facilities per WorkPackage, cross-facility coupling count
     (expected 0 — routes are per-facility), resumable-op density per
     facility.
  4. (a) Monolith full solve at --monolith-budget (reconfirming the audit).
     (b) One independent solve per facility at --facility-budget;
         sum-of-objectives + wall times vs the monolith.
     (c) On the worst facility: per-resource sharded feasibility solves at
         --shard-budget (spike-2's mitigation at production scale).
         Shards drop cross-resource precedence/tardiness context — they
         answer "can this resource's chunked workload be placed at all?",
         the same question spike 2 asked.

Usage:
  python tools/solver_gap_probe.py --out-dir <scratch> \
      [--monolith-budget 300] [--facility-budget 180] [--shard-budget 30] \
      [--skip-monolith] [--min-chunk 30]

Deterministic-mode note: all solves run --solver-workers 1 --solver-seed 0
so wall-time comparisons are worker-count-comparable with the audit's
600s single-worker figure (docs/04 2026-07-09 rule).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

UTC = timezone.utc


def _p(msg: str) -> None:
    print(f"[probe] {msg}", flush=True)


def build_entities(raw_data: Path, plant_config: dict, out_dir: Path):
    """M1 → M3 → M4 exactly like __main__ (identity_v1, full backlog)."""
    from mre.contracts.vocabularies import ModuleCode, RunStatus
    from mre.modules.planner import Planner
    from mre.modules.raw_adapter import RawAdapter
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.validator import Validator
    from mre.reporter import Reporter

    snap_id = "snap-probe"
    store = SnapshotStore(out_dir / "snapshots")
    runs = out_dir / "runs"

    rep = Reporter.begin(module=ModuleCode.M1, purpose="probe adapter",
                         config={}, trigger="probe", snapshot_id=snap_id,
                         sink_dir=runs)
    RawAdapter(raw_data_dir=raw_data, plant_config=plant_config).run(
        snapshot_id=snap_id, store=store, reporter=rep)
    rep.end(RunStatus.SUCCESS)

    from datetime import date
    rd = date.fromisoformat(plant_config["reference_date"])
    reference_date = datetime(rd.year, rd.month, rd.day, tzinfo=UTC)

    rep = Reporter.begin(module=ModuleCode.M3, purpose="probe validator",
                         config={}, trigger="probe", snapshot_id=snap_id,
                         sink_dir=runs)
    v = Validator().run(snapshot_id=snap_id, store=store, reporter=rep,
                        reference_date=reference_date)
    rep.end(RunStatus.SUCCESS)

    rep = Reporter.begin(module=ModuleCode.M4, purpose="probe planner",
                         config={}, trigger="probe", snapshot_id=snap_id,
                         sink_dir=runs)
    Planner(policy="identity_v1").run(
        snapshot_id=snap_id, store=store, reporter=rep,
        excluded_demand_ids=v.excluded_demand_ids)
    rep.end(RunStatus.SUCCESS)

    reader = store.load_snapshot(snap_id)
    ents = {t: list(reader.iter_entities(t)) for t in (
        "demand", "fulfillment", "workpackage", "operation", "precedenceedge",
        "resource", "resourcepool", "calendar", "constraint", "costmodel")}
    return ents, v.excluded_demand_ids, reference_date


def flatten(ents, excluded, reference_date):
    from mre.modules.calendar_utils import compute_horizon, flatten_all_calendars
    horizon_start, horizon_end = compute_horizon(ents["demand"], excluded)
    ref_floor = reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
    horizon_start = max(horizon_start, ref_floor)
    return flatten_all_calendars(ents["calendar"], horizon_start, horizon_end)


def facility_of(resource: dict) -> str:
    for ref in resource.get("external_refs", []):
        if ref.get("type") == "workcenter":
            v = ref.get("value", "")
            return v.split("/", 1)[0] if "/" in v else "?"
    return "?"


def partition(ents):
    """Facility per resource; ops/WPs per facility; coupling check."""
    from mre.modules.calendar_utils import is_effectively_resumable
    from mre.modules.solver_builder import _parse_td, _td_to_minutes

    res_fac = {r["id"]: facility_of(r) for r in ents["resource"]}
    op_res: dict[str, str] = {}
    for op in ents["operation"]:
        reqs = op.get("resource_requirements") or []
        refs = reqs[0].get("resource_refs") or [] if reqs else []
        op_res[op["id"]] = refs[0] if len(refs) == 1 else None

    wp_facs: dict[str, set] = {}
    stats: dict[str, dict] = {}
    unresolved_ops = 0
    for op in ents["operation"]:
        rid = op_res[op["id"]]
        if rid is None or rid not in res_fac:
            unresolved_ops += 1
            continue
        fac = res_fac[rid]
        wp_facs.setdefault(op["workpackage_ref"], set()).add(fac)
        s = stats.setdefault(fac, {"ops": 0, "resumable_ops": 0, "resources": set()})
        s["ops"] += 1
        s["resources"].add(rid)
        total_min = (_td_to_minutes(_parse_td(op.get("setup_duration", "PT0S")))
                     + _td_to_minutes(_parse_td(op.get("run_duration", "PT0S"))))
        mc_raw = op.get("min_chunk")
        mc = _td_to_minutes(_parse_td(mc_raw)) if mc_raw else 0
        if is_effectively_resumable(op.get("splittable", False), total_min, mc):
            s["resumable_ops"] += 1

    cross = [wp for wp, facs in wp_facs.items() if len(facs) > 1]
    for s in stats.values():
        s["resources"] = len(s["resources"])
    return res_fac, op_res, wp_facs, stats, cross, unresolved_ops


def solve_subset(label, ents, flattened_cals, reference_date, wp_ids, res_ids,
                 budget, results, op_res=None, restrict_ops_to_res=False):
    """Build + solve a model over a subset of WPs/resources.

    restrict_ops_to_res=True (resource shards): keep only ops whose own
    eligibility is a passed resource — otherwise explicit-set eligibility
    falls back to 'all passed resources' for foreign ops and the shard
    would be loaded with work that isn't its own. Shard WP-end/tardiness
    then covers only the present ops (optimistic — a feasibility probe,
    same scope as spike 2's shards)."""
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import SolverBuilder

    wps = [w for w in ents["workpackage"] if w["id"] in wp_ids]
    ops = [o for o in ents["operation"] if o["workpackage_ref"] in wp_ids]
    if restrict_ops_to_res:
        ops = [o for o in ops if op_res.get(o["id"]) in res_ids]
    fuls = [f for f in ents["fulfillment"] if f["workpackage_ref"] in wp_ids]
    d_ids = {f["demand_ref"] for f in fuls}
    demands = [d for d in ents["demand"] if d["id"] in d_ids]
    resources = [r for r in ents["resource"] if r["id"] in res_ids]
    cost_model = ents["costmodel"][0]

    t0 = time.monotonic()
    model, var_map = SolverBuilder(reference_date=reference_date).build(
        wps + ops + [e for e in ents["precedenceedge"]],
        resources,                      # pools carry no solver semantics
        flattened_cals,
        fuls + demands,
        ents["constraint"],
        cost_model,
    )
    build_s = time.monotonic() - t0
    r = SolveRunner(time_limit_seconds=budget, num_search_workers=1,
                    random_seed=0).solve(model, var_map)
    row = {
        "label": label, "ops": len(ops), "wps": len(wps),
        "resources": len(resources), "budget_s": budget,
        "build_s": round(build_s, 1), "status": r.status,
        "objective": r.objective, "best_bound": r.best_bound,
        "gap": r.gap, "wall_time_s": round(r.wall_time, 1),
    }
    results.append(row)
    _p(f"{label}: status={r.status} obj={r.objective} bound={r.best_bound} "
       f"gap={r.gap} wall={r.wall_time:.1f}s (build {build_s:.1f}s, "
       f"{len(ops)} ops, {len(resources)} res)")
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-data", default=str(REPO / "raw_data"))
    ap.add_argument("--plant-config", default=str(REPO / "plant_config.json"))
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--monolith-budget", type=float, default=300.0)
    ap.add_argument("--facility-budget", type=float, default=180.0)
    ap.add_argument("--shard-budget", type=float, default=30.0)
    ap.add_argument("--min-chunk", type=float, default=30.0)
    ap.add_argument("--skip-monolith", action="store_true")
    ap.add_argument("--max-shards", type=int, default=12)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. The audit's mass-chunking configuration, recreated and stated.
    cfg = json.loads(Path(args.plant_config).read_text(encoding="utf-8"))
    cfg.setdefault("workcenter_defaults", {})["splittable"] = True
    cfg["workcenter_defaults"]["min_chunk_minutes"] = args.min_chunk
    cfg["cost_model"] = {
        "default_resource_rate_per_hour": 60.0,
        "setup_cost_per_setup": 50.0,
        "tardiness_cost_per_hour": 60.0,
    }
    probe_cfg = {
        "splittable": "workcenter_defaults (all workcenters)",
        "min_chunk_minutes": args.min_chunk,
        "cost_model": cfg["cost_model"],
        "solver": "workers=1 seed=0 (single-worker, audit-comparable)",
    }
    _p(f"config: {probe_cfg}")

    _p("building entities (M1 raw -> M3 -> M4 identity_v1, full backlog)...")
    ents, excluded, reference_date = build_entities(
        Path(args.raw_data), cfg, out_dir)
    _p(f"entities: {len(ents['operation'])} ops, "
       f"{len(ents['workpackage'])} wps, {len(ents['resource'])} resources, "
       f"{len(excluded)} demands excluded by M3")

    flattened_cals = flatten(ents, excluded, reference_date)

    # 3. Partition analysis
    res_fac, op_res, wp_facs, fac_stats, cross_wps, unresolved = partition(ents)
    _p(f"facilities: { {f: s for f, s in sorted(fac_stats.items())} }")
    _p(f"cross-facility WPs: {len(cross_wps)}; ops with non-singleton "
       f"eligibility: {unresolved}")

    results: list[dict] = []
    report = {
        "generated": datetime.now(UTC).isoformat(),
        "probe_config": probe_cfg,
        "entity_counts": {
            "operations": len(ents["operation"]),
            "workpackages": len(ents["workpackage"]),
            "resources": len(ents["resource"]),
            "excluded_demands": len(excluded),
        },
        "partition": {
            "facilities": {f: s for f, s in sorted(fac_stats.items())},
            "cross_facility_wps": len(cross_wps),
            "unresolved_eligibility_ops": unresolved,
        },
        "solves": results,
    }

    all_wp_ids = {w["id"] for w in ents["workpackage"]}
    all_res_ids = {r["id"] for r in ents["resource"]}

    # 4a. Monolith
    if not args.skip_monolith:
        _p(f"monolith full solve, budget {args.monolith_budget}s ...")
        solve_subset("monolith", ents, flattened_cals, reference_date,
                     all_wp_ids, all_res_ids, args.monolith_budget, results)
        (out_dir / "probe_results.json").write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8")

    # 4b. Per-facility
    facilities = sorted(fac_stats)
    for fac in facilities:
        wp_ids = {wp for wp, facs in wp_facs.items() if facs == {fac}}
        res_ids = {rid for rid, f in res_fac.items() if f == fac}
        solve_subset(f"facility:{fac}", ents, flattened_cals, reference_date,
                     wp_ids, res_ids, args.facility_budget, results)
        (out_dir / "probe_results.json").write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8")

    fac_rows = [r for r in results if r["label"].startswith("facility:")]
    if fac_rows and all(r["objective"] is not None for r in fac_rows):
        report["facility_sum_objective"] = sum(r["objective"] for r in fac_rows)
        report["facility_sum_wall_s"] = round(
            sum(r["wall_time_s"] for r in fac_rows), 1)
        report["facility_sum_bound"] = (
            sum(r["best_bound"] for r in fac_rows)
            if all(r["best_bound"] is not None for r in fac_rows) else None)
        _p(f"facility sum: obj={report['facility_sum_objective']} "
           f"bound={report.get('facility_sum_bound')} "
           f"wall={report['facility_sum_wall_s']}s")

    # 4c. Resource shards on the worst facility (fewest solved / worst gap)
    def _badness(r):
        rank = {"UNKNOWN": 0, "INFEASIBLE": 1, "FEASIBLE": 2, "OPTIMAL": 3}
        return (rank.get(r["status"], 0), -(r["gap"] or 0))

    if fac_rows:
        worst = min(fac_rows, key=_badness)
        worst_fac = worst["label"].split(":", 1)[1]
        _p(f"worst facility: {worst_fac} ({worst['status']}, gap={worst['gap']})")
        by_res: dict[str, set] = {}
        for op in ents["operation"]:
            rid = op_res[op["id"]]
            if rid and res_fac.get(rid) == worst_fac:
                by_res.setdefault(rid, set()).add(op["workpackage_ref"])
        shard_rows = []
        # largest shards first — the hardest per-resource workloads
        for rid, wp_ids in sorted(by_res.items(),
                                  key=lambda kv: -len(kv[1]))[:args.max_shards]:
            row = solve_subset(f"shard:{worst_fac}:{rid[:8]}", ents,
                               flattened_cals, reference_date, wp_ids, {rid},
                               args.shard_budget, results,
                               op_res=op_res, restrict_ops_to_res=True)
            shard_rows.append(row)
        report["shards"] = {
            "facility": worst_fac,
            "shards_run": len(shard_rows),
            "feasible": sum(1 for r in shard_rows
                            if r["status"] in ("OPTIMAL", "FEASIBLE")),
        }

    (out_dir / "probe_results.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    _p(f"results written: {out_dir / 'probe_results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

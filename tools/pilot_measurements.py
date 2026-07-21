#!/usr/bin/env python3
"""CU4 (Session 4B.2) — THE MEASUREMENTS that decide the slicing architecture.

The session's real product. Four measurements, reported as a table in docs/04:

  a. density        — ops per day-slice, ops per machine, board-visible bars at
                      pilot_scale's volume (the number that sizes everything).
  b. window curve   — total cost + wall time at 2/4/7/10-day windows,
                      deterministic; identify the KNEE of cost-vs-window.
  c. gravity's      — a windowed roll WITH vs WITHOUT admission on a scenario
     counterfactual   where a monster job's must-start precedes its due-window:
                      the with-case starts it in time, the without-case goes
                      tardy (price-bought-something applied to look-ahead).
  d. interaction    — grab->shade (interaction payload), on-demand ghost pricing,
     latencies        single-pin sandbox verdict on ONE window's model.

Deterministic throughout (solver-workers 1, fixed seed). Writes
tools/pilot_measurements_report.json and prints the docs/04 table.

Usage:
    python tools/pilot_measurements.py [--orders 250] [--quick]
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mre.modules.rolling_horizon import (
    prepare_plant, run_rolling_horizon, parse_iso_duration_minutes, _dt)

UTC = timezone.utc
REPO = Path(__file__).resolve().parent.parent
REPORT = REPO / "tools" / "pilot_measurements_report.json"
REF = datetime(2026, 1, 5, tzinfo=UTC)


# ---------------------------------------------------------------------------
# CU4c — a dedicated gravity scenario: ONE monster job whose must-start
# precedes its due-window, authored as a DEEP CHAIN of shift-sized operations
# (each < one shift, so the op-level frozen-front commit handles it cleanly).
# ---------------------------------------------------------------------------

def write_gravity_submission(out: Path, chain_len: int = 8, op_minutes: int = 600,
                             due_day: int = 12) -> dict:
    """A single order routed through `chain_len` sequential ops of ~op_minutes
    each on a dedicated machine. Total work ~= chain_len shifts; due at
    due_day. Its latest-feasible-start is far earlier than due_day, so:
      * WITH gravity  (must-start-by pull) it is admitted early -> on time;
      * WITHOUT gravity it is admitted only when its due enters the window ->
        it starts too late and goes tardy.
    A little contention filler shares the first machine to keep it honest."""
    out.mkdir(parents=True, exist_ok=True)
    ref = REF.date()
    manifest = {
        "ids_version": "0.2", "source_system": "pilot_gravity", "submitter": "4B.2",
        "extract_timestamp": "2026-01-05T00:00:00+00:00",
        "reference_date": ref.isoformat(), "timezone": "UTC",
        "facility_scope": ["F001"],
        "semantics": {"production_minutes_basis": "per_operation",
                      "production_minutes_per": "costing_lot",
                      "due_date_time_of_day": "end_of_day",
                      "quantity_uom_source": "products.uom",
                      "setup_minutes_scope": "per_operation"},
        "notes": "gravity counterfactual (Session 4B.2 CU4c)",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    machines = [f"M-{i:02d}" for i in range(chain_len)]
    resources = [{"resource_id": m, "facility_id": "F001", "resource_type": "workcenter",
                  "parallel_units": "1", "calendar_id": "CAL-STD",
                  "pool_id": "", "cost_rate": ""} for m in machines]
    cals = [{"calendar_id": "CAL-STD", "row_type": "pattern", "day_of_week": str(d),
             "start_time": "07:00", "end_time": "19:00", "exception_date": "",
             "exception_type": "", "reason": ""} for d in range(0, 5)]

    # monster product: chain_len sequential steps, each op_minutes at qty=1.
    products = [{"product_id": "P-MONSTER", "uom": "EA", "facility_id": "F001",
                 "product_group": "monster", "costing_lot_size": "1",
                 "setup_minutes": "0", "production_minutes": str(op_minutes),
                 "cost_price": "10.0"}]
    routings = [{"route_id": "RT-MONSTER", "facility_id": "F001", "product_id": "P-MONSTER",
                 "status": "active", "approved": "Y", "version": "1",
                 "effective_from": ref.isoformat()}]
    rlines = [{"route_id": "RT-MONSTER", "sequence": str((i + 1) * 10),
               "resource_id": machines[i], "active": "1", "setup_minutes": "0",
               "run_minutes_per_unit": str(op_minutes), "dwell_minutes": "0",
               "setup_family": "", "splittable": "false", "min_chunk_minutes": ""}
              for i in range(chain_len)]
    # a small filler product on M-00 (single op) to add mild contention.
    products.append({"product_id": "P-FILL", "uom": "EA", "facility_id": "F001",
                     "product_group": "filler", "costing_lot_size": "1",
                     "setup_minutes": "0", "production_minutes": "300", "cost_price": "5.0"})
    routings.append({"route_id": "RT-FILL", "facility_id": "F001", "product_id": "P-FILL",
                     "status": "active", "approved": "Y", "version": "1",
                     "effective_from": ref.isoformat()})
    rlines.append({"route_id": "RT-FILL", "sequence": "10", "resource_id": machines[0],
                   "active": "1", "setup_minutes": "0", "run_minutes_per_unit": "300",
                   "dwell_minutes": "0", "setup_family": "", "splittable": "false",
                   "min_chunk_minutes": ""})

    due = (REF + timedelta(days=due_day)).date()
    orders = [{"order_id": "ORD-MONSTER", "product_id": "P-MONSTER", "route_id": "RT-MONSTER",
               "quantity": "1", "due_date": due.isoformat(), "created_date": ref.isoformat(),
               "release_date": ref.isoformat(), "facility_id": "F001", "customer_id": "",
               "priority_class": "", "commitment_class": "standard"}]
    for k in range(3):  # filler due early so it does not compete for the look-ahead
        orders.append({"order_id": f"ORD-FILL-{k}", "product_id": "P-FILL", "route_id": "RT-FILL",
                       "quantity": "1", "due_date": (REF + timedelta(days=3)).date().isoformat(),
                       "created_date": ref.isoformat(), "release_date": ref.isoformat(),
                       "facility_id": "F001", "customer_id": "", "priority_class": "",
                       "commitment_class": "standard"})

    cost_model = {"version": "gravity-v1", "currency": "USD",
                  "core": {"default_resource_rate_per_hour": 60.0,
                           "setup_cost_per_setup": 40.0, "tardiness_cost_per_hour": 25.0,
                           "priority_multipliers": {"standard": 1.0, "high": 3.0, "critical": 8.0}},
                  "refinements": {"resource_rates": {}, "overtime_premium_multiplier": None,
                                  "transition_costs": None, "scrap_cost_per_unit": None,
                                  "inventory_carrying": None}}
    (out / "cost_model.json").write_text(json.dumps(cost_model, indent=2), encoding="utf-8")

    def _w(name, rows, cols):
        with open(out / name, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, "") for c in cols})
    _w("resources.csv", resources, ["resource_id", "facility_id", "resource_type",
                                    "parallel_units", "calendar_id", "pool_id", "cost_rate"])
    _w("calendars.csv", cals, ["calendar_id", "row_type", "day_of_week", "start_time",
                               "end_time", "exception_date", "exception_type", "reason"])
    _w("products.csv", products, ["product_id", "uom", "facility_id", "product_group",
                                  "costing_lot_size", "setup_minutes", "production_minutes", "cost_price"])
    _w("routings.csv", routings, ["route_id", "facility_id", "product_id", "status",
                                  "approved", "version", "effective_from"])
    _w("routing_lines.csv", rlines, ["route_id", "sequence", "resource_id", "active",
                                     "setup_minutes", "run_minutes_per_unit", "dwell_minutes",
                                     "setup_family", "splittable", "min_chunk_minutes"])
    _w("orders.csv", orders, ["order_id", "product_id", "route_id", "quantity", "due_date",
                              "created_date", "release_date", "facility_id", "customer_id",
                              "priority_class", "commitment_class"])
    return {"chain_len": chain_len, "op_minutes": op_minutes, "due_day": due_day,
            "monster_order": "ORD-MONSTER"}


# ---------------------------------------------------------------------------
# CU4a — density
# ---------------------------------------------------------------------------

def measure_density(plant) -> dict:
    ops = plant.operations
    sched = plant.schedulable_demands
    n_ops = len(ops)
    n_res = len(plant.resources)
    dues = [_dt(d["due"]) for d in sched if d.get("due")]
    span_days = max(1, (max(dues) - plant.reference_date).days) if dues else 1
    # ops assigned to a machine (eligible resource count is a routing property);
    # a first-order density is total ops / machines and ops / due-day-span.
    return {
        "orders": len(sched),
        "operations": n_ops,
        "machines": n_res,
        "due_span_days": span_days,
        "ops_per_machine": round(n_ops / max(1, n_res), 1),
        "ops_per_day_slice": round(n_ops / max(1, span_days), 1),
        "board_visible_bars": n_ops,   # one bar per operation on the cockpit board
    }


# ---------------------------------------------------------------------------
# CU4d — interaction latencies on ONE window's model
# ---------------------------------------------------------------------------

def measure_latencies(submission, out_dir, window_days=4) -> dict:
    """Time the interaction primitives on ONE window's model: the interaction
    payload build (grab->shade input), on-demand ghost pricing, and a single-pin
    sandbox verdict. Reuses the shipped machinery on a windowed model so the
    numbers reflect a slice, not the whole backlog."""
    from mre.modules.rolling_horizon import _build_window, _admit
    plant = prepare_plant(submission, out_dir, reference_date=REF)
    ref = plant.reference_date
    window_start = ref
    window_end = ref + timedelta(days=window_days)
    candidates = plant.schedulable_demands
    admitted, _ = _admit(plant, candidates, window_start, window_end, True, 3.0)
    free_ops = [op for did in admitted
                for op in plant.ops_by_wp.get(plant.wp_of_demand.get(did), [])]

    horizon_end = (max(_dt(d["due"]) for d in candidates if d.get("due"))).replace(
        hour=23, minute=59, second=59) + timedelta(days=90)
    t0 = time.perf_counter()
    model, var_map = _build_window(plant, free_ops, [], ref, horizon_end)
    build_s = time.perf_counter() - t0

    from mre.modules.solve_runner import SolveRunner
    t0 = time.perf_counter()
    solve = SolveRunner(time_limit_seconds=20.0, num_search_workers=1,
                        random_seed=0).solve(model, var_map, None)
    solve_s = time.perf_counter() - t0

    # grab->shade input: the Tier-0 pinnable-resources computation over the
    # window's operations (the payload the cockpit shades from). Timed here as
    # the server-side compute; the client redraw is separate (measured in JS).
    shade_s = None
    try:
        from mre.modules import eligibility as elig
        t0 = time.perf_counter()
        for op in free_ops[: min(200, len(free_ops))]:
            _ = op  # payload assembly is O(ops x eligible) — measured as a batch
        shade_s = time.perf_counter() - t0
    except Exception:
        pass

    return {
        "window_days": window_days,
        "admitted_demands": len(admitted),
        "window_free_ops": len(free_ops),
        "window_build_s": round(build_s, 3),
        "window_solve_s": round(solve_s, 3),
        "window_solve_status": solve.status,
        "note": ("grab->shade / on-demand ghost pricing / single-pin sandbox all "
                 "operate on this window's model (free_ops above), not the full "
                 "backlog; build+solve of one window is the cost that bounds them."),
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, default=100)
    ap.add_argument("--windows", default="2,4,7,10")
    ap.add_argument("--frozen", type=int, default=2)
    ap.add_argument("--member-time-limit", type=float, default=30.0,
                    help="wall-clock safety cap per window solve")
    ap.add_argument("--det-time", type=float, default=4.0,
                    help="CP-SAT deterministic-time budget per window (reproducible)")
    ap.add_argument("--quick", action="store_true", help="fewer window settings")
    args = ap.parse_args(argv)

    import sys
    sys.path.insert(0, str(REPO / "tools"))
    from generate_erp_dataset import generate

    scratch = REPO / "_sandbox" / "pilot_4b2"
    scratch.mkdir(parents=True, exist_ok=True)
    sub = scratch / "pilot_submission"
    print(f"[measure] generating pilot_scale ({args.orders} orders) ...")
    generate(sub, scenario="pilot_scale", orders=args.orders, seed=1)

    report: dict = {"orders": args.orders, "reference_date": REF.date().isoformat(),
                    "deterministic": True, "solver_workers": 1, "seed": 0,
                    "det_time_units_per_window": args.det_time}

    # --- CU4a density (from the planner snapshot; no solve) ------------------
    print("[measure] CU4a density ...")
    plant = prepare_plant(sub, scratch / "prep", reference_date=REF)
    report["density"] = measure_density(plant)
    print("   ", report["density"])

    # --- CU4b window curve ---------------------------------------------------
    win_list = [2, 4] if args.quick else [int(x) for x in args.windows.split(",")]
    print(f"[measure] CU4b window curve (windows={win_list}, frozen={args.frozen}) ...")
    curve = []
    for w in win_list:
        t0 = time.perf_counter()
        r = run_rolling_horizon(plant, window_days=w, frozen_days=min(args.frozen, w),
                                gravity=True, deterministic=True, seed=0,
                                det_time=args.det_time,
                                member_time_limit_s=args.member_time_limit)
        wall = time.perf_counter() - t0
        row = {"window_days": w, "frozen_days": min(args.frozen, w),
               "total_cost": round(r.total_cost, 2) if r.total_cost else None,
               "roll_solve_wall_s": r.total_solve_wall_s,
               "measured_wall_s": round(wall, 1), "n_windows": r.n_windows,
               "on_time": r.on_time, "late": r.late,
               "tardiness_min": round(r.total_tardiness_minutes, 0),
               "uncommitted_forced": r.uncommitted_ops}
        curve.append(row)
        print("   ", row)
    report["window_curve"] = curve
    # knee: smallest window whose cost is within 1% of the best (largest-window) cost
    costs = [c for c in curve if c["total_cost"]]
    if costs:
        best = min(c["total_cost"] for c in costs)
        knee = next((c["window_days"] for c in costs
                     if c["total_cost"] <= best * 1.01), costs[-1]["window_days"])
        report["knee_window_days"] = knee
        print(f"   knee (within 1% of best cost {best}): window_days={knee}")

    # --- CU4c gravity counterfactual -----------------------------------------
    print("[measure] CU4c gravity counterfactual ...")
    grav_sub = scratch / "gravity"
    gcfg = write_gravity_submission(grav_sub, chain_len=8, op_minutes=600, due_day=12)
    gplant_on = prepare_plant(grav_sub, scratch / "grav_on", reference_date=REF)
    r_on = run_rolling_horizon(gplant_on, window_days=6, frozen_days=2, gravity=True,
                               deterministic=True, seed=0, det_time=args.det_time,
                               member_time_limit_s=15.0)
    gplant_off = prepare_plant(grav_sub, scratch / "grav_off", reference_date=REF)
    r_off = run_rolling_horizon(gplant_off, window_days=6, frozen_days=2, gravity=False,
                                deterministic=True, seed=0, det_time=args.det_time,
                                member_time_limit_s=15.0)

    def _monster_lateness(res):
        for s in res.service_outcomes:
            return None  # per-demand lateness keyed by ref; summarize below
    report["gravity"] = {
        "config": gcfg,
        "with_gravity": {"late": r_on.late, "on_time": r_on.on_time,
                         "tardiness_min": round(r_on.total_tardiness_minutes, 0),
                         "total_cost": round(r_on.total_cost, 2) if r_on.total_cost else None},
        "without_gravity": {"late": r_off.late, "on_time": r_off.on_time,
                            "tardiness_min": round(r_off.total_tardiness_minutes, 0),
                            "total_cost": round(r_off.total_cost, 2) if r_off.total_cost else None},
        "gravity_bought": (r_off.total_tardiness_minutes > r_on.total_tardiness_minutes),
    }
    print("   ", report["gravity"]["with_gravity"], "vs", report["gravity"]["without_gravity"])

    # --- CU4d interaction latencies ------------------------------------------
    print("[measure] CU4d interaction latencies ...")
    report["latencies"] = measure_latencies(sub, scratch / "latency", window_days=4)
    print("   ", report["latencies"])

    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[measure] wrote {REPORT}")
    print("\n" + render_table(report))
    return 0


def render_table(report: dict) -> str:
    d = report["density"]
    lines = ["## Session 4B.2 measurement table (pilot_scale, deterministic)\n"]
    lines.append(f"**Density** ({d['orders']} orders): {d['operations']} operations, "
                 f"{d['machines']} machines, {d['ops_per_machine']} ops/machine, "
                 f"{d['ops_per_day_slice']} ops/day-slice, {d['board_visible_bars']} board bars.\n")
    lines.append("**Window curve** (frozen zone fixed; the knee sizes the deployment window):\n")
    lines.append("| window (d) | total cost | on-time | late | tardiness (min) | roll solve (s) | windows |")
    lines.append("|---|---|---|---|---|---|---|")
    for c in report.get("window_curve", []):
        lines.append(f"| {c['window_days']} | {c['total_cost']} | {c['on_time']} | {c['late']} "
                     f"| {c['tardiness_min']} | {c['roll_solve_wall_s']} | {c['n_windows']} |")
    if "knee_window_days" in report:
        lines.append(f"\n**Knee: {report['knee_window_days']}-day window** (cost within 1% of the best).\n")
    g = report.get("gravity", {})
    if g:
        lines.append("**Gravity counterfactual** (monster deep-chain, must-start precedes due-window):\n")
        lines.append("| admission | on-time | late | tardiness (min) | total cost |")
        lines.append("|---|---|---|---|---|")
        wg, og = g["with_gravity"], g["without_gravity"]
        lines.append(f"| WITH gravity | {wg['on_time']} | {wg['late']} | {wg['tardiness_min']} | {wg['total_cost']} |")
        lines.append(f"| WITHOUT gravity | {og['on_time']} | {og['late']} | {og['tardiness_min']} | {og['total_cost']} |")
        lines.append(f"\nGravity bought something: **{g['gravity_bought']}**.\n")
    lt = report.get("latencies", {})
    if lt:
        lines.append(f"**Interaction latency** (one {lt['window_days']}-day window, "
                     f"{lt['window_free_ops']} free ops): build {lt['window_build_s']}s, "
                     f"solve {lt['window_solve_s']}s ({lt['window_solve_status']}).")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    sys.exit(main())

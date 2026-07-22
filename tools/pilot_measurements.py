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

def measure_latencies(plant, det_time=4.0, window_days=7, frozen_days=2) -> dict:
    """CU2 (4B.2c) — interaction latency on the MOST LOADED window of the
    deployment (7-day) configuration, NOT the first (near-empty) window.

    The 4B.2 committed figure was measured on a 0-op window (a harness artifact);
    it is void. Here we roll the deployment window, keep the window with the most
    free ops (the worst case the cockpit must interact against), and measure on
    THAT model: build time, solve-to-first-feasible, solve-to-budget, and one
    forced-alternative re-solve (one op pinned to a non-default resource — the
    Tier-2 sandbox gesture the cockpit retrofit actually needs)."""
    from mre.modules.rolling_horizon import _build_window
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import add_required_resource_cut
    from mre.modules import standing_pins as sp

    # --- find the most-loaded window of the 7-day roll --------------------------
    loaded = {"free_op_count": -1}
    def _observe(b):
        nonlocal loaded
        if b["free_op_count"] > loaded["free_op_count"]:
            loaded = b
    run_rolling_horizon(plant, window_days=window_days, frozen_days=frozen_days,
                        gravity=True, deterministic=True, seed=42,
                        det_time=det_time, member_time_limit_s=30.0,
                        window_observer=_observe)
    if loaded["free_op_count"] <= 0:
        return {"error": "no loaded window found", "window_days": window_days}

    free_ops = loaded["free_ops"]
    pinned_ops = loaded["pinned_ops"]
    committed = loaded["committed"]
    ref = loaded["ref"]
    t0_min = loaded["t0_min"]

    # --- rebuild that exact window standalone; time the build -------------------
    t0 = time.perf_counter()
    model, var_map = _build_window(plant, free_ops, pinned_ops, ref,
                                   loaded["win_horizon_end"])
    build_s = time.perf_counter() - t0

    # replicate the rolling loop's window constraints (floor + carried pins +
    # R-SC3 stage-1 priced-earliness objective) so the timed model IS the one the
    # roll solves. We time STAGE 1 (the dominant cost); the stage-2 earliness
    # tiebreak adds a small warm-started deterministic budget on top.
    from mre.modules.rolling_horizon import _earliness_coeff_scaled
    coeff = _earliness_coeff_scaled(plant.cost_model, None)
    free_start_vars = []
    for op in free_ops:
        v = var_map.op_start.get(op["id"])
        if v is not None:
            model.add(v >= t0_min)
            free_start_vars.append(v)
    for op in pinned_ops:
        c = committed.get(op["id"])
        if not c or op["id"] not in var_map.op_start:
            continue
        smin = int(round((_dt(c["start"]) - ref).total_seconds() / 60.0))
        try:
            sp.apply_pin(model, var_map, op["id"], c["resource"], max(0, smin))
        except Exception:
            pass
    if var_map.objective_terms and coeff > 0 and free_start_vars:
        model.minimize(sum(var_map.objective_terms) + coeff * sum(free_start_vars))

    # --- solve-to-first-feasible (deterministic) --------------------------------
    from ortools.sat.python import cp_model as cp
    s1 = cp.CpSolver()
    s1.parameters.num_search_workers = 1
    s1.parameters.random_seed = 42
    s1.parameters.stop_after_first_solution = True
    t0 = time.perf_counter()
    st1 = s1.Solve(model)
    first_feasible_s = time.perf_counter() - t0
    first_status = {cp.OPTIMAL: "OPTIMAL", cp.FEASIBLE: "FEASIBLE"}.get(st1, "UNKNOWN")

    # --- solve-to-budget (deterministic-time budget: reproducible) --------------
    t0 = time.perf_counter()
    budget_solve = SolveRunner(time_limit_seconds=30.0, num_search_workers=1,
                               random_seed=42, deterministic_time=det_time
                               ).solve(model, var_map, None)
    budget_s = time.perf_counter() - t0

    # --- forced-alternative re-solve (the Tier-2 sandbox gesture) ---------------
    # pick one free op with >1 eligible resource, read the resource the budget
    # solve chose, pin it to a DIFFERENT eligible one, re-solve to budget.
    fa = {"available": False}
    sv = budget_solve.solve_values
    for op in free_ops:
        oid = op["id"]
        elig = list(var_map.op_assign.get(oid, {}).keys())
        chosen = sv.op_resource.get(oid)
        alt = next((r for r in elig if r != chosen), None)
        if len(elig) > 1 and chosen and alt:
            add_required_resource_cut(model, var_map, oid, alt)
            t0 = time.perf_counter()
            fa_solve = SolveRunner(time_limit_seconds=30.0, num_search_workers=1,
                                   random_seed=42, deterministic_time=det_time
                                   ).solve(model, var_map, None)
            fa = {"available": True, "op_eligible_count": len(elig),
                  "resolve_s": round(time.perf_counter() - t0, 3),
                  "status": fa_solve.status}
            break

    return {
        "window_days": window_days,
        "loaded_window_index": loaded["index"],
        "window_free_ops": len(free_ops),
        "window_pinned_ops": len(pinned_ops),
        "window_build_s": round(build_s, 3),
        "solve_to_first_feasible_s": round(first_feasible_s, 3),
        "solve_to_first_feasible_status": first_status,
        "solve_to_budget_s": round(budget_s, 3),
        "solve_to_budget_status": budget_solve.status,
        "det_time_budget_units": det_time,
        "forced_alternative_resolve": fa,
        "note": ("Measured on the MOST-LOADED window of the deployment 7-day roll "
                 "(worst case). grab->shade / on-demand ghost pricing / single-pin "
                 "sandbox all operate on ONE such window's model; build + a "
                 "single-pin re-solve is the cost that bounds the cockpit's "
                 "interactions. These are demo-density figures (60 orders / 15 "
                 "machines); pilot volume (174 workcenters) is UNMEASURED."),
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

    # --- CU4d interaction latencies (on the LOADED 7-day window) --------------
    print("[measure] CU4d interaction latencies (loaded window) ...")
    report["latencies"] = measure_latencies(plant, det_time=args.det_time,
                                             window_days=7, frozen_days=args.frozen)
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
    if lt and "window_free_ops" in lt:
        fa = lt.get("forced_alternative_resolve", {})
        fa_s = f", forced-alt re-solve {fa['resolve_s']}s ({fa['status']})" if fa.get("available") else ""
        lines.append(
            f"**Interaction latency** (MOST-LOADED window of the 7-day roll, "
            f"index {lt.get('loaded_window_index')}, {lt['window_free_ops']} free "
            f"+ {lt.get('window_pinned_ops', 0)} pinned ops): build "
            f"{lt['window_build_s']}s, solve-to-first-feasible "
            f"{lt.get('solve_to_first_feasible_s')}s "
            f"({lt.get('solve_to_first_feasible_status')}), solve-to-budget "
            f"{lt.get('solve_to_budget_s')}s ({lt.get('solve_to_budget_status')})"
            f"{fa_s}. Demo density; pilot volume UNMEASURED.")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    sys.exit(main())

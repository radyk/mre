#!/usr/bin/env python3
"""Session 4B.6c — the three-arm tiebreak measurement (MEASUREMENT ONLY).

Nothing here is reachable from any shipped path. It exists to answer one
question with evidence: does encoding the earliness tiebreak as a single
lexicographic objective (BIG*cost + sum(starts)) degrade CP-SAT's search
enough to cost us more ledger dollars than it saves?

THE INSTANCE is ONE WINDOW-0 SOLVE of a pilot_scale plant at the standing
rolling depths (window 14d / frozen 3d, ref 2026-01-05) — a faithful
transcription of ``rolling_horizon.build_rolling_view``'s solve, with the
OBJECTIVE as the only thing that varies between arms. Everything else (the
gate/adapter/validator/planner spine, gravity admission, the window model
build, the >= t0 floor, the Extractor pass that produces the ledger) is
literally the same code on every arm.

ARMS
  A0    cost only                sum(terms)                     one solve
  A1    status quo (shipped)     stage1 sum(terms) + C*sum(S)   two solves
                                 stage2 cap + minimize sum(S)
  A2    candidate B              BIG*sum(terms) + sum(S)        one solve
  A2h   candidate B, hour gran.  BIGh*sum(terms) + sum(H)       one solve
  A2x   candidate B, 10x BIG     10*BIG*sum(terms) + sum(S)     one solve

BUDGET PARITY: every arm gets the SAME total deterministic budget
(DET_TOTAL). A1 splits it exactly as shipped (4.0 stage 1 + 2.0 stage 2);
the single-solve arms take the whole thing in one go. The wall ceiling is a
safety ceiling far above the deterministic budget; any run where the wall
clock bound is reported and EXCLUDED from the comparison.

Usage:
    python tools/spikes/tiebreak_4b6c/arm_harness.py --probe
    python tools/spikes/tiebreak_4b6c/arm_harness.py --orders 40 120 200 \
        --arms A0 A1 A2 A2h --seeds 42 43 44 45 46
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

UTC = timezone.utc
REF = datetime(2026, 1, 5, tzinfo=UTC)
WINDOW_DAYS = 14
FROZEN_DAYS = 3
DET_TOTAL = 6.0          # deterministic budget, IDENTICAL on every arm
DET_STAGE1 = 4.0         # A1's split — the shipped rolling default
DET_STAGE2 = 2.0         # = rolling_horizon._STAGE2_DET_TIME_S
WALL_CEILING_S = 1800.0  # a CEILING, never the budget

SCRATCH = REPO / "_4b6c_scratch"
OUT = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# world
# ---------------------------------------------------------------------------

def build_plant(orders: int):
    """Generate (once, cached on disk) a pilot_scale submission at `orders` and
    run the spine. Returns a PreparedPlant."""
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import prepare_plant

    sub = SCRATCH / f"sub_{orders}"
    if not (sub / "manifest.json").exists():
        sub.parent.mkdir(parents=True, exist_ok=True)
        print(f"[world] generating pilot_scale orders={orders} seed=1 ...", flush=True)
        generate(sub, scenario="pilot_scale", orders=orders, seed=1)
    out = SCRATCH / f"run_{orders}"
    return prepare_plant(sub, out, reference_date=REF)


def window_inputs(plant, window_days=WINDOW_DAYS, frozen_days=FROZEN_DAYS):
    """The window-0 model inputs, IDENTICAL for every arm and seed: gravity
    admission (deterministic, seed-independent) then the sorted free-op list.
    Mirrors build_rolling_view exactly."""
    from mre.modules.rolling_horizon import _admit

    ref = plant.reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
    sched = plant.schedulable_demands
    t0 = ref
    window_end = t0 + timedelta(days=window_days)
    frozen_end = t0 + timedelta(days=frozen_days)
    win_horizon_end = window_end + timedelta(days=21)   # _WINDOW_TAIL_DAYS
    admitted, _ = _admit(plant, sched, t0, window_end, True, 3.0)
    free_ops = [op for did in sorted(admitted)
                for op in plant.ops_by_wp.get(plant.wp_of_demand.get(did), [])]
    return dict(ref=ref, t0=t0, window_end=window_end, frozen_end=frozen_end,
                win_horizon_end=win_horizon_end, free_ops=free_ops,
                window_days=window_days, frozen_days=frozen_days, t0_min=0,
                frozen_end_min=int((frozen_end - ref).total_seconds() / 60.0),
                sched=sched)


# ---------------------------------------------------------------------------
# solving
# ---------------------------------------------------------------------------

def _det_time(solver):
    for getter in (lambda: solver.response_proto.deterministic_time,
                   lambda: solver.ResponseProto().deterministic_time):
        try:
            return float(getter())
        except Exception:
            continue
    return None


def _solve(model, var_map, *, seed, det, wall, eval_exprs=None):
    """One CP-SAT solve, deterministic, capturing the deterministic time the
    solve actually consumed (SolveRunner does not expose it) and the value of
    any named expression at the returned solution — notably the PURE cost
    objective sum(objective_terms), which is the only solver-side quantity
    comparable across arms."""
    from ortools.sat.python import cp_model as cp
    solver = cp.CpSolver()
    solver.parameters.max_time_in_seconds = wall
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    solver.parameters.max_deterministic_time = det
    solver.parameters.log_search_progress = False
    t = time.perf_counter()
    st = solver.Solve(model)
    wall_s = time.perf_counter() - t
    name = {cp.OPTIMAL: "OPTIMAL", cp.FEASIBLE: "FEASIBLE",
            cp.INFEASIBLE: "INFEASIBLE", cp.UNKNOWN: "UNKNOWN",
            cp.MODEL_INVALID: "MODEL_INVALID"}.get(st, "UNKNOWN")
    obj = bound = None
    sv = None
    vals = {}
    if name in ("OPTIMAL", "FEASIBLE"):
        obj = solver.ObjectiveValue()
        bound = solver.BestObjectiveBound()
        sv = var_map.extract(solver)
        for k, expr in (eval_exprs or {}).items():
            try:
                vals[k] = int(solver.value(expr))
            except Exception:
                vals[k] = None
    return dict(status=name, objective=obj, best_bound=bound, wall_s=wall_s,
                det_consumed=_det_time(solver), solve_values=sv, values=vals,
                wall_truncated=(solver.WallTime() >= wall - 0.05))


def _domain_lb(v):
    # NB: protobuf repeated fields do NOT support negative indexing — materialize
    # the domain as a list first. Indexing v.proto.domain[-1] raises, and a
    # swallowed exception here silently collapses BIG to 1 (measured the hard way).
    return int(list(v.proto.domain)[0])


def _domain_ub(v):
    return int(list(v.proto.domain)[-1])


def apply_arm(model, var_map, free_start_vars, arm, coeff_scaled):
    """Set the arm's objective. Returns a magnitude report (item 2a)."""
    terms = var_map.objective_terms
    n = len(free_start_vars)
    if not terms or not n:
        return {"arm": arm, "degenerate": True}
    lo = min(_domain_lb(v) for v in free_start_vars)
    hi = max(_domain_ub(v) for v in free_start_vars)
    start_range = hi - lo
    big = n * start_range + 1
    rep = {"arm": arm, "n_free_ops": n, "start_lb": lo, "start_ub": hi,
           "start_range": start_range, "BIG": big, "n_terms": len(terms),
           "max_sum_starts": n * hi, "int64_max": 2 ** 63 - 1}

    if arm == "A0":
        model.minimize(sum(terms))
    elif arm == "A1":
        if coeff_scaled > 0:
            model.minimize(sum(terms) + coeff_scaled * sum(free_start_vars))
        # else: the builder's own minimize(sum(terms)) stands (shipped behaviour)
        rep["coeff_scaled"] = coeff_scaled
    elif arm == "A2":
        model.minimize(big * sum(terms) + sum(free_start_vars))
    elif arm == "A2x":
        rep["BIG"] = big = big * 10
        model.minimize(big * sum(terms) + sum(free_start_vars))
    elif arm == "A2h":
        horizon_hours = hi // 60 + 1
        big_h = n * horizon_hours + 1
        hvars = []
        for v in free_start_vars:
            h = model.new_int_var(0, horizon_hours, f"h_{v.name}")
            r = model.new_int_var(0, 59, f"r_{v.name}")
            model.add(v == 60 * h + r)     # linear-equality encoding of v // 60
            hvars.append(h)
        rep.update(BIG=big_h, horizon_hours=horizon_hours, granularity="hour")
        model.minimize(big_h * sum(terms) + sum(hvars))
    else:
        raise ValueError(arm)
    rep["objective_worst_case_magnitude"] = _objective_magnitude(model)
    rep["int64_headroom_x"] = (
        (2 ** 63 - 1) / rep["objective_worst_case_magnitude"]
        if rep["objective_worst_case_magnitude"] else None)
    return rep


def _objective_magnitude(model):
    """An EXACT upper bound on |objective| from the objective proto itself:
    sum over terms of |coeff| x max(|lb|, |ub|) of that variable. This is the
    number the int64 headroom claim must rest on — not an assurance."""
    try:
        obj = model.proto.objective
        variables = model.proto.variables
        total = 0
        for vi, c in zip(obj.vars, obj.coeffs):
            dom = list(variables[vi].domain)
            total += abs(int(c)) * max(abs(dom[0]), abs(dom[-1]))
        return int(total)
    except Exception as exc:      # pragma: no cover - diagnostic only
        return None


def run_arm(plant, win, arm, seed, det_total=DET_TOTAL, keep_placements=False):
    from mre.modules.rolling_horizon import _build_window, _earliness_coeff_scaled

    free_ops = win["free_ops"]
    t_b = time.perf_counter()
    model, var_map = _build_window(plant, free_ops, [], win["ref"],
                                   win["win_horizon_end"])
    build_s = time.perf_counter() - t_b

    free_start_vars = []
    for op in free_ops:
        v = var_map.op_start.get(op["id"])
        if v is not None:
            model.add(v >= win["t0_min"])
            free_start_vars.append(v)

    coeff = _earliness_coeff_scaled(plant.cost_model, None)
    mag = apply_arm(model, var_map, free_start_vars, arm, coeff)
    # The PURE cost objective and the raw start sum, evaluated at whatever
    # solution the arm returns. sum(objective_terms) is in CP-SAT scaled cost
    # units on EVERY arm, so it is the one solver-side figure that IS
    # comparable across arms (the raw objective value is not).
    probes = {"cost_scaled": sum(var_map.objective_terms),
              "start_sum": sum(free_start_vars)} if var_map.objective_terms and free_start_vars else {}

    if arm == "A1":
        # the SHIPPED two-stage shape, transcribed from
        # rolling_horizon._two_stage_solve (lines 147-172).
        s1 = _solve(model, var_map, seed=seed, det=DET_STAGE1, wall=WALL_CEILING_S,
                    eval_exprs=probes)
        res = s1
        stage2_ran = False
        terms = var_map.objective_terms
        if (terms and free_start_vars and s1["objective"] is not None
                and s1["status"] in ("OPTIMAL", "FEASIBLE")):
            best = int(round(s1["objective"]))
            if coeff > 0:
                model.add(sum(terms) + coeff * sum(free_start_vars) <= best)
            else:
                model.add(sum(terms) <= best)
            model.minimize(sum(free_start_vars))
            _rehint(model, var_map, s1["solve_values"])
            s2 = _solve(model, var_map, seed=seed, det=DET_STAGE2,
                        wall=WALL_CEILING_S, eval_exprs=probes)
            if s2["status"] in ("OPTIMAL", "FEASIBLE"):
                s2["stage1_objective"] = s1["objective"]
                s2["objective"] = s1["objective"]     # stage 1's is the recorded one
                s2["status_stage1"] = s1["status"]
                s2["wall_s"] += s1["wall_s"]
                s2["det_consumed"] = (s1["det_consumed"] or 0) + (s2["det_consumed"] or 0)
                s2["wall_truncated"] = s1["wall_truncated"] or s2["wall_truncated"]
                res = s2
                stage2_ran = True
        if not stage2_ran:
            res["status_stage1"] = s1["status"]
        res["stage2_ran"] = stage2_ran
        # A1's REPORTED status is stage 1's — the cost-proof status, the only
        # one comparable to the single-solve arms (stage 2 proves optimality of
        # the TIEBREAK, not of the cost).
        res["status_reported"] = res.get("status_stage1", res["status"])
    else:
        res = _solve(model, var_map, seed=seed, det=det_total, wall=WALL_CEILING_S,
                     eval_exprs=probes)
        res["status_reported"] = res["status"]
        res["stage2_ran"] = False

    row = dict(orders=plant_orders(plant), arm=arm, seed=seed,
               build_s=round(build_s, 3), magnitudes=mag,
               status=res["status_reported"], raw_status=res["status"],
               raw_objective=res["objective"],
               cost_scaled=(res.get("values") or {}).get("cost_scaled"),
               start_sum_scaled=(res.get("values") or {}).get("start_sum"),
               stage1_objective=res.get("stage1_objective"),
               wall_s=round(res["wall_s"], 3),
               det_consumed=res["det_consumed"],
               wall_truncated=res["wall_truncated"],
               stage2_ran=res["stage2_ran"],
               n_free_ops=len(free_start_vars))

    if res["solve_values"] is None:
        row["ledger"] = None
        return row, None

    sv = res["solve_values"]
    row.update(measure_solution(plant, win, var_map, sv, free_ops, free_start_vars))
    payload = None
    if keep_placements:
        payload = {"var_map": var_map, "sv": sv, "model_free": free_start_vars}
    return row, payload


def _rehint(model, var_map, sv):
    model.clear_hints()
    for oid, smin in sv.op_start_minutes.items():
        v = var_map.op_start.get(oid)
        if v is not None:
            model.add_hint(v, smin)
        ev = var_map.op_end.get(oid)
        emin = sv.op_end_minutes.get(oid)
        if ev is not None and emin is not None:
            model.add_hint(ev, emin)
        res = sv.op_resource.get(oid)
        if res is not None:
            for r2, bv in var_map.op_assign.get(oid, {}).items():
                model.add_hint(bv, 1 if r2 == res else 0)


_ORDERS_ATTR = {}


def plant_orders(plant):
    return _ORDERS_ATTR.get(id(plant), 0)


# ---------------------------------------------------------------------------
# what we measure about a solution
# ---------------------------------------------------------------------------

def extract_ledger(plant, win, var_map, sv, free_ops):
    """The SAME Extractor pass build_rolling_view runs — the ledger is the
    comparison that matters. Identical on every arm."""
    from mre.modules.extractor import Extractor

    wp_ids = {op["workpackage_ref"] for op in free_ops}
    wps = [w for w in plant.workpackages if w["id"] in wp_ids]
    fuls = [f for f in plant.fulfillments if f["workpackage_ref"] in wp_ids]
    dem_ids = {f["demand_ref"] for f in fuls}
    demands = [d for d in plant.demands if d["id"] in dem_ids]
    extract_cm = dict(plant.cost_model)
    result = Extractor().extract(
        solve_values=sv, snapshot_id=plant.snapshot_id,
        operations=free_ops, workpackages=wps, resources=plant.resources,
        fulfillments=fuls, demands=demands, cost_model=extract_cm,
        reporter=None, cal_windows=var_map.cal_windows,
        op_eligible=var_map.op_eligible, snapshot_writer=None,
        overtime_windows=var_map.overtime_windows, is_scenario=True)
    return result


def wip_proxies(plant, sv, free_ops):
    """Item 5 direction numbers. total dwell = sum over ops with >=1 placed
    predecessor of (start - end of the LATEST-completing predecessor); mean and
    peak concurrent WIP over work packages started-but-not-complete."""
    preds = predecessor_map(plant, free_ops)
    dwell = 0
    dwell_n = 0
    for oid, plist in preds.items():
        if oid not in sv.op_start_minutes:
            continue
        ends = [sv.op_end_minutes[p] for p in plist if p in sv.op_end_minutes]
        if not ends:
            continue
        dwell += sv.op_start_minutes[oid] - max(ends)
        dwell_n += 1

    spans = {}
    for op in free_ops:
        oid = op["id"]
        if oid not in sv.op_start_minutes:
            continue
        wp = op["workpackage_ref"]
        s, e = sv.op_start_minutes[oid], sv.op_end_minutes[oid]
        cur = spans.get(wp)
        spans[wp] = (min(cur[0], s), max(cur[1], e)) if cur else (s, e)
    events = []
    for s, e in spans.values():
        events.append((s, 1))
        events.append((e, -1))
    events.sort()
    cur = peak = 0
    prev_t = events[0][0] if events else 0
    area = 0
    for t, d in events:
        area += cur * (t - prev_t)
        prev_t = t
        cur += d
        peak = max(peak, cur)
    span = (events[-1][0] - events[0][0]) if events else 0
    return {"total_dwell_min": dwell, "dwell_ops": dwell_n,
            "peak_wip_wp": peak,
            "mean_wip_wp": round(area / span, 3) if span else 0.0,
            "wip_span_min": span}


_PRED_CACHE = {}


def predecessor_map(plant, free_ops):
    """op_id -> [predecessor op_ids], resolved exactly as SolverBuilder does
    (template edges keyed by spec_ref, resolved per workpackage)."""
    key = (id(plant), len(free_ops))
    if key in _PRED_CACHE:
        return _PRED_CACHE[key]
    by_wp_spec = {(o["workpackage_ref"], o["spec_ref"]): o["id"] for o in free_ops}
    wps = {o["workpackage_ref"] for o in free_ops}
    out = {}
    for edge in plant.edges:
        for wp in wps:
            p = by_wp_spec.get((wp, edge["predecessor"]))
            s = by_wp_spec.get((wp, edge["successor"]))
            if p and s:
                out.setdefault(s, []).append(p)
    _PRED_CACHE[key] = out
    return out


def measure_solution(plant, win, var_map, sv, free_ops, free_start_vars):
    res = extract_ledger(plant, win, var_map, sv, free_ops)
    led = res.cost_ledger
    sum_starts = sum(sv.op_start_minutes[o["id"]] for o in free_ops
                     if o["id"] in sv.op_start_minutes)
    placed = len(sv.op_start_minutes)
    fe = win["frozen_end_min"]
    committed = sum(1 for o in free_ops
                    if sv.op_start_minutes.get(o["id"], 10**9) < fe)
    tard_min = sum(max(0, s.get("lateness_minutes", 0))
                   for s in res.service_outcomes)
    late = sum(1 for s in res.service_outcomes if s.get("lateness_minutes", 0) > 0)
    out = {"ledger": led, "sum_free_starts_min": sum_starts,
           "placed_ops": placed, "committed_ops": committed,
           "tardiness_minutes": tard_min, "late_demands": late,
           "n_demands": len(res.service_outcomes)}
    out.update(wip_proxies(plant, sv, free_ops))
    return out


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, nargs="+", default=[40, 120, 200])
    ap.add_argument("--arms", nargs="+", default=["A0", "A1", "A2", "A2h"])
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    ap.add_argument("--det", type=float, default=DET_TOTAL)
    ap.add_argument("--out", default=str(OUT / "arm_results.jsonl"))
    ap.add_argument("--window", type=int, default=WINDOW_DAYS)
    ap.add_argument("--frozen", type=int, default=FROZEN_DAYS)
    ap.add_argument("--max-seconds", type=float, default=None,
                    help="stop cleanly before this wall budget is exhausted "
                         "(the run is resumable, so chunking costs nothing)")
    ap.add_argument("--probe", action="store_true",
                    help="one arm, one seed, per instance — wall-time calibration")
    args = ap.parse_args()

    if args.probe:
        args.arms = ["A0"]
        args.seeds = [42]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # RESUMABLE by construction: every (orders, window, frozen, arm, seed) already
    # in the output file is skipped. Each run is individually deterministic, so a
    # chunked sweep and a single long one produce the same rows.
    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            done.add((r["orders"], r.get("window_days", WINDOW_DAYS),
                      r.get("frozen_days", FROZEN_DAYS), r["arm"], r["seed"]))
    started = time.perf_counter()
    fh = out_path.open("a", encoding="utf-8")

    for orders in args.orders:
        todo = [(a, s) for a in args.arms for s in args.seeds
                if (orders, args.window, args.frozen, a, s) not in done]
        if not todo:
            print(f"[world] orders={orders} — nothing to do (resumed)", flush=True)
            continue
        plant = build_plant(orders)
        _ORDERS_ATTR[id(plant)] = orders
        win = window_inputs(plant, args.window, args.frozen)
        print(f"[world] orders={orders} window={args.window}d frozen={args.frozen}d "
              f"admitted_free_ops={len(win['free_ops'])} "
              f"demands={len(win['sched'])}", flush=True)
        for arm in args.arms:
            for seed in args.seeds:
                if (orders, args.window, args.frozen, arm, seed) in done:
                    continue
                if (args.max_seconds is not None
                        and time.perf_counter() - started > args.max_seconds):
                    print(f"[chunk] wall budget reached — stopping cleanly "
                          f"(resume by re-running the same command)", flush=True)
                    fh.close()
                    return
                t = time.perf_counter()
                row, _ = run_arm(plant, win, arm, seed, det_total=args.det)
                row["window_days"] = args.window
                row["frozen_days"] = args.frozen
                row["det_budget"] = args.det
                row["total_s"] = round(time.perf_counter() - t, 2)
                fh.write(json.dumps(row, default=str) + "\n")
                fh.flush()
                led = row.get("ledger") or {}
                print(f"  {orders:>4} {arm:<4} seed={seed} {row['status']:<8} "
                      f"total={led.get('total_cost')} "
                      f"tard={led.get('tardiness_cost')} "
                      f"sumS={row.get('sum_free_starts_min')} "
                      f"wall={row['wall_s']}s det={row['det_consumed']}",
                      flush=True)
    fh.close()


if __name__ == "__main__":
    main()

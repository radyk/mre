#!/usr/bin/env python3
"""Session 4B.10 ITEM 3 — SWEEP OPS-PER-MACHINE, NOT WINDOW DEPTH.

MEASUREMENT ONLY. Nothing here is reachable from a shipped path.

WHY THE AXIS CHANGES. Every scale number the programme holds was taken on
pilot_scale: 13-15 machines at ~24 ops/machine. The measured planning unit
(docs/07 §5a.24/.25) is FOUR MACHINES carrying 250-800 OPERATIONS EACH. This
sweep holds the real shape fixed (`facility_real`: 4 machines, 4-op routes, the
book's due-date histogram) and sweeps DENSITY.

CONFIGURATION — all three, or the measurement is void:
  * COST-ONLY objective. As shipped since 4B.7; `_two_stage_solve` sets no
    objective of its own, so stage 1 minimizes the builder's cost terms alone.
  * P3 ALLOCATION. As shipped since 4B.8: stage 1 capped at det_total minus a
    1/12 reserve, stage 2 gets the remainder. We call the SHIPPED
    `rolling_horizon._two_stage_solve`, not a transcription of it.
  * WALL CEILING RAISED so the DETERMINISTIC budget is what binds.
    `member_time_limit_s` defaults to 30.0 while stage 1 needs 37-120 s at 200
    orders, so every prior measurement on the shipped path was wall-truncated
    and therefore — by this repository's own hard rule — a lottery. We pass
    WALL_CEILING_S and EXCLUDE any row whose `wall_truncated` is True.

Per (density, alternates, seed) this records: status, ledger, deterministic
units to FIRST SOLUTION (a satisfaction probe) and to PROOF, ops/machine, and
utilisation against the plant's ACTUAL calendar capacity.

Usage:
    python tools/spikes/density_4b10/density_sweep.py --seeds 42
    python tools/spikes/density_4b10/density_sweep.py --seeds 43 44 45 46 \
        --max-seconds 3600
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
REF = datetime(2026, 1, 5, tzinfo=UTC)      # a Monday, as every fixture uses
WINDOW_DAYS = 14
FROZEN_DAYS = 3
DET_TOTAL = 6.0             # the SHIPPED rolling default (_DET_TOTAL_DEFAULT)
WALL_CEILING_S = 1800.0     # a CEILING far above the budget — never the budget
SAT_DET = 20.0              # the satisfaction probe's own budget

SCRATCH = REPO / "_4b10_scratch"
OUT = Path(__file__).resolve().parent

# Order counts chosen to land near 25/50/100/150/250/400/600/800 ops per
# machine: 4 ops/order over 4 machines, and ~92% of a facility_real book falls
# inside a 14-day window, so ops/machine ~= 0.92 x orders.
DENSITIES = [28, 55, 110, 165, 275, 435, 650, 870]


def _status_name(cp, st):
    return {cp.OPTIMAL: "OPTIMAL", cp.FEASIBLE: "FEASIBLE",
            cp.INFEASIBLE: "INFEASIBLE", cp.UNKNOWN: "UNKNOWN",
            cp.MODEL_INVALID: "MODEL_INVALID"}.get(st, "UNKNOWN")


def build_plant(orders: int, alternates: int):
    """Generate (once, cached on disk) a facility_real submission and run the
    spine. The GENERATION seed is fixed at 1 so the plant is identical across
    solver seeds — seed spread then measures the SOLVER, not the world."""
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import prepare_plant

    sub = SCRATCH / f"sub_o{orders}_a{alternates}"
    if not (sub / "manifest.json").exists():
        sub.parent.mkdir(parents=True, exist_ok=True)
        print(f"[world] generating facility_real orders={orders} "
              f"alternates={alternates} ...", flush=True)
        generate(sub, scenario="facility_real", orders=orders, seed=1,
                 fr_machines=4, fr_alternates=alternates)
    out = SCRATCH / f"run_o{orders}_a{alternates}"
    return prepare_plant(sub, out, reference_date=REF)


def window_inputs(plant, window_days=WINDOW_DAYS, frozen_days=FROZEN_DAYS):
    """The window-0 model inputs — gravity admission then the sorted free-op
    list. Mirrors `build_rolling_view` exactly (as arm_harness does)."""
    from mre.modules.rolling_horizon import _admit

    ref = plant.reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
    sched = plant.schedulable_demands
    window_end = ref + timedelta(days=window_days)
    admitted, _ = _admit(plant, sched, ref, window_end, True, 3.0)
    free_ops = [op for did in sorted(admitted)
                for op in plant.ops_by_wp.get(plant.wp_of_demand.get(did), [])]
    return dict(ref=ref, t0=ref, window_end=window_end,
                win_horizon_end=window_end + timedelta(days=21),
                free_ops=free_ops, n_demands_admitted=len(admitted),
                n_schedulable=len(sched), t0_min=0)


def _iso_minutes(val) -> float:
    """ISO-8601 duration -> minutes. The op dicts carry 'PT20M' / 'PT51.72S'."""
    from datetime import timedelta as _td
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, _td):
        return val.total_seconds() / 60.0
    s = str(val)
    if not s.startswith("PT"):
        return 0.0
    s, num, total = s[2:], "", 0.0
    for ch in s:
        if ch.isdigit() or ch == ".":
            num += ch
        else:
            v = float(num or 0)
            total += {"H": v * 60.0, "M": v, "S": v / 60.0}.get(ch, 0.0)
            num = ""
    return total


def calendar_minutes(plant, ref, window_end) -> float:
    """Open machine-minutes in the window, per the plant's ACTUAL calendars —
    not an assumed 720x7.

    This matters and is not a detail. docs/07 §5a.25 computed the book's
    utilisation against `window_days x 720`, i.e. a SEVEN-day week, because the
    extract carries no calendars at all. facility_real authors Mon-Fri
    07:00-19:00, so a 14-day window holds TEN working days, not fourteen — the
    solver sees 5/7 of that denominator and true utilisation is ~1.4x the
    §5a.25 figure at the same density. Every utilisation in this sweep is
    against the real calendar."""
    total = 0.0
    cal_by_id = {c["id"]: c for c in plant.calendars}
    days = (window_end - ref).days
    for r in plant.resources:
        cal = cal_by_id.get(r.get("calendar_ref"))
        if not cal:
            continue
        pat = cal.get("base_pattern") or {}
        wd = pat.get("weekdays") or []
        try:
            sh, sm = (int(x) for x in str(pat.get("shift_start", "0:00")).split(":"))
            eh, em = (int(x) for x in str(pat.get("shift_end", "0:00")).split(":"))
            per_day = (eh * 60 + em) - (sh * 60 + sm)
        except Exception:
            per_day = 0
        total += len(wd) * per_day * days / 7.0
    return total


class _RecordingRunner:
    """Wraps SolveRunner so each stage's own status and deterministic spend can
    be read back. `_two_stage_solve` returns the COMBINED det_consumed
    (`spent1 + stage2`), so "units to PROOF" — stage 1's spend at the moment it
    proved the cost optimum — is not recoverable from its return value. This
    records it WITHOUT reimplementing the shipped allocation: the two-stage
    logic, its budgets and its reserve are untouched and still the shipped
    code's."""

    calls: list = []
    #: bound to the REAL SolveRunner before patching. Re-importing it here would
    #: resolve to this class (the module attribute is what we patch) and recurse.
    inner_cls = None

    def __init__(self, *a, **kw):
        self._inner = _RecordingRunner.inner_cls(*a, **kw)
        self._det = kw.get("deterministic_time")

    def solve(self, *a, **kw):
        res = self._inner.solve(*a, **kw)
        _RecordingRunner.calls.append({
            "budget": self._det, "status": res.status,
            "det_consumed": res.det_consumed, "objective": res.objective,
            "best_bound": res.best_bound, "gap": res.gap,
            "wall_time": getattr(res, "wall_time", None),
            "wall_truncated": bool(res.wall_truncated)})
        return res


def run_cell(orders: int, alternates: int, seed: int) -> dict:
    from ortools.sat.python import cp_model as cp
    from mre.modules.rolling_horizon import _build_window, _two_stage_solve

    plant = build_plant(orders, alternates)
    win = window_inputs(plant)
    free_ops = win["free_ops"]

    # --- load / density, before any solving ---------------------------------
    req_min = sum(_iso_minutes(op.get("setup_duration"))
                  + _iso_minutes(op.get("run_duration")) for op in free_ops)
    avail_min = calendar_minutes(plant, win["ref"], win["window_end"])

    # --- BUILD (timed separately, always) -----------------------------------
    t = time.perf_counter()
    model, var_map = _build_window(plant, free_ops, [], win["ref"],
                                   win["win_horizon_end"])
    free_start_vars = []
    for op in free_ops:
        v = var_map.op_start.get(op["id"])
        if v is not None:
            model.add(v >= win["t0_min"])
            free_start_vars.append(v)
    build_s = time.perf_counter() - t

    per_machine: dict[str, int] = {}
    for op in free_ops:
        for rid in (var_map.op_eligible or {}).get(op["id"], []):
            per_machine[rid] = per_machine.get(rid, 0) + 1
    counts = sorted(per_machine.values(), reverse=True)
    n_free = len(free_start_vars)
    n_mach = len(plant.resources)

    row = dict(
        orders=orders, alternates=alternates, seed=seed,
        window_days=WINDOW_DAYS, frozen_days=FROZEN_DAYS,
        det_total=DET_TOTAL, wall_ceiling_s=WALL_CEILING_S,
        n_schedulable=win["n_schedulable"], n_admitted=win["n_demands_admitted"],
        n_free_ops=n_free, n_machines=n_mach,
        ops_per_machine=round(n_free / n_mach, 1) if n_mach else 0,
        ops_per_machine_eligible_max=(counts[0] if counts else 0),
        required_minutes=round(req_min, 1),
        available_minutes=round(avail_min, 1),
        utilisation_pct=(round(100.0 * req_min / avail_min, 2) if avail_min else None),
        build_s=round(build_s, 3),
    )

    # --- SATISFACTION PROBE: units to the FIRST solution --------------------
    m2, vm2 = _build_window(plant, free_ops, [], win["ref"], win["win_horizon_end"])
    for op in free_ops:
        v = vm2.op_start.get(op["id"])
        if v is not None:
            m2.add(v >= win["t0_min"])
    m2.minimize(0)
    s = cp.CpSolver()
    s.parameters.max_time_in_seconds = WALL_CEILING_S
    s.parameters.num_search_workers = 1
    s.parameters.random_seed = seed
    s.parameters.max_deterministic_time = SAT_DET
    s.parameters.stop_after_first_solution = True
    t = time.perf_counter()
    st = s.Solve(m2)
    row.update(sat_status=_status_name(cp, st),
               sat_wall_s=round(time.perf_counter() - t, 2),
               sat_det=float(s.response_proto.deterministic_time),
               sat_wall_truncated=(s.WallTime() >= WALL_CEILING_S - 0.05))

    # --- THE SHIPPED TWO-STAGE COST SOLVE -----------------------------------
    # Patched at the module the shipped code imports FROM, so `_two_stage_solve`
    # picks the recorder up through its own local import. Restored in `finally`.
    import mre.modules.solve_runner as _sr_mod
    _orig = _sr_mod.SolveRunner
    _RecordingRunner.inner_cls = _orig
    _RecordingRunner.calls = []
    t = time.perf_counter()
    try:
        _sr_mod.SolveRunner = _RecordingRunner
        res, stage2_ran, _recovery = _two_stage_solve(
            model, var_map, free_start_vars,
            workers=1, seed=seed, deterministic=True,
            member_time_limit_s=WALL_CEILING_S, det_total=DET_TOTAL,
            free_op_ids=[op["id"] for op in free_ops])
    finally:
        _sr_mod.SolveRunner = _orig
    solve_s = time.perf_counter() - t

    stages = list(_RecordingRunner.calls)
    s1 = stages[0] if stages else {}
    s2 = stages[1] if len(stages) > 1 else {}
    row.update(
        status=res.status, tiebreak_status=getattr(res, "tiebreak_status", None),
        tiebreak_skipped_reason=getattr(res, "tiebreak_skipped_reason", None),
        stage2_ran=stage2_ran,
        objective=res.objective, best_bound=res.best_bound, gap=res.gap,
        det_consumed=res.det_consumed, solve_s=round(solve_s, 2),
        wall_time=round(getattr(res, "wall_time", 0.0) or 0.0, 2),
        wall_truncated=bool(res.wall_truncated),
        # STAGE 1 alone — the COST PROOF. `det_to_proof` is the deterministic
        # spend at which the cost optimum was PROVEN; it is only meaningful when
        # stage 1 returned OPTIMAL, and is None otherwise (a FEASIBLE stage 1
        # exhausted its budget without proving anything).
        stage1_budget=s1.get("budget"), stage1_status=s1.get("status"),
        stage1_det=s1.get("det_consumed"), stage1_gap=s1.get("gap"),
        stage1_wall_s=(round(s1["wall_time"], 2) if s1.get("wall_time") else None),
        stage1_wall_truncated=s1.get("wall_truncated"),
        det_to_proof=(s1.get("det_consumed") if s1.get("status") == "OPTIMAL" else None),
        stage2_budget=s2.get("budget"), stage2_status=s2.get("status"),
        stage2_det=s2.get("det_consumed"),
        stage2_wall_truncated=s2.get("wall_truncated"))

    # --- the LEDGER (the same Extractor pass build_rolling_view runs) --------
    if res.solve_values is not None:
        try:
            from mre.modules.extractor import Extractor
            wp_ids = {op["workpackage_ref"] for op in free_ops}
            wps = [w for w in plant.workpackages if w["id"] in wp_ids]
            fuls = [f for f in plant.fulfillments if f["workpackage_ref"] in wp_ids]
            dem_ids = {f["demand_ref"] for f in fuls}
            dems = [d for d in plant.demands if d["id"] in dem_ids]
            r = Extractor().extract(
                solve_values=res.solve_values, snapshot_id=plant.snapshot_id,
                operations=free_ops, workpackages=wps, resources=plant.resources,
                fulfillments=fuls, demands=dems, cost_model=dict(plant.cost_model),
                reporter=None, cal_windows=var_map.cal_windows,
                op_eligible=var_map.op_eligible, snapshot_writer=None,
                overtime_windows=var_map.overtime_windows, is_scenario=True)
            led = r.cost_ledger or {}
            row.update(ledger_total=led.get("total_cost"),
                       ledger_tardiness=led.get("tardiness_cost"),
                       placed_ops=len(res.solve_values.op_start_minutes),
                       late_demands=sum(1 for s2 in r.service_outcomes
                                        if s2.get("lateness_minutes", 0) > 0),
                       tardiness_minutes=sum(max(0, s2.get("lateness_minutes", 0))
                                             for s2 in r.service_outcomes))
        except Exception as exc:      # noqa: BLE001 — diagnostic, never fatal
            row["ledger_error"] = f"{type(exc).__name__}: {exc}"
    else:
        row["ledger_total"] = None
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, nargs="+", default=DENSITIES)
    ap.add_argument("--alternates", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--seeds", type=int, nargs="+", default=[42])
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--out", default=str(OUT / "density.jsonl"))
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["orders"], r["alternates"], r["seed"]))

    started = time.perf_counter()
    for orders in args.orders:
        for alt in args.alternates:
            for seed in args.seeds:
                if (orders, alt, seed) in done:
                    print(f"[skip] o={orders} a={alt} s={seed}", flush=True)
                    continue
                if (args.max_seconds is not None
                        and time.perf_counter() - started > args.max_seconds):
                    print("[chunk] wall budget reached — stopping cleanly "
                          "(re-run the same command to resume)", flush=True)
                    return
                row = run_cell(orders, alt, seed)
                with out_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, default=str) + "\n")
                proof = row.get("det_to_proof")
                print(f"[density] o={orders:>4} a={alt} s={seed} "
                      f"free={row['n_free_ops']:>5} opm={row['ops_per_machine']:>6} "
                      f"util={row['utilisation_pct']}% "
                      f"SAT={row['sat_status']}@{row['sat_det']:.3f} "
                      f"S1={row.get('stage1_status')}@{row.get('stage1_det')} "
                      f"proof={'-' if proof is None else round(proof, 3)} "
                      f"gap={row['gap']} total={row.get('ledger_total')} "
                      f"wall={row['wall_time']}s trunc={row['wall_truncated']}",
                      flush=True)


if __name__ == "__main__":
    main()

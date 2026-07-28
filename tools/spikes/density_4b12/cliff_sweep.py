#!/usr/bin/env python3
"""Session 4B.12 CU1/CU2 — RE-BASELINE THE CLIFF UNDER R-PD1, AND SOLVE THE
TWO BRACKETED REAL DENSITIES.

MEASUREMENT ONLY. Nothing here is reachable from a shipped path.

WHY A SECOND SWEEP EXISTS. 4B.10 located a cliff at 137 ops/machine and
BRACKETED the two real densities (F004 246, F006 803) rather than solving them.
4B.11 then changed the world underneath that measurement: R-PD1 admits past-due
work, and 4B.10 itself proved tardiness onset is the cliff's driver. A cliff
measured on a book that silently DROPPED its late orders is not a cliff on the
book we now schedule.

WHAT IS REUSED, AND WHY. The 4B.10 harness's components are imported, not
copied: `build_plant` (the pinned generation seed), `window_inputs` (the
gravity-admission mirror), `calendar_minutes` (the REAL calendar denominator,
not an assumed 720x7), `_iso_minutes`, and above all `_RecordingRunner` — the
wrapper that recovers each stage's own status and deterministic spend WITHOUT
reimplementing the shipped two-stage allocation. `analyze.py` reads this file
unchanged (the column names are 4B.10's).

WHAT IS ADDED, and it is the reason this is not just `density_sweep --out`:

  * the R-PD1 quantities, which 4B.10 could not have recorded because they did
    not exist — past-due demands at intake, how many SURVIVE to schedulable,
    how many are ADMITTED to the window, and the ledger's tardiness SPLIT
    (`tardiness_floor_cost` / `tardiness_controllable_cost`, contract 1.11);
  * the GAP on unproved rows is already recorded by 4B.10's row, but it is now
    the headline column rather than a diagnostic (4B.11 made it visible to
    planners, so it is the number the session reports);
  * the CU3 hint arms (`hint_mode`), off by default so a CU1/CU2 row is
    identical in construction to a 4B.10 row.

CONFIGURATION — all four, or the measurement is void (brief, Part 0):
  * COST-ONLY objective — the SHIPPED `rolling_horizon._two_stage_solve`.
  * P3 allocation — the shipped 4B.8 split, called and not transcribed.
  * WALL CEILING 1800 s so the DETERMINISTIC budget binds. Any row whose
    `wall_truncated` is True is reported and EXCLUDED by `analyze.py`.
  * det_total 6.0, window 14 d, frozen 3 d, 4 machines.

SCRATCH. This sweep regenerates its worlds into `_4b12_scratch` rather than
reusing `_4b10_scratch`. Generation is seeded (seed=1) and deterministic, so the
re-baselined worlds are identical BY CONSTRUCTION — and `verify_world_identity.py`
proves it byte-for-byte instead of assuming it. Separate run dirs also let cells
of different (orders, alternates) run as concurrent processes without two of them
writing one spine output directory.

Usage:
    PYTHONHASHSEED=0 python tools/spikes/density_4b12/cliff_sweep.py \
        --orders 110 --alternates 1 --seeds 42 43 44 45 46 --out cu1_o110a1.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "spikes" / "density_4b10"))

import density_sweep as ds        # noqa: E402  — the 4B.10 harness, reused

# Own scratch root: see the module docstring. Set BEFORE build_plant is called.
ds.SCRATCH = REPO / "_4b12_scratch"

OUT = Path(__file__).resolve().parent
REF = ds.REF
WINDOW_DAYS = ds.WINDOW_DAYS
FROZEN_DAYS = ds.FROZEN_DAYS
DET_TOTAL = ds.DET_TOTAL
WALL_CEILING_S = ds.WALL_CEILING_S
SAT_DET = ds.SAT_DET


#: Suffix appended to this process's SPINE OUTPUT directory. Two processes
#: sweeping the same (orders, alternates) — the CU3 arms, which differ only in
#: `hint_mode` — otherwise both call `prepare_plant` on ONE run dir, and the
#: second wipes and rebuilds the snapshot store the first is reading. The damage
#: is not a crash: a first pass of CU3 produced rows reading 800 free ops where
#: the world has 400, INFEASIBLE at 0.0 deterministic units, because both
#: processes' entities landed in one store. Those rows were discarded, not
#: repaired. The SUBMISSION cache stays shared — it is written once and read
#: thereafter — so the worlds remain identical across tags by construction.
RUN_TAG = ""


def build_plant(orders: int, alternates: int):
    """4B.10's `build_plant` with a per-process run dir. Same generation call,
    same pinned generation seed (1), same cached submission."""
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import prepare_plant

    sub = ds.SCRATCH / f"sub_o{orders}_a{alternates}"
    if not (sub / "manifest.json").exists():
        sub.parent.mkdir(parents=True, exist_ok=True)
        print(f"[world] generating facility_real orders={orders} "
              f"alternates={alternates} ...", flush=True)
        generate(sub, scenario="facility_real", orders=orders, seed=1,
                 fr_machines=4, fr_alternates=alternates)
    out = ds.SCRATCH / f"run_o{orders}_a{alternates}{RUN_TAG}"
    return prepare_plant(sub, out, reference_date=REF)


def _due(d):
    from mre.modules.rolling_horizon import _dt
    return _dt(d["due"])


def past_due_counts(plant, admitted_ids) -> dict:
    """R-PD1's quantities, at the three places a demand can be lost.

    `n_past_due_all` counts the snapshot; `n_past_due_schedulable` counts what
    survived the validator (before R-PD1 this was where they died: Check 1
    excluded them, and Check 5's resumable window-fit test excluded the rest
    under a different code); `n_past_due_admitted` counts what the window's
    admission policy then took. The three being equal is the measurement — it is
    how "gravity did not have to be told" is checked rather than believed."""
    ref = plant.reference_date
    all_pd = [d for d in plant.demands if d.get("due") and _due(d) < ref]
    sched = plant.schedulable_demands
    sched_pd = [d for d in sched if d.get("due") and _due(d) < ref]
    adm_pd = [d for d in sched_pd if d["id"] in admitted_ids]
    floor_min = sum((ref - _due(d)).total_seconds() / 60.0 for d in adm_pd)
    return dict(
        n_demands_total=len(plant.demands),
        n_excluded=len(plant.excluded_demand_ids),
        n_past_due_all=len(all_pd),
        n_past_due_schedulable=len(sched_pd),
        n_past_due_admitted=len(adm_pd),
        past_due_pct_of_book=(round(100.0 * len(all_pd) / len(plant.demands), 2)
                              if plant.demands else None),
        past_due_floor_minutes=round(floor_min, 1),
    )


def window_inputs(plant, window_days=WINDOW_DAYS, frozen_days=FROZEN_DAYS):
    """4B.10's `window_inputs`, plus the admitted ID SET (which it summed away).

    Identical admission call, so the free-op list is the same list 4B.10 built."""
    from mre.modules.rolling_horizon import _admit
    ref = plant.reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
    sched = plant.schedulable_demands
    window_end = ref + timedelta(days=window_days)
    admitted, reasons = _admit(plant, sched, ref, window_end, True, 3.0)
    free_ops = [op for did in sorted(admitted)
                for op in plant.ops_by_wp.get(plant.wp_of_demand.get(did), [])]
    return dict(ref=ref, t0=ref, window_end=window_end,
                win_horizon_end=window_end + timedelta(days=21),
                free_ops=free_ops, admitted=admitted, admit_reasons=reasons,
                n_demands_admitted=len(admitted), n_schedulable=len(sched),
                t0_min=0)


def run_cell(orders: int, alternates: int, seed: int,
             hint_mode: str = "off") -> dict:
    from ortools.sat.python import cp_model as cp
    from mre.modules.rolling_horizon import _build_window, _two_stage_solve

    plant = build_plant(orders, alternates)
    win = window_inputs(plant)
    free_ops = win["free_ops"]

    req_min = sum(ds._iso_minutes(op.get("setup_duration"))
                  + ds._iso_minutes(op.get("run_duration")) for op in free_ops)
    avail_min = ds.calendar_minutes(plant, win["ref"], win["window_end"])

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
        orders=orders, alternates=alternates, seed=seed, hint_mode=hint_mode,
        window_days=WINDOW_DAYS, frozen_days=FROZEN_DAYS,
        det_total=DET_TOTAL, wall_ceiling_s=WALL_CEILING_S,
        n_schedulable=win["n_schedulable"], n_admitted=win["n_demands_admitted"],
        admit_reasons=win["admit_reasons"],
        n_free_ops=n_free, n_machines=n_mach,
        ops_per_machine=round(n_free / n_mach, 1) if n_mach else 0,
        ops_per_machine_eligible_max=(counts[0] if counts else 0),
        required_minutes=round(req_min, 1),
        available_minutes=round(avail_min, 1),
        utilisation_pct=(round(100.0 * req_min / avail_min, 2) if avail_min else None),
        build_s=round(build_s, 3),
        **past_due_counts(plant, win["admitted"]),
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
    row.update(sat_status=ds._status_name(cp, st),
               sat_wall_s=round(time.perf_counter() - t, 2),
               sat_det=float(s.response_proto.deterministic_time),
               sat_wall_truncated=(s.WallTime() >= WALL_CEILING_S - 0.05))

    # --- THE SHIPPED TWO-STAGE COST SOLVE -----------------------------------
    import mre.modules.solve_runner as _sr_mod
    _orig = _sr_mod.SolveRunner
    ds._RecordingRunner.inner_cls = _orig
    ds._RecordingRunner.calls = []
    t = time.perf_counter()
    try:
        _sr_mod.SolveRunner = ds._RecordingRunner
        res, stage2_ran, _recovery = _two_stage_solve(
            model, var_map, free_start_vars,
            workers=1, seed=seed, deterministic=True,
            member_time_limit_s=WALL_CEILING_S, det_total=DET_TOTAL,
            free_op_ids=[op["id"] for op in free_ops],
            hint_mode=hint_mode)
    finally:
        _sr_mod.SolveRunner = _orig
    solve_s = time.perf_counter() - t

    stages = list(ds._RecordingRunner.calls)
    # With a warm start the recorder sees THREE calls: phase 0 (satisfiability),
    # then the two cost stages. Off, it sees the same two 4B.10 saw.
    if hint_mode != "off" and len(stages) >= 1:
        p0 = stages[0]
        stages = stages[1:]
        row.update(phase0_status=p0.get("status"), phase0_det=p0.get("det_consumed"),
                   phase0_budget=p0.get("budget"),
                   phase0_wall_s=(round(p0["wall_time"], 2) if p0.get("wall_time") else None),
                   phase0_wall_truncated=p0.get("wall_truncated"))
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
        stage1_budget=s1.get("budget"), stage1_status=s1.get("status"),
        stage1_det=s1.get("det_consumed"), stage1_gap=s1.get("gap"),
        stage1_wall_s=(round(s1["wall_time"], 2) if s1.get("wall_time") else None),
        stage1_wall_truncated=s1.get("wall_truncated"),
        det_to_proof=(s1.get("det_consumed") if s1.get("status") == "OPTIMAL" else None),
        stage2_budget=s2.get("budget"), stage2_status=s2.get("status"),
        stage2_det=s2.get("det_consumed"),
        stage2_wall_truncated=s2.get("wall_truncated"))
    # CU3 rule (a): the hint is NOT free. The shipped `_two_stage_solve` already
    # counts phase 0 into `det_consumed`, so this is a READBACK, not a sum done
    # here — and the cross-check below fails loudly if the two ever disagree.
    row["det_total_consumed"] = round(res.det_consumed or 0.0, 6)
    _parts = round((row.get("phase0_det") or 0.0) + (s1.get("det_consumed") or 0.0)
                   + (s2.get("det_consumed") or 0.0), 4)
    row["det_parts_sum"] = _parts
    row["det_accounting_ok"] = abs(_parts - (res.det_consumed or 0.0)) < 0.05

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
            row.update(
                ledger_total=led.get("total_cost"),
                ledger_tardiness=led.get("tardiness_cost"),
                # Contract 1.11 (R-PD1 clause 4). ABSENT — not zero — on a book
                # with no past-due work, and recorded as absent for that reason.
                ledger_tardiness_floor=led.get("tardiness_floor_cost"),
                ledger_tardiness_controllable=led.get("tardiness_controllable_cost"),
                ledger_production=led.get("production_cost"),
                ledger_setup=led.get("setup_cost"),
                placed_ops=len(res.solve_values.op_start_minutes),
                late_demands=sum(1 for s3 in r.service_outcomes
                                 if s3.get("lateness_minutes", 0) > 0),
                tardiness_minutes=sum(max(0, s3.get("lateness_minutes", 0))
                                      for s3 in r.service_outcomes),
                tardiness_floor_minutes=sum(s3.get("tardiness_floor_minutes", 0)
                                            for s3 in r.service_outcomes))
        except Exception as exc:      # noqa: BLE001 — diagnostic, never fatal
            row["ledger_error"] = f"{type(exc).__name__}: {exc}"
    else:
        row["ledger_total"] = None
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, nargs="+", required=True)
    ap.add_argument("--alternates", type=int, nargs="+", default=[1])
    ap.add_argument("--seeds", type=int, nargs="+", default=[42])
    ap.add_argument("--hint-mode", default="off",
                    choices=["off", "full", "assign"])
    ap.add_argument("--run-tag", default=None,
                    help="suffix for THIS process's spine output dir; defaults "
                         "to the hint mode, which is what makes the CU3 arms "
                         "safe to run concurrently")
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--out", required=True,
                    help="results file — ONE WRITER PER FILE (4B.10's trap 2)")
    args = ap.parse_args()

    global RUN_TAG
    RUN_TAG = args.run_tag if args.run_tag is not None else (
        "" if args.hint_mode == "off" else f"_{args.hint_mode}")

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = OUT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["orders"], r["alternates"], r["seed"],
                          r.get("hint_mode", "off")))

    started = time.perf_counter()
    for orders in args.orders:
        for alt in args.alternates:
            for seed in args.seeds:
                key = (orders, alt, seed, args.hint_mode)
                if key in done:
                    print(f"[skip] {key}", flush=True)
                    continue
                if (args.max_seconds is not None
                        and time.perf_counter() - started > args.max_seconds):
                    print("[chunk] wall budget reached — stopping cleanly",
                          flush=True)
                    return
                row = run_cell(orders, alt, seed, hint_mode=args.hint_mode)
                with out_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, default=str) + "\n")
                proof = row.get("det_to_proof")
                print(f"[4b12] o={orders:>4} a={alt} s={seed} h={args.hint_mode} "
                      f"free={row['n_free_ops']:>5} opm={row['ops_per_machine']:>6} "
                      f"util={row['utilisation_pct']}% "
                      f"pd={row['n_past_due_admitted']}/{row['n_past_due_all']} "
                      f"S1={row.get('stage1_status')}@{row.get('stage1_det')} "
                      f"proof={'-' if proof is None else round(proof, 3)} "
                      f"gap={row['gap']} total={row.get('ledger_total')} "
                      f"floor={row.get('ledger_tardiness_floor')} "
                      f"wall={row['wall_time']}s trunc={row['wall_truncated']}",
                      flush=True)


if __name__ == "__main__":
    main()

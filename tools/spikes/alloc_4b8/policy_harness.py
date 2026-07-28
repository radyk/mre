#!/usr/bin/env python3
"""Session 4B.8 CU1 — the BUDGET-ALLOCATION measurement (MEASUREMENT ONLY).

Nothing here is reachable from any shipped path. It answers one question with
evidence, before CU2 changes anything: given a fixed total deterministic budget,
how should it be SPLIT between the two stages of the R-SC3 solve?

The instance, the world, the window build, the admission, the extractor pass and
the ledger are all REUSED VERBATIM from ``tools/spikes/tiebreak_4b6c/
arm_harness.py`` (4B.6c). The ONLY thing that varies between policies is the
deterministic budget each stage receives. Every policy runs the SAME arm — A0s,
the staged cost-only shape 4B.7 shipped — so a ledger difference between them is
a BUDGET fact and nothing else.

  P1  CURRENT      stage 1 <= 4.0     stage 2 = fixed 2.0        (shipped)
  P2  COST FIRST   stage 1 <= 6.0     stage 2 = 6.0 - consumed   (MAY BE ZERO)
  P3  RESERVED     stage 1 <= 5.5     stage 2 = 6.0 - consumed   (>= 0.5)

P2 and P3 share the remainder formula; they differ ONLY in stage 1's cap, which
is what guarantees P3 a nonzero stage-2 slice. That is the whole design space the
prompt asks about, and stating it this way makes the comparison one variable wide.

NB the 4B.6c harness's ``run_arm`` cannot be called against HEAD: it imports
``rolling_horizon._earliness_coeff_scaled``, which 4B.7 DELETED on purpose. The
staged loop is therefore re-expressed here over that module's still-live
primitives (``_solve``, ``measure_solution``, ``_rehint``, ``window_inputs``,
``build_plant``) rather than by resurrecting the dead symbol.

Usage:
    python tools/spikes/alloc_4b8/policy_harness.py --probe
    python tools/spikes/alloc_4b8/policy_harness.py \
        --instances 5 8 15 40 120 200:7 --policies P1 P2 P3 --seeds 42 43 44 45 46
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "spikes" / "tiebreak_4b6c"))

import arm_harness as AH   # noqa: E402  — the 4B.6c world, reused not rebuilt

DET_TOTAL = 6.0
WALL_CEILING_S = 1800.0
OUT = Path(__file__).resolve().parent

#: (stage-1 cap, stage-2 rule). "fixed" = a constant regardless of what stage 1
#: spent — the defect under measurement. "remainder" = DET_TOTAL minus what
#: stage 1 actually consumed, floored at zero.
POLICIES = {
    "P1": {"stage1_cap": 4.0, "stage2": ("fixed", 2.0)},
    "P2": {"stage1_cap": 6.0, "stage2": ("remainder", 0.0)},
    "P3": {"stage1_cap": 5.5, "stage2": ("remainder", 0.0)},
}


def stage2_budget(policy: str, stage1_consumed) -> float:
    kind, val = POLICIES[policy]["stage2"]
    if kind == "fixed":
        return float(val)
    spent = float(stage1_consumed or 0.0)
    return max(0.0, DET_TOTAL - spent)


def run_policy(plant, win, orders, window_days, policy, seed):
    """One (instance, policy, seed) run of the STAGED COST-ONLY solve, with the
    policy's budget split. Records BOTH stages: the cost proof is stage 1's and
    the tiebreak proof is stage 2's, and conflating them is the very defect
    CU3 exists to fix."""
    from mre.modules.rolling_horizon import _build_window

    free_ops = win["free_ops"]
    # A FRESH model per run, always: the staged solve MUTATES it (the cap
    # constraint, the second minimize, the hints), so a cached model would make
    # every run after the first a different problem.
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

    terms = var_map.objective_terms
    model.minimize(sum(terms))
    probes = ({"cost_scaled": sum(terms), "start_sum": sum(free_start_vars)}
              if terms and free_start_vars else {})

    cap1 = POLICIES[policy]["stage1_cap"]
    s1 = AH._solve(model, var_map, seed=seed, det=cap1, wall=WALL_CEILING_S,
                   eval_exprs=probes)

    row = dict(orders=orders, window_days=window_days, policy=policy, seed=seed,
               stage1_cap=cap1, build_s=round(build_s, 3),
               n_free_ops=len(free_start_vars),
               stage1_status=s1["status"], stage1_det=s1["det_consumed"],
               stage1_wall=round(s1["wall_s"], 3),
               stage1_objective=s1["objective"],
               wall_truncated=s1["wall_truncated"])

    if s1["solve_values"] is not None:
        m1 = AH.measure_solution(plant, win, var_map, s1["solve_values"],
                                 free_ops, free_start_vars)
        row["stage1_ledger"] = m1["ledger"]
        row["stage1_sum_free_starts_min"] = m1["sum_free_starts_min"]
        row["stage1_tardiness_minutes"] = m1["tardiness_minutes"]

    b2 = stage2_budget(policy, s1["det_consumed"])
    row["stage2_budget"] = round(b2, 4)
    row["stage2_got_zero"] = (b2 <= 0.0)
    row["stage2_ran"] = False
    row["stage2_status"] = None
    row["stage2_det"] = None

    # THE SKIP IS EXPLICIT. A tiebreak that silently did not run is
    # indistinguishable from one that ran and won nothing — so the reason is
    # recorded on every row, including the runs where it is "no reason, it ran".
    if not (terms and free_start_vars and s1["objective"] is not None
            and s1["status"] in ("OPTIMAL", "FEASIBLE")):
        row["stage2_skip_reason"] = "stage1_no_solution_or_degenerate_model"
    elif b2 <= 0.0:
        row["stage2_skip_reason"] = "budget_exhausted_by_stage1"
    else:
        row["stage2_skip_reason"] = None
        best = int(round(s1["objective"]))
        model.add(sum(terms) <= best)
        model.minimize(sum(free_start_vars))
        AH._rehint(model, var_map, s1["solve_values"])
        s2 = AH._solve(model, var_map, seed=seed, det=b2, wall=WALL_CEILING_S,
                       eval_exprs=probes)
        row.update(stage2_status=s2["status"], stage2_det=s2["det_consumed"],
                   stage2_wall=round(s2["wall_s"], 3))
        if s2["status"] in ("OPTIMAL", "FEASIBLE"):
            row["stage2_ran"] = True
            m2 = AH.measure_solution(plant, win, var_map, s2["solve_values"],
                                     free_ops, free_start_vars)
            row["ledger"] = m2["ledger"]
            row["sum_free_starts_min"] = m2["sum_free_starts_min"]
            row["tardiness_minutes"] = m2["tardiness_minutes"]
            row["placed_ops"] = m2["placed_ops"]
        else:
            row["stage2_skip_reason"] = "stage2_no_solution"

    # THE SHIPPED RESULT: stage 1's objective and ledger, stage 2's placements.
    # When stage 2 did not produce a solution, stage 1's incumbent stands whole.
    if not row["stage2_ran"]:
        row["ledger"] = row.get("stage1_ledger")
        row["sum_free_starts_min"] = row.get("stage1_sum_free_starts_min")
        row["tardiness_minutes"] = row.get("stage1_tardiness_minutes")

    row["det_total_consumed"] = round(
        (s1["det_consumed"] or 0.0) + (row["stage2_det"] or 0.0), 4)
    row["det_unused"] = round(DET_TOTAL - row["det_total_consumed"], 4)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", nargs="+",
                    default=["5", "8", "15", "40", "120", "200:7"],
                    help="orders, or orders:window_days (default window 14)")
    ap.add_argument("--policies", nargs="+", default=["P1", "P2", "P3"])
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    ap.add_argument("--out", default=str(OUT / "policy_results.jsonl"))
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()
    if args.probe:
        args.policies, args.seeds = ["P1"], [42]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # RESUMABLE: every (orders, window, policy, seed) already present is skipped.
    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["orders"], r["window_days"], r["policy"], r["seed"]))

    for spec in args.instances:
        orders, _, wd = spec.partition(":")
        orders, wd = int(orders), int(wd or AH.WINDOW_DAYS)
        plant = win = None
        for policy in args.policies:
            for seed in args.seeds:
                key = (orders, wd, policy, seed)
                if key in done:
                    print(f"[skip] {key}", flush=True)
                    continue
                if plant is None:
                    plant = AH.build_plant(orders)
                    win = AH.window_inputs(plant, window_days=wd)
                    print(f"[world] orders={orders} w={wd} "
                          f"free_ops={len(win['free_ops'])}", flush=True)
                t = time.perf_counter()
                row = run_policy(plant, win, orders, wd, policy, seed)
                with out_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, default=str) + "\n")
                print(f"[run] o={orders} w={wd} {policy} s={seed} "
                      f"s1={row['stage1_status']}/{row['stage1_det']} "
                      f"s2={row['stage2_status']}/{row['stage2_det']} "
                      f"ledger={row.get('ledger')} "
                      f"starts={row.get('sum_free_starts_min')} "
                      f"({time.perf_counter() - t:.1f}s)", flush=True)


if __name__ == "__main__":
    main()

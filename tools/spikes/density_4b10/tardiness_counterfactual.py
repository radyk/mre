#!/usr/bin/env python3
"""Session 4B.10 ITEM 3 — THE COUNTERFACTUAL BEHIND THE CLIFF.

The sweep shows a perfect correlation: every cell with ZERO tardiness proved
the cost optimum (0.0002-0.015 deterministic units at alternates=1), and the
first cell with ANY tardiness failed the proof outright (5.59 units spent, an
11.47% gap). The hypothesis that explains it:

  With alternates=1 every operation has exactly ONE eligible machine, so the
  ASSIGNMENT is forced and production + setup cost is a CONSTANT. The only
  placement-dependent term left in the objective is weighted TARDINESS. When
  nothing is late the objective is constant, every feasible solution is optimal
  and CP-SAT proves it immediately. The moment a due date cannot be met, the
  objective becomes a real function of the schedule and the problem is hard.

A correlation over one sweep is not a mechanism, so this PRICES it: the SAME
instance is solved twice, changing ONLY the tardiness weight.

  arm  PRICED    the shipped cost model (base_weight as declared)
  arm  FREE      tardiness_weights.base_weight = 0 and every commitment-class
                 multiplier = 0 -- tardiness costs nothing, so the objective
                 is exactly the constant the hypothesis claims

If FREE proves OPTIMAL near-instantly on an instance where PRICED cannot, the
cliff is the ONSET OF TARDINESS, not density, not utilisation and not op count.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import density_sweep as DS      # noqa: E402  (reuse the world builder exactly)


def run(orders: int, alternates: int, seed: int, free: bool) -> dict:
    from mre.modules.rolling_horizon import _build_window, _two_stage_solve

    plant = DS.build_plant(orders, alternates)
    if free:
        cm = dict(plant.cost_model)
        tw = dict(cm.get("tardiness_weights") or {})
        tw["base_weight"] = 0.0
        for k, v in list(tw.items()):
            if isinstance(v, dict):
                tw[k] = {kk: 0.0 for kk in v}
        cm["tardiness_weights"] = tw
        plant.cost_model = cm

    win = DS.window_inputs(plant)
    free_ops = win["free_ops"]
    t = time.perf_counter()
    model, var_map = _build_window(plant, free_ops, [], win["ref"],
                                   win["win_horizon_end"])
    fsv = []
    for op in free_ops:
        v = var_map.op_start.get(op["id"])
        if v is not None:
            model.add(v >= win["t0_min"])
            fsv.append(v)
    build_s = time.perf_counter() - t

    import mre.modules.solve_runner as _sr
    orig = _sr.SolveRunner
    DS._RecordingRunner.inner_cls = orig
    DS._RecordingRunner.calls = []
    t = time.perf_counter()
    try:
        _sr.SolveRunner = DS._RecordingRunner
        res, stage2_ran, _ = _two_stage_solve(
            model, var_map, fsv, workers=1, seed=seed, deterministic=True,
            member_time_limit_s=DS.WALL_CEILING_S, det_total=DS.DET_TOTAL,
            free_op_ids=[o["id"] for o in free_ops])
    finally:
        _sr.SolveRunner = orig
    solve_s = time.perf_counter() - t
    s1 = DS._RecordingRunner.calls[0] if DS._RecordingRunner.calls else {}

    return dict(orders=orders, alternates=alternates, seed=seed,
                arm=("FREE" if free else "PRICED"),
                n_free_ops=len(fsv), ops_per_machine=len(fsv) / len(plant.resources),
                build_s=round(build_s, 2),
                stage1_status=s1.get("status"), stage1_det=s1.get("det_consumed"),
                det_to_proof=(s1.get("det_consumed")
                              if s1.get("status") == "OPTIMAL" else None),
                gap=s1.get("gap"), objective=s1.get("objective"),
                wall_s=round(solve_s, 1),
                wall_truncated=bool(res.wall_truncated))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, nargs="+", default=[165])
    ap.add_argument("--alternates", type=int, nargs="+", default=[1])
    ap.add_argument("--seeds", type=int, nargs="+", default=[42])
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent
                                         / "tardiness_counterfactual.jsonl"))
    args = ap.parse_args()

    out = Path(args.out)
    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["orders"], r["alternates"], r["seed"], r["arm"]))

    for o in args.orders:
        for a in args.alternates:
            for s in args.seeds:
                for free in (False, True):
                    arm = "FREE" if free else "PRICED"
                    if (o, a, s, arm) in done:
                        print(f"[skip] {o}/{a}/{s}/{arm}", flush=True)
                        continue
                    row = run(o, a, s, free)
                    with out.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(row, default=str) + "\n")
                    p = row["det_to_proof"]
                    print(f"[cf] o={o} a={a} s={s} {arm:<6} "
                          f"opm={row['ops_per_machine']:.0f} "
                          f"S1={row['stage1_status']} "
                          f"det={row['stage1_det']:.4f} "
                          f"proof={'-' if p is None else f'{p:.4f}'} "
                          f"gap={row['gap']} wall={row['wall_s']}s "
                          f"trunc={row['wall_truncated']}", flush=True)


if __name__ == "__main__":
    main()

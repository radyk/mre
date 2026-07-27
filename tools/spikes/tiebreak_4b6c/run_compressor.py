#!/usr/bin/env python3
"""Session 4B.6c item 3 driver — measure C on A0's solutions, and A2h + C
stacked. SCRATCH ONLY.

    python tools/spikes/tiebreak_4b6c/run_compressor.py --orders 40 --seeds 42 43 44 45 46
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import arm_harness as H          # noqa: E402
import compressor as C           # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, nargs="+", default=[40])
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    ap.add_argument("--arms", nargs="+", default=["A0", "A2h"])
    ap.add_argument("--det", type=float, default=H.DET_TOTAL)
    ap.add_argument("--window", type=int, default=H.WINDOW_DAYS)
    ap.add_argument("--frozen", type=int, default=H.FROZEN_DAYS)
    ap.add_argument("--out", default=str(HERE / "compressor_results.jsonl"))
    args = ap.parse_args()

    fh = Path(args.out).open("a", encoding="utf-8")
    for orders in args.orders:
        plant = H.build_plant(orders)
        H._ORDERS_ATTR[id(plant)] = orders
        win = H.window_inputs(plant, args.window, args.frozen)
        free_ops = win["free_ops"]
        for arm in args.arms:
            for seed in args.seeds:
                row, payload = H.run_arm(plant, win, arm, seed,
                                         det_total=args.det, keep_placements=True)
                if payload is None:
                    fh.write(json.dumps({"orders": orders, "arm": arm,
                                         "seed": seed, "error": "no solution",
                                         "status": row["status"]}) + "\n")
                    fh.flush()
                    continue
                var_map, sv = payload["var_map"], payload["sv"]

                def ledger_of(cand, _vm=var_map):
                    return H.extract_ledger(plant, win, _vm, cand, free_ops).cost_ledger

                base_total = (row["ledger"] or {}).get("total_cost")
                out = {"orders": orders, "arm": arm, "seed": seed,
                       "window_days": args.window, "frozen_days": args.frozen,
                       "status": row["status"], "base_total": base_total,
                       "base_sum_starts": row["sum_free_starts_min"],
                       "base_ledger": row["ledger"],
                       "base_wip": {k: row[k] for k in
                                    ("total_dwell_min", "mean_wip_wp",
                                     "peak_wip_wp", "dwell_ops")}}
                for variant, respect in (("C_free", False), ("C_frozen", True)):
                    t = time.perf_counter()
                    final, st = C.compress(plant, win, var_map, sv, free_ops,
                                           respect_frozen=respect,
                                           ledger_of=ledger_of,
                                           base_total=base_total)
                    st["compress_wall_s"] = round(time.perf_counter() - t, 3)
                    led = ledger_of(final)
                    st["ledger_after"] = led
                    st["wip_after"] = H.wip_proxies(plant, final, free_ops)
                    placements = {oid: (final.op_resource[oid],
                                        final.op_start_minutes[oid])
                                  for oid in final.op_start_minutes}
                    t = time.perf_counter()
                    st["validation_status"] = C.validate(plant, win, placements)
                    st["validate_wall_s"] = round(time.perf_counter() - t, 3)
                    out[variant] = st
                    print(f"  {orders} {arm} seed={seed} {variant}: "
                          f"moved={st['moved']} rejected={st['rejected_overtime']} "
                          f"dS={st['start_reduction_min']} "
                          f"total {st['total_before']} -> {st['total_after']} "
                          f"valid={st['validation_status']}", flush=True)
                fh.write(json.dumps(out, default=str) + "\n")
                fh.flush()
    fh.close()


if __name__ == "__main__":
    main()

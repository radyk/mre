#!/usr/bin/env python3
"""Session 4B.6c item 3 — summarize compressor_results.jsonl. SCRATCH."""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent


def fmt(x, n=2):
    return "-" if x is None else (f"{x:,.{n}f}" if isinstance(x, float) else f"{x:,}")


rows = [json.loads(l) for l in (HERE / "compressor_results.jsonl").read_text(
    encoding="utf-8").splitlines() if l.strip()]

print("=" * 132)
print("THE COMPRESSOR (C) — sequence-preserving left-shift over a solved schedule; FULL ledger recomputed after every shift")
print("=" * 132)
hdr = (f"{'instance':<14} {'from':<5} {'variant':<9} {'seed':>4} {'movable':>8} {'moved':>6} "
       f"{'rejected':>9} {'rej $':>9} {'sum starts before':>18} {'after':>14} {'won':>12} "
       f"{'ledger before':>14} {'ledger after':>14} {'validated':>10}")
print(hdr)
print("-" * 132)
for r in rows:
    label = f"{r['orders']}o w{r.get('window_days',14)}"
    for variant in ("C_free", "C_frozen"):
        s = r.get(variant)
        if not s:
            continue
        print(f"{label:<14} {r['arm']:<5} {variant:<9} {r['seed']:>4} "
              f"{s['considered']:>8} {s['moved']:>6} {s['rejected_overtime']:>9} "
              f"{fmt(s['rejected_magnitude']):>9} "
              f"{fmt(s['sum_starts_before'],0):>18} {fmt(s['sum_starts_after'],0):>14} "
              f"{fmt(s['start_reduction_min'],0):>12} "
              f"{fmt(s['total_before']):>14} {fmt(s['total_after']):>14} "
              f"{s['validation_status']:>10}")
print()
print("ROLLUP")
for variant in ("C_free", "C_frozen"):
    tot_rej = sum(r[variant]["rejected_overtime"] for r in rows if r.get(variant))
    mag = sum(r[variant]["rejected_magnitude"] for r in rows if r.get(variant))
    n = sum(1 for r in rows if r.get(variant))
    bad = [r for r in rows if r.get(variant)
           and r[variant]["validation_status"] not in ("OPTIMAL", "FEASIBLE")]
    rose = [r for r in rows if r.get(variant)
            and r[variant]["total_after"] > r[variant]["total_before"] + 1e-9]
    print(f"  {variant}: {n} runs, rejected shifts {tot_rej} "
          f"(total magnitude {fmt(mag)}), runs whose ledger ROSE {len(rose)}, "
          f"validation failures {len(bad)}")
print()
print("STACKED — A2h + C vs each alone (start-time reduction, C_frozen)")
by = {}
for r in rows:
    by[(r["orders"], r.get("window_days", 14), r["arm"], r["seed"])] = r
for key in sorted(k for k in by if k[2] == "A2h"):
    o, w, _, seed = key
    a2h = by[key]
    a0 = by.get((o, w, "A0", seed))
    if not a0:
        continue
    a0_s = a0["base_sum_starts"]
    print(f"  {o}o w{w} seed {seed}: A0 alone {fmt(a0_s,0):>12} | "
          f"A0+C {fmt(a0['C_frozen']['sum_starts_after'],0):>12} | "
          f"A2h alone {fmt(a2h['base_sum_starts'],0):>12} | "
          f"A2h+C {fmt(a2h['C_frozen']['sum_starts_after'],0):>12} | "
          f"ledger A0 {fmt(a0['base_total']):>12} A2h+C {fmt(a2h['C_frozen']['total_after']):>12}")
print()
print("DIRECTION NUMBERS — dwell before/after compression (item 5, C_frozen)")
for r in rows:
    s = r.get("C_frozen")
    if not s:
        continue
    print(f"  {r['orders']}o w{r.get('window_days',14)} {r['arm']:<4} seed {r['seed']}: "
          f"dwell {fmt(r['base_wip']['total_dwell_min'],0):>10} -> "
          f"{fmt(s['wip_after']['total_dwell_min'],0):>10} | "
          f"mean WIP {fmt(r['base_wip']['mean_wip_wp'])} -> {fmt(s['wip_after']['mean_wip_wp'])} | "
          f"peak {r['base_wip']['peak_wip_wp']} -> {s['wip_after']['peak_wip_wp']}")

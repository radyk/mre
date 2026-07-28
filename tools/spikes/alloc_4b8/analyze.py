#!/usr/bin/env python3
"""Session 4B.8 CU1 — the policy table.

Reads policy_results.jsonl and prints, per (instance, policy): ledger median and
spread across seeds, the STAGE-1 OPTIMAL count (the cost proof is the thing that
matters — stage 2 proves the TIEBREAK, which is a different claim), the sum of
free-op start minutes, the deterministic units each stage consumed, and how often
stage 2 received a zero slice.
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
POLICY_ORDER = ["P1", "P2", "P3"]


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def load(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else HERE / "policy_results.jsonl"
    rows = load(path)
    by = defaultdict(list)
    for r in rows:
        by[(r["orders"], r["window_days"], r["policy"])].append(r)

    instances = sorted({(k[0], k[1]) for k in by})
    hdr = (f"{'inst':>8} {'pol':>4} {'n':>2} {'s1 OPT':>7} {'ledger med':>12} "
           f"{'spread':>9} {'starts med':>11} {'s1 det':>7} {'s2 det':>7} "
           f"{'unused':>7} {'s2=0':>5} {'s2 OPT':>7}")
    print(hdr)
    print("-" * len(hdr))
    for orders, wd in instances:
        for pol in POLICY_ORDER:
            rs = by.get((orders, wd, pol))
            if not rs:
                continue
            led = [r["ledger"]["total_cost"] for r in rs if r.get("ledger")]
            starts = [r.get("sum_free_starts_min") for r in rs]
            s1opt = sum(1 for r in rs if r["stage1_status"] == "OPTIMAL")
            s2opt = sum(1 for r in rs if r.get("stage2_status") == "OPTIMAL")
            zero = sum(1 for r in rs if r.get("stage2_got_zero"))
            spread = (max(led) - min(led)) if led else None
            d1 = med([r["stage1_det"] for r in rs])
            d2 = med([r.get("stage2_det") for r in rs])
            un = med([r["det_unused"] for r in rs])
            n = len(rs)
            c_inst = f"{orders}w{wd}"
            c_led = f"{med(led):,.2f}" if led else "-"
            c_spr = f"{spread:,.2f}" if spread is not None else "-"
            c_sta = f"{med(starts):,.0f}" if med(starts) is not None else "-"
            c_d1 = f"{d1:.3f}" if d1 is not None else "-"
            c_d2 = f"{d2:.3f}" if d2 is not None else "-"
            c_un = f"{un:.3f}" if un is not None else "-"
            print(f"{c_inst:>8} {pol:>4} {n:>2} {f'{s1opt}/{n}':>7} {c_led:>12} "
                  f"{c_spr:>9} {c_sta:>11} {c_d1:>7} {c_d2:>7} {c_un:>7} "
                  f"{f'{zero}/{n}':>5} {f'{s2opt}/{n}':>7}")
        print()

    # The 120-order question the recommendation must answer with numbers:
    # under P2, what does stage 1's EXTRA budget buy, and is it more than the
    # start-minute reduction stage 2 wins there?
    print("=" * 78)
    print("THE 120-ORDER QUESTION (and every other instance, same shape)")
    print("=" * 78)
    for orders, wd in instances:
        p1 = by.get((orders, wd, "P1"), [])
        p2 = by.get((orders, wd, "P2"), [])
        p3 = by.get((orders, wd, "P3"), [])
        if not (p1 and p2):
            continue
        l1, l2 = med([r["ledger"]["total_cost"] for r in p1 if r.get("ledger")]), \
                 med([r["ledger"]["total_cost"] for r in p2 if r.get("ledger")])
        l3 = med([r["ledger"]["total_cost"] for r in p3 if r.get("ledger")]) if p3 else None
        s1, s2 = med([r.get("sum_free_starts_min") for r in p1]), \
                 med([r.get("sum_free_starts_min") for r in p2])
        s3 = med([r.get("sum_free_starts_min") for r in p3]) if p3 else None
        print(f"\n{orders} orders / {wd}d:")
        print(f"  ledger   P1 {l1:>14,.2f} | P2 {l2:>14,.2f}"
              + (f" | P3 {l3:>14,.2f}" if l3 is not None else ""))
        if l1:
            print(f"           P2 vs P1 {100 * (l2 - l1) / l1:+7.2f}%"
                  + (f" | P3 vs P1 {100 * (l3 - l1) / l1:+7.2f}%" if l3 is not None else ""))
        print(f"  starts   P1 {s1:>14,.0f} | P2 {s2:>14,.0f}"
              + (f" | P3 {s3:>14,.0f}" if s3 is not None else ""))
        if s1:
            print(f"           P2 vs P1 {100 * (s2 - s1) / s1:+7.2f}%"
                  + (f" | P3 vs P1 {100 * (s3 - s1) / s1:+7.2f}%" if s3 is not None else ""))
        # what stage 1's extra budget BOUGHT: P1 stage-1 ledger vs P2 stage-1 ledger
        b1 = med([r.get("stage1_ledger", {}).get("total_cost")
                  for r in p1 if r.get("stage1_ledger")])
        b2 = med([r.get("stage1_ledger", {}).get("total_cost")
                  for r in p2 if r.get("stage1_ledger")])
        if b1 and b2:
            print(f"  STAGE-1-ONLY ledger  P1 {b1:>14,.2f} | P2 {b2:>14,.2f}"
                  f"   -> extra stage-1 budget bought {b1 - b2:+,.2f}")


if __name__ == "__main__":
    main()

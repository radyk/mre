#!/usr/bin/env python3
"""Session 4B.6c — turn arm_results.jsonl into the three-arm table. SCRATCH."""
from __future__ import annotations

import argparse
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = ["A0", "A1", "A2", "A2h", "A2x"]


def med(xs):
    return st.median(xs) if xs else None


def fmt(x, n=2):
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:,.{n}f}"
    return f"{x:,}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(HERE / "arm_results.jsonl"))
    args = ap.parse_args()

    rows = [json.loads(l) for l in Path(args.file).read_text(encoding="utf-8").splitlines() if l.strip()]
    by = defaultdict(list)
    for r in rows:
        key = (r["orders"], r.get("window_days", 14), r.get("frozen_days", 3))
        by[(key, r["arm"])].append(r)

    keys = sorted({k for k, _ in by}, key=lambda k: (k[0], k[1]))

    print("=" * 118)
    print("THREE-ARM TABLE  (ledger total cost is THE comparison; raw objective values are NOT comparable across arms)")
    print("=" * 118)
    hdr = (f"{'instance':<18} {'arm':<5} {'n':>2} {'OPT':>3} {'TRUNC':>5} "
           f"{'ledger median':>14} {'min':>13} {'max':>13} {'spread':>10} "
           f"{'tardiness med':>14} {'sum starts med':>15} {'wall med':>9} {'det med':>8}")
    print(hdr)
    print("-" * 118)
    summary = {}
    for k in keys:
        label = f"{k[0]}o w{k[1]}/f{k[2]}"
        for arm in ARMS:
            rs = by.get((k, arm), [])
            if not rs:
                continue
            usable = [r for r in rs if not r.get("wall_truncated")]
            trunc = len(rs) - len(usable)
            led = [r["ledger"]["total_cost"] for r in usable if r.get("ledger")]
            tard = [r["ledger"]["tardiness_cost"] for r in usable if r.get("ledger")]
            ss = [r["sum_free_starts_min"] for r in usable if r.get("sum_free_starts_min") is not None]
            nopt = sum(1 for r in usable if r["status"] == "OPTIMAL")
            spread = (max(led) - min(led)) if led else None
            summary[(k, arm)] = dict(n=len(rs), opt=nopt, trunc=trunc,
                                     led_med=med(led), led_min=min(led) if led else None,
                                     led_max=max(led) if led else None, spread=spread,
                                     tard_med=med(tard), ss_med=med(ss),
                                     statuses=[r["status"] for r in rs])
            s = summary[(k, arm)]
            print(f"{label:<18} {arm:<5} {len(rs):>2} {nopt:>3} {trunc:>5} "
                  f"{fmt(s['led_med']):>14} {fmt(s['led_min']):>13} {fmt(s['led_max']):>13} "
                  f"{fmt(spread):>10} {fmt(s['tard_med']):>14} {fmt(s['ss_med'],0):>15} "
                  f"{fmt(med([r['wall_s'] for r in usable]),1):>9} "
                  f"{fmt(med([r['det_consumed'] for r in usable if r.get('det_consumed') is not None]),2):>8}")
        print("-" * 118)

    print()
    print("=" * 100)
    print("THE THREE READINGS")
    print("=" * 100)
    for k in keys:
        label = f"{k[0]} orders, window {k[1]}d / frozen {k[2]}d"
        a0 = summary.get((k, "A0"))
        if not a0 or a0["led_med"] is None:
            print(f"\n{label}: A0 produced no ledger — instance EXCLUDED "
                  f"(statuses {a0['statuses'] if a0 else 'none'})")
            continue
        print(f"\n{label}   [A0 median {fmt(a0['led_med'])}, seed spread {fmt(a0['spread'])}]")
        for arm in ("A2", "A2h", "A2x", "A1"):
            s = summary.get((k, arm))
            if not s or s["led_med"] is None:
                print(f"   {arm:<4} no ledger (statuses {s['statuses'] if s else 'not run'})")
                continue
            d = s["led_med"] - a0["led_med"]
            pct = d / a0["led_med"] * 100.0
            worse_than_spread = abs(d) > (a0["spread"] or 0.0)
            ss_win = (a0["ss_med"] - s["ss_med"]) if (a0["ss_med"] and s["ss_med"]) else None
            ss_pct = (ss_win / a0["ss_med"] * 100.0) if ss_win is not None and a0["ss_med"] else None
            starts = (f"| starts {fmt(s['ss_med'],0):>12} won {fmt(ss_win,0):>10} "
                      f"({ss_pct:+6.2f}%)") if ss_pct is not None else ""
            print(f"   {arm:<4} ledger {fmt(s['led_med']):>13}  "
                  f"delta {('+' if d >= 0 else '')+fmt(d):>12} "
                  f"({pct:+7.2f}%)  worse-than-A0-spread: "
                  f"{'YES' if worse_than_spread else 'no':<3}  {starts}")
    print()
    print("=" * 100)
    print("CORRECTNESS CHECK — where BOTH A0 and the candidate prove OPTIMAL, ledgers must be IDENTICAL")
    print("=" * 100)
    for k in keys:
        a0 = summary.get((k, "A0"))
        if not a0 or a0["opt"] == 0:
            continue
        for arm in ("A2", "A2h", "A2x"):
            s = summary.get((k, arm))
            if not s or s["opt"] == 0:
                continue
            same = (s["led_min"] == a0["led_min"] == s["led_max"] == a0["led_max"])
            verdict = "OK" if same else "*** DEFECT ***"
            print(f"  {k[0]:>4}o w{k[1]}  A0 {fmt(a0['led_min'])} ({a0['opt']}/{a0['n']} OPT)  vs  "
                  f"{arm} {fmt(s['led_min'])} ({s['opt']}/{s['n']} OPT)   {verdict}")

    print()
    print("=" * 100)
    print("MAGNITUDES / int64 HEADROOM (item 2a)")
    print("=" * 100)
    seen = set()
    for r in rows:
        m = r.get("magnitudes") or {}
        key = (r["orders"], r.get("window_days", 14), r["arm"])
        if key in seen or not m.get("BIG"):
            continue
        seen.add(key)
        print(f"  {r['orders']:>4}o w{r.get('window_days',14)} {r['arm']:<4} "
              f"n_free={m.get('n_free_ops'):>4} start_range={m.get('start_range'):>8,} "
              f"BIG={m.get('BIG'):>16,} max_sum_starts={m.get('max_sum_starts',0):>14,} "
              f"|obj|max={m.get('objective_worst_case_magnitude') or 0:>22,} "
              f"int64_headroom={(m.get('int64_headroom_x') or 0):>12,.0f}x")

    print()
    print("=" * 100)
    print("DIRECTION NUMBERS (item 5) — report only")
    print("=" * 100)
    print(f"{'instance':<18} {'arm':<5} {'dwell median (min)':>19} {'mean WIP (wp)':>14} {'peak WIP':>9} {'sum starts':>12}")
    for k in keys:
        for arm in ARMS:
            rs = [r for r in by.get((k, arm), []) if r.get("ledger")]
            if not rs:
                continue
            print(f"{str(k[0])+'o w'+str(k[1]):<18} {arm:<5} "
                  f"{fmt(med([r['total_dwell_min'] for r in rs]),0):>19} "
                  f"{fmt(med([r['mean_wip_wp'] for r in rs]),2):>14} "
                  f"{fmt(med([r['peak_wip_wp'] for r in rs]),0):>9} "
                  f"{fmt(med([r['sum_free_starts_min'] for r in rs]),0):>12}")


if __name__ == "__main__":
    main()

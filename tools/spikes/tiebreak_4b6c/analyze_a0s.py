#!/usr/bin/env python3
"""Session 4B.7 item 1 — the A0s arm against A0 and A1, per seed. SCRATCH.

Two conditions, stated pass/fail rather than left to judgement:

  (i)  COST SAFETY. The cap guarantees "stage 2's cost <= stage 1's cost"
       WITHIN a run — that is the units check, and it is reported first and
       per row. Comparing A0s to A0 ALSO crosses a budget split (A0s stage 1
       gets DET_STAGE1=4.0; A0 gets DET_TOTAL=6.0), so a gap there is a
       budget fact and is reported separately, per seed, never fused.
  (ii) THE TIEBREAK EARNS ITS PLACE. A0s sum-of-starts strictly lower than
       A0's, checked on the instances where A0 proves OPTIMAL.
"""
from __future__ import annotations

import json
import statistics as st
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def fmt(x, n=2):
    if x is None:
        return "-"
    return f"{x:,.{n}f}" if isinstance(x, float) else f"{x:,}"


def main():
    rows = [json.loads(l) for l in (HERE / "arm_results.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()]
    by = {}
    for r in rows:
        by[((r["orders"], r.get("window_days", 14)), r["arm"], r["seed"])] = r
    insts = sorted({(r["orders"], r.get("window_days", 14)) for r in rows},
                   key=lambda k: (k[0], k[1]))
    insts = [k for k in insts if k != (200, 14)]     # A0-only budget probe
    seeds = [42, 43, 44, 45, 46]

    print("=" * 112)
    print("A0s — STAGED COST-ONLY (4B.7 item 1). Per seed, against A0 (single solve, full budget) and A1 (shipped).")
    print("=" * 112)
    hdr = (f"{'instance':<12} {'seed':>4} | {'A0 status':<9} {'A0 ledger':>12} {'A0 starts':>11} | "
           f"{'A0s st':<9} {'A0s ledger':>12} {'A0s starts':>11} | {'A1 ledger':>12} {'A1 starts':>11}")
    print(hdr)
    print("-" * 112)
    for k in insts:
        for s in seeds:
            a0 = by.get((k, "A0", s))
            a0s = by.get((k, "A0s", s))
            a1 = by.get((k, "A1", s))
            def led(r):
                return (r.get("ledger") or {}).get("total_cost") if r else None
            print(f"{str(k[0])+'o w'+str(k[1]):<12} {s:>4} | "
                  f"{(a0 or {}).get('status','-'):<9} {fmt(led(a0)):>12} {fmt((a0 or {}).get('sum_free_starts_min'),0):>11} | "
                  f"{(a0s or {}).get('status','-'):<9} {fmt(led(a0s)):>12} {fmt((a0s or {}).get('sum_free_starts_min'),0):>11} | "
                  f"{fmt(led(a1)):>12} {fmt((a1 or {}).get('sum_free_starts_min'),0):>11}")
        print("-" * 112)

    # ---- (i-a) THE UNITS CHECK: stage 2 cost <= stage 1 cost, within each A0s run
    print()
    print("=" * 112)
    print("(i-a) UNITS CHECK — within each A0s run, stage-2 ledger <= stage-1 ledger. "
          "This is what the cap guarantees.")
    print("=" * 112)
    viol = []
    for k in insts:
        for s in seeds:
            r = by.get((k, "A0s", s))
            if not r:
                continue
            stg = r.get("stages") or {}
            s1 = (stg.get("stage1_ledger") or {}).get("total_cost")
            s2 = (r.get("ledger") or {}).get("total_cost")
            if s1 is None or s2 is None:
                continue
            ok = s2 <= s1 + 1e-6
            if not ok:
                viol.append((k, s, s1, s2))
            print(f"  {str(k[0])+'o w'+str(k[1]):<12} seed={s}  stage1 {fmt(s1):>13}  ->  stage2 {fmt(s2):>13}   "
                  f"delta {fmt(s2-s1):>10}   {'OK' if ok else '*** DEFECT ***'}")
    print()
    print(f"  VERDICT (i-a): {'PASS — no run raised cost through stage 2' if not viol else '*** FAIL *** ' + str(viol)}")

    # ---- (i-b) BUDGET COMPARISON: A0s vs A0, per seed
    print()
    print("=" * 112)
    print("(i-b) A0s vs A0, per seed. NOT a units claim — A0s stage 1 gets 4.0 deterministic units, A0 gets 6.0.")
    print("=" * 112)
    worse = []
    for k in insts:
        for s in seeds:
            a0, a0s = by.get((k, "A0", s)), by.get((k, "A0s", s))
            if not a0 or not a0s:
                continue
            l0 = (a0.get("ledger") or {}).get("total_cost")
            ls = (a0s.get("ledger") or {}).get("total_cost")
            if l0 is None or ls is None:
                continue
            if ls > l0 + 1e-6:
                worse.append((k, s, l0, ls, a0["status"], a0s["status"]))
    if not worse:
        print("  PASS — A0s ledger <= A0 ledger on every instance and every seed.")
    else:
        print(f"  {len(worse)} seed(s) where A0s is DEARER than A0:")
        for k, s, l0, ls, st0, sts in worse:
            print(f"    {k[0]}o w{k[1]} seed={s}: A0 {fmt(l0)} ({st0})  ->  A0s {fmt(ls)} ({sts})  "
                  f"+{fmt(ls-l0)} ({(ls-l0)/l0*100:+.2f}%)")

    # ---- (ii) THE TIEBREAK EARNS ITS PLACE
    print()
    print("=" * 112)
    print("(ii) THE TIEBREAK EARNS ITS PLACE — A0s sum-of-starts vs A0's, on the instances where A0 proves OPTIMAL.")
    print("=" * 112)
    for k in insts:
        a0s_all = [by.get((k, "A0", s)) for s in seeds]
        if not all(a0s_all):
            continue
        opt = all(r["status"] == "OPTIMAL" for r in a0s_all)
        m0 = st.median([r["sum_free_starts_min"] for r in a0s_all])
        rs = [by.get((k, "A0s", s)) for s in seeds]
        if not all(rs):
            continue
        ms = st.median([r["sum_free_starts_min"] for r in rs])
        strict = all(by[(k, "A0s", s)]["sum_free_starts_min"]
                     <= by[(k, "A0", s)]["sum_free_starts_min"] for s in seeds)
        anywin = any(by[(k, "A0s", s)]["sum_free_starts_min"]
                     < by[(k, "A0", s)]["sum_free_starts_min"] for s in seeds)
        pct = (m0 - ms) / m0 * 100.0 if m0 else 0.0
        print(f"  {str(k[0])+'o w'+str(k[1]):<12} A0 {'OPTIMAL 5/5' if opt else 'not proven '}  "
              f"starts A0 {fmt(m0,0):>12} -> A0s {fmt(ms,0):>12}   won {fmt(m0-ms,0):>12} ({pct:+6.2f}%)   "
              f"{'STRICT WIN' if (strict and anywin) else ('no win' if not anywin else 'mixed')}")

    # ---- stage budget behaviour
    print()
    print("=" * 112)
    print("STAGE BUDGET BEHAVIOUR — stage 2 gets the FIXED _STAGE2_DET_TIME_S (2.0), not the remainder.")
    print("=" * 112)
    print(f"  {'instance':<12} {'seed':>4} {'s1 status':<9} {'s1 det':>9} {'s2 status':<9} {'s2 det':>9} "
          f"{'s1 wall':>9} {'s2 wall':>9}")
    for k in insts:
        for s in seeds:
            r = by.get((k, "A0s", s))
            if not r:
                continue
            g = r.get("stages") or {}
            print(f"  {str(k[0])+'o w'+str(k[1]):<12} {s:>4} {str(g.get('stage1_status')):<9} "
                  f"{fmt(g.get('stage1_det'),3):>9} {str(g.get('stage2_status')):<9} "
                  f"{fmt(g.get('stage2_det'),3):>9} {fmt(g.get('stage1_wall'),1):>9} "
                  f"{fmt(g.get('stage2_wall'),1):>9}")

    # ---- tardiness
    print()
    print("=" * 112)
    print("TARDINESS COMPONENT (ledger dollars), median over seeds")
    print("=" * 112)
    print(f"  {'instance':<12} {'A0':>14} {'A0s':>14} {'A1':>14}")
    for k in insts:
        def tmed(arm):
            v = [(by[(k, arm, s)].get("ledger") or {}).get("tardiness_cost")
                 for s in seeds if (k, arm, s) in by
                 and by[(k, arm, s)].get("ledger")]
            return st.median(v) if v else None
        print(f"  {str(k[0])+'o w'+str(k[1]):<12} {fmt(tmed('A0')):>14} {fmt(tmed('A0s')):>14} {fmt(tmed('A1')):>14}")


if __name__ == "__main__":
    main()

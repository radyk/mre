#!/usr/bin/env python3
"""Session 4B.10 ITEM 3 — read density.jsonl and answer the three questions.

  Q1  WHERE IS THE CLIFF in ops/machine on the real shape?
  Q2  DO ALTERNATES HELP OR HURT?
  Q3  DOES THE CLIFF TRACK UTILISATION rather than op count?

Rows whose `wall_truncated` is True are EXCLUDED and counted — a wall-stopped
solve is a lottery under this repository's own hard rule, not a measurement.
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent


def load(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "density.jsonl"
    rows = load(path)
    # A duplicated (orders, alternates, seed) means two sweep processes wrote to
    # one file — the runs contend for CPU and the wall clock stops meaning what
    # it says. Fail loudly rather than average over it.
    keys = [(r["orders"], r["alternates"], r["seed"]) for r in rows]
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        raise SystemExit(
            f"REFUSING TO ANALYZE: {len(dupes)} duplicated cell(s) in {path.name} "
            f"— concurrent writers. {sorted(dupes)[:6]}")
    kept = [r for r in rows if not r.get("wall_truncated")]
    dropped = [r for r in rows if r.get("wall_truncated")]
    print(f"rows={len(rows)}  kept={len(kept)}  "
          f"EXCLUDED for wall truncation={len(dropped)}")
    if dropped:
        for r in dropped:
            print(f"  DROPPED o={r['orders']} a={r['alternates']} s={r['seed']} "
                  f"wall={r['wall_time']}s")
    print(f"config: window={kept[0]['window_days']}d frozen={kept[0]['frozen_days']}d "
          f"det_total={kept[0]['det_total']} wall_ceiling={kept[0]['wall_ceiling_s']}s "
          f"machines={kept[0]['n_machines']}")

    # ---------------------------------------------------------------- table
    print("\n" + "=" * 108)
    print("PER CELL")
    print("=" * 108)
    hdr = (f"{'ord':>5}{'alt':>4}{'seed':>5}{'ops':>6}{'ops/m':>7}{'util%':>8}"
           f"{'S1':>9}{'proof':>9}{'gap':>9}{'tiebrk':>9}"
           f"{'ledger':>13}{'tard':>10}{'wall_s':>8}")
    print(hdr)
    for r in sorted(kept, key=lambda x: (x["orders"], x["alternates"], x["seed"])):
        proof = r.get("det_to_proof")
        gap = r.get("gap")
        print(f"{r['orders']:>5}{r['alternates']:>4}{r['seed']:>5}"
              f"{r['n_free_ops']:>6}{r['ops_per_machine']:>7.0f}"
              f"{(r['utilisation_pct'] or 0):>8.1f}"
              f"{str(r.get('stage1_status'))[:8]:>9}"
              f"{('-' if proof is None else f'{proof:.3f}'):>9}"
              f"{('-' if gap is None else f'{gap:.4f}'):>9}"
              f"{str(r.get('tiebreak_status'))[:8]:>9}"
              f"{(r.get('ledger_total') or 0):>13,.0f}"
              f"{(r.get('tardiness_minutes') or 0):>10,.0f}"
              f"{r['wall_time']:>8.0f}")

    # ------------------------------------------------------------------ Q1
    print("\n" + "=" * 108)
    print("Q1 — WHERE IS THE CLIFF? (status of the COST PROOF, stage 1)")
    print("=" * 108)
    by = defaultdict(list)
    for r in kept:
        by[(r["orders"], r["alternates"])].append(r)
    print(f"{'ord':>5}{'alt':>4}{'ops/m':>7}{'util%':>8}{'n':>4}"
          f"{'OPTIMAL':>9}{'proof_med':>11}{'gap_med':>10}{'ledger_spread%':>16}")
    for k in sorted(by):
        g = by[k]
        opt = [r for r in g if r.get("stage1_status") == "OPTIMAL"]
        proofs = [r["det_to_proof"] for r in opt if r.get("det_to_proof") is not None]
        gaps = [r["gap"] for r in g if r.get("gap") is not None]
        leds = [r["ledger_total"] for r in g if r.get("ledger_total") is not None]
        spread = (100 * (max(leds) - min(leds)) / min(leds)) if len(leds) > 1 and min(leds) else 0.0
        print(f"{k[0]:>5}{k[1]:>4}{g[0]['ops_per_machine']:>7.0f}"
              f"{(g[0]['utilisation_pct'] or 0):>8.1f}{len(g):>4}"
              f"{f'{len(opt)}/{len(g)}':>9}"
              f"{('-' if not proofs else f'{st.median(proofs):.3f}'):>11}"
              f"{('-' if not gaps else f'{st.median(gaps):.4f}'):>10}"
              f"{spread:>15.3f}%")

    # find the transition
    print("\n  CLIFF LOCATION — the first density at which the cost proof fails:")
    for alt in sorted({r["alternates"] for r in kept}):
        seq = sorted({(r["orders"], r["ops_per_machine"], r["utilisation_pct"] or 0.0)
                      for r in kept if r["alternates"] == alt})
        last_ok, first_bad = None, None
        for o, opm, util in seq:
            g = [r for r in kept if r["orders"] == o and r["alternates"] == alt]
            allopt = g and all(r.get("stage1_status") == "OPTIMAL" for r in g)
            if allopt:
                last_ok = (o, opm, util)
            elif first_bad is None:
                first_bad = (o, opm, util)
        print(f"    alternates={alt}: last all-OPTIMAL = {last_ok}   "
              f"first non-OPTIMAL = {first_bad}")

    # ------------------------------------------------------------------ Q2
    print("\n" + "=" * 108)
    print("Q2 — DO ALTERNATES HELP OR HURT? (same load, same machines: only")
    print("     eligibility differs, so this is a controlled comparison)")
    print("=" * 108)
    print(f"{'ord':>5}{'ops/m':>7}{'ledger a=1':>14}{'ledger a=2':>14}{'delta%':>9}"
          f"{'proof a=1':>11}{'proof a=2':>11}{'x':>8}{'status a1/a2':>16}")
    for o in sorted({r["orders"] for r in kept}):
        g1 = [r for r in kept if r["orders"] == o and r["alternates"] == 1]
        g2 = [r for r in kept if r["orders"] == o and r["alternates"] == 2]
        if not g1 or not g2:
            continue
        l1 = [r["ledger_total"] for r in g1 if r.get("ledger_total")]
        l2 = [r["ledger_total"] for r in g2 if r.get("ledger_total")]
        p1 = [r["det_to_proof"] for r in g1 if r.get("det_to_proof") is not None]
        p2 = [r["det_to_proof"] for r in g2 if r.get("det_to_proof") is not None]
        m1 = st.median(l1) if l1 else None
        m2 = st.median(l2) if l2 else None
        d = (100 * (m2 - m1) / m1) if (m1 and m2) else None
        q1 = st.median(p1) if p1 else None
        q2 = st.median(p2) if p2 else None
        ratio = (q2 / q1) if (q1 and q2) else None
        s1 = f"{sum(1 for r in g1 if r.get('stage1_status')=='OPTIMAL')}/{len(g1)}"
        s2 = f"{sum(1 for r in g2 if r.get('stage1_status')=='OPTIMAL')}/{len(g2)}"
        print(f"{o:>5}{g1[0]['ops_per_machine']:>7.0f}"
              f"{(m1 or 0):>14,.0f}{(m2 or 0):>14,.0f}"
              f"{('-' if d is None else f'{d:+.2f}%'):>9}"
              f"{('-' if q1 is None else f'{q1:.3f}'):>11}"
              f"{('-' if q2 is None else f'{q2:.3f}'):>11}"
              f"{('-' if ratio is None else f'{ratio:.1f}x'):>8}"
              f"{f'{s1} / {s2}':>16}")

    # ------------------------------------------------------------------ Q3
    print("\n" + "=" * 108)
    print("Q3 — DOES THE CLIFF TRACK UTILISATION OR OP COUNT?")
    print("=" * 108)
    print("  Every cell, ordered by UTILISATION, with the proof outcome beside it.")
    print("  If the boundary is consistent in the util column across BOTH alternate")
    print("  settings, utilisation is predictive and computable BEFORE solving.")
    print(f"{'util%':>8}{'ops/m':>7}{'ord':>5}{'alt':>4}{'S1':>9}{'proof':>9}")
    for r in sorted(kept, key=lambda x: (x["utilisation_pct"] or 0)):
        proof = r.get("det_to_proof")
        print(f"{(r['utilisation_pct'] or 0):>8.1f}{r['ops_per_machine']:>7.0f}"
              f"{r['orders']:>5}{r['alternates']:>4}"
              f"{str(r.get('stage1_status'))[:8]:>9}"
              f"{('-' if proof is None else f'{proof:.3f}'):>9}")

    ok = [r for r in kept if r.get("stage1_status") == "OPTIMAL"]
    bad = [r for r in kept if r.get("stage1_status") != "OPTIMAL"]
    if ok and bad:
        print(f"\n  PROVED    : util {min(r['utilisation_pct'] for r in ok):.1f}"
              f"-{max(r['utilisation_pct'] for r in ok):.1f}%   "
              f"ops/machine {min(r['ops_per_machine'] for r in ok):.0f}"
              f"-{max(r['ops_per_machine'] for r in ok):.0f}")
        print(f"  NOT PROVED: util {min(r['utilisation_pct'] for r in bad):.1f}"
              f"-{max(r['utilisation_pct'] for r in bad):.1f}%   "
              f"ops/machine {min(r['ops_per_machine'] for r in bad):.0f}"
              f"-{max(r['ops_per_machine'] for r in bad):.0f}")
        sep_u = max(r["utilisation_pct"] for r in ok) < min(r["utilisation_pct"] for r in bad)
        sep_o = max(r["ops_per_machine"] for r in ok) < min(r["ops_per_machine"] for r in bad)
        print(f"\n  UTILISATION separates the two classes cleanly : {sep_u}")
        print(f"  OPS/MACHINE separates the two classes cleanly : {sep_o}")
    elif not bad:
        print("\n  NO CELL FAILED THE COST PROOF — there is no cliff in this range.")


if __name__ == "__main__":
    main()

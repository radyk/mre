#!/usr/bin/env python3
"""Session 4B.10 — does `facility_real` reproduce the MEASURED book?

Reads a generated submission's own CSVs (no pipeline) and prints the shape
beside the measured target from docs/07 §5a.24/.25. A calibration claim that
is not checked is an assertion, not a measurement.

    python tools/spikes/density_4b10/verify_facility_real.py <submission_dir>
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from datetime import date
from pathlib import Path

SHIFT = 720.0

# The measured targets (docs/07 §5a.24 / §5a.25).
TARGET = {
    "ops_per_order_mean": (4.00, "F004/F006: exactly 4 on 100% of orders"),
    "pct_due_le_7": (50.06, "book: 50.06%"),
    "pct_due_le_14": (89.98, "book: 89.98%"),
    "median_lead": (7, "book median 7 d"),
    "p25_lead": (2, "book p25 2 d"),
    "pct_past_due": (7.83, "book 7.83%"),
    "op_min_mean": (13.8, "F004 13.2 / F006 14.4 min"),
    "setup_med": (5.0, "F006 median 5"),
}


def rows(p: Path, name):
    with (p / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def pct(vals, q):
    s = sorted(vals)
    if not s:
        return 0
    i = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return s[i]


def main():
    sub = Path(sys.argv[1])
    orders = rows(sub, "orders.csv")
    rlines = rows(sub, "routing_lines.csv")
    res = rows(sub, "resources.csv")

    ref = date.fromisoformat(sorted(o["created_date"] for o in orders)[0])

    # ops per route (DISTINCT sequences — alternates share a sequence)
    seqs_by_route: dict[str, set] = {}
    for r in rlines:
        seqs_by_route.setdefault(r["route_id"], set()).add(r["sequence"])
    ops_by_route = {k: len(v) for k, v in seqs_by_route.items()}

    # per-sequence time model (read once, as the adapter does)
    time_by_seq: dict[tuple[str, str], tuple[float, float]] = {}
    elig_by_seq: dict[tuple[str, str], int] = {}
    for r in rlines:
        k = (r["route_id"], r["sequence"])
        elig_by_seq[k] = elig_by_seq.get(k, 0) + 1
        if k not in time_by_seq:
            time_by_seq[k] = (float(r["setup_minutes"] or 0),
                              float(r["run_minutes_per_unit"] or 0))

    n_mach = len(res)
    leads, ops_per_order, op_mins, setups, runs = [], [], [], [], []
    order_min = []
    for o in orders:
        rid = o["route_id"]
        n = ops_by_route.get(rid, 0)
        ops_per_order.append(n)
        leads.append((date.fromisoformat(o["due_date"]) - ref).days)
        qty = float(o["quantity"])
        tot = 0.0
        for s in seqs_by_route.get(rid, ()):
            setup, run = time_by_seq[(rid, s)]
            m = setup + run * qty
            op_mins.append(m)
            setups.append(setup)
            runs.append(run * qty)
            tot += m
        order_min.append(tot)

    n = len(orders)
    got = {
        "ops_per_order_mean": sum(ops_per_order) / n,
        "pct_due_le_7": 100 * sum(1 for l in leads if l <= 7) / n,
        "pct_due_le_14": 100 * sum(1 for l in leads if l <= 14) / n,
        "median_lead": pct(leads, 0.5),
        "p25_lead": pct(leads, 0.25),
        "pct_past_due": 100 * sum(1 for l in leads if l < 0) / n,
        "op_min_mean": sum(op_mins) / len(op_mins),
        "setup_med": pct(setups, 0.5),
    }

    print(f"submission : {sub}")
    print(f"orders={n}  machines={n_mach}  "
          f"eligible/op: {sorted(Counter(elig_by_seq.values()).items())}")
    print(f"{'metric':<22}{'GOT':>12}{'TARGET':>12}   note")
    print("-" * 78)
    for k, (tgt, note) in TARGET.items():
        print(f"{k:<22}{got[k]:>12,.2f}{tgt:>12,.2f}   {note}")

    print("\nDUE-DATE HISTOGRAM (target from docs/07 §5a.24)")
    buckets = [("PAST DUE", lambda l: l < 0, 7.83),
               ("0-7 d", lambda l: 0 <= l <= 7, 42.22),
               ("8-14 d", lambda l: 8 <= l <= 14, 39.92),
               ("15-30 d", lambda l: 15 <= l <= 30, 8.61),
               ("31-60 d", lambda l: 31 <= l <= 60, 1.41)]
    for name, f, tgt in buckets:
        c = sum(1 for l in leads if f(l))
        print(f"  {name:<10}{c:>6}{100*c/n:>9.2f}%   target {tgt:>6.2f}%")
    print(f"  lead: min={min(leads)} p25={pct(leads,.25)} med={pct(leads,.5)} "
          f"p75={pct(leads,.75)} p90={pct(leads,.90)} max={max(leads)}")

    print("\nOPERATION DURATIONS")
    print(f"  setup: med={pct(setups,.5):.0f} p75={pct(setups,.75):.0f} "
          f"p90={pct(setups,.90):.0f} mean={sum(setups)/len(setups):.1f}"
          f"   (F006: med 5, p75 20, p90 30, mean 12.4)")
    print(f"  run  : med={pct(runs,.5):.1f} p90={pct(runs,.90):.1f} "
          f"mean={sum(runs)/len(runs):.1f}   (F006: med 0.5, p90 4.7, mean 2.0)")
    print(f"  op   : med={pct(op_mins,.5):.1f} p90={pct(op_mins,.90):.1f} "
          f"mean={sum(op_mins)/len(op_mins):.1f}   (F004 13.2 / F006 14.4)")

    print("\nDENSITY AND LOAD (7-day working week denominator, as item 1 used)")
    for w in (7, 14):
        sel = [(l, om, opo) for l, om, opo in zip(leads, order_min, ops_per_order)
               if l <= w]
        ops = sum(o for _l, _m, o in sel)
        mins = sum(m for _l, m, _o in sel)
        avail = n_mach * w * SHIFT
        print(f"  w={w:>2}d  orders={len(sel):>4}  ops={ops:>5}  "
              f"ops/machine={ops/n_mach:>6.0f}  req={mins:>9,.0f}min  "
              f"util={100*mins/avail:>6.1f}%")
    print("  NB the generated calendar is Mon-Fri, so the SOLVER sees 5/7 of this")
    print("     capacity; utilisation against the real calendar is ~1.4x these.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Session 4B.8 CU6 — account a moved schedule BY OPERATION IDENTITY.

A schedule.csv diff is a TEXT diff: it reports the lines that changed, which on
a re-sequenced machine lane is nearly every line, and it cannot tell "this op
moved" from "a different op now occupies this row". That difference is the whole
point of the accounting rule — an unexplained movement HALTS the session, so the
movement has to be attributable to a NAMED OPERATION, not to a row number.

This joins golden and current on (work_order, step, chunk_seq) and reports, per
operation: resource before/after, start before/after, duration and cost
before/after. It then states the aggregate the tiebreak is actually optimizing
(Σ start-minutes) and the ledger totals, which must NOT move.

Usage:
    python tools/spikes/alloc_4b8/account_goldens.py GOLDEN.csv CURRENT.csv
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path


def load(path):
    with Path(path).open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    for r in rows:
        key = (r.get("work_orders"), r.get("op_seq"), r.get("chunk_seq") or "")
        out[key] = r
    return out, rows


def _dt(s):
    return datetime.fromisoformat(s) if s else None


def main():
    gpath, cpath = sys.argv[1], sys.argv[2]
    g, grows = load(gpath)
    c, crows = load(cpath)

    print(f"golden rows : {len(grows)}   current rows: {len(crows)}")
    only_g = sorted(set(g) - set(c))
    only_c = sorted(set(c) - set(g))
    if only_g:
        print(f"\n!! OPERATIONS PRESENT IN GOLDEN ONLY ({len(only_g)}) — this is NOT a "
              f"re-sequencing, it is a scheduling-set change:")
        for k in only_g:
            print(f"   {k}")
    if only_c:
        print(f"\n!! OPERATIONS PRESENT IN CURRENT ONLY ({len(only_c)}):")
        for k in only_c:
            print(f"   {k}")

    shared = sorted(set(g) & set(c))
    moved = []
    for k in shared:
        a, b = g[k], c[k]
        if (a.get("machine") != b.get("machine")
                or a.get("start") != b.get("start")
                or a.get("end") != b.get("end")):
            moved.append((k, a, b))

    print(f"\nshared operations: {len(shared)}   MOVED: {len(moved)}   "
          f"identical: {len(shared) - len(moved)}")
    if moved:
        print(f"\n{'operation':>28} {'resource':>26} {'start':>42} {'minutes':>16}")
        print("-" * 118)
        for k, a, b in moved:
            op = f"{k[0]}/{k[1]}" + (f"/{k[2]}" if k[2] else "")
            res = (a["machine"] if a["machine"] == b["machine"]
                   else f"{a['machine']} -> {b['machine']}")
            sa, sb = _dt(a["start"]), _dt(b["start"])
            delta = int((sb - sa).total_seconds() / 60) if (sa and sb) else None
            st = (a["start"][:16] if a["start"] == b["start"]
                  else f"{a['start'][:16]} -> {b['start'][:16]}")
            dm = (f"{delta:+,} min" if delta else "same start")
            print(f"{op:>28} {res:>26} {st:>42} {dm:>16}")

    # The quantity stage 2 minimizes. A tiebreak given MORE budget must not make
    # this worse; if it does, the cap or the warm start is broken.
    def start_sum(d):
        base = min(_dt(r["start"]) for r in d.values() if r.get("start"))
        return sum(int((_dt(r["start"]) - base).total_seconds() / 60)
                   for r in d.values() if r.get("start"))

    gs, cs = start_sum(g), start_sum(c)
    print(f"\nΣ start-minutes (the stage-2 objective)  golden {gs:,}  current {cs:,}  "
          f"delta {cs - gs:+,} ({100 * (cs - gs) / gs:+.2f}%)")
    print("  -> stage 2 improved its own objective" if cs < gs else
          "  -> stage 2 did NOT improve; investigate before accepting"
          if cs > gs else "  -> unchanged")

    def cost(d):
        return sum(float(r["production_cost"]) for r in d.values() if r.get("production_cost"))

    gc, cc = cost(g), cost(c)
    print(f"row-cost total  golden {gc:,.2f}  current {cc:,.2f}  delta {cc - gc:+,.2f}")
    print("  -> LEDGER UNCHANGED (equal-cost re-placement)" if abs(cc - gc) < 0.005
          else "  -> !! LEDGER MOVED — the stage-1 cap did not hold. HALT.")


if __name__ == "__main__":
    main()

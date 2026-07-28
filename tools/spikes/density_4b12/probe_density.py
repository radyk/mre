#!/usr/bin/env python3
"""Session 4B.12 CU2 — find the ORDER COUNT that lands on a target ops/machine.

The sweep's axis is ops/machine, but the generator's dial is ORDERS, and the map
between them is not a constant: it is `4 ops/order x the fraction of the book
admitted to a 14-day window`, and R-PD1 moved that fraction (past-due demands are
now schedulable and admitted, so the same order count yields MORE free ops than
it did in 4B.10). Guessing the multiplier would put the session's two headline
cells at the wrong densities, so it is measured — build the plant and the window,
count, and report. No solve.

    python tools/spikes/density_4b12/probe_density.py 265 300 860 900
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cliff_sweep as cs        # noqa: E402


def probe(orders: int, alternates: int = 1) -> dict:
    plant = cs.build_plant(orders, alternates)
    win = cs.window_inputs(plant)
    n_free = len(win["free_ops"])
    n_mach = len(plant.resources)
    req = sum(cs.ds._iso_minutes(op.get("setup_duration"))
              + cs.ds._iso_minutes(op.get("run_duration"))
              for op in win["free_ops"])
    avail = cs.ds.calendar_minutes(plant, win["ref"], win["window_end"])
    pd = cs.past_due_counts(plant, win["admitted"])
    return dict(orders=orders, alternates=alternates, n_free_ops=n_free,
                n_machines=n_mach, ops_per_machine=round(n_free / n_mach, 1),
                utilisation_pct=round(100.0 * req / avail, 2) if avail else None,
                n_admitted=win["n_demands_admitted"],
                n_schedulable=win["n_schedulable"], **pd)


if __name__ == "__main__":
    alts = 1
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--alternates" in sys.argv:
        alts = int(sys.argv[sys.argv.index("--alternates") + 1])
        args = [a for a in args if a != str(alts)]
    for o in (int(a) for a in args):
        r = probe(o, alts)
        print(f"orders={r['orders']:>5} a={r['alternates']} "
              f"free_ops={r['n_free_ops']:>5} ops/machine={r['ops_per_machine']:>7} "
              f"util={r['utilisation_pct']}% "
              f"admitted={r['n_admitted']}/{r['n_schedulable']} "
              f"past_due={r['n_past_due_admitted']}/{r['n_past_due_all']} "
              f"({r['past_due_pct_of_book']}% of book)", flush=True)

#!/usr/bin/env python3
"""Session 4B.8 CU5(d) — WHAT THE COARSE ZONE SAYS AT EACH WINDOW DEPTH.

DIAGNOSIS ONLY.

Narrowing the window does not DISCARD the work it stops admitting — it moves it
from the fine model to the coarse zone (R-SC2 amendment, 4B.6). So "narrow the
window" is only a graceful degradation if the displaced demand still gets
coarsely PLACED and the coarse zone still says something load-bearing about it.
If narrowing instead pushes work into a zone that models it as nothing, the
window is not degrading gracefully — it is losing the work quietly.

Per depth: how many demands fall beyond the horizon, how many coarse buckets and
how many of them BIND, and the coarse run's own status.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "spikes" / "tiebreak_4b6c"))

import arm_harness as AH   # noqa: E402

OUT = Path(__file__).resolve().parent


def _run_facts(run):
    """One coarse run's load facts. `density` and `binding` live on CoarseRun
    (per (resource, bucket)), NOT on the zone — read from the dataclass rather
    than guessed, so a zero here means 'nothing bound', never 'the attribute
    moved'."""
    return {
        "status": run.status, "rho": run.rho,
        "cells": len(run.density or {}),
        "binding_cells": len(run.binding or []),
        "placements": len(run.placements or []),
        "unmodelable": len(run.unmodelable or []),
        "n_ops_modeled": run.n_ops_modeled,
        "tardiness_buckets": sum((run.demand_tardiness_buckets or {}).values()),
        "wall_truncated": run.wall_truncated,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, default=200)
    ap.add_argument("--windows", type=int, nargs="+",
                    default=[7, 8, 9, 10, 11, 12, 14])
    ap.add_argument("--frozen", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(OUT / "coarse_depths.jsonl"))
    args = ap.parse_args()

    from mre.modules.coarse_horizon import build_coarse_zone
    from mre.modules.rolling_horizon import build_rolling_view

    plant = AH.build_plant(args.orders)
    for w in args.windows:
        row = {"orders": args.orders, "window_days": w, "seed": args.seed}
        try:
            view = build_rolling_view(plant, window_days=w,
                                      frozen_days=min(args.frozen, w),
                                      seed=args.seed, deterministic=True,
                                      persist=False)
            row.update(window_status=view.status,
                       tiebreak_status=view.tiebreak_status,
                       committed=len(view.committed), active=len(view.active),
                       beyond_horizon=len(view.beyond_demand_ids),
                       total_cost=(view.cost_ledger or {}).get("total_cost"))
            zone = build_coarse_zone(plant, view)
            row.update(buckets=len(zone.buckets),
                       proof=_run_facts(zone.proof),
                       planning=_run_facts(zone.planning),
                       coarse_beyond=len(zone.beyond_demand_ids),
                       rho=zone.coefficients.capacity_derate,
                       bucket_days=zone.coefficients.bucket_days)
        except Exception as exc:   # noqa: BLE001 — diagnostic, never fatal
            row["error"] = f"{type(exc).__name__}: {exc}"
        Path(args.out).open("a", encoding="utf-8").write(
            json.dumps(row, default=str) + "\n")
        print("[coarse] " + json.dumps(row, default=str), flush=True)


if __name__ == "__main__":
    main()

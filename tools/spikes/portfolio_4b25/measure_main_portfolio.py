"""Session 4B.25 Item 3 -- MEASURE THE MAIN-SOLVE PORTFOLIO on the dense board.

Five seeded deterministic searches at a declared per-member budget, over the
demo board's own submission (`demo_board`, 280 orders, seed 1, ref 2026-01-05,
window 10 / frozen 1 -- the board `rolling-c9973708-865` was minted from).

Reports, per member: the LEDGER total (the selection key), the solver status,
the objective and gap, and the wall it cost. Then the winner, the spread, and
both wall totals -- sequential and process-parallel. That table is the purchase
decision for the cloud box, stated in dollars against minutes.

NOTHING IS PERSISTED. Every member runs with `persist=False` into a scratch
directory; the registered board and the working data root are untouched.

    python tools/spikes/portfolio_4b25/measure_main_portfolio.py --mode both

Rows land in `measurements.jsonl` beside this file (append-only).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "src"))

REF = datetime(2026, 1, 5, tzinfo=timezone.utc)
SUBMISSION = REPO / "_4b22a_scratch" / "demo_board" / "submission"
WINDOW_DAYS, FROZEN_DAYS = 10, 1
WALL_CEILING_S = 1800.0          # a CEILING, never the budget


def _emit(row: dict) -> None:
    row["t"] = time.time()
    with (HERE / "measurements.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
    print(json.dumps(row, default=str), flush=True)


def _incumbent(run_dir: Path) -> dict:
    """The registered board's own ledger + solver block, for the comparison."""
    doc = json.loads((run_dir / "schedule_document.json").read_text("utf-8"))
    return {"total": doc["cost_summary"]["total"],
            "status": doc["solver"]["status"],
            "objective": doc["solver"].get("objective"),
            "gap": doc["solver"].get("gap")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--submission", default=str(SUBMISSION))
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--det-total", type=float, default=3.0)
    ap.add_argument("--seed0", type=int, default=42)
    ap.add_argument("--scratch", default="_4b25_scratch/main")
    ap.add_argument("--mode", choices=("sequential", "parallel", "both"),
                    default="both")
    ap.add_argument("--incumbent-run", default=None,
                    help="run dir of the registered board, for the comparison")
    a = ap.parse_args(argv)

    from mre.modules.rolling_horizon import prepare_plant, solve_rolling_portfolio

    os.environ.setdefault("PYTHONHASHSEED", "0")
    scratch = Path(a.scratch)
    scratch.mkdir(parents=True, exist_ok=True)

    if a.incumbent_run:
        _emit({"kind": "incumbent", **_incumbent(Path(a.incumbent_run))})

    t0 = time.monotonic()
    plant = prepare_plant(a.submission, scratch / "prep", reference_date=REF)
    _emit({"kind": "plant", "prepare_s": round(time.monotonic() - t0, 3),
           "demands": len(plant.demands), "operations": len(plant.operations),
           "resources": len(plant.resources)})

    common = dict(window_days=WINDOW_DAYS, frozen_days=FROZEN_DAYS,
                  deterministic=True, seed=a.seed0,
                  member_time_limit_s=WALL_CEILING_S, det_total=a.det_total,
                  persist=False, k=a.k, k_declared=True,
                  det_time_declared=True)

    if a.mode in ("sequential", "both"):
        t = time.monotonic()
        view, book = solve_rolling_portfolio(plant, **common,
                                             portfolio_workers=1)
        wall = time.monotonic() - t
        _emit({"kind": "portfolio", "execution": "sequential",
               "wall_total_s": round(wall, 3),
               "placed": len(view.placed), "committed": len(view.committed),
               "block": book.block()})

    if a.mode in ("parallel", "both"):
        t = time.monotonic()
        view, book = solve_rolling_portfolio(plant, **common,
                                             portfolio_workers=a.k)
        wall = time.monotonic() - t
        _emit({"kind": "portfolio", "execution": "processes",
               "wall_total_s": round(wall, 3),
               "placed": len(view.placed), "committed": len(view.committed),
               "block": book.block()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

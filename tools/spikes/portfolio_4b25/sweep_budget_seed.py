"""Errand 4B.26 Item 1 -- THE (BUDGET x SEED) SWEEP.

4B.25 measured the COLD main-solve portfolio at ONE per-member budget (3.0
deterministic units) and found $578.16 of value against the warm audit's
$545,549.60 -- and could not say whether the cause is BUDGET STARVATION (two of
five seeds placed nothing at all) or COLD-START GEOMETRY (cold members converge
on the same poor region however long they run). This sweep answers that by
running the same five seeds at four budgets.

It EXTENDS `measure_main_portfolio.py` rather than replacing it: the instrument
is the same `solve_rolling_portfolio` call with the same coefficients, and the
3.0-unit row is RE-USED from `measurements.jsonl`, not re-run. What is new is
the budget axis and the second density.

NOTHING IS PERSISTED and nothing is registered. Every member runs with
`persist=False` into a scratch data root; the working root and the registered
demo board are untouched. At `persist=False` with a cached winner view
`solve_rolling_portfolio` performs exactly K solves -- the K+1 re-solve fires
only when the winner must be written to disk -- so every wall below is five
members and nothing else.

EXECUTION IS STRICTLY SEQUENTIAL, ONE ARM AT A TIME. 4B.25 measured a member
running ~1.8x slower with four siblings on this laptop, so a wall taken beside
a competing process is not a wall. `portfolio_workers=1` and one process at a
time is what makes the wall column mean anything.

    python tools/spikes/portfolio_4b25/sweep_budget_seed.py --arm all

Rows land in `sweep.jsonl` beside this file (append-only).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "src"))

REF = datetime(2026, 1, 5, tzinfo=timezone.utc)

#: The demo board's own submission -- the one `rolling-c9973708-865` was minted
#: from (4B.22a). Re-used, never regenerated: regenerating it would measure a
#: different world wearing the same name.
DEMO_SUBMISSION = REPO / "_4b22a_scratch" / "demo_board" / "submission"
DEMO_WINDOW, DEMO_FROZEN = 10, 1

#: The generator settings of 4B.22a's `c3-w14-170` / `c2-mid`, verbatim from
#: `measure_candidates.py`. GEN_SEED 1 is the pilot family's standing seed.
GEN_SEED = 1
MID_ORDERS, MID_PD, MID_LEAD, MID_SPLIT_W = 170, 0.12, 10, 1

K = 5
SEED0 = 42
WALL_CEILING_S = 1800.0          # a CEILING, never the budget
SCRATCH = REPO / "_4b26_scratch"


def _emit(row: dict) -> None:
    row["t"] = time.time()
    with (HERE / "sweep.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
    print(json.dumps(row, default=str), flush=True)


def _mid_submission() -> Path:
    """Generate the 170-order world ONCE and re-use it across its arms.

    Both 170-order arms must run against the SAME world or the window
    comparison is confounded by the generator.
    """
    from generate_erp_dataset import generate

    sub = SCRATCH / "mid170" / "submission"
    if (sub / "manifest.json").exists():
        return sub
    if sub.exists():
        shutil.rmtree(sub)
    t0 = time.monotonic()
    generate(sub, scenario="demo_board", orders=MID_ORDERS, seed=GEN_SEED,
             pd_share=MID_PD, lead_p50=MID_LEAD,
             splittable_weight=MID_SPLIT_W)
    _emit({"kind": "generate", "world": "mid170", "orders": MID_ORDERS,
           "seed": GEN_SEED, "pd_share": MID_PD, "lead_p50": MID_LEAD,
           "wall_s": round(time.monotonic() - t0, 3)})
    return sub


def run_arm(label: str, submission: Path, window_days: int, frozen_days: int,
            det_total: float) -> None:
    from mre.modules.rolling_horizon import prepare_plant, solve_rolling_portfolio

    scratch = SCRATCH / label
    scratch.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    plant = prepare_plant(submission, scratch / "prep", reference_date=REF)
    _emit({"kind": "plant", "arm": label,
           "prepare_s": round(time.monotonic() - t0, 3),
           "demands": len(plant.demands), "operations": len(plant.operations),
           "resources": len(plant.resources)})

    t = time.monotonic()
    view, book = solve_rolling_portfolio(
        plant, window_days=window_days, frozen_days=frozen_days,
        deterministic=True, seed=SEED0, member_time_limit_s=WALL_CEILING_S,
        det_total=det_total, persist=False, k=K, k_declared=True,
        det_time_declared=True, portfolio_workers=1)
    wall = time.monotonic() - t

    _emit({"kind": "arm", "arm": label, "submission": str(submission),
           "window_days": window_days, "frozen_days": frozen_days,
           "det_total": det_total, "execution": "sequential",
           "wall_total_s": round(wall, 3),
           "placed": len(view.placed), "committed": len(view.committed),
           "block": book.block()})


ARMS = {
    # THE DEMO BOARD, COLD, ACROSS THE BUDGET AXIS. 3.0 is 4B.25's row and is
    # deliberately absent: it is re-used from measurements.jsonl.
    "demo-6.0":  dict(submission=None, window_days=DEMO_WINDOW,
                      frozen_days=DEMO_FROZEN, det_total=6.0),
    "demo-10.0": dict(submission=None, window_days=DEMO_WINDOW,
                      frozen_days=DEMO_FROZEN, det_total=10.0),
    "demo-15.0": dict(submission=None, window_days=DEMO_WINDOW,
                      frozen_days=DEMO_FROZEN, det_total=15.0),
    # ONE DENSITY DOWN. The candidate is named by its w14 result, so w14 is run
    # verbatim; w10 is run beside it because the demo board's window is 10 and a
    # w14-only comparison would confound density with window.
    "mid170-w14-6.0": dict(submission="mid170", window_days=14,
                           frozen_days=1, det_total=6.0),
    "mid170-w10-6.0": dict(submission="mid170", window_days=DEMO_WINDOW,
                           frozen_days=1, det_total=6.0),
}

# Cheapest decision-relevant arm first: if the machine dies at hour two, the
# shipped-default row is already on disk.
ORDER = ["demo-6.0", "mid170-w14-6.0", "mid170-w10-6.0",
         "demo-10.0", "demo-15.0"]


def _completed() -> set:
    """Arms already on disk. An arm row is written only after all K members
    finished, so a half-run arm is correctly absent and will be re-run whole."""
    p = HERE / "sweep.jsonl"
    if not p.exists():
        return set()
    done = set()
    for ln in p.read_text("utf-8").splitlines():
        if not ln.strip():
            continue
        r = json.loads(ln)
        if r.get("kind") == "arm":
            done.add(r["arm"])
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arm", default="all", help="an arm name, or 'all'")
    ap.add_argument("--resume", action="store_true",
                    help="skip arms whose row is already in sweep.jsonl")
    a = ap.parse_args(argv)

    os.environ.setdefault("PYTHONHASHSEED", "0")
    SCRATCH.mkdir(parents=True, exist_ok=True)

    names = ORDER if a.arm == "all" else [a.arm]
    if a.resume:
        done = _completed()
        skipped = [n for n in names if n in done]
        if skipped:
            print(f"resume: skipping {', '.join(skipped)}", flush=True)
        names = [n for n in names if n not in done]
    for name in names:
        spec = dict(ARMS[name])
        sub = spec.pop("submission")
        submission = DEMO_SUBMISSION if sub is None else _mid_submission()
        print(f"\n=== ARM {name} ===", flush=True)
        t0 = time.monotonic()
        try:
            run_arm(name, submission, **spec)
        except Exception as exc:  # noqa: BLE001 -- an arm that dies is a row
            _emit({"kind": "arm_failed", "arm": name,
                   "error": f"{type(exc).__name__}: {exc}",
                   "wall_s": round(time.monotonic() - t0, 3)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

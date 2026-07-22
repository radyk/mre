#!/usr/bin/env python3
"""Session 4B.2c CU3 — the rolling-horizon DETERMINISM golden driver.

The 4B.2 "bit-identical across two trials" claim had no committed regression.
This driver produces the canonical, hashable committed-schedule + cost-ledger of
one deterministic rolling-horizon run, so a subprocess test can assert (a) two
runs agree byte-for-byte AND (b) the run matches a committed golden — detecting
DRIFT across sessions, not just intra-run nondeterminism.

Determinism (mirrors test_defaults_reproduce_baseline): PYTHONHASHSEED=0 (set by
the caller's env) + --solver-workers 1 (num_search_workers=1) + a fixed seed +
a CP-SAT max_deterministic_time budget (reproducible run-to-run, unlike a wall
clock). Prints ONLY the canonical JSON to stdout; incidental output goes to
stderr so the subprocess stdout is clean.

Usage:
    PYTHONHASHSEED=0 python tools/rolling_golden.py \
        --orders 24 --window 7 --frozen 3 --det-time 0.5 --seed 42
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
REF = datetime(2026, 1, 5, tzinfo=timezone.utc)


def _canonical(result) -> dict:
    """Deterministic, hashable summary of a rolling run's committed schedule."""
    rows = sorted([oid, c["resource"], c["start"], c["end"]]
                  for oid, c in result.committed_ops.items())
    digest = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    led = result.cost_ledger
    return {
        "n_committed": len(rows),
        "on_time": result.on_time,
        "late": result.late,
        "total_cost": round(led.get("total_cost", 0.0), 2),
        "production_cost": round(led.get("production_cost", 0.0), 2),
        "setup_cost": round(led.get("setup_cost", 0.0), 2),
        "tardiness_cost": round(led.get("tardiness_cost", 0.0), 2),
        "schedule_digest": digest,
    }


def run(orders: int, window: int, frozen: int, det_time: float, seed: int,
        max_windows=None) -> dict:
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import prepare_plant, run_rolling_horizon

    tmp = Path(tempfile.mkdtemp(prefix="rolling_golden_"))
    # generation + spine chatter -> stderr, so stdout carries only the JSON.
    with contextlib.redirect_stdout(sys.stderr):
        generate(tmp / "sub", scenario="pilot_scale", orders=orders, seed=1)
        plant = prepare_plant(tmp / "sub", tmp / "prep", reference_date=REF)
        result = run_rolling_horizon(
            plant, window_days=window, frozen_days=frozen, gravity=True,
            deterministic=True, seed=seed, det_time=det_time,
            member_time_limit_s=30.0, max_windows=max_windows)
    out = {"orders": orders, "window": window, "frozen": frozen,
           "det_time": det_time, "seed": seed}
    out.update(_canonical(result))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, default=24)
    ap.add_argument("--window", type=int, default=7)
    ap.add_argument("--frozen", type=int, default=3)
    ap.add_argument("--det-time", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-windows", type=int, default=None)
    args = ap.parse_args(argv)
    out = run(args.orders, args.window, args.frozen, args.det_time, args.seed,
              max_windows=args.max_windows)
    sys.stdout.write(json.dumps(out, sort_keys=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Session 4B.24 — drive the local pricer over the founder's gesture. SCRATCH."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ctx import Board, DEMO, PINNED  # noqa: E402

from mre.modules.local_price import price_local_move  # noqa: E402


def op_of(board, work_order, op_seq):
    for a in board.assignments():
        if work_order in (a.get("work_orders") or []) and a.get("op_seq") == op_seq:
            return a
    raise SystemExit(f"no {work_order} op{op_seq}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=DEMO)
    ap.add_argument("--order", default="ORD-000057")
    ap.add_argument("--op", type=int, default=30)
    ap.add_argument("--shift-min", type=int, default=240)
    ap.add_argument("--target", default=None, help="absolute ISO target start")
    ap.add_argument("--no-validate", action="store_true")
    a = ap.parse_args()

    board = Board(a.board)
    bar = op_of(board, a.order, a.op)
    from datetime import datetime, timedelta, timezone
    s = datetime.fromisoformat(bar["chunks"][0]["start"].replace("Z", "+00:00"))
    target = (a.target or (s + timedelta(minutes=a.shift_min)).isoformat())
    print(f"{a.order} op{a.op} on {bar['external_name']}: "
          f"{bar['chunks'][0]['start']} -> {target}")

    t0 = time.monotonic()
    res = price_local_move(
        board.out_dir, board.snapshot_id,
        pin_op_id=bar["operation_ref"], pin_resource_id=bar["resource_id"],
        pin_start_iso=target,
        restrict_op_ids=board.window_op_ids,
        standing_pins=board.standing_pins,
        validate=not a.no_validate)
    print(f"TOTAL WALL {time.monotonic() - t0:.3f}s")
    print(json.dumps(res.summary(), indent=2, default=str))


if __name__ == "__main__":
    main()

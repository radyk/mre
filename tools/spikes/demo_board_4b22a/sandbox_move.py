"""Errand 4B.22a -- ONE sandbox move against a registered board, printed in full.

Split out of `verify_demo_surfaces.py` so the SAME gesture can be run against the
old board and the new one and the two cards compared. The errand's claim is that
the current demo board prices every move at $0 with an empty affected-orders
list because there is nothing to disturb; that claim is only worth anything if
the identical gesture is measured on both.

THE GESTURE IS A COLLISION, chosen by the board rather than authored: take the
machine carrying the most MOVABLE bars (`commitment_state == "active_window"`,
not chunked -- dragging a chunked operation is broken and out of scope here),
and pin its LAST movable bar onto the START of its FIRST. Two operations cannot
share a machine-minute, so the re-solve must displace something or refuse.
Neither outcome is a failure of the script; $0 with nothing affected is a
statement about the board.

    python tools/spikes/demo_board_4b22a/sandbox_move.py --schedule <id>
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _api(base: str, path: str, body=None, timeout: float = 600.0):
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json"} if data is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{path} -> HTTP {e.code}: "
                           f"{e.read().decode('utf-8', 'replace')[:600]}") from e


def _start_of(a: dict) -> str:
    return (a["chunks"][0]["start"] if a.get("chunks")
            else a["phases"]["setup"]["start"])


def candidate_moves(doc: dict, limit: int = 8) -> tuple[str, list[tuple]]:
    """Gestures to try, in order, on the machine carrying the most movable bars.

    THE FIRST VERSION OF THIS FUNCTION PICKED THE WRONG GESTURE AND THE BOARD
    SAID SO. It moved the machine's LAST bar onto its FIRST bar's start -- a
    six-week backward jump -- and the sandbox returned INFEASIBLE, "pin
    infeasible this horizon". That is a correct answer to a question about a
    placement no planner would attempt: the operation's own predecessor had not
    finished. It tests the refusal path, not the contention path.

    So the gestures below are SHORT FORWARD SHIFTS onto an occupied neighbour:
    take bar i and pin it at bar i+1's start. Forward is the safe direction for
    precedence (a successor that no longer fits can itself be re-placed by the
    re-solve, and that displacement is exactly what the card is meant to price),
    and landing on an occupied minute is what forces the displacement.

    Every attempt is reported by the caller, including the refused ones -- an
    errand that showed only the gesture that worked would be reporting its own
    search, not the board.
    """
    assigns = doc.get("assignments") or []
    movable = [a for a in assigns
               if a.get("commitment_state") == "active_window"
               and len(a.get("chunks") or []) <= 1]
    by_machine: dict[str, list] = {}
    for a in movable:
        by_machine.setdefault(a.get("external_name") or a["resource_id"],
                              []).append(a)
    if not by_machine:
        raise SystemExit("no movable bar on this board: every placement is "
                         "committed or chunked")
    busiest = max(by_machine, key=lambda m: len(by_machine[m]))
    bars = sorted(by_machine[busiest], key=_start_of)
    # Start from the middle of the machine's day-book: the very first bars abut
    # the frozen front and the very last have nothing after them to disturb.
    out = []
    mid = len(bars) // 2
    for i in range(mid, min(len(bars) - 1, mid + limit)):
        out.append((bars[i], bars[i + 1], _start_of(bars[i + 1])))
    return busiest, out


def run(base: str, sched: str, max_attempts: int = 8) -> dict:
    doc = _api(base, f"/schedules/{sched}")["data"]
    busiest, moves = candidate_moves(doc, limit=max_attempts)
    print(f"board {sched}: {len(doc.get('assignments') or [])} bars")
    print(f"  busiest movable machine : {busiest}")
    print(f"  gestures to try         : {len(moves)}")

    attempts = []
    for n, (mover, target, pin_start) in enumerate(moves, 1):
        pin = {"pin_op_id": mover["operation_ref"],
               "pin_resource_id": mover["resource_id"],
               "pin_start_iso": pin_start}
        print(f"\n{'='*68}\nATTEMPT {n}: move {mover.get('work_orders')} "
              f"op{mover.get('op_seq')}")
        print(f"  from {_start_of(mover)}")
        print(f"  onto {busiest} at {pin_start} "
              f"(occupied by {target.get('work_orders')} "
              f"op{target.get('op_seq')})")

        t0 = time.perf_counter()
        ghost = _api(base, f"/schedules/{sched}/sandbox/feasibility",
                     pin)["data"]
        print(f"\n--- BEAT ONE: feasibility ghost "
              f"({time.perf_counter()-t0:.1f}s) ---")
        print(json.dumps(ghost, indent=2))

        t0 = time.perf_counter()
        card = _api(base, f"/schedules/{sched}/sandbox",
                    {**pin, "correlation_id": ghost.get("correlation_id")})["data"]
        print(f"\n--- BEAT TWO: the priced delta card "
              f"({time.perf_counter()-t0:.1f}s) ---")
        print(json.dumps(card, indent=2))
        attempts.append({"attempt": n, "pin": pin, "ghost": ghost, "card": card,
                         "mover": mover.get("work_orders"),
                         "op_seq": mover.get("op_seq"),
                         "from": _start_of(mover),
                         "displaced": target.get("work_orders")})
        if card.get("feasible"):
            print(f"\n>>> ATTEMPT {n} IS THE PRICED ONE. "
                  f"{n - 1} earlier gesture(s) were refused and are above.")
            break

    last = attempts[-1] if attempts else {}
    return {"schedule_id": sched, "machine": busiest,
            "attempts": attempts, "chosen": last}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--api-base", default="http://localhost:8000")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    out = run(args.api_base, args.schedule)
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

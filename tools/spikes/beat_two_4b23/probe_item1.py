"""Session 4B.23 Item 1 -- WHERE DOES THE CHAIN END, and does the 56-bar board
behave differently?

The cockpit's drag handler fires beat one, then (controller.js:465) fires beat
two ONLY when ``ghost.feasible`` is true. This probe measures what beat one
actually returns for the SAME class of gesture on both boards, and then calls
beat two anyway -- proving whether the beat the cockpit skipped would have
succeeded.

It calls the API exactly as the cockpit does (same endpoints, same body, same
default budgets), so a difference here is a difference the cockpit would see.

    python tools/spikes/beat_two_4b23/probe_item1.py
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request

DENSE = "rolling-c9973708-865"
PINNED = "rolling-c362baa4-1b0"


def _api(base, path, body=None, timeout=600.0):
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


def _start_of(a):
    return (a["chunks"][0]["start"] if a.get("chunks")
            else a["phases"]["setup"]["start"])


def gesture(doc, order=None):
    """The 4B.22a gesture: on the machine with the most movable bars, pin bar i
    onto bar i+1's occupied start. With ``order`` given, pick the pair whose
    mover is that order."""
    movable = [a for a in (doc.get("assignments") or [])
               if a.get("commitment_state") == "active_window"
               and len(a.get("chunks") or []) <= 1]
    by_machine = {}
    for a in movable:
        by_machine.setdefault(a.get("external_name") or a["resource_id"], []).append(a)
    busiest = max(by_machine, key=lambda m: len(by_machine[m]))
    bars = sorted(by_machine[busiest], key=_start_of)
    pairs = [(bars[i], bars[i + 1]) for i in range(len(bars) - 1)]
    if order:
        for mv, tg in pairs:
            if order in (mv.get("work_orders") or []):
                return busiest, mv, tg
    mid = len(bars) // 2
    return busiest, pairs[mid][0], pairs[mid][1]


def probe(base, sched, order=None):
    doc = _api(base, f"/schedules/{sched}")["data"]
    n = len(doc.get("assignments") or [])
    machine, mover, target = gesture(doc, order)
    pin = {"pin_op_id": mover["operation_ref"],
           "pin_resource_id": mover["resource_id"],
           "pin_start_iso": _start_of(target)}

    print(f"\n{'='*70}\nBOARD {sched}  ({n} bars)")
    print(f"  machine   : {machine}")
    print(f"  move      : {mover.get('work_orders')} op{mover.get('op_seq')}")
    print(f"  from      : {_start_of(mover)}")
    print(f"  onto      : {pin['pin_start_iso']} "
          f"(occupied by {target.get('work_orders')} op{target.get('op_seq')})")

    t0 = time.perf_counter()
    g = _api(base, f"/schedules/{sched}/sandbox/feasibility", pin)["data"]
    round_trip = time.perf_counter() - t0
    print(f"\n  BEAT ONE  http {round_trip:.2f}s  solve {g['wall_time_s']}s "
          f"budget {g['budget_s']}s")
    print(f"    status={g['status']}  feasible={g['feasible']}  "
          f"within_budget={g['within_budget']}")
    print(f"    message : {g['message']!r}")
    print(f"    -> cockpit controller.js:465 would "
          f"{'FIRE BEAT TWO' if g['feasible'] else 'SNAP BACK (no beat two)'}")

    t0 = time.perf_counter()
    c = _api(base, f"/schedules/{sched}/sandbox",
             {**pin, "correlation_id": g.get("correlation_id")})["data"]
    print(f"\n  BEAT TWO  http {time.perf_counter()-t0:.2f}s  "
          f"solve {c['wall_time_s']}s budget {c['budget_s']}s")
    print(f"    outcome={c['outcome']}  status={c['status']}  "
          f"feasible={c['feasible']}")
    print(f"    cost_delta_abs = {c.get('cost_delta_abs')}  "
          f"(reopt {c.get('reopt_delta_abs')} / move {c.get('move_delta_abs')})")
    print(f"    moves={len(c.get('moves') or [])}  "
          f"affected={[o.get('work_order') for o in (c.get('affected_orders') or [])]}")
    return {"bars": n, "beat_one": g, "beat_two": c, "http_one_s": round_trip}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--order", default=None)
    args = ap.parse_args()
    dense = probe(args.api, DENSE, args.order)
    pinned = probe(args.api, PINNED)
    print(f"\n{'='*70}\nITEM 1 COMPARISON")
    for label, r in (("dense  ", dense), ("pinned ", pinned)):
        g = r["beat_one"]
        print(f"  {label} {r['bars']:>4} bars  beat one {g['status']:<9} "
              f"feasible={str(g['feasible']):<5} -> "
              f"{'2 requests' if g['feasible'] else '1 REQUEST, snap back'}"
              f"   beat two would price {r['beat_two'].get('cost_delta_abs')}")


if __name__ == "__main__":
    main()

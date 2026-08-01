#!/usr/bin/env python3
"""Session 4B.24 ITEM 6 — VERIFY BY GESTURE. SCRATCH ONLY.

Drives the LIVE API in exactly the sequence `controller.js` drives it: beat one
(`POST /sandbox/feasibility` with the feel token's wall ceiling), then beat two
(`POST /sandbox` with the feel token's ceiling and beat one's correlation id).
Request names, statuses and t+ offsets are printed the way a network tab shows
them, because that is what the brief asks to see.

    python tools/spikes/sandbox_4b24/gestures.py --api http://localhost:8010
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ctx import Board, DEMO, PINNED  # noqa: E402

# The two feel tokens the cockpit sends (src/cockpit/src/drag/feel.js).
FEASIBILITY_BUDGET_S = 12.0
SANDBOX_BUDGET_S = 20.0


def post(api, path, body, timeout=900):
    req = urllib.request.Request(
        api + path, data=json.dumps(body).encode(),
        headers={"content-type": "application/json"}, method="POST")
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read())
            return r.status, payload.get("data"), round(time.monotonic() - t0, 3)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), round(time.monotonic() - t0, 3)


def bar_of(board, order, op_seq):
    for a in board.assignments():
        if order in (a.get("work_orders") or []) and a.get("op_seq") == op_seq:
            return a
    raise SystemExit(f"no {order} op{op_seq}")


def drag(api, board, bar, target_iso, label, t_origin=None):
    """One gesture, the cockpit's own two beats, printed as a request sequence."""
    sid = board.schedule_id
    pin = {"pin_op_id": bar["operation_ref"],
           "pin_resource_id": bar["resource_id"],
           "pin_start_iso": target_iso}
    t0 = time.monotonic()
    print(f"\n--- {label}")
    print(f"    {bar['work_orders'][0]} op{bar['op_seq']} on {bar['external_name']}: "
          f"{bar['chunks'][0]['start']} -> {target_iso}")
    print("    request sequence (name / status / t+s):")
    s1, ghost, w1 = post(api, f"/schedules/{sid}/sandbox/feasibility",
                         {**pin, "budget_s": FEASIBILITY_BUDGET_S})
    print(f"      {sid}/sandbox/feasibility  POST  {s1}   +{round(time.monotonic()-t0,2)}s")
    if s1 != 200:
        print("      beat one failed:", ghost)
        return None
    print(f"        verdict={ghost['verdict']} status={ghost['status']} "
          f"det={ghost.get('det_consumed')} wall={ghost['wall_time_s']}s "
          f"wall_truncated={ghost.get('wall_truncated')}")
    if ghost["verdict"] == "impossible":
        print("      -> PROVEN impossible; no beat two (the chain stops only on a proof)")
        return {"beats": 1, "ghost": ghost, "result": None}
    s2, res, w2 = post(api, f"/schedules/{sid}/sandbox",
                       {**pin, "budget_s": SANDBOX_BUDGET_S,
                        "correlation_id": ghost["correlation_id"]})
    print(f"      {sid}/sandbox                POST  {s2}   +{round(time.monotonic()-t0,2)}s")
    if s2 != 200:
        print("      beat two failed:", res)
        return {"beats": 2, "ghost": ghost, "result": None}
    print_card(res)
    return {"beats": 2, "ghost": ghost, "result": res}


def print_card(r):
    print("    CARD:")
    print(f"      outcome={r['outcome']} status={r['status']} feasible={r['feasible']} "
          f"pricing_mode={r['pricing_mode']} wall={r['wall_time_s']}s")
    if r.get("refusal"):
        f = r["refusal"]
        print(f"      REFUSED  [{f['family']}]  {f['sentence']}")
        print(f"        blocking={f.get('other_work_orders')} at={f.get('at')} "
              f"holds_others={f['holds_others']}")
        print(f'      message: "{r["message"]}"')
        return
    if not r["feasible"]:
        print(f'      message: "{r["message"]}"')
        return
    print(f"      attribution={r['attribution']}  your move = "
          f"{fmt(r['move_delta_abs'])}   (reopt {fmt(r['reopt_delta_abs'])})")
    print(f"      cost_delta_abs={fmt(r['cost_delta_abs'])}  "
          f"cost_delta_pct={r['cost_delta_pct']}")
    print(f"      AFFECTED ORDERS: {r['affected_orders'] or '(none)'}")
    print(f"      moves: {len(r['moves'])}   lateness_delta_min={r['lateness_delta_min']}")
    print(f"      validation: {r.get('validation')}")
    if r.get("opportunity"):
        print(f"      OPPORTUNITY (its own section): {r['opportunity'].get('sentence')}")
    else:
        print("      OPPORTUNITY: not requested on this gesture (clause 3 is a "
              "deliberate act — see 'search deeper')")


def fmt(v):
    if v is None:
        return "n/a"
    return f"{'-' if v < 0 else '+'}${abs(v):,.2f}" if abs(v) >= 0.005 else "$0.00"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8010")
    ap.add_argument("--only", nargs="*", default=list("abcde"))
    a = ap.parse_args()
    demo = Board(DEMO)
    founder = bar_of(demo, "ORD-000057", 30)
    fstart = datetime.fromisoformat(
        founder["chunks"][0]["start"].replace("Z", "+00:00"))
    nudge = (fstart + timedelta(hours=4)).isoformat()

    if "a" in a.only:
        print("\n" + "=" * 70)
        print("6(a) THE FOUNDER'S NUDGE — four hours inside its own overtime window")
        print("=" * 70)
        drag(a.api, demo, founder, nudge, "founder's nudge")

    if "b" in a.only:
        print("\n" + "=" * 70)
        print("6(b) A REAL COLLISION — dropped onto occupied time")
        print("=" * 70)
        occupied = bar_of(demo, "ORD-000123", 30)
        onto = datetime.fromisoformat(
            occupied["chunks"][0]["start"].replace("Z", "+00:00")) + timedelta(hours=1)
        drag(a.api, demo, founder, onto.isoformat(), "collision drop")

    if "c" in a.only:
        print("\n" + "=" * 70)
        print("6(c) THE SAME GESTURE FIVE TIMES")
        print("=" * 70)
        cards = []
        for i in range(5):
            r = drag(a.api, demo, founder, nudge, f"repetition {i + 1}")
            res = r and r["result"]
            cards.append(None if not res else (
                res["cost_delta_abs"], res["move_delta_abs"], res["attribution"],
                json.dumps(res["affected_orders"], sort_keys=True),
                json.dumps(res["moves"], sort_keys=True), res["status"]))
        print("\n    DISTINCT CARDS:", len(set(map(str, cards))))
        for c in set(map(str, cards)):
            print("      ", c[:160])

    if "d" in a.only:
        print("\n" + "=" * 70)
        print("6(d) THE PINNED WORLD — regression")
        print("=" * 70)
        pinned = Board(PINNED)
        movable = [x for x in pinned.assignments()
                   if x.get("commitment_state") != "committed" and x.get("chunks")]
        movable.sort(key=lambda x: x["chunks"][0]["start"])
        bar = movable[0]
        s = datetime.fromisoformat(bar["chunks"][0]["start"].replace("Z", "+00:00"))
        drag(a.api, pinned, bar, (s + timedelta(hours=1)).isoformat(),
             "a drag on the pinned exam world")

    if "e" in a.only:
        print("\n" + "=" * 70)
        print("6(e) SEARCH DEEPER — the deliberate audit (clause 5)")
        print("=" * 70)
        t0 = time.monotonic()
        st, res, w = post(a.api, f"/schedules/{demo.schedule_id}/audit", {})
        print(f"      {demo.schedule_id}/audit  POST  {st}   +{round(time.monotonic()-t0,2)}s")
        if st != 200:
            print("      failed:", res)
            return
        print(f"      searched={res['searched']} seed={res['seed']} "
              f"det_time_s={res['det_time_s']} det_consumed={res['det_consumed']} "
              f"status={res['status']} wall={res['wall_time_s']}s")
        print(f'      SENTENCE: "{res["sentence"]}"')
        off = res.get("offer")
        if off:
            print(f"      OFFER: {fmt(off['delta_abs'])}, {off['moved_op_count']} ops move")
            print("      ITS OWN AFFECTED LIST:")
            for x in off["affected_orders"]:
                print(f"        {x['work_order']}  {fmt(x['tardiness_delta'])}  "
                      f"{x['lateness_delta_min']:+d} min")
        else:
            print("      no offer — the incumbent-held sentence above is the answer")


if __name__ == "__main__":
    main()

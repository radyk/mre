"""Errand 4B.22a Item 4 -- verify the demo surfaces on a registered board.

Runs, against the LIVE dev API and the same endpoints the cockpit calls:

  (a) the opener            "what should I be worried about"
  (b) lateness              "why is <a late order> late"
  (c) the counterfactual    "what would have to change for <that order> to
                             start earlier"
  (d) past due              "where is <a past-due order>"
  (e) A SANDBOX MOVE        POST /sandbox/feasibility (beat one) then
                            POST /sandbox (beat two), and the delta card in full

Subjects are CHOSEN FROM THE BOARD, not authored: the late order is the one with
the largest positive `lateness_min` in the document's service outcomes, the
past-due order is the placed order with the earliest due date behind the
reference origin. If the board has no such order the script SAYS SO and does not
substitute a different question -- an errand that silently swapped its own
specimen would prove nothing.

(e) IS THE POINT OF THE ERRAND, and it delegates to `sandbox_move.py` so the
identical gesture can be run against the old board and the new one. The move is
a COLLISION -- the pinned operation is dropped onto the start of a DIFFERENT
operation already occupying the busiest machine, so the re-solve must displace
something or refuse. A move that prices at $0 with an empty affected-orders list
means the board still has no contention: that is a result, not a bug here.

    python tools/spikes/demo_board_4b22a/verify_demo_surfaces.py \
        --schedule rolling-xxxxxxxx-xxx --out _4b22a_scratch/item4.json

`--llm` is ON by default: the contracted routes render deterministically but the
synthesis tier and the LLM renderer need the key, and an answer produced without
one is the honest could-not-interpret floor rather than the product. The key is
read exactly once, through `mre.env_local` -- the ONE reader (4B.16a).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

REF = datetime.fromisoformat("2026-01-05T00:00:00+00:00")


def _api(base: str, path: str, body=None, timeout: float = 180.0):
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json"} if data is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        payload = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"{path} -> HTTP {e.code}: {payload[:500]}") from e


def _dt(v):
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def _banner(t: str):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


def ask(base: str, sched: str, question: str, use_llm: bool,
        session_id: str) -> dict:
    t0 = time.perf_counter()
    r = _api(base, f"/schedules/{sched}/ask",
             {"question": question, "llm": use_llm, "session_id": session_id})
    d = r["data"]
    d["_wall_s"] = round(time.perf_counter() - t0, 1)
    return d


def print_answer(label: str, question: str, d: dict):
    _banner(f"{label}   {question!r}")
    b = d.get("bundle") or {}
    print(f"[route={b.get('route')} register={b.get('register')} "
          f"intent={b.get('intent')} confidence={b.get('confidence')} "
          f"{d['_wall_s']}s]")
    print()
    print(d["answer"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--api-base", default="http://localhost:8000")
    ap.add_argument("--out", default="_4b22a_scratch/item4.json")
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args(argv)

    from mre.env_local import load_env_local
    load_env_local()

    base, sched = args.api_base, args.schedule
    use_llm = not args.no_llm
    session = f"4b22a-{sched}"
    doc = _api(base, f"/schedules/{sched}")["data"]

    # ---- pick the subjects, from the board --------------------------------
    outcomes = doc.get("service_outcomes") or []
    assigns = doc.get("assignments") or []
    late = sorted((o for o in outcomes if (o.get("lateness_min") or 0) > 0),
                  key=lambda o: -(o["lateness_min"]))
    past_due = sorted((o for o in outcomes
                       if o.get("due") and _dt(o["due"]) < REF),
                      key=lambda o: _dt(o["due"]))
    late_order = late[0]["work_order"] if late else None
    past_due_order = past_due[0]["work_order"] if past_due else None

    print(f"board {sched}: {len(assigns)} bars, {len(outcomes)} service outcomes")
    print(f"  late orders on the board : {len(late)}"
          + (f"  (worst: {late_order}, {late[0]['lateness_min']} min)" if late else ""))
    print(f"  past-due orders placed   : {len(past_due)}"
          + (f"  (earliest due: {past_due_order}, {past_due[0]['due']})"
             if past_due else ""))

    results = {"schedule_id": sched, "late_order": late_order,
               "past_due_order": past_due_order, "answers": {}}

    def _record(key, label, question):
        d = ask(base, sched, question, use_llm, session)
        print_answer(label, question, d)
        results["answers"][key] = {"question": question, "answer": d["answer"],
                                   "bundle": d.get("bundle"),
                                   "wall_s": d["_wall_s"]}

    # (a) ---------------------------------------------------------------
    _record("a_opener", "ITEM 4(a) THE OPENER", "what should I be worried about")

    # (b) ---------------------------------------------------------------
    if late_order:
        _record("b_late", "ITEM 4(b) LATENESS", f"why is {late_order} late")
        # (c) -----------------------------------------------------------
        _record("c_counterfactual", "ITEM 4(c) THE COUNTERFACTUAL",
                f"what would have to change for {late_order} to start earlier")
    else:
        _banner("ITEM 4(b)/(c) NOT RUN")
        print("The board carries NO late order. The errand's specimen does not "
              "exist here and no substitute question was asked.")
        results["answers"]["b_late"] = {"skipped": "no late order on the board"}
        results["answers"]["c_counterfactual"] = {
            "skipped": "no late order on the board"}

    # (d) ---------------------------------------------------------------
    if past_due_order:
        _record("d_past_due", "ITEM 4(d) PAST DUE (R-PD1's specimen)",
                f"where is {past_due_order}")
    else:
        _banner("ITEM 4(d) NOT RUN")
        print("No past-due order is placed on this board.")
        results["answers"]["d_past_due"] = {"skipped": "no past-due order placed"}

    # (e) THE SANDBOX MOVE ------------------------------------------------
    _banner("ITEM 4(e) A SANDBOX MOVE -- THE POINT OF THE ERRAND")
    from sandbox_move import run as run_move

    move = run_move(base, sched)
    results["sandbox"] = move
    card = (move.get("chosen") or {}).get("card") or {}

    print("\n--- THE VERDICT THIS ERRAND TURNS ON ---")
    print(f"  cost_delta_abs      : {card.get('cost_delta_abs')}")
    print(f"  attribution         : {card.get('attribution')}")
    print(f"  reopt_delta_abs     : {card.get('reopt_delta_abs')}")
    print(f"  move_delta_abs      : {card.get('move_delta_abs')}")
    print(f"  affected_orders     : {len(card.get('affected_orders') or [])} row(s)")
    print(f"  moves               : {len(card.get('moves') or [])}")
    print(f"  lateness_delta_min  : {card.get('lateness_delta_min')}")
    if not (card.get("affected_orders") or []) and not card.get("cost_delta_abs"):
        print("\n  !! THE MOVE COST NOTHING AND TOUCHED NOTHING. The board has "
              "not met the errand's contention target.")

    Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Replay a pinned board's edit lineage through the REAL accept path.

R-PW1(4): the edits that built a pinned world are a committed script, not a
memory of some drags. The Khalil board's lineage was made by hand and died with
it; this is what a lineage that can survive the same accident looks like.

NOTHING HERE WRITES TO THE REGISTRY. Every child is minted by the product's own
two-beat gesture and its accept -- `POST /sandbox/feasibility` (beat one),
`POST /sandbox` (beat two), `POST /accept` -- so the children carry real
`planner_edit` Decision records with the `PLANNER_DIRECTIVE` driver (R-DP13),
priced under R-DP11's plan-of-record scope and R-DP12's cleared objective. A
script that inserted rows would produce a board that LOOKED edited and had never
been through the code the edit exists to exercise.

TWO EDITS, AND THE SECOND ONE IS THE POINT:

  1. A ZERO-MOVE accept -- pin an operation at its own placement. This is
     4B.31's founding specimen and it always prices at $0.00. It mints an
     AUTHORITY-ONLY child: real Decision, real driver, no placement changed.
  2. A REAL MOVE, taken from a declared ladder of (operation, offset) candidates
     in a fixed order, first one that beat one allows and beat two prices. This
     is what makes the tip PLACEMENT-BEARING, which is what R-GP1 requires
     before a child may be CURRENT -- an authority-only tip would leave the
     board's newest version unable to outrank its own parent.

The ladder is walked in a FIXED ORDER and the first success wins, so the script
is deterministic given a board; which candidate succeeded is REPORTED, because
on a dense board most drags are refusals (4B.32 measured 50 of 54) and a script
that hid which one landed would make its own output unreproducible.

    python tools/worlds/replay_demo_lineage.py --schedule rolling-xxxx-xxx
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta

# The declared candidate ladder: MINUTES to push a bar later, deliberately
# small. The first version of this ladder used whole days (+24h/+48h/+72h) and
# every one of 48 probes was refused C1/C2 "the machine is not open at that
# time" -- a day-scale offset lands wherever the calendar happens to be, and on
# a plant with shifts that is usually shut. A nudge of an hour or two stays
# inside the open window the bar is already in, which is the gesture a planner
# actually makes (4B.24's founder nudge was four hours inside a window the order
# already occupied).
#
# Later, not earlier: earlier is a refusal on a board this dense far more often
# than not, and the point here is to land ONE placement change, not to measure
# mobility.
OFFSET_MINUTES = (60, 120, 30, 240)
MAX_CANDIDATE_OPS = 40


def api(base, path, body=None, timeout=300.0):
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json"} if data is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"{path} -> HTTP {e.code}: "
            f"{e.read().decode('utf-8', 'replace')[:500]}") from e


def active_bars(doc):
    """Active (uncommitted), single-chunk bars, in a fixed order.

    Single-chunk only: a CHUNKED operation cannot be locally priced and the
    sandbox declines it by name (4B.24), so offering one to the ladder would
    spend a beat-one budget to be told something already known.
    """
    out = []
    for a in doc.get("assignments") or []:
        chunks = a.get("chunks") or []
        if a.get("commitment_state") == "committed" or len(chunks) != 1:
            continue
        if not chunks[0].get("start"):
            continue
        out.append((a["operation_ref"], a["resource_id"], chunks[0]["start"]))
    return sorted(out)


REFUSALS: dict[str, int] = {}


def accept(base, sched, op, res, start_iso, authority, label):
    """One gesture, all three beats, reported whatever it does."""
    print(f"\n--- {label}")
    print(f"    op {op} on {res} -> {start_iso}")
    ghost = api(base, f"/schedules/{sched}/sandbox/feasibility",
                {"pin_op_id": op, "pin_resource_id": res,
                 "pin_start_iso": start_iso, "deterministic": True})["data"]
    verdict = ghost.get("verdict")
    print(f"    beat one : {verdict}")
    if verdict == "impossible":
        ref = ghost.get("refusal") or {}
        fam = (ref.get("family") if isinstance(ref, dict) else None) or "(none)"
        REFUSALS[fam] = REFUSALS.get(fam, 0) + 1
        print(f"      refused: {ref}")
        return None
    priced = api(base, f"/schedules/{sched}/sandbox",
                 {"pin_op_id": op, "pin_resource_id": res,
                  "pin_start_iso": start_iso, "deterministic": True})["data"]
    if priced.get("refused") or priced.get("status") in ("INFEASIBLE",):
        print(f"    beat two : REFUSED {priced.get('refusal_reason') or ''}")
        return None
    print(f"    beat two : total_delta="
          f"{(priced.get('cost_delta') or {}).get('total_delta')}  "
          f"status={priced.get('status')}")
    child = api(base, f"/schedules/{sched}/accept",
                {"pin_op_id": op, "pin_resource_id": res,
                 "pin_start_iso": start_iso, "authority": authority})["data"]
    dec = child.get("decision") or {}
    print(f"    ACCEPTED : child {child['schedule_id']}")
    print(f"      driver   : {dec.get('driver')}")
    print(f"      basis    : {dec.get('basis')}   authority: {authority}")
    return child["schedule_id"]


def audit_accept(base, sched, authority, det_time_s=None):
    """THE SECOND CEREMONY (R-T2 amendment clauses 4-5).

    ``POST /audit`` runs the deterministic seeded search and OFFERS what it
    found; ``POST /audit/accept`` is a separate act with its own authority, and
    is handed the offer's own ``delta_abs`` so a board that re-solved
    differently is REFUSED rather than accepted silently (4B.25 Item 4a).
    """
    print("\n--- SECOND CEREMONY: POST /audit (the deliberate search)")
    # AUDIT_K and AUDIT_DET_TIME_S are CONSTANTS (3 at 3.0 units) and are NOT
    # calibrated -- 4B.29 §5a.111 named that and it bites here: at 3.0 units on
    # this plant all three seeded members came back unusable and the audit
    # honestly said so. The plant's ACCEPTED profile says 10.0, so that is what
    # this asks for; the budget is stated rather than defaulted.
    body = {} if det_time_s is None else {"det_time_s": float(det_time_s)}
    if body:
        print(f"    budget     : det_time_s={det_time_s} (the plant's "
              f"calibrated budget; the audit's own default is 3.0)")
    offer = api(base, f"/schedules/{sched}/audit", body, timeout=3600.0)["data"]
    delta = offer.get("delta_abs")
    print(f"    offer      : delta_abs={delta}  moved={offer.get('moved_count')}")
    print(f"    sentence   : {str(offer.get('sentence') or '')[:220]}")
    if not offer.get("improved") and (delta is None or delta >= 0):
        print("    the audit HELD THE INCUMBENT -- nothing to accept")
        return None
    got = api(base, f"/schedules/{sched}/audit/accept",
              {"authority": authority, "expect_delta_abs": delta},
              timeout=1800.0)["data"]
    print(f"    ACCEPTED   : child {got['schedule_id']}")
    print(f"      audit    : {json.dumps(got.get('audit'), default=str)[:300]}")
    return got["schedule_id"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--api-base", default="http://localhost:8000")
    ap.add_argument("--authority", default="4x-lineage-replay")
    ap.add_argument("--continue-from", default="",
                    help="an EDIT 1 child that already exists -- resume at "
                         "EDIT 2 instead of minting a second zero-move child")
    ap.add_argument("--audit-only", action="store_true",
                    help="skip the nudge ladder and go straight to the second "
                         "ceremony (use with --continue-from)")
    ap.add_argument("--audit-det-time", type=float, default=None,
                    help="deterministic units per audit member; the audit's own "
                         "default is 3.0 and is NOT calibrated (4B.29)")
    args = ap.parse_args(argv)

    doc = api(args.api_base, f"/schedules/{args.schedule}")["data"]
    bars = active_bars(doc)
    print(f"board {args.schedule}: {len(doc.get('assignments') or [])} bars, "
          f"{len(bars)} active single-chunk candidates")
    if not bars:
        print("no editable bar on this board", file=sys.stderr)
        return 1

    lineage = [args.schedule]

    if args.continue_from:
        child = args.continue_from
        print(f"\n--- EDIT 1: resuming from existing child {child}")
        lineage.append(child)
    else:
        # EDIT 1 -- the zero-move accept. Authority changes, nothing moves.
        op, res, start = bars[0]
        child = accept(args.api_base, args.schedule, op, res, start,
                       args.authority,
                       "EDIT 1: zero-move accept (authority only)")
        if child is None:
            print("the zero-move accept was refused -- that is a finding, not "
                  "a flake; stopping rather than papering over it",
                  file=sys.stderr)
            return 1
        lineage.append(child)

    # EDIT 2 -- the first candidate that lands. Walked in a fixed order.
    doc2 = api(args.api_base, f"/schedules/{child}")["data"]
    moved = None
    tried = 0
    candidates = [] if args.audit_only else active_bars(doc2)[:MAX_CANDIDATE_OPS]
    for op, res, start in candidates:
        for mins in OFFSET_MINUTES:
            when = (datetime.fromisoformat(start.replace("Z", "+00:00"))
                    + timedelta(minutes=mins))
            target = when.isoformat().replace("+00:00", "Z")
            tried += 1
            got = accept(args.api_base, child, op, res, target, args.authority,
                         f"EDIT 2 candidate {tried}: {op[:8]} +{mins}min")
            if got:
                moved = (op, res, start, target, mins, got)
                break
        if moved:
            break

    print(f"\n{tried} candidate gesture(s) tried; beat-one refusals by family: "
          f"{REFUSALS}")
    if moved is None:
        # NOT A WORKAROUND, A DIFFERENT CEREMONY. R-T2 amendment clause (4)
        # and (5): accepting the planner's MOVE and accepting the SEARCH's
        # improvement are two acts with two endpoints and two Decisions. The
        # nudge ladder having found nothing is a fact about this board's
        # density, not a reason to fake a planner move -- so the placement-
        # bearing tip comes from the audit, WITH ITS OWN DRIVER
        # (`COST_TRADEOFF`, not `PLANNER_DIRECTIVE`), and the lineage carries
        # both kinds of authorship, which is what a real board looks like.
        print("\nNO PLANNER NUDGE LANDED on this board. Falling through to the "
              "SECOND CEREMONY (the audit) for a placement-bearing tip.")
        got = audit_accept(args.api_base, child, args.authority,
                           det_time_s=args.audit_det_time)
        if got is None:
            print("\nThe audit held the incumbent too. The lineage tip is "
                  "AUTHORITY-ONLY: real Decisions, no placement change, so by "
                  "R-GP1 it does not outrank its parent. Reported, not worked "
                  "around.", file=sys.stderr)
        else:
            lineage.append(got)
            print(f"\nPLACEMENT-BEARING TIP (audit): {got}")
    else:
        op, res, start, target, mins, got = moved
        lineage.append(got)
        print(f"\nPLACEMENT-BEARING TIP: {got}")
        print(f"  moved {op} on {res}  {start} -> {target}  (+{mins}min)")

    print("\nLINEAGE (root -> tip):")
    for i, sid in enumerate(lineage):
        print(f"  {i}. {sid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

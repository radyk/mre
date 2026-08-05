"""Errand 4B.22a Item 3 -- mint the chosen demo board through the NORMAL path.

Generate the `demo_board` submission, then take it through the two steps the API
actually exposes -- POST /submissions (the M0 gate -> a certificate) and POST
/submissions/{id}/solve (sliced, deterministic, coarse) -- so the registered
board carries everything a real board carries: a certificate grade, a persisted
run, a schema-2 evidence index, the coarse zone, the beyond-horizon tray, and
the current contract.

    python tools/spikes/demo_board_4b22a/mint_demo_board.py

Its defaults ARE the chosen board: 280 orders, window 10, frozen 1, seed 1,
reference 2026-01-05. Run bare, it reproduces `rolling-c9973708-865`'s world
(a fresh run id and schedule id, the same placements).

**ONLY IF THE DATA ROOT HOLDS NO ACCEPTED PROFILE FOR THIS PLANT** (R-PW1(3),
measured 2026-08-04). The bare request declares `portfolio_k` but NOT
`portfolio_det_time`, and R-CAL1 rule (2) withholds only what the caller
declared -- so with a profile present the solve silently takes the profile's
`det_total` (10.0 here, not 6.0) and lands on a DIFFERENT board. That is the
rule working; the recipe is what was incomplete. Verified both ways on
2026-08-04: with the profile in place the bare command produced ledger
$2,135,369.63 (digest `f836c206...`); with it withheld it reproduced
`rolling-c9973708-865` exactly -- digest
`ac86d185e8a977838335bde3a33a08dd01d394ce36f5117c1c6b101ec353fd6a`, ledger
$2,127,482.58 to the cent. To reproduce that board, move
`_data/calibration/<plant>.json` aside first, or read the `solver.calibration`
block afterwards and check `applied` is empty.

WHY NOT `build_rolling_exam_run.py`. That tool mints the PINNED EXAM WORLD --
`_ai_exam_scratch/rolling_pinned`, 40 pilot_scale orders at window 14 / frozen 3,
the regression target six sessions of AI measurement are calibrated against. Its
constants ARE the exam world; parameterising them would make the exam target a
function of whoever ran it last. So this is a sibling, and
`rolling-c362baa4-1b0` is not touched, replaced or re-solved.

`time_limit` is the WALL CEILING, not the budget: under `deterministic: true`
the deterministic budget must be what binds, and the API's own `det_total`
(6.0, not a request field) is that budget. The ceiling is set far above it.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "src"))

REF = "2026-01-05"
GEN_SEED = 1
WALL_CEILING_S = 900.0


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
        raise RuntimeError(f"{path} -> HTTP {e.code}: "
                           f"{e.read().decode('utf-8', 'replace')[:600]}") from e
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise RuntimeError(f"{path} -> unreachable: {e}") from e


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--orders", type=int, default=280)
    ap.add_argument("--pd-share", type=float, default=0.12)
    ap.add_argument("--lead-p50", type=int, default=10)
    # THE CHOSEN CONFIGURATION, as defaults. `window_days` is a SolveRequest
    # field, so 10 is a solve parameter and not a product change; it is the
    # measured choice (14 returns an EMPTY board at this density, 7 places 100
    # fewer bars at a similar gap). `frozen_days` 1 is what leaves a planner 345
    # draggable bars instead of the pinned world's 11.
    ap.add_argument("--window-days", type=int, default=10)
    ap.add_argument("--frozen-days", type=int, default=1)
    ap.add_argument("--out", default="_4b22a_scratch/demo_board/submission")
    ap.add_argument("--api-base", default="http://localhost:8000")
    ap.add_argument("--poll-timeout", type=float, default=1800.0)
    # Session 4B.28 Item 5 — THE KHALIL BOARD. Same world, different SEARCH.
    # `--calibrated` omits `portfolio_k` and `portfolio_det_time` from the solve
    # request entirely, which is the ONLY way the plant's accepted calibration
    # profile can apply: R-CAL1 rule (2) says the caller always wins, and the API
    # reads `model_fields_set` to find out what the caller actually said. So a
    # request that names K=1 "to be explicit" silently refuses the profile.
    #
    # The bare command is UNCHANGED and still reproduces `rolling-c9973708-865`'s
    # world at K=1 — a registered artifact minted from one seeded search.
    ap.add_argument("--calibrated", action="store_true",
                    help="let this plant's ACCEPTED calibration profile supply K "
                         "and the per-member budget (omits both from the request). "
                         "Mints the Khalil board: w10 / 10.0 units / K=3.")
    ap.add_argument("--reuse", action="store_true",
                    help="reuse the submission already at --out (the generator "
                         "stamps a fresh extract_timestamp on every run, so "
                         "regenerating gives a byte-different manifest for the "
                         "same world)")
    args = ap.parse_args(argv)

    from generate_erp_dataset import generate

    try:
        h = _api(args.api_base, "/health", timeout=5.0)
    except RuntimeError:
        print(f"no API at {args.api_base}. Start it from the repo root with "
              f".\\src\\cockpit\\dev_api.ps1 and re-run. Nothing was built.",
              file=sys.stderr)
        return 2
    print(f"API {args.api_base}: {h['data']['status']}")

    sub = (REPO / args.out).resolve()
    if sub.exists() and args.reuse and (sub / "manifest.json").exists():
        print(f"reusing submission at {sub}")
    else:
        if sub.exists():
            shutil.rmtree(sub)
        print(f"generating demo_board ({args.orders} orders, "
              f"pd={args.pd_share}, lead_p50={args.lead_p50}, "
              f"seed={GEN_SEED}) ...")
        marker = generate(sub, scenario="demo_board", orders=args.orders,
                          seed=GEN_SEED, pd_share=args.pd_share,
                          lead_p50=args.lead_p50)
        ps = marker.get("pilot_scale", {})
        print(f"  past-due orders generated: "
              f"{ps.get('past_due_orders_generated')} of {args.orders}")
        print(f"  maintenance closure: {ps.get('maintenance_day')}   "
              f"overtime Saturday: {ps.get('overtime_saturday')}")

    print(f"submitting {sub} ...")
    s = _api(args.api_base, "/submissions", {"path": str(sub)},
             timeout=300.0)["data"]
    sub_id, grade = s["submission_id"], s["grade"]
    print(f"certificate grade {grade} (costing {s.get('costing_grade')}), "
          f"submission {sub_id}")
    for d in s.get("deficiencies", []) or []:
        print(f"  - {d}")
    if grade == "REJECTED":
        print("REJECTED submissions never solve.", file=sys.stderr)
        return 1

    # K=1, PINNED EXPLICITLY (Session 4B.29 Item 1(b)). The product default
    # became 3, and `rolling-c9973708-865` is a REGISTERED ARTIFACT minted from
    # ONE seeded search: a K=3 rebuild would legitimately publish a different
    # board (best of three, not seed 42's), so this command would stop
    # reproducing the board its own docstring says it reproduces. The flip
    # changes FUTURE solves; it does not retroactively re-mint the demo board.
    req = {"policy": "identity_v1", "deterministic": True, "sliced": True,
           "window_days": args.window_days, "frozen_days": args.frozen_days,
           "time_limit": WALL_CEILING_S, "coarse": True,
           "portfolio_k": 1,
           "reference_date": REF}
    # `--calibrated` REMOVES the field rather than setting a different value:
    # R-CAL1 rule (2) reads `model_fields_set`, so a request naming ANY K —
    # including the profile's own — refuses the profile. Written as a deletion so
    # the K=1 literal above stays in this file, where 4B.29's guard
    # (`test_the_two_minted_worlds_pin_k_one`) can still see that the bare
    # command reproduces `rolling-c9973708-865`.
    if args.calibrated:
        del req["portfolio_k"]
    print(f"solving sliced (window={args.window_days}d "
          f"frozen={args.frozen_days}d, deterministic, coarse"
          + (", CALIBRATED: K and budget from the accepted profile"
             if args.calibrated else ", K=1 pinned") + ") ...")
    run = _api(args.api_base, f"/submissions/{sub_id}/solve", req,
               timeout=120.0)["data"]
    run_id = run["run_id"]

    t0 = time.perf_counter()
    while True:
        row = _api(args.api_base, f"/runs/{run_id}")["data"]
        if row["status"] in ("succeeded", "failed"):
            break
        if time.perf_counter() - t0 > args.poll_timeout:
            print(f"run {run_id} still '{row['status']}' after "
                  f"{args.poll_timeout:.0f}s.", file=sys.stderr)
            return 1
        time.sleep(3.0)

    if row["status"] == "failed":
        print(f"run {run_id} FAILED: {row.get('error')}", file=sys.stderr)
        return 1
    result = row.get("result") or {}
    sched = result.get("schedule_id")
    if not sched:
        print(f"run succeeded but registered no schedule: {result}",
              file=sys.stderr)
        return 1

    print(f"\nrun {run_id} succeeded in {time.perf_counter()-t0:.0f}s")
    print(f"  {result.get('committed')} committed, "
          f"{result.get('beyond_horizon')} in the tray")
    meta = _api(args.api_base, f"/schedules/{sched}/meta")["data"]
    print("")
    print("=" * 68)
    print(f"  SCHEDULE ID : {sched}")
    print(f"  submission  : {sub_id}   grade {grade} / "
          f"costing {meta.get('costing_grade')}")
    print(f"  cost proof  : {meta.get('cost_proof', {}).get('state')} "
          f"(status {meta.get('cost_proof', {}).get('status')}, "
          f"gap {meta.get('cost_proof', {}).get('gap')})")
    print(f"  contract    : {meta.get('contract_version')}")
    print("")
    print(f"  localhost:5175/?theme=light&schedule={sched}")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Session 4B.25 Items 2, 4a and 5(b/c) -- the audit portfolio, live, and the
accept's SUCCESS branch executed for the first time.

Runs against a SCRATCH COPY of the data root (`_4b25_scratch/dataroot`), holding
only the dense demo board `rolling-c9973708-865` and its submission. Nothing is
minted into the working `_data/` root; the registered demo board is untouched.

  1. POST /schedules/{id}/audit with k=K, TWICE. The two offers must be
     IDENTICAL -- that is the portfolio's determinism proven, not asserted.
  2. POST /schedules/{id}/audit/accept with the WINNING SEED and the offer's own
     delta as `expect_delta_abs`. The server refuses to mint a child whose
     ledger does not match the promise to the cent.
  3. Verify the child: registered, lineage to its parent, renders as a document,
     and `cost_summary.total == incumbent_total + offer.delta_abs` TO THE CENT.

    python tools/spikes/portfolio_4b25/audit_and_accept.py --k 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "src"))

BOARD = "rolling-c9973708-865"
ROOT = REPO / "_4b25_scratch" / "dataroot"


def _emit(row: dict) -> None:
    row["t"] = time.time()
    with (HERE / "audit_accept.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
    print(json.dumps(row, default=str)[:2000], flush=True)


def _offer_key(res: dict) -> tuple:
    """Everything that must be identical between two runs of the same audit --
    compared on the full tuple, not the headline (the 4B.24 convention)."""
    off = res.get("offer") or {}
    pf = res.get("portfolio") or {}
    return (res.get("sentence"), res.get("winning_seed"),
            off.get("delta_abs"), off.get("moved_op_count"), off.get("seed"),
            json.dumps(off.get("affected_orders"), sort_keys=True),
            json.dumps([m.get("ledger_total") for m in pf.get("members", [])]),
            pf.get("spread_abs"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--det-time", type=float, default=3.0)
    ap.add_argument("--budget", type=float, default=1800.0)
    ap.add_argument("--board", default=BOARD)
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--no-accept", action="store_true")
    # Skip the (~12 minute) audits and accept a KNOWN offer. Only legitimate
    # because the audits above proved the portfolio deterministic: the offer is
    # recomputable, so it does not have to be re-earned to be accepted.
    ap.add_argument("--accept-only", nargs=2, metavar=("SEED", "DELTA"),
                    default=None)
    a = ap.parse_args(argv)

    os.environ["MRE_DATA_ROOT"] = str(Path(a.root).resolve())
    os.environ.setdefault("MRE_DEV", "1")
    from fastapi.testclient import TestClient
    from mre.api.app import create_app

    client = TestClient(create_app())
    doc = client.get(f"/schedules/{a.board}").json()["data"]
    incumbent = round(float(doc["cost_summary"]["total"]), 2)
    _emit({"kind": "incumbent", "board": a.board, "total": incumbent,
           "status": doc["solver"]["status"], "gap": doc["solver"].get("gap"),
           "contract": doc["contract_version"]})

    if a.accept_only:
        results = [{"offer": {"seed": int(a.accept_only[0]),
                              "delta_abs": float(a.accept_only[1])}}]
        a.repeats = 0
    results = results if a.accept_only else []
    for i in range(a.repeats):
        t0 = time.monotonic()
        r = client.post(f"/schedules/{a.board}/audit",
                        json={"k": a.k, "det_time_s": a.det_time,
                              "budget_s": a.budget})
        r.raise_for_status()
        res = r.json()["data"]
        _emit({"kind": "audit", "rep": i, "wall_s": round(time.monotonic() - t0, 3),
               "sentence": res.get("sentence"),
               "winning_seed": res.get("winning_seed"),
               "offer_delta": (res.get("offer") or {}).get("delta_abs"),
               "portfolio": res.get("portfolio")})
        results.append(res)

    if a.repeats:
        keys = {_offer_key(r) for r in results}
        _emit({"kind": "determinism", "repeats": a.repeats,
               "distinct_offers": len(keys), "identical": len(keys) == 1})

    res = results[0]
    offer = res.get("offer")
    if offer is None:
        _emit({"kind": "accept", "skipped": "the audit made no offer — the "
                                            "success branch needs one"})
        return 0
    if a.no_accept:
        _emit({"kind": "accept", "skipped": "--no-accept"})
        return 0

    t0 = time.monotonic()
    r = client.post(f"/schedules/{a.board}/audit/accept",
                    json={"k": a.k, "det_time_s": a.det_time,
                          "budget_s": a.budget, "seed": offer.get("seed"),
                          "expect_delta_abs": offer.get("delta_abs"),
                          "authority": "4B.25-item-4a"})
    if r.status_code >= 400:
        _emit({"kind": "accept", "http": r.status_code, "body": r.text[:1500]})
        return 1
    acc = r.json()["data"]
    child_id = acc["schedule_id"]
    child = client.get(f"/schedules/{child_id}").json()["data"]
    child_total = round(float(child["cost_summary"]["total"]), 2)
    promised = round(incumbent + float(offer["delta_abs"]), 2)
    _emit({
        "kind": "accept", "wall_s": round(time.monotonic() - t0, 3),
        "child_schedule_id": child_id,
        "parent_schedule_id": acc.get("parent_schedule_id"),
        "status": acc.get("status"),
        "audit": acc.get("audit"),
        "child_total": child_total,
        "promised_total": promised,
        "equal_to_the_cent": abs(child_total - promised) <= 0.005,
        "child_bars": len(child.get("assignments", [])),
        "child_contract": child.get("contract_version"),
        "child_parent_in_doc": (child.get("scenario") or {}).get(
            "parent_schedule_id") if child.get("scenario") else None,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

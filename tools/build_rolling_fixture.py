"""Build the committed cockpit fixture for the SLICED (rolling-horizon) world
(Session 4B.3a CU2). Generates a pilot_scale plant, solves the CURRENT window
(build_rolling_view), assembles the contract-1.7 rolling document, and writes a
hermetic fixture set the Playwright harness serves — so CI renders the real
rolling document (committed frozen front + active window + beyond-horizon tray)
with NO solver in the browser test.

Two fixtures are written under tests/cockpit/fixtures/rolling/:
  * schedule.json  — the real assembled contract-1.7 document (POPULATED tray)
  * meta.json      — the registry meta the top strip reads
  * asks.json      — canned AI answers for the CU3 rolling questions
and under tests/cockpit/fixtures/rolling_empty/:
  * schedule.json  — a variant whose tray is empty (window covers the whole book)

Run:  python tools/build_rolling_fixture.py
The output JSON is committed; regenerate only when the contract or plant changes.
"""
from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "src"))

from mre.modules.rolling_horizon import prepare_plant, build_rolling_view
from mre.modules.schedule_assembler import assemble_rolling_document

REF = datetime(2026, 1, 5, tzinfo=timezone.utc)
OUT = REPO / "tests" / "cockpit" / "fixtures"


def _meta(sid: str) -> dict:
    return {
        "id": sid, "schedule_id": sid, "status": "proposed",
        "contract_version": "1.8", "grade": "ACCEPTED", "costing_grade": "C2",
        "created_at": "2026-01-05T09:41:00Z", "generation": 1,
    }


def _asks(doc: dict, gesture: dict | None = None) -> dict:
    """Canned AI answers for the CU3 rolling questions, in the /ask envelope shape
    the fixture server serves. The real deterministic answers are proven by the
    Python tests; these let the cockpit exercise the ask flow hermetically."""
    tray = doc["rolling"]["beyond_horizon"]
    n = len(tray)
    first = tray[0] if tray else None
    beyond_ans = (
        f"{n} order(s) are known but not yet scheduled — they sit beyond the "
        f"current window and will enter a later one. Nearest due: "
        f"{(first or {}).get('work_order', '—')}."
    ) if n else "Nothing is beyond the horizon — every known order is in the current window."
    asks = {
        "what's beyond the horizon?": {
            "question": "what's beyond the horizon?",
            "answer": beyond_ans + "\n\nregister: testimony",
            "bundle": {"register": "testimony", "subject_type": "beyond-horizon",
                       "cited_refs": {"operations": [], "resources": [], "demands": []}},
        },
        "what's frozen?": {
            "question": "what's frozen?",
            "answer": (f"{doc['rolling']['committed_count']} operation(s) are frozen "
                       f"and committed — locked in the frozen zone through "
                       f"{doc['rolling']['frozen_until'][:10]}.\n\nregister: testimony"),
            "bundle": {"register": "testimony", "subject_type": "frozen",
                       "cited_refs": {"operations": [], "resources": [], "demands": []}},
        },
    }
    # CU4(c): a canned "why is {order} on {machine}?" for the gesture op, so the
    # cockpit's ask-why bridge from the beat-two card lands a real grounded answer
    # (the Python tests prove the deterministic answer against a real solve).
    if gesture:
        op = gesture["gesture"]["op"]
        a = next((x for x in doc["assignments"] if x["operation_ref"] == op), None)
        if a and a.get("work_orders") and a.get("external_name"):
            wo, mach = a["work_orders"][0], a["external_name"]
            q = f"why is {wo} on {mach}?"
            asks[q] = {
                "question": q,
                "answer": (f"{wo} is on {mach} because the machine was the "
                           f"lowest-cost eligible placement for it in this window."
                           f"\n\nregister: testimony"),
                "bundle": {"register": "testimony", "subject_type": "operation",
                           "cited_refs": {"operations": [op], "resources": [a["resource_id"]],
                                          "demands": []}},
            }
    return asks


def build(orders: int, window_days: int, frozen_days: int, sid: str,
          capture_gesture: bool = False):
    """Build a rolling document. When ``capture_gesture`` is set (4B.3c), PERSIST
    the window-0 solve as a first-class run and run the REAL two-beat against it,
    capturing byte-faithful interaction / feasibility / sandbox / contradiction
    fixtures the Playwright harness serves — so the browser test exercises a real
    sliced-board two-beat with no solver in the browser."""
    import tempfile
    from generate_erp_dataset import generate
    tmp = Path(tempfile.mkdtemp(prefix="rollfix"))
    generate(tmp / "sub", scenario="pilot_scale", orders=orders, seed=1)
    plant = prepare_plant(tmp / "sub", tmp / "prep", reference_date=REF)
    view = build_rolling_view(plant, window_days=window_days, frozen_days=frozen_days,
                              gravity=True, deterministic=True, seed=42,
                              member_time_limit_s=10.0, det_time=2.0,
                              persist=capture_gesture)
    idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
    doc = assemble_rolling_document(plant=plant, view=view, schedule_id=sid,
                                    run_id="run-fixture", identity_map=idmap)
    docd = doc.model_dump(mode="json")
    gesture = _capture_gesture(plant, docd) if capture_gesture else None
    return docd, view, gesture


def _capture_gesture(plant, docd) -> dict:
    """Run the real two-beat against the persisted rolling run and return the
    canned {interaction, feasibility, sandbox, contradiction, gesture} the fixture
    server serves. Picks an active cross-machine op (the normal gesture) and, if
    findable, an active op that overlaps a committed slot (the forced infeasible
    contradiction)."""
    from mre.modules.sandbox import feasibility_ghost, sandbox_pin_resolve

    out_dir, snap = plant.out_dir, plant.snapshot_id
    window_op_ids = {a["operation_ref"] for a in docd["assignments"]}
    committed_pins = [
        {"operation_ref": a["operation_ref"], "resource_id": a["resource_id"],
         "start": a["chunks"][0]["start"]}
        for a in docd["assignments"]
        if a.get("commitment_state") == "committed" and a["chunks"]]
    iops = {o["operation_ref"]: o for o in (docd.get("interaction") or {}).get("operations", [])}

    # normal gesture: an active op eligible on ≥2 machines
    tgt = None
    for a in docd["assignments"]:
        if a.get("commitment_state") != "active_window":
            continue
        io = iops.get(a["operation_ref"])
        if io and len(io["eligible_resource_ids"]) > 1:
            alt = [r for r in io["eligible_resource_ids"] if r != a["resource_id"]]
            if alt:
                tgt = (a["operation_ref"], alt[0], a["chunks"][0]["start"])
                break
    if tgt is None:
        raise RuntimeError("no cross-machine active op for the gesture fixture")
    op, alt, start = tgt
    g = feasibility_ghost(out_dir, snap, pin_op_id=op, pin_resource_id=alt,
                          pin_start_iso=start, restrict_op_ids=window_op_ids)
    r = sandbox_pin_resolve(out_dir, snap, pin_op_id=op, pin_resource_id=alt,
                            pin_start_iso=start, standing_pins=committed_pins,
                            restrict_op_ids=window_op_ids)

    # forced contradiction: a DIFFERENT active op dropped onto a committed slot
    # (must not be the normal-gesture op, or the two canned results collide).
    contra = None
    for comm in committed_pins:
        for a in docd["assignments"]:
            if a.get("commitment_state") != "active_window":
                continue
            io = iops.get(a["operation_ref"])
            if (io and comm["resource_id"] in io["eligible_resource_ids"]
                    and a["operation_ref"] != comm["operation_ref"]
                    and a["operation_ref"] != op):
                cg = feasibility_ghost(out_dir, snap, pin_op_id=a["operation_ref"],
                                       pin_resource_id=comm["resource_id"],
                                       pin_start_iso=comm["start"],
                                       restrict_op_ids=window_op_ids)
                cr = sandbox_pin_resolve(out_dir, snap, pin_op_id=a["operation_ref"],
                                         pin_resource_id=comm["resource_id"],
                                         pin_start_iso=comm["start"],
                                         standing_pins=committed_pins,
                                         restrict_op_ids=window_op_ids)
                if cg.feasible and not cr.feasible:
                    contra = {"op": a["operation_ref"],
                              "resource": comm["resource_id"], "start": comm["start"],
                              "ghost": cg.summary(), "sandbox": cr.summary()}
                    break
        if contra:
            break

    return {
        "interaction": docd.get("interaction"),
        "feasibility": {"by_op": {op: g.summary()},
                        **({"contra_op": contra["op"]} if contra else {})},
        "sandbox": {"by_op": {op: r.summary()}, "default": r.summary()},
        "contradiction": contra,
        "gesture": {"op": op, "resource": alt, "start": start,
                    "contra": ({"op": contra["op"], "resource": contra["resource"],
                                "start": contra["start"]} if contra else None)},
    }


def write_set(subdir: str, doc: dict, sid: str, gesture: dict | None = None):
    d = OUT / subdir
    d.mkdir(parents=True, exist_ok=True)
    # The main document never carries the interaction payload inline (contract 1.3
    # split-endpoint delivery) — it lives in the sibling interaction.json, served
    # by GET /interaction. Mirror _persist_document so the fixture matches prod.
    doc = copy.deepcopy(doc)
    doc["interaction"] = None
    (d / "schedule.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    (d / "meta.json").write_text(json.dumps(_meta(sid), indent=2), encoding="utf-8")
    (d / "asks.json").write_text(json.dumps(_asks(doc, gesture), indent=2), encoding="utf-8")
    if gesture is not None:
        # the split-endpoint interaction payload (served by GET /interaction)
        (d / "interaction.json").write_text(json.dumps(
            {"schedule_id": sid, "contract_version": doc["contract_version"],
             "interaction": gesture["interaction"]}, indent=2), encoding="utf-8")
        # canned two-beat responses + a forced contradiction, keyed by op
        feas = dict(gesture["feasibility"])
        sb = dict(gesture["sandbox"])
        if gesture.get("contradiction"):
            c = gesture["contradiction"]
            # mark the contradiction op so the fixture server serves an infeasible
            # beat two + a feasible (relaxed) beat one for it.
            feas.setdefault("by_op", {})[c["op"]] = c["ghost"]
            sb.setdefault("by_op", {})[c["op"]] = c["sandbox"]
        (d / "feasibility.json").write_text(json.dumps(feas, indent=2), encoding="utf-8")
        (d / "sandbox.json").write_text(json.dumps(sb, indent=2), encoding="utf-8")
        (d / "gesture.json").write_text(json.dumps(gesture["gesture"], indent=2), encoding="utf-8")
    print(f"  {subdir}: {len(doc['assignments'])} bars, "
          f"{len(doc['rolling']['beyond_horizon'])} in tray "
          f"({doc['rolling']['committed_count']} committed, "
          f"{doc['rolling']['active_count']} active)"
          + (f" · gesture op {gesture['gesture']['op'][:8]}"
             + (" +contradiction" if gesture.get('contradiction') else " (no contradiction)")
             if gesture else ""))


def main():
    print("building rolling fixture (populated tray, MIXED committed/active, gesturable)…")
    # window 14 / frozen 3 on the 40-order plant yields a rich sliced world — a
    # frozen front, a wide active window with cross-machine ops, and a full tray.
    doc, _, gesture = build(orders=40, window_days=14, frozen_days=3,
                            sid="sched-rolling-fixture", capture_gesture=True)
    write_set("rolling", doc, "sched-rolling-fixture", gesture)

    print("building rolling_empty fixture (empty tray)…")
    # A window long enough to admit the whole (small) book → nothing beyond it.
    # If the solve still leaves work beyond, blank the tray deterministically for
    # the empty-state screenshot (the render path is what the test asserts).
    doc2, _, _ = build(orders=8, window_days=60, frozen_days=3, sid="sched-rolling-empty")
    if doc2["rolling"]["beyond_horizon"]:
        doc2 = copy.deepcopy(doc2)
        doc2["rolling"]["beyond_horizon"] = []
    write_set("rolling_empty", doc2, "sched-rolling-empty")
    print("done.")


if __name__ == "__main__":
    main()

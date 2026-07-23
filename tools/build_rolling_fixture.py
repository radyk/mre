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
        "contract_version": "1.7", "grade": "ACCEPTED", "costing_grade": "C2",
        "created_at": "2026-01-05T09:41:00Z", "generation": 1,
    }


def _asks(doc: dict) -> dict:
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
    return {
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


def build(orders: int, window_days: int, frozen_days: int, sid: str):
    import tempfile
    from generate_erp_dataset import generate
    tmp = Path(tempfile.mkdtemp(prefix="rollfix"))
    generate(tmp / "sub", scenario="pilot_scale", orders=orders, seed=1)
    plant = prepare_plant(tmp / "sub", tmp / "prep", reference_date=REF)
    view = build_rolling_view(plant, window_days=window_days, frozen_days=frozen_days,
                              gravity=True, deterministic=True, seed=42,
                              member_time_limit_s=10.0, det_time=2.0)
    idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
    doc = assemble_rolling_document(plant=plant, view=view, schedule_id=sid,
                                    run_id="run-fixture", identity_map=idmap)
    return doc.model_dump(mode="json"), view


def write_set(subdir: str, doc: dict, sid: str):
    d = OUT / subdir
    d.mkdir(parents=True, exist_ok=True)
    (d / "schedule.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    (d / "meta.json").write_text(json.dumps(_meta(sid), indent=2), encoding="utf-8")
    (d / "asks.json").write_text(json.dumps(_asks(doc), indent=2), encoding="utf-8")
    print(f"  {subdir}: {len(doc['assignments'])} bars, "
          f"{len(doc['rolling']['beyond_horizon'])} in tray "
          f"({doc['rolling']['committed_count']} committed, "
          f"{doc['rolling']['active_count']} active)")


def main():
    print("building rolling fixture (populated tray, MIXED committed/active)…")
    # window 10 / frozen 1 on the 40-order plant yields a genuine mix — a frozen
    # front AND active-window work spilling past the boundary AND a populated tray.
    doc, _ = build(orders=40, window_days=10, frozen_days=1, sid="sched-rolling-fixture")
    write_set("rolling", doc, "sched-rolling-fixture")

    print("building rolling_empty fixture (empty tray)…")
    # A window long enough to admit the whole (small) book → nothing beyond it.
    # If the solve still leaves work beyond, blank the tray deterministically for
    # the empty-state screenshot (the render path is what the test asserts).
    doc2, _ = build(orders=8, window_days=60, frozen_days=3, sid="sched-rolling-empty")
    if doc2["rolling"]["beyond_horizon"]:
        doc2 = copy.deepcopy(doc2)
        doc2["rolling"]["beyond_horizon"] = []
    write_set("rolling_empty", doc2, "sched-rolling-empty")
    print("done.")


if __name__ == "__main__":
    main()

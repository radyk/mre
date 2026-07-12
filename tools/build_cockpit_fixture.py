#!/usr/bin/env python
"""Capture the deterministic cockpit test fixture (docs/07 Phase 3, CU5).

Regenerates the `multi_route` submission (docs/05 B2, CU1), runs the pipeline
deterministically, and writes what the Playwright screenshot harness serves as
a stand-in for the live API — so CI renders the exact cockpit board WITHOUT
running the solver in the browser test:

  tests/cockpit/fixtures/schedule.json   the contract-1.2 document (GET /schedules/{id})
  tests/cockpit/fixtures/meta.json       registry meta incl. certificate grade (GET .../meta)
  tests/cockpit/fixtures/asks.json       canned /ask responses (question -> envelope data),
                                         including the acceptance question with cited_refs

The live acceptance moment (the exit bar) runs the SAME cockpit against the real
FastAPI — this fixture only makes the screenshot regression hermetic.

Run:  PYTHONHASHSEED=0 python tools/build_cockpit_fixture.py
Determinism: --solver-workers 1 --solver-seed 42, generator seed 7 (the
`multi_route` module fixture's settings).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from mre.__main__ import main as mre_main  # noqa: E402
from mre.api.app import _answer_question  # noqa: E402
from mre.modules.conformance import ConformanceGate  # noqa: E402
from mre.modules.schedule_assembler import build_document_from_run  # noqa: E402
from mre.reporter import Reporter  # noqa: E402
from mre.contracts.vocabularies import ModuleCode, RunStatus  # noqa: E402
from tools.generate_erp_dataset import generate  # noqa: E402

SNAP = "snap-mr"
SCHEDULE_ID = "sched-multi-route-fixture"

# The acceptance question (the exit bar) + a judgment-register question so the
# harness can assert the two registers render visibly distinct (honesty armor).
ACCEPTANCE_Q = "why is ORD-000012 on F001-RES001?"
QUESTIONS = [ACCEPTANCE_Q, "what data problems exist?"]

FIXDIR = ROOT / "tests" / "cockpit" / "fixtures"


def main() -> int:
    FIXDIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        sub, out = tmp / "sub", tmp / "out"
        generate(sub, scenario="multi_route", seed=7)

        rc = mre_main([
            "--submission", str(sub), "--out", str(out), "--snapshot-id", SNAP,
            "--time-limit", "45", "--solver-workers", "1", "--solver-seed", "42",
        ])
        if rc != 0:
            print(f"pipeline failed rc={rc}", file=sys.stderr)
            return 1

        # contract-1.3 document, split-endpoint discipline (R-T1d): the main
        # render document (interaction stripped → lean) and a sibling
        # interaction.json the /interaction endpoint serves.
        doc = build_document_from_run(out, SNAP, "run-mr-fixture")
        interaction = doc.interaction
        d = doc.model_copy(update={"interaction": None}).model_dump(mode="json")
        d["schedule_id"] = SCHEDULE_ID
        (FIXDIR / "schedule.json").write_text(json.dumps(d, indent=2), encoding="utf-8")
        (FIXDIR / "interaction.json").write_text(json.dumps({
            "schedule_id": SCHEDULE_ID,
            "contract_version": d["contract_version"],
            "interaction": interaction.model_dump(mode="json") if interaction else None,
        }, indent=2), encoding="utf-8")

        # certificate grade (the top strip) — run the gate on the submission
        reporter = Reporter.begin(
            module=ModuleCode.M0, purpose="fixture cert",
            config={}, trigger="fixture", snapshot_id="pre-adapter",
            sink_dir=out / "gate_runs",
        )
        gate = ConformanceGate().run(sub, reporter)
        reporter.end(RunStatus.SUCCESS if gate.go else RunStatus.PARTIAL)
        meta = {
            "id": SCHEDULE_ID, "run_id": "run-mr-fixture", "submission_id": "sub-mr",
            "snapshot_id": SNAP, "status": d["status"],
            "contract_version": d["contract_version"], "is_scenario": 0,
            "parent_schedule_id": None,
            "grade": gate.grade, "costing_grade": gate.costing_grade,
        }
        (FIXDIR / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # canned /ask responses (the envelope `data` payload)
        asks = {}
        for q in QUESTIONS:
            answer, bundle = _answer_question(out, SNAP, q, use_llm=False)
            asks[q] = {"question": q, "answer": answer, "bundle": bundle}
        (FIXDIR / "asks.json").write_text(json.dumps(asks, indent=2), encoding="utf-8")

    acc = asks[ACCEPTANCE_Q]["bundle"]["cited_refs"]
    print(f"wrote fixtures to {FIXDIR}")
    print(f"  schedule: {len(d['assignments'])} assignments / {len(d['resources'])} resources / grade {meta['grade']}")
    print(f"  acceptance cited_refs: {len(acc['operations'])} ops, {len(acc['resources'])} resources")
    prices = [ln for ln in asks[ACCEPTANCE_Q]["answer"].splitlines() if "cost" in ln.lower()]
    print("  answer prices alternatives:", bool(prices))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

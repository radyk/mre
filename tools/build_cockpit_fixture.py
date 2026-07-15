#!/usr/bin/env python
"""Capture the deterministic cockpit test fixtures (docs/07 Phase 3, CU5 + 3.2b).

Regenerates two hermetic fixture sets the Playwright harness serves as a
stand-in for the live API, so CI renders the real cockpit board WITHOUT running
the solver in the browser test:

  tests/cockpit/fixtures/            the READ-ONLY (interim-A) fixture on the
                                     SATURATED `multi_route` scenario — its pool
                                     surfaces the priced cross-machine answer the
                                     acceptance moment asserts (cockpit.spec.mjs).

  tests/cockpit/fixtures/distinct/   the GESTURE (3.2b) fixture on the realistic
                                     `multi_route_distinct` scenario — distinct
                                     rates, so the priced GHOSTS are the
                                     forced-alternative service's (R-T1), plus
                                     canned SANDBOX verdicts for the drop flow
                                     (gesture.spec.mjs).

Each set: schedule.json (contract-1.3 main doc), interaction.json (the split
Tier-0 payload), meta.json (registry meta incl. certificate grade), asks.json
(canned /ask). The distinct set additionally writes alternatives.json (the
/alternatives ghost payload) and sandbox.json (canned POST /sandbox responses
keyed by pinned op).

The live acceptance moment (the exit bar) runs the SAME cockpit against the real
FastAPI — these fixtures only make the screenshot regressions hermetic.

Run:  PYTHONHASHSEED=0 python tools/build_cockpit_fixture.py
Determinism: --solver-workers 1 --solver-seed 42, generator seed 7.
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
from mre.modules.forced_alternatives import (  # noqa: E402
    build_forced_alternatives, build_op_alternatives,
)
from mre.modules.sandbox import SANDBOX_BUDGET_S, sandbox_pin_resolve  # noqa: E402
from mre.modules.schedule_assembler import build_document_from_run  # noqa: E402
from mre.reporter import Reporter  # noqa: E402
from mre.contracts.vocabularies import ModuleCode, RunStatus  # noqa: E402
from tools.generate_erp_dataset import generate  # noqa: E402

FIXDIR = ROOT / "tests" / "cockpit" / "fixtures"

# --- the read-only (interim-A) fixture -------------------------------------
MR_SNAP = "snap-mr"
MR_SCHEDULE_ID = "sched-multi-route-fixture"
MR_ACCEPTANCE_Q = "why is ORD-000012 on F001-RES001?"
MR_QUESTIONS = [MR_ACCEPTANCE_Q, "what data problems exist?"]

# --- the gesture (3.2b) fixture --------------------------------------------
MRD_SNAP = "snap-mrd"
MRD_SCHEDULE_ID = "sched-multi-route-distinct"


def _run_pipeline(sub: Path, out: Path, snap: str, time_limit: str = "45") -> None:
    rc = mre_main([
        "--submission", str(sub), "--out", str(out), "--snapshot-id", snap,
        "--time-limit", time_limit, "--solver-workers", "1", "--solver-seed", "42",
    ])
    if rc != 0:
        raise SystemExit(f"pipeline failed rc={rc}")


def _write_core(fixdir: Path, out: Path, snap: str, run_id: str,
                schedule_id: str) -> dict:
    """schedule.json + interaction.json (split-endpoint discipline, R-T1d) +
    meta.json (with the certificate grade). Returns the main-doc dict."""
    fixdir.mkdir(parents=True, exist_ok=True)
    doc = build_document_from_run(out, snap, run_id)
    interaction = doc.interaction
    d = doc.model_copy(update={"interaction": None}).model_dump(mode="json")
    d["schedule_id"] = schedule_id
    (fixdir / "schedule.json").write_text(json.dumps(d, indent=2), encoding="utf-8")
    (fixdir / "interaction.json").write_text(json.dumps({
        "schedule_id": schedule_id,
        "contract_version": d["contract_version"],
        "interaction": interaction.model_dump(mode="json") if interaction else None,
    }, indent=2), encoding="utf-8")
    return d


def _write_meta(fixdir: Path, sub: Path, out: Path, schedule_id: str,
                run_id: str, snap: str, d: dict) -> dict:
    reporter = Reporter.begin(
        module=ModuleCode.M0, purpose="fixture cert", config={},
        trigger="fixture", snapshot_id="pre-adapter", sink_dir=out / "gate_runs",
    )
    gate = ConformanceGate().run(sub, reporter)
    reporter.end(RunStatus.SUCCESS if gate.go else RunStatus.PARTIAL)
    meta = {
        "id": schedule_id, "run_id": run_id, "submission_id": schedule_id,
        "snapshot_id": snap, "status": d["status"],
        "contract_version": d["contract_version"], "is_scenario": 0,
        "parent_schedule_id": None,
        "grade": gate.grade, "costing_grade": gate.costing_grade,
    }
    (fixdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def _write_asks(fixdir: Path, out: Path, snap: str, questions: list[str]) -> dict:
    asks = {}
    for q in questions:
        try:
            answer, bundle = _answer_question(out, snap, q, use_llm=False)
            asks[q] = {"question": q, "answer": answer, "bundle": bundle}
        except Exception as exc:  # noqa: BLE001 — best-effort canned answers
            print(f"  (ask skipped: {q!r} → {type(exc).__name__}: {exc})")
    (fixdir / "asks.json").write_text(json.dumps(asks, indent=2), encoding="utf-8")
    return asks


# ---------------------------------------------------------------------------
# The read-only fixture (multi_route) — UNCHANGED behavior (keeps the 6
# interim-A regressions byte-stable modulo solver determinism).
# ---------------------------------------------------------------------------

def build_multi_route() -> dict:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        sub, out = tmp / "sub", tmp / "out"
        generate(sub, scenario="multi_route", seed=7)
        _run_pipeline(sub, out, MR_SNAP)
        d = _write_core(FIXDIR, out, MR_SNAP, "run-mr-fixture", MR_SCHEDULE_ID)
        meta = _write_meta(FIXDIR, sub, out, MR_SCHEDULE_ID, "run-mr-fixture",
                           MR_SNAP, d)
        asks = _write_asks(FIXDIR, out, MR_SNAP, MR_QUESTIONS)
    acc = asks[MR_ACCEPTANCE_Q]["bundle"]["cited_refs"]
    print(f"multi_route: {len(d['assignments'])} assignments / "
          f"{len(d['resources'])} resources / grade {meta['grade']}")
    print(f"  acceptance cited_refs: {len(acc['operations'])} ops, "
          f"{len(acc['resources'])} resources")
    return d


# ---------------------------------------------------------------------------
# The gesture fixture (multi_route_distinct) — ghosts + canned sandbox verdicts.
# ---------------------------------------------------------------------------

def _member_row(m, *, pool_id: str, on_demand: bool = False) -> dict:
    """One /alternatives member row (mirrors Registry.get_pool_for_schedule)."""
    return {
        "pool_id": pool_id, "member_index": m.member_index,
        "objective": m.objective, "objective_delta_pct": m.objective_delta_pct,
        "hamming_from_incumbent": None, "document_path": None,
        "source": "forced_alternative", "verdict": m.verdict,
        "label": {
            "target_operation_ref": m.target_operation_ref,
            "forbidden_resource_ref": m.forbidden_resource_ref,
            "alternative_resource_ref": m.alternative_resource_ref,
            "status": m.status, "on_demand": on_demand,
            "placement": m.alternative_placement,   # now carries work_orders (CU2)
        },
    }


def _copy_member_docs(result, fixdir: Path) -> None:
    """Copy each priced member's full solved document into the fixture dir as
    member_<index>.json — what GET /alternatives/<index> serves, so a
    drop-onto-ghost can lazy-fetch it and trace the FULL moved-set (CU4)."""
    for m in result.members:
        if m.document_path and Path(m.document_path).exists():
            (fixdir / f"member_{m.member_index}.json").write_text(
                Path(m.document_path).read_text(encoding="utf-8"), encoding="utf-8")


def _alternatives_payload(pool_id: str, schedule_id: str, snap: str,
                          result) -> dict:
    """The /alternatives envelope-`data` shape: a pool row of kind
    'alternatives' with its member rows, each carrying the compact ghost
    placement (with planner work_orders, CU2) in its label."""
    return {
        "id": pool_id, "schedule_id": schedule_id, "kind": "alternatives",
        "status": result.status, "created_at": None, "finished_at": None,
        "error": None, "params": result.params, "summary": {},
        "members": [_member_row(m, pool_id=pool_id) for m in result.members],
    }


def _ondemand_payload(out: Path, fixdir: Path, covered: set[str],
                      pool_id: str) -> dict:
    """Build the ON-DEMAND fixture (session 3.3 CU1): pick a multi-eligible op
    the precomputed batch MISSED, price its every eligible machine on demand,
    and record the resulting ghost members keyed by op. The fixture server
    replays this when the harness POSTs /alternatives/op/<op> — proving a grab
    of an uncovered op surfaces priced ghosts where none existed. Member indices
    are offset (100+) so they never collide with the precomputed batch."""
    interaction = json.loads(
        (fixdir / "interaction.json").read_text(encoding="utf-8"))["interaction"]
    multi = [o["operation_ref"] for o in (interaction or {}).get("operations", [])
             if len(o.get("eligible_resource_ids", [])) > 1]
    uncovered = next((op for op in multi if op not in covered), None)
    if uncovered is None:
        print("  (on-demand: no uncovered multi-eligible op — skipping)")
        return {}
    od = build_op_alternatives(
        out_dir=out, snapshot_id=MRD_SNAP, base_schedule_id=MRD_SCHEDULE_ID,
        run_id="run-mrd-fixture", op_id=uncovered, max_machines=4,
        member_time_limit_s=8.0, pool_id="alt-ondemand",
    )
    members = []
    for m in od.members:
        m.member_index = 100 + m.member_index      # offset off the batch
        if m.document_path and Path(m.document_path).exists():
            (fixdir / f"member_{m.member_index}.json").write_text(
                Path(m.document_path).read_text(encoding="utf-8"), encoding="utf-8")
        members.append(_member_row(m, pool_id="alt-ondemand", on_demand=True))
    priced = [m for m in members if m["verdict"] == "priced"]
    print(f"  on-demand: op {uncovered[:8]} -> {len(priced)} priced / "
          f"{len(members)} total machines")
    return {"op_id": uncovered, "members": members}


def _sandbox_canned(out: Path, snap: str, priced, doc: dict) -> dict:
    """Canned POST /sandbox responses keyed by pinned op (R-T1c). One REAL
    verdict (pin the first priced ghost's op at its alternative placement — a
    known-feasible move, so a real delta + moved-set), plus a synthetic FLAGGED
    (feasible-unproven) and a synthetic NO_VERDICT (return-home) derived from it
    — the two other honest outcomes the classifier is unit-tested for. The
    harness reads this file to know which op triggers which outcome."""
    tgt0 = priced[0].target_operation_ref
    p0 = priced[0].alternative_placement
    verdict = sandbox_pin_resolve(
        out_dir=out, snapshot_id=snap, pin_op_id=tgt0,
        pin_resource_id=p0["resource_id"], pin_start_iso=p0["start"],
        budget_s=SANDBOX_BUDGET_S, deterministic=True,
    ).summary()

    # The tiny distinct fixture is too light for a pin to displace a neighbour,
    # so this verdict's moved-set is just the pinned op — no "why" clause to
    # render. Synthesize ONE reasoned consequence line (an occupancy block) so
    # the CU3 renderer has something to draw; the reason DERIVATION itself is
    # unit-tested in Python (test_sandbox._annotate_move_reasons). Uses a real
    # neighbour op + real resource so nameOf/woOf resolve.
    neighbour = next((a for a in doc.get("assignments", [])
                      if a.get("operation_ref") != tgt0 and a.get("chunks")), None)
    if neighbour:
        verdict = dict(verdict)
        verdict["moves"] = list(verdict["moves"]) + [{
            "operation_ref": neighbour["operation_ref"],
            "from_resource": neighbour["resource_id"],
            "to_resource": neighbour["resource_id"],
            "from_start": neighbour["chunks"][0]["start"],
            "to_start": neighbour["chunks"][0]["start"],
            "start_delta_min": 240, "resource_changed": False, "pinned": False,
            "reason": {"kind": "occupancy",
                       "on_resource": neighbour["resource_id"],
                       "blocker_op": tgt0, "until": p0["start"]},
        }]

    by_op = {tgt0: verdict}
    # a FLAGGED card: feasible, bound unproven (SOLVER_NONOPTIMAL in the UI).
    if len(priced) > 1:
        flagged = dict(verdict)
        flagged.update(outcome="feasible_unproven", status="FEASIBLE",
                       within_budget=True, feasible=True,
                       message="≈ delta, bound not proven")
        flagged["pin"] = {"operation_ref": priced[1].target_operation_ref,
                          "resource_id": priced[1].alternative_placement["resource_id"],
                          "start": priced[1].alternative_placement["start"]}
        by_op[priced[1].target_operation_ref] = flagged
    # a NO_VERDICT card: nothing provable → return home (R-DP2).
    if len(priced) > 2:
        no_v = dict(verdict)
        no_v.update(outcome="no_verdict", status="UNKNOWN", within_budget=True,
                    feasible=False, objective=None, delta_pct=None,
                    delta_abs=None, moves=[],
                    message="couldn't verify this placement in time")
        no_v["pin"] = {"operation_ref": priced[2].target_operation_ref,
                       "resource_id": priced[2].alternative_placement["resource_id"],
                       "start": priced[2].alternative_placement["start"]}
        by_op[priced[2].target_operation_ref] = no_v

    return {"default": verdict, "budget_s": SANDBOX_BUDGET_S, "by_op": by_op}


def build_distinct() -> dict:
    fixdir = FIXDIR / "distinct"
    # NOTE: not a TemporaryDirectory — the forced-alternative + sandbox re-solves
    # read the run dir after the pipeline, and we build everything in one scope.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        sub, out = tmp / "sub", tmp / "out"
        generate(sub, scenario="multi_route_distinct", seed=7)
        _run_pipeline(sub, out, MRD_SNAP)
        d = _write_core(fixdir, out, MRD_SNAP, "run-mrd-fixture", MRD_SCHEDULE_ID)
        meta = _write_meta(fixdir, sub, out, MRD_SCHEDULE_ID, "run-mrd-fixture",
                           MRD_SNAP, d)
        # The sixty-second rehearsal's opening ask beat (CU5): a real
        # "why is <order> on <machine>?" answered by the explainer against the
        # solved run, so its cited_refs glow real bars. (The closing "summarize
        # my changes" beat is synthesized by the fixture server for the accepted
        # -edit version, which the base run has no evidence for.)
        a0 = d["assignments"][0]
        demo_wo = (a0.get("work_orders") or ["?"])[0]
        demo_machine = a0.get("external_name") or a0["resource_id"][:8]
        _write_asks(fixdir, out, MRD_SNAP,
                    [f"why is {demo_wo} on {demo_machine}?"])

        # ghosts: the forced-alternative service (the priced roads not taken on
        # distinct rates — R-T1's whole point).
        pool_id = "alt-fixture"
        result = build_forced_alternatives(
            out_dir=out, snapshot_id=MRD_SNAP, base_schedule_id=MRD_SCHEDULE_ID,
            run_id="run-mrd-fixture", budget=4, member_time_limit_s=8.0,
            pool_id=pool_id,
        )
        payload = _alternatives_payload(pool_id, MRD_SCHEDULE_ID, MRD_SNAP, result)
        (fixdir / "alternatives.json").write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8")
        # member documents for the full-consequences lazy fetch (CU4)
        _copy_member_docs(result, fixdir)

        priced = result.priced_cross_machine()
        if not priced:
            raise SystemExit("distinct fixture: no priced cross-machine ghost — "
                             "the gesture fixture needs at least one")

        # on-demand coverage fixture (CU1): an uncovered op priced on grab.
        covered = {m.target_operation_ref for m in result.members}
        ondemand = _ondemand_payload(out, fixdir, covered, pool_id)
        (fixdir / "ondemand.json").write_text(
            json.dumps(ondemand, indent=2, default=str), encoding="utf-8")

        sandbox = _sandbox_canned(out, MRD_SNAP, priced, d)
        (fixdir / "sandbox.json").write_text(
            json.dumps(sandbox, indent=2, default=str), encoding="utf-8")

    n_priced = len(priced)
    n_infeasible = sum(1 for m in result.members
                       if m.verdict == "infeasible_this_horizon")
    print(f"multi_route_distinct: {len(d['assignments'])} assignments / "
          f"{len(d['resources'])} resources / grade {meta['grade']}")
    print(f"  ghosts: {n_priced} priced cross-machine, {n_infeasible} infeasible")
    print(f"  sandbox canned outcomes: {[v['outcome'] for v in sandbox['by_op'].values()]}")
    return d


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "multi_route"):
        build_multi_route()
    if which in ("all", "distinct"):
        build_distinct()
    print(f"wrote fixtures under {FIXDIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

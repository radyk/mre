"""Session 4B.3c — the two-beat sandbox + Explainer on a REAL rolling run.

CU1 persists the window-0 solve as a first-class run (assignments / service
outcomes / schedule / M5-M6-M7 evidence into the plant's canonical snapshot). On
that substrate:

  * CU3 — the R-T2 two-beat runs against the rolling schedule: beat one is a
    first-feasible ghost restricted to the ACTIVE WINDOW (the frozen front
    relaxed); beat two prices the window holding the frozen front via standing
    pins. Every 4B.3b invariant is re-proven on the rolling substrate
    (no-money-by-construction, correlation, decomposition-sums-exactly,
    no-committed-work-changes — now LOAD-BEARING) and the forced infeasible
    contradiction is demonstrated by gesturing an active op at a COMMITTED slot.
  * CU4 — the Explainer reads the persisted rolling run: the sliced-world routes
    answer from the document, and "why is {order} on {machine}" (an "ask why"
    from a beat-two card) is a real grounded answer.

All of these require a real solve + persist, so the substantive tests are slow.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from mre.modules.rolling_horizon import prepare_plant, build_rolling_view
from mre.modules.schedule_assembler import assemble_rolling_document
from mre.modules.sandbox import (
    _MONEY_FIELD_TOKENS, beat_two_contradicts, feasibility_ghost,
    sandbox_pin_resolve,
)

REF = datetime(2026, 1, 5, tzinfo=timezone.utc)
# A window wide enough to hold a rich sliced world: committed frozen front AND an
# active window AND a populated beyond-horizon tray (probed on the 40-order plant).
WINDOW_DAYS, FROZEN_DAYS = 14, 3


# ---------------------------------------------------------------------------
# a persisted rolling run — the sliced world, on disk, exactly as the API mints it
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rolling(tmp_path_factory):
    from generate_erp_dataset import generate
    from mre.api.app import _persist_document

    d = tmp_path_factory.mktemp("roll2beat")
    generate(d / "sub", scenario="pilot_scale", orders=40, seed=1)
    plant = prepare_plant(d / "sub", d / "prep", reference_date=REF)
    view = build_rolling_view(
        plant, window_days=WINDOW_DAYS, frozen_days=FROZEN_DAYS, gravity=True,
        deterministic=True, seed=42, member_time_limit_s=10.0, det_time=1.0,
        persist=True)
    idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
    doc = assemble_rolling_document(
        plant=plant, view=view, schedule_id="s-roll", run_id="run-roll",
        identity_map=idmap)
    _persist_document(doc, plant.out_dir)          # schedule_document.json + interaction.json
    docd = json.loads((plant.out_dir / "schedule_document.json").read_text("utf-8"))
    # The main document strips the interaction payload (split-endpoint delivery,
    # contract 1.3); a client re-attaches it from the sibling interaction.json —
    # so do we, to mirror what the cockpit actually reads.
    inter = json.loads((plant.out_dir / "interaction.json").read_text("utf-8"))
    docd["interaction"] = inter["interaction"]
    window_op_ids = {a["operation_ref"] for a in docd["assignments"]}
    committed_pins = [
        {"operation_ref": a["operation_ref"], "resource_id": a["resource_id"],
         "start": a["chunks"][0]["start"]}
        for a in docd["assignments"]
        if a.get("commitment_state") == "committed" and a["chunks"]]
    return {"plant": plant, "view": view, "doc": docd,
            "out_dir": plant.out_dir, "snapshot_id": plant.snapshot_id,
            "window_op_ids": window_op_ids, "committed_pins": committed_pins}


def _interaction_ops(docd):
    return {o["operation_ref"]: o for o in (docd.get("interaction") or {}).get("operations", [])}


def _pick_cross_machine_active(docd):
    """An ACTIVE-window op eligible on ≥2 machines → drag it to an alternative."""
    iops = _interaction_ops(docd)
    for a in docd["assignments"]:
        if a.get("commitment_state") != "active_window":
            continue
        io = iops.get(a["operation_ref"])
        if io and len(io["eligible_resource_ids"]) > 1:
            alt = [r for r in io["eligible_resource_ids"] if r != a["resource_id"]]
            if alt:
                return a["operation_ref"], alt[0], a["chunks"][0]["start"]
    return None


# ---------------------------------------------------------------------------
# CU1 — the persisted window-0 snapshot is a first-class, sandbox-readable run
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_window0_persists_a_readable_run(rolling):
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solution_pool import (
        _incumbent_objective, _m5_horizon, _placements, _read_evidence,
    )
    reader = SnapshotStore(rolling["out_dir"] / "snapshots").load_snapshot(
        rolling["snapshot_id"])
    asg = list(reader.iter_entities("assignment"))
    svc = list(reader.iter_entities("serviceoutcome"))
    sched = list(reader.iter_entities("schedule"))
    assert asg, "no persisted assignments — window-0 was not written as a run"
    assert svc and sched, "no persisted service outcomes / schedule"
    # the schedule carries a decomposing summary the priced card diffs against
    sm = sched[-1].get("summary_metrics") or {}
    assert sm.get("total_cost") is not None
    # placements == the window op set (committed ∪ active); nothing beyond leaks in
    placed = set(rolling["view"].committed) | set(rolling["view"].active)
    assert set(_placements(asg)) == placed
    # evidence carries the M5 horizon + M6 objective the sandbox reads
    ev = _read_evidence(rolling["out_dir"] / "runs")
    hs, he = _m5_horizon(ev)
    assert hs == rolling["view"].win_horizon_start
    assert _incumbent_objective(ev) is not None
    # assignment Decisions are in evidence (reconstructed) so "why-on-machine" works
    assert sum(1 for r in ev if r.get("record_type") == "decision") > 0


@pytest.mark.slow
def test_completeness_invariant_holds_on_the_PERSISTED_document(rolling):
    """The 4B.3a completeness invariant, counted against the on-disk artifact (not
    just the in-memory view): every schedulable demand appears exactly once —
    placed bar or beyond-horizon tray entry."""
    docd = rolling["doc"]
    plant = rolling["plant"]
    wp_of_op = {o["id"]: o.get("workpackage_ref", "") for o in plant.operations}
    dem_of_wp: dict = {}
    for f in plant.fulfillments:
        dem_of_wp.setdefault(f.get("workpackage_ref", ""), []).append(f.get("demand_ref"))
    placed_dem: set = set()
    for a in docd["assignments"]:
        for did in dem_of_wp.get(wp_of_op.get(a["operation_ref"], ""), []):
            placed_dem.add(did)
    tray_dem = {b["demand_ref"] for b in docd["rolling"]["beyond_horizon"]}
    schedulable = {d["id"] for d in plant.schedulable_demands}
    assert not (placed_dem & tray_dem)
    assert placed_dem | tray_dem == schedulable


# ---------------------------------------------------------------------------
# CU2 — the rolling document carries an interaction payload for the active window
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_rolling_document_carries_interaction_for_the_window(rolling):
    docd = rolling["doc"]
    inter = docd.get("interaction")
    assert inter is not None, "rolling document has no interaction payload (CU2)"
    iop_ids = {o["operation_ref"] for o in inter["operations"]}
    # the payload targets the ACTIVE window ONLY — committed bars carry no
    # interaction op, so they are non-targets by construction.
    assert iop_ids == set(rolling["view"].active)
    committed_ops = set(rolling["view"].committed)
    assert not (iop_ids & committed_ops), "a committed op leaked into the gesture payload"
    committed_states = {a["commitment_state"] for a in docd["assignments"]}
    assert "committed" in committed_states
    # the sibling interaction.json exists (the split-endpoint delivery)
    assert (rolling["out_dir"] / "interaction.json").exists()


# ---------------------------------------------------------------------------
# CU3 — the two-beat on the rolling substrate (all 4B.3b invariants re-proven)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_two_beat_runs_against_a_rolling_schedule(rolling):
    target = _pick_cross_machine_active(rolling["doc"])
    assert target is not None, "no cross-machine active op to drag"
    op, alt, start = target
    g = feasibility_ghost(
        rolling["out_dir"], rolling["snapshot_id"], pin_op_id=op,
        pin_resource_id=alt, pin_start_iso=start,
        restrict_op_ids=rolling["window_op_ids"])
    # beat one carries NO money by construction
    for k in g.summary():
        assert not any(t in k.lower() for t in _MONEY_FIELD_TOKENS)
    assert g.feasible
    r = sandbox_pin_resolve(
        rolling["out_dir"], rolling["snapshot_id"], pin_op_id=op,
        pin_resource_id=alt, pin_start_iso=start,
        standing_pins=rolling["committed_pins"],
        restrict_op_ids=rolling["window_op_ids"])
    # correlation: the two beats share the id (same gesture, no server state)
    assert g.correlation_id == r.correlation_id
    assert r.feasible
    # decomposition sums EXACTLY to the verdict (rollup_of)
    assert r.cost_lines is not None
    assert round(sum(l["delta"] for l in r.cost_lines), 2) == r.cost_delta_abs
    # no committed work changed — LOAD-BEARING here (the frozen front is real
    # committed work held via standing pins)
    assert r.no_committed_work_changes is True
    committed_ops = {p["operation_ref"] for p in rolling["committed_pins"]}
    moved_ops = {m["operation_ref"] for m in r.moves if not m.get("pinned")}
    assert not (committed_ops & moved_ops), "a committed op was reported as moved"


@pytest.mark.slow
def test_forced_infeasible_contradiction_on_a_committed_slot(rolling):
    """Gesture an active op at a COMMITTED slot: beat one (frozen front relaxed) is
    feasible; beat two (frozen front held) proves it infeasible and NAMES the
    blocking commitment — the R-T2 contradiction, on a real rolling run."""
    docd = rolling["doc"]
    iops = _interaction_ops(docd)
    active = [a for a in docd["assignments"]
              if a.get("commitment_state") == "active_window"]
    pair = None
    for comm in rolling["committed_pins"]:
        for a in active:
            io = iops.get(a["operation_ref"])
            if (io and comm["resource_id"] in io["eligible_resource_ids"]
                    and a["operation_ref"] != comm["operation_ref"]):
                pair = (a["operation_ref"], comm)
                break
        if pair:
            break
    assert pair is not None, "no active op eligible on a committed op's resource"
    victim, comm = pair
    g = feasibility_ghost(
        rolling["out_dir"], rolling["snapshot_id"], pin_op_id=victim,
        pin_resource_id=comm["resource_id"], pin_start_iso=comm["start"],
        restrict_op_ids=rolling["window_op_ids"])
    r = sandbox_pin_resolve(
        rolling["out_dir"], rolling["snapshot_id"], pin_op_id=victim,
        pin_resource_id=comm["resource_id"], pin_start_iso=comm["start"],
        standing_pins=rolling["committed_pins"],
        restrict_op_ids=rolling["window_op_ids"])
    assert g.feasible, "beat one should be feasible (it relaxes the frozen front)"
    assert not r.feasible, "beat two should be infeasible (it holds the frozen front)"
    contra = beat_two_contradicts(g, r)
    assert contra["infeasible"] and contra["contradicts"]
    # the verdict names the blocking commitment (never a silent sacrifice)
    assert r.pin.get("conflict_op_ref"), "the infeasible verdict did not name a conflict"


@pytest.mark.slow
def test_forced_alternative_inherits_the_two_beat_shape_on_rolling(rolling):
    """A cross-machine (forced-alternative) pin runs the IDENTICAL two-beat path —
    no parallel machinery — on the rolling substrate."""
    target = _pick_cross_machine_active(rolling["doc"])
    assert target is not None
    op, alt, start = target
    g = feasibility_ghost(
        rolling["out_dir"], rolling["snapshot_id"], pin_op_id=op,
        pin_resource_id=alt, pin_start_iso=start,
        restrict_op_ids=rolling["window_op_ids"])
    r = sandbox_pin_resolve(
        rolling["out_dir"], rolling["snapshot_id"], pin_op_id=op,
        pin_resource_id=alt, pin_start_iso=start,
        standing_pins=rolling["committed_pins"],
        restrict_op_ids=rolling["window_op_ids"])
    assert g.feasible and r.feasible
    # the pinned op lands on the chosen alternative resource (R-DP1 literalness)
    assert r.pin["resource_id"] == alt
    assert r.cost_lines is not None
    assert round(sum(l["delta"] for l in r.cost_lines), 2) == r.cost_delta_abs


# ---------------------------------------------------------------------------
# CU4 — the Explainer reads the persisted rolling run
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_rolling_ask_routes_the_sliced_world_shapes(rolling):
    import mre.api.app as app
    docd = rolling["doc"]
    a, m = app._try_rolling_answer("what's beyond the horizon?", docd, None, None, None)
    assert m["route"] == "beyond-horizon" and "beyond" in a.lower()
    a, m = app._try_rolling_answer("what's frozen?", docd, None, None, None)
    assert m["route"] == "frozen" and ("frozen" in a.lower() or "committed" in a.lower())


@pytest.mark.slow
def test_rolling_ask_why_not_scheduled_yet_is_answerable_for_a_tray_order(rolling):
    """A tray order gets a grounded, HEDGED answer (admitted, due, estimate — never
    a placement). The 'answerable' specimen of the CU4 audit pair."""
    import mre.api.app as app
    docd = rolling["doc"]
    tray = docd["rolling"]["beyond_horizon"]
    assert tray, "empty tray — cannot test why-not-scheduled"
    wo = tray[0]["work_order"] or tray[0]["demand_ref"]
    a, m = app._try_rolling_answer(f"why isn't {wo} scheduled yet?", docd, None, None, None)
    assert m["route"] == "why-not-scheduled-yet"
    assert str(wo) in a and "beyond the current window" in a


@pytest.mark.slow
def test_rolling_ask_why_not_hedges_for_an_already_placed_order(rolling):
    """The 'must hedge / decline' specimen: asking why a PLACED (committed/active)
    order 'isn't scheduled yet' gets an honest 'not in the beyond-horizon list —
    it's already in the current window' answer, never a confident fabrication."""
    import mre.api.app as app
    docd = rolling["doc"]
    placed_wo = next(a["work_orders"][0] for a in docd["assignments"]
                     if a.get("work_orders"))
    a, m = app._try_rolling_answer(f"why isn't {placed_wo} scheduled yet?",
                                   docd, None, None, None)
    assert m["route"] == "why-not-scheduled-yet"
    assert "isn't in the beyond-horizon list" in a


@pytest.mark.slow
def test_rolling_ask_why_not_declines_cleanly_for_an_unknown_order(rolling):
    """An order-shaped token not in the schedule never gets a fabricated placement
    — the resolver refuses to echo an id it cannot resolve (relevance guard); the
    answer is an honest clarify, not a confident wrong."""
    import mre.api.app as app
    a, m = app._try_rolling_answer("why isn't ORD-999999 scheduled yet?",
                                   rolling["doc"], None, None, None)
    assert m["route"] == "why-not-scheduled-yet"
    assert "ORD-999999" not in a          # never fabricates against a phantom id
    assert "which order" in a.lower()


@pytest.mark.slow
def test_ask_why_on_machine_is_grounded_on_the_persisted_run(rolling):
    """CU4(c): 'ask why' from a beat-two card reaches a REAL grounded answer — the
    Explainer resolves why-on-machine against the persisted window-0 evidence."""
    import mre.api.app as app
    docd = rolling["doc"]
    a0 = next(a for a in docd["assignments"] if a.get("work_orders"))
    wo, mach = a0["work_orders"][0], a0["external_name"]
    ans, meta = app._answer_question(
        rolling["out_dir"], rolling["snapshot_id"],
        f"why is {wo} on {mach}?", use_llm=False, document=docd)
    assert meta["route"] == "why-on-machine"
    assert wo in ans and "because" in ans.lower()

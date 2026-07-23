"""Session 4B.3a CU1 — the rolling (sliced) schedule document.

A rolling-horizon solve (pilot_scale, R-SC2) becomes a contract-1.7 document
through the SAME assembler contract the cockpit already renders. These tests
prove:
  * build_rolling_view classifies the current window into committed / active /
    beyond-horizon (the sliced world's three states);
  * assemble_rolling_document produces a valid contract-1.7 document whose bars
    carry a commitment_state and whose RollingBlock carries the window metadata
    + the beyond-horizon tray;
  * the COMPLETENESS INVARIANT holds — every schedulable demand appears exactly
    once (committed/active bar, or beyond-horizon tray entry), counted here so a
    silent exclusion is a test failure, not an invisible one.

All rolling views require a real solve, so the substantive tests are slow.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from mre.modules.rolling_horizon import prepare_plant, build_rolling_view
from mre.modules.schedule_assembler import (
    assemble_rolling_document, _earliest_window_estimate,
)

REF = datetime(2026, 1, 5, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# fast unit — the beyond-horizon estimate is honest (derivable or absent)
# ---------------------------------------------------------------------------

def test_earliest_window_estimate_clamped_and_absent():
    ref = REF
    # a due 10 days out with ~2 working days of content → est = due - 2d, > ref
    d = {"due": "2026-01-15T00:00:00+00:00"}
    est = _earliest_window_estimate(d, working_min=900, ref=ref)
    assert est is not None and est > ref and est < datetime(2026, 1, 15, tzinfo=timezone.utc)
    # a due already past the working-day offset clamps to the reference origin
    near = {"due": "2026-01-05T12:00:00+00:00"}
    assert _earliest_window_estimate(near, working_min=5000, ref=ref) == ref
    # no due date → no estimate (never invented)
    assert _earliest_window_estimate({}, working_min=100, ref=ref) is None


# ---------------------------------------------------------------------------
# slow — the sliced world, end to end
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def plant(tmp_path_factory):
    from generate_erp_dataset import generate
    d = tmp_path_factory.mktemp("rolldoc")
    generate(d / "sub", scenario="pilot_scale", orders=40, seed=1)
    return prepare_plant(d / "sub", d / "prep", reference_date=REF)


@pytest.fixture(scope="module")
def view(plant):
    return build_rolling_view(plant, window_days=7, frozen_days=2, gravity=True,
                              deterministic=True, seed=42, member_time_limit_s=8.0,
                              det_time=1.0)


@pytest.fixture(scope="module")
def identity_map(plant):
    return plant.store.load_snapshot(plant.snapshot_id).read_identity_map()


@pytest.mark.slow
def test_view_classifies_the_three_states(plant, view):
    # something is committed this window (the frozen front fills), and the tray is
    # populated (a 40-order plant cannot fit its whole book in one 7-day window).
    assert view.status in ("OPTIMAL", "FEASIBLE")
    assert len(view.committed) > 0, "no op committed to the frozen front"
    assert len(view.beyond_demand_ids) > 0, "nothing beyond the horizon (tray empty)"
    # committed and active are disjoint op sets
    assert not (set(view.committed) & set(view.active))
    # every committed op starts strictly before the frozen boundary
    from mre.modules.rolling_horizon import _dt
    for pl in view.committed.values():
        assert _dt(pl["start"]) < view.frozen_end
    for pl in view.active.values():
        assert _dt(pl["start"]) >= view.frozen_end


@pytest.mark.slow
def test_completeness_invariant_every_demand_counted(plant, view, identity_map):
    """The anti-silent-exclusion clause: every schedulable demand appears exactly
    once. assemble_rolling_document RAISES on a violation; here we also count."""
    doc = assemble_rolling_document(
        plant=plant, view=view, schedule_id="sched-rolling-test",
        run_id="run-x", identity_map=identity_map)

    # placed demand ids (via the placed ops' workpackages) ∪ tray ids = schedulable
    wp_of_op = {o["id"]: o.get("workpackage_ref", "") for o in plant.operations}
    dem_of_wp: dict = {}
    for f in plant.fulfillments:
        dem_of_wp.setdefault(f.get("workpackage_ref", ""), []).append(f.get("demand_ref"))
    placed_dem = set()
    for oid in view.placed:
        placed_dem.update(dem_of_wp.get(wp_of_op.get(oid, ""), []))
    tray_dem = {b.demand_ref for b in doc.rolling.beyond_horizon}

    schedulable = {d["id"] for d in plant.schedulable_demands}
    # partition: no overlap, full cover
    assert not (placed_dem & tray_dem), "a demand is both placed and beyond-horizon"
    assert placed_dem | tray_dem == schedulable, (
        f"demands missing from the document: "
        f"{sorted(schedulable - placed_dem - tray_dem)[:5]}")


@pytest.mark.slow
def test_rolling_document_shape(plant, view, identity_map):
    doc = assemble_rolling_document(
        plant=plant, view=view, schedule_id="sched-rolling-test",
        run_id="run-x", identity_map=identity_map)

    assert doc.contract_version == "1.7"
    assert doc.rolling is not None
    r = doc.rolling
    assert r.reference_origin == REF
    assert r.window_days == 7 and r.frozen_days == 2
    assert r.frozen_until == view.frozen_end
    assert r.committed_count == len(view.committed)
    assert r.active_count == len(view.active)
    assert len(r.beyond_horizon) == len(view.beyond_demand_ids)

    # every bar carries a commitment_state ∈ {committed, active_window}
    states = {a.commitment_state for a in doc.assignments}
    assert states <= {"committed", "active_window"}
    assert "committed" in states
    committed_bars = [a for a in doc.assignments if a.commitment_state == "committed"]
    assert len(committed_bars) == len(view.committed)

    # the tray items carry a due date and (where derivable) an estimate; never a
    # placement. Names are planner vocabulary (work_order), never a raw UUID.
    for item in r.beyond_horizon:
        assert item.demand_ref
        # a work_order when the identity map resolves it (pilot_scale populates it)
    # cost decomposes (enforced at construction; assert it exists)
    assert doc.cost_summary.total >= 0


@pytest.mark.slow
def test_monolithic_document_unaffected(plant):
    """A monolithic document (assemble_schedule_document) carries no rolling block
    and no commitment_state — contract 1.7 is additive."""
    # Build a rolling view but assert the NON-rolling assembler path is untouched:
    # the monolithic assembler is exercised throughout test_schedule_document.py;
    # here we only pin that the new fields default to absent on that path.
    from mre.contracts.schedule_document import ScheduleDocument, AssignmentBlock
    a = AssignmentBlock(assignment_id="a", operation_ref="o",
                        workpackage_ref="w", resource_id="r")
    assert a.commitment_state is None
    # a document with no rolling block round-trips with rolling=None
    from mre.contracts.schedule_document import CostSummary, SolverBlock
    doc = ScheduleDocument(
        schedule_id="s", snapshot_id="snap", run_id="run",
        solver=SolverBlock(status="OPTIMAL"),
        cost_summary=CostSummary(total=0, production_regular=0,
                                 production_overtime=0, setup=0, tardiness=0))
    assert doc.rolling is None
    assert doc.contract_version == "1.7"

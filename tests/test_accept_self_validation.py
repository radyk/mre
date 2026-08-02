"""R-DP11 — THE ACCEPT MODEL IS THE PLAN OF RECORD'S OWN SCOPE (Session 4B.31).

The missing invariant, written from the ruling:

    The model an accept compiles is built over exactly the operations the plan
    of record PLACES. The published plan is therefore a feasible assignment of
    that model BY CONSTRUCTION — an accept may fail because of the EDIT, never
    because of the plan it edits.

Before 4B.31 the accept compiled the WHOLE BOOK against the WINDOW's horizon.
On every rolling board this product has ever minted, that made the accept model
infeasible with no edit at all: a ZERO-MOVE accept — pinning a bar at its own
placement — was refused. Nothing had ever committed on a rolling board.

THE GUARD HAS TWO MEMBERS AND IT NEEDS BOTH.

  * the PROPERTY (``test_accept_compiles_only_the_plan_of_record``) — the scope
    equality itself, asserted through the live dispatch on ANY rolling board.
  * the BEHAVIOUR (``test_incumbent_revalidates``) — a zero-move accept
    succeeds, on a board dense enough that the unadmitted tray genuinely does
    not fit the window horizon.

The behaviour test alone would not have caught this. Measured in 4B.31 CU1: at
40 orders / w14 the whole book DOES fit the horizon and the zero-move accept is
green at HEAD, defect and all. The condition needs density (pilot_scale 200 /
w7 reproduces; 40 and 80 do not), which is exactly why six sessions of
monolithic accept fixtures reported green over a path nothing could commit on.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from mre.modules.planner_edit import apply_planner_edit
from mre.modules.rolling_horizon import build_rolling_view, prepare_plant
from mre.modules.sandbox import _restrict_window, plan_of_record_scope
from mre.modules.schedule_assembler import assemble_rolling_document
from mre.modules.scenario import derive_base_context

pytestmark = pytest.mark.slow

REF = datetime(2026, 1, 5, tzinfo=timezone.utc)

# Two rolling worlds, deliberately either side of the density at which the
# unadmitted tray stops fitting the window horizon (4B.31 CU1's measurement).
SPARSE = dict(orders=40, window_days=14, frozen_days=3)    # book FITS the horizon
DENSE = dict(orders=200, window_days=7, frozen_days=2)     # book does NOT fit


def _rolling_world(tmp_path_factory, tag, orders, window_days, frozen_days):
    from generate_erp_dataset import generate
    from mre.api.app import _persist_document

    d = tmp_path_factory.mktemp(tag)
    generate(d / "sub", scenario="pilot_scale", orders=orders, seed=1)
    plant = prepare_plant(d / "sub", d / "prep", reference_date=REF)
    view = build_rolling_view(
        plant, window_days=window_days, frozen_days=frozen_days, gravity=True,
        deterministic=True, seed=42, member_time_limit_s=10.0, det_total=1.0,
        persist=True)
    reader = plant.store.load_snapshot(plant.snapshot_id)
    doc = assemble_rolling_document(
        plant=plant, view=view, schedule_id=f"s-{tag}", run_id=f"run-{tag}",
        identity_map=reader.read_identity_map())
    _persist_document(doc, plant.out_dir)
    docd = json.loads((plant.out_dir / "schedule_document.json").read_text("utf-8"))
    return {
        "out_dir": plant.out_dir,
        "snapshot_id": plant.snapshot_id,
        "doc": docd,
        "operations": list(reader.iter_entities("operation")),
        "assignments": list(reader.iter_entities("assignment")),
    }


@pytest.fixture(scope="module")
def sparse(tmp_path_factory):
    return _rolling_world(tmp_path_factory, "sparse", **SPARSE)


@pytest.fixture(scope="module")
def dense(tmp_path_factory):
    return _rolling_world(tmp_path_factory, "dense", **DENSE)


def _base_context(world):
    ctx = derive_base_context(Path(world["out_dir"]) / "runs")
    ctx["base_runs_dir"] = str(Path(world["out_dir"]) / "runs")
    return ctx


def _active_bar(world):
    """A bar the planner could actually gesture at: active window, one chunk."""
    for a in world["doc"]["assignments"]:
        if a.get("commitment_state") != "committed" and len(a.get("chunks") or []) == 1:
            return a
    raise AssertionError("fixture produced no active single-chunk bar")


def _accept(world, tmp_path, *, op, resource, start, snapshot_src=None):
    """The LIVE accept dispatch — the same call ``_execute_accept`` makes.

    ``snapshot_src`` overrides where the base snapshot is copied FROM, which is
    how the negative control feeds it a deliberately corrupted plan."""
    snapshot_id = world["snapshot_id"]
    src = Path(snapshot_src or (Path(world["out_dir"]) / "snapshots" / snapshot_id))
    out = Path(tmp_path) / "accept"
    if not (out / "snapshots" / snapshot_id).exists():
        shutil.copytree(src, out / "snapshots" / snapshot_id)
    return apply_planner_edit(
        out_dir=out, base_snapshot_id=snapshot_id,
        pin_op_id=op, pin_resource_id=resource, pin_start_iso=start,
        authority="guard", base_context=_base_context(world),
        budget_s=120.0, hold_all_placements=True, det_time_s=2.0, seed=42)


# ---------------------------------------------------------------------------
# premise — the fixtures really do produce the conditions the guard needs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("which", ["sparse", "dense"])
def test_premise_the_board_carries_work_it_did_not_place(which, request):
    """A rolling board's snapshot holds operations the window never admitted —
    the beyond-horizon tray. Without them the property has nothing to bite on."""
    world = request.getfixturevalue(which)
    placed = {a["operation_ref"] for a in world["assignments"]}
    assert len(placed) < len(world["operations"]), (
        "premise failed: this board placed every operation, so there is no tray "
        "and the whole-book compile would be harmless")
    states = {a.get("commitment_state") for a in world["doc"]["assignments"]}
    assert "committed" in states and "active_window" in states, states


def test_premise_the_dense_book_does_not_fit_the_window_horizon(dense):
    """The condition the BEHAVIOUR test needs: with the plan of record held, the
    whole book is infeasible in the window's horizon and the plan's own scope is
    not. This is the fixture reproducing the Khalil board's shape — and it is
    what the sparse board, by measurement, does NOT do."""
    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solution_pool import _m5_horizon, _placements, _read_evidence
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import SolverBuilder
    from mre.modules import standing_pins as sp
    from mre.reporter import Reporter
    from mre.contracts.vocabularies import ModuleCode, RunStatus

    out = Path(dense["out_dir"])
    reader = SnapshotStore(out / "snapshots").load_snapshot(dense["snapshot_id"])
    ent = {k: list(reader.iter_entities(k)) for k in
           ("demand", "fulfillment", "workpackage", "operation", "precedenceedge",
            "resource", "resourcepool", "calendar", "constraint", "costmodel")}
    hs, he = _m5_horizon(_read_evidence(out / "runs"))
    placement = _placements(dense["assignments"])
    cals = flatten_all_calendars(ent["calendar"], hs, he)
    sink = out / "premise_runs"

    def solve(scope):
        ops, wps, fuls, dems = _restrict_window(
            ent["operation"], ent["workpackage"], ent["fulfillment"],
            ent["demand"], scope)
        rep = Reporter.begin(module=ModuleCode.M5, purpose="premise", config={},
                             trigger="test", snapshot_id=dense["snapshot_id"],
                             sink_dir=sink)
        model, vm = SolverBuilder(reference_date=hs).build(
            wps + ops + ent["precedenceedge"], ent["resource"] + ent["resourcepool"],
            cals, fuls + dems, ent["constraint"],
            ent["costmodel"][0] if ent["costmodel"] else {})
        rep.end(RunStatus.SUCCESS)
        keep = {o["id"] for o in ops}
        for oid, (rid, s_dt) in placement.items():
            if oid in keep:
                sp.apply_pin(model, vm, oid, rid,
                             int((s_dt - hs).total_seconds() // 60))
        rr = Reporter.begin(module=ModuleCode.M6, purpose="premise", config={},
                            trigger="test", snapshot_id=dense["snapshot_id"],
                            sink_dir=sink)
        res = SolveRunner(time_limit_seconds=180.0, num_search_workers=1,
                          random_seed=42, deterministic_time=2.0).solve(model, vm, rr)
        rr.end(RunStatus.SUCCESS)
        return res.status

    assert solve(None) == "INFEASIBLE", (
        "premise failed: the WHOLE BOOK fits this window's horizon, so the "
        "behaviour test would pass at HEAD and prove nothing")
    assert solve(plan_of_record_scope(dense["assignments"])) in ("OPTIMAL", "FEASIBLE")


# ---------------------------------------------------------------------------
# the PROPERTY — scope equality, through the live dispatch, at any density
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("which", ["sparse", "dense"])
def test_accept_compiles_only_the_plan_of_record(which, request, tmp_path,
                                                 monkeypatch):
    """R-DP11: the operations handed to the SolverBuilder by an accept are
    exactly the operations the plan of record places.

    Asserted by watching the real build the live accept performs, not by
    re-deriving the scope here — the point is that the shipped path does it."""
    world = request.getfixturevalue(which)
    from mre.modules import solver_builder as sb

    all_op_ids = {o["id"] for o in world["operations"]}
    seen: list[set] = []
    real_build = sb.SolverBuilder.build

    def spy(self, planning, resources, calendars, demand, constraints, cost_model):
        seen.append({e["id"] for e in planning} & all_op_ids)
        return real_build(self, planning, resources, calendars, demand,
                          constraints, cost_model)

    monkeypatch.setattr(sb.SolverBuilder, "build", spy)

    bar = _active_bar(world)
    try:
        _accept(world, tmp_path, op=bar["operation_ref"],
                resource=bar["resource_id"], start=bar["chunks"][0]["start"])
    except RuntimeError:
        pass          # the property holds (or does not) regardless of the verdict
    assert seen, "the accept never built a model"
    placed = {a["operation_ref"] for a in world["assignments"]}
    assert seen[0] == placed, (
        f"the accept compiled {len(seen[0])} operations for a plan that places "
        f"{len(placed)}; {len(seen[0] - placed)} of them are work this board "
        "never admitted (R-DP11)")


def test_the_scope_of_a_plan_that_places_everything_is_the_identity(sparse):
    """R-DP11 clause (4): on a monolithic plan — every operation placed — the
    restriction changes nothing, which is why the monolithic path is unchanged
    byte for byte and its goldens still hold."""
    ops = sparse["operations"]
    every = [{"operation_ref": o["id"]} for o in ops]
    scope = plan_of_record_scope(every)
    assert scope == {o["id"] for o in ops}
    kept, _, _, _ = _restrict_window(ops, [], [], [], scope)
    assert [o["id"] for o in kept] == [o["id"] for o in ops]


def test_a_plan_with_no_placements_has_no_scope():
    """None, not the empty set: 'this plan places nothing' and 'restrict the
    model to nothing' are different claims (4B.18's `unreadable` discipline)."""
    assert plan_of_record_scope([]) is None
    assert plan_of_record_scope([{"operation_ref": None}]) is None


# ---------------------------------------------------------------------------
# the BEHAVIOUR — the incumbent re-validates
# ---------------------------------------------------------------------------

def test_incumbent_revalidates(dense, tmp_path):
    """THE MISSING INVARIANT: the accept model, given NO edit, must accept the
    plan of record. A bar pinned at its own placement changes nothing, so the
    only thing this can fail on is the compile."""
    bar = _active_bar(dense)
    result = _accept(dense, tmp_path, op=bar["operation_ref"],
                     resource=bar["resource_id"], start=bar["chunks"][0]["start"])
    assert result.feasible, result.status
    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert result.cost_delta["total_delta"] == pytest.approx(0.0, abs=0.005), (
        "a zero-move accept changed the ledger")


def test_negative_control_a_corrupted_plan_is_refused(dense, tmp_path):
    """The guard bites. Corrupt the plan of record — move one placement on top
    of another on the same machine — and the zero-move accept must refuse.

    Without this, ``test_incumbent_revalidates`` would be satisfied by an accept
    that had stopped checking anything at all."""
    snap = dense["snapshot_id"]
    corrupt_out = tmp_path / "corrupt"
    shutil.copytree(Path(dense["out_dir"]) / "snapshots" / snap,
                    corrupt_out / "snapshots" / snap)

    path = corrupt_out / "snapshots" / snap / "entities_assignment.jsonl"
    rows = [json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()]

    def res_of(r):
        ra = r.get("resource_assignments") or []
        return ra[0].get("resource_ref") if ra else None

    by_res: dict = {}
    for r in rows:
        by_res.setdefault(res_of(r), []).append(r)
    victim = donor = None
    for _rid, group in sorted(by_res.items(), key=lambda kv: str(kv[0])):
        if len(group) >= 2:
            donor, victim = group[0], group[1]
            break
    assert victim is not None, "fixture has no machine carrying two bars"
    # victim now starts exactly where the donor does, on the same machine.
    victim["phase_windows"]["run"] = json.loads(
        json.dumps(donor["phase_windows"]["run"]))
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    bar = _active_bar(dense)
    with pytest.raises(RuntimeError):
        _accept(dense, tmp_path / "corrupt_run", op=bar["operation_ref"],
                resource=bar["resource_id"], start=bar["chunks"][0]["start"],
                snapshot_src=corrupt_out / "snapshots" / snap)

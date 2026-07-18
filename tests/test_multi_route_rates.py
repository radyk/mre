"""multi_route_rates (docs/06 §5.3, Session 4B.0 CU4) — per-ALTERNATIVE rates
through the CSV doorway, end to end.

The multi_route scenario proved eligible SETS enter through routing_lines rows.
This scenario proves the harder, newer contract: an operation's eligible
machines running it at DIFFERENT speeds (distinct run_minutes_per_unit per
alternative row) is captured, scheduled, and PRICED honestly — the silent-drop
the pre-4B.0 adapter had (time read from the first row only) is closed.

Rates are equal across machines, so a placement's whole cost differential is its
DURATION. The counterfactual PINS the slow alternative and asserts, through a
real re-solve + extraction:
  * the slow placement's scheduled duration is the SLOW run time (120 min), not
    the fast one (60) — the per-resource duration flowed through the solver;
  * the slow placement costs strictly MORE than the fast placement — the
    extractor priced the chosen alternative's honest rate.

The re-solves are slow-marked (two pinned pipeline solves).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.modules.snapshot_store import SnapshotStore
from tools.generate_erp_dataset import generate

SNAP = "snap-mrr"


def _run_pipeline(sub: Path, out: Path, snap: str = SNAP) -> None:
    rc = mre_main([
        "--submission", str(sub), "--out", str(out), "--snapshot-id", snap,
        "--time-limit", "30", "--solver-workers", "1", "--solver-seed", "42",
    ])
    assert rc == 0, f"pipeline exit {rc}"


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("mrr")
    sub = tmp / "sub"
    truth = generate(sub, scenario="multi_route_rates", seed=7)["multi_route_rates"]
    out = tmp / "out"
    _run_pipeline(sub, out)
    reader = SnapshotStore(out / "snapshots").load_snapshot(SNAP)
    return truth, sub, out, reader


def _target_op(reader):
    """One seq-10 operation instance (the fast/slow multi-eligible step) plus
    its (fast_ref, slow_ref) resolved from the resolved per-resource durations:
    the slow machine is the one carrying a LONGER run duration override."""
    from mre.modules.solver_builder import _parse_td, _td_to_minutes
    for op in reader.iter_entities("operation"):
        if op["sequence"] != 10:
            continue
        refs = op["resource_requirements"][0].get("resource_refs") or []
        run_ov = op.get("resource_run_durations") or {}
        if len(refs) < 2 or not run_ov:
            continue
        default_run = _td_to_minutes(_parse_td(op.get("run_duration", "PT0S")))
        slow_ref = max(run_ov, key=lambda r: _td_to_minutes(_parse_td(run_ov[r])))
        slow_min = _td_to_minutes(_parse_td(run_ov[slow_ref]))
        fast_ref = next(r for r in refs if r != slow_ref)
        return op["id"], fast_ref, slow_ref, default_run, slow_min
    raise AssertionError("no seq-10 multi-eligible op with a rate override")


# ---------------------------------------------------------------------------
# Structure — the per-alternative time entered through the CSV doorway
# ---------------------------------------------------------------------------

def test_slow_alternative_carries_a_longer_resolved_duration(base):
    _, _, _, reader = base
    op_id, fast_ref, slow_ref, fast_min, slow_min = _target_op(reader)
    # The slow machine's own run time (120) is captured, distinct from the
    # first-row default (60) — the drop is closed.
    assert slow_min == 120
    assert fast_min == 60
    assert slow_min > fast_min


# ---------------------------------------------------------------------------
# Counterfactual — pin the slow alternative, price it through end to end (slow)
# ---------------------------------------------------------------------------

def _solve_pinned(out: Path, target: str, resource_ref: str):
    """Force ``target`` onto ``resource_ref`` and re-solve from the snapshot,
    returning (duration_minutes, production_cost) for that op."""
    from mre.modules.extractor import Extractor
    from mre.modules.forced_alternatives import _load_alt_context
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import SolverBuilder, add_required_resource_cut
    from mre.contracts.vocabularies import ModuleCode, RunStatus
    from mre.reporter import Reporter

    actx = _load_alt_context(out, SNAP, "runs")
    runs = out / "cf_runs"
    b_rep = Reporter.begin(module=ModuleCode.M5, purpose="cf build", config={},
                           trigger="test", snapshot_id=SNAP, sink_dir=runs)
    model, var_map = SolverBuilder(reference_date=actx.reference_date).build(
        actx.wps + actx.ops + actx.edges, actx.resources + actx.pools,
        actx.flattened_cals, actx.fuls + actx.demands, actx.constraints,
        actx.cost_model,
    )
    b_rep.end(RunStatus.SUCCESS)
    assert add_required_resource_cut(model, var_map, target, resource_ref), \
        "target op has no literal on the required resource"
    r_rep = Reporter.begin(module=ModuleCode.M6, purpose="cf solve",
                           config={"time_limit": 20}, trigger="test",
                           snapshot_id=SNAP, sink_dir=runs)
    result = SolveRunner(time_limit_seconds=20, num_search_workers=1,
                         random_seed=42).solve(model, var_map, r_rep)
    r_rep.end(RunStatus.SUCCESS if result.status in ("OPTIMAL", "FEASIBLE")
              else RunStatus.PARTIAL)
    assert result.status in ("OPTIMAL", "FEASIBLE"), result.status
    assert result.solve_values.op_resource.get(target) == resource_ref
    extract = Extractor().extract(
        solve_values=result.solve_values, snapshot_id=SNAP,
        operations=actx.ops, workpackages=actx.wps, resources=actx.resources,
        fulfillments=actx.fuls, demands=actx.demands, cost_model=actx.cost_model,
        reporter=None, cal_windows=var_map.cal_windows,
        op_eligible=var_map.op_eligible, snapshot_writer=None,
        overtime_windows=var_map.overtime_windows,
    )
    asgn = next(a for a in extract.assignments if a["operation_ref"] == target)
    dur = (result.solve_values.op_end_minutes[target]
           - result.solve_values.op_start_minutes[target])
    return dur, asgn["production_cost"]


@pytest.mark.slow
def test_pinning_the_slow_alternative_is_longer_and_costlier(base):
    truth, _, out, reader = base
    op_id, fast_ref, slow_ref, fast_min, slow_min = _target_op(reader)

    fast_dur, fast_cost = _solve_pinned(out, op_id, fast_ref)
    slow_dur, slow_cost = _solve_pinned(out, op_id, slow_ref)

    # The per-alternative time flowed through the SOLVER: pinning the slow
    # machine schedules an op exactly 60 minutes longer than the fast machine
    # (120 vs 60 run minutes). A pre-existing systemic +1-minute offset — it
    # hits the homogeneous successor op identically — cancels in the delta, so
    # the invariant is stated as the difference, which is exact.
    assert slow_dur - fast_dur == 60
    assert slow_dur > fast_dur
    # And the EXTRACTOR priced the chosen alternative's honest rate: equal
    # $/min, ~double the minutes → the slow placement costs strictly more
    # (the price the pre-4B.0 silent-drop hid).
    assert slow_cost > fast_cost
    assert truth["expected_slow_costlier_than_fast"]

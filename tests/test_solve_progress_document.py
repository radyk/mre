"""R-SP1 at the DOCUMENT seam — contract 1.16 `solver.progress`.

Two assemblers build the block from two different SOURCES: the monolithic one
reads the `solve_progress` Event out of evidence, the rolling one reads the
trail off the completed view. Both compose their CONTENT through
`solve_progress.progress_block_fields`, and both are exercised here — a defect
class fixed at one seam is not fixed (4B.14 §5a.34).

Clause (5)'s absent state is asserted at the contract level AND measured against
the three real pinned boards in the close-out.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# the generator lives in tools/, exactly as test_rolling_horizon reaches it
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

UTC = timezone.utc
REF = datetime(2026, 1, 5, tzinfo=UTC)


# ---------------------------------------------------------------------------
# the contract
# ---------------------------------------------------------------------------

def test_the_contract_version_names_this_block():
    from mre.contracts.schedule_document import CONTRACT_VERSION
    assert CONTRACT_VERSION == "1.16"


def test_a_solver_block_without_a_trail_is_absent_not_empty():
    """CLAUSE (5). Every board solved before this contract has no trail and
    never will — evidence is append-only and nothing is reconstructed. An empty
    `SolveProgressBlock` would claim a search that recorded nothing; None says
    the recording did not exist."""
    from mre.contracts.schedule_document import SolverBlock
    assert SolverBlock(status="OPTIMAL").progress is None


def test_a_pre_1_16_document_still_parses(tmp_path):
    """The bump must not orphan the stored boards. Their documents say 1.15 and
    carry no `progress`, and they are never re-minted."""
    from mre.contracts.schedule_document import ScheduleDocument
    doc = ScheduleDocument(
        contract_version="1.15", schedule_id="rolling-old", snapshot_id="s",
        run_id="r",
        solver={"status": "FEASIBLE"},
        cost_summary={"total": 10.0, "production_regular": 10.0,
                      "production_overtime": 0.0, "setup": 0.0,
                      "tardiness": 0.0})
    assert doc.solver.progress is None
    assert doc.contract_version == "1.15"


def test_the_block_carries_the_clause_labels_and_no_currency():
    from mre.contracts.schedule_document import SolveProgressBlock
    from mre.modules.solve_progress import (
        CLAUSE_2_LABEL, CLAUSE_3_LABEL, progress_block_fields,
    )
    trail = [{"index": 1, "objective": 1000.0, "elapsed_s": 0.1},
             {"index": 2, "objective": 750.0, "elapsed_s": 0.2}]
    b = SolveProgressBlock(**progress_block_fields(
        trail, best_bound=700.0, gap=0.0667, window_key="2026-01-05T00:00:00+00:00"))
    assert b.clause_2_label == CLAUSE_2_LABEL
    assert b.clause_3_label == CLAUSE_3_LABEL
    assert b.objective_unit == "objective_units"
    assert "$" not in b.headline
    assert b.improvement_pct == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# the MONOLITHIC seam — written by SolveRunner, read back by the assembler
# ---------------------------------------------------------------------------

def test_the_monolithic_path_writes_the_trail_and_the_assembler_reads_it(tmp_path):
    """Round trip through the real seam: ``SolveRunner`` emits the record
    (because it was given a reporter), and ``_progress_block_from_evidence``
    rebuilds the block from the stream. The two ends are tested TOGETHER because
    a writer and a reader that agree only in the author's head is how a record
    ends up unreadable."""
    from ortools.sat.python import cp_model as cp

    from mre.contracts.vocabularies import ModuleCode, RunStatus
    from mre.modules.schedule_assembler import _progress_block_from_evidence
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import VariableMap
    from mre.reporter import Reporter

    # a model with real search in it, so the trail is worth reading back
    m = cp.CpModel()
    durs, weights, dues = [30, 45, 20, 60, 25], [7, 1, 9, 2, 8], [60, 90, 40, 200, 70]
    H, ivs, terms, starts, ends = sum(durs), [], [], {}, {}
    for i, d in enumerate(durs):
        s = m.new_int_var(0, H, f"s{i}"); e = m.new_int_var(0, H, f"e{i}")
        m.add(e == s + d)
        ivs.append(m.new_interval_var(s, d, e, f"iv{i}"))
        t = m.new_int_var(0, H, f"t{i}"); m.add(t >= e - dues[i])
        terms.append(t * weights[i]); starts[f"J{i}"], ends[f"J{i}"] = s, e
    m.add_no_overlap(ivs); m.minimize(sum(terms))
    vm = VariableMap(horizon_start=REF)
    vm.op_start, vm.op_end = dict(starts), dict(ends)
    vm.op_assign = {k: {} for k in starts}
    vm.objective_terms = list(terms)

    rep = Reporter.begin(module=ModuleCode.M6, purpose="solve run", config={},
                         trigger="test", snapshot_id="snap-m",
                         sink_dir=tmp_path / "runs")
    result = SolveRunner(time_limit_seconds=30.0, num_search_workers=1,
                         random_seed=42).solve(m, vm, rep)
    rep.end(RunStatus.SUCCESS)

    import json
    recs = []
    for f in (tmp_path / "runs").glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                recs.append(json.loads(line))
    m6 = [r for r in recs if r.get("record_type") == "run_context_open"
          and r.get("module") == "M6"]
    blk = _progress_block_from_evidence(recs, m6[-1]["run_id"])
    assert blk is not None, "the monolithic seam wrote no readable trail"
    assert blk.count == len(result.incumbent_trail) > 1
    assert blk.final == pytest.approx(result.objective)
    assert blk.best_bound == pytest.approx(result.best_bound)
    # a monolithic solve has no window to name (clause 1)
    assert blk.window_key is None


def test_the_assembler_returns_none_when_no_trail_was_recorded():
    """Clause (5) at the read seam: an evidence stream with no trail record
    yields None, not an empty block."""
    from mre.modules.schedule_assembler import _progress_block_from_evidence
    assert _progress_block_from_evidence([], "run-x") is None


# ---------------------------------------------------------------------------
# the ROLLING seam, on a real solved window
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rolling_plant_and_view(tmp_path_factory):
    from generate_erp_dataset import generate

    from mre.modules.rolling_horizon import build_rolling_view, prepare_plant
    d = tmp_path_factory.mktemp("w21_rolling")
    generate(d / "sub", scenario="pilot_scale", orders=40, seed=1)
    plant = prepare_plant(d / "sub", d / "prep", reference_date=REF)
    view = build_rolling_view(plant, window_days=10, frozen_days=1,
                              deterministic=True, seed=42, persist=False)
    return plant, view


@pytest.fixture(scope="module")
def rolling_view(rolling_plant_and_view):
    return rolling_plant_and_view[1]


def test_the_rolling_view_carries_the_cost_search_trail(rolling_view):
    trail = rolling_view.incumbent_trail
    assert trail, "a solved window must carry its own search history"
    assert [i["index"] for i in trail] == list(range(1, len(trail) + 1))
    # CP-SAT minimizes, so the trail descends — this is what makes
    # "first minus final" an improvement rather than a signed difference.
    objs = [i["objective"] for i in trail]
    assert objs == sorted(objs, reverse=True)


def test_the_rolling_trail_is_stage_ones_not_the_tiebreaks(rolling_view):
    """CLAUSE (7). Stage 2 minimizes Σ free-op START MINUTES; stage 1 minimizes
    COST. The view's `objective` has been stage 1's since 4B.7, and the trail
    must belong to the same search — its LAST point is that objective.

    If stage 2's trail leaked in, the final point would be a minute count and
    would not match, which is 4B.7 §5a.16's defect on a new surface."""
    assert rolling_view.objective is not None
    assert rolling_view.incumbent_trail[-1]["objective"] == pytest.approx(
        rolling_view.objective)


def test_the_rolling_document_renders_the_block_keyed_to_its_window(rolling_view):
    from mre.modules.schedule_assembler import _progress_block_from_view
    b = _progress_block_from_view(rolling_view)
    assert b is not None
    assert b.stage == "cost"
    # CLAUSE (1): the trail names the ONE window it belongs to, which is what
    # stops any reader summing two of them.
    assert b.window_key == rolling_view.window_start.isoformat()
    assert b.count == len(rolling_view.incumbent_trail)
    assert b.final == pytest.approx(rolling_view.objective)


def test_THE_ASSEMBLER_puts_the_block_on_a_real_rolling_document(rolling_plant_and_view):
    """THROUGH THE REAL DOOR, NOT THE HELPER.

    The test above calls `_progress_block_from_view` with a view it supplies
    itself — which proves the helper, not the path (4B.21 §5a.78). The wiring in
    `assemble_rolling_document` is ONE LINE, and if it ever returned None every
    other assertion in this file would still pass while every real board shipped
    without a trail. So this one builds an actual document and looks at
    `doc.solver.progress`."""
    from mre.modules.schedule_assembler import assemble_rolling_document
    plant, view = rolling_plant_and_view
    doc = assemble_rolling_document(plant=plant, view=view,
                                    schedule_id="sched-w21", run_id="run-w21")
    assert doc.contract_version == "1.16"
    assert doc.solver.progress is not None, (
        "a solved rolling window shipped a document with no search history")
    p = doc.solver.progress
    assert p.stage == "cost"
    assert p.count == len(view.incumbent_trail) > 1
    assert p.window_key == view.window_start.isoformat()
    assert p.headline and "$" not in p.headline
    assert p.clause_2_label and p.clause_3_label
    # the block's terminal point agrees with the solver telemetry beside it
    assert p.final == pytest.approx(doc.solver.objective)


def test_a_window_that_ran_no_search_has_no_block():
    """An empty trail is not a flat trail. A window that admitted nothing ran no
    search at all, and a headline saying "no workable plan was found" would
    claim a search happened."""
    from mre.modules.schedule_assembler import _progress_block_from_view

    class _Empty:
        incumbent_trail: list = []
        best_bound = None
        gap = None
    assert _progress_block_from_view(_Empty()) is None

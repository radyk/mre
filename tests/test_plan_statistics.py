"""W2.2 Part B — the three rollups W2.1's screen named as gaps.

Written from the brief and from the defect history each rollup inherits:

  B1  late/on-time counts must DECOMPOSE (late + on_time = counted, verified by
      the consolidator) and must stay distinct from R-PD1's tardiness SPLIT,
      which decomposes a cost, not a count.
  B2  utilization must carry its DENOMINATOR in the record. 4B.20's defect was
      one denominator per surface; a ratio that travels without its definition
      invites the next surface to supply its own.
  B3  changeover minutes must be summed over EXACTLY the operation set the setup
      charge is billed on, or the plant's changeover time and its changeover
      bill describe different plans.
"""
from __future__ import annotations

import json

import pytest

from mre.modules import plan_statistics as ps


# ---------------------------------------------------------------------------
# B1 — late / on-time
# ---------------------------------------------------------------------------

def _outcome(lateness):
    return {"lateness_minutes": lateness}


def test_late_counts_decompose_exactly():
    c = ps.late_counts([_outcome(10), _outcome(-5), _outcome(0), _outcome(1)])
    assert c == {"late": 2, "on_time": 2, "counted": 4}
    assert c["late"] + c["on_time"] == c["counted"]


def test_a_demand_finishing_exactly_on_time_is_not_late():
    """lateness_minutes == 0 is ON TIME. The boundary is stated because the
    cockpit's own bar colouring already draws it here (`board.js`: > 0 is past
    due), and two surfaces disagreeing about the boundary is how a count stops
    matching the picture beside it."""
    assert ps.late_counts([_outcome(0)]) == {"late": 0, "on_time": 1, "counted": 1}


def test_an_empty_book_counts_zero_of_zero_and_says_so():
    assert ps.late_counts([]) == {"late": 0, "on_time": 0, "counted": 0}


def test_the_lateness_rule_is_written_down():
    assert "lateness_minutes > 0" in ps.LATENESS_DEFINITION


# ---------------------------------------------------------------------------
# B2 — utilization, and its denominator
# ---------------------------------------------------------------------------

def test_utilization_is_working_minutes_over_open_capacity():
    u = ps.utilization_by_resource({"R1": 300}, {"R1": [(0, 600)]})
    assert u["R1"]["working_minutes"] == 300
    assert u["R1"]["open_capacity_minutes"] == 600
    assert u["R1"]["utilization"] == pytest.approx(0.5)


def test_an_idle_resource_appears_at_zero_rather_than_vanishing():
    """A rollup whose members appear only when non-empty cannot be read as a set
    (docs/02 §4.4, applied to a map). An idle machine at 0% is a fact a planner
    wants."""
    u = ps.utilization_by_resource({}, {"R1": [(0, 600)]})
    assert u["R1"]["working_minutes"] == 0
    assert u["R1"]["utilization"] == 0.0


def test_no_calendar_means_no_ratio_never_a_zero_ratio():
    """THE THIRD STATE. An instrument that cannot see the denominator does not
    report a value — a 0.0 here would be a claim about the plant manufactured
    from a fact about our inputs (4B.23)."""
    u = ps.utilization_by_resource({"R1": 300}, None)
    assert u["R1"]["working_minutes"] == 300
    assert u["R1"]["open_capacity_minutes"] is None
    assert u["R1"]["utilization"] is None


def test_a_closed_resource_has_no_ratio_either():
    u = ps.utilization_by_resource({"R1": 0}, {"R1": []})
    assert u["R1"]["open_capacity_minutes"] == 0
    assert u["R1"]["utilization"] is None, "a ratio over zero capacity is undefined"


def test_the_denominator_is_written_down_in_full():
    """4B.20's fix, asserted: the definition names BOTH sides and the span."""
    d = ps.UTILIZATION_DEFINITION
    assert "working minutes" in d
    assert "open calendar minutes" in d
    assert "planning horizon" in d
    assert "excluding calendar pauses" in d, (
        "working time and elapsed span are different quantities (4B.20)")


# ---------------------------------------------------------------------------
# B3 — changeover minutes
# ---------------------------------------------------------------------------

def test_the_changeover_rule_names_the_same_op_set_the_charge_uses():
    d = ps.CHANGEOVER_DEFINITION
    assert "the same operation set the setup charge is billed on" in d
    assert "wip_status complete or in_progress" in d


# ---------------------------------------------------------------------------
# build() — the payload both assemblers read
# ---------------------------------------------------------------------------

def test_build_carries_every_figure_with_its_definition():
    s = ps.build(service_outcomes=[_outcome(5), _outcome(-1)],
                 working_minutes={"R1": 120}, changeover_minutes=45,
                 cal_windows={"R1": [(0, 480)]})
    assert s["late_demands"] == 1 and s["on_time_demands"] == 1
    assert s["demands_counted"] == 2
    assert s["changeover_minutes"] == 45
    # every figure arrives with the rule that produced it
    assert s["lateness_definition"] and s["changeover_definition"]
    assert s["utilization_definition"]
    assert s["utilization_by_resource"]["R1"]["utilization"] == pytest.approx(0.25)


def test_the_payload_is_json_serialisable():
    """It rides in `summary_metrics` on a persisted Schedule entity."""
    s = ps.build(service_outcomes=[], working_minutes={}, changeover_minutes=0,
                 cal_windows={})
    json.dumps(s)


# ---------------------------------------------------------------------------
# the evidence records
# ---------------------------------------------------------------------------

@pytest.fixture()
def rep(tmp_path):
    from mre.contracts.vocabularies import ModuleCode
    from mre.reporter import Reporter
    return Reporter.begin(module=ModuleCode.M7, purpose="stats test", config={},
                          trigger="test", snapshot_id="snap-s",
                          sink_dir=tmp_path / "runs")


def _records(rep, tmp_path):
    from mre.contracts.vocabularies import RunStatus
    rep.end(RunStatus.SUCCESS)
    out = []
    for f in (tmp_path / "runs").glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


def test_demands_counted_is_a_rollup_that_decomposes_exactly(rep, tmp_path):
    stats = ps.build(service_outcomes=[_outcome(5), _outcome(-1), _outcome(9)],
                     working_minutes={}, changeover_minutes=0, cal_windows={})
    ps.emit(rep, stats)
    recs = _records(rep, tmp_path)
    by_id = {r["record_id"]: r for r in recs if r.get("record_type") == "metric"}
    total = next(r for r in by_id.values() if r["name"] == ps.METRIC_DEMANDS)
    assert total["rollup_of"], "the count must decompose into late + on-time"
    parts = [by_id[i] for i in total["rollup_of"]]
    assert {p["name"] for p in parts} == {ps.METRIC_LATE, ps.METRIC_ON_TIME}
    assert sum(p["value"] for p in parts) == pytest.approx(total["value"])


def test_the_components_are_emitted_even_at_zero(rep, tmp_path):
    """docs/02 §4.4: a component present only when non-empty cannot be verified
    as a set, and an absent one reads as an unasked question."""
    stats = ps.build(service_outcomes=[_outcome(-1)], working_minutes={},
                     changeover_minutes=0, cal_windows={})
    ps.emit(rep, stats)
    names = {r["name"]: r["value"] for r in _records(rep, tmp_path)
             if r.get("record_type") == "metric"}
    assert names[ps.METRIC_LATE] == 0.0          # zero, and present
    assert names[ps.METRIC_CHANGEOVER] == 0.0


def test_every_utilization_record_carries_its_denominator(rep, tmp_path):
    """THE 4B.20 FIX, ON THE RECORD. Not in a docstring, not on the surface — on
    the metric, so a reader who has only the record still has the definition."""
    stats = ps.build(service_outcomes=[], working_minutes={"R1": 240},
                     changeover_minutes=0, cal_windows={"R1": [(0, 480)]})
    ps.emit(rep, stats)
    recs = [r for r in _records(rep, tmp_path) if r.get("record_type") == "metric"]
    util = next(r for r in recs if r["name"] == ps.METRIC_UTILIZATION)
    assert ps.UTILIZATION_DEFINITION in util["message"]
    assert util["unit"] == "ratio"
    assert util["subjects"] and util["subjects"][0]["entity_id"] == "R1"
    # …and both components ride beside it so the reader can check the arithmetic
    names = {r["name"] for r in recs}
    assert ps.METRIC_WORKING in names and ps.METRIC_OPEN_CAPACITY in names


def test_no_utilization_metric_is_emitted_without_a_denominator(rep, tmp_path):
    stats = ps.build(service_outcomes=[], working_minutes={"R1": 240},
                     changeover_minutes=0, cal_windows=None)
    ps.emit(rep, stats)
    names = {r["name"] for r in _records(rep, tmp_path)
             if r.get("record_type") == "metric"}
    assert ps.METRIC_WORKING in names, "the working minutes are still a fact"
    assert ps.METRIC_UTILIZATION not in names
    assert ps.METRIC_OPEN_CAPACITY not in names


def test_the_rollups_emit_no_finding_and_no_decision(rep, tmp_path):
    """A count is not a defect and not a deliberation — the same two refusals
    R-SP1 made, on a different record."""
    stats = ps.build(service_outcomes=[_outcome(9)], working_minutes={"R1": 1},
                     changeover_minutes=1, cal_windows={"R1": [(0, 10)]})
    ps.emit(rep, stats)
    kinds = {r.get("record_type") for r in _records(rep, tmp_path)}
    assert "finding" not in kinds and "decision" not in kinds


# ---------------------------------------------------------------------------
# B3 AT THE EXTRACTOR — the filter, not just the definition string
# ---------------------------------------------------------------------------

def _minimal_extract(ops, *, setup_fixed=10.0):
    """Run the real extractor over a hand-built one-resource placement."""
    from datetime import datetime, timezone

    from mre.modules.extractor import Extractor
    from mre.modules.solver_builder import SolveValues
    ref = datetime(2026, 1, 5, tzinfo=timezone.utc)
    sv = SolveValues(
        op_start_minutes={o["id"]: 0 for o in ops},
        op_end_minutes={o["id"]: 60 for o in ops},
        op_resource={o["id"]: "R1" for o in ops},
        wp_end_minutes={}, tardiness_minutes={}, horizon_start=ref)
    return Extractor().extract(
        solve_values=sv, snapshot_id="snap-x", operations=ops,
        workpackages=[], resources=[{"id": "R1", "name": "R1"}],
        fulfillments=[], demands=[],
        cost_model={"resource_rates": {"R1": 0.0},
                    "setup_cost_basis": {"fixed_per_setup": setup_fixed}},
        cal_windows={"R1": [(0, 600)]}, is_scenario=True)


def _op(oid, setup="PT30M", wip=None):
    o = {"id": oid, "workpackage_ref": "wp", "setup_duration": setup}
    if wip:
        o["wip_status"] = wip
    return o


def test_changeover_minutes_and_the_setup_CHARGE_share_one_population():
    """B3'S WHOLE POINT, ASSERTED AT THE SEAM.

    A setup that happened before the reference date is SUNK: it is excluded
    from the charge (docs/06 §5.13) and must be excluded from the minutes. If
    the two filters ever diverge, the plant's changeover time and its
    changeover bill describe different plans — and nothing else in the system
    would notice.
    """
    ops = [_op("a"), _op("b"), _op("c", wip="complete"), _op("d", wip="in_progress")]
    r = _minimal_extract(ops, setup_fixed=10.0)
    # the CHARGE counts 2 running ops
    assert r.cost_ledger["setup_cost"] == pytest.approx(20.0)
    assert r.cost_ledger["sunk_setup_cost"] == pytest.approx(20.0)
    # …and the MINUTES count the same 2, not all 4
    assert r.statistics["changeover_minutes"] == 60, (
        "changeover minutes and the setup charge disagree about which "
        "operations ran")


def test_changeover_minutes_take_the_resource_specific_setup_where_declared():
    """An op with a per-resource setup duration is billed its own, not the
    default — the same rule the assignment's own setup phase uses."""
    op = _op("a", setup="PT30M")
    op["resource_setup_durations"] = {"R1": "PT45M"}
    r = _minimal_extract([op])
    assert r.statistics["changeover_minutes"] == 45


def test_utilization_numerator_is_the_minutes_the_ledger_bills():
    """4B.20: working time, not elapsed span. Two 60-minute ops on one machine
    is 120 working minutes over the 600 open minutes the calendar declares."""
    r = _minimal_extract([_op("a"), _op("b")])
    u = r.statistics["utilization_by_resource"]["R1"]
    assert u["working_minutes"] == 120
    assert u["open_capacity_minutes"] == 600
    assert u["utilization"] == pytest.approx(0.2)


def test_the_statistics_ride_in_summary_metrics_for_the_monolithic_assembler():
    """ONE producer, two readers. The rolling assembler takes the payload off
    the view; this is the other door."""
    r = _minimal_extract([_op("a")])
    assert r.schedule["summary_metrics"]["statistics"] == r.statistics


def test_utilization_numerator_EXCLUDES_the_pauses_in_a_resumable_op():
    """4B.20's DISTINCTION, ON A SPECIMEN THAT CAN SEE IT.

    The test above uses unchunked ops, where working minutes and elapsed span
    are the same number — so it would pass against either definition, and a
    negative control proved exactly that (W2.2 NC9 stayed GREEN when the
    numerator was swapped for `end - start`). A resumable op is the only shape
    where the two differ: this one spans 0..600 but WORKS 120 minutes across two
    chunks, pausing over a closure. The numerator must be 120.
    """
    from datetime import datetime, timezone

    from mre.modules.extractor import Extractor
    from mre.modules.solver_builder import SolveValues
    ref = datetime(2026, 1, 5, tzinfo=timezone.utc)
    op = {"id": "a", "workpackage_ref": "wp", "setup_duration": "PT0S"}
    sv = SolveValues(
        op_start_minutes={"a": 0}, op_end_minutes={"a": 600},
        op_resource={"a": "R1"}, wp_end_minutes={}, tardiness_minutes={},
        horizon_start=ref,
        op_chunk_windows={"a": [(0, 60), (540, 600)]})   # 120 worked, 600 spanned
    r = Extractor().extract(
        solve_values=sv, snapshot_id="snap-x", operations=[op],
        workpackages=[], resources=[{"id": "R1", "name": "R1"}],
        fulfillments=[], demands=[],
        cost_model={"resource_rates": {"R1": 1.0},
                    "setup_cost_basis": {"fixed_per_setup": 0.0}},
        cal_windows={"R1": [(0, 600)]}, is_scenario=True)
    u = r.statistics["utilization_by_resource"]["R1"]
    assert u["working_minutes"] == 120, (
        "utilization counted the elapsed span, including the pauses — working "
        "time and elapsed span are different quantities (4B.20)")
    assert u["utilization"] == pytest.approx(0.2)
    # …and it is the SAME quantity the ledger billed for
    assert r.cost_ledger["production_cost"] == pytest.approx(120.0)

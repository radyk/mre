"""W2.2 Part A — the pricing bridge, and the self-proof that licenses it.

R-SP1 AMENDMENT 1 admits dollars "exactly when both endpoints are LEDGER-PRICED
PLACEMENTS — priced by the same extractor that prices the finished plan". The
load-bearing test in this file is therefore not that the bridge returns a number
but that it returns THE LEDGER'S OWN number:

    re-price the FINAL plan through the bridge and it must equal the shipped
    ledger total to the cent.

The bridge proves itself against the known answer before its novel answer — the
first plan's price — is trusted. Without that, "a nearly-real dollar" is a
fabricated dollar, and R-DP12 is back in play.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

UTC = timezone.utc
REF = datetime(2026, 1, 5, tzinfo=UTC)


@pytest.fixture(scope="module")
def solved(tmp_path_factory):
    """A real 40-order rolling window solved under deterministic law, plus the
    pricing inputs its own extractor was given. Everything below prices against
    THIS plant, so a first plan and a final plan are two answers to one
    question rather than two questions."""
    from generate_erp_dataset import generate

    from mre.modules.rolling_horizon import build_rolling_view, prepare_plant
    d = tmp_path_factory.mktemp("w22_pricing")
    generate(d / "sub", scenario="pilot_scale", orders=40, seed=1)
    plant = prepare_plant(d / "sub", d / "prep", reference_date=REF)
    view = build_rolling_view(plant, window_days=10, frozen_days=1,
                              deterministic=True, seed=42, persist=False)
    return plant, view


def test_the_first_incumbents_placements_are_captured(solved):
    """A1. One snapshot, at the first incumbent only."""
    _plant, view = solved
    assert view.incumbent_trail, "the specimen produced no trail"
    sv = view.first_incumbent_values
    assert sv is not None, "the first incumbent's placements were not captured"
    # a captured placement set is a real one: every placed op has a resource
    assert sv.op_start_minutes and sv.op_resource
    assert set(sv.op_resource) <= set(sv.op_start_minutes)


def test_THE_BRIDGE_SELF_PROOF_final_repriced_equals_the_shipped_ledger(solved):
    """A2, AND THE WHOLE LICENSE FOR PART A.

    The bridge marshals a dozen arguments into the extractor. If it forgets one
    — overtime windows, the calendar, the cost model's setup basis — it would
    still return a plausible number, and the first plan's price (which nobody
    can check independently) would be wrong in the same direction. So the bridge
    is pointed at the ONE placement set whose price is already known, and it
    must reproduce it TO THE CENT."""
    plant, view = solved
    inputs = view.pricing_inputs
    assert inputs is not None, "the view did not carry its pricing inputs"

    from mre.modules.plan_pricing import price_placements
    shipped = round(float(view.cost_ledger["total_cost"]), 2)
    repriced = price_placements(view.final_values, inputs)
    assert repriced == pytest.approx(shipped, abs=0.005), (
        f"the bridge re-priced the shipped plan at {repriced} but the ledger "
        f"says {shipped} — the bridge is marshalling something wrong, so its "
        f"price for the first plan is not to be trusted")


def test_the_first_plan_is_priced_and_is_not_cheaper_than_the_final(solved):
    """The novel answer, now licensed by the test above. The solver minimizes,
    so its first workable plan cannot be cheaper than the one it finished on —
    if it were, the search would have kept the cheaper one."""
    _plant, view = solved
    assert view.first_plan_cost is not None
    final = round(float(view.cost_ledger["total_cost"]), 2)
    assert view.first_plan_cost >= final - 0.005, (
        f"first plan {view.first_plan_cost} cheaper than final {final}")


def test_pricing_an_absent_placement_set_returns_none_not_zero(solved):
    from mre.modules.plan_pricing import price_placements
    _plant, view = solved
    assert price_placements(None, view.pricing_inputs) is None


def test_A_PLACEMENT_SET_THAT_IS_NOT_THIS_PLAN_IS_REFUSED_NOT_PRICED(solved):
    """THE DEFECT A GUARD FOUND BY ASSERTING THE OPPOSITE.

    This test was written expecting the extractor to FAIL on a degenerate
    placement set. It does not — it prices it, as a plan where every demand is
    late, and returns a confident number (1520.00 on this window). A capture
    that silently came back empty or partial would therefore not raise: it would
    produce a plausible first-plan price that is not a price of this plan at
    all, and the money story would compare the solver's plan against a fiction.

    So the bridge checks COVERAGE — the amendment's "both endpoints are
    placements of the same plan", enforced instead of assumed — and refuses.
    """
    from mre.modules.plan_pricing import price_placements
    _plant, view = solved

    class _Empty:
        op_start_minutes: dict = {}
        op_end_minutes: dict = {}
        op_resource: dict = {}
        op_chunk_windows: dict = {}
        wp_end_minutes: dict = {}
        tardiness_minutes: dict = {}
        horizon_start = REF

    required = set(view.final_values.op_resource)
    # unchecked, the extractor prices it rather than refusing — the fact itself
    unchecked = price_placements(_Empty(), view.pricing_inputs)
    assert unchecked is not None, (
        "the premise of this guard changed: a placement set covering nothing "
        "now fails to price, so the coverage check may no longer be load-bearing")
    # checked, it is refused
    assert price_placements(_Empty(), view.pricing_inputs,
                            require_ops=required) is None
    # and the real capture passes the same check
    assert price_placements(view.first_incumbent_values, view.pricing_inputs,
                            require_ops=required) is not None


def test_pricing_writes_no_evidence_and_no_entities(solved, tmp_path):
    """A hypothetical plan mints no assignment Decisions and no Schedule. The
    bridge passes reporter=None and snapshot_writer=None, and this asserts the
    consequence rather than the argument: a reporter handed to the run around it
    stays empty."""
    from mre.contracts.vocabularies import ModuleCode, RunStatus
    from mre.modules.plan_pricing import price_placements
    from mre.reporter import Reporter
    _plant, view = solved
    rep = Reporter.begin(module=ModuleCode.M7, purpose="pricing isolation",
                         config={}, trigger="test", snapshot_id="snap-p",
                         sink_dir=tmp_path / "runs")
    price_placements(view.first_incumbent_values, view.pricing_inputs)
    rep.end(RunStatus.SUCCESS)
    import json
    kinds = []
    for f in (tmp_path / "runs").glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                kinds.append(json.loads(line).get("record_type"))
    assert "decision" not in kinds and "metric" not in kinds

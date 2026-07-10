"""mid_replan scenario (docs/06 §5.13, session 2.3 CU4) — reschedule from a
point. The generator's mid_replan submission carries WIP; this proves the
capability end to end, deterministically:

  * completed ops free capacity — the counterfactual (strip the WIP and the
    same plant carries more tardiness) is the price-bought-something rule
    applied to capacity;
  * the rescue order is on time only because a completed op vacated its window;
  * the in-flight fixed op holds its ground — the future op starts at/after
    the in-flight remaining;
  * the completed op produces no assignment (it is history, not scheduled);
  * warm-start: a re-solve hinted from the prior schedule never hints the
    fixed/in-flight ops (they have no variables to move).

Deterministic mode throughout (--solver-workers 1 --solver-seed 0).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from tools.generate_erp_dataset import generate

UTC = timezone.utc
SNAP = "snap-run"
REF = datetime(2026, 1, 5, tzinfo=UTC)


def _run_pipeline(sub: Path, out: Path) -> None:
    rc = mre_main([
        "--submission", str(sub), "--out", str(out),
        "--snapshot-id", SNAP, "--time-limit", "30",
        "--solver-workers", "1", "--solver-seed", "0",
    ])
    assert rc == 0, f"pipeline exit {rc}"


def _load(out: Path):
    from mre.modules.snapshot_store import SnapshotStore
    return SnapshotStore(out / "snapshots").load_snapshot(SNAP)


def _order_of(reader, demand_id: str) -> str:
    d = reader.get_entity(demand_id) or {}
    return next((r["value"] for r in d.get("external_refs", [])
                 if r.get("type") == "order_id"), demand_id)


def _lateness_by_order(reader) -> dict[str, float]:
    """order_id → lateness minutes (from ServiceOutcome, the authoritative
    record — never recomputed)."""
    out: dict[str, float] = {}
    for svc in reader.iter_entities("serviceoutcome"):
        order = _order_of(reader, svc["demand_ref"])
        lat = svc.get("lateness_minutes")
        if lat is None:
            from mre.modules.scenario import _parse_duration_minutes
            lat = _parse_duration_minutes(svc.get("lateness"))
        out[order] = lat
    return out


def _summary(reader) -> dict:
    scheds = list(reader.iter_entities("schedule"))
    return scheds[0]["summary_metrics"] if scheds else {}


def _total_tardiness(reader) -> float:
    return _summary(reader).get("tardiness_cost", 0.0)


def _assignments_by_order(reader):
    """order_id → {machine_id, start_min} from Assignment entities."""
    ful_wp = {f["workpackage_ref"]: f["demand_ref"]
              for f in reader.iter_entities("fulfillment")}
    out = {}
    for a in reader.iter_entities("assignment"):
        did = ful_wp.get(a["workpackage_ref"])
        if did is None:
            continue
        order = _order_of(reader, did)
        ra = a.get("resource_assignments") or []
        rid = ra[0]["resource_ref"] if ra else None
        runs = (a.get("phase_windows") or {}).get("run") or []
        start = runs[0]["start"] if runs else None
        out[order] = {"resource_ref": rid, "start": start}
    return out


@pytest.fixture(scope="module")
def replan(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("mid_replan")
    sub = tmp / "sub"
    truth = generate(sub, scenario="mid_replan", seed=1)["mid_replan"]

    out_wip = tmp / "out_wip"
    _run_pipeline(sub, out_wip)

    # Counterfactual: the SAME plant with the WIP stripped (the "prior"
    # blank-slate plan). Deleting wip_status.csv makes every order not_started.
    sub_nowip = tmp / "sub_nowip"
    import shutil
    shutil.copytree(sub, sub_nowip)
    (sub_nowip / "wip_status.csv").unlink()
    out_nowip = tmp / "out_nowip"
    _run_pipeline(sub_nowip, out_nowip)

    return truth, _load(out_wip), _load(out_nowip)


# ---------------------------------------------------------------------------
# Truth-manifest assertions
# ---------------------------------------------------------------------------

def test_completed_op_produces_no_assignment(replan):
    truth, wip, _ = replan
    orders = _assignments_by_order(wip)
    assert truth["done_order_id"] not in orders, (
        "the completed order's op must not be scheduled — it is history"
    )


def test_rescue_order_on_time_with_wip(replan):
    truth, wip, _ = replan
    lateness = _lateness_by_order(wip)
    assert lateness[truth["rescue_order_id"]] <= 0, (
        f"rescue order should be on time once the completed op frees the "
        f"window; lateness={lateness[truth['rescue_order_id']]}"
    )


def test_completion_frees_capacity_counterfactual(replan):
    """price-bought-something on capacity: strip the WIP and the same plant
    carries strictly more tardiness (the completed op's window is contested
    again, and the rescue order specifically slips)."""
    truth, wip, nowip = replan
    assert _total_tardiness(wip) < _total_tardiness(nowip), (
        f"WITH wip tardiness {_total_tardiness(wip)} should be < WITHOUT "
        f"{_total_tardiness(nowip)}"
    )
    assert _lateness_by_order(nowip)[truth["rescue_order_id"]] > 0, (
        "without WIP the rescue order must be late (window contested)"
    )


def test_in_flight_op_holds_future_starts_after_remaining(replan):
    """The fixed in-flight op stays put; the only movable op on its resource
    (the future order) starts at/after the in-flight remaining."""
    truth, wip, _ = replan
    orders = _assignments_by_order(wip)
    fut = orders[truth["future_order_id"]]
    assert fut["resource_ref"] == truth["second_resource"] or \
        _machine_name(wip, fut["resource_ref"]) == truth["second_resource"]
    start_min = int((datetime.fromisoformat(fut["start"].replace("Z", "+00:00")) - REF)
                    .total_seconds() // 60)
    assert start_min >= truth["inflight_remaining_minutes"], (
        f"future op starts at {start_min} min; in-flight remaining is "
        f"{truth['inflight_remaining_minutes']} — the fixed op did not hold"
    )


def _machine_name(reader, resource_ref: str) -> str:
    r = reader.get_entity(resource_ref) or {}
    return next((e["value"] for e in r.get("external_refs", [])
                 if e.get("type") == "resource_id"), resource_ref)


# ---------------------------------------------------------------------------
# Sunk-setup ledger (CU0.5): a completed / in-flight op's setup already
# happened and must not be re-charged in the movable objective.
# ---------------------------------------------------------------------------

def test_mid_replan_ledger_does_not_recharge_sunk_setups(replan):
    """The WIP run bills setup only for ops that actually run (RESCUE, FUTURE);
    the completed (DONE) and in-flight (INFLIGHT) ops carry SUNK setup, reported
    on a separate non-decomposing line. Stripping the WIP re-charges all four as
    new setups — the counterfactual proving the WIP run saved the sunk portion."""
    truth, wip, nowip = replan
    wip_s, nowip_s = _summary(wip), _summary(nowip)

    # The movable setup_cost is strictly lower WITH the WIP (sunk ops dropped).
    assert wip_s["setup_cost"] < nowip_s["setup_cost"], (
        f"WITH wip setup {wip_s['setup_cost']} should be < WITHOUT "
        f"{nowip_s['setup_cost']} — sunk setups must not be re-charged"
    )
    # The sunk line is present and positive (DONE + INFLIGHT each had a setup).
    assert wip_s.get("sunk_setup_cost", 0.0) > 0, (
        "the WIP run must report a sunk_setup_cost line"
    )
    # WIP-less run never observes WIP → no sunk line at all.
    assert "sunk_setup_cost" not in nowip_s

    # Decomposition still verifies EXACTLY in the WIP run — the sunk line is
    # additive/informational and is NOT part of the total.
    parts = wip_s["production_cost"] + wip_s["setup_cost"] + wip_s["tardiness_cost"]
    assert abs(parts - wip_s["total_cost"]) < 1e-6


# ---------------------------------------------------------------------------
# Warm-start: the re-solve never hints the fixed/in-flight ops
# ---------------------------------------------------------------------------

def test_warm_start_never_hints_fixed_or_in_flight_ops(replan):
    """The mid_replan re-solve hints from the prior (no-WIP) schedule. The
    completed and in-flight ops have NO variables in the WIP model, so they
    can never be hinted-and-moved; only future movable ops are hinted."""
    from mre.modules.calendar_utils import compute_horizon, flatten_all_calendars
    from mre.modules.solver_builder import SolverBuilder, apply_solution_hints

    truth, wip, nowip = replan

    # Rebuild the WIP model from the WIP snapshot (mirrors the pipeline).
    demands = list(wip.iter_entities("demand"))
    fuls = list(wip.iter_entities("fulfillment"))
    wps = list(wip.iter_entities("workpackage"))
    ops = list(wip.iter_entities("operation"))
    edges = list(wip.iter_entities("precedenceedge"))
    resources = list(wip.iter_entities("resource"))
    pools = list(wip.iter_entities("resourcepool"))
    calendars = list(wip.iter_entities("calendar"))
    constraints = list(wip.iter_entities("constraint"))
    cost_model = next(iter(wip.iter_entities("costmodel")))

    hs, he = compute_horizon(demands)
    hs = max(hs, REF)
    flat = flatten_all_calendars(calendars, hs, he)
    model, vm = SolverBuilder(reference_date=REF).build(
        wps + ops + edges, resources + pools, flat, fuls + demands,
        constraints, cost_model,
    )

    # The prior schedule's assignments (no-WIP run) are the hint source.
    prior_assignments = list(nowip.iter_entities("assignment"))
    stats = apply_solution_hints(model, vm, prior_assignments)

    # Completed + in-flight ops have no start variable → unhintable by
    # construction (this is the structural guarantee, not luck).
    complete_ops = [o["id"] for o in ops if o.get("wip_status") == "complete"]
    inflight_ops = [o["id"] for o in ops if o.get("wip_status") == "in_progress"]
    assert complete_ops and inflight_ops, "fixture must contain both WIP kinds"
    for oid in complete_ops + inflight_ops:
        assert oid not in vm.op_start, (
            f"fixed/in-flight op {oid} has a variable — it could be moved"
        )
    # Future movable ops WERE hinted from the prior plan.
    assert stats["hinted_operations"] > 0

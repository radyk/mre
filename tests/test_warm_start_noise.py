"""Warm-start acceptance: the Phase-1 exit audit's noise case (docs/07 Phase 2).

The exit audit found that a 2-order unbatch what-if on the messy generated
plant reported hundreds of assignment moves — search noise (plus a
string-format comparison bug in the differ, fixed alongside warm-start),
not consequences of the modification. Acceptance here, all in deterministic
mode (workers=1, seed pinned; inherited by the scenario via
derive_base_context):

  (a) the unbatch scenario's untouched-operation moves are bounded small;
  (b) the diff is stable across repeated scenario runs;
  (c) counterfactual (2026-07-12 rule): the warm start buys the stability —
      a cold (unhinted) run of the same scenario moves at least as much;
  (d) warm_start_hints telemetry is recorded and the hints were accepted.

Slow (--runslow): generates and solves the 200-order messy_realistic plant.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.modules.scenario import Scenario, ScenarioRunner, SuppressMerge, derive_base_context
from mre.modules.snapshot_store import SnapshotStore
from tools.generate_erp_dataset import generate

SNAP_ID = "snap-run"


@pytest.fixture(scope="module")
def messy_base(tmp_path_factory):
    """Deterministic base run of messy_realistic seed 23 (the audit's seed)
    under merge_by_family_v1, so an unbatchable merged WP exists."""
    tmp = tmp_path_factory.mktemp("warm_start_noise")
    sub_dir = tmp / "submission"
    out_dir = tmp / "out"
    generate(sub_dir, scenario="messy_realistic", seed=23)
    exit_code = mre_main([
        "--submission", str(sub_dir), "--out", str(out_dir),
        "--policy", "merge_by_family_v1",
        "--time-limit", "120", "--solver-workers", "1", "--solver-seed", "0",
    ])
    assert exit_code == 0
    return tmp, out_dir


def _merged_wp_orders(reader) -> list[str]:
    """External order ids of the demands in one merged (2+ fulfillment) WP."""
    by_wp: dict[str, list[str]] = {}
    for ful in reader.iter_entities("fulfillment"):
        by_wp.setdefault(ful["workpackage_ref"], []).append(ful["demand_ref"])
    merged = next((dids for dids in by_wp.values() if len(dids) >= 2), None)
    assert merged, "expected at least one merged WP under merge_by_family_v1"
    demands = {d["id"]: d for d in reader.iter_entities("demand")}
    orders = []
    for did in merged[:2]:
        ext = next(e["value"] for e in demands[did]["external_refs"]
                   if e["type"] == "order_id")
        orders.append(ext)
    return orders


def _run_scenario(tmp: Path, out_dir: Path, orders: list[str],
                  label: str, warm_start: bool):
    store = SnapshotStore(out_dir / "snapshots")
    ctx = derive_base_context(out_dir / "runs")
    runner = ScenarioRunner(
        store, tmp / f"scenario_runs_{label}",
        time_limit_seconds=ctx.get("time_limit", 120.0),
        base_context=ctx,
        warm_start=warm_start,
    )
    return runner.run(Scenario(base_snapshot_id=SNAP_ID,
                               modifications=[SuppressMerge(demand_refs=orders)]))


def _events(runs_dir: Path, status_text: str) -> list[dict]:
    out = []
    for f in runs_dir.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("record_type") == "event" and \
                    rec.get("status_text") == status_text:
                out.append(rec)
    return out


@pytest.mark.slow
class TestWarmStartNoiseCase:
    def test_unbatch_moves_bounded_stable_and_priced_by_counterfactual(
        self, messy_base,
    ):
        tmp, out_dir = messy_base
        reader = SnapshotStore(out_dir / "snapshots").load_snapshot(SNAP_ID)
        orders = _merged_wp_orders(reader)

        warm1 = _run_scenario(tmp, out_dir, orders, "warm1", warm_start=True)
        warm2 = _run_scenario(tmp, out_dir, orders, "warm2", warm_start=True)
        cold = _run_scenario(tmp, out_dir, orders, "cold", warm_start=False)

        # (a) untouched operations essentially stay put. total_changed only
        # counts ops present in BOTH schedules — the restructured WPs' ops
        # have new uuid5 ids — so this IS the untouched-operation move count.
        moves_warm = warm1.diff["assignment_moves"]["total_changed"]
        assert moves_warm <= 10, (
            f"unbatch moved {moves_warm} untouched operations under "
            f"warm-start: {warm1.diff['assignment_moves']['notable']}"
        )

        # (b) deterministic mode: repeated runs produce the same diff.
        assert warm1.diff["cost_delta"] == warm2.diff["cost_delta"]
        assert warm1.diff["service_deltas"] == warm2.diff["service_deltas"]
        assert (warm1.diff["assignment_moves"]["total_changed"]
                == warm2.diff["assignment_moves"]["total_changed"])

        # (c) the counterfactual: cold search is allowed to be equally quiet
        # (CP-SAT may land on the same optimum) but must never be quieter —
        # and the audit's historical figure was two orders of magnitude
        # noisier. The warm start's price bought the ceiling.
        moves_cold = cold.diff["assignment_moves"]["total_changed"]
        assert moves_warm <= moves_cold

        # (d) hint telemetry recorded, and nearly all shared ops hinted.
        hint_events = _events(tmp / "scenario_runs_warm1", "warm_start_hints")
        assert hint_events
        payload = hint_events[-1]["payload"]
        assert payload["hinted_operations"] > 0
        assert payload["hinted_operations"] > payload["skipped_structure_changed"]
        # solution_info (CP-SAT's hint-acceptance report) is present
        solves = _events(tmp / "scenario_runs_warm1", "solve_complete")
        assert solves and "solution_info" in solves[-1]["payload"]

"""multi_route scenario (docs/05 B2, session 3.1 CU1) — capability-routed
generated data with GENUINE routing alternatives. This is the interim-A
prerequisite the frontend bake-off proved generated data lacked (VERDICT.md
"honest caveat about the fixture": every op routed to exactly one resource, so
no legal cross-machine move and no priced ghost existed).

Proven end to end, deterministically (--solver-workers 1 --solver-seed 42):

  * STRUCTURE — a counted number of operations have >1 eligible resource
    (the adapter groups multiple routing_lines rows sharing one
    (route_id, sequence) into one OperationSpec whose ResourceRequirement is
    EXPLICIT_SET over the whole set); at least one such op sits in a
    precedence chain; and at least one has an eligible alternative on a
    DIFFERENT-RATE machine (a nonzero Tier-1 ghost price — read off the
    contract-1.2 interaction payload: working_min × Δrate).
  * POOL — the solution pool built on the deterministic solve places at least
    one operation cross-machine (the Tier-1 ghost precondition).
  * COUNTERFACTUAL (price-bought-something) — collapsing the scenario to
    single-eligibility (each op's route reduced to one eligible row) drives
    the pool's cross-machine count to zero and lowers its diversity profile.
    This proves the routing alternatives are REAL, not decorative.

The pool + counterfactual solves are slow-marked (two pipeline solves + two
pools); the structural checks run in the default suite.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.modules.snapshot_store import SnapshotStore
from mre.modules.solution_pool import warm_solution_pool
from tools.generate_erp_dataset import generate

SNAP = "snap-mr"


def _run_pipeline(sub: Path, out: Path, snap: str = SNAP) -> None:
    rc = mre_main([
        "--submission", str(sub), "--out", str(out), "--snapshot-id", snap,
        "--time-limit", "45", "--solver-workers", "1", "--solver-seed", "42",
    ])
    assert rc == 0, f"pipeline exit {rc}"


def _eligible_sets(reader) -> dict[str, list[str]]:
    """operation instance id → the resource_refs of its (single, explicit_set)
    ResourceRequirement — the eligible set the adapter grouped from multiple
    routing_lines rows (docs/05 B2)."""
    out: dict[str, list[str]] = {}
    for op in reader.iter_entities("operation"):
        reqs = op.get("resource_requirements") or []
        refs = (reqs[0].get("resource_refs") or []) if reqs else []
        out[op["id"]] = refs
    return out


def _resource_rate(reader, cost_model: dict, resource_id: str) -> float:
    """The effective $/h for a resource: its per-resource rate override else
    the cost-model default (the same source the solver prices against)."""
    rates = (cost_model.get("resource_rates") or {})
    if resource_id in rates:
        return float(rates[resource_id])
    return float(cost_model.get("default_resource_rate_per_hour", 0.0))


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("multi_route")
    sub = tmp / "sub"
    truth = generate(sub, scenario="multi_route", seed=7)["multi_route"]
    out = tmp / "out"
    _run_pipeline(sub, out)
    reader = SnapshotStore(out / "snapshots").load_snapshot(SNAP)
    return truth, sub, out, reader


# ---------------------------------------------------------------------------
# Structure — the generated scenario really carries routing alternatives
# ---------------------------------------------------------------------------

def test_multi_eligible_ops_exist(base):
    """The adapter grouped multiple routing_lines rows sharing one
    (route_id, sequence) into one OperationSpec with a multi-element eligible
    set — so scheduled operation instances carry >1 eligible resource."""
    truth, _, _, reader = base
    assert truth["multi_eligible_op_count"] >= 3
    elig = _eligible_sets(reader)
    multi = [oid for oid, refs in elig.items() if len(refs) > 1]
    assert multi, "no scheduled op has more than one eligible resource"
    assert max(len(refs) for refs in elig.values()) == truth["max_eligible_alternatives"]


def test_a_multi_eligible_op_is_in_a_precedence_chain(base):
    truth, _, _, reader = base
    assert truth["expected_multi_eligible_in_precedence_chain"]
    elig = _eligible_sets(reader)
    multi_specs = set()  # spec ids of multi-eligible ops
    spec_of = {}
    for op in reader.iter_entities("operation"):
        spec_of[op["id"]] = op.get("spec_ref")
        if len(elig.get(op["id"], [])) > 1:
            multi_specs.add(op.get("spec_ref"))
    edges = list(reader.iter_entities("precedenceedge"))
    assert edges, "no precedence edges in the snapshot"
    chained_specs = {e["predecessor"] for e in edges} | {e["successor"] for e in edges}
    assert multi_specs & chained_specs, (
        "no multi-eligible op appears in the precedence graph"
    )


def test_a_cross_machine_move_carries_a_nonzero_price(base):
    """The price-bought-something guarantee: some scheduled multi-eligible op
    has an eligible alternative on a machine with a DIFFERENT cost rate, so a
    cross-machine move there costs working_min × Δrate ≠ 0 — a real Tier-1
    ghost price, independent of the pool's stochastic choice."""
    truth, _, _, reader = base
    assert truth["expected_nonzero_ghost_price"]
    cost_model = next(iter(reader.iter_entities("costmodel")))
    elig = _eligible_sets(reader)
    found = False
    for refs in elig.values():
        rates = {_resource_rate(reader, cost_model, r) for r in refs}
        if len(rates) > 1:  # eligible set spans ≥2 distinct rates
            assert max(rates) - min(rates) > 0
            found = True
    assert found, "no scheduled op has a different-rate eligible alternative"


# ---------------------------------------------------------------------------
# Pool — the alternatives are actually reachable near-optimum (slow)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pool(base):
    _, _, out, _ = base
    return warm_solution_pool(
        out_dir=out, snapshot_id=SNAP, base_schedule_id="s", run_id="run-mr",
        k=5, member_time_limit_s=8.0,
    )


@pytest.mark.slow
def test_pool_places_ops_cross_machine(base, pool):
    truth, _, _, _ = base
    assert pool.status == "ready"
    assert pool.diversity["cross_machine_ops"] >= truth["expected_pool_cross_machine_ops_ge"], (
        f"pool cross_machine_ops={pool.diversity['cross_machine_ops']} — "
        f"the routing alternatives are not being exercised near-optimum"
    )


@pytest.mark.slow
def test_single_eligibility_collapse_kills_cross_machine_diversity(base, pool, tmp_path_factory):
    """The counterfactual: collapse the scenario to single-eligibility (keep
    only the FIRST routing_lines row per (route_id, sequence)) and the pool's
    cross-machine count falls to zero — the diversity profile provably
    changes. This is the proof the routing alternatives bought something."""
    truth, sub, _, _ = base
    tmp = tmp_path_factory.mktemp("multi_route_collapsed")

    # Copy the submission and collapse routing_lines to one row per (route,seq).
    import csv
    import shutil
    csub = tmp / "sub"
    shutil.copytree(sub, csub)
    rows = list(csv.DictReader(open(csub / "routing_lines.csv")))
    seen: set[tuple[str, str]] = set()
    kept = []
    for r in rows:
        key = (r["route_id"], r["sequence"])
        if key in seen:
            continue
        seen.add(key)
        kept.append(r)
    with open(csub / "routing_lines.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(kept)

    cout = tmp / "out"
    _run_pipeline(csub, cout, snap="snap-mr-col")
    cpool = warm_solution_pool(
        out_dir=cout, snapshot_id="snap-mr-col", base_schedule_id="s",
        run_id="run-col", k=5, member_time_limit_s=8.0,
    )
    assert cpool.diversity["cross_machine_ops"] == truth["expected_collapse_cross_machine_ops"] == 0, (
        "collapsed (single-eligibility) pool must have no cross-machine moves"
    )
    # The diversity PROFILE changed: the multi-eligible pool crossed machines,
    # the collapsed one cannot (every op has exactly one eligible resource).
    assert pool.diversity["cross_machine_ops"] > cpool.diversity["cross_machine_ops"]

"""WIP landing (docs/06 §5.13, session 2.3 CU2): the IDS adapter lands
observed shop-floor state on Demand.wip_operations, and the Planner projects
it onto Operation fields and the WorkPackage.state seam — with TRUTHFUL
provenance (observed values cite real wip_status.csv rows; the computed
remaining duration is derived, never a constant under an observed sidecar —
the yield_factor false-observed anti-pattern, docs/04 2026-07-12).

Adapter → Planner directly (no gate/validator needed for the landing).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.modules.adapter import _stable_id
from mre.modules.ids_adapter import IDSAdapter
from mre.modules.planner import Planner
from mre.modules.snapshot_store import SnapshotStore
from mre.reporter import Reporter
from tools.generate_erp_dataset import generate

SNAP = "wip-snap"
_WIP_COLS = ["order_id", "sequence", "status", "actual_start",
             "actual_resource_id", "remaining_minutes", "quantity_complete"]


def _shape(sub: Path):
    """(orders, order_id→sorted seqs, (route,seq)→resource_id)."""
    with open(sub / "orders.csv", encoding="utf-8-sig", newline="") as f:
        orders = list(csv.DictReader(f))
    with open(sub / "routing_lines.csv", encoding="utf-8-sig", newline="") as f:
        lines = list(csv.DictReader(f))
    seqs_by_route: dict[str, list[int]] = {}
    res: dict[tuple[str, str], str] = {}
    for rl in lines:
        if rl.get("active") == "1":
            seqs_by_route.setdefault(rl["route_id"], []).append(int(rl["sequence"]))
            res[(rl["route_id"], rl["sequence"])] = rl["resource_id"]
    order_seqs = {o["order_id"]: sorted(seqs_by_route.get(o["route_id"], []))
                  for o in orders}
    return orders, order_seqs, res


def _order_with_two_ops(orders, order_seqs):
    for o in orders:
        if len(order_seqs[o["order_id"]]) >= 2:
            return o
    raise AssertionError("no order with >= 2 operations in fixture")


def _write_wip(sub: Path, rows: list[dict], basis: str) -> None:
    with open(sub / "wip_status.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_WIP_COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in _WIP_COLS})
    manifest = json.loads((sub / "manifest.json").read_text(encoding="utf-8"))
    manifest["semantics"]["wip_progress_basis"] = basis
    (sub / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _run_adapter_and_planner(sub: Path, tmp: Path):
    store = SnapshotStore(tmp / "snapshots")
    runs = tmp / "runs"
    manifest = json.loads((sub / "manifest.json").read_text(encoding="utf-8"))
    a_rep = Reporter.begin(module=ModuleCode.M1, purpose="wip adapter", config={},
                           trigger="test", snapshot_id=SNAP, sink_dir=runs)
    IDSAdapter(submission_dir=sub, manifest=manifest).run(SNAP, store, a_rep)
    a_rep.end(RunStatus.SUCCESS)
    p_rep = Reporter.begin(module=ModuleCode.M4, purpose="wip planner", config={},
                           trigger="test", snapshot_id=SNAP, sink_dir=runs)
    Planner(policy="identity_v1").run(SNAP, store, p_rep)
    p_rep.end(RunStatus.SUCCESS)
    return store.load_snapshot(SNAP)


def _demand_by_order(reader, order_id: str) -> dict:
    for d in reader.iter_entities("demand"):
        if any(r.get("type") == "order_id" and r.get("value") == order_id
               for r in d.get("external_refs", [])):
            return d
    raise AssertionError(f"no demand for order {order_id}")


def _ops_by_seq(reader, demand_id: str) -> "tuple[dict[int, dict], str]":
    wp_id = next(f["workpackage_ref"] for f in reader.iter_entities("fulfillment")
                 if f["demand_ref"] == demand_id)
    return {o["sequence"]: o for o in reader.iter_entities("operation")
            if o["workpackage_ref"] == wp_id}, wp_id


# ---------------------------------------------------------------------------
# remaining_minutes basis: complete + in_progress landing
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def wip_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("wip_min")
    sub = tmp / "sub"
    generate(sub, scenario="clean_small", seed=1)
    orders, order_seqs, res = _shape(sub)
    o = _order_with_two_ops(orders, order_seqs)
    seqs = order_seqs[o["order_id"]]
    route = o["route_id"]
    rows = [
        {"order_id": o["order_id"], "sequence": str(seqs[0]), "status": "complete",
         "actual_start": "2026-01-02T08:00:00",
         "actual_resource_id": res[(route, str(seqs[0]))]},
        {"order_id": o["order_id"], "sequence": str(seqs[1]), "status": "in_progress",
         "actual_start": "2026-01-02T14:00:00",
         "actual_resource_id": res[(route, str(seqs[1]))],
         "remaining_minutes": "240"},
    ]
    _write_wip(sub, rows, basis="remaining_minutes")
    reader = _run_adapter_and_planner(sub, tmp)
    return reader, o, seqs, res, route


def test_demand_carries_wip_observations(wip_run):
    reader, o, seqs, res, route = wip_run
    d = _demand_by_order(reader, o["order_id"])
    obs = {w["sequence"]: w for w in d["wip_operations"]}
    assert set(obs) == {seqs[0], seqs[1]}
    assert obs[seqs[0]]["status"] == "complete"
    assert obs[seqs[1]]["status"] == "in_progress"
    # canonical terms only — spec_ref/actual_resource_ref are canonical ids
    assert obs[seqs[0]]["spec_ref"] and "-" in obs[seqs[0]]["spec_ref"]
    assert obs[seqs[1]]["actual_resource_ref"] is not None


def test_demand_wip_provenance_is_observed_citing_rows(wip_run):
    reader, o, seqs, res, route = wip_run
    d = _demand_by_order(reader, o["order_id"])
    prov = reader.get_provenance(d["id"], "wip_operations")
    assert prov["provenance_class"] == "observed"
    # cites the actual source rows, not a bare column name
    assert "rows" in prov["payload"]["source_field"]


def test_completed_op_carries_observed_actuals(wip_run):
    reader, o, seqs, res, route = wip_run
    d = _demand_by_order(reader, o["order_id"])
    ops, _ = _ops_by_seq(reader, d["id"])
    op = ops[seqs[0]]
    assert op["wip_status"] == "complete"
    assert op["observed_start"] is not None
    # observed_resource_ref is the CANONICAL id (ERP ids live only in
    # external_refs) — the adapter resolves actual_resource_id through the
    # identity map
    assert op["observed_resource_ref"] == _stable_id("resource", res[(route, str(seqs[0]))])
    # nothing remains on a complete op; that zero is DERIVED from status,
    # not observed (there is no observed "remaining" column for it)
    assert reader.get_provenance(op["id"], "wip_status")["provenance_class"] == "observed"
    assert reader.get_provenance(op["id"], "observed_start")["provenance_class"] == "observed"
    assert reader.get_provenance(op["id"], "remaining_duration")["provenance_class"] == "derived"


def test_in_progress_op_remaining_minutes_is_observed(wip_run):
    reader, o, seqs, res, route = wip_run
    d = _demand_by_order(reader, o["order_id"])
    ops, _ = _ops_by_seq(reader, d["id"])
    op = ops[seqs[1]]
    assert op["wip_status"] == "in_progress"
    assert op["observed_start"] is not None
    assert op["observed_resource_ref"] == _stable_id("resource", res[(route, str(seqs[1]))])
    # remaining_minutes = 240 → PT4H; the plant reported it, so OBSERVED
    assert op["remaining_duration"] == "PT4H"
    rp = reader.get_provenance(op["id"], "remaining_duration")
    assert rp["provenance_class"] == "observed"


def test_workpackage_state_is_in_progress_observed(wip_run):
    reader, o, seqs, res, route = wip_run
    d = _demand_by_order(reader, o["order_id"])
    _, wp_id = _ops_by_seq(reader, d["id"])
    wp = reader.get_entity(wp_id)
    assert wp["state"] == "in_progress"          # one complete, one running
    prov = reader.get_provenance(wp_id, "state")
    assert prov["provenance_class"] == "observed"
    assert "rows" in prov["payload"]["source_field"]


def test_blank_slate_demand_has_defaulted_wip(wip_run):
    """An order with no WIP row: operations carry no observation and the WP
    stays planned — DEFAULTED provenance, never a false observed sidecar."""
    reader, o, seqs, res, route = wip_run
    other = next(d for d in reader.iter_entities("demand")
                 if not d["wip_operations"])
    prov = reader.get_provenance(other["id"], "wip_operations")
    assert prov["provenance_class"] == "defaulted"
    ops, wp_id = _ops_by_seq(reader, other["id"])
    op = next(iter(ops.values()))
    assert op["wip_status"] is None
    assert reader.get_provenance(op["id"], "wip_status")["provenance_class"] == "defaulted"
    assert reader.get_entity(wp_id)["state"] == "planned"
    assert reader.get_provenance(wp_id, "state")["provenance_class"] == "defaulted"


# ---------------------------------------------------------------------------
# quantity_complete basis: the remainder arithmetic is DERIVED (the
# price-bought / anti-pattern guard — a computed value never claims observed)
# ---------------------------------------------------------------------------

def test_in_progress_remaining_from_quantity_complete_is_derived(tmp_path):
    sub = tmp_path / "sub"
    generate(sub, scenario="clean_small", seed=2)
    orders, order_seqs, res = _shape(sub)
    o = _order_with_two_ops(orders, order_seqs)
    seqs = order_seqs[o["order_id"]]
    route = o["route_id"]
    rows = [
        {"order_id": o["order_id"], "sequence": str(seqs[1]), "status": "in_progress",
         "actual_start": "2026-01-02T14:00:00",
         "actual_resource_id": res[(route, str(seqs[1]))],
         "quantity_complete": "5"},
    ]
    _write_wip(sub, rows, basis="quantity_complete")
    reader = _run_adapter_and_planner(sub, tmp_path)

    d = _demand_by_order(reader, o["order_id"])
    ops, _ = _ops_by_seq(reader, d["id"])
    op = ops[seqs[1]]
    assert op["wip_status"] == "in_progress"
    # remaining_duration = (order_qty - 5) * run_rate — computed, so DERIVED,
    # with the remainder arithmetic and its inputs recorded
    assert op["remaining_duration"] is not None
    rp = reader.get_provenance(op["id"], "remaining_duration")
    assert rp["provenance_class"] == "derived"
    assert "quantity_complete" in rp["payload"]["formula_id"]
    input_attrs = {ir["attribute_name"] for ir in rp["payload"]["input_refs"]}
    assert "quantity" in input_attrs and "run_rate" in input_attrs

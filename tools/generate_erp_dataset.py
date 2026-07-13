"""Synthetic ERP dataset generator — the IDS's executable twin (docs/06 §6).

Emits only IDS-conformant submissions (a manifest + the required/optional
CSV and JSON tables described in docs/06-incoming-data-spec.md §2/§5).
Every seeded anomaly maps to exactly one gate check (src/mre/modules/conformance.py)
and is recorded in the emitted truth_manifest.json alongside the expected
finding code/severity/disposition and the expected certificate grade.

Usage:
    python tools/generate_erp_dataset.py --scenario clean_small --out out_dir
    python tools/generate_erp_dataset.py --orders 200 --resources 20 --facilities 2 \\
        --seed 7 --scenario messy_realistic --out out_dir

Importable API (used by the test harness):
    generate(out_dir, orders=None, resources=None, facilities=None, seed=1,
             scenario="clean_small", anomalies=None) -> dict (the truth manifest)
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

UTC = timezone.utc

# Default priority ladder — matches docs/06 §5.9 cost_model.json example verbatim.
_DEFAULT_PRIORITY_MULTIPLIERS = {"standard": 1.0, "high": 3.0, "critical": 8.0}
_FAMILIES = ["gearing", "casting", "machining", "finishing"]


# ---------------------------------------------------------------------------
# Dataset container — plain lists of dict rows, mutated in place by anomalies
# ---------------------------------------------------------------------------

@dataclass
class Dataset:
    reference_date: date
    facilities: list[str]
    manifest: dict[str, Any]
    products: list[dict] = field(default_factory=list)
    routings: list[dict] = field(default_factory=list)
    routing_lines: list[dict] = field(default_factory=list)
    resources: list[dict] = field(default_factory=list)
    calendars: list[dict] = field(default_factory=list)
    orders: list[dict] = field(default_factory=list)
    customers: list[dict] = field(default_factory=list)
    setup_transitions: list[dict] = field(default_factory=list)
    locks: list[dict] = field(default_factory=list)
    wip_status: list[dict] = field(default_factory=list)
    cost_model: dict[str, Any] = field(default_factory=dict)
    # bookkeeping for anomalies / assertions
    priority_multipliers: dict[str, float] = field(default_factory=dict)
    omit_files: set[str] = field(default_factory=set)
    drop_columns: dict[str, set[str]] = field(default_factory=dict)
    drop_manifest_keys: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Scenario catalog v1 (docs/06 companion; CLAUDE.md task description)
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, dict[str, Any]] = {
    "clean_small": dict(orders=30, resources=8, facilities=1, anomalies=[],
                         with_customers=False, cost_profile="C1"),
    "clean_large": dict(orders=3000, resources=60, facilities=3, anomalies=[],
                         with_customers=False, cost_profile="C1", slow=True),
    "messy_realistic": dict(
        orders=200, resources=16, facilities=2,
        anomalies=[
            "orphan_product_refs:4", "duplicate_order_ids:3",
            "inactive_route_refs:4", "stale_due_dates:6", "placeholder_dates:2",
        ],
        with_customers=False, cost_profile="C1",
    ),
    "rejected": dict(orders=20, resources=6, facilities=1,
                      anomalies=["missing_required_file:calendars.csv"],
                      with_customers=False, cost_profile="C0"),
    "priority_pressure": dict(
        orders=12, resources=4, facilities=1, anomalies=[],
        with_customers=True, cost_profile="C1", bottleneck=True,
    ),
    "transition_heavy": dict(
        orders=24, resources=6, facilities=1, anomalies=[],
        with_customers=False, cost_profile="C2", transitions=True,
    ),
    "locked_plant": dict(
        orders=16, resources=6, facilities=1, anomalies=[],
        with_customers=False, cost_profile="C1", locks=True,
    ),
    "chunking_exam": dict(
        orders=10, resources=4, facilities=1, anomalies=["chunking_exam:2"],
        with_customers=False, cost_profile="C1",
    ),
    "overtime_required": dict(
        orders=8, resources=3, facilities=1, anomalies=[],
        with_customers=False, cost_profile="C2", overtime=True,
    ),
    "mid_replan": dict(
        orders=4, resources=3, facilities=1, anomalies=[],
        with_customers=False, cost_profile="C1", mid_replan=True,
    ),
    "multi_route": dict(
        orders=30, resources=6, facilities=1, anomalies=[],
        with_customers=False, cost_profile="C1", multi_route=True,
    ),
    # The DISTINCT-rate case that motivated R-T1 (docs/04): every eligible
    # machine bills a different rate and the load is LIGHT, so the optimum
    # concentrates on the cheapest machine and the near-optimal pool converges
    # on machine placement (few/no cross-machine ghosts) — the economically
    # realistic case where pool-only ghosts degrade and the forced-alternative
    # service earns its keep. Used by the CU3 counterfactual.
    "multi_route_distinct": dict(
        orders=6, resources=6, facilities=1, anomalies=[],
        with_customers=False, cost_profile="C1",
        multi_route=True, multi_route_distinct=True,
    ),
    # A FEEL fixture (feel=True), NOT a truth-bearing test scenario: a lively,
    # multi-eligible, loaded board for hands-on iteration of the cockpit gesture
    # surface. Seeds no anomalies and asserts nothing — generate() writes a
    # feel_fixture.json marker instead of a truth_manifest, and the
    # scenario-enumerating tests skip it. Wired as dev_api.ps1's default
    # --scenario. See _apply_busy_board for the design.
    "busy_board": dict(
        orders=40, resources=6, facilities=1, anomalies=[],
        with_customers=False, cost_profile="C1",
        busy_board=True, feel=True,
    ),
}


# ---------------------------------------------------------------------------
# Base dataset construction
# ---------------------------------------------------------------------------

def _facility_ids(k: int) -> list[str]:
    return [f"F{str(i + 1).zfill(3)}" for i in range(k)]


def _resource_ids(m: int, facilities: list[str]) -> list[tuple[str, str]]:
    """Return [(resource_id, facility_id), ...] spread evenly across facilities."""
    out = []
    for i in range(m):
        fac = facilities[i % len(facilities)]
        out.append((f"{fac}-RES{str(i + 1).zfill(3)}", fac))
    return out


def _build_base(
    rng: random.Random,
    n_orders: int,
    n_resources: int,
    n_facilities: int,
    reference_date: date,
    with_customers: bool,
    cost_profile: str,
) -> Dataset:
    facilities = _facility_ids(n_facilities)
    manifest = {
        "ids_version": "0.2",
        "source_system": "SyntheticERP vGen",
        "submitter": "mre-generator",
        "extract_timestamp": datetime.now(UTC).isoformat(),
        "reference_date": reference_date.isoformat(),
        "timezone": "UTC",
        "facility_scope": facilities,
        "semantics": {
            "production_minutes_basis": "per_operation",
            "production_minutes_per": "costing_lot",
            "due_date_time_of_day": "end_of_day",
            "quantity_uom_source": "products.uom",
            "setup_minutes_scope": "per_operation",
        },
        "notes": "synthetic",
    }
    ds = Dataset(reference_date=reference_date, facilities=facilities, manifest=manifest)

    resource_pairs = _resource_ids(n_resources, facilities)
    for rid, fac in resource_pairs:
        ds.resources.append({
            "resource_id": rid, "facility_id": fac, "resource_type": "workcenter",
            "parallel_units": "1", "calendar_id": "CAL-STD", "pool_id": "",
            "cost_rate": "",
        })

    ds.calendars.append({
        "calendar_id": "CAL-STD", "row_type": "pattern",
        "day_of_week": "0", "start_time": "07:00", "end_time": "19:00",
        "exception_date": "", "exception_type": "", "reason": "",
    })
    for dow in range(1, 6):
        ds.calendars.append({
            "calendar_id": "CAL-STD", "row_type": "pattern",
            "day_of_week": str(dow), "start_time": "07:00", "end_time": "19:00",
            "exception_date": "", "exception_type": "", "reason": "",
        })

    n_products = max(3, n_orders // 5)
    for i in range(n_products):
        pid = f"PROD-{str(i + 1).zfill(4)}"
        fam = _FAMILIES[i % len(_FAMILIES)]
        ds.products.append({
            "product_id": pid, "uom": "EA", "facility_id": facilities[i % len(facilities)],
            "product_group": fam, "costing_lot_size": "100",
            "setup_minutes": str(rng.choice([20, 30, 45, 60])),
            "production_minutes": str(round(rng.uniform(30, 90), 1)),
            "cost_price": str(round(rng.uniform(5, 50), 2)),
        })

        route_id = f"RT-{pid}"
        ds.routings.append({
            "route_id": route_id, "facility_id": facilities[i % len(facilities)],
            "product_id": pid, "status": "active", "approved": "Y",
            "version": "1", "effective_from": reference_date.isoformat(),
        })

        n_steps = rng.choice([2, 3])
        for seq in range(1, n_steps + 1):
            res_id, _ = resource_pairs[(i + seq) % len(resource_pairs)]
            ds.routing_lines.append({
                "route_id": route_id, "sequence": str(seq * 10), "resource_id": res_id,
                "active": "1", "setup_minutes": "", "run_minutes_per_unit": "",
                "dwell_minutes": "0", "setup_family": "",
                "splittable": "false", "min_chunk_minutes": "",
            })

    for i in range(n_orders):
        oid = f"ORD-{str(i + 1).zfill(6)}"
        prod = ds.products[i % len(ds.products)]
        route_id = f"RT-{prod['product_id']}"
        due = reference_date + timedelta(days=rng.randint(2, 30))
        ds.orders.append({
            "order_id": oid, "product_id": prod["product_id"], "route_id": route_id,
            "quantity": str(rng.randint(10, 200)),
            "due_date": due.isoformat(),
            "created_date": (reference_date - timedelta(days=rng.randint(0, 5))).isoformat(),
            "release_date": "",
            "facility_id": prod["facility_id"],
            "customer_id": "", "priority_class": "", "commitment_class": "standard",
        })

    core = {
        "default_resource_rate_per_hour": 60.0,
        "setup_cost_per_setup": 40.0,
        "tardiness_cost_per_hour": 25.0,
        "priority_multipliers": dict(_DEFAULT_PRIORITY_MULTIPLIERS),
    }
    refinements: dict[str, Any] = {
        "resource_rates": {}, "overtime_premium_multiplier": None,
        "transition_costs": None, "scrap_cost_per_unit": None,
        "inventory_carrying": None,
    }
    if cost_profile in ("C1", "C2", "C3"):
        for rid, _ in resource_pairs[: max(1, len(resource_pairs) // 2)]:
            refinements["resource_rates"][rid] = round(rng.uniform(40, 120), 2)
    if cost_profile in ("C2", "C3"):
        refinements["overtime_premium_multiplier"] = 1.5
    if cost_profile == "C3":
        refinements["scrap_cost_per_unit"] = 2.5
        refinements["inventory_carrying"] = 0.1

    ds.cost_model = {
        "version": "generator-v1", "currency": "USD",
        "core": core, "refinements": refinements,
    }
    ds.priority_multipliers = core["priority_multipliers"]

    if with_customers:
        ds.customers = [
            {"customer_id": "CUST-STD", "name": "Standard Co", "priority_class": "standard", "notes": ""},
            {"customer_id": "CUST-CRIT", "name": "Critical Corp", "priority_class": "critical", "notes": ""},
        ]
        for i, order in enumerate(ds.orders):
            order["customer_id"] = "CUST-CRIT" if i % 3 == 0 else "CUST-STD"
            order["priority_class"] = "critical" if i % 3 == 0 else "standard"
        ds.manifest["semantics"]["priority_precedence"] = "customer_over_order"

    return ds


# ---------------------------------------------------------------------------
# Scenario shaping helpers (priority_pressure / transition_heavy / locked_plant / chunking_exam)
# ---------------------------------------------------------------------------

def _apply_bottleneck(ds: Dataset, rng: random.Random) -> None:
    """Force the first two orders' routes onto one shared bottleneck resource
    with a due date neither can both meet, so a high vs. standard priority
    order compete for the same capacity window and cannot both be on time.

    Only the two target orders' own routes are touched (via a per-operation
    run_minutes_per_unit/setup_minutes override) — every other order's
    product/route timing is left at the base-dataset default, so this scenario
    stays ACCEPTED/C1 rather than tripping INFEASIBLE_SUBSET elsewhere.
    """
    bottleneck_id = ds.resources[0]["resource_id"]
    order0, order1 = ds.orders[0], ds.orders[1]
    target_routes = {order0["route_id"], order1["route_id"]}
    for line in ds.routing_lines:
        if line["route_id"] in target_routes:
            line["resource_id"] = bottleneck_id
            line["run_minutes_per_unit"] = "3"
            line["setup_minutes"] = "20"

    due_dt = datetime.combine(ds.reference_date, datetime.min.time(), tzinfo=UTC) + timedelta(hours=23, minutes=59)
    release_dt = datetime.combine(ds.reference_date, datetime.min.time(), tzinfo=UTC) + timedelta(hours=7)
    for order in (order0, order1):
        order["due_date"] = due_dt.isoformat()
        order["release_date"] = release_dt.isoformat()
        order["quantity"] = "150"  # 150*3 + 20 = 470 min/operation on the shared bottleneck
    order0["customer_id"] = "CUST-CRIT"
    order0["priority_class"] = "critical"
    order1["customer_id"] = "CUST-STD"
    order1["priority_class"] = "standard"


def _apply_transitions(ds: Dataset, rng: random.Random) -> None:
    """Populate setup_transitions.csv with a real, measurable transition cost
    between the two families used most heavily in routing_lines."""
    fams = _FAMILIES[:2]
    for i, line in enumerate(ds.routing_lines):
        line["setup_family"] = fams[i % 2]
    ds.setup_transitions = [
        {"from_family": fams[0], "to_family": fams[1], "setup_minutes": "90",
         "setup_cost": "60", "scrap_units": ""},
        {"from_family": fams[1], "to_family": fams[0], "setup_minutes": "90",
         "setup_cost": "60", "scrap_units": ""},
        {"from_family": fams[0], "to_family": fams[0], "setup_minutes": "15",
         "setup_cost": "10", "scrap_units": ""},
        {"from_family": fams[1], "to_family": fams[1], "setup_minutes": "15",
         "setup_cost": "10", "scrap_units": ""},
    ]
    ds.manifest["semantics"]["unlisted_transition_default"] = "base_setup"


def _apply_locks(ds: Dataset, rng: random.Random) -> tuple[str, str, str]:
    """Freeze the first order's first operation to a specific resource + start.

    Returns (order_id, resource_id, start_iso) for the truth manifest.
    """
    order = ds.orders[0]
    route_id = order["route_id"]
    first_line = next(rl for rl in ds.routing_lines if rl["route_id"] == route_id)
    resource_id = first_line["resource_id"]
    start_dt = datetime.combine(ds.reference_date, datetime.min.time(), tzinfo=UTC) + timedelta(hours=7)
    ds.locks = [{
        "order_id": order["order_id"], "sequence": first_line["sequence"], "resource_id": resource_id,
        "start": start_dt.isoformat(), "lock_type": "frozen",
        "authority": "plant_manager", "expiry": "",
    }]
    return order["order_id"], resource_id, start_dt.isoformat()


def _apply_chunking_exam(ds: Dataset, rng: random.Random, n: int) -> tuple[list[str], int]:
    """Give n orders a dedicated single-step operation whose working duration
    exceeds a 720-min shift window — but, since Rep 2 (docs/05 R-C3), marked
    resumable (splittable=true) so it is CHUNKED and scheduled rather than
    excluded. costing_lot_size=1, production_minutes=1500, quantity=1 ->
    working duration = 1500 min (2.08x a 720-min shift), which at a
    shift-open start needs exactly 3 chunks (720 + 720 + 60) — deterministic
    regardless of seed.

    Each affected order gets its OWN product/route/routing_line (not shared
    with any other order) — reusing the base dataset's round-robin product
    pool would silently give the same abnormal duration to every other order
    sharing that product, breaking the "exactly n orders affected, exactly 3
    chunks" guarantee.

    Returns (affected_order_ids, expected_chunk_count).
    """
    affected: list[str] = []
    for i in range(min(n, len(ds.orders))):
        order = ds.orders[i]
        pid = f"PROD-CHUNK-{i + 1:03d}"
        route_id = f"RT-{pid}"
        ds.products.append({
            "product_id": pid, "uom": "EA", "facility_id": order["facility_id"],
            "product_group": "chunking_exam", "costing_lot_size": "1",
            "setup_minutes": "0", "production_minutes": "1500", "cost_price": "10.0",
        })
        ds.routings.append({
            "route_id": route_id, "facility_id": order["facility_id"],
            "product_id": pid, "status": "active", "approved": "Y",
            "version": "1", "effective_from": ds.reference_date.isoformat(),
        })
        resource_id = ds.resources[i % len(ds.resources)]["resource_id"]
        ds.routing_lines.append({
            "route_id": route_id, "sequence": "10", "resource_id": resource_id,
            "active": "1", "setup_minutes": "", "run_minutes_per_unit": "",
            "dwell_minutes": "0", "setup_family": "",
            "splittable": "true", "min_chunk_minutes": "30",
        })
        order["product_id"] = pid
        order["route_id"] = route_id
        order["quantity"] = "1"
        affected.append(order["order_id"])
    return affected, 3


def _apply_overtime_required(ds: Dataset, rng: random.Random) -> dict:
    """Make regular capacity provably insufficient so the solver must buy
    priced overtime — deterministically, whatever the seed.

    Six "rescue" orders each get a dedicated single-op product/route on
    resources[0]: setup 30 + run 570 = a 600-minute operation (setup kept
    nonzero to avoid the documented 1-minute PT0S floor quirk), quantity 1,
    due Saturday end-of-day, released Monday (= reference_date). One 720-min
    weekday shift fits exactly one such op and never two, so Mon-Fri holds 5
    of the 6; a Saturday `added`/overtime calendar exception (07:00-19:00)
    supplies the sixth slot. Rates are pinned to 60/h ($1/min) on every
    resource, so the economics are exact: running the sixth op in Saturday
    overtime costs a $300 premium (600 min x $1 x 0.5) vs ~$1,025 tardiness
    (~41h x $25/h) if it waited for Monday — an optimal solver must use
    overtime for exactly one operation, 600 minutes, and no more.

    Two "control" orders get identical 600-min ops on resources[1]/[2] with
    two weeks of slack: any overtime minutes there would be pure premium
    waste, so the truth manifest asserts zero.

    Returns the truth_manifest "overtime" block.
    """
    # The base dataset's CAL-STD is SIX-day (pattern rows 0-5). Saturday must
    # be genuinely closed here or the overtime window would duplicate regular
    # capacity — and the counterfactual (strip the exception, demands go
    # late) would be false. Discovered by exactly that counterfactual test.
    ds.calendars = [
        r for r in ds.calendars
        if not (r.get("row_type") == "pattern" and r.get("day_of_week") == "5")
    ]
    saturday = ds.reference_date + timedelta(days=5 - ds.reference_date.weekday())
    ds.calendars.append({
        "calendar_id": "CAL-STD", "row_type": "exception",
        "day_of_week": "", "start_time": "07:00", "end_time": "19:00",
        "exception_date": saturday.isoformat(), "exception_type": "added",
        "reason": "overtime",
    })

    rate_per_hour = 60.0
    for r in ds.resources:
        ds.cost_model["refinements"]["resource_rates"][r["resource_id"]] = rate_per_hour

    def _dedicated_op_order(order: dict, tag: str, resource_id: str, due: date) -> None:
        pid = f"PROD-{tag}"
        route_id = f"RT-{pid}"
        ds.products.append({
            "product_id": pid, "uom": "EA", "facility_id": order["facility_id"],
            "product_group": "overtime_exam", "costing_lot_size": "1",
            "setup_minutes": "30", "production_minutes": "570", "cost_price": "10.0",
        })
        ds.routings.append({
            "route_id": route_id, "facility_id": order["facility_id"],
            "product_id": pid, "status": "active", "approved": "Y",
            "version": "1", "effective_from": ds.reference_date.isoformat(),
        })
        ds.routing_lines.append({
            "route_id": route_id, "sequence": "10", "resource_id": resource_id,
            "active": "1", "setup_minutes": "", "run_minutes_per_unit": "",
            "dwell_minutes": "0", "setup_family": "",
            "splittable": "false", "min_chunk_minutes": "",
        })
        order["product_id"] = pid
        order["route_id"] = route_id
        order["quantity"] = "1"
        order["release_date"] = ds.reference_date.isoformat()
        order["due_date"] = due.isoformat()

    bottleneck_id = ds.resources[0]["resource_id"]
    rescue_ids, control_ids = [], []
    for i in range(6):
        order = ds.orders[i]
        _dedicated_op_order(order, f"OT-{i + 1:02d}", bottleneck_id, saturday)
        rescue_ids.append(order["order_id"])
    for i in range(2):
        order = ds.orders[6 + i]
        _dedicated_op_order(order, f"CTRL-{i + 1:02d}",
                            ds.resources[1 + i]["resource_id"],
                            ds.reference_date + timedelta(days=12))
        control_ids.append(order["order_id"])

    op_minutes = 600
    rate_per_min = rate_per_hour / 60.0
    multiplier = ds.cost_model["refinements"]["overtime_premium_multiplier"]
    return {
        "resource_id": bottleneck_id,
        "overtime_date": saturday.isoformat(),
        "overtime_window": {"start": "07:00", "end": "19:00"},
        "premium_multiplier": multiplier,
        "rescue_order_ids": rescue_ids,
        "control_order_ids": control_ids,
        "op_minutes": op_minutes,
        "expected_overtime_minutes": op_minutes,
        "expected_production_overtime_cost": op_minutes * rate_per_min * multiplier,
        "expected_overtime_premium_delta": op_minutes * rate_per_min * (multiplier - 1),
        "expected_late_without_overtime_count": 1,
    }


def _apply_mid_replan(ds: Dataset, rng: random.Random) -> dict:
    """Reschedule-from-a-point (docs/06 §5.13). The plant's second submission
    carries WIP: some work is done, some underway, the rest still to plan.
    Deterministic, seed-independent — the whole point is a repeatable
    counterfactual on capacity.

    Layout (reference_date = Monday; CAL-STD open 07:00–19:00 = 720 min/day):
      R0  ORD_DONE   (complete)   would have filled R0's Monday window; now
                                  done, so its capacity is FREED.
          ORD_RESCUE (not_started, due Monday) 600 min — fits Monday ONLY
                                  because ORD_DONE vacated the window. Strip
                                  the WIP and R0 must serve both → tardiness.
      R1  ORD_INFLIGHT (in_progress, 600 min remaining) — a FIXED interval
                                  from reference_date; it holds R1's early
                                  block.
          ORD_FUTURE  (not_started, due Monday) 300 min — the only movable op
                                  on R1; it is pushed past the in-flight
                                  remaining.

    Truth: rescue on time WITH wip; total tardiness strictly lower WITH wip
    than without (completion bought capacity); the future op starts at/after
    the in-flight remaining (the fixed op stayed put); the completed op
    produces no assignment.
    """
    ref = ds.reference_date                       # a Monday
    prev_workday = ref - timedelta(days=3)         # the previous Friday (history)
    r0 = ds.resources[0]["resource_id"]
    r1 = ds.resources[1]["resource_id"]

    def _dedicated(order: dict, tag: str, resource_id: str, run_minutes: int,
                   due: date) -> None:
        pid = f"PROD-{tag}"
        route_id = f"RT-{pid}"
        ds.products.append({
            "product_id": pid, "uom": "EA", "facility_id": order["facility_id"],
            "product_group": "mid_replan", "costing_lot_size": "1",
            "setup_minutes": "0", "production_minutes": str(run_minutes),
            "cost_price": "10.0",
        })
        ds.routings.append({
            "route_id": route_id, "facility_id": order["facility_id"],
            "product_id": pid, "status": "active", "approved": "Y",
            "version": "1", "effective_from": ref.isoformat(),
        })
        ds.routing_lines.append({
            "route_id": route_id, "sequence": "10", "resource_id": resource_id,
            "active": "1", "setup_minutes": "", "run_minutes_per_unit": "",
            "dwell_minutes": "0", "setup_family": "",
            "splittable": "false", "min_chunk_minutes": "",
        })
        order["product_id"] = pid
        order["route_id"] = route_id
        order["quantity"] = "1"
        order["release_date"] = ref.isoformat()
        order["due_date"] = due.isoformat()

    done, rescue, inflight, future = ds.orders[0], ds.orders[1], ds.orders[2], ds.orders[3]
    _dedicated(done,     "MR-DONE",     r0, 600, ref)
    _dedicated(rescue,   "MR-RESCUE",   r0, 600, ref)
    _dedicated(inflight, "MR-INFLIGHT", r1, 660, ref)
    _dedicated(future,   "MR-FUTURE",   r1, 300, ref)

    inflight_remaining = 600
    # wip_status.csv: DONE complete, INFLIGHT underway. RESCUE/FUTURE absent
    # ⇒ not_started. actual_start on the previous workday (history — before
    # reference_date, deliberately NOT a gate finding).
    ds.wip_status = [
        {"order_id": done["order_id"], "sequence": "10", "status": "complete",
         "actual_start": f"{prev_workday.isoformat()}T08:00:00",
         "actual_resource_id": r0, "remaining_minutes": "", "quantity_complete": ""},
        {"order_id": inflight["order_id"], "sequence": "10", "status": "in_progress",
         "actual_start": f"{prev_workday.isoformat()}T08:00:00",
         "actual_resource_id": r1, "remaining_minutes": str(inflight_remaining),
         "quantity_complete": ""},
    ]
    ds.manifest["semantics"]["wip_progress_basis"] = "remaining_minutes"

    return {
        "reference_date": ref.isoformat(),
        "bottleneck_resource": r0,
        "second_resource": r1,
        "done_order_id": done["order_id"],
        "rescue_order_id": rescue["order_id"],
        "inflight_order_id": inflight["order_id"],
        "future_order_id": future["order_id"],
        "inflight_remaining_minutes": inflight_remaining,
        "expected_rescue_on_time_with_wip": True,
        "expected_total_tardiness_lower_with_wip": True,
        "expected_future_starts_after_inflight_remaining": True,
        "expected_completed_op_has_no_assignment": True,
    }


def _apply_multi_route(ds: Dataset, rng: random.Random,
                       distinct_rates: bool = False) -> dict:
    """Capability-routed scenario (docs/05 B2): operations whose eligible
    resource set has 2-4 members carrying REAL cost differentials, so a
    cross-machine move has a genuine, nonzero price (docs/04 R-DP consequence
    (2): the interim-A prerequisite the 3.0 spike proved generated data
    lacked).

    IDS expression (no schema change): an operation's eligible set is the set
    of routing_lines rows sharing one (route_id, sequence) but naming
    different resource_id — docs/05 B2's "routing_lines.resource_id →
    explicit_set". The adapter groups them into one OperationSpec whose
    ResourceRequirement is EXPLICIT_SET over the whole set. The differential
    lives on the *resource* (per-resource cost_rate), not the op time, so a
    single OperationSpec.run_rate still holds — the choice of machine, not the
    duration, is what carries the price. This keeps the canonical model
    unchanged while giving the pool real cross-machine ghosts to render.

    Layout (1 facility, 6 resources, all on CAL-STD 07:00-19:00). The design
    turns on the one mechanism that makes the pool surface cross-machine
    ghosts at a CLEAN, near-optimal base (the interim-A lesson, learned the
    hard way): a genuine near-optimal cross-machine alternative exists only
    where two machines are cost-EQUIVALENT for an op AND both are needed, so
    the machine assignment is a free, degenerate choice.

      (1) A SATURATED IDENTICAL-RATE PAIR — R0 and R1 both bill $50/h, and
          almost every operation is eligible on {R0,R1}. The order load fills
          R0+R1 to ~90%, so which of the two an op runs on is a genuinely free
          choice: the optimum is massively degenerate, the base solve is easy
          and near-optimal (flat cost ⇒ FEASIBLE≈optimal), and the pool's
          diversity cut readily swaps ops R0↔R1 at ZERO cost delta. THIS is
          what makes cross-machine moves appear in the pool at all (a slack or
          distinct-rate board yields only time-shifts, hamming≈1).
      (2) PRICIER ELIGIBLE ALTERNATIVES for the ghost PRICE — some ops are
          also eligible on R2/R3 ($55/$60), idle spill valves the optimum
          avoids. They give each such op a different-rate alternative, so the
          Tier-1 ghost price of a cross-tier move is nonzero by construction —
          asserted directly from the contract-1.2 eligibility payload
          (working_min × Δrate), independent of the pool's stochastic choice.

      PROD-MR-A (3 steps): seq10 {R0,R1,R2} → seq20 {R0,R1} → seq30 {R0,R1,R3}
      PROD-MR-B (2 steps): seq10 {R0,R1}    → seq20 {R0,R1,R2}
    Every op is a 240-min block (production_minutes=240, lot=1, qty=1).

    Truth: a counted number of ops have >1 eligible resource; at least one
    such op sits in a precedence chain; at least one scheduled multi-eligible
    op has an eligible alternative on a different-rate machine (a nonzero ghost
    price); the pool built on the deterministic solve yields ≥1 op placed
    cross-machine; and the single-eligibility collapse (each op's route reduced
    to one eligible row) drives the pool's cross-machine count to zero — the
    price-bought-something proof that the alternatives are real, not decorative.
    """
    ref = ds.reference_date
    # Two rate regimes:
    #  * DEFAULT (saturated identical pair): R0 and R1 both bill $50 — a free
    #    degenerate machine choice the pool swaps at zero delta, which is what
    #    surfaces cross-machine ghosts in the pool at all.
    #  * DISTINCT (R-T1 realistic case): every machine bills a different rate,
    #    so each op has a strictly cheapest eligible machine; with a light load
    #    the optimum concentrates there and the pool CONVERGES on machine
    #    placement (the pool-only ghost degradation R-T1 names). The
    #    forced-alternative service is what still prices the roads not taken.
    rate_by_res = {}
    tiers = ([50.0, 52.0, 54.0, 56.0, 58.0, 60.0] if distinct_rates
             else [50.0, 50.0, 55.0, 60.0, 65.0, 70.0])
    for i, r in enumerate(ds.resources):
        rate = tiers[i % len(tiers)]
        rate_by_res[r["resource_id"]] = rate
    ds.cost_model["refinements"]["resource_rates"] = dict(rate_by_res)
    R = [r["resource_id"] for r in ds.resources]

    # Reset the process + demand tables; rebuild a controlled multi-route fixture.
    ds.products, ds.routings, ds.routing_lines, ds.orders = [], [], [], []

    # (route_id, sequence) -> list of eligible resource_ids (the eligible set).
    def _product(pid: str, steps: list[list[str]]) -> str:
        route_id = f"RT-{pid}"
        ds.products.append({
            "product_id": pid, "uom": "EA", "facility_id": ds.facilities[0],
            "product_group": "multi_route", "costing_lot_size": "1",
            "setup_minutes": "0", "production_minutes": "240", "cost_price": "10.0",
        })
        ds.routings.append({
            "route_id": route_id, "facility_id": ds.facilities[0],
            "product_id": pid, "status": "active", "approved": "Y",
            "version": "1", "effective_from": ref.isoformat(),
        })
        for step_idx, eligible in enumerate(steps):
            seq = (step_idx + 1) * 10
            for res_id in eligible:  # one row per eligible resource — the set
                ds.routing_lines.append({
                    "route_id": route_id, "sequence": str(seq), "resource_id": res_id,
                    "active": "1", "setup_minutes": "", "run_minutes_per_unit": "",
                    "dwell_minutes": "0", "setup_family": "",
                    "splittable": "false", "min_chunk_minutes": "",
                })
        return route_id

    steps_a = [[R[0], R[1], R[2]], [R[0], R[1]], [R[0], R[1], R[3]]]
    steps_b = [[R[0], R[1]], [R[0], R[1], R[2]]]
    route_a = _product("PROD-MR-A", steps_a)
    route_b = _product("PROD-MR-B", steps_b)
    specs = [("PROD-MR-A", route_a, steps_a), ("PROD-MR-B", route_b, steps_b)]

    # Light load for the distinct-rate case (so the optimum concentrates on the
    # cheapest machine and the pool converges); the saturated case needs the
    # heavier load to fill the identical pair to ~90%.
    n_orders = 4 if distinct_rates else 12
    for i in range(n_orders):
        pid, route_id, _ = specs[i % 2]
        oid = f"ORD-{i + 1:06d}"
        due = ref + timedelta(days=5 + (i % 2))
        ds.orders.append({
            "order_id": oid, "product_id": pid, "route_id": route_id,
            "quantity": "1", "due_date": due.isoformat(),
            "created_date": ref.isoformat(), "release_date": ref.isoformat(),
            "facility_id": ds.facilities[0], "customer_id": "",
            "priority_class": "", "commitment_class": "standard",
        })

    # Count multi-eligible ops, whether any sits in a precedence chain, and
    # whether any spans rate tiers (a nonzero ghost price by construction).
    multi_eligible = []
    in_chain = False
    tier_spanning = 0
    for pid, route_id, steps in specs:
        for step_idx, eligible in enumerate(steps):
            if len(eligible) > 1:
                seq = (step_idx + 1) * 10
                rates = {rate_by_res[r] for r in eligible}
                multi_eligible.append({"route_id": route_id, "sequence": seq,
                                       "eligible_count": len(eligible),
                                       "distinct_rates": sorted(rates)})
                if len(steps) > 1:  # any neighbour ⇒ it is in a chain
                    in_chain = True
                if len(rates) > 1:
                    tier_spanning += 1

    return {
        "resources": R,
        "resource_rates": rate_by_res,
        "distinct_rates": distinct_rates,
        "n_orders": n_orders,
        "multi_eligible_ops": multi_eligible,
        "multi_eligible_op_count": len(multi_eligible),
        "max_eligible_alternatives": max(m["eligible_count"] for m in multi_eligible),
        "tier_spanning_op_count": tier_spanning,
        "expected_multi_eligible_in_precedence_chain": in_chain,
        "expected_nonzero_ghost_price": tier_spanning > 0,
        # verified by the end-to-end test that builds the pool on the solve.
        # DEFAULT (saturated pair): the pool surfaces cross-machine ghosts.
        # DISTINCT (light load): the pool converges — few/no cross-machine
        # ghosts — and the forced-alternative service supplies the priced ones.
        "expected_pool_cross_machine_ops_ge": 0 if distinct_rates else 1,
        "expected_collapse_cross_machine_ops": 0,
    }


def _apply_busy_board(ds: Dataset, rng: random.Random) -> dict:
    """FEEL fixture — a lively cockpit board for hands-on iteration of the
    gesture surface (grab → shade → ghosts → magnets → drop → traces). This is
    NOT a truth-bearing test scenario: it seeds no anomalies and asserts
    nothing, so generate() writes a feel_fixture.json marker instead of a
    truth_manifest.json (and the scenario-enumerating tests skip it).

    It is tuned for the qualities feel-iteration needs, not for a proof:
      * 30–50 orders spread across MOST of the six resources;
      * NEAR-EQUIVALENT but strictly distinct machine rates ($50.0–$51.0/h, a
        ~2% spread) — close enough that tardiness dominates the objective and
        the optimum SPREADS work across the machines (not concentrating on the
        cheapest), distinct enough that every cross-machine ghost still carries
        a nonzero (if small) price (Δrate × working minutes);
      * MULTI-ELIGIBLE ops throughout (every op eligible on 2–6 machines), so
        grab-shading and forced-alternative ghosts always have somewhere to go;
      * enough LOAD, with front-loaded due dates, that some demands run tight or
        late — so lateness coloring and consequence traces have real material;
      * a few PRECEDENCE CHAINS that cross machines (products B and C: their
        consecutive steps have DISJOINT eligible sets, so successive ops must
        land on different resources).

    Same IDS expression as multi_route (docs/05 B2, no schema change): one
    routing_lines row per eligible resource under a shared (route_id, sequence);
    the adapter groups them into a single EXPLICIT_SET OperationSpec. The rate
    differential lives on the resource, not the op time, so one run_rate holds.
    """
    ref = ds.reference_date
    R = [r["resource_id"] for r in ds.resources]
    n_res = len(R)

    # Near-equivalent, strictly distinct rates: a $0.20/h step per machine (a
    # ~2% spread). Deliberately tiny — small enough that tardiness dominates the
    # objective and the optimum SPREADS work across all six machines rather than
    # concentrating on the cheapest, yet strictly distinct so every
    # cross-machine ghost still carries a nonzero (if small) price.
    rate_by_res = {R[i]: round(50.0 + 0.2 * i, 2) for i in range(n_res)}
    ds.cost_model["refinements"]["resource_rates"] = dict(rate_by_res)

    # Preserve the preset order count, then rebuild the process/demand tables.
    n_orders = len(ds.orders)
    ds.products, ds.routings, ds.routing_lines, ds.orders = [], [], [], []

    def _product(pid: str, steps: list[list[str]], minutes: int) -> str:
        route_id = f"RT-{pid}"
        ds.products.append({
            "product_id": pid, "uom": "EA", "facility_id": ds.facilities[0],
            "product_group": "busy_board", "costing_lot_size": "1",
            "setup_minutes": "0", "production_minutes": str(minutes),
            "cost_price": "10.0",
        })
        ds.routings.append({
            "route_id": route_id, "facility_id": ds.facilities[0],
            "product_id": pid, "status": "active", "approved": "Y",
            "version": "1", "effective_from": ref.isoformat(),
        })
        for step_idx, eligible in enumerate(steps):
            seq = (step_idx + 1) * 10
            for res_id in eligible:  # one row per eligible resource — the set
                ds.routing_lines.append({
                    "route_id": route_id, "sequence": str(seq),
                    "resource_id": res_id, "active": "1",
                    "setup_minutes": "", "run_minutes_per_unit": "",
                    "dwell_minutes": "0", "setup_family": "",
                    "splittable": "false", "min_chunk_minutes": "",
                })
        return route_id

    # Eligible sets deliberately overlap so the whole board touches all six
    # resources and most ops have 2–4 homes; B and C are cross-machine chains
    # (disjoint consecutive steps ⇒ the precedence edge MUST span machines).
    catalog = [
        ("PROD-BB-A", [[R[0], R[1], R[2]], [R[1], R[2], R[3]], [R[3], R[4], R[5]]], 240),
        ("PROD-BB-B", [[R[0], R[2], R[4]], [R[1], R[3], R[5]]], 260),
        ("PROD-BB-C", [[R[0], R[1]], [R[2], R[3]], [R[4], R[5]]], 220),
        ("PROD-BB-D", [[R[0], R[1], R[2], R[3], R[4], R[5]]], 300),
    ]
    routes = [(pid, _product(pid, steps, minutes), steps)
              for pid, steps, minutes in catalog]

    # Two due-date cohorts that together exercise the full lateness spectrum:
    #  * a RUSH FRONT due tomorrow (ref+1), a window that provably cannot hold
    #    their work — the front cohort's minutes modestly exceed the first two
    #    working days of capacity across the six machines — so SOME must run late
    #    (red) and the rest tight (amber);
    #  * a comfortable TAIL due a week+ out (green).
    front = 2 * n_orders // 5
    for i in range(n_orders):
        pid, route_id, _steps = routes[i % len(routes)]
        oid = f"ORD-{i + 1:06d}"
        if i < front:
            due = ref + timedelta(days=1)             # over-subscribed rush front
        else:
            due = ref + timedelta(days=9 + (i % 3))   # comfortable green tail
        ds.orders.append({
            "order_id": oid, "product_id": pid, "route_id": route_id,
            "quantity": "1", "due_date": due.isoformat(),
            "created_date": ref.isoformat(), "release_date": ref.isoformat(),
            "facility_id": ds.facilities[0], "customer_id": "",
            "priority_class": "", "commitment_class": "standard",
        })

    # A compact, non-asserting summary for the marker (feel fixture: descriptive,
    # not a truth manifest — nothing here is checked by a test).
    multi_eligible_steps = sum(1 for _pid, _rt, steps in routes
                               for s in steps if len(s) > 1)
    return {
        "resources": R,
        "resource_rates": rate_by_res,
        "n_orders": n_orders,
        "products": [pid for pid, _s, _m in catalog],
        "multi_eligible_step_count": multi_eligible_steps,
        "cross_machine_chains": ["PROD-BB-B", "PROD-BB-C"],
    }


# ---------------------------------------------------------------------------
# Anomaly catalog v1 — each returns a truth_manifest entry
# ---------------------------------------------------------------------------

def _anomaly_missing_required_file(ds: Dataset, rng: random.Random, fname: str) -> dict:
    ds.omit_files.add(fname)
    return {
        "anomaly": "missing_required_file", "param": fname,
        "expected_finding_code": "MISSING_REFERENCE", "expected_severity": "blocker",
        "expected_disposition": "blocked", "expected_grade_floor": "REJECTED",
    }


def _anomaly_missing_manifest_field(ds: Dataset, rng: random.Random, field_name: str) -> dict:
    ds.manifest["semantics"].pop(field_name, None)
    return {
        "anomaly": "missing_manifest_field", "param": field_name,
        "expected_finding_code": "MALFORMED_FIELD", "expected_severity": "blocker",
        "expected_disposition": "blocked", "expected_grade_floor": "REJECTED",
    }


def _anomaly_orphan_product_refs(ds: Dataset, rng: random.Random, pct: float) -> dict:
    pct = float(pct)
    n = max(1, int(len(ds.orders) * pct / 100.0))
    victims = rng.sample(ds.orders, min(n, len(ds.orders)))
    for o in victims:
        o["product_id"] = "PROD-NONEXISTENT"
    rate = 1 - n / len(ds.orders)
    band = "REJECTED" if rate < 0.60 else ("CONDITIONAL" if rate < 0.97 else "ACCEPTED")
    return {
        "anomaly": "orphan_product_refs", "param": pct, "affected_count": n,
        "expected_finding_code": "ORPHAN_ENTITY",
        "expected_severity": "blocker" if band == "REJECTED" else ("error" if band == "CONDITIONAL" else "warning"),
        "expected_disposition": "excluded",
        "expected_grade_floor": band,
    }


def _anomaly_orphan_route_refs(ds: Dataset, rng: random.Random, pct: float) -> dict:
    pct = float(pct)
    n = max(1, int(len(ds.orders) * pct / 100.0))
    victims = rng.sample(ds.orders, min(n, len(ds.orders)))
    for o in victims:
        o["route_id"] = "RT-NONEXISTENT"
    rate = 1 - n / len(ds.orders)
    band = "REJECTED" if rate < 0.60 else ("CONDITIONAL" if rate < 0.97 else "ACCEPTED")
    return {
        "anomaly": "orphan_route_refs", "param": pct, "affected_count": n,
        "expected_finding_code": "ORPHAN_ENTITY",
        "expected_severity": "blocker" if band == "REJECTED" else ("error" if band == "CONDITIONAL" else "warning"),
        "expected_disposition": "excluded",
        "expected_grade_floor": band,
    }


def _anomaly_duplicate_order_ids(ds: Dataset, rng: random.Random, n: int) -> dict:
    n = int(n)
    victims = rng.sample(ds.orders, min(n, len(ds.orders)))
    for o in victims:
        ds.orders.append(dict(o))
    return {
        "anomaly": "duplicate_order_ids", "param": n, "affected_count": n,
        "expected_finding_code": "DUPLICATE_IDENTITY", "expected_severity": "error",
        "expected_disposition": "proceeded_flagged", "expected_grade_floor": "CONDITIONAL",
    }


def _anomaly_zero_lot_size(ds: Dataset, rng: random.Random, n: int) -> dict:
    n = int(n)
    victims = rng.sample(ds.products, min(n, len(ds.products)))
    for p in victims:
        p["costing_lot_size"] = "0"
    return {
        "anomaly": "zero_lot_size", "param": n, "affected_count": n,
        "expected_finding_code": "VALUE_OUT_OF_RANGE", "expected_severity": "error",
        "expected_disposition": "excluded", "expected_grade_floor": "CONDITIONAL",
    }


def _anomaly_inactive_route_refs(ds: Dataset, rng: random.Random, n: int) -> dict:
    n = int(n)
    victims = rng.sample(ds.routings, min(n, len(ds.routings)))
    for r in victims:
        r["status"] = "inactive"
    return {
        "anomaly": "inactive_route_refs", "param": n, "affected_count": n,
        "expected_finding_code": "LOW_CONFIDENCE_INPUT", "expected_severity": "warning",
        "expected_disposition": "proceeded_flagged", "expected_grade_floor": "CONDITIONAL",
    }


def _anomaly_stale_due_dates(ds: Dataset, rng: random.Random, n: int) -> dict:
    n = int(n)
    victims = rng.sample(ds.orders, min(n, len(ds.orders)))
    stale = ds.reference_date - timedelta(days=400)
    for o in victims:
        o["due_date"] = stale.isoformat()
        # A stale-backlog order was CREATED long ago too — keep the row
        # internally coherent (due >= created), so the stale flag is a
        # backlog signal, not a spurious order_dates inconsistency.
        o["created_date"] = (stale - timedelta(days=5)).isoformat()
    return {
        "anomaly": "stale_due_dates", "param": n, "affected_count": n,
        "expected_finding_code": "VALUE_OUT_OF_RANGE", "expected_severity": "info",
        "expected_disposition": "proceeded_flagged", "expected_grade_floor": "ACCEPTED",
    }


def _anomaly_placeholder_dates(ds: Dataset, rng: random.Random, n: int) -> dict:
    """Set due_date implausibly far out (> reference_date + 3y, Appendix A).

    Deliberately bounded to a few years past the 3y threshold rather than a
    literal placeholder like 2099-12-31: the planning horizon is derived from
    max(due_date) + a fixed buffer (see __main__.py / solver_builder.py), so
    an unbounded placeholder blows the horizon out to decades and makes
    calendar flattening and CP-SAT model construction intractable. The gate
    check under test only cares that the date exceeds the threshold, not by
    how much.
    """
    n = int(n)
    victims = rng.sample(ds.orders, min(n, len(ds.orders)))
    placeholder = ds.reference_date.replace(year=ds.reference_date.year + 3) + timedelta(days=45)
    for o in victims:
        o["due_date"] = placeholder.isoformat()
    return {
        "anomaly": "placeholder_dates", "param": n, "affected_count": n,
        "expected_finding_code": "VALUE_OUT_OF_RANGE", "expected_severity": "info",
        "expected_disposition": "proceeded_flagged", "expected_grade_floor": "ACCEPTED",
    }


def _anomaly_setup_family_without_matrix(ds: Dataset, rng: random.Random, _: Any = None) -> dict:
    for line in ds.routing_lines:
        if not line.get("setup_family"):
            line["setup_family"] = _FAMILIES[0]
    ds.setup_transitions = []
    return {
        "anomaly": "setup_family_without_matrix", "param": None,
        "expected_finding_code": "AMBIGUOUS_SOURCE", "expected_severity": "warning",
        "expected_disposition": "proceeded_flagged", "expected_grade_floor": "CONDITIONAL",
    }


def _anomaly_uncovered_priority_class(ds: Dataset, rng: random.Random, _: Any = None) -> dict:
    victim = ds.orders[0]
    victim["priority_class"] = "platinum"
    return {
        "anomaly": "uncovered_priority_class", "param": "platinum",
        "expected_finding_code": "UNMAPPABLE_VALUE", "expected_severity": "error",
        "expected_disposition": "proceeded_flagged", "expected_grade_floor": "CONDITIONAL",
    }


def _anomaly_lock_on_unknown_order(ds: Dataset, rng: random.Random, n: int) -> dict:
    n = int(n)
    for i in range(n):
        ds.locks.append({
            "order_id": f"ORD-UNKNOWN-{i}", "sequence": "", "resource_id": ds.resources[0]["resource_id"],
            "start": datetime.now(UTC).isoformat(), "lock_type": "frozen",
            "authority": "test", "expiry": "",
        })
    return {
        "anomaly": "lock_on_unknown_order", "param": n, "affected_count": n,
        "expected_finding_code": "ORPHAN_ENTITY", "expected_severity": "error",
        "expected_disposition": "excluded", "expected_grade_floor": "CONDITIONAL",
    }


def _anomaly_chunking_exam(ds: Dataset, rng: random.Random, n: int) -> dict:
    """Rep 2 (docs/05 R-C3): a duration exceeding a shift window is no
    longer excluded (INFEASIBLE_SUBSET) — it is CHUNKED and scheduled, so
    there is no finding to expect. The truth manifest instead asserts the
    positive chunking behavior directly (schedule.csv row count, chunk
    count, and that every derived pause aligns exactly with a calendar
    closure — the spike-2 semantic assertion, now a standing production
    test per tests/test_precedence_edges.py's sibling for chunking)."""
    affected, expected_chunks = _apply_chunking_exam(ds, rng, int(n))
    return {
        "anomaly": "chunking_exam", "param": int(n), "affected_order_ids": affected,
        "expected_finding_code": None,
        "expected_chunked": True,
        "expected_chunk_count": expected_chunks,
        "expected_pause_aligns_with_calendar": True,
        "expected_grade_floor": "ACCEPTED",
    }


# ---------------------------------------------------------------------------
# Anomaly catalog v2 — the seven new gate checks + the transition-matrix
# converse + the structural/WIP/quality coverage anomalies (2026-07-10,
# Certificate session). Each seeds exactly one gate rule; every entry carries
# expected_rule_id + expected_outcome so the coverage matrix can assert on the
# precise registry rule, not just the (shared) finding code.
# ---------------------------------------------------------------------------

def _entry(anomaly: str, code: Optional[str], rule_id: str, outcome: str,
           severity: str, disposition: str, grade_floor: str, **extra) -> dict:
    d = {
        "anomaly": anomaly, "expected_finding_code": code,
        "expected_rule_id": rule_id, "expected_outcome": outcome,
        "expected_severity": severity, "expected_disposition": disposition,
        "expected_grade_floor": grade_floor,
    }
    d.update(extra)
    return d


def _anomaly_manifest_schema_invalid(ds: Dataset, rng: random.Random, field_name: Any = None) -> dict:
    """Parses as JSON but omits a REQUIRED top-level manifest field (§3)."""
    key = field_name or "ids_version"
    ds.drop_manifest_keys.add(key)
    return _entry("manifest_schema_invalid", "MALFORMED_FIELD",
                  "ids.manifest_schema_valid", "violated", "blocker", "blocked",
                  "REJECTED", param=key)


def _anomaly_missing_columns(ds: Dataset, rng: random.Random, spec: Any = None) -> dict:
    """Drop a REQUIRED column from a file (no silent .get() fall-through)."""
    fname, col = (spec or "resources.csv:facility_id").split(":")
    ds.drop_columns.setdefault(fname, set()).add(col)
    return _entry("missing_columns", "MALFORMED_FIELD",
                  "ids.required_columns_parse", "violated", "blocker", "blocked",
                  "REJECTED", param=f"{fname}:{col}")


def _anomaly_blank_keys(ds: Dataset, rng: random.Random, n: Any = 1) -> dict:
    """Blank a key field (product_id) on n order rows — un-subsumed from the
    valid-orders aggregate; a per-field null scan of its own."""
    n = int(n)
    for o in rng.sample(ds.orders, min(n, len(ds.orders))):
        o["product_id"] = ""
    return _entry("blank_keys", "MALFORMED_FIELD",
                  "ids.key_fields_populated", "violated", "blocker", "blocked",
                  "REJECTED", param=n, affected_count=n)


def _anomaly_lineless_routes(ds: Dataset, rng: random.Random, n: Any = 1) -> dict:
    """n orders reference a route HEADER that has no active routing lines —
    header resolves, lines do not (routes_resolve_to_lines, unfolded)."""
    n = int(n)
    victims = rng.sample(ds.orders, min(n, len(ds.orders)))
    for i, o in enumerate(victims):
        route_id = f"RT-LINELESS-{i + 1:03d}"
        ds.routings.append({
            "route_id": route_id, "facility_id": o["facility_id"],
            "product_id": o["product_id"], "status": "active", "approved": "Y",
            "version": "1", "effective_from": ds.reference_date.isoformat(),
        })
        o["route_id"] = route_id  # product still resolves; route header exists; no lines
    return _entry("lineless_routes", "ORPHAN_ENTITY",
                  "ids.routes_resolve_to_lines", "degraded", "error", "excluded",
                  "CONDITIONAL", param=n, affected_count=n)


def _anomaly_inverted_dates(ds: Dataset, rng: random.Random, n: Any = 2) -> dict:
    """n orders whose due_date precedes their release_date (§5.1)."""
    n = int(n)
    early = ds.reference_date + timedelta(days=2)
    late = ds.reference_date + timedelta(days=20)
    for o in rng.sample(ds.orders, min(n, len(ds.orders))):
        o["release_date"] = late.isoformat()
        o["due_date"] = early.isoformat()
    return _entry("inverted_dates", "TEMPORAL_IMPOSSIBILITY",
                  "ids.order_dates_internally_consistent", "degraded", "error",
                  "proceeded_flagged", "CONDITIONAL", param=n, affected_count=n)


def _anomaly_foreign_facility(ds: Dataset, rng: random.Random, n: Any = 2) -> dict:
    """n orders reference a facility outside the manifest facility_scope."""
    n = int(n)
    for o in rng.sample(ds.orders, min(n, len(ds.orders))):
        o["facility_id"] = "F-FOREIGN"
    return _entry("foreign_facility", "ORPHAN_ENTITY",
                  "ids.facility_references_consistent", "degraded", "error",
                  "excluded", "CONDITIONAL", param=n, affected_count=n)


def _anomaly_defaulted_attributes(ds: Dataset, rng: random.Random, n: Any = 3) -> dict:
    """n orders carry no priority signal at all (blank priority AND
    commitment class) — a defaulted decision-relevant attribute."""
    n = int(n)
    for o in rng.sample(ds.orders, min(n, len(ds.orders))):
        o["priority_class"] = ""
        o["commitment_class"] = ""
    return _entry("defaulted_attributes", "LOW_CONFIDENCE_INPUT",
                  "ids.decision_relevant_attributes_populated", "flagged", "info",
                  "proceeded_flagged", "ACCEPTED", param=n, affected_count=n)


def _anomaly_sparse_optionals(ds: Dataset, rng: random.Random, n: Any = 1) -> dict:
    """Populate an optional column (release_date) on a sub-floor fraction of
    orders — present, non-empty, but sparse."""
    n = int(n)
    start = ds.reference_date.isoformat()
    for o in rng.sample(ds.orders, min(n, len(ds.orders))):
        o["release_date"] = start
    return _entry("sparse_optionals", "LOW_CONFIDENCE_INPUT",
                  "ids.optional_columns_are_not_sparse", "flagged", "info",
                  "proceeded_flagged", "ACCEPTED", param=n, affected_count=n)


def _anomaly_unused_transition_matrix(ds: Dataset, rng: random.Random, _: Any = None) -> dict:
    """setup_transitions.csv present, but no setup_family values are used
    (the converse of setup_family_without_matrix)."""
    fams = _FAMILIES[:2]
    ds.setup_transitions = [
        {"from_family": fams[0], "to_family": fams[1], "setup_minutes": "90",
         "setup_cost": "", "scrap_units": ""},
    ]
    ds.manifest["semantics"]["unlisted_transition_default"] = "base_setup"
    for line in ds.routing_lines:
        line["setup_family"] = ""
    return _entry("unused_transition_matrix", "AMBIGUOUS_SOURCE",
                  "ids.transition_matrix_references_declared_families", "degraded",
                  "error", "proceeded_flagged", "CONDITIONAL", param=None)


def _anomaly_no_valid_orders(ds: Dataset, rng: random.Random, _: Any = None) -> dict:
    """Every order has quantity 0 → zero in-scope orders."""
    for o in ds.orders:
        o["quantity"] = "0"
    return _entry("no_valid_orders", "MISSING_REFERENCE",
                  "ids.in_scope_orders_exist", "violated", "blocker", "blocked",
                  "REJECTED", param=None)


def _anomaly_no_resources(ds: Dataset, rng: random.Random, _: Any = None) -> dict:
    """resources.csv has no rows."""
    ds.resources = []
    return _entry("no_resources", "MISSING_REFERENCE",
                  "ids.in_scope_resources_exist", "violated", "blocker", "blocked",
                  "REJECTED", param=None)


def _anomaly_no_calendar_patterns(ds: Dataset, rng: random.Random, _: Any = None) -> dict:
    """calendars.csv carries no pattern rows — capacity is not optional (§5.6)."""
    ds.calendars = [r for r in ds.calendars if r.get("row_type") != "pattern"]
    return _entry("no_calendar_patterns", "MISSING_REFERENCE",
                  "ids.calendar_patterns_exist", "violated", "blocker", "blocked",
                  "REJECTED", param=None)


def _anomaly_incomplete_cost_core(ds: Dataset, rng: random.Random, field_name: Any = None) -> dict:
    """Delete a required cost_model.core field (§5.9)."""
    key = field_name or "tardiness_cost_per_hour"
    ds.cost_model.get("core", {}).pop(key, None)
    return _entry("incomplete_cost_core", "MISSING_REFERENCE",
                  "ids.cost_model_core_present", "violated", "blocker", "blocked",
                  "REJECTED", param=key)


def _anomaly_runrate_outlier(ds: Dataset, rng: random.Random, _: Any = None) -> dict:
    """One product's run rate is >10x its family median (§4 outlier).

    Seeds a dedicated family with three normal members and one gross outlier —
    three normals keep the median stable so the outlier stands clear (a
    two-member family's median is dragged by the outlier itself). The products
    are unreferenced by orders, which the gate does not flag."""
    for i in range(3):
        ds.products.append({
            "product_id": f"PROD-OUTLIER-N{i}", "uom": "EA",
            "facility_id": ds.facilities[0], "product_group": "outlier_family",
            "costing_lot_size": "100", "setup_minutes": "20",
            "production_minutes": "50", "cost_price": "10.0",
        })
    ds.products.append({
        "product_id": "PROD-OUTLIER-HUGE", "uom": "EA",
        "facility_id": ds.facilities[0], "product_group": "outlier_family",
        "costing_lot_size": "100", "setup_minutes": "20",
        "production_minutes": "60000", "cost_price": "10.0",  # 1200x the normals
    })
    return _entry("runrate_outlier", "STATISTICAL_OUTLIER",
                  "ids.durations_within_plausible_range", "flagged", "info",
                  "proceeded_flagged", "ACCEPTED", param=None)


def _anomaly_customer_without_master(ds: Dataset, rng: random.Random, _: Any = None) -> dict:
    """Orders carry customer_id and the manifest declares customer weighting,
    but customers.csv is absent (§5.10)."""
    ds.manifest["semantics"]["priority_precedence"] = "customer_over_order"
    for o in ds.orders:
        o["customer_id"] = "CUST-EXT"
    ds.customers = []
    return _entry("customer_without_master", "AMBIGUOUS_SOURCE",
                  "ids.customer_references_have_master", "degraded", "error",
                  "proceeded_flagged", "CONDITIONAL", param=None)


def _num(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# --- WIP coverage anomalies (docs/06 §5.13). Each builds a coherent base then
#     injects exactly one incoherence, reusing the first order's real route. ---

def _wip_context(ds: Dataset) -> tuple[dict, list[int], dict]:
    order = ds.orders[0]
    lines = sorted(
        (rl for rl in ds.routing_lines if rl["route_id"] == order["route_id"]
         and str(rl.get("active", "1")) == "1"),
        key=lambda r: int(r.get("sequence", "0") or "0"),
    )
    seqs = [int(rl["sequence"]) for rl in lines]
    res_by_seq = {int(rl["sequence"]): rl["resource_id"] for rl in lines}
    ds.manifest["semantics"]["wip_progress_basis"] = "remaining_minutes"
    return order, seqs, res_by_seq


def _anomaly_undeclared_wip_basis(ds: Dataset, rng: random.Random, _: Any = None) -> dict:
    """wip_status.csv present but manifest omits the REQUIRED wip_progress_basis
    declaration (§3) — the source cannot be interpreted (AMBIGUOUS_SOURCE)."""
    order = ds.orders[0]
    lines = sorted(
        (rl for rl in ds.routing_lines if rl["route_id"] == order["route_id"]
         and str(rl.get("active", "1")) == "1"),
        key=lambda r: int(r.get("sequence", "0") or "0"),
    )
    seq0 = int(lines[0]["sequence"])
    ds.wip_status = [{
        "order_id": order["order_id"], "sequence": str(seq0), "status": "complete",
        "actual_start": "2026-01-02T08:00:00", "actual_resource_id": lines[0]["resource_id"],
        "remaining_minutes": "", "quantity_complete": "",
    }]
    ds.manifest["semantics"].pop("wip_progress_basis", None)
    return _entry("undeclared_wip_basis", "AMBIGUOUS_SOURCE",
                  "ids.manifest_semantics_declared", "violated", "blocker", "blocked",
                  "REJECTED", param=None)


def _anomaly_wip_unknown_refs(ds: Dataset, rng: random.Random, _: Any = None) -> dict:
    order, seqs, res_by_seq = _wip_context(ds)
    ds.wip_status = [{
        "order_id": "ORD-DOES-NOT-EXIST", "sequence": str(seqs[0]),
        "status": "complete", "actual_start": "2026-01-02T08:00:00",
        "actual_resource_id": res_by_seq[seqs[0]],
        "remaining_minutes": "", "quantity_complete": "",
    }]
    return _entry("wip_unknown_refs", "ORPHAN_ENTITY",
                  "ids.wip_references_known_entities", "degraded", "error",
                  "excluded", "CONDITIONAL", param=None)


def _anomaly_wip_in_progress_incomplete(ds: Dataset, rng: random.Random, _: Any = None) -> dict:
    order, seqs, res_by_seq = _wip_context(ds)
    ds.wip_status = [{
        "order_id": order["order_id"], "sequence": str(seqs[0]),
        "status": "in_progress", "actual_start": "",  # missing observed start
        "actual_resource_id": res_by_seq[seqs[0]],
        "remaining_minutes": "60", "quantity_complete": "",
    }]
    return _entry("wip_in_progress_incomplete", "MALFORMED_FIELD",
                  "ids.wip_in_progress_rows_carry_progress", "degraded", "error",
                  "defaulted", "CONDITIONAL", param=None)


def _anomaly_wip_sequence_violation(ds: Dataset, rng: random.Random, _: Any = None) -> dict:
    order, seqs, res_by_seq = _wip_context(ds)
    if len(seqs) < 2:
        raise ValueError("wip_sequence_violation needs a >=2-step route")
    ds.wip_status = [
        {"order_id": order["order_id"], "sequence": str(seqs[0]),
         "status": "not_started", "actual_start": "", "actual_resource_id": "",
         "remaining_minutes": "", "quantity_complete": ""},
        {"order_id": order["order_id"], "sequence": str(seqs[1]),
         "status": "in_progress", "actual_start": "2026-01-02T08:00:00",
         "actual_resource_id": res_by_seq[seqs[1]],
         "remaining_minutes": "60", "quantity_complete": ""},
    ]
    return _entry("wip_sequence_violation", "LOW_CONFIDENCE_INPUT",
                  "ids.wip_progression_respects_sequence", "degraded", "error",
                  "proceeded_flagged", "CONDITIONAL", param=None)


def _anomaly_wip_complete_with_remaining(ds: Dataset, rng: random.Random, _: Any = None) -> dict:
    order, seqs, res_by_seq = _wip_context(ds)
    ds.wip_status = [{
        "order_id": order["order_id"], "sequence": str(seqs[0]),
        "status": "complete", "actual_start": "2026-01-02T08:00:00",
        "actual_resource_id": res_by_seq[seqs[0]],
        "remaining_minutes": "120", "quantity_complete": "",  # inconsistent
    }]
    return _entry("wip_complete_with_remaining", "VALUE_OUT_OF_RANGE",
                  "ids.wip_completion_is_internally_consistent", "degraded", "error",
                  "proceeded_flagged", "CONDITIONAL", param=None)


def _anomaly_wip_start_after_reference(ds: Dataset, rng: random.Random, _: Any = None) -> dict:
    order, seqs, res_by_seq = _wip_context(ds)
    after = (ds.reference_date + timedelta(days=3)).isoformat()
    ds.wip_status = [{
        "order_id": order["order_id"], "sequence": str(seqs[0]),
        "status": "in_progress", "actual_start": f"{after}T08:00:00",
        "actual_resource_id": res_by_seq[seqs[0]],
        "remaining_minutes": "60", "quantity_complete": "",
    }]
    return _entry("wip_start_after_reference", "VALUE_OUT_OF_RANGE",
                  "ids.wip_actual_starts_are_at_or_before_reference_date", "degraded",
                  "error", "proceeded_flagged", "CONDITIONAL", param=None)


_ANOMALY_FUNCS = {
    "missing_required_file": _anomaly_missing_required_file,
    "missing_manifest_field": _anomaly_missing_manifest_field,
    "manifest_schema_invalid": _anomaly_manifest_schema_invalid,
    "missing_columns": _anomaly_missing_columns,
    "blank_keys": _anomaly_blank_keys,
    "orphan_product_refs": _anomaly_orphan_product_refs,
    "orphan_route_refs": _anomaly_orphan_route_refs,
    "lineless_routes": _anomaly_lineless_routes,
    "duplicate_order_ids": _anomaly_duplicate_order_ids,
    "zero_lot_size": _anomaly_zero_lot_size,
    "inactive_route_refs": _anomaly_inactive_route_refs,
    "inverted_dates": _anomaly_inverted_dates,
    "foreign_facility": _anomaly_foreign_facility,
    "stale_due_dates": _anomaly_stale_due_dates,
    "placeholder_dates": _anomaly_placeholder_dates,
    "setup_family_without_matrix": _anomaly_setup_family_without_matrix,
    "unused_transition_matrix": _anomaly_unused_transition_matrix,
    "uncovered_priority_class": _anomaly_uncovered_priority_class,
    "customer_without_master": _anomaly_customer_without_master,
    "lock_on_unknown_order": _anomaly_lock_on_unknown_order,
    "no_valid_orders": _anomaly_no_valid_orders,
    "no_resources": _anomaly_no_resources,
    "no_calendar_patterns": _anomaly_no_calendar_patterns,
    "incomplete_cost_core": _anomaly_incomplete_cost_core,
    "runrate_outlier": _anomaly_runrate_outlier,
    "defaulted_attributes": _anomaly_defaulted_attributes,
    "sparse_optionals": _anomaly_sparse_optionals,
    "undeclared_wip_basis": _anomaly_undeclared_wip_basis,
    "wip_unknown_refs": _anomaly_wip_unknown_refs,
    "wip_in_progress_incomplete": _anomaly_wip_in_progress_incomplete,
    "wip_sequence_violation": _anomaly_wip_sequence_violation,
    "wip_complete_with_remaining": _anomaly_wip_complete_with_remaining,
    "wip_start_after_reference": _anomaly_wip_start_after_reference,
    "chunking_exam": _anomaly_chunking_exam,
}


# Rule → anomaly spec that triggers it (docs/06 §4 coverage matrix). Every
# implemented registry rule MUST have an entry here; the coverage test asserts
# completeness against RULE_REGISTRY, so a future rule added without an anomaly
# fails CI by construction. Value is a generate() anomaly spec string.
RULE_TO_ANOMALY: dict[str, str] = {
    "ids.submission_files_present": "missing_required_file:products.csv",
    "ids.manifest_schema_valid": "manifest_schema_invalid:ids_version",
    "ids.manifest_semantics_declared": "undeclared_wip_basis",
    "ids.required_columns_parse": "missing_columns:resources.csv:facility_id",
    "ids.key_fields_populated": "blank_keys:1",
    "ids.in_scope_orders_exist": "no_valid_orders",
    "ids.in_scope_resources_exist": "no_resources",
    "ids.calendar_patterns_exist": "no_calendar_patterns",
    "ids.cost_model_core_present": "incomplete_cost_core:tardiness_cost_per_hour",
    "ids.orders_resolve_to_products": "orphan_product_refs:5",
    "ids.orders_resolve_to_routes": "orphan_route_refs:5",
    "ids.routes_resolve_to_lines": "lineless_routes:1",
    "ids.operation_durations_computable": "zero_lot_size:2",
    "ids.order_identities_unique": "duplicate_order_ids:3",
    "ids.order_dates_internally_consistent": "inverted_dates:2",
    "ids.facility_references_consistent": "foreign_facility:2",
    "ids.orders_use_active_routes": "inactive_route_refs:3",
    "ids.priority_classes_priced": "uncovered_priority_class",
    "ids.setup_families_have_transition_matrix": "setup_family_without_matrix",
    "ids.transition_matrix_references_declared_families": "unused_transition_matrix",
    "ids.customer_references_have_master": "customer_without_master",
    "ids.locks_reference_known_entities": "lock_on_unknown_order:2",
    "ids.wip_references_known_entities": "wip_unknown_refs",
    "ids.wip_progression_respects_sequence": "wip_sequence_violation",
    "ids.wip_in_progress_rows_carry_progress": "wip_in_progress_incomplete",
    "ids.wip_actual_starts_are_at_or_before_reference_date": "wip_start_after_reference",
    "ids.wip_completion_is_internally_consistent": "wip_complete_with_remaining",
    "ids.durations_within_plausible_range": "runrate_outlier",
    "ids.due_dates_within_planning_horizon": "placeholder_dates:1",
    "ids.backlog_is_current": "stale_due_dates:2",
    "ids.decision_relevant_attributes_populated": "defaulted_attributes:3",
    "ids.optional_columns_are_not_sparse": "sparse_optionals:1",
}


def _parse_anomaly_spec(spec: str) -> tuple[str, Optional[str]]:
    if ":" in spec:
        name, param = spec.split(":", 1)
        return name, param
    return spec, None


# ---------------------------------------------------------------------------
# CSV / JSON writers
# ---------------------------------------------------------------------------

_COLUMNS = {
    "orders.csv": ["order_id", "product_id", "route_id", "quantity", "due_date",
                   "created_date", "release_date", "facility_id", "customer_id",
                   "priority_class", "commitment_class"],
    "routings.csv": ["route_id", "facility_id", "product_id", "status", "approved",
                     "version", "effective_from"],
    "routing_lines.csv": ["route_id", "sequence", "resource_id", "active",
                          "setup_minutes", "run_minutes_per_unit", "dwell_minutes",
                          "setup_family", "splittable", "min_chunk_minutes"],
    "products.csv": ["product_id", "uom", "facility_id", "product_group",
                      "costing_lot_size", "setup_minutes", "production_minutes",
                      "cost_price"],
    "resources.csv": ["resource_id", "facility_id", "resource_type", "parallel_units",
                        "calendar_id", "pool_id", "cost_rate"],
    "calendars.csv": ["calendar_id", "row_type", "day_of_week", "start_time", "end_time",
                        "exception_date", "exception_type", "reason"],
    "customers.csv": ["customer_id", "name", "priority_class", "notes"],
    "setup_transitions.csv": ["from_family", "to_family", "setup_minutes", "setup_cost", "scrap_units"],
    "locks.csv": ["order_id", "sequence", "resource_id", "start", "lock_type", "authority", "expiry"],
    "wip_status.csv": ["order_id", "sequence", "status", "actual_start",
                       "actual_resource_id", "remaining_minutes", "quantity_complete"],
}


def _write_csv(path: Path, fname: str, rows: list[dict], dropped: set[str] | None = None) -> None:
    cols = [c for c in _COLUMNS[fname] if not (dropped and c in dropped)]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in rows:
            w.writerow({c: row.get(c, "") for c in cols})


def _write_submission(out_dir: Path, ds: Dataset) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    if "manifest.json" not in ds.omit_files:
        manifest_out = {k: v for k, v in ds.manifest.items() if k not in ds.drop_manifest_keys}
        (out_dir / "manifest.json").write_text(json.dumps(manifest_out, indent=2), encoding="utf-8")

    table_map = {
        "orders.csv": ds.orders, "routings.csv": ds.routings,
        "routing_lines.csv": ds.routing_lines, "products.csv": ds.products,
        "resources.csv": ds.resources, "calendars.csv": ds.calendars,
        "customers.csv": ds.customers, "setup_transitions.csv": ds.setup_transitions,
        "locks.csv": ds.locks, "wip_status.csv": ds.wip_status,
    }
    for fname, rows in table_map.items():
        if fname in ds.omit_files:
            continue
        if (fname in ("customers.csv", "setup_transitions.csv", "locks.csv",
                      "wip_status.csv") and not rows):
            continue  # optional doorway tables: omit entirely when unused
        _write_csv(out_dir / fname, fname, rows, ds.drop_columns.get(fname))

    if "cost_model.json" not in ds.omit_files:
        (out_dir / "cost_model.json").write_text(
            json.dumps(ds.cost_model, indent=2), encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate(
    out_dir: Path | str,
    orders: Optional[int] = None,
    resources: Optional[int] = None,
    facilities: Optional[int] = None,
    seed: int = 1,
    scenario: str = "clean_small",
    anomalies: Optional[list[str]] = None,
    reference_date: Optional[date] = None,
) -> dict[str, Any]:
    """Generate an IDS submission + truth_manifest.json under out_dir.

    CLI-supplied orders/resources/facilities/anomalies override the scenario
    preset's defaults; None means "use the preset's value".
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario}'. Known: {sorted(SCENARIOS)}")
    preset = SCENARIOS[scenario]
    n_orders = orders if orders is not None else preset["orders"]
    n_resources = resources if resources is not None else preset["resources"]
    n_facilities = facilities if facilities is not None else preset["facilities"]
    anomaly_specs = anomalies if anomalies is not None else list(preset["anomalies"])
    ref_date = reference_date or date(2026, 1, 5)  # a Monday

    out_dir = Path(out_dir)
    rng = random.Random(seed)

    ds = _build_base(
        rng, n_orders, n_resources, n_facilities, ref_date,
        with_customers=preset.get("with_customers", False),
        cost_profile=preset.get("cost_profile", "C0"),
    )

    truth_extra: dict[str, Any] = {}
    if preset.get("bottleneck"):
        _apply_bottleneck(ds, rng)
        truth_extra["bottleneck_orders"] = [ds.orders[0]["order_id"], ds.orders[1]["order_id"]]
        truth_extra["must_win_order_id"] = ds.orders[0]["order_id"]  # critical priority
    if preset.get("transitions"):
        _apply_transitions(ds, rng)
        truth_extra["transition_families"] = _FAMILIES[:2]
    if preset.get("locks"):
        oid, rid, start_iso = _apply_locks(ds, rng)
        truth_extra["lock"] = {"order_id": oid, "resource_id": rid, "start": start_iso}
    if preset.get("overtime"):
        truth_extra["overtime"] = _apply_overtime_required(ds, rng)
    if preset.get("mid_replan"):
        truth_extra["mid_replan"] = _apply_mid_replan(ds, rng)
    if preset.get("multi_route"):
        truth_extra["multi_route"] = _apply_multi_route(
            ds, rng, distinct_rates=preset.get("multi_route_distinct", False))
    if preset.get("busy_board"):
        truth_extra["busy_board"] = _apply_busy_board(ds, rng)

    anomaly_entries: list[dict] = []
    for spec in anomaly_specs:
        name, param = _parse_anomaly_spec(spec)
        fn = _ANOMALY_FUNCS[name]
        entry = fn(ds, rng, param)
        anomaly_entries.append(entry)

    _write_submission(out_dir, ds)

    if preset.get("feel"):
        # Feel fixture (docs/07 Phase 3): a hands-on cockpit board, not a
        # truth-bearing scenario. It seeds no anomalies and is tight/late BY
        # DESIGN, so there is nothing to assert. Emit a descriptive marker —
        # clearly NOT a truth_manifest — and return it.
        marker = {
            "feel_fixture": True,
            "scenario": scenario, "seed": seed,
            "orders": n_orders, "resources": n_resources, "facilities": n_facilities,
            "reference_date": ref_date.isoformat(),
            "expected_costing_grade": preset.get("cost_profile", "C0"),
            **truth_extra,
        }
        (out_dir / "feel_fixture.json").write_text(
            json.dumps(marker, indent=2), encoding="utf-8")
        return marker

    grade_order = {"REJECTED": 0, "CONDITIONAL": 1, "ACCEPTED": 2}
    expected_grade = "ACCEPTED"
    for entry in anomaly_entries:
        floor = entry.get("expected_grade_floor", "ACCEPTED")
        if grade_order[floor] < grade_order[expected_grade]:
            expected_grade = floor

    truth_manifest = {
        "scenario": scenario, "seed": seed,
        "orders": n_orders, "resources": n_resources, "facilities": n_facilities,
        "reference_date": ref_date.isoformat(),
        "expected_certificate_grade": expected_grade,
        "expected_costing_grade": preset.get("cost_profile", "C0"),
        "anomalies": anomaly_entries,
        **truth_extra,
    }
    (out_dir / "truth_manifest.json").write_text(
        json.dumps(truth_manifest, indent=2), encoding="utf-8"
    )
    return truth_manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthetic ERP dataset generator (IDS-conformant)")
    parser.add_argument("--orders", type=int, default=None)
    parser.add_argument("--resources", type=int, default=None)
    parser.add_argument("--facilities", type=int, default=None)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--scenario", default="clean_small", choices=sorted(SCENARIOS))
    parser.add_argument("--anomalies", default=None,
                        help="Comma-separated anomaly specs, e.g. 'orphan_product_refs:5,duplicate_order_ids:2'")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    anomalies = args.anomalies.split(",") if args.anomalies else None
    truth = generate(
        out_dir=args.out, orders=args.orders, resources=args.resources,
        facilities=args.facilities, seed=args.seed, scenario=args.scenario,
        anomalies=anomalies,
    )
    print(f"[generate_erp_dataset] wrote submission to {args.out}")
    if truth.get("feel_fixture"):
        print("[generate_erp_dataset] feel fixture — no truth manifest "
              "(marker: feel_fixture.json)")
    else:
        print(f"[generate_erp_dataset] expected_certificate_grade={truth['expected_certificate_grade']}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

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
    cost_model: dict[str, Any] = field(default_factory=dict)
    # bookkeeping for anomalies / assertions
    priority_multipliers: dict[str, float] = field(default_factory=dict)
    omit_files: set[str] = field(default_factory=set)


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


def _apply_chunking_exam(ds: Dataset, rng: random.Random, n: int) -> list[str]:
    """Give n orders an operation whose duration exceeds every eligible
    resource's shift window (720 min) on every eligible resource — the
    validator's pre-solve INFEASIBLE_SUBSET check must exclude them."""
    affected: list[str] = []
    for i in range(min(n, len(ds.orders))):
        order = ds.orders[i]
        prod = next(p for p in ds.products if p["product_id"] == order["product_id"])
        prod["costing_lot_size"] = "1"
        prod["production_minutes"] = "3000"  # 3000 min/unit -> any qty >=1 exceeds 720 min shift
        order["quantity"] = "5"
        affected.append(order["order_id"])
    return affected


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
    affected = _apply_chunking_exam(ds, rng, int(n))
    return {
        "anomaly": "chunking_exam", "param": int(n), "affected_order_ids": affected,
        "expected_finding_code": "INFEASIBLE_SUBSET", "expected_severity": "error",
        "expected_disposition": "excluded", "expected_grade_floor": "ACCEPTED",
    }


_ANOMALY_FUNCS = {
    "missing_required_file": _anomaly_missing_required_file,
    "missing_manifest_field": _anomaly_missing_manifest_field,
    "orphan_product_refs": _anomaly_orphan_product_refs,
    "orphan_route_refs": _anomaly_orphan_route_refs,
    "duplicate_order_ids": _anomaly_duplicate_order_ids,
    "zero_lot_size": _anomaly_zero_lot_size,
    "inactive_route_refs": _anomaly_inactive_route_refs,
    "stale_due_dates": _anomaly_stale_due_dates,
    "placeholder_dates": _anomaly_placeholder_dates,
    "setup_family_without_matrix": _anomaly_setup_family_without_matrix,
    "uncovered_priority_class": _anomaly_uncovered_priority_class,
    "lock_on_unknown_order": _anomaly_lock_on_unknown_order,
    "chunking_exam": _anomaly_chunking_exam,
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
}


def _write_csv(path: Path, fname: str, rows: list[dict]) -> None:
    cols = _COLUMNS[fname]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in rows:
            w.writerow({c: row.get(c, "") for c in cols})


def _write_submission(out_dir: Path, ds: Dataset) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    if "manifest.json" not in ds.omit_files:
        (out_dir / "manifest.json").write_text(json.dumps(ds.manifest, indent=2), encoding="utf-8")

    table_map = {
        "orders.csv": ds.orders, "routings.csv": ds.routings,
        "routing_lines.csv": ds.routing_lines, "products.csv": ds.products,
        "resources.csv": ds.resources, "calendars.csv": ds.calendars,
        "customers.csv": ds.customers, "setup_transitions.csv": ds.setup_transitions,
        "locks.csv": ds.locks,
    }
    for fname, rows in table_map.items():
        if fname in ds.omit_files:
            continue
        if fname in ("customers.csv", "setup_transitions.csv", "locks.csv") and not rows:
            continue  # optional doorway tables: omit entirely when unused
        _write_csv(out_dir / fname, fname, rows)

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

    anomaly_entries: list[dict] = []
    for spec in anomaly_specs:
        name, param = _parse_anomaly_spec(spec)
        fn = _ANOMALY_FUNCS[name]
        entry = fn(ds, rng, param)
        anomaly_entries.append(entry)

    _write_submission(out_dir, ds)

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
    print(f"[generate_erp_dataset] expected_certificate_grade={truth['expected_certificate_grade']}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

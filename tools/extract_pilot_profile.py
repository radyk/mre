#!/usr/bin/env python3
"""CU1 (Session 4B.2) — extract a GENERATOR PROFILE from the historical extract.

R-SC1 (docs/04): the ticketing extract is INTELLIGENCE, not a fixture. It is
demoted from test data to a profile SOURCE. This tool reads the extract and
emits the distributions the pilot_scale synthetic plant is sized against —
volumes, order-size distribution, product-family cardinality, machine count,
demand-arrival and due-date shapes — and NOTHING about plant physics
(calendars, downtime, capabilities, setup families, alternates, priorities),
which are AUTHORED deliberately in the generator (see _apply_pilot_scale).

What is MEASURED here vs. what is AUTHORED downstream is stated verbatim in the
provenance note (datasets/pilot_scale/PROFILE_PROVENANCE.md).

Deterministic: reads files in a fixed order, computes exact quantiles, no
sampling, no randomness. SalesOrder.csv (189 MB, demand *history*) is
deliberately NOT read — OpenWorkOrder.csv IS the work-order backlog we would
schedule, and it carries its own arrival (CreatedDate) and due (ScheduleDate)
shapes.

Usage:
    python tools/extract_pilot_profile.py
    python tools/extract_pilot_profile.py --raw-data raw_data --out datasets/pilot_scale/pilot_profile.json
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "raw_data"
OUT = REPO / "datasets" / "pilot_scale" / "pilot_profile.json"
PROV = REPO / "datasets" / "pilot_scale" / "PROFILE_PROVENANCE.md"

_QUANTILES = [0.10, 0.25, 0.50, 0.75, 0.90, 0.99]


def _quantiles(values: list[float]) -> dict[str, float]:
    """Exact nearest-rank quantiles + min/max/mean over a numeric sample."""
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return {}
    n = len(xs)
    out: dict[str, float] = {"n": n, "min": xs[0], "max": xs[-1],
                             "mean": round(sum(xs) / n, 3)}
    for q in _QUANTILES:
        idx = min(n - 1, max(0, int(round(q * (n - 1)))))
        out[f"p{int(q * 100)}"] = xs[idx]
    return out


def _num(s: str) -> Optional[float]:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _parse_date(s: str) -> Optional[datetime]:
    s = (s or "").strip().rstrip(";")
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:26], fmt)
        except ValueError:
            continue
    return None


def extract_profile(raw_dir: Path) -> dict:
    # --- OpenWorkOrder.csv: the work-order backlog (volumes, sizes, shapes) ---
    wo = _read(raw_dir / "OpenWorkOrder.csv")
    wo_qty = [q for r in wo if (q := _num(r.get("WoQuantity", ""))) and q > 0]
    facilities = Counter(r.get("FacilityCode", "").strip() for r in wo if r.get("FacilityCode"))
    lead_days: list[float] = []
    for r in wo:
        sched = _parse_date(r.get("ScheduleDate", ""))
        created = _parse_date(r.get("CreatedDate", ""))
        if sched and created:
            lead_days.append((sched - created).total_seconds() / 86400.0)

    # --- Product.csv: family cardinality + real setup/production minutes ------
    prod = _read(raw_dir / "Product.csv")
    groups = Counter(r.get("ProductGroup", "").strip() for r in prod if r.get("ProductGroup"))
    setup_min = [s for r in prod if (s := _num(r.get("SetUpMinutes", ""))) is not None]
    prod_min = [p for r in prod if (p := _num(r.get("ProductionMinutes", ""))) is not None and p > 0]

    # --- Routing / RoutingLines: routing depth + workcenter count ------------
    rlines = _read(raw_dir / "RoutingLines.csv")
    workcenters = Counter(r.get("Workcenter", "").strip() for r in rlines if r.get("Workcenter"))
    depth = Counter(r.get("RoutingCode", "").strip() for r in rlines if r.get("RoutingCode"))
    # workcenters-per-facility (workcenter code prefix "Fxxx/Dyyyy")
    wc_by_fac: dict[str, set] = {}
    for wc in workcenters:
        fac = wc.split("/", 1)[0] if "/" in wc else wc
        wc_by_fac.setdefault(fac, set()).add(wc)

    # top families by share (the cardinality shape the generator mirrors)
    total_prod = sum(groups.values()) or 1
    top_groups = [{"group": g, "count": c, "share": round(c / total_prod, 4)}
                  for g, c in groups.most_common(12)]

    return {
        "provenance": {
            "source_dir": raw_dir.name,
            "source_files": ["OpenWorkOrder.csv", "Product.csv",
                             "Routing.csv", "RoutingLines.csv"],
            "not_read": ["SalesOrder.csv (189 MB demand history; "
                         "OpenWorkOrder IS the backlog)"],
            "ruling": "R-SC1 — the extract is intelligence, not a fixture; "
                      "this profile carries SHAPES only, no plant physics.",
        },
        "backlog": {
            "open_work_order_count": len(wo),
            "product_count": len(prod),
            "route_count": len(depth),
        },
        "order_quantity": _quantiles(wo_qty),
        "product_family": {
            "family_count": len(groups),
            "top_families": top_groups,
        },
        "product_minutes": {
            "setup_minutes": _quantiles(setup_min),
            "production_minutes": _quantiles(prod_min),
        },
        "routing": {
            "distinct_workcenter_count": len(workcenters),
            "ops_per_route": _quantiles([float(c) for c in depth.values()]),
        },
        "machines": {
            "facility_count": len(wc_by_fac),
            "workcenters_per_facility": _quantiles(
                [float(len(s)) for s in wc_by_fac.values()]),
            "backlog_facility_count": len(facilities),
            "top_facilities_by_backlog": [
                {"facility": f, "work_orders": c}
                for f, c in facilities.most_common(8)],
        },
        "lead_time_days": _quantiles(lead_days),
    }


def _prov_note(profile: dict) -> str:
    bl = profile["backlog"]
    oq = profile["order_quantity"]
    pf = profile["product_family"]
    rt = profile["routing"]
    lt = profile["lead_time_days"]
    return f"""# pilot_profile provenance — MEASURED vs. AUTHORED

Generated by `tools/extract_pilot_profile.py` from the historical extract
(`raw_data/`). Under **R-SC1** (docs/04, Session 4B.2) the extract is
*intelligence*, not a fixture: it supplies **shapes**, never plant physics.

## What is MEASURED (this file → `pilot_profile.json`)

Drawn from `OpenWorkOrder.csv` (the work-order backlog), `Product.csv`
(the product master), and `Routing.csv`/`RoutingLines.csv` (the process master):

| Dimension | Measured value |
|---|---|
| Backlog volume | {bl['open_work_order_count']:,} open work orders |
| Product master | {bl['product_count']:,} products, {rt['ops_per_route'].get('n', 0):,} routes |
| Order size (WoQuantity) | median {oq.get('p50')}, p90 {oq.get('p90')}, max {oq.get('max')} (heavy-tailed) |
| Product families | {pf['family_count']} product groups |
| Routing depth | median {rt['ops_per_route'].get('p50')} ops/route, max {rt['ops_per_route'].get('max')} |
| Distinct workcenters | {rt['distinct_workcenter_count']} |
| Facilities | {profile['machines']['facility_count']} |
| Lead time (ScheduleDate − CreatedDate) | median {lt.get('p50')} d, p90 {lt.get('p90')} d |

`SalesOrder.csv` (189 MB) is **not read**: it is demand *history*; the work-order
backlog carries its own arrival (`CreatedDate`) and due (`ScheduleDate`) shapes.

## What is AUTHORED (downstream, in the generator — NOT here)

Everything a schedule's *physics* turns on is authored by hand in the
`pilot_scale` synthetic plant (`tools/generate_erp_dataset.py::_apply_pilot_scale`),
at Glass-Box discipline, so every behavior is nameable and predicted before the
solve:

- **Calendars & downtime** — shift patterns, weekend closures, a planned
  maintenance window, overtime windows.
- **Capability groups & alternates** — which machines can run which ops, at
  **honest differing rates** (a real cross-machine price).
- **Setup families & changeover matrix.**
- **Priority / customer weights** — POPULATED, deliberately. (The Glass Box's
  eternal warning: an empty priority column is a silent lie; it must not recur.)
- **Splittable long jobs** — the resumable monster jobs the rolling horizon must
  admit early via gravity.

The extract's real per-product minutes and family cardinality *inform* the
authored physics (so the synthetic plant feels like this one), but no physics
value is copied blind from a single extract row.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract a generator profile (R-SC1)")
    ap.add_argument("--raw-data", default=str(RAW))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    raw_dir = Path(args.raw_data)
    if not raw_dir.is_dir():
        print(f"ERROR: {raw_dir} not found")
        return 1

    print(f"[extract_pilot_profile] reading {raw_dir} …")
    profile = extract_profile(raw_dir)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    PROV.write_text(_prov_note(profile), encoding="utf-8")
    print(f"[extract_pilot_profile] wrote {out}")
    print(f"[extract_pilot_profile] wrote {PROV}")
    print(f"[extract_pilot_profile] backlog={profile['backlog']['open_work_order_count']} "
          f"products={profile['backlog']['product_count']} "
          f"families={profile['product_family']['family_count']} "
          f"workcenters={profile['routing']['distinct_workcenter_count']}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

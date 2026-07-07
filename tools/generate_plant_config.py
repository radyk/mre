"""Generate plant_config.json from raw_data/.

Scans distinct Workcenter values in RoutingLines for in-scope routes
(OpenWorkOrder.ScheduleDate >= reference_date) and writes a starter
plant_config.json. The user then edits parallel_units and shift overrides.

Usage:
    python tools/generate_plant_config.py
    python tools/generate_plant_config.py --raw-data raw_data --out plant_config.json --reference-date 2025-03-22
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-data", default="raw_data")
    parser.add_argument("--out", default="plant_config.json")
    parser.add_argument("--reference-date", default="2025-03-22")
    args = parser.parse_args(argv)

    raw_dir = Path(args.raw_data)
    ref_date = date.fromisoformat(args.reference_date)

    # Step 1: in-scope routes from OpenWorkOrder
    in_scope_routes: set[str] = set()
    wo_path = raw_dir / "OpenWorkOrder.csv"
    with open(wo_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sdate_str = row.get("ScheduleDate", "").strip()[:10]
            try:
                sdate = date.fromisoformat(sdate_str)
            except ValueError:
                continue
            if sdate >= ref_date:
                rc = row.get("RouteCode", "").strip()
                if rc:
                    in_scope_routes.add(rc)

    # Step 2: distinct Workcenter values for active lines on in-scope routes
    wc_set: set[str] = set()
    rl_path = raw_dir / "RoutingLines.csv"
    with open(rl_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("RoutingCode", "").strip() not in in_scope_routes:
                continue
            if str(row.get("Active", "0")).strip() != "1":
                continue
            wc = row.get("Workcenter", "").strip()
            if wc:
                wc_set.add(wc)

    # Step 3: distinct workcenter codes (D-codes) from full strings
    wc_codes: set[str] = set()
    for wc in wc_set:
        parts = wc.split("/", 1)
        if len(parts) == 2:
            wc_codes.add(parts[1])
        else:
            wc_codes.add(wc)

    config = {
        "reference_date": args.reference_date,
        "workcenter_defaults": {
            "parallel_units": 1,
            "shift_days": [0, 1, 2, 3, 4, 5],
            "shift_start": "07:00",
            "shift_end": "19:00",
        },
        "workcenters": {
            code: {"parallel_units": 1}
            for code in sorted(wc_codes)
        },
        "facility_overrides": {},
    }

    out_path = Path(args.out)
    out_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    print(f"Wrote {out_path}")
    print(f"  reference_date : {args.reference_date}")
    print(f"  in-scope routes: {len(in_scope_routes)}")
    print(f"  workcenters    : {len(wc_set)} strings -> {len(wc_codes)} D-codes")
    print(f"Edit {out_path} to set parallel_units and shift overrides per workcenter.")


if __name__ == "__main__":
    main()

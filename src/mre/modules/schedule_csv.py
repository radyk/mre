"""Generate schedule.csv from extraction results.

Columns: work_orders, op_seq, chunk_seq, setup_family, machine, start, end,
         duration_min, production_cost.

Resumable (chunked, docs/05 R-C3) operations produce multiple rows sharing
the same (work_orders, op_seq, machine) key — one per calendar-window chunk
— so the operation groups naturally; chunk_seq (1-indexed) orders them.
Non-resumable operations keep a single row with chunk_seq blank, unchanged
from the pre-Rep-2 format. production_cost is prorated per chunk by its
share of the assignment's total working minutes, so summing a group's rows
reproduces the assignment's true cost — never billing the pause.

Sorted by machine then start. External names only — no UUIDs.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, TextIO

UTC = timezone.utc


def generate_schedule_csv(
    assignments: list[dict[str, Any]],
    operations: list[dict[str, Any]],
    fulfillments: list[dict[str, Any]],
    demands: list[dict[str, Any]],
    identity_map,
    out: TextIO | None = None,
) -> str:
    """Build schedule.csv content and optionally write to *out*.

    Returns the CSV as a string. When *out* is provided it is also written there.

    identity_map is a IdentityMap instance (has .get_external_name(entity_id) → str).
    """
    ops_by_id = {o["id"]: o for o in operations}
    # workpackage_ref → list of work_order external names (sorted for determinism)
    wp_to_wo_names: dict[str, list[str]] = {}
    demand_name_by_id: dict[str, str] = {}
    for d in demands:
        # Prefer ERP work_order ref; fall back to canonical ID prefix
        wo_name = _external_name(d["id"], identity_map) or d["id"][:8]
        demand_name_by_id[d["id"]] = wo_name
    for f in fulfillments:
        wp_id = f["workpackage_ref"]
        d_id = f["demand_ref"]
        name = demand_name_by_id.get(d_id, d_id)
        wp_to_wo_names.setdefault(wp_id, []).append(name)
    for wp_id in wp_to_wo_names:
        wp_to_wo_names[wp_id] = sorted(set(wp_to_wo_names[wp_id]))

    rows = []
    for asgn in assignments:
        op_id = asgn["operation_ref"]
        op = ops_by_id.get(op_id, {})
        wp_id = asgn["workpackage_ref"]
        resource_id = asgn["resource_id"]

        wo_names = wp_to_wo_names.get(wp_id, [])
        work_orders = "+".join(wo_names) if wo_names else wp_id

        machine = _external_name(resource_id, identity_map) or resource_id

        run_windows = asgn.get("run_windows") or [
            {"start": asgn["run_start"], "end": asgn["run_end"]}
        ]
        total_cost = round(asgn.get("production_cost", 0.0), 4)
        total_working_min = sum(
            int((datetime.fromisoformat(w["end"]) - datetime.fromisoformat(w["start"])).total_seconds() / 60)
            for w in run_windows
        ) or 1
        is_chunked = len(run_windows) > 1

        for idx, w in enumerate(run_windows, start=1):
            start_dt = datetime.fromisoformat(w["start"])
            end_dt = datetime.fromisoformat(w["end"])
            duration_min = int((end_dt - start_dt).total_seconds() / 60)
            chunk_cost = round(total_cost * duration_min / total_working_min, 4)

            rows.append({
                "work_orders": work_orders,
                "op_seq": op.get("sequence", ""),
                "chunk_seq": idx if is_chunked else "",
                "setup_family": op.get("setup_family", ""),
                "machine": machine,
                "start": w["start"],
                "end": w["end"],
                "duration_min": duration_min,
                "production_cost": chunk_cost,
            })

    rows.sort(key=lambda r: (r["machine"], r["start"]))

    fieldnames = ["work_orders", "op_seq", "chunk_seq", "setup_family", "machine",
                  "start", "end", "duration_min", "production_cost"]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    content = buf.getvalue()

    if out is not None:
        out.write(content)

    return content


def _external_name(entity_id: str, identity_map) -> str | None:
    """Look up the first ERP external name for an entity UUID via the identity map."""
    if identity_map is None:
        return None
    try:
        refs = identity_map.external_refs(entity_id)
        if refs:
            return refs[0].value
    except Exception:
        pass
    return None

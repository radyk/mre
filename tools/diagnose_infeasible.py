"""Diagnose solver INFEASIBLE root cause.

Run from repo root:  python tools/diagnose_infeasible.py
"""
from __future__ import annotations
import re
import sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, "src")

from mre.modules.snapshot_store import SnapshotStore

UTC = timezone.utc
SHIFT_WINDOW_MIN = 720.0


def parse_td_sec(raw) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    if not isinstance(raw, str):
        return 0.0
    m = re.match(
        r"^P(?:(\d+\.?\d*)D)?(?:T(?:(\d+\.?\d*)H)?(?:(\d+\.?\d*)M)?(?:(\d+\.?\d*)S)?)?$", raw,
    )
    if not m:
        return 0.0
    return (
        float(m.group(1) or 0) * 86400
        + float(m.group(2) or 0) * 3600
        + float(m.group(3) or 0) * 60
        + float(m.group(4) or 0)
    )


def parse_dt(s) -> datetime:
    if not s:
        return datetime(2099, 1, 1, tzinfo=UTC)
    dt = datetime.fromisoformat(str(s)[:19])
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def longest_shift_minutes(cal: dict) -> float:
    bp = cal.get("base_pattern", {})
    days = bp.get("weekdays", [])
    if not days:
        return 0.0
    start = bp.get("shift_start", "07:00")
    end = bp.get("shift_end", "19:00")
    try:
        h_s, m_s = (int(x) for x in start.split(":"))
        h_e, m_e = (int(x) for x in end.split(":"))
        return float((h_e * 60 + m_e) - (h_s * 60 + m_s))
    except (ValueError, AttributeError):
        return 0.0


def main():
    store = SnapshotStore("mre_output/snapshots")
    reader = store.load_snapshot("snap-run")

    demands = {d["id"]: d for d in reader.iter_entities("demand")}
    products = {p["id"]: p for p in reader.iter_entities("product")}
    processes = {pr["id"]: pr for pr in reader.iter_entities("process")}
    specs = {s["id"]: s for s in reader.iter_entities("operationspec")}
    resources = {r["id"]: r for r in reader.iter_entities("resource")}
    calendars = {c["id"]: c for c in reader.iter_entities("calendar")}

    res_window = {}
    for rid, res in resources.items():
        cal_id = res.get("calendar_ref")
        if cal_id and cal_id in calendars:
            res_window[rid] = longest_shift_minutes(calendars[cal_id])
        else:
            res_window[rid] = 0.0

    prod_to_proc = {}
    for p in products.values():
        pref = p.get("process_ref")
        if pref and pref in processes:
            prod_to_proc[p["id"]] = processes[pref]

    # Check 1: op durations for admitted demands
    print("=== Check 1: Op duration violations (admitted demands) ===")
    op_violations = []
    for d in demands.values():
        qty_raw = d.get("quantity", {})
        qty = float(qty_raw.get("value", 0) if isinstance(qty_raw, dict) else qty_raw or 0)
        if qty <= 0:
            continue
        wono = next((e["value"] for e in d.get("external_refs", []) if e.get("type") == "work_order"), "?")
        proc = prod_to_proc.get(d.get("product_ref", ""))
        if not proc:
            continue
        for spec_id in proc.get("operation_specs", []):
            spec = specs.get(spec_id)
            if not spec:
                continue
            rr_sec = parse_td_sec(spec.get("run_rate"))
            setup_sec = parse_td_sec(spec.get("base_setup"))
            total_min = (qty * rr_sec + setup_sec) / 60.0
            if total_min > SHIFT_WINDOW_MIN:
                op_violations.append((wono, qty, rr_sec / 60, total_min))

    distinct_wos = len({v[0] for v in op_violations})
    print(f"  Total (demand, spec) violations: {len(op_violations)}")
    print(f"  Distinct WOs: {distinct_wos}")
    if op_violations:
        op_violations.sort(key=lambda x: -x[3])
        for wono, qty, rr, tot in op_violations[:5]:
            print(f"    {wono}: qty={qty:.0f} x rr={rr:.4f}m = {tot:.0f}m")

    # Check 2: earliest_start > due
    print("\n=== Check 2: earliest_start > due (impossible window) ===")
    impossible = []
    for d in demands.values():
        es = d.get("earliest_start")
        due = d.get("due")
        if not es or not due:
            continue
        es_dt = parse_dt(es)
        due_dt = parse_dt(due)
        if es_dt > due_dt:
            wono = next((e["value"] for e in d.get("external_refs", []) if e.get("type") == "work_order"), "?")
            impossible.append((wono, es, due))
    print(f"  Demands with earliest_start > due: {len(impossible)}")
    for wono, es, due in impossible[:5]:
        print(f"    {wono}: earliest={es} due={due}")

    # Check 3: Compute solver horizon and look for invalid start-var domains
    print("\n=== Check 3: Solver horizon and domain validity ===")
    all_earliest = [parse_dt(d.get("earliest_start")) for d in demands.values() if d.get("earliest_start")]
    all_due = [parse_dt(d.get("due")) for d in demands.values() if d.get("due")]

    if all_earliest:
        hs = min(all_earliest).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        hs = datetime.now(UTC)
    if all_due:
        he = max(all_due).replace(hour=23, minute=59, second=59) + timedelta(days=7)
    else:
        he = hs + timedelta(days=60)

    horizon_minutes = int((he - hs).total_seconds() / 60)
    print(f"  horizon_start: {hs.date()}")
    print(f"  horizon_end:   {he.date()}")
    print(f"  horizon_minutes: {horizon_minutes}")

    domain_violations = []
    for d in demands.values():
        es_str = d.get("earliest_start")
        wp_earliest_min = 0
        if es_str:
            es_dt = parse_dt(es_str)
            wp_earliest_min = max(0, int((es_dt - hs).total_seconds() / 60))

        proc = prod_to_proc.get(d.get("product_ref", ""))
        if not proc:
            continue
        qty_raw = d.get("quantity", {})
        qty = float(qty_raw.get("value", 0) if isinstance(qty_raw, dict) else qty_raw or 0)

        for spec_id in proc.get("operation_specs", []):
            spec = specs.get(spec_id)
            if not spec:
                continue
            rr_sec = parse_td_sec(spec.get("run_rate"))
            setup_sec = parse_td_sec(spec.get("base_setup"))
            # solver uses max(1, total_seconds/60) for total_min
            total_sec = qty * rr_sec + setup_sec
            total_min = max(1, int(total_sec / 60))

            ub = horizon_minutes - total_min
            if ub < wp_earliest_min:
                wono = next((e["value"] for e in d.get("external_refs", []) if e.get("type") == "work_order"), "?")
                domain_violations.append({
                    "wono": wono,
                    "wp_earliest_min": wp_earliest_min,
                    "ub": ub,
                    "total_min": total_min,
                    "horizon_minutes": horizon_minutes,
                })

    print(f"  s_var domain contradictions (ub < lb): {len(domain_violations)}")
    for v in domain_violations[:10]:
        print(f"    {v['wono']}: lb={v['wp_earliest_min']} ub={v['ub']} total={v['total_min']} horizon={v['horizon_minutes']}")

    # Check 4: operations with total = 0 (solver forces to 1, still fine but worth noting)
    print("\n=== Check 4: Zero-duration operations (solver rounds to 1) ===")
    zero_dur = 0
    for d in demands.values():
        qty_raw = d.get("quantity", {})
        qty = float(qty_raw.get("value", 0) if isinstance(qty_raw, dict) else qty_raw or 0)
        proc = prod_to_proc.get(d.get("product_ref", ""))
        if not proc:
            continue
        for spec_id in proc.get("operation_specs", []):
            spec = specs.get(spec_id)
            if not spec:
                continue
            rr_sec = parse_td_sec(spec.get("run_rate"))
            setup_sec = parse_td_sec(spec.get("base_setup"))
            if (qty * rr_sec + setup_sec) == 0.0:
                zero_dur += 1
    print(f"  Zero-duration (demand, spec) pairs: {zero_dur}")


if __name__ == "__main__":
    main()

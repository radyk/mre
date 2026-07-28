#!/usr/bin/env python3
"""Session 4B.7 item 5 — the fixture accounting, KEYED BY OPERATION IDENTITY.

A positional diff over a reordered list reports hundreds of "moved" values and
tells you nothing (4B.6a measured 639). This keys every placement by op id and
every tray item by order id, so "the same 56 ops, 3 changed machine" is a fact
rather than an impression.

Usage:
    python tools/spikes/tiebreak_4b6c/fixture_account.py snapshot BEFORE.json
    python tools/spikes/tiebreak_4b6c/fixture_account.py compare BEFORE.json AFTER.json
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "tests" / "cockpit" / "fixtures"
SETS = ["rolling", "rolling_empty", "rolling_coarse_hot"]


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def _placements(doc: dict) -> dict:
    """op_id -> (resource, start, end, region). Region is committed/active."""
    out = {}
    for region in ("committed", "active"):
        for row in (doc.get("rolling") or {}).get(region) or []:
            for op in row.get("operations", []) or []:
                out[op.get("operation_id") or op.get("id")] = {
                    "resource": row.get("resource_id") or op.get("resource_id"),
                    "start": op.get("start"), "end": op.get("end"),
                    "region": region,
                }
    # fall back to a flat assignment list if the document shape differs
    if not out:
        for a in doc.get("assignments") or []:
            out[a.get("operation_ref") or a.get("operation_id")] = {
                "resource": a.get("resource_ref") or a.get("resource_id"),
                "start": a.get("start"), "end": a.get("end"), "region": "flat"}
    return out


def _bars(doc: dict) -> dict:
    """Every placement keyed by OPERATION IDENTITY (operation_ref), never by
    list position — the whole point of the 4B.6a accounting protocol."""
    out = {}
    for a in doc.get("assignments") or []:
        chunks = a.get("chunks") or []
        out[a["operation_ref"]] = {
            "resource": a.get("resource_id"),
            "external_name": a.get("external_name"),
            "start": chunks[0]["start"] if chunks else None,
            "end": chunks[-1]["end"] if chunks else None,
            "committed": a.get("commitment_state"),
            "work_order": (a.get("work_orders") or [None])[0],
            "n_chunks": len(chunks),
            "overtime_min": a.get("in_overtime_min"),
        }
    return out


def _tray(doc: dict) -> dict:
    rows = ((doc.get("rolling") or {}).get("beyond_horizon") or [])
    if isinstance(rows, dict):
        rows = rows.get("items") or []
    out = {}
    for it in rows:
        key = it.get("work_order") or it.get("demand_ref") or it.get("id")
        out[key] = {k: it.get(k) for k in
                    ("due", "earliest_window_estimate", "customer_name")}
        out[key]["coarse"] = it.get("coarse")
    return out


def snapshot(out_path: Path):
    snap = {"digests": {}, "sets": {}}
    for s in SETS:
        d = FIXTURES / s
        if not d.exists():
            continue
        snap["digests"][s] = {p.name: digest(p) for p in sorted(d.glob("*.json"))}
        sched = json.loads((d / "schedule.json").read_text(encoding="utf-8"))
        entry = {
            "bars": _bars(sched),
            "tray": _tray(sched),
            "cost_summary": sched.get("cost_summary"),
            "solver": sched.get("solver"),
            "service_outcomes": {
                (s.get("work_order") or s.get("demand_ref")): {
                    k: s.get(k) for k in ("lateness_minutes", "on_time", "status")}
                for s in (sched.get("service_outcomes") or [])},
            "contract_version": sched.get("contract_version"),
            "coarse_zone": ((sched.get("rolling") or {}).get("coarse_zone") or {}),
        }
        sb = d / "sandbox.json"
        if sb.exists():
            entry["sandbox"] = json.loads(sb.read_text(encoding="utf-8"))
        meta = d / "meta.json"
        if meta.exists():
            entry["meta"] = json.loads(meta.read_text(encoding="utf-8"))
        snap["sets"][s] = entry
    out_path.write_text(json.dumps(snap, indent=1, sort_keys=True), encoding="utf-8")
    for s, ds in snap["digests"].items():
        print(f"{s}:")
        for name, dg in ds.items():
            print(f"    {name:<20} {dg}")
        e = snap["sets"][s]
        print(f"    bars={len(e['bars'])} tray={len(e['tray'])} "
              f"contract={e['contract_version']}")
        print(f"    cost_summary={json.dumps(e['cost_summary'], sort_keys=True)}")


def _fmt(v):
    return json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else str(v)


def compare(before_p: Path, after_p: Path):
    b = json.loads(before_p.read_text(encoding="utf-8"))
    a = json.loads(after_p.read_text(encoding="utf-8"))
    for s in SETS:
        if s not in b["sets"] or s not in a["sets"]:
            continue
        print("=" * 92)
        print(f"SET: {s}")
        print("=" * 92)
        bd, ad = b["digests"][s], a["digests"][s]
        for name in sorted(set(bd) | set(ad)):
            mark = "same" if bd.get(name) == ad.get(name) else "MOVED"
            print(f"  {name:<20} {bd.get(name,'-')} -> {ad.get(name,'-')}  {mark}")
        eb, ea = b["sets"][s], a["sets"][s]

        bb, ab = eb["bars"], ea["bars"]
        arrived = sorted(set(ab) - set(bb))
        left = sorted(set(bb) - set(ab))
        common = sorted(set(bb) & set(ab))
        print(f"\n  OPS keyed by identity: {len(bb)} before, {len(ab)} after, "
              f"{len(common)} the same, {len(arrived)} arrived, {len(left)} left")
        if arrived:
            print(f"    ARRIVED: {arrived[:20]}")
        if left:
            print(f"    LEFT:    {left[:20]}")
        moved_res = [o for o in common if bb[o]["resource"] != ab[o]["resource"]]
        moved_start = [o for o in common if bb[o]["start"] != ab[o]["start"]]
        moved_state = [o for o in common if bb[o]["committed"] != ab[o]["committed"]]
        print(f"    changed machine: {len(moved_res)}   changed start: {len(moved_start)}"
              f"   changed commitment: {len(moved_state)}")

        bt, at = eb["tray"], ea["tray"]
        print(f"\n  TRAY: {len(bt)} before, {len(at)} after, "
              f"same order set: {set(bt) == set(at)}")
        tmoved = [k for k in set(bt) & set(at) if bt[k] != at[k]]
        if tmoved:
            print(f"    tray items whose fields moved: {len(tmoved)} {tmoved[:10]}")

        print(f"\n  COST SUMMARY")
        cb, ca = eb["cost_summary"] or {}, ea["cost_summary"] or {}
        for k in sorted(set(cb) | set(ca)):
            mark = "" if cb.get(k) == ca.get(k) else "   <-- MOVED"
            print(f"    {k:<26} {_fmt(cb.get(k)):>16} -> {_fmt(ca.get(k)):>16}{mark}")

        print(f"\n  CONTRACT VERSION  {eb['contract_version']} -> {ea['contract_version']}"
              f"   {'same' if eb['contract_version'] == ea['contract_version'] else '*** MOVED ***'}")
        print(f"  SOLVER  {_fmt(eb.get('solver'))} -> {_fmt(ea.get('solver'))}")

        sb_, sa_ = eb.get("service_outcomes") or {}, ea.get("service_outcomes") or {}
        late_b = [k for k, v in sb_.items() if (v.get("lateness_minutes") or 0) > 0]
        late_a = [k for k, v in sa_.items() if (v.get("lateness_minutes") or 0) > 0]
        smoved = [k for k in set(sb_) & set(sa_) if sb_[k] != sa_[k]]
        print(f"\n  SERVICE OUTCOMES: {len(sb_)} -> {len(sa_)}; late {len(late_b)} -> "
              f"{len(late_a)}; outcomes changed: {len(smoved)}")
        if late_b or late_a:
            print(f"    late before: {sorted(late_b)[:12]}")
            print(f"    late after:  {sorted(late_a)[:12]}")

        if "sandbox" in eb and "sandbox" in ea:
            print(f"\n  DELTA CARD (item 6)")
            for k in ("cost_delta_abs", "reopt_delta_abs", "move_delta_abs",
                      "baseline_total_cost", "attribution", "attribution_note",
                      "total_cost", "delta_abs", "delta_pct"):
                if k in eb["sandbox"] or k in ea["sandbox"]:
                    mark = "" if eb["sandbox"].get(k) == ea["sandbox"].get(k) else "   <-- MOVED"
                    print(f"    {k:<22} {_fmt(eb['sandbox'].get(k)):>16} -> "
                          f"{_fmt(ea['sandbox'].get(k)):>16}{mark}")

        cz_b, cz_a = eb.get("coarse_zone") or {}, ea.get("coarse_zone") or {}
        if cz_b or cz_a:
            print(f"\n  COARSE ZONE keys moved: "
                  f"{sorted(k for k in set(cz_b) | set(cz_a) if cz_b.get(k) != cz_a.get(k))}")


if __name__ == "__main__":
    if sys.argv[1] == "snapshot":
        snapshot(Path(sys.argv[2]))
    else:
        compare(Path(sys.argv[2]), Path(sys.argv[3]))

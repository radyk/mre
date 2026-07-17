"""Build the hermetic PLANNER-SURFACE fixture for the cockpit harness
(docs/07 Session 4.2). Unlike the multi_route fixtures (captured from real
solves), this one is HAND-AUTHORED to exercise the read-layer features the demo
scenarios don't produce: planned-maintenance + generic closures, an overtime
(premium) window, a setup segment, a split op paused across a closure, a
standing pin, and per-order customer / quantity for the job card.

It is a contract-1.6 document + its interaction payload + meta + canned asks,
written to tests/cockpit/fixtures/planner/. Static test data — no solver.

Run:  python tools/build_planner_fixture.py
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "cockpit" / "fixtures" / "planner"
SID = "sched-planner-fixture"


def dt(day: int, h: int, m: int = 0) -> str:
    return f"2026-01-{day:02d}T{h:02d}:{m:02d}:00Z"


# --- resources + calendars ------------------------------------------------
R1, R2, R3 = ("res-001", "res-002", "res-003")
NAME = {R1: "F001-RES001", R2: "F001-RES002", R3: "F001-RES003"}


def regular_days(res: str, days: list[int]) -> list[dict]:
    return [{"start": dt(d, 7), "end": dt(d, 19), "kind": "regular", "reason": None} for d in days]


def resource(res: str, windows: list[dict], booked: str, gap: str) -> dict:
    return {
        "resource_id": res, "external_name": NAME[res],
        "facility": "F001", "pool": None,
        "calendar_windows": windows,
        "booked_through": booked, "next_open_gap": gap,
    }


r1_wins = regular_days(R1, [5, 6, 7, 8, 9])
r2_wins = (
    regular_days(R2, [5, 6, 8, 9])
    + [{"start": dt(7, 0), "end": dt(8, 0), "kind": "closure", "reason": "planned_maintenance"}]
)
r3_wins = (
    regular_days(R3, [5, 6, 7, 8, 9])
    + [{"start": dt(6, 19), "end": dt(6, 22), "kind": "overtime", "reason": "overtime"}]
)

resources = [
    resource(R1, r1_wins, dt(8, 12), dt(8, 12)),
    resource(R2, r2_wins, dt(8, 10), dt(8, 10)),
    resource(R3, r3_wins, dt(6, 21), dt(6, 21)),
]


# --- assignments ----------------------------------------------------------
def chunk(seq: int, s: str, e: str, mins: int) -> dict:
    return {"chunk_seq": seq, "start": s, "end": e, "working_min": mins}


def asg(aid, op, res, orders, seq, chunks, setup=None, pin=False, fam=""):
    return {
        "assignment_id": aid, "operation_ref": op, "workpackage_ref": f"wp-{aid}",
        "work_orders": orders, "op_seq": seq, "setup_family": fam,
        "resource_id": res, "external_name": NAME[res],
        "chunks": chunks,
        "phases": {"setup": setup, "teardown": None},
        "in_overtime_min": 120 if aid == "a-104" else 0,
        "decision_ref": f"dec-{aid}", "standing_pin": pin,
    }


assignments = [
    # setup segment: the first 30 min are setup (07:00–07:30).
    asg("a-100", "op-100", R1, ["ORD-100"], 10,
        [chunk(1, dt(5, 7), dt(5, 11), 240)],
        setup={"start": dt(5, 7), "end": dt(5, 7, 30)}, fam="FAM-A"),
    # a standing pin (committed accepted edit).
    asg("a-101", "op-101", R1, ["ORD-101"], 10,
        [chunk(1, dt(5, 11), dt(5, 15), 240)], pin=True),
    # SPLIT op paused across the Jan-7 planned-maintenance closure on RES002.
    asg("a-102", "op-102", R2, ["ORD-102"], 20,
        [chunk(1, dt(6, 15), dt(6, 19), 240), chunk(2, dt(8, 7), dt(8, 10), 180)]),
    asg("a-103", "op-103", R3, ["ORD-103"], 10,
        [chunk(1, dt(6, 7), dt(6, 12), 300)]),
    # runs into the RES003 overtime window (19:00–21:00 Jan 6).
    asg("a-104", "op-104", R3, ["ORD-104"], 10,
        [chunk(1, dt(6, 19), dt(6, 21), 120)]),
    asg("a-105", "op-105", R1, ["ORD-105"], 10,
        [chunk(1, dt(8, 7), dt(8, 12), 300)]),
]


# --- service outcomes (per demand) ---------------------------------------
def svc(demand, wo, cust, qty, uom, due, proj, lateness):
    return {
        "demand_ref": demand, "work_order": wo, "customer_ref": f"cust-{wo}",
        "customer_name": cust, "quantity": qty, "quantity_uom": uom,
        "due": due, "projected_completion": proj, "lateness_min": lateness,
        "tardiness_cost": max(0.0, lateness) * 0.5,
    }


service_outcomes = [
    svc("d-100", "ORD-100", "Acme Aerospace", 500.0, "ea", dt(9, 23, 59), dt(5, 11), -6000),
    svc("d-101", "ORD-101", "Globex Corp", 120.0, "ea", dt(6, 12), dt(5, 15), -1260),   # tight
    svc("d-102", "ORD-102", "Initech", 40.0, "ea", dt(7, 12), dt(8, 10), 1320),          # late
    svc("d-103", "ORD-103", "Umbrella Co", 1000.0, "kg", dt(10, 23, 59), dt(6, 12), -8000),
    svc("d-104", "ORD-104", "Stark Industries", 8.0, "ea", dt(9, 23, 59), dt(6, 21), -4200),
    svc("d-105", "ORD-105", "Wayne Enterprises", 250.0, "ea", dt(7, 12), dt(8, 12), 1440),  # late
]


# --- the schedule document (contract 1.6) --------------------------------
document = {
    "contract_version": "1.6", "schedule_id": SID, "snapshot_id": "snap-planner",
    "run_id": "run-planner", "status": "published",
    "reference_date": dt(6, 12),
    "horizon": {"start": dt(5, 0), "end": "2026-01-09T23:59:59Z"},
    "solver": {"status": "OPTIMAL", "objective": 1234.0, "gap": 0.0,
               "wall_time_s": 2.1, "deterministic": True},
    "cost_summary": {"total": 1234.0, "production_regular": 900.0,
                     "production_overtime": 120.0, "setup": 50.0, "tardiness": 164.0,
                     "costmodel_version": 1},
    "resources": resources, "assignments": assignments,
    "service_outcomes": service_outcomes,
    "annotations": {"locks": [], "scenario": {"is_scenario": False, "parent_schedule_id": None},
                    "pool": None},
    "interaction": None,
}


# --- interaction payload (Tier-0 facts) ----------------------------------
def op_fact(op, elig, working, setup, release, resumable=False):
    return {
        "operation_ref": op, "eligible_resource_ids": elig, "dim_reasons": {},
        "working_min": working, "setup_min": setup,
        "earliest_start": release, "resumable": resumable,
    }


interaction = {
    "schedule_id": SID, "contract_version": "1.6",
    "interaction": {
        "operations": [
            op_fact("op-100", [R1, R3], 240, 30, dt(5, 7)),
            op_fact("op-101", [R1], 240, 0, dt(5, 9)),
            op_fact("op-102", [R2], 420, 0, dt(6, 12), resumable=True),
            op_fact("op-103", [R3], 300, 0, dt(6, 7)),
            op_fact("op-104", [R3], 120, 0, dt(6, 12)),
            op_fact("op-105", [R1, R2], 300, 0, dt(8, 7)),
        ],
        "precedence_edges": [],
    },
}

meta = {
    "id": SID, "schedule_id": SID, "status": "published",
    "contract_version": "1.6", "grade": "ACCEPTED", "costing_grade": "C1",
}

asks = {
    "why is ORD-102 late?": {
        "answer": "ORD-102 finishes late: its op is split across the planned-"
                  "maintenance closure on F001-RES002 (Jan 7), pausing until the "
                  "row reopens Jan 8.\n\nregister: testimony",
        "bundle": {"register": "testimony", "subject_type": "late_orders",
                   "cited_refs": {"operations": ["op-102"], "resources": [R2], "demands": ["d-102"]}},
    },
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "schedule.json").write_text(json.dumps(document, indent=1))
    (OUT / "interaction.json").write_text(json.dumps(interaction, indent=1))
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))
    (OUT / "asks.json").write_text(json.dumps(asks, indent=1))
    print(f"planner fixture -> {OUT}")


if __name__ == "__main__":
    main()

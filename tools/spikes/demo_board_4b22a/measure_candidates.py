"""Errand 4B.22a Item 2 -- MEASURE THE DENSITY CANDIDATES, DO NOT PICK ONE.

A denser demo board may stop proving its cost optimum. 4B.12 put the cliff at
92 ops/machine on the realistic shape and showed that under R-PD1 -- which
admits past-due work, so tardiness is nonzero at the lightest density -- the
last all-OPTIMAL density fell to 50. This errand's board deliberately introduces
BOTH lateness and past-due work, which is the mechanism 4B.12 proved breaks the
proof. So the trade is real and it is measured here rather than assumed.

Each candidate is taken through the SAME path the demo board will be minted
through: generate -> prepare_plant -> build_rolling_view (window 0, deterministic)
-> build_coarse_zone -> assemble_rolling_document. Nothing is estimated from the
submission; every figure below is read off the solved window or the assembled
contract-1.11/1.12 document, which is what the cockpit renders.

    python tools/spikes/demo_board_4b22a/measure_candidates.py \
        --out _4b22a_scratch/candidates --json _4b22a_scratch/candidates.json

WALL CEILINGS ARE GENEROUS BY CONSTRUCTION (900 s against a 4.0-unit
deterministic budget). Under `deterministic: true` the DETERMINISTIC budget is
what must bind; a candidate stopped by the wall clock is a lottery wearing a
determinism label, so `wall_truncated` is reported for every candidate and the
errand excludes any candidate where it fired. A board that cannot be reproduced
is not a demo board.

THE DENOMINATOR IS NAMED, AND IT IS NOT THE ACTIVE WINDOW (4B.20's ruling: a
capacity figure names its denominator). Utilisation here is WORKING MINUTES (the
sum of the run windows, never the elapsed span) over the machine's OPEN CALENDAR
MINUTES ACROSS THE BOARD EXTENT -- `window_start` to the LAST placement end on
the whole board, the same interval for every machine so machines are comparable.

It is emphatically NOT `window_start` to `window_end`: `build_rolling_view`
classifies a placement as `active` on its START (`start >= frozen_end`), and the
window solve's horizon runs past the window end, so admitted work is legitimately
placed beyond it. Measured against a 14-day-window denominator, CUT-01 read
174.2% at the lightest candidate -- an impossible number produced by a
denominator shorter than the thing it was dividing. It is also not
`evidence_tools.machine_load`'s denominator (that machine's own first-to-last
interval), which answers a different question -- "how hard is this machine
working while it is working" -- and is not comparable across machines. The three
figures are not interchangeable and none is compared with another below.
"""
from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "src"))

REF = datetime(2026, 1, 5, tzinfo=timezone.utc)
SEED = 42                  # the standing seed for rolling / pilot_scale work
GEN_SEED = 1               # the generator seed the pilot family has always used
# THE BUDGETS ARE THE API'S, NOT THIS TOOL'S CHOICE. The demo board is minted
# THROUGH the dev API (errand Item 3), and `det_total` is NOT a SolveRequest
# field: `app.py` calls `build_rolling_view` without it, so the registered board
# gets `rolling_horizon._DET_TOTAL_DEFAULT` = 6.0 whatever a caller wants. The
# coarse zone is the same story — `app.py` passes neither `det_time` nor
# `safety_ceiling_s`, so the registered zone runs on `build_coarse_zone`'s own
# defaults (4.0 units, a 60 s ceiling). Measuring at any other budget would
# measure a board nobody will ever see. Raising either is a src/mre change and
# this errand makes none.
DET_TOTAL = 6.0            # rolling_horizon._DET_TOTAL_DEFAULT
COARSE_DET_TIME = 4.0      # build_coarse_zone's default
WALL_CEILING_S = 900.0     # a CEILING, never the budget (SolveRequest.time_limit)
COARSE_CEILING_S = 60.0    # build_coarse_zone's default

# THE CANDIDATES.
#
# `frozen_days` and `window_days` are SOLVE parameters, not world properties
# (errand Item 1(h)). The pinned exam world runs frozen=3, which commits 45 of
# its 56 bars and leaves a planner almost nothing to drag; 1 is the obvious
# candidate and every demo candidate carries it, so the density comparison is
# not confounded by the frozen split.
#
# `window_days` is on the table because of docs/07 §5a.15, still open: the
# shipped 14-day window is BUDGET-STARVED at 200 orders on this plant (UNKNOWN
# at a deterministic budget of 6.0 AND of 20.0), while a 7-day window on the
# same plant proves OPTIMAL in under 5. If that holds, the 7-day arm buys the
# proof AND a denser board AND a fuller tray at the same order count -- so it is
# measured rather than argued about.
#
# c0 is the CURRENT demo board, taken through the identical measurement path, so
# every row below has something to be compared against. It is `pilot_scale`, not
# `demo_board`: no past-due share, pilot_scale's own wide due-date spread,
# frozen=3.
#
# EVERY ROW CARRIES ITS OWN `splittable_weight`, INCLUDING THE ROWS MEASURED
# BEFORE THE KNOB EXISTED. The `demo_board` preset now DECLARES a weight, so a
# candidate that omitted the field would silently inherit whatever the preset
# says today and stop reproducing the number printed against its name. 1 is
# pilot_scale's own weight and produces a byte-identical weight list, so the
# eleven rows below are exactly what was measured.
CANDIDATES = [
    dict(name="c0-current", scenario="pilot_scale", orders=40, splittable_weight=1,
         pd_share=0.0, lead_p50=None, frozen_days=3, window_days=14),

    # --- the 14-day arm, the shipped window ---------------------------------
    dict(name="c1-w14-90",  orders=90,  pd_share=0.12, lead_p50=10,
         splittable_weight=1, frozen_days=1, window_days=14),
    dict(name="c2-w14-140", orders=140, pd_share=0.12, lead_p50=10,
         splittable_weight=1, frozen_days=1, window_days=14),
    dict(name="c3-w14-170", orders=170, pd_share=0.12, lead_p50=10,
         splittable_weight=1, frozen_days=1, window_days=14),
    dict(name="c4-w14-360", orders=360, pd_share=0.12, lead_p50=10,
         splittable_weight=1, frozen_days=1, window_days=14),

    # --- the 7-day arm (§5a.15's lever) -------------------------------------
    dict(name="c5-w7-140",  orders=140, pd_share=0.12, lead_p50=10,
         splittable_weight=1, frozen_days=1, window_days=7),
    dict(name="c6-w7-200",  orders=200, pd_share=0.12, lead_p50=10,
         splittable_weight=1, frozen_days=1, window_days=7),
    dict(name="c7-w7-280",  orders=280, pd_share=0.12, lead_p50=10,
         splittable_weight=1, frozen_days=1, window_days=7),

    # --- a 10-day middle arm, added AFTER the first eight were measured -----
    # The 7-day arm placed the most work but chunked NOTHING: a long splittable
    # operation is the most expensive admission a tight window can make, so
    # P-SPACER lands in the tray and 4B.20's per-chunk rendering has no
    # specimen. The 14-day arm chunks (four at 90 orders) and then goes UNKNOWN
    # at 140. If a middle window buys both, it is here.
    dict(name="c8-w10-200", orders=200, pd_share=0.12, lead_p50=10,
         splittable_weight=1, frozen_days=1, window_days=10),
    dict(name="c9-w10-280", orders=280, pd_share=0.12, lead_p50=10,
         splittable_weight=1, frozen_days=1, window_days=10),
    dict(name="c10-w7-360", orders=360, pd_share=0.12, lead_p50=10,
         splittable_weight=1, frozen_days=1, window_days=7),

    # --- THE CONTROLLED PAIR, added last ------------------------------------
    # Every populated demo candidate came back FEASIBLE with a 76-92% gap while
    # c0, the current board, proves OPTIMAL. Two things changed at once between
    # them -- the density AND the past-due work -- so neither can be blamed from
    # the rows above. 4B.12 says it is the past-due work: R-PD1 admits it, the
    # tardiness floor is nonzero wherever late work exists, and the proof cost
    # rises 200-360x on the same world with its late work restored.
    #
    # c11 is c7 with pd_share = 0.0 and NOTHING else changed. If it proves, the
    # floor is the mechanism and the demo board's gap is the price of showing
    # R-PD1 at all -- a trade Daryn can price. If it does not, density alone is
    # enough and the past-due share is free.
    dict(name="c11-w7-280-nopd", orders=280, pd_share=0.0, lead_p50=10,
         splittable_weight=1, frozen_days=1, window_days=7),

    # --- THE SPLITTABLE ARM, added last -------------------------------------
    # Every candidate above chunked 0 or 1 operation -- FEWER than the 40-order
    # board it is meant to replace, which chunks 2. R-C3 chunking needs a
    # splittable operation too long for one open window, and this plant has
    # exactly one such product at ~4.5% of the book. c12 is c9 -- the densest
    # solvable candidate -- with P-SPACER's weight raised from 1 to 4 (~15% of
    # the book) and NOTHING else changed. c13 is the same at the 7-day window.
    dict(name="c12-w10-280-split", orders=280, pd_share=0.12, lead_p50=10,
         splittable_weight=4, frozen_days=1, window_days=10),
    dict(name="c13-w7-280-split", orders=280, pd_share=0.12, lead_p50=10,
         splittable_weight=4, frozen_days=1, window_days=7),
]


# ---------------------------------------------------------------------------
# the calendar, as open minutes per machine per interval
# ---------------------------------------------------------------------------

def _open_minutes(plant, resource_id: str, lo: datetime, hi: datetime) -> int:
    """Open calendar minutes for one machine between lo and hi.

    Read from the plant's RAW calendar rows (patterns + exceptions), so the
    plant-wide maintenance closure and the added Saturday overtime window both
    land in the denominator exactly as the solver saw them. A denominator we
    computed a different way from the solver's would make every percentage below
    an unverifiable number -- the class of claim this codebase refuses to make.
    """
    res = next((r for r in plant.resources if r["id"] == resource_id), None)
    if res is None:
        return 0
    cal = next((c for c in plant.calendars
                if c["id"] == res.get("calendar_ref")), None)
    if cal is None:
        return 0
    pat = cal.get("base_pattern") or {}
    weekdays = set(pat.get("weekdays") or [])
    a, b = pat.get("shift_start"), pat.get("shift_end")

    def _span(x: str, y: str) -> int:
        xh, xm = (int(v) for v in x.split(":")[:2])
        yh, ym = (int(v) for v in y.split(":")[:2])
        return (yh * 60 + ym) - (xh * 60 + xm)

    base = _span(a, b) if (a and b) else 0
    closures: set[str] = set()
    added: dict[str, int] = {}
    for ex in cal.get("exceptions") or []:
        w = ex.get("window") or {}
        day = str(w.get("start") or "")[:10]
        kind = (ex.get("type") or "").lower()
        if kind == "closure":
            closures.add(day)
        elif kind == "added":
            s, e = str(w.get("start") or ""), str(w.get("end") or "")
            if "T" in s and "T" in e:
                added[day] = added.get(day, 0) + _span(s[11:16], e[11:16])

    total = 0
    day = lo.date()
    while day < hi.date():
        key = day.isoformat()
        if key not in closures and day.weekday() in weekdays:
            total += base
        total += added.get(key, 0)
        day = day + timedelta(days=1)
    return total


# ---------------------------------------------------------------------------
# working minutes of one placement (4B.20: name the quantity)
# ---------------------------------------------------------------------------

def _working_minutes(placement: dict) -> float:
    """WORKING minutes, never the elapsed span.

    A chunked (R-C3 resumable) placement carries its run windows; the sum of
    those windows IS its working time and (end - start) is a SPAN that includes
    every calendar pause. For a non-chunked pilot-family operation the two agree
    by construction -- the generator caps a non-splittable op at 680 minutes so
    it fits inside one 720-minute shift -- but the two quantities are still
    computed from different fields and never conflated.
    """
    chunks = placement.get("chunks") or []
    if chunks:
        return sum((datetime.fromisoformat(c["end"])
                    - datetime.fromisoformat(c["start"])).total_seconds() / 60.0
                   for c in chunks)
    return ((datetime.fromisoformat(placement["end"])
             - datetime.fromisoformat(placement["start"])).total_seconds() / 60.0)


# ---------------------------------------------------------------------------

def measure(cand: dict, out_root: Path) -> dict:
    from generate_erp_dataset import generate
    from mre.modules import rolling_horizon as rh
    from mre.modules.coarse_horizon import build_coarse_zone
    from mre.modules.schedule_assembler import assemble_rolling_document

    name = cand["name"]
    work = out_root / name
    if work.exists():
        shutil.rmtree(work)
    sub = work / "submission"
    scenario = cand.get("scenario", "demo_board")
    window_days = cand["window_days"]
    print(f"\n=== {name}: {scenario} {cand['orders']} orders, "
          f"pd={cand['pd_share']}, lead_p50={cand['lead_p50']}, "
          f"split_w={cand.get('splittable_weight')}, "
          f"window={window_days}d frozen={cand['frozen_days']}d ===")
    marker = generate(sub, scenario=scenario, orders=cand["orders"],
                      seed=GEN_SEED, pd_share=cand["pd_share"],
                      lead_p50=cand["lead_p50"],
                      splittable_weight=cand.get("splittable_weight"))
    ps = marker.get("pilot_scale", {})

    # CAPTURE THE DETERMINISTIC SPEND. RollingView does not carry det_consumed
    # and adding a field would be a src/mre change this errand forbids, so the
    # TOOL observes it: a shim around the module's own two-stage solve that
    # records the SolveResult and delegates untouched. Nothing about the solve
    # changes -- the shim adds no arguments and alters no result.
    seen: list = []
    original = rh._two_stage_solve

    def _shim(*a, **k):
        r = original(*a, **k)
        seen.append(r[0])
        return r

    rh._two_stage_solve = _shim
    try:
        t0 = time.perf_counter()
        plant = rh.prepare_plant(sub, work / "run", reference_date=REF)
        view = rh.build_rolling_view(
            plant, window_days=window_days, frozen_days=cand["frozen_days"],
            gravity=True, deterministic=True, seed=SEED,
            member_time_limit_s=WALL_CEILING_S, det_total=DET_TOTAL,
            persist=True)
        solve_wall = time.perf_counter() - t0
    finally:
        rh._two_stage_solve = original
    det_consumed = seen[-1].det_consumed if seen else None

    t1 = time.perf_counter()
    zone = build_coarse_zone(plant, view, deterministic=True, seed=SEED,
                             det_time=COARSE_DET_TIME,
                             safety_ceiling_s=COARSE_CEILING_S)
    coarse_wall = time.perf_counter() - t1

    idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
    doc = assemble_rolling_document(plant=plant, view=view,
                                    schedule_id=f"sched-{name}",
                                    run_id=f"run-{name}",
                                    identity_map=idmap,
                                    coarse_zone=zone).model_dump(mode="json")

    # ---- density -----------------------------------------------------------
    placed = view.placed
    by_machine: dict[str, list] = {}
    for oid, p in placed.items():
        by_machine.setdefault(p["resource"], []).append(p)
    def _ext(ent, kind: str) -> str:
        for ref in ent.get("external_refs") or []:
            if ref.get("type") == kind:
                return ref.get("value")
        return ent["id"]

    machines = sorted(r["id"] for r in plant.resources)
    name_of = {r["id"]: _ext(r, "resource_id") for r in plant.resources}

    # THE BOARD EXTENT — window_start to the last placement end anywhere on the
    # board. The same interval for every machine, so the percentages below are
    # comparable to each other. See the module docstring for why this is not the
    # active window.
    ends = [datetime.fromisoformat(p["end"]) for p in placed.values()]
    board_end = max(ends) if ends else view.window_end
    board_start = view.window_start

    util = {}
    counts = []
    for mid in machines:
        rows = by_machine.get(mid, [])
        work_min = sum(_working_minutes(p) for p in rows)
        openm = _open_minutes(plant, mid, board_start,
                              board_end + timedelta(days=1))
        counts.append(len(rows))
        util[name_of[mid]] = {
            "ops": len(rows),
            "working_min": round(work_min, 1),
            "open_min_board_extent": openm,
            "utilization_pct": (round(100.0 * work_min / openm, 1)
                                if openm else None),
        }
    ops_per_machine = sorted(counts, reverse=True)
    util_vals = [v["utilization_pct"] for v in util.values()
                 if v["utilization_pct"] is not None]

    # ---- lateness / past due ----------------------------------------------
    def _dt(v):
        if not v:
            return None
        if isinstance(v, datetime):
            return v
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))

    past_due_ids = {d["id"] for d in plant.demands
                    if (_dt(d.get("due")) or REF) < REF}

    outcomes = doc.get("service_outcomes", [])
    late = [o for o in outcomes if (o.get("lateness_min") or 0) > 0]
    cs = doc.get("cost_summary", {}) or {}

    # which demands actually got bars this window
    op_by_id = {o["id"]: o for o in plant.operations}
    placed_wps = {op_by_id[oid]["workpackage_ref"] for oid in placed
                  if oid in op_by_id}
    placed_demands = {did for did, wp in (plant.wp_of_demand or {}).items()
                      if wp in placed_wps}
    past_due_scheduled = len(past_due_ids & placed_demands)
    past_due_in_tray = len(past_due_ids & set(view.beyond_demand_ids))

    chunked = [oid for oid, p in placed.items() if len(p.get("chunks") or []) > 1]
    # WHY A CHUNK COUNT CAN BE ZERO ON A BUSY BOARD. R-C3 chunking only happens
    # to a SPLITTABLE operation that cannot fit one open window, and on this
    # plant that is one product (P-SPACER, 600-1500 working minutes). A long
    # splittable op is the most expensive thing the window solve can admit, so a
    # tight window pushes it to the TRAY -- where it draws no bar and chunks
    # nothing. Counting only the placed ones would report the symptom and hide
    # the mechanism, so both sides are counted.
    splittable_ops = [o["id"] for o in plant.operations if o.get("splittable")]
    split_placed = [oid for oid in splittable_ops if oid in placed]
    cz = (doc.get("rolling") or {}).get("coarse_zone") or {}

    row = {
        "name": name,
        "scenario": scenario,
        **{k: cand[k] for k in ("orders", "pd_share", "lead_p50",
                                "splittable_weight", "frozen_days",
                                "window_days")},
        "past_due_generated": ps.get("past_due_orders_generated"),
        "past_due_demands": len(past_due_ids),
        "past_due_scheduled": past_due_scheduled,
        "past_due_in_tray": past_due_in_tray,
        "machines": len(machines),
        "board_start": board_start.isoformat(),
        "board_end": board_end.isoformat(),
        "board_extent_days": round((board_end - board_start).days
                                   + (board_end - board_start).seconds / 86400.0, 1),
        "window_end": view.window_end.isoformat(),
        "placed_ops": len(placed),
        "committed_ops": len(view.committed),
        "active_ops": len(view.active),
        "ops_per_machine_max": max(counts) if counts else 0,
        "ops_per_machine_median": statistics.median(counts) if counts else 0,
        "util_max_pct": max(util_vals) if util_vals else None,
        "util_median_pct": statistics.median(util_vals) if util_vals else None,
        "machines_over_85pct": sum(1 for v in util_vals if v >= 85.0),
        "machines_under_15pct": sum(1 for v in util_vals if v < 15.0),
        "late_orders": len(late),
        "tardiness_cost": cs.get("tardiness"),
        "tardiness_floor": cs.get("tardiness_floor"),
        "tardiness_controllable": cs.get("tardiness_controllable"),
        "cost_total": cs.get("total"),
        "chunked_ops": len(chunked),
        "splittable_ops_total": len(splittable_ops),
        "splittable_ops_placed": len(split_placed),
        "tray_count": len(view.beyond_demand_ids),
        "coarse_cells": len(cz.get("density") or []),
        "coarse_binding_cells": len(cz.get("binding_cells") or []),
        "coarse_rho": cz.get("capacity_derate"),
        "coarse_rho_provenance": cz.get("capacity_derate_provenance"),
        "status": view.status,
        "gap": view.gap,
        "tiebreak_status": view.tiebreak_status,
        "det_budget": DET_TOTAL,
        "det_consumed": det_consumed,
        "solve_wall_s": round(solve_wall, 1),
        "coarse_wall_s": round(coarse_wall, 1),
        "wall_truncated": bool(view.wall_truncated),
        "coarse_wall_truncated": bool(zone.proof.wall_truncated
                                      or zone.planning.wall_truncated),
        "per_machine": util,
    }
    print(f"  status={row['status']} gap={row['gap']} "
          f"det={row['det_consumed']}/{DET_TOTAL} wall={row['solve_wall_s']}s "
          f"truncated={row['wall_truncated']}")
    print(f"  placed={row['placed_ops']} ({row['committed_ops']}c/{row['active_ops']}a) "
          f"ops/machine max={row['ops_per_machine_max']} "
          f"med={row['ops_per_machine_median']}")
    print(f"  util max={row['util_max_pct']}% med={row['util_median_pct']}% "
          f">=85%: {row['machines_over_85pct']} <15%: {row['machines_under_15pct']}")
    print(f"  late={row['late_orders']} tardiness={row['tardiness_cost']} "
          f"(floor {row['tardiness_floor']} / ctrl {row['tardiness_controllable']}) "
          f"past-due scheduled={row['past_due_scheduled']}/{row['past_due_demands']}")
    print(f"  chunked={row['chunked_ops']} "
          f"(splittable ops {row['splittable_ops_placed']} placed of "
          f"{row['splittable_ops_total']}) tray={row['tray_count']} "
          f"coarse binding={row['coarse_binding_cells']}/{row['coarse_cells']} "
          f"rho={row['coarse_rho']} ({row['coarse_rho_provenance']})")
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="_4b22a_scratch/candidates")
    ap.add_argument("--json", default="_4b22a_scratch/candidates.json")
    ap.add_argument("--only", default=None, help="comma-separated candidate names")
    args = ap.parse_args(argv)

    out_root = REPO / args.out
    out_root.mkdir(parents=True, exist_ok=True)
    wanted = set(args.only.split(",")) if args.only else None

    rows = []
    for cand in CANDIDATES:
        if wanted and cand["name"] not in wanted:
            continue
        try:
            rows.append(measure(cand, out_root))
        except Exception as e:                       # noqa: BLE001
            print(f"  !! {cand['name']} FAILED: {type(e).__name__}: {e}",
                  file=sys.stderr)
            rows.append({"name": cand["name"], "error": f"{type(e).__name__}: {e}",
                         **{k: cand[k] for k in
                            ("orders", "pd_share", "lead_p50",
                             "splittable_weight", "frozen_days",
                             "window_days")}})

    dest = REPO / args.json
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

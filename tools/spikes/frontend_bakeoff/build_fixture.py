"""Frontend bake-off SPIKE — shared fixture builder (Session 3.0).

Builds the ONE fixture both candidates consume:

  1. ``fixture/schedule.json`` — a REAL contract-1.1 ScheduleDocument from a
     deterministic ``messy_realistic`` solve (16 resources, 475 assignments,
     built by ``build_document_from_run``). Unmodified; this is the board.

  2. ``fixture/anchors.json`` — the STATIC precomputed anchors for one chosen
     "grab" task. Per the spike brief, anchor COMPUTATION is interim-A work;
     the spike tests RENDERING + INTERACTION only, so static anchors are the
     honest scope. Every anchor group carries a ``basis`` tag saying whether
     it is derived from real schedule data or authored as a spike stand-in.

PROVENANCE / the honest caveat (see also VERDICT.md and the fixture README):
  ``messy_realistic`` — like every generator scenario — routes each operation
  to EXACTLY ONE resource (single ``resource_id`` per routing line; verified:
  eligibility-size distribution is {1: 475}). So on real generated data a
  moved task has no legal alternative MACHINE, only alternative TIMES on its
  own row, and the solution pool on this slack schedule yields flat,
  zero-cost, non-successor movers (verified: 9 movers at delta 0.0, none in a
  precedence chain). That defeats the point of a drag fixture, whose whole
  reason to exist is testing cross-row shading + priced ghosts ("+$120 on the
  other press", docs/07 Phase 3 Tier-1).

  Resolution: the BOARD stays real (schedule.json is untouched). The grab
  task's GEOMETRY anchors (its bar, its real predecessor's finish, its row's
  real neighbours, the real calendar openings) are derived from real data.
  The cross-row LEGALITY + ghost placements are authored as a documented
  ``spike_capability_overlay`` — they represent what a capability-routed plant
  (same-facility workcentres forming an eligibility pool) WOULD yield, priced
  with the REAL cost model's per-resource rates. They are labelled as such and
  never claimed to be computed from the single-resource routing. This is the
  "precomputed static anchors" the brief calls for, made transparent.

Deterministic: run under ``PYTHONHASHSEED=0``. Selection is by sorted refs.

Usage (from tools/spikes/frontend_bakeoff/):
    PYTHONHASHSEED=0 python build_fixture.py
(Assumes fixture/messy_run already exists — produced by, from repo root:
    PYTHONHASHSEED=0 python tools/generate_erp_dataset.py --seed 7 \
        --scenario messy_realistic --out .../fixture/messy_submission
    PYTHONHASHSEED=0 python -m mre --submission .../fixture/messy_submission \
        --out .../fixture/messy_run --snapshot-id snap-messy \
        --solver-workers 1 --solver-seed 42 --time-limit 40 )
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mre.modules.schedule_assembler import build_document_from_run
from mre.modules.snapshot_store import SnapshotStore

UTC = timezone.utc
HERE = Path(__file__).parent
FIX = HERE / "fixture"
RUN = FIX / "messy_run"
SNAP = "snap-messy"


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _iso(d: datetime) -> str:
    return d.astimezone(UTC).isoformat().replace("+00:00", "Z")


def main() -> None:
    # --- 1. the real board -------------------------------------------------
    doc = build_document_from_run(str(RUN), SNAP, run_id="fixture")
    (FIX / "schedule.json").write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    sch = json.loads((FIX / "schedule.json").read_text(encoding="utf-8"))
    asg = {a["operation_ref"]: a for a in sch["assignments"]}

    reader = SnapshotStore(str(RUN / "snapshots")).load_snapshot(SNAP)
    ops = list(reader.iter_entities("operation"))
    resources = {r["id"]: r for r in reader.iter_entities("resource")}
    costmodels = list(reader.iter_entities("costmodel"))
    rates = (costmodels[0].get("resource_rates") or {}) if costmodels else {}

    def rname(rid: str) -> str:
        for e in resources.get(rid, {}).get("external_refs", []):
            if e.get("type") == "resource_id":
                return e["value"]
        return rid[:8]

    def facility(rid: str) -> str:
        return rname(rid).split("-")[0]

    # --- 2. deterministic grab-task selection ------------------------------
    # Real operation-instance precedence = same WorkPackage, ordered by
    # ``sequence`` (edges are spec-level). Pick, among WPs with >=3 scheduled
    # ops, the one with the TIGHTEST predecessor->grab gap (a compelling
    # "snap to predecessor finish"), tie-broken by same-facility neighbour
    # count, then by workpackage ref for full determinism.
    bywp: dict[str, list] = defaultdict(list)
    for o in ops:
        bywp[o["workpackage_ref"]].append(o)

    def start(a):
        return _dt(a["chunks"][0]["start"])

    def end(a):
        return _dt(a["chunks"][-1]["end"])

    candidates = []
    for wp, members in sorted(bywp.items()):
        chain = sorted(members, key=lambda o: o["sequence"])
        if len(chain) < 3 or not all(o["id"] in asg for o in chain):
            continue
        grab_op, pred_op = chain[-1], chain[-2]
        ga, pa = asg[grab_op["id"]], asg[pred_op["id"]]
        gap = (start(ga) - end(pa)).total_seconds()
        if gap < 0:
            continue  # keep the invariant: grab starts after its predecessor
        fac = facility(ga["resource_id"])
        neighbours = sum(
            1 for a in sch["assignments"]
            if facility(a["resource_id"]) == fac
        )
        candidates.append((gap, -neighbours, wp, chain))
    candidates.sort(key=lambda c: (c[0], c[1], c[2]))
    _, _, wp, chain = candidates[0]

    grab_op, pred_op = chain[-1], chain[-2]
    ga, pa = asg[grab_op["id"]], asg[pred_op["id"]]
    grab_res = ga["resource_id"]
    grab_fac = facility(grab_res)
    grab_min = ga["chunks"][0]["working_min"]
    pred_finish = end(pa)
    grab_start = start(ga)

    # --- 3. visible window (contains pred finish, grab, and >=1 weekend) ----
    vis_start = (pred_finish - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    vis_end = (grab_start + timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)

    def in_window(d: datetime) -> bool:
        return vis_start <= d <= vis_end

    # --- 4. real geometry anchors ------------------------------------------
    # calendar-opening snap points: the start of each real regular window on
    # the grab's own resource lane, inside the visible window.
    def lane(rid: str):
        return next((L for L in sch["resources"] if L["resource_id"] == rid), None)

    def openings(rid: str) -> list[str]:
        L = lane(rid)
        if not L:
            return []
        return [
            _iso(_dt(w["start"])) for w in L["calendar_windows"]
            if w["kind"] in ("regular", "overtime") and in_window(_dt(w["start"]))
        ]

    # adjacency edges: real neighbouring-bar start/end on the grab's own row.
    def neighbours_on(rid: str) -> list[dict]:
        out = []
        for a in sch["assignments"]:
            if a["resource_id"] != rid or a["operation_ref"] == grab_op["id"]:
                continue
            s, e = start(a), end(a)
            if in_window(s) or in_window(e):
                out.append({
                    "start": _iso(s), "end": _iso(e),
                    "work_orders": a.get("work_orders", []),
                })
        return sorted(out, key=lambda x: x["start"])

    # --- 5. authored capability overlay (spike stand-in), REAL pricing ------
    # candidate rows = same-facility workcentres (an eligibility pool a
    # capability-routed plant would expose). Legality: green if the row has no
    # bar overlapping [pred_finish, pred_finish+grab_min] region, else amber
    # (fits but displaces). The grab's own row is green (real eligible).
    same_fac = sorted(
        [rid for rid in resources if facility(rid) == grab_fac],
        key=rname,
    )

    def busy_near(rid: str, at: datetime, dur_min: int) -> bool:
        w0, w1 = at, at + timedelta(minutes=dur_min)
        for a in sch["assignments"]:
            if a["resource_id"] != rid:
                continue
            if start(a) < w1 and end(a) > w0:
                return True
        return False

    rows = []
    for L in sch["resources"]:
        rid = L["resource_id"]
        if rid == grab_res:
            legality, reason, basis = "green", "eligible resource (real routing)", "real_routing"
        elif rid in same_fac:
            displaces = busy_near(rid, pred_finish, grab_min)
            legality = "amber" if displaces else "green"
            reason = ("same-facility workcentre; placing here displaces an existing bar"
                      if displaces else "same-facility workcentre; open slot")
            basis = "spike_capability_overlay"
        else:
            legality, reason, basis = "dim", "illegal: different facility / not in eligibility pool", "real_routing"
        rows.append({
            "resource_id": rid, "external_name": rname(rid),
            "facility": facility(rid), "legality": legality,
            "reason": reason, "basis": basis,
        })

    # ghosts: 3 authored placements on the 3 nearest same-facility candidate
    # rows (excluding the grab's own row), each at the first calendar opening
    # at/after pred_finish, priced by the REAL cost model marginal delta:
    #   delta = (rate[target] - rate[current]) * grab_min
    # (tardiness delta 0 here: ORD demand stays comfortably early either way).
    cur_rate = float(rates.get(grab_res, 1.0))
    ghost_rows = [rid for rid in same_fac if rid != grab_res][:3]
    ghosts = []
    for i, rid in enumerate(ghost_rows):
        ops_open = openings(rid)
        gstart = next((o for o in ops_open if _dt(o) >= pred_finish), None)
        if gstart is None:
            gstart = _iso(pred_finish)
        gs = _dt(gstart)
        ge = gs + timedelta(minutes=grab_min)
        delta = round((float(rates.get(rid, cur_rate)) - cur_rate) * grab_min, 2)
        ghosts.append({
            "ghost_index": i,
            "resource_id": rid,
            "external_name": rname(rid),
            "start": _iso(gs),
            "end": _iso(ge),
            "cost_delta": delta,
            "cost_label": f"{'+' if delta >= 0 else '-'}${abs(delta):,.0f}",
            "basis": "spike_capability_overlay",
            "pricing": "real cost-model marginal (rate[target]-rate[current])*working_min; tardiness delta 0",
        })

    anchors = {
        "_meta": {
            "spike": "frontend_bakeoff (Session 3.0)",
            "purpose": "static precomputed anchors for ONE grab task; tests RENDERING + INTERACTION only",
            "board_scenario": "messy_realistic seed=7, deterministic solve seed=42 workers=1",
            "honest_caveat": (
                "Generated data routes every op to exactly one resource "
                "(eligibility {1:475}); the pool on this slack schedule yields "
                "flat zero-cost non-successor movers. Board geometry is real; "
                "cross-row legality + ghosts are an authored spike_capability_"
                "overlay (same-facility pool), REAL-priced. Anchor computation "
                "is interim-A work, out of spike scope."
            ),
            "contract": "consumed by both bake-off candidates unchanged",
        },
        "visible_window": {"start": _iso(vis_start), "end": _iso(vis_end)},
        "grab": {
            "assignment_id": ga["assignment_id"],
            "operation_ref": grab_op["id"],
            "workpackage_ref": wp,
            "work_orders": ga.get("work_orders", []),
            "resource_id": grab_res,
            "external_name": rname(grab_res),
            "start": _iso(grab_start),
            "end": _iso(end(ga)),
            "working_min": grab_min,
            "basis": "real_schedule",
        },
        "predecessor_finish": {
            "operation_ref": pred_op["id"],
            "resource_id": pa["resource_id"],
            "external_name": rname(pa["resource_id"]),
            "finish": _iso(pred_finish),
            "note": "earliest legal start for the grab task (same-WP precedence)",
            "basis": "real_schedule",
        },
        "rows": rows,
        "calendar_openings": {
            "basis": "real_schedule",
            "own_row": openings(grab_res),
            "by_ghost_row": {rname(rid): openings(rid) for rid in ghost_rows},
        },
        "adjacency_edges": {
            "basis": "real_schedule",
            "own_row": neighbours_on(grab_res),
            "by_ghost_row": {rname(rid): neighbours_on(rid) for rid in ghost_rows},
        },
        "ghosts": ghosts,
        "grid_fallback_minutes": 30,
    }
    (FIX / "anchors.json").write_text(json.dumps(anchors, indent=2), encoding="utf-8")

    # --- report ------------------------------------------------------------
    print(f"schedule.json : {len(sch['assignments'])} assignments, {len(sch['resources'])} resources")
    print(f"grab task     : {ga.get('work_orders')} op {grab_op['id'][:12]} on {rname(grab_res)}")
    print(f"  window      : {_iso(vis_start)} .. {_iso(vis_end)}")
    print(f"  pred_finish : {_iso(pred_finish)}  grab_start: {_iso(grab_start)}  ({grab_min} min)")
    print(f"  rows        : green={sum(r['legality']=='green' for r in rows)} "
          f"amber={sum(r['legality']=='amber' for r in rows)} "
          f"dim={sum(r['legality']=='dim' for r in rows)}")
    print(f"  ghosts      : {[g['cost_label'] for g in ghosts]}")
    print("anchors.json  : written")


if __name__ == "__main__":
    main()

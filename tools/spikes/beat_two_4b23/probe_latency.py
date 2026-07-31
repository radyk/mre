"""Session 4B.23 Item 5(a) -- WHERE DOES BEAT ONE'S ~4.6 SECONDS GO?

R-T2 designed beat one as the instant beat: no money by construction, a small
budget, "grab -> ghost stays snappy". On the dense demo board the founder's
network tab measured 4.61s for it, and the solve inside it is budgeted at 2.0s
-- so most of the wait is NOT the solve.

This times `feasibility_ghost`'s own stages against the real run dir, with no
API in the way, so the answer is attributable rather than inferred. It reports,
it does not fix.

    python tools/spikes/beat_two_4b23/probe_latency.py
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

DENSE_RUN = "c9973708-865e-4753-8c89-12bf35e024d4"
PINNED_RUN = "c362baa4-1b03-4f6c-b3a4-d092c341dbdf"


def _api(base, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        base.rstrip("/") + path, data=data,
        method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json"} if data is not None else {})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))


class Stage:
    def __init__(self):
        self.rows = []
        self._t = time.perf_counter()

    def mark(self, name):
        now = time.perf_counter()
        self.rows.append((name, now - self._t))
        self._t = now

    def report(self, total_label="TOTAL"):
        tot = sum(d for _, d in self.rows)
        for name, d in self.rows:
            print(f"    {name:<34} {d:7.3f}s  {100*d/tot:5.1f}%")
        print(f"    {total_label:<34} {tot:7.3f}s")
        return tot


def stages(run_dir: Path, snapshot_id: str, pin: dict, budget_s: float = 2.0):
    """Re-walk feasibility_ghost's own steps, timed. Mirrors the shipped order in
    src/mre/modules/sandbox.py; if that order changes this probe must too, which
    is why it lives in tools/spikes and not in the guard."""
    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.scenario import derive_base_context
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import SolverBuilder, apply_solution_hints
    from mre.modules.solution_pool import _m5_horizon, _placements, _read_evidence
    from mre.modules import standing_pins as sp
    from mre.modules.sandbox import (_parse_dt, _parse_ref_date, _restrict_window,
                                     classify_feasibility)
    from mre.contracts.vocabularies import ModuleCode, RunStatus
    from mre.reporter import Reporter

    s = Stage()
    reader = SnapshotStore(run_dir / "snapshots").load_snapshot(snapshot_id)
    s.mark("open snapshot")
    demands = list(reader.iter_entities("demand"))
    fuls = list(reader.iter_entities("fulfillment"))
    wps = list(reader.iter_entities("workpackage"))
    ops = list(reader.iter_entities("operation"))
    edges = list(reader.iter_entities("precedenceedge"))
    resources = list(reader.iter_entities("resource"))
    pools = list(reader.iter_entities("resourcepool"))
    calendars = list(reader.iter_entities("calendar"))
    constraints = list(reader.iter_entities("constraint"))
    costmodels = list(reader.iter_entities("costmodel"))
    incumbent = list(reader.iter_entities("assignment"))
    s.mark("read entities")
    cost_model = costmodels[0] if costmodels else {}

    evidence = _read_evidence(run_dir / "runs")
    s.mark("read evidence (_read_evidence)")
    ctx = derive_base_context(run_dir / "runs")
    s.mark("derive_base_context")
    reference_date = _parse_ref_date(ctx.get("reference_date"))
    hs, he = _m5_horizon(evidence)
    incumbent_placement = _placements(incumbent)
    flat = flatten_all_calendars(calendars, hs, he)
    s.mark("flatten calendars")

    # window restriction, as the API supplies it
    window_ops = {a["operation_ref"] for a in _window_op_ids(run_dir, incumbent)}
    ops2, wps2, fuls2, demands2 = _restrict_window(ops, wps, fuls, demands,
                                                   window_ops or None)
    s.mark("restrict to active window")

    rep = Reporter.begin(module=ModuleCode.M5, purpose="latency probe build",
                         config={}, trigger="probe", snapshot_id=snapshot_id,
                         sink_dir=run_dir / "sandbox" / "runs")
    model, var_map = SolverBuilder(reference_date=reference_date).build(
        wps2 + ops2 + edges, resources + pools, flat,
        fuls2 + demands2, constraints, cost_model)
    rep.end(RunStatus.SUCCESS)
    s.mark("SolverBuilder.build")

    apply_solution_hints(model, var_map, incumbent)
    s.mark("apply_solution_hints")

    pin_dt = _parse_dt(pin["pin_start_iso"])
    pin_min = int((pin_dt - hs).total_seconds() // 60)
    sp.apply_pin(model, var_map, pin["pin_op_id"], pin["pin_resource_id"], pin_min)
    s.mark("apply_pin")

    r = Reporter.begin(module=ModuleCode.M6, purpose="latency probe solve",
                       config={}, trigger="probe", snapshot_id=snapshot_id,
                       sink_dir=run_dir / "sandbox" / "runs")
    res = SolveRunner(time_limit_seconds=budget_s, num_search_workers=1,
                      random_seed=0, deterministic_time=1.0,
                      stop_after_first_solution=True).solve(model, var_map, r)
    r.end(RunStatus.SUCCESS)
    s.mark("SolveRunner.solve (THE BUDGET)")
    print(f"    -> status {res.status} = {classify_feasibility(res.status)}")
    print(f"    -> model: {len(ops2)} ops, {len(resources)} resources, "
          f"{len(flat)} flattened calendars")
    return s


def _window_op_ids(run_dir: Path, incumbent):
    """The active-window ops, the way the API's _rolling_gesture_context finds
    them: from the schedule document's commitment_state."""
    docs = sorted((run_dir).rglob("schedule_document*.json"))
    if not docs:
        return []
    doc = json.loads(docs[-1].read_text(encoding="utf-8"))
    return [a for a in (doc.get("assignments") or [])
            if a.get("commitment_state") == "active_window"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--data-root", default="_data")
    args = ap.parse_args()

    for label, sched, run in (("DENSE  386 bars", "rolling-c9973708-865", DENSE_RUN),
                              ("PINNED  56 bars", "rolling-c362baa4-1b0", PINNED_RUN)):
        doc = _api(args.api, f"/schedules/{sched}")["data"]
        movable = [a for a in doc["assignments"]
                   if a.get("commitment_state") == "active_window"
                   and len(a.get("chunks") or []) <= 1]
        mover = sorted(movable, key=lambda a: a["chunks"][0]["start"])[len(movable) // 2]
        pin = {"pin_op_id": mover["operation_ref"],
               "pin_resource_id": mover["resource_id"],
               "pin_start_iso": mover["chunks"][0]["start"]}

        # the HTTP figure the founder saw
        t0 = time.perf_counter()
        _api(args.api, f"/schedules/{sched}/sandbox/feasibility", pin)
        http = time.perf_counter() - t0

        run_dir = Path(args.data_root) / "runs" / run
        snap = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))["snapshot_id"] \
            if (run_dir / "run.json").exists() else _snapshot_of(args.api, sched)
        print(f"\n{'='*70}\n{label}   HTTP round trip {http:.2f}s")
        s = stages(run_dir, snap, pin)
        tot = s.report("SUM OF STAGES")
        print(f"    {'HTTP (incl. FastAPI + JSON)':<34} {http:7.3f}s")


def _snapshot_of(base, sched):
    return _api(base, f"/schedules/{sched}/meta")["data"]["snapshot_id"]


if __name__ == "__main__":
    main()

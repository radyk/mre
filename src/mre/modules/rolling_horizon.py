"""Rolling-horizon (sliced) solve runner — Session 4B.2, R-SC2.

R-SC2 (docs/04): slicing is a ROLLING HORIZON with a FROZEN ZONE and GRAVITY
admission. Solve a window of declared length; commit only the frozen front;
roll and re-solve (committed work is in the past, so it constrains nothing and
is dropped; warm-start carries the incumbent). Inclusion = the time window PLUS
gravity:
    (a) must-start-by pull   — latest-feasible-start inside the window admits it
    (b) weighted-criticality — a high-weight job is pulled in early
    (c) setup-family affinity — a job sharing a family with in-window work

Window length is chosen by MEASUREMENT (the knee of the cost-vs-window curve,
tools/pilot_measurements.py) and declared per deployment. Far-horizon
look-ahead pricing is named and parked.

Design (v1):
  * The spine (gate → adapter → validator → planner) runs ONCE (prepare_plant),
    persisting the full canonical snapshot. The rolling loop then works at the
    M5/M6/M7 level, choosing per window which demands' operations to solve.
  * FROZEN ZONE: after each window solve, every operation whose solved END falls
    within [window_start, frozen_end) is COMMITTED — its (resource, start) is
    recorded and it is removed from all future windows. Because the next window's
    floor IS frozen_end, committed work always ends before every future window
    starts: it can never conflict with future operations and never needs a pin
    (this is why "committed work enters as fixed" reduces, in a rolling design,
    to "committed work is in the past" — the WIP machinery's guarantee, for free).
  * STANDING PINS (R-DP8): external accepted-edit pins compile into whichever
    window holds them (apply_standing_pins, on the operations still in the model).
  * DETERMINISTIC mode (solver-workers 1 + seed) for every measurement claim.
  * COST: the rolling process yields a committed placement per operation; the
    reported total cost is ONE exact Extractor pass over the fully-pinned union
    (§_final_extract) — the same method across every window setting, so the
    window curve is a fair comparison.

Nothing here imports ortools directly except through SolverBuilder/SolveRunner.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.modules.calendar_utils import flatten_all_calendars
from mre.modules.snapshot_store import SnapshotStore
from mre.reporter import Reporter

UTC = timezone.utc
_SHIFT_MIN = 720          # nominal working minutes/day (07:00-19:00) for est.
_HORIZON_BUFFER_DAYS = 90  # must match compute_horizon / SolverBuilder (chunk slots)
_WINDOW_TAIL_DAYS = 21     # per-window horizon tail past window_end (near-term only)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

_DUR_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def parse_iso_duration_minutes(s: Optional[str]) -> int:
    """'PT1H45M' -> 105 (minutes). None/'' -> 0."""
    if not s:
        return 0
    m = _DUR_RE.fullmatch(s.strip())
    if not m:
        return 0
    h, mi, se = (int(x) if x else 0 for x in m.groups())
    return h * 60 + mi + (1 if se else 0)


def _dt(iso: str) -> datetime:
    d = datetime.fromisoformat(iso)
    return d if d.tzinfo else d.replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# prepared plant (spine run once)
# ---------------------------------------------------------------------------

@dataclass
class PreparedPlant:
    snapshot_id: str
    out_dir: Path
    store: Any
    reference_date: datetime
    cost_model: dict
    resources: list[dict]
    pools: list[dict]
    calendars: list[dict]            # raw (not flattened)
    constraints: list[dict]
    demands: list[dict]
    fulfillments: list[dict]
    workpackages: list[dict]
    operations: list[dict]
    edges: list[dict]
    excluded_demand_ids: set
    # derived
    ops_by_wp: dict = field(default_factory=dict)
    wp_of_demand: dict = field(default_factory=dict)
    demand_working_minutes: dict = field(default_factory=dict)
    demand_families: dict = field(default_factory=dict)
    priority_multipliers: dict = field(default_factory=dict)

    @property
    def schedulable_demands(self) -> list[dict]:
        return [d for d in self.demands if d["id"] not in self.excluded_demand_ids]


def _report(module, purpose, snap_id, runs_dir, config=None):
    return Reporter.begin(module=module, purpose=purpose, config=config or {},
                          trigger="rolling_horizon", snapshot_id=snap_id,
                          sink_dir=runs_dir)


def prepare_plant(
    submission_dir: Path | str,
    out_dir: Path | str,
    reference_date: Optional[datetime] = None,
    policy: str = "identity_v1",
) -> PreparedPlant:
    """Run the spine (gate → adapter → validator → planner) once and load the
    full canonical snapshot. reference_date defaults to the manifest's."""
    from mre.api.registry import prepare_out_dir
    from mre.modules.conformance import ConformanceGate
    from mre.modules.ids_adapter import IDSAdapter
    from mre.modules.validator import Validator
    from mre.modules.planner import Planner

    submission_dir = Path(submission_dir)
    snap_id = "snap-rolling"
    out_dir, runs_dir = prepare_out_dir(Path(out_dir), snap_id, log=lambda *_: None)
    store = SnapshotStore(out_dir / "snapshots")

    # M0 gate
    g_rep = _report(ModuleCode.M0, "IDS conformance gate", snap_id, runs_dir,
                    {"submission_dir": str(submission_dir)})
    gate = ConformanceGate().run(submission_dir, g_rep)
    g_rep.end(RunStatus.SUCCESS if gate.go else RunStatus.PARTIAL)
    if gate.grade == "REJECTED":
        raise ValueError(f"submission REJECTED by gate: {gate.certificate['deficiencies']}")
    manifest = gate.certificate["manifest"]
    if reference_date is None:
        from datetime import date
        rd = date.fromisoformat(manifest["reference_date"])
        reference_date = datetime(rd.year, rd.month, rd.day, tzinfo=UTC)

    # M1 adapter
    a_rep = _report(ModuleCode.M1, "IDS adapter", snap_id, runs_dir)
    IDSAdapter(submission_dir=submission_dir, manifest=manifest).run(
        snapshot_id=snap_id, store=store, reporter=a_rep)
    a_rep.end(RunStatus.SUCCESS)

    # M3 validator
    v_rep = _report(ModuleCode.M3, "validator", snap_id, runs_dir,
                    {"reference_date": reference_date.isoformat()})
    v_result = Validator().run(snapshot_id=snap_id, store=store, reporter=v_rep,
                               reference_date=reference_date)
    v_rep.end(RunStatus.SUCCESS)

    # M4 planner
    p_rep = _report(ModuleCode.M4, "planner", snap_id, runs_dir, {"policy": policy})
    Planner(policy=policy).run(snapshot_id=snap_id, store=store, reporter=p_rep,
                               excluded_demand_ids=v_result.excluded_demand_ids)
    p_rep.end(RunStatus.SUCCESS)

    reader = store.load_snapshot(snap_id)
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
    cost_model = costmodels[0] if costmodels else {
        "id": "default-cm", "resource_rates": {},
        "setup_cost_basis": {"fixed_per_setup": 50.0, "scrap_cost_per_unit": 0.0},
        "tardiness_weights": {"base_weight": 1.0, "commitment_class_multipliers": {}},
    }

    plant = PreparedPlant(
        snapshot_id=snap_id, out_dir=out_dir, store=store,
        reference_date=reference_date, cost_model=cost_model,
        resources=resources, pools=pools, calendars=calendars,
        constraints=constraints, demands=demands, fulfillments=fuls,
        workpackages=wps, operations=ops, edges=edges,
        excluded_demand_ids=set(v_result.excluded_demand_ids),
    )
    _derive_maps(plant)
    return plant


def _derive_maps(plant: PreparedPlant) -> None:
    for op in plant.operations:
        plant.ops_by_wp.setdefault(op["workpackage_ref"], []).append(op)
    for ful in plant.fulfillments:
        plant.wp_of_demand[ful["demand_ref"]] = ful["workpackage_ref"]
    # priority multipliers (commitment_class -> weight)
    pm = ((plant.cost_model.get("tardiness_weights") or {})
          .get("commitment_class_multipliers") or {})
    if not pm:
        pm = {"standard": 1.0, "high": 3.0, "critical": 8.0}
    plant.priority_multipliers = pm
    # per-demand working minutes + setup families
    for d in plant.demands:
        wp = plant.wp_of_demand.get(d["id"])
        ops = plant.ops_by_wp.get(wp, [])
        mins = 0
        fams: set[str] = set()
        for op in ops:
            mins += (parse_iso_duration_minutes(op.get("run_duration"))
                     + parse_iso_duration_minutes(op.get("setup_duration")))
            if op.get("setup_family"):
                fams.add(op["setup_family"])
        plant.demand_working_minutes[d["id"]] = mins
        plant.demand_families[d["id"]] = fams


# ---------------------------------------------------------------------------
# rolling result
# ---------------------------------------------------------------------------

@dataclass
class WindowMetric:
    index: int
    window_start: str
    window_end: str
    frozen_end: str
    admitted_demands: int
    free_ops: int
    committed_this_window: int
    gravity_admits: dict
    status: str
    objective: Optional[float]
    solve_wall_s: float
    build_wall_s: float


@dataclass
class RollingResult:
    window_days: int
    frozen_days: int
    gravity: bool
    windows: list[WindowMetric]
    committed_ops: dict           # op_id -> {resource, start(iso), end(iso)}
    n_windows: int
    total_solve_wall_s: float
    total_build_wall_s: float
    total_cost: Optional[float]
    cost_ledger: dict
    service_outcomes: list[dict]
    on_time: int
    late: int
    total_tardiness_minutes: float
    uncommitted_ops: int


# ---------------------------------------------------------------------------
# admission (the time window + gravity)
# ---------------------------------------------------------------------------

def _weight(plant: PreparedPlant, d: dict) -> float:
    cc = d.get("commitment_class") or "standard"
    return float(plant.priority_multipliers.get(cc, 1.0))


def _latest_feasible_start(plant: PreparedPlant, d: dict) -> datetime:
    due = _dt(d["due"])
    mins = plant.demand_working_minutes.get(d["id"], 0)
    days = max(1, -(-mins // _SHIFT_MIN))     # ceil working days
    return due - timedelta(days=days)


def _admit(plant, candidates, window_start, window_end, gravity, crit_threshold):
    """Return (admitted_ids:set, reasons:dict). candidates = demands with >=1
    uncommitted op. Base = due within window AND released by window_end."""
    admitted: set = set()
    reasons: dict = {"base": 0, "a_must_start": 0, "b_criticality": 0, "c_family": 0}
    for d in candidates:
        es = _dt(d["earliest_start"]) if d.get("earliest_start") else window_start
        if es > window_end:
            continue
        if _dt(d["due"]) <= window_end:
            admitted.add(d["id"])
            reasons["base"] += 1
    if not gravity:
        return admitted, reasons
    window_families: set = set()
    for did in admitted:
        window_families |= plant.demand_families.get(did, set())
    # criticality-sorted single pass so family affinity sees the base + earlier pulls
    for d in sorted(candidates, key=lambda x: -_weight(plant, x)):
        if d["id"] in admitted:
            continue
        es = _dt(d["earliest_start"]) if d.get("earliest_start") else window_start
        if es > window_end:
            continue
        if _latest_feasible_start(plant, d) <= window_end:
            admitted.add(d["id"]); reasons["a_must_start"] += 1
            window_families |= plant.demand_families.get(d["id"], set())
        elif _weight(plant, d) >= crit_threshold:
            admitted.add(d["id"]); reasons["b_criticality"] += 1
            window_families |= plant.demand_families.get(d["id"], set())
        elif plant.demand_families.get(d["id"], set()) & window_families:
            admitted.add(d["id"]); reasons["c_family"] += 1
    return admitted, reasons


# ---------------------------------------------------------------------------
# per-window model build (subset of the canonical entities)
# ---------------------------------------------------------------------------

def _build_window(plant, free_ops, pinned_ops, ref, horizon_end):
    """Build the window model with an ABSOLUTE origin (ref), over the free
    operations (admitted, not yet committed) PLUS the still-overlapping committed
    (pinned) operations. Free ops are floored at t0 and pinned ops fixed by the
    CALLER. The single ref origin lets committed work that began before this
    window pin at a non-negative offset while free work is floored at t0."""
    from mre.modules.solver_builder import SolverBuilder

    ops = free_ops + pinned_ops
    wp_ids = {op["workpackage_ref"] for op in ops}
    wps = [w for w in plant.workpackages if w["id"] in wp_ids]
    fuls = [f for f in plant.fulfillments if f["workpackage_ref"] in wp_ids]
    dem_ids = {f["demand_ref"] for f in fuls}
    demands = [d for d in plant.demands if d["id"] in dem_ids]
    edges = plant.edges   # spec-level; builder resolves per-WP, skips absent (§665)

    cals = flatten_all_calendars(plant.calendars, ref, horizon_end)
    builder = SolverBuilder(reference_date=ref)
    model, var_map = builder.build(
        wps + ops + edges, plant.resources + plant.pools, cals,
        fuls + demands, plant.constraints, plant.cost_model)
    return model, var_map


# ---------------------------------------------------------------------------
# the rolling loop
# ---------------------------------------------------------------------------

def run_rolling_horizon(
    plant: PreparedPlant,
    window_days: int,
    frozen_days: int,
    gravity: bool = True,
    deterministic: bool = True,
    seed: int = 0,
    member_time_limit_s: float = 30.0,
    det_time: float = 4.0,
    crit_threshold: float = 3.0,
    standing_pins: Optional[list[dict]] = None,
    max_windows: Optional[int] = None,
) -> RollingResult:
    """Roll a window of `window_days`, committing the frozen front of
    `frozen_days`, until every operation is committed."""
    from mre.modules.solve_runner import SolveRunner
    from mre.modules import standing_pins as sp

    if frozen_days > window_days:
        raise ValueError("frozen_days must be <= window_days")

    ref = plant.reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
    sched = plant.schedulable_demands
    if not sched:
        raise ValueError("no schedulable demands")
    last_due = max(_dt(d["due"]) for d in sched if d.get("due"))
    horizon_days = max(1, (last_due - ref).days)
    if max_windows is None:
        # enough windows to cover the horizon AND a generous late tail (an
        # overloaded plant schedules work well past its due dates); a final
        # sweep (below) catches anything the cap leaves uncommitted.
        max_windows = (2 * horizon_days // frozen_days) + 20

    import time as _t
    from mre.modules.solver_builder import apply_solution_hints

    committed: dict = {}                   # op_id -> {resource, start, end}  (placements)
    last_placements: list[dict] = []       # warm-start carry (all solved ops)
    windows: list[WindowMetric] = []
    total_solve = total_build = 0.0
    workers = 1 if deterministic else None
    sp_norm = [sp.normalize_pin(p) for p in (standing_pins or [])]

    # A windowed build only needs to reach far enough to place near-term work
    # (free ops are earliness-pulled and floored at t0), so a MODEST horizon
    # keeps the per-window build cheap — the whole point of slicing. The global
    # horizon end (max due + full buffer) is used only by the final pricing pass.
    global_horizon_end = last_due.replace(hour=23, minute=59, second=59) + \
        timedelta(days=_HORIZON_BUFFER_DAYS)
    all_ops_of_sched = [op for op in plant.operations
                        if op["workpackage_ref"] in
                        {plant.wp_of_demand.get(d["id"]) for d in sched}]
    total_op_count = len(all_ops_of_sched)

    def _ops_of(did):
        return plant.ops_by_wp.get(plant.wp_of_demand.get(did), [])

    for i in range(max_windows):
        t0 = ref + timedelta(days=i * frozen_days)
        window_end = t0 + timedelta(days=window_days)
        frozen_end = t0 + timedelta(days=frozen_days)
        t0_min = int((t0 - ref).total_seconds() / 60.0)
        frozen_end_min = int((frozen_end - ref).total_seconds() / 60.0)

        # candidate demands: any op not yet committed
        remaining = [d for d in sched
                     if any(op["id"] not in committed for op in _ops_of(d["id"]))]
        if not remaining:
            break
        admitted, reasons = _admit(plant, remaining, t0, window_end,
                                   gravity, crit_threshold)
        if not admitted:
            continue

        free_ops = [op for did in admitted for op in _ops_of(did)
                    if op["id"] not in committed]
        # committed operations still overlapping this window (end > t0) are pinned;
        # those fully in the past cannot conflict with free work floored at t0.
        pinned_ops = [op for op in all_ops_of_sched
                      if op["id"] in committed and _dt(committed[op["id"]]["end"]) > t0]

        win_horizon_end = min(global_horizon_end,
                              window_end + timedelta(days=_WINDOW_TAIL_DAYS))
        t_b = _t.perf_counter()
        model, var_map = _build_window(plant, free_ops, pinned_ops, ref, win_horizon_end)
        total_build += _t.perf_counter() - t_b

        free_start_vars = []
        for op in free_ops:
            v = var_map.op_start.get(op["id"])
            if v is not None:
                model.add(v >= t0_min)          # no scheduling in the past
                free_start_vars.append(v)
        for op in pinned_ops:                   # fix carried commitments (absolute)
            c = committed.get(op["id"])
            if not c or op["id"] not in var_map.op_start:
                continue
            smin = int(round((_dt(c["start"]) - ref).total_seconds() / 60.0))
            try:
                sp.apply_pin(model, var_map, op["id"], c["resource"], max(0, smin))
            except Exception:
                pass
        # EARLINESS incentive: a weight-1-per-minute ASAP pull, strictly dominated
        # by tardiness (~42 units/min at _COST_SCALE=100) and setup — a pure
        # tiebreaker that fills the frozen front so the roll makes progress.
        if var_map.objective_terms and free_start_vars:
            model.minimize(sum(var_map.objective_terms) + sum(free_start_vars))
        if last_placements:
            apply_solution_hints(model, var_map, last_placements)
        if sp_norm:
            sp.apply_standing_pins(model, var_map, sp_norm, var_map.horizon_start)

        t_s = _t.perf_counter()
        solve = SolveRunner(time_limit_seconds=member_time_limit_s,
                            num_search_workers=workers, random_seed=seed,
                            deterministic_time=(det_time if deterministic else None)
                            ).solve(model, var_map, None)
        solve_wall = _t.perf_counter() - t_s
        total_solve += solve_wall

        committed_this = 0
        if solve.status in ("OPTIMAL", "FEASIBLE"):
            sv = solve.solve_values
            placements = []
            for op in free_ops:
                oid = op["id"]
                if oid not in sv.op_start_minutes:
                    continue
                res = sv.op_resource.get(oid)
                if res is None:
                    continue
                s_min = sv.op_start_minutes[oid]
                s_dt = ref + timedelta(minutes=s_min)
                e_dt = ref + timedelta(minutes=sv.op_end_minutes[oid])
                placements.append({"operation_ref": oid, "resource_id": res,
                                   "start": s_dt.isoformat(),
                                   "run_windows": [{"start": s_dt.isoformat(),
                                                    "end": e_dt.isoformat()}]})
                # FROZEN ZONE: commit every operation STARTING within the frozen
                # front (op-level, so a long job freezes piecewise as it rolls).
                if s_min < frozen_end_min:
                    committed[oid] = {"resource": res, "start": s_dt.isoformat(),
                                      "end": e_dt.isoformat()}
                    committed_this += 1
            last_placements = placements

        windows.append(WindowMetric(
            index=i, window_start=t0.isoformat(),
            window_end=window_end.isoformat(), frozen_end=frozen_end.isoformat(),
            admitted_demands=len(admitted), free_ops=len(free_ops),
            committed_this_window=committed_this, gravity_admits=reasons,
            status=solve.status, objective=solve.objective,
            solve_wall_s=round(solve_wall, 3), build_wall_s=0.0))

        if len(committed) >= total_op_count:
            break

    # RESOLVE + PRICE: one full solve that PINS the committed operations and
    # places any leftovers (a demand the window cap never reached) FREELY around
    # them, then extracts the exact decomposed cost. Same method for every
    # window setting => a fair curve.
    ledger, svc, tot_cost, uncommitted = _final_extract(plant, committed, seed,
                                                        deterministic, sched, det_time)
    on_time = sum(1 for s in svc if s.get("lateness_minutes", 0) <= 0)
    late = sum(1 for s in svc if s.get("lateness_minutes", 0) > 0)
    tard = sum(max(0, s.get("lateness_minutes", 0)) for s in svc)

    return RollingResult(
        window_days=window_days, frozen_days=frozen_days, gravity=gravity,
        windows=windows, committed_ops=committed, n_windows=len(windows),
        total_solve_wall_s=round(total_solve, 3),
        total_build_wall_s=round(total_build, 3),
        total_cost=tot_cost, cost_ledger=ledger, service_outcomes=svc,
        on_time=on_time, late=late, total_tardiness_minutes=tard,
        uncommitted_ops=uncommitted)


# ---------------------------------------------------------------------------
# final exact cost — one Extractor pass over the fully-pinned committed union
# ---------------------------------------------------------------------------

def _final_extract(plant, committed, seed, deterministic, sched, det_time=8.0):
    """Build the full model over every scheduled demand's operations, PIN the
    committed operations to their rolling placement, let any leftovers place
    FREELY around the pins (so they cannot conflict), solve, then extract the
    exact decomposed ledger + service outcomes. Returns
    (ledger, service_outcomes, total_cost, leftover_count)."""
    from mre.modules.solver_builder import SolverBuilder
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.extractor import Extractor
    from mre.modules import standing_pins as sp

    sched_ids = {d["id"] for d in sched}
    wp_ids = {plant.wp_of_demand.get(did) for did in sched_ids}
    wp_ids.discard(None)
    ops = [op for op in plant.operations if op["workpackage_ref"] in wp_ids]
    wps = [w for w in plant.workpackages if w["id"] in wp_ids]
    fuls = [f for f in plant.fulfillments if f["demand_ref"] in sched_ids]
    demands = [d for d in plant.demands if d["id"] in sched_ids]
    edges = plant.edges   # spec-level; builder resolves per-WP, skips absent (§665)

    ref = plant.reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
    dues = [_dt(d["due"]) for d in demands if d.get("due")]
    ends = [_dt(c["end"]) for c in committed.values()]
    # Every op is pinned to a known placement (or a small free leftover set), so
    # a modest horizon past the last placement/due suffices — no full buffer.
    horizon_end = (max(dues + ends) if (dues or ends) else ref).replace(
        hour=23, minute=59, second=59) + timedelta(days=_WINDOW_TAIL_DAYS)
    cals = flatten_all_calendars(plant.calendars, ref, horizon_end)

    builder = SolverBuilder(reference_date=ref)
    model, var_map = builder.build(
        wps + ops + edges, plant.resources + plant.pools, cals,
        fuls + demands, plant.constraints, plant.cost_model)

    hstart = var_map.horizon_start
    for oid, c in committed.items():
        if oid not in var_map.op_start:
            continue
        start_min = int(round((_dt(c["start"]) - hstart).total_seconds() / 60.0))
        try:
            sp.apply_pin(model, var_map, oid, c["resource"], max(0, start_min))
        except Exception:
            pass  # a splittable/edge case that resists pinning — priced by solve

    workers = 1 if deterministic else None
    solve = SolveRunner(time_limit_seconds=120.0, num_search_workers=workers,
                        random_seed=seed,
                        deterministic_time=(det_time * 4 if deterministic else None)
                        ).solve(model, var_map, None)
    if solve.status not in ("OPTIMAL", "FEASIBLE"):
        return {}, [], None, len([o for o in ops if o["id"] not in committed])

    # record any leftover (uncommitted) operations' placements from this solve
    sv = solve.solve_values
    leftovers = 0
    for op in ops:
        oid = op["id"]
        if oid in committed or oid not in sv.op_start_minutes:
            continue
        res = sv.op_resource.get(oid)
        if res is None:
            continue
        committed[oid] = {
            "resource": res,
            "start": (sv.horizon_start + timedelta(minutes=sv.op_start_minutes[oid])).isoformat(),
            "end": (sv.horizon_start + timedelta(minutes=sv.op_end_minutes[oid])).isoformat()}
        leftovers += 1

    result = Extractor().extract(
        solve_values=solve.solve_values, snapshot_id=plant.snapshot_id,
        operations=ops, workpackages=wps, resources=plant.resources,
        fulfillments=fuls, demands=demands, cost_model=plant.cost_model,
        reporter=None, cal_windows=var_map.cal_windows,
        op_eligible=var_map.op_eligible, snapshot_writer=None,
        overtime_windows=var_map.overtime_windows, is_scenario=True)
    ledger = result.cost_ledger
    return ledger, result.service_outcomes, ledger.get("total_cost"), leftovers

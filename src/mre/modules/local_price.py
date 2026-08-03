"""THE LOCAL PRICER — what "your move" costs, and nothing else.

Session 4B.24, R-T2 amendment clause (2). The card has always had a line
labelled *your move*. Until this module existed, that line was computed by
re-solving the whole window with the pin held and subtracting the incumbent's
total — so it carried, under the planner's name, every difference between two
searches: a different tie broken here, a different order sequenced there, all of
it re-optimization the planner neither asked for nor caused.

On a board whose incumbent sits at a 92.4% gap that is not a rounding error. The
founder nudged one operation four hours inside an overtime window it already
occupied, on a machine where nothing else ran in those hours, and the card
charged the move $50,784.33 and relocated four unrelated orders by two to three
weeks. Every one of those numbers was real; not one of them was about the
gesture.

THE ONLY READING UNDER WHICH THE WORDS "YOUR MOVE" ARE TRUE is this one: hold
every other placement exactly where it is, move the one bar, recompute the whole
ledger, and check that the result is still a legal schedule. That is what this
module does. It is the 4B.6c compressor's validate-and-price discipline
(``tools/spikes/tiebreak_4b6c/compressor.py``) pointed at a pin instead of at a
left-shift: full ledger recompute after the change, and re-validation by PINNING
EVERY PLACEMENT INTO A FRESHLY BUILT MODEL and asking CP-SAT — the model's own
verdict, not this module's opinion of itself (56/56 precedent, docs/04 4B.6c).

Three properties this buys, none of which the re-solve had:

  * DETERMINISTIC BY CONSTRUCTION. There is no search on the happy path. The
    ledger is arithmetic over a fixed set of placements; the same gesture gives
    the same number on any machine, forever.
  * ATTRIBUTABLE. Nothing else moved, so nothing else can be charged. The
    founder's nudge prices at $0.00 with an empty affected list.
  * REFUSABLE WITH A REASON. Where the pin makes the HELD world illegal — a real
    collision, a closed calendar, a predecessor that has not finished — the
    structural checks below name WHICH constraint, in docs/05 family terms. That
    is a TRUE REFUSAL about the plant, a different thing from beat one's
    ``undetermined`` (which is about our budget) and from a failure (which is
    about our process).

WHAT IT DOES NOT CLAIM. A local price is the cost of the move against a world
held still. It is NOT a claim that no cheaper arrangement exists — that question
belongs to the opportunity search (clause 3), which is reported separately, under
its own heading, with its own affected list, and is never fused with this number.
A refusal here means the pin does not fit the world AS IT STANDS; the solver
might well place it there if allowed to move other work, and the card says so.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Two placements on one machine may not overlap. A shared boundary (one ends
# exactly where the next begins) is not an overlap.
_OVERLAP_TOLERANCE_MIN = 0

# The docs/05 constraint families a structural refusal can name. These are the
# families this module can PROVE from the held world; anything else is left to
# CP-SAT's verdict, which is authoritative but cannot name a family.
FAMILY_RESOURCE = "B1"        # resource capacity — the machine is occupied
FAMILY_CALENDAR = "C1/C2"     # the calendar — the machine is not open then
FAMILY_PRECEDENCE = "A1/A2"   # precedence — an upstream step has not finished
FAMILY_FROZEN = "R-F1"        # the frozen boundary — committed work
FAMILY_ELIGIBILITY = "B2"     # eligibility — the op cannot run on that machine
FAMILY_MODEL = "model"        # CP-SAT refused and no structural check explains it


@dataclass
class LocalRefusal:
    """A PROVEN refusal about the plant: the pin does not fit the world as it
    stands, and this is which constraint says so. ``family`` is the docs/05
    family; ``sentence`` is the authored planner-facing line."""
    family: str
    sentence: str
    # The other operation involved, when the refusal is about one (a collision,
    # a predecessor). Canonical ids — the cockpit resolves planner vocabulary.
    other_op_ref: Optional[str] = None
    other_work_orders: list[str] = field(default_factory=list)
    resource_id: Optional[str] = None
    at: Optional[str] = None          # the ISO instant the constraint binds at
    # Is this refusal a consequence of HOLDING OTHER WORK STILL, or of the plant
    # itself? A machine that is shut refuses the pin however the rest of the plan
    # is arranged; a machine that is merely OCCUPIED refuses it only because this
    # price holds the occupant where it is. The distinction is the difference
    # between "no" and "not without moving other work", and a planner must never
    # be told the first when the second is true.
    holds_others: bool = False

    def summary(self) -> dict:
        return asdict(self)


@dataclass
class LocalPrice:
    """The price of ONE move against a world held still.

    ``priced`` is True only when the move is legal AND the ledger closed. Every
    other case is a stated outcome, never a silent zero: ``refusal`` carries a
    proven refusal about the plant, ``error`` carries a failure of ours."""
    priced: bool
    pin: dict = field(default_factory=dict)
    refusal: Optional[dict] = None
    error: str = ""
    # The move itself, in ledger dollars: total_after - total_before, both
    # recomputed by the SAME code path over the SAME placements bar one, so the
    # difference is a property of the move and of nothing else.
    cost_delta_abs: Optional[float] = None
    cost_delta_pct: Optional[float] = None
    total_before: Optional[float] = None
    total_after: Optional[float] = None
    cost_lines: Optional[list[dict]] = None
    affected_orders: list[dict] = field(default_factory=list)
    lateness_delta_min: int = 0
    moves: list[dict] = field(default_factory=list)
    # The incumbent's own PERSISTED total, and whether the locally recomputed
    # "before" agrees with it. They are computed by different paths (one at solve
    # time through the reporter, one here in memory), so agreement is a claim
    # that must be checked rather than assumed — a disagreement does not
    # invalidate the DELTA (both sides of it are recomputed here) but it is a
    # fact a reader is entitled to.
    persisted_total: Optional[float] = None
    agrees_with_persisted: Optional[bool] = None
    # Session 4B.30 Item 3 — THE SUBJECT'S OWN DUE-DATE VERDICT, before and
    # after. ``affected_orders`` reports DELTAS across the board and is the right
    # shape for "what does this displace"; it cannot answer "does the due date
    # survive", which needs the absolute completion, the declared due date, and
    # R-PD1 clause (4)'s split of what is already sunk from what this placement
    # decides. Populated only when the caller names the demands it cares about,
    # so nothing changes for a caller that does not ask.
    subject_outcomes: list[dict] = field(default_factory=list)
    # The model's own verdict on the held world with the pin applied.
    # {"method": "cp-sat-pin-all", "status": ..., "wall_time_s": ...} or
    # {"method": "skipped", ...} when the caller did not ask for it.
    validation: dict = field(default_factory=dict)
    wall_time_s: float = 0.0
    build_wall_time_s: float = 0.0
    price_wall_time_s: float = 0.0

    def summary(self) -> dict:
        return asdict(self)


def _parse_dt(raw) -> Optional[datetime]:
    if raw is None or raw == "":
        return None
    dt = (raw if isinstance(raw, datetime)
          else datetime.fromisoformat(str(raw).replace("Z", "+00:00")))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _parse_ref_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw or raw == "now":
        return None
    dt = datetime.fromisoformat(raw)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class _HeldWorld:
    """Everything the pricer needs about the incumbent, loaded once."""
    ops: list
    wps: list
    resources: list
    fuls: list
    demands: list
    cost_model: dict
    var_map: object
    model: object
    horizon_start: datetime
    reader: object
    # op_id -> (resource_id, start_min, end_min)
    placements: dict
    # op_id -> [(chunk_start_min, chunk_end_min), ...] for chunked ops
    chunks: dict
    ops_by_id: dict
    wo_of_op: dict
    # Everything the model build needed, kept so a SECOND model can be built
    # without re-reading the snapshot. Validation pins into the model above and
    # therefore consumes it; a world priced twice rebuilds rather than pinning
    # one model twice, which would silently validate against the first pin too.
    build_args: tuple = ()
    model_consumed: bool = False
    edges: list = field(default_factory=list)
    # Session 4B.30: the far end of the model's own grid. A pin past it is not
    # something the pricer can be asked about, and the difference between "we
    # can't price that" and "the plant refuses it" is the whole discipline here.
    horizon_end: Optional[datetime] = None


def _load_held_world(out_dir: Path, snapshot_id: str, runs_subdir: str,
                     restrict_op_ids: Optional[set]) -> _HeldWorld:
    from mre.contracts.vocabularies import ModuleCode, RunStatus
    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.scenario import derive_base_context
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solver_builder import SolverBuilder
    from mre.modules.solution_pool import _m5_horizon, _read_evidence
    from mre.modules.sandbox import _restrict_window
    from mre.reporter import Reporter

    reader = SnapshotStore(out_dir / "snapshots").load_snapshot(snapshot_id)
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
    assignments = list(reader.iter_entities("assignment"))
    cost_model = costmodels[0] if costmodels else {}

    ops, wps, fuls, demands = _restrict_window(
        ops, wps, fuls, demands, restrict_op_ids)

    evidence = _read_evidence(out_dir / runs_subdir)
    ctx = derive_base_context(out_dir / runs_subdir)
    reference_date = _parse_ref_date(ctx.get("reference_date"))
    horizon_start, horizon_end = _m5_horizon(evidence)
    flattened = flatten_all_calendars(calendars, horizon_start, horizon_end)

    sandbox_dir = out_dir / "sandbox"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    b_rep = Reporter.begin(
        module=ModuleCode.M5, purpose="local price model build",
        config={"local_price": True},
        trigger="local_price", snapshot_id=snapshot_id,
        sink_dir=sandbox_dir / "runs")
    build_args = (reference_date, wps + ops + edges, resources + pools,
                  flattened, fuls + demands, constraints, cost_model)
    model, var_map = SolverBuilder(reference_date=reference_date).build(
        *build_args[1:])
    b_rep.end(RunStatus.SUCCESS)

    keep = {o["id"] for o in ops}
    placements: dict = {}
    chunks: dict = {}
    for a in assignments:
        oid = a.get("operation_ref")
        if oid not in keep:
            continue
        rid = a.get("resource_id")
        if not rid:
            ras = a.get("resource_assignments") or []
            rid = ras[0].get("resource_ref") if ras else None
        wins = (a.get("phase_windows") or {}).get("run") or []
        if not (rid and wins):
            continue
        spans = []
        for w in wins:
            s = _parse_dt(w["start"])
            e = _parse_dt(w["end"])
            spans.append((int((s - horizon_start).total_seconds() // 60),
                          int((e - horizon_start).total_seconds() // 60)))
        spans.sort()
        placements[oid] = (rid, spans[0][0], spans[-1][1])
        if len(spans) > 1:
            chunks[oid] = spans

    ops_by_id = {o["id"]: o for o in ops}
    wo_of_op = _work_orders_by_op(reader, ops, wps, fuls, demands)
    return _HeldWorld(
        ops=ops, wps=wps, resources=resources, fuls=fuls, demands=demands,
        cost_model=cost_model, var_map=var_map, model=model,
        horizon_start=horizon_start, horizon_end=horizon_end,
        reader=reader, placements=placements,
        chunks=chunks, ops_by_id=ops_by_id, wo_of_op=wo_of_op,
        build_args=build_args, edges=edges)


def load_held_world(out_dir: Path | str, snapshot_id: str, *,
                    runs_subdir: str = "runs",
                    restrict_op_ids: Optional[set] = None) -> _HeldWorld:
    """Load the incumbent ONCE so several prices can share it.

    Session 4B.30: the later-move route prices a planner's target and, when the
    world refuses it, prices the RECOMPUTED alternative it offers. Two prices,
    and on the demo board the model build is ~6.5 s of the ~7 s each one costs
    (4B.23 §5a.92 measured it) — so building twice would make the offer cost
    more than the answer. ``price_local_move`` has always accepted a ``world``;
    this is the public door to one."""
    return _load_held_world(Path(out_dir), snapshot_id, runs_subdir,
                            restrict_op_ids)


def demands_of_operation(world: _HeldWorld, op_id: str) -> list[str]:
    """The demand refs an operation's completion is judged against — the same
    fulfillment walk the ledger uses, so a due-date verdict and a tardiness
    figure are about the same demands."""
    wp = (world.ops_by_id.get(op_id) or {}).get("workpackage_ref", "")
    return [f.get("demand_ref") for f in world.fuls
            if f.get("workpackage_ref") == wp and f.get("demand_ref")]


def _subject_outcomes(world: _HeldWorld, demand_refs: list[str],
                      before, after) -> list[dict]:
    """One row per named demand: the declared due date, the completion before
    and after, the lateness both sides, and R-PD1 clause (4)'s split.

    THE FLOOR CANNOT MOVE AND THE ROW SAYS SO by carrying it once, not twice: it
    is ``max(0, t0 − due)`` priced, a fact about when the plan opened against
    when the order was due, and no placement of any operation can change either.
    Reporting it as a before/after pair would invite a reader to subtract two
    equal numbers and conclude something was decided."""
    from mre.modules.sandbox import _order_name_resolver

    wo_of = _order_name_resolver(world.reader.read_identity_map())
    dem_by_id = {d["id"]: d for d in world.demands}
    b_by = {s.get("demand_ref"): s for s in (before.service_outcomes or [])}
    a_by = {s.get("demand_ref"): s for s in (after.service_outcomes or [])}
    out: list[dict] = []
    for dem in demand_refs:
        b, a = b_by.get(dem), a_by.get(dem)
        if a is None:
            continue
        d = dem_by_id.get(dem, {})
        floor_min = int(a.get("tardiness_floor_minutes") or 0)
        out.append({
            "demand_ref": dem,
            "work_order": wo_of(dem),
            "due": d.get("due"),
            "completion_before": (b or {}).get("projected_completion"),
            "completion_after": a.get("projected_completion"),
            "lateness_before_min": int((b or {}).get("lateness_minutes") or 0),
            "lateness_after_min": int(a.get("lateness_minutes") or 0),
            "tardiness_before": round(float((b or {}).get("tardiness_cost")
                                            or 0.0), 2),
            "tardiness_after": round(float(a.get("tardiness_cost") or 0.0), 2),
            # UNCHANGEABLE BY ANY MOVE (R-PD1 clause 4): already accrued when
            # the plan opened. Stated once, on both sides of nothing.
            "tardiness_floor_min": floor_min,
            "tardiness_floor_cost": round(
                float(a.get("tardiness_floor_cost") or 0.0), 2),
        })
    return out


def _work_orders_by_op(reader, ops, wps, fuls, demands) -> dict:
    """op_id -> [work-order external names], via the identity map — the same
    source the schedule assembler uses. Best-effort: a refusal that cannot name
    the blocking ORDER still names the blocking OPERATION and the constraint."""
    try:
        from mre.modules.schedule_assembler import _ORDER_REF_TYPES, _external_name
        idmap = reader.read_identity_map()
        dem_of_wp: dict = {}
        for f in fuls:
            wp = f.get("workpackage_ref")
            dem = f.get("demand_ref")
            if wp and dem:
                dem_of_wp.setdefault(wp, []).append(dem)
        out: dict = {}
        for o in ops:
            names = []
            for dem in dem_of_wp.get(o.get("workpackage_ref", ""), []):
                try:
                    n = _external_name(idmap, dem, _ORDER_REF_TYPES)
                except Exception:  # noqa: BLE001
                    n = None
                if n:
                    names.append(n)
            out[o["id"]] = names
        return out
    except Exception:  # noqa: BLE001
        return {}


def _solve_values(world: _HeldWorld, placements: dict, chunks: dict):
    """A :class:`SolveValues` carrying exactly these placements. Workpackage
    completions are RECOMPUTED from the operation ends, because tardiness — and
    therefore most of the ledger — is derived from them (the 4B.6c ``_rebuild``
    lesson: shift an op without moving its workpackage end and the ledger lies
    in the planner's favour)."""
    from mre.modules.solver_builder import SolveValues

    starts = {oid: p[1] for oid, p in placements.items()}
    ends = {oid: p[2] for oid, p in placements.items()}
    res = {oid: p[0] for oid, p in placements.items()}
    wp_end: dict = {}
    for oid, e in ends.items():
        wp = (world.ops_by_id.get(oid) or {}).get("workpackage_ref", "")
        if wp:
            wp_end[wp] = max(wp_end.get(wp, 0), e)
    return SolveValues(
        op_start_minutes=starts, op_end_minutes=ends, op_resource=res,
        wp_end_minutes=wp_end, tardiness_minutes={},
        horizon_start=world.horizon_start,
        op_chunk_windows={k: list(v) for k, v in chunks.items()},
    )


def _extract(world: _HeldWorld, sv, tag: str):
    from mre.modules.extractor import Extractor
    return Extractor().extract(
        solve_values=sv, snapshot_id=tag,
        operations=world.ops, workpackages=world.wps, resources=world.resources,
        fulfillments=world.fuls, demands=world.demands,
        cost_model=world.cost_model, reporter=None,
        cal_windows=world.var_map.cal_windows,
        op_eligible=world.var_map.op_eligible, snapshot_writer=None,
        is_scenario=True, overtime_windows=world.var_map.overtime_windows)


# ---------------------------------------------------------------------------
# The structural checks — a refusal that NAMES its constraint
# ---------------------------------------------------------------------------

def relaxed_refusal(var_map, pin_op: str, rid: str, start_min: int,
                    end_min: int, chunked: bool = False) -> Optional[LocalRefusal]:
    """Why a pin is refused WHATEVER ELSE MOVES — the subset of
    :func:`structural_refusal` that survives a fully relaxed world.

    BEAT ONE relaxes everything but the dragged bar (docs/04 R-T2): every other
    operation is free to move out of the way. So the only constraints a beat-one
    INFEASIBLE can be attributed to are the ones no rearrangement can lift —
    **eligibility** (this machine cannot run this operation) and the
    **calendar** (it is shut then, or it does not stay open long enough).

    Occupancy, precedence and the frozen front are DELIBERATELY not tested here,
    even though the held-world checker tests them and they are the commonest
    real blockers. Under beat one's relaxation each of them is a fact about the
    incumbent arrangement, not about the plant: reporting "that time is already
    taken" for a solve that was free to move the occupant would be exactly the
    over-claim `holds_others` exists to prevent (4B.24), stated by a checker
    that never even asked. Where none of the surviving families explains the
    refusal, this returns None and the caller says so rather than inventing one.

    Pure arithmetic over the model's own maps — no solve, no world load, so it
    is free to call on beat one's already-built ``var_map``.
    """
    eligible = (var_map.op_eligible or {}).get(pin_op)
    if eligible is not None and rid not in eligible:
        return LocalRefusal(
            family=FAMILY_ELIGIBILITY, resource_id=rid,
            sentence="this operation cannot run on that machine")

    windows = (var_map.cal_windows or {}).get(rid) or []
    if not any(ws <= start_min and end_min <= we for ws, we in windows):
        # A chunked op may span closures; a whole one may not. Same two facts,
        # same two sentences as the held-world checker — ONE vocabulary.
        if not chunked:
            open_at = next((w for w in windows if w[0] <= start_min < w[1]), None)
            if open_at is None:
                return LocalRefusal(
                    family=FAMILY_CALENDAR, resource_id=rid,
                    sentence="the machine is not open at that time")
            return LocalRefusal(
                family=FAMILY_CALENDAR, resource_id=rid,
                sentence=f"the machine closes before this would finish — it "
                         f"needs {end_min - start_min} working minutes and "
                         f"{open_at[1] - start_min} are left in that window")
    return None


def structural_refusal(world: _HeldWorld, pin_op: str, rid: str,
                       start_min: int, end_min: int,
                       frozen_end_min: Optional[int] = None,
                       standing_ops: Optional[set] = None
                       ) -> Optional[LocalRefusal]:
    """Why the HELD world cannot take this pin — in docs/05 family terms.

    Pure arithmetic over the incumbent's own placements and the model's own
    calendar/eligibility maps. It runs BEFORE CP-SAT so a refusal can be
    explained; CP-SAT then confirms. Order matters only for which reason is
    reported first, and it is deliberate: eligibility (is this even the right
    kind of machine), then the calendar (is the machine open), then occupancy
    (is something already there), then precedence, then the frozen boundary —
    coarsest fact first, because that is the one a planner can act on soonest."""
    vm = world.var_map

    eligible = (vm.op_eligible or {}).get(pin_op)
    if eligible is not None and rid not in eligible:
        return LocalRefusal(
            family=FAMILY_ELIGIBILITY, resource_id=rid,
            sentence="this operation cannot run on that machine")

    windows = (vm.cal_windows or {}).get(rid) or []
    if not any(ws <= start_min and end_min <= we for ws, we in windows):
        # A chunked op is allowed to span closures; a whole one is not.
        if pin_op not in world.chunks:
            # Two different facts, and a planner acts on them differently: the
            # machine is SHUT then, or it is open but not for long enough. The
            # 4B.20 discipline — a surface reporting a quantity names which one.
            open_at = next((w for w in windows
                            if w[0] <= start_min < w[1]), None)
            if open_at is None:
                return LocalRefusal(
                    family=FAMILY_CALENDAR, resource_id=rid,
                    at=_iso(world, start_min),
                    sentence="the machine is not open at that time")
            return LocalRefusal(
                family=FAMILY_CALENDAR, resource_id=rid,
                at=_iso(world, open_at[1]),
                sentence=f"the machine closes before this would finish — it "
                         f"needs {end_min - start_min} working minutes and "
                         f"{open_at[1] - start_min} are left in that window")

    for oid, (o_rid, o_s, o_e) in world.placements.items():
        if oid == pin_op or o_rid != rid:
            continue
        if o_s < end_min - _OVERLAP_TOLERANCE_MIN and start_min < o_e - _OVERLAP_TOLERANCE_MIN:
            return LocalRefusal(
                family=FAMILY_RESOURCE, other_op_ref=oid,
                other_work_orders=list(world.wo_of_op.get(oid) or []),
                resource_id=rid, at=_iso(world, o_s), holds_others=True,
                sentence="that time is already taken on this machine")

    for pred, lag in _predecessors(world, pin_op):
        p = world.placements.get(pred)
        if p and p[2] + lag > start_min:
            return LocalRefusal(
                family=FAMILY_PRECEDENCE, other_op_ref=pred,
                other_work_orders=list(world.wo_of_op.get(pred) or []),
                at=_iso(world, p[2] + lag), holds_others=True,
                sentence="an earlier step in this order has not finished by then")

    for succ, lag in _successors(world, pin_op):
        s = world.placements.get(succ)
        if s and end_min + lag > s[1]:
            return LocalRefusal(
                family=FAMILY_PRECEDENCE, other_op_ref=succ,
                other_work_orders=list(world.wo_of_op.get(succ) or []),
                at=_iso(world, s[1]), holds_others=True,
                sentence="the next step in this order is already scheduled "
                         "before this one would finish")

    if frozen_end_min is not None and start_min < frozen_end_min:
        return LocalRefusal(
            family=FAMILY_FROZEN, at=_iso(world, frozen_end_min),
            holds_others=True,
            sentence="that time is inside the committed front of the plan")
    return None


def _iso(world: _HeldWorld, minute: int) -> str:
    return (world.horizon_start + timedelta(minutes=minute)).isoformat()


def _edge_map(world: _HeldWorld) -> dict:
    """(pred_op_id, succ_op_id) -> min_lag minutes, resolved exactly as the
    SolverBuilder does (template edge keyed by spec_ref, per workpackage — the
    4B.6c ``min_lag_map`` transcription, kept in step with it deliberately)."""
    cached = getattr(world, "_edge_cache", None)
    if cached is not None:
        return cached
    from mre.modules.solver_builder import _parse_td, _td_to_minutes
    by_wp_spec = {(o.get("workpackage_ref"), o.get("spec_ref")): o["id"]
                  for o in world.ops}
    wp_ids = {o.get("workpackage_ref") for o in world.ops}
    out: dict = {}
    for e in world.edges:
        lag = _td_to_minutes(_parse_td(e.get("min_lag", "PT0S")))
        for wp in wp_ids:
            p = by_wp_spec.get((wp, e.get("predecessor")))
            s = by_wp_spec.get((wp, e.get("successor")))
            if p and s:
                out[(p, s)] = lag
    world._edge_cache = out
    return out


def _predecessors(world: _HeldWorld, op_id: str):
    return [(p, lag) for (p, s), lag in _edge_map(world).items() if s == op_id]


def _successors(world: _HeldWorld, op_id: str):
    return [(s, lag) for (p, s), lag in _edge_map(world).items() if p == op_id]


def validate_held_world(world: _HeldWorld, placements: dict,
                        time_limit_s: float = 60.0) -> dict:
    """Pin EVERY placement into a freshly built model and ask CP-SAT whether the
    result is a legal schedule (the 4B.6c method, docs/04 2026-07-27: the model's
    own verdict, not this module's opinion of itself).

    The objective is cleared: this asks a feasibility question, not a cost one,
    and a cleared objective is what makes it fast — the search has nothing to
    prove beyond consistency, and every variable it could search over is already
    pinned. Deterministic by construction (workers=1, fixed seed, and a fully
    constrained model), with the wall limit as a safety ceiling only."""
    from mre.modules.solver_builder import SolverBuilder
    from mre.modules import standing_pins as sp
    from ortools.sat.python import cp_model as cp

    t0 = time.monotonic()
    rebuilt = False
    if world.model_consumed:
        # A second validation against the same world: the first one's pins are
        # still in that model, so pinning into it again would validate a schedule
        # nobody asked about. Pay for a fresh build rather than answer wrongly.
        rebuilt = True
        model, var_map = SolverBuilder(
            reference_date=world.build_args[0]).build(*world.build_args[1:])
    else:
        model, var_map = world.model, world.var_map
        world.model_consumed = True
    unpinnable = []
    for oid, (rid, s, _e) in placements.items():
        try:
            sp.apply_pin(model, var_map, oid, rid, int(s))
        except sp.PinUnsatisfiable as exc:
            unpinnable.append({"operation_ref": oid, "reason": exc.reason})
    model.clear_objective()
    solver = cp.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    solver.parameters.max_time_in_seconds = time_limit_s
    st = solver.Solve(model)
    status = {cp.OPTIMAL: "OPTIMAL", cp.FEASIBLE: "FEASIBLE",
              cp.INFEASIBLE: "INFEASIBLE"}.get(st, "UNKNOWN")
    return {"method": "cp-sat-pin-all", "status": status,
            "unpinnable": unpinnable, "rebuilt_model": rebuilt,
            "wall_time_s": round(time.monotonic() - t0, 3)}


# ---------------------------------------------------------------------------
# The entry point
# ---------------------------------------------------------------------------

def price_local_move(
    out_dir: Path | str,
    snapshot_id: str,
    pin_op_id: Optional[str] = None,
    pin_resource_id: Optional[str] = None,
    pin_start_iso: Optional[str] = None,
    *,
    runs_subdir: str = "runs",
    restrict_op_ids: Optional[set] = None,
    standing_pins: Optional[list[dict]] = None,
    validate: bool = True,
    world: Optional[_HeldWorld] = None,
    subject_demand_refs: Optional[list[str]] = None,
) -> LocalPrice:
    """Price ONE move with every other placement held exactly where it is.

    Omitting the pin fields prices the FIRST incumbent operation at its own
    placement — a zero-distance move, and therefore the latency FLOOR the CI
    regression uses (:func:`mre.modules.sandbox.sandbox_pin_resolve` has always
    defaulted the same way; the two must agree or the same request would mean
    different gestures on the two paths).

    ``world`` lets a caller amortise the (expensive) model build across several
    prices of the same board; leave it None and one is loaded."""
    from mre.modules.sandbox import _LEDGER_LINES, _affected_orders

    t_all = time.monotonic()
    pin = {"operation_ref": pin_op_id, "resource_id": pin_resource_id,
           "start": pin_start_iso}
    t_build = 0.0
    if world is None:
        t0 = time.monotonic()
        try:
            world = _load_held_world(Path(out_dir), snapshot_id, runs_subdir,
                                     restrict_op_ids)
        except Exception as exc:  # noqa: BLE001
            return LocalPrice(priced=False, pin=pin,
                              error=f"could not load the plan to price against: {exc}")
        t_build = round(time.monotonic() - t0, 3)

    t_price = time.monotonic()
    if pin_op_id is None:
        pin_op_id = next(iter(world.placements), None)
        if pin_op_id is None:
            return LocalPrice(priced=False, pin=pin, build_wall_time_s=t_build,
                              error="this plan has no placements to price against")
    old = world.placements.get(pin_op_id)
    if old is None:
        return LocalPrice(priced=False, pin=pin, build_wall_time_s=t_build,
                          error="that operation has no placement in this plan")
    if pin_resource_id is None:
        pin_resource_id = old[0]
    if pin_start_iso is None:
        pin_start_iso = _iso(world, old[1])
    pin = {"operation_ref": pin_op_id, "resource_id": pin_resource_id,
           "start": pin_start_iso}
    start_dt = _parse_dt(pin_start_iso)
    if start_dt is None:
        return LocalPrice(priced=False, pin=pin, build_wall_time_s=t_build,
                          error="the drop carried no time")
    start_min = int((start_dt - world.horizon_start).total_seconds() // 60)
    duration = old[2] - old[1]
    end_min = start_min + duration
    shift = start_min - old[1]

    # A chunked operation's pauses are calendar closures the solver placed; a
    # local shift cannot re-derive them, so this module declines rather than
    # inventing a chunk pattern (named, not silent — 4B.24 close-out §7).
    if pin_op_id in world.chunks:
        return LocalPrice(
            priced=False, pin=pin, build_wall_time_s=t_build,
            error="this operation runs in chunks around calendar closures; "
                  "moving it needs the full re-solve, not a local price")

    new_placements = dict(world.placements)
    new_placements[pin_op_id] = (pin_resource_id, start_min, end_min)

    frozen_end = _frozen_end_min(world, standing_pins, pin_op_id)
    refusal = structural_refusal(world, pin_op_id, pin_resource_id,
                                 start_min, end_min, frozen_end_min=frozen_end)
    if refusal is not None:
        return LocalPrice(priced=False, pin=pin, refusal=refusal.summary(),
                          build_wall_time_s=t_build,
                          price_wall_time_s=round(time.monotonic() - t_price, 3),
                          wall_time_s=round(time.monotonic() - t_all, 3))

    try:
        before = _extract(world, _solve_values(world, world.placements,
                                               world.chunks), "local-before")
        after = _extract(world, _solve_values(world, new_placements,
                                              world.chunks), "local-after")
    except Exception as exc:  # noqa: BLE001
        return LocalPrice(priced=False, pin=pin, build_wall_time_s=t_build,
                          error=f"the ledger could not be recomputed: {exc}")

    led_b = before.cost_ledger or {}
    led_a = after.cost_ledger or {}
    tb = led_b.get("total_cost")
    ta = led_a.get("total_cost")
    if tb is None or ta is None:
        return LocalPrice(priced=False, pin=pin, build_wall_time_s=t_build,
                          error="the recomputed ledger carried no total")
    delta = round(float(ta) - float(tb), 2)

    named_sum = 0.0
    cost_lines: list[dict] = []
    for label, key in _LEDGER_LINES:
        d = round(float(led_a.get(key, 0.0)) - float(led_b.get(key, 0.0)), 2)
        named_sum += d
        cost_lines.append({"line": label, "delta": d})
    cost_lines.append({"line": "other placement changes",
                       "delta": round(delta - named_sum, 2)})

    affected, lateness_delta = _affected_orders(
        world.reader, after.service_outcomes,
        base_svc=before.service_outcomes, with_total=True)
    subject_outcomes = (_subject_outcomes(world, subject_demand_refs,
                                          before, after)
                        if subject_demand_refs else [])

    persisted = _persisted_total(world.reader)
    price_wall = round(time.monotonic() - t_price, 3)

    validation = {"method": "skipped", "status": None}
    if validate:
        validation = validate_held_world(world, new_placements)
        if validation["status"] == "INFEASIBLE":
            # The structural checks found nothing and the model refuses anyway.
            # Say exactly that: the refusal is real, and we cannot name which
            # constraint — inventing one would be worse than admitting it.
            return LocalPrice(
                priced=False, pin=pin, validation=validation,
                build_wall_time_s=t_build, price_wall_time_s=price_wall,
                wall_time_s=round(time.monotonic() - t_all, 3),
                refusal=LocalRefusal(
                    family=FAMILY_MODEL, resource_id=pin_resource_id,
                    holds_others=True,
                    sentence="the scheduler refuses this placement with every "
                             "other job held where it is, and I can't name which "
                             "rule stops it").summary())
        if validation["status"] == "UNKNOWN":
            return LocalPrice(
                priced=False, pin=pin, validation=validation,
                build_wall_time_s=t_build, price_wall_time_s=price_wall,
                wall_time_s=round(time.monotonic() - t_all, 3),
                error="I could not confirm this placement is legal with "
                      "everything else held in place")

    return LocalPrice(
        priced=True, pin=pin,
        cost_delta_abs=delta,
        cost_delta_pct=(round(delta / float(tb) * 100.0, 4) if tb else None),
        total_before=round(float(tb), 2), total_after=round(float(ta), 2),
        cost_lines=cost_lines, affected_orders=affected,
        lateness_delta_min=lateness_delta,
        moves=[{
            "operation_ref": pin_op_id,
            "from_resource": old[0], "to_resource": pin_resource_id,
            "from_start": _iso(world, old[1]), "to_start": _iso(world, start_min),
            "start_delta_min": shift,
            "resource_changed": old[0] != pin_resource_id,
            "pinned": True,
        }],
        persisted_total=persisted,
        agrees_with_persisted=(None if persisted is None
                               else abs(persisted - float(tb)) < 0.01),
        subject_outcomes=subject_outcomes,
        validation=validation,
        build_wall_time_s=t_build, price_wall_time_s=price_wall,
        wall_time_s=round(time.monotonic() - t_all, 3))


def _frozen_end_min(world: _HeldWorld,
                    standing_pins: Optional[list[dict]],
                    pin_op_id: Optional[str] = None) -> Optional[int]:
    """The last minute covered by a standing commitment. A drop before it lands
    in committed territory (R-F1) — and the pricer never quietly re-plans
    committed work, which is the whole reason standing pins exist.

    The op BEING DRAGGED is excluded, exactly as ``sandbox_pin_resolve`` excludes
    it from the standing pins it compiles: the new drop re-commits it, so
    measuring the boundary against its own current placement would let a bar be
    refused for standing where it already stands."""
    if not standing_pins:
        return None
    ends = []
    for p in standing_pins:
        oid = p.get("operation_ref")
        if oid == pin_op_id:
            continue
        held = world.placements.get(oid)
        if held:
            ends.append(held[2])
    return max(ends) if ends else None


def _persisted_total(reader) -> Optional[float]:
    try:
        schedules = list(reader.iter_entities("schedule"))
        if not schedules:
            return None
        return round(float((schedules[-1].get("summary_metrics") or {})
                           .get("total_cost", 0.0)), 2)
    except Exception:  # noqa: BLE001
        return None

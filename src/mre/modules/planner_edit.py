"""Accepted cockpit edits become real schedule versions (docs/07 Phase 3, CU1;
R-DP1/R-DP2/R-DP7).

When a planner drops a bar and ACCEPTS the Tier-2 verdict, the edit stops being
a sandbox scenario and becomes a NEW proposed schedule version — the base is
never mutated (R-DP2's "nothing mutates before accept" becomes "accept CREATES,
never overwrites"). This module does exactly that and nothing more:

  1. derive a child snapshot from the base (copy every planned entity — the M4
     workpackages/operations/fulfillments included — so the accepted version
     reproduces the base's planning EXACTLY, differing only by the pin);
  2. warm-start from the base schedule, PIN the dropped op at (machine + time as
     displayed, R-DP1), and re-solve its surroundings under the sandbox budget;
  3. extract canonical entities (Schedule/Assignment/ServiceOutcome) into the
     child snapshot — a real schedule, ``is_scenario=False``;
  4. record ONE ``planner_edit`` Decision (basis=observed — a human command;
     authority MANDATORY; payload = the pin, the priced delta, the moved-set).

The API accept worker registers the result as a ``proposed`` schedule whose
parent is the base; publish (proposed → published) is a separate act in the
registry that supersedes the base and invalidates its pools/alternatives.

Determinism: the re-solve is warm-started + pinned + deterministic, so an accept
reproduces the sandbox verdict the planner already saw rather than drifting.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Copied from the base snapshot when deriving the accepted-edit child snapshot:
# every planned entity EXCEPT the M7 outputs (Schedule/Assignment/ServiceOutcome),
# which the extractor writes fresh from the pinned re-solve. Copying the M4
# workpackages/operations/fulfillments (not just the M1 inputs the ScenarioRunner
# copies) means the accepted edit does NOT re-plan — it reproduces the base's
# exact planning and differs only by the pin.
_EDIT_COPY_TYPES = [
    "demand", "product", "resource", "resourcepool", "calendar", "constraint",
    "costmodel", "process", "operationspec", "precedenceedge",
    "workpackage", "operation", "fulfillment",
]


@dataclass
class PlannerEditResult:
    child_snapshot_id: str
    feasible: bool
    status: str
    objective: Optional[float]
    delta_abs: Optional[float]
    delta_pct: Optional[float]
    moved_count: int
    decision_record_id: Optional[str]
    wall_time_s: float
    message: str = ""
    moves: list[dict] = field(default_factory=list)
    pin: dict = field(default_factory=dict)
    # The DECOMPOSED dollar cost delta (production/setup/tardiness), so the
    # accepted card shows LEDGER dollars, never the scaled objective (exit-audit).
    cost_delta: dict = field(default_factory=dict)


def apply_planner_edit(
    out_dir: Path | str,
    base_snapshot_id: str,
    pin_op_id: str,
    pin_resource_id: str,
    pin_start_iso: str,
    authority: str,
    base_context: dict,
    budget_s: float = 15.0,
    runs_subdir: str = "runs",
    deterministic: bool = True,
) -> PlannerEditResult:
    """Materialize an accepted edit as a child snapshot + a ``planner_edit``
    Decision, under ``out_dir`` (a freshly minted run directory whose
    ``snapshots/`` already contains a copy of the base snapshot).

    Returns a :class:`PlannerEditResult`; the caller assembles the document from
    ``child_snapshot_id`` and registers it as a proposed schedule. Raises on an
    infeasible pin — an accept must never register an unsolvable version.
    """
    from mre.contracts.entities import EntityRef
    from mre.contracts.records import DecisionAlternative
    from mre.contracts.vocabularies import (
        DecisionBasis, DecisionType, DriverCode, ModuleCode, RecordTier, RunStatus,
    )
    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.extractor import Extractor
    from mre.modules.sandbox import _moved_set, _annotate_move_reasons
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import SolverBuilder, apply_solution_hints
    from mre.modules.solution_pool import (
        _incumbent_objective, _m5_horizon, _placements, _read_evidence,
    )
    from mre.reporter import Reporter

    if not authority:
        raise ValueError("a planner_edit requires an authority (who accepted it)")

    out_dir = Path(out_dir)
    store = SnapshotStore(out_dir / "snapshots")
    runs_dir = out_dir / runs_subdir
    runs_dir.mkdir(parents=True, exist_ok=True)

    # 1. Derive the child snapshot (copy every planned entity but the M7 outputs).
    edit_hash = _short_pin_hash(pin_op_id, pin_resource_id, pin_start_iso)
    child_snap_id = _edit_snapshot_id(base_snapshot_id, edit_hash)
    store.derive_scenario_snapshot(base_snapshot_id, child_snap_id, _EDIT_COPY_TYPES)

    # 2. Load base entities (base snapshot still intact — accept never mutates it).
    base_reader = store.load_snapshot(base_snapshot_id)
    demands = list(base_reader.iter_entities("demand"))
    fuls = list(base_reader.iter_entities("fulfillment"))
    wps = list(base_reader.iter_entities("workpackage"))
    ops = list(base_reader.iter_entities("operation"))
    edges = list(base_reader.iter_entities("precedenceedge"))
    resources = list(base_reader.iter_entities("resource"))
    pools = list(base_reader.iter_entities("resourcepool"))
    calendars = list(base_reader.iter_entities("calendar"))
    constraints = list(base_reader.iter_entities("constraint"))
    costmodels = list(base_reader.iter_entities("costmodel"))
    incumbent_assignments = list(base_reader.iter_entities("assignment"))
    cost_model = costmodels[0] if costmodels else {}

    reference_date = _parse_ref_date(base_context.get("reference_date"))
    # The horizon must match the base run's M5 horizon exactly, so the pinned
    # re-solve places against the same clock the incumbent did.
    evidence = _read_evidence(_base_runs_dir(base_context))
    horizon_start, horizon_end = _m5_horizon(evidence)
    incumbent_objective = _incumbent_objective(evidence)
    incumbent_placement = _placements(incumbent_assignments)
    flattened_cals = flatten_all_calendars(calendars, horizon_start, horizon_end)

    pin_start_dt = _parse_dt(pin_start_iso)
    if pin_start_dt is None:
        raise ValueError(f"cannot parse pin start {pin_start_iso!r}")
    pin_start_min = int((pin_start_dt - horizon_start).total_seconds() // 60)

    workers = 1 if deterministic else base_context.get("solver_workers")

    # 3. Build + warm-start + pin + solve (mirrors the sandbox re-solve, R-DP1).
    b_rep = Reporter.begin(
        module=ModuleCode.M5, purpose="planner-edit model build",
        config={"horizon_start": horizon_start.isoformat(),
                "horizon_end": horizon_end.isoformat(),
                "pin_op": pin_op_id, "pin_resource": pin_resource_id,
                "pin_start_min": pin_start_min},
        trigger="planner_edit", snapshot_id=child_snap_id, sink_dir=runs_dir,
    )
    model, var_map = SolverBuilder(reference_date=reference_date).build(
        wps + ops + edges, resources + pools, flattened_cals,
        fuls + demands, constraints, cost_model,
    )
    b_rep.end(RunStatus.SUCCESS)

    apply_solution_hints(model, var_map, incumbent_assignments)
    # R-DP1 (4.0 hotfix): the pin MUST bind on BOTH axes — machine AND time.
    # The machine literal exists ONLY for resources the op is eligible on; a
    # target outside that set has no literal. The prior code did
    # ``if lit is not None: model.add(lit == 1)`` and SILENTLY SKIPPED the
    # machine constraint when the literal was absent, so the re-solve honoured
    # only the time pin and legally relocated the op to a cheaper eligible
    # machine — right time, wrong machine, reported as a happy verdict. An accept
    # must NEVER place the op anywhere but where the planner dropped it, so an
    # un-pinnable target is a hard error (nothing accepted, the base stands) —
    # never a silent skip.
    if pin_op_id not in var_map.op_start:
        raise RuntimeError(
            f"planner edit: op {pin_op_id} has no schedulable start variable to "
            "pin — nothing accepted; the base version stands")
    model.add(var_map.op_start[pin_op_id] == pin_start_min)
    assign = var_map.op_assign.get(pin_op_id, {})
    lit = assign.get(pin_resource_id)
    if lit is None:
        raise RuntimeError(
            f"planner edit: op {pin_op_id} is not eligible on resource "
            f"{pin_resource_id} (eligible: {sorted(assign)}) — R-DP1 requires the "
            "pinned resource be honoured; nothing accepted, the base stands")
    model.add(lit == 1)

    r_rep = Reporter.begin(
        module=ModuleCode.M6, purpose="planner-edit re-solve",
        config={"time_limit": budget_s, "num_search_workers": workers,
                "random_seed": 0 if deterministic else base_context.get("solver_seed"),
                "pin_op": pin_op_id},
        trigger="planner_edit", snapshot_id=child_snap_id, sink_dir=runs_dir,
    )
    t0 = time.monotonic()
    solve_result = SolveRunner(
        time_limit_seconds=budget_s, num_search_workers=workers,
        random_seed=0 if deterministic else base_context.get("solver_seed"),
    ).solve(model, var_map, r_rep)
    wall = round(time.monotonic() - t0, 3)
    feasible = solve_result.status in ("OPTIMAL", "FEASIBLE")
    r_rep.end(RunStatus.SUCCESS if feasible else RunStatus.PARTIAL)

    if not feasible:
        raise RuntimeError(
            f"planner edit infeasible with the pin held (status={solve_result.status}) "
            "— nothing accepted; the base version stands")

    # R-DP1 post-condition (4.0 hotfix): the pinned op MUST have solved to the
    # pinned resource at the pinned start. The mandatory constraints above
    # guarantee it, but an accept is irreversible once registered — so verify the
    # solved placement (what extraction is about to write) BEFORE minting the
    # version. A mismatch means the pin did not bind and the accept aborts; it
    # must never register a version that renders the op somewhere the planner did
    # not drop it.
    # Compare in the SAME canonical minute grid the pin compiled to (int minutes
    # since horizon_start), never re-serialized datetimes — solve_values carry
    # integer minutes straight from solver.Value(), and pin_start_min is an int,
    # so there is no rounding/tz seam between the pin and the check (4.0c).
    solved_res = solve_result.solve_values.op_resource.get(pin_op_id)
    solved_start = solve_result.solve_values.op_start_minutes.get(pin_op_id)
    solved_start = int(solved_start) if solved_start is not None else None
    if solved_res != pin_resource_id or solved_start != pin_start_min:
        raise RuntimeError(
            f"planner edit: R-DP1 post-condition FAILED — pinned op {pin_op_id} "
            f"solved to resource {solved_res} @ {solved_start}min, not the pinned "
            f"{pin_resource_id} @ {pin_start_min}min; nothing accepted, the base "
            "version stands")

    delta_abs = delta_pct = None
    if incumbent_objective and solve_result.objective is not None:
        delta_abs = round(solve_result.objective - incumbent_objective, 4)
        if incumbent_objective > 0:
            delta_pct = round(delta_abs / incumbent_objective * 100.0, 4)

    moves = _moved_set(solve_result.solve_values, incumbent_placement,
                       horizon_start, pin_op_id)
    _annotate_move_reasons(moves, solve_result.solve_values, horizon_start, pin_op_id)

    # 4. Extract canonical entities into the child snapshot — a REAL schedule.
    e_rep = Reporter.begin(
        module=ModuleCode.M7, purpose="planner-edit schedule extraction",
        config={}, trigger="planner_edit",
        snapshot_id=child_snap_id, sink_dir=runs_dir,
    )
    m7_writer = store.extend_snapshot(child_snap_id)
    extract_result = Extractor().extract(
        solve_values=solve_result.solve_values, snapshot_id=child_snap_id,
        operations=ops, workpackages=wps, resources=resources,
        fulfillments=fuls, demands=demands, cost_model=cost_model,
        reporter=e_rep, cal_windows=var_map.cal_windows,
        op_eligible=var_map.op_eligible, snapshot_writer=m7_writer,
        is_scenario=False, overtime_windows=var_map.overtime_windows,
    )
    m7_writer.finalize()
    e_rep.end(RunStatus.SUCCESS)

    # The cost delta, DECOMPOSED (production Δ + setup Δ + tardiness Δ) from the
    # ledgers — the answer to "why does this move cost N" (CU2). Recorded on the
    # Decision so it is self-contained evidence, single-run-scoped, decomposing
    # exactly (docs/02 §4.4). Base ledger from the base schedule's summary; new
    # from the fresh extraction.
    cost_delta = _cost_delta(base_reader, extract_result)

    # 5. Record the planner_edit Decision (basis=observed; authority mandatory).
    d_rep = Reporter.begin(
        module=ModuleCode.M4, purpose="planner-edit accept",
        config={"pin_op": pin_op_id, "pin_resource": pin_resource_id,
                "authority": authority},
        trigger="planner_edit", snapshot_id=child_snap_id, sink_dir=runs_dir,
    )
    chosen = {
        "pin": {"operation_ref": pin_op_id, "resource_id": pin_resource_id,
                "start": pin_start_dt.isoformat()},
        "delta_abs": delta_abs, "delta_pct": delta_pct,
        "moved_count": len(moves),
        "verdict": "OPTIMAL" if solve_result.status == "OPTIMAL" else solve_result.status,
        # the decomposed cost delta (dollars) + the moved-set with its "why"
        # clauses — the self-contained evidence CU2's edit-question domain reads.
        "cost_delta": cost_delta,
        "moves": moves,
    }
    old_res, old_start = incumbent_placement.get(pin_op_id, (None, None))
    alternatives = [DecisionAlternative(
        option="keep the incumbent placement",
        consequence=("the base schedule stands unchanged (0 cost delta)"
                     if old_res else "no prior placement recorded"),
    )]
    subjects = [EntityRef(entity_type="operation", entity_id=pin_op_id),
                EntityRef(entity_type="resource", entity_id=pin_resource_id)]
    driver = (DriverCode.COST_TRADEOFF if delta_abs and delta_abs > 0
              else DriverCode.NO_ALTERNATIVE)
    decision = d_rep.record_decision(
        decision_type=DecisionType.PLANNER_EDIT,
        subjects=subjects, chosen=chosen, alternatives=alternatives,
        driver=driver, basis=DecisionBasis.OBSERVED,
        tier=RecordTier.HEADLINE, authority=authority,
        message=(f"Planner edit: pinned op {pin_op_id[:8]} to "
                 f"{pin_resource_id[:8]} @ {pin_start_dt.isoformat()}"
                 + (f" ({'+' if (delta_abs or 0) >= 0 else '−'}${abs(delta_abs):,.0f})"
                    if delta_abs is not None else "")),
    )
    d_rep.end(RunStatus.SUCCESS)

    return PlannerEditResult(
        child_snapshot_id=child_snap_id, feasible=True,
        status=solve_result.status, objective=solve_result.objective,
        delta_abs=delta_abs, delta_pct=delta_pct, moved_count=len(moves),
        decision_record_id=decision.record_id, wall_time_s=wall,
        message="accepted", moves=moves, cost_delta=cost_delta,
        pin={"operation_ref": pin_op_id, "resource_id": pin_resource_id,
             "start": pin_start_dt.isoformat()},
    )


def _cost_delta(base_reader, extract_result) -> dict:
    """Decompose the cost delta (new − base) into production / setup / tardiness
    dollars, which sum to the total delta (docs/02 §4.4 decomposability). Base
    ledger from the base schedule's summary_metrics; new ledger from the fresh
    extraction's cost_ledger."""
    schedules = list(base_reader.iter_entities("schedule"))
    base_sm = schedules[-1].get("summary_metrics", {}) if schedules else {}
    new = getattr(extract_result, "cost_ledger", {}) or {}
    base_prod = float(base_sm.get("production_cost", 0.0))
    base_setup = float(base_sm.get("setup_cost", 0.0))
    base_tard = float(base_sm.get("tardiness_cost", 0.0))
    base_total = float(base_sm.get("total_cost", base_prod + base_setup + base_tard))
    new_prod = float(new.get("production_cost", 0.0))
    new_setup = float(new.get("setup_cost", 0.0))
    new_tard = float(new.get("tardiness_cost", 0.0))
    new_total = float(new.get("total_cost", new_prod + new_setup + new_tard))
    return {
        "total_before": round(base_total, 2), "total_after": round(new_total, 2),
        "total_delta": round(new_total - base_total, 2),
        "production_delta": round(new_prod - base_prod, 2),
        "setup_delta": round(new_setup - base_setup, 2),
        "tardiness_delta": round(new_tard - base_tard, 2),
    }


def _short_pin_hash(*parts: str) -> str:
    import hashlib
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:8]


# A child snapshot id is a directory NAME on disk (snapshots/<id>/entities_*.jsonl).
# The naive scheme appends "--edit-<hash>" to the parent id on every accept, so a
# chain of edits grows the id — and thus the on-disk path — without bound. Past
# ~8 chained edits the path crosses the Windows MAX_PATH limit (260) and the
# derive/copy fails with FileNotFoundError [WinError 3]; pre-4.0c that aborted the
# accept SILENTLY (the cockpit returned the bar home with no error). Bounding the
# id keeps every base a valid short directory name forever (each base is either a
# root or an already-bounded child), so no chain ever reaches that depth. The
# lineage itself is not lost — it lives in the registry's parent_schedule_id chain.
_MAX_EDIT_SNAP_ID_LEN = 90


def _edit_snapshot_id(base_snapshot_id: str, edit_hash: str) -> str:
    """The child snapshot id for an accepted edit, bounded in length so chained
    edits never grow the snapshot-directory path past a filesystem limit (4.0c).

    Shallow chains keep the readable ``<base>--edit-<hash>`` lineage. Once that
    would exceed the cap, the ancestry collapses into a stable digest of the
    (real, on-disk) parent id — preserving the visible root and the fresh edit
    hash, and staying collision-free because the digest is over the exact parent
    id we derive from."""
    import hashlib
    import re
    candidate = f"{base_snapshot_id}--edit-{edit_hash}"
    if len(candidate) <= _MAX_EDIT_SNAP_ID_LEN:
        return candidate
    # The pure root — everything before the FIRST edit/chain marker — so a second
    # collapse does not accumulate "--chain-" segments (the id stays fixed-width
    # however deep the chain goes). The digest is over the whole parent id, so it
    # still uniquely fingerprints the exact lineage we derive from.
    root = re.split(r"--edit-|--chain-", base_snapshot_id, maxsplit=1)[0]
    lineage = hashlib.sha256(base_snapshot_id.encode()).hexdigest()[:12]
    return f"{root}--chain-{lineage}--edit-{edit_hash}"


def _base_runs_dir(base_context: dict) -> Path:
    """The base run's ``runs/`` directory, carried in base_context so the M5
    horizon + incumbent objective read from the SAME evidence the base solved
    against (not the empty new-run evidence)."""
    return Path(base_context["base_runs_dir"])


def _parse_dt(raw) -> Optional[datetime]:
    if raw is None or raw == "":
        return None
    dt = raw if isinstance(raw, datetime) else datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _parse_ref_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw or raw == "now":
        return None
    dt = datetime.fromisoformat(raw)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

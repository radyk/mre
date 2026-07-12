"""Forced-alternative service (docs/07 Phase 3, R-T1a/b): the TRUE price of a
road not taken.

The solution pool (``solution_pool.py``) surfaces the CHEAP alternatives —
near-optimal placements the optimum could just as well have chosen. But under
economically realistic DISTINCT rates the near-optimal pool converges on
machine placement, so pool-only ghosts degrade precisely where machine choice
matters most (the 3.1 multi_route finding). The forced-alternative service
fills that gap: for a selected operation, a targeted re-solve carrying a
"not on the incumbent machine" cut (``add_forced_alternative_cut``),
warm-started from the incumbent under a short time limit, yields the true best
cost of moving THAT op off its machine — or proves the move infeasible this
horizon (R-T1a: "not feasible this horizon" is a renderable answer, stored as
first-class information).

Each result is a pool-member-class document (``annotations.pool`` with
``source="forced_alternative"``) — same registry tables, same
never-in-schedule-listings exclusion, same supersede invalidation as the pool.
Infeasible forced solves carry a verdict and no document.

Selection heuristic v1 (``select_target_ops``, records itself in the docs/04
amendment; it WILL evolve): the at-risk demands — late first, then the tightest
by slack — and their multi-eligible operations (only a multi-eligible op can be
moved off its machine at all). A budget caps the count (each target is a full
warm-started re-solve; R-T1b names the solve-count multiplier honestly).

Isolation + laziness posture is identical to the pool: writes only under
``out_dir/alternatives/``; leaves the base snapshot untouched (in-memory
extraction, no snapshot writer, no reporter Decisions); registry indexing is
the caller's job (this module stays registry-free).
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from mre.modules.solution_pool import (
    _incumbent_objective,
    _m5_horizon,
    _parse_dt,
    _placements,
    _read_evidence,
)

DEFAULT_MEMBER_TIME_LIMIT_S = 10.0
DEFAULT_SEED = 1234
DEFAULT_BUDGET = 4          # max targeted re-solves per build (R-T1b cost cap)


@dataclass
class ForcedAlternative:
    member_index: int
    target_operation_ref: str
    forbidden_resource_ref: str
    status: str                            # FEASIBLE | OPTIMAL | INFEASIBLE | UNKNOWN
    verdict: str                           # "priced" | "infeasible_this_horizon" | "no_solution"
    objective: Optional[float] = None
    objective_delta_pct: Optional[float] = None
    alternative_resource_ref: Optional[str] = None
    wall_time_s: float = 0.0
    document_path: Optional[str] = None


@dataclass
class ForcedAlternativeResult:
    pool_id: str
    base_schedule_id: str
    snapshot_id: str
    status: str                            # ready | empty
    members: list[ForcedAlternative] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    wall_time_s: float = 0.0
    summary_path: Optional[str] = None

    def summary(self) -> dict:
        return asdict(self)

    def priced_cross_machine(self) -> list[ForcedAlternative]:
        """Feasible forced alternatives that actually crossed machines and
        carry a price — the Tier-1 priced-ghost payload."""
        return [m for m in self.members
                if m.verdict == "priced" and m.alternative_resource_ref
                and m.alternative_resource_ref != m.forbidden_resource_ref
                and m.objective_delta_pct is not None]


def _eligible_refs(op: dict) -> list[str]:
    """The explicit eligible set of an operation instance (multi_route uses
    explicit_set). Empty for a single-requirement capability op (resolution
    needs the resource table — v1 selection only needs the count for
    explicit_set data)."""
    reqs = op.get("resource_requirements") or []
    if not reqs:
        return []
    return list(reqs[0].get("resource_refs") or [])


def select_target_ops(
    *,
    operations: list[dict],
    fulfillments: list[dict],
    demands: list[dict],
    service_outcomes: list[dict],
    incumbent_placement: dict[str, tuple],
    budget: int = DEFAULT_BUDGET,
) -> list[str]:
    """Heuristic v1 (R-T1b): the at-risk demands' multi-eligible ops.

    Rank demands by risk — late first (positive lateness, largest first), then
    the tightest by slack (due − projected_completion) — walk them in that
    order, and collect the multi-eligible operations of each demand's
    workpackage until the budget is filled. Only multi-eligible SCHEDULED ops
    qualify (a forced-off-machine cut can only move an op with an alternative).
    """
    demand_by_id = {d["id"]: d for d in demands}
    svc_by_demand = {s.get("demand_ref"): s for s in service_outcomes}

    def _risk(demand_id: str) -> tuple:
        svc = svc_by_demand.get(demand_id, {})
        lateness = svc.get("lateness_minutes")
        if lateness is None:
            from mre.modules.scenario import _parse_duration_minutes as _m
            lateness = _m(svc.get("lateness")) or 0.0
        due = _parse_dt(demand_by_id.get(demand_id, {}).get("due")) if demand_by_id.get(demand_id, {}).get("due") else None
        proj = svc.get("projected_completion")
        proj_dt = _parse_dt(proj) if proj else None
        slack_min = ((due - proj_dt).total_seconds() / 60.0
                     if due and proj_dt else float("inf"))
        # sort key: late (lateness>0) first by -lateness, then least slack
        return (0 if lateness > 0 else 1, -float(lateness), slack_min)

    ranked = sorted((s.get("demand_ref") for s in service_outcomes if s.get("demand_ref")),
                    key=_risk)

    ops_by_wp: dict[str, list[dict]] = {}
    for op in operations:
        ops_by_wp.setdefault(op.get("workpackage_ref", ""), []).append(op)
    wp_by_demand: dict[str, list[str]] = {}
    for f in fulfillments:
        wp_by_demand.setdefault(f.get("demand_ref", ""), []).append(f.get("workpackage_ref", ""))

    picked: list[str] = []
    seen: set[str] = set()
    for demand_id in ranked:
        for wp_id in wp_by_demand.get(demand_id, []):
            for op in ops_by_wp.get(wp_id, []):
                oid = op["id"]
                if oid in seen or oid not in incumbent_placement:
                    continue
                if len(_eligible_refs(op)) > 1:      # movable off its machine
                    seen.add(oid)
                    picked.append(oid)
                    if len(picked) >= budget:
                        return picked
    return picked


def build_forced_alternatives(
    out_dir: Path | str,
    snapshot_id: str,
    base_schedule_id: str,
    run_id: str,
    target_op_ids: Optional[list[str]] = None,
    budget: int = DEFAULT_BUDGET,
    member_time_limit_s: float = DEFAULT_MEMBER_TIME_LIMIT_S,
    seed: int = DEFAULT_SEED,
    runs_subdir: str = "runs",
    pool_id: Optional[str] = None,
) -> ForcedAlternativeResult:
    """Build forced-alternative ghosts for a solved run.

    When ``target_op_ids`` is None the heuristic selects them. Each target gets
    one warm-started re-solve with its incumbent machine forbidden; the result
    is stored as a pool-member-class document (feasible) or a verdict-only
    member (infeasible). Registry-free — the caller indexes the result.
    """
    from mre.contracts.schedule_document import PoolBlock
    from mre.contracts.vocabularies import ModuleCode, RunStatus
    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.extractor import Extractor
    from mre.modules.scenario import derive_base_context
    from mre.modules.schedule_assembler import assemble_schedule_document
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import (
        SolverBuilder,
        add_forced_alternative_cut,
        apply_solution_hints,
    )
    from mre.reporter import Reporter

    t0 = time.monotonic()
    out_dir = Path(out_dir)
    alt_dir = out_dir / "alternatives"
    alt_dir.mkdir(parents=True, exist_ok=True)
    pool_id = pool_id or f"alt-{uuid.uuid4().hex[:12]}"

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
    service_outcomes = list(reader.iter_entities("serviceoutcome"))
    incumbent_assignments = list(reader.iter_entities("assignment"))
    identity_map = reader.read_identity_map()
    cost_model = costmodels[0] if costmodels else {}

    evidence = _read_evidence(out_dir / runs_subdir)
    ctx = derive_base_context(out_dir / runs_subdir)
    reference_date = _parse_ref_date(ctx.get("reference_date"))
    horizon_start, horizon_end = _m5_horizon(evidence)
    incumbent_objective = _incumbent_objective(evidence)
    flattened_cals = flatten_all_calendars(calendars, horizon_start, horizon_end)
    incumbent_placement = _placements(incumbent_assignments)

    if target_op_ids is None:
        target_op_ids = select_target_ops(
            operations=ops, fulfillments=fuls, demands=demands,
            service_outcomes=service_outcomes,
            incumbent_placement=incumbent_placement, budget=budget,
        )
    else:
        target_op_ids = [o for o in target_op_ids if o in incumbent_placement][:budget]

    params = {
        "budget": budget, "member_time_limit_s": member_time_limit_s,
        "seed": seed, "incumbent_objective": incumbent_objective,
        "selection": ("explicit" if target_op_ids is not None else "heuristic_v1"),
        "n_targets": len(target_op_ids),
        "mechanism": (
            "per target op: warm-start hints from incumbent + a "
            "'not on the incumbent machine' cut (add_forced_alternative_cut), "
            "short time limit; no objective bound (the true best price of the "
            "road not taken, even when worse than the incumbent)"
        ),
    }

    members: list[ForcedAlternative] = []
    for i, target in enumerate(target_op_ids):
        m_t0 = time.monotonic()
        forbidden = incumbent_placement[target][0]

        b_rep = Reporter.begin(
            module=ModuleCode.M5, purpose=f"forced-alt {i} model build",
            config={"horizon_start": horizon_start.isoformat(),
                    "horizon_end": horizon_end.isoformat(),
                    "pool_id": pool_id, "member_index": i,
                    "target_operation": target, "forbidden_resource": forbidden},
            trigger="forced_alternative", snapshot_id=snapshot_id,
            sink_dir=alt_dir / f"member_{i}_runs",
        )
        model, var_map = SolverBuilder(reference_date=reference_date).build(
            wps + ops + edges, resources + pools, flattened_cals,
            fuls + demands, constraints, cost_model,
        )
        b_rep.end(RunStatus.SUCCESS)

        apply_solution_hints(model, var_map, incumbent_assignments)
        forced = add_forced_alternative_cut(model, var_map, target, forbidden)

        r_rep = Reporter.begin(
            module=ModuleCode.M6, purpose=f"forced-alt {i} solve",
            config={"time_limit": member_time_limit_s,
                    "num_search_workers": ctx.get("solver_workers"),
                    "random_seed": seed + i, "pool_id": pool_id,
                    "member_index": i, "target_operation": target},
            trigger="forced_alternative", snapshot_id=snapshot_id,
            sink_dir=alt_dir / f"member_{i}_runs",
        )
        solve_result = SolveRunner(
            time_limit_seconds=member_time_limit_s,
            num_search_workers=ctx.get("solver_workers"),
            random_seed=seed + i,
        ).solve(model, var_map, r_rep)
        r_rep.end(RunStatus.SUCCESS
                  if solve_result.status in ("OPTIMAL", "FEASIBLE")
                  else RunStatus.PARTIAL)

        member = ForcedAlternative(
            member_index=i, target_operation_ref=target,
            forbidden_resource_ref=forbidden, status=solve_result.status,
            verdict="no_solution", wall_time_s=round(time.monotonic() - m_t0, 3),
        )
        if not forced:
            # nothing to forbid (op had no literal for the incumbent machine —
            # e.g. single-eligibility): there is no alternative to price.
            member.verdict = "infeasible_this_horizon"
            members.append(member)
            continue
        if solve_result.status not in ("OPTIMAL", "FEASIBLE"):
            # R-T1a: infeasibility is information — "not feasible this horizon".
            member.verdict = "infeasible_this_horizon"
            members.append(member)
            continue

        member.objective = solve_result.objective
        if incumbent_objective and incumbent_objective > 0 and solve_result.objective:
            member.objective_delta_pct = round(
                (solve_result.objective - incumbent_objective)
                / incumbent_objective * 100.0, 4)
        member.alternative_resource_ref = solve_result.solve_values.op_resource.get(target)
        member.verdict = "priced"

        extract = Extractor().extract(
            solve_values=solve_result.solve_values,
            snapshot_id=snapshot_id,
            operations=ops, workpackages=wps, resources=resources,
            fulfillments=fuls, demands=demands, cost_model=cost_model,
            reporter=None, cal_windows=var_map.cal_windows,
            op_eligible=var_map.op_eligible, snapshot_writer=None,
            overtime_windows=var_map.overtime_windows,
        )
        document = assemble_schedule_document(
            snapshot_id=snapshot_id, run_id=run_id,
            schedule=extract.schedule, assignments=extract.assignments,
            service_outcomes=extract.service_outcomes,
            operations=ops, workpackages=wps, fulfillments=fuls,
            demands=demands, resources=resources, pools=pools,
            calendars=calendars, constraints=constraints,
            costmodels=costmodels, identity_map=identity_map,
            evidence_records=_read_evidence(alt_dir / f"member_{i}_runs"),
            pool_block=PoolBlock(
                pool_id=pool_id, base_schedule_id=base_schedule_id,
                member_index=i, objective=solve_result.objective,
                objective_delta_pct=member.objective_delta_pct,
                source="forced_alternative",
                target_operation_ref=target,
                forbidden_resource_ref=forbidden,
                alternative_resource_ref=member.alternative_resource_ref,
            ),
        )
        doc_path = alt_dir / f"member_{i}.json"
        doc_path.write_text(document.model_dump_json(indent=2), encoding="utf-8")
        member.document_path = str(doc_path)
        members.append(member)

    result = ForcedAlternativeResult(
        pool_id=pool_id, base_schedule_id=base_schedule_id,
        snapshot_id=snapshot_id,
        status="ready" if any(m.verdict == "priced" for m in members) else "empty",
        members=members, params=params,
        wall_time_s=round(time.monotonic() - t0, 3),
    )
    summary_path = alt_dir / "alternatives.json"
    summary_path.write_text(json.dumps(result.summary(), indent=2, default=str),
                            encoding="utf-8")
    result.summary_path = str(summary_path)
    return result


def _parse_ref_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw or raw == "now":
        return None
    dt = datetime.fromisoformat(raw)
    from datetime import timezone
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

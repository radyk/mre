"""Solution-pool service (docs/07 Phase 2): diverse near-optimal alternatives.

For a solved schedule, produce K near-optimal solutions that are genuinely
*different* placements — the raw material for Tier-1 drag ghosts ("this op
also fits Tuesday 09:00 on the other press, +$120"), pool-consensus
testimony ("in 4 of 5 near-optimal schedules this runs on WC-B"), and later
ATP's fast re-solve.

Mechanism (documented, measured):
  Each member is a short re-solve of the EXACT base model (rebuilt from the
  persisted snapshot + the run's own evidence — same entities, same
  M5-recorded horizon, same reference date), with three additions:
    1. warm-start hints from the incumbent schedule
       (``solver_builder.apply_solution_hints`` — the warm-start mechanics);
    2. an objective upper bound: member objective ≤ incumbent × (1 + X/100)
       (``add_objective_upper_bound`` over the builder's own objective
       terms), so every member is near-optimal by construction;
    3. diversity pressure: a randomized search seed per member PLUS a
       no-good cut over a random sample of the incumbent's start times
       (``add_start_diversity_cut``: at least one sampled op must start at
       a different minute) — disjunctive, so one tight operation cannot
       sink a member.
  Measured diversity (assignment Hamming distance: ops whose (resource,
  start) differ) is reported per member and pairwise in the pool summary.

Isolation rules (same posture as scenarios, docs/01 §8):
  - Pool members are documents in the run dir's ``pool/`` subdirectory and
    rows in the registry's pool tables — NEVER rows in the schedules table,
    so they can never appear in any schedule listing.
  - Nothing is written into the base snapshot: member extraction runs with
    no snapshot writer and no reporter-side Decisions; each member's own
    solve evidence sinks to ``pool/member_<n>_runs/``.
  - Pool documents carry ``annotations.pool`` (contract 1.1) so a document
    alone is identifiable as a pool member.
  - Pools are invalidated when the base schedule is superseded
    (``Registry.mark_schedule_superseded``).
"""
from __future__ import annotations

import json
import random
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

UTC = timezone.utc

DEFAULT_K = 5
DEFAULT_TOLERANCE_PCT = 10.0
DEFAULT_MEMBER_TIME_LIMIT_S = 10.0
DEFAULT_SEED = 1234


@dataclass
class PoolMember:
    member_index: int
    status: str                       # OPTIMAL | FEASIBLE | INFEASIBLE | UNKNOWN
    objective: Optional[float] = None
    objective_delta_pct: Optional[float] = None
    hamming_from_incumbent: Optional[int] = None
    wall_time_s: float = 0.0
    document_path: Optional[str] = None


@dataclass
class PoolResult:
    pool_id: str
    base_schedule_id: str
    snapshot_id: str
    status: str                       # ready | empty
    k_requested: int
    members: list[PoolMember] = field(default_factory=list)
    diversity: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    wall_time_s: float = 0.0
    summary_path: Optional[str] = None

    def summary(self) -> dict:
        d = asdict(self)
        return d


def warm_solution_pool(
    out_dir: Path | str,
    snapshot_id: str,
    base_schedule_id: str,
    run_id: str,
    k: int = DEFAULT_K,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
    member_time_limit_s: float = DEFAULT_MEMBER_TIME_LIMIT_S,
    seed: int = DEFAULT_SEED,
    runs_subdir: str = "runs",
    pool_id: Optional[str] = None,
) -> PoolResult:
    """Build the solution pool for a persisted, solved run directory.

    Pure with respect to the base run: reads the snapshot and its evidence,
    writes only under ``out_dir/pool/``. Registry indexing is the caller's
    job (the API worker) — this module stays registry-free so the CLI and
    tests can drive it directly.
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
        add_objective_upper_bound,
        add_start_diversity_cut,
        apply_solution_hints,
    )
    from mre.reporter import Reporter

    t0 = time.monotonic()
    out_dir = Path(out_dir)
    pool_dir = out_dir / "pool"
    pool_dir.mkdir(parents=True, exist_ok=True)
    pool_id = pool_id or f"pool-{uuid.uuid4().hex[:12]}"

    # ------------------------------------------------------------------
    # Load the base run: entities, identity map, evidence-derived config
    # ------------------------------------------------------------------
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
    incumbent_assignments = list(reader.iter_entities("assignment"))
    identity_map = reader.read_identity_map()
    cost_model = costmodels[0] if costmodels else {
        "id": "default-cm", "resource_rates": {},
        "setup_cost_basis": {"fixed_per_setup": 50.0, "scrap_cost_per_unit": 0.0},
        "tardiness_weights": {"base_weight": 1.0, "commitment_class_multipliers": {}},
    }

    evidence = _read_evidence(out_dir / runs_subdir)
    ctx = derive_base_context(out_dir / runs_subdir)
    reference_date = _parse_ref_date(ctx.get("reference_date"))
    horizon_start, horizon_end = _m5_horizon(evidence)
    incumbent_objective = _incumbent_objective(evidence)

    flattened_cals = flatten_all_calendars(calendars, horizon_start, horizon_end)

    # ------------------------------------------------------------------
    # Incumbent placements (for hints, the diversity cut, and Hamming)
    # ------------------------------------------------------------------
    incumbent_starts_min: dict[str, int] = {}
    for a in incumbent_assignments:
        windows = (a.get("phase_windows") or {}).get("run") or []
        if not windows:
            continue
        start_dt = _parse_dt(windows[0]["start"])
        incumbent_starts_min[a["operation_ref"]] = int(
            (start_dt - horizon_start).total_seconds() // 60
        )
    incumbent_placement = _placements(incumbent_assignments)

    params = {
        "k": k, "tolerance_pct": tolerance_pct,
        "member_time_limit_s": member_time_limit_s, "seed": seed,
        "solver_workers": ctx.get("solver_workers"),
        "incumbent_objective": incumbent_objective,
        "diversity_mechanism": (
            "warm-start hints from incumbent + objective bound "
            f"<= incumbent x {1 + tolerance_pct / 100.0:.2f} + per-member "
            "randomized seed + no-good cut on a random sample of incumbent "
            "start times (at least one sampled op must move)"
        ),
    }

    members: list[PoolMember] = []
    member_placements: dict[int, dict] = {}

    for i in range(k):
        m_t0 = time.monotonic()
        rng = random.Random(seed * 1000 + i)

        b_rep = Reporter.begin(
            module=ModuleCode.M5, purpose=f"pool member {i} model build",
            config={"horizon_start": horizon_start.isoformat(),
                    "horizon_end": horizon_end.isoformat(),
                    "pool_id": pool_id, "member_index": i},
            trigger="pool", snapshot_id=snapshot_id,
            sink_dir=pool_dir / f"member_{i}_runs",
        )
        model, var_map = SolverBuilder(reference_date=reference_date).build(
            wps + ops + edges, resources + pools, flattened_cals,
            fuls + demands, constraints, cost_model,
        )
        b_rep.end(RunStatus.SUCCESS)

        apply_solution_hints(model, var_map, incumbent_assignments)
        if incumbent_objective and incumbent_objective > 0:
            add_objective_upper_bound(
                model, var_map,
                int(incumbent_objective * (1 + tolerance_pct / 100.0)),
            )
        candidates = sorted(oid for oid in incumbent_starts_min
                            if oid in var_map.op_start)
        n_sample = min(len(candidates), max(3, len(candidates) // 10))
        sampled = rng.sample(candidates, n_sample) if candidates else []
        add_start_diversity_cut(model, var_map, incumbent_starts_min,
                                sampled, name=f"m{i}")

        r_rep = Reporter.begin(
            module=ModuleCode.M6, purpose=f"pool member {i} solve",
            config={"time_limit": member_time_limit_s,
                    "num_search_workers": ctx.get("solver_workers"),
                    "random_seed": seed + i,
                    "pool_id": pool_id, "member_index": i},
            trigger="pool", snapshot_id=snapshot_id,
            sink_dir=pool_dir / f"member_{i}_runs",
        )
        solve_result = SolveRunner(
            time_limit_seconds=member_time_limit_s,
            num_search_workers=ctx.get("solver_workers"),
            random_seed=seed + i,
        ).solve(model, var_map, r_rep)
        r_rep.end(RunStatus.SUCCESS
                  if solve_result.status in ("OPTIMAL", "FEASIBLE")
                  else RunStatus.PARTIAL)

        member = PoolMember(
            member_index=i,
            status=solve_result.status,
            objective=solve_result.objective,
            wall_time_s=round(time.monotonic() - m_t0, 3),
        )
        if solve_result.status not in ("OPTIMAL", "FEASIBLE"):
            # No near-optimal alternative in this cut's direction — a valid
            # finding about the schedule's rigidity, kept in the summary.
            members.append(member)
            continue

        if incumbent_objective and incumbent_objective > 0 and solve_result.objective:
            member.objective_delta_pct = round(
                (solve_result.objective - incumbent_objective)
                / incumbent_objective * 100.0, 4,
            )

        # Extract in memory only: no snapshot writer, no reporter — pool
        # members must leave the canonical snapshot untouched.
        extract = Extractor().extract(
            solve_values=solve_result.solve_values,
            snapshot_id=snapshot_id,
            operations=ops, workpackages=wps, resources=resources,
            fulfillments=fuls, demands=demands, cost_model=cost_model,
            reporter=None,
            cal_windows=var_map.cal_windows,
            op_eligible=var_map.op_eligible,
            snapshot_writer=None,
            overtime_windows=var_map.overtime_windows,
        )

        placement = _placements(extract.assignments)
        member_placements[i] = placement
        member.hamming_from_incumbent = _hamming(incumbent_placement, placement)

        document = assemble_schedule_document(
            snapshot_id=snapshot_id,
            run_id=run_id,
            schedule=extract.schedule,
            assignments=extract.assignments,
            service_outcomes=extract.service_outcomes,
            operations=ops, workpackages=wps, fulfillments=fuls,
            demands=demands, resources=resources, pools=pools,
            calendars=calendars, constraints=constraints,
            costmodels=costmodels, identity_map=identity_map,
            evidence_records=_read_evidence(pool_dir / f"member_{i}_runs"),
            pool_block=PoolBlock(
                pool_id=pool_id,
                base_schedule_id=base_schedule_id,
                member_index=i,
                objective=solve_result.objective,
                objective_delta_pct=member.objective_delta_pct,
            ),
        )
        doc_path = pool_dir / f"member_{i}.json"
        doc_path.write_text(document.model_dump_json(indent=2), encoding="utf-8")
        member.document_path = str(doc_path)
        members.append(member)

    # ------------------------------------------------------------------
    # Measured diversity
    # ------------------------------------------------------------------
    ok = [m for m in members if m.document_path]
    from_incumbent = [m.hamming_from_incumbent for m in ok
                      if m.hamming_from_incumbent is not None]
    pairwise = [
        _hamming(member_placements[a.member_index], member_placements[b.member_index])
        for x, a in enumerate(ok) for b in ok[x + 1:]
    ]
    diversity = {
        "mean_hamming_from_incumbent": (
            round(sum(from_incumbent) / len(from_incumbent), 2)
            if from_incumbent else None
        ),
        "mean_pairwise_hamming": (
            round(sum(pairwise) / len(pairwise), 2) if pairwise else None
        ),
        "ops_with_alternative_positions": _ops_with_alternatives(
            incumbent_placement, member_placements
        ),
        "operation_count": len(incumbent_placement),
    }

    result = PoolResult(
        pool_id=pool_id,
        base_schedule_id=base_schedule_id,
        snapshot_id=snapshot_id,
        status="ready" if ok else "empty",
        k_requested=k,
        members=members,
        diversity=diversity,
        params=params,
        wall_time_s=round(time.monotonic() - t0, 3),
    )
    summary_path = pool_dir / "pool.json"
    summary_path.write_text(
        json.dumps(result.summary(), indent=2, default=str), encoding="utf-8",
    )
    result.summary_path = str(summary_path)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_evidence(runs_dir: Path) -> list[dict]:
    records: list[dict] = []
    if not runs_dir.exists():
        return records
    for f in sorted(runs_dir.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _parse_ref_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw or raw == "now":
        return None
    dt = datetime.fromisoformat(raw)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _parse_dt(raw: str) -> datetime:
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _m5_horizon(evidence: list[dict]) -> tuple[datetime, datetime]:
    """The base run's own recorded M5 horizon — rebuilding with anything
    else risks a model that does not correspond to the incumbent."""
    m5 = [r for r in evidence
          if r.get("record_type") == "run_context_open" and r.get("module") == "M5"]
    m5.sort(key=lambda r: r.get("started_at", ""))
    if not m5:
        raise ValueError("no M5 run evidence — cannot rebuild the base model")
    cfg = m5[-1].get("config_snapshot") or {}
    if not cfg.get("horizon_start") or not cfg.get("horizon_end"):
        raise ValueError("M5 run evidence carries no horizon (pre-2.1 run?)")
    return _parse_dt(cfg["horizon_start"]), _parse_dt(cfg["horizon_end"])


def _incumbent_objective(evidence: list[dict]) -> Optional[float]:
    solves = [r for r in evidence
              if r.get("record_type") == "event"
              and r.get("status_text") == "solve_complete"]
    if not solves:
        return None
    return (solves[-1].get("payload") or {}).get("objective")


def _placements(assignments: list[dict]) -> dict[str, tuple[str, str]]:
    """op_id → (resource_id, run_start ISO normalized) for Hamming distance.
    Handles both the persisted-entity and extractor dict shapes; datetimes
    are parsed (never compared as raw strings — the 2026-07-13 differ
    lesson)."""
    out: dict[str, tuple[str, str]] = {}
    for a in assignments:
        rid = a.get("resource_id")
        if not rid:
            ras = a.get("resource_assignments") or []
            rid = ras[0].get("resource_ref") if ras else None
        windows = (a.get("phase_windows") or {}).get("run") or a.get("run_windows") or []
        if not (rid and windows):
            continue
        out[a["operation_ref"]] = (rid, _parse_dt(windows[0]["start"]).isoformat())
    return out


def _hamming(p1: dict[str, tuple], p2: dict[str, tuple]) -> int:
    """Number of operations placed differently (resource OR start)."""
    shared = set(p1) & set(p2)
    return sum(1 for oid in shared if p1[oid] != p2[oid])


def _ops_with_alternatives(
    incumbent: dict[str, tuple], member_placements: dict[int, dict],
) -> int:
    """Count of operations with ≥2 distinct placements across the incumbent
    and all pool members — the Tier-1 ghost precondition: a drag ghost
    exists only for ops the pool actually places elsewhere."""
    count = 0
    for oid, inc in incumbent.items():
        placements = {inc} | {
            p[oid] for p in member_placements.values() if oid in p
        }
        if len(placements) >= 2:
            count += 1
    return count

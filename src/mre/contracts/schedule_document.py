"""The Schedule JSON contract — the versioned document the API serves.

This is the record shape the demo cockpit (and any other consumer) reads.
It is DERIVED, never invented: every field maps to an existing source —
canonical entities (Schedule, Assignment, ServiceOutcome, Resource,
Calendar, Demand via Fulfillment), the identity map, or evidence records
(RunContext telemetry, assignment Decisions, cost-ledger metrics).

Field rules (docs/04 amendment, contract derivation decision):
- External (customer-vocabulary) names appear ONLY in ``*_name`` /
  ``work_order`` fields. Canonical UUID refs are kept alongside for
  machine navigation — both, deliberately.
- All timestamps are ISO 8601 UTC (timezone-aware datetimes here;
  serialize with ``model_dump(mode="json")``).
- ``cost_summary`` must decompose exactly:
  total = production_regular + production_overtime + setup + tardiness.
  Enforced at construction (malformed documents die at the source).
- Chunked (resumable) operations carry one chunk per run window; the
  pauses are the gaps between chunks (docs/05 R-C3). Plain operations
  carry exactly one chunk.
- Tardiness is evaluated per Demand: service_outcomes are keyed by
  demand_ref, never by workpackage.

Version this contract: additive changes bump the minor, breaking changes
bump the major. Add, never repurpose.

Version history:
- 1.0 (2026-07-13, session 2.1): initial contract.
- 1.1 (2026-07-13, session 2.2): additive — ``annotations.pool`` marks
  solution-pool member documents (pool_id, member_index, objective delta).
  Absent (None) on every non-pool document.
- 1.2 (2026-07-11, session 3.1): additive — the top-level ``interaction``
  block: the Tier-0 legality-arithmetic payload (docs/04 R-DP6). Everything
  the cockpit needs to shade legal drop zones WITHOUT a solver — per-operation
  eligible resource sets, working/setup durations, release floors, and the
  precedence graph. Calendar windows already live in
  ``resources[].calendar_windows``; occupancy is computed client-side from
  ``assignments[]`` (resource_id + chunks) and is deliberately NOT duplicated.
  Present only when the assembler is given the precedence edges (the API
  path); None on pool members and pre-1.2 documents. 1.1 consumers ignore it.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, model_validator

from mre.contracts.vocabularies import ScheduleStatus

CONTRACT_VERSION = "1.2"

# Exact decomposition tolerance: cost components are currency values
# accumulated in float; "exactly" means to the cent, matching the
# consolidator's rollup check and the scenario diff's _decomp_ok.
_DECOMP_TOLERANCE = 0.01


class HorizonBlock(BaseModel):
    """The solver builder's planning horizon (recorded in M5 run evidence)."""
    start: datetime
    end: datetime


class SolverBlock(BaseModel):
    """M6 RunContext telemetry for the solve that produced this schedule."""
    status: str                                # OPTIMAL | FEASIBLE
    objective: Optional[float] = None
    gap: Optional[float] = None
    wall_time_s: float = 0.0
    deterministic: bool = False                # workers pinned to 1 + seed set


class CostSummary(BaseModel):
    """The cost ledger, decomposed. Must satisfy exact decomposability."""
    total: float
    production_regular: float
    production_overtime: float
    setup: float
    tardiness: float
    costmodel_version: int = 1

    @model_validator(mode="after")
    def _decomposes_exactly(self) -> "CostSummary":
        parts = (
            self.production_regular + self.production_overtime
            + self.setup + self.tardiness
        )
        if abs(self.total - parts) > _DECOMP_TOLERANCE:
            raise ValueError(
                f"cost_summary does not decompose: total={self.total} but "
                f"components sum to {parts}"
            )
        return self


class CalendarWindow(BaseModel):
    """One flattened calendar window on a resource lane — the Gantt's shading."""
    start: datetime
    end: datetime
    kind: Literal["regular", "overtime", "closure"]


class ResourceLane(BaseModel):
    """One Gantt row: a Resource plus its flattened Calendar."""
    resource_id: str                           # canonical UUID
    external_name: Optional[str] = None        # customer vocabulary
    facility: Optional[str] = None
    pool: Optional[str] = None                 # pool external name if mapped
    calendar_windows: list[CalendarWindow] = []


class Chunk(BaseModel):
    """One contiguous run window. Plain operations have exactly one;
    resumable operations have one per window, pausing in the gaps (R-C3)."""
    chunk_seq: int
    start: datetime
    end: datetime
    working_min: int


class PhaseWindow(BaseModel):
    start: datetime
    end: datetime


class Phases(BaseModel):
    """Setup/teardown phase windows. The solver models the operation
    interval as setup + run contiguous from the operation start, so setup
    is the first setup_duration minutes of the first chunk. Teardown is
    not modeled in the current solver — always null, present for contract
    stability."""
    setup: Optional[PhaseWindow] = None
    teardown: Optional[PhaseWindow] = None


class AssignmentBlock(BaseModel):
    """Per-Operation scheduling result, external names alongside UUID refs."""
    assignment_id: str
    operation_ref: str                         # canonical UUID
    workpackage_ref: str                       # canonical UUID
    work_orders: list[str] = []                # external; merged WPs list all
    op_seq: int = 0
    setup_family: str = ""
    resource_id: str                           # canonical UUID
    external_name: Optional[str] = None        # resource, customer vocabulary
    chunks: list[Chunk] = []
    phases: Phases = Phases()
    in_overtime_min: int = 0                   # overtime evidence (Decision)
    decision_ref: str = ""                     # reconstructed-alternatives Decision


class ServiceOutcomeBlock(BaseModel):
    """Per-Demand service truth (via Fulfillments; never per WorkPackage)."""
    demand_ref: str                            # canonical UUID
    work_order: Optional[str] = None           # external
    customer_ref: Optional[str] = None         # canonical UUID
    due: Optional[datetime] = None
    projected_completion: datetime
    lateness_min: int                          # negative = early
    tardiness_cost: float = 0.0


class ScenarioBlock(BaseModel):
    is_scenario: bool = False
    parent_schedule_id: Optional[str] = None


class PoolBlock(BaseModel):
    """Marks a solution-pool member (contract 1.1). Pool members are diverse
    near-optimal alternatives to a base schedule — never the schedule of
    record, never listed among real schedules (same isolation rule as
    scenarios)."""
    is_pool_member: bool = True
    pool_id: str
    base_schedule_id: str
    member_index: int
    objective: Optional[float] = None          # solver objective (scaled units)
    objective_delta_pct: Optional[float] = None  # vs the incumbent's objective


class OperationInteraction(BaseModel):
    """Per-operation Tier-0 facts the client needs to shade legal drop zones
    without a solver (contract 1.2, docs/04 R-DP6). ``eligible_resource_ids``
    is the FULL set the op may run on — not just the chosen one — so the board
    can dim capability-illegal rows; ``working_min``/``setup_min`` size the bar
    for a fit/displace test; ``earliest_start`` is the release floor; the
    precedence graph (separate ``precedence_edges`` list) supplies the
    predecessor-finish floor."""
    operation_ref: str                         # canonical UUID
    eligible_resource_ids: list[str] = []      # canonical UUIDs (the WHOLE set)
    working_min: int = 0                        # run working minutes (sum of chunks)
    setup_min: int = 0                          # setup minutes prefixed to the run
    earliest_start: Optional[datetime] = None  # release floor (demand.release)


class PrecedenceEdgeBlock(BaseModel):
    """One precedence relationship (docs/05 R-A2/A3). The successor cannot
    start before predecessor_finish + min_lag; max_lag (when set) caps the
    gap. Both refs are operation UUIDs present in ``interaction.operations``."""
    predecessor_ref: str
    successor_ref: str
    min_lag_min: int = 0
    max_lag_min: Optional[int] = None


class InteractionBlock(BaseModel):
    """Contract 1.2 additive: the Tier-0 legality-arithmetic payload.

    Everything the cockpit needs to compute legal drop zones CLIENT-SIDE, with
    no solver round-trip (docs/07 Phase 3 Tier-0; docs/04 R-DP6): per-operation
    eligible sets + durations + release floors, and the precedence graph.
    Calendar windows are already carried per lane in
    ``resources[].calendar_windows``; resource occupancy is computed from
    ``assignments[]`` (each assignment's resource_id + chunks) and is
    deliberately NOT duplicated here (the schedule already IS the occupancy)."""
    operations: list[OperationInteraction] = []
    precedence_edges: list[PrecedenceEdgeBlock] = []


class Annotations(BaseModel):
    locks: list[str] = []                      # F1/A7 pins, rendered
    scenario: ScenarioBlock = ScenarioBlock()
    pool: Optional[PoolBlock] = None           # set only on pool members (1.1)


class ScheduleDocument(BaseModel):
    """The versioned schedule document served by GET /schedules/{id}."""
    contract_version: str = CONTRACT_VERSION
    schedule_id: str
    snapshot_id: str
    run_id: str
    status: ScheduleStatus = ScheduleStatus.PROPOSED
    reference_date: Optional[datetime] = None
    horizon: Optional[HorizonBlock] = None
    solver: SolverBlock
    cost_summary: CostSummary
    resources: list[ResourceLane] = []
    assignments: list[AssignmentBlock] = []
    service_outcomes: list[ServiceOutcomeBlock] = []
    annotations: Annotations = Annotations()
    interaction: Optional[InteractionBlock] = None   # contract 1.2 (Tier-0 payload)

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
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, model_validator

from mre.contracts.vocabularies import ScheduleStatus

CONTRACT_VERSION = "1.0"

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


class Annotations(BaseModel):
    locks: list[str] = []                      # F1/A7 pins, rendered
    scenario: ScenarioBlock = ScenarioBlock()


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

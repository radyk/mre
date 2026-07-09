"""Canonical entity types for the manufacturing reasoning engine.

Every entity carries id, snapshot_id, external_refs (docs/01 §4).
ERP identifiers appear only inside external_refs.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from pydantic import BaseModel, model_validator

from mre.contracts.vocabularies import (
    CalendarExceptionReason,
    CalendarExceptionType,
    CommitmentClass,
    ConstraintHardness,
    ConstraintProvenance,
    ConstraintType,
    DemandStatus,
    LimitReason,
    ProcessStatus,
    ResourceRequirementMode,
    ResourceType,
    ScheduleStatus,
    WorkPackageState,
)


# ---------------------------------------------------------------------------
# Shared structural types (not entities — no id/snapshot_id)
# ---------------------------------------------------------------------------


class ExternalRef(BaseModel):
    """One source-system identifier. The only place ERP IDs may appear."""
    system: str
    type: str
    value: str


class EntityRef(BaseModel):
    """Lightweight canonical entity reference used in evidence-record subjects."""
    entity_id: str
    entity_type: str


class Quantity(BaseModel):
    """Number plus unit of measure. Never pre-multiplied into duration."""
    value: float
    uom: str


class TimeWindow(BaseModel):
    start: datetime
    end: datetime


class ResourceRequirement(BaseModel):
    """Struct (not entity) — no id or snapshot_id.

    One Operation may carry several requirements simultaneously (machine AND tool).
    Capability vs explicit_set are distinct facts with different explanation semantics.
    """
    mode: ResourceRequirementMode
    capability_ref: Optional[str] = None
    resource_refs: list[str] = []
    count: int = 1

    @model_validator(mode="after")
    def _mode_consistency(self) -> ResourceRequirement:
        if self.mode == ResourceRequirementMode.CAPABILITY and not self.capability_ref:
            raise ValueError("capability_ref is required when mode=capability")
        if self.mode == ResourceRequirementMode.EXPLICIT_SET and not self.resource_refs:
            raise ValueError("resource_refs must be non-empty when mode=explicit_set")
        return self


class CalendarException(BaseModel):
    window: TimeWindow
    type: CalendarExceptionType
    reason: CalendarExceptionReason


class PhaseWindows(BaseModel):
    """Setup / run / dwell windows for an Assignment.
    Chunked (splittable) operations carry multiple run windows."""
    setup: Optional[TimeWindow] = None
    run: list[TimeWindow] = []
    dwell: Optional[TimeWindow] = None


class ResourceAssignment(BaseModel):
    """Resolves one ResourceRequirement to a specific Resource."""
    requirement: ResourceRequirement
    resource_ref: str


class TardinessWeights(BaseModel):
    base_weight: float
    commitment_class_multipliers: dict[str, float] = {}


class SetupCostBasis(BaseModel):
    fixed_per_setup: float = 0.0
    scrap_cost_per_unit: float = 0.0


# ---------------------------------------------------------------------------
# Product + Process chain
# ---------------------------------------------------------------------------


class Product(BaseModel):
    id: str
    snapshot_id: str
    external_refs: list[ExternalRef] = []
    name: str
    unit_of_measure: str
    process_ref: Optional[str] = None
    product_family: Optional[str] = None


class Capability(BaseModel):
    """Deliberately thin. PoC uses exact reference equality for matching."""
    id: str
    snapshot_id: str
    external_refs: list[ExternalRef] = []
    name: str
    description: str = ""
    parameters: dict[str, Any] = {}


class OperationSpec(BaseModel):
    """Quantity-independent template; Process owns these.

    No dwell_rule (docs/05 R-Dwell): dwell is not a phase. It is a min-lag
    on the PrecedenceEdge outgoing from this spec. Phases occupy resources;
    lags don't.
    """
    id: str
    snapshot_id: str
    sequence: int
    resource_requirements: list[ResourceRequirement] = []
    setup_family: str = ""
    base_setup: timedelta = timedelta(0)
    run_rate: timedelta = timedelta(0)
    splittable: bool = False
    min_chunk: Optional[timedelta] = None
    yield_factor: float = 1.0


class PrecedenceEdge(BaseModel):
    """First-class precedence relationship between two OperationSpecs
    (docs/05 R-A2/A3, §4 surgery).

    Lags are properties of the relationship, not of either operation —
    this is what survives non-linear routings and matches how the
    constraint is actually spoken ("max 4 hours between coating and
    curing"). predecessor/successor are OperationSpec refs (template-level:
    the same edge applies to every WorkPackage instantiating the Process).

    min_lag defaults to 0 (immediate succession); dwell lands here per
    R-Dwell. max_lag=None means unconstrained (R-A3's default of infinity —
    the doorway for a real max-lag source is deferred, docs/06 §8).
    """
    id: str
    snapshot_id: str
    predecessor: str
    successor: str
    min_lag: timedelta = timedelta(0)
    max_lag: Optional[timedelta] = None


class Process(BaseModel):
    """The manufacturing recipe. One active Process per Product for the PoC."""
    id: str
    snapshot_id: str
    external_refs: list[ExternalRef] = []
    product_ref: str
    operation_specs: list[str] = []
    version: int = 1
    effective_from: Optional[datetime] = None
    status: ProcessStatus = ProcessStatus.ACTIVE


# ---------------------------------------------------------------------------
# Calendar + Resource
# ---------------------------------------------------------------------------


class Calendar(BaseModel):
    id: str
    snapshot_id: str
    external_refs: list[ExternalRef] = []
    base_pattern: dict[str, Any] = {}
    exceptions: list[CalendarException] = []
    horizon_resolved: list[TimeWindow] = []


class Resource(BaseModel):
    """Anything finite. One entity type covers machines, tools, labor, fixtures."""
    id: str
    snapshot_id: str
    external_refs: list[ExternalRef] = []
    resource_type: ResourceType
    capabilities: list[str] = []
    capacity: int = 1
    cost_rate: float = 0.0
    calendar_ref: Optional[str] = None
    pool_refs: list[str] = []


class ResourcePool(BaseModel):
    """Canonical resolution of the ERP concept 'workcenter'."""
    id: str
    snapshot_id: str
    external_refs: list[ExternalRef] = []
    members: list[str] = []
    concurrent_capacity: Optional[int] = None
    calendar_ref: Optional[str] = None
    limit_reason: LimitReason = LimitReason.UNKNOWN


# ---------------------------------------------------------------------------
# Spine entities
# ---------------------------------------------------------------------------


class Demand(BaseModel):
    """What is wanted. Immutable observation; never mutated by planning."""
    id: str
    snapshot_id: str
    external_refs: list[ExternalRef] = []
    product_ref: str
    quantity: Quantity
    due: datetime
    earliest_start: Optional[datetime] = None
    commitment_class: CommitmentClass
    customer_weight: float = 1.0
    customer_ref: Optional[str] = None
    status: DemandStatus


class Operation(BaseModel):
    """Schedulable instance; Planner creates one per OperationSpec per WorkPackage.
    run_duration is derived: quantity × spec run_rate.

    No predecessors list (docs/05 §4 surgery) and no dwell_duration (R-Dwell):
    precedence and lags (including dwell) are read from PrecedenceEdge
    records keyed by spec_ref, not carried as instance attributes.
    """
    id: str
    snapshot_id: str
    spec_ref: str
    workpackage_ref: str
    sequence: int
    resource_requirements: list[ResourceRequirement] = []
    setup_family: str = ""
    setup_duration: timedelta = timedelta(0)
    run_duration: timedelta = timedelta(0)
    splittable: bool = False
    min_chunk: Optional[timedelta] = None


class WorkPackage(BaseModel):
    """Unit of planning and scheduling.

    Deliberately absent: no due date (lives on Demands via Fulfillments),
    no priority (derived at solve time from constituent Demands).
    """
    id: str
    snapshot_id: str
    external_refs: list[ExternalRef] = []
    product_ref: str
    quantity: Quantity
    earliest_start: Optional[datetime] = None
    operations: list[str] = []
    process_version: int = 1
    state: WorkPackageState = WorkPackageState.PLANNED
    created_by: str


class Fulfillment(BaseModel):
    """Explicit Demand ↔ WorkPackage mapping. First-class entity, not a FK."""
    id: str
    snapshot_id: str
    demand_ref: str
    workpackage_ref: str
    allocated_quantity: Quantity
    decision_ref: str


class Constraint(BaseModel):
    """Typed restrictions that are not structural (ordering lives in the entities)."""
    id: str
    snapshot_id: str
    external_refs: list[ExternalRef] = []
    constraint_type: ConstraintType
    subjects: list[str] = []
    parameters: dict[str, Any] = {}
    provenance_class: ConstraintProvenance
    authority: Optional[str] = None
    expiry: Optional[datetime] = None
    hardness: ConstraintHardness = ConstraintHardness.HARD
    penalty_weight: Optional[float] = None


class CostModel(BaseModel):
    """Economics as a versioned document. Every solve records which version it used."""
    id: str
    snapshot_id: str
    version: int = 1
    effective_from: Optional[datetime] = None
    resource_rates: dict[str, float] = {}
    setup_cost_basis: SetupCostBasis = SetupCostBasis()
    tardiness_weights: TardinessWeights = TardinessWeights(base_weight=1.0)
    overtime_premium: float = 0.0
    inventory_carrying: float = 0.0


# ---------------------------------------------------------------------------
# Solve output in canonical language
# ---------------------------------------------------------------------------


class Schedule(BaseModel):
    """The solve output container. Lives in canonical language; solver model discarded."""
    id: str
    snapshot_ref: str
    costmodel_ref: str
    solver_run_ref: Optional[str] = None
    status: ScheduleStatus = ScheduleStatus.PROPOSED
    summary_metrics: dict[str, Any] = {}


class Assignment(BaseModel):
    """Per-Operation scheduling result. decision_ref → a reconstructed Decision."""
    id: str
    snapshot_id: str
    operation_ref: str
    workpackage_ref: str
    resource_assignments: list[ResourceAssignment] = []
    phase_windows: PhaseWindows = PhaseWindows()
    decision_ref: str


class ServiceOutcome(BaseModel):
    """One per Fulfillment — the per-customer truth table, materialized.

    lateness < 0 means early; lateness > 0 means late.
    Consumers must not recompute lateness; this record is authoritative.
    Tardiness is evaluated per Demand, never per WorkPackage.
    """
    id: str
    snapshot_id: str
    demand_ref: str
    fulfillment_ref: str
    projected_completion: datetime
    lateness: timedelta
    tardiness_cost: float

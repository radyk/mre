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
    WipStatus,
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
    """Lightweight entity reference used in evidence-record subjects.

    ``system`` defaults to ``"canonical"``: entity_id/entity_type name a
    canonical entity. Pre-canonical modules (M0) set ``system="IDS"`` to name a
    *submission-space* ref — a typed (system, type, id) that exists before any
    canonical identity does (docs/02 boundary rule 1). entity_id then carries
    the submission id (e.g. "ORD-000001") and entity_type the submission-space
    type (e.g. "order_id"), which the M1 adapter registers in the identity map
    when it mints the corresponding canonical entity, making the finding
    reachable by canonical key. Added 2026-07-10 (Certificate session)."""
    entity_id: str
    entity_type: str
    system: str = "canonical"


class Quantity(BaseModel):
    """Number plus unit of measure. Never pre-multiplied into duration."""
    value: float
    uom: str


class TimeWindow(BaseModel):
    start: datetime
    end: datetime


class ResourceRateOverride(BaseModel):
    """Per-alternative time model for one eligible resource of an explicit_set
    requirement (docs/06 §5.3 alternative groups; docs/01 §5.5).

    A multi-eligible operation is expressed as repeated routing_lines rows
    sharing one (route_id, sequence) but naming different resource_id. When an
    alternative machine runs the operation at a DIFFERENT speed (its own
    setup_minutes / run_minutes_per_unit), that per-alternative time lands here,
    keyed by resource_ref on the requirement's ``rate_overrides``. The scalar
    ``OperationSpec.base_setup`` / ``run_rate`` remain the DEFAULT for any
    eligible resource with no override — an empty map is byte-identical old
    behaviour (the defaults-reproduce-baseline guarantee). Quantity-INDEPENDENT,
    exactly like ``run_rate``: the Planner resolves it against demand quantity.
    """
    base_setup: timedelta = timedelta(0)
    run_rate: timedelta = timedelta(0)


class ResourceRequirement(BaseModel):
    """Struct (not entity) — no id or snapshot_id.

    One Operation may carry several requirements simultaneously (machine AND tool).
    Capability vs explicit_set are distinct facts with different explanation semantics.
    """
    mode: ResourceRequirementMode
    capability_ref: Optional[str] = None
    resource_refs: list[str] = []
    count: int = 1
    # Per-alternative time model (docs/06 §5.3). resource_ref → its own
    # (base_setup, run_rate); resources absent from the map fall back to the
    # OperationSpec scalar defaults. Empty ⇒ every alternative shares one
    # duration (the pre-4B.0 model; byte-identical solves).
    rate_overrides: dict[str, ResourceRateOverride] = {}

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


class WipOperationObservation(BaseModel):
    """Observed shop-floor state of one operation of one order at
    reference_date (docs/06 §5.13). Struct, not entity — carried on the
    Demand (the order-level observation) in canonical terms only:
    spec_ref/actual_resource_ref are canonical ids, never ERP identifiers.
    source_rows are the wip_status.csv row numbers (1-based, excluding the
    header) this observation was read from — the provenance citation.

    Exactly one of remaining_minutes / quantity_complete is populated for
    in_progress observations: the adapter normalizes to the manifest's
    declared wip_progress_basis so downstream code never re-reads the
    manifest to know which is authoritative.
    """
    sequence: int
    spec_ref: str
    status: WipStatus
    actual_start: Optional[datetime] = None
    actual_resource_ref: Optional[str] = None
    remaining_minutes: Optional[float] = None
    quantity_complete: Optional[float] = None
    source_rows: list[int] = []


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
    # Observed execution state of this order's operations at reference_date
    # (docs/06 §5.13). Empty = no WIP source = blank slate. An observation,
    # like everything else on Demand — never written by planning.
    wip_operations: list[WipOperationObservation] = []


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
    # Per-alternative resolved durations (docs/06 §5.3): resource_ref → its own
    # quantity-resolved setup / run duration, projected by the Planner from the
    # requirement's rate_overrides (the instance analogue of run_duration).
    # A resource absent from these maps runs at the scalar setup_duration /
    # run_duration above; both empty ⇒ every eligible machine shares one
    # duration (byte-identical pre-4B.0 solves).
    resource_setup_durations: dict[str, timedelta] = {}
    resource_run_durations: dict[str, timedelta] = {}
    splittable: bool = False
    min_chunk: Optional[timedelta] = None
    # WIP landing (docs/06 §5.13, docs/01 §5.4): observed execution state at
    # reference_date. None = no observation (blank slate). complete ops carry
    # their observed actuals; in_progress ops carry observed start, observed
    # resource, and a DERIVED remaining_duration (the remainder arithmetic).
    wip_status: Optional[WipStatus] = None
    observed_start: Optional[datetime] = None
    observed_resource_ref: Optional[str] = None
    remaining_duration: Optional[timedelta] = None


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
    """Per-Operation scheduling result. decision_ref → a reconstructed Decision.

    overtime_minutes: scheduled minutes falling inside overtime premium
    calendar windows (docs/06 §5.6) — the entity is the authoritative source
    of the fact (added 2026-07-13, docs/01 §6.9); the assignment Decision's
    chosen payload repeats it only as narrative context. 0 when no premium
    is active.
    """
    id: str
    snapshot_id: str
    operation_ref: str
    workpackage_ref: str
    resource_assignments: list[ResourceAssignment] = []
    phase_windows: PhaseWindows = PhaseWindows()
    overtime_minutes: int = 0
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

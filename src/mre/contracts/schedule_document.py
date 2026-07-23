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
- 1.3 (2026-07-12, session 3.2a): split-endpoint delivery (docs/04 R-T1d).
  The interaction block is no longer delivered INLINE on ``GET /schedules/{id}``
  — it moves to the sibling ``GET /schedules/{id}/interaction`` so the main
  render document returns to its ~1.1 size (the +35.7% Tier-0 payload measured
  in 3.1 CU2 no longer sits inside first-paint). The document SCHEMA is
  unchanged (``interaction`` remains an optional field, always None on the main
  endpoint; the assembler still builds it in-memory for the split endpoint to
  persist and serve). Ruled a MINOR bump, not major: the field was optional
  from 1.2 and legitimately None for pool members / pre-1.2 docs, so a 1.2
  consumer already handles None; the sole production consumer is the cockpit,
  updated in the same session. Also additive: ``OperationInteraction.resumable``
  — a Tier-0 window-fit input (a resumable op may span calendar closures), a
  CU2-discovered payload gap extended in the same bump.
- 1.4 (2026-07-16, Session 4.0b): additive — ``OperationInteraction.dim_reasons``
  and a semantics fix to ``eligible_resource_ids``. The eligible set is now the
  set the SOLVER would give an op_assign literal (capability resolution AND the
  builder's resumable calendar feasible-window prune), derived through the shared
  ``eligibility`` module rather than a hand-copy of the capability logic — so
  Tier-0 can never green a row the R-DP1 pin would silently skip (docs/04 R-DP6).
  On the demo fixtures (no resumable/WIP ops) the set is BYTE-IDENTICAL to 1.3;
  it narrows only where the solver prunes. ``dim_reasons`` maps a
  capability-eligible-but-pruned resource to a truthful hover reason
  ("no_calendar_window" / "wip_fixed"); empty on documents with no such prune.
  MINOR: both are additive with empty defaults; a 1.3 consumer ignores
  ``dim_reasons`` and reads a strictly-narrower (never-wider) eligible set.
- 1.5 (2026-07-17, Session 4.0e): additive — ``AssignmentBlock.standing_pin``.
  True on an operation carrying a STANDING commitment (an accepted, still-held
  pin) on this version's lineage (docs/04 R-DP8). The cockpit renders a subtle
  standing-pin marker on those bars and, structurally, never lists a
  standing-pinned op as a moved consequence (a committed placement cannot be
  moved). Default False (a root solve has no standing pins); a 1.4 consumer
  ignores it. MINOR: additive with an empty default.
- 1.6 (2026-07-17, Session 4.2): additive — the planner-surface read layer.
  * ``CalendarWindow.reason`` — a non-regular window (closure / overtime) now
    carries its calendar-exception reason (planned_maintenance / holiday /
    breakdown / overtime), so the cockpit shades a planned-maintenance closure
    distinctly from generic off-shift and names it in the downtime hover. None
    on base-pattern regular windows. UNPLANNED (observed-actuals) downtime has
    no doorway yet and is deliberately NOT sourced (docs/04 4.2 debt).
  * ``ServiceOutcomeBlock.customer_name`` / ``quantity`` — the external customer
    (resolved via the identity map, never a UUID on screen) and the demand
    quantity, for the job-card hover. Both None when the source is absent.
  All three are additive with None defaults; a 1.5 consumer ignores them. MINOR.
- 1.7 (2026-07-23, Session 4B.3a): additive — the SLICED (rolling-horizon) world.
  A monolithic solve is ONE document rendering a whole plan; a rolling-horizon
  solve (pilot_scale, R-SC2) renders the plant AS OF the reference origin — a
  current window of committed + active-window work, with future work known but
  not yet placed. Three additions, all None/empty-defaulted so a monolithic
  document and its 1.6-and-earlier consumers are byte-unchanged:
  * ``AssignmentBlock.commitment_state`` — ``committed`` (frozen-front: locked,
    static, affords no gesture) or ``active_window`` (solved this window, not yet
    frozen). None on a monolithic bar (there is no rolling frozen zone), so the
    board renders it exactly as before.
  * ``ScheduleDocument.rolling`` — a ``RollingBlock`` carrying the window metadata
    (frozen-front boundary, active-window span, reference origin) and the
    BEYOND-HORIZON list: admitted-but-unscheduled future work (known Demands with
    no placement yet — id, name, due, and a cheap earliest-window estimate when
    derivable, else absent). None on a monolithic document.
  * The COMPLETENESS INVARIANT (the anti-silent-exclusion clause, docs/01 /
    the Glass Box audit): every schedulable Demand in the snapshot appears in the
    document EXACTLY ONCE — as a committed placement, an active-window placement,
    a beyond-horizon tray entry, or (if the gate excluded it) a certificate-
    visible exclusion. A Demand in none of these is a defect. The rolling
    assembler enforces it; ``test_rolling_document`` counts.
  MINOR: every field is additive with a None/empty default; a 1.6 consumer
  ignores ``rolling`` and reads ``commitment_state`` as absent.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, model_validator

from mre.contracts.vocabularies import ScheduleStatus

CONTRACT_VERSION = "1.7"

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
    reason: Optional[str] = None               # exception reason for a non-regular
    #                                            window (planned_maintenance / holiday
    #                                            / breakdown / overtime); None on a
    #                                            base-pattern regular window (1.6). Lets
    #                                            the cockpit render a planned-maintenance
    #                                            closure distinctly and name it in the
    #                                            downtime hover. UNPLANNED (observed)
    #                                            downtime is NOT sourced here — there is
    #                                            no observed-actuals doorway yet (a named
    #                                            debt, docs/04 4.2); only calendar-declared
    #                                            exceptions carry a reason.


class ResourceLane(BaseModel):
    """One Gantt row: a Resource plus its flattened Calendar."""
    resource_id: str                           # canonical UUID
    external_name: Optional[str] = None        # customer vocabulary
    facility: Optional[str] = None
    pool: Optional[str] = None                 # pool external name if mapped
    calendar_windows: list[CalendarWindow] = []
    booked_through: Optional[datetime] = None  # last assignment end on this row (1.6):
    #                                            the moment it is booked through; None
    #                                            when the row carries no work. Computed
    #                                            via row_intelligence over the same
    #                                            flattened windows the solver uses.
    next_open_gap: Optional[datetime] = None   # earliest open, unbooked minute at/after
    #                                            the reference date (1.6) — the next slot
    #                                            the row could take work; None when none
    #                                            exists in-horizon. Visible-window
    #                                            utilization is recomputed client-side as
    #                                            the planner pans (same arithmetic).


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
    standing_pin: bool = False                 # a still-held accepted commitment
    #                                            on this lineage (R-DP8, 1.5): the
    #                                            board marks it and never lists it
    #                                            as a moved consequence
    commitment_state: Optional[Literal["committed", "active_window"]] = None
    #                                            rolling-horizon state (1.7): the
    #                                            frozen front commits (``committed``
    #                                            — locked, static, no gesture) while
    #                                            the rest of the current window is
    #                                            ``active_window`` (solved, not yet
    #                                            frozen). None on a monolithic bar —
    #                                            there is no rolling frozen zone, so
    #                                            the board renders it unchanged.


class ServiceOutcomeBlock(BaseModel):
    """Per-Demand service truth (via Fulfillments; never per WorkPackage)."""
    demand_ref: str                            # canonical UUID
    work_order: Optional[str] = None           # external
    customer_ref: Optional[str] = None         # canonical UUID
    customer_name: Optional[str] = None        # external customer vocabulary (1.6):
    #                                            resolved via the identity map so the
    #                                            job-card hover never shows a UUID; None
    #                                            when the demand has no customer or it
    #                                            does not resolve.
    quantity: Optional[float] = None           # Demand.quantity value (1.6) — surfaced
    #                                            for the job-card hover; None when absent.
    quantity_uom: Optional[str] = None         # its unit of measure (1.6), e.g. "ea".
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
    scenarios).

    Contract 1.3 (session 3.2a, R-T1a): ``source`` distinguishes the two
    Tier-1 ghost sources — ``pool`` (near-optimal placements, the cheap
    options) and ``forced_alternative`` (a targeted re-solve carrying a
    "not on the incumbent machine" cut, giving the TRUE best price of a road
    not taken). Forced-alternative members additionally name the op they moved,
    the machine forbidden, and the machine it landed on — the priced
    cross-machine ghost's identity."""
    is_pool_member: bool = True
    pool_id: str
    base_schedule_id: str
    member_index: int
    objective: Optional[float] = None          # solver objective (scaled units)
    objective_delta_pct: Optional[float] = None  # vs the incumbent's objective
    source: Literal["pool", "forced_alternative"] = "pool"
    target_operation_ref: Optional[str] = None   # forced: the op moved off its machine
    forbidden_resource_ref: Optional[str] = None  # forced: the incumbent machine cut
    alternative_resource_ref: Optional[str] = None  # forced: where it landed


class OperationInteraction(BaseModel):
    """Per-operation Tier-0 facts the client needs to shade legal drop zones
    without a solver (contract 1.2, docs/04 R-DP6). ``eligible_resource_ids``
    is the set the SOLVER would give an op_assign literal — capability
    resolution AND (for a resumable op) the same calendar feasible-window prune
    the builder applies, computed through the shared ``eligibility`` module so
    Tier-0 can never green a row the R-DP1 pin would silently skip (contract
    1.4, docs/04 Session 4.0b). ``working_min``/``setup_min`` size the bar for a
    fit/displace test; ``earliest_start`` is the release floor; the precedence
    graph (separate ``precedence_edges`` list) supplies the predecessor-finish
    floor."""
    operation_ref: str                         # canonical UUID
    eligible_resource_ids: list[str] = []      # canonical UUIDs (solver-pinnable set)
    dim_reasons: dict[str, str] = {}           # resource_id → dim reason for a
    #                                            capability-eligible resource the
    #                                            solver still refuses a literal
    #                                            ("no_calendar_window"/"wip_fixed"),
    #                                            so Tier-0's hover reads the truth
    #                                            (contract 1.4, Session 4.0b)
    working_min: int = 0                        # run working minutes (sum of chunks)
    setup_min: int = 0                          # setup minutes prefixed to the run
    earliest_start: Optional[datetime] = None  # release floor (demand.release)
    resumable: bool = False                     # splittable: may span calendar
    #                                             closures (Tier-0 window-fit
    #                                             input, contract 1.3 / CU2)


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


class BeyondHorizonItem(BaseModel):
    """One admitted-but-unscheduled future job (contract 1.7): known work with
    no placement yet — it has no bar to draw, so it lives in the board's tray.
    The tray is the ghost-job answer at board level: known work is ALWAYS visible
    somewhere, so no schedulable demand can be silently invisible (the Glass Box
    cardinal danger)."""
    demand_ref: str                            # canonical UUID
    work_order: Optional[str] = None           # external (customer vocabulary)
    customer_name: Optional[str] = None        # external customer, via identity map
    due: Optional[datetime] = None
    earliest_window_estimate: Optional[datetime] = None
    #                                            a CHEAP, honest estimate of when
    #                                            this work must first enter a
    #                                            scheduling window (its
    #                                            latest-feasible-start, clamped to
    #                                            the reference origin); None when
    #                                            not derivable (no due). It is an
    #                                            estimate, never a placement — the
    #                                            AI answer hedges accordingly.


class RollingBlock(BaseModel):
    """The rolling-horizon (sliced) metadata (contract 1.7, R-SC2). Present only
    on a rolling document; None on a monolithic one. The document renders the
    plant AS OF ``reference_origin`` — the current planning moment — so the board
    shows the current window (committed frozen front + active-window work) and the
    tray shows everything beyond it."""
    reference_origin: datetime                 # the roll's t0 (the current moment)
    window_start: datetime                     # the current window [t0, t0+window)
    window_end: datetime
    frozen_until: datetime                     # the frozen-front boundary: work
    #                                            starting before this is committed;
    #                                            the board draws a labeled marker here
    window_days: int
    frozen_days: int
    committed_count: int = 0                   # bars in the ``committed`` state
    active_count: int = 0                      # bars in the ``active_window`` state
    beyond_horizon: list[BeyondHorizonItem] = []   # the tray (may be empty)


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
    rolling: Optional[RollingBlock] = None           # contract 1.7 (sliced world);
    #                                                  None on a monolithic document

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
- 1.8 (2026-07-23, Session 4B.3c): additive — a ROLLING document now carries the
  ``interaction`` (Tier-0 legality) payload for its ACTIVE WINDOW, so the cockpit
  can shade legal drop zones and target a gesture on a sliced board exactly as it
  does on a monolithic one. No new field: ``interaction`` has been an optional
  block since 1.2 (delivered via the split ``/interaction`` endpoint since 1.3) and
  was simply None on rolling documents until now. Committed (frozen-front) bars and
  the beyond-horizon tray remain non-targets — the client reads
  ``commitment_state`` and never offers a gesture on a committed bar. Underneath,
  the rolling run now persists its window-0 solve as a first-class canonical run
  (assignments / service outcomes / evidence), so the Tier-2 sandbox and the M10
  Explainer read it exactly as a monolithic run (the connector-era prerequisite the
  4B.3a/4B.3b debts named). A monolithic document is byte-unchanged apart from the
  version string; a 1.7 consumer ignores nothing new (the field already existed).
  MINOR.

* **1.9** (Session 4B.6) — THE COARSE ZONE (R-SC2 amendment): beyond-horizon
  demand is coarsely PLACED rather than merely listed. Additive only. A rolling
  document gains ``rolling.coarse_zone`` (``CoarseZoneBlock``: the declared
  bucket length and derate rho WITH THEIR PROVENANCE, the bucket grid, per-run
  status, and the per-resource-per-bucket density band) and each tray entry
  gains ``coarse`` (``CoarsePlacementBlock``: its bucket, a resource
  FEASIBILITY WITNESS, coarse tardiness in BUCKETS, and the run label the figure
  came from). Both are Optional and None when the coarse zone did not run.
  ``earliest_window_estimate`` is UNCHANGED — it remains the due-date backoff
  heuristic it has been since 1.7, and the coarse bucket sits beside it rather
  than overwriting it (a 4B.6 pre-flight found the heuristic already populated
  on every tray entry with a due date; filling it from the coarse bucket would
  have repurposed a live field, which CLAUDE.md forbids). A MONOLITHIC document
  is byte-unchanged apart from the version string: it has no beyond-horizon set,
  so ``rolling`` is None and the whole block is simply absent. Coarse currency
  never appears — coarse tardiness is counted in buckets, so no consumer can sum
  it into ``cost_summary`` (clause 5, enforced by shape). MINOR.

* **1.10** (Session 4B.8 CU3) — THE TWO PROOFS, SEPARATED. An R-SC3 solve proves
  two different claims and the document conflated them. ``solver.status`` carried
  STAGE 2's status — the TIEBREAK proof ("no equally-cheap schedule starts
  earlier") — while the ledger beside it was the product of STAGE 1's COST proof
  ("no cheaper schedule exists"). Stage 2 exhausts its budget above roughly eight
  orders, so in practice every rolling board read FEASIBLE over a ledger that was
  provably OPTIMAL: for a product whose thesis is provable numbers, the UI
  contradicted the strongest claim it had.

  ``solver.status`` now carries STAGE 1's status — the COST proof, which is what
  a planner asking "is this optimal?" means. Two Optional fields are ADDED:
  ``solver.tiebreak_status`` (stage 2's status, None when stage 2 never ran) and
  ``solver.tiebreak_skipped_reason`` (why, when it did not — so a tiebreak that
  silently did not run is distinguishable from one that ran and won nothing).
  A schedule whose cost is proven optimal now SAYS SO, and an unproven tiebreak
  never downgrades that claim.

  Additive in SHAPE, but note the honest caveat: the MEANING of the existing
  ``status`` field changes on any two-stage run, which is why this is a recorded
  RULING (docs/04, 2026-07-28) and not a bug fix — which of the two statuses "the
  solve status" meant had simply never been decided. A 1.9 consumer keeps reading
  ``status`` and gets a strictly more accurate answer. Monolithic documents are
  byte-unchanged apart from the version string and the added optional fields
  (verified: the sample_data goldens reproduce byte-for-byte). MINOR.

* **1.11** (Session 4B.11 CU3) — THE TARDINESS SPLIT (R-PD1 clause (4)). Once
  past-due demand is SCHEDULED rather than excluded (R-PD1 clause (1)), a single
  tardiness number stops being readable: the pilot book's minimum due date is
  −1573 days, so one such order's unavoidable lateness would swamp every figure
  on the board — and every delta card would attribute it to whatever the planner
  last touched. ``cost_summary`` gains two Optional fields that DECOMPOSE the
  existing ``tardiness`` rather than adding to it:

    ``tardiness_floor``        max(0, t0 − due) priced — UNAVOIDABLE
    ``tardiness_controllable`` completion − max(due, t0) priced — this schedule's

  They are present TOGETHER or not at all, and when present sum to ``tardiness``
  to the cent (enforced in ``CostSummary``). They are absent on any book with no
  past-due demand — which is every monolithic fixture we own — so those documents
  are byte-identical to their 1.10 selves apart from the version string.
  ``ServiceOutcomeBlock`` gains the same pair per demand, on the same
  present-only-when-non-zero rule.

  The floor provably cannot change the argmin, and not by assertion: the solver
  has ALWAYS priced the controllable part alone (``solver_builder`` clamps
  ``due_min = max(0, due − horizon_start)``, so a past-due fulfillment's
  objective term is measured from t0), while the extractor has always priced
  lateness from the DECLARED due date. The split does not change the model; it
  makes a decomposition the pipeline already contained legible. MINOR.

1.12 (Session 4B.14 Item 4) — ``AssignmentBlock.splittable`` and
  ``min_chunk_min``: the R-C3 interruptibility class the SOLVER applied to this
  operation, and its minimum-piece floor. Both Optional, both absent on a
  document assembled before this, so every 1.11 reader is unaffected and a
  monolithic golden built without them is byte-identical to its 1.11 self.

  WHY THE DOCUMENT NEEDS THEM. They are what decides whether an operation can
  take a short window, which is what put ORD-000013's op20 on Thursday: it needs
  7h11m in one piece and PAINT-01 had 4h54m left. Confirming that from the
  cockpit meant zooming the board and counting pixels, and the job card — the
  one surface built to answer "what is this bar" — could not say it. The board
  already renders the CONSEQUENCE (a chunked bar, since 4B.13); this states the
  RULE that produced it. MINOR.

1.13 (Session 4B.25, R-BK1) — ``solver.portfolio`` (``PortfolioBlock``): the
  DECLARATION that this schedule is the best of K seeded deterministic searches,
  with K, the per-member deterministic budget, their provenance, and EVERY
  member's ledger total beside the winner's.

  WHY THE DOCUMENT NEEDS IT. A board produced by a portfolio is a different
  object from a board produced by one search, and the difference is not
  cosmetic: the losing members' totals are the CROSS-SEED SPREAD, which is the
  stability figure 4B.12 named as the honest companion to the gap. A 92.4%-gap
  board whose five searches all landed on the same total and one whose five
  spread 16% apart are in completely different positions, and before this the
  document could not tell them apart. Clause (4) of R-BK1 is what makes the
  spread free: those searches have already run.

  ``portfolio`` is Optional and is ABSENT AT K=1 — not present-and-empty, and
  not a block declaring a portfolio of one. K=1 IS the pre-1.13 behaviour, so
  every existing golden, digest and pinned world is byte-identical apart from
  the version string (the rolling determinism golden hashes PLACEMENTS, and is
  unmoved). The absent-by-construction discipline is 4B.24's, on the delta
  card's missing re-optimization row: a block claiming a portfolio nobody ran
  would be a measurement nobody took. MINOR.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, model_validator

from mre.contracts.vocabularies import ScheduleStatus

CONTRACT_VERSION = "1.13"

# Exact decomposition tolerance: cost components are currency values
# accumulated in float; "exactly" means to the cent, matching the
# consolidator's rollup check and the scenario diff's _decomp_ok.
_DECOMP_TOLERANCE = 0.01


class HorizonBlock(BaseModel):
    """The solver builder's planning horizon (recorded in M5 run evidence)."""
    start: datetime
    end: datetime


class PortfolioMemberBlock(BaseModel):
    """One member of a declared portfolio: a seeded deterministic search and the
    LEDGER total it reached. ``ledger_total`` is None on a member that could not
    be published (it did not finish, produced no ledger, or was stopped by the
    wall rather than by its deterministic budget) — and such a member still
    appears, with ``reason`` saying which, because dropping it silently would
    make the spread look tighter than the evidence supports (R-BK1 clause 4)."""
    seed: int
    ledger_total: Optional[float] = None
    status: str = ""
    det_consumed: Optional[float] = None
    wall_time_s: Optional[float] = None
    selectable: bool = True
    reason: str = ""


class PortfolioBlock(BaseModel):
    """R-BK1 (contract 1.13) — THE DECLARED PORTFOLIO.

    Present only when K > 1. ``k`` and ``det_time_s`` are the declared
    coefficients with their provenance, exactly as the coarse zone declares rho:
    a defaulted K must never read as a customer's choice. ``winner_seed`` is the
    member this document was built from — selection is by the LEDGER (never the
    raw objective, 4B.7's lesson), ties broken by lowest seed, so the whole
    portfolio is a pure function of a fixed set.

    ``spread_abs`` / ``spread_pct`` are None below two publishable members: a
    spread of one number is not a spread, and printing 0.00 there would claim an
    agreement nobody observed (``partitions()``'s tri-state, 4B.21)."""
    k: int
    k_provenance: Literal["declared", "defaulted"] = "defaulted"
    det_time_s: float
    det_time_s_provenance: Literal["declared", "defaulted"] = "defaulted"
    seed0: int
    workers: int = 1
    execution: Literal["sequential", "processes"] = "sequential"
    declaration: str = ""
    agreement: str = ""
    unpublished: str = ""
    winner_seed: Optional[int] = None
    winner_ledger_total: Optional[float] = None
    spread_abs: Optional[float] = None
    spread_pct: Optional[float] = None
    members: list[PortfolioMemberBlock] = []
    wall_time_s: float = 0.0


class SolverBlock(BaseModel):
    """M6 RunContext telemetry for the solve that produced this schedule."""
    # THE COST PROOF (contract 1.10, Session 4B.8 CU3). An R-SC3 solve proves two
    # different things and this field carries the one a planner is asking about:
    # "is there a cheaper schedule?". Before 1.10 it carried STAGE 2's status —
    # the tiebreak proof — so a board whose cost was provably OPTIMAL read
    # FEASIBLE, understating the strongest claim the product can make.
    status: str                                # OPTIMAL | FEASIBLE
    objective: Optional[float] = None
    gap: Optional[float] = None
    wall_time_s: float = 0.0
    deterministic: bool = False                # workers pinned to 1 + seed set
    # THE TIEBREAK PROOF (contract 1.10): stage 2's status — "is there an equally
    # cheap schedule that starts earlier?". Optional and routinely weaker than
    # the cost proof, because stage 2 exhausts its budget on most real instances.
    # An unproven tiebreak NEVER downgrades the cost claim. None when stage 2 did
    # not run at all, in which case tiebreak_skipped_reason says why — a tiebreak
    # that silently did not run must not look like one that ran and won nothing.
    tiebreak_status: Optional[str] = None
    tiebreak_skipped_reason: Optional[str] = None
    # THE PORTFOLIO (contract 1.13, R-BK1). Absent at K=1 — which is the default
    # and is exactly the pre-1.13 behaviour. Everything above describes the
    # WINNING member; this says how many others there were and what they found.
    portfolio: Optional[PortfolioBlock] = None


class CostSummary(BaseModel):
    """The cost ledger, decomposed. Must satisfy exact decomposability."""
    total: float
    production_regular: float
    production_overtime: float
    setup: float
    tardiness: float
    # THE TARDINESS SPLIT (contract 1.11, Session 4B.11 CU3, R-PD1 clause (4)).
    # `tardiness` above is unchanged and still the whole tardiness charge; these
    # DECOMPOSE it rather than adding to it, so `total`'s decomposition is
    # untouched and a 1.10 consumer reads exactly what it read before.
    #
    #   tardiness_floor        = max(0, t0 − due) priced — UNAVOIDABLE. Already
    #                            accrued when the horizon opened; no schedule can
    #                            recover it and no planner's move can be blamed
    #                            for it.
    #   tardiness_controllable = completion − max(due, t0) priced — what THIS
    #                            schedule added.
    #
    # Both are None on a book with NO past-due demand, which is every monolithic
    # fixture we own: the split is present exactly when there is something to
    # split, so an on-time run's document is byte-identical to its 1.10 self.
    # Present-or-absent TOGETHER; when present they sum to `tardiness` to the
    # cent, and the validator below enforces it.
    tardiness_floor: Optional[float] = None
    tardiness_controllable: Optional[float] = None
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
        # Contract 1.11 — the split is all-or-nothing and exact. A half-present
        # split would let a reader infer the missing side by subtraction from a
        # number nobody asserted; an inexact one would let floor tardiness leak
        # into a delta card's money, which is the whole thing clause (4) forbids.
        f, c = self.tardiness_floor, self.tardiness_controllable
        if (f is None) != (c is None):
            raise ValueError(
                "cost_summary tardiness split is half-present: "
                f"tardiness_floor={f}, tardiness_controllable={c} — both or "
                "neither."
            )
        if f is not None and abs(self.tardiness - (f + c)) > _DECOMP_TOLERANCE:
            raise ValueError(
                f"tardiness does not decompose: tardiness={self.tardiness} but "
                f"floor+controllable={f + c}"
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
    splittable: Optional[bool] = None           # 1.12 (Session 4B.14 Item 4): the
    #                                             R-C3 interruptibility class as the
    #                                             SOLVER applied it, and its floor.
    min_chunk_min: Optional[float] = None       # These are what decide whether an
    #                                             operation can take a short window
    #                                             — the fact that put ORD-000013's
    #                                             op20 on Thursday — and confirming
    #                                             it previously meant zooming the
    #                                             board and counting pixels. Both
    #                                             Optional and absent on a document
    #                                             built before this, so a 1.11
    #                                             reader is unaffected.
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
    # THE TARDINESS SPLIT, per demand (contract 1.11, R-PD1 clause (4)). Present
    # only on a demand that was ALREADY LATE at the reference date; absent (None)
    # for every demand due on or after t0, so an on-time book's outcomes are
    # byte-unchanged. `tardiness_floor_cost` decomposes `tardiness_cost`; the
    # controllable remainder is the difference, and the two are never fused in an
    # answer or a delta card. `tardiness_floor_min` is the same fact in minutes —
    # the honest unit for "how late was this before we touched it".
    tardiness_floor_min: Optional[int] = None
    tardiness_floor_cost: Optional[float] = None


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


class CoarseBucket(BaseModel):
    """One coarse-zone bucket (contract 1.9, R-SC2 coarse-zone amendment). Fixed
    length, DECLARED not hardcoded (``CoarseZoneBlock.bucket_days``), spanning
    from the active-window end to the last beyond-horizon due date plus a
    capacity-sized tail."""
    index: int
    start: datetime
    end: datetime


class CoarseDensityCell(BaseModel):
    """Load against DERATED capacity for one resource in one bucket.

    CLAUSE (6) — COARSE NEVER RENDERS AS A BAR. Bars mean placement; this is
    LOAD. The cockpit draws these as a density band per resource per bucket:
    different epistemic status, different visual grammar. ``load_minutes`` and
    ``capacity_minutes`` are both carried so the reader checks the arithmetic
    rather than trusting an adjective."""
    resource_id: str
    bucket_index: int
    load_minutes: int
    capacity_minutes: int                      # already DERATED by rho
    utilization: float                         # load / capacity, 0.0 when cap==0


class CoarsePlacementBlock(BaseModel):
    """One beyond-horizon demand's COARSE placement (contract 1.9).

    A coarse placement is an ALLOCATION TO A BUCKET, never a schedule. It comes
    from a relaxation of the fine model whose only claimed direction is the
    negative (coarse-infeasible ⇒ fine-infeasible), so every consumer — the
    cockpit, the AI layer — must present it as an estimate carrying its
    ``run_label``, never as a placement.

    ``resource_witness`` is a FEASIBILITY WITNESS, NOT A PLAN. It exists because
    per-resource capacity cannot be checked honestly without deciding which
    resource's bucket budget an op consumes. It is not rendered as an
    assignment, and the fine solve re-decides it freely."""
    start_bucket_index: int                    # earliest bucket any of its ops occupies
    start_bucket_start: datetime               # → "when will ORD-X start?" (an ESTIMATE)
    start_bucket_end: datetime
    completion_bucket_index: int               # the terminal op's bucket
    resource_witness: str                      # WITNESS, never a plan (see above)
    coarse_tardiness_buckets: int              # BUCKETS, never currency (clause 5)
    run_label: str                             # "proof" | "planning" — clause (2)
    sub_disposition: str                       # coarsely_placed | coarse_unmodelable
    unmodelable_reason: Optional[str] = None   # named, never a silent drop
    #                                            resumable_out_of_scope |
    #                                            exceeds_bucket_capacity |
    #                                            no_eligible_resource


class CoarseZoneBlock(BaseModel):
    """The coarse zone's run-level facts (contract 1.9, R-SC2 amendment).

    CLAUSE (3): ``capacity_derate`` (rho) and ``bucket_days`` are DECLARED IDS
    coefficients (docs/06 §5.9), and each carries its provenance — a defaulted
    value can never read as a customer's choice.

    CLAUSE (5) — TWO LEDGERS, NEVER FUSED: coarse tardiness is reported in
    BUCKETS and there is no currency field here at all, so no caller can add it
    to ``cost_summary`` by accident. The shape enforces the discipline."""
    bucket_days: int
    bucket_days_provenance: str                # "declared" | "defaulted"
    capacity_derate: float                     # rho
    capacity_derate_provenance: str            # "declared" | "defaulted"
    buckets: list[CoarseBucket] = []
    proof_status: str                          # OPTIMAL | FEASIBLE | INFEASIBLE | UNKNOWN
    planning_status: str
    planning_mirrors_proof: bool = False       # rho == 1.0 ⇒ copied, not re-solved
    # CLAUSE (1)+(2): True only when the PROOF run (rho = 1.0) returned a
    # COMPLETE (not wall-truncated) INFEASIBLE. This is the only field that
    # licenses "this cannot fit", and it licenses the NEGATIVE only — the
    # converse is never asserted anywhere.
    infeasibility_proven: bool = False
    tardiness_buckets_total: int = 0
    # True when a run stopped at FEASIBLE rather than OPTIMAL: its objective and
    # tardiness figures are UPPER BOUNDS, and every surface must say so.
    figures_are_upper_bounds: bool = False
    wall_truncated: bool = False
    unmodelable_count: int = 0
    density: list[CoarseDensityCell] = []
    binding_cells: list[CoarseDensityCell] = []   # at/near capacity → "why is week N full?"


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
    # Contract 1.9 (R-SC2 coarse-zone amendment): the COARSE placement, when the
    # coarse zone ran. DISTINCT from earliest_window_estimate above, which stays
    # exactly what it has always been — a due-date backoff heuristic. The two are
    # different figures from different methods and are never fused: a 4B.6
    # pre-flight found the heuristic already populated on every tray entry with a
    # due date, so filling it from the coarse bucket would have silently
    # repurposed a live field (CLAUDE.md: add, never repurpose).
    coarse: Optional[CoarsePlacementBlock] = None


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
    # Contract 1.9: the coarse zone over the tray. None when the coarse zone did
    # not run (it is opt-in per solve), so a 1.8-shaped rolling document remains
    # exactly what it was.
    coarse_zone: Optional[CoarseZoneBlock] = None


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

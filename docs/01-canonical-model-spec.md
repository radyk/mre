# Canonical Manufacturing Model — Specification

**Document 1 of 3** · Status: Draft v0.1 (living document) · Companion documents: *Evidence Contract Specification*, *PoC Plan*

---

## 1. Purpose

This document defines the canonical manufacturing model: the permanent, ERP-independent representation of manufacturing reality that sits at the center of the platform. It is the shared language used by the optimizer, the AI reasoning layer, validation, reporting, and all future integrations.

The platform is a **manufacturing reasoning engine**, not an ERP scheduling engine. The AI reasons about operations, resources, constraints, costs, and tradeoffs regardless of how those concepts are represented in any underlying ERP.

## 2. The three-model architecture

The platform is built around three distinct models, each with a single responsibility:

| Model | Responsibility | Lifetime |
|---|---|---|
| **ERP Model** | Source-system tables, field names, identifiers (QuickBooks, SAP, Epicor, Oracle, …). Implementation details. | External; never crosses the boundary |
| **Canonical Manufacturing Model** | How manufacturing actually works. The permanent source of truth. | Persistent, versioned via snapshots |
| **Solver Model** | Temporary mathematical representation for OR-Tools (intervals, variables, objectives). | Discarded after each solve |

### Pipeline

```
ERP ──► ERP Adapter ──► Canonical Model ──► Validation ──► Solver Builder ──► OR-Tools
              │               ▲    │             │              │                │
              │               │    └─────────────┼──────────────┼── mapping ──► Solution Extraction
              │               │                  │              │                │
              │               └── canonical Schedule ◄──────────┼────────────────┘
              │                                  │              │
              ▼                                  ▼              ▼
        ═══════════════════ Evidence Reporter (all stages write) ═══════════════════
                                          │
                                          ▼
                            AI Explanation ──► Planner / ERP
```

Key corrections to the naive linear pipeline:

1. **The solution flows back into the canonical model.** The Solver Builder produces the CP-SAT model *plus a variable↔entity mapping table*. Solution Extraction uses that mapping to translate results into a canonical **Schedule**. Only then is the solver model discarded. The mapping table is the one piece of solver-adjacent state that must survive the solve.
2. **The Evidence Reporter is a cross-cutting service, not a pipeline stage.** Every module writes to it as it runs (see Document 2).
3. **Validation is layered.** ERP-shape checks happen in the adapter; semantic checks happen at the canonical gate; joint-infeasibility checks happen at solve time. Same Finding schema at all three layers.
4. **The AI layer reads exactly two things:** the canonical model (including Schedules) and the evidence store. Never ERP shapes, never solver internals.

### Symmetry principle

The ERP Adapter and the Solver Builder are the same kind of thing: translators protecting the canonical model from an external vocabulary. New ERP = new inbound adapter. New optimization engine = new outbound builder. The canonical model never knows either exists.

## 3. Canonicity rules

### 3.1 Litmus tests for admitting a concept

A concept becomes canonical only if it passes **both**:

1. **Is this a fundamental manufacturing concept, or an ERP implementation detail?** Sales Orders, Work Orders, Routing Codes, Machine IDs, Work Center Codes are ERP details, translated at the adapter.
2. **Does the scheduling or reasoning core need to act on it?** The canonical model is the *minimal* set of concepts the reasoning engine acts on — not a universal manufacturing ontology.

Anything the core does not act on but might matter later travels as opaque attributes attached to canonical entities — preserved and queryable, but not modeled.

### 3.2 Anti-leakage defenses

- The core imports only canonical types.
- ERP-native identifiers appear in core records **only** inside the designated `external_refs` field.
- Every proposed concept passes the two litmus tests in review.
- Portability is proven by the second adapter, not designed in the abstract; the PoC builds against one real adapter with the discipline that nothing ERP-specific crosses the line.

### 3.3 Living document governance

The entity vocabulary is a living document. New concepts may be added through review; existing concepts are never silently repurposed. Every addition records the consumer that justified it.

## 4. Universal conventions

Every canonical entity carries:

| Field | Meaning |
|---|---|
| `id` | System-minted identifier, stable across snapshots (same real-world thing ⇒ same id) |
| `snapshot_id` | The snapshot this entity version belongs to |
| `external_refs` | List of source-system identifiers (`{system, type, value}`) — the **only** place ERP IDs may appear |

Every attribute on every entity has a provenance record (Section 7).

### 4.1 Snapshot semantics

- The canonical model is versioned via **snapshots**. Every run (validation, planning, solve, explanation) executes against an identified snapshot; no run operates on "current state."
- Every evidence record references the snapshot it was produced against.
- Demands and other observed entities are **immutable within a snapshot**; change arrives only as a new snapshot.
- Identity resolution (recognizing today's extract row as the same entity as yesterday's) is adapter responsibility. Material changes to a persisted identity raise an `IDENTITY_CHANGED` finding.
- Derived entities (WorkPackages) are re-derived each snapshot, **except** those in frozen or later states, which persist; their mappings update instead (see 5.2).

## 5. The spine entities

### 5.1 Demand — *what is wanted; immutable observation*

Absorbs: sales orders, work orders, forecasts, safety-stock triggers.

| Attribute | Type | Notes | Expected provenance |
|---|---|---|---|
| `product_ref` | entity ref | Must resolve to a Product | observed |
| `quantity` | number + UoM | **Never fused into durations** | observed |
| `due` | timestamp | Real datetime; solver-time conversion is the Solver Builder's job | observed |
| `earliest_start` | timestamp, optional | Material availability / release proxy | observed or defaulted |
| `commitment_class` | enum: `standard` / `rush` / `firm` | Canonicalizes rush/must-do semantics into one ladder | observed or defaulted |
| `customer_weight` | number | Tardiness weight; the AI must know when defaulted | observed, often defaulted |
| `customer_ref` | entity ref, optional | Enables per-customer service reporting | observed |
| `status` | enum: `open` / `cancelled` / `fulfilled` | Drives re-derivation rules across snapshots | observed |
| `wip_operations` | list of WipOperationObservation | Observed shop-floor execution state of this order's operations at reference_date (docs/06 §5.13). Empty ⇒ no WIP source ⇒ blank slate. Each observation is `{sequence, spec_ref, status (not_started/in_progress/complete), actual_start?, actual_resource_ref?, remaining_minutes?, quantity_complete?, source_rows}` — canonical ids only, ERP identifiers never appear. | observed (cites the wip_status.csv source rows); defaulted when no WIP source |

Demands are never mutated by planning. They are observations — WIP included: `wip_operations` is what the plant reported was already underway, not anything the planner chose.

### 5.2 WorkPackage — *what we plan to do; derived and owned by us*

The unit of planning and scheduling. The only thing the Solver Builder ever sees.

| Attribute | Type | Notes |
|---|---|---|
| `product_ref` | entity ref | Inherited from constituent Demands (must agree) |
| `quantity` | number + UoM | Derivation policy recorded on the creating Decision |
| `earliest_start` | timestamp | Max of constituents' earliest_start; policy-recorded |
| `operations` | ordered list of Operation ids | Instantiated from the Product's Process at creation; records Process version used |
| `state` | enum: `planned` / `frozen` / `in_progress` / `complete` | `frozen`+ survives re-derivation on new snapshots. `in_progress` / `complete` are the WIP seam (docs/06 §5.13): the Planner rolls the constituent operations' observed statuses up to this field — all complete ⇒ `complete`, any underway or partial ⇒ `in_progress` — with observed provenance citing the wip_status.csv source rows. `planned` when no WIP source. |
| `created_by` | Decision ref | Every WorkPackage traces to the planning decision that made it |

Deliberately absent: **no due date** (lives on Demands, felt via Fulfillments) and **no priority** (derived at solve time from constituent Demands).

**Change-after-batching rule:** on a new snapshot, WorkPackages are re-derived except frozen+ ones. If a constituent Demand of a frozen WorkPackage is cancelled or changed, the Fulfillment mapping updates and a `BATCH_CONFLICT` finding is raised with a disposition (e.g., excess becomes stock; or the WorkPackage shrinks if not yet started).

### 5.3 Fulfillment — *the explicit Demand ↔ WorkPackage mapping*

A first-class entity, not a foreign key.

| Attribute | Type | Notes |
|---|---|---|
| `demand_ref` | entity ref | |
| `workpackage_ref` | entity ref | |
| `allocated_quantity` | number + UoM | Partial allocation deferred; full quantity for PoC |
| `decision_ref` | Decision ref | The planning decision that created this mapping |

Cardinalities express every planning move with zero additional concepts:

| Situation | Mapping shape |
|---|---|
| Plain job | 1 Demand → 1 WorkPackage |
| **Batching** | many Fulfillments → 1 WorkPackage |
| **Splitting** | 1 Demand → many WorkPackages |
| **Make-to-stock** | WorkPackage with no Fulfillments (yet) |

### 5.4 Operation — template and instance

**Structural decision:** the Process owns **OperationSpecs** (quantity-independent templates). When the Planner creates a WorkPackage, each spec is **instantiated** as an Operation — the schedulable unit with computed durations. This is where quantity × rate becomes duration, as a derived attribute with a recorded derivation chain.

**Operation (instance):**

| Attribute | Type | Notes |
|---|---|---|
| `spec_ref` / `workpackage_ref` | entity refs | Lineage to template and owner |
| `sequence` | int | Position within the WorkPackage; precedence itself lives on PrecedenceEdge (below), not here |
| `resource_requirements` | list of ResourceRequirement | See 5.5 |
| `setup_family` | code | Feeds sequence-dependent transition Constraint |
| `setup_duration` | duration | Derived (spec + family) or observed |
| `run_duration` | duration | **Derived**: quantity × spec rate; chain recorded |
| `splittable` / `min_chunk` | bool / duration | Canonical home of preemption & min-split policy |
| `wip_status` | enum: `not_started` / `in_progress` / `complete`, optional | Observed execution state at reference_date (docs/06 §5.13), projected by the Planner from the owning Demand's `wip_operations`. None ⇒ no observation (blank slate). | observed; defaulted when absent |
| `observed_start` / `observed_resource_ref` | timestamp / entity ref, optional | For `in_progress` and `complete` ops: where and when the operation actually ran. | observed (cites wip_status.csv rows) |
| `remaining_duration` | duration, optional | Working time left at reference_date. `complete` ⇒ 0. `in_progress` ⇒ the plant's observed `remaining_minutes` (observed) **or** `(quantity − quantity_complete) × run_rate` (derived — the remainder arithmetic). Consumed by the Solver Builder to size the fixed in-flight interval (docs/06 §5.13). | observed or derived per basis; defaulted when absent |

No `predecessors` list and no `dwell_duration` (docs/05 §4 surgery, R-A2/A3, R-Dwell — see 5.4a). Phases occupy resources; lags don't.

**WIP landing (docs/06 §5.13).** The observed shop-floor state enters on the Demand as `wip_operations` (an immutable observation) and the Planner projects it onto the Operations it instantiates and onto WorkPackage.state. Provenance is truthful: observed actuals cite the wip_status.csv source rows; the computed remaining duration is derived where it is arithmetic (quantity_complete basis) and observed where the plant reported it directly (remaining_minutes basis) — a constant under an observed sidecar is the yield_factor defect class (docs/04 2026-07-12), never repeated. WIP is projected only for 1:1 (identity_v1) WorkPackages; a merged operation corresponds to no single order's in-flight op, so its actuals would be ambiguous (the observation still lives on each constituent Demand).

### 5.4a PrecedenceEdge — precedence and lags as first-class records

**Structural decision (docs/05 R-A2/A3):** lags are properties of the *relationship* between two operations, not of either operation individually — this is what survives non-linear routings and matches how the constraint is actually spoken ("max 4 hours between coating and curing"). Precedence is therefore not an implicit `sequence`-order convention; it is an edge record.

| Attribute | Type | Notes |
|---|---|---|
| `predecessor` / `successor` | OperationSpec refs | **Template-level**, not instance-level: one edge set per Process, reused by every WorkPackage that instantiates it. Resolved to concrete Operations via `spec_ref` at solve-build time. |
| `min_lag` | duration, default 0 | Immediate succession by default. **Dwell lands here** (R-Dwell): a machine-free, calendar-indifferent gap is definitionally a min-lag on the outgoing edge of the operation it follows — dwell is not, and was never structurally, a phase. |
| `max_lag` | duration, optional, default unconstrained (∞) | R-A3. No IDS doorway yet (docs/06 §8, deferred); the field and the Solver Builder constraint both exist so the doorway is a data problem, not a redesign, when it lands. |

**Synthesis rule (adapter-owned):** every adapter synthesizes a linear chain of edges from `routing_lines.sequence` at ingestion time — this is the default (and, until a real precedence-edge doorway exists, the only) source. `min_lag` is populated from a dwell source where one exists (currently only the IDS `routing_lines.dwell_minutes` column); absent a source it is 0, provenance `defaulted`. This keeps the six-canonical-input Solver Builder invariant intact: edges ride in the same mixed `work_items` list as WorkPackage and Operation entities.

### 5.5 ResourceRequirement (struct, not entity)

```
{ mode: capability | explicit_set,
  capability_ref  (when mode = capability),
  resource_refs   (when mode = explicit_set),
  count }
```

- One Operation may carry **several requirements simultaneously** (machine *and* tool). This unifies tooling into the general resource mechanism — no parallel tool system.
- **Capability requirement vs. explicit resource restriction are distinct facts with different explanation semantics** ("no capable machine was free" vs. "the routing restricts this to two machines"). When the ERP is ambiguous, the adapter records the safe interpretation (`explicit_set`) and emits an `AMBIGUOUS_SOURCE` finding.

### 5.6 Resource — *anything finite*

| Attribute | Type | Notes |
|---|---|---|
| `resource_type` | enum: `machine` / `tool` / `labor` / `fixture` | One entity, typed — no parallel systems |
| `capabilities` | list of Capability refs | The indirection that frees the core from hardcoded machine lists |
| `capacity` | int | 1 for machines; pooled count for tools |
| `cost_rate` | number, canonical $/minute | The resource's **effective** rate — equal by invariant to its `CostModel.resource_rates` entry (adapters fold docs/06 §5.5 precedence: cost-model default < resources.csv override < refinements; provenance class names the winning source). The pipeline prices from CostModel; this field is the same value made visible on the entity |
| `calendar_ref` | entity ref | Shifts, downtime, exceptions |
| `pool_refs` | list, optional | ResourcePool membership |

## 6. Supporting entities

### 6.1 Product

The thing made; carries the link to its Process. Thin for the PoC: `id`, `name`, `unit_of_measure`, `process_ref`, plus opaque attributes.

### 6.2 Process — *the recipe*

| Attribute | Type | Notes |
|---|---|---|
| `product_ref` | entity ref | One active Process per Product for the PoC |
| `operation_specs` | ordered list of OperationSpec | Linear chain now; partial order deferred |
| `version` / `effective_from` | int / timestamp | WorkPackages record which version they instantiated |
| `status` | enum: `active` / `superseded` | Supersession is a snapshot event, not a mutation |

Versioning is not bookkeeping: "the schedule changed because engineering revised the routing" is a required explanation, only possible if WorkPackages pin the Process version.

### 6.3 OperationSpec — *quantity-independent template*

| Attribute | Type | Notes |
|---|---|---|
| `sequence` | int | Position in the chain |
| `resource_requirements` | list of ResourceRequirement | |
| `setup_family` | code | Transition-matrix key |
| `base_setup` / `run_rate` | duration / duration-per-unit | **Rate, never pre-multiplied duration** |
| `splittable` / `min_chunk` | bool / duration | Policy defaults, overridable at instantiation |
| `yield_factor` | fraction, default 1.0 | Scrap ⇒ upstream quantity inflation; stubbed at 1.0, slot reserved |

No `dwell_rule` (docs/05 R-Dwell): dwell is a `PrecedenceEdge.min_lag` (§5.4a), not an OperationSpec attribute.

### 6.4 Capability

Deliberately thin: `id`, `name`, `description`, optional `parameters` (schema-free key-values: max_tolerance, bed_size, …).

**PoC matching rule: exact reference equality.** An Operation requires capability C; eligible resources are those listing C. Parameterized matching is a later enhancement with a reserved home. Do not build a capability ontology.

### 6.5 Calendar — *when a Resource or Pool exists to be used*

| Attribute | Type | Notes |
|---|---|---|
| `base_pattern` | recurring windows | Shift templates |
| `exceptions` | list of `{window, type, reason}` | type: `closure` / `added`; reason: `planned_maintenance` / `breakdown` / `holiday` / `overtime` |
| `horizon_resolved` | derived | The Solver Builder consumes the flattened window list |

- Exceptions carry provenance: a breakdown is *observed*; scheduled maintenance is *policy*. The AI phrases them differently.
- **Overtime enters as an `added` exception** — a fact the calendar records. Later, solver-proposed overtime becomes "optional calendar additions with a cost": a well-defined extension, not a redesign.

### 6.6 ResourcePool — *the canonical resolution of "workcenter"*

The ERP word "workcenter" conflates three roles; the canonical model separates them:

| ERP role | Canonical home |
|---|---|
| Routing target ("runs at WC-CNC") | ResourceRequirement on the OperationSpec (capability where the grouping is technology-based; explicit_set + finding where organizational/ambiguous) |
| Aggregate capacity ("at most 3 of these 5 run at once") | **ResourcePool** with `concurrent_capacity` |
| Reporting / organizational grouping | ResourcePool with no limits — pure membership |

| Attribute | Type | Notes |
|---|---|---|
| `members` | list of Resource refs | A Resource may belong to several pools |
| `concurrent_capacity` | int, optional | Max simultaneously active members |
| `calendar_ref` | optional | Pool-level windows |
| `limit_reason` | enum: `labor_proxy` / `utility` / `space` / `policy` / `unknown` | See below |

`limit_reason` lets the AI explain honestly ("only 3 can run at once because the cell has 3 operators") and marks proxy constraints for retirement when the unmodeled cause (usually labor) becomes a real Resource.

The word "workcenter" itself lives in the adapter's mapping table as an external term, so planners can use it and the AI resolves it.

### 6.7 Constraint — *typed restrictions that are not structural*

Structure (operation ordering) lives in the entities. Constraint captures the rest.

| Attribute | Type | Notes |
|---|---|---|
| `constraint_type` | enum, extensible | `setup_transition` / `frozen_assignment` / `pinned_window` / `resource_exclusion` / `max_queue_time` / … |
| `subjects` | entity refs | What it binds |
| `parameters` | typed payload per constraint_type | e.g., transition matrix ref; pinned start |
| `provenance_class` | enum: `physics` / `erp_data` / `policy` / `human_override` | "The routing says so" and "the plant manager said so" warrant different explanations and confidence |
| `authority` / `expiry` | string / timestamp, optional | Who imposed it; overrides should decay, not accrete |
| `hardness` | enum: `hard` / `soft` | Soft constraints carry their penalty weight |

Setup transition matrices are Constraint instances (`setup_transition`, provenance physics-or-policy). Frozen/fixed jobs become `frozen_assignment` constraints with authority recorded.

### 6.8 CostModel — *the economics as a versioned document*

| Attribute | Type | Notes |
|---|---|---|
| `version` / `effective_from` | | **Every solve records which CostModel version it used** |
| `resource_rates` | map Resource → cost/time | |
| `setup_cost_basis` | fixed per setup + scrap cost/unit | |
| `tardiness_weights` | base weight × commitment_class multipliers | Rush multiplier lives here, not in code |
| `overtime_premium` | multiplier | **Live** (docs/06 §5.6/§5.9): minutes scheduled inside overtime `added` calendar windows price at rate × this multiplier; ≤ 1 (including the 0 default) disables the premium and creates no solver machinery |
| deferred slots | `inventory_carrying` | Named now, zero for PoC |

Answers "why did the schedule change when nothing else did": the weights changed, and that is a diffable, versioned fact.

### 6.9 Schedule, Assignment, ServiceOutcome — *the solve output, in canonical language*

**Schedule:** `id`, `snapshot_ref`, `costmodel_ref`, solver run ref, `status` (`proposed` / `published` / `superseded`), summary metrics.

**Assignment** (per scheduled Operation):

| Attribute | Type | Notes |
|---|---|---|
| `operation_ref` / `workpackage_ref` | entity refs | What work |
| `resource_assignments` | list of `{requirement, resource_ref}` | Every requirement resolved — machine *and* tool |
| `phase_windows` | setup / run / dwell, each `{start, end}` | Real timestamps; chunked ops carry multiple run windows |
| `overtime_minutes` | int | Scheduled minutes inside overtime premium windows (docs/06 §5.6); derived at extraction. **Authoritative source** — the assignment Decision's payload repeats it as narrative only (2026-07-13 ruling) |
| `decision_ref` | ref | The reconstructed-alternatives Decision from Solution Extraction |

**ServiceOutcome** — one per Fulfillment: `demand_ref`, projected completion, lateness (may be negative), tardiness cost as charged. The per-customer truth table, materialized so no consumer recomputes lateness ad hoc and disagrees with the solver's own accounting.

## 7. Provenance

### 7.1 Architecture: clean entity + sidecar

| Layer | Content | Rationale |
|---|---|---|
| Canonical entity | Clean manufacturing object, plain values | Solver Builder = simple, fast, legible reads |
| Provenance sidecar | Trust, evidence, source, confidence per attribute | AI explanation = full traceability |

Sidecar keying: `entity_id + attribute_name + snapshot_id`. Provenance can change across snapshots (defaulted yesterday, observed today) — itself a data-quality signal worth trending.

### 7.2 The four provenance classes and their payloads

| Class | Meaning | Class-specific payload |
|---|---|---|
| `observed` | Read from the source system | source system, source field, extract reference |
| `derived` | Computed by a formula | **formula identity + input references** (which attributes, on which entities, at which snapshot) |
| `defaulted` | Supplied by a policy in absence of data | the policy that supplied the default |
| `synthesized` | Generated (test data, simulation) | generator identity + loud "not real" marker — test data must never masquerade as truth |

Derived values carry a walkable **derivation chain** ("duration 250 min ← quantity 500 observed on demand X × rate 0.5 min/unit observed on product Y"). Confidence of a derived value is a function of its inputs' confidence, degraded when any input was defaulted.

### 7.3 The write contract (structural, not disciplinary)

- Canonical entities are created or mutated **only** through the adapter and planning modules.
- Those writers emit provenance **as part of the same write operation** — one API, one transaction. There is no code path that sets a value without its provenance record.
- The Validator runs an integrity sweep every run: every attribute has a provenance entry; every provenance entry points at a live attribute (`PROVENANCE_GAP` finding otherwise). Completeness is a verified property, not a hope.

### 7.4 Reader tiers

| Reader | Sidecar access |
|---|---|
| Solver Builder | **Never.** If it seems to need provenance, the concern belongs upstream in validation. |
| Validation & Planning modules | Narrow, deliberate interface (e.g., "is this attribute trustworthy above threshold X?"). Trust may gate decisions: flag priority tradeoffs resting on defaulted weights; hesitate to batch on fabricated data. |
| AI Explanation | Full access. **The AI must never explain a schedule by citing a value nobody actually set.** |

## 8. Design invariants

1. **Internal planning constructs never redefine external commitments.** Batching, splitting, campaigns — the measurement frame stays anchored to Demands. Batching is solver convenience; the customer commitment is the truth. Concretely: the WorkPackage is scheduled, but **tardiness is evaluated per Demand** — one tardiness term per Fulfillment against the WorkPackage's completion, each weighted by that Demand's own weight.
2. **Costs attach where they are incurred; service is measured where it is experienced.** Setup/processing/scrap costs attach to WorkPackages; tardiness and priority penalties attach to Demands. The ledger rolls up both views without double-counting.
3. **Quantity and rate are first-class; duration is derived.** Never fuse quantity into minutes upstream. (Reverses the legacy pipeline, which multiplied quantity into ProcTime and discarded it — destroying the ability to split, track partials, or re-derive.)
4. **Observations are immutable.** Planning never mutates Demands; change arrives as snapshots.
5. **No number without decomposition.** Any reported total must be reconstructable from its recorded components (enforced by the evidence layer, Document 2).
6. **The Solver Builder consumes exactly six things:** WorkPackages (with Operations **and PrecedenceEdges**), Resources, ResourcePools, Calendars (flattened), Constraints, CostModel. PrecedenceEdges ride in the WorkPackages+Operations bucket rather than becoming a seventh input — the count stays six. This short list is the measure of whether the canonical model stays minimal.

## 9. Deferred concepts (named stubs)

Each has a reserved seam; none requires architectural rework to activate.

| Deferred | Seam reserved |
|---|---|
| Material / inventory flow | `earliest_start` on Demand stands in for availability; Material stays an opaque attribute until a scheduling decision depends on it |
| Labor as skill-bearing resources | Resource type `labor` exists; pool `limit_reason = labor_proxy` marks which pool limits to retire |
| Yield / scrap inflation | `yield_factor` slot on OperationSpec, fixed at 1.0 |
| Overtime as a solver decision | Calendar `added` exceptions record it as fact; optional-additions-with-cost is the extension |
| Partial-quantity fulfillment | `allocated_quantity` on Fulfillment |
| Parameterized capability matching | `parameters` on Capability |
| Process partial order | `predecessors` on Operation |
| Multi-plant | Out of scope entirely |
| Multi-level batching (batching batches) | Rejected, not deferred |

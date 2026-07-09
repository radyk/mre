# Constraint Catalog

**Document 5** · Status: v1.0 (rulings locked; living document) · Companions: 01 Canonical Model, 02 Evidence Contract, 04 Design History, 06 Incoming Data Spec, 07 Roadmap

---

## 0. Purpose, form, and consumers

This catalog is the authoritative census of scheduling constraints: what the system models, how, what it deliberately excludes, and what proof each capability carries. It defines the system's **niche by inclusion and exclusion alike** — documented exclusions with approximation guidance are product statements, not gaps.

**Form:** structured records first; prose is rendered from them (assembly-then-render, the house principle). Each item carries:

- `id` · `category` · **verdict** (In-core / In-later modular slot / Out)
- **plane** — *structural* (falls out of entities: Calendar, Capability, OperationSpec), *declarative* (a Constraint record layered on structure), or *objective* (a CostModel term). Not everything called a constraint is a Constraint record.
- **coverage** — the entity/field mechanism
- **input contract** — ERP/IDS source → default when absent → validator finding when malformed
- **test triad** — real-data case (pilot dataset), synthetic activation (generator scenario), malformed-input finding
- **status** — unimplemented / model-proven / **pipeline-proven** (full chain per docs/06 §8: doorway → gate check → adapter → generator scenario with truth manifest → schedule assertion)
- **IDS doorway** — where a submitter expresses it
- for exclusions: **approximation & limits** text

**Consumers:** (1) this design doc; (2) docs/06 manifest vocabulary; (3) website-AI grounding ("can it handle X?"); (4) in-product capability queries.

## 1. Locked rulings (the four, plus two corollaries)

### R-B3 — Resource requirement = set with roles
An operation's requirement is a **set of `{capability, quantity, role, phases}`**, phases ⊆ {setup, run, teardown}. The **primary** role is the schedule lane (disjunctive); **secondary** roles are cumulative draws (tools, operator pools). Teardown occupies the primary resource, defaults to 0 (the phase vanishes when absent), and is **constant per operation — job-dependent cleanup is changeover, not teardown**. Operators are calendar-bearing capacity **pools, never individuals**. Fractional quantities disallowed.

### R-C3 — Interruptibility: three classes, per phase
- **resumable** — spans calendar breaks; occupies its resource while paused; working duration fixed, elapsed stretches; **pauses only at calendar boundaries, never for other jobs**.
- **non-resumable** — must fit one contiguous calendar window.
- **calendar-indifferent** — runs through breaks unattended.

Defaults: setup/teardown resumable; run non-resumable. Restart cost on resume: **excluded**, documented, revisitable. Extraction must carry pause windows; the Gantt renders pauses honestly. *This ruling is the semantic spec for chunking (roadmap Rep 2): chunk boundaries are calendar boundaries, so chunk count = windows crossed — bounded by construction.* IDS `splittable/min_chunk` (§5.3) declares the run phase resumable.

### R-B7/B8 — ChangeoverRule: attribute-keyed, never product-pair
`ChangeoverRule {attribute, from_value, to_value, scope, duration}`. Wildcards allowed; direction-sensitive; multi-attribute combinator = **max** (policy knob); no matching rule ⇒ zero; forbidden sequences = same record with a legality flag / ∞ duration. Attributes must be canonical and provenance-bearing; missing attributes on participating products ⇒ validator finding. **IDS §5.11 (`setup_transitions.csv`, from_family/to_family) is the degenerate single-attribute case** (attribute = setup_family); the generalized multi-attribute table arrives via docs/06 §8 when demanded. Soft grouping *preference* may ship earlier as a CostModel term (objective plane). Verdict: **In-later modular slot** — shape blessed now so nothing upstream changes when it lands.

### R-A2/A3 — Min/max lags live on precedence edges
Lags are properties of the **relationship** between operations, not of either operation. Precedence edges become **first-class records** (docs/01 surgery, §4 below); lags attach there. Survives non-linear routings; matches how the constraint is spoken ("max 4 hours between coating and curing").

### R-A4 (corollary) — Release: one date, always; the ladder is a resolution policy
- **Canonical:** one field, `release`, provenance-bearing. The solver, planner, and evidence want exactly one truth: "earliest start, and why we believe it."
- **Adapter:** owns the resolution ladder — explicit material-ready date → PO promise → order release → reference-date default. Multiple source signals in, one output out, provenance naming the rung and citation ("release = 2026-07-15, source: PO-4471 promise date").
- **IDS:** no new date columns. The existing `release_date` column plus a **declared-semantics manifest field** states which rung it carries ("this is a material-ready date" / "this is order creation, material status unknown"). The conformance certificate grades accordingly. Multi-signal submissions (several date columns wanting adapter-side resolution) are a demand-driven doorway per §8 — untested spec surface is worse than absent spec surface.
- **Degradation finding** reads off declared semantics: "release dates carry rung-3 semantics (order release); no material signal present; schedule assumes material availability at order release." Honest by declaration, not inferred from absence.
- Derivation of release from inventory/PO netting is a **designed adapter-side slot, permanently outside the core**.

### R-Dwell (corollary) — Dwell dies as a phase, deliberately
Dwell is a machine-free, calendar-indifferent gap — **definitionally a min-lag on the outgoing precedence edge**. It becomes A2's first native customer; the ticketing dataset's founding dwell semantics land on edge records. The phase set stays clean at {setup, run, teardown}, where **phases occupy resources; lags don't.** (Adapter and extractor: that sentence is the contract.)

## 2. The catalog

Legend: ✔core = In-core · ◐slot = In-later modular slot · ✘out = Out · S/D/O = structural/declarative/objective plane · Status: **PP** pipeline-proven · **MP** model-proven · **UI** unimplemented.

### Category A — Temporal & precedence

| id | Item | Verdict/Plane | Coverage | Input contract | Test triad | Status | IDS doorway |
|---|---|---|---|---|---|---|---|
| A1 | Finish-start precedence | ✔core S | Precedence edges (first-class, §4); synthesized from linear Sequence, provenance derived | routing_lines.sequence → linear chain default → ORPHAN/sequence-gap finding | gauntlet routes (13-step) · any scenario · malformed sequence finding | PP | §5.3 |
| A2 | Min lag (incl. dwell) | ✔core S (edge attr) | `min_lag` on edge; dwell per R-Dwell | routing_lines.dwell_minutes → 0 → negative/absurd-lag finding | none in gauntlet (no Dwell column in the real extract) · dwell_heavy scenario (queued, docs/07 Phase 1) · negative lag finding (queued) | MP (edge surgery landed 2026-07-09: entity, all three adapters, Solver Builder; see docs/04 amendment) → PP pending gate check + dwell_heavy scenario | §5.3 (dwell_minutes); edge-lag columns per §8 when demanded |
| A3 | Max lag | ✔core S (edge attr) | `max_lag` on edge | doorway per §8 → ∞ default → max<min finding | none in gauntlet (state so) · binding max-lag scenario (queued) · max<min finding (queued) | MP (Solver Builder honors `max_lag` when present, `tests/test_precedence_edges.py::test_max_lag_enforced`; no doorway populates it yet — every adapter writes `None`) | §8 doorway |
| A4 | Release date | ✔core S | Demand.release, one field, provenance rung | R-A4 ladder; declared semantics | gauntlet CreatedDate rung-3 · release-binding scenario · future-release-past-due finding | PP | §5.1 + manifest semantics |
| A5 | Due date | ✔core S | Demand.due; per-Demand tardiness via Fulfillments (D-07) | orders.due_date → none (required) → TEMPORAL_IMPOSSIBILITY | gauntlet · every scenario · past-due excluded | PP | §5.1 |
| A6 | Hard deadline | ✔core S (Demand attr) | commitment_class=firm ⇒ deadline semantics; **never a Constraint record**; infeasibility ⇒ relax-and-report evidence | orders.commitment_class → standard → uncovered-class finding | none in gauntlet · firm-deadline-infeasible scenario (asserts relax-and-report) · unknown class finding | MP | §5.1 |
| A7 | Frozen/pinned operations | ✔core **D** | Constraint records: frozen_assignment / pinned_window; provenance + authority **mandatory** | locks.csv → none → lock-on-unknown finding | none in gauntlet · locked_plant scenario · unknown-ref finding | PP | §5.12 |

### Category B — Resources & requirements

| id | Item | Verdict/Plane | Coverage | Input contract | Test triad | Status | IDS doorway |
|---|---|---|---|---|---|---|---|
| B1 | Disjunctive capacity | ✔core S | Resource + no-overlap on primary lane | resources.parallel_units → 1 → nonpositive finding | gauntlet 93 workcenters · all scenarios · bad units finding | PP | §5.5 |
| B2 | Eligibility / alternative resources | ✔core S | ResourceRequirement capability/explicit_set | routing_lines.resource_id → explicit_set + AMBIGUOUS_SOURCE when unclear | gauntlet fixed lanes · multi-eligible scenario · NO_CAPABLE_RESOURCE | PP | §5.3/§5.5 |
| B3 | Multi-resource set-with-roles | ✔core S | R-B3 requirement sets; primary lane + cumulative secondaries; teardown phase | doorway per §8 for secondaries → single-primary default → role-without-capability finding | none in gauntlet · operator-pool-contention scenario · missing-capability finding | MP | §8 doorway (roles) |
| B5 | Cumulative secondary resources (tools, operator pools) | ✔core S | Cumulative constraint over secondary draws; pools calendar-bearing | resources resource_type=tool/labor, capacity → absent = unconstrained → capacity<demand-at-instant is solver truth, not finding | none in gauntlet (single tool cut) · tool-contention scenario · bad capacity finding | MP | §5.5 |
| B6 | Sequence-independent setup | ✔core S | OperationSpec.base_setup (phase, R-C3 resumable default) | product/routing_lines setup_minutes → 0 → negative finding | gauntlet product-level setups · all scenarios · negative setup finding | PP | §5.3/§5.4 |
| B7/B8 | Sequence-dependent changeover / forbidden sequences | ◐slot D | R-B7/B8 ChangeoverRule | §5.11 (single-attribute today) → zero default per manifest → family-without-matrix finding | none in gauntlet (no families) · transition_heavy scenario · unlisted-pair per manifest | PP (single-attr) / UI (multi-attr) | §5.11; §8 for multi-attribute |
| B9 | Batch co-loading (oven/tank shared cycles) | ✘out | — | — | — | — | — |
| B10 | Blocking / finite WIP buffers | ✘out | — | — | — | — | — |

**B9 approximation & limits:** model the oven as a cumulative resource with cycle-long operations sharing a window via pool capacity; adequate when co-loaded jobs are pre-batched by the planner. Limit: the solver will not *form* co-load groups or synchronize cycle starts; true co-loading is a different model class (bin-packing-in-time). Revisit if a pilot's bottleneck is a batch furnace.
**B10 approximation & limits:** max_queue_time constraints (declarative, edge max-lag) approximate perishable-WIP pressure; buffer *counts* are not modeled. Limit: no blocking propagation (a full downstream buffer does not hold an upstream machine). Adequate for job shops with floor space; wrong for tightly coupled lines — which are outside the niche.

### Category C — Calendars & availability

| id | Item | Verdict/Plane | Coverage | Input contract | Test triad | Status | IDS doorway |
|---|---|---|---|---|---|---|---|
| C1 | Working calendars (shifts, weekends, holidays) | ✔core S | Calendar base_pattern; flattened for solve | calendars.csv patterns → **none: Tier-1, capacity is not optional** → empty-pattern rejection | gauntlet plant config · all scenarios · zero-pattern rejection | PP |§5.6 |
| C2 | Downtime, maintenance, breakdowns | ✔core S | Calendar exceptions {closure, reason}; **never Constraint records** | calendars exception rows → none → overlapping/invalid-window finding | sample-world maintenance day · calendar_chaos scenario · invalid exception finding | PP | §5.6 |
| C3 | Interruptibility & chunking | ✔core S | R-C3 per-phase classes; pause windows in extraction | §5.3 splittable/min_chunk → run non-resumable default → min_chunk>duration finding | 116/173 gauntlet exclusions rescued (counterfactual — raw_data has no real `splittable` source; `tools/gauntlet_rescue_report.py`), 57 genuine survivors · chunking_exam (pause-window assertions, `tests/test_ids_end_to_end.py::TestChunkingExamScenario`) · min_chunk enforced via `OnlyEnforceIf` (no dedicated "bad chunk" finding yet — malformed min_chunk/duration combinations surface as ordinary solve infeasibility, not a validator check) | PP (2026-07-11; see docs/04 amendment — chunk-boundary-interval encoding, spike 2 verdicted YELLOW, productionized) | §5.3 |
| C4 | Time-window operation restrictions ("only day shift") | ✔core S | Capability-bearing calendar on the requirement's eligible set (structural, no new record) | doorway per §8 → unrestricted default → window-excludes-all finding | none in gauntlet · night-forbidden scenario · impossible-window finding | MP | §8 doorway |

### Category D — Quantity & lots

| id | Item | Verdict/Plane | Coverage | Input contract | Test triad | Status | IDS doorway |
|---|---|---|---|---|---|---|---|
| D1 | Lot sizing, min/max batch | ✔core (Planner policy, not solver constraint) | M4 policies create WorkPackages; Fulfillment cardinalities (D-07) | policy config → identity_v1 default → merge-guard findings (Rep 4) | gauntlet merges · priority_pressure/merge scenarios · BATCH_CONFLICT | PP | policy config |
| D2 | Transfer-batch overlap (op N+1 starts on partial qty) | ✘out | — | — | — | — | — |
| D3 | Yield / scrap inflation | ✔core S (slot active) | OperationSpec.yield_factor; quantity model upstream-inflates | doorway per §8 → 1.0 → yield≤0 or >1 finding | none in gauntlet · yield-inflation scenario · bad yield finding | MP | §8 doorway |

**D2 approximation & limits:** split the order into planner-created WorkPackages (D-07 splitting) to get coarse overlap. Limit: no continuous flow coupling; precision below WorkPackage grain is not modeled. Adequate for discrete job shops; wrong for high-volume flow lines — outside the niche.

### Category F — Assignment overrides (declarative, provenance mandatory)

| id | Item | Verdict/Plane | Coverage | Input contract | Test triad | Status | IDS doorway |
|---|---|---|---|---|---|---|---|
| F1 | Pin-to-resource | ✔core D | Constraint pinned_resource; **the compile target of cockpit drags** | locks.csv lock_type · cockpit edits (authority=user) → none → unknown-ref finding | none in gauntlet · locked_plant · unknown-ref finding | PP | §5.12 + cockpit |
| F2 | Exclude-resource | ✔core D | Constraint resource_exclusion | §8 doorway / cockpit → none → excludes-all-eligible finding | none in gauntlet · exclusion scenario · no-resource-left finding | MP | §8 doorway |
| F3 | SameResource(op_a, op_b) | ◐slot D | Linkage constraint; shape reserved | §8 doorway → absent → unknown-op finding | — · same-resource scenario (at activation) · unknown-op finding | UI | §8 doorway |

### Category G — Objective-side firewall (costs, never Constraint records)

Priorities and customer weights (**cost coefficients**, docs/06 §5.9) · preferred machines/shifts (soft preference terms) · minimize-changeovers / minimize-WIP / makespan pressure (objective terms) · overtime premiums (calendar `added` × CostModel premium). **Rule:** anything expressing *preference or price* lives in CostModel; the Constraint entity is reserved for restrictions. A "preference" arriving as a hard rule is a modeling error to be caught in review, not accommodated.

### Global exclusions (with approximation & limits)

- **Individual operator rostering** — operators are pools (R-B3). Approximation: pool capacity per calendar. Limit: no named-person assignments, skills matrices deferred with the labor stub. Revisit trigger: a pilot whose binding constraint is certified individuals.
- **MRP / material netting** — release derivation is an adapter-side slot (R-A4), permanently outside core. Approximation: declared-semantics release dates. Limit: no BOM explosion, no pegging.
- **Multi-site with transport** — facilities are disjoint namespaces. Approximation: none across sites. Limit: no inter-plant flows.
- **Energy/tariff-aware scheduling** — out. Approximation: time-window restrictions (C4) for hard curtailment. Limit: no price-curve optimization.
- **Arbitrary-point preemption** — out. Interruption exists only as R-C3 resumable-at-calendar-boundaries. Limit: no job-bumps-job preemption; that is a policy decision expressed via pins/priorities, not solver freedom.
- **Batch co-loading (B9), WIP blocking (B10), transfer overlap (D2)** — see category notes.

## 3. Acceptance gates

1. **Input contract + test triad present for every non-Out item.** No exceptions; blanks are backlog, not omissions.
2. **Defaults-reproduce-baseline (the modularity gate):** a dataset exercising no new fields must solve **identically** to the pre-catalog system. Regression-tested, not promised.
3. **Real-data cases named** against pilot-dataset work orders where the gauntlet contains the phenomenon; where it doesn't, the catalog says so explicitly (an honest "none in gauntlet" is data).
4. **Synthetic activation coverage:** generator scenarios exist (or are queued with owners) for: operator-pool contention (B3/B5), resumable run spanning a break with pause-window assertions (C3/Rep 2), binding max-lag (A3), forbidden changeover direction (B7/B8), firm-deadline relax-and-report (A6).
5. **Status honesty:** PP only with the full docs/06 §8 chain; MP and UI are respectable, tracked states — the column exists so nothing hides between "the model supports it" and "the system has ever done it."

## 4. docs/01 surgery — precedence edges become first-class (one amendment, four consumers)

The R-A2/A3 ruling requires Operation precedence to be edge **records** `{predecessor, successor, min_lag, max_lag}` rather than implicit sequence. Consumers to update in the same change: **(1)** docs/01 §5.4 (entity spec: edges replace `predecessors` list; linear chains synthesized from Sequence with provenance derived); **(2)** the adapter (emit edges; dwell lands as edge min_lag per R-Dwell); **(3)** the solver builder (precedence + lags read edges); **(4)** WIP semantics (docs/06 §5.13: "downstream chains from fixed reality" chains along edge records). The defaults-reproduce-baseline gate is the proof the surgery was clean.

## 5. Maintenance

Living document under the standard rules: verdicts never silently repurposed; new items enter with full records; status column moves only on evidence (test IDs cited in docs/04 amendments); exclusions revisited only against a named trigger (usually a pilot phenomenon), and the revisit is itself recorded.

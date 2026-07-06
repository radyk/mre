# Design History — The Founding Conversation

**Companion to the three specifications.** The specs record *what* was decided; this
document records *why* — the alternatives considered and rejected, the arguments
that settled each fork, and the observations that motivated the design. It exists
so future revisiting of any decision starts from the original reasoning, not from
scratch. (Fittingly, this is the project's own evidence contract applied to
itself: decisions, alternatives, drivers.)

---

## D-01 — Structured evidence over parsed output

**Context.** The legacy system communicated through print statements; a bridge
script regex-parsed stdout to recover metrics. The solver knew why it made each
decision but discarded that knowledge at solve time.

**Decision.** Every module emits structured, machine-readable records (decisions,
findings, metrics) through one shared contract. Human-readable messages accompany
but never replace structured payloads.

**Rejected.** Improving the print/parse pipeline. Reason: an LLM explaining a
schedule must trace facts through the whole pipeline; reconstructed fragments of
console output cannot support that, and regex-on-stdout is brittle by
construction.

**Driver.** Explainability requires capturing decision context *at the moment it
exists*, not reconstructing it from output.

---

## D-02 — One universal run-record contract for all modules

**Decision.** Ingestion, validation, planning, solving, extraction all speak the
same contract: identity, events, decisions, findings, artifacts. A thin shared
Reporter enforces the schema in one place.

**Rejected.** Per-module output formats. Reason: "why is this order on the slow
machine?" may have its true answer in the optimizer, the validator, or the
adapter; a uniform history lets the AI query one structure instead of parsing
five bespoke ones. Also rejected: heavyweight per-module integration — if
emission costs an author more than a line or two per event, modules stop
reporting and the system's value collapses. Ease of emission is first-order.

---

## D-03 — Serve both consumption patterns; retrieval is never sacrificed

**Context.** Two AI consumption patterns: (a) whole-run summarization, (b)
interactive retrieval across runs. User ruling: *"I wouldn't want to give up (b)
in pursuit of (a), which is the priority."*

**Decision.** Design content for (a); impose the discipline of (b) on every
record — stable IDs, canonical entity keys on everything, self-contained
fragments, cross-run identity via snapshots and lineage.

**Consequence.** Entity keys became the single most important structural
requirement, which directly triggered D-04.

---

## D-04 — Canonical manufacturing model, ERP as adapter-translated detail

**Context.** User's framing: model the permanent concepts of manufacturing
(Demand, Product, Operation, Resource, Capability, Constraint, Cost, Decision,
Evidence), not the terminology of any ERP. Sales orders, work orders, routing
codes, machine IDs are implementation details. The objective is *"not an ERP
scheduling engine, but a manufacturing reasoning engine."*

**Decision.** Canonical domain model with an anti-corruption (adapter) layer.
Two litmus tests for admitting a concept: (1) fundamental manufacturing concept
vs. ERP detail; (2) does the reasoning core *act* on it — the canonical model is
the minimal acted-upon set, not a universal ontology. Anything else travels as
opaque attributes.

**Known failure mode + defense.** Canonical models die by leakage ("just one
field" reached around the adapter). Defenses: core imports only canonical types;
ERP IDs live only in `external_refs`; litmus tests at every review. Portability
is proven by the second adapter, not designed in the abstract.

**Consequences.** Identity resolution (today's row = yesterday's entity) moves to
the adapter and is genuinely hard; the mapping table is a first-class persistent
artifact, load-bearing in both directions (inbound identity, outbound rendering
of explanations in planner vocabulary).

---

## D-05 — Three models, and two bugs in the naive pipeline

**Decision.** ERP Model (external) / Canonical Model (permanent truth) / Solver
Model (temporary math, discarded after solve). The ERP Adapter and Solver Builder
are symmetric translators; the canonical model knows neither exists.

**Bug 1 fixed.** The solution must flow *back into the canonical model*: the
builder produces the model **plus a variable↔entity mapping table**; extraction
translates results into a canonical Schedule before the solver model dies.
Otherwise the schedule is orphaned in the quarantined representation.

**Bug 2 fixed.** The Evidence Reporter is not a pipeline stage after Solution —
it is a cross-cutting floor all stages write to as they run (the adapter decides,
the validator finds, the builder simplifies).

**Also settled here.** Validation is layered (adapter-shape / canonical-semantic /
solve-time joint feasibility, same Finding schema); snapshot semantics — no run
operates on "current state," only on an identified snapshot, every record pinned
to it. Cheap to adopt now, near-impossible to retrofit.

---

## D-06 — The hand-translation exercise and what it exposed

**Method.** Took a real row from the legacy pipeline and translated it to
canonical form. Strains found, each forcing a model decision:

1. **Quantity fused into ProcTime** (qty/lot-size × rate, pre-multiplied,
   quantity discarded) → lossy; kills splitting, partials, re-derivation.
   ⇒ *Quantity and rate first-class; duration derived* (invariant 3).
2. **Epoch-minute due dates** → solver arithmetic leaking into data. ⇒ Canonical
   entities hold real timestamps; time conversion is the builder's job.
3. **Constants masquerading as data** (Priority=5, CustomerWeight=5, etc.
   injected by the formatter) → the AI must never explain a schedule by citing a
   value nobody set. ⇒ Attribute provenance (D-08).
4. **MachineOptions ambiguity** ("CNC-1/CNC-2": capability or restriction?) →
   different explanation semantics, different planner actions. ⇒ Two requirement
   modes; adapter defaults to the safe interpretation (explicit_set) + finding.
5. **Silent batching in the formatter** (merge by task/workcenter/product within
   3 days, demand mapping lost — "where is WO-10441?" unanswerable) ⇒ D-07.
6. **Setup times stored on the Product table** though they belong to operations →
   adapter placement judgment, recorded as low-confidence evidence.
7. **Tools as a parallel bolt-on system** ⇒ unified: a tool is just a finite
   Resource required simultaneously with a machine.

---

## D-07 — Demand / WorkPackage / Fulfillment (the batching decision)

**Options considered.**
- *Batch-as-attribute* (mutate a winner demand): rejected — planning must never
  mutate observations.
- *First-class Batch entity*: rejected — makes batching structurally special;
  every consumer handles two cases.
- *Intermediary entity* (**WorkPackage**) with an explicit mapping
  (**Fulfillment**): **chosen.**

**Why it wins.** Separates *what is wanted* (Demand, immutable, ERP-sourced)
from *what we plan to do* (WorkPackage, derived, ours). Batching, splitting,
make-to-stock, and (later) partial allocation are all just cardinalities of the
same mapping — the edge cases collapse into the general case, the signature of a
right abstraction. The scheduler sees only WorkPackages.

**The per-Demand tardiness insight.** The WorkPackage is scheduled, but tardiness
is evaluated per constituent Demand against the same completion variable, each
with its own weight. No min-due-date hack, no information destroyed by batching.
This is what makes batching honest, and it directly serves the explanation:
"10432 is one day late; it was batched to save a setup; the batch couldn't finish
earlier because…"

**Naming.** "WorkPackage" chosen by the user for industry independence (over Job,
ProductionOrder, Lot, Campaign).

**Elevated to invariant (user's ruling).** *Batching is solver convenience; the
customer commitment is the truth.* Generalized: **internal planning constructs
never redefine external commitments** — the measurement frame stays anchored to
Demands no matter what planning moves are invented later.

**Corollary.** Costs attach where incurred (WorkPackages); service is measured
where experienced (Demands). Both rollups from the same records, no double
counting.

**Change-after-batching rule.** Re-derive WorkPackages each snapshot except
frozen+; mappings update instead; conflicts raise `BATCH_CONFLICT` with a
disposition. The structure makes the situation representable, which
mutate-the-demand never could.

**Deferred.** Solver-decided batching (possible via optional merge booleans,
rejected for complexity — pre-solve batching with recorded decisions, iterate);
partial-quantity allocation; multi-level batching (rejected outright).

---

## D-08 — Provenance: clean entity + sidecar

**User's formulation (adopted verbatim as the argument).** Canonical entity =
clean manufacturing object · Provenance sidecar = trust, evidence, source,
confidence · Solver builder = simple reads · AI explanation = full traceability.

**Rejected.** Value-plus-metadata on every attribute: burdens the hottest,
most correctness-critical consumer (the builder) for the benefit of the
latency-tolerant one (the AI). Put the join cost on the consumer that can
afford it.

**Failure mode + structural defense.** Optional sidecars become incomplete
sidecars, worse than none (absence gets misread as "observed"). Defense: writes
only via adapter/planning, provenance emitted in the same write operation — no
code path sets a value without it — plus a validator integrity sweep
(`PROVENANCE_GAP`). Completeness is verified, not hoped.

**Two refinements.** (1) Provenance is not only for explanation: validation and
planning may read it through a narrow trust interface (defaulted customer
weights should gate priority tradeoffs); the *solver builder never reads it* —
if it seems to need to, the concern belongs upstream. (2) Derived values carry
their derivation: formula identity + input references at snapshot, giving the AI
a walkable chain and data-quality monitoring root-cause power. Confidence of a
derived value degrades with its inputs.

**Four classes.** observed / derived / defaulted / synthesized — each with a
class-specific payload; synthesized carries a loud "not real" marker so test
data can never masquerade as truth.

---

## D-09 — Workcenters: one ERP word, three canonical concepts

**Finding.** "Workcenter" conflates (1) routing target, (2) aggregate capacity
limit, (3) reporting group — all three visible in the legacy code.

**Decision.** (1) → ResourceRequirement (capability where technology-based,
explicit_set + finding where organizational/ambiguous); (2) + (3) →
**ResourcePool** with optional `concurrent_capacity` and a `limit_reason` enum.

**Why limit_reason matters.** Pool limits are usually proxies for something
unmodeled (operators, utilities). Recording the reason lets the AI explain
honestly ("3 at once because the cell has 3 operators") and marks exactly which
constraints to retire when labor becomes a real Resource — the deferred-labor
decision leaving a clean seam instead of a landmine.

---

## D-10 — Template and instance: OperationSpec vs Operation

**Decision.** Process owns quantity-independent OperationSpecs (rates, setup
family, requirements); the Planner instantiates them as Operations per
WorkPackage — where quantity × rate becomes duration, as a *derived* attribute
with a recorded chain. Cost: one extra entity. Benefit: one Process serves every
WorkPackage; the quantity→duration derivation stays clean and traceable.

**Adjacent decisions.** Process versioning (WorkPackages pin the version —
"engineering revised the routing Tuesday" must be an available explanation);
`yield_factor` slot reserved at 1.0; Capability kept deliberately thin with
exact-match semantics — *do not build a capability ontology* for the PoC.

---

## D-11 — Calendar, Constraint, CostModel details worth remembering

- Overtime enters as a calendar `added` exception — a recorded fact today, and
  the seam through which "solver-proposed overtime with a premium" arrives later
  as an extension, not a redesign.
- Constraint carries `provenance_class` (physics / erp_data / policy /
  human_override) because "the routing says so" and "the plant manager said so"
  warrant different explanations and confidence — plus `authority` and `expiry`
  so overrides decay rather than accrete.
- CostModel is a versioned document, not scattered config: "why did the schedule
  change when nothing else did" becomes a diffable fact.
- The Solver Builder consumes exactly six inputs (WorkPackages+Operations,
  Resources, Pools, flattened Calendars, Constraints, CostModel) — the short
  list is the ongoing measure of canonical-model minimality.

---

## D-12 — Evidence vocabularies: small closed enums, free payloads

**Principle.** Codes are for routing and retrieval; payloads are for substance.
12 driver codes, ~16 finding codes grouped by pipeline layer of origin. One
mandatory *primary* driver per decision — forcing commitment to the dominant
cause is what keeps explanations crisp. Extension rule: add, never repurpose,
always reviewed.

**The honesty flag.** `basis: observed / reconstructed / policy_applied`.
A CP-SAT solve's internal search is unobservable; what M7 records is a
*reconstruction* of alternatives from the model's own data — cheap, honest, and
always labeled, so the AI says "X was chosen; alternatives would have cost…" and
never "the solver chose X because…". This is the primary defense against
hallucinated motive.

**Other rules with teeth.** Decomposability contract on rollup metrics, verified
at consolidation. Tier system (headline/supporting/detail) keeps summaries within
LLM reading budgets without discarding information. No AI write path — no
`record_explanation` verb; the store is testimony, AI narratives go in a separate
annotation store. Findings carry *disposition* (what the system did), which is
what connects data quality to schedule quality.

---

## D-13 — PoC strategy: the thesis is traceability, not the solver

**Decision.** Build the evidence backbone first (Phase 0), then adapter+validator
(Phase 1 — standalone shippable data-quality value), then the solver spine
(Phase 2), then the AI layer (Phase 3). CP-SAT is proven by the legacy code; the
unproven claim is that canonical model + evidence contract make explanation work
with *plain retrieval* — deliberately no embeddings, no agent loops in the PoC,
because "dumb retrieval suffices over well-structured evidence" is itself the
result to demonstrate.

**Acceptance test written before code.** The demo script, centrally: *"Why is
WO-10432 late?"* answered as a chain where every clause is sourced from a record
and the assignment is marked reconstructed. "This interaction is the whole
project."

**Solver scope cuts** (all incremental to restore from legacy reference):
chunked/preemptive processing, straddling rewards, dwell subtleties, tool
variety. **Test defects are seeded deliberately** so validation checks are
written against known truth.

---

## Standing tensions to monitor

1. **Canonical minimality vs. feature pressure** — every new concept fights the
   two litmus tests; the builder's six-input list is the canary.
2. **Evidence volume vs. usefulness** — tiers and vocabularies are the pressure
   valves; if consolidated documents bloat, tighten tier discipline before
   inventing new machinery.
3. **Reconstruction honesty** — as explanations get fluent, the temptation to
   let the AI narrate motive grows; `basis` labeling and phrasing rules are the
   line.
4. **The living-document promise** — specs must move with the code (same-commit
   rule in CLAUDE.md) or they decay into archaeology, which is exactly what this
   document exists to prevent.

---

# Amendment log

New material decisions and corrections are appended below, dated. **This file is
append-only:** never recreate or truncate it — the founding records above are
the project's institutional memory.

## 2026-07-05 — Finding code count corrected to 17

docs/02 §4.3 originally read "Finding codes (~16)". The exhaustive enumeration in
that same section lists 6 adapter codes + 7 validation codes + 4 plan/solve codes
= **17** total. The "~16" approximation was incorrect. The spec text and the
`FindingCode` enum in `src/mre/contracts/vocabularies.py` now both say 17.
The test `test_exactly_17` in `tests/test_vocabularies.py` pins this count.

## 2026-07-06 — This document was overwritten and restored

During the Phase 1 build, this file was recreated from scratch (containing only
the 17-codes note above), silently discarding the thirteen founding decision
records. Restored from the preserved original. Lessons applied:
- The append-only rule above is now stated in the file itself.
- CLAUDE.md gains an explicit rule: docs/04 is append-only; amendments go under
  the Amendment log heading.
- Standing tension #4 was validated within two sessions of being written.

## 2026-07-05 — Phase 1 interpretive choice: outlier grouping proxy

The M3 statistical-outlier check groups OperationSpec run rates "by product
family" using `setup_family` as the grouping key. This is a **proxy** (setup
family ≈ product family), adopted for expedience because no distinct
product-family attribute exists yet. It is not a principled equivalence: if a
true product-family attribute is later added, the outlier grouping should move
to it, and setup_family reverts to its sole intended role as the
transition-matrix key.

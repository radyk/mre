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

## 2026-07-06 — Phase 2 scheduling spine: judgment calls

**Time granularity — integer minutes.** The CP-SAT model expresses all times as
integer minutes from `horizon_start`. Hours or seconds were the alternatives.
Minutes were chosen because: (a) the shortest operations in the sample data are
~30-minute setups (sub-minute granularity buys nothing), (b) the widest
horizon (~650 days) fits in a 32-bit integer in minutes (941 760), and (c)
cost coefficients scaled by 100 keep integer precision without overflow.

**Horizon computation — internal vs external.** `SolverBuilder._compute_horizon`
derives the horizon from demand data (earliest start, latest due + 7 days).
`__main__.py` independently computes a wider horizon (due + 14 days) for
calendar pre-flattening. The mismatch is benign: the extra calendar windows
fall outside the operation variable domains and create no blocking intervals
inside the horizon. If exact consistency is later required, pass the computed
horizon into `build()` as a parameter rather than re-deriving it.

**Setup transitions — pairwise literals, not circuit.** Sequence-dependent
setup times use pairwise big-M constraints (one `both_ij` bool + one
`order_ij` bool per op-pair per shared resource). The CP-SAT `add_circuit`
alternative was considered but rejected for Phase 2: `add_circuit` requires a
fixed resource assignment before building the circuit, which conflicts with the
optional-interval assignment model. The pairwise encoding is O(n²) per
resource but sufficient for the PoC load (~10 ops per resource).

**Calendar blocking — fixed intervals in no-overlap.** Unavailable periods are
encoded as fixed-duration interval variables added to each resource's
`add_no_overlap` group. This prevents operations from spanning shift boundaries
without requiring explicit shift-indexed start variables. Consequence: all
operations must complete within a single shift window; `splittable=False` is
enforced implicitly. Multi-day operations are infeasible with this encoding;
the sample data was calibrated accordingly.

**Capability UUID matching.** `ResourceRequirement.capability_ref` is a UUID5
computed as `uuid5(DNS_NS, "capability:<code>")`. The solver builder reverses
the mapping by computing `uuid5(DNS_NS, "capability:<c>")` for each resource
capability string and comparing. This avoids storing a second index.

**setup_family per step, not per product.** Each OperationSpec step carries the
*workcenter's* capability code as `setup_family`, not the product family. This
ensures transition-matrix lookups are between capability codes (casting→casting,
machining→machining), which is the intended semantics. An earlier implementation
used the product's family for all steps; this caused cross-capability machine
pairs to be erroneously considered for transition constraints.

**Sample data calibration.** Two values were adjusted to keep operations within
a single 720-minute shift window while preserving detectability by the validator:
- `PROD-007 ProductionMinutes` changed from 150.0 to 60.0. The value 60.0 is
  still 30× the gear-family median (0.45–0.6 sec/unit), so M3's statistical
  outlier check (>10× threshold) still fires. With 150.0, the merged WP for
  all four R-GEAR-C work orders totalled 847 minutes per operation — infeasible.
- `_FALLBACK_RUN_RATE_SECONDS` changed from 600 to 30. PROD-008 still has
  `CostingLotSize=0`, still triggers the LOW_CONFIDENCE_INPUT finding with
  `disposition=defaulted`, and the merged R-ZERO WP now produces ~280-minute
  operations instead of ~5 000-minute ones.

---

## Amendment log

### 2026-07-06 — Pre-Phase-3 fixes: identity boundary lesson and decomposability ≠ truth

**External-ID-in-config is still an ERP ID.** `costmodel.json` stored production
rates keyed by external machine IDs (`"M-CAST-01": 5.0`). The solver builder and
extractor reference resources only by canonical UUID, so every `rates.get(rid,
0.0)` silently returned 0.0. The fix: `load_cost_model` now accepts the
`identity_map` built by M1 and translates each rate key from external machine ID
to canonical UUID before constructing the CostModel entity. No ERP identifier
ever appears in the canonical model.

Lesson recorded: *identity mapping applies to config files too*, not only to ERP
extract rows. Any policy document that addresses a machine, product, or workcenter
by its ERP name must pass through the identity map at the adapter boundary.
Failure mode is silent — the config loads without error, the entity looks correct,
and the consumer just gets 0.0 for every lookup.

Guards added: M1 now emits a `LOW_CONFIDENCE_INPUT / WARNING / disposition=defaulted`
finding for (a) any rate key in the config file that the identity map cannot
resolve, and (b) any registered machine that has no rate entry after translation.
Silent zero-defaults are forbidden; every 0.0 must be accompanied by a finding.

**Decomposability passing ≠ cost model being correct.** The cost ledger had been
verifying `total = production + setup + tardiness` and passing that check since
Phase 2 shipped — because all three components decomposed correctly. What it did
not check was whether any component was factually accurate. With `production_cost
= 0.0` (all rates silently zero), the ledger was internally coherent but
factually wrong. The decomposability invariant guarantees arithmetic consistency;
it says nothing about whether the input rates are non-zero or meaningful.

The no-silent-defaults guard is the fix: a production_cost of 0.0 is now only
reachable if there is a corresponding finding in the evidence store. A future
audit or AI explanation can therefore detect the anomaly rather than propagating
a silently wrong number.

**Demo story tuning.** `PROD-007 ProductionMinutes` was further adjusted from
60.0 to 90.0 to ensure the merged WP (WO-2001 + WO-2002, qty=800) produces
operations of 420 min each. With two 420-min steps in sequence and a 720-min
shift window, gear cutting fills 07:00–14:00 on 2026-07-13, leaving 300 min in
the shift — insufficient for the 420-min inspection step. Inspection is pushed to
2026-07-14, making WO-2001 (due 2026-07-13 23:59) approximately 841 min late.
The STATISTICAL_OUTLIER finding still fires: 27 sec/unit ÷ 0.6 sec/unit = 45×
the gear-family median, well above the 10× detection threshold.

## 2026-07-06 — Phase 3: M9 Evidence Index, M10 Explainer, demo script

**Stale-snapshot INFEASIBLE incident.** During pre-Phase-3 verification, deleting
`mre_output/` between runs was required to get a clean solve — old entity files from
the previous snapshot directory persisted and the solver saw conflicting state. The
fix (implemented in `__main__.py` and `demo.py`) is to delete the snapshot
subdirectory for the target `snap_id` before M1 runs. This converts a silent
data-poisoning bug into a deterministic clean-start guarantee. The
incident is the origin of the "run-scoped output" housekeeping item in docs/03.

**L4 Index design (M9).** The evidence index reads raw JSONL stream files from
`runs/`, not the in-memory consolidated documents. Consolidated docs are never
written to disk; the index is the persistence layer for cross-run retrieval.
Two-key indexing: `entity_id -> [records]` and `finding_code -> [findings]`.
`lineage_walk(entity_id)` adds transitive graph traversal via the snapshot
reader: demand -> fulfillment -> workpackage -> operations. This is the critical
primitive for the "why is WO-X late?" query path, because ASSIGNMENT decisions
are keyed by operation_id, not demand_id; reaching them requires the multi-hop
walk. Records within a walk are ordered by pipeline stage (M1=1 ... M7=7) then
by seq within stage, giving a coherent causal narrative.

**M10 read-only invariant.** The explainer module imports neither Reporter nor
SnapshotWriter. This invariant is enforced by a test (AST import inspection) rather
than by module structure alone, since Python's dynamic imports make structural
barriers easy to accidentally bypass. The test is the guard.

**Evidence emission gap (M7).** ServiceOutcomes were computed in the extractor but
not emitted as evidence records — they lived only in the ExtractResult in-memory
struct. The demo query "why is WO-2001 late?" requires a `lateness_minutes` metric
in the evidence store so M9 can find it by entity_id. Two metrics were added to
M7's extractor loop: `lateness_minutes` and `projected_completion_epoch` per
fulfillment. The projected_completion_epoch metric stores the Unix timestamp of
the projected completion so renderers can format it without recomputing from
the schedule.

**TemplateRenderer rendering rules.** The renderer uses `identity_map.external_refs()`
to convert canonical UUIDs to external names at render time. Planner vocabulary
rule: demand -> work_order, resource -> machine_id, product -> product_no.
Basis=reconstructed decisions include an explicit note ("This is a reconstruction
from the solved schedule") to distinguish them from policy decisions. Every cited
record is footnoted with its 8-char record_id prefix. No UUIDs appear in renderer
output — enforced by a test that asserts `bundle.subject_id not in rendered_text`.

**Snapshot diff design.** `Explainer.snapshot_diff(snap_a, snap_b)` reads both
snapshot stores and compares demand entities (by work_order external_ref) and
CostModel (by version + resource_rates). Resource rate changes are resolved back
to machine_id names via the identity map from snapshot_a. The diff is returned as
a plain dict (not an evidence record) since it crosses snapshot boundaries and has
no single snapshot_id to attribute to.

**sample_data_v2 changes.** Three intentional changes from v1: (1) WO-PAST-001
removed (demand cancellation scenario), (2) WO-1002 due date tightened from
2026-08-20 to 2026-07-20 (supply chain pressure scenario), (3) M-CAST-01 cost
rate increased 5.0 -> 7.5 in costmodel.json version 2 (supplier price increase
scenario). These three change types (removed entity, field change, config change)
cover the most common production planning re-run triggers.

---

### Amendment — 2026-07-06 (post-Phase-3 gap fixes)

**Fix 1 — Schedule entity persistence (M7 write contract).** M7 built
Schedule/Assignment/ServiceOutcome as plain dicts in the `ExtractResult` struct
but never wrote them to the snapshot store. The write contract (docs/01 §7.3)
requires every non-universal attribute to have a matching ProvenanceSidecar.
M7's `Extractor.extract()` now accepts an optional `snapshot_writer` parameter.
When provided (by `__main__.py` via `store.extend_snapshot(snap_id)`), the
extractor builds canonical Pydantic models — `Schedule`, `Assignment` (with
`ResourceAssignment` + `PhaseWindows`), `ServiceOutcome` (with `lateness:
timedelta`) — and writes them with `DerivedProvenance(formula_id="M7.*_extraction")`
sidecars for all five non-universal attributes on each entity type. The
SnapshotWriter `extend=True` mode appends to existing entity JSONL files without
overwriting the manifest, so M1/M4 entities are preserved.

A new `schedule.csv` output artifact is also written at `mre_output/schedule.csv`:
one row per assignment, columns `work_orders`, `op_seq`, `setup_family`, `machine`,
`start`, `end`, `duration_min`, `production_cost`, sorted by machine then start.
External names are resolved via the `IdentityMap.external_refs()` API (no UUIDs
in output). Merged WorkPackages show both WO names joined with `+`.

18 new tests in `tests/test_schedule_persist.py`.

**Fix 2 — Ghost job exclusion (TEMPORAL_IMPOSSIBILITY policy).** WO-PAST-001
(`due=2025-01-15`) was reaching the solver, dragging `horizon_start` to 2024-12-20
and producing a nonsense −37,739-minute lateness metric in the ServiceOutcome.
**Policy decision: EXCLUDED**, not clamped. Clamping would produce synthetic
`earliest_start` dates that could mislead the solver and obscure the real data
problem. Exclusion is the honest answer: a demand past its due date cannot be
feasibly scheduled, and the finding should say so clearly.

Changes:
- `Validator`: `TEMPORAL_IMPOSSIBILITY` disposition changed from
  `PROCEEDED_FLAGGED` to `EXCLUDED`. The validator now returns
  `ValidationResult.excluded_demand_ids: set[str]`.
- `Planner.run()`: new `excluded_demand_ids` parameter; excluded demands are
  filtered before batch construction — no Fulfillment or WorkPackage is created
  for them.
- `__main__.py`: passes `v_result.excluded_demand_ids` to `Planner.run()` and
  filters `demands` to `schedulable` (non-excluded) before computing
  `horizon_start`. `horizon_start` now derives only from schedulable work.

Two existing tests that asserted `disposition == "proceeded_flagged"` for
TEMPORAL_IMPOSSIBILITY were updated to assert `disposition == "excluded"`.

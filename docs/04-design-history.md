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

---

### Amendment — 2026-07-06 (Phase 3 extension: what-if runner M_whatif)

**What-if runner design.** `python -m mre.whatif --suppress-merge WO-X,WO-Y`
re-runs the full scheduling spine against a copy-on-write scenario snapshot and
returns a cost/lateness diff vs the base schedule. Evidence is isolated to
`mre_output/scenario_runs/` — the main `EvidenceIndex` is never populated with
scenario evidence, so scenario runs cannot contaminate production explanation
queries.

**Snapshot lineage.** `SnapshotStore.derive_scenario_snapshot(src, dst,
entity_types)` copies only M1-written input entities (demand, product, resource,
calendar, constraint, costmodel, process, operationspec) plus the identity map.
No provenance.jsonl is copied — downstream modules write their own. The manifest
records `parent_snapshot_id` and `snapshot_type="scenario"` for traceability.

**Modification decisions.** Each scenario modification is emitted as a
`DecisionType.SCENARIO_MODIFICATION` record (`basis=policy_applied`,
`driver=POLICY_RULE`) in the scenario's run evidence. `suppress_merge` records an
alternative noting the setup amortization trade-off. These are the scenario's own
institutional memory.

**Measured setup cost trade vs estimated_benefit discrepancy.**

The Planner's merge decision (D-07, docs/04) records:

    estimated_benefit = (len(batch) - 1) × setup_cost_per_setup = 1 × $50 = $50

This counts "WPs avoided" (1 merge saves 1 WorkPackage). The Extractor's cost
model bills one setup charge per *operation* (`setup_cost = len(ops) ×
fixed_per_setup`). When WO-2001 + WO-2002 merge into a single WP containing 2
operations, setup cost = 2 × $50 = $100. When unbatched, each WP has 2 operations:
4 operations total × $50 = $200. The measured setup delta is **+$250**, not +$50.

The discrepancy (×5) arises from two compounding factors:
1. The planner's model counts 1 avoided setup per merged WP; the extractor bills
   per operation (2 ops per WP × factor).
2. Unbatching frees the two WOs to be scheduled on different machines at different
   times, causing 88 assignment moves and cascading re-sequencing across the shop.
   These moves shift other demands, incurring additional setup charges.

Net result on the 34-demand sample: **total cost decreases by $260** when
unbatching WO-2001/WO-2002 — because eliminating WO-2001's 840-minute tardiness
saves $840 in tardiness cost, outweighing the $250 increase in setup cost and
$330 increase in production cost (WO-2001 now runs on M-GEAR-01 at a higher rate
than the merged WP used).

Recording this discrepancy here, not in the planner code: the planner's
`estimated_benefit` is a planning-time heuristic for batch selection, not a
contract for the realized cost delta. The scenario runner is the right tool for
measuring actual trade-offs.

**REPL integration.** The `ask.py` REPL detects "what if we unbatch WO-X and
WO-Y" phrases and routes them to `ScenarioRunner` before the normal explainer
routing. The rendered diff is added to session history so the LLM judgment path
can reference it in follow-up turns. The CLI `python -m mre.whatif` is the
non-interactive path; the REPL phrase is the dialogue-mode path.

**Vocabulary addition.** `DecisionType.SCENARIO_MODIFICATION` added to
`vocabularies.py`. This is a add-never-repurpose entry; the spec in
`docs/02-evidence-contract-spec.md` should be updated at next spec review.

**524 tests green** after this amendment.

---

### 2026-07-06 — LLM testimony validator: single-source-of-truth refactor

**Root cause.** The `LLMRenderer` had two parallel derivations of "what values
is the LLM allowed to quote":

1. `_llm_render` builds a prompt that includes a **PRE-COMPUTED FACTS** section
   (`_extract_precomputed_facts`) alongside the template-rendered evidence chain.
2. `_validate_testimony` re-derives the verifiable set from `bundle_body + kf_text`
   — a different combination that excludes any future content added to the prompt
   but not present in those two sources.

This is a latent defect: as soon as any content is added to the prompt that is
not also in `kf_text` or the rendered body, the validator incorrectly rejects
the LLM's legitimate quote of that content.  The recurring production failure
(validator flagging `"2026-07-13T23:59"` as unverifiable even though the demand's
due date appears in the prompt headline) revealed this fragility.

**Decision.** Collapse the two paths into one: `_build_prompt_material(bundle,
regen_note=None)` returns `(prompt_text, known_ts, known_time, known_machines)`.
The three verifiable-value sets are extracted from `base_evidence` (the prompt
text without the regen_note header) using the same three regexes that `_validate_testimony`
applies to the LLM's response.  Both `render()` and the validator use this single
function.  `_llm_render` and `_collect_known_time_values` are removed.

**Critical safety rule.** When regenerating, the `known_*` sets from the
*first* prompt are reused for validating the second response.  The regen prompt
prepends a header that repeats the rejected values ("PREVIOUS ATTEMPT REJECTED:
unverifiable timestamp '2026-07-14T08:39'").  Extracting known sets from the
regen prompt text would inadvertently whitelist the rejected value — the validator
would then accept any response quoting the same bad timestamp.  Extracting from
`base_evidence` only (stripping the header before scanning) prevents this.

**Tests.** Three integration tests added (through `renderer.render(bundle)` with
`FakeLLMClient`): (1) LLM quoting due-date with seconds stripped passes, (2) LLM
inventing a timestamp absent from the prompt fails and falls back, (3) `known_ts`
and `known_time` from `_build_prompt_material` contain the expected prompt values.
Thirteen existing tests that called `_validate_testimony(text, bundle)` directly
are updated to go through `_build_prompt_material(bundle)` to get the known sets —
this is now the only live path and the only tested path.

**527 tests green** after this amendment.

---

### 2026-07-07 — First real-data ingestion: raw_data/ hardening (M1 + M3)

**Reference-date concept.** A new field `reference_date` in `plant_config.json`
establishes the scheduling "now" for every temporal computation (demand filtering,
TEMPORAL_IMPOSSIBILITY, horizon math). Validator receives `reference_date` as an
explicit parameter; when provided it replaces `datetime.now(UTC)`. The design
enables historical-replay runs: a schedule produced against `2025-03-22` data is
reproducible months later because no module reads the wall clock. The rule is: any
module that needs "now" reads it from `reference_date`, never from `datetime.now()`.

**Product-resolution correction: WO.ProductNo, not Routing.ProductNo.**  The
legacy pipeline resolved `Product` via `Routing.ProductNo`. For generic routes
(`ProductNo = 0`), no product was found and the WO was silently dropped with no
finding. The correction: `Product` is resolved via `WO.ProductNo` in all cases.
Generic routes (where the Routing table's ProductNo = 0) are now treated as normal;
the WO's own ProductNo determines the product. Recorded in the raw adapter code as
a named correction; the Amendment log is the institutional memory.

**Duration-semantics RULING (provenance policy "legacy_author_definition_v1").**
The legacy ProFunctv2 implementation applies the full `ProductionMinutes /
CostingLotSize` run rate *to each operation independently* — the rate is not split
across operations or accumulated at the route level. Likewise `SetUpMinutes` is the
per-operation setup, not a route-level total. This interpretation reproduces the
legacy scheduler's time estimates and was confirmed as the ruling on 2026-07-07.
All `run_rate` and `base_setup` values in real-data OperationSpecs carry
`DerivedProvenance(formula_id="legacy_author_definition_v1")`, so every consumer
of these values can trace the origin and the ruling in one hop.

**Process keyed by (route_code, product_no).** Because a generic route (ProductNo=0)
may serve many products, each with its own `CostingLotSize` and `ProductionMinutes`,
a single route yields multiple Processes — one per (route, product) pair.
`Process.id = stable_id("process", f"{route_code}:{product_no}")`. This makes
rates product-specific without copying RoutingLines.

**SalesOrder deferred.** `SalesOrder.csv` is not read in round one. It is
explicitly out of scope: `commitment_class` and `customer_weight` are defaulted on
every Demand with `DefaultedProvenance(policy="plant_config_v1")`. A
`LOW_CONFIDENCE_INPUT / WARNING / disposition=defaulted` finding is emitted for the
CostModel since no cost rates exist in the raw extract.

**setup_family proxy retired for real-data runs.** The validator's
STATISTICAL_OUTLIER grouping previously used `spec.setup_family` as a proxy for
product family when `product_family` was absent (sample_data used `setup_family`
values like `"gear_cutting"`). Real data has `Product.ProductGroup` mapped to
`product.product_family`; the outlier check now preferentially uses
`spec_to_family[spec_id]` (derived from process → product chain) and falls back to
`spec.setup_family` for backward compat with sample_data tests. The fallback will
be removed when sample_data is migrated.

**INFEASIBLE_SUBSET severity=ERROR not BLOCKER.** CLAUDE.md item #2 originally
specified `severity=blocker` for the pre-solve window-fit check. The real-data
context changes the calculus: with hundreds of demands, the DQ report must survive
even when some demands are INFEASIBLE_SUBSET so the full scope of exclusions is
visible. `severity=ERROR + disposition=excluded` achieves the correct effect
(demand removed from planning) while allowing the pipeline gate to remain GO.
A BLOCKER would abort the run before the DQ report completes — defeating its
purpose. CLAUDE.md will be updated at next spec review to reflect ERROR.

**test_zero_quantity_flagged due-date fix.** The test used `due=datetime(2026, 6, 1)`
which was future when written but became past by 2026-07-07. The
TEMPORAL_IMPOSSIBILITY check ran first, excluded the demand, and the
VALUE_OUT_OF_RANGE check never saw it. Fixed to `due=datetime(2035, 6, 1)`. Root
cause recorded: unit tests that validate behavior relative to "now" must either use
a far-future date or supply an explicit `reference_date` to `Validator.run()`.

**554 tests green** after this amendment (527 pre-existing + 27 new raw adapter
tests in `tests/test_raw_adapter.py`, fixture at `tests/fixtures/raw_data_mini/`).

---

## Amendment — 2026-07-07: Real-data solver INFEASIBLE root cause and fix

**Context.** First run of the full pipeline against real extracted data
(`python -m mre --raw-data raw_data --plant-config plant_config.json`) returned
`status=INFEASIBLE` in 0.29 s despite only 23% average resource utilization and
the validator correctly excluding all 173 WOs whose operations exceeded the 720-min
shift window.

**Root cause: horizon buffer mismatch.** Two independent buffer values controlled
the planning window: `__main__.py` pre-flattened calendars with `+14 days` beyond
the latest demand due date, while `solver_builder._compute_horizon` added only `+7
days`. The effective scheduler boundary therefore ended at the last calendar shift
close on day +7 (2025-05-05 19:00 = offset 99060 min), while `horizon_minutes` was
99359. The solver's blocking interval for the overnight gap [99060, 99780] straddled
the horizon boundary. CP-SAT's energy-based propagation (`not-first/not-last`,
edge-finding) proved that the mandatory operations could not be packed into the
remaining calendar windows — even though simple utilization math showed slack. The
culprit WP was isolated by binary search to position 1806 (PP10299762, three 78-min
operations on F008/* machines).

**Fix.** Both buffer values raised from +7/+14 days to **+90 days** in
`solver_builder._compute_horizon` and in `__main__.py`'s calendar pre-flattening.
Result: real-data pipeline reaches FEASIBLE in 108.59 s (2864 WPs, 13315 ops, 93
resources). All 2864 demands are LATE — expected, since the historical extract's WOs
were overdue as of reference_date 2025-03-22.

**Lesson: horizon mismatch is a silent feasibility bug.** When the solver's internal
horizon is narrower than the pre-flattened calendar window, the last blocking
interval straddles the boundary and creates a hard constraint that no admitted
operation can satisfy. The symptom (instant INFEASIBLE at low utilization) is
counter-intuitive. Any change to horizon computation must update all three locations
consistently: `solver_builder._compute_horizon`, `__main__.py` calendar flattening,
and `test_phase2_integration.py` (which hardcodes `+14 days` for the sample-data
fixture and must remain unchanged as a regression anchor).

**merge_by_family_v1 infeasibility.** Separately, `merge_by_family_v1` was
infeasible on real data for a different reason: merged WorkPackages accumulate
operation durations proportional to total batch quantity. With dozens of demands per
product family, merged operations exceeded 720 min (the single-shift constraint
window), violating the CP-SAT `add_no_overlap + calendar-blocking` model regardless
of horizon size. The pre-solve `INFEASIBLE_SUBSET` check catches this for individual
demands but has no visibility into post-merge sizes.

**Decision: change default policy to `identity_v1`.** Because `merge_by_family_v1`
creates post-merge infeasibility that the solver cannot recover from and the
validator cannot yet catch, the CLI default in `__main__.py` was changed to
`identity_v1`. `demo.py` and `test_phase2_integration.py` continue to use
`merge_by_family_v1` explicitly, preserving the merge demo and its test coverage.
`identity_v1` is the safe, always-feasible baseline; batching is opt-in.

**CLAUDE.md task 2 (post-merge infeasibility check) remains open.** The correct
long-term fix is either (a) a post-merge INFEASIBLE_SUBSET check in the validator
that runs after M4 and before M5, or (b) a merge-policy limit that caps merged
quantity so that `run_rate × batch_qty + setup ≤ shift_window_minutes`.

**CLAUDE.md task 2 (pre-solve infeasibility test) completed in this session.**
`TestInfeasibleSubset` in `tests/test_validator.py` creates a minimal snapshot with
qty=1 demand, run_rate=PT3000M OperationSpec, and a 720-min shift calendar, then
asserts: (a) INFEASIBLE_SUBSET finding emitted, (b) demand in `excluded_demand_ids`,
(c) gate remains GO (severity=ERROR not BLOCKER), (d) evidence records
`estimated_duration_minutes ≥ 3000` and `max_window_minutes ≤ 720`. A reusable
`_synth_prov` helper in the test module generates SynthesizedProvenance for all
non-universal entity fields, satisfying the snapshot store's write contract.

**558 tests green** after adding 4 new INFEASIBLE_SUBSET tests.

---

## Amendment — 2026-07-07: REP 1 — First real solve telemetry and horizon-slice policy

**Solve telemetry (full backlog, 300s).** First full real-data solve against the
2025-03-22 snapshot with 2864 admitted WPs / 13315 operations:

| Metric | Value |
|--------|-------|
| Status | FEASIBLE |
| Wall time | 312.68 s |
| Objective | 29,323,488 (all tardiness; prod/setup = 0) |
| Gap (LP bound) | 87.4 % |
| Demands: LATE | 1745 (61 %) — late p50 = +9,644 min (161 h) |
| Demands: EARLY | 1119 (39 %) — early margin p50 = 9,324 min (155 h) |
| schedule.csv rows | 13,315 |

**Gap interpretation.** The 87.4 % LP bound gap is structural to minimum-tardiness
scheduling in CP-SAT: the LP relaxation ignores `add_no_overlap` timing constraints
and produces a near-zero lower bound even for well-solved instances. This gap does
NOT indicate that the solution is far from optimal — it indicates that CP-SAT cannot
PROVE optimality within practical time. Running 3× longer (90 s → 300 s) improved
the objective by only 0.8 %; the solver is in a FEASIBLE plateau. The gap was also
~87 % on a 7-day demand slice (1318 WPs, 31 s), confirming it is problem-structure-
driven, not problem-size-driven.

**Demand distribution.** All 2864 admitted demands have due dates in the range
2025-03-24 to 2025-04-28 (reference_date 2025-03-22 + 0–37 days). There is no
meaningful "outside the horizon" cutoff at typical slicing granularities: 45 % are
due within 7 days, 86 % within 14 days, 100 % within 45 days.

**Decision: add `--horizon-days N` demand-selection policy.** Per CLAUDE.md REP 1
clause ("If solve quality is poor, add a horizon-slice Demand-selection policy"):
added `--horizon-days N` CLI flag to `__main__.py`. When specified, demands with
`due > reference_date + N days` are added to `excluded_demand_ids` before M4 runs.
Recorded as a `Decision(decision_type=model_simplification, driver=POLICY_RULE,
basis=policy_applied)` in a brief M4 reporter run. With `--horizon-days 7`: 1546
demands deferred, 1318 WPs remain, FEASIBLE in 31 s. Intended use: focus the
solver on the most-urgent backlog tier when the operator wants a provably-good
near-term schedule rather than a best-effort backlog sweep.

**5 new tests** in `tests/test_horizon_slice.py` verify: pipeline succeeds,
MODEL_SIMPLIFICATION/POLICY_RULE decision emitted, decision message mentions cutoff
date, beyond-horizon WOs absent from schedule.csv, within-horizon WOs present.

**563 tests green.**

## Amendment — 2026-07-07: Horizon floor clamped to reference_date (BUG FIX)

**Bug.** Real-data solves were scheduling operations before `reference_date`
(2025-03-22). Analysis of a `--horizon-days 7` run showed 14 % of operation
starts as early as 2025-02-26 — roughly four weeks in the past relative to the
planning snapshot.

**Root cause.** Two code sites independently computed the planning horizon start
as `min(earliest_starts)` with no floor at `reference_date`:

1. `solver_builder._compute_horizon` — sets CP-SAT time-zero origin `hs`.
2. `__main__.py` — sets `horizon_start` used for calendar flattening.

`raw_adapter.py` maps `CreatedDate` → `earliest_start` on WorkPackages. Some
real WOs have `CreatedDate` weeks or months before `reference_date` (e.g.,
WO created 2025-02-26, but the snapshot reference is 2025-03-22). With
`hs = 2025-02-26`, the solver could legally start operations as early as
that date, and did.

The existing `wp_earliest_min = max(0, int((es_dt - horizon_start) / 60))`
guard in `solver_builder` (line 202) correctly clamps WP-level earliest start
relative to `hs`, but only once `hs` itself is correct.

**Fix.**

- `SolverBuilder.__init__` now accepts optional `reference_date: datetime`.
  Rationale: `reference_date` is solver configuration (run-time planning floor),
  not a canonical model input — it belongs on the constructor, not `build()`,
  preserving the six-canonical-inputs invariant for `build()`.
- `_compute_horizon` uses `self._reference_date` to clamp:
  `hs = max(hs, reference_date.replace(hour=0, ...))`.
- `__main__.py` clamps `horizon_start = max(horizon_start, ref_floor)` after
  computing it from demand dates, then passes `reference_date=reference_date`
  to `SolverBuilder(...)`.

**Test.** `tests/test_horizon_slice.py::TestNoPreReferenceDateStarts` runs the
mini fixture (WO-A001 has `CreatedDate=2025-03-20`, two days before
`reference_date=2025-03-22`) and asserts `min(assignment.start) >= 2025-03-22`.

**565 tests green.**

---

## Amendment — 2026-07-08: IDS adoption — conformance gate + synthetic generator (M0)

**Context.** docs/06-incoming-data-spec.md (IDS) formalizes a narrow-waist
intake surface: N acquisition connectors -> one conformance gate -> the
unchanged M1 adapter. This session built the gate and its executable twin
(the synthetic ERP generator) as a pair, per the standing design principle
that a check and its counterexample-generator keep each other honest.

**Module code addition.** `ModuleCode.M0` added (`src/mre/contracts/vocabularies.py`)
for the gate, which runs *before* M1 in `--submission` mode. `test_exactly_11`
replaces `test_exactly_10` in `tests/test_vocabularies.py`. No Finding or
Driver codes were added — all Tier 1/2/3 gate checks in docs/06 §4 map onto
the existing 17 finding codes (e.g. `ORPHAN_ENTITY` for reference-chain
resolution bands, `UNMAPPABLE_VALUE` for uncovered priority classes,
`AMBIGUOUS_SOURCE` for doorway consistency), confirming the vocabulary's
closed set is expressive enough for a second intake mechanism.

**The costing ruling: $/hour in, $/minute stored.** docs/06 §5.9 expresses
`cost_model.json` rates per HOUR (`default_resource_rate_per_hour`,
`tardiness_cost_per_hour`) because that is what a submitter can state without
knowing this system's internals. The solver (M5) prices in $/minute against
duration-in-minutes (the convention already established by
`sample_data/costmodel.json`). `IDSAdapter` (`src/mre/modules/ids_adapter.py`)
is the one place that divides by 60 — `CostModel.resource_rates` and
`CostModel.tardiness_weights.base_weight` are stored in $/minute in the
canonical model, so no downstream module needs to know two rate units exist.
`core.default_resource_rate_per_hour` is applied as the floor rate for every
resource before `refinements.resource_rates` (per-resource, IDS-external-id
keyed) and `resources.csv.cost_rate` (highest-precedence override) are
overlaid — this preserves the existing "silent zero-default is forbidden"
rule from the 2026-07-06 amendment: every resource gets a real, sourced rate
in the CostModel, never a bare 0.0 for lack of an override.

**Doorway set implemented.** `customers.csv` -> `Demand.customer_ref` +
`customer_weight` (looked up from `cost_model.core.priority_multipliers` per
`manifest.semantics.priority_precedence`; `order_over_customer` /
`customer_over_order` resolve to a single class label today, `max`/`multiply`
fall back to the same single-label resolution — numeric combination of two
multipliers is a deferred refinement, not exercised by any current scenario).
`setup_transitions.csv` -> `Constraint(SETUP_TRANSITION)`, same shape as the
existing JSON-config path. `locks.csv` -> `Constraint(FROZEN_ASSIGNMENT)` for
`lock_type=frozen`, `Constraint(PINNED_WINDOW)` for `pinned_resource`/
`pinned_start` (no dedicated ConstraintType exists for "pin resource, leave
time free" — parameters carry the actual semantics; `provenance_class=
human_override`, `hardness=hard`). Overtime enters via `calendars.csv` `added`
rows with `reason=overtime`, consistent with the existing D-11 seam — pricing
the premium into the objective remains the same deferred extension noted in
D-11, not newly implemented here.

**Solver Builder gains lock consumption.** Constraints were previously
inert data as far as M5 was concerned (only `setup_transition` was read).
`SolverBuilder._apply_lock_constraints` (new, additive) resolves each
`frozen_assignment`/`pinned_window` Constraint's `demand_ref` through the
Fulfillment -> WorkPackage chain to the matching Operation(s) (by `sequence`;
blank sequence was *intended* to mean "the whole order" but is **not**
currently exercised that way — see the locked_plant bug below) and pins the
assignment boolean and/or start-time variable directly. No-op when no lock
constraints are present, so `sample_data`/`raw_data` runs are provably
unaffected.

**Two real bugs found via the generator+gate+pipeline round-trip (exactly
the payoff the pairing is for):**

1. **`Product.process_ref` was always `None`.** The original adapter draft
   wrote `Product` before computing `process_id_for_pair`, then tried to
   "backfill" a field on an already-written (and, by the write contract,
   already-provenanced) entity — which silently did nothing. Every
   `INFEASIBLE_SUBSET` pre-solve check in `Validator` depends on
   `Product.process_ref` resolving to a real `Process`
   (`prod_to_process` lookup); with it always `None`, the check silently
   no-op'd for *every* IDS-sourced snapshot, not just the scenario meant to
   exercise it. Fixed by computing `pairs_needed` / `process_id_for_pair` /
   `prod_first_process` in a first pass (pure ID arithmetic, no writes) so
   `Product.process_ref` is correct at initial write time. Lesson: the
   write-once contract (docs/01 §7.3, `WriteContractError`) makes "write now,
   correct later" a silent no-op rather than a loud failure — sequencing
   must be right the first time when an entity's own fields are
   cross-referential.
2. **`locked_plant`'s own lock created a false INFEASIBLE solve.** The
   generator picked the *first* routing line's resource but wrote
   `sequence=""` ("whole order") to locks.csv. For a 2-3 step route, that
   pins *every* operation in the WorkPackage to the identical start minute —
   directly contradicting the intra-WorkPackage precedence constraint
   (`op[i+1].start >= op[i].end`), so the model was infeasible by
   construction. Fixed by writing the specific `sequence` of the routing
   line actually being locked. The generator and the solver disagreed about
   what "lock the order" means; making the generator's intent explicit
   (lock *one* operation) resolved it. Verified: the locked operation's
   `schedule.csv` row now shows the exact pinned resource and start
   (`tests/test_ids_end_to_end.py::TestLockedPlantScenario`).

**One scenario-tuning fix (not a code bug).** `priority_pressure`'s first
draft resized every product's rate uniformly to create the bottleneck, which
pushed several *unrelated* orders' operation durations past the 720-minute
shift window and tripped `INFEASIBLE_SUBSET` for most of the dataset — the
gate/pipeline correctly caught bad test data. Fixed by scoping the rate
override to only the two competing orders' own routes
(`_apply_bottleneck` in `tools/generate_erp_dataset.py`). The harness asserts
the *relative* property (`critical order's completion <= standard order's
completion`) rather than literal on-time completion, since the deliberately
tight shared-resource contention makes both orders late by construction —
the property under test is that priority pressure changes *scheduling
order*, not that it defies physics.

**Generator bug: `setup_family` populated by default.** The first draft set
`setup_family` on every routing line unconditionally (for realism), which
made every non-`transition_heavy` scenario spuriously trip the
`setup_family_without_matrix` doorway-consistency check and downgrade from
ACCEPTED to CONDITIONAL. Fixed: `setup_family` is blank unless a scenario
explicitly opts in (`transition_heavy`, or the `setup_family_without_matrix`
anomaly itself).

**Harness.** `tests/test_ids_end_to_end.py` — for every scenario in
`tools/generate_erp_dataset.SCENARIOS` (excluding `clean_large`, marked
`@pytest.mark.slow`, opt-in via `--runslow`): generate -> gate -> assert
certificate grade and costing grade against `truth_manifest.json` -> assert
every seeded anomaly's expected finding code appears somewhere in the full
evidence stream (the gate's own certificate for structural/integrity/quality
defects; the full pipeline run for solve-time defects like
`chunking_exam`'s `INFEASIBLE_SUBSET`, which only M3 can see) -> for
non-REJECTED scenarios, run the full pipeline via `--submission` and assert
scenario-specific schedule properties (lock respected, priority-pressure
ordering, transition gap honored, oversized orders excluded). Deterministic
via seed.

**Pipeline-proof rule applied.** Per docs/06 §8, a capability is
pipeline-proven only when intake doorway + gate check + adapter translation +
generator scenario + schedule-level assertion all exist. By that bar:
customers/priority (`priority_pressure`), setup_transitions
(`transition_heavy`), and locks (`locked_plant`) are now pipeline-proven, not
merely model-proven. Overtime pricing remains model-proven only (calendar
fact recorded; premium not yet in the objective) — tracked as a deferred
doorway per docs/06 §8, consistent with D-11.

**docs/06 housekeeping.** The spec file was found on disk as
`docs/06-incoming-data-spec-v0.2.md` (drafted in a prior session, never
committed) and renamed to `docs/06-incoming-data-spec.md` to match the
`0N-title.md` convention of docs 00-04 — the version lives in the document's
own "Status:" line, not the filename.

**Test count.** 565 pre-existing + 18 new generator tests
(`tests/test_generate_erp_dataset.py`) + 16 new gate tests
(`tests/test_conformance.py`) + the end-to-end harness
(`tests/test_ids_end_to_end.py`, parametrized across 7 non-slow scenarios plus
5 dedicated scenario-property tests, `clean_large` opt-in). 624 tests green
after this amendment.

---

## Amendment — 2026-07-09: Precedence edges become first-class records (docs/05 §4 surgery)

**What moved.** Per docs/05 R-A2/A3 and R-Dwell: `Operation.predecessors`
(always empty in practice — nothing ever populated it) and
`Operation.dwell_duration` / `OperationSpec.dwell_rule` (always zero — no
data source ever fed them) are removed. A new entity, `PrecedenceEdge`
(`{id, snapshot_id, predecessor, successor, min_lag, max_lag}`), carries
precedence and lags instead. `predecessor`/`successor` are **OperationSpec**
refs, not Operation refs — the edge is template-level (one linear chain per
Process, reused by every WorkPackage that instantiates it), consistent with
how OperationSpec itself is quantity-independent (D-10). docs/01 §5.4/§5.4a
and §6.3 updated in this commit; docs/01 §8 invariant 6 updated to note
PrecedenceEdges ride in the WorkPackages+Operations bucket of the Solver
Builder's six inputs, not a seventh.

**Four consumers, as docs/05 §4 specified:**
1. **Contracts** (`src/mre/contracts/entities.py`) — `PrecedenceEdge` added;
   `predecessors`/`dwell_duration` removed from `Operation`; `dwell_rule`
   removed from `OperationSpec`.
2. **All three adapters** (`adapter.py`, `raw_adapter.py`, `ids_adapter.py`)
   — each now synthesizes a linear chain of edges from routing-line sequence
   order after writing a Process's OperationSpecs (`_synthesize_precedence_pairs`,
   new shared helper in `adapter.py`, imported by the other two).
   `ids_adapter.py` is the one adapter with a real dwell source
   (`routing_lines.dwell_minutes`); its dwell value lands as `min_lag` on the
   *outgoing* edge of the spec it follows, with `DerivedProvenance`
   (`formula_id="ids_dwell_to_min_lag"`). The other two adapters have no
   dwell column in their source data (confirmed: sample_data's
   `routinglines.csv` and the real ticketing extract's `RoutingLines.csv`
   both lack one — `RoutingLines.TargetTime` is 0% populated per
   `raw_data_profile.md`), so their edges carry `min_lag=0` with
   `DefaultedProvenance(policy="no_dwell_source_in_...")`. `max_lag` is
   `None` (unconstrained) from every adapter — no doorway exists yet
   (docs/06 §8, tracked as A3 in docs/05).
3. **Solver Builder** (`solver_builder.py`) — the old implicit
   `sequence`-sorted precedence loop is replaced by `edges = [d for d in
   work_items if "predecessor" in d]`, resolved to concrete Operations per
   WorkPackage via `spec_ref` (`ops_by_wp_and_spec`), enforcing
   `succ.start >= pred.end + min_lag` and, when `max_lag` is not `None`,
   `succ.start <= pred.end + max_lag`. `_apply_lock_constraints` (the
   2026-07-08 locks doorway) and the transition-constraint pass are
   unaffected — both already worked from `operations`/`constraints`
   directly, not from the old precedence loop.
4. **WIP semantics** (docs/06 §5.13) — no code yet (still docs-only per the
   2026-07-08 amendment), but the "downstream operations chain from this
   fixed reality" sentence now explicitly says this chaining walks
   PrecedenceEdge records, the same edges the Solver Builder reads for
   ordinary precedence — so when WIP lands, an in-flight operation's
   successor is found by graph walk, not by re-deriving sequence order.

**The defaults-reproduce-baseline gate — and what capturing it actually required.**
Golden baselines were captured *before* any code changed
(`tests/fixtures/baselines/{sample_data,gauntlet}_{schedule.csv,summary.json}`),
per the docs/05 §3 modularity gate. Two things had to be solved to make
"identical schedule" a checkable claim rather than an aspiration:

- **CP-SAT's default parallel search is not reproducible run-to-run**,
  confirmed empirically before touching any surgery code: two stock runs of
  the *unchanged* sample_data pipeline produced different resource
  assignments (which of two equal-rate casting machines, which order among
  same-cost operations) for the *same* proven-optimal total cost
  (24769.00 both times). Bit-identical comparison therefore required pinning
  three independent sources of nondeterminism simultaneously:
  `PYTHONHASHSEED=0` (Python's per-process string-hash randomization affects
  dict/set iteration order, which affects CP-SAT variable-creation order —
  entity IDs are UUID strings), `--solver-workers 1` (CP-SAT parallel search
  is inherently non-reproducible across processes), and `--solver-seed 42`
  (CP-SAT's internal tie-breaking). All three together, on the *same*
  process-per-run `python -m mre` invocation used to capture the fixtures,
  gave bit-identical `schedule.csv` output across reruns. `--solver-workers`
  and `--solver-seed` are new optional CLI flags / `SolveRunner` constructor
  params (default `None` = unchanged parallel-search production behavior —
  this is purely a testing knob, not a production default change).
- **"The gauntlet" baseline uses `--horizon-days 2` against the real
  `raw_data/` extract**, not the full 2864-demand backlog: this slice
  happens to reproduce the documented "173 gauntlet exclusions" number
  (cited repeatedly in docs/05/07) at a size that solves in ~1s and a total
  pipeline wall time of ~6s, making it a fast, real, reproducible regression
  fixture rather than the 100-300s+ full-backlog solve. `tests/
  test_defaults_reproduce_baseline.py::TestGauntletReproducesBaseline::
  test_still_173_infeasible_subset_exclusions` pins that number as a named
  regression anchor independent of the byte-identical CSV comparison.

**A subtle pre-existing quirk had to be preserved, not "fixed."** The old
dwell-gap code reused `_td_to_minutes` (`max(1, int(td.total_seconds()/60))`)
for the predecessor→successor gap, the same helper used for operation
*durations* (where a 1-minute floor exists to avoid zero-length CP-SAT
intervals). Since dwell was always 0 in every dataset, this meant every
consecutive same-WorkPackage operation pair already had an implicit
1-minute gap baked into every historical schedule — confirmed directly in
the golden fixture (`WO-1001` seq 10 ends `07:36`, seq 20 starts `07:37`,
seq 30 starts `08:14` after seq 20 ends `08:13`). R-Dwell's semantic intent
is a true zero-lag default; the edge-based `min_lag` code reuses the same
`_td_to_minutes` floor rather than "correcting" it to true zero, because
correcting it would shift every downstream operation's start time by a
minute and fail the defaults-reproduce-baseline gate. Recorded here as a
known, deliberate, non-obvious behavior — worth revisiting the day dwell
values are real and the 1-minute floor's origin (an accidental side effect
of code reuse, not a deliberate design choice) stops being harmless.

**docs/05 status column moved on evidence, not aspiration.** A1
(finish-start precedence) was already marked PP; unaffected. A2 (min lag
incl. dwell) moves from "MP→PP with edge surgery" to a corrected **MP**
pending its actual PP bar (docs/06 §8 full chain: a gate check for
malformed dwell values, and the `dwell_heavy` generator scenario docs/07
Phase 1 already lists as backlog) — the edge-surgery portion is done and
cited, but "the mechanism works" and "the full pipeline chain is proven" are
different claims, and docs/05 §5 explicitly warns against blurring them. A3
(max lag) moves from **UI** to **MP**: the Solver Builder now honors
`max_lag` when present (`tests/test_precedence_edges.py::test_max_lag_enforced`),
though no doorway populates a non-`None` value yet.

**New tests.** `tests/test_precedence_edges.py` (14 tests) — entity
defaults, `_synthesize_precedence_pairs`, field-removal assertions on
`Operation`/`OperationSpec`, edge synthesis from each of the three adapters
(including the IDS adapter's dwell→min_lag mapping via an injected
`dwell_minutes` value), and direct Solver Builder tests proving both
`min_lag` and `max_lag` are enforced (and that `max_lag=None` stays
unconstrained). `tests/test_defaults_reproduce_baseline.py` (5 tests) — the
gate itself, described above.

**629 tests green** after this amendment (624 + 14 new precedence-edge tests
+ 5 new baseline-reproduction tests; existing-fixture edits for the
field removals changed no test counts).

---

## Amendment — 2026-07-10: Chunking week-one spikes (docs/07 §2 risk #1) — element-table encoding falsified, chunk-boundary-interval encoding verdicted YELLOW

Two scratch-script spikes (no production code; `tools/chunking_scale_spike.py`,
`tools/chunking_spike2.py`, full data in their companion `_report.md` files)
tested candidate CP-SAT encodings for R-C3 resumable operations before
committing to Rep 2 (chunking) in full — the roadmap's first week-one spike.

**Spike 1 — start-indexed elapsed table via `AddElement`: FALSIFIED.** One
interval per operation, `elapsed = table[start]`, tested both dense
(per-minute) and pruned (coarse-grid) table strategies. Dense tables grow
linearly in `horizon_minutes × n_resumable_ops` — confirmed at 531K/2.55M/
7.8M entries for a 7d/30d/90d horizon at N=300 — and the CP-SAT backend
**crashed with `MemoryError`** handing the N=3,000 dense tables to
`solver.Solve()`. The pruned strategy kept model size modest (comparable to
the non-resumable baseline, +20-25%) but **never found a first feasible
solution within 60 seconds at N≥300**, at any scale, with or without an
objective (confirmed via a control run with the objective stripped — ruling
out "hard to prove optimal" in favor of "hard to find any solution at all").
The failure was non-monotonic in N (solves at 10/50, fails at 100, solves-
slowly at 200, fails at 300+) — the signature of weak constraint
propagation from the `AddElement`/dual-no-overlap-group structure, not a
clean size-vs-time curve. Verdict: **RED**, reported before building.
Suggested redesign direction: explicit chunk-boundary intervals — R-C3's
own text already points there ("chunk boundaries are calendar boundaries,
so chunk count = windows crossed — bounded by construction").

**Spike 2 — explicit chunk-boundary intervals: YELLOW.** One optional
interval per resumable operation *per calendar window it could occupy*
(pruned to a feasible range), all in the resource's single native
`add_no_overlap` alongside non-resumable and calendar-blocking intervals —
no lookup tables. Three constraints: chunk durations sum to the working
duration; gluing (a chunk followed by another chunk of the same op must run
to its window's end, the next must start at the next window's open —
`OnlyEnforceIf` accepts the two-literal list directly, no auxiliary boolean
needed); contiguity (exactly one "start transition" and one "end
transition" among the used-window booleans — the same transition booleans
double as the op's overall start/end for the objective, at no extra cost).
Because chunk intervals are bounded to their own window by construction,
they can never overlap a calendar-closure blocking interval, so — unlike
spike 1 — one `add_no_overlap` group per resource suffices; no split
needed.

Tested at two densities: **realistic** (~1% resumable, the deployment
shape) and **stress** (20% resumable, spike 1's ceiling-finding setup,
not a deployment target). Realistic density **solved correctly at all
three scales** (300/3,000/10,000 ops), first feasible in 0.13s/1.59s/10.0s,
model-size overhead modest (~1.6-2x the baseline's variables/constraints),
and the required post-solve semantic assertion — every derived pause window
aligns exactly with a real calendar closure — held at every rung (3, 34, 94
chunked operations verified). Stress density failed cleanly and
*consistently* at all three scales (not scale-dependent, unlike spike 1's
erratic pattern) — pointing at a density ceiling around ~4-4.5 resumable
ops sharing one resource, independent of total N.

Two named mitigations for the stress-density ceiling were **tested, not
just proposed**: warm-start hints (`AddHint` on a greedy front-loading
assignment) did not help — still unresolved after 60s. Per-resource
decomposition **did**: three sampled single-resource shards from the same
N=3,000 stress scenario (matching its per-resource resumable density
exactly) each solved to feasible in under 0.2 seconds, isolating the
difficulty to the *global* cross-resource model, not the per-resource
encoding itself.

**Verdict: YELLOW.** Build Rep 2 on the chunk-boundary-interval encoding;
ship unconditionally for the realistic density; fall back to per-resource/
per-facility decomposition (architecturally the same fallback already
planned for the unrelated solver-gap risk, docs/07) if a facility's
resumable density approaches the stress regime. Do not rely on warm-start
hints for that case.

**A minor `add_hint` API lesson recorded for future spikes.** `CpModel.
add_hint(var, value)` takes one variable and one value — not batched lists
(`add_hint(vars, values)` raises `TypeError` deep inside ortools' internals
with a confusing message, `'>=' not supported between instances of
'builtin_function_or_method' and 'int'`, because it iterates the list
argument as if it were a single `IntVar`). Call it once per (var, value)
pair.

No production code changed by either spike; `src/mre/` is untouched. Test
suite unaffected (still 629 green) — these are standalone scripts under
`tools/`, not covered by `pytest`.

---

## Amendment — 2026-07-11: Rep 2 — resumable operations productionized (docs/05 R-C3)

**Encoding decision.** The chunk-boundary-interval encoding verdicted
YELLOW in spike 2 (`tools/chunking_spike2_report.md`) is now production
code in `SolverBuilder._build_resumable_operation`. The element-table
encoding from spike 1 (`tools/chunking_scale_spike_report.md`) remains
falsified and was never built. One optional interval per (eligible
resource, candidate calendar window) chunk slot, all in that resource's
single native `add_no_overlap` alongside non-resumable and calendar-
blocking intervals — chunk intervals are bounded to their own window by
construction, so they can never overlap a closure, meaning no split
no-overlap group is needed (unlike the falsified encoding). Three
constraints per resumable operation, generalized from the spike to handle
genuine multi-resource eligibility (the spike fixed one resource per op):
duration-sum (scoped `OnlyEnforceIf` the chosen resource, since only one
resource's chunks may be non-zero), gluing (`OnlyEnforceIf` a two-literal
list — no auxiliary boolean needed, matching the spike's finding), and
contiguity (single start/end transition, which double as the operation's
overall start/end for the objective and WorkPackage-end/tardiness — again
matching the spike). `CHUNKS_MAX` is computed per operation from its actual
working duration and the shortest candidate window, not spike 2's hardcoded
constant (4, sufficient only for its synthetic "1-3x window" duration
assumption) — real durations are not bounded that way.

**IDS doorway (item 1).** `routing_lines.splittable=true` declares the RUN
phase resumable (R-C3's default is non-resumable for run, resumable for
setup/teardown). Rather than model setup/teardown resumability separately
(no `teardown_duration` field exists on `Operation`/`OperationSpec` yet —
out of scope), a resumable operation's setup and run durations are folded
into one chunked "working duration" total — this is a deliberate
simplification, not a redesign seam: it makes setup effectively resumable
too (since it now shares the same multi-window chunking), consistent with
R-C3's default, while `splittable=true` remains the single switch that
enables chunking at all. `min_chunk_minutes` forbids chunks shorter than it
(`OnlyEnforceIf` the chunk's `used` boolean). `ids_adapter.py` previously
declared `min_chunk` provenance without ever parsing the column — a latent
bug (same shape as the 2026-07-08 `Product.process_ref` incident: a field
that looks populated but silently isn't) — fixed alongside. `planner.py`
had the identical bug for `Operation.min_chunk` (defaulted, never copied
from spec) and `splittable` copy-through was already correct; both are now
copied with `DerivedProvenance`, no more `DefaultedProvenance` placeholder.

**Validator, two additions (item 3).**
(a) Class-aware window-fit: non-resumable operations keep the existing
longest-contiguous-window check unchanged. Resumable operations are tested
against total working time available — the best eligible resource's weekly
open minutes (`_weekly_open_minutes`, new — open days/week × shift length),
scaled to the calendar time between `reference_date` and the *demand's own
due date* (not a global horizon, which the validator does not have at this
point in the pipeline — the due date is a real, available, meaningful
bound: "even chunked, can this finish before the customer needs it?").
`INFEASIBLE_SUBSET` fires only when even chunked it cannot fit.
(b) Density guard: resumable operations per eligible resource > 3 emits
`STATISTICAL_OUTLIER` (broadened, defensible reuse — no new finding code:
an unusual concentration is a distributional-threshold flag, the same kind
of check the code already performs for run-rate outliers), severity
`warning`, disposition `proceeded_flagged`, citing spike 2's measured
ceiling (~4-4.5 resumable ops/resource) and decomposition as the mitigation
in `disposition_detail`. Approximated at demand/spec granularity — Planner
has not run yet at validator time, so concrete Operations don't exist.

**Extraction (item 4).** `SolveValues.op_chunk_windows` (new) carries, per
chunked operation, the actual (start, end) minute pairs the solver used —
populated by a new `VariableMap.op_chunks` registry of chunk-slot variables
recorded during `_build_resumable_operation`. The extractor's production-
cost calculation was a real risk here: billing the OVERALL elapsed span
(first-chunk-start to last-chunk-end) would have charged for the pause as
if it were production time. Fixed by summing each chunk's OWN
(end − start) — exactly the working minutes, never the elapsed span.
`Assignment.phase_windows.run` (already `list[TimeWindow]` — no entity
change needed) carries one window per chunk; pauses are the implicit gaps
between consecutive windows, not a stored field — consistent with the
2026-07-09 removal of `PhaseWindows.dwell` as a first-class phase.

**schedule.csv / viewer.** One row per chunk window, sharing
`(work_orders, op_seq, machine)` as the grouping key; a new `chunk_seq`
column (1-indexed, blank for non-resumable ops) makes the grouping
unambiguous. `production_cost` per row is prorated by that chunk's share of
the assignment's total working minutes (so summing a group's rows
reproduces the assignment's true cost). `schedule_viewer.py` needed no
structural change: `px.timeline` already renders each row as its own bar on
the shared machine row, so consecutive chunks show a natural visual gap
during the pause ("gap", the simpler of the two rendering options offered)
— only `chunk_seq` was added to the hover label.

**chunking_exam redesigned as a positive test.** Pre-Rep-2, this scenario's
oversized operations were *expected* to be `INFEASIBLE_SUBSET`-excluded.
Post-Rep-2 they are genuinely schedulable, so the anomaly now marks its
affected operations `splittable=true` with a calibrated duration (1,500
min, 2.08× a 720-min shift — exactly 3 chunks at a shift-open start: 720 +
720 + 60) and the truth manifest asserts the positive outcome instead
(`expected_finding_code: null`, `expected_chunked: true`,
`expected_chunk_count: 3`). A real bug surfaced while building this: the
original design reused the base dataset's round-robin product pool, which
would have silently given the same abnormal 1,500-minute duration to every
*other* order sharing that product (round-robin cycling means multiple
orders share a product once order count exceeds product count) —
undetected, this would have created unboundedly-long durations on
unrelated orders. Fixed by giving each affected order its own dedicated
product/route/routing_line. `tests/test_ids_end_to_end.py`'s
`TestChunkingExamScenario` is the standing production test for the spike's
semantic assertion: every derived pause is checked, via
`flatten_calendar`, to land exactly on a real closure — not just asserted
by construction, verified against the actual solved schedule.

**Acceptance (item 5).**
(a) `chunking_exam` passes — both affected orders chunk into exactly 3
windows each, `chunk_seq` populated, pauses verified against the flattened
calendar.
(b) Modularity gate: golden fixtures regenerated once, *verified beforehand*
to be byte-identical to the pre-Rep-2 fixtures with the new `chunk_seq`
column removed (`tests/test_defaults_reproduce_baseline.py` — sample_data
and the gauntlet slice have zero resumable ops, so `chunk_seq` is blank on
every row). All 5 baseline tests green with the regenerated fixtures.
(c) Gauntlet re-run (`tools/gauntlet_rescue_report.py`): `raw_adapter.py`
has no real data source for `splittable` (the ticketing extract has no such
column — R-C3's default, correctly, leaves real pipeline behavior
unchanged; inventing a value would violate the no-attribute-write-without-
a-real-basis rule). The report instead runs the counterfactual a plant
conversation would actually ask: if every excluded operation's spec were
declared resumable, how many of the 173 documented `INFEASIBLE_SUBSET`
exclusions would Rep 2 rescue? **116 rescued, 57 genuine survivors** —
each survivor's evidence (`estimated_duration_minutes` vs.
`available_minutes_before_due`) shows a demand whose due date is too close
given the duration and available weekly capacity, regardless of chunking
strategy; none are encoding artifacts.
(d) Scale-ladder timings recorded (`tests/test_chunking_scale_ladder.py`,
realistic ~1% density, through the actual production pipeline — not the
spike's isolated minimal model): N=300 in 4.6s (OPTIMAL); N=3,000 in 97.3s
(OPTIMAL, `--time-limit 60`); N=10,000 in 349-373s (FEASIBLE,
`--time-limit 240`). Two findings worth recording precisely because they
were *not* predicted by spike 2:
  1. **CP-SAT's time-limit enforcement overshoots at this model size** —
     configuring `max_time_in_seconds=240` produced a measured
     `solver.WallTime()` of ~349s (~1.45×), reproduced twice. Not a bug in
     this codebase; a real characteristic to budget for when setting
     production time limits at N≥10,000.
  2. **The full production objective compounds chunking's search
     difficulty beyond spike 2's isolated measurement.** A clean
     (non-resumable) N=10,000 run reaches OPTIMAL in ~60s; adding spike 2's
     validated "realistic density" (~100 resumable ops, well under the
     per-resource density-guard threshold — these use dedicated resources,
     not shared ones) pushed the *same* model to `UNKNOWN` at 120s and
     `FEASIBLE` only at ~350s. Spike 2's model was intervals + no_overlap +
     a bare sum-of-ends objective; production adds cost/setup/tardiness
     terms competing for the same search attention. This means the
     validated ceiling is not simply "~4-4.5 resumable ops/resource" in
     isolation — it interacts with overall model richness. Filed as a
     concrete follow-up for docs/07's parked solver-gap workstream (the
     week-one spike #2 risk in docs/07 §2, "sliced daily solve blessed as
     operational mode") rather than re-opened here: the mitigation
     directions are the same (decomposition, warm-start — spike 2 already
     showed decomposition works and warm-start alone does not) and the
     production number now gives that future work a measured target
     instead of an estimated one.

**docs/05 catalog.** C3 (Interruptibility & chunking) moves from **UI** to
**PP** — the full docs/06 §8 chain now exists: doorway (§5.3
`splittable`/`min_chunk`), gate check (validator class-aware window-fit +
density guard), adapter (`ids_adapter.py` parses both fields), generator
scenario with truth manifest (`chunking_exam`, redesigned above), and a
schedule-level assertion (`TestChunkingExamScenario`'s pause-alignment
check). This is exactly the docs/07 Phase 1 exit criterion ("`chunking_exam`
passes; the gauntlet's 173 window-fit exclusions collapse") — collapse
measured precisely as 116/173, not asserted qualitatively.

**Test count.** 644 tests green (629 + 1 new fast test:
`test_chunking_scale_ladder.py::test_n300`; the N=3,000/N=10,000 scale-
ladder tests are `@pytest.mark.slow`, 8 skipped by default, opt in with
`--runslow`). No existing test's assertions changed except the two golden
`schedule.csv` fixtures (regenerated, verified equivalent modulo the new
column) and `TestChunkingExamScenario` (redesigned per above, expected —
its pre-Rep-2 behavior no longer exists to test).

---

### 2026-07-12 — Vocabulary fix (DENSITY_LIMIT) and Rep 3 outlier recalibration

**Vocabulary governance violation found and fixed.** The Rep 2 density guard
(resumable operations per resource > 3, `tools/chunking_spike2_report.md`'s
validated ceiling) was emitting `STATISTICAL_OUTLIER` — the same code already
used for run-rate distributional deviation within a product family. This is
an add-never-repurpose violation (docs/02 §5): two semantically distinct
signals ("is this data point weird relative to its peers?" vs. "will this
resource's workload be hard for the solver?") sharing one code means trending
either one silently includes the other. **Fixed** by adding `FindingCode.
DENSITY_LIMIT` (18th finding code; docs/02 §4.3 updated with the
distinguishing rationale) and repointing the density guard at it
(`src/mre/modules/validator.py`). Regression guard: `TestDensityGuard` in
`tests/test_validator.py` asserts findings carrying `resumable_op_count`
evidence are never `STATISTICAL_OUTLIER`.

**Rep 3 — outlier threshold calibration.** The `STATISTICAL_OUTLIER` check's
`>10x median` threshold was a fixed constant, never calibrated against a real
distribution. On the gauntlet it fired at 578/4007 = 14.4% of OperationSpecs
with a computable family ratio — not a "these are unusual" signal, a
miscalibrated-threshold signal.

`tools/calibrate_outliers.py` reads every OperationSpec's run_rate from a
snapshot, groups by product family exactly as the validator does, computes
each spec's ratio to its family's median, and reports percentiles pooled
across families **on a log2 scale** (ratios are multiplicative — 0.125x and
8x are symmetric deviations only in log space) rather than per-family
(real family sizes are small and uneven; per-family percentiles are not
statistically meaningful at that sample size). The recommended threshold is
calibrated to the **p99** of the pooled distribution, converted back to a
plain multiplier — targeting the acceptance criterion's hit rate directly
rather than picking another arbitrary constant.

Against the gauntlet snapshot: **p99 = 75.76x** (recommended threshold).
Hit rate at this threshold: **40/4007 = 1.00%**, down from 578/4007 = 14.4%
at the old fixed 10x. Spot-check of the 40 flagged specs: all 40 span only
4 product families (PG111 ×20, PG107 ×8, PG106 ×8, PG104 ×4), and **every
one carries an identical `run_rate_seconds = 60.0`** against family medians
of 0.21–0.50 seconds — consistent with a fallback/default rate (exactly
60s, a suspiciously round number) being applied to specs whose real family
runs in fractions of a second, not natural variance. This is a genuinely
defensible "worth a human look" signal, unlike the old threshold's 578 hits
which mostly just meant the distribution has a long multiplicative tail.

**Validator wiring** (`src/mre/modules/validator.py`): `Validator.run()`
gained `outlier_threshold_ratio: Optional[float] = None`. Default is
`_DEFAULT_OUTLIER_THRESHOLD_RATIO = 75.76`, the gauntlet-calibrated value.
Resolution order: CLI `--outlier-threshold` > `plant_config.json`'s
`statistical_outlier_threshold_ratio` key > the module default (wired in
`src/mre/__main__.py`). The finding's evidence payload now carries
`threshold`, and `threshold_basis` (`"calibrated_v1 from snapshot <id>"`,
or `"config_override from snapshot <id>"` when an explicit value was
passed) alongside the existing `median_seconds`/`ratio` fields, so the DQ
report can say *why* something was flagged, not just that it was.

**Sample-world / demo scenario preserved deliberately, not by accident.**
`sample_data`'s seeded PROD-007 outlier (`DEFECTS.md` #5, corrected here —
it had drifted stale, citing ProductionMinutes=150.0/median≈1.75 when the
actual seeded values are 90.0/2.0 = 45x) and `sample_data_v2`'s identical
scenario are both designed against the *original* 10x threshold. 45x is
comfortably below the gauntlet-calibrated 75.76x, so leaving the new default
in place globally would have silently stopped the demo's seeded defect from
firing. The gauntlet-calibrated value is a property of the one real dataset
this system has been calibrated against, not a universal constant — so
`mre.demo.run_demo` and the sample-data-backed test fixtures
(`tests/test_validator.py::validated_run`, `tests/test_dq_report.py`,
`tests/test_integration.py`) now pass `outlier_threshold_ratio=10.0`
explicitly, each with a comment pointing at this amendment. This is the
config-driven-per-deployment mechanism working as intended, not a special
case bolted on: the demo is a different "deployment" with its own
already-calibrated (by construction) truth manifest.

**Acceptance.** Full gauntlet re-run (`python -m mre --raw-data raw_data
--plant-config plant_config.json --skip-schedule`) confirms 40
`STATISTICAL_OUTLIER` warnings (down from 578). All 648 tests green
(646 + 2 new: `TestDensityGuard`'s 4 methods replace-in-place the
`STATISTICAL_OUTLIER`-based density assertions that existed before the
vocabulary fix; net delta accounts for the `TestDensityGuard` class and the
`test_exactly_17`→`test_exactly_18` rename). Deterministic-mode note: this
recalibration touches only the validator, not the solver, so no
`PYTHONHASHSEED`/`--solver-seed` considerations apply here.

**Rep 4 — merge feasibility & risk guard (merge_by_family_v2).** `identity_v1`
became the CLI default (2026-07-07 amendment above) because `merge_by_family_v1`
creates post-merge infeasibility the solver cannot recover from and had no
economic guard — the $260 unbatch verdict (2026-07-06 amendment) showed its
`estimated_benefit` formula undercounting real setup cost by 5x. `merge_by_family_v2`
(`src/mre/modules/planner.py`) fixes both, gated, and re-enters as a **non-default**
opt-in policy (`--policy merge_by_family_v2`).

*Feasibility gate* (`Planner._check_merge_feasibility`): class-aware window-fit
(docs/05 R-C3), applied to the MERGED batch's total quantity per operation spec
— the check the validator cannot perform per-demand, since it runs before the
planner creates merged quantities. Non-resumable: merged operation must fit the
longest contiguous calendar window on some eligible resource. Resumable: merged
operation's total working time must fit the batch's own horizon (earliest
release → latest constituent due date) on the best eligible resource, even
chunked. Reused helpers `longest_shift_minutes`/`weekly_open_minutes`
(moved from `validator.py` to `calendar_utils.py` so both modules share one
implementation — the validator's per-demand check and the planner's
per-merged-batch check must never silently diverge).

*Risk gate* (`Planner._check_merge_risk`): rejects when estimated tardiness
exposure — the earliest-due constituent's slack consumed by the merged
batch's total duration (working-time budget from release to that demand's
due date, on the representative eligible resource's calendar; NOT raw
wall-clock days — the WO-2001/2002 case shows why: wall-clock budget is
~1439 min, comfortably above the 840-min merged duration, but the *working-
time* budget, which is what the calendar-blocked maintenance closure
actually leaves available, is ~514 min, well under it), priced at that
demand's `customer_weight` — exceeds estimated setup benefit × `risk_margin`
(policy knob, default 1.0, `--risk-margin` CLI flag). The corrected benefit
formula used here (and only here — `merge_by_family_v1`'s original formula
is left untouched, still documented as approximate, to avoid changing its
existing tested behavior): `estimated_benefit = (len(batch)-1) × len(spec_ids)
× setup_cost_per_setup`, matching the extractor's actual per-operation setup
billing. For WO-2001/2002: benefit = 1×2×$50 = $100 (vs. v1's buggy $50);
risk ≈ $840 (merged_duration 840 min − budget ~0 min, since release ≈ due
day) × weight 1.0. $840 ≫ $100 → **rejected**, matching the real recorded
outcome (WO-2001 841 min late). This is the acceptance regression test
(`tests/test_planner_merge_v2.py::TestWO2001RejectedOnRisk`).

*Decisions.* Both gates record their evidence on a Decision even when they
reject, so "why didn't these batch?" is answerable from evidence alone —
`decision_type` stays `DEMAND_MERGE` (still fundamentally a merge decision);
a rejection is distinguished by `chosen.decision == "merge_rejected"`, not a
new closed-vocab `DecisionType` member (avoiding another vocabulary-review
cycle for what is a payload distinction, not a new kind of decision).
`driver=CAPACITY_BLOCKED` for feasibility-gate rejections, `driver=COST_TRADEOFF`
for risk-gate rejections. Accepted v2 merges carry a numeric `estimated_risk`
alongside `estimated_benefit` (docs/02 §4.2's benefit/risk counterfactual pair
— v1's Decision only had a text risk description, never a number).

**Acceptance (item 3c).** (i) `TestWO2001RejectedOnRisk`: WO-2001/WO-2002 no
longer share a WorkPackage under v2; a `merge_rejected` Decision is recorded
with `driver=COST_TRADEOFF`, `gate="risk"`. (ii) `TestProfitableMergeAccepted`:
a synthetic two-demand scenario (same product/family, due dates 60/61 days
out, small quantities) — v2 accepts the merge (`merge_count == 1`), and the
realized cost ledger (`M5`→`M6`→`M7`, run for both `merge_by_family_v2` and
`identity_v1` on the same data) shows `total_cost` strictly lower when merged
— the schedule actually realizes the saving, not just the Decision's estimate.
(iii) `TestGauntletFeasibleWithV2` (`@pytest.mark.slow`, `--runslow`): the full
raw_data gauntlet solves FEASIBLE under `--policy merge_by_family_v2`
(`time-limit 120`, ~140s wall time) — no post-merge infeasibility, confirming
the feasibility gate does its job at real-data scale.

**Item 4 — the declared-but-unread guard.** Third occurrence of this bug
species (after `Product.process_ref` and `Operation.min_chunk`/`OperationSpec.
min_chunk`): an attribute is adapter-written, carries a real provenance
record, looks load-bearing — and nothing downstream reads it.
`tests/test_declared_but_unread.py` runs the Adapter against `sample_data/`,
collects every `(entity_type, attribute)` pair with a real ProvenanceSidecar,
and greps `validator.py`/`planner.py`/`solver_builder.py`/`extractor.py` for a
literal reference. Anything unaccounted must be in `_DORMANT_REGISTER`, and
every entry must cite where the field IS meaningful — a docs/05 catalog id,
a module outside the pipeline's scope, or a named future-work item; a second
test asserts no registered entry has quietly grown a real consumer (register
drift the other way), and a third guards against citing an attribute that no
longer exists.

Running it for the first time surfaced real findings, not hypotheticals:
- **`Resource.cost_rate` is dead** — `solver_builder.py` and `extractor.py`
  both price production cost from `CostModel.resource_rates`
  (`cost_model.get("resource_rates", {})`), never from `Resource.cost_rate`.
  The ERP-sourced field is read only by `conformance.py`'s certificate
  grading. This is a real duplicate-source risk (the two could silently
  disagree) — flagged in the register, not fixed here; worth a product
  decision (should ERP `cost_rate` seed or override `CostModel.resource_rates`?).
- **Resource pooling is declared but not solved**: `solver_builder.py`
  detects a pool only via the presence of a `"concurrent_capacity"` key,
  never reads `ResourcePool.members` or `Resource.pool_refs`, and never
  reads `Resource.capacity` for single resources (always implicit capacity=1).
  Matches docs/05 B5's status exactly (MP, not yet PP).
- **`OperationSpec.yield_factor`** is adapter-written on all three adapter
  paths but never read — docs/05 D3 is MP not PP for the same reason (the
  validation half of D3 exists per its doorway; the "quantity model
  upstream-inflates" half is not yet in `planner.py`).
- **Soft-constraint fields** (`Constraint.hardness`, `.penalty_weight`,
  `.subjects`, `.authority`, `.expiry`) are gate-checked at write time
  (`authority` is "mandatory" per docs/05 A7) but not read by
  `solver_builder.py` — only hard `frozen_assignment`/`pinned_window` locks
  are enforced, and lock targeting is read out of `parameters`
  (`demand_ref`/`sequence`/`resource_ref`/`start`), not the canonical
  `subjects` field. Consistent with docs/05's own Category F rule that
  preference/price belongs in `CostModel`, not `Constraint` — soft-constraint
  penalty pricing simply isn't built yet.
- `CostModel.overtime_premium` is registered dormant too, but is expected to
  be short-lived: it is this session's own next-work item (below).

**657 tests green** (654 + 3 new: `test_declared_but_unread.py`'s three
tests; `tests/test_planner_merge_v2.py` adds 7 more — 6 fast + 1
`@pytest.mark.slow` gauntlet test, not counted in the default run).

## Amendment — 2026-07-12: Overtime premium priced in solves + resource-rates audit closed

Two items from the Phase 1 queue, worked together because the second is a
prerequisite of honest overtime pricing (a premium multiplier on a rate that
doesn't flow is a premium on nothing).

**Item 1 — the resource-rates audit (dormant-register follow-up).** The
2026-07-12 guard finding asked: does `Resource.cost_rate` feed anything, or
does the solver price everything from the cost-model default? Verdict: the
VALUE is consumed — `ids_adapter.py` folds `resources.csv cost_rate` into
`CostModel.resource_rates` under the docs/06 §5.5 precedence (cost-model
default < resources.csv override < refinements.resource_rates), and
solver_builder/extractor price from that dict. The guard's grep couldn't see
it because the fold is adapter-side by design (the builder prices only from
CostModel, docs/01 §8.6). So this was the "guard's trace was incomplete"
branch — but the audit surfaced two real defects on the way:

- **False provenance (fixed).** `IDSAdapter` wrote `Resource.cost_rate=0.0`
  hardcoded while recording an *observed* sidecar citing the `cost_rate`
  column — the entity field lied about both its value and its source. Now
  the entity carries the **effective rate in canonical $/minute**, equal by
  invariant to its `CostModel.resource_rates` entry, with the provenance
  class naming the winning source: observed (csv override), derived
  (refinement), defaulted (cost-model default). The duplicate-source risk
  the register flagged is closed structurally — the two cannot disagree,
  and `tests/test_resource_rates.py` asserts the equality for every
  resource.
- **Sample adapter never folded (fixed).** `adapter.py` read
  `machines.csv CostRate` onto the entity but a machine missing from
  `costmodel.json` silently priced at 0.0 (with only a warning) despite an
  observed rate. Now costmodel.json wins where present and the CSV rate
  fills the gaps; the 0.0 warning fires only when both sources are missing.
  No-op for `sample_data` (its costmodel.json covers all nine machines with
  values equal to the CSV) — verified by the untouched golden baselines.

The register entry for `("resource", "cost_rate")` now cites the verified
consumption path instead of "flagged not fixed". `tests/test_resource_rates.py`
adds the behavioral proof the audit demanded: per-resource rates flip the
solver's machine choice when flipped (builder level), and on a generated C1
scenario the schedule's `production_cost` equals Σ assignment-minutes ×
per-resource rate — and differs from the all-default figure.

**Item 2 — overtime premium (docs/06 §5.6/§5.9).** Calendar `added`
exceptions with `reason=overtime` were already capacity (flatten appends
them); they are now also **priced**. Design decisions worth recording:

- **Premium = overtime minus regular availability.** The builder computes
  per-resource premium minute-windows as the overtime exception windows
  minus every non-overtime availability window. An overtime window that
  merely overlaps a regular shift (15:00–23:00 over a 07:00–19:00 shift) is
  premium only for the portion outside it — you pay extra only for capacity
  that exists *because* of overtime.
- **The objective charges the delta, not the gross.** Base production
  already charges rate × duration for every minute, so overtime adds
  rate × (multiplier − 1) per overlap minute. Overlap variables are only
  lower-bounded (`ov ≥ min(end, we) − max(start, ws)` under the assignment
  literal); the positive objective coefficient pins them exact under
  minimization. Chunked (R-C3) operations get one overlap var per chunk
  slot, gated by the slot's own `used` literal.
- **Multiplier ≤ 1 creates zero variables.** Datasets without overtime build
  byte-identical models — a hard requirement, since the
  defaults-reproduce-baseline gate compares schedule.csv byte-for-byte and
  CP-SAT is sensitive to variable creation order. Asserted directly
  (`test_multiplier_unset_creates_no_overtime_variables` checks the model
  proto) and indirectly (the gate still passes).
- **Extraction re-derives the split arithmetically** (chunk/run minute spans
  × premium windows), never by reading solver internals. Ledger decomposes
  twice: `production = production_regular + production_overtime`;
  `total = production + setup + tardiness`. The assignment's reconstructed
  Decision carries `overtime_minutes` / multiplier / cost and a
  testimony-renderable message ("Includes 600 min in an overtime calendar
  window (premium ×1.5: $300.00 above the regular rate)").

**The `overtime_required` scenario and what its counterfactual caught.**
Six 600-minute single-op orders due Saturday EOD share one resource; Mon–Fri
holds five (one per 720-min shift, never two); a Saturday overtime exception
supplies the sixth slot. Rates pinned to $1/min make the economics exact:
$300 premium vs ≈$1,025 tardiness — an optimal solver must buy exactly 600
overtime minutes and no more (two slack-rich control orders assert the "no
more"). The truth manifest's third claim — *removing the overtime windows
makes the same demands late* — *failed on first run* and caught a real
scenario bug: the generator's base CAL-STD is **six-day** (pattern rows 0–5),
so the "overtime" window duplicated regular Saturday capacity and stripping
it changed nothing. The with-overtime assertions had passed anyway, because
the premium-window subtraction removes availability windows that exactly
match overtime exception windows — the premium was billed against capacity
that was regular all along. The scenario now closes Saturday in its base
pattern. Lesson, same shape as the WO-2001 verdict: **a priced feature's
test must include the counterfactual that proves the price bought
something** — the positive assertions alone were green on a broken scenario.

Setup minutes in the scenario are 30 + 570 run (not 0 + 600) to sidestep the
documented 1-minute PT0S floor quirk (docs/05 §3 item 2).

**Files.** solver_builder.py (premium windows, `_overlap_var`,
`VariableMap.overtime_windows`, chunk slots carry `resource`), extractor.py
(regular/overtime split, Decision evidence, two new ledger keys),
`__main__.py`/scenario.py (plumbing + summary lines), ids_adapter.py
(effective-rate single source), adapter.py (CostRate fold),
generate_erp_dataset.py (`overtime_required`), test_declared_but_unread.py
(register: `costmodel.overtime_premium` removed — it has real consumers now;
`resource.cost_rate` justification rewritten), docs/01 §5.6/§6.8 rows,
docs/07 Phase 1. New tests: test_overtime_premium.py (7),
test_overtime_end_to_end.py (6), test_resource_rates.py (6).

## Amendment — 2026-07-12: Phase-1 exit audit — what the demo script found when run as written

The docs/07 Phase-1 exit demo was executed as an audit (two acts: a fresh
messy generated plant end-to-end, then the ticketing gauntlet with the
chunking counterfactual made live). The audit's rule was "no fixes unless a
clause fails"; seven clauses failed, each on the first honest attempt to run
something the docs already claimed. All seven are fixed, with the failures
recorded here because their *shape* matters: every one is a seam between two
components that had only ever been exercised from one side.

1. **The explainer only spoke sample_data's vocabulary.** The question
   router matched order refs with a hardcoded `WO-…` regex (and machines
   with `M-…`), and `_resolve_wo` tried only `("ERP", "work_order")` — so
   "why is ORD-000090 late" misrouted on every IDS submission and the
   gauntlet. Routing and resolution now match question tokens against the
   identity map (any registered order/machine ref type, any system) — the
   identity map IS the vocabulary bridge; assuming an id shape was always a
   violation of its purpose. Same fix in `ask.py`'s what-if parser and
   `scenario.py`'s SuppressMerge resolution.
2. **Pydantic serializes ≥365-day timedeltas with a years component**
   (`-P3Y34DT10H34M`, Y = exactly 365 days). Both hand-rolled ISO-duration
   parsers (explainer: silent 0.0; scenario differ: crash) choked on it —
   and the docs/06 Appendix-A `placeholder_dates` anomaly (due ~3y out)
   produces such lateness values routinely. Both parsers now handle Y.
3. **The what-if runner measured configuration drift, not the
   modification.** ScenarioRunner re-planned with a hardcoded
   `merge_by_family_v1`, never re-ran the validator (base exclusions lost —
   a stale-due demand the base excluded reappeared 575k minutes late in a
   scenario diff), never reproduced the horizon slice, never passed
   reference_date to the builder, and solved unpinned. It now recovers the
   base run's configuration from the run_context_open records
   (`derive_base_context`) and re-validates/re-plans/re-solves under it.
   `__main__` now records risk_margin and solver workers/seed in run
   configs so they are recoverable. The test_scenario base fixture was
   itself unfaithful (planned validator-excluded demands); fixed.
4. **Three horizon computations disagreed.** `__main__` and
   `SolverBuilder._compute_horizon` buffer max(due)+90d;
   `calendar_utils.compute_horizon` (the scenario path) buffered +14d.
   Calendars flattened shorter than the builder's internal horizon leave
   resumable operations with no windows to sum to their working duration —
   structurally INFEASIBLE, while the identical base solved fine. Unified
   at +90d.
5. **The R-C3 chunk encoding was structurally infeasible for any operation
   shorter than its min_chunk** (a 17-minute op with a workcenter-level
   30-minute floor: every used chunk must be ≥30 while chunks must sum to
   17). Never hit before because splittability had only ever been declared
   per-op on purpose-built long operations. The degenerate-split rule —
   working < 2 × min_chunk cannot split, so the op is effectively
   non-resumable — now lives in `calendar_utils.is_effectively_resumable`,
   shared by SolverBuilder and the Validator's class-aware window-fit (the
   two MUST agree or the validator admits work the solver cannot place).
6. **Two promised plant-config doorways did not exist.** The raw path's
   zero-rate warning said "edit plant_config to add rates" — nothing read
   rates from plant_config; and there was no way to declare splittability
   for raw data at all (the 116/173 rescue lived only in
   tools/gauntlet_rescue_report.py's snapshot-rewrite counterfactual).
   plant_config now supports `cost_model` (docs/06 §5.9 semantics:
   default_resource_rate_per_hour, setup_cost_per_setup,
   tardiness_cost_per_hour, overtime_premium_multiplier, resource_rates —
   hour-denominated, divided by 60 in the adapter like the IDS path, with
   the Resource.cost_rate single-source invariant) and per-workcenter
   `splittable` + `min_chunk_minutes`. Absent keys reproduce the old
   behavior byte-for-byte (defaults-reproduce-baseline verified). The
   pre-doorway provenance for splittable/min_chunk claimed *observed from
   RoutingLines* — a column that does not exist; now defaulted policy.
   (`OperationSpec.yield_factor` still carries the same false-observed
   pattern on the raw path — noted, not fixed here.)
7. **Windows consoles crash the ask REPL on '→'.** Renderers legitimately
   emit non-cp1252 characters (assignment Decision messages); cp1252
   stdout raised 'charmap' errors mid-session. `mre.ask`/`mre.whatif` now
   reconfigure stdio with errors="replace".

Also fixed on the way: the schedule viewer's lateness join assumed a dict
shape for `external_refs` that the contract never had (crashed on every
snapshot), and now recognizes IDS `order_id` refs.

**What the audit measured after the fixes** (details in the session report;
scratchpad artifacts, not repo fixtures): messy_realistic (unseen seed 23)
gates CONDITIONAL/C1 and solves clean; the pressured variant answers
why-late with the batch-coupling chain and prices the unbatch what-if
(+$13.4k — keep the batch). The gauntlet with splittability + costs
declared via plant config: 173 → 57 window-fit exclusions (116 rescued,
now through the shipping doorway, not a snapshot rewrite), 40 calibrated
outliers (was 578), 102 structural MISSING_REFERENCE unchanged, DENSITY_LIMIT
warned 58 times exactly as designed, sliced solve FEASIBLE with a fully
decomposed ledger, chunk rows pausing exactly at calendar closures. The
full 4,933-op solve with mass chunking could not find an incumbent in 600s
single-worker — Rep 2's scale-ladder warning realized at ~19% resumable
density; the sliced daily solve remains the blessed operational mode (the
docs/07 solver-gap workstream now has a second concrete input).

**685 tests green** (+5 audit-born: splittability doorway ×3, cost-model
doorway ×2).

## Amendment — 2026-07-13: Phase 2 session 2.1 — API layer, schedule JSON contract, run registry

**The schedule JSON contract is derived, never invented.** The document the API
serves (`src/mre/contracts/schedule_document.py`, `contract_version: "1.0"`,
versioned from day one — add, never repurpose) is a pure projection of what
already exists: canonical entities (Schedule, Assignment, ServiceOutcome,
Resource, Calendar, Demand-via-Fulfillment, Constraint), the identity map, and
evidence records. No field is computed fresh at serving time. Rules locked in
the contract:

- **External names appear ONLY in `*_name` / `work_order` fields**, with the
  canonical UUID refs kept alongside for machine navigation — both,
  deliberately. This is the identity-boundary lesson (2026-07-06) applied to
  the outbound surface: the cockpit speaks the customer's vocabulary, the
  machine-navigable spine stays canonical.
- **Timestamps are ISO 8601 UTC.**
- **`cost_summary` must decompose exactly** (total = production_regular +
  production_overtime + setup + tardiness) and dies at construction if it
  doesn't — validation-at-construction, same posture as the record contracts.
  `costmodel_version` rides along so every served cost is attributable.
- **Chunked (resumable) operations carry one chunk per run window; the pauses
  are the gaps between chunks** (docs/05 R-C3), `working_min` per chunk.
  Merged WPs list every constituent work order. Tardiness stays per Demand.
- **Phases are derived, with an honesty note:** the solver models an operation
  interval as setup + run contiguous from its start, so `phases.setup` is the
  first `setup_duration` minutes of the first chunk; `teardown` is always null
  because the current solver does not model it — the field exists for contract
  stability, not to pretend we have data we don't.
- `in_overtime_min` comes from the assignment Decision's `chosen` payload (the
  persisted Assignment entity never carried it) — evidence as the source of a
  document field, by design.

**The assembler is a pure function** (`modules/schedule_assembler.py`):
canonical snapshot + evidence records → document; no solver imports, no
writes, deterministic ordering. Round-trip rule tested end-to-end: the
document rebuilt from a persisted run equals the one built at extraction time.

**Evidence enrichment to make the derivation possible** (no vocabulary
changes — these are free-form Event/`config_snapshot` fields): M6 now emits a
`solve_complete` Event carrying status/objective/bound/gap/wall-time; M5's
RunContext config records the builder horizon (both pipeline and scenario
paths); the scenario runner's M6 config records the solver pinning it actually
inherits from the base run, so the document's `deterministic` flag is derived
truthfully everywhere.

**The API layer** (`src/mre/api/`, FastAPI + uvicorn added to dependencies) is
deliberately thin — it validates, mints run directories, invokes the EXISTING
pipeline (`mre.__main__.main`), ScenarioRunner, ConformanceGate, and Explainer,
and serves the contract. Every response is a versioned envelope
(`{"api_version": "1", data|error}`). Endpoints: POST /submissions (multipart
or dir path → gate → certificate; REJECTED returns the deficiency list and can
never be solved — 409), GET /submissions/{id}/certificate, POST
/submissions/{id}/solve (202 + run_id; background task; `deterministic: true`
pins `--solver-workers 1 --solver-seed 0`), GET /runs/{id}, GET /schedules,
GET /schedules/{id}, POST /schedules/{id}/ask (template renderer default; the
llm flag is honored server-side only if ANTHROPIC_API_KEY is present), POST
/schedules/{id}/whatif (202; diff bundle + the scenario's own document).

**Evidence isolation extends to the API:** what-if scenario schedules NEVER
appear in the default GET /schedules listing (opt-in query flag), scenario
documents carry `is_scenario` + `parent_schedule_id` lineage, and a what-if
cannot branch from a scenario schedule.

**Run-scoped outputs are now structural.** The registry
(`api/registry.py`, SQLite) mints `runs/<run_id>/` for every API-triggered
run — its own snapshot id (`snap-<run8>`), its own evidence directory, its own
document. What-if runs copy the base snapshot into their own run dir before
deriving, so scenario artifacts never touch the base run's directories. The
CLI routes through the same `prepare_out_dir` function (single owner of
stale-artifact clearing) — the shadowed-artifact incident class dies at the
structure, not at discipline. SQLite is the INDEX (submissions, certificates,
runs, schedules); the filesystem stores remain the artifact truth — no
evidence-store migration.

**Tests:** 50 new (28 contract-assembly from the contract rules: chunked op
with pauses, merged WP with two work orders, overtime-from-Decision,
decomposability dies at construction, determinism, scenario lineage; 22
endpoint tests over a generated clean_small: happy paths, REJECTED-never-
solves, scenario listing exclusion, deterministic plumb-through verified from
M6 RunContext evidence, round-trip rebuild equality, structural run-scoping).
**735 green** (685 carried + 50).

## Amendment — 2026-07-13: Overtime attribution ruling — the Assignment entity is the source of truth

Session 2.1 carried a qualification: the schedule document's
`in_overtime_min` was read from the assignment Decision's `chosen` payload
because the persisted Assignment entity never carried the fact. That left
two candidate sources that could drift. **Ruling: promote the fact to the
entity.** The amount of overtime an assignment consumes is a "what" —
canonical solve output — not a "why"; entities carry the whats, Decisions
carry the narrative. `Assignment.overtime_minutes` (docs/01 §6.9, added —
never repurposed) is persisted at extraction with a derived-provenance
sidecar (`M7.overtime_attribution`: overlap of the solved run windows with
the resource calendar's premium windows). The Decision's `chosen` payload
still repeats the number for testimony rendering, but it is now explicitly
narrative; the assembler prefers the entity and keeps the Decision read
only as a fallback for snapshots persisted before the attribute existed.
Tests: the `overtime_required` harness asserts the persisted entity value,
its provenance class/formula, and that the rebuilt schedule document
derives `in_overtime_min` from the entity (57 tests in the module, 2 new).

## Amendment — 2026-07-13: Warm-start scenario solves (docs/07 Phase 2) + a diff-comparison defect

**Warm-start.** ScenarioRunner now seeds every scenario solve with the base
schedule as a CP-SAT solution hint (`solver_builder.apply_solution_hints`,
shared with the solution-pool service). Correspondence needs no mapping
table: the Planner mints deterministic uuid5 ids (`op = uid("op", wp_id,
spec_id)`, `wp = uid("wp", *batch demand ids)`), so an operation whose
WorkPackage composition is unchanged has the same id in both snapshots and
hints directly, while a structurally modified portion (an unbatched merge)
finds no matching variable and is naturally unhinted. Deliberate
invalidation on top of that: operations on resources whose calendar a
modification touched are left unhinted (all resources sharing the touched
calendar, not just the named one) — a wrong hint is worse than none.
Chunked (R-C3) ops hint overall start/end and the resource literal only;
chunk-slot variables stay free. Hints are per (var, value), per the
2026-07-10 `add_hint` lesson. Telemetry: a `warm_start_hints` Event
(hinted / structure-changed / invalidated counts) and CP-SAT's own
`solution_info` now recorded on every `solve_complete` event payload —
hint acceptance is observable from evidence.

**The exit-audit noise case, re-measured** (messy_realistic seed 23, 310
operations, merge_by_family_v1, deterministic mode, 2-order unbatch
ORD-000043+ORD-000123): warm-started scenario = **0 untouched-operation
moves**; cold re-solve of the identical scenario = **51 moves at the
identical cost delta (+$309.24)** — pure tied-cost search noise, which is
what the warm start eliminates. The audit's historical "~307 moves" figure
was additionally inflated by a real differ defect found while testing this:
`_compute_schedule_diff` compared `run_start` as raw strings, but the
persisted base serializes UTC as `...Z` (pydantic) while the in-memory
scenario extract uses `+00:00` — so EVERY shared operation counted as
"moved" on format alone. Fixed (datetimes parsed before comparison); every
pre-fix move count in earlier reports should be read as ≈ total shared ops,
not as measured noise.

**Acceptance** (`tests/test_warm_start_noise.py`, slow): moves ≤ 10 warm
(measured 0), diff byte-stable across repeated deterministic runs, cold
counterfactual ≥ warm (2026-07-12 priced-feature rule: the price bought
the ceiling), telemetry present. Fast tests in `tests/test_scenario.py`:
hint-application unit tests (both assignment shapes, skip accounting,
proto-level hint values), warm-start event on the sample unbatch, moves ≤ 3
there (measured 0). `VariableMap.objective_terms` added (build-time capture
so pool tooling can bound the same objective expression — used next).

## Amendment — 2026-07-13: Solution-pool service (docs/07 Phase 2) — contract 1.1

**What ships.** `src/mre/modules/solution_pool.py`: for a solved run, K
(default 5) diverse near-optimal alternatives to the incumbent schedule —
the raw material for Tier-1 drag ghosts, pool-consensus testimony, and
ATP's fast re-solve. Mechanism (chosen and measured, per the session spec):
each member is a short re-solve of the EXACT base model — rebuilt from the
persisted snapshot with the run's own M5-recorded horizon and reference
date, so the incumbent's variables correspond — with three additions:
(1) warm-start hints from the incumbent (the warm-start mechanics, shared
code); (2) an in-model objective upper bound ≤ incumbent × (1 + X/100)
(X default 10) posted over the builder's own captured `objective_terms` —
near-optimality by construction, not post-hoc filtering; (3) diversity
pressure = a randomized search seed per member PLUS a no-good cut over a
random sample (10%, min 3) of the incumbent's start times — disjunctive
("at least one sampled op moves"), so a single tight operation cannot make
a member infeasible. Members that still come back infeasible are recorded
as rigidity findings, not errors. Measured diversity is reported: per-member
and mean assignment-Hamming distance from the incumbent (ops whose
(resource, start) differ — datetimes parsed, per the differ lesson), mean
pairwise, and `ops_with_alternative_positions` (the Tier-1 ghost
precondition, asserted ≥ 1 in the acceptance tests).

**Isolation, structural.** Pool members are contract documents in the run
dir's `pool/` subdirectory and rows in NEW registry tables
(`pools`/`pool_members`) — never rows in `schedules`, so no listing can
ever contain them (the scenario rule, made structural). Member extraction
runs with no snapshot writer and no reporter: the canonical snapshot is
byte-untouched (tested). Each member's own M5/M6 evidence sinks to
`pool/member_<n>_runs/` so its document's solver block is still derived
from real evidence, and the member document carries `annotations.pool`
(pool_id, base_schedule_id, member_index, objective + delta) —
**schedule-document contract 1.0 → 1.1**, additive, version history added
to the contract docstring.

**API.** POST `/schedules/{id}/pool` (202, warming; sync flag for tests),
GET `/schedules/{id}/pool` (summary: status, members, measured diversity,
mechanism string), GET `/schedules/{id}/pool/{n}` (member document),
409 for scenario schedules (pools belong to base schedules). Auto-warm:
`pool: true` on the solve request warms in the same background task
strictly after the schedule registers; it stays opt-in until the Phase-3
publish workflow exists, at which point warming-on-publish becomes the
default (the roadmap's "warmed async after publish"). Invalidation:
`Registry.mark_schedule_superseded` supersedes the schedule AND
invalidates its pools in one transaction — the supersede hook the publish
workflow will call.

**Acceptance measured** (clean_small and messy_realistic seed 23, both
deterministic base): pools populate ready within seconds (clean_small
~2s for K=5; messy plant within its generous bound), every member differs
from the incumbent (Hamming ≥ 1 guaranteed by the cut, measured higher),
every member document parses against the contract (cost decomposition
dies at construction), objective deltas ≤ 10%. Tests:
`tests/test_solution_pool.py` (helpers unit-tested at the ortools level,
integration, registry invalidation, slow messy acceptance) and
`tests/test_api_endpoints.py::TestSolutionPool` (endpoints, structural
listing isolation, auto-warm).

## Amendment — 2026-07-13: Solver-gap probe #1 — facility decomposition on the gauntlet full solve: RED

The dossier's first real experiment (`tools/solver_gap_probe.py`, report in
`tools/solver_gap_probe_report.md`). Question: does per-facility /
per-resource decomposition make the mass-splittability full solve viable,
and does it change the 87%-gap story? **Verdict RED** — it does not; the
sliced daily solve remains the blessed operational mode, and the research
stays parked per docs/07 §2, now with a sharper measured explanation.

Headline measurements (single-worker seed 0; config recreated and stated —
the audit's mass-chunking plant config was a scratch artifact): the full
backlog builds 14,042 ops / 2,980 WPs / 93 resources across 10 facilities
that are PERFECTLY decomposable (0 cross-facility WorkPackages, explicit
single-resource eligibility — sum of facility objectives would be exact).
Monolith: UNKNOWN, and **model build alone took 289s**. Decomposed: 8 of 10
facilities still UNKNOWN at 180s; only trivial F002 (3 ops, OPTIMAL) and
F004 (1,040 ops, ~9 resumable/resource → FEASIBLE, gap 43.6% vs the 87%
REP-1 monolith figure) produced solutions. Sharpest finding: single-resource
shards of F001 (~170–190 ops, ~65 resumable ops/resource) fail at 30s —
spike 2's "per-resource decomposition works" was measured at ~4–4.5
resumable ops/resource and does NOT extend to mass-splittability density.
The difficulty has moved inside the resource.

Two independent killers, either sufficient: (a) chunk-slot volume — on the
full-backlog horizon the suffix-capacity tail pruning leaves candidate
window ranges spanning most of the horizon, so one machine's no-overlap
group holds tens of thousands of optional intervals (build time is the
visible symptom); (b) raw per-machine op count — F006 with only 12
resumable ops still fails at ~850 ops/machine, while F004 solves at ~260.
The sliced daily solve caps the horizon and therefore caps BOTH at once —
it is the correct structural counter, not just "less work". Named parked
directions (not built): horizon-capped chunk slots (due-date-relative
candidate window policy), hierarchical slice-within-facility with LNS
repair from the sliced incumbent (the warm-start/pool machinery is the
natural repair loop), and facility decomposition productionized as a
speedup for the SLICED mode. Scope note recorded: the audit's "4,933-op
full solve" figure described a differently-scoped run; this probe's
partition table sums self-consistently to 14,042.

## Amendment — 2026-07-14: Session 2.3 carry-ins from the 2.2 review (corrections + pool threshold)

**Correction — the invalidated historical move counts, named.** The differ
string-format defect fixed 2026-07-13 (`_compute_schedule_diff` compared
`run_start` as raw strings; `...Z` vs `+00:00` made every shared operation
count as "moved") invalidates two specific published figures: the Phase-1
exit audit's **"~307 moves"** for the messy-plant unbatch noise case, and
the **"88 assignment moves"** in the 2026-07-06 unbatch amendment above.
Both should be read as ≈ the count of shared operations, not as measured
movement. **Cost figures are unaffected**: every cost delta (including the
$260 unbatch verdict) was computed from the cost ledgers, which never
touched the string comparison. The lateness deltas are likewise unaffected
(computed from ServiceOutcomes). Only the move COUNTS were inflated.

**Warm-start counterfactual test.** The 2.2 warm-start acceptance proved
the hint eliminates noise (0 moves warm vs 51 cold); it did not prove the
hint permits improvement. Added
`tests/test_scenario.py::test_warm_start_still_departs_hint_for_lower_cost`:
the WO-2001/WO-2002 unbatch, run warm-started, must still find the known
lower-cost outcome (tardiness_delta < 0 and total_delta < 0 per the
2026-07-06 verdict). A hint that traps the solver at the incumbent's cost
structure is a defect; this test is the standing proof it doesn't.

**The no-good cut's difference threshold.** As shipped, the pool's
diversity cut was satisfiable by sliding one sampled op a single minute —
technically "different", semantically the same schedule.
`add_start_diversity_cut` now takes `tolerance_minutes` (default
`DIVERSITY_TOLERANCE_MINUTES = 15`): at least one sampled op must start
≥ 15 minutes from its incumbent start (|start − incumbent| via
`add_abs_equality`; floor of 1 since a 0 tolerance would make the cut
vacuous). The pool's Hamming metric is aligned to the SAME threshold
(`solution_pool._differs`: resource changed OR start moved ≥ tolerance),
so the constraint and the metric agree on what "different placement"
means — a member can never satisfy the cut while measuring Hamming 0.
`ops_with_alternative_positions` uses the same rule. The threshold is
recorded in pool params (`diversity_tolerance_minutes`). Unit tests: the
cut INFEASIBLE when every sampled op is pinned within ±1 minute; the
forced move measures ≥ 15.

**4,933 vs 14,042, resolved by measurement.** Operation-instance count is
a planner-policy artifact: on the same gauntlet backlog (repo
plant_config, same M1(raw)→M3 exclusions), identity_v1 plans 2,864 WPs /
13,315 ops while merge_by_family_v1 plans 668 WPs / 4,088 ops (3.3×
collapse — one Operation per spec per WorkPackage). The audit's "4,933-op
full solve" is a merge-policy op count under its scratch config (whose
splittability rescues admitted more demands); the probe pinned identity_v1
and built 14,042. Both self-consistent; verdict untouched (the killers are
per-machine densities, measured directly). Paragraph added to
`tools/solver_gap_probe_report.md`.

**Pool slice-awareness qualification.** Pool members rebuild the base
model from the run's own M5-recorded horizon — correct for monolithic
solves, but a sliced run's per-slice demand selection is not reproduced.
"Pool must become slice-aware for sliced-mode schedules" added to the
probe report's parked directions and to docs/07's pool item as a carried
qualification.

## Amendment — 2026-07-14: WIP doorway, gate coherence checks (session 2.3 unit 1)

`wip_status.csv` (docs/06 §5.13, IDS v0.3) now enters through the gate.
Tier 1c: `manifest.semantics.wip_progress_basis` is required iff the file
is present (we do not divine which progress column is authoritative) —
MALFORMED_FIELD blocker, REJECTED, matching the other required
declarations. Tier 2 WIP coherence: five checks, all findings, never
crashes, each bumping CONDITIONAL.

**Finding-code review (add-never-repurpose):** every check maps to an
existing code with its established meaning; no vocabulary additions were
needed —
- unknown order/sequence/resource refs → `ORPHAN_ENTITY` (excluded);
- in_progress rows missing observed start, observed resource, or the
  declared-basis progress value → `MALFORMED_FIELD` (defaulted: the
  adapter will treat such rows as not_started — an in-flight claim
  without its observed state cannot be honored as a fixed interval);
- sequence-order violations (op in_progress/complete while a predecessor
  is not_started, explicitly or by absence — absence = not_started per
  §5.13) → `LOW_CONFIDENCE_INPUT` (proceeded_flagged; a shop-floor
  reporting-quality signal, not an exclusion). IDS routing has no
  overlap-permitting edge source (min_lag ≥ 0, max-lag doorway deferred
  §8), so no edge can excuse the overlap at the gate;
- completed op still carrying remaining work (completion wins) and
  observed start after THIS submission's reference_date →
  `VALUE_OUT_OF_RANGE` (proceeded_flagged).

**Recurring-submission rule (recorded as a test, not just a note):** an
observed start after a PREVIOUS run's reference but before this
manifest's reference_date is normal drift between extracts — deliberately
NOT a finding (`test_pre_reference_observed_start_is_normal_not_a_finding`).
Pilots' second extracts will always contain these; drift belongs on the
certificate trend line, not in the gate.

Certificate counts gain `wip_status`. Tests:
`tests/test_conformance.py::TestWipDoorway` (7 checks incl. the
clean-file ACCEPTED case).

## Amendment — 2026-07-14: WIP canonical landing — adapter + Demand/Operation/WorkPackage (session 2.3 unit 2)

Observed shop-floor state now lands in the canonical model (docs/06 §5.13,
docs/01 §5.1/§5.2/§5.4).

**Contracts.** New `WipStatus` enum (`not_started`/`in_progress`/`complete`)
— distinct from `WorkPackageState`: that is the planning seam
(planned/frozen come from us), this is shop-floor fact (comes from the
plant). New struct `WipOperationObservation` carried on `Demand.wip_operations`
(the immutable order-level observation, canonical ids only, cites its
wip_status.csv `source_rows`). New optional `Operation` fields
`wip_status` / `observed_start` / `observed_resource_ref` /
`remaining_duration`. docs/01 §5.1/§5.2/§5.4 updated in the same commit
(add-never-repurpose).

**IDS adapter.** `_build_wip_observations` translates wip_status.csv into
`Demand.wip_operations`, normalizing progress to the manifest-declared
`wip_progress_basis` (exactly one of remaining_minutes/quantity_complete
survives). It follows the gate's dispositions rather than crashing:
unknown sequence → ORPHAN_ENTITY (excluded); in_progress missing observed
start/resource/progress → MALFORMED_FIELD, downgraded to not_started (an
in-flight claim without its observed state cannot be honored as a fixed
interval). First row wins per sequence. Provenance on
`Demand.wip_operations` is observed, citing the actual source rows. The
sample and raw adapters (no WIP doorway) write a truthful `defaulted`
`no_wip_source_blank_slate` — never a false observed sidecar.

**Planner projection.** For each Operation it instantiates, the Planner
projects the owning Demand's observation:
- complete → observed actuals; `remaining_duration = 0` (DERIVED from
  status, not observed — there is no observed "remaining" column for it);
- in_progress → observed start + resource; `remaining_duration` is
  **observed** when the plant reported `remaining_minutes` directly, or
  **derived** when computed as `(quantity − quantity_complete) × run_rate`
  (the remainder arithmetic). This observed-vs-derived split is the
  truthful-provenance guard: the yield_factor false-observed defect
  (2026-07-12) wrote a constant under an observed sidecar; a computed
  remainder here is never labeled observed.
- not_started / no observation → fields None, defaulted.

WorkPackage.state is a rollup of the constituent operations' observed
statuses (all complete → complete; any underway or partial → in_progress),
with **observed provenance citing the wip_status.csv source rows** — the
seam docs/06 §5.13 names. WIP is projected only for 1:1 (identity_v1)
WorkPackages: a merged operation corresponds to no single order's in-flight
op, so its actuals would be ambiguous (the observation still lives on each
constituent Demand). The WIP doorway runs identity_v1, so this restricts
nothing in the supported flow.

**Not yet consumed by the solver** — CU3 makes the Solver Builder treat
complete ops as satisfied (no variables, capacity freed) and in_progress
ops as fixed intervals for `remaining_duration` on `observed_resource_ref`,
with the amended pre-reference invariant. Tests: `tests/test_wip_landing.py`
(7: observation landing + provenance class per basis, WP-state rollup,
blank-slate defaulted). Fixture provenance-attr lists updated for the new
`Demand.wip_operations` field (test_planner / test_snapshot_store /
test_validator).

## Amendment — 2026-07-14: WIP solver semantics + the amended invariant (session 2.3 unit 3)

The Solver Builder now honors observed execution state (docs/06 §5.13).

**Complete operations** are satisfied and OFF the model: no start/end/assign
variables, not added to any resource's no-overlap group, not billed in the
objective. Their capacity is freed (the work already happened, in the past).
A complete predecessor imposes no precedence constraint — its successor
chains from reference_date.

**In-progress operations** become a FIXED interval `[0, remaining]` on the
observed resource (the remaining working time from reference_date), added to
that resource's no-overlap group so no future op can double-book the machine.
No free start or resource choice — it is where it is. A successor chains from
the fixed end (a constant), by walking the PrecedenceEdge — the same edge the
builder reads for ordinary precedence. WorkPackage end takes the fixed end as
a constant term; a fully-complete WP contributes no end (it is done).

**The amended invariant, at both clamp sites.** The old blanket rule ("no op
starts before reference_date") is now: no NEWLY scheduled op starts before
reference_date (the horizon floor, minute 0, applies to new ops via their
start-var lower bound); an observed in-flight op is EXEMPT — its remaining
work is pinned at minute 0 and its observed pre-reference start is history,
not a scheduled start. Clamp site 1 (horizon derivation) already floors new
ops at reference_date and never reads op-level observed starts, so in-flight
history can't drag the horizon back. Clamp site 2 (calendar flattening /
blocking): an in-flight op's `[0, remaining]` busy span is carved OUT of the
resource's blocking intervals (`_blocking_intervals(busy_spans=...)`), because
committed in-flight work continues across shift boundaries — without the
carve-out, a midnight reference_date with a 07:00 shift would make the fixed
interval overlap the pre-shift closure and go infeasible.

**Ghost-job non-regression** (docs/07 standing risk). The Validator's
TEMPORAL_IMPOSSIBILITY check now exempts a past-due demand that carries an
in_progress/complete observation — live in-flight work is not a ghost.
A past-due demand with NO WIP is still excluded (the original fix, intact).
`test_wip_solver.py::test_temporal_impossibility_still_fires_while_in_flight_honored`
proves both in one run.

Objective note: committed/sunk production of complete and in-flight ops is
not in the objective (no assign literals) — it cannot be optimized away and
the re-solve prices only the future movable work. Extractor cost accounting
for completed ops is revisited with the mid_replan ledger (unit 4).
Tests: `tests/test_wip_solver.py` (6). defaults-reproduce-baseline stays
green (WIP-less data builds byte-identical models — WIP branches are guarded
on wip_status, absent on every existing path).

## Amendment — 2026-07-14: mid_replan scenario — the WIP capability, end to end (session 2.3 unit 4)

The generator's `mid_replan` scenario (W1) exercises reschedule-from-a-point
with a truth manifest and a counterfactual. Deterministic, seed-independent
layout (reference_date = Monday, CAL-STD 07:00–19:00): R0 carries a COMPLETE
order (its window freed) and a not_started RESCUE order due Monday; R1 carries
an IN_PROGRESS order (600 min remaining, fixed) and a not_started FUTURE order.
Emits `wip_status.csv` + `wip_progress_basis`; gates ACCEPTED with zero WIP
findings (the observed pre-reference actual_start is history, not flagged).

Proven end to end (`tests/test_mid_replan.py`, deterministic
`--solver-workers 1 --solver-seed 0`):
- **Completed op frees capacity** — the price-bought-something rule on
  capacity. The counterfactual strips `wip_status.csv` (every order
  not_started, the "prior" blank-slate plan) and the SAME plant carries
  strictly more tardiness; the rescue order is on time WITH the WIP and late
  WITHOUT it, purely because the completed op vacated R0's window.
- **Only the future moves / fixed ops stay put** — the completed op produces
  no assignment (history, not scheduled); the in-flight op holds R1's early
  block so the future op starts at/after the in-flight remaining (600 min).
- **Warm-start never hints the fixed/in-flight ops** — a re-solve hinted from
  the prior (no-WIP) schedule finds the completed and in-flight ops have NO
  variables in the WIP model, so they are unhintable by construction (not
  luck); only future movable ops are hinted.

Generator plumbing: `wip_status` table on the Dataset, `wip_status.csv`
columns + optional-doorway omit-when-empty, `_apply_mid_replan`. The scenario
joins the auto-parametrized IDS harness (`test_ids_end_to_end.py`), which
gates it and runs the full pipeline.

## Amendment — 2026-07-14: Session 2.4 CU0 — carry-ins from the 2.3 review

Five review carry-ins resolved before the cloud-deploy work; two are code
fixes with counterfactual tests, three are written rulings.

**CU0.1 — WIP finding-code review (add-never-repurpose audit).** The five
Tier-2 WIP coherence checks and the exact existing code each reused, with a
semantic-stretch verdict per check:

| Check | Code | Disposition | Verdict |
|---|---|---|---|
| `wip_unknown_refs` (order/seq/resource ref not in the submission) | `ORPHAN_ENTITY` | excluded | clean fit (a reference to a non-existent entity is the canonical orphan) |
| `wip_in_progress_incomplete` (in_progress row missing observed start / resource / declared-basis progress) | `MALFORMED_FIELD` | defaulted → not_started | clean fit (a required field of the record is absent/unusable) |
| `wip_sequence_order_violation` (op in_progress/complete while a route predecessor is not_started) | `LOW_CONFIDENCE_INPUT` | proceeded_flagged | **closest to a stretch — held**; see below |
| `wip_complete_with_remaining` (completed row still carries remaining work) | `VALUE_OUT_OF_RANGE` | proceeded_flagged | fit (remaining > 0 is out of the range implied by status=complete) |
| `wip_observed_start_after_reference` (actual_start after THIS submission's reference_date) | `VALUE_OUT_OF_RANGE` | proceeded_flagged | fit (a timestamp past the declared clock is out of range) |

The one worth naming: `wip_sequence_order_violation → LOW_CONFIDENCE_INPUT`.
The established meaning of that code (its other use: orders routed through
inactive/unapproved routes) is "input we proceed with but flag as lower
confidence, a shop-floor data-quality signal" — and a WIP report that says
an operation is underway while its predecessor is not_started is exactly a
self-inconsistent shop-floor report we choose to proceed on (proceeded_flagged,
CONDITIONAL), not a hard structural error (IDS routing has no overlap-permitting
edge, so no edge *excuses* it, but the report may simply be mis-keyed). No
existing code is a precedence-consistency code, and inventing one for a
proceed-and-flag signal would over-specify the vocabulary. **Ruling: all five
reuse existing codes within their established meanings; no new finding code is
warranted.** (Recorded per the add-never-repurpose review discipline.)

**CU0.2 — resumable in-flight remainder respects calendars (code fix).** The
2.3 solver modelled EVERY in-flight op as a single fixed `[0, remaining]`
interval with its busy span carved out of calendar blocking — so a *resumable*
in-flight op's remaining work crossed shift closures without permission. Fixed
in `solver_builder`: an in-flight op that `is_effectively_resumable` now has its
remaining working minutes placed greedily into the observed resource's working
windows from reference_date (`_place_inflight_remaining`), pausing at closures —
fixed intervals, each already inside a window, so no carve-out. A *non-resumable*
in-flight op keeps the contiguous carve-out (it physically cannot pause, so it
does cross the boundary). Only the observed ELAPSED span (history, never
modelled) ever crossed a closure. The rule stated: **the future must respect
calendars even when the past didn't need permission.** Tests
(`test_wip_solver.py`): a helper unit test (900 min on 07:00-19:00 lands
720+180, never in the [0,420] closure) and a solver test (a successor chains
after the calendar-respecting fixed end, minute ≥ 2040, not the old contiguous
900). mid_replan is unaffected (its in-flight op is `splittable=false` → the
carve-out path); `test_in_flight_interval_exempt_from_calendar_closure` (also
non-resumable) still green; defaults-reproduce-baseline unmoved (the branch is
guarded on effective resumability, absent on WIP-less paths).

**CU0.3 — op-count reconciliation.** The four figures (13,315 / 14,042 /
4,088 / 4,933) reconciled in one table in `tools/solver_gap_probe_report.md`:
13,315→14,042 and 4,088→4,933 are the SAME effect (a splittability config
rescues window-fit-excluded demands into the backlog) measured under
identity_v1 and merge_by_family_v1 respectively; the cross-policy ~3.3× gap is
the merge collapse. Verdict untouched.

**CU0.4 — solver-gap dossier entry #2: merge policy as a ~3.3× tractability
lever, and its cost.** Added to the probe report. merge_by_family_v1 shrinks
the model 3.3× (668 vs 2,864 WPs; 4,088 vs 13,315 ops) — a larger, denser-
attacking decomposition lever than facility decomposition — BUT the WO-2001/
WO-2002 unbatch verdict (2026-07-06) already priced merge as a **+$260 cost
loss**. The tension is the point: the same knob that buys tractability spends
optimality. The sliced daily solve stays primary (caps chunk-slot volume with
no merge penalty); merge is a deliberate secondary lever. **Pilot entry
conditions must declare which planner policy their tractability/cost figures
are measured under** — added to the Phase-4 entry-condition discipline (op
count, and therefore both speed and the cost baseline, move 3.3× between
policies).

**CU0.5 — sunk-setup ledger ruling (code fix).** A completed or in-flight op's
setup already happened before reference_date; it is SUNK and must not be
re-charged in the movable objective. The Solver Builder already excluded both
from the objective's setup term (no assign literals); the extractor ledger
still billed `len(operations) × fixed_per_setup`, over-counting them. Fixed:
`setup_cost` now counts only ops whose `wip_status` is neither complete nor
in_progress, so `total = production + setup + tardiness` verifies exactly and
matches the objective. The sunk portion is reported on a separate, additive,
**non-decomposing** `sunk_setup_cost` ledger/summary line — present only when
WIP is observed, so WIP-less runs keep a byte-identical ledger (a future WIP
cost report can consume it). Counterfactual test
(`test_mid_replan.py::test_mid_replan_ledger_does_not_recharge_sunk_setups`):
the WIP run's `setup_cost` is strictly below the WIP-stripped run's (which
re-charges all four ops), a positive `sunk_setup_cost` line is present WITH
the WIP and absent WITHOUT, and the WIP run's decomposition still closes to
`total_cost`.

## Amendment — 2026-07-14: Session 2.4 CU1 — containerization (docs/07 Phase 2, W4)

The API service is now containerized, provider-agnostic by construction (no
cloud SDKs, no provider env-var names; the app reads only `MRE_*` config).

**Healthcheck endpoint.** `GET /health` (app.py) — a cheap liveness/readiness
probe for the container `HEALTHCHECK` and any reverse-proxy/platform check.
It confirms the process is up and `MRE_DATA_ROOT` is present and writable (the
run registry, snapshots and evidence all live under it) via a write-probe, and
returns 503 if not — without touching the solver. Tests
(`test_api_endpoints.py::TestHealth`): 200 with `data_root_writable` when
writable, 503 envelope when the probe write fails.

**Dockerfile — multi-stage.** `builder` resolves the pinned lockfile into a
`/opt/venv` and installs the app wheel (`pip install --no-deps .`), so
compilers and pip caches never reach the shipped image. `runtime` (the shipped
target) copies only the venv, adds `curl` for the healthcheck, creates a
non-root `mre` user owning `/data`, `EXPOSE`s 8000, declares the `HEALTHCHECK`,
and runs uvicorn via the app factory. `test` is `FROM runtime` + pinned dev
deps + `tests/`+`tools/`+committed data, run from an `/app` rootdir where
pytest prepends the suites to `sys.path` while `import mre` still resolves to
the SHIPPED venv package — so CI exercises the image as shipped, not the
checkout (the stale-install false-green lesson applied to images).

**Pinned lockfiles.** `requirements.lock` (runtime: FastAPI/Starlette/uvicorn,
Pydantic, OR-Tools + numpy/protobuf/absl/immutabledict) and
`requirements-dev.lock` (`-r` the runtime lock + pytest + httpx). Exact
versions, grouped by the direct dep that pulls each transitive; regenerated
deliberately, never floated. `.dockerignore` keeps runtime artifacts, caches,
and the gitignored `raw_data/` out of the build context.

**Compose (local parity).** `docker-compose.yml`: the `api` service (runtime
target) + a persistent named volume `mre-data:/data` holding registry +
snapshots + evidence, `PYTHONHASHSEED=0` set to support the deterministic-mode
guarantee, compose-level healthcheck. The TLS reverse proxy is a CU2 overlay
(the API never speaks TLS itself).

**CI (`.github/workflows/ci.yml`).** Builds the `runtime` image (must build on
its own), builds the `test` image, runs `pytest -q -m "not slow"` INSIDE it,
then boots the runtime image and polls `/health` to prove it serves.

**Fresh-checkout / container robustness.** `TestGauntletReproducesBaseline`
hard-depended on the gitignored `raw_data/` extract and would error anywhere
that extract is absent (fresh checkout, CI, container). Guarded with
`skipif(not (REPO/"raw_data").exists())` — it skips gracefully off the
developer machine (the merge_v2 gauntlet test was already `@pytest.mark.slow`,
so excluded from the fast suite already).

**Verification gap named.** Docker is not available in this session's
environment, so the image was NOT built here. Everything buildable-independent
was verified: the compose and CI YAML parse, the Dockerfile stage graph is
well-formed, the runtime CMD itself was smoke-tested on the host (uvicorn
`--factory` boots and `/health` returns 200 with the exact command the
container runs), and the fast suite is green on the host (793 passed). The
in-container run is exercised by CI on first push; **image-built-and-tested-in-
CI is the outstanding confirmation, not done locally this session.**

## Amendment — 2026-07-14: Session 2.4 CU2 — encryption + secrets (W4 baseline)

The W4 encryption/secrets posture ships with the deploy work; the durable
record is the new **docs/08-security-posture.md** (what's encrypted and where,
where keys live, secrets rule, single-tenant-by-construction with the tenant-#2
trigger). Highlights:

**TLS in transit.** The API never terminates TLS — a reverse proxy fronts it
and speaks plaintext to `:8000` on a private network. Local parity:
`docker-compose.tls.yml` overlay adds a Caddy service
(`deploy/local-tls/Caddyfile`, `tls internal` = offline self-signed local CA),
publishes 443, and `!reset`s the base file's public api port so the proxy is
the only entrypoint. Cloud: the platform's managed TLS front end (CU3/deploy/
azure) — same app image, different terminator. HSTS set at the terminator in
both.

**Encryption at rest.** All durable state is under one mount
(`MRE_DATA_ROOT=/data`: registry, submissions, snapshots, evidence). Encryption
is a property of the volume's backing store, application-agnostic: a
host-encrypted disk locally, an encrypted managed disk in cloud; keys live with
the host/platform, never in the repo or image. No application-level field
encryption in the baseline (threat model = disk/host/backup compromise,
answered at the storage layer).

**Secrets — environment injection only.** No credentials in the image
(multi-stage build copies only a venv + app) or the repo. Runtime secrets
(today just the optional `ANTHROPIC_API_KEY` for the explainer LLM) are injected
by the platform secret store in cloud / a git-ignored `.env` locally.
Provider-neutral `MRE_*` config only. **CI `secret-scan` job** (gitleaks,
`.gitleaks.toml` extending the default ruleset, synthetic-data dirs allowlisted)
fails the build on any committed credential across full history.

**Single tenant by construction.** One data root = one customer; no tenant key
on any entity/evidence record, no tenant-selecting code path — isolation is the
process/volume boundary. Tenant #2 = a second isolated deployment, not a shared
store. The **tenant-#2 isolation trigger** (first time two tenants must share
infrastructure → tenant id on snapshot + every evidence record, tenant-scoped
registry, per-tenant keys) is named in docs/08 §4 so multi-tenancy is a
deliberate design item, never discovered by accident. Certification stays
post-window and trigger-gated (docs/07 §4.3).

**Verification.** Compose (base + TLS overlay, the `!reset` tag) and CI YAML
parse; the gitleaks step and Caddy proxy are not run here (no Docker) — they
execute in CI / when the TLS stack is brought up. Named as the outstanding
confirmation alongside CU1's.

## Amendment — 2026-07-14: Session 2.4 CU3 — deploy artifacts + smoke (Azure-first, swappable)

**Azure deploy artifacts (`deploy/azure/`, isolated).** `main.bicep` provisions
a Container Apps deployment mirroring the compose stack: an **encrypted**
Storage account + file share backing the single `/data` volume (registry /
snapshots / evidence), a managed environment with that share linked, and the
API container app with **managed-TLS external ingress** to plaintext `:8000`,
ACR-pull creds and the optional `ANTHROPIC_API_KEY` as **secrets** (never in the
image), `/health` liveness+readiness probes, `MRE_DATA_ROOT=/data`,
`PYTHONHASHSEED=0`, and **one replica** (single tenant by construction — one
writer for the SQLite registry and the volume). `deploy.sh` runs `az acr build
--target runtime` (the shipped stage) then `az deployment group create`;
`.env.example` documents the parameters (secrets injected, never committed).
`README.md` states the **provider-swap boundary** explicitly: app code, image,
and local stack are provider-agnostic; a new provider is a sibling
`deploy/<provider>/` supplying four things (managed TLS → `:8000`, an encrypted
`/data` volume, secret injection, one replica) and touching nothing else.

**Smoke script (`deploy/smoke.py`), the docs/07 Phase 2 exit demo over the
API.** Provider-agnostic — speaks only the HTTP contract, so the SAME script
validates local compose and a cloud instance by `--base-url`. It generates a
submission client-side, then `/health` → multipart submit+gate → solve (async,
polled to done) → retrieve schedule → one always-valid what-if
(`set_cost_weight` on the tardiness base weight — dataset-independent), timing
each phase and writing a scale-ladder baseline JSON. Deterministic solve by
default (`--insecure` skips TLS verify for the local self-signed CA). ASCII-only
output (the cp1252-console lesson: an em-dash/arrow in a print crashed the first
run; fixed).

**Measured (local, deterministic; the exit-demo proof).** Against a local
uvicorn instance (Docker unavailable this session, so NOT the container — named
gap): **clean_large (~3,000 orders) gated ACCEPTED/C1 and produced a 7,460-
assignment schedule via the API in ~165s total** (generate 0.03s, submit+gate
0.4s, solve 81.6s at a 45s solver limit + build/extract, retrieve 0.24s, what-if
83s) — "schedule via API in minutes, repeatably." clean_small runs the full
path in 3.3s. Baselines in `deploy/scale_ladder.json` (environment-stamped as
a reference point, not a hard CI gate — wall-clock is host-specific).

**Honest gap (deploy-verified-locally ≠ deploy-verified-in-cloud).** No live
Azure subscription this session: the Bicep is unvalidated against ARM, the image
was not built (no Docker), and the smoke ran against a local server, not the
containerized/cloud stack. The artifacts ship; the first live `az deployment
group create` + cloud smoke run + the in-container CI run (CU1) are the
outstanding confirmations, carried forward.

### 2026-07-10 — Conversational Certificate groundwork: Rule Registry, gate completion, evidence-shape

Certificate session 1 (design) + a verification audit produced four rulings and
an eight-finding audit, all implemented this session (IMPLEMENT mode). The gate
had been a prose tier list emitting anonymous checks; it is now a **registry of
32 named rules** (`src/mre/contracts/ids_rules.py`, the single source that also
renders docs/06 §4), each carrying a stable rule_id, finding code, category, and
status. No new finding codes (all 32 rules map onto the existing 18-code
vocabulary, verified).

**R-CC1 (catalog unit = gate rule).** The remediation catalog's unit is the
gate *rule*, not the finding code — a two-level catalog (per-rule note; finding-
code fallback for rule-less findings). docs/07 wording refined and bumped v1.5.

**R-CC2 (rule identity survives reimplementation).** Rule ids are stable
identifiers with governance: never renamed for style, retired-never-reused,
`superseded_by` keeps a superseded rule resolvable; thresholds (Appendix A) are
versioned rule *parameters* — a change of meaning is a new rule_id, never a
repurpose. Naming convention is lint-bound (present-tense IDS-vocabulary
conditions; no digits/threshold/severity/implementation words). Registry lives
in docs/06 §4.

**R-CC3 (four-outcome vocabulary; grade as pure function).** Closed outcome enum
`satisfied / flagged / degraded / violated`. Grade is a pure function of
outcomes (any violated → REJECTED; else any degraded → CONDITIONAL; else
ACCEPTED). Banded rules take the measured outcome; structural rules resolve
satisfied/violated only; quality rules satisfied/flagged only and structurally
cannot degrade a grade. Verified equivalent to the old ad-hoc grading on every
existing scenario (grades unchanged).

**R-CC4 (typed gate evidence payload).** `GateFindingEvidence` (contracts)
carries rule_id + outcome + optional measured{name,value,unit} + thresholds_ref
+ a detail dict, validation-at-construction (outcome must be one the rule's
category permits). The legacy `check=` string is kept for one transition (some
tests still grep it).

**Evidence-shape refactor (the audit's structural findings).**
- *subjects=[] envelope violation → submission-space refs.* Gate findings now
  name typed subjects. `EntityRef` gained an additive `system` field (default
  `"canonical"`; M0 sets `"IDS"`) — the honest way to say "this id is a
  submission-space id, not a canonical one." M1 already registered these refs
  in the identity map; a new test proves a gate finding on an order is reachable
  by canonical key after a full run, and that the IDS ref is the permanent
  identity for a REJECTED submission (docs/02 boundary rule 1 amended).
- *satisfied-findings-as-WARNING / metrics-vs-findings.* Banded rules always
  record a **Metric**; a **Finding** is emitted only on a non-satisfied outcome
  — the two spurious "100% resolved" WARNINGs are gone. Severity now derives
  from outcome (flagged→WARNING, degraded→ERROR, violated→BLOCKER).
- *the one registry-stands ruling (B4).* `manifest_semantics_declared` recoded
  MALFORMED_FIELD → **AMBIGUOUS_SOURCE**: an absent declaration malforms
  nothing — the source cannot be interpreted, which is the code's literal
  meaning and §3's stated purpose. Pinned test updated.
- *manifest_schema_valid made true to its name (B5).* Extended from
  JSON-parseability to schema validation (required fields present + typed) via
  an `IDSManifest` model; semantics-field presence stays a separate rule.

**Seven checks made real + one unfold + two identity splits.**
required_columns_parse, key_fields_populated (un-subsumed from the valid-orders
aggregate), routes_resolve_to_lines (unfolded from orders_resolve_to_routes,
which is now pure order→route-header resolution — the affected anomaly manifests
were re-derived from the new definitions, not hand-tuned),
order_dates_internally_consistent, facility_references_consistent,
decision_relevant_attributes_populated, optional_columns_are_not_sparse. The
transition-matrix emit sites split into
setup_families_have_transition_matrix + transition_matrix_references_declared_families
(one condition per rule); the orphaned wip complete-with-remaining check gained
rule_id wip_completion_is_internally_consistent. Each new check landed with a
generator anomaly (the executable twin) and a coverage-matrix entry.

**Registry additions vs. the handoff's 32.** The handoff listed 32; both were
present and correct (wip_completion_is_internally_consistent; the
transition-matrix converse split).

**Regression: coverage by construction.** `RULE_TO_ANOMALY` (in the generator)
must name a trigger for every implemented rule; a completeness test asserts set
equality against RULE_REGISTRY, and a parametrized coverage matrix generates
each anomaly and asserts the precise rule's finding appears with a permitted
outcome — so a future rule added without an anomaly fails CI by construction.
A reverse guard asserts every M0 finding carries a registry rule_id (no orphan
checks). 840 tests green (+45).

**One under-specification, reconciled and recorded.** Handoff §B3 gives a single
severity mapping (flagged→WARNING) while §A pins quality rules to a "fixed INFO
consequence." These conflict only for a quality *flag*. Resolved: quality flags
emit at INFO (preserves the existing stale/placeholder/outlier INFO tests and
honors "quality cannot degrade a grade"); grade-bearing (banded/conditional)
flags use WARNING. A second shorthand — the handoff writes
`EntityRef(system="IDS", type=, id=)` where the real `EntityRef` is
`{entity_id, entity_type}` and `system` lived only on `ExternalRef` — was
resolved by adding the `system` field to `EntityRef` (additive, default
`"canonical"`), entity_type carrying the submission-space type ("order_id") and
entity_id the submission id.

**Generator truthfulness fix (found by a test interaction).** The `stale_due_dates`
anomaly pushed due_date 400 days into the past while leaving created_date recent,
which the new order_dates_internally_consistent check correctly reads as due <
created. A stale-backlog order was *created* long ago too, so the anomaly now
ages created_date with the due date — the row stays internally coherent and the
stale flag is a pure backlog signal, not a spurious inconsistency.

### 2026-07-10 — Conversational Certificate: catalog, renderer, router, triage

The Rule Registry groundwork (same-day entry above) built the machinery; this
session built the **conversational surface** over it. Three answer registers now
sit alongside testimony and judgment; a frozen remediation catalog supplies the
words; a single grade-distance triage supplies the order.

**Frozen catalog, loaded typed.** `remediation-catalog-v1.yaml` (32 rule-level
notes + 18 code-level fallbacks, FROZEN in the design thread) lands at
`src/mre/catalog/` and loads into validation-at-construction Pydantic models
(`RemediationNote` keyed by RuleId, `FallbackNote` keyed by FindingCode). The
prose was treated as read-only authored knowledge — not edited here; edits are
design-thread work that bumps note_version. Completeness tests parametrize over
the registry/vocabulary (never hand lists): every rule has exactly one note,
every finding code exactly one fallback, each note's outcome_phrasing keys ⊆ its
rule's category-permitted outcomes, banded notes carry the registry's `measures`.

**Reported defect, not fixed (report-don't-edit).** Two frozen quality-rule
notes — `decision_relevant_attributes_populated`, `optional_columns_are_not_sparse`
— carry a `fix_looks_like` with **no resolvable IDS §-cite**, which the §2
jurisdiction lint requires of every rule-level fix. Adding a cite is a prose edit
(note_version bump) reserved to the design thread, so the two are **quarantined**:
the lint runs for the other 30, and a pinned guard asserts the uncited set is
exactly those two, so a later catalog fix trips the guard and the quarantine is
re-derived rather than silently kept. Surfaced for the design thread; not
worked around by editing frozen prose.

**Thresholds_ref resolves to real numbers.** The catalog's `appendix_a.*`
anchors resolve through a single `APPENDIX_A_BANDS` source in `ids_rules.py`
(reject 0.60 / conditional 0.97), the same numbers the gate bands against — so a
note's authored threshold is instantiated, never reinvented. (The registry's
coarse "App A" ref and the catalog's specific anchor point at the same band; the
completeness test asserts the measure name matches and a thresholds_ref is
present, not that the two anchor *strings* are equal.)

**Remediation register — single-source-of-truth validator (the 2026-07-06
lesson, again).** Rendering a remediation is the note's authored text
instantiated with one finding's evidence (subjects, measured value, threshold
band, phrasing keyed by the finding's outcome). The allowed-number set is
derived from *exactly* the render material in one derivation; any number in the
output absent from that set fails closed (the LLM path falls back to the
deterministic authored body). Output is introduced as authored guidance with the
catalog note_version as a footnote — never as testimony.

**Grade-distance triage — one ordering, pure function.** `triage_findings`:
all `violated` first; then `degraded` by proximity to the Appendix A threshold
that escapes the band (closest first); then `flagged`, WARNING before INFO,
quality last. Severity is reused as (outcome, category) via `outcome_severity`,
never re-derived. The judgment register names the arithmetic (rule, measured,
threshold, distance). Both the remediation ordering and any future UI consume
this one function.

**Router + REJECTED certificate-only mode.** The explainer routes certificate
questions: "what's wrong / why rejected" → testimony; "how do I fix it" →
remediation; "what should I fix first / does this matter" → judgment. Resolution
goes through identity (canonical when a snapshot exists, else the IDS-space
subject the gate finding already carries) — never an id-shape regex (Phase-1
exit audit rule). A REJECTED submission has no snapshot; `python -m mre` now
builds the evidence index from the gate run before stopping, and the explainer
runs certificate-only (reader/identity_map None) so all three questions still
answer with IDS-space identity.

**Errand (a) — wip_in_progress_rows_carry_progress disposition audit.** The gate
(and the adapter) labelled the in_progress-missing-progress finding `DEFAULTED`.
Audit: the adapter sets status to not_started and **clears** actual_start /
resource / progress — nothing is invented; the unverifiable in-flight claim is
dropped. `defaulted` mislabelled an **exclusion**. Corrected to `EXCLUDED` in
both the gate and the adapter (matching the sibling wip_references_known_entities
"treated as not started"), making the catalog note ("we never invent a progress
value") true. Grade is unaffected (a pure function of outcomes, not
dispositions). The separate blank-slate provenance (`defaulted` on an unobserved
op's wip_status attribute) is legitimate and untouched.

**Errand (b) — docs/06 §4 severity wording.** Amended from "severity derives
from outcome … with the one exception" to "severity is a function of (outcome,
category)", the two arguments named irreducible — the category is what
distinguishes an informational quality flag from a WARNING flag at the same
outcome. Matches `outcome_severity(rule, outcome)` and the catalog header.

985 tests green (+145). No new finding codes. docs/06 §4 amended (severity
wording); docs/02/05 untouched.

### 2026-07-10 — Phase-2 exit audit (fresh session, audit mode): five clauses run live

The docs/07 Phase-2 exit was audited as written (Clauses 1–5; Clause 6, the
certificate-session addenda, was resolved at `acb75b8` and is treated as
recorded). Audit rule: run the clauses as written, **no fixes unless a clause
fails**, name every accommodation, verify live (stale context presumed wrong).
**No clause failed — the audit was fix-free.** Verdicts and the accommodations
they rest on:

**Clause 1 — Exit demo, fresh, deterministic, ≥2× identical: PASS.** The
`deploy/smoke.py` exit demo (clean_large seed 7, ~3000 orders) was driven over a
live `uvicorn` instance (`PYTHONHASHSEED=0`) twice. Both runs: ACCEPTED/C1, 7460
assignments, whatif cost-delta 23773588.5 (identical), ~130s wall (under the
165s scale-ladder baseline — a faster host; timings are environment-specific,
not a gate). The business-stable schedule hash (`0f475d2a…`, dropping
per-submission uuid5 surrogate refs) was **byte-identical across the two fresh
submissions**. Accommodation named: the uuid5 refs (operation/workpackage/
resource) differ between two independent submissions — expected (per-submission
surrogate identity, not schedule content). `smoke.py`'s what-if POST omits
`deterministic:true` (only the solve sends it) — a latent gap that did **not**
reproduce here (identical cost-deltas both runs), so it is a code follow-up to
pin, not a carried discrepancy.

**Clause 2 — Live per Phase-2 item: PASS.**
- *2a API layer:* contract 1.1 doc retrievable; scenarios excluded from the
  default `/schedules` listing and pool members are never schedule rows
  (structural); POST pool on a what-if scenario → **409**.
- *2b Warm-start:* the exit-audit noise case reproduced live — unbatching a
  merged WP moved **0 untouched ops warm (both repeats) vs 51 cold, at identical
  cost delta (309.24)**; warm departs the hint to the same optimum cold finds.
  Base run under `merge_by_family_v1`, deterministic.
- *2c Solution pool:* a pool built on a fresh schedule (5 members, ready);
  diversity honours `DIVERSITY_TOLERANCE_MINUTES=15` (per-member Hamming
  ≥1 at the 15-min threshold; the no-good cut and Hamming share it); the base
  snapshot was **byte-identical before/after pooling**; `mark_schedule_superseded`
  flips the pool to `invalidated`.
- *2d WIP/mid_replan:* completed op produces no assignment; rescue on time
  (−418 min); completion-frees-capacity counterfactual (WIP tardiness 0 <
  no-WIP 725.8; no-WIP rescue 1021 min late); in-flight holds future start
  (600 ≥ 600 remaining); no scheduled start before reference_date; the sunk-setup
  ledger separates the sunk line (80.0) from a strictly-lower movable setup
  (80 < 160), decomposition exact (prod+setup+tard = total, sunk additive).
  Accommodations named: mid_replan's in-flight op is a *fixed interval*
  (non-resumable), so "resumable remainder pauses at closures" was verified via
  the shared chunk-pause invariant (chunking_exam live: 4 derived pauses, all
  inside closures); and the fixture has no *genuine* ghost job, so the ghost
  guard was confirmed in its un-regressed direction (WIP demands correctly NOT
  ghost-excluded).
- *2e Conversational Certificate:* against a fresh CONDITIONAL (messy_realistic)
  and REJECTED (rejected) plant, the three questions route to three distinct
  registers (testimony/remediation/judgment tags, never blended); testimony
  footnotes records; remediation renders authored notes citing IDS §-sections
  (§5.1, §5.6; catalog note v1); judgment orders violated-first / degraded-by-
  closest-escape; REJECTED answers certificate-only (no snapshot). No ERP-specific
  surgery in any answer (jurisdiction holds).
  Environment accommodation (2a/2c/2e): an initial long absolute data root chosen
  to dodge a Git-Bash-`/tmp`-vs-native-Windows-`/tmp` split tripped Windows
  MAX_PATH on the what-if's snapshot `copytree` (WinError 3); re-running under a
  short root made the what-if succeed. A path-length artifact of the audit
  harness, **not** a product defect (corroborated by the clean_large smoke and
  the full suite).

**Clause 3 — Gauntlet + sliced daily solve: PASS.** `--raw-data raw_data
--plant-config plant_config.json --horizon-days 2` (the sliced daily solve),
deterministic (`PYTHONHASHSEED=0 --solver-workers 1 --solver-seed 42`), produced
a schedule.csv **byte-identical to the golden** and a cost ledger **identical**
(total 18481, all tardiness), with the **173 INFEASIBLE_SUBSET exclusions**
regression anchor intact. Accommodation: a first run without the deterministic
flags differed (CP-SAT parallel search) — the "identical schedule" rule requires
deterministic mode; re-run under it, byte-identical. **Policy finding (per the
audit's correction):** the gauntlet's run context records
`policy=identity_v1` — the **default, 0 merges** — not a merge policy. Both
`merge_by_family_v1` *and* `merge_by_family_v2` exist as opt-in `--policy`
choices (the merge-as-tractability-lever dossier concerns those, not the default
gauntlet run); **v2 exists — flagged as instructed.** **Restated, not resolved
(Phase-4):** the raw_data path bypasses the M0 gate — it produced **no
certificate** — and has no WIP doorway; owned by the pilot connector, after which
the raw path is demo-frozen.

**Clause 4 — Cloud posture: PASS-WITH-QUALIFICATION.** Docker and the Azure CLI
are both unavailable in-session, so the three open confirmations — first
in-container CI run, live `az deployment` from `deploy/azure/`, cloud smoke —
are recorded **OPEN, carried to follow-up 2.4b**. Deploy-verified-locally is not
deploy-verified-in-cloud.

**Clause 5 — Carry-forward inventory** (nothing evaporates silently):
- `OperationSpec.yield_factor` false-observed provenance — **OPEN** (default 1.0
  still cites `routing_lines.csv` as an observed source; provenance-truthfulness
  cleanup, re-parked to Phase 3).
- Sentinel / repeated-identical-value detector (the 40× `run_rate_seconds=60.0`
  fingerprint) — **OPEN**, not built (re-parked to W1, the permanently-open gym).
- Provenance spot-check guard — **OPEN**, not built (re-parked to W1/Phase 3).
- W1 scenarios `dwell_heavy` / `calendar_chaos` / `multi_facility_balance` —
  **OPEN**, none built (mid_replan was built in 2.3; these three re-parked to W1).
- Pool warming-on-publish — **OPEN**, explicitly parked (becomes default when the
  Phase-3 publish workflow lands; auto-warm opt-in until then).
- Pool slice-awareness — **OPEN** (2.3 carry; lands with pool sliced-mode
  productionization).
- Extractor sunk-setup billing — **RESOLVED** 2.4 CU0.5 (re-confirmed live in 2d).
- Two quarantined catalog notes (`decision_relevant_attributes_populated`,
  `optional_columns_are_not_sparse`) with no resolvable IDS §-cite in
  `fix_looks_like` — **OPEN**, quarantined + pinned, design-thread note_version fix.
- `test_n3000` contention-sensitivity — **OPEN/known**: passes solo (~50–58s),
  flakes under full-suite CPU contention; marked contention-sensitive.

**Verdict: Phase 2 exits COMPLETE (qualified).** All five clauses PASS or
PASS-WITH-QUALIFICATION; no clause failed; no fixes were required. The
qualifications above are the carried exit conditions.

### 2026-07-11 — Session 3.0: frontend bake-off SPIKE (Phase-3 entry) + merge_v2 carry-in

A timeboxed, throwaway spike to choose the rendering substrate for the Phase-3
cockpit's three-tier drag surface. Spike rules (chunking-spike precedent):
code in `tools/spikes/frontend_bakeoff/`, no production wiring, the deliverable
is a verdict. Full report: `tools/spikes/frontend_bakeoff/VERDICT.md`. **The
docs/07 frontend line is deliberately NOT updated — verdict reviewed jointly
first.**

**Carry-in — `merge_by_family_v2` traced.** Origin commit `847fe89` ("Rep 4"),
**design-reviewed** (this doc, 2026-07-12 amendment; acceptance tests
`tests/test_planner_merge_v2.py`). Behavioural diff vs `_v1`: identical
candidate grouping, then two gates before committing a merge — feasibility
(class-aware window-fit on the *merged* quantity, R-C3) and risk (tardiness
exposure on the earliest-due constituent's *working-time* budget vs. a
corrected setup benefit × `risk_margin`); a rejection at either gate falls the
batch back to solo WorkPackages with a `merge_rejected` Decision
(`CAPACITY_BLOCKED` / `COST_TRADEOFF`). Both variants added to the solver-gap
dossier's tractability-lever entry (`tools/solver_gap_probe_report.md`): v1 =
maximum tractability, unpriced risk (the 3.3× figure is v1's); v2 = gated,
data-dependent, ≤ v1's multiplier but each merge earned. Phase-4 name-the-policy
discipline now spans three values.

**Fixture (shared, both candidates + a real finding).** Real `messy_realistic`
deterministic solve (seed 7 / solver seed 42, `PYTHONHASHSEED=0`) → contract-1.1
`schedule.json` (475 assignments / 16 resources) via `build_document_from_run`;
static `anchors.json` for one grab task via `build_fixture.py`. **Finding:**
every generator scenario routes each operation to **exactly one** resource
(eligibility `{1:475}`; single `resource_id` per routing line), and the pool on
this slack schedule yields **9 movers at Δ$0, none in a precedence chain** — so
generated data has **no legal cross-machine move and no priced successor
ghost**, defeating a faithful drag fixture. Resolution: board geometry anchors
are real; cross-row legality + ghosts are an authored `spike_capability_overlay`
(same-facility pool), **real-priced** from the cost model, and labelled as such
in `anchors.json._meta` (static anchors = the brief's honest interim-A scope).
**Carry-forward (W1/Phase-3):** the generator needs capability-based
multi-eligible routing before real Tier-0/Tier-1 anchor computation is possible.

**Bake-off result.** Candidate A (custom React: SVG + dnd-kit) and Candidate B
(vis-timeline), same fixture, same `shared/geometry.js` snap core, driven by a
candidate-agnostic Playwright harness (`harness/run.mjs`, the surviving
interim-A infra). Both **GREEN on the mechanics**, both driveable headlessly
(scripted contract + real pointer — dnd-kit robustly; vis's Hammer.js drag
engaged only via a diagonal multi-step gesture, a criterion-5 caveat, *not* a
hard fail — an initial "hard fail" read was a diagnostic artifact, corrected by
driving the real gesture). Latency well under target (A 17–23 ms, B 30–45 ms).
Neither hard-failed criterion 1/3/5. B's one material blemish: vis-timeline
**clips all in-bar text to the bar box**, so priced-ghost labels ("+$53" → "+")
and narrow-bar labels need an always-on overlay layer synced to vis's pan/zoom
(fragile) — a criterion-2/6 concern on a demo-critical feature. Licences clear
both ways (dnd-kit/react MIT; vis-timeline Apache-2.0 OR MIT). **Recommendation
(decision rule "library wins ties", no killer hard-failed): adopt vis-timeline,
conditional on a follow-up proving a stable label/overlay layer; Candidate A is
the proven zero-blocker fallback with a higher feel ceiling. Close call — to be
settled in joint review.**

### 2026-07-11 — Session 3.0b: frontend bake-off extension — the drop ruling's four criteria (vis-timeline SELECTED)

The 3.0 recommendation adopted vis-timeline **conditional** on a follow-up
proving a stable always-on overlay layer, with custom React as the zero-blocker
fallback if the overlay or magnet feel proved fragile. 3.0b **is that follow-up**,
widened by a new drag ruling (pending its own amendment): *a drag is a literal
must — the bar lands exactly where dropped or returns home; proven-illegal zones
must **visibly refuse the drop mid-drag** (no post-hoc dialog); semantic snap
with generous tolerance interprets within legal zones.* Same throwaway spike,
same directory. New surface `candidate_b_3b.html` + `src_b/main_3b.js`
(zoom/pan **enabled**, unlike 3.0's frozen window, so the overlay's tracking is
actually exercised); new evidence harness `harness/run_3b.mjs` →
`shots/report_3b.json` + `shots/b3b_*.png`. Only vis-timeline under test (3.0
already cleared A).

**Decision rule (final, from the 3.0b brief):** vis-timeline adopted **only if
all four criteria pass clean**; any failure or fragile workaround → Candidate A.

**Result — all four PASS clean → vis-timeline ADOPTED.**
- **C1 always-on overlay layer:** a positioned layer (mounted in vis's
  `centerContainer`, redrawn from public `getWindow()` on
  `rangechange`/`rangechanged`/`changed`) carries the priced ghost labels +
  tentative hatch. True drift test = overlay-label centre-x vs the **vis-rendered**
  ghost-bar centre-x: **0.0 px** at the 4-day window, a 30 h zoom, and a 16 h
  zoom (shared linear time→x map). The 3.0 in-bar clipping blemish ("+$53" → "+")
  is **resolved**; labels legible at every level.
- **C2 mid-drag rejection:** `onMoving`'s `cb(null)` refuses the frame — the bar
  will not enter a dim (illegal) row, pinning at the last legal boundary with a
  `not-allowed` cursor + banner; `onMove`'s `cb(null)` returns it home on an
  illegal release (`phase=returned_home`). Proven scripted **and** by a real
  Playwright pointer drag. Public API, not a workaround.
- **C3 one real magnet with falloff:** single shift-start/ghost anchor,
  tolerance radius, Alt-disable, falloff line in the overlay. Isolated-anchor
  sweep gives a **clean monotonic** `0→0→0.27→0.5→0.73→0.9→1.0`, 0 outside
  tolerance, Alt frees. Granularity answered by call:step ratio **0.95 (42/44)**
  — **vis fires `onMoving` per pointer-move, no throttle**; the single hook
  carries falloff rather than fighting it. (Custom React keeps a higher feel
  ceiling via a dedicated rAF loop, but the hook is not the bottleneck.)
- **C4 headless reliability:** **20 / 20** consecutive real-pointer drags
  (deterministic; each `dropped`, 14 `onMoving` calls) — **conditional on the
  diagonal group-crossing engage gesture** the 3.0 spike identified, now encoded
  in the harness. The number behind "finicky": 20/20 with the right gesture; a
  prescriptive engage motion, not per-run flake.

**Honest correction (recorded).** My first 3.0b harness pass read C3 as **FAIL**
on two counts, both **probe artifacts** — corrected exactly as the 3.0
criterion-5 Hammer misread was: (1) "non-monotonic falloff" measured
*nearest-of-all-targets*, so a passing `adjacency` edge broke monotonicity — the
criterion asks about **one** magnet, so the fixed probe measures a single
anchor; (2) "21 Hz too coarse" was **Playwright's synthetic ~45 ms/step pacing**,
not a vis throttle — the call:step ratio (0.95) is the throttle-free measure.
Raw first run is in git history; corrected numbers above.

**Effect on the 3.0 recommendation:** the condition is **discharged**. The
overlay is stable (0 px), magnet feel is reachable and un-throttled, illegal-zone
refusal works, headless drag is 20/20 — vis-timeline passes on its own merits, no
tiebreaker needed. **Adopt vis-timeline;** custom React/SVG + dnd-kit stays on
record as the proven zero-blocker fallback (higher feel ceiling) should
feel-iteration on the bespoke overlay later change the calculus. **docs/07
frontend line updated (v1.8)** per the brief's instruction; `VERDICT.md` carries
the full 3.0b addendum. Residuals disclosed, neither a failure under evidence:
the overlay reads vis DOM geometry (stable public-ish surface), and I verified
settled-window drift across three zoom levels rather than a single mid-flight pan
frame.

## Amendment — 2026-07-11: Drop-pin ruling resolved (open-rulings queue item 5) + the cockpit edit vocabulary

Resolved in the Phase 3 design thread. Supersedes all earlier
sketches of drag-intent inference as the primary mechanism.

**R-DP1 — A drag is a literal must.** The dropped bar lands exactly
where the planner placed it — machine and time as displayed — or
the drop does not happen. The sandbox re-solve holds the dropped
bar fixed and rearranges only its surroundings; it never relocates
the dragged bar to a "better" spot. Rationale: planner testimony —
a moved bar settling anywhere other than where it was dropped is
read as disobedience, not intelligence. The one thing the planner
touched is the one thing that cannot move. This resolves the
drop-pin default (machine / start / both): the pin is BOTH, as
displayed.

**R-DP2 — Commit-or-return.** Proven-illegal zones (Tier-0 dim:
capability, closed calendar, precedence floor, window-fit) refuse
the drop mid-drag — release over dim snaps the bar home; no dialog,
no post-hoc explanation beyond a one-line hover reason during the
drag. Drops that pass Tier 0 land as a visually distinct TENTATIVE
bar pending the sandbox verdict; if the re-solve is infeasible with
the pin held, the bar returns home carrying the binding constraint
and the nearest feasible alternative (relax-and-report, per A7
machinery). Invariant: the bar ends where it was put, or where it
started — never a third place. Nothing mutates before accept.

**R-DP3 — Semantic snap, generous tolerance.** Within legal zones,
snap targets are semantic anchors, not a time grid: ghost
placements (strongest), calendar openings, adjacency edges,
predecessor-finish floors; coarse grid only as fallback in open
space. Snap resolves DURING the drag (the planner watches the bar
click to the anchor before release), preserving R-DP1 literalness.
Alt-drag disables snapping. Tolerance radii are externalized design
tokens (feel-iteration owned).

**R-DP4 — Gesture is command; language is wish.** Soft preferences
("try to keep Henderson on Press 2 this week") enter through the
conversational channel only, compile to objective penalty terms
(new soft-preference constraint category alongside A7's hard pins,
docs/05 row required), and may be overridden by the solver with a
visible priced explanation. Gestures never compile to wishes;
wishes never move bars silently.

**R-DP5 — Additional verbs, all priced Decisions through the
sandbox:** HOLD (earliest-start push / parked state for
not-yet-started work; capacity freed; accruing tardiness priced on
the card; in-flight pause is out of scope pending the
interruptibility ruling) and DEFER (unschedule a demand — never
deletion; the card prices what removal costs against what it buys).

**R-DP6 — Legality epistemics (what each layer may claim).** Dim =
proven illegal by canonical arithmetic; never wrong. Green =
provably-not-illegal by every cheaply-evaluable rule; NOT a
full-model guarantee. Ghosts = the only pre-release known-feasible
targets (a complete solved schedule vouches for each). The Tier-2
re-solve is the sole full-model authority. Saved solutions (pool,
incumbents) never define legality — rules define the map, solutions
decorate it. Delta cards may offer an explicit relaxation toggle
("keep machine, let time float") after landing, with the drag axis
informing only which relaxation is offered as the default — never
silently applied.

**Consequences registered:** (1) contract 1.2 additive
"interaction payload" — eligibility sets, calendar windows,
precedence edges, remaining durations, occupancy — so Tier-0 is
computable client-side; (2) a capability-routed generator scenario
(multi-eligible routing per B2, real cost differentials) is an
interim-A entry prerequisite — the 3.0 spike proved generated data
currently contains no legal cross-machine move and no priced ghost,
making the sixty-second script impossible on it; (3) mid-drag
refusal (R-DP2) is a load-bearing bake-off criterion, tested and
PASSED in 3.0b; (4) the docs/07 open-rulings queue marks item 5
resolved, citing this entry.

## Amendment — 2026-07-11: R-DP7 — Change legibility (extends the drop-pin ruling)

Added in the Phase 3 design thread immediately after R-DP1–R-DP6
were ratified; authored as its own entry per append-only.

**R-DP7 — Change legibility.** No schedule state change is ever
rendered as an instantaneous silent swap. (a) The dropped bar
carries a distinct visual state through its whole lifecycle —
tentative on landing, confirmed on accept, and if returned home it
returns animated along a visible path with the reason attached,
never teleporting. (b) Every bar the sandbox re-solve moved as a
consequence of an edit is visibly traced from old to new position
(ghost-of-old + motion trace or equivalent), held on screen until
the edit is accepted or discarded. (c) Delta card line items are
linked to board annotations — the card's "Ortiz slips 4h" IS
Ortiz's on-board displacement trace; selecting a card line
navigates to that bar. (d) Accepted edits remain replayable from
their Decision records (recent-changes affordance: re-highlight
what a past edit moved). Rationale: planner testimony — a drop
followed by unexplained board motion, or by hunting for what
happened to the dropped item, is the same frustration R-DP1
eliminated, arriving through the surroundings instead of the bar.
Implementation note: the moved-set is computed by the schedule
differ (2.2, serialization fix applied); warm-started sandbox
re-solves keep consequence sets minimal by construction, which is
what makes tracing them tractable.

## Amendment — 2026-07-11: Session 3.1 CU1 — `multi_route`, the capability-routed scenario (docs/05 B2; the interim-A prerequisite)

The Session 3.0 bake-off's honest caveat (VERDICT.md) was that
**every generator scenario routed each operation to exactly one
resource** (eligibility-size distribution `{1: N}`), so generated
data contained no legal cross-machine move and no priced ghost —
the sixty-second cockpit script was impossible on it. The R-DP
consequences block (2026-07-11) named a capability-routed scenario
as an interim-A entry prerequisite. This is it.

**Representation — no schema change (docs/06 §5.3, docs/05 B2).**
An operation's eligible set is expressed as **multiple
`routing_lines` rows sharing one (route_id, sequence) but naming
different resource_id**. The IDS adapter now GROUPS a route's lines
by sequence and builds one OperationSpec whose ResourceRequirement
is `explicit_set` over the whole resolved set (previously: one spec
per line, single-element set). One row per sequence — the common
case — yields a single-element set **byte-identical to the
pre-grouping adapter**, so the defaults-reproduce-baseline
modularity gate holds (the full IDS end-to-end + generator suites
stayed green, 54 passed). The op's time model (setup/run overrides)
is read once from the sequence's first row; the differential a
multi-eligible op carries lives on the *resources* (per-resource
`cost_rate`/`calendar`), never the op time — so the single
`OperationSpec.run_rate` still holds and the canonical model is
unchanged. The Solver Builder already implemented the disjunctive
alternative-resource choice (one optional interval per eligible
resource); it needed nothing.

**The scenario (`tools/generate_erp_dataset.py::_apply_multi_route`).**
1 facility, 6 resources; R0,R1 share the cheap $50 rate, R2..R5 are
$55/$60/$65/$70. Two products with multi-eligible ops IN precedence
chains: PROD-MR-A (3 steps) seq10 {R0,R1,R2} → seq20 {R0,R1} →
seq30 {R0,R1,R3}; PROD-MR-B (2 steps) seq10 {R0,R1} → seq20
{R0,R1,R2}. 12 orders, due 5-6 days. 5 multi-eligible ops, 3 of
them tier-spanning (a nonzero ghost price by construction).

**The design that made the pool actually surface cross-machine
ghosts — the hard-won lesson.** A pool member is a near-optimal
re-solve under a start-time diversity cut; it MINIMIZES objective,
so it reveals a cross-machine alternative only when a sampled op is
*boxed in* (cannot slide in time on its own machine) AND the jump
is near-optimal. Two facts follow, both learned by measurement
(many tuning iterations recorded in the session):
- **Distinct rates ⇒ a unique optimum.** With a wide rate spread,
  the optimal machine assignment is essentially unique; at the true
  optimum the pool finds only time-shifts (hamming≈1, cross-machine
  0). Early "cross-machine = 15" readings were an ARTIFACT of a
  *suboptimal* incumbent (the pool found 40% cheaper, cross-machine
  solutions) — not genuine near-optimal alternatives. A wide spread
  also made contention hard to solve, so the base itself was a poor
  incumbent — an ugly fixture.
- **The fix: a saturated identical-rate pair.** R0 and R1 both bill
  $50 and carry almost all the work at ~90% load, so *which of the
  two* an op runs on is a genuinely free, degenerate choice: the
  base solve is easy and near-optimal (flat cost ⇒ FEASIBLE ≈
  optimal, on-time), and the diversity cut readily swaps ops R0↔R1
  at ZERO delta — this is what puts cross-machine moves in the pool.
  The R2+ pricier machines are idle spill valves whose only job is
  to give some ops a *different-rate* eligible alternative, i.e. the
  nonzero ghost PRICE, asserted directly from the eligibility set
  (working_min × Δrate), independent of the pool's stochastic choice.

**Assertions (`tests/test_multi_route.py`, deterministic
workers=1/seed=42).** Structural (default suite): multi-eligible
ops exist with the expected max fan-out; a multi-eligible op sits
in a precedence chain; a scheduled multi-eligible op has a
different-rate eligible alternative (nonzero ghost price). Slow:
the pool built on the solve places ≥1 op cross-machine; and the
**counterfactual** — collapsing the scenario to single-eligibility
(keep the first `routing_lines` row per (route,sequence)) drives
the pool's cross-machine count to **0** and lowers its diversity
profile. That collapse is the price-bought-something proof the
routing alternatives are real, not decorative.

**New diversity sub-metric.** `solution_pool.py` now reports
`diversity.cross_machine_ops` (ops at least one member places on a
different *resource*, not merely a different time) — the Tier-1
"other press" ghost precondition and the counterfactual's anchor
(0 by construction on single-eligibility data).

**Carry-forward.** The base solve is a fixed-time-limit FEASIBLE
solve that measures optimal-quality here (pool cannot beat it) but
is not PROVEN optimal; the fixture is small by design so this is
cheap and stable. The `multi_route` board is now the cockpit
fixture for CU2–CU5.

## Amendment — 2026-07-11: Session 3.1 CU2 — schedule contract 1.2, the Tier-0 interaction payload

Additive minor bump (`schedule_document.py` CONTRACT_VERSION 1.1 →
1.2). Per the R-DP consequences block (contract 1.2 "interaction
payload"), the cockpit computes legal drop zones CLIENT-SIDE with
no solver round-trip (docs/07 Phase 3 Tier-0; R-DP6 legality
epistemics). The new top-level `interaction` block carries exactly
what that arithmetic needs and nothing it can derive:
- `operations[]` — per scheduled op: `eligible_resource_ids` (the
  WHOLE set, not the chosen one, so the board can dim
  capability-illegal rows), `working_min` + `setup_min` (bar size
  for a fit/displace test), `earliest_start` (the release floor =
  Demand.earliest_start, R-A4; MAX across a merged WP's demands).
- `precedence_edges[]` — template PrecedenceEdge records EXPANDED to
  Operation-instance refs the same way the Solver Builder resolves
  them ((workpackage_ref, spec_ref) → op id), so the refs live in
  the same id-space as `interaction.operations` and the board bars
  (a spec-keyed edge would be unusable — refs in a different space).

**Deliberately NOT duplicated:** calendar windows already live per
lane in `resources[].calendar_windows` (regular/overtime/closure);
resource occupancy is computed client-side from `assignments[]`
(resource_id + chunks) — the schedule already IS the occupancy.

**Additivity proven.** The block is built ONLY when the assembler
is given `edges` (the API path, `build_document_from_run`, now
passes them); pool members and any 1.1-shaped caller get
`interaction=None` and are unaffected (tested:
`test_absent_when_no_edges_supplied`). The eligibility resolver
mirrors `solver_builder._eligible_resources` so the client sees the
SAME set the solver enforced.

**Size check (the brief's request).** On the 3K-order `clean_large`
schedule (7,460 assignments) the payload adds **+1.9 MB (+35.7%)**:
base document 5.4 MB → 7.3 MB. This is material. **Proposed, not
implemented** (interim-A is read-only): a split-endpoint —
`GET /schedules/{id}` keeps the render document (1.1 shape), and a
sibling `GET /schedules/{id}/interaction` serves the Tier-0 payload
fetched once on first grab. The payload is grab-time data, not
first-paint data, so the split costs nothing perceptible and keeps
the initial render document lean. Deferred to interim-B (the drag
surface) where the payload is actually consumed.

## Amendment — 2026-07-11: Session 3.1b — interim-A frontend stack decisions (CU3–CU5 groundwork)

Session 3.1b built the three remaining interim-A commit-units (CU3
cockpit shell, CU4 ask panel, CU5 screenshot harness). The stack
choices left open by the Session 3.1 brief are recorded here so
they are reviewable; the per-unit amendments follow.

**Home — `src/cockpit/`** (a peer of `src/mre/`, its own npm
package). The production frontend lives here; nothing about it
reaches into the Python package and vice-versa (it talks to the API
over HTTP only). `.gitignore`d: `node_modules/`, `dist/`.

**Bundler — Vite 5** (`5.4.21`), the same tool the throwaway
bake-off spike used, so the vis-timeline substrate's proven
behaviour carries over unchanged. Dev/preview PROXY the API
(`/schedules`, `/submissions`, `/runs`, `/health`) so the browser
sees one origin — the FastAPI surface has no CORS middleware by
design (single-tenant-by-construction, docs/08). The built app
fetches the same relative paths, so it runs behind the API or the
test fixture server with no rebuild.

**Framework — none (vanilla ES modules).** The read-only board
needs no component runtime; the bake-off's Candidate-A React path
was the *drag*-surface's higher-feel fallback, not required for a
render-only cockpit. Feel-iteration lives entirely in
`src/cockpit/src/tokens.css` (colors, spacing, motion durations,
and the semantic mappings — lateness bands, register hues,
calendar shading, citation glow) — externalized from day one per
the CU3 brief.

**vis-timeline pinned to the bake-off version.** `vis-timeline`
`7.7.4` + `vis-data` `7.1.10` pinned exactly (no `^`) in
`src/cockpit/package.json` — a version bump is now a deliberate act
that must clear the CU5 harness (the C1 drift regression is the
tripwire).

**Small API additions (thin, additive, no business logic).**
(1) `GET /schedules/{id}/meta` — registry metadata joined to the
submission's certificate GRADE (`registry.get_schedule_meta`). The
grade is a submission property living in the certificate store, NOT
in the derived-not-invented schedule document; the cockpit's top
strip reads it here. (2) The `/ask` response envelope gained two
additive fields read straight off the bundle the explainer already
produced — `bundle.register` (testimony | judgment, so the panel
styles the card without parsing prose) and `bundle.cited_refs`
(`{operations, resources, demands}`, the entity refs the answer
already cites, so the board can highlight the matching bars/lanes).
Both SURFACE existing citations; neither adds an answer path or an
evidence surface (honesty armor intact). Covered by
`tests/test_api_endpoints.py::TestScheduleMeta` +
`TestAsk::test_ask_surfaces_register_and_cited_refs` /
`test_cited_refs_point_at_real_board_entities`.

## Amendment — 2026-07-11: Session 3.1b CU3 — the cockpit shell (read-only board)

The production reasoning-cockpit board (`src/cockpit/src/board.js`
+ `main.js` + `cockpit.css` + `tokens.css`), a vis-timeline render
of a **contract-1.2 document fetched from the live API**. Verified
end-to-end against the real FastAPI (a live `multi_route` solve,
Vite proxying `:8000`).

- **Resources are rows, assignments are bars, in the PLANNER's
  vocabulary** — `external_name` on lanes, `work_orders` on bars;
  canonical UUIDs never appear on screen (they stay in refs the
  code navigates by). The identity map already put the external
  names in the document (`*_name`/`work_order` fields); the board
  just renders them.
- **Lateness-signal coloring, per Demand.** Each bar's color is the
  worst lateness among its demands' `service_outcomes`
  (`lateness_min`), never a per-WorkPackage number — bands (on-time
  / tight / late) in `board.js`, hues in `tokens.css`. (On the
  near-optimal `multi_route` fixture every order is early, so the
  board reads on-time/tight; the late band is exercised by any
  tardy schedule.)
- **Calendar closures shaded**; overtime tinted; regular windows
  left unshaded (`resources[].calendar_windows`, culled to the
  visible span).
- **Top strip = version + certificate grade** — `contract 1.2 ·
  <id>` + status + the certificate grade chip (`ACCEPTED / C1`),
  the grade fetched from `/meta`.
- **Read-only is the law:** `editable: false` everywhere — no drag
  handlers wired (interim-A). The drag surface is interim-B.

**vis-timeline blank-board fix (recorded because it will recur).**
vis leaves the timeline root `visibility:hidden` until an initial
range-change completes *when `start`/`end` are passed as
constructor options*; for a static (non-animated) window that
range-change never fires and the whole board renders blank while
the item DOM exists (so a naive DOM-count test passes green — it
did, and hid the bug until the screenshot). Fix: do NOT pass
`start`/`end` as options; construct with `min`/`max` only, then
`timeline.setWindow(win.start, win.end, {animation:false})` +
a `requestAnimationFrame(redraw)`. This is load-bearing; the CU5
harness now screenshots the board so a regression can't hide.

## Amendment — 2026-07-11: Session 3.1b CU4 — the ask panel + cited-bar highlighting

`src/cockpit/src/askpanel.js` embeds the M10 explainer against the
rendered board (`POST /schedules/{id}/ask`). Three integrations
make the evidence architecture spatial:

- **Registers render visibly distinct.** The answer card is styled
  from `bundle.register` (testimony = teal left-rule + fill;
  judgment = amber) — the two never blend, mirroring the renderer's
  own discipline. The register is surfaced structurally, not parsed
  from the rendered footer.
- **Cited bars + lanes light up in sync with the answer.** On each
  answer the board highlights the bars whose `operation_ref` is in
  `cited_refs.operations` (+ bars of any cited demand) and tints the
  lanes in `cited_refs.resources` — the CHOSEN resource AND the
  priced alternatives the answer names ("the other press"). An
  always-on overlay layer (the 3.0b concept, productionized) draws a
  legible tag centred on each cited bar — this both solves the 3.0
  narrow-bar label-clipping lesson and is the carrier for the CU5
  drift regression.
- **Shared selection → deictic ask.** Clicking a bar scopes the
  panel ("selected ORD-000012 on F001-RES002"); "Why is this here?"
  composes the exact question the explainer already understands
  (`why is <wo> on <resource>?`) from the board's own state —
  proven live (click → `why is ORD-000006 on F001-RES001?`).

**Honesty armor — the acceptance moment holds through existing
surfaces.** The exit-bar question ("why is ORD-000012 on
F001-RES002?") returns a **testimony** answer that cites the
alternatives' PRICES directly from the reconstructed-assignment
Decision already in the evidence store — "Alternative: F001-RES001
— Same cost." and "Alternative: F001-RES002 — Would cost −20.08
more." — and the two cited bars + three lanes light up. No new
answer path was added, no LLM given new reach. **Observed
pre-existing renderer quirk (reported, not fixed):** the template
renderer phrases a cheaper alternative as "Would cost −20.08 more."
(negative-more), awkward but truthful — the differential IS cited;
the wording is a `renderers.py` matter for a future prose pass, out
of scope for interim-A's honesty-armor rule (don't add/alter answer
paths for the demo).

## Amendment — 2026-07-11: Session 3.1b CU5 — screenshot harness promoted to `tests/`

The candidate-agnostic Playwright harness moved from the throwaway
spike into production test infra at **`tests/cockpit/`** (its own
npm package — `@playwright/test` pinned `1.61.1`; the cockpit app
deps stay in `src/cockpit`). It is **hermetic**: a captured
`multi_route` fixture (`tools/build_cockpit_fixture.py` →
`tests/cockpit/fixtures/{schedule,meta,asks}.json`, committed,
deterministic seed 7 / solver seed 42) is served by a tiny
`fixture-server.mjs` that stands in for the live API with the exact
envelopes — so CI renders the real cockpit and runs the
ask/highlight flow **with no Python solver in the browser test**.
`playwright.config.mjs` builds the cockpit + serves it, headless in
CI.

Six scripted states, each screenshotted, each with machine-checked
assertions (the 3.0b evidence-grade discipline — numbers, not
golden-image pixel diffs, so cross-platform font rendering can't
flake it):
- **load** — 6 lanes, bars, planner vocabulary on screen, top-strip
  grade `ACCEPTED`.
- **select** — a clicked bar scopes the deictic ask (shared
  selection).
- **ask+highlight** (the acceptance frame) — the answer names an
  alternative resource and PRICES it (`/Would cost [+-]?\$?\d/` +
  "Same cost"); ≥2 cited bars glow, ≥2 lanes tint; register =
  testimony.
- **C1 drift — the standing regression** — overlay tag centre-x vs
  the **vis-rendered** bar centre-x, both measured independently
  from the DOM, `≤ 1.0px` at default zoom AND a hard zoom-in;
  culling of off-window cited bars is respected (only on-screen tags
  asserted, ≥1 required). Measured drift is **1.0px** (a systematic
  sub-pixel of DOM re-measurement — honestly not the spike's literal
  0.0px, which was measured against *computed* geometry, not the
  rendered DOM; the guard's teeth are proven — an earlier
  tag↔bar mismatch bug read 183.6px). A vis-timeline version bump
  that broke item geometry trips this test, not the demo.
- **mid-pan frame** — the 3.0b residual (it had verified settled
  zoom levels, not a mid-flight frame): drift holds `≤ 1.0px`
  DURING an un-settled pan.
- **registers** — testimony and judgment answers carry different
  left-border colors (never blend).

Result: **6/6 green** headless. The live acceptance moment was ALSO
driven end-to-end against the real API (not cited from the fixture)
— live `multi_route` solve → cockpit over the Vite proxy → auto-ask
→ priced answer + 2 cited bars + 3 lanes + `ACCEPTED / C1` strip,
0 page errors — the first frame of the sixty-second script.

**Carry-forwards (interim-B / design-thread, named not lost):**
(1) the contract-1.2 **split-endpoint** `GET /schedules/{id}/interaction`
(the +35.7% Tier-0 payload) is still proposed-not-built — lands with
the drag surface that consumes it (interim-B); (2) **no drag
handlers** — Tier-0/1/2 (R-DP1–R-DP7) are interim-B; (3) the
board's overlay reads vis DOM geometry (`itemSet.items[id].dom.box`)
— the same stable-public-ish surface disclosed in 3.0b, now with the
CU5 drift test guarding it; (4) the parked **pool-diversity design
question** from 3.1 — ghost realism under *distinct* rates (the
saturated identical-rate pair is what surfaces cross-machine ghosts;
a distinct-rate optimum is machine-unique) — remains
**design-thread-owned**, not attempted here; (5) the `renderers.py`
"−N more" prose quirk (above).

## Amendment — 2026-07-12: R-T1 — Tier-1 ghost sources, sandbox
time-boxing, and interaction-payload delivery (interim-B design
session)

Resolved in the Phase 3 design thread. Context: the 3.1 multi_route
finding — under realistic distinct rates the near-optimal pool
converges on machine placement, so pool-only ghosts degrade
precisely on economically realistic data.

**R-T1a — Two ghost sources, unified rendering, honest labels.**
Tier-1 ghosts come from (1) POOL members (near-optimal placements,
the cheap options) and (2) FORCED-ALTERNATIVE solves: for selected
ops, targeted re-solves each carrying a "not on the incumbent
machine" cut, warm-started, short time limit — yielding the TRUE
best price of each road not taken. An infeasible forced solve is
information: the ghost renders as a proven "not feasible this
horizon" verdict. Planner-visible result: every eligible machine
for a grabbed op wears a price or a verdict. Epistemics per R-DP6
hold — both sources are vouched for by complete solved schedules;
they deliberately sample different regions. Demo language: "priced
alternatives," not "near-optimal alternatives."

**R-T1b — Lifecycle.** Forced-alternative solves run async
post-publish (never at grab time), per likely-grabbed op
(initial heuristic: late demands and their critical-path ops),
stored as pool-member-class documents, invalidated on supersede —
the pool's exact lifecycle. Coverage misses degrade gracefully:
no ghost, Tier-0 green remains. Scale note (named, not hidden):
this multiplies pool-build solve count and inherits the pool's
slice-awareness qualification, now heavier; the per-slice answer
remains pilot-gated. Strategic note: the forced-alternative
service is the ATP fast-targeted-re-solve muscle built early.

**R-T1c — Sandbox time-boxing (elaborates R-DP2).** The Tier-2
sandbox re-solve runs under a hard, visible budget (design token;
initial 15s). Three honest outcomes, never an unbounded spinner:
(1) verdict within budget → delta card as designed; (2) feasible
incumbent, bound unproven → card ships flagged ("≈ delta, bound
not proven" — SOLVER_NONOPTIMAL surfacing in the UI); (3) nothing
within budget → R-DP2 return-home with "couldn't verify this
placement in time." The board is never blocked during the wait.
Drops ONTO a ghost may render their card from the vouching
schedule near-instantly (no fresh solve required for the
placement itself). CI acceptance: a pinned re-solve on the demo
fixture must return a verdict within budget — a standing latency
regression, so a heavy fixture fails a test before it fails a
demo.

**R-T1d — Interaction payload delivery.** Contract 1.2's
interaction block moves to a split endpoint
(GET /schedules/{id}/interaction), fetched on schedule load in
the background after first paint — never grab-triggered (a
network round-trip must not sit inside Tier-0's latency budget).
Stale-while-revalidate on schedule-version change. The board
renders read-only immediately; drag affordances enable when the
payload arrives.

## Amendment — 2026-07-12: Session 3.2a — interim-B part 1, the interaction data spine (CU1–CU4)

Everything interim B needs that is testable WITHOUT a cursor. No
drag handlers, no cockpit rendering changes beyond CU1's fetch
wiring — the interaction layer (grab/shade/ghosts/magnets/tuning
panel/change traces) is Session 3.2b. Per-unit below.

**CU1 — the split interaction endpoint (R-T1d).** Contract 1.2 →
**1.3**. `GET /schedules/{id}/interaction` now serves the Tier-0
interaction block; the main `GET /schedules/{id}` document drops
it (returns to its ~1.1 size). **Version ruling recorded honestly:
a MINOR bump, not major.** The document SCHEMA is unchanged —
`interaction` remains an optional field, always None on the main
endpoint; the assembler still builds it in-memory and a thin
`_persist_document` writes the main doc (interaction stripped) and
a sibling `interaction.json` the split endpoint serves. Justified
as minor because `interaction` was optional from 1.2 and
legitimately None for pool members / pre-1.2 docs, so any 1.2
consumer already handles None; the SOLE production consumer is the
cockpit, updated in the same session (no production consumer relied
on inline delivery). Pool members / edge-less callers write no
sibling file so `/interaction` 404s (degrade to Tier-0-green-only,
R-T1b/R-DP6). Cockpit fetch (`src/cockpit/src/interaction.js`):
background fetch after first paint via `wireInteraction`, never
grab-triggered; **stale-while-revalidate** cached per schedule id
(a new solve mints a new id = a new version); a stub
`dragEnabled`/`interactionReady` flag + a `data-drag-enabled` host
attribute enable on payload arrival (the gesture surface itself is
3.2b). Size: the main document is lean again;
`test_round_trip_rebuild_equals_served_document` compares the
served main doc against the interaction-stripped rebuild.
**Additive payload extension (a CU2-discovered gap):**
`OperationInteraction.resumable` (splittable so may span calendar
closures), a Tier-0 window-fit input, landed in the same 1.3 bump.

**CU2 — the Tier-0 legality library (client-side).**
`src/cockpit/legality/tier0.js` — PURE, framework-free (no DOM, no
vis, no fetch), so node tests import it directly. `buildContext(doc,
interaction)` + `computeTier0(opRef, ctx)` compute, for one op:
eligible resource ROWS (capability), LEGAL START REGIONS per
eligible row (open calendar windows [regular union overtime]
intersected with the precedence/release floor and window-fit for
the remaining duration), and the semantic ANCHOR set (calendar
openings, adjacency edges, predecessor finishes, release floor,
ghosts pass-through). Output serves both 3.2b's shading/magnets and
the harness; occupancy is reported but NOT subtracted from legality
(a fit-but-displace is amber, still legal). **Conservative-error
direction asserted (R-DP6):** the four dim dimensions are all
subtractive, so the library may under-offer green but never greens a
proven-illegal spot — `isLegalStart` returns false for capability,
closed-calendar, precedence-floor, and window-fit. Resumable
window-fit handled via `latestStartForRemaining` (a resumable op may
pause across closures but still needs at least its duration in
cumulative open capacity ahead of its start). Tested
(`tests/cockpit/legality.spec.mjs`, hand-verified zones + the
multi_route fixture): one case each of capability / closed-calendar /
precedence-floor / resumable-window-fit dim, plus the
conservative-error invariant on real data. **Finding, extended not
failed:** the interaction payload lacked a resumability flag Tier-0
needs for window-fit — reported and added additively (CU1's
`resumable`).

**CU3 — the forced-alternative service (R-T1a/b).**
`src/mre/modules/forced_alternatives.py` — for selected ops, one
warm-started re-solve each carrying a "not on the incumbent machine"
cut (`solver_builder.add_forced_alternative_cut`), short time
limit, NO objective bound (the true best price of the road not
taken). Results are pool-member-class documents
(`annotations.pool.source="forced_alternative"` plus the moved op /
forbidden machine / landing machine), stored in the SAME registry
pool tables (new `pools.kind='alternatives'`, `pool_members.source /
verdict / label_json`, nullable `document_path`) — same
never-in-schedule-listings exclusion, same supersede invalidation.
An infeasible forced solve is FIRST-CLASS: a
`verdict="infeasible_this_horizon"` member with no document ("not
feasible this horizon" is a renderable answer, R-T1a). API additive:
`POST/GET /schedules/{id}/alternatives` (plus `/{member}`),
distinguishable by source label. **Selection heuristic v1
(`select_target_ops`, it WILL evolve):** the at-risk demands — late
first, then tightest by slack — and their MULTI-ELIGIBLE ops (only
a multi-eligible op can move off its machine); a budget caps the
count (R-T1b: forced solves multiply the pool-build solve count and
inherit its slice-awareness qualification, now heavier). **The
price-bought-something counterfactual** needed the DISTINCT-rate
case R-T1 names: new generator scenario `multi_route_distinct`
(distinct rates + light load, so the optimum concentrates on the
cheapest machine and the pool CONVERGES on machine placement). On
it both halves assert (`tests/test_forced_alternatives.py`,
deterministic): the plain pool crosses machines ~0 times (the
pool-only ghost degradation R-T1 names), while the forced service
yields at least one feasible cross-machine alternative at a positive
price — strictly MORE than the pool. The saturated `multi_route`'s
`expected_pool_cross_machine_ops_ge` stays 1 (unchanged).

**CU4 — the sandbox latency budget (R-T1c).**
`src/mre/modules/sandbox.py`. `classify_sandbox_outcome(status,
wall, budget)` — the pure three-outcome classifier, unit-tested
without a solve (budget-exhausted paths SIMULATED, never waited):
OPTIMAL/INFEASIBLE gives **verdict** (1); FEASIBLE gives
**feasible_unproven** (2, flagged "≈ delta, bound not proven"); else
gives **no_verdict** (3, return home). The budget is a **design
token** (`SANDBOX_BUDGET_S = 15.0`), not a constant — the outcome is
a function of the PROOF, so the same status classifies the same at
any budget; `within_budget` allows a 1s stop-overhead margin (a
solve given time_limit=budget stops a hair over it).
`sandbox_pin_resolve` warm-starts, pins one op at (machine + time as
displayed, R-DP1), re-solves under budget, classifies. **CI
acceptance:** a single-pin re-solve on the demo fixture returns a
verdict within budget — asserted on `multi_route_distinct` (a
non-degenerate optimum proves fast). **CU4 FINDING (honest, not
hidden):** the SATURATED `multi_route` fixture is degenerate BY
DESIGN (the identical-rate R0/R1 pair — the very thing that surfaces
pool cross-machine ghosts), so a pinned re-solve there finds the
incumbent-cost placement (delta 0) but cannot PROVE optimality
inside 15s and returns outcome (2), a shippable FLAGGED card, WITHIN
budget (never a hang). That is exactly the honest second outcome
R-T1c designs for; the verdict regression therefore uses the
distinct fixture, and the degeneracy is asserted, not papered over.

**Harness readiness-wait (3.1c 0-bars flake).** `cockpit.spec.mjs`
`boot()` now waits for at least one painted `.vis-item.bar` after
`window.__cockpit.ready` — the vis item DOM can lag ready by a
frame; one retry-until-bars guard, cheap insurance.

**Carry-forwards (named, not lost).** (a) The pool/forced-alternative
**slice-awareness qualification** is now heavier (forced solves
multiply solve count) and remains pilot-gated (R-T1b). (b) The
cockpit fetch wiring lands a **stub** drag flag only — the gesture
surface (grab/shade via the CU2 library, Tier-1 ghost rendering from
the CU3 alternatives, magnets/tuning panel, Tier-2 drop + change
traces per R-DP7) is Session 3.2b. (c) The forced-alternative
**selection heuristic is v1** (at-risk demands' multi-eligible ops)
and will evolve as the pilot data teaches. Tests: **1022 non-slow
green** (+23) plus the new slow ladder (forced counterfactual,
sandbox latency, multi_route unchanged); the cockpit JS suite is
**12/12** (7 board + 5 legality).

## Amendment — 2026-07-12: Session 3.2b — interim-B part 2, the gesture surface (CU1–CU6)

The interaction layer itself — grab → shade → ghosts → magnet-snap
drag → drop-or-refuse → tentative → sandbox verdict → delta card →
change traces → DISCARD. Rendered against the DISTINCT-rate fixture
(`multi_route_distinct`) as primary, so the priced ghosts are the
forced-alternative service's (R-T1), not the saturated pool's. Voice
and Tier-2 accept/publish stay out (later / final). Per-unit below.

**Data spine (backend, all hermetic-testable).** Three additive
backend changes the surface needs, none touching a record shape.
(1) `sandbox.py`: `SandboxResult` now carries the **moved-set**
(R-DP7) — `_moved_set` diffs the pinned re-solve's placements against
the incumbent, emitting old→new (resource + start) per displaced op,
the pinned op flagged and listed first (so the delta card leads with
what the planner touched); warm-starting keeps the set minimal by
construction, which is what makes tracing it tractable. Plus
`delta_abs` and an echoed `pin`. (2) API `POST /schedules/{id}/sandbox`
— the Tier-2 pinned re-solve (R-DP1/R-T1c), synchronous under the
budget token, returns the classified outcome + moves; scenarios 409,
unknown 404. (3) `forced_alternatives.py`: each priced member carries
a compact `alternative_placement` (resource + start + end), extracted
from the member's own solved document — the Tier-1 ghost bar the
cockpit renders WITHOUT a full-document fetch (CU2); surfaced through
the `/alternatives` member label. Fixture builder rebuilt to produce
BOTH the read-only `multi_route` set (unchanged) AND a
`fixtures/distinct/` gesture set: schedule/interaction/meta +
`alternatives.json` (4 priced cross-machine ghosts) + `sandbox.json`
(canned verdict/flagged/no_verdict by pinned op — one REAL verdict
from a real pin, the other two honest outcomes synthesized, since the
classifier itself is unit-tested in Python).

**CU1 — grab → Tier-0 shading (`drag/shade.js`, R-DP2/R-DP6).** On
grab, every resource row is painted from the grabbed op's
`computeTier0` result: green legal-start regions, amber occupancy
(fit-but-displace, still legal), a dim wash where eligible-but-illegal,
a stronger capability-dim wash on wrong-machine rows. Green =
provably-not-illegal by the cheap rules, dim = proven illegal — the
library's epistemics, only painted here. Hover-over-dim shows the
one-line reason (capability / precedence / calendar-or-window-fit),
resolved via `isLegalStart`. Standing latency regression: grab→shade
measured in the harness, asserted **< 100 ms** (the 3.0b bake-off
bar) — the Tier-0 payload is prefetched (R-T1d), so grab touches no
network.

**CU2 — ghosts (`drag/ghosts.js`, R-T1a).** The forced-alternative
(and, when present, pool) placements for the grabbed op, rendered
UNIFIED and source-distinguished only subtly (border style: solid
teal = forced/priced road, dashed grey = pool/cheap option), each
wearing its signed price (`+0.30%`, or "same cost" for a free move)
or its "not feasible this horizon" verdict. Labels ride an overlay
that tracks pan/zoom and stays legible at every zoom — the C1 drift
discipline extended to ghost labels (`ghostDriftProbe`, ≤ 1 px).
Ghosts are the only pre-release known-feasible targets (R-DP6), so
they are also the strongest magnet and the near-instant drop path.

**CU3 — drag physics (`drag/magnets.js`, pure; controller wiring,
R-DP1/R-DP3).** Semantic snap from the anchor set: ghosts strongest,
then calendar openings, adjacency edges, the predecessor/release
floor, coarse grid only as the open-space fallback — priority-ordered,
radii as feel tokens converted px→minutes at the current zoom so a
token means the same on-screen distance at any zoom. Snap resolves
DURING the drag (the bar clicks to the anchor before release,
preserving R-DP1 literalness). Alt disables snapping. Dim zones refuse
mid-drag: the carry is boundary-pinned at the nearest legal edge (the
3.0b-proven behavior), the overlay wears `not-allowed`, and the reason
shows; release over dim returns the bar home animated, never
teleporting (R-DP7a). The one thing the planner touched is the one
thing that cannot silently move.

**CU4 — drop → tentative → verdict (`drag/controller.js` +
`drag/sandboxui.js`, R-DP2/R-T1c).** A legal drop lands a hatched,
pulsing tentative bar and opens the delta card in one of the three
honest states, never an unbounded spinner: (1) VERDICT — the delta
card, headline cost delta + the moved-set as line items; (2) FLAGGED
— "≈ delta, bound not proven" (SOLVER_NONOPTIMAL surfaced); (3)
RETURN-HOME — "couldn't verify this placement in time", the bar goes
home, no line items. A visible countdown paces the budget token while
`POST /sandbox` runs; the board is never blocked. Drop ONTO a ghost
renders its card near-instantly from the vouching schedule (no fresh
solve) — its price is already proven; the dropped bar's own old→new is
the shown move (deeper consequence traces from the ghost's document
are a carry-forward). Accept is STUBBED DISABLED with a tooltip naming
why — the publish workflow isn't built, and a dead-end accept would
violate R-DP7's no-silent-change law. Discard is the only commit verb
this session.

**CU5 — change traces (`drag/traces.js`, R-DP7).** The moved-set is
drawn on the board: a faint ghost-of-old bar at each displaced op's
former placement + a motion line (with arrowhead) to its new one,
held until discard. The delta card's line items ARE these traces
(R-DP7c): each carries the same `data-op`, so clicking a card line
selects the bar and pulses its trace. Discard restores everything
(overlays cleared, tentative removed, card hidden, phase idle),
animated.

**CU6 — the tuning panel (`drag/tuning.js`, DEV-BUILD-ONLY).** Every
numeric feel token (snap radii, magnet falloff, ghost opacity,
tentative pulse, trace styling, sandbox budget) exposed as a live
control that hot-reloads the surface on change (mutates the one
`feel` object the controller reads, mirrors the CSS-visible subset
onto `:root`, re-`redraw`s), plus export-to-tokens (console + JSON
download). Mounted only under `import.meta.env.DEV`, so it never ships
in the production build the harness serves — it cannot leak feel knobs
into the planner's cockpit. This is the instrument for the feel
iteration: Daryn plays it, prompts don't.

**Feel-token architecture.** The numeric interaction-feel knobs live
in `drag/feel.js` (`DEFAULT_FEEL`, `makeFeel`, `applyFeel`) — the
tuning panel's single source; the CSS-visible subset (opacities,
pulse period, trace width) is mirrored onto `:root` custom properties
so `drag.css` and JS never disagree. Purely visual tokens (shade
greens/ambers, ghost edges, tentative hatch, reason colors) stay in
`tokens.css`. Nothing outside these two files hard-codes a color or a
feel number.

**Tests.** `tests/cockpit/gesture.spec.mjs` — 11 screenshot-asserted
states (grab-shade, refusal, ghosts, magnet-snap, Alt-disable, ghost-
drop verdict + traces, /sandbox verdict, flagged, return-home, discard
restore, card-line navigation) against the distinct fixture, driven
through the programmatic `window.__cockpit.drag` hooks (the same
transitions the pointer handlers call). The full cockpit JS suite is
**23/23** (7 board + 5 legality + 11 gesture). The gesture controller
stands up on the read-only `multi_route` fixture too (no ghosts →
green-only) without disturbing the interim-A regressions. Python
**1026 passed** (+4 sandbox API), plus the slow ladder (the sandbox
latency regression on the distinct fixture is the drop→verdict
authority — the canned harness path is near-instant by construction).

**Carry-forwards (named, not lost).** (a) The accept/publish path is
STUBBED (final session) — accept is disabled by design until the
publish workflow exists, so no gesture can mutate canonical state yet.
(b) Voice (a later interim). (c) Pool/forced slice-awareness remains
pilot-gated (R-T1b), now heavier. (d) Drop-onto-ghost shows the
dropped bar's own trace only; the ghost's deeper consequence set would
come from its stored document (a fetch we deliberately avoided for the
near-instant path). (e) Each forced-alternative gives ONE ghost per op
(one cut per op); multiple ghosts per op await forbidding each machine
in turn. (f) Whatever the feel iteration discovers once Daryn's hands
are on the tuning panel — the tokens are provisional by design.

## Amendment — 2026-07-14: Session 3.2c — the drag/pan conflict fix (unblocking feel iteration)

**The bug, observed live on `busy_board`.** While dragging a bar,
horizontal mouse movement panned the whole timeline instead of (or in
addition to) moving the bar — the board slid out from under the cursor.
The gesture surface was built on the premise that the board is still
during a drag; it was not.

**Root cause.** vis-timeline owns a built-in Hammer pan/zoom on the
center container (`Range._onDragStart`/`_onDrag`, bound to
`panstart`/`panmove` in the vendored `vis-timeline-graph2d.js`). That
pan lives entirely in vis's own input pipeline — the controller's
`onPointerMove` calling `preventDefault()` does nothing to it. So a
horizontal drag fed BOTH the controller's bar-carry AND vis's window
pan simultaneously. This was latent through all of 3.2b because the
harness drives the phase machine through the programmatic
`window.__cockpit.drag` hooks, which never emit Hammer events — the
conflict only exists on the real pointer path, which no test exercised.

**The fix (options, not Hammer surgery).** Read the vendored Range
source first: `_onDragStart` (guard at the top) AND `_onDrag`
(re-checked on EVERY panmove) both bail early on `!this.options.moveable`.
So toggling the option mid-gesture reliably halts the window — no need
to reach into Hammer or detach recognizers. `board.js` gains
`setPanZoom(enabled)` (`timeline.setOptions({moveable, zoomable})` +
a tracked flag) and `isPanZoomEnabled()`. `drag/controller.js`
suppresses on `onPointerDown` OVER A BAR — before any movement can
start a Hammer pan, so the board is still from the first pixel — and
restores on `onPointerUp`. Suppression is bound to the PHYSICAL pointer
gesture (down→up), not the phase machine: pan resumes the instant the
bar is released, so the tentative/verdict phase is freely pannable to
inspect traces (the overlay tracks pan via `redraw()` as always). The
programmatic harness path never panned and is deliberately left
unsuppressed. vis tap-selection is unaffected (a plain click suppresses
on down, restores on up, and `selectable` is untouched), confirmed by
the interim-A select regression still green.

**Verified.** New `gesture.spec.mjs` test — the ONLY one driven by
REAL pointer events (`page.mouse.down/move/up`) against the real built
cockpit + real vis-timeline, the one path that exercises the Hammer
pan: a horizontal bar-drag leaves the timeline window bit-for-bit
unchanged mid-drag and after drop, while the phase confirms a grab
happened; `isPanZoomEnabled()` is false during and true after.
**Negative control run before trusting it:** with the real
`setOptions` call stubbed to a no-op, the test failed exactly on the
mid-drag assertion (window jumped a full day) — the test bites. Full
cockpit JS suite **24/24** (7 board + 5 legality + **12** gesture, up
from 11). Python untouched (frontend-only). **Shading-lifecycle check
(asked for in the same session):** confirmed already correct — `redraw()`
early-returns on `idle` and every idle-entry path (`returnHome`,
`discard`, `cancelSilently`) runs `clearOverlays()` in the same
synchronous block, so no wash survives to an idle board; added standing
`.shade-row === 0` assertions to the return-home and discard tests as a
regression pin. No fix needed there. Live `busy_board` confirmation is
the user's hands-on eyeball (the fixture exists for exactly that); the
real-pointer harness test + negative control are the machine-checked
proof.

### 2026-07-14 — Session 3.2d: feel-session fixes (six items from a live `busy_board` session)

Six items observed by Daryn with his hands on the gesture surface. All
frontend except CU4 (a Python renderer wording fix) and CU6 (an
investigation that confirmed a config-only wiring). Screenshots existed
for the shading-persist (CU1) and shading-noise (CU5) items.

**CU1 — Tier-0 shading must clear on drop (bug, fixed).** After a legal
drop the grab-phase green/amber/dim wash persisted into the tentative
phase alongside the tentative bar + card. 3.2c had verified clearing on
every *idle-entry* path (return-home / discard / cancel) and added
regression pins there — but the **drop→tentative transition** is not an
idle entry, and it was the missed seam. Per design the drop answers the
"where can it go" question, so on that transition the legality overlays
(shade + ghosts + the refusal reason) retire, leaving only tentative bar
+ traces + delta card. Fix in `drag/controller.js`: a new
`clearLegalityOverlays()` (clears shade/ghosts/labels + `S.drawnGhosts`,
drops the `refusing` class) called on entering tentative in BOTH drop
paths (the sandbox re-solve and the near-instant drop-onto-ghost); and
`redraw()` now only repaints shade/ghosts while `phase ∈ {grabbed,
dragging}` so a pan/zoom during tentative/verdict can't bring the wash
back. New `gesture.spec.mjs` test drives a canned-VERDICT drop WITHOUT
awaiting the sandbox promise to observe the tentative phase in flight:
`shade-row === 0` and `ghost-bar === 0` at the drop instant AND through
the verdict, tentative bar still present, then Discard restores a clean
idle board. (The existing return-home/discard shade pins from 3.2c stay.)

**CU2 — Accept must READ as disabled (feel/honesty).** It was already
`disabled` and inert on click, but styled like a live control. Now
visibly inert: `drag.css` `.dc-accept` dimmed (`opacity: .5`) with
`cursor: not-allowed` and no hover affordance; tooltip reworded from the
dev-facing R-DP7 note to the planner-facing "Publish workflow arrives in
the next build." A dead control that looks alive violates the
no-silent-anything spirit of R-DP7.

**CU3 — deictic injection (fixed at the UI seam).** The
"Why is this here?" deictic must compile the RESOLVED planner-vocabulary
question from the live selection *before* `/ask` — never a literal "this",
never a canonical id. `askpanel.js` already composed
`why is <wo> on <resource_name>?`, but two seams were hardened: (a) the
scope's `(op)` fallback that could show a *selected-but-unresolvable*
bar with an enabled-but-dead button is gone — an order-less selection
now keeps the button disabled with a hint (`.scope-hint` "click a bar to
ask why it's placed there"), the honest state; (b) `board.select()`
(programmatic selection, used by delta-card navigation and the harness)
now fires the shared-selection callback — vis emits `select` only on user
interaction, so a programmatic select previously left the ask panel's
scope silently stale. The router is UNTOUCHED: its refusal of an
unresolvable "this" was correct; it only ever sees fully-resolved
external refs. New `cockpit.spec.mjs` test: no selection → button
disabled + hint; select ORD-000012/F001-RES001 → scope populated, button
enabled, click → the exact resolved question `why is ORD-000012 on
F001-RES001?` was sent and a non-fallback testimony answer rendered.

**CU4 — fallback menu speaks planner, not developer (wording only).**
The unsupported-question menu listed `WO-XXXX / M-YYYY / snap-a vs
snap-b` id-shapes. `explainer.py` `_SUPPORTED_ROUTES` reworded into
planner language ("why is an order late", "what's running on a machine",
"schedule for a customer", "what changed between two schedule versions"),
and a new `_planner_routes()` leads the menu with CONCRETE examples drawn
from the loaded schedule's real external refs where cheap (a deterministic
`min()` pick of the identity map's order + machine names), falling back to
the generic planner list. Router capabilities unchanged; the
`supported_routes` key and the renderer header are unchanged, so the
explainer tests hold (129 green).

**CU5 — shading emphasis controls (feel; tokens first).** On busy boards
most rows are legitimately green, so the wash reads as noise. Added two
feel knobs — `shade.green_opacity` and `shade.dim_opacity` — mirrored to
`:root` by `applyFeel()`, exposed as tuning-panel sliders, and applied in
`drag.css` as separate `opacity` multipliers on the green legal segments
vs the dim/capability washes. Defaults deliberately let dim + ghosts
dominate over green (green damped to 0.5, dim at full 1.0). No
rendering-philosophy change yet — the inversion decision (emphasize
forbidden over legal) waits on Daryn's verdict with the knobs in hand.

**CU6 — LLM renderer wiring (investigated, wired for dev — it was
config-only).** The M10 `LLMRenderer` + testimony validator path was
already fully built and reachable from `POST /schedules/{id}/ask`
(`use_llm = req.llm and bool(ANTHROPIC_API_KEY)`), and fails closed three
ways: no key / no `anthropic` package → template with a note; prose that
fails post-render validation (timestamps / durations / machine names
against the evidence bundle), even after one regeneration → deterministic
template with a `[LLM validation failed … fell back to template]` stamp.
So the only gap was the client never asking for it. Wired: `api.js`
`ask()` sends the `llm` flag; `main.js` sets it true only in the dev
build (`import.meta.env.DEV`) so the production `vite build` the harness
serves always renders templates; documented in the cockpit README
(key via the API server's environment, never committed — gitleaks scans
for it). No new answer path, no new LLM reach; template render remains
the default and the fail-closed floor.

**Result.** Cockpit JS **26/26** (7 board + 5 legality + 14 gesture; the
board suite gains the CU3 deictic test, the gesture suite the CU1
shade-clear test). Python explainer suite **129 green** (CU4 wording).
Committed on master. (Pre-existing, untouched: the
`test_certificate_conversation.py[busy_board]` parametrization KeyErrors
on `expected_certificate_grade` — `busy_board` is a feel fixture with a
`feel_fixture.json` marker, not a truth manifest; fails identically on
3.2c HEAD, flagged for a later test-guard.)

### 2026-07-14 — Session 3.3: Tier-1 coverage + card explainability (feel-session findings)

Five findings from a live `busy_board` run (schedule `769223cf`, Daryn's
hands on the gesture surface) drove this session. All are about the Tier-1
promise failing QUIETLY or INCOMPLETELY, not the mechanics — the mechanics
(R-T1a/b/c, R-DP7) held; the gaps were coverage and legibility.

**CU1 — coverage: widen the precomputed batch + add an on-demand path.**
The precomputed forced-alternative batch priced 8 targets on a board of
hundreds of ops; a random grab (a not-late, not-covered op) showed ZERO
ghosts — the Tier-1 promise failing silently. Two fixes, both in
`forced_alternatives.py`, both R-T1a-faithful:

  * *Widen the heuristic* (`select_target_ops`, now v2, three phases,
    budget-capped): **(A)** late demands' multi-eligible ops, **(B)** the
    top-N most-EXPENSIVE multi-eligible ops overall (config token
    `DEFAULT_TOP_N_EXPENSIVE = 6` — where a cross-machine move is likeliest
    to buy something, late or not), **(C)** the remaining at-risk demands by
    slack (the old catch-all, so a no-late-demand board still gets coverage).
    Phase B needs a cost key; the Assignment entity carries none, so
    `_incumbent_costs` DERIVES it (working-minutes × the incumbent machine's
    rate) — a RANKING key only, never surfaced as a priced number. Without a
    cost key the heuristic degrades to A+C (the pre-widening behavior), which
    keeps the existing selection test green.
  * *On-demand pricing* (`build_op_alternatives` + `POST
    /schedules/{id}/alternatives/op/{op_id}`): grabbing an uncovered op fires
    its forced solves RIGHT THEN. Honoring R-T1a's original language ("every
    eligible machine wears a price or a verdict"), it prices EVERY eligible
    machine — `add_required_resource_cut` pins the op to each machine in turn
    (`op_assign[op][machine] == 1`), not the single "forbid incumbent" cut the
    solver's cheapest-escape would take (K'). Results APPEND to the same
    alternatives pool (`Registry.append_pool_members`, globally-unique indices,
    member docs under `alternatives/op_<op8>/`), so the second grab is instant.
    The solve bill is guarded two ways: a per-op machine cap
    (`DEFAULT_ONDEMAND_MAX_MACHINES = 4`) + per-solve time limit
    (`DEFAULT_ONDEMAND_TIME_LIMIT_S = 6.0`), and a process-wide concurrency cap
    + in-flight dedup in the API (`MAX_CONCURRENT_ONDEMAND = 2`,
    `_ONDEMAND_SEMAPHORE`, `_ONDEMAND_INFLIGHT`) so a burst of grabs can't fan
    out into an unbounded fleet. The refactor extracted a shared
    `_load_alt_context` + `_solve_alternative` (forbid | require modes) so the
    precomputed and on-demand builds share one per-member solve.
    **Cockpit (`controller.js`):** on grab of a multi-eligible op with no
    ghosts, `maybePriceOnDemand` fires the POST behind a "pricing
    alternatives…" shimmer (`.drag-pricing`) — absence is NEVER silent — polls
    `/alternatives`, and fades the priced ghosts in (or shows "no cheaper
    alternative found"). **Measured on the small distinct fixture: one
    on-demand pricing of an uncovered multi-eligible op = a single eligible
    machine, priced sub-2s wall.** (The `busy_board` cost-center number the
    brief asked for is bounded BY DESIGN now, not measured raw: max_machines ×
    per-solve-limit = 4 × 6s worst case, throttled to 2 concurrent.)

**CU2 — planner vocabulary in alternatives (the empty-`work_orders` bug).**
`alternative_placement.work_orders` was always `[]` because the extractor's
assignment dict carries no order names. `_placement_of` now resolves them from
the workpackage→order map (the same identity-map + fulfillments source the
schedule assembler uses, threaded through `_load_alt_context.wp_orders`), so
ghost placements and API alternative documents speak external refs end to end.
The cockpit ghost bar wears its work order in its `title` (`ghosts.js`, CU2).

**CU3 — the delta card "why" line.** A card that said "+9818 min" never said
WHY. `sandbox._annotate_move_reasons` reads the story off the re-solve's own
placements (the same occupancy arithmetic the reconstruction already knows):
for each MAJOR forward-shifted move (threshold token `MAJOR_MOVE_THRESHOLD_MIN
= 60`), whatever holds its new machine right up to its start — the dropped op
(`displaced_by_drop`) or another op (`occupancy`, naming machine + until-time).
The reason is STRUCTURED (resource ids), rendered in planner vocabulary by the
card (`sandboxui.js` `_reasonClause` → "blocked on <machine> until <time>").
Conservative: a non-contiguous blocker (gap > threshold) earns NO clause — the
card never fabricates a why. No new answer path; the derivation is unit-tested
without a solve (`test_sandbox.TestMoveReasons`).

**CU4 — ghost-drop full consequences.** Drop-onto-ghost priced the dropped bar
but traced only IT; the ghost's deeper consequences needed its document.
`dropOnGhost` now lazy-fetches the ghost's member document
(`GET /alternatives/{member_index}`), diffs it against the incumbent
(`movedSetFromDoc`), and re-renders the FULL moved-set — "consequences
loading…" on the card until it lands (R-DP7: never silence). The member index
rides the ghost descriptor (`ghosts.js` CU2/CU4); a failed/absent fetch keeps
the single-bar trace (never a lie). Harness: the served member doc displaces 9
of 10 ops → the card's traces go from 1 to 9.

**CU5 — small guards.** (a) `test_certificate_conversation` and
`test_ids_end_to_end` now EXCLUDE feel fixtures explicitly (`not
SCENARIOS[s].get("feel")` + a defensive in-body skip) — the `busy_board`
KeyError/grade reds carried since 3.2d are retired (the fixtures carry a
`feel_fixture.json` marker, no truth manifest). (b) `SandboxResult` gains
`applied_time_limit_s` (= the budget handed to the solver) so budget-vs-actual
is inspectable straight from the payload — the "was 60s the limit or the wall
time?" question from the session answers itself next time.

**Result.** Backend: `forced_alternatives.py` (widen + on-demand + shared
solve + work_orders), `sandbox.py` (reasons + applied limit), `solver_builder`
(`add_required_resource_cut`), API (`/alternatives/op/{op}` + concurrency
guards + `Registry.append_pool_members`). Cockpit: on-demand grab flow +
shimmer, ghost work-order titles + member index, ghost-drop full consequences,
card "why" clause. Distinct fixture rebuilt (work_orders populated, member docs
+ on-demand fixture written); fixture server serves member docs + replays
on-demand priming. **Cockpit JS 30/30** (7 board + 5 legality + **18**
gesture); **Python: non-slow green** (+ new slow on-demand + reason tests).
**Carry-forwards (named):** on-demand pool/forced slice-awareness (still
pilot-gated); the `busy_board` raw cost-center wall time (bounded by design, not
measured at scale this session — a Phase-4 profiling item); ghost-drop
consequences for POOL ghosts (no document → single-bar trace, unchanged);
accept/publish (final session) and voice (later interim). (Pre-existing,
untouched: `test_defaults_reproduce_baseline`, `test_planner_merge_v2`, and
three `test_scenario` warm-start/merge tests fail on THIS machine's HEAD too —
ortools 9.15 vs the golden baseline + CP-SAT noise — unrelated to this session.)

## Amendment — 2026-07-15: Session 3.3b — ortools "drift" was a wall-clock time-bomb (baselines STAND; solver pinned)

**The prompt's premise, tested and overturned.** Ten regression tests
(`test_defaults_reproduce_baseline` ×2, `test_planner_merge_v2::TestWO2001
RejectedOnRisk` ×2, four `test_scenario` warm-start/merge tests, and the two
slow scenario tests behind them) had been standing red on this machine's HEAD,
blamed across three prior amendments on "ortools 9.15 vs the golden baseline +
CP-SAT noise." That attribution is **wrong**, and this session proves it by
construction rather than asserting it.

**Establishing what changed (prompt item 1).** `pyproject` pinned
`ortools>=9.8` — an open upper bound. The installed build is **9.15.6755**,
which arrived by an *unpinned* `pip install`, not a deliberate adoption
(nothing in git chose it). An unpinned solver is an unpinned product, so it is
now pinned **exactly**: `ortools==9.15.6755`, guarded by
`tests/test_ortools_pin.py` (reads the pin out of `pyproject.toml` — single
source — and fails if the installed `ortools.__version__` differs; environment
drift is now a named test failure, not a mystery). This is the same discipline
the differ fix used: the environment is part of the baseline.

**The decision (prompt item 2): NEITHER pin-back NOR regenerate.** The prompt
framed a binary — (a) pin back if 9.15 bought nothing, or (b) adopt 9.15 and
regenerate every golden as a new baseline epoch. Both presuppose 9.15 changed
the output. **It did not.** Isolation test: a new `--reference-date` CLI flag
(see below) lets the sample_data pipeline be pinned to a fixed planning date.
Run under `--reference-date 2026-07-09/10/11`, `PYTHONHASHSEED=0
--solver-workers 1 --solver-seed 42`, ortools **9.15.6755 reproduces the
golden `sample_data_schedule.csv` byte-for-byte** and the cost ledger
value-for-value (24769.00). There is **zero ortools drift**. The goldens
STAND; no baseline epoch is invalidated; the pin moves forward to the
already-validated 9.15.6755 with no regeneration.

**The actual root cause: a fixed-date fixture read the wall clock.** The
sample_data path has no manifest `reference_date`, so `__main__` left it `None`
and the validator fell back to `datetime.now(UTC)` (validator.py:127). The
sample scenario is a *fixed narrative* — WO-2001 due 2026-07-13, WO-2002 due
2026-07-15, the $260-unbatch counterexample. The golden was captured as-of the
~2026-07-09 epoch, with both demands in-window and merged. Once the machine
clock passed **2026-07-13**, the validator began excluding WO-2001 as past-due
(validator.py:209, "due date before reference_date"), which:
  - removed the one late demand → the 840-min tardiness and its cost vanished
    (the "cheaper" 22009-vs-24769 read was the *smaller model*, never 9.15
    "finding a better solution" — a trap the session nearly fell into before
    checking the demand population);
  - dissolved the WO-2001/WO-2002 merge → `merge_by_family_v2`'s risk gate had
    nothing to reject, and the suppress-merge scenario diffed to a no-op
    (setup_delta 0.0).
Proof it is the clock and nothing else: pinning the validator to
`reference_date=2026-07-09` restores WO-2001, restores the two
`merge_rejected` decisions the v2 test asserts, and (the merge gate being
entirely pre-solve) never touches ortools. The 1024 other tests — including
real-solve regressions on fixed-date fixtures like `TestProfitableMergeAccepted`
— were green throughout, exactly the signature of a time-bomb localized to the
one wall-clock-dated fixture, not a solver regression.

**The fix (prompt item 3: full green + guard).**
  - **`--reference-date <ISO>` CLI flag** (`__main__`): highest priority over
    manifest/plant_config, and the missing knob for the sample-data path. Its
    help text names the failure mode ("without this the wall clock silently
    excludes past-due demands and the schedule rots"). This is the proper
    reproducibility fix, not a test-only patch.
  - **Regression tests pinned to the 2026-07-09 sample epoch.**
    `test_defaults_reproduce_baseline` passes `--reference-date 2026-07-09`;
    `test_planner_merge_v2` and `test_scenario` pass
    `reference_date=2026-07-09` to the validator. `test_scenario` additionally
    **records** the reference_date in its M3 run-context config and derives
    `base_context` via `derive_base_context(runs_dir)`, so the ScenarioRunner's
    re-validation inherits the same epoch (the runner reads reference_date off
    M3's config, not the clock — without this the base run pins but the
    scenario re-solve still excluded WO-2001).
  - **ortools pin + drift guard** as above.
  - **Full suite green at close: 1033 passed, 0 failed, 35 skipped** (non-slow;
    +1 vs the pre-session 1024 is the new pin guard) + the scenario/merge slow
    ladder. Zero standing reds.

**Baseline epochs, stated (prompt's fixture question).** Two distinct epochs,
neither disturbed by 9.15:
  - **sample_data regression baselines** (`tests/fixtures/baselines/
    sample_data_*`): epoch **2026-07-09**, now pinned explicitly. Goldens
    unchanged — byte-verified under 9.15.6755.
  - **gauntlet baselines** (`gauntlet_*`): epoch = `plant_config.json`
    reference_date (already fixed); time-stable; untouched (and skipped here —
    raw_data is gitignored).
  - **generator / cockpit / feel fixtures** (`multi_route`,
    `multi_route_distinct`, `busy_board`): epoch **2026-01-05**, the fixed
    `generate()` default (`ref_date = reference_date or date(2026,1,5)`), carried
    in each submission's manifest `reference_date` and used by the solve — so
    these were **never** wall-clock-dated and did **not** rot. Confirmed against
    the committed `tests/cockpit/fixtures/distinct/` (manifest reference_date
    `2026-01-05`, all dates in Jan 2026). Byte-reproducible under 9.15, so **no
    rebuild** — the "solved under the drifted env" worry is void once drift is
    disproven. They belong to the 2026-01-05 generator epoch and stay there.

**Lesson (do not lose).** A regression baseline that reads `datetime.now()`
is not a baseline — it is a countdown. The only wall-clock-dated fixture in the
repo was the one without a manifest reference_date; the fix is structural (pin
the epoch at the boundary, CLI flag + recorded config), and the correct reflex
when a "solver" regression appears is to check the *input population* before
blaming the solver. The prior three amendments' "ortools 9.15 + CP-SAT noise"
attribution is hereby corrected: it was neither the version nor CP-SAT
nondeterminism — it was the calendar.

## Amendment — 2026-07-15: Session 3.4 — the interim final (accept/publish, the answering edit, voice, latency, the sixty-second rehearsal)

The last build session of Phase 3. It ends with the sixty-second script running
end to end. Fresh session; production discipline throughout. Five commit-units +
three riders.

**CU1 — accept → Decision → publish (the headline).** Accept on the delta card
is REAL now. An accepted edit records a `planner_edit` Decision (new
decision_type, docs/02 §4.2; **basis=observed** — a human command, not a solver
reconstruction; **authority MANDATORY** — a dev identity token now, real auth
post-pilot; new optional `Decision.authority`, machine-authored decisions leave
it None) and mints a NEW proposed schedule version — **the base is never
mutated** (R-DP2's "nothing mutates before accept" becomes "accept CREATES,
never overwrites"). Publish is an explicit second act (proposed → published)
that supersedes the prior version and invalidates its pools/alternatives via the
existing supersede machinery. Backend: `modules/planner_edit.py`
(`apply_planner_edit`) derives a child snapshot copying every planned entity but
the M7 outputs (so the edit reproduces the base's planning EXACTLY, differing
only by the pin), warm-starts + pins the dropped op (machine+time as displayed,
R-DP1), re-solves under the sandbox budget, extracts canonical entities
(is_scenario=False → a real schedule), records the one Decision with the
DECOMPOSED cost delta + annotated moved-set. API: `POST /schedules/{id}/accept`
(synchronous — a deliberate act behind the budget; parent-linked, is_scenario
False) + `POST /schedules/{id}/publish` (`Registry.publish_schedule`). **The
registry is the live-lifecycle source of truth** — the served document's status
is frozen at assembly; `/meta` reflects current state, which the cockpit strip
reads. Chained edits: the accept path walks `base_run_id` to the ROOT solve for
the reference date (an accept run records no M3/M4, so re-deriving from a chained
parent would lose it — the 3.3b wall-clock trap avoided by construction) while
reading the M5 horizon + incumbent objective from the IMMEDIATE parent. Cockpit:
the delta card walks verdict → accepted → published (Accept + Publish are LIVE
controls now); `board.rebind(newDoc)` settles the moved bars into their new
positions by re-stamping the new assignments with the old bars' ids (the op set
is unchanged, so bars animate rather than teleport-reload — R-DP7); the
controller + ask panel retarget the new version (sequential edits sandbox against
the proposed version; asks read the new version's evidence). **Tests: Python
`test_planner_edit` 6; cockpit "accept mints a new proposed version; publish
supersedes it".**

**CU2 — the sandbox/edit question domain** (from a live refusal, "why does this
move cost 261"). New explainer routes: `_summarize_edits` ("summarize what I
changed and what it cost" — the demo's closing beat) and `_explain_edit_cost`
(production Δ + setup Δ + tardiness Δ, decomposing exactly per docs/02 §4.4, plus
the per-consequence "why" clauses from 3.3 CU3). Both read the `planner_edit`
Decisions in the current version's run — no new answer path; the Decision carries
the decomposed delta as self-contained evidence. Registers as testimony;
refuses honestly (unsupported) when no edit exists. New renderer subject types.
**Tests: `test_edit_question_domain` — routing (no solve) + a live end-to-end.**

**CU3 — voice.** `voice.js`: push-to-talk (Web Speech, feature-detected, degrades
to typed WITHOUT drama) feeds the transcript into the SAME ask path — the
deterministic router IS the transcript→route mapper and its "unsupported" bundle
IS the low-confidence refusal (an LLM-interpreter normalizer is NOT added; the
LLM never authors answers). `spokenSummary` leads with the register aloud + a
one-sentence summary and **strips every id-shape** — record IDs are NEVER voiced
(the screen holds the receipts). **Tests: cockpit "spoken summary … NEVER voices
record ids" + "the mic degrades without drama".** Carry-forward: the
LLM-interpreter transcript normalizer.

**CU4 — ghost latency.** Dial (b): on-demand pricing fires on pointer-DOWN (eager
= silent) so the K solves are in flight before the bar lifts. Dial (c): the K
per-machine solves run in a bounded thread pool (`ONDEMAND_SOLVE_WORKERS=4`;
CP-SAT releases the GIL during search, per-solve determinism unchanged). Dial (a)
precompute widening landed in 3.3 CU1; deepening it further is a measured
carry-forward. Measured (hermetic): grab→shade 5.2 ms; the rehearsal records
`priceToGhostsMs`/`acceptToDoneMs` per beat. busy_board raw wall time stays
bounded-by-design (Phase-4 profiling carry-forward).

**CU5 — the rehearsal.** `tests/cockpit/rehearsal.spec.mjs` drives the
sixty-second script end to end on the distinct fixture, BEAT BY BEAT,
screenshot-asserted, recording each beat's latency to `shots/
rehearsal_report.json`: ask why (VOICE) → 3 bars glow · grab → priced ghosts ·
drag onto a ghost → verdict + traced moved-set · Accept → new proposed version,
Publish → supersedes the base, strip flips · "summarize my changes" (VOICE) →
narrative naming the edit + authority. **Every beat green; 557 ms total beat
latency hermetic.** The fixture server stands in for the API across the arc
(canned ask + ghosts + sandbox + accept/publish + a synthesized edit narrative
for the accepted -edit version); the REAL accept→Decision→publish + the REAL
decomposed edit answer are proven against the live API by the Python tests. The
distinct fixture was regenerated to add the opening ask (real cited_refs glow
real bars).

**Riders.** (a) `dev_api.ps1` / `dev_cockpit.ps1` ALREADY self-locate via
`$PSScriptRoot` — confirmed, no change. (b) datetime.now() audit: the only
wall-clock fallbacks are `validator.py` (the known reference_date fallback,
mitigated by 3.3b's `--reference-date`, always supplied on the sample/API/edit
paths), `solver_builder.py` (horizon floor when NO demand is dated), and
`scenario.py` (slice cutoff when reference_date is None) — none new;
`apply_planner_edit` threads the reference date from the ROOT solve, so accept
never reintroduces the trap. (c) The feel-token export (`drag/tuning.js`
`exportFeel`) is confirmed working (JSON print + `feel.tokens.json` download,
console print the headless fallback).

**Result.** **Cockpit JS 34/34** (7 board + 5 legality + 20 gesture + rehearsal);
**Python 1035 non-slow passed** (the one intermittent
`test_scenario_untouched_moves_bounded` is a known CP-SAT-contention flake —
passes in isolation, unrelated to this session) + the new slow ladder. Phase 3
build work is complete — **Phase 3 awaits its exit audit** (a fresh session
driving the exit demo cold). See docs/07 v2.7 and CLAUDE.md.

## Amendment — 2026-07-15: Phase 3 EXIT AUDIT (audit mode; one seam found + fixed)

A fresh session ran the exit prompt's six clauses LIVE against the real dev stack
(uvicorn on :8137/:8138, `busy_board`, deterministic env `PYTHONHASHSEED=0` +
`--deterministic`), no fixes unless a clause failed. **One clause failed
(Clause 2, the delta-card dollar provenance); it was fixed in-session and
re-verified live.** Every accommodation is named below. `busy_board` measured at
90 scheduled assignments (CLAUDE.md's "board of hundreds of ops" was imprecise —
corrected).

**Clause 1 — the sixty-second script, LIVE: PASS (qualified).** Driven end to end
over HTTP on `busy_board`, TWICE; the deterministic legs AGREE byte-for-byte
(objective 5107162.0, sandbox/accept objective-delta 602.0, cost delta $5.02 —
identical both legs). Beats: (1) ask "why is ORD-000012 late?" → testimony answer,
1 op + 6 resources cited to glow; (2) 8 priced cross-machine ghosts; (3) drag onto
a ghost → the Tier-2 re-solve returned **`feasible_unproven`** (FEASIBLE, bound
unproven) within the 15 s budget — the honest FLAGGED card (R-T1c outcome 2), NOT
a proven-optimal verdict, and **0 why-clauses** on the exercised drag (the moved
op was not a major contiguous displacement, so none was fabricated — R-DP7); (4)
Accept → a `planner_edit` Decision recorded (record_id present, **authority
"audit-planner" present**), a NEW **proposed** version (is_scenario false, parent
link true), **the base byte-identical/untouched**; (4b) Publish → base
**superseded**, its **pool invalidated**, double-publish 409; (5) "summarize what
I changed and what it cost" → testimony narrative naming the authority + the
decomposed cost, and the cost-question decomposes production/setup/tardiness.
**Accommodations:** the LLM renderer ran OFF (no `ANTHROPIC_API_KEY`) — template
throughout; voice was driven programmatically (`panel.askSpoken`, no microphone in
automation); the UI beats (glow / drag physics / card) are verified by the cockpit
harness (client-side) while the BACKEND beats were verified live over HTTP.
**Qualification:** on `busy_board` the sandbox uses the FULL 15 s budget and ships
the flagged card — the demo's "delta confirms" is an honest ≈-delta, not a proven
optimum, on a board this size.

**Clause 2 — honesty armor: FAILED → FIXED → re-verified.** Registers never blend
(testimony vs judgment distinct, live). Fail-closed verified: `llm:true` with no
key returns a clean TEMPLATE answer (`[rendered by: template | register:
testimony]`), no error, no unvalidated prose — named accommodation: the key was
absent throughout, so the fail-closed path was verified DIRECTLY rather than by
breaking a working key mid-session. Unsupported question refused honestly. **The
failure:** the delta card rendered `delta_abs` (the SCALED, tardiness-weighted
solver OBJECTIVE delta, ~100× the dollar ledger) with a `$` sign — on `busy_board`
it would have shown **"+$602"** when the true ledger cost delta is **+$5.02** (a
~120× overstatement); the "% cost" and the accepted card carried the same
objective-as-dollars defect. A delta-card number that does NOT trace to ledger
records (docs/02 §4.4). **Fix (authorized by the clause failure):** `SandboxResult`
gains `cost_delta_abs`/`cost_delta_pct` computed from a no-persist extraction of
the re-solve's ledger vs the base schedule's total; `apply_planner_edit` exposes
the decomposed `cost_delta` and the accept response carries it; the cockpit card
(`sandboxui.js` `_deltaHeadline` + `showAccepted`) shows dollars ONLY when
ledger-backed and degrades to a relative-`%`-vs-current-plan label otherwise —
never a false dollar figure. Re-verified LIVE: the card now shows **"+0.01% cost ·
+$5.02"** with the decomposition summing exactly (5.02 = 5.02 + 0 + 0). Sandbox +
planner_edit tests green, full cockpit suite green.

**Clause 3 — R-DP compliance: PASS.** Verified via the cockpit harness on current
HEAD (34/34): literal drop (R-DP1), dim-refusal + return-home with reason (R-DP2),
shading clears on the drop→tentative transition (3.2d CU1), no silent motion —
traces held + legible board rebind on accept (R-DP7), Accept a LIVE control (no
longer stubbed). Client-side / harness-driven (not a live pointer) — named.

**Clause 4 — measurements (baselines recorded, LIVE on `busy_board`).** Median
first-grab time-to-ghosts = **6.2 s** (82 of 90 multi-eligible ops uncovered;
server-side K per-machine solves, parallelized dial-c, bounded by the 6 s
per-solve limit — the cockpit shows the "pricing alternatives…" shimmer over the
wait, absence never silent). Cached-grab (pool re-read on a second grab) =
**3.6 ms**. Sandbox verdict latency = **15.0 s = the full budget token** → flagged.
grab→shade = **5.2 ms** (client-side, from the gesture harness). The CU4 gap the
record owed is now MEASURED: first grab is multi-second by design, cached is
instant.

**Clause 5 — the exit bar (cold stranger): MET-BY-PROXY.** No stranger who plans
for a living was available this session. The bar is met by proxy — Daryn's live
`busy_board` feel sessions (3.2d/3.3) + this audit's twice-run live script + the
hermetic beat-by-beat rehearsal. **The cold-stranger drive is a NAMED CONDITION on
Phase 4 entry** (docs/07 Phase 4 entry conditions), not relaxed.

**Clause 6 — carry-forward inventory (nothing evaporates).** 2.4b cloud in-cloud
confirmations (Docker/Azure) — OPEN. Pool/forced slice-awareness (pilot-gated) —
OPEN. LLM voice normalizer — OPEN. Ghost precompute dial (a) — OPEN, but the
`busy_board` first-grab profiling it was paired with is now MEASURED (6.2 s /
3.6 ms above). Pool-ghost partial consequences — OPEN. Real auth (dev token now) —
OPEN. **Feel tokens exported + committed: NOT LANDED** — no `feel.tokens.json` in
the tree; the surface runs on `DEFAULT_FEEL`; the export path is verified working
(3.4), Daryn's tuning pass is still pending. CP-SAT-contention flakes
(`test_scenario_untouched_moves_bounded`, `test_n3000`) marked as such — this
audit's full run passed CLEAN (1036 non-slow, 0 failed), confirming flake status.
**NEW (from this audit):** the hermetic canned-sandbox fixture carries no
`cost_delta_abs`, so the rehearsal/gesture cards degrade to the relative-% headline
while the LIVE path shows dollars — a minor fixture-realism follow-up (the builder
could compute it on the next regen).

**Verdict: Phase 3 COMPLETE (qualified).** One seam found and fixed in-session
(the delta-card dollar provenance — the exit audit earning its keep); all other
clauses PASS or are recorded with named accommodations. **1036 non-slow Python
passed (0 failed)** + slow sandbox/planner_edit ladder + **cockpit 34/34**.
Entering Phase 4 preparation; carried conditions: the cold-stranger cold-drive,
cloud in-cloud confirmations, and Daryn's feel-token pass.

## Amendment — 2026-07-15: R-M1 — Motion carries register (ruling; implementation is Session 3.6)

Settled in a parallel design thread; reconciled and renumbered into the main
thread here. **Implementation is Session 3.6; Session 3.5 builds the token
surface it depends on** (the named-but-unconsumed motion tokens in
`src/cockpit/src/tokens.css`, panel-tunable via `drag/feel.js` + the tuning
panel). Transcribed VERBATIM:

--- RULING TEXT BEGINS ---
R-M1 — MOTION CARRIES REGISTER
Bar motion is communication. Each movement class has a fixed
meaning:

a) REJECTION (return-home per R-DP1): fast snap-back with a brief,
   subtle shake at arrival. Must read as "the board refused,"
   never as "the system placed it." No easing that implies
   settling. The rejection reason surfaces through existing text
   channels (status/conversational layer), not the animation.

b) REFLOW (other bars moving after a committed re-solve): smooth,
   simultaneous eased transitions (~300-400ms), moved bars briefly
   highlighted. Simultaneous, not cascaded — CP-SAT re-solves
   globally; a cascade would imply a causal chain that doesn't
   exist. (The 3.4 accept-rebind "settles into place" behavior is
   an instance of this class and is unified under it in 3.6.)

c) OWN PLACEMENT (committed drop): never moves. Confirmation is a
   static pin-lock effect, visually distinct from pending-solve.

d) GHOSTS: fade in/out only, price/verdict labels fading WITH
   their bars (labels never pop independently).

All durations, easings, and shake amplitude are design tokens
(panel-tunable). Semantics are fixed by this ruling; feel numbers
iterate on busy_board.
--- RULING TEXT ENDS ---

**Reconciliation notes (main-thread, non-normative).** R-M1 governs the
*motion vocabulary* of the surfaces R-DP1/R-DP2/R-DP7 and R-T1 already ruled:
(a) refines the R-DP2 return-home into a refusal-reading snap-back (no settling
ease); (b) subsumes the 3.4 accept-rebind `board.rebind` "settle" under one
REFLOW class (simultaneous, not cascaded); (c) makes the R-DP1 committed drop a
static pin-lock, distinct from the tentative/pending-solve state; (d) fixes
ghost fade as the only ghost motion, labels bound to their bars (the C1/CU2
label-tracking discipline extended into fade). No vocabulary or contract changes;
this is presentation semantics. Session 3.6 implements it against the token
surface Session 3.5 lays down below.

## Amendment — 2026-07-15: Session 3.5 — cockpit design-token pass (visual only, zero behavior changes)

Visual modernization of the board WITHIN the existing token architecture — no
behavior, timing-logic, or gesture changes. The 34/34 cockpit harness stayed
green untouched (it asserts behavior / geometry / text, not colors; screenshots
are gitignored and NOT pixel-compared, so visual changes cannot trip it — no
baselines to rebaseline, they re-capture on run). The C1 label-vs-bar drift
regression (≤ 1 px) passing confirms the bar-radius/sheen changes did not shift
geometry.

**Token consolidation.** Every palette + typography + geometry + elevation +
motion value now lives in `src/cockpit/src/tokens.css` (or derives from it);
`cockpit.css` and `drag.css` reference tokens only — grepping either for a bare
hex/rgba or a bare `px` font-size now returns nothing. Added: a typography scale
(`--font-ui`/`--font-mono` families + `--fs-2xs…--fs-lg` + `--fw-*` weights +
`--ls-caps`/`--lh-*`), color primitives the CSS had hard-coded (`--ink-inverse`,
`--on-accent`, `--grade-ink`, `--cite-ink`, `--scrim`, `--bg-deep`), an elevation
scale (`--shadow-scrim/-1/-2/-3`), a `--radius-xs`, bar-geometry tokens
(`--bar-radius`, `--bar-sheen`, `--bar-pad-x`), general motion durations
(`--dur-slow/-pulse/-shimmer`, replacing the inline `0.35s/0.9s/1.1s`), and the
tentative/carry glow + outline tokens (`--tentative-glow-0/-1`, `--carry-outline`)
that pulled the last rgba literals out of the keyframes. (Incidental micro-paddings
on the 4 px rhythm — `3px 7px` chip insets etc. — remain inline; they are not
palette/semantic values.)

**R-M1 motion tokens — NAMED-BUT-UNCONSUMED.** The R-M1 group (`--motion-reject-*`,
`--motion-reflow-*`, `--motion-pinlock-*`, `--motion-ghost-fade-*`) is added now
so Session 3.6 implements the ruling against a live surface. It is NOT wired into
any animation this session (that is the point — build the surface first). The
numbers are panel-tunable NOW: `drag/feel.js` gains `motion.*` (+ `bars.radius_px`)
and `applyFeel()` mirrors them onto the `--motion-*` custom properties, and the
tuning panel exposes them under a "motion · R-M1 (3.6)" group (the panel gained
group headers + the geometry/motion groups so every visual token group Daryn
tunes is in one place).

**Restrained modernization** (named, since it changes the look): the base surface
calmed a touch (`--bg` #0f1117→#0e1016, `--grid` #232836→#262b3a); bars get a
cleaner 4 px radius (from 3 px) + a subtle inset top sheen; the ghost / carried /
trace bars adopt the same `--bar-radius` for consistency; typography moved to the
`--font-ui`/`--font-mono` stacks with fuller fallbacks + the semantic scale;
elevations unified through the shadow scale; the legend gained a light backdrop
blur; the ask input gained a focus ring. Sleek, not flashy — this board's job is
trust. Verified rendering on the harness-captured board state (rounded bars,
sheen, calm chrome, mic affordance, green grade chip all intact).

**Result.** `tokens.css` (rewritten), `cockpit.css` + `drag.css` (fully
token-routed), `drag/feel.js` (+motion +bars groups, mirrored), `drag/tuning.js`
(grouped panel + motion/geometry controls). Cockpit JS **34/34** (unchanged);
Python untouched. **Carry-forward: Session 3.6 — R-M1 implementation** (consume
the motion tokens; unify the 3.4 accept-rebind settle under the REFLOW class;
the return-home snap-back, pin-lock, and ghost-fade animations). See docs/07 v2.9.

## Amendment — 2026-07-15: Session 3.6 — R-M1 implementation (motion carries register)

Animation only — no solver, API, or gesture-logic changes; the ruling is law,
implemented as written. Consumes the 3.5 motion tokens; adds none outside the
panel surface. The cockpit harness went 34 → 38 (the four end-states below);
nothing else changed.

**CU1 — REJECTION (R-M1a).** `returnHome` is now a FAST snap-back of the
*existing* carry element (not a fresh render, which would teleport) using
`--motion-reject-*` — `--motion-reject-ease` is deliberately a non-settling curve
so it reads as "the board refused," never "the system placed it" — followed by a
brief `reject-shake` at ARRIVAL (`transform` translateX, `--motion-reject-shake-*`).
The reason stays in the existing text channels (the return-home card / the
mid-drag reason tip), never the animation — verified un-regressed (the
return-home card still shows on a no-verdict drop). Harness: post-rejection the
op's board placement == its origin (nothing committed); the `.carry-bar.rejecting`
snap-back class is observed mid-return.

**CU2 — REFLOW (R-M1b).** ONE reflow implementation, unifying the consequence
motion and the 3.4 accept-rebind: on accept, `board.rebind` enables a
SIMULTANEOUS eased transition (`--motion-reflow-*`) on every bar for the reflow
window only (a single `.reflowing` class on the host; `transition-delay: 0s
!important` — explicitly no per-bar stagger, because CP-SAT re-solves globally and
a cascade would imply a causal chain that does not exist), and the displaced bars
get a one-shot `reflow-moved` highlight that fades over
`--motion-reflow-highlight-dur`. Harness asserts the computed `transition-delay`
on a reflow bar is `0s` (simultaneity) and the committed placements match.

**CU3 — OWN PLACEMENT (R-M1c).** The dropped bar NEVER slides: its motion class
(`pin-lock`) is baked into the same `items.update` that repositions it, and the
reflow transition selector is `:not(.pin-lock)`, so the committed bar SNAPS to its
drop spot (matching where the tentative already was) and plays a static green
pin-lock ring (`--motion-pinlock-*`) — visually distinct from the tentative's
purple hatch/pulse — while everything else reflows. The tentative overlay is
cleared on accept so the committed board bar (with its lock) stands for it.
pin-lock persists as the "locked" confirmation until the next gesture/rebind
(`board.clearMotionClasses`, called on discard + at the head of a rebind).
Harness: the pinned op carries `pin-lock` post-accept and sits on the dropped
machine.

**CU4 — GHOSTS (R-M1d).** Fade in/out ONLY, and the label layer fades WITH the
bar layer (`fadeGhosts()` applies `ghost-fade`/`--motion-ghost-fade-*` to BOTH
`.drag-ghosts` and `.drag-ghost-labels`), so a price/verdict label never pops
independently of its bar — covering both the precomputed appearance (on grab) and
the on-demand shimmer→ghosts arrival (replacing the old bars-only `.fade-in`).
Harness: on grab, both layers carry `ghost-fade` and the ghosts are present.

**Reduced motion.** A single `@media (prefers-reduced-motion: reduce)` block
drops every R-M1 animation/transition to instant; the motion CLASSES still apply
(so the confirmation semantics are present — the pin-lock class is there, the
return still lands at origin) and the rejection stays distinct via the text
channel (the shake is dropped, not the meaning). Harness asserts under
`reducedMotion: reduce`: the rejection ends at origin with the card shown, and
accept pin-locks with NO `.reflowing` transition class.

**Result.** `drag.css` (the R-M1 animation blocks + reduced-motion), `board.js`
(reflow/pin-lock in `rebind`, `clearMotionClasses`, `placementOf`/`motionOf`
probes), `drag/controller.js` (reject snap-back, `fadeGhosts`, reflow wiring on
accept, discard cleanup), the fixture server (an accepted -edit version reflects
its pin so the reflow has a real move to assert), + four harness end-state tests.
**Cockpit JS 38/38**; Python untouched. **Carry-forward check:** after 3.6, the
queue before Phase-4 design is exactly **Daryn's grand feel pass + export**
(the tuning panel now exposes every visual + motion token, incl. the R-M1
group). The Phase-4 ENTRY conditions (the cold-stranger cold-drive, cloud
in-cloud confirmations) are gates on entering Phase 4, distinct from the build
queue; the deferred items (slice-awareness, LLM voice normalizer, ghost
precompute dial (a), pool-ghost partial consequences, real auth) are all Phase-4+/
pilot-gated/post-pilot, not before Phase-4 design. See docs/07 v2.10.

## Amendment — 2026-07-15: Session 3.7 — voice input hardening (a bug + the interaction model)

**Provenance.** A bug observed live on the gesture surface: during press-and-hold
voice recording, the interim transcript streamed into the ask composer, reflowed
the panel, and shifted the **mic button out from under the pressed pointer** — the
pointer left the button, `pointerup`/`pointerleave` fired `stop()`, and recognition
ended after the first few words, so only a **fragment** was submitted. The
press-and-hold model coupled the capture lifetime to a pointer sitting on a target
that could move. This session fixes the reflow AND retires the hold model.

**CU1 — no layout motion during recording.** The interim transcript now renders in
a **fixed-footprint FLOATING overlay** (`.voice-overlay`, `position:absolute`,
`transform: translateY(calc(-100% - …))` above the composer, fixed
`--voice-overlay-h`, single-line ellipsis), so streaming speech is drawn *over* the
log and **never reflows the row the mic lives in** — nothing under an active
pointer moves (R-M1 spirit). The interim text is written ONLY to that overlay
(`onInterim`); the input is untouched mid-record. The **final** transcript lands in
the input only on **stop**, then runs on the spoken path (register aloud + one
sentence, record ids never voiced — the 3.4 contract, un-regressed).

**CU2 — interaction model.** Press-and-hold → **tap-to-start / tap-to-stop
toggle** (`voice.js` `createVoiceInput` replaces `createPushToTalk`; the mic click
calls `voice.toggle()`, no pointerdown/up/leave capture coupling). Recording is an
explicit LATCHED state — push-to-talk **explicitness** per docs/07 is preserved (the
mic never opens itself). **Unmistakable recording state** (tokenized): the mic gets
`.recording` (solid `--voice-rec-fill` red + `--voice-rec-pulse-ms` pulse +
`aria-pressed`), and the overlay carries a pulsing `--voice-rec-dot` + a "recording"
label. **Escape cancels** without submitting (`voice.cancel()` → `abort()`, the
`cancelled` flag suppresses the `onTranscript` submit; a `window` keydown listener
active only while `listening()`). **Optional silence auto-stop** as a convenience:
`VOICE_SILENCE_MS = 2500` + a `silenceMs` option (a timer re-armed on each result),
**OFF by default at the call site** — explicit tap-to-stop is the contract. The
recognizer now runs `continuous = true` and **accumulates finals across result
events** (never resets `finalText` mid-session), which is what keeps the whole
sentence instead of a leading fragment.

**Tokens.** All voice visuals are tokenized in `tokens.css`
(`--voice-rec-*`/`--voice-overlay-*`); the silence timeout is a named const in
`voice.js`. A `@media (prefers-reduced-motion: reduce)` block in `cockpit.css` drops
the mic/dot pulse — recording stays unmistakable via the solid fill + label.

**Harness.** Headless has no microphone, so a **fake `SpeechRecognition`** injected
before page scripts (`window.__VOICE_TEST_RECOGNITION`, honored by
`recognitionCtor()` — harness-only) drives the REAL controller/UI path. Three new
`gesture.spec.mjs` tests: (1) tap latches recording (class + `aria-pressed` +
overlay) and a long interim leaves the **mic bounding box unchanged** (≤0.5px on
x/y/w/h) while capture stays live; (2) the **fragment regression** — incremental
interims + a final, then stop, submits the FULL sentence as the "you" message, never
a fragment; (3) **Escape cancels** — state returns idle, overlay retired, nothing
submitted. **Cockpit JS 41/41** (was 38); Python untouched. See docs/07 v2.11.

## Amendment — 2026-07-16: Session 3.8 — version-lifecycle continuity in the cockpit

**Provenance.** Feel-pass findings, live: after an accept→publish the cockpit was
observed still referencing the *superseded* schedule id. The consequences were a
raw "superseded" error from `/ask`, a subsequent accepted drop that *returned
home* (a committed edit apparently rendering as a rejection — R-DP1/R-M1a as
experienced), and Tier-0 shading/ghosts still rendered from the stale version's
payload while drops validated against reality ("zombie legality"). Backend +
gesture mechanics only; no solver/model changes.

**CU2 — diagnosis FIRST (which case it actually was).** Reproduced against the
real API (`TestClient`, one deterministic `clean_small` solve; scratch repro):
accept edit1 → C1 (proposed), publish C1 → C1 published, base B **superseded**.
Then two probes:

- *Bound to the current version C1* (the correct state): `/ask`, `/sandbox`,
  `/accept` all **succeed** (200/201).
- *Stale-bound to the superseded base B*: `/ask` → **409 "is superseded"**,
  `/sandbox` → **409**, `/accept` → **409**. **But `/interaction` → 200** even
  for a superseded id (the endpoint has no status guard).

So the returned-home drop was **NOT** "a committed edit reverting" (the suspected
case A). It was **case B: the accept/sandbox itself 409'd against a superseded id
— the backend never committed anything** — and the controller surfaced that 409
as a generic `sandbox error` / silent `returnHome`. The zombie legality is
explained by the same asymmetry: `/interaction` keeps serving the stale payload
while every *mutating/asking* call against that id 409s. The backend lifecycle is
correct (accept mints a proposed-with-interaction child, publish supersedes the
immediate parent, sequential edits re-enter the accept path — all already tested);
the defect is entirely in the **cockpit's version binding + its handling of a
superseded response**. The fix therefore is *surfacing + continuity*, not a
re-solve change.

**CU1 — version continuity (full rebind on accept AND publish).** The live rebind
existed for the strip/panel/controller but left two seams that let a stale id
persist and one that made it fail opaquely: (a) the **address bar was never
rewritten**, so a reload re-bound the now-superseded id; (b) the **shared
selection** kept a moved op's stale scope. `main.js` now routes every version
change through one seam that updates the URL (`history.replaceState`, other params
preserved), the strip (new id + live status), the ask target, the selection
(`panel.clearSelection()`), and the harness hook — and the deep-link boot stamps
the resolved id into the URL up front. The controller already re-fetches the new
version's interaction + alternatives on accept (`rebindController`); publish keeps
the same id, so no refetch is needed there. Invariant restated: **no user action
may ever be issued against a superseded id from a live session.**

**CU3 — superseded-schedule UX (never a raw error, never an editable zombie).**
Additive backend: `Registry.live_successor(id)` follows the child chain forward
past further-superseded links to the live descendant; `GET /schedules/{id}/meta`
adds `successor_id` when `status == "superseded"`. Frontend: `api.js` throws a
typed `ApiError` with a `.superseded` flag (409 + "is superseded"), plus
`resolveSuccessor(id)`. A **deep link** to a superseded id loads read-only behind
a banner ("This plan was replaced by a newer version" + a one-click *View current
(<id8>)* jump) and the gesture surface is **deliberately not wired** (no zombie).
A **live** 409 self-heals: the ask panel renders planner language + a jump, and
the controller's drop/accept catch routes to the live successor instead of a raw
error. "View current" / the self-heal do a clean full reload bound to the
successor — no half-rebound state.

**Harness — the missing seam.** The hermetic fixture server now models the
lifecycle: it records each accept's parent, supersedes the immediate parent on
publish (recording the successor), answers `/ask`|`/sandbox`|`/accept`|`/publish`
against a superseded id with **409 "is superseded"** exactly like the real API,
serves `successor_id` on a superseded `/meta`, composes the whole edit chain's
pins in `GET /schedule` (so an earlier accepted bar stays put through later
cycles), and exposes `POST /__test__/reset` (called before each `boot()`) so a
publish in one test never supersedes a base fixture the next test boots against.
Three new `gesture.spec.mjs` tests: (1) **two consecutive edit→accept cycles** —
the hook, controller, and URL all advance together each cycle and each accepted
bar stays where committed; (2) **edit→accept→publish→edit** — the post-publish
edit re-enters accept against the *published* version, never a superseded-id 409 →
return-home; (3) **deep link to a superseded version** — read-only banner + jump,
gesture surface not wired.

**Results.** Cockpit JS **44/44** (was 41). Python **1036 passed / 0 failed**
(non-slow) + the planner_edit slow ladder **7/7** incl. a new
`test_superseded_meta_carries_its_live_successor`. See docs/07 v2.12.

## Amendment — 2026-07-16: R-AI1 ruling — EVERYTHING LOGS FACTS AND ESTABLISHES PATHWAYS TO AI

Ruled in the design thread, transcribed here verbatim (append-only; settled).
Implementation begins AI-track Session 4A.1 (same day, below).

--- RULING TEXT BEGINS ---
R-AI1 — EVERYTHING LOGS FACTS AND ESTABLISHES PATHWAYS TO AI
Every capability ships AI-reachable or names its debt:
(a) It emits structured evidence of what it did and why — no
    silent mechanisms.
(b) It ships with, or explicitly queues, its question domain — a
    pathway from planner language to its records.
(c) Intelligence accrues only in reviewable artifacts (routes,
    catalogs, interpreter cases, authored copy) — never in model
    state; models are swappable renderers behind the validation
    armor.
(d) Unanswerable questions are themselves logged facts (the
    question ledger), feeding a human-curated improvement loop —
    the system never rewrites its own routing unreviewed.
Session close-outs must name the session's evidence and its
question pathway, or name the debt.
--- RULING TEXT ENDS ---

## Amendment — 2026-07-16: AI-track Session 4A.1 — the interpreter, conversational context, and the question ledger

First AI-track session. Wraps the M10 deterministic router (which the router IS
the taxonomy) with a normalization stage, conversational memory, a logged fact
stream, and a no-dead-end fallback — **without touching the router's routing**
(1086 non-slow Python green, the existing explainer/certificate/edit suites among
them; cockpit JS 45/45, was 44).

**The refactor that makes it possible (zero regression).** `Explainer.answer()`
is now exactly `route(*classify(question))`: `classify()` maps a working phrasing
onto a route id + params (branch order preserved byte-for-byte from the pre-4A.1
router), `route()` dispatches. The 15 route ids are a closed taxonomy
(`ROUTE_TAXONOMY`, each with its param slots + a canonical planner-vocabulary
question). This split makes the taxonomy callable by everything downstream while
routing is unchanged — the deterministic path never calls an LLM, never pays
latency or cost (a call-counting mock asserts zero interpreter calls across the
17-row deterministic paraphrase table).

**CU1 — the interpreter** (`interpreter.py`). Invoked ONLY when `classify()`
returns `unsupported`. LLM-backed (a swappable client; fail-closed — no key /
malformed JSON / unknown route / low confidence → the honest refusal), strict JSON
contract (`{route, params, confidence, nearest}`), route validated against the
closed taxonomy. Params are external refs resolved through the identity map
(`resolve_order_value` / `resolve_machine_value`: exact token then unique
substring — `'2001' ⊂ 'WO-2001'`, `'GEAR-01' ⊂ 'M-GEAR-01'`), never an id-shape
regex (the Phase-1 audit lesson). A high-confidence route with all params resolved
answers by synthesizing the canonical question and re-routing it through the same
assemblers (external refs re-resolved inside). The paraphrase table is the growing
asset the ledger feeds (≥25 cases: deterministic rows route with no LLM; the rest
via a mocked interpreter).

**CU2 — conversational context** (`resolve_followup`). Deterministic ellipsis
resolution BEFORE routing: a self-contained question passes through; a cost
follow-up after an edit answer ("how much?") resolves into the edit-cost domain; a
pronoun/fragment follow-up ("and what about it?") resolves against the last
order/machine subject in the short history or the board selection; an ellipsis
with no prior subject → **clarify** (ask for the referent, never guess). Resolution
is VISIBLE — the resolved question rides back on the bundle (`bundle.question`) and
the cockpit renders an "interpreted as" note above the answer (the 3.2d deictic
pattern, generalized). The server stays stateless: the cockpit carries a rolling
4-turn history + selection + a session id in the `/ask` body.

**CU3 — the question ledger** (`question_ledger.py`, shape in
`contracts/question_ledger.py`). Every ask logged as one `QuestionLedgerEntry` in
its OWN append-only JSONL stream under the data root
(`ledger/questions.jsonl`) — **never** inside a run's evidence dir (a fact about
the AI layer, not the schedule). Records: verbatim + resolved question, route (or
`REFUSED`/`NEAR_MISS`/`CLARIFY`), source (`deterministic`/`llm`/`none`),
confidence, register, schedule id, session id, and **rephrase linkage** — a routed
entry that follows a refusal in the same session within 180 s points at that
refusal (`rephrase_of`), the free labeled pair the improvement loop consumes.
`refusal_clusters()` (frequency-ranked, "any_rephrased" marked) backs a DEV-gated
cockpit panel; a **meta-route** ("what questions couldn't you answer recently?")
reads the ledger — the ledger answering about itself (R-AI1(d)). The `/ledger/
refusals` endpoint is DEV-gated (404 unless `MRE_DEV`).

**CU4 — tiered fallback** (`ask_fallback_copy.py`, all copy AUTHORED, never
LLM-improvised). Between routed and refused: the **near-miss bridge** — moderate
interpreter confidence (`[0.45, 0.75)`) OR params that only partially resolve →
answer honestly and offer the two nearest routes as concrete one-phrase follow-ups
("I can't answer that exactly — I can show you every late order, or …"). The full
refusal keeps the planner-language capability list. No dead ends.

**Verification.** `test_interpreter.py` (paraphrase table + deterministic-never-
calls-LLM + fail-closed + near-miss + param resolution + 3-turn context chains),
`test_question_ledger.py` (roundtrip, rephrase linkage, clusters, malformed-line
tolerance), `test_ask_chain_api.py` (slow, one deterministic solve: voice-shaped
phrasing → route → render → ledger row in its own stream; live ellipsis
resolution; meta-route; DEV gating). Existing router/explainer suites untouched-
green. One cockpit test for the visible resolved-question.

**R-AI1 close-out for this session.** *Evidence:* the question-ledger records
(every ask, routed or refused, in its own stream). *Question pathway:* the
interpreter + `ROUTE_TAXONOMY` + the meta-route (the ledger is itself queryable).
*Debts named, not built* (AI-track Session 2/3 scope): **WIP has no question
domain** ("what's already running / in progress?"); **cross-run economics has
none** ("is batching paying for itself?"); the **constraint-catalog "why can't it
do X"** is not conversational. See docs/07 the AI-track line.

---

### 2026-07-16 — Session 4.0-hotfix: an accepted cross-machine drop landed on the wrong machine (R-DP1 violated in shipped code)

**The report (live, screenshots).** A bar for ORD-000002 was dragged
RES001→RES002, held tentative, the sandbox returned "+0.30% proven within
budget," Accept was pressed — and the new proposed version rendered the op back
on **RES001** at approximately the dropped time. Right time, wrong machine.

**CU1 — diagnosis by evidence, before any code change.** The pin is applied
identically in `sandbox.py` and `planner_edit.py`:

```python
apply_solution_hints(model, var_map, incumbent_assignments)
if pin_op_id in var_map.op_start:
    model.add(var_map.op_start[pin_op_id] == pin_start_min)   # TIME pin
lit = var_map.op_assign.get(pin_op_id, {}).get(pin_resource_id)
if lit is not None:                                            # MACHINE pin
    model.add(lit == 1)                                        #  — SILENTLY skipped
```

`var_map.op_assign[op]` carries a `{resource_id: BoolVar}` entry **only for the
resources the op is eligible on** (solver_builder builds it from the eligible
set). So `.get(pin_resource_id)` returns `None` — and `if lit is not None:`
**silently drops the entire machine constraint** — whenever the pinned resource
is not a key in that op's assignment dict. The time pin binds independently.
Result: the re-solve honours only the time pin and is free to place the op on
its cheaper eligible machine — right time, its machine — while reporting a
feasible verdict for a placement that was **never actually tested**.

Reproduced deterministically (`multi_route`/`multi_route_distinct`, workers 1,
seed 42, `PYTHONHASHSEED=0`), driving the real API exactly as the cockpit does:

- **Eligible, id-matching cross-machine pin** (distinct rates, drop onto the more
  expensive machine): the pin binds end to end; the op lands on the pinned
  resource; the verdict is **+0.3012% / +0.33% cost** — the reported "+0.30%"
  reproduced *exactly*, and honest. So the gesture→CP-SAT→extraction chain is
  **sound when the machine literal exists**.
- **Un-pinnable target** (a resource the op has no literal for): the machine pin
  is silently skipped, the op stays on its cheaper incumbent machine, and the
  solve reports **OPTIMAL / feasible / 0.0% delta** — a false-happy verdict; the
  accepted version places the op on the wrong resource. The live symptom,
  reproduced.

**What compiled the pin — precisely.** The compiled pin constrained **start**
(always) and **resource** (only when the eligibility literal existed, else
skipped). The extracted assignment reflects exactly that: on the un-pinnable
path it carries the incumbent resource at the pinned start. **The sandbox verdict
solve and the accept solve use the SAME pin** — identical code, and the cockpit
sends identical params to both (`t.resource_id` to `/sandbox`,
`S.target.resource_id` to `/accept`, both the canonical vis-group id). They
cannot diverge; the reporter's "verdict pinned both, accept re-compiled
differently" hypothesis is **refuted**. A happy-verdict-and-wrong-placement can
arise only when the machine literal was absent in *both* — i.e. the drop targeted
a resource with no assignment literal (an ineligible row Tier-0 should have
dimmed, or a Tier-0-vs-solver eligibility disagreement), or the delta shown was a
ghost's precomputed price while the accept-solve silently dropped the machine pin.

**Mechanism, named honestly: R-DP1 was violated in shipped code.** R-DP1 requires
the pinned op be placed on the pinned resource at the pinned start — gesture
through CP-SAT through extraction. The pin code did not *enforce* the machine
axis; it *offered* it and **silently discarded** it whenever the literal was
absent, then reported a verdict as if the placement had been proven. The
invariant was not merely unasserted (CU3) — it was actively broken by a
`if lit is not None:` that turned a hard constraint into a no-op.

**CU2 — the fix (per diagnosis).** The machine pin is now **mandatory**, never
silently skipped, in both modules:

- `planner_edit.py` (accept): an absent start variable or an absent machine
  literal is a **hard error** — the accept raises (surfaced by the API as 409),
  nothing is registered, the base version stands. An accept must never mint a
  version that places the op where the planner did not drop it. Added a **post-
  solve R-DP1 post-condition**: the solved `(op_resource, op_start_minutes)` for
  the pinned op must equal `(pin_resource_id, pin_start_min)` before the version
  is minted — belt-and-suspenders against any residual model looseness on an
  irreversible act.
- `sandbox.py`: an un-pinnable target is a **proven-illegal placement**, so the
  re-solve short-circuits (before spending budget) to an honest INFEASIBLE
  verdict → R-DP2 return-home ("this placement isn't possible: op is not eligible
  on the target resource"), never a false-happy delta. Symmetric post-solve guard
  added. "Green + refused-by-solve is its own finding": if Tier-0 ever offers an
  un-pinnable row, the sandbox now says so out loud instead of pricing a fiction.

Eligible, id-matching pins (the demo path, and every existing same-machine
`_pin_from_incumbent` test) are unaffected — the literal exists, `model.add(lit
== 1)` binds, the post-condition passes.

**CU3 — the missing assertion, permanently.** The 3.4/3.8 suites pinned only
**same-machine** (`_pin_from_incumbent`, chosen precisely so the fixture needn't
carry a cross-machine move) and **never asserted the extracted placement**, so
they could not see this. Added:

- **`test_planner_edit.py::TestAcceptHonoursThePinnedResource`** (slow, on
  `multi_route_distinct`): a genuine cross-machine accept must land the op on the
  **pinned resource at the pinned start** (the end-state check); the sandbox
  verdict must move the op to the target; an **ineligible pin is refused** — accept
  409 (base stands), sandbox an honest infeasible return-home — never silently
  relocated. Planner_edit slow ladder **7 → 10**.
- **`gesture.spec.mjs`** — one harness test drives a cross-machine drag → accept →
  rebind and asserts the **rendered row** (`board.placementOf(op).group`) equals
  the pinned machine and differs from the incumbent; **rehearsal.spec.mjs** Beat 4
  gains the same rendered-row R-DP1 end-state check (the demo script now catches
  the regression). Cockpit JS **45 → 46**.

**Result.** Non-slow Python **1086 passed** (unchanged — the new accept tests are
slow); planner_edit slow **10/10**, sandbox slow **12/12**; cockpit JS **46/46**.
See docs/07 v2.14. Lesson: a hard invariant applied through
`if <thing-exists>:` is not an invariant — it is a suggestion the code drops the
moment the thing is missing, and then reports success. Enforce, or refuse; never
skip-and-vouch.

---

### 2026-07-16 — Session 4.0b: Tier-0 vs solver eligibility — one source of truth (R-DP6)

**Why.** The 4.0-hotfix proved an accepted drop targeted a resource the solver
had NO `op_assign` literal for — the R-DP1 machine pin was silently skipped. Its
CU1 left the upstream question open: could Tier-0 have *offered* (greened) that
un-pinnable row? R-DP6 requires green = provably-not-illegal **by the same rules
the solver compiles**. Eligibility was resolved TWICE, by hand — the Solver
Builder (which resources get an `op_assign` literal, the set the pin binds) and
the schedule-document assembler (the payload's `eligible_resource_ids` the
cockpit dims/greens with). Two copies can drift; worse, they measured **different
things** (below). This session makes them one.

**CU1 — the divergence, traced and reproduced.** Two axes:

1. **Duplicated capability resolution.** `solver_builder._eligible_resources` and
   `schedule_assembler._eligible_resource_ids` were byte-for-byte hand-copies of
   the same explicit_set/capability uuid5 resolution — "mirrors" by comment, not
   by construction. (A *third* copy, `planner._eligible_resource_ids` over
   OperationSpec, is a separate allocation concern — noted, left for a later
   unification; it is neither the Tier-0 payload nor the solver's op_assign.)

2. **Raw eligibility vs COMPILED eligibility — the real gap.** The payload
   advertised the RAW capability set (== `var_map.op_eligible`, set *before* any
   prune). The pin binds `var_map.op_assign`, the COMPILED set, which the builder
   prunes further: a **resumable** op drops a capability-eligible resource with no
   in-horizon calendar window that could finish it (the chunk-slot prune —
   `_feasible_window_range is None`); a **WIP** op (`complete`/`in_progress`) gets
   no free literal at all. So `payload_eligible(op) ⊇ solver_literals(op)`,
   strict-superset-possible → Tier-0 could green a row the pin then silently
   skips.

   **Empirically:** a probe built the model AND the payload for every op on
   `multi_route_distinct` (10 ops) and `busy_board` (90 ops) and diffed
   `eligible_resource_ids` against `op_assign` keys: **0/100 diverge** — both
   fixtures are `splittable=0, wip=0`, so the raw and compiled sets coincide. The
   divergence is **latent, not active on the demo path**. It was then reproduced
   deterministically on a constructed resumable op eligible on two machines, one
   with a dead in-horizon calendar: the payload advertised BOTH, the solver built
   a literal for only the live one. So the class is real; the pilot's data
   (splittable ops, WIP) would surface it.

**The original live case — was ORD-000002's RES002 row green, amber, or dim?**
Determined by evidence, not memory. On `busy_board` (the feel fixture), ORD-000002
is two ops on **disjoint** machine sets — the RES001 op is eligible on
{RES001, RES003, RES005}, so **RES002 is capability-DIM for it** (correctly, and
its op_assign has no RES002 literal — payload and solver AGREE it is ineligible).
On `multi_route_distinct`, ORD-000002's op IS eligible on {RES001, RES002}, both
**green/pinnable** — a RES001→RES002 drag there binds honestly and lands on
RES002 (the +0.30% HONEST reproduction from the hotfix). **Neither fixture ever
greens an un-pinnable row.** So the live "wrong machine" symptom was **not** a
Tier-0-vs-solver eligibility-DATA divergence: the data is honest on the demo path.
The mechanism was the pin-skip the 4.0-hotfix already closed (mandatory pin). Note
the corollary the task named: because the RES001 op is correctly DIM on RES002,
any live drop there must be **refused** — and the client `drop()` does refuse
(`if (!t.legal) return returnHome`, before any sandbox/ghost path), so refusal
enforcement is intact in shipped code. 4.0b's job is therefore the **latent**
axis: make it structurally impossible for a payload to advertise a resource the
solver would prune, on any data, and pin a standing guard.

**CU2 — unify: one derivation, two consumers (the narrow waist).** New ortools-
free `src/mre/modules/eligibility.py` is the SINGLE definition of:
`capability_eligible` (the explicit_set/capability resolution, in the solver's
resource-dict order so variable-creation order — and the defaults-reproduce-
baseline gate — is unchanged), `feasible_window_range` (moved verbatim from the
solver: `None` ⟺ a resumable op gets no literal, since the `lo` window always
yields at least one usable chunk slot — the equivalence that lets the payload
re-derive op_assign membership EXACTLY), `flatten_resource_windows` (the solver's
calendar flatten, moved so both sides see identical minute windows), and
`pinnable_resources` (the resources the builder would give a literal + a dim
reason for those it prunes). The Solver Builder now **delegates** all three (the
goldens confirm byte-identical solves). The assembler builds
`eligible_resource_ids` = `pinnable_resources(...)` and carries the SAME prune it
can't offer as truthful `dim_reasons` (`no_calendar_window` / `wip_fixed`). The
two sets are now equal **by construction** — the divergence is structural, not a
promise. Contract **1.3 → 1.4** (additive `OperationInteraction.dim_reasons`;
`eligible_resource_ids` narrows to the solver-pinnable set — byte-identical on
the demo fixtures, strictly-never-wider elsewhere). The cockpit surfaces the new
reasons: `tier0.js` reads `dim_reasons` for a dimmed row; `shade.js` carries the
row's own reason; `controller.js` REASONS map renders "no open calendar window
this horizon" / "this operation is already running and can't be moved."

**CU3 — the standing guard.** `tests/test_eligibility_consistency.py`: (slow) for
a SOLVED schedule, every scheduled op's payload `eligible_resource_ids` **equals**
its `op_assign` literal set — asserted on `multi_route_distinct` AND `busy_board`
(the consistency contract as a permanent regression); (fast) the constructed
resumable case — the solver prunes the dead machine, `pinnable_resources` prunes
it too, and the payload names it `no_calendar_window` (never greened); plus the
shared capability resolver's unit cases (order + fallbacks). And a cockpit
row-type test (`legality.spec.mjs`): a drop on each of the three row kinds —
eligible / capability-ineligible / **solver-pruned** — behaves per R-DP2
(**takes / dims / dims**), the pruned row dimmed with its truthful reason and its
drop refused. (The constructed dates derive from `now()` so they never rot — the
3.3b `datetime.now()` horizon trap, avoided.)

**Result.** Non-slow Python **1092 passed** (+6; `test_declared_but_unread`
consumer list gained `eligibility.py`), + the slow eligibility guard on both
fixtures; solver goldens byte-identical (delegation only); planner_edit/sandbox/
forced_alternatives slow ladders green (R-DP1 accept guard intact); **cockpit JS
47/47** (was 46). See docs/07 v2.15. Lesson: when two layers must agree on an
invariant, do not have each *compute* it — give them ONE function to *call*. A
hand-mirrored copy is a divergence with a delay; and a payload that reports RAW
capability while the pin binds the COMPILED set is that same delay wearing an
"eligible" label.

### 2026-07-16 — Session 4.0c: the silent accept (an accept that 409'd on a storage limit, rendered mutely)

**Live specimen.** Schedule `ea1a42f0` in Daryn's `_data` root: a sandbox verdict
succeeds (+0.70% proven, ORD-000004 RES001→RES003 on `multi_route_distinct`),
Accept is pressed, the bar returns to RES001 with **no visible error** and the
**same schedule id** — no new version bound.

**CU1 — diagnose against the live registry FIRST (before any fix).** Three
suspects were named in order: (1) accept 409ing on the 4.0-hotfix's post-solve
post-condition via a rounding/serialization mismatch (pinned vs solved start);
(2) accept failing for another reason, rendered mutely; (3) accept succeeding +
rebind not firing. The registry settled it:

- **`ea1a42f0` has NO child** (nothing lists it as `parent_schedule_id`) and it is
  `proposed`, not superseded — so the accept did **not** create a version and it
  was **not** a supersede-409. **Suspect (3) refuted** (no child ⇒ nothing to fail
  to rebind).
- The `runs` table is the smoking gun: **eleven** `kind=accept` runs off
  `ea1a42f0`'s run, **every one `status=failed` with the identical error**
  `FileNotFoundError: [WinError 3] The system cannot find the path specified`.
  Not the post-condition RuntimeError, not an eligibility refusal — a **filesystem
  error**. **Suspect (2) confirmed; suspect (1) refuted.**

**The mechanism, reproduced deterministically.** `ea1a42f0`'s snapshot id is
`snap-be998b25--edit-…--edit-3e7811a6` — a chain of **seven** `--edit-<hash>`
segments, 118 chars, because `apply_planner_edit` minted each accepted child as
`f"{base_snapshot_id}--edit-{hash}"`, appending unboundedly. On Windows the
snapshot directory path
`…\_data\runs\<uuid>\snapshots\<child-id>\entities_serviceoutcome.jsonl` crosses
**MAX_PATH (260)** at that depth; the child derive (`shutil.copy2` /
`copytree`) fails with `FileNotFoundError [WinError 3]`, `_execute_accept` catches
it and raises `HTTPException(409, "accept failed: …")`, and — pre-4.0c — the
cockpit's `accept().catch` called `returnHome(reason, keepCard=false)`, which
**hid the card and the reason tip**: the bar snapped home with nothing on screen.
A committed-looking edit vanishing silently. Reproduced at the real `_data` path
length (a temp-dir repro passed — its shorter prefix stayed under 260, which is
exactly why this never surfaced in tests).

**Named plainly, per the close instruction: the 4.0-hotfix's own guard did NOT
cause this.** The post-solve R-DP1 post-condition already compares in the
canonical minute grid (`solve_values.op_start_minutes`, integer
`solver.Value()`, vs the integer `pin_start_min`) — no datetime is re-serialized,
so there is no rounding seam for it to 409 on. The live 409 came from storage,
upstream of the check. (Hardened anyway: the solved start is coerced `int()` with
a comment fixing the invariant, so no future float can introduce a seam.)

**CU2 — the root-cause fix: bound the snapshot-id growth.** New
`_edit_snapshot_id(base, edit_hash)` (`planner_edit.py`): shallow chains keep the
readable `<base>--edit-<hash>` lineage; once that would exceed
`_MAX_EDIT_SNAP_ID_LEN = 90` the ancestry **collapses** into a stable
digest — `f"{root}--chain-{sha256(base)[:12]}--edit-{hash}"`, where `root` is the
id up to the FIRST edit/chain marker (so a second collapse does not accumulate
`--chain-` segments — the id stays fixed-width however deep the chain goes). The
digest is over the exact parent id we derive from, so it is deterministic
(idempotent re-accept) and collision-free per lineage. Every base is thereafter a
root or an already-bounded child, so **no fresh chain can ever reach MAX_PATH**.
The lineage is not lost — it lives in the registry's `parent_schedule_id` chain.
(`ea1a42f0`'s already-118-char id is a pre-existing casualty the bound cannot
retroactively shorten; accepting on it still fails — but now **loudly**, see CU3.)

**CU3 — a refused accept must be LOUD (R-M1a), regardless of cause.** The
cockpit's `accept().catch`, on a non-superseded failure, now renders an **authored
refusal on the delta card** — `card.showRefused({reason})`: "Edit not saved · the
plan is unchanged", the honest sentence "This placement couldn't be committed —
the schedule of record still stands. Nothing was changed.", and the raw server
reason kept as a muted `.dc-detail` (never hidden) — then snaps the bar home as a
rejection with `keepCard=true` so the card stays. The card wears a `refused`
class: a rejected border + a one-shot `card-refuse` shake (reduced-motion drops
the shake, keeps the text). A silent bar-goes-home on a committed gesture is no
longer reachable.

**CU4 — the dev question-ledger refusal panel (4A.1) was occluding ask.** It was
`position: fixed; right; bottom; z-index 40` — floating over the ask composer
(input + buttons) bottom-right. Now docked bottom-**left** (board side, never over
ask), **collapsible**, and **collapsed by default** (header only; the body —
including the "no dev ledger (set MRE_DEV)" empty state — lives inside the docked
panel and loads lazily on first expand). DEV-build-only, unchanged.

**Tests.** `tests/test_edit_snapshot_id.py` (fast, pure-string): shallow lineage
preserved; a 7-deep chain (the `ea1a42f0` shape) stays ≤ cap with root + fresh
hash visible; a **50-deep** accept-on-accept chain never crosses the cap (this
caught a real bug mid-session — the first collapse scheme re-accumulated
`--chain-` segments); determinism + per-parent distinctness. `gesture.spec.mjs`:
"a refused accept is LOUD" — a `page.route`-mocked 409 accept renders
`.delta-card.refused` visibly with the authored line + the raw reason, and the
cockpit stays bound to the base id (nothing committed). **Non-slow Python 1096
passed** (+4); slow `planner_edit` **10/10** (real chained accepts, bound in
effect); **cockpit JS 48/48** (was 47). See docs/07 v2.16. Lesson: a snapshot id
that embeds its whole ancestry is a path-length bomb on a chained-edit workflow —
bound the name, keep the lineage in the registry; and a hard failure surfaced
through `returnHome(reason, keepCard=false)` is a silent failure — enforce, or
refuse loudly, but never drop the reason on the floor.

### 2026-07-16 — Session 4.0d: MAX_PATH survives the bound (the 4.0c fix was validated in a short prefix)

**Live report.** Post-4.0c, on Daryn's real stack, **every** accept still failed
`FileNotFoundError [WinError 3]` — now even on a **fresh schedule with a depth-1
edit**, not just the pre-existing 118-char `ea1a42f0`. The 4.0c bound capped chain
GROWTH, but the fix was validated in a short temp-dir prefix, and Daryn's real data
root (`…\OneDrive\Documents\PythonProjects\mre\_data\…`) spends ~130 chars before
any snapshot id ever appears. **The blind spot named plainly:** the 4.0c cap of
**90** chars was calibrated against that short test prefix. At Daryn's real
~130-char prefix a chain grown to *near* the cap (an id in the ~75–90 range, which
the collapse deliberately allows) plus `\entities_serviceoutcome.jsonl` (30) still
crosses 260 — the cap was chosen without accounting for the real prefix the temp
tests never had. Reproduced deterministically at a padded ~136-char prefix: a naive
write at 265 chars fails `FileNotFoundError`; the same write through a `\\?\`
extended-length path succeeds (`os.makedirs`/`open`/`shutil.copy2`/`copytree`/`glob`
all honor the prefix — `pathlib.Path.mkdir(parents=True)` does NOT, it walks up to
`\\?\C:` and raises `WinError 123`, so the seam uses the low-level calls).

**Fixed in order of preference, all three (defense in depth):**

**Fix 1 — long-path support at the filesystem seam (the correct fix on modern
Windows).** New `src/mre/modules/longpath.py` is the SINGLE seam through which the
snapshot/run store does disk I/O. `extended(path)` returns the `\\?\`-prefixed
absolute string on Windows (idempotent; UNC → `\\?\UNC\…`; a no-op pass-through on
every other platform), lifting the 260-char limit (paths to ~32767). It exposes
`makedirs`/`open_`/`write_text`/`read_text`/`exists`/`copy2`/`copytree`/`rmtree`/
`glob`/`child_dir_names`, and `SnapshotStore`, `registry.prepare_out_dir`, and the
accept/scenario `copytree` + `_persist_document` in `app.py` route through it. The
snapshot tree (where the accept died) is now MAX_PATH-proof regardless of data-root
or chain depth. (Named residual: the shallow run-dir writers — the Reporter
evidence sink, the certificate writers — are not on the seam; at a data root beyond
~200 chars they too would need it. They are safe at Daryn's real depth and flagged
by fix 3, not silently left.)

**Fix 2 — short, opaque snapshot directory names (shrink the budget anyway).**
`_edit_snapshot_id` no longer embeds any lineage. It is now a fixed-width
`snap-edit-<sha256(base|hash)[:12]>` = **22 chars**, deterministic per
(base, edit_hash) and distinct per parent; the parent chain lives solely in the
registry's `parent_schedule_id`. The on-disk snapshot name is therefore tiny and
constant however deep the edit chain grows — the 4.0c "grow then collapse" scheme
(and its 90-char ceiling) is gone. `_MAX_EDIT_SNAP_ID_LEN` is repurposed from a cap
into a guaranteed ceiling (32) the tests assert the fixed-width id stays under. The
4.0c collapse recursion is moot (no growth to collapse).

**Fix 3 — a boot / `/health` path-budget tripwire.** `longpath.path_budget(root)`
computes the worst-case snapshot path length under the data root and reports
`status` (`ok` / `at_risk` when it exceeds the classic 260 even with a bounded id),
`long_path_mitigation` (the seam covers it), and the numbers. `create_app` **warns
loudly at startup** when a root is `at_risk` (mitigated, but dangerously deep —
shorten it), and `/health` carries the whole block. A path-length problem is never
again discovered only at accept time.

**Why the arithmetic works now.** At Daryn's real ~130-char prefix: 4.0c near-cap
id (~88) → 130+1+88+30 = **249…268** (crossed on the deeper chains); 4.0d opaque id
(22) → 130+1+22+30 = **183** (fix 2 alone clears it). And even a pathological
>200-char prefix that would push the 22-char child past 260 is defeated by fix 1's
`\\?\` seam. Belt and suspenders.

**Tests — at a REALISTIC prefix, so the temp-dir blind spot cannot recur.**
`tests/test_longpath.py` (fast): `extended()` prefix/idempotency/UNC/pass-through;
a **SnapshotStore write→derive→read round-trip at a >260-char prefix** with a naive
**negative control** proving the limit is real (the seam succeeds where the naive
path raises); `path_budget` ok vs at_risk. `tests/test_edit_snapshot_id.py`
rewritten for the opaque scheme (short/fixed-width/opaque; a 50-deep chain stays
one constant length; deterministic + distinct per parent; a realistic-prefix
under-260 assertion). `tests/test_planner_edit.py` gains
`TestAcceptAtARealisticDataRootPrefix` (**slow, end-to-end**): a real solve + accept
under a data root padded so the prefix reaches ~160 — deep enough that a 4.0c-era
~88-char id WOULD have crossed 260 (asserted in the test) — succeeds and lands on
the pinned resource+start. `/health` gains a `path_budget` assertion. **Non-slow
Python 1103 passed** (+7, 0 failed); slow `planner_edit` **11/11** (+1). Cockpit
untouched (backend-only), JS stays 48/48. See docs/07 v2.17. Lesson: a bound
validated against a short test prefix is a bound with an unmeasured margin — pin the
budget to the REAL deployment path length, and prefer making the limit not exist
(`\\?\`) over racing it with an ever-tighter cap.

### 2026-07-17 — Session 4.0e: accepted placements are standing commitments (R-DP8)

**The observed revert, named.** Live on the gesture surface: an accepted, then
PUBLISHED, edit was silently reverted by the NEXT edit's re-solve. The delta card
was honest about it — it listed "ORD-000003 RES002→RES001 −1440min" as a
*consequence* of the new drop — but a placement the planner already committed
should not be movable at all. The culprit: the accept/sandbox re-solve pinned only
the ONE op being dropped; every prior accepted pin was free again, so the optimizer
did exactly what it is paid to do and undid a cost-neutral cross-machine move to
recover a few dollars. A commitment that survives only until the next solve is not
a commitment.

**The ruling (R-DP8), transcribed.** An accepted edit's pin persists in the
schedule lineage as a STANDING constraint — compiled into EVERY subsequent sandbox,
accept, and scenario solve of that lineage — until explicitly released. An accepted
placement is a commitment WITH AUTHORITY (the `planner_edit` Decision), not a
one-solve preference. Rationale: the planner must never have to re-defend a decision
they already made; a cost-neutral edit is exactly the kind the optimizer will
otherwise silently undo. Release is a future explicit verb (`unpin`), named as a
carry-forward, not built now.

**CU1 — persistence.** Standing pins live in ONE place structurally: a new
`schedules.pins_json` column carries the CUMULATIVE lineage pins of each version —
every accepted `(op, resource, start)` from the root down to and including this
version (empty on a root solve). An accept composes the new set from the base's
(`standing_pins.compose_lineage_pins`: the drop's op re-committed in place, or
appended if fresh — order-stable, never duplicated) and stores it; a migration
(`Registry._migrate`) ALTERs the column into pre-4.0e databases so old rows read as
no-pins. Publish/supersede are untouched — the pins belong to the lineage row, not
the pool, so they carry through both. Every subsequent sandbox/accept/scenario
solve gathers the base version's pins (`Registry.schedule_pins`) and compiles ALL
of them as hard constraints alongside the new drop. **The single seam:**
`src/mre/modules/standing_pins.py` — the primary drop AND the standing pins go
through the SAME `apply_pin` (both axes mandatory, `PinUnsatisfiable` on a missing
start var / literal — never skipped-and-vouched, the 4.0-hotfix lesson), so the two
can never diverge in how they bind (the 4.0b "give the layers ONE function to call"
discipline). `sandbox.py`, `planner_edit.py`, and `scenario.py` all delegate to it.
**Conflict handled honestly:** a drop that is INFEASIBLE against the standing pins
returns a verdict that NAMES the blocking commitment — `detect_conflict` reports a
conflict ONLY on a provable same-resource interval overlap (durations from the
new `VariableMap.op_durations`, the solver's own minute durations), so an
infeasibility that is actually precedence/calendar is never mis-blamed on a
commitment — rather than quietly sacrificing the older pin. In a scenario the pins
are best-effort (a what-if may legitimately re-plan an op away; the applied count
lands in evidence as `standing_pins_applied`, never silent).

**CU2 — visibility.** Schedule contract **1.4 → 1.5** (additive
`AssignmentBlock.standing_pin`): the assembler marks every op carrying a standing
commitment from the version's cumulative pins. The cockpit renders a subtle,
PERSISTENT standing-pin marker on those bars (a thin amber left edge + faint ring,
tokenized `--standing-pin-*`) — deliberately quieter than, and distinct from, the
transient green pin-lock of a just-accepted drop (which animates then fades). And
the delta card can NEVER list a standing-pinned op as a moved consequence: it is
STRUCTURALLY excluded in `_moved_set` (`exclude_ops`, the freshly-dropped op
exempt) and in the cockpit's ghost-drop `movedSetFromDoc` — not filtered
downstream, removed at the source. (A pinned op cannot move anyway, so it would not
appear; the structural exclusion is the belt to that suspenders, and the CU2
guarantee in code.)

**CU3 — the regression that was missing.** `tests/test_standing_pins.py`: fast
units for the shared seam (pin accessors reading both record shapes, lineage
composition, apply/skip, conflict overlap-detection, moved-set exclusion) + registry
pins round-trip + the pre-4.0e migration; and the two-edit chain END TO END (slow,
`multi_route_distinct`) — edit A a cost-neutral CROSS-MACHINE move (the kind the
optimizer reverts) accepted + PUBLISHED, edit B accepted on a different op → assert
A's placement is UNCHANGED in B's version, A stays `standing_pin=True`, and A's op
appears in NO moved-set of edit B's `planner_edit` Decision; plus a drop that lands
ON a standing commitment's slot is refused (sandbox infeasible, accept 409, base
stands). The cockpit harness drives the same flow visually
(`gesture.spec.mjs`): edit A accept→publish, edit B accept → A's committed row is
held through B's rebind and A's bar wears the standing-pin marker (the fixture
server composes every ancestor pin into `GET /schedule` and flags them, exactly as
the real assembler does). **Non-slow Python 1118 passed** (+15, 0 failed) + slow
`standing_pins` **2/2**, `planner_edit`/`sandbox`/`scenario` **55/55**,
`forced_alternatives`/`eligibility`/`api_endpoints` green, solver goldens
byte-identical; **cockpit JS 49/49** (+1). See docs/07 v2.18. Lesson: a hard
constraint that lives for exactly one solve is a preference; a commitment must be
COMPILED into every solve of its lineage, held in the registry, and structurally
un-moveable — the optimizer will otherwise, correctly and quietly, undo the very
decisions the planner made by hand.

### 2026-07-17 — Session 4.1: light theme as the shipped default; theme as a first-class token dimension

**Product decision (Daryn's charter, recorded as ratified): LIGHT IS TRUST.** The
dark cockpit "tried too hard to be relevant" — it signalled *developer tool*. This
product's visual language is the DOCUMENT, the LEDGER — dark ink on light paper;
professional, calm, modern through restraint. **Light is now the shipped default;
dark becomes an option.** Light is a *designed* theme, not an inversion of dark.

**CU1 — theme architecture.** `src/cockpit/src/tokens.css` split into a STRUCTURAL
layer (typography, spacing, geometry, radii, motion TIMING — durations/easings/
amplitudes — and the feel-panel opacity multipliers; all theme-invariant) plus two
COLOR files selected by a `data-theme` attribute on the document root:
`theme-light.css` (`:root, :root[data-theme="light"]` — declared for a bare `:root`
too, so the board renders light before any JS runs, no flash on the default path)
and `theme-dark.css` (`:root[data-theme="dark"]`, equal-specificity attribute
selector, defined later → cleanly overrides). Nothing in `tokens.css` carries a
color; every color lives in exactly one theme file. Semantic ALIASES that are pure
references (e.g. `--voice-rec-fill: var(--bar-late)`) stay in the structural layer
and resolve lazily against the active theme. One chrome toggle in the top strip
(shows the theme you'd switch TO); a no-flash inline `<head>` script stamps the
attribute from `?theme=` / `localStorage` before first paint; `main.js` keeps it in
sync with the URL + storage. Theme choice is a **tier-2-class preference** (a
per-deployment default when that layer lands; a URL/config param + the toggle for
now). **The feel panel's visual knobs write to the ACTIVE theme** — the opacity
multipliers mirror to `:root` inline and only one theme renders at a time, so a
re-tune lands on whatever theme is showing; semantic/motion tokens stand across it.

**CU2 — the light theme, designed (not inverted).** Warm ivory PAPER background
(`#f6f4ef`, not `#fff` glare); dark-slate ink (`#23262d`); a warm-grey ramp for
chrome/recess/hairlines; soft shadows (restraint on paper). **The lateness palette
re-chosen colorblind-safe (deuteranopia checked on the red/amber pair)** via THREE
redundant cues: (1) on-time = BLUE (`#2f63bd`) — unambiguous vs red/amber for
red-green CVD; (2) tight (`#d98a2b`, a LIGHT warm orange) vs late (`#b5271e`, a
distinctly DARKER red) separated by LIGHTNESS, which survives the deut simulation
where both trend to brown; (3) INK POLARITY as a redundant channel — tight carries
DARK ink, late carries WHITE ink, so the two read apart even under full color loss.
All bar-label ink meets WCAG AA on its fill. Shading re-tuned for paper (dim = a
cool grey VEIL that darkens the forbidden zone; green = a legal tint) — Daryn's
**dim-dominates-green verdict carries as SEMANTICS**; the opacity multipliers
re-tune per theme at the feel panel. Ghosts/traces redrawn (a dark ghost-tag chip
keeps prices legible over the busy board). **The tentative bar is the one place the
carry ink had to become theme-aware:** the hatch used to sit on a transparent
backing with white ink — invisible on paper — so 4.1 added `--carry-ink` /
`--tentative-ink` / `--tentative-backing` tokens; on light the hatch sits over a
translucent PAPER backing (reads unmistakably NOT-YET-REAL) with DARK ink (legible).
Closures visible without murk; the amber STANDING-PIN marker vs the transient green
pin-lock both re-tuned to read on paper; the refusal card's authored-reason
treatment, legend, cards, ask panel, ledger dock all carry through the same tokens.
**Dark theme kept working — its pre-4.1 colors moved VERBATIM under the selector;
no design effort spent improving dark this session (the design went into light).**

**CU3 — contrast pass, both themes + the harness parametrized.** Micro-chip
typography bumped for AA (the smallest chip text sat at 9px below the contrast some
carried → `--fs-2xs` 10px, `--fs-xs` 11px, register chip → semibold). The Playwright
harness is now **parametrized on `data-theme` via projects**: a theme-free `logic`
project (the pure-JS Tier-0 legality tests) plus `light` and `dark` projects that
run EVERY rendering spec (cockpit/gesture/rehearsal) — each boot appends
`&theme=<project theme>`, so the **C1 label-vs-bar drift regression is asserted per
theme**; screenshots + the rehearsal report are suffixed by theme (`shots/` is
gitignored). A new `cockpit.spec` theme test asserts light is the default (fresh
context, no stored pref), the chrome toggle flips the attribute + palette (the
paper base is far brighter than the dark base — a designed theme, not a tint), and
the chosen theme rides in the URL. **Cockpit JS 94 passed** (logic 6 + light 44 +
dark 44; was 49 single-theme), C1 drift green on both themes. Python untouched
(frontend-only): non-slow suite green as a regression guard. Backend/contracts/
solver unchanged. See docs/07 v2.19. Lesson: a theme is a token DIMENSION, not a
palette swap — split structural from color, let one attribute select, and the one
place a hard-coded `ink-inverse` hid (the tentative hatch's white label) is exactly
where an inversion would have failed silently; design the light theme, don't invert
the dark one.

### 2026-07-17 — AI-track Session 4A.1b: the ask endpoint 500'd with a real API key (mocked fail-closed ≠ real-path fail-closed)

**The gap, named plainly.** Session 4A.1 shipped "fail-closed armor" over the LLM
interpreter and renderer, and its tests proved it — but every one of those tests
injected a **mock client** (`_client=…`), so the REAL construction path
(`anthropic.Anthropic(...)`) and the REAL call site (`_call_llm`) were never
exercised. That was the named CI caveat ("no ANTHROPIC_API_KEY … the real-key path
is untested"). What lived in the gap: with `ANTHROPIC_API_KEY` set and the DEV
build's `llm: true`, the **taxonomy-shaped** question "why is ORD-000004 on
F001-RES002?" — which routes DETERMINISTICALLY — returned **HTTP 500** on `/ask`.
Mocked fail-closed is not real-path fail-closed.

**CU1 — diagnosis (reproduced, layer named).** Reproduced with the real SDK
(anthropic 0.116.0): `anthropic.Anthropic(api_key="…invalid…")` does **NOT** raise —
it builds a client; a bad key surfaces only on the first CALL. That call,
`self._client.messages.create(...)` inside `LLMRenderer._call_llm`, raises
`anthropic.AuthenticationError` (an `APIError`, i.e. a **non-`ImportError`**
exception), and **`render()` had no try/except around it** — so it propagated
straight out of the SYNCHRONOUS `/ask` handler → 500. The layer is therefore
**response/request execution in the renderer**, not construction and not the
interpreter: `LLMRenderer.__init__`'s `except ImportError` was mistaken for a full
seal, when the hazards are runtime (auth, connection, rate-limit, not-found,
overloaded) plus response PARSING (`response.content[0].text` → `IndexError` on an
empty/non-text block). Crucially, a taxonomy question routes deterministically but
still hits the LLM at **render** time (testimony is LLM-prettified) — so the
ordering guarantee has to cover rendering, not just classify-vs-interpret. The
interpreter itself was already runtime-safe (`interpret()` returns `None` on any
exception); only its CONSTRUCTION shared the too-narrow `except ImportError`.

**CU2 — the armor sealed structurally (defense in depth).** (1) The renderer is now
the seal: `LLMRenderer.render`, `_render_register`, and `render_judgment` each wrap
the ENTIRE LLM-touching body (prompt build + `_call_llm` + validation + regen) in
one `try/except Exception` that degrades to the deterministic TEMPLATE via a single
`_template_fallback` target — so **any** failure (import, network, auth, parsing,
validation) yields an honest `[rendered by: template — LLM error: … ]`, never a
raise. (2) Construction of both `LLMRenderer` and `Interpreter` broadened
`except ImportError` → `except Exception` (a malformed proxy env / an eager-
validation SDK change can no longer propagate). (3) The API `/ask` path adds the
outer belt: `_answer_question` routes inside a guard that, on any routing raise,
re-routes DETERMINISTICALLY (interpreter off, ledger not double-written) and logs
`EVENT ask.llm_degraded`; rendering goes through the new `_render_fail_closed(...)`
helper — the SINGLE render seam — which on the LLM path degrades to the template +
the same logged Event. A 5xx from the AI stack is no longer reachable.

**CU3 — the ordering guarantee, as a test.** `test_ask_chain_api.py`
`TestAskFailClosedWithRealKey` drives the endpoint with a genuine (invalid) key so
the interpreter AND renderer construct for REAL, then injects the three modes at the
call seam — an injected auth failure, a garbage (invalid-value) response, a raised
exception — each asserting **200 + `[rendered by: template]`**. The ordering test
monkeypatches BOTH `Interpreter.interpret` and `LLMRenderer._call_llm` to raise and
asserts the taxonomy question still reaches `route == "late-orders"`,
`source == "deterministic"`, and renders (template) — deterministic answers are
unbreakable by anything in the AI stack. Fast unit coverage in
`test_render_fail_closed.py` exercises the same three modes plus a malformed-object
parse error, the register path, and a construction-raise, all on the unmocked
renderer (real `anthropic.Anthropic` build).

**Result.** Non-slow Python green (was 1118 before this session's additions) +
`test_ask_chain_api.py` 10/10 slow. Frontend untouched (backend-only). See docs/07
v2.20. Lesson: a fail-closed guarantee proved only against a MOCK is unproven —
mock the transport at the seam, but exercise the real construction and the real call
site, or the one exception the mock never throws is exactly the one that reaches the
user as a 500. And a deterministic route still renders through the LLM: seal the
RENDER path, not just the router.

### 2026-07-17 — AI-track Session 4A.1c: the testimony validator passed FABRICATED record citations

**The hole, from screenshots.** LLM-rendered answers footnoted records that do not
exist: `[record: Nothing scheduled for all]` and `[record: evidence_chain_001]`.
The 4A.1 testimony validator (`_validate_testimony`) checked four things —
timestamps, time-unit numbers, machine names, and that SOME factual sentence
carried a footnote — but it **never checked that a cited record id is REAL**. A
model that invented an id-shaped citation, or stuffed header prose into a
`[record: …]`, sailed through. Separately, "is there a better schedule" answered
with PROSE (a schedule listing) instead of a refusal.

**Issue 2 — traced.** `classify("is there a better schedule")` matches the BARE word
`schedule` in `_SCHEDULE_TRIGGERS` → routes to the schedule LISTING → renders the
plan as prose. It is not an unsupported question falling through to the interpreter;
it is a **deterministic mis-route** — an optimality question ("does a BETTER plan
exist", a re-optimization/what-if the deterministic surface cannot answer) swallowed
by a listing trigger. And when the listing is empty, the header text "Nothing
scheduled for all" became the LLM's fabricated citation — the two defects are the
same root: an unresolvable question reaching the LLM renderer with an empty/garbage
evidence chain.

**Fix A — every citation must name a real record.** `_build_prompt_material` now
also returns `known_records` = the real `record_id`s on `bundle.ordered_records`;
`_validate_testimony` gained rule 5: every `[record: X]` in the answer must be a
prefix of a real id (the template footnotes an 8-char prefix, so the model may cite
the prefix), else `"fabricated record citation 'X'"` — which, like any validation
issue, triggers one regeneration and then the deterministic **template fallback**.
The bare `?` placeholder (template's missing-id marker) is exempt (not a claim).

**Fix B — a no-evidence bundle never reaches the LLM.** `LLMRenderer.render` now
short-circuits to the template body BEFORE any LLM call when
`not bundle.ordered_records`: an honest refusal / near-miss / clarify (authored
copy) and an empty schedule listing have nothing to testify FROM, so the model
could only fabricate. This closes the "empty/garbage evidence chain reaches the LLM"
path for every such bundle in one rule; the authored header IS the answer.

**Fix C — an optimality question is not a schedule listing.** New
`_OPTIMALITY_TRIGGERS` (`better`, `best`, `optimal`, `improve`, `cheaper`,
`cheapest`, `worse`, `suboptimal`, `more efficient`); the schedule-listing branch in
`classify` fires only when NO optimality word is present. "is there a better
schedule" now falls through to `unsupported` → the honest refusal / interpreter
bridge, and (by Fix B) that refusal renders verbatim, never as LLM prose.

**Tests.** `test_testimony_validation.py` (fast): the two live symptoms rejected
(id-shaped + prose-as-citation → template), a real-prefix citation passes, the
`?` placeholder is exempt, and — Fix B — an empty-evidence / refusal bundle is
rendered without EVER calling the client (a call-counting fake asserts
`calls == 0`). `test_interpreter.py`: "is there a better schedule" classifies
`unsupported` (a normal `schedule` listing still routes) and refuses
deterministically. `test_ask_chain_api.py` (slow): end-to-end, the better-schedule
question returns a refusal citing NO records, and an injected fabricating LLM
(real key + `llm:true`) degrades to the template with no live `[record: …]` footnote
surviving. The 14 `test_explainer.py` validator call sites updated to thread
`known_records` (the full-`render()` tests already cite real ids, so they still pass
through the LLM). **Non-slow Python green (+ the new fast suites)** +
`test_ask_chain_api.py` 12/12 slow; frontend untouched. See docs/07 v2.21. Lesson:
"cite a record" is not "cite a REAL record" — validate the id against the bundle,
and never hand the model an empty evidence chain, because the only citation it can
then produce is a fabricated one.

### 2026-07-17 — Session 4.2: planner surface pass 1 (read layer only)

The first pass at making the cockpit read like a PLANNER's board, not a demo
Gantt — capacity state, time anchors, hover intelligence, row intelligence, and
operation anatomy — with a hard rule: **render only what the model can source
truthfully.** No interaction changes, no solver changes; everything below reads
existing data (plus three additive contract fields the data already justified).

**Scope discipline (the read-layer test).** Unplanned / observed downtime is OUT
— there is no observed-actuals doorway yet, so a machine that broke has no
truthful place on this board (rendering it would be inventing state). The
background architecture RESERVES the slot; the doorway debt is named below per
R-AI1. Everything shipped is derivable from the canonical model: calendar
windows + their exception reasons, assignment chunks + setup phases, service
outcomes, and the flattened windows the solver's eligibility already computes.

**Contract 1.5 → 1.6 (additive, three fields the data already had).**
- `CalendarWindow.reason` — a closure/overtime window now carries its
  calendar-exception reason (planned_maintenance / holiday / breakdown /
  overtime). The assembler was collapsing every closure to `kind="closure"` and
  DROPPING the reason; 1.6 keeps it, so the board shades a planned-maintenance
  closure distinctly from generic off-shift and the downtime hover names it.
- `ServiceOutcomeBlock.customer_name` / `quantity` (+`quantity_uom`) — the
  external customer (resolved through the identity map, never a UUID on screen)
  and the demand quantity, for the job-card hover. `Demand.quantity` is a
  `Quantity {value, uom}` (not a scalar) — surfaced as both.
- `ResourceLane.booked_through` / `next_open_gap` — per-row absolute facts
  computed server-side over the SAME flattened windows the solver's eligibility
  uses (new `row_intelligence.py`, built on `eligibility.flatten_resource_
  windows`), so a row that reads "booked through Thu" is booked through Thu by
  canonical minutes, not by anything rendered.

**CU1 — capacity-state backgrounds + shift structure.** Per-row banding for
off-shift / closure / planned-maintenance / overtime (premium) / open-idle,
distinct on BOTH themes (tokenized, feel-tunable). Off-shift = the complement of
every declared window in the data span; open-idle = regular capacity minus
booked work; closure/maintenance/overtime come straight from the 1.6 window
kind+reason. Shift boundaries render as subtle ticks in the markers overlay. All
pure-computed in `legality/capacity.js`.

**CU2 — time anchors.** A now-line from the run's REFERENCE DATE (the 3.3b
epoch), never wall clock — absent (not faked) when the run is "now"-anchored
(reference_date null), because a wall-clock "now" on a fixed-epoch schedule is a
lie. Due + release markers render for the SELECTED/hovered order only (release
from the Tier-0 `earliest_start`). All in one `markers.js` overlay tracking vis
pan/zoom at ~0px drift (the C1 discipline, extended).

**CU3 — hover cards, planner-voiced.** A job card (order, qty, due, customer,
routing position, late/tight status, standing-pin state) and a downtime/closure
card (which calendar state, its reason, when the row reopens), driven by vis's
own hit-test. External refs everywhere; a UUID never reaches the card.

**CU4 — row intelligence.** Per-row utilization % over the VISIBLE window
(recomputed live as the planner pans), booked-through, and next-open-gap — all
from the same window arithmetic, never the rendered DOM. `row_intelligence.py`
is the canonical definition; `legality/rowstats.js` is a byte-for-byte port; the
two are pinned together by shared numeric fixtures
(`fixtures/rowstats_cases.json`, asserted from BOTH sides). A subtle row-label
strip carries it.

**CU5 — operation anatomy.** Setup rendered as a distinct hatched leading
portion of a bar (the first visual appearance of setup, from `phases.setup`);
split/chunked ops rendered as linked pieces with a dashed kinship connector
across each pause (they read as ONE job) — WITHOUT disturbing the single-item
identity the drag/citation/rebind paths rely on (single-chunk bars, all existing
fixtures, are byte-unchanged; the split path is additive); the standing-pin
(R-DP8) indicator unified into the commitment marker family.

**Rider.** The dev question-ledger empty state was reworded from the cryptic "no
dev ledger (set MRE_DEV)" to planner-comprehensible copy that names what the
panel IS ("Unanswered-question log (off) — set MRE_DEV=1 in the API environment
to record refusals for review") — its label had confused the person who
commissioned it twice.

**Harness.** A hand-authored contract-1.6 planner fixture
(`tools/build_planner_fixture.py` → `fixtures/planner/`) exercises every read-
layer feature the demo scenarios don't produce (closures, maintenance, overtime,
setup, a split op across a closure, a standing pin, customers/quantities).
`planner.spec.mjs` screenshot-asserts each CU on BOTH themes; `rowstats.spec.mjs`
(logic project) pins the JS port to the shared fixtures. Python: contract 1.6
fields + `row_intelligence` parity (`test_row_intelligence.py`,
`test_schedule_document.py`). **Non-slow Python 1148 passed, 0 failed**;
**cockpit JS 113 passed** (was 94: +10 planner ×2 themes, +9 rowstats logic).

**Question-pathway notes (R-AI1).** Each new surface's AI reach, named:
- downtime/closure cards align with the EXISTING downtime/calendar question
  route (the explainer already answers "why is X closed" style questions);
- **utilization / booked-through / next-gap have NO ask route yet** — you can
  see a row is 90% booked but cannot yet ASK "which rows are overloaded?" This is
  a named debt for AI-track Session 2 (a row-economics question domain), not
  built this session.

**Named debt — the unplanned-downtime doorway.** The capacity-band architecture
reserves the slot for observed/unplanned downtime (a machine that actually broke,
distinct from a calendar-declared closure), but there is no observed-actuals
ingestion doorway (docs/06 has no WIP/actuals downtime channel). Until that
doorway exists, only calendar-declared exceptions carry a reason and only
calendar-declared closures band the board. This is the read-layer's honest edge:
we render what the model knows, and the model does not yet know about downtime it
was not told to plan.

Lesson: a planner's board is mostly ABSENCE made legible — off-shift, idle,
closed, waiting. The discipline that makes it trustworthy is the same one that
makes the answers trustworthy: render only what you can source, and where you
can't (unplanned downtime), reserve the slot and name the debt rather than paint
a plausible lie.

---

## Amendment — 2026-07-18: Session 4B.0 — IDS alternative-resource doorway (per-alternative rates), spec + adapter truth + pipeline proof

Connector-track opener. Design settled in a parallel thread, re-applied to the
live repo here (not merged as external files). The doorway was HALF-built: eligible
*sets* entered through the CSV since Session 3.1, but per-alternative *rates* did not.

**CU1 — adapter truth, established by test FIRST (before any spec edit).** What did
`IDSAdapter` do with repeated `(route_id, sequence)` rows naming different
`resource_id`? Answer (pinned by `tests/test_ids_alternative_groups.py::TestAdapterTruth`):
it grouped them into ONE `explicit_set` OperationSpec over the whole eligible set —
NOT last-wins, NOT two operations, NOT a crash. But the per-operation TIME model
(setup/run) was read from the FIRST row ONLY, so a submitter who gave a distinct
`run_minutes_per_unit` per alternative machine had every non-first row silently
DROPPED — a per-alternative rate never reached the solver. A silent-wrong, now a
standing regression. **And the second CU1 question: does the existing multi-eligible
scenario enter through the CSV doorway or adapter-side construction?** Through the
CSV — the `multi_route` generator writes the rows and `test_multi_route` runs the
full pipeline (generate → gate → adapter → solve). So B2 pipeline-proof for eligible
SETS was NOT one-sided; it was per-alternative RATES that were unproven, and CU4
restores that leg honestly.

**Decision.** (a) Per-alternative `setup_minutes`/`run_minutes_per_unit` are
first-class: captured in `ResourceRequirement.rate_overrides {resource_ref →
{base_setup, run_rate}}` (docs/01 §5.5), the first row the default, any differing
alternative an override; an all-agree group carries an empty map and solves
byte-identically (the no-map guarantee, tested). (b) `setup_family`/`dwell`/
`splittable`/`min_chunk` are STEP attributes of the OPERATION, not the machine —
they must agree across a group; disagreement is a new Tier-2 rule
`ids.alternative_step_attributes_agree` (registry #33, AMBIGUOUS_SOURCE, conditional/
degraded), resolved first-row-wins with a catalog note (note_version 1). (c) The
solver builds PER-RESOURCE durations for a heterogeneous op (a variable-duration
encoding: the end var is linked by each machine`s own optional interval, not a
fixed `e==s+total`); a homogeneous op keeps the exact scalar path untouched, which
is what makes the no-map guarantee hold. (d) The extractor prices the chosen
machine from the solved end−start (already honest) and prices ALTERNATIVES at their
own per-resource duration — reducing exactly to the historical `(alt_rate−rate)×dur`
when durations agree.

**Follow-through.**
- Contracts: `ResourceRateOverride` struct + `ResourceRequirement.rate_overrides`;
  `Operation.resource_setup_durations` / `resource_run_durations` (qty-resolved
  projections, the instance analogue of `run_duration`, derived provenance).
- Adapter groups repeated-sequence rows, first-row default + per-alternative
  overrides; STEP attributes first-row-wins (the gate owns detection — "the gate
  checks; it never repairs").
- Gate: new rule + check (group by (route,seq), compare the four step attrs);
  ids_rules.py registry → 33, coverage anomaly `alternative_step_disagreement`,
  remediation catalog note (cites §5.3).
- CU4 pipeline proof: new `multi_route_rates` generator scenario (per-alternative
  run times through the CSV, EQUAL rates so price is purely duration). The
  counterfactual (`test_multi_route_rates.py`, slow) pins the slow alternative and
  asserts, through a real re-solve + extraction, a duration exactly 60 min longer
  and a strictly higher cost — priced end to end. B2 pipeline-proven, honestly.

**Named carry-forwards (debts, not built).** (1) A `splittable` (resumable) op WITH
rate_overrides uses the scalar default duration — per-resource chunk-slot working
minutes are a follow-up; splittable is a STEP attribute that must agree, and the
CU4 fixture is splittable=false, so the case is latent. (2) A heterogeneous op`s
`var_map.op_durations` scalar (used by setup-transition adjacency and R-DP8
standing-pin conflict detection) is the DEFAULT duration, a representative — pins on
rate-varying ops are not exercised this session. (3) A pre-existing systemic
+1-minute offset on solved op durations (it hits homogeneous ops identically) is
unrelated and untouched; the counterfactual states its invariant as the delta,
which is exact.

Reconciliation note: the parallel design thread targeted "docs/06 v0.4"; the live
repo was ALREADY v0.4, so this lands as **v0.5** (registry v0.3).

Non-slow Python **1160 passed, 0 failed**; slow guards green (multi_route pool +
eligibility_consistency 13/13; multi_route_rates counterfactual 2/2). Goldens
(sample_data schedule.csv + ledger) byte-identical. See docs/06 §5.3 + §4, docs/01
§5.5, docs/05 B2, docs/07 v2.23.

Lesson: a doorway proved for the STRUCTURE (eligible sets) is not proved for the
VALUES that ride through it (per-alternative rates) — read the adapter`s truth
before trusting the claim, and where the two rows disagree on a machine property vs
an operation property, split them: vary the rate, agree on the step.

## Amendment — 2026-07-18: Session 4B.1 — Glass Box instruments (the hand-auditable dataset, sabotage menu, and walkthrough)

Purpose: give Daryn the instruments to verify, at his own pace, that (a) the gate
catches deliberate data defects with the right rule/severity/disposition, and
(b) every placement in the solved schedule traces back to a row he authored —
"read the story of the solve." This session BUILDS the instruments; it does not
run the audit (that is Daryn's, by design). No solver/model/contract changes —
this is a dataset + docs + one dev-script wiring + one standing test.

**CU1 — the glass_box dataset (a story, not a soup).** A HAND-AUTHORED, committed
IDS submission at `datasets/glass_box/` (manifest + the six required CSVs +
`cost_model.json`) — human-readable IDs Daryn can open in Excel and hold in his
head: 15 orders, 5 machines (`CUT-01`, `PRESS-FAST`, `PRESS-SLOW`, `PAINT-01`,
`HEAT-01`), one facility, reference date Monday 2026-01-05, a flat $60/h rate so a
cost difference IS a time difference. It is NOT generator output — it was authored
by hand, borrowing the PROVEN minute values from the generator's narrative
builders (`_apply_bottleneck`'s 470-min contention op, `_apply_overtime_required`'s
600-min-op / 5-weekday-slots economics, the 4B.0 fast/slow-press rate split) so the
stories are reliable, then re-verified by real solve. Each of the seven features is
present EXACTLY ONCE with a nameable purpose: (1) an alternative group with honest
per-machine rates — `RT-BRACKET` seq10 on `PRESS-FAST` (5 min/unit) vs `PRESS-SLOW`
(10), three orders due Monday so exactly one takes the slow press (~$250 more, not
late); (2) a splittable 900-min op (`ORD-03`) that pauses at the overnight closure
and resumes (two chunks, no cost billed to the pause); (3) one order late BY DESIGN
from pure capacity contention (`ORD-04` high-priority holds `CUT-01` Monday, `ORD-05`
standard slips to Tuesday — data clean, cause traceable); (4) a Saturday overtime
window on `HEAT-01` that rescues `ORD-11` (600 min at the 1.5× premium = 900) while
`ORD-10` takes Friday; (5) a two-machine precedence chain (`P-WIDGET`: CUT→PAINT);
(6) a setup_family changeover (RED `ORD-09` / BLUE `ORD-12` on `PAINT-01`, a 90-min
colour change from `setup_transitions.csv`); (7) the control (`ORD-13`, comfortably
early). Everything else (the boring `P-BASIC` background on HEAT) is deliberately
unremarkable. A README-style companion (`datasets/glass_box/README.md`) narrates
the INTENDED story as PREDICTIONS AUTHORED BEFORE THE SOLVE — what each order WILL
do and WHY, from the input alone — with the discipline stated in the doc: if the
solve contradicts a prediction that is a FINDING, not a licence to rewrite the
prediction. (The predictions held; `test_glass_box.py` pins them.) Verified live:
gate **ACCEPTED / C2 / 0 findings**; deterministic solve (`--solver-workers 1
--solver-seed 0`) reproduces all seven, byte-identical across runs; total
$6956.83 = production 5006 + overtime 900 + setup 680 + tardiness 370.83, the ledger
decomposing exactly.

**CU2 — the sabotage menu (one page, committed).** `datasets/glass_box/
SABOTAGE_MENU.md` — ten keyed one-cell edits, each naming file · row · column →
value, the rule caught (a real id from the 33), the outcome/severity, the resulting
grade, and what the certificate conversation should say: (1) broken product ref →
`ids.orders_resolve_to_products` degraded/CONDITIONAL; (2) impossible due date →
`ids.order_dates_internally_consistent` TEMPORAL_IMPOSSIBILITY/CONDITIONAL; (3)
alternative-group step-attribute mismatch (rule #33) →
`ids.alternative_step_attributes_agree` AMBIGUOUS_SOURCE/CONDITIONAL (first-row-wins,
disclosed); (4) statistical outlier rate → `ids.durations_within_plausible_range`
STATISTICAL_OUTLIER flagged/INFO/**still ACCEPTED**; (5) duplicate identity →
`ids.order_identities_unique` DUPLICATE_IDENTITY/CONDITIONAL; (6) blank key field →
`ids.key_fields_populated` MALFORMED_FIELD violated/**REJECTED**; (7) unroutable
step (zero active rows) → `ids.routes_resolve_to_lines` ORPHAN_ENTITY/CONDITIONAL;
(8) the **false-positive CONTROL** — a legal quantity change that must trip NOTHING;
(9) facility mismatch → `ids.facility_references_consistent`; (10) an inactive route
used by a live order → `ids.orders_use_active_routes` LOW_CONFIDENCE_INPUT. Each row
was verified ONCE, mechanically, so Daryn never meets a menu item that is wrong about
itself — the verification is frozen in `test_glass_box.py`
(`test_sabotage_menu_item`, parametrised). Two calibration findings during the build,
recorded because they shaped the menu: the outlier rule is a PRODUCT-GROUP
statistical check (>10× the family median of `production_minutes/costing_lot_size`),
so it needs ≥3 members with a low median — the clean dataset groups the simple
fabricated products into one `fabricated` family so the outlier sabotage has a home
(a lone product is its own median and can never be an outlier); and a NEGATIVE
quantity is NOT a checked defect (the gate has no quantity-sign rule), so the
"malformed field" item uses a blank key (which is caught, hard) — the negative-value
gap is noted here, not papered over.

**CU3 — the walkthrough (one committed doc, planner-voiced).** `datasets/glass_box/
WALKTHROUGH.md` — the session script: clean submit → read the certificate →
interrogate it (the three registers: `what's wrong?` testimony, `how do I fix the
worst one?` remediation citing the catalog note + IDS §, `what should I fix first?`
judgment) → apply sabotages in batches (rejections / conditionals / disclosures /
the control) → certificate catches them → fix → solve → READ THE STORY: a table
giving, for each of the seven features, the exact question to type (verified working
against the real explainer — e.g. `why is ORD-05 late?` returns CAPACITY_BLOCKED on
CUT-01 + the 890-min lateness metric; `why is ORD-08 on PRESS-SLOW?` surfaces
PRESS-FAST as the priced alternative) and where the receipt lives (which record type,
which bar, which hover). Includes the TRACE EXERCISE: follow ORD-05 CSV row →
gate (no finding — lateness is a scheduling outcome, not a data defect) → canonical
Demand/WorkPackage/Operation → solver placement (Tuesday, driver CAPACITY_BLOCKED) →
cost ledger line ($470 production + $370.83 tardiness) → the "why" answer, the same
record chain reached two ways. Exit bar, stated in the doc: "you tried to catch it
lying and could not."

**CU4 — wiring.** `dev_api.ps1` gains a `glass_box` special case: instead of running
the generator it copies the committed `datasets/glass_box/*.csv|*.json` verbatim into
`_data/mrd` (companion `.md` docs and any stray `gate_output/` excluded), so the
existing dev flow (`dev_cockpit.ps1` submit → solve → alternatives) serves it
unchanged. The ledger + LLM env already flow through `.env.local` / `MRE_DEV=1` /
`MRE_DATA_ROOT=./_data` (set before the branch), so Daryn's questions during the
audit are recorded to the question ledger (AI-track-2 fuel). `.gitignore` gains
`datasets/**/gate_output/` so a gate run beside the committed dataset never gets
committed.

**Tests.** New `tests/test_glass_box.py` (the standing guard): Part A — the clean
dataset gates ACCEPTED/C2/0-findings; Part B — the ten sabotage items, each tripping
exactly its claimed rule/outcome/grade and the control tripping nothing; Part C
(slow) — the real solve reproduces the seven narrative features deterministically
(exactly one late order = ORD-05, overtime rescue on Saturday, the spacer split, one
slow-press placement, the changeover, the chain, the early control). **19 passed**
(1 clean + 10 sabotage + 8 story). Full non-slow Python suite green (frontend
untouched — this is a dataset/docs/dev-script session).

Lesson: to make a system auditable you build the audit's INSTRUMENTS, not the
audit's verdict — a dataset small enough to hold in one's head, predictions authored
BEFORE the solve so the check is against a claim rather than a rationalisation, a
sabotage menu every item of which is mechanically proven right about itself, and a
trace you can walk by hand and by evidence to the same answer. The auditor's trust
comes from trying to break it and failing, not from being told it works.

## Amendment — 2026-07-18: Session 4.3 — Glass Box audit riders + R-DP9 (the no-op drop)

Eight small findings from Daryn's live Glass Box audit, batched. No solver / model /
contract changes; frontend + one ruling + docs + env. The theme throughout: absence
made legible (bands, markers), chrome that never fights itself (the ledger/legend
collision), and a commitment surface that does not manufacture commitments out of
gestures that changed nothing.

**The ruling (R-DP9), transcribed.** A drop within snap tolerance of the op's
INCUMBENT placement is a NO-OP: the bar settles home with a brief "already here"
cue, and NOTHING is committed — no sandbox re-solve, no zero-delta edit, no
`planner_edit` Decision, no standing pin. Rationale: a commitment that commits
nothing is not free. A zero-delta accepted pin (R-DP8) would be compiled as a hard
constraint into EVERY future solve of the lineage and would pollute the edit
narrative ("you changed 4 things" when one of them moved the bar back onto itself).
The tolerance is the EXISTING snap token — `feel.snap.grid_px` converted to a
minute distance through the current zoom's px→minutes factor, so "basically did not
move" means the same on-screen distance at any zoom. This is the mirror image of
R-DP8: R-DP8 says a real commitment must survive every solve; R-DP9 says a
non-commitment must never become one.

**CU0 — `.env.local` end to end (verified, not rebuilt).** `dev_api.ps1` already
loads a gitignored `.env.local` at the repo root into the API's process env on
startup (KEY=VALUE, `#`/blank ignored, quotes stripped, existing env wins) — so a
key in the file reaches the M10 LLM renderer with no terminal typing (the 4B.0
rider claim held). Missing pieces built: a committed `.env.local.example` (no real
secret; `git check-ignore` confirms `.env.local` is ignored and the `.example` is
not) and a README dev section documenting the `cp .env.local.example .env.local`
flow as the intended, no-typing path. gitleaks still guards a real-key commit.

**CU1 — the ledger/legend collision (SECOND occlusion incident), made structural.**
The 4.0c fix moved the DEV question-ledger dock to bottom-LEFT to clear the ask
composer — but bottom-left is where the legend lives, so a `position:fixed` dock at
`z-40` sat on top of it. The fix is layout, not z-index: a new `.board-chrome` row
(`position:absolute; left/right:sp-3; bottom:sp-3; display:flex;
justify-content:space-between; flex-wrap:wrap-reverse`) holds the legend (left) and
a right cluster (the zoom controls + the ledger dock). The ledger is no longer a
free floating panel — it is a thin TAB in that row whose refusal body drops UPWARD
over board space (`bottom: calc(100% + sp-1)`), never over chrome. `wrap-reverse`
means that when the board is too narrow to hold both, the right cluster lifts ABOVE
the legend rather than colliding with it. The legend is visible by default on first
load (it always was; now it can never be occluded). The harness serves the
production build (no dev auto-mount), so `window.__cockpit.mountDevLedger()` exposes
the REAL dock for the test, which expands it and asserts bounding-box
non-intersection of {tab, expanded body} × {legend, ask column} at two viewport
widths (1540 and 1100 — the latter wraps).

**CU2 — R-DP9 implemented.** `controller.drop()` gains an `isNoOpDrop(target)` guard
BEFORE the ghost/sandbox branches: same resource AND within `grid_px×pxToMin` of the
incumbent start → `noOpReturn()` settles the carry home (a gentle snap, NOT the
R-M1a reject shake — this is "already here", not a refusal) and shows a neutral
`.drag-noop` cue, with no card and no network. The state probe carries `noop:true`.
This surfaced in the existing gesture harness immediately: nine sandbox-path tests
dropped AT `incumbent(op)` as a convenient "legal, non-ghost" target — which R-DP9
correctly reclassifies as a no-op. Those tests now compute a genuine legal move on
the incumbent machine (a shared `legalMove()` helper reading
`tier0For(op).legal_regions`, dropped with altKey so it is not snapped back) and a
new test proves the incumbent drop is a no-op with `/sandbox` never called.

**CU3 — empty delta-card copy.** A verdict whose moved-set is empty (the re-solve
reproduced the incumbent schedule — distinct from CU2, which never calls the
sandbox) now reads "equivalent placement — nothing else moved" (authored) instead
of blank space under the "Same cost" headline. Skipped while ghost consequences are
still loading (they may yet fill).

**CU4 — marker/band legibility.** (a) The due marker was `--marker-due:
var(--bar-late)` — a MET due date rendered in the late-alarm red, reading as a
problem. It is decoupled to a NEUTRAL slate (`#5f6675` light / `#9aa3b5` dark) and
rendered as a DASHED outline (a repeating vertical gradient), distinct from the
solid dark now-line and the solid blue release-line. (b) Marker labels near the
right edge were clipped by the overlay's `overflow:hidden` to a fragment ("…ase");
`markers.js` now flips the chip to the LEFT of its line (`right:3px`) when the line
is within ~130px of the right edge, so the full word always shows. (c) Downtime
hover cards now state the WINDOW ("17:00 – 05:00") in addition to the reopen time,
which itself now reads as a weekday+time ("reopens Mon 05:00"). (d) The legend is
visible by default (CU1).

**CU5 — zoom affordance.** The board had no pointer/keyboard zoom path — a
trackpad-less mouse was stuck at one scale (Ctrl+wheel worked but was
undiscoverable). Added a `.board-zoom` +/− control in the chrome row's right cluster
(`board.zoomIn/zoomOut` → vis's own `timeline.zoomIn/zoomOut`; Ctrl+wheel and
trackpad pinch unchanged) and a first-load `.board-hint` ("Ctrl+scroll to zoom")
that fades out so it never becomes permanent chrome. **Accessibility note:** the
zoom buttons carry `aria-label`s ("zoom out" / "zoom in"); they give a
keyboard-reachable, pointer-only zoom path for users who cannot perform the
Ctrl+wheel/pinch gesture. The board itself remains read-only.

**CU6 — newer-schedule detection (extends 3.8's superseded self-heal).** The 3.8
work handled a bound schedule that was explicitly SUPERSEDED; it did nothing for a
bound schedule that is merely STALE — perfectly valid, but older than a newer solve
of the same submission sitting in the registry while a tab lingers (this cost five
audit rounds). A new pure `freshness.js` `findNewerSchedule(boundId, schedules)`
scans the listing (ordered oldest→newest by created_at, scenarios excluded) for the
newest LIVE schedule of the SAME submission strictly newer than the bound one; it
never crosses submission scope and never guesses when the scope is unknown. On a
live (non-superseded) boot the cockpit offers a dismissible "A newer schedule
exists · Open it" info bar (calmer than the amber superseded banner). Pinned by
`freshness.spec.mjs` (logic project) + a negative e2e (no false-positive banner on a
current boot).

**CU7 — packed bars distinct at coarse zoom.** At day zoom, temporally-adjacent
same-lateness bars abutted with only a faint 0.16-alpha border and read as one
merged bar. Each bar now carries a right-edge SEAM (`box-shadow: inset -1px 0 0 0
var(--bar-sep)`, a per-theme token) so packed bars always show a boundary. Asserted
at day zoom on the busy multi_route row (12 back-to-back bars — the same packing
shape as glass_box CUT-01, which motivated the finding; the glass_box CSV set has no
committed cockpit fixture, so the hermetic assertion runs on multi_route, an
accommodation named here rather than a new solve path in CI).

**Tests.** Cockpit JS **137 passed** (was 113): +6 `freshness.spec.mjs` (logic),
+8 cockpit.spec (CU1 ledger-chrome, CU5 zoom, CU6 negative, CU7 packed × light+dark),
+6 planner.spec (CU4 due-decouple / label-flip / band-window × light+dark), +4
gesture.spec (R-DP9 no-op, CU3 equivalent × light+dark). Nine pre-existing
sandbox-path gesture tests migrated off the now-no-op incumbent drop to a real move.
Python untouched (frontend + docs + env only); the non-slow suite runs green
(1171 passed) as a regression guard. See docs/07 v2.25 and CLAUDE.md → Session 4.3.
Lesson: two of these were the same bug wearing different clothes — a control that
fights the thing beside it (the ledger over the legend) and a gesture that
fabricates a commitment out of no change (the no-op drop). The cure for both is to
make the structure say the truth: one layout row that cannot overlap itself, and a
drop that changed nothing changes nothing.

## Amendment — 2026-07-19: Session 4.4 — schedule freshness done right (the sixth stale-tab incident)

The behavior contract, stated plainly: **the cockpit must never leave the user
unknowingly on anything but the newest relevant schedule.** Six times now a stale
tab has been the root of a live-audit finding, and 4.3's CU6 newer-schedule
detection — real, but half-scoped — was the fifth-and-a-half: it noticed a newer
solve only of the SAME SUBMISSION. The sixth incident proved that blind to the
workflow the audit actually uses. In Daryn's ledger the resubmit path is: fix a data
defect in Excel → **re-submit** (which mints a NEW submission id) → re-solve → return
to the cockpit tab. The newer schedule is a different submission, so 4.3's
same-submission `findNewerSchedule` returned null every time. The tab sat stale and
never said so.

**CU1 — freshness scope fix.** `findNewerSchedule` now compares against the newest
LIVE (non-superseded) schedule across the whole **DATA ROOT**, not the same
submission. For a single-tenant / dev deployment — which is what exists — "relevant"
IS the root: the newest solve is the one the planner means, whatever submission
produced it. "Strictly newer" is by `created_at` (the real listing is
`ORDER BY created_at`; the function reads it), with an explicit rule that a
**same-instant tie is NOT newer** — two live boards minted at the same moment are not
a progression of one another, which is what keeps unrelated schedules from
cross-following. Superseded rows and (belt-and-suspenders) scenarios are never
offered. **Multi-tenant scoping is a NAMED future concern, not silently pre-built:**
a real tenant boundary is a property the data root does not model today, and inventing
a scope the system cannot yet source truthfully would be exactly the kind of plausible
lie docs/01 forbids. When a second tenant exists, the scope narrows from "the root" to
"the tenant's schedules" — recorded here as the trigger, deliberately unwritten now.

**CU2 — auto-follow on resubmit (the real fix).** Noticing is not enough; a banner the
planner has to see and click is still a tab left stale until they do. So when a newer
schedule appears while the cockpit is bound to an older one AND there is **no
uncommitted user state**, the cockpit **follows it automatically** — a full reload onto
the new version, then a brief, R-M1-legible toast ("Switched to the new schedule ·
View previous (<id8>)") that confirms the switch and offers one click back. The handoff
across the reload rides `sessionStorage` (same tab, same origin): the previous id is
stashed before the jump and read + cleared on the next boot. **With uncommitted state
present, the cockpit NEVER auto-switches** — it falls back to the 4.3 banner and lets
the planner decide. An edit-in-flight outranks freshness; generalized, *any* user
investment does. "Uncommitted state" = a drag phase that is not `idle` (a tentative
edit, an open delta card, an accept/publish in flight) **or** a pinned conversation in
the ask panel (a live bar selection, a built-up Q&A history, or an ask mid-round-trip —
new `panel.hasUserState()`). The watch re-checks on **window focus** and **tab
re-show** (`visibilitychange`) and on a slow 30s interval backstop; focus is the
load-bearing signal, because a planner returning from Excel after a data fix is the
exact moment the newer schedule became relevant. Idempotent per newer id (a banner is
never stacked); the auto-follow reload resets watch state, so a chain never loops (the
followed-to version is newest → nothing newer → no re-follow).

**CU3 — identity made visible.** Across all six incidents the hex id was insufficient:
two visually-similar boards read identically, so a stale one was indistinguishable from
the fresh one at a glance. The registry's `get_schedule_meta` now carries a
**`generation`** counter (this schedule's 1-based ordinal among the data root's
non-scenario schedules, `created_at` asc — a monotonic "solve #N") and its
**`created_at`**; the top strip renders a human-scale identity — **"solve #3 · 09:41"**
— with the short hex kept in the element `title` for debugging. It degrades to the hex
(a plain document, a pool member without these fields) rather than showing a blank.

**Tests.** New harness seam in the fixture server: `POST /__test__/add-schedule`
injects a newer schedule into the data-root listing (resolving as a real doc/meta from
a chosen base fixture dir, so an auto-follow lands on a coherent board), cleared per
test. `freshness.spec.mjs` rewritten for the cross-root `created_at` semantics (the
resubmit-under-a-new-submission case now IS offered; the tie is not; superseded and
scenarios skipped; position fallback). `cockpit.spec.mjs` drives the three CU2 flows
end to end — resubmit-while-viewing **auto-follows** (URL advances + toast + one click
back to the previous id), an **uncommitted selection** shows the banner and **never**
changes the URL, and a **window focus** rechecks and follows — plus CU3 (the strip
shows "solve #N · HH:MM") and a strengthened CU6 (no spurious auto-follow on a normal
boot: the static fixtures tie on `created_at`). `test_api_endpoints.py` asserts `/meta`
carries `created_at` + an integer `generation ≥ 1`. **Cockpit JS 146 passed** (was 137:
+1 freshness logic, +4 cockpit.spec × light+dark = +8, minus the one 4.3 freshness
logic test folded into the rewrite). **Non-slow Python 1172 passed** (backend change is
additive to `get_schedule_meta`; registry/api/planner_edit/standing_pins green). See
docs/07 v2.26 and CLAUDE.md → Session 4.4. Lesson: "notice the newer schedule" and
"the user is now on the newer schedule" are different guarantees — the first still
depends on the human, so the sixth incident needed the second. Follow automatically
when nothing is at stake, yield to the banner the moment something is, and make the two
boards nameable so a human can tell which one they are on.

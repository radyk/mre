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

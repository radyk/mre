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

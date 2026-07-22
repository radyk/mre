# Evidence Contract — Specification

**Document 2 of 3** · Status: Draft v0.1 (living document) · Companion documents: *Canonical Manufacturing Model Specification*, *PoC Plan*

---

## 1. Purpose

Every module in the system — ingestion, validation, planning, solving, extraction — takes inputs, makes decisions or transformations, encounters issues, and produces outputs. Instead of each module inventing its own logging and output format, all modules speak **one contract**. The evidence store this contract produces is the substrate for both AI consumption patterns:

- **(a) Run summarization** — an LLM reads a complete, self-explanatory run document and produces a planner-facing narrative.
- **(b) Interactive retrieval** — an agent lands on the right fragments across many runs to answer planner questions ("why is this order late?", "how often has this machine's data been flagged?").

**Reconciliation rule:** design the content for (a); impose the discipline of (b) on every record — stable IDs, canonical entity keys, self-containment. (b) is never sacrificed in pursuit of (a).

## 2. Architecture: four layers

| Layer | Content |
|---|---|
| **L1 — Schema** | Versioned record-type definitions (RunContext, Decision, Finding, Metric, Event, Artifact) + the controlled vocabularies. Lives in one place; modules never construct records by hand. |
| **L2 — Reporter** | The object modules touch. Eight verbs. Validates against the schema at write time (malformed records die at the source). Performs all ambient capture automatically. |
| **L3 — Sink** | Dual-write: append-only per-run JSONL stream (crash-safe, live progress) + consolidated run document assembled at run end. Same schema in both; consolidation is pure aggregation. Filesystem first; the sink abstraction makes later storage moves invisible upstream. |
| **L4 — Index** | Built from the streams, serving (b): entity key → records, finding code → occurrences, run lineage graph, run registry. Can start trivially simple because the hard part (keys on every record) is paid at L2. |

### Design goals with teeth

- **Ease of emission is first-order.** A module author gets ~80% of a complete run record from `begin()` and `end()` alone. If the contract costs more than a line or two per interesting event, authors stop using it and the system's value collapses.
- **Structured payloads, human messages.** Every record carries both a human-readable message and a machine-readable payload. The AI never parses prose.
- **The evidence store is testimony.** The AI layer reads it; it never writes into it (see §8).

## 3. Record structure — common envelope

Every record carries:

| Field | Meaning |
|---|---|
| `record_id` | Unique |
| `run_id` | The producing run |
| `seq` | Ordering within the run |
| `module` | M1–M10 code (see Document 3) |
| `timestamp` | |
| `snapshot_id` | The canonical snapshot the run executed against |
| `subjects` | **Canonical entity refs only.** Never ERP identifiers, never solver indices. Modules translate internal indices back to canonical keys *before* emitting. |
| `tier` | `headline` / `supporting` / `detail` (see §7) |
| `message` | Human-readable one-liner |

**Self-containment rule:** a retrieval agent gets fragments, not documents. Each record must make sense alone — it carries enough embedded context that it does not depend on the record above it. Slightly redundant, deliberately so.

## 4. Record types

### 4.1 RunContext (opened by `begin`, closed by `end`)

- Identity: run_id, module, purpose, trigger (who/what initiated), parent-run linkage.
- Config snapshot + config hash.
- Input manifest: every input artifact/snapshot with ID, hash, and a **small statistical profile** (row counts, date ranges, entity counts) — what lets the LLM ground its narrative without the raw file.
- Outcome: status, timing, exception capture, output manifest, solver telemetry where applicable (status, optimality gap, solutions found).
- Baseline hooks where possible: recorded counterfactuals ("tardiness if due dates ignored", "cost of naive FIFO") — cannot be reconstructed after the fact and make the most persuasive summaries.

### 4.2 Decision

| Field | Content |
|---|---|
| `decision_type` | Per-module enum: `identity_resolution`, `interpretation` (M1); `demand_merge`, `demand_split` (M4); `model_simplification`, `constraint_relaxation` (M5); `assignment` (M7); `scenario_modification` (what-if); `planner_edit` (an accepted cockpit gesture, Phase 3) |
| `subjects` | Canonical entity refs |
| `chosen` | Structured description of what was selected |
| `alternatives` | List of `{option, consequence}` — consequences in comparable terms (cost delta, constraint violated, lateness created) |
| `driver` | Primary driver code (mandatory, exactly one) + optional secondary list. Forcing commitment to the dominant cause is what makes explanations crisp. |
| `basis` | `observed` / `reconstructed` / `policy_applied` — **the honesty flag** |
| `policy_ref` | The named policy that governed, if any |
| `authority` | **WHO authored the decision** (Phase 3 addition). `None` for machine-authored decisions (adapter interpretations, planner merges, solver-reconstructed assignments). **MANDATORY on a `planner_edit`** — an accepted cockpit edit is a human act pinning an operation and re-solving its surroundings, so the store must name the authority that stands behind it. A dev identity token in Phase 3; real auth (SSO/role) is post-pilot. The value never carries ERP identifiers — it is an identity of the *actor*, orthogonal to `subjects`. |

**The planner-edit Decision (Phase 3, R-DP7).** When a planner drops a bar and *accepts* the Tier-2 verdict, the accept records a `planner_edit` Decision and mints a NEW proposed schedule version (the base is never mutated). `basis` is `observed` — the pin is a directly observed human command, not a solver reconstruction (the *consequences* the re-solve computes are reconstructed evidence in that new version's own run, as always). `chosen` carries the pin (operation, resource, start), the priced delta, and the moved-set count; `alternatives` carries the road not taken (keeping the incumbent placement, at its known cost). `authority` is mandatory. Publish (proposed → published) is a separate act that supersedes the prior version and invalidates its pools/alternatives; it is not itself a Decision but a status transition recorded in the registry.

**Driver codes (13):**

`COST_TRADEOFF` · `DUE_DATE_PRESSURE` · `CAPACITY_BLOCKED` · `CAPABILITY_LIMITED` · `SETUP_AMORTIZATION` · `SEQUENCE_DEPENDENCY` · `CALENDAR_WINDOW` · `FROZEN_COMMITMENT` · `DATA_EXCLUSION` · `POLICY_RULE` · `SOLVER_LIMIT` · `NO_ALTERNATIVE` · `EARLINESS_PREFERENCE`

`EARLINESS_PREFERENCE` (added 2026-07-22, R-SC3): a placement on a dearer-but-earlier eligible machine that a positive `CostModel.earliness_value` (docs/06 §5.9) *bought*. It fires only when earliness_value > 0; with the 0 default the earliness floor is a pure zero-cost tiebreak and no assignment is attributed to it, so pre-R-SC3 datasets classify byte-identically. Under the declared model the only priced reason to prefer a dearer eligible machine is an earlier start (tardiness has its own weight), so a dearer-than-cheapest eligible choice is attributed to the earliness preference.

**The reconstruction principle.** A CP-SAT solve makes thousands of implicit decisions; the solver's internal search is not observable. What is recorded is the reconstruction at solution-extraction time: for each task in the final solution, re-derive the alternative set and consequences from the model's own data (eligible resources, occupancy, cost parameters). Cheap and honest — and always marked `basis: reconstructed`, so the AI layer never overclaims. The correct phrasing is "X was chosen; the alternatives would have cost…" — never "the solver chose X *because*…". Improving-solution snapshots during the solve stream through the same mechanism via the solver callback.

**Decisions exist outside the optimizer.** The adapter decides interpretations, the planner decides merges, the validator decides exclusions, the builder decides simplifications. Same shape everywhere. Batching decisions additionally record: constituent demand IDs, compatibility basis, policy parameters in force, **estimated benefit** (setups avoided × cost) and **estimated risk** (tardiness exposure created) — the counterfactual pair that lets the AI answer "is our batching policy paying for itself?" across runs.

### 4.3 Finding

| Field | Content |
|---|---|
| `code` | From the finding vocabulary below |
| `severity` | `blocker` (run cannot proceed) / `error` (entity excluded, run proceeds) / `warning` (proceeds, flagged) / `info` |
| `subjects` | Canonical entity refs |
| `evidence` | Expected vs. actual — the values themselves |
| `disposition` | **What the system did:** `blocked` / `excluded` / `defaulted` / `proceeded_flagged` / `auto_corrected` |
| `disposition_detail` | Which default was applied; which policy authorized the correction |

Disposition is what connects data quality to schedule quality — it answers "did any data problems affect this schedule?"

**Severity carries a consequence (enforced, Session 4.5).** Severity and
disposition are not free to disagree: a severity is a *claim about what happened
to the entity*, and the disposition must back it.

- `blocker` ⇒ disposition `blocked` (the run cannot proceed).
- `error` ⇒ disposition `excluded` (or `blocked`) — the entity does not survive
  this run. **`proceeded_flagged` is not a legal disposition for `error`
  severity**: a run that proceeded past the entity intact is, by definition, not
  an error-severity consequence. The cure is to *demote honestly* (the run
  proceeded → `warning`) or to *act* (exclude / block). The named specimen is
  `VALUE_OUT_OF_RANGE` emitted at `error` while the demand proceeded_flagged into
  a floored-duration operation — a label claiming a consequence the disposition
  never delivered.
- `warning` / `info` ⇒ any disposition (the run proceeded; the flag is disclosed).

This is enforced at construction in `contracts.records.Finding`, so no module —
gate, validator, or adapter — can emit a lying severity. It also decouples the
M0 gate's finding severity from the rule *outcome*: the outcome vocabulary
(satisfied/flagged/degraded/violated) drives the certificate GRADE, while the
finding severity now derives from the DISPOSITION (`finding_severity`). A
`degraded` rule that proceeds flagged therefore emits a `warning` finding while
still degrading the grade to CONDITIONALLY ACCEPTED — the two axes agree instead
of contradicting.

**Finding codes (18), grouped by pipeline layer of origin:**

*Adapter (ERP-shape):*
`MISSING_REFERENCE` · `UNMAPPABLE_VALUE` · `AMBIGUOUS_SOURCE` · `MALFORMED_FIELD` · `DUPLICATE_IDENTITY` · `IDENTITY_CHANGED`

*Validation (semantic):*
`TEMPORAL_IMPOSSIBILITY` · `NO_CAPABLE_RESOURCE` · `ORPHAN_ENTITY` · `VALUE_OUT_OF_RANGE` · `STATISTICAL_OUTLIER` · `PROVENANCE_GAP` · `LOW_CONFIDENCE_INPUT`

*Planning / Solve:*
`BATCH_CONFLICT` · `INFEASIBLE_SUBSET` · `HORIZON_EXCEEDED` · `SOLVER_NONOPTIMAL` · `DENSITY_LIMIT`

`DENSITY_LIMIT` (added 2026-07-12): a structural concentration of a scheduling
feature on one resource exceeds a validated solver-scale ceiling (e.g. resumable
operations per resource, docs/05 R-C3) — a distinct signal from `STATISTICAL_OUTLIER`
(an individual value's deviation from its group's distribution). The two must not
share a code: they answer different planner questions ("is this data point weird?"
vs. "will this resource's workload be hard to solve?") and trending one must never
silently include the other.

Code + subjects + snapshot on every record turns the store into a **monitoring** system, not a log: "trend `STATISTICAL_OUTLIER` on durations by product family over 90 days" is a query, not a project. "Where in the pipeline do problems enter?" is answerable because codes carry their layer of origin.

### 4.4 Metric

`{run_id, name, value, unit, subjects, rollup_of}`

**Decomposability contract (enforced):** any metric carrying `rollup_of` must equal the aggregate of the records it references; the consolidator verifies this at run end. No number appears in a summary that cannot be traced to its constituents. Attribution follows Document 1's invariant: costs at the finest meaningful grain (WorkPackage/task/resource), service outcomes per Demand.

### 4.5 Event

Progress and status: `{status_text, payload}`. Long solves stream improving solutions and telemetry here.

### 4.6 Artifact

Registered inputs and outputs: reference, hash, producing/consuming run. Artifact lineage links (this run consumed artifacts of runs X, Y) plus stable entity keys give cross-run identity — the run lineage graph — for free.

## 5. Vocabulary governance

Small, closed enums for the fields the AI and the index filter on; free structure in the payloads. Codes are for routing and retrieval; payloads are for substance.

**Extension rule:** new codes may be added; existing codes are never repurposed; every addition is a reviewed change. A vocabulary that tries to encode everything becomes a second schema nobody maintains.

## 6. The Reporter verb set (L2)

```
reporter = Reporter.begin(module, purpose, config, trigger)
    → mints run_id; captures config hash, timestamp, parent-run linkage

reporter.register_input(artifact_ref | snapshot_id)      # hashes, records lineage, profiles
reporter.record_decision(type, subjects, chosen, alternatives, driver, basis,
                         policy=None, tier=...)
reporter.record_finding(code, severity, subjects, evidence, disposition, detail=None)
reporter.record_metric(name, value, unit, subjects=None, rollup_of=None)
reporter.record_event(status_text, payload=None)
reporter.register_output(artifact_ref)
reporter.end(status)          # or auto via context manager; exceptions captured
```

Eight verbs. Ambient capture (IDs, sequence numbers, timing, exception state) is entirely the reporter's job. Schema validation happens at the verb call.

## 7. Sink and consolidation behavior (L3)

- **During the run:** every record appends to the per-run JSONL stream immediately (crash-safe; live progress on long solves).
- **At `end()`:** the consolidator assembles the run document from the stream — pure aggregation, same schema — and runs:
  - the **decomposability check** (§4.4);
  - the **tier filter**: `headline` + `supporting` records enter the consolidated document; `detail` remains stream-only but index-reachable. This keeps the summary document within an LLM's comfortable reading budget on a 400-job schedule without discarding information.
- Index update (L4) follows consolidation.

## 8. Boundary rules

1. **Canonical keys only.** No ERP identifiers, no solver indices in `subjects`. Rendering back into planner vocabulary is done at read time via the adapter's external-refs mapping table. *Pre-canonical modules (M0) cannot emit canonical refs because canonical identities do not yet exist. They emit **typed submission-space refs** — `EntityRef(system="IDS", type, id)` — as subjects. The M1 adapter MUST register every such ref in the identity map when minting the corresponding canonical entity, making gate findings retroactively reachable by canonical key. For REJECTED submissions that never reach M1, the IDS ref is the finding's permanent identity — stable per source, which is what certificate trending requires.* (`EntityRef.system` defaults to `"canonical"`; M0 sets it to `"IDS"`.)
2. **No AI write path.** There is deliberately no `record_explanation` verb. The AI layer reads evidence; it does not write into the store it reasons over — that preserves the store's testimony value. Persisted AI narratives (worthwhile for audit) go in a separate annotation store that references evidence and never amends it.
3. **Reconstructed is labeled reconstructed.** `basis` is mandatory on Decisions; downstream renderers must respect it in phrasing.
4. **Every record references its snapshot.** No evidence floats free of the ground truth it was produced against.

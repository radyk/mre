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

**Driver codes (14):**

`COST_TRADEOFF` · `DUE_DATE_PRESSURE` · `CAPACITY_BLOCKED` · `CAPABILITY_LIMITED` · `SETUP_AMORTIZATION` · `SEQUENCE_DEPENDENCY` · `CALENDAR_WINDOW` · `FROZEN_COMMITMENT` · `DATA_EXCLUSION` · `POLICY_RULE` · `SOLVER_LIMIT` · `NO_ALTERNATIVE` · `EARLINESS_PREFERENCE` · `PLANNER_DIRECTIVE`

`PLANNER_DIRECTIVE` (added 2026-08-03, R-DP13): **a human directed this placement.** Every other member of this vocabulary names something the *plant* or the *model* did — capacity, capability, a calendar, a price, a policy, the solver's own budget. An accepted cockpit gesture (§4.2's `planner_edit` Decision) has no such cause: the operation sits where it sits because a person put it there and then accepted the priced consequence. It is the driver of a `planner_edit` accept **at every ledger delta** — a planner's move may cost nothing, cost money, or save money, and the code does not vary, because the variation is not information about *why* the placement is where it is. The size of the consequence rides `chosen.cost_delta`, which is the ledger and is checkable.

The code exists because the two adjacent members each make a claim the record cannot support. `NO_ALTERNATIVE` voices as *"there was no other feasible option"* — a claim about the **plant**, which an accept never establishes; under `hold_all_placements` (R-DP11) it would be asserting it from a property of *our own pinning*, which is manufacturing a plant claim from a method fact. `COST_TRADEOFF` claims a cost decided the matter: true where one did (the planner's merge decisions, the extractor's price-ranked attribution, `POST /audit/accept` — where the accepted board **is** the cheaper one and the saving is stated), and false on a planner edit, where the ledger delta is simply whatever the planner's own move happened to cost. Its phrase is wrong at **$0.00** (the comparison came back level) and wrong on a **dearer** accept (the planner knowingly paid).

**No docs/06 doorway is owed either.** The pipeline-proof rule governs a new **declared fact about the plant** — something a submission asserts, the gate checks, an adapter maps and remediation can advise on. `PLANNER_DIRECTIVE` is not a fact about the plant: it classifies an act performed *inside the product* by a person using it, and its whole evidentiary basis (`authority` — who; `chosen.cost_delta` — what it cost) is already on the Decision that carries it. No submission can declare it, no gate can check it, no adapter maps it. This is R-CAL1's product-side/IDS distinction (4B.29) on a different axis.

**No contract-version bump is owed for adding a driver code, and this is the rule, not a judgement call.** The version constant `CONTRACT_VERSION` (`contracts/schedule_document.py`) versions the **schedule document** — the read-only artifact the cockpit and the API render. The driver vocabulary is not in that document at any version: `driver` appears on **Decision records in the evidence store**, which the document does not carry. A vocabulary change is instead governed by the *add-never-repurpose* rule (this §4.2 plus `contracts/vocabularies.py` in the same commit) — the ceremony this entry is part of. A bump **would** be owed if a driver code ever reached a document field; none does.

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

**Finding codes (20), grouped by pipeline layer of origin:**

*Adapter (ERP-shape):*
`MISSING_REFERENCE` · `UNMAPPABLE_VALUE` · `AMBIGUOUS_SOURCE` · `MALFORMED_FIELD` · `DUPLICATE_IDENTITY` · `IDENTITY_CHANGED`

*Validation (semantic):*
`TEMPORAL_IMPOSSIBILITY` · `PAST_DUE_AT_INTAKE` · `NO_CAPABLE_RESOURCE` · `ORPHAN_ENTITY` · `VALUE_OUT_OF_RANGE` · `STATISTICAL_OUTLIER` · `PROVENANCE_GAP` · `LOW_CONFIDENCE_INPUT`

*Planning / Solve:*
`BATCH_CONFLICT` · `INFEASIBLE_SUBSET` · `HORIZON_EXCEEDED` · `SOLVER_NONOPTIMAL` · `DENSITY_LIMIT` · `CALIBRATION_DRIFT`

`CALIBRATION_DRIFT` (added 2026-08-01, R-CAL1 rule (3)): this plant has an
**accepted calibration profile** and the solve did not get what that profile
measured — fewer than K of its K seeded searches produced a publishable board at
the calibrated per-member budget. **INFO severity, `proceeded_flagged`
disposition, never an exclusion and never a grade change**: the solve completes
on the best available member (R-BK1 clause 1) and the finding recommends
re-running the ceremony.

It exists because the two adjacent codes make different claims. `SOLVER_NONOPTIMAL`
is about the PROOF of this board — we found a schedule and could not prove it
optimal. `DENSITY_LIMIT` is about the PLANT — a structural concentration that will
be hard to solve. `CALIBRATION_DRIFT` is about OUR OWN COEFFICIENTS: the numbers
were measured against a book that has since moved, and the remedy is a
re-measurement rather than anything a planner does to the data. It fires only
under an ACCEPTED profile, because a plant running product defaults has no
promise to drift from and reporting drift there would turn an uncalibrated plant
into a broken one.

`PAST_DUE_AT_INTAKE` (added 2026-07-28, R-PD1): a Demand whose declared due
date is already behind the reference date when planning starts. **INFO severity,
`proceeded_flagged` disposition, and never an exclusion** — the demand is
scheduled and priced with tardiness (R-PD1 clause (1)), and the unavoidable part
of that lateness is reported as `cost_summary.tardiness_floor` (contract 1.11).

It exists because `TEMPORAL_IMPOSSIBILITY` already means something else and must
not be stretched to cover this. That code is the M0 gate's verdict on
`due < release/created` — a pair of dates that genuinely cannot both be true, and
a real data defect with a real fix. M3 was raising the SAME code for
`due < reference_date`, which is not a contradiction at all: it is a released
work order that is simply late. The consequences of the conflation were concrete
— the authored phrase "has dates that can't both be true" is false of an overdue
order, and 21 real orders on the first fixture that could produce them were filed
into a fix-first remediation queue for a condition that has no fix (docs/07
§5a.26). The remediation catalog therefore carries `PAST_DUE_AT_INTAKE` with
`remediation_applies: false` and an explicit rationale.

The two codes must never be merged or trended together: one asks "is this record
self-contradictory?", the other asks "how far behind is this plant?".

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

**Decomposability contract (enforced):** any metric carrying `rollup_of` must equal the aggregate of the records it references; the consolidator verifies this at run end. A rollup's components are emitted **even at zero** (M0's `gate.rules_*` are the worked example): components that appear only when non-empty cannot be verified as a set, and an absent component reads as an unasked question rather than a measured nought. No number appears in a summary that cannot be traced to its constituents. Attribution follows Document 1's invariant: costs at the finest meaningful grain (WorkPackage/task/resource), service outcomes per Demand.

### 4.5 Event

Progress and status: `{status_text, payload}`. Long solves stream improving solutions and telemetry here.

`subjects` is **emittable** on an Event. The record model has carried the field since L1 (§3's envelope), but `record_event` hardcoded an empty list until 2026-08-05; it is now an optional parameter defaulting to none, so a progress ping stays subject-less while a status record that is *about* something names it. Boundary rule 1 is what makes such a record reachable by key.

**The M0 gate verdict** (`status_text: "gate_verdict"`, added 2026-08-05, R-CT1). The conformance gate emits a Finding only for a rule it did **not** satisfy — which is correct and stays correct: every finding code names a defect, and a satisfied rule is not one. The consequence, unnoticed until the shared-body census, was that an **ACCEPTED submission left the evidence store silent about its own certificate**. The grade was computed, written to `certificate.json`, and never reported, so every surface reading evidence alone was *structurally* unable to state it — the board opener returns `grade: None` and says so, and the certificate answer had to reach past the store to the artifact.

The gate now reports its verdict at **both** of its exits — the full rule cascade and the intake refusal ("I was pointed at nothing" is still a grade) — decomposed across three record types that already existed:

| part | record | content |
|---|---|---|
| the categorical verdict | **this Event** | `grade`, `costing_completeness_grade`, `outcome_tally`, `flags_disclosed`, deficiency/normalization/finding counts, the submission ref, `grade_provenance` |
| the coverage | **Metric** (§4.4) | `gate.rules_checked` rolling up `gate.rules_{satisfied,flagged,degraded,violated}` |
| the artifact | **Artifact** (§4.6) | `certificate.json`, registered with its sha256 |

`grade_provenance` names the provenance **class** (Document 1 §7) and the formula that produced the value: the grade is `derived` by `grade_from_outcomes` from observed rule outcomes. It is a *use of that vocabulary*, not a sidecar write — a sidecar is keyed on a canonical entity attribute, and M0 runs before canonical identities exist at all.

**What was refused, and why it stays refused.** A *Finding* — an ACCEPTED grade would have to wear a defect's code, and the gate's silence on a satisfied rule is therefore not the bug. A *Decision* — the grade is a pure function, not a choice: there are no alternatives to enumerate, and `driver` is mandatory-exactly-one where every code names a scheduling cause, so filling one would claim deliberation that did not happen. A *Metric* for the grade itself — `value` is a float and a grade is a word. A *new record type* — nothing here needs one.

**No `CONTRACT_VERSION` bump is owed**, by the rule §4.2 already states: that constant versions the **schedule document**, and no field added here reaches it. This is an add-never-repurpose vocabulary change, committed with its spec update.

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
reporter.record_event(status_text, payload=None, subjects=None)
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

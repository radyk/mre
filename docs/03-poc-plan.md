# Proof of Concept — Plan

**Document 3 of 3** · Status: Draft v0.1 · Companion documents: *Canonical Manufacturing Model Specification*, *Evidence Contract Specification*

---

## 1. Objective and thesis

Develop an AI-assisted production scheduling system that generates practical, cost-optimized schedules while strictly enforcing operational constraints; minimizes total cost of production by balancing due dates, setup times, overtime, machine utilization, and other business priorities; makes every scheduling decision transparent and explainable in plain language; and validates and monitors ERP data quality, identifying anomalies before optimization.

**The PoC thesis is the traceability chain, not the solver.** CP-SAT scheduling is proven (the legacy ProFunct codebase demonstrates it). The unproven claim is that a canonical model + evidence contract makes schedules *explainable* and data quality *monitorable* with plain retrieval — no exotic AI machinery. The build order therefore optimizes for reaching the payoff demo — *"Why is WO-10432 late?" answered with a sourced, honest chain* — with the fewest components.

**Organizing principle:** build the evidence backbone first; every subsequent module proves itself by emitting into it.

## 2. Module inventory

| # | Module | Responsibility |
|---|---|---|
| **M1** | **ERP Adapter** | Raw ERP extracts → canonical snapshot + external-identity mapping table + adapter Findings. The only module that knows ERP field names. Owns identity resolution (today's extract row → same canonical entity as yesterday's). |
| **M2** | **Snapshot Store** | Persists versioned canonical snapshots + provenance sidecars. Enforces the write contract: no attribute write without its provenance record; writes only via adapter and planning modules. |
| **M3** | **Validator** | Semantic checks against a snapshot + the provenance integrity sweep. Emits Findings with dispositions; produces the go/no-go gate for solving. May read the sidecar through the narrow trust interface. |
| **M4** | **Planner (Batcher/Splitter)** | Demands → WorkPackages + Fulfillments under named policies. Heavy Decision emitter (merge rationale, estimated benefit/risk). The only module that creates WorkPackages pre-execution. |
| **M5** | **Solver Builder** | Canonical snapshot + WorkPackages → CP-SAT model + **variable↔entity mapping table**. Reads plain values only, never the sidecar. Emits Decisions about its own simplifications. Consumes exactly six inputs: WorkPackages (with Operations), Resources, Pools, Calendars (flattened), Constraints, CostModel. |
| **M6** | **Solve Runner** | Executes OR-Tools with configured limits; streams improving-solution events and solver telemetry (status, gap, timing). |
| **M7** | **Solution Extractor** | Solver values + mapping table → canonical Schedule (Assignments), per-Demand ServiceOutcomes via Fulfillments, cost ledger, reconstructed alternatives per assignment (`basis: reconstructed`). After this, the solver model dies. |
| **M8** | **Evidence Reporter** | The cross-cutting library every module is handed. Eight verbs; ambient capture; JSONL sink + consolidation. |
| **M9** | **Evidence Store & Index** | Per-run streams + consolidated documents + entity-key index serving retrieval. |
| **M10** | **AI Explanation Layer** | Pure consumer: reads canonical snapshots, Schedules, evidence; renders answers in planner vocabulary via the M1 mapping table. **No write path into anything.** |

## 3. Build phases

### Phase 0 — Contracts (no behavior, all shape)

- Schema definitions as code: entity types, provenance sidecar structure, Decision/Finding/Metric/Event/Artifact records, all enums. Nothing defines record shapes locally; every module imports the contracts.
- Reporter library (M8): eight verbs, JSONL sink, consolidator, decomposability check, tier filter.
- Snapshot store (M2) in its simplest honest form: directory-per-snapshot of JSON files with the sidecar alongside. No database until the file layout hurts.

**Deliverable:** a toy module that begins a run, emits one of each record type, ends, and produces a valid consolidated document.

### Phase 1 — Adapter + Validator (the data-quality half of the objective)

- M1 against the real extract shapes (open workorders, routing, routing lines, product — the legacy joins, reborn): translation into canonical entities, identity mapping table, provenance on every attribute, Findings instead of print warnings.
- M3 with the starter check set: referential integrity, temporal impossibility, no-capable-resource, provenance sweep, one statistical check (duration outliers by product family), and `LOW_CONFIDENCE_INPUT` for defaulted decision-relevant attributes.
- **Seed the test extract with defects** — a missing routing, a zero lot size, a due date in the past, an unmappable workcenter. The demo needs findings to show, and writing checks against known defects keeps them honest.

**Milestone:** a data-quality report generated entirely from the evidence store. **This alone is a shippable artifact of independent value** — it can go in front of a planner before any scheduling exists.

### Phase 2 — Planner + Solver spine

- M4 with exactly two policies: identity (one Demand → one WorkPackage) and the setup-family/window merge policy. Every merge emits its Decision with estimated benefit/risk.
- M5/M6/M7 as the re-architecture of the legacy solver core: intervals, no-overlap, calendars as forbidden windows, pool concurrent capacity, sequence-dependent setups, **per-Demand tardiness via Fulfillments**, cost ledger — built from canonical entities, with the mapping table, extraction back to Schedule/Assignments/ServiceOutcomes and reconstructed alternatives.

**Deliberate solver scope cuts** (each incremental to re-add; legacy code is the reference implementation):

| Cut | PoC stance |
|---|---|
| Chunked / preemptive processing | `splittable = false` everywhere initially |
| Straddling rewards | Omitted |
| Dwell-phase machine-release subtleties | Simple machine-free wait |
| Tool variety | Single tool type |

**Milestone:** a solved schedule where every assignment traces to canonical entities and every cost total decomposes.

### Phase 3 — AI layer + demo

Two consumers, matching the two patterns:

- **Run summarizer (pattern a):** consolidated document + canonical Schedule → planner-facing narrative (headline outcomes, notable decisions, findings that affected the schedule, per-customer service).
- **Question answerer (pattern b):** entity-key lookup → assemble the record chain for a subject → LLM renders in planner vocabulary via external refs. **Keep retrieval dumb:** entity-key lookup and lineage-walk only — no embeddings, no agent loops. The thesis is that the records themselves make explanation easy; if plain retrieval over well-structured evidence suffices, that is precisely the result to demonstrate.

Cheap win: reuse the existing Dash Gantt against the new Schedule shape.

**Sequencing note:** Phases 1 and 2 are parallelizable (both depend only on Phase 0). If serial, the order stands — Phase 1 delivers standalone value even if Phase 2 runs long.

## 4. Demonstration script (the acceptance test — written before the code)

1. **Ingest the seeded extract.** Adapter findings appear with dispositions: *"WO-10455 excluded: routing R-118 not found."*
2. **Validation report.** The planner sees data problems *before* any schedule exists, including `LOW_CONFIDENCE_INPUT` flagging defaulted customer weights.
3. **Batch, solve, extract.** Schedule renders on the Gantt.
4. **Ask: "Why is WO-10432 late?"** The answer walks the chain:
   > Demand due Mar 30 → batched with 10441 and 10467 to save two setups (Decision, driver `SETUP_AMORTIZATION`, projected saving X) → batch assigned to CNC-2 because CNC-1 is closed Saturday for planned maintenance (Calendar exception) → completes Mar 31, one day late, tardiness charged Y (ServiceOutcome).

   Every clause sourced from a record; the assignment marked reconstructed; no invented motive. **This interaction is the whole project. If it assembles from records without hand-waving, the architecture is vindicated.**
5. **Cross-run question after two snapshots:** "What changed since yesterday and why?" → snapshot diff + Decision/CostModel comparison.

## 5. Explicit stub list

Named so nothing is silently forgotten. Each has a reserved seam in the canonical model (Document 1, §9); none requires architectural rework to activate.

- Material / inventory flow
- Labor as skill-bearing resources (`limit_reason = labor_proxy` marks the seam)
- Yield inflation (`yield_factor` = 1.0)
- Overtime as a solver decision (calendar records it as fact only)
- Partial-quantity Fulfillments
- Parameterized capability matching
- Process partial order
- Multi-plant

## 6. Key risks and their designed mitigations

| Risk | Mitigation already in the design |
|---|---|
| Provenance sidecar silently drifts incomplete | Structural write contract (one API, one transaction) + validator integrity sweep (`PROVENANCE_GAP`) |
| Canonical model leaks ERP shapes over time | Import discipline; `external_refs` as the only sanctioned home; litmus tests at review |
| Evidence emission too burdensome, modules stop reporting | Reporter ambient capture; 80% from `begin()`/`end()`; ease of emission as a first-order design goal |
| AI invents motives | `basis: reconstructed` labeling; provenance-aware phrasing rules; AI reads only canonical model + evidence |
| Schedule orphaned when solver model discarded | Variable↔entity mapping table survives the solve; extraction to canonical Schedule before disposal |
| Batching destroys demand traceability | Fulfillment entity; per-Demand tardiness; batch decisions carry constituents + benefit/risk |
| Ground truth shifts under runs | Snapshot semantics; every run and record pinned to a snapshot ID |

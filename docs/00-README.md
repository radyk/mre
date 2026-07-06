# Manufacturing Reasoning Engine — Founding Documents

Three specifications, in reading order:

| Doc | Contents | Answers |
|---|---|---|
| **01 — Canonical Manufacturing Model** | Three-model architecture, canonicity rules, snapshot semantics, all entities (spine + supporting), provenance sidecar, design invariants, deferred stubs | *What does the system know, and how is it represented?* |
| **02 — Evidence Contract** | Four-layer reporter architecture, record types (Decision/Finding/Metric/Event/Artifact), driver & finding vocabularies, the eight reporter verbs, sink/consolidation rules, boundary rules | *How does every module account for what it did, and how does the AI consume it?* |
| **03 — PoC Plan** | Module inventory M1–M10, build phases 0–3, solver scope cuts, the demonstration script (acceptance test), stub list, risk table | *What do we build first, and how do we know it worked?* |

## The system in one paragraph

ERP data enters through an adapter (the only ERP-aware code) and becomes a versioned snapshot of canonical entities — Demand, WorkPackage, Fulfillment, Operation, Resource, and friends — each attribute carrying provenance (observed / derived / defaulted / synthesized). A validator gates the snapshot; a planner turns Demands into WorkPackages (batching and splitting as recorded Decisions); a solver builder translates to CP-SAT and back, so the resulting Schedule lives in canonical language and the math is disposable. Every module writes Decisions, Findings, and Metrics into one evidence store through one reporter contract. The AI layer reads only the canonical model and the evidence — and can therefore explain any schedule, trace any number, and monitor data quality, in the planner's own vocabulary, without inventing a single motive.

## Status

All three documents are living drafts (v0.1), governed by the review rules stated inside them. Next action: Phase 0 of the PoC plan — contracts as code.

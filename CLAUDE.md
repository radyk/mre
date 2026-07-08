# CLAUDE.md — Manufacturing Reasoning Engine

## What this repository is

An AI-assisted production scheduling platform built around a canonical manufacturing
model, an evidence contract, and OR-Tools CP-SAT. The goal is a **manufacturing
reasoning engine**: schedules that are cost-optimized, constraint-respecting, and —
above all — explainable and traceable.

## Authoritative documents (read these first)

The specifications in `docs/` are the constitution of this project. They were
produced through extensive design work and are **authoritative over any other
source, including this file and the legacy code**:

1. `docs/01-canonical-model-spec.md` — the three-model architecture, all canonical
   entities and their attributes, provenance rules, snapshot semantics, design
   invariants.
2. `docs/02-evidence-contract-spec.md` — record types (Decision, Finding, Metric,
   Event, Artifact, RunContext), controlled vocabularies (12 driver codes,
   17 finding codes), the eight Reporter verbs, sink/consolidation rules.
3. `docs/03-poc-plan.md` — module inventory M1–M10, build phases 0–3, solver scope
   cuts, the demonstration script that serves as the acceptance test.

`docs/00-README.md` is a one-page orientation.

## Hard rules (do not violate, do not "improve away")

- **Nothing defines record shapes outside `src/mre/contracts/`.** All modules import
  entity types, record types, and enums from the contracts package.
- **ERP identifiers appear only inside `external_refs`.** The core imports only
  canonical types. The adapter (M1) is the only ERP-aware code.
- **No attribute write without its provenance record** — one API, one transaction.
  Provenance classes: observed / derived / defaulted / synthesized.
- **The Solver Builder never reads the provenance sidecar.** Validation and planning
  may, via a narrow trust interface. The AI layer reads everything.
- **Every Decision carries `basis`** (observed / reconstructed / policy_applied).
  Solution-extraction assignments are always `reconstructed`.
- **Tardiness is evaluated per Demand** (via Fulfillments), never per WorkPackage.
- **Every run executes against an identified snapshot**; every evidence record
  references its snapshot ID.
- **Metrics with `rollup_of` must decompose exactly**; the consolidator verifies.
- **The AI layer (M10) has no write path** into the canonical model or the
  evidence store.
- Vocabulary changes (driver codes, finding codes, entity attributes) are reviewed
  changes: add, never repurpose. Update the relevant spec in `docs/` in the same
  commit.
- **`docs/04-design-history.md` is append-only.** Never recreate or truncate it.
  The founding decision records (D-01 through D-13) are the project's institutional
  memory. New material goes only under the "Amendment log" heading as dated entries.

## Repository layout

```
docs/                 Authoritative specifications (living documents)
legacy/               Previous-generation codebase. REFERENCE ONLY — see legacy/README.md
src/mre/contracts/    L1: entity types, record types, enums, provenance structures
src/mre/reporter/     L2+L3: the Reporter (eight verbs), JSONL sink, consolidator
src/mre/modules/      M1–M7, M10 as they are built (adapter, validator, planner,
                      solver_builder, solve_runner, extractor, explainer)
tests/                Tests derived from the specs — write them from the spec text
```

## Current status / next work

**Phases 0–3 complete, plus real-data ingestion, what-if runner, and IDS
adoption (gate + generator). 624+ tests green.**

Built so far: contracts + Reporter (Phase 0); adapter M1, snapshot store M2,
validator M3, DQ report, identity-map persistence, per-resource Calendars,
Process wiring (Phase 1 + gap-closing); planner M4 (identity_v1 +
merge_by_family_v1 policies), solver builder M5 (six canonical inputs,
VariableMap, plus lock-constraint consumption), solve runner M6, extractor M7
(canonical Schedule, per-Demand ServiceOutcomes, reconstructed-alternative
Decisions, decomposable cost ledger), full `python -m mre` pipeline (Phase 2);
M9 evidence index + M10 explainer + demo script (Phase 3); real raw_data/
ingestion (RawAdapter); the what-if scenario runner (M_whatif). Judgment
calls are recorded in the docs/04 Amendment log.

**IDS adoption (docs/06, this session).** `ModuleCode.M0` — the IDS
conformance gate (`src/mre/modules/conformance.py`, `python -m mre.gate
<submission_dir>`) grades a submission REJECTED / CONDITIONAL / ACCEPTED plus
a C0–C3 costing-completeness grade, against Tier 1/2/3 checks mapped onto the
existing 17 finding codes. `IDSAdapter` (`src/mre/modules/ids_adapter.py`)
translates an IDS submission to canonical entities, including the
customers/setup_transitions/locks doorways; `python -m mre --submission DIR`
runs gate → (if not REJECTED) IDSAdapter → the unchanged M3–M7 spine.
`tools/generate_erp_dataset.py` is the gate's executable twin (8 scenario
presets, a 13-item anomaly catalog, `truth_manifest.json` per submission);
`tests/test_ids_end_to_end.py` is the harness proving the pair against each
other. Full detail, including two real bugs the round-trip caught, in the
2026-07-08 docs/04 amendment.

Immediate next tasks, in order:

1. **Rep 2 — chunking.** `chunking_exam` is currently pipeline-proven only up
   to "correctly excluded via INFEASIBLE_SUBSET." Landing chunked/preemptive
   operation support (docs/03 solver-scope-cut table) turns this scenario
   into a positive acceptance test: long operations should split across
   shift windows and schedule, not just get excluded. Update the scenario's
   truth_manifest expectations in the same change.
2. **docs/05 — Constraint Catalog.** Referenced by docs/06 as "in progress"
   but not yet started. Needs the test-status column (model-proven /
   pipeline-proven / unimplemented) called for in docs/06 §8; the IDS
   harness this session already gives pipeline-proven status to
   customers/priority, setup_transitions, and locks.
3. **Overtime pricing.** Calendar `added`/`overtime` exceptions are recorded
   as capacity fact (model-proven) but the premium is not yet in the solver
   objective — the seam has existed since D-11; `cost_model.refinements.
   overtime_premium_multiplier` is parsed and stored on CostModel but unused
   by M5. Pricing it is the natural next doorway to make pipeline-proven.

## Working style

- Write schema/behavior tests **from the spec documents first**, then implement.
  The specs are executable acceptance criteria.
- Python 3.11+, `pyproject.toml` at root, `pytest` for tests. `ortools` is a
  dependency as of Phase 2; keep it quarantined to solver_builder / solve_runner
  — the canonical Schedule must remain readable with no ortools import (tested).
- Prefer plain dataclasses / pydantic for contracts (choose one and stay
  consistent; pydantic recommended for validation-at-construction, which matches
  the "malformed records die at the source" rule).
- When legacy behavior is needed (Phase 2 solver constraints: chunking, hybrid
  capacity, setup matrices), read `legacy/ProFunctv2_8.py` as the reference
  implementation — port the *logic*, never the *shapes*.

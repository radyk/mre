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

Phase 0 (see `docs/03-poc-plan.md` §3): implement the contracts package and the
Reporter, then the toy-module deliverable — a module that begins a run, emits one
of each record type, ends, and produces a valid consolidated document that passes
the decomposability check. `PHASE0_PROMPT.md` in the repo root contains the
intended opening instruction.

## Working style

- Write schema/behavior tests **from the spec documents first**, then implement.
  The specs are executable acceptance criteria.
- Python 3.11+, `pyproject.toml` at root, `pytest` for tests, `ortools` and
  `pandas` arrive in Phase 2 (not needed for Phase 0).
- Prefer plain dataclasses / pydantic for contracts (choose one and stay
  consistent; pydantic recommended for validation-at-construction, which matches
  the "malformed records die at the source" rule).
- When legacy behavior is needed (Phase 2 solver constraints: chunking, hybrid
  capacity, setup matrices), read `legacy/ProFunctv2_8.py` as the reference
  implementation — port the *logic*, never the *shapes*.

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
4. `docs/05-constraint-catalog.md` — the census of scheduling constraints: locked
   rulings, the full catalog with verdict/plane/status per item, acceptance gates
   (including the defaults-reproduce-baseline modularity gate).
5. `docs/06-incoming-data-spec.md` — the IDS: submission schema, the conformance
   gate's Tier 1/2/3 checks, the costing-completeness grade, doorways (customers,
   setup_transitions, locks, wip_status).
6. `docs/07-roadmap.md` — the live product roadmap (phases, workstreams, open
   rulings queue). **Check this before picking "next work"** — it supersedes any
   hand-written task list here.

`docs/00-README.md` is a one-page orientation. `docs/04-design-history.md` is the
append-only decision log — read its Amendment log tail for the most recent
non-obvious judgment calls before touching an area it covers.

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

**Phases 0–3 complete, plus real-data ingestion, what-if runner, IDS
adoption (gate + generator), and the precedence-edge surgery. 629+ tests green.**

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

**IDS adoption (docs/06, 2026-07-08).** `ModuleCode.M0` — the IDS
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

**Precedence edges (docs/05 §4 surgery, 2026-07-09).** `Operation.predecessors`
and `dwell_duration`/`dwell_rule` are gone; a new `PrecedenceEdge` entity
(`{predecessor, successor, min_lag, max_lag}`, keyed by OperationSpec, docs/01
§5.4a) carries precedence and lags instead — dwell lands as `min_lag` on the
outgoing edge (R-Dwell: phases occupy resources, lags don't). All three
adapters synthesize edges from routing-line sequence; the Solver Builder reads
them (`max_lag` plumbing in place, unconstrained by default — no doorway
populates it yet, docs/05 A3). `tests/test_defaults_reproduce_baseline.py` is
the defaults-reproduce-baseline gate (docs/05 §3): golden fixtures captured
pre-surgery from `sample_data` and a `--horizon-days 2` gauntlet slice (the
documented 173-exclusion window), compared byte-for-byte post-surgery — this
required pinning `PYTHONHASHSEED=0` plus new `--solver-workers`/`--solver-seed`
CLI flags, since CP-SAT's default parallel search is not reproducible
run-to-run even without any code change (see the 2026-07-09 docs/04 amendment
for what that discovery implies for any future "identical schedule" claim).

**Next work: see `docs/07-roadmap.md`** for the live, prioritized plan (Phase
1 exit bar, week-one spikes, cross-cutting workstreams). Do not hand-maintain
a duplicate task list here — docs/07 is the authoritative source and is
updated same-day per its own W2 workstream rule. As of this entry, Phase 1 is
in progress: chunking/splittable operations, overtime premium pricing, outlier
calibration, and the dwell_heavy/overtime_required/calendar_chaos/
multi_facility_balance/scale-ladder generator scenarios are the open items.

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

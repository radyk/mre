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
   18 finding codes), the eight Reporter verbs, sink/consolidation rules.
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
adoption (gate + generator), the precedence-edge surgery, Rep 2
(chunking/resumable operations), Reps 3–4 (outlier recalibration,
merge feasibility & risk guard), and overtime premium pricing + the
resource-rates audit. 680 tests green.**

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

**Rep 2 — chunking / resumable operations (docs/05 R-C3, 2026-07-11).**
`routing_lines.splittable=true` declares the RUN phase resumable;
`SolverBuilder._build_resumable_operation` productionizes the chunk-
boundary-interval encoding two week-one spikes vetted (`tools/
chunking_scale_spike*.py` — element-table encoding falsified RED; `tools/
chunking_spike2*.py` — chunk-boundary encoding verdicted YELLOW). One
optional interval per (eligible resource, candidate calendar window),
sharing that resource's native `add_no_overlap` with non-resumable and
calendar-blocking intervals — no split no-overlap group needed, since chunk
intervals can never overlap a closure by construction. Validator gained a
class-aware window-fit (resumable ops tested against total working time
available before the demand's due date, not a single window) and a density
guard (`STATISTICAL_OUTLIER`/warning when resumable ops/resource > 3, citing
spike 2's measured ceiling). Extraction bills working minutes per chunk, never
the elapsed span including pauses; `schedule.csv` gained a `chunk_seq` column
(one row per chunk, blank for non-resumable ops). Gauntlet counterfactual
(`tools/gauntlet_rescue_report.py`, since raw_data has no real `splittable`
source): **116/173 documented window-fit exclusions rescued**, 57 genuine
survivors. Scale-ladder timings recorded at realistic (~1%) density through
the real pipeline — N=10,000 surfaced two findings spike 2 didn't predict:
CP-SAT's time-limit enforcement overshoots (~1.4x) at this model size, and
the full cost/tardiness objective compounds chunking's search difficulty
beyond spike 2's isolated minimal-model measurement. Full detail in the
2026-07-11 docs/04 amendment; docs/05 catalog C3 moved UI→PP.

**Reps 3–4 (docs/05 §4.3 vocabulary fix, outlier recalibration, merge
feasibility & risk guard; 2026-07-12).** Fixed a vocabulary-governance
violation first: the Rep 2 density guard had been repurposing
`STATISTICAL_OUTLIER` for a structural (not distributional) signal — added
`FindingCode.DENSITY_LIMIT` (18th code) and repointed the guard.
`tools/calibrate_outliers.py` calibrates the `STATISTICAL_OUTLIER` threshold
from a snapshot's actual run-rate distribution (pooled log2-ratio, p99) instead
of a fixed 10x constant; against the gauntlet this collapses the hit rate from
578/4007 (14.4%) to 40/4007 (1.00%), and the 40 survivors all share a
suspicious exact `run_rate_seconds=60.0` — a real, defensible finding, not
noise. `Validator.run()`'s `outlier_threshold_ratio` is config-driven
(`--outlier-threshold`, `plant_config.json`, or the calibrated default);
sample_data's seeded 45x-median scenario keeps its own 10x threshold
explicitly (a different "deployment," its own truth manifest). `merge_by_family_v2`
(`src/mre/modules/planner.py`) re-enables merge batching as a non-default
policy (`--policy merge_by_family_v2`), gated by a feasibility check
(class-aware window-fit on the MERGED batch, closing the post-merge-
infeasibility gap that forced `identity_v1` to become the default) and a risk
check (estimated tardiness exposure vs. a corrected setup-benefit formula,
margin-adjustable via `--risk-margin`) — the WO-2001/WO-2002 case from the
$260 unbatch verdict is now the regression test proving v2 rejects it. A new
standing test (`tests/test_declared_but_unread.py`) guards the "declared but
unread" bug species (third occurrence after `Product.process_ref` and
`min_chunk`) and surfaced real dead fields (`Resource.cost_rate`,
`ResourcePool.members`, `OperationSpec.yield_factor` — see the 2026-07-12
docs/04 amendment). Full detail there; docs/05 D1 updated.

**Overtime premium + resource-rates audit (docs/06 §5.6/§5.9, 2026-07-12).**
The audit closed the dormant-register finding: `resources.csv cost_rate` IS
consumed (adapter-fold into `CostModel.resource_rates`, docs/06 §5.5
precedence default < csv override < refinements) — but the entity field was
written 0.0 under false *observed* provenance (IDSAdapter) and the sample
adapter never folded `machines.csv CostRate`. Both fixed: `Resource.cost_rate`
now carries the effective canonical $/min rate, equal by invariant to its
CostModel entry (`tests/test_resource_rates.py`). Overtime: the builder
computes per-resource premium windows (overtime `added` exceptions minus
regular availability — overlap with a regular shift is NOT premium), charges
the objective the delta rate × (multiplier − 1) per overlap minute (zero new
variables when the multiplier is unset — baseline-gate-critical), and the
extractor splits the ledger into `production_regular_cost` +
`production_overtime_cost` with the assignment Decision carrying
testimony-renderable overtime evidence. `overtime_required` generator
scenario + `tests/test_overtime_end_to_end.py`; its strip-the-windows
counterfactual caught a real scenario bug (the base generator calendar is
six-day; Saturday had to be genuinely closed) — see the 2026-07-12 docs/04
amendment ("a priced feature's test must include the counterfactual that
proves the price bought something").

**Next work: see `docs/07-roadmap.md`** for the live, prioritized plan (Phase
1 exit bar, week-one spikes, cross-cutting workstreams). Do not hand-maintain
a duplicate task list here — docs/07 is the authoritative source and is
updated same-day per its own W2 workstream rule. As of this entry, Phase 1
reps and overtime premium pricing are done; remaining Phase 1 work is the
dwell_heavy/calendar_chaos/multi_facility_balance generator scenarios and
then the Phase 1 exit demo (docs/07 §3: messy generated plant → certificate
→ costed schedule → why → what-if → verdict, then the ticketing gauntlet
passing clean). The solver-gap/model-richness interaction found during Rep 2
is a concrete input to the parked solver-gap workstream.

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

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
   entities and their attributes (incl. PrecedenceEdge, docs/01 §5.4a), provenance
   rules, snapshot semantics, design invariants.
2. `docs/02-evidence-contract-spec.md` — record types (Decision, Finding, Metric,
   Event, Artifact, RunContext), controlled vocabularies (12 driver codes,
   18 finding codes), the eight Reporter verbs, sink/consolidation rules.
3. `docs/03-poc-plan.md` — module inventory M0–M10 and the original PoC phases
   (historical; superseded for planning by docs/07).
4. `docs/05-constraint-catalog.md` — the census of scheduling constraints: locked
   rulings (R-B3, R-C3, R-B7/B8, R-A2/A3, R-A4, R-Dwell), the catalog with
   verdict/plane/status per item, acceptance gates (incl. the
   defaults-reproduce-baseline modularity gate).
5. `docs/06-incoming-data-spec.md` — the IDS: submission schema + manifest declared
   semantics, the conformance gate's Tier 1/2/3 checks, the C0–C3
   costing-completeness grade, doorways (customers, setup_transitions, locks,
   wip_status §5.13).
6. `docs/07-roadmap.md` — the live product roadmap (vision, phases, workstreams,
   open rulings queue). **Check this before picking "next work"** — it supersedes
   any hand-written task list here.

`docs/00-README.md` is a one-page orientation. `docs/04-design-history.md` is the
append-only decision log — **read its Amendment log tail before touching any area
it covers**; the full build history (IDS adoption, edge surgery, chunking spikes
and Rep 2, Reps 3–4, overtime premium, the Phase-1 exit audit) lives there, not
here.

## Hard rules (do not violate, do not "improve away")

- **Nothing defines record shapes outside `src/mre/contracts/`.** All modules import
  entity types, record types, and enums from the contracts package.
- **ERP identifiers appear only inside `external_refs`.** The core imports only
  canonical types. Adapters (M1 family) are the only ERP-aware code.
- **No attribute write without its provenance record** — one API, one transaction.
  Provenance classes: observed / derived / defaulted / synthesized. Provenance must
  be TRUTHFUL: writing a constant under an `observed` sidecar is a defect class
  (see 2026-07-12 amendments).
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
  changes: **add, never repurpose**. Update the relevant spec in `docs/` in the
  same commit.
- **`docs/04-design-history.md` is append-only.** Never recreate or truncate it.
  New material goes only under the "Amendment log" heading as dated entries.
- **Any "identical schedule" claim requires deterministic mode**
  (`--solver-workers 1 --solver-seed …`, `PYTHONHASHSEED=0`) — CP-SAT parallel
  search is not reproducible (2026-07-09 amendment).
- **Phase exits are audited by a fresh session in audit mode** (no fixes unless
  failure; every accommodation named) — the Phase-1 exit found seven
  proven-from-one-side seams this way.

## Repository layout

```
docs/                 Authoritative specifications (living documents)
legacy/               Previous-generation codebase. REFERENCE ONLY — see legacy/README.md
src/mre/contracts/    L1: entity types, record types, enums, provenance structures
src/mre/reporter/     L2+L3: the Reporter (eight verbs), JSONL sink, consolidator
src/mre/modules/      M0 (conformance gate), M1 adapters (sample / raw / IDS),
                      M2–M7 spine, M9 index, M10 explainer, scenario runner,
                      schedule-document assembler
src/mre/api/          FastAPI surface (thin, no business logic) + SQLite
                      run/schedule registry; run-dir minting lives here
tools/                Generator, calibration, spikes, viewers, profilers
tests/                Tests derived from the specs — write them from the spec text
```

## Current status

**Roadmap position: Phase 3 IN PROGRESS — frontend bake-off SPIKE complete
2026-07-11.** Throwaway spike (`tools/spikes/frontend_bakeoff/`, nothing ships)
choosing the cockpit's drag-surface substrate. **Both candidates GREEN on the
mechanics**, both headlessly driveable (custom React SVG+dnd-kit vs vis-timeline;
shared fixture from a real `messy_realistic` solve + shared snap core + a
surviving candidate-agnostic Playwright harness). Neither hard-failed criteria
1/3/5; vis-timeline's one material blemish is **in-bar-text clipping** (priced
ghost labels truncate → need a fragile overlay layer). **Recommendation
(rule: library wins ties): adopt vis-timeline, conditional on a stable
label-overlay follow-up; custom React is the zero-blocker fallback.** Verdict at
`tools/spikes/frontend_bakeoff/VERDICT.md`; **docs/07 frontend line intentionally
NOT updated — to be settled in joint review.** Spike findings/carry-forwards:
(a) the generator has **no capability-based multi-eligible routing** (every op
routes to one resource), so it cannot yet produce a faithful drag fixture — a
W1/Phase-3 prerequisite for real Tier-0/Tier-1 anchor computation; (b)
`merge_by_family_v2` traced (carry-in): design-reviewed, origin `847fe89`, added
to the solver-gap dossier's tractability-lever entry alongside v1. See the
docs/04 2026-07-11 amendment.

**Roadmap position: Phase 2 COMPLETE (qualified) — entering Phase 3.**
Phase-2 exit **audited by a fresh session 2026-07-10** (audit mode, no fixes
unless a clause fails): all five exit-prompt clauses PASS / PASS-WITH-
QUALIFICATION, **fix-free** (Clause 6 addenda resolved at `acb75b8`). Live
evidence: exit demo byte-identical across two fresh API runs (7460 assignments);
API 409/listing invariants; warm-start 0-vs-51-move noise case at identical cost
delta; pool diversity@15min + snapshot byte-identity + supersede-invalidation;
mid_replan WIP counterfactual + sunk-setup ledger; three certificate registers
with §-cited remediation + jurisdiction rule; gauntlet reproduces its golden
byte-identically with the 173-exclusion anchor (default `identity_v1`, 0 merges;
`merge_by_family_v1`/`_v2` both exist as opt-in). **Carried exit qualifications:**
cloud in-cloud confirmations (in-container CI + live `az deployment` + cloud
smoke) OPEN → **2.4b** (Docker/Azure unavailable at audit); raw_data path
bypasses M0 gate / no WIP doorway → Phase 4; pool slice-awareness + warming-on-
publish → Phase 3; two quarantined catalog notes (no IDS §-cite) → design-thread
note_version fix; W1 scenarios `dwell_heavy`/`calendar_chaos`/
`multi_facility_balance` + sentinel-value detector + provenance spot-check guard
+ `yield_factor` false-observed provenance → OPEN, re-parked (W1/Phase 3);
`test_n3000` contention-sensitive. See the docs/04 2026-07-10 exit-audit
amendment and docs/07 v1.7. Certificate session
(groundwork) done 2026-07-10: **the M0 gate is now a Rule Registry** — 32 named
rules (`src/mre/contracts/ids_rules.py`, the single source that renders docs/06
§4), closed outcome vocabulary (satisfied/flagged/degraded/violated), grade as a
pure function of outcomes, evidence-shape refactor (typed `GateFindingEvidence`
with rule_id; banded rules record a Metric, emit a Finding only on non-satisfied;
severity derives from outcome; findings name typed submission-space subjects
`EntityRef(system="IDS")`, reachable by canonical key via the M1 identity map).
Seven checks made real + the routes_resolve_to_lines unfold + the
transition-matrix converse split; `manifest_semantics_declared` recoded
MALFORMED_FIELD→AMBIGUOUS_SOURCE. Coverage-matrix + reverse-guard tests make the
registry complete-by-construction. **840 tests green** (+45). Docs §4 (docs/06),
docs/07 v1.5, docs/02 boundary rule 1, docs/04 amended. **Conversational
Certificate landed 2026-07-10** (catalog v1 frozen, renderer/router/triage
live): frozen `remediation-catalog-v1.yaml` (32 rule notes + 18 fallbacks) at
`src/mre/catalog/`, typed + completeness-tested; three answer registers —
testimony / **remediation** (authored, single-source-of-truth number validator,
fail-closed) / **judgment** (one grade-distance triage: violated → degraded by
closest escape → flagged, quality last); explainer routes cert questions through
identity, never id-shape regex; REJECTED runs answer certificate-only (index
built pre-stop, no snapshot). `APPENDIX_A_BANDS` single source resolves the
catalog's `appendix_a.*` anchors. **Errand (a):** `wip_in_progress_rows_carry_progress`
disposition `DEFAULTED`→`EXCLUDED` (gate + adapter) — no progress value is
invented, the in-flight claim is excluded. **Errand (b):** docs/06 §4 severity
reworded as a function of **(outcome, category)**. **Reported, not fixed** (frozen
prose, report-don't-edit): two quality notes'
`fix_looks_like` carry no resolvable IDS §-cite — quarantined + pinned, a
design-thread note_version fix. **985 tests green** (+145); docs/06 §4 + docs/04
amended. Session 2.4 done
2026-07-14: **cloud deploy, encrypted (W4 baseline)** + the 2.3-review
carry-ins. **CU0:** WIP finding-code review (all five checks reuse existing
codes within their meanings; `wip_sequence_order_violation → LOW_CONFIDENCE_INPUT`
named as closest-to-a-stretch and justified; no new code) · **resumable
in-flight remainder now RESPECTS calendars** (`_place_inflight_remaining`
greedily fills working windows; non-resumable keeps the contiguous carve-out —
"the future respects calendars even when the past didn't") · op-count
reconciliation (13,315/14,042/4,088/4,933 = planner-policy × splittability
rescues) + dossier entry #2 (merge as ~3.3× tractability lever vs the +$260
cost-loss verdict; pilot entry conditions must declare their policy) ·
**sunk-setup ledger** (completed/in-flight ops bill zero movable setup; separate
non-decomposing `sunk_setup_cost` line; counterfactual on mid_replan). **CU1:**
multi-stage Dockerfile (non-root, pinned lockfiles, `/health`, image-as-shipped
CI) + compose parity; `TestGauntletReproducesBaseline` guarded to skip when the
gitignored raw_data is absent. **CU2:** Caddy TLS overlay (`tls internal`) +
encryption-at-rest as a volume property + secrets via env injection only + CI
gitleaks secret-scan + **docs/08-security-posture.md** (single-tenant-by-
construction with the named tenant-#2 trigger). **CU3:** `deploy/azure/` (Bicep +
deploy.sh + provider-swap-boundary README) + provider-agnostic `deploy/smoke.py`;
**exit demo demonstrated locally** — clean_large ~3K orders → ACCEPTED/C1 →
7,460-assignment schedule via the API in ~165s (deterministic), baselines in
`deploy/scale_ladder.json`. **795 tests green** (+5). **Carried gap:**
deploy-verified-LOCALLY, not in-cloud (no Docker / no live Azure this session —
Bicep unvalidated vs ARM, image not built, smoke ran against a local server);
first in-container CI run + live `az deployment` + cloud smoke are the
confirmations. Session 2.3 (WIP) `5600de2`; 2.2 `86e0115`; 2.1 `517b1fe`;
Phase-1 exit audit `9a70e5c`. Qualification carried (owned by Phase 4): the
raw_data path bypasses the M0 gate (no WIP doorway there either) — resolved by
the pilot connector; the raw path is then demo-frozen.

**Phase 2 mission (docs/07):** ~~API layer + schedule JSON contract~~ ·
~~warm-start scenario solves~~ · ~~solution-pool service~~ · ~~solver-gap
probe~~ · ~~WIP/soft-start doorway (docs/06 §5.13 + mid_replan scenario)~~ ·
~~cloud deploy with encryption (W4 baseline; single tenant by construction)~~
(done, sessions 2.1–2.4; cloud deploy verified locally, in-cloud carried) ·
~~Conversational Certificate (router domain + remediation catalog; jurisdiction
rule: coach the IDS requirement, never ERP-specific surgery)~~ (done 2026-07-10).
**Phase 2 mission complete** — all workstreams landed (cloud deploy in-cloud
confirmation still carried from 2.4).

**Small carry-forwards (queue behind Phase 2 items, do not lose):**
`OperationSpec.yield_factor` still carries false observed provenance
(flagged 2026-07-12, not fixed) · sentinel/repeated-identical-value detector
(the 40× `run_rate_seconds=60.0` fingerprint from Rep 3) · provenance
spot-check guard (sampled: `observed` values must appear in the cited source) ·
W1 scenarios not yet built: dwell_heavy, calendar_chaos,
multi_facility_balance (mid_replan now built) · pool warming-on-publish
becomes the default when the Phase-3 publish workflow exists (auto-warm is
opt-in until then) · **pool must become slice-aware before serving
sliced-mode schedules** (2.3 probe carry: members rebuild from the run's
M5 horizon, not a sliced run's per-slice selection) · **cloud deploy
in-cloud confirmation** (2.4 carry: live `az deployment` from `deploy/azure/`
+ cloud smoke, and the first in-container CI run — Docker/Azure both
unavailable in session 2.4, so verified locally only). [extractor
sunk-setup billing — RESOLVED 2.4 CU0.5.]

**Do not hand-maintain a duplicate task list here** — docs/07 is authoritative
and updated same-day per its W2 rule; this section records only position,
qualifications, and carry-forwards.

## Working style

- Write schema/behavior tests **from the spec documents first**, then implement.
  The specs are executable acceptance criteria.
- Python 3.11+, `pyproject.toml` at root, `pytest` for tests (`--runslow` opts
  into the slow ladder). `ortools` stays quarantined to
  solver_builder / solve_runner — the canonical Schedule must remain readable
  with no ortools import (tested).
- Pydantic for contracts (validation-at-construction: "malformed records die at
  the source").
- Deterministic mode for any baseline or regression comparison (see hard rules).
- Legacy code is reference-only for remaining ports (hybrid workcenter capacity,
  setup-matrix shapes): read `legacy/ProFunctv2_8.py`, port the *logic*, never
  the *shapes*.
- A priced feature's test must include the counterfactual proving the price
  bought something (2026-07-12 amendment).

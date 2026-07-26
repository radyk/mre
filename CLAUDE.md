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
src/cockpit/          L-frontend: the reasoning cockpit (Vite + vis-timeline,
                      read-only). Renders a contract-1.2 document from the API;
                      talks to the core over HTTP only. Design tokens in
                      tokens.css. (interim-A, Phase 3)
tools/                Generator, calibration, spikes, viewers, profilers
tests/                Tests derived from the specs — write them from the spec text.
                      tests/cockpit/ = the Playwright screenshot harness (CU5).
```

## Dev API quick reference

Start it: `.\src\cockpit\dev_api.ps1` (repo root; serves `http://localhost:8000`,
`MRE_DATA_ROOT=./_data`, `MRE_DEV=1`). Every response is `{"api_version","data"}`.
Submitting is always TWO steps — gate first, solve second (field names live in
`SolveRequest`, `src/mre/api/app.py`; a REJECTED submission never solves):

```
POST /submissions                {"path": "C:/abs/path/to/submission_dir"}
    -> data.submission_id, data.grade (ACCEPTED|CONDITIONAL|REJECTED), data.deficiencies
POST /submissions/{id}/solve     {"policy":"identity_v1","deterministic":true,
                                  "sliced":true,"window_days":14,"frozen_days":3,
                                  "time_limit":900}
    -> data.run_id (202, async unless "sync":true)
GET  /runs/{run_id}              -> data.status, data.result.schedule_id
GET  /schedules                  -> every registered schedule (the cockpit's list)
```

A submission dir is IDS files (`manifest.json` + the seven required tables), NOT a
generator scenario name or a profile dir; generate one with
`python tools/generate_erp_dataset.py --scenario <name> --out <dir>`. `time_limit`
is the solver's WALL CEILING, not its budget — under `deterministic:true` the
deterministic budget is what must bind, so keep it generous.

One command for a rolling run in the cockpit (builds the pinned world, verifies
its determinism, submits, solves, prints the schedule id to select):

```
python tools/build_rolling_exam_run.py --register
```

**`?schedule=<id>` is authoritative** (2026-07-26 hotfix). The cockpit loads that id,
never rewrites the param, and never auto-follows a newer schedule off it — an unknown
id is a named error over the schedule list, never a substitution. Only a boot WITHOUT
the param resolves from the listing and auto-follows a resubmit (Session 4.4 CU2).
To switch boards, click the strip's identity chip (`solve #N`): the **schedule
picker** lists the registry newest first, tagged rolling vs monolithic. NB
`dev_cockpit.ps1` mints a fresh busy_board solve on every boot unless `-Resume`, so
the data root's newest row is usually the last dev restart, not your work.

## Current status

**Roadmap position:** Phase 3 COMPLETE (qualified); Phase 4 preparation. Last closed:
**AI-track Session 4A.5c — R-AI5 part 3: telemetry, the Pareto, the promotion
pipeline (the R-AI5 arc CLOSED)**, 2026-07-26 (docs/07 v2.46; docs/04 amendment same
date). The working thread returns to the 4B mission.

**The ask path (R-AI5) — two tiers, sealed from each other, and a loop between
them.** Every question is parsed FIRST by a model against the closed intent
vocabulary (`src/mre/contracts/parse.py`), with the conversation history, the live
board selection and the last-answered subject as context. **No deterministic
classifier survives anywhere** — `Explainer.classify` / `answer` went in 4A.5a and
`rolling_questions.classify_rolling` (the last one) in 4A.5c. They must not come back.

- A **matched** intent dispatches into the unchanged route assembly, render and
  validator — unless the parse reports a **dropped qualifier** (a time scope, an
  "actually", a comparative the route cannot honour), which diverts it to the second
  tier and names the qualifier in the rendered-by line. The parse REPORTS; the
  dispatch decides.
- An **unmatched** intent goes to **labeled open synthesis** (R-AI5(2)): a model
  reasons over the closed read-only tool surface (`src/mre/modules/evidence_tools.py`)
  under a stated budget and drafts structured CLAIMS, hardened claim-by-claim by
  `claim_verifier` — **deterministic code, never a model** — into VERIFIED /
  INTERPRETIVE / FAILED-and-cut. Provenance is visible per claim, the register is
  `synthesis`, "prove it" re-runs the grounding pass on one claim, and the
  couldn't-answer floor keeps its nearest-capabilities doors.
- Otherwise a matched intent can NEVER fall to synthesis, and an unmatched one NEVER
  guesses a route (pinned by dispatch tests). Without a parser or a synthesizer the
  honest floor answers that it could not interpret / could not ground.
- On a **rolling** run, subject resolution reads the document's three regions
  (`RollingVocabulary`): a beyond-horizon tray order resolves as a real subject with
  a BEYOND-HORIZON disposition and every placement question about it lands on
  `why-not-scheduled-yet`. **A tray order is never "not in this schedule."**

**THE PROMOTION LOOP (R-AI5(5)/(7)) — the system proposes its own healing; the
proven register is entered only by review.** Every sweep writes a question ledger and
emits `tools/provenance_report.py`: synthesis residue clustered into recurring shapes
(adjacency + subject kinds + dominant tool, method stated in the report), ranked by a
frequency-weighted Pareto. **R-AI5(6) is printed in the report's own header** —
clusters whose residue is takes or aggregate reads are NOT-PROMOTABLE-BY-DESIGN,
excluded from the Pareto, never counted as backlog.

- `tools/promotion_dossier.py` drafts a dossier autonomously (`docs/promotions/`) and
  **cannot reach dispatch**. The dossier is the application; the working thread's
  review is the signature.
- Promotion is a **reviewed vocabulary-class change** (Intent + meaning + taxonomy +
  offer + assembler + authored copy + prompt bump + a `PROMOTIONS` entry citing the
  dossier). **Never automatic.**
- A promoted route runs **shadowed** through its probation: the sweep answers its
  shape under both paths and diffs the facts. **Demotion is automatic** on a
  contradiction — one field in `contracts/promotion.py`, and the intent leaves
  `model_selectable_intents()`, so the parse can no longer name it and the shape
  returns to the second tier.
- Live: **one** promotion, `lateness-cause` (the aggregate-lateness shape), on
  probation.

**R-AI5(8) is the hard rule of the tier:** the answering model's beliefs about its
own citations are INPUT to verification, never the label — and the same discipline
now governs routing (the parse reports a dropped qualifier; it never decides the
diversion). Both prompts (`parse_prompt.md` v7, `synthesis_prompt.md`) are governed
artifacts: changing either is a vocabulary-class change, reviewed, versioned,
committed with its doc update.

**Where history lives — do not duplicate it here:**

- `docs/07-roadmap.md` is authoritative for *what comes next*. Check it before
  picking up work. It is updated same-day per its own W2 rule.
- `docs/04-design-history.md` is authoritative for *what happened and why*. It is
  append-only. **Read the Amendment log tail before touching any area it covers.**
- Session close-outs are written to docs/04 and docs/07 — never narrated here.

**Carried qualifications (open, owned):**

- Cloud deploy is verified **in-container**, not **in-cloud**: live `az deployment group
  create` from `deploy/azure/` + cloud smoke remain PARKED on the Azure trigger; the
  Bicep is still ARM-unvalidated (Session 2.4 carry, partially retired 2.4b).
- The `raw_data` path bypasses the M0 gate and has no WIP doorway — owned Phase-4 debt
  (RawAdapter retirement / pilot connector); the live gate-free entry points are named in
  docs/04's 4B.2c R-SC1 correction.
- Phase 3's **cold-stranger cold-drive** is MET-BY-PROXY only — a named Phase-4 *entry*
  condition, not relaxed.
- Daryn's feel-token export is not yet committed; the cockpit runs on `DEFAULT_FEEL`.
- Two remediation-catalog quality notes carry no resolvable IDS §-cite (quarantined +
  pinned) — a design-thread `note_version` fix.
- Pool service must become **slice-aware** before serving sliced-mode schedules;
  warming-on-publish becomes the default when the publish workflow lands.
- `test_n3000` is contention-sensitive (green in isolation).
- The **parallel-load screenshot-flake** class is standing debt (two members: 3.1c
  0-bars, 4A.3 planner due-marker; both pass in isolation).
- Product naming is under review in the GTM thread — "MRE" is the working repository
  name, not a confirmed brand.

**Small carry-forwards (do not lose):**

- `OperationSpec.yield_factor` still carries false `observed` provenance (flagged
  2026-07-12, not fixed).
- Sentinel / repeated-identical-value detector (the 40× `run_rate_seconds=60.0`
  fingerprint from Rep 3).
- Provenance spot-check guard: sampled `observed` values must appear in the cited source.
- W1 scenarios not yet built: `dwell_heavy`, `calendar_chaos`, `multi_facility_balance`.
- AI-track named debts: the docs/05 structured-constraint surface (prose-locked,
  retrieval must never read prose); machine-idle eligibility naming no specific ops
  on the monolithic path; per-order PRODUCTION-dollar attribution (a ledger change).
  (Aggregate-cause coaching is RETIRED — promoted to `lateness-cause`, 4A.5c.)
- R-AI5 residue, carried: start-reason's early-vs-plain read is still the
  assembler's (only a NEGATIVE polarity is authoritative from the parse); a CLARIFY
  turn carries no subject forward.
- Promotion-loop limits (4A.5c): clustering is crude-but-stated and UNDER-states
  frequency (it splits shapes whose parses disagreed) — merging is a human's, in a
  dossier. The shadow diff compares only figures BOTH sides state about the same
  labelled quantity, which on the promoted shape is thin overlap: the teeth are
  real but narrow. The two-phase ask's first beat names the tool BUDGET, not a live
  count — a real ticking count needs streaming or background execution.
- Synthesis-tier named limits (4A.5b): a claim's COUNT is checked against the
  toolbox's own tallies for the enumerating call, not typed to the predicate it
  sits beside; percentages and ratios the model computes are never verifiable and
  land interpretive by construction.
- A splittable op with `rate_overrides` uses the scalar default duration; a heterogeneous
  op's `var_map.op_durations` scalar is the default representative (rate-varying pins
  unexercised).
- Pilot-volume latency (174 workcenters) is UNMEASURED — every committed figure is demo
  density.

Everything else — what a session built, its test counts, its commit — lives in docs/04
and docs/07. Do not restate it here.

---

**Maintenance rule for this section.** This file is loaded into every session and
has a hard character ceiling. On 2026-07-25 it reached 191,692 bytes against a
150k limit, of which 94% was a session changelog duplicating docs/04 — pushing
`## Working style` to the far end of a file that was no longer delivered whole.

This section records **position, qualifications, and carry-forwards only**. It
does not record what a session built, how many tests it added, or which commit
carried it. `CLAUDE.md` is checked against a **40k-char ceiling at every phase
exit**; if it is over, the status section is the first thing to shrink.

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
- **Sessions commit to `master` directly and push — no session branches, no
  PRs** (the working pattern since Session 3.0). Push after every session commit
  (see the README). A session branch may exist transiently, but it fast-forwards
  into `master` and is deleted at close; `master` is the trunk.

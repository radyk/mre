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

The COARSE ZONE is **opt-in per solve** — `"coarse": true` on a `sliced` SolveRequest
(4B.6a). `"reference_date": "2026-01-12"` rolls the clock; without it every solve of a
submission renders the SAME window, so cross-roll prediction history never accrues.
A coarse solve mints predictions into `<run_dir>/coarse_predictions.jsonl` and judges
every earlier roll's against this window (`coarse_realizations.jsonl`); the counts and
any store error come back on `run.result.coarse_history`. A store failure never loses a
schedule and is never swallowed. Module level, unchanged:

```python
from mre.modules.coarse_horizon import build_coarse_zone
zone = build_coarse_zone(plant, view)              # rho/bucket_days from the cost model
doc  = assemble_rolling_document(..., coarse_zone=zone)   # 1.9 blocks appear
```

`zone.certificate_block()` carries rho + its provenance (acceptance: a hidden default
is a failure). Declare the coefficients in a submission via `cost_model.json`
`refinements.coarse_horizon = {"bucket_days": 7, "capacity_derate": 0.85}`.

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
`dev_cockpit.ps1` RESUMES the cached board by default (4B.5 CU4e); `-Fresh` mints a
new solve. Before that it minted one every boot, so the data root's newest row was
the last dev restart rather than your work — and the freshness watch, correctly,
kept offering to follow it.

## Current status

**Roadmap position:** Phase 3 COMPLETE (qualified); Phase 4 preparation. Last closed:
**Session 4B.8 — the budget split, the status ruling, and the 14-day diagnosis**,
2026-07-28 (docs/07 v2.53; docs/04 session amendment same date; full table in
`SESSION_CLOSEOUT.md`).

**THE TWO-STAGE BUDGET IS DERIVED, NOT A CONSTANT (CU2).** The caller declares a
TOTAL (`det_total`); stage 1 is capped at total minus a **1/12 RESERVE**; **stage 2
gets what the total has left after stage 1 actually ran**. `_STAGE2_DET_TIME_S = 2.0`
is DELETED from both twins. Measured first (`tools/spikes/alloc_4b8/`, 3 policies x
6 instances x 5 seeds): the old fixed split **loses the COST PROOF at 200 orders**
(two seeds need 4.542/4.962 units against a 4.0 cap — ledger 35,127.05 vs the optimum
**27,863.63** the alternatives prove 5/5 with **zero** spread), while a plain
cost-first remainder gives stage 2 **ZERO on 5/5 seeds at 120 orders** and silently
retires the tiebreak. The reserve is what keeps R-SC3(1) true at scale. NB the
parameter was **RENAMED `det_time` -> `det_total`**, not reinterpreted: the old total
was `stage1 + 2.0`, so no single multiplier preserved every caller (6.0 default, 4.0
exam/fixture, 2.5 golden driver) — each now declares its own. The MONOLITHIC path
passes `cap_stage1=False` (its cost proof stays uncapped) with a 2.0 total; raising
that was measured and REJECTED (−0.01% start-minutes for 2.5x the wall clock).

**THE STATUS LINE REPORTS THE COST PROOF (CU3 — a RULING, contract 1.9 -> 1.10).**
`solver.status` carries **STAGE 1's** status; new Optional `solver.tiebreak_status` /
`tiebreak_skipped_reason` carry stage 2's. Stage 2 exhausts its budget above ~8
orders, so every rolling board used to read FEASIBLE over a provably OPTIMAL ledger.
**A schedule whose cost is proven optimal SAYS SO, and an unproven tiebreak never
downgrades that claim.** A tiebreak that never ran is distinguishable from one that
ran and won nothing. **§5a.23 is the standing debt: NOTHING VOICES IT** — neither the
cockpit nor the answer surface reads any solve status (an R-AI1 debt, named not
built, per the brief).

**`EARLINESS_PREFERENCE` IS DORMANT (CU4, interim only).** The extractor no longer
emits it and `earliness_value` is DELETED from `_assignment_driver`'s signature. The
fallthrough was checked FIRST and is better: `CAPACITY_BLOCKED` carries real
occupancy evidence (4B.5 CU3a), and under a cost-only objective a dearer eligible
choice IS capacity. **The DriverCode member SURVIVES and docs/07 §5a.20 stays OPEN**
for the vocabulary migration. The declared-but-unread guard was resolved by a
dormant-register entry, never by widening.

**§5a.15 DIAGNOSED, NOT FIXED (CU5): THE 200-ORDER / 14-DAY INSTANCE IS FEASIBLE** —
a solution in **0.082 deterministic units** once the objective is dropped, so this is
**NOT an R-SC2 admission defect**. Build time is 0.05–0.19 s and ops-per-machine peaks
at **92**, killing both standing hypotheses. The cliff is between **8 and 9 days** at
200 orders, and is **NOT general**: 200 orders proves optimality at 123 free ops while
120 orders fails at 115, so neither n_free nor ops/machine predicts it. At 14 days the
COST solve finds **nothing at all** in 6.0 units while satisfiability takes 0.082 — a
factor of **74**. **Discharged: §5a.19, §5a.21.**

**PRE-FLIGHT: the missing API key was LOADER WIRING.** `.env.local` was present all
along; `tests/conftest.py` had no loader while `tools/run_ai_exam_sweep.py` carried
the repo's only one. Now loaded in conftest (repo-root anchored) — **the four blocked
slow tests pass**. No `skipif`, no assertion weakened, the r5 bank still NOT run.

Before it: **Session 4B.7 — the earliness price is removed from the objective**
(docs/07 v2.52).

**R-SC3(2) IS RETIRED — `earliness_value` IS NO LONGER A PRICE.** Stage 1 of the two-stage
solve minimizes COST ALONE on both paths, and the coefficient parameter is DELETED from
both signatures (`solver_builder.solve_two_stage`, `rolling_horizon._two_stage_solve`) so
it cannot leak back. **R-SC3(1) stands and is now genuinely implemented: stage 2 IS the
tiebreak and runs UNCONDITIONALLY** at every coefficient including 0 and undeclared.
Measured (`tools/spikes/tiebreak_4b6c/`, arm **A0s**, 6 instances x 5 seeds): the price cost
**+73.20%** of ledger total at 40 orders / **+97.61%** at 120 against a cost-only arm whose
seed spread is exactly zero. Staged cost-only reproduces the PROVEN OPTIMUM to the cent at
5/8/15/40 orders (OPTIMAL 5/5) while spending **45.53% fewer start-minutes** at 40.
`earliness_value` survives as a **REPORTING rate** (`_earliness_rate`,
`earliness_tiebreak_report`): it values the start-minutes the tiebreak recovered, on its own
labelled line, `in_ledger: False`, never in `cost_summary.total` and never in a delta card's
money. **THE INVARIANT, ASSERTED: the SCHEDULE is byte-identical across every
`earliness_value`** (0 / declared / 100x declared) — a failure means the coefficient is back
in the objective, and that is the only way it can return.

**Four findings DISCHARGED, three of them by construction:** §5a.16 (rolling now returns
stage 1's COST objective with stage 2's placements — monolithic 300 / rolling 300, was
400/20); §5a.17 (the pool's stated 5% is 5%, was 40% — no gap remains, so no second cause);
§5a.12 (`reopt_delta_abs` **−11,975.83 → exactly 0.00**; the card was NOT relabelled);
§5a.9 (the fixture's ~7.9%-dearer incumbent is gone — the board now sits at the proven
optimum **16,481.95, tardiness 0.00**). Fixtures regenerated under a spent single-use
authorization, every figure accounted BY OPERATION IDENTITY, reproducing across
PYTHONHASHSEED 0/1/2. Before it: **Session 4B.6c — measurement** (docs/07 v2.51), which
priced the tiebreak and found candidate B worse; **Session 4B.6b — errand: four answers**
(v2.50); **Session 4B.6a — consolidation**.

**THE COARSE ZONE (R-SC2 amendment, 4B.6).** Beyond-horizon demand is coarsely
PLACED, not merely listed (`src/mre/modules/coarse_horizon.py`; contract **1.9**
adds `BeyondHorizonItem.coarse` + `RollingBlock.coarse_zone`, both Optional and
absent on a monolithic run). Seven clauses govern it, and the ones that bite:

- **RELAXATION, ALWAYS.** Only the NEGATIVE is claimed — coarse-INFEASIBLE implies
  fine-INFEASIBLE; **the converse is never asserted in code, certificate or AI
  answer.** The relaxation guard (`tests/test_coarse_horizon.py`) makes this a
  theorem, and its NEGATIVE CONTROL proves the guard can go red.
- **THE PROOF RUN AND THE PLANNING RUN ARE DIFFERENT RUNS.** `proves_infeasible`
  is the only gate the negative escapes through: False for a planning run, a
  FEASIBLE run, and a wall-truncated one.
- **rho IS A DECLARED IDS COEFFICIENT** (docs/06 §5.9 `refinements.coarse_horizon`),
  pipeline-proven per §8. Defaulted rho is **1.0 — a no-op derate**; an undeclared
  plant is never given an invented margin, and provenance prints beside the value.
- **COARSE NEVER CONSTRAINS FINE, nor its admission policy** — enforced as an
  import-direction test. Unlock condition is stated in docs/07 §5a, not left to drift.
- **TWO LEDGERS, NEVER FUSED** — enforced by SHAPE: coarse tardiness is counted in
  BUCKETS and there is no currency field on the coarse surface at all.
- **COARSE NEVER RENDERS AS A BAR** — a density band (`src/cockpit/src/coarse.js`).
- Predictions are persisted OUTSIDE the document (`coarse_predictions.py`): the
  document is a window-0 view, the audit is cross-roll. Realization is captured on
  both intake paths — natural roll and **gravity admission** — and since 4B.6a the
  rolling worker actually WRITES it (`record_roll_history`), judging each prediction
  exactly once however many rolls sweep past it.
- **EVERY LOAD FIGURE NAMES WHAT IT DID NOT COUNT** (4B.6a). Resumables and
  over-capacity ops consume ZERO coarse minutes, so load is understated — answers,
  tooltips and the band footer say so, and say nothing when nothing is excluded. A
  plant with **no declared derate** is told loudly that its figures assume full
  utilization; that is a docs/06 §5.9 remediation note, **not a gate rule** (36
  rules, unchanged).
- Resumable ops are EXCLUDED and NAMED (`coarse_unmodelable`), because
  single-bucket forcing would TIGHTEN the relaxation. The exclusion is what makes
  clause (1) true; the ruling's own "permissive" parenthetical is corrected in
  docs/04.
- Ask path: `coarse-fit` + `bucket-load` join the closed vocabulary (parse prompt
  **v9**). "When will ORD-X start" gets NO new route — it is
  `why-not-scheduled-yet`, now carrying the coarse bucket BESIDE the untouched
  `earliest_window_estimate` heuristic (two figures, two methods, never fused).

**THE DELTA CARD SPLITS ITS VERDICT (4B.5 CU1).** `cost_delta_abs` measures the
RE-SOLVE, not the move — two different gestures on one incumbent produced identical
cards to the cent. Beat two also solves the window WITHOUT the pin (the BASELINE,
cached per incumbent) and the card always shows *window re-optimization* (baseline
vs incumbent) beside *your move* (pinned vs baseline), summing exactly to the total.
**A planner's move is judged against the baseline, never the stale incumbent.** An
unprovable baseline shows the unsplit total with an explicit "includes window
re-optimization" line — never a silent fused number, never a half split.

**R-F1/R-F2/R-F3 are RULED and RECORDED, not built** (4B.5 CU6; verbatim in docs/04,
summarized in docs/07 §6). The planner-movable frozen boundary (a thaw makes standing
pins, never free work); rush intake as a Demand the SOLVER places; the OUTCOME ->
WINDOW -> PIN constraint ladder with optional reasons. NAMED-QUEUED behind them: the
pin register, amend-submission (pilot-relevant), the boundary-drag gesture, the window
constraint.

**The ask path (R-AI5) — two tiers, sealed from each other, and a loop between
them.** Every question is parsed FIRST by a model against the closed intent
vocabulary (`src/mre/contracts/parse.py`), with the conversation history, the live
board selection, the last-answered subject and — since 4B.5 CU2 — the OPEN DELTA CARD
as context. The resolution ladder is **card > selection > last answer > history >
clarify**; while a priced card is showing, `open-card` READS IT BACK rather than
re-deriving it, so the two surfaces cannot state different numbers, and with no card
open the same words are never answered as a card question. **No deterministic
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
  0-bars, 4A.3 planner due-marker; both pass in isolation). A THIRD, non-screenshot
  member observed 4B.6c: `test_scenario.py::test_scenario_untouched_moves_bounded`
  failed once in a full-suite run and passes in isolation and as a whole file (32/32).
  Root cause is structural, not incidental: its fixture solves with
  `time_limit_seconds=30.0` and **no pinned workers or seed**
  (`tests/test_scenario.py:341-344`), i.e. CP-SAT default PARALLEL search under a
  WALL-CLOCK limit — which the hard rules already say is not reproducible. Under load
  it reaches a different tied-optimal placement and the `moves <= 3` bound breaks.
  The fix is deterministic mode in that fixture, not a wider bound. NOT fixed in 4B.6c
  (a measurement session changes no test but its own).
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
- 4B.6c findings: **§5a.16 and §5a.17 are DISCHARGED by 4B.7** (rolling records the
  COST objective; the pool's 5% is 5%). **STILL OPEN — §5a.15: the shipped 14-day
  window is BUDGET-STARVED at 200 orders** (313 free ops, UNKNOWN on the plain cost
  objective at a deterministic budget of 6.0 AND of 20.0; a 7-day window on the same
  plant proves OPTIMAL in under 5). The 14-day convention was measured on a plant 5x
  smaller. **Next session's subject.**
- 4B.7 findings (docs/07 §5a.19-22 — REPORTED, deliberately NOT fixed):
  **stage 2's deterministic budget is FIXED at 2.0, not the remainder, and the
  allocation is backwards** — at 40 orders stage 1 proves OPTIMAL in 0.101 of its 4.0
  while stage 2 exhausts its whole 2.0, so 3.9 units go unused (§5a.19; the fix is free
  but moves every rolling golden — pair it with §5a.15).
  **`EARLINESS_PREFERENCE` now names a mechanism that no longer exists** — the extractor
  still attributes a dearer-than-cheapest placement to it whenever `earliness_value > 0`,
  and nothing purchases anything any more. Not silently lying (it hedges, 4B.3a CU4b) but
  its stated MEANING is false. Correcting it is a **vocabulary-class change** reaching
  planner_language / explainer / renderers / four AI-voice tests / the exam bank (§5a.20).
  **The reported window status is stage 2's tiebreak-proof, not stage 1's cost-proof** —
  the fixture reads FEASIBLE over a provably OPTIMAL ledger (§5a.21; pre-existing, newly
  conspicuous, entangled with §5a.19).
  **The r5 bank's card expectations are invalidated again** (`ai_exam/runner.py:317-320,377`
  still hard-codes reopt −11,975.83; the card is now 0.00 / 32.20) and the exam WORLD
  changes too. NOT recalibrated — the bank has never been graded (§5a.22, §5a.7).
- 4B.6b findings (docs/07 §5a.8, .10, .12-14 — REPORTED, deliberately NOT fixed):
  **§5a.12 is DISCHARGED by 4B.7** — the coefficient left the objective, so the window
  solve and the sandbox baseline now minimize the SAME expression and `reopt_delta_abs`
  collapsed to **exactly 0.00** by construction; the card was NOT relabelled, and 4B.6b's
  own proof (forcing `earliness_value=0` drove it to 0.00) predicted the number. STILL
  OPEN: the prediction store's data-root sweep is
  scoped by NOTHING and matches on `op_id` alone — two plants sharing order numbering
  in one root produced **20 cross-plant realizations** (a CORRECTNESS debt now, plus
  the perf one); a COMPLETED order's predictions are never retired (orphaned,
  re-swept forever); the intake-path label reads ~100% `gravity_admission` at short
  windows and carries no signal; the pinned exam world's coarse zone runs at
  DEFAULTED rho 1.0 because its submission predates the generator's declaration
  (`--fresh` would fix it and is provably free — measured, not done).
- **The absent `ANTHROPIC_API_KEY` blocks MORE than the exam bank** (4B.7, §5a.7):
  FOUR committed SLOW tests fail on it — `test_api_endpoints.py`'s rolling-ask case and
  the three `test_edit_question_domain.py::TestEditDomainEndToEnd` cases — all landing
  on the honest could-not-interpret floor, which is CORRECT with no parser. Verified
  pre-existing against HEAD in a separate worktree, not assumed. So a full `--runslow`
  run is red for a reason unrelated to whatever is under test, which is how a real
  regression eventually gets waved through. Fix shape is `skipif` on the key with the
  reason stated, NOT weaker assertions; it is a suite-wide call, unmade.
- 4B.6a debts (docs/07 §5a.7, .9, .11): **`regression_founder_r5` is UNRUN AFTER
  FOUR SESSIONS** — blocked on the same key, and its 27
  expectations have never been graded (4B.7 invalidates them again, §5a.22); **§5a.9 is DISCHARGED by 4B.7** — the ~7.9%-dearer incumbent is gone, the board
  now sits at the proven optimum 16,481.95 / tardiness 0.00; `rolling_coarse_hot/` binds by
  DECLARED derate 0.10, a contrivance for screenshot coverage, not a discharge of the
  demo-density limit.
- 4B.5 debts: the two-solve BASELINE is not extended to FORCED-ALTERNATIVES pricing
  (same economics, separate audit); the causal vacuity tripwire counts a quantity
  as a DIGIT only, and a driver phrase alone clears it (the founder's own specimen is
  fixed at the assembler, not by the tripwire); CU4(b)'s viewport guard is a standing
  invariant the harness cannot make fail.
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
- **`--horizon-days` files horizon work as EXCLUSION on a PRODUCTION path**
  (`__main__.py` 251-300, reachable via `SolveRequest.horizon_days`): demand due
  beyond ref+N joins the same set that carries gate exclusions — a horizon category
  shelved as a data-defect category. NOT reachable from a rolling run. Full reasoning
  and fix shape in docs/07 §5a.
- **Per-component gravity ablation** (4B.2c): the counterfactual proves the BUNDLE;
  **no individual pull is proven, and setup-family affinity is the priced-air
  candidate.** Restated here because 4B.6 built a mechanism adjacent to gravity.
- 4B.6 debts (all in docs/07 §5a): the three deferred coarse refinements (family-presence
  setup, cross-bucket allocation for resumables, the WP makespan bound — each a
  TIGHTENING, so each must land against the CU4 guard); the coarse zone is UNEXERCISED
  at demo density (38 beyond-horizon demands but ~8% load, nothing binds — **the
  binding behaviour is now pinned at 200 orders by `tests/test_coarse_binding.py`,
  4B.6a CU3; the DEMO instance is still light**); coarse slip attribution is mostly
  `unattributed` by construction (the store now has data to attribute over);
  `coarse_horizon.py` carries its own narrow ortools surface (a stated deviation from
  the solver_builder/solve_runner quarantine, not an oversight).

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

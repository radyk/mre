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
- **A PINNED WORLD HAS A COMMITTED RECIPE, A COMMITTED PLACEMENT DIGEST AND AN
  OFF-TREE CAPSULE** (R-PW1, 2026-08-04). The recipe names everything the mint
  reads — *including state in the data root*, since an accepted calibration
  profile silently supplies a budget the caller did not declare. The digest is
  sha256 over sorted `(operation_ref, resource_id, first-chunk start)`; it is
  the ONLY way identity is ever proven, because `schedule_id` is
  `rolling-<uuid4[:12]>` and lives inside the document, so whole-file identity
  is impossible by construction. **A pinned world with no off-tree copy is a
  standing defect** — `python tools/worlds/pin_world.py --schedule <id>`.
  Lineage is a committed replay script driving the real accept path, never
  registry writes. A lost id is RETIRED-LOST in `docs/worlds/LEDGER.md` and
  never reused; it comes back only where its own document bytes survive.
- **NEVER RUN A CLEAN AGAINST THE MAIN CHECKOUT, AND NEVER JUNCTION `_data`
  INTO A WORKTREE** (R-PW1(6)). A worktree cleanup names the worktree path
  explicitly. A junction is a reparse point: a recursive delete inside the
  worktree empties the REAL data root and leaves its directory standing, which
  is what the evidence of 2026-08-04 points at. To give a worktree a data root,
  copy one or point `MRE_DATA_ROOT` at it.
- **SESSIONS APPEND TO THIS FILE ONLY POINTER-FORM LINES** (R-CM1, 2026-08-05).
  A ruling code, an id, a one-sentence discipline — that is the whole permitted
  shape. **Prose, rationale, measurements and changelog content are BORN in
  `docs/04` or `docs/07` and referenced from here**, never written here first
  and relocated later. This file is loaded into every session and is enforced at
  **150,000 characters** by `tests/test_claude_md_budget.py`. A session whose
  CLAUDE.md diff adds **more than ~15 lines** is presumptively doing it wrong and
  **says so in its close-out**. Full rules-of-writing text: docs/04, 2026-08-05.

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

Contract is **1.15** since 4B.28 (`rolling.boundary_moves`, R-F1 — the log of
PLANNER-MOVED frozen boundaries: old instant, new instant, direction, authority
and the operations whose commitment state changed. EMPTY on a board nobody has
moved the boundary on, which is every board a solve mints, and absent entirely on
a monolithic document). 1.14 was `solver.calibration` (R-CAL1 — PRESENT even when
the answer is "nobody has measured this plant"; absent only where the assembler
was given no store to consult, which is every module-level assembly and therefore
every golden). 1.13 was `solver.portfolio` (R-BK1, ABSENT at K=1); 1.11 the R-PD1
tardiness split, 1.12 the R-C3 pair.

**`SolveRequest.portfolio_k` DEFAULTS TO 3 SINCE 4B.29** — publication insurance,
not optimization (~$578 of ledger against a measured 2-in-5 chance of an EMPTY
BOARD at demo density). The per-member budget is UNCHANGED at 6.0: 10.0 units is
the demo board's knee, and it rises per plant through R-CAL1's ceremony. K=1 is
still requestable and is what the two pinned worlds are minted with.

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

**Roadmap position:** Phase 3 COMPLETE (qualified); Phase 4 preparation.
**Last closed: Session S-02 + S-03 — the certificate contract**, 2026-08-05
(docs/07 v3.00, §5a.223-226; docs/04 2026-08-05 **R-CT1 ruled and BUILT**;
contract unchanged **1.15** — docs/02 amended, no `CONTRACT_VERSION` bump owed;
prompts unchanged **v19 / v9**; narrative
`docs/closeouts/4x-certificate-contract.md`).

**THE SESSION LEDGER IS NOT IN THIS FILE.** What a session built, what it
measured, its test counts and its commit live in `docs/07` §5a (position and
named debts), `docs/04` (the ruling and the reasoning, append-only) and one
close-out per session under `docs/closeouts/`. The prose this section used to
carry — every session from 4B.11 to (e2), every ruling narrative, every
findings list — is archived **verbatim** in `docs/04` under **2026-08-05 —
CLAUDE.md STATUS SECTION CONSOLIDATION**. Nothing was deleted; it was moved.
**Read the docs/04 Amendment log tail before touching any area it covers.**

Recent sessions, newest first. `docs/closeouts/<file>.md` is the narrative:

| session | subject | ruling | close-out |
| --- | --- | --- | --- |
| S-02 + S-03 | the certificate contract | R-CT1 | `4x-certificate-contract.md` |
| 4A tg (d.3) | the product explains its own words | R-TE1 | `4a-teaching-d3-term-explanation.md` |
| 4A tg (d.2) | bank format, ladder, clarify-carry | R-EX2, R-LD6 | `4a-teaching-d2-format-ladder-carry.md` |
| 4A tg (e2) | the measurement errand | R-TG7 + W4 lead order | `4a-teaching-e2-measurement-errand.md` |
| 4A tg (e) | teaching may not contradict the floors | R-TG6, W6 | `4a-teaching-e-floor-truth.md` |
| 4A micro | shared-body census + certificate route | (none new) | `4a-micro-shared-body-census.md` |
| 4A tg (d.1) | carried answer state | R-MT1, R-LD5 | `4a-teaching-d1-carried-state.md` |
| 4A tg (d.0) | multi-turn recon | (measurement) | `4a-teaching-d0-multiturn-recon.md` |
| 4A tg (c2) | the teaching answer reads the board | R-TG5 | `4a-teaching-c2-reads-the-board.md` |
| 4A tg (c) | the exam learns to grade understanding | R-SW1, R-EX1 | `4a-teaching-c-exam-axis.md` |
| 4A tg (b) | the depth licence and teaching intent | R-TG2/3/4 | `4a-teaching-b-depth-license.md` |
| 4A tg (a) | the general-knowledge claim class | R-TG1 | `4a-teaching-a-claim-class.md` |
| 4A micro | the outage floor | R-OF1 | `4a-outage-floor.md` |
| 4A.y | the floor is family-scoped | R-FF1–R-FF4 | `4a-family-floor.md` |
| 4A.x | the listening docket | R-LD1–R-LD4 | `4a-listening-docket.md` |
| 4x | pinned-world reconstruction | R-PW1 | `4x-pinned-world-reconstruction.md` |
| 4B.35 | one clock, and the refused nudge | R-TZ1 | `4b35-one-clock.md` |
| 4B.34 | GUI polish | R-GP1 | `4b34-gui-polish.md` |
| 4B.33 | the honest driver's name | R-DP13 | `4b33-honest-driver-and-last-wall.md` |
| 4B.32 | verdict identity | R-DP12 | `4b32-verdict-identity.md` |
| 4B.31 | accept integrity | R-DP11 | `4b31-accept-integrity.md` |

Earlier sessions (4B.11–4B.30) are indexed the same way in docs/07 §5a and in
`docs/closeouts/`; the consolidation entry names each with its docs/07 version
and §5a range.

### Governed artifacts, current versions

Contract **1.15** · parse prompt **v19** · synthesis prompt **v9** ·
`DriverCode` **14 members** · finding codes **20** · RUBRIC axes through **C9**.
Changing any of these is a **vocabulary-class change**: reviewed, versioned,
committed with its spec update in the same commit.

### The worlds a session must know

**THE DEMO BOARD IS `rolling-c32a6140-b6b`** (2026-08-04, R-PW1) — the Khalil
board's world under a new id, minted from the SAME submission bytes under the
SAME accepted profile, reproducing every figure the record holds (ledger
**$1,667,467.80**, K=3 at 10.0 units, seeds 42-44, winner **seed 44**, spread
**28.06%**, 386 bars / 24 committed / 122 tray, ACCEPTED / C2, gap 89.6%).
Rebuild: `python tools/spikes/demo_board_4b22a/mint_demo_board.py --calibrated
--reuse`. **`--calibrated` DELETES `portfolio_k` from the request** rather than
setting it — R-CAL1 rule (2) reads `model_fields_set`, so a request naming ANY K
refuses the profile. **That rebuild needs the plant's accepted profile in
`_data/calibration/`**, and **the bare command is not hermetic** (with a profile
present it takes the profile's `det_total`, not its own, and lands elsewhere).

**THE EXAM WORLD IS `rolling-e9ccc879-a4b`** — proven identical to the lost
`rolling-c362baa4-1b0` by placement digest `07638cec…`; resolving, `proved`. Use
it when a demo wants a proved optimum.

**THE PREVIOUS DEMO BOARD IS `rolling-c9973708-865`** (4B.22a) — `demo_board`,
280 orders, seed 1, ref 2026-01-05, window 10 / frozen 1, 386 bars, tardiness
$2,040,146.67 ($535,800 floor). Rebuild:
`python tools/spikes/demo_board_4b22a/mint_demo_board.py` (its defaults ARE this
board). It is the one board still carrying a placement-bearing lineage child.

**`rolling-db5395dc-2ae` and `rolling-c362baa4-1b0` are RETIRED-LOST** and never
reused (`docs/worlds/LEDGER.md`). Both pinned rolling boards were deleted from
`_data` on 2026-08-04 with no backup; ids are `rolling-<uuid4[:12]>`, so only the
id could not come back.

**THE FENCED SPECIMEN WORLD IS `datasets/mobility_box`** (R-SW1) — a plant that
STOPS, the only shape that can produce the `boxed-in` and `earlier-open` mobility
verdicts (0 of 386 and 0 of 56 on the pinned boards, and IMPOSSIBLE on a plant
that keeps working: `later_at` scans a fortnight past the last placement). Nine
orders, three machines, `BOX-01` down for a rebuild from 2026-01-14. Monolithic,
deterministic, NOT registered in `_data`. Its bank is `sweep_mobility_v3`, its
guard `tests/test_mobility_box.py`. `held` is unreachable here by construction.

```
python -m mre --submission datasets/mobility_box --out _ai_exam_scratch/mobility_pinned     --snapshot-id snap-mobility --solver-workers 1 --solver-seed 0 --time-limit 600
python tools/spikes/teaching_graft_c/census_mobility.py        # one line per bar, one verdict each
python tools/spikes/teaching_graft_c/mint_edited_world.py      # + a real planner_edit accept
```

### Standing law in force

One line each. **The ruling code is the pointer** — every code below resolves to
its full text in `docs/04-design-history.md`; the docs/07 §5a entry carries the
measurements. Do not restate a ruling's reasoning here.

**The ask path**

- **R-AI5** — two tiers, sealed. Every question is parsed FIRST by a model
  against the closed intent vocabulary; a matched intent dispatches into the
  contracted route, an unmatched one goes to labeled open synthesis over the
  read-only tool surface, hardened claim-by-claim by `claim_verifier`
  (deterministic code, never a model). A matched intent can NEVER fall to
  synthesis; an unmatched one NEVER guesses a route. **No deterministic
  classifier survives anywhere, and none may come back.**
- **R-AI5(8)** — the answering model's beliefs about its own citations are INPUT
  to verification, never the label. The parse REPORTS; the dispatch DECIDES.
- **R-AI5(5)/(7)** — the promotion loop proposes; only review promotes. A
  promoted route runs shadowed; demotion is automatic on contradiction. Live:
  one promotion, `lateness-cause`, on probation.
- **R-TG1** — a GENERAL-KNOWLEDGE claim is unverifiable by design: verification
  SKIPPED, claim LABELLED, never passed unlabelled. `gk_disqualifiers` is ONE
  predicate read BOTH ways (a claim naming board content may not wear the label;
  a claim naming nothing on this board is DROPPED unless proposed).
- **R-TG2/R-TG3/R-TG4** — `teaching` is a second-tier INTENT, not a route; depth
  is granted by intent (LONG 8 claims, SHORT 4) at the DISPATCH seam; a deferred
  claim is not a cut claim; the boss question is 8 lines — account, lever, offer.
- **R-TG5** — a teaching answer must ATTEMPT a board read. The ATTEMPT is
  required, never the grounding; the no-case line CITES the read that found
  nothing. **The catalog is not the board.**
- **R-TG6** — a sentence asserting THIS PRODUCT's behavior may not wear the
  general-knowledge label; a mobility statement naming a board entity is checked
  against the floor's own verdict (asked, never re-derived); a general rule the
  floor's verdict vocabulary falsifies is refused.
- **R-TG7** — an empty teaching drop has a floor: the authored card replaces the
  capability card and says a draft existed and was REFUSED, never "nothing was
  found". It does not enter `ANSWER_MEMORY`.
- **R-TE1** — the product explains its OWN WORDS. `term-explanation` is a
  CONTRACTED route over a governed, CITED glossary; the model proposes, the
  deterministic seam confirms only a word we SAID on THIS board (`TermMemory`,
  R-MT1's key). Not a documentation browser — the trigger contract is the wall.
- **R-EX2** — banks grade ROUTES and RELATIONS; bodies belong to tests.
  `REBIND` is a sequence step; three relational forms index an earlier turn
  (`BODY_SAME_AS`/`BODY_DIFFERS_FROM`, `RECORDS_FROM` — non-empty required —
  and `RECORDS`); no prose assertion is expressible, and `EXPECT_KEYS` being
  closed is what enforces it.
- **R-LD6** — ONE resolver contract. All four rungs live and disclosed; the
  parse model's words are the LAST resort; **nothing resolves during a parse
  outage**; HISTORY remembers what was LOOKED AT and LAST-ANSWER what the turn
  was ABOUT. Clause (5): the carry takes the bundle's subject, else the subject
  the PARSE resolved — one definition (`interpreter.carry_subject`), three
  readers, additive by construction.
- **R-MT1** — carried answer state is schedule-scoped, cleared on rebind, honest
  about its own absence. `ANSWER_MEMORY` / `SYNTHESIS_MEMORY` / `_DELIVERED` key
  on `(session_id, schedule_id)`; `forget` is by SESSION.
- **R-LD1–R-LD5** — a typed operation number reaches the route; every resolution
  made is disclosed; a premise is verified at the GRAIN it was asserted at;
  disclosure follows the SUBJECT, not the resolver.
- **R-FF1–R-FF4** — the premise floor attaches to the QUESTION FAMILY, not one
  route; the parse may not invent a direction; each member renders in its own
  shape and the lead claims nothing about what follows.
- **R-OF1** — an outage may never wear the capability card. `system` is a
  register; three stages (parse / synthesis / unconfigured), no doors.
- **R-EX1** — RUBRIC C9 grades whether a planner could predict the next case,
  via a transfer pair with the conversation cleared between halves. **The LLM
  judge is written down and REFUSED.**
- **R-SW1** — a specimen world is a committed dataset whose specimens are
  MEASURED, never assumed.
- **R-CT1** — the gate's VERDICT is evidence (Event + Metrics + Artifact, both
  exits, provenance `derived`); the certificate answer states what the
  certificate CONTAINS and never asserts a signing step. ONE read definition,
  evidence-first / artifact-second; the fallback is permanent (append-only).
  Countersigning is PARKED with two prerequisites; R-CAL1 is untouched.

**Money, proof and the board**

- **R-PD1** — past-due is work, not a defect: admitted, scheduled, priced from
  its declared due date. **Exclusion is a data-defect category ONLY.** The gate's
  disposition binds downstream; tardiness decomposes and never fuses; every
  per-order route voices the disposition. Clause (5) (age vs lateness) is OPEN
  and deliberately unbuilt — the threshold is a declared IDS coefficient that
  does not exist.
- **R-BK1** — the published board is a portfolio, not a draw: K deterministic
  runs at consecutive seeds, best by LEDGER, ties by lowest seed. K and the
  budget are DECLARED coefficients; losing members' totals are PUBLISHED; a
  spread of one number is None, never 0.00. Separate PROCESSES, never
  CP-SAT `workers>1`.
- **R-CAL1** — calibration is MEASURED (sha256 over its own grid), OFFERED never
  auto-applied (**the caller always wins**; the WINDOW is never offered),
  DECLARED including when the answer is no, and the FACILITY is the scope. The
  coefficients are product-side, not IDS — no docs/06 doorway is owed.
- **R-T2** — every sandbox solve is deterministic and a wall-truncated solve
  REFUSES TO PRICE; "your move" is priced locally; the window's opportunity is
  its own labelled thing; accepting is two ceremonies; the incumbent is audited,
  not enshrined.
- **R-DP11** — the accept model is the plan of record's own scope, DERIVED inside
  the accept and never passed in.
- **R-DP12** — the ledger is the only comparable number. The scaled objective
  survives only as labelled solver telemetry, None never 0.0.
- **R-DP13** — `PLANNER_DIRECTIVE` is the driver for a `planner_edit` accept; the
  phrase names no direction and says "a planner", not "you".
- **R-DP9** — the no-op tolerance is a FIXED 5 working minutes, not a function of
  the zoom. A no-op says so.
- **R-GP1** — current means the most recent PLACEMENT-BEARING state of a lineage,
  compared by a derived placement digest scoped to descendants.
- **R-TZ1** — every planner-facing time renders in ONE declared clock, the
  facility's, with provenance in THREE states (declared / defaulted /
  unreadable). A rendering ruling: stored instants are untouched. **Named limit:
  the Python answer surfaces still render stored UTC verbatim.**
- **R-F1** — the frozen boundary is planner-movable; a thaw changes AUTHORITY,
  never position (uncovered assignments become standing pins); a freeze absorbs
  the pins it crosses; the ceremony is two calls (preview, then apply against the
  preview's digest). **Standing pins do not survive a slice roll** — splicing
  seam 3 is unbuilt.
- **R-F2 / R-F3** — ruled and RECORDED, not built (rush intake as a Demand the
  solver places; the OUTCOME → WINDOW → PIN ladder).
- **R-SC2 / R-SC3** — the coarse zone is a RELAXATION, always: only the negative
  is claimed, and the converse is never asserted in code, certificate or answer.
  Coarse never constrains fine, never renders as a bar; two ledgers, never fused;
  rho is a declared IDS coefficient defaulting to a no-op 1.0. Stage 1 minimizes
  COST ALONE; stage 2 IS the tiebreak and runs unconditionally.
- **R-C3 / R-B3 / R-B7/B8 / R-A2/A3 / R-A4 / R-Dwell** — the locked constraint
  rulings; the catalog with verdict/plane/status per item is `docs/05`.

**Discipline learned the expensive way (each has its specimen in docs/04)**

- **A pre-commit hook blocks a commit whose staged docs outrun the corpus
  index** (R1, (d.3)). Install: `git config core.hooksPath tools/hooks`;
  bypass is `git commit --no-verify` and nothing else.
- **An empty denominator is not a clean bill.** A check that fires 0 of 0 says
  the corpus could not exercise it (4A-(d.3) §5a.212).
- **A predicate is audited by the NEXT session, over the BUILDING session's own
  artifacts** — a session that has just built a check is the worst-placed
  observer of what it misses (4A-(e2) §9; 4A-(d.2) §5a.204 found a third missing
  construction this way).
- **A zero produced by an instrument that cannot see the value is not a zero**
  (4A-(d.2) §5a.209), and a count whose numerator's SET is empty proves nothing.
- **A defect class fixed at one seam is not fixed.** Census the class; the
  4B.14 chunk read, the 4B.20 duration class and the (e2) counterfactual sites
  were each found this way.
- **A guard that supplies its own arguments proves the assembler, not the path**
  (4B.21 §5a.78). A guard pointed at one file guards one file (4B.25 §5a.105).
- **A negative control that calls past the broken line proves nothing** (4B.28
  §5a.123). Prove every control RED against physically reverted code, and assert
  the restore is byte-identical by sha256.
- **A count names the disposition it counts** (4B.21): a predicate asserted over
  a count must apply to every member of the set counted; adjacent counts share a
  denominator or name their own.
- **Working time and elapsed span are different quantities** (4B.20) and a
  capacity figure names its denominator.
- **A category fusion is a name written once and never re-read as a claim** —
  five in six sessions (4B.21 §5a.72). Re-read names as claims.
- **A ruled species: the third state.** `unreadable` beside absent/present
  (4B.18), `undetermined` beside possible/impossible (4B.23), `UNDECIDABLE`
  beside holds/refutes (4A.x). **An unrecognised value fails SAFE and says
  nothing about the plant.**
- **A default that ASSERTS manufactures a claim out of a gap** (4B.23).
- **This repo mixes line endings PER FILE.** Byte anchors and multi-line
  replacements must work in bytes and check the file's own newline state first
  (4A-(a); (e2) §6 found the same at the docs layer).
- **Close-outs live at `docs/closeouts/<session-id>.md`** — one path per session,
  nothing overwrites.

### Carried qualifications (open, owned)

- Cloud deploy is verified **in-container**, not **in-cloud**: live `az deployment
  group create` from `deploy/azure/` + cloud smoke remain PARKED on the Azure
  trigger; the Bicep is still ARM-unvalidated (Session 2.4 carry).
- The `raw_data` path bypasses the M0 gate and has no WIP doorway — owned Phase-4
  debt; the live gate-free entry points are named in docs/04's 4B.2c R-SC1
  correction.
- Phase 3's **cold-stranger cold-drive** is MET-BY-PROXY only — a named Phase-4
  entry condition, not relaxed.
- Daryn's feel-token export is not committed; the cockpit runs on `DEFAULT_FEEL`.
- Two remediation-catalog quality notes carry no resolvable IDS §-cite
  (quarantined) — a design-thread `note_version` fix.
- Pool service must become **slice-aware** before serving sliced-mode schedules.
- `test_n3000` is contention-sensitive (green alone).
- The **parallel-load flake** class is standing debt, six members named in
  docs/07 §5a and the consolidation entry. Root cause where diagnosed is
  structural: a fixture solving under a WALL-CLOCK limit with no pinned workers
  or seed, which the hard rules already call irreproducible. 4B.33 fixed the
  golden-CSV member and answered the shape question for the rest.
- `OperationSpec.yield_factor` still carries false `observed` provenance (flagged
  2026-07-12, not fixed).
- A splittable op with `rate_overrides` uses the scalar default duration
  (rate-varying pins unexercised).
- Pilot-volume latency (174 workcenters) is UNMEASURED — every committed figure
  is demo density.
- **`--horizon-days` files horizon work as EXCLUSION on a PRODUCTION path**
  (`__main__.py`, reachable via `SolveRequest.horizon_days`) — a horizon category
  shelved as a data-defect category. NOT reachable from a rolling run; full
  reasoning and fix shape in docs/07 §5a.
- Product naming is under GTM review — "MRE" is the working repo name, not a
  brand.

### Small carry-forwards (do not lose)

**These are pointers. The text is in docs/07 §5a and the named close-out** — and
verbatim, as it stood here, in the docs/04 consolidation entry. Each was
REPORTED and deliberately NOT fixed.

| where | the two to take next | full list |
| --- | --- | --- |
| 4B.28 | standing pins do not survive a slice roll; the fold set is plant-wide, not per row | §5a.124 · `4B.28.md` §7 |
| 4B.29 | the profile has no expiry; two synthetic worlds share one plant key | §5a.111 · `4B.29.md` §8 |
| 4B.22a | `order-schedule` does not voice the past-due disposition; the concentration band cannot fire at any density | §5a.86-88 · `4B.22a.md` §7 |
| 4B.22 | the `why-on-machine` record answers a different question; "how do i fix that" after a board read lands on CLARIFY | §5a.83 |
| 4B.21 | two disposition questions are claimed by routes that do not answer them | §5a.75-78 |
| 4B.20 | `busy_minutes`' metric name is under-specified; 4B.17's A3 specimen no longer reaches tier two | §5a.68-70 |
| 4B.17 | the `repeat`/`deaf` boundary is keyed on string identity; the coaching invitation cannot decline to fire | §5a.54-62 |
| 4B.16 | the opener cannot state the certificate grade; concentration is unexercised live | §5a.49-50 |
| 4B.15 | the synthesis toolbox cannot read a declared field; the corpus excludes 15 undated `D-nn` decisions | §5a.39-45 |
| 4B.14 | a `chose` verdict on a splittable op is a LOWER BOUND; the runner-up can be a stale true fact | §5a.34-38 |
| 4B.12 | the tardiness split needs a THIRD category (`capacity_infeasible`); the a=2 cliff is bracketed, not pinned | §5a.31-32 |
| 4B.11 | R-PD1 clause (5) is open; there is no optimality ROUTE — nobody can ASK | §5a.28-30 |
| 4B.6b/c | §5a.15 the 14-day window is budget-starved at 200 orders; the prediction store's sweep is scoped by nothing | §5a.8-17 |
| 4B.5–4B.7 | the two-solve baseline is not extended to forced-alternatives pricing; `EARLINESS_PREFERENCE` names a mechanism that no longer exists (§5a.20) | §5a.19-21 |
| S-02/S-03 | the board opener still returns `grade: None` though its record now exists; `certificate.md` is written but not registered | §5a.226 · `4x-certificate-contract.md` |
| 4A (d.3) | a defined word asked about before it is said gets the second tier; the glossary is 10 entries against 27 emitted terms | §5a.222 · `4a-teaching-d3-term-explanation.md` |
| 4A (d.2) | `RECORDS_FROM` is a subset test, not equality; the cross-version bank names two schedule ids (the postposed deictic was discharged by (d.3) R2) | §5a.211 · `4a-teaching-d2-format-ladder-carry.md` |
| 4A (a)–(e2) | the widened GK predicate is still a pattern map; C9's transfer pair is still not bank-expressible (the fourth W4 site and the same-answer assertion were discharged by (d.2)) | §5a.162-202 |

Standing named debts not tied to one session: the sentinel /
repeated-identical-value detector (Rep 3's 40× `run_rate_seconds=60.0`); a
provenance spot-check guard (sampled `observed` values must appear in the cited
source); W1 scenarios unbuilt (`dwell_heavy`, `calendar_chaos`,
`multi_facility_balance`); the docs/05 structured-constraint surface is
prose-locked for the PROSE (the catalog ROWS were discharged 4B.15);
per-component gravity ablation proves the BUNDLE, no individual pull; and
per-order PRODUCTION-dollar attribution is a ledger change.

Everything else — what a session built, its test counts, its commit — lives in
docs/04 and docs/07. Do not restate it here.

---

**Maintenance rule for this section.** This file is loaded into every session and
is checked against a **150,000-character budget by
`tests/test_claude_md_budget.py`**, which fails the suite when it is exceeded. On
2026-07-25 it reached 191,692 characters, of which 94% was a session changelog
duplicating docs/04; on 2026-08-05 it reached 190,354 and was consolidated back
to orientation plus pointers (docs/04, same date).

This section records **position, qualifications, and carry-forwards only**. It
does not record what a session built, how many tests it added, or which commit
carried it. See **the write rule** in Hard rules: sessions append pointer-form
lines here, and prose is born in docs/04 or docs/07.

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

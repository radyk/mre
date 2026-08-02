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

**Roadmap position:** Phase 3 COMPLETE (qualified); Phase 4 preparation. Last closed:
**Session 4B.33 — the honest driver's name + the last wall limit**, 2026-08-03
(docs/07 v2.80, §5a.133-135; docs/04 2026-08-03 **R-DP13 ruled and BUILT** and the
golden-CSV flake FIXED; contract unchanged **1.15** and the bump question answered
either way; **`DriverCode` 13 -> 14**; narrative in
`docs/closeouts/4b33-honest-driver-and-last-wall.md`). Before it:
**Session 4B.32 — verdict identity + honest driver**, 2026-08-03 (docs/07 v2.79,
§5a.129-132; docs/04 2026-08-03 **R-DP12 ruled and BUILT**, **R-DP10 DISCHARGED
BY IDENTITY**, R-T2's disclosure line STRUCTURALLY MOOT on this path; contract
unchanged **1.15**; narrative in `docs/closeouts/4b32-verdict-identity.md`).
Before it:
**Session 4B.31 — accept integrity: the incumbent must re-validate**, 2026-08-02
(docs/07 v2.78, §5a.125-128; docs/04 2026-08-02 **R-DP11 ruled and BUILT**,
**R-DP10 ruled and NOT built**; contract unchanged **1.15**; narrative in
`docs/closeouts/4b31-accept-integrity.md`). Before it:
**Session 4B.28 — the board serves a person using it**, 2026-08-02 (docs/07 v2.77,
§5a.119-124; docs/04 2026-08-02 R-F1's mechanics verbatim; contract **1.15**;
parse prompt **v16**; narrative in `docs/closeouts/4B.28.md`). Before it:
**Session 4B.27 — the conversational batch**, 2026-08-01 (docs/07 v2.75,
§5a.112-113; docs/04 2026-08-01; parse prompt **v14**; narrative in
`docs/closeouts/4B.27.md`). Before it:
**Session 4B.29 — calibration is the product**, 2026-08-01 (docs/07 v2.74,
§5a.108-111; docs/04 2026-08-01 R-CAL1 verbatim; narrative in
`docs/closeouts/4B.29.md`). Before it:
**Errand 4B.26 — what is the main-solve K actually for?**, 2026-08-01 (docs/07
v2.73, §5a.107; narrative in `docs/closeouts/4B.26.md`). Before it:
**Session 4B.25 — the published board is a portfolio, not a draw**, 2026-08-01
(docs/07 v2.72, §5a.101-106; docs/04 2026-08-01 R-BK1 verbatim; narrative in
`docs/closeouts/4B.25.md`). Before it:
**Session 4B.24 — the incumbent earns its flag**, 2026-07-31 (docs/07 v2.71,
§5a.96-100; docs/04 2026-07-31 R-T2 AMENDMENT verbatim; narrative in
`docs/closeouts/4B.24.md`). Before it:
**Session 4B.23 — beat two is never called**, 2026-07-31 (docs/07 v2.70,
§5a.89-95; docs/04 2026-07-31; narrative in `docs/closeouts/4B.23.md`). Before it:
**Errand 4B.22a — a demo board worth dragging**, 2026-07-31 (docs/07 v2.69,
§5a.84-88; docs/04 2026-07-31; narrative in `docs/closeouts/4B.22a.md`). Before
it: **Session 4B.22 — the second question**, 2026-07-31 (docs/07 v2.68, §5a.79-83;
docs/04 ruling; narrative in `docs/closeouts/4B.22.md`). Before that:
4B.21 (v2.67, §5a.71-78), 4B.20 (v2.66, §5a.67-70),
4B.19 (v2.65, §5a.64-66), 4B.18 (v2.64, §5a.63), 4B.17 (v2.63, §5a.54-62),
4B.16 (v2.61, §5a.49-50), 4B.15 (v2.59, §5a.39-45), 4B.14 (v2.58, §5a.34-38),
4B.13 (v2.57), 4B.12 (v2.56, a MEASUREMENT session), 4B.11 (v2.55, **R-PD1
verbatim**).

**THE DEMO BOARD IS `rolling-db5395dc-2ae` — THE KHALIL BOARD (4B.28, §5a.120).**
The SAME WORLD as `rolling-c9973708-865` under its plant's **ACCEPTED**
calibration profile: K=3 at 10.0 deterministic units, seeds 42-44 ->
**$2,135,369.63 / $1,801,222.70 / $1,667,467.80**, winner **seed 44**, spread
**$467,901.83 = 28.06%** and the certificate says *"far from settled"*. Ledger
**$1,667,467.80** (the profile predicted it to the cent), 386 bars (24 committed
/ 362 active), 122 in the tray, coarse zone present, ACCEPTED / C2, gap 89.6%,
contract 1.15, 989s. Rebuild:
`python tools/spikes/demo_board_4b22a/mint_demo_board.py --calibrated --reuse`
— `--calibrated` **DELETES** `portfolio_k` from the request rather than setting
it, because R-CAL1 rule (2) reads `model_fields_set` and a request naming ANY K
(including the profile's own) refuses the profile. **THE OLD BOARD IS UNTOUCHED**
and still resolvable: this thread's measurements are calibrated against it, and
everything below about it still holds.

**THE PREVIOUS DEMO BOARD IS `rolling-c9973708-865` (4B.22a, §5a.84).** `demo_board`
(`generate_erp_dataset.py`), 280 orders, seed 1, ref 2026-01-05, **window 10 /
frozen 1**, deterministic, coarse — minted through the API's own two steps.
386 bars (41 committed / 345 active), 96 late, **47 past-due orders SCHEDULED**,
tardiness $2,040,146.67 split **$535,800 floor / $1,504,346.67 controllable**, a
coarse zone binding **8 of 48 cells at 95-99%** of derated capacity, a 122-order
tray, ACCEPTED / C2 / contract 1.12. Reproduces IDENTICALLY across PYTHONHASHSEED
0/1/2. Rebuild with ONE command, whose defaults ARE this board:
`python tools/spikes/demo_board_4b22a/mint_demo_board.py`.
**`rolling-c362baa4-1b0` IS UNTOUCHED** —
still the pinned exam world, still resolving, still `proved`; use it when a
demo wants a proved optimum. **THE PRICE IS THE PROOF: FEASIBLE at gap 92.4%**,
and **that is DENSITY, not R-PD1** — the controlled pair (same board,
`pd_share=0.0`) is still FEASIBLE at 84.5% (§5a.85). **The shipped 14-day window
does not survive this density**: UNKNOWN — an EMPTY board — at 140 and 170 orders,
INFEASIBLE at 360; and solvability is **NOT MONOTONE** (10-day: UNKNOWN at 200,
FEASIBLE with 386 bars at 280). A drag now costs **$2,596.67** (split $0.00
re-optimization / $2,596.67 your move), and **$2,301.67 of it is paid by the
order it displaced**; the same gesture on the old board costs $354.58 of which
the displaced order pays **$0.00** — on an empty board displacement is free, so
the card can only ever charge a planner for their own order. **`pilot_scale` is
BYTE-IDENTICAL** and proven so at 40 and 400 orders — the three `demo_board`
knobs draw nothing from `rng` at their defaults. NO `src/mre/` CHANGE.

**"YOUR MOVE" IS PRICED LOCALLY, AND THE FOUNDER'S NUDGE COSTS $0.00 (4B.24,
R-T2 AMENDMENT, §5a.96 — §5a.95(b) DISCHARGED).** Five clauses, verbatim in
docs/04. **(1) EVERY SANDBOX SOLVE IS DETERMINISTIC** — deterministic budget,
pinned seed, workers=1, **wall as a SAFETY CEILING only**, and a wall-truncated
solve REFUSES TO PRICE rather than pricing from a lottery draw. **(2) "YOUR MOVE"
IS PRICED LOCALLY** — everything else held, the bar moved, the ledger recomputed
and validated. **(3) THE WINDOW'S OPPORTUNITY IS ITS OWN LABELLED THING.**
**(4) ACCEPTING IS TWO CEREMONIES.** **(5) THE INCUMBENT IS AUDITED, NOT
ENSHRINED.** The founder nudged ORD-000057 four hours inside an overtime window
it already occupied, on a machine carrying nothing else those hours; the card
charged **-$50,784.33**, all to *"your move"*, relocating four unrelated orders by
weeks. Beat two re-solved the WHOLE WINDOW wall-clock-bounded with no
deterministic time over an incumbent at a 92.4% gap — **the card reported the
difference between two lottery draws and labelled it the planner's**.
`src/mre/modules/local_price.py` is compressor C's validate-and-price (4B.6c)
pointed at a pin, re-validated by pinning all 386 placements into a fresh model
and asking CP-SAT. Live: **$0.00, empty affected list, 0.384s** against 64s, and
**five repetitions give ONE DISTINCT CARD** on the full tuple. A refusal names its
docs/05 family and carries **`holds_others` — SHUT is not OCCUPIED**, the ruled
species a FIFTH time (`CostProof` 4B.18, `partitions()` 4B.21,
`FeasibilityGhost.verdict` 4B.23). Clause (2) reached ACCEPT and had to:
`hold_all_placements` pins every incumbent placement, so **the promise on the card
and the schedule that lands are the same object**. `POST /audit` (the deliberate
search) found **$239,824.80 cheaper, 226 ops moving**, offered with its own
affected list and its own accept (`POST /audit/accept`) — **one click can never
commit both**. The card's `attribution: "local"` draws ONE row and never a
`window re-optimization $0.00` line: the component is **ABSENT by construction,
not measured as zero**.

**BEAT ONE'S BUDGET WAS MARGINAL IN THE WRONG CURRENCY, AND THERE IS NO PLATEAU
(4B.24, §5a.97-98).** Beat one's verdict costs **0.0426 deterministic units — the
same to four decimals at all five seeds — and 2.5-3.9 SECONDS**, because the
deterministic meter barely counts PRESOLVE; so raising the deterministic budget
alone would have changed nothing. `FEASIBILITY_BUDGET_S` **2.0 -> 12.0**,
`FEASIBILITY_DET_TIME_S` **1.0 -> 2.0**, and `wall_ceiling_for()` gives a
deterministic re-solve `max(caller ceiling, det x 120 s/unit)` so **the clock can
no longer decide** (`applied_time_limit_s` reports the limit ACTUALLY applied).
One unit of unpinned search, five seeds: **three find exactly the incumbent, seed
44 finds 16.3% cheaper, seed 45 13.2%**; seed 42 at THREE units finds 12.4% — the
SEED decides and so does the BUDGET, because CP-SAT schedules its portfolio around
the budget it is handed. **"Units to plateau" was NOT measured and could not be**:
improvements run to the budget edge at every budget tested, and
`CpSolverSolutionCallback.DeterministicTime()` returns a CONSTANT for every
solution of a run. Exchange rate **33.9-77.0 s/deterministic unit**. Two runs of
seed 42: identical det time (1.0328) and trace, wall times 2.4s apart. **NOT
FIXED, named (§5a.100):** beat one is now the whole cost of a gesture (4.8-5.7s of
~8.2s, mostly presolve); the audit's single seed finds nothing at 1 unit; a
CHUNKED op cannot be locally priced and declines BY NAME; **a collision drop is
now a REFUSAL by ruling**, so 4B.22a's displacement card is unreachable from a
gesture; and Item 6 was driven through the API, not a pointer (no browser
extension). **DISCHARGED BY 4B.25:** `POST /audit/accept`'s success branch (it was
BROKEN — see below) and `tests/test_rolling_two_beat.py`'s 12 errors.

**R-BK1 — THE PUBLISHED BOARD IS A PORTFOLIO, NOT A DRAW (4B.25, §5a.101,
docs/04 verbatim).** Five clauses. **(1)** A solve may be a DECLARED PORTFOLIO:
K deterministic runs at CONSECUTIVE seeds `seed0..seed0+K-1`, best by LEDGER,
ties by lowest seed — a pure function of a fixed set, so **the portfolio is
deterministic**; a member the WALL stopped is not reproducible and is NOT
SELECTABLE (4B.24 clause (1), same words). **(2)** K and the per-member budget
are DECLARED coefficients with provenance, and **K=1 IS EXACTLY TODAY'S
BEHAVIOUR** — one call, no extra solve, no scratch dir, **NO BLOCK IN THE
DOCUMENT** (absent by construction, 4B.24's discipline), proven by SCHEDULE
DIGEST. **(3)** by the LEDGER, never the raw objective (4B.7). **(4)** the losing
members' totals are PUBLISHED — the cross-seed spread is 4B.12's honest companion
to the gap and is free here; three authored registers, and **a spread of one
number is not a spread** (None, never 0.00). **(5)** separate PROCESSES, never
CP-SAT `workers>1`. Live: `src/mre/modules/portfolio.py` (the primitive),
`rolling_horizon.solve_rolling_portfolio` (K+1 searches at K>1, the winner's
re-solve CHECKED against the member that won — `PortfolioDrift`), and
`sandbox.audit_incumbent`. **`AUDIT_K` = 3. `SolveRequest.portfolio_k` WAS 1
and is 3 since 4B.29** (see the contract note above); the audit's K is NOT
calibrated and is still a constant.

**THE AUDIT PORTFOLIO FOUND 2.3x MORE MONEY THAN THE SINGLE SEED (4B.25,
§5a.102).** Dense demo board, `POST /audit` at K=5 x 3.0 units, seeds 42-46:
**$1,887,657.78 / $2,030,588.40 / $1,581,932.98 / $1,784,070.77 /
$1,859,103.07**. 4B.24's $239,824.80 was **seed 42, the FOURTH BEST of five**;
seed 44 finds **$545,549.60**. **SPREAD $448,655.42 = 28.36%, and the offer
sentence says so** — *"far from settled"* — which turns a figure a planner would
read as the answer into a floor. Seed 42 reproduces 4B.24's number **TO THE
CENT** across sessions. **K=3 finds the same winner** for 60% of the wall. Two
K=5 audits → **ONE DISTINCT OFFER** on the full tuple. **`POST /audit/accept`'s
SUCCESS BRANCH WAS BROKEN** (`AttributeError: DriverCode has no attribute
'COST_MINIMIZATION'` — a name never in the vocabulary, behind the button 4B.24
reported as never-executed); corrected to `COST_TRADEOFF`, and a real child
minted: 386 bars, 333 ops moved, **ledger equal to the offer TO THE CENT**
(§5a.104). The offer now carries its WINNING SEED and the accept carries
`expect_delta_abs`, so a child that re-solved differently is REFUSED.

**THE MAIN-SOLVE PORTFOLIO IS WORTH $578, NOT $545,549 (4B.25, §5a.103).** Same
board, seeds and budget, COLD instead of warm-started: **42 $2,127,482.58
(exactly the incumbent) / 43 $2,164,599.48 / 44 UNKNOWN / 45 UNKNOWN / 46
$2,126,904.42**. Winner seed 46, **$578.16 (0.027%)**, spread 1.77%. **TWO OF
FIVE SEEDS RETURN AN EMPTY BOARD** — 4B.22a's non-monotone solvability is
SEED-dependent as well as size-dependent, and clause (4) is what stops a
portfolio that shrank to three from reporting a tighter spread than its evidence.
**WALLS: sequential 515.8s vs five processes 298.8s — 1.73x, not 5x**, because
each member runs **~1.8x SLOWER with four siblings** on this laptop. **Ledgers
AND deterministic times are IDENTICAL TO TEN DECIMAL PLACES across execution
modes** while walls differ by 80s: clauses (1) and (5) in one table. **NOT FIXED,
named (§5a.106):** the cold-vs-warm gap is unexplained; K=1 at seed 44 would
publish an EMPTY board here; *"search deeper"* now costs **~7 min at K=3** and
nothing in the cockpit says it is three searches long; the parallel speedup is a
LAPTOP number; a parallel member re-runs the WHOLE SPINE; the audit child's
lineage is in the REGISTRY, not its document; and **the portfolio is not
reachable from the ask path** (§5a.29's shape, second member).

**R-CAL1 — CALIBRATION IS MEASURED, OFFERED, AND DECLARED (4B.29, §5a.108,
docs/04 verbatim).** 4B.26 recommended shipping K=3 AND 10.0 units as one
change; this session shipped the K and REFUSED the budget, because **10.0 is ONE
BOARD's calibration, not a law** — its own control board wants a different
WINDOW, not a bigger budget. Four rules. **(1) MEASURED, NEVER AUTHORED** — the
profile carries a **sha256 of its own grid**, recomputed on load; an edited grid
is `unreadable` (never `absent`), refused at read AND at accept. The digest
covers the MEASUREMENT and not the bookkeeping, which is what makes RE-USE legal:
30 of 55 cells are 4B.26's own rows, imported with `source` naming them. **(2)
OFFERED, NEVER AUTO-APPLIED** — `--accept` takes a NAME and refuses a blank one;
**THE CALLER ALWAYS WINS**, and **THE WINDOW IS NEVER OFFERED** (it is what a
planner asked to SEE, not a coefficient of how hard we look) though
`window_calibrated` rides beside `window_solved`. **(3) DECLARED — INCLUDING
WHEN THE ANSWER IS NO**: `solver.calibration` is PRESENT on an uncalibrated
plant and says so, the OPPOSITE discipline from `solver.portfolio`'s absent-at-
K=1, deliberately. **(4) THE FACILITY IS THE SCOPE** — a two-facility submission
is REFUSED calibration by name. **THE COEFFICIENTS ARE PRODUCT-SIDE, NOT IDS,
AND THAT IS ON THE RECORD:** K, the budget and the window are facts about OUR
SEARCH; nothing reaches the model, objective or ledger, so **no docs/06 doorway
is owed**. **THE KNEE IS A STATED RULE:** *the smallest measured budget at which
(i) every seeded search published a board and (ii) its winner is within a
declared tolerance (1%) of the best winner at any LARGER measured budget* —
(ii) is vacuously true at the largest measured budget, the rule's own limit
stated. Where no budget satisfies (i) that is a FINDING and the profile
recommends the deepest window that IS reachable. Recommended K comes off the
same grid (consecutive seeds → the K-portfolio IS the first K) and is **floored
at 2**, with the floor named separately so an argument never wears a
measurement's clothes. **DRIFT** (`CALIBRATION_DRIFT`, finding code 20, ADDED
never repurposed): fewer than K publishable under an ACCEPTED AND APPLIED
profile → INFO / `proceeded_flagged`, on the certificate, **and the board still
publishes**. It fires only under an accepted profile — a plant on defaults has
no promise to drift from. Live: `python -m mre.calibrate`, resumable,
append-only, cost stated BEFORE it spends.

**THE 8.0 BISECTION SAYS NO, AND THE MONEY AND THE RELIABILITY ARRIVE AT
DIFFERENT BUDGETS (4B.29, §5a.109 — §5a.107's residual arm).** Demo board, five
new cells: **seeds 44 and 45 are STILL EMPTY at 8.0 units**, so the knee stays
at **10.0** and the hazard clears between **8 and 10**, not 6 and 10. But seed
43 finds **$1,801,222.70 at 8.0** — 16.8% cheaper than any 6.0 member and
exactly its 10.0 and 15.0 figure. So a K=3 portfolio at 8.0 would publish
$325k cheaper while two of five siblings still place NOTHING; **condition (i) is
what stops the profile recommending it**, and this is the grid where (i) bites
(on 4B.26's own table condition (ii) ruled the starved budgets out alone).
**ON A PROVABLE BOARD THE FLIP CHANGES NOTHING BUT THE WALL** — 20 orders, three
members, all OPTIMAL at $885.58, winner seed 42 by tie-break, and the
certificate gains *"all 3 seeded searches landed on the same total"* free.

**THE COLD PORTFOLIO WAS BUDGET-STARVED, NOT GEOMETRICALLY WEAK (4B.26,
§5a.107 — §5a.106(a)(b) MEASURED).** A (budget x seed) sweep, demo board, COLD,
seeds 42-46. Value vs the incumbent at K=5: **$578.16 at 3.0 units / $1,298.60
at 6.0 / $460,014.78 (21.6%) at 10.0 / the SAME $460,014.78 at 15.0** — it
switches on **between 6.0 and 10.0** (354x) and the WINNER PLATEAUS AT 10. Cold
at 10.0 recovers **84% of the warm audit's $545,549.60**. **THE SPREAD WIDENS
BEFORE IT NARROWS** (1.77/1.81/**28.06**/25.20%) — the tight low-budget spread
was three STARVED searches failing in the same place, never agreement. **THE
EMPTY-BOARD HAZARD IS A BUDGET THRESHOLD, NOT A BAD SEED:** 44/45 empty at 3.0
and 6.0, **nobody fails at >=10.0, and seed 44 WINS there**. At the shipped
default (K=1, 6.0, seed 42) the board DOES publish at the incumbent's ledger to
the cent — but **2 of 5 seeds would publish an EMPTY BOARD**, and which two is a
property of (board x budget), so no fixed seed0 is safe in advance. **K IS NOT
UNIVERSAL INSURANCE:** the 170-order world at w14 is **0 of 5**; the SAME world
at w10 is **5 of 5, spread 42.10%** — **the window, not the density, kills it**
(§5a.15 from the seed axis). **RAISING THE BUDGET AT K=1 MAKES THE BOARD WORSE**
(seed 42 **+$7,887.05** at 10.0 vs 6.0) while the same spend at K=3 earns
$460,014.78 — the budget lever is unsafe alone and safe with K. **RECOMMENDED,
NOT FLIPPED: K=3 + 10.0 units as ONE change** (K=3 takes the ENTIRE K=5 gain
wherever material; K=5's edge is <=$1,298.60 = 0.06% and only at starved
budgets; 45% of K=5's wall, ~12.9 min sequential, **3.9x the shipped solve**).
**Daryn decides.** NOT FIXED: more budget is **NOT MONOTONE** in the ledger for
a fixed seed; the 6.0-10.0 plateau was not bisected; mid170-w14 was not pushed
past 6.0; every publishable cell is FEASIBLE, so **"cheaper" is never "closer to
optimal"**.

**THE 4B.8 RENAME DRIFT WAS SIX FILES AND THE GUARD WAS POINTED AT ONE (4B.25,
§5a.105).** `test_rolling_two_beat.py`'s 12 errors were the visible member; five
more `det_time`/`det_total` call sites had been broken since 4B.8, **every one
inside a `--runslow`-gated fixture, so the default suite collected them, skipped
them and reported green** — and one was `tools/build_rolling_fixture.py` carrying
**the exact defect the errand session's signature guard was written for**. The
guard now sweeps EVERY file in `tests/` and `tools/`. A sixth thing was stale: an
assertion pinning the PRE-4B.11 hedge for a placed order, correct-in-life for
three sessions, never run. **A GUARD POINTED AT ONE FILE GUARDS ONE FILE.**

**BEAT TWO WAS NEVER CALLED, AND THE CHAIN WAS NEVER BROKEN — IT WAS
CONDITIONAL (4B.23, §5a.89 — §5a.88(a) DISCHARGED).** One drag on the demo board
made ONE request. `controller.js` branched on `ghost.feasible`, which
`feasibility_ghost` computes as `status in ("OPTIMAL","FEASIBLE")` — so **UNKNOWN
(our budget ran out) and INFEASIBLE (the plant has no room) were one branch
wearing one sentence**, and `returnHome`'s `keepCard` default then HID the card.
Matched gesture: **dense 386 bars → UNKNOWN → 1 request; pinned 56 bars →
OPTIMAL → 2 requests and a $354.58 card.** Identical code; the fixture cans a
FEASIBLE beat one, so every two-beat test was green over a branch nothing
exercised. **THIRD INSTANCE OF A RULED SPECIES** (`CostProof`'s fourth state
4B.18, `partitions()` tri-state 4B.21): `FeasibilityGhost.verdict` is
`possible | impossible | undetermined`, an unrecognised status **fails SAFE to
undetermined**, `feasible` alone is never sufficient to author a sentence about
the plant, and **both `possible` and `undetermined` proceed to pricing** — only a
PROVEN refusal stops the chain. **A REFUSAL AND A FAILURE READ DIFFERENTLY**
(§5a.91), in different registers, four exits and none silent, the failure naming
WHICH BEAT and offering a retry, **no raw transport string on a planner
surface**. Two caught on the way: the pending card said *"this is possible
here"* BEFORE the request was sent, and a Tier-0 refusal lost its reason at the
release. **BEAT ONE's 4.6s IS THE MODEL BUILD** — `SolverBuilder.build` 6.564s /
67% dense vs 0.308s / 13% pinned, so its budget governs 22% of its own latency
(§5a.92; a model cache is named and priced, not built). **15s WAS TOO SMALL A
BEAT-TWO BUDGET AT DEMO DENSITY** — 15s `no_verdict`, 25/40/60s FEASIBLE at
$2,596.67; token now **30.0s**, and **a budget is a CEILING not a spend** (the
pinned world still proves in 1.3s; the cost is ~64s cold / ~34s warm on 386 bars,
§5a.93). **A POLL CANNOT DISCARD A LIVE PROPOSAL** — SUPPRESS, because the
proposal is in no document to reconcile against; narrower than
`hasUncommittedState`, so 4.4 CU2's banner and 4B.5's fixes stand (§5a.94).
Guard: 11 tests x 2 themes, premise test, **three negative controls proven red
against physically reverted code**. **NOT FIXED, named (§5a.95):** R-DP9's no-op
tolerance **scales with the zoom** (~240 min at the default 30-day view swallows
a 236-min move — no card, no request, indistinguishable to a planner from the
defect just fixed); beat two is a **wall-clock solve with no deterministic
budget**; `cockpit.spec.mjs:111` ("deictic") is **red at HEAD**, not from this
session.

**A DRILL-DOWN RESOLVES TO THE ANSWER IT FOLLOWS (4B.22, §5a.79 — §5a.77
DISCHARGED).** The 4B.5 ladder (card > selection > last-subject > history)
resolves WHO a question is about and **has no rung for WHAT WE SAID** — a
citation set is not a subject — so *"show me the evidence for that"*, one turn
after an answer citing a record and lighting three bars, bound the order
correctly and grounded nothing. Three authored cases, **none silent**: records
open (naming the question they are behind, and saying a contracted route has no
per-sentence claims); **an answer that cited nothing SAYS SO** — a different
fact from having nothing open, and `PROVE_IT_NO_TARGET` stated the wrong one for
both, telling a planner the citations were "on it" about a CLARIFY;
synthesis provenance unchanged (4B.5 CU5). `AnswerMemory` is written at
**`run_ask`**, the ONE seam every live answer passes — NOT at `dispatch`'s
matched-route branch, which a rolling route, a tray answer and a CLARIFY never
reach. `forget_deliveries` clears it and is now the ONE clear for server-side
conversation state (4B.16a's fifth-channel defect refused in advance). The
4A.5a fall-through stands: a prove-it gesture that ALSO names a real intent is
answered as that intent.

**THREE ANSWERS EXISTED AND NO ROUTE REACHED THEM (4B.22, §5a.80-82 — §5a.69
DISCHARGED).** 4B.15's attribute-lookup shape, three times. **NO NEW INTENT WAS
TAKEN**: the parse already reaches each route, so the cheaper honest option was
to let it carry the figure. **B1** `machine-schedule` states the load from
`evidence_tools.machine_load`, **the one definition it now shares with the
toolbox** — naming its QUANTITY (working time, never the span) and its
DENOMINATOR (open minutes over the same first-to-last interval: 5,981 against
6,655, 89.9%; the whole calendar is 22,320) — **and REFUSING the judgment**,
because "overloaded" is a threshold no plant declares and `SATURATED = 0.85`
measures CONCENTRATION, a different claim. A multi-machine listing states no
load at all. **B2** `advice` leads with the opener's top-ranked item and names
which of the two questions it answered; the intervention refusal is right and is
kept verbatim. `Intent.ADVICE` joins the document allow-list. **B3** `inventory`
answers whether an order can be PARTLY placed and **distinguishes measured from
invariant** — nothing enforces all-or-nothing, because
`rolling_horizon._derive_maps` keeps ONE work package per demand. Guard: 35
tests, **every Class A assertion over TWO CONSECUTIVE `run_ask` CALLS**, five
premise tests, **four negative controls each proven red on its own half** — and
the premise fixture's own first version was wrong in exactly the way the session
exists to catch. **NOT FIXED, named (§5a.83):** the `why-on-machine` lead is
about ELIGIBILITY and its record's driver is about OCCUPANCY, so the drill-down
shows a planner two propositions about one record (the sixth driver-phrase site
now reads **"recorded driver:"** — 4B.21's remedy, a one-line scope widening
taken because the drill-down put it on the demo path); *"how do i fix that"*
after a whole-board read lands on CLARIFY `no-subject`, honest, because the
BOARD is the subject and the ladder has no rung for it.

**A COUNT NAMES THE DISPOSITION IT COUNTS (4B.21, §5a.71 — 4B.17's A5
DISCHARGED).** "Orders" alone is not a disposition: known, scheduled, committed,
active-window, beyond-horizon and excluded are different sets and a surface
reporting one says WHICH. **A PREDICATE ASSERTED OVER A COUNT MUST APPLY TO
EVERY MEMBER OF THE SET COUNTED** — where it does not the set is SPLIT and each
part reported with the predicate that applies. Two clauses added: adjacent
counts share a denominator or name their own; where the dispositions do not
partition the known set the surface **says so and states no total** (4B.18's
`unreadable` again). `inventory` said *"40 order(s) are in the plan, scheduled
across 56 operation(s) … Every order finishes on time"* on a board of **40
known / 26 scheduled / 14 beyond-horizon / 56 placed of 88 declared** — three
denominators in three lines — while the opener said 26, the tray said 14, and
the toolbox's `lateness_set` note stated the split correctly. **THE SURFACE THAT
WAS RIGHT IS THE ONE NOBODY READS.** Census: 542 raw sites → 253 candidates → 8
defects, plus a separate UNIVERSAL sweep (38 planner-facing, 15 with a
placement-presupposing predicate, 3 defects) because the sharpest specimen
carries no number. Fix: ONE definition, `order_disposition.census`, every field
naming its set, read by seven surfaces. Guard: agreement + prose, 10 tests,
premise test, **two negative controls red on opposite halves**, limit in the
docstring. **§5a.72: THIS IS THE FIFTH CATEGORY FUSION IN SIX SESSIONS** (delta
card 4B.5, `lateness_set` 4B.13, `CostProof` 4B.18, working-time 4B.20,
`inventory` 4B.21) and docs/04 names the mechanism: **a name written once, by
whoever needed a number, and never re-read as a claim.** **§5a.78: THE GUARD WAS
GREEN WHILE THE LIVE PATH WAS BROKEN** — every test supplies its own document;
the ask path injects one from an intent ALLOW-LIST `inventory` was not on. A
guard that supplies its own arguments proves the assembler, not the path.
**A5 (§5a.73):** the chain was assembled for the ORDER and the lead computed for
the OPERATION — *"no alternative to weigh"* over a chain entry for a DIFFERENT
op pricing two. Scoping ONE list (`ordered_records`) fixes chain, cited refs,
lit bars and the cockpit footer together; `why-on-machine` now takes an
`op_seq`. The driver-phrase-as-whole-clause census found seven sites and the two
RENDERER ones now read **"Recorded driver:"** — *"Why:"* claimed to be the
reason. **§5a.74: A CONTRACT TERM THAT IS ALSO AN ORDINARY WORD WAS DEFINED IN
NO REACHABLE DOCUMENT** — synthesis called the 14 beyond-horizon orders *"inside
this plan's horizon … left out of the schedule itself"* because "horizon" means
the date extent in English; `"committed"` retrieved ZERO corpus passages.
docs/01 **§6.10** now states the four dispositions and the everyday senses that
mislead (free — docs/01 is already CURRENT tier); `synthesis_prompt.md` **v5**
rule 12. **NOT FIXED, named:** *"what does it mean that work is beyond the
horizon"* parses to `coaching`, which lists nine submission fields (§5a.75 —
§5a.69's shape again); drill-down anaphora is a context-ladder change (§5a.77);
three prose sites still print raw minutes, deliberately, for R-PD1 clause (4)
comparability (§5a.76).

**WORKING TIME AND ELAPSED SPAN ARE DIFFERENT QUANTITIES AND ARE NEVER
INTERCHANGEABLE (4B.20, §5a.67 — §5a.56 DISCHARGED).** Any surface reporting one
names WHICH, in the field name or the sentence; **(end − start) on a chunked
operation is a SPAN**, and working time is the sum of the run windows and nothing
else. Two clauses added: **a capacity figure names its DENOMINATOR** (5821 busy
minutes against 1501 of open capacity — 3.9x — with nothing on the surface making
it checkable), and **a figure the product DERIVES must be quotable by the surface
that derives it** (see below). The census was by ARITHMETIC, not name — an AST
walk, then a binding pass: **408 raw sites → 198 time-quantity bindings → 63
OFFSETS (the solver's whole variable space) → 135 true durations, of which THREE
are wrong and all three are `evidence_tools.py`**; `_duration_minutes` feeds
THREE tools, so 4B.17's "two seams" was one function. **THE TRUER FIGURE WAS
ALREADY ON THE ROW** — `run_min`/`span_min`/`chunks` since 4B.14 — and the
toolbox discarded them to recompute the subtraction. **`board.js` WAS RIGHT AND
RIGHT BY A PROPERTY OF THE DATA NOTHING ENFORCES** (§5a.68): span occupancy
saved only by the open-window intersection, measured identical on every machine;
now per-chunk. The opener was never affected (it reads `run_min`). **MAKING THE
ANSWER TRUER MADE IT UNVERIFIABLE (§5a.70):** working time lives in no single
record, so a correct claim with four real citations was CUT — derived row figures
now enter the toolbox's tallies through a NAMED set. Guard: naming register +
value property, **its limit stated in the docstring** (the toolbox surface only),
premise test, **two negative controls proven red**. Governed: four
`TOOL_MEANINGS`, `synthesis_prompt.md` **v4** rule 11. **NOT FIXED, named:** *"how
busy is CUT-01"* parses to the contracted `machine-schedule` route, which
enumerates 18 placements and states **no utilisation figure at all** — the fixed
surface is unreachable from the question that most directly asks for it (§5a.69).

**A PERSISTED EVIDENCE INDEX IS A FAITHFUL RECONSTRUCTION OF THE INDEX IT WAS
SAVED FROM (4B.18, §5a.63 — §5a.55 DISCHARGED).** Any record class the builder
puts in `_all_evidence` survives a round trip, or the load reports itself
INCOMPLETE and names what is missing. **Silence is forbidden: an answer surface
may not be unable to distinguish "this never happened" from "this was not
persisted".** Schema 1 lost **25 records across FOUR classes** on a real run
(236 → 211), not the one 4B.17 measured: `record_event` and
`register_input`/`register_output` hardcode `subjects=[]`, so **every Event and
Artifact is subject-less**, and `load()` rebuilt from `entity_records` alone —
taking the entire input manifest and the four M0 conformance rate metrics with
the solver report. A subject-less Finding survived in `finding_index` but not
`_all_evidence`, so **one loaded index gave two answers about itself**. Schema 2
persists `_all_evidence` and DERIVES the indices on load through `build`'s own
`_index_record`. `CostProof` has a fourth state, **`unreadable`**, priority over
the other three, so a claim about the PLANT is never manufactured from a fact
about our STORAGE; the rider, the opener item and the route each have an
authored branch and **none may be silent**. Old indexes load and declare
themselves; **forward compatibility is NOT provided** (a schema-2 file read by
older code yields an EMPTY index — loud, not subtly wrong). The guard asserts by
**kind and count**, emits through the real Reporter, runs over every real run,
and its **negative control is proven red**. NOT DONE, named: the seven schema-1
indexes in `_data/runs/` are left unmigrated as the live incomplete-path
specimens; **a schema-2 file that is lossy for a future reason is not
self-detecting** (`incomplete` covers schema 1 only) — the round-trip guard
stands in that gap, because a file cannot audit itself and a test can.

**§5a.22 IS DISCHARGED — THE r5 BANK IS CALIBRATED, RUN AND GRADED (4B.17).**
27 → 33 questions, six runs, 198 answers; every expectation change logged in
`tests/ai_exam/RUBRIC.md`'s append-only RECALIBRATION LOG with its cause and old
text; the 27 original question TEXTS untouched. **NOTHING IS LATE ON THE PINNED
BOARD**, so nine lateness questions are false-premise specimens now. **FIVE
REPRODUCIBLE TRUTH FAILURES, NONE A MODEL ARTIFACT, ALL REPORTED AND NOT FIXED:**
a door label offers to *"explain why CUT-01 carries no work"* about the BUSIEST
machine (§5a.60 — a door label is a claim, and the reverse-guard only proves the
door OPENS); the no-such-machine correction lists **8 of 15** machines and drops
the one the asked order is on (§5a.54, verbatim in 4B.13's own close-out);
**the synthesis toolbox reports the merged SPAN as `duration_minutes` and
`busy_minutes`** — 5821 against 1501 working minutes, 3.9x the machine's open
time, the **FOURTH SEAM** of a class fixed three times (§5a.56 — **FIXED 4B.20,
§5a.67**, where the census proved the class has four members and three are one
function); the pinned exam
world could not state its own cost proof because `EvidenceIndex.save()` dropped
run-level records (§5a.55 — **FIXED 4B.18, §5a.63**, where the loss turned out to
be four classes and 25 records, not one); and `why-on-machine`'s evidence
chain **contradicts its own only-eligible lead and still carries the founder's
original vacuous driver phrase** (§5a.54). **THE TIER QUESTION IS STILL
UNRESOLVED AND THE REASON IS NOW STRUCTURAL: 31 of 33 questions never reach the
layer the split changes** (§5a.57) — one differing routing decision in 198
answers, and it is the parse's, which is Haiku in both configurations. Cost
$0.0105 vs $0.0110/question, **Sonnet the cheaper here**. A founder-regression
bank cannot resolve a tier decision; that needs a bank UNMATCHED by design.

**THE COUNTERFACTUAL — `what-would-change` (4B.16, §5a.49, parse prompt v13).**
The INVERSE of `why-here` over the SAME computed bounds and NO new ones: take
the docs/05 family that BINDS and report the change that would move it, with
its threshold and the arithmetic (min_chunk / predecessor finish / another
eligible lane / a longer window). **EVERY THRESHOLD IS VERIFIED BY RE-RUNNING
`earliest_fit`, THROUGH `resumable_fit` SO R-C3 APPLIES** — which is how the
brief's own specimen was caught: `min_chunk <= 240` DOES NOT WORK, the ceiling
is **215 = floor(431/2)**, because at 216 the solver treats the op as atomic.
Unverified levers are DROPPED. **NECESSARY, NEVER SUFFICIENT:** every answer
names the NEXT bound (recomputed through the ladder tail, not assumed to be the
runner-up) and says it removes a barrier rather than placing anything. B7/B8,
the objective (on `chose`) and a declared closure are NAMED as unpriceable.
Alternative lanes are scanned from the UPSTREAM FLOOR, never from the start of
their calendar. A planner-named DAY is NOT parsed — the target is computed and
the answer says which day it tested.

**THE OPENER — `briefing`, widened (4B.16, §5a.50).** Every item the document
supports, RANKED BY CONSEQUENCE, each carrying its number and a pointer;
contracted testimony, no synthesis on the path. Band 1 is money and its two
members are comparable because both are currency (controllable tardiness —
never the floor — and the unproved gap x ledger); band 4 is CLEAN, so **"three
things and none of them are on fire" is reachable**. ELIGIBILITY is what makes
a busy machine a concentration; at-risk is conservative by construction (slack
in calendar minutes vs the longest step in WORKING minutes). **WHAT THE
DOCUMENT DOES NOT SUPPORT IS REPORTED** — no tray on a monolithic run, no
coarse zone, no document at all. NOT FIXED: the certificate item cannot state
the GRADE (a submission fact the document does not carry), and concentration
did not fire on either measured board (demo density is far below 85%, so it is
unexercised live).

**A MATCHED ROUTE COULD NOT BE WRONG (4B.15, §5a.40).** Five consecutive
measured turns were swallowed by `coaching` at 0.92 confidence — including an
EXPLICIT CORRECTION reparsed into the same wrong intent. R-AI5 inverted: tier
one over-claims, tier two is never reached, and synthesis OUTPERFORMED the
routes everywhere it was allowed to run. `route_falsifiability.py` checks the
DETERMINISTIC template rendering at the dispatch seam (before any LLM render)
and falls through to synthesis on **SUBJECT SILENCE** or a **DISCARDED
DISJUNCTION** — the alternatives carry the question's own preposition, so an
answer CONTAINING the fact without surfacing the choice is a fall-through, not
a pass. **IT CAN ONLY REJECT THE ROUTE THE PARSE CHOSE**, never name one, so no
deterministic classifier returns. Fails OPEN in every direction.

**ANY DECLARED FIELD IS ASKABLE (4B.15, §5a.41).** `Intent.ATTRIBUTE_LOOKUP` +
`attribute_lookup.py`, parse prompt **v12**. "is ORD-000013 op20 splittable"
returned capability documentation with a scold while the blocker analysis
quoted the answer off the same snapshot one exchange later. The field
vocabulary is **REFLECTED off `contracts/entities.py`** — a new entity field is
askable the day it lands; the authored alias map picks WHICH FIELD to read,
never a value. The provenance chain is walked (an Operation's `splittable` is
`derived` → cite the OperationSpec's `observed` submission column). NOT
DECLARED and DECLARED-AS-ZERO render differently, always.

**CAPABILITY CLAIMS GROUND IN docs/05 OR ARE REFUSED (4B.15, §5a.43).**
`constraint_catalog.py` parses docs/05's own **MARKDOWN TABLES** into 26
records + 6 rulings + 6 exclusions — a table is structure, and docs/05 §0 says
the catalog is "structured records first". **THE PROSE-LOCKED DEBT IS
DISCHARGED FOR THE CATALOG ROWS, NOT THE PROSE** (quoted verbatim, never parsed
for meaning). The honesty register is **DERIVED** from (verdict, status), so
moving a status column changes every answer about that item; a MIXED status
gets its own register rather than being flattened. Two synthesis tools
(`constraint_catalog`, `spec_lookup`) put the same ground under tier two;
synthesis prompt **v3** rule 9 makes reaching for them mandatory before a
capability claim. Agreement with the blocker analysis's not-weighed list is
ASSERTED from `UNCOMPUTED_FAMILIES`, so the two surfaces cannot drift.
**LABELING IS NOT SUFFICIENT WHERE THE CLAIM IS WHAT THE PRODUCT CAN DO** — a
planner acts on it by authoring data that is then silently ignored, and there
is no board to check that against.

**THE CORPUS SHIPS WITH THE BUILD, IN TIERS (4B.15, §5a.39).** `corpus.py`:
CURRENT (docs/01/05/06) free rein; **HISTORICAL (docs/04) opt-in and every
passage DATED** — it carries superseded rulings as first-class text, so a
first-match retriever states a retired mechanism as current with a real
citation; **INTENT (docs/07) REACHABLE BY NOTHING**, enforced by
`TIERS_FOR_PURPOSE` not listing it. Fail-closed dating DROPS the 15 undated
`D-nn` founding decisions. **`docs/` IS NOT IN THE RUNTIME IMAGE** (the
Dockerfile says so), so the index is package data with a sha256 per document —
a spec edit without `python tools/build_corpus_index.py` is a RED TEST.

**THE REPEAT DETECTOR WAS INVERTED AND IT SCOLDED (4B.15, §5a.42).** Four
measured firings, ZERO true positives, escalating to "Still the same; nothing
has changed since you asked". It counted MY OUTPUT (how recently a route
answered) and read it as THEIR INPUT. Split: `repeat` needs the same QUESTION;
`deaf` needs the same delivered ANSWER for a DIFFERENT question and responds
with self-doubt plus an offer to narrow. **THE SIGNAL IS THE OUTPUT, NOT THE
ROUTE.**

**THE TIER IS MEASURED, AND WAS UNASKABLE UNTIL IT WAS (4B.15, §5a.44).** Both
governed call sites hardcoded `temperature=0` — a **400 on Claude Opus 5 and
Sonnet 5**, so every request to both candidate tiers failed at the transport
before any answer existed to grade. `llm_compat.py` fixes it and retries once
without the offending field. `tools/model_tier_bench.py`, counted tokens:
**parse on Haiku + synthesis on Sonnet 5** ties best correctness (14/15) and
multi-hop (7/8) at the LOWEST median latency (1.5s) and 37% under
Sonnet-everywhere. **Opus 5 is NOT recommended** — 2.7x, better on no quality
column, and the source of the bench's only fabricated answer (three
non-existent machines, zero tool calls, correctly labelled and shipped anyway).
**NOTHING SHIPPED CHANGED — both layers still run Haiku; the tier is Daryn's
call.**

**ITEM 0: A TRUE FACT ABOUT THE WRONG DAY (4B.15, §5a.45).** 4B.14's close-out
is CORRECT — PAINT-01 is OPEN on Tue Jan 13 and carries ZERO work; the live
answer's "07:00 to 11:24" is real occupancy on Tuesday **Jan 6**, the other
Tuesday in a five-Tuesday horizon. Nothing told the model what day it was. The
shared context block now carries the reference date and horizon; synthesis rule
10 forbids taking a weekday from whichever row appeared first. 4B.14's chain
was re-verified from the snapshot and is unchanged.

**THE EXPLAINER KNEW ONE CAUSAL STORY AND THE PLANT HAS SIX — `why-here`
(4B.14, docs/07 §5a.35, parse prompt v11).** `start-reason` answered every
"why is it placed here" with resource contention, the last job on the machine;
when the true cause was one of the other five it reached for the only one it
had and rendered it fluently, with citations.
`src/mre/modules/blocker_analysis.py` computes an earliest-feasible-start per
docs/05 family — release A4, precedence A1/A2, frozen R-F1, pin A7/F1, resource
B1, calendar C1/C2, chunk-fit C3 — and names the one that BINDS. **BINDING is
the EARLIEST family attaining the maximum**: when precedence and chunk-fit land
together, precedence pushed it and chunk-fit merely failed to push further.
**THE DISTINCTION THAT MATTERS MOST, and the product could not draw it:**
`actual == max(est)` is COULDN'T; `actual > max(est)` is NOTHING PREVENTED IT
and the solver CHOSE. Four docs/05 families are **NAMED as uncomputed on every
answer** (B3/B5, B7/B8, C4, F3); A3/A6 are out of scope, being upper bounds.
The route is AUTHORED COPY — **the verb is the answer**, and a reword that
softens "couldn't" is the failure it was built to end.

**ITEM 0 RETURNED (A): THE SCHEDULE IS RIGHT, THE EXPLANATION WAS WRONG.**
ORD-000013's op20 is `splittable=False`, needs **431 working minutes**, and had
**294** left before PAINT-01 closed on Tuesday; Wed Jan 14 is a
`planned_maintenance` closure on **13 of 15 machines** (HEAT-01/02 open).
**THE ROOT CAUSE WAS A THIRD FIRST-CHUNK-ONLY READ (§5a.34):**
`_load_enriched_assignments` read `phase_windows["run"][0]["end"]`, so a chunked
op reported its first PAUSE as its end — the exact figure the bad answer cited.
4B.13 fixed the same class at two other seams and stopped. **A defect class
fixed at one seam is not fixed.**

**CAUSAL SUFFICIENCY — A CITED CAUSE MUST ACCOUNT FOR THE QUANTITY IT EXPLAINS
(§5a.36, `causal_sufficiency.py`).** "Held until T, so it took the next opening"
asserts an arithmetic identity nobody checked. **The 4B.5 vacuity tripwire
cannot catch this and neither check subsumes the other** — the specimen names an
order, a machine AND a timestamp, and would pass with the timestamp off by a
year. **The two 4B.14 fixes are independent, and this is pinned:** repairing the
chunk read alone leaves the sentence false, because the real cause is chunk-fit.

**DISAGREEMENT LAUNDERING (§5a.37, `ContestedClaim`).** "it seems it should be
able to start on tuesday after op10 finishes" came back "is ORD-000013 really on
time? Yes - the record agrees." The intent was right; the ASSEMBLER knew one
proposition and its canonical question said so verbatim. **Worse than a wrong
number, because the planner cannot tell they were ignored.** The parse now
reports which claim is disputed (`lateness`/`timing`/`other`, also on
`why-here`) and a challenge is answered ON ITS OWN TERMS — where the planner is
right, plainly, first. `predicate_coverage` went from **one entry to three**,
both additions measured.

**Contract 1.12** (4B.14): `AssignmentBlock.splittable` + `min_chunk_min`, both
Optional and absent on an older document. The job card carries RUN TIME and
ELAPSED SPAN as **separate labelled rows** — after 4B.13's chunk fix they
genuinely differ (1,501 working minutes across a 5,821-minute span) and
conflating them is the confusion the merged bar used to create.

**CLOSE-OUTS LIVE AT `docs/closeouts/<session-id>.md` — ONE PATH PER SESSION,
NOTHING OVERWRITES** (4B.13 Item 6). Until then every session wrote the repo-root
`SESSION_CLOSEOUT.md`, so the newest close-out silently replaced the last one and
a stale root file kept being read as current. Historical references in docs/04
(append-only, never rewritten) and older docs/07 entries name the ROOT path; they
mean that session's file, now under `docs/closeouts/`. Errand and recon reports
follow the same rule with a qualified name (`4B.12-errand-exam-world.md`).

**THE CLIFF IS AT 92 OPS/MACHINE, NOT 137 — AND §5a.27's NUMBERS ARE SUPERSEDED
(4B.12, docs/07 §5a.31; §5a.27 carries a dated note and is NOT rewritten).**
Re-run against **byte-identical worlds** (`verify_world_identity.py`: 8 worlds,
all identical; the generator untouched since 4B.10's commit), the last density
proving 5/5 is **92** and at **94** it is **0/5**. Cause is 4B.10's own
mechanism firing everywhere: R-PD1 admits past-due work, so the floor is nonzero
wherever late work exists and CONTROLLABLE tardiness is nonzero at the LIGHTEST
density measured — **there is no tardiness-free regime left on this book**, and
the proof costs **200-360x** what it cost on the same world without its late
work. **OPS/MACHINE IS REFUTED AS A PREDICTOR by a sharper argument than
utilisation was: the proof cost is not even MONOTONE** — 65 ops/machine proves
in 0.045-0.286 units while the LIGHTER 50 takes 0.294-0.735.

**F004 AND F006 ARE SOLVED, NOT BRACKETED (§5a.31(e-g)), and the product result
is ANSWERABILITY.** F004, the MEDIAN facility: 254 ops/machine, **0/5 proved,
gap 83.5-85.8%**. F006, the largest: 772 ops/machine at 134.9% utilisation,
**gap 98.8%**. **NOT ONE CELL AT ANY DENSITY RETURNED UNKNOWN** — every failing
cell places every admitted op and states its own gap, while a FIRST SOLUTION
costs 0.0002-0.147 units against a 5.5-unit cap that cannot close the bound
(37x at F006, 948x at 149 ops/machine; 4B.8 measured the same shape at 74x).
**The problem at real density is not producing an answer, it is proving one** —
which is why 4B.11's rendered gap is the right response and a pre-solve warning
is the wrong one. **EVERY a=1 FIGURE IS THE OPTIMISTIC ONE:** the plant
cross-trains, and a=2 proves 0/5 at 100 ops/machine where a=1 manages 1/5.
**REPORTED, NOT FIXED — the tardiness split needs a THIRD category** at F006:
"controllable" means not-already-accrued, NOT discretionary, and on a 134.9%
plant most of it cannot be scheduled away by any placement (§5a.31(g)).

**`hint_mode` — THE WARM START, SHIPPED BEHIND A FLAG, DEFAULT OFF** (4B.12 CU3,
`rolling_horizon.py`; guards in `tests/test_hint_warm_start.py`). Its spend comes
out of the SAME `det_total`. **Turning it on is a ruling, not a default change** —
every golden is captured with it off. Verdict in docs/07 §5a.32.

**R-PD1 — PAST-DUE IS WORK, NOT A DEFECT (ruled and implemented, docs/04
2026-07-28).** Six clauses. **(1)** a past-due unstarted demand is admitted,
scheduled and priced with tardiness from its DECLARED due date. **(2) EXCLUSION IS A
DATA-DEFECT CATEGORY ONLY** — never for a true statement about the plant's position
(late, beyond horizon, over capacity); this **generalizes §5a.1 and §5a.26 into one
rule**. **(3) THE GATE'S DISPOSITION BINDS DOWNSTREAM** — a module removing a
`proceeded_flagged` demand raises its OWN finding naming ITSELF (`excluded_by_module`
in evidence; the general guard is committed in `tests/test_pastdue_disposition.py`,
35 tests). **(4)** tardiness decomposes and never fuses. **(5) AGE IS NOT LATENESS —
OPEN, deliberately unbuilt** (§5a.28: the threshold is a declared IDS coefficient
that does not exist, and inventing one authors a business fact we do not have; the
full pipeline-proof chain is named in docs/06 §5.9). **(6)** every per-order route
voices the disposition.

**21 of 21 past-due orders are SCHEDULED on the specimen, and GRAVITY DID NOT HAVE
TO BE TOLD** — measured, they are admitted by the BASE rule (`due <= window_end`)
before gravity runs at all, so the admission policy needed no change and got none.
`validator.py` Check 1 excludes nothing and raises one
**`PAST_DUE_AT_INTAKE`** finding (**finding code 19**, ADDED never repurposed —
`TEMPORAL_IMPOSSIBILITY` is M0's verdict on `due < release/created` and keeps that
meaning) at INFO / `proceeded_flagged`, `remediation_applies: false`. **A SECOND
EXCLUSION SITE was found and closed:** Check 5's resumable window-fit test floors
`elapsed_days` at 0, so every past-due resumable demand would have been excluded
there as `INFEASIBLE_SUBSET` — the same removal wearing a different code. And
**scheduling past-due WORK never means modelling past TIME**: `_compute_horizon`'s
reference-date floor is now unconditional (sample_data dragged the horizon to
**2024-12-20** without it).

**THE TARDINESS SPLIT — contract 1.10 -> 1.11.** `cost_summary.tardiness_floor` +
`tardiness_controllable`, present TOGETHER or not at all, summing to `tardiness` to
the cent, **ABSENT on any book with no past-due work**. It does not change the model
— the floor was never in the objective. **4B.12 found its LIMIT: an over-capacity
plant needs a THIRD category** — see above.

**§5a.23 DISCHARGED — the cost proof is rendered and voiced.**
`src/mre/modules/cost_proof.py` is the single definition. The cockpit strip carries a
chip (label + title composed SERVER-SIDE, delivered on `/meta`, so the JS composes no
wording); the answer surface carries an unprompted rider fired by the ONE delivery
seam **only when the board is UNPROVED and the text states money** — the asymmetry is
the point. Every bundle leaving `Explainer.route` carries the proof, read from the M6
`solve_complete` event the document's `SolverBlock` is also built from. **The rolling
path could not state a gap at all** before this. **No optimality ROUTE was built** —
a vocabulary-class change, named as §5a.29.

**THE 42 IS RECONCILED** (4B.11): `_excluded_summary` counted a token set holding
both id-spaces of every excluded demand. Counting keys on the **resolved ORDER**
and `scheduled + count == total` is asserted.

**THE sample_data BASELINE WAS REGENERATED** (WO-PAST-001, seeded defect 3, whose
`DEFECTS.md` declared `proceeded_flagged` all along). **Accounted for by
construction:** the pipeline re-run with that single row REMOVED reproduces the
previous golden **byte-for-byte**. New golden **801,930.00**, tardiness
**777,521.00**, of which **776,160 is FLOOR**; `pilot_scale` and every rolling golden
untouched. **Two fixtures were building against TWO CLOCKS** (bare `SolverBuilder()`
while pinning a reference date elsewhere in the same run) — invisible until a
released-long-ago order became schedulable; both now pass the date they had pinned.

**THE REAL SHAPE, AND WHY IT REFRAMES SCALE (4B.10; full tables docs/07 §5a.24-27).**
`pilot_scale` runs 13-15 machines at ~24 ops/machine; **the measured planning unit is
4 MACHINES CARRYING 250-800 OPS EACH.** No long tail — 90% of demand due inside 14
days, 50% inside 7, **7.83% ALREADY PAST DUE**. Durations are **DETERMINED**:
`op = SetUpMinutes + (WoQuantity/CostingLotSize) x ProductionMinutes` (§5a.25) — and
**a SENTINEL CLASS carries 93.56% of computed load** (1,434 products reading
`lot = setup = production = 1`; **no exclusion rule we have catches them**, they fire
on `lot == 0`). Every utilisation figure is taken with the class removed.
**Utilisation is BOTH answers:** F006, the LARGEST facility, is structurally
over-capacity (no solver fixes that); F004, the MEDIAN, is comfortably feasible —
**there the difficulty is OURS**. The cases must not be conflated.

**THE CLIFF IS A REGION WHERE THE SEED DECIDES, AND ITS DRIVER IS TARDINESS
(§5a.27). ITS NUMBERS ARE SUPERSEDED BY 4B.12 — the MECHANISM below is current,
137 and 13.056% are not.** Priced, not asserted: freeing the tardiness weight turns
FEASIBLE/gap-11.47% into OPTIMAL and collapses the objective's spread across feasible
solutions by a factor of **194** — **not constant, nearly flat**. UTILISATION was
refuted as a predictor twice; 4B.12 refuted ops/machine as well, so **no pre-solve
rule can exist** and the honest mechanism is REPORTING (why §5a.23 mattered).
**Caveat that must travel:** this mirrors an extract with no setup families, no
changeover matrix and no overtime; a plant that prices changeovers carries a
placement-dependent term even at `alternates=1`. What generalizes is the SHAPE of the
rule — difficulty turns on how much of the objective varies with placement — **not
any particular number**.

**`facility_real` ADDED, `pilot_scale` UNTOUCHED AND PROVEN SO.** Four variants (F004
median / F006 largest / cross-trained / F005's 25% past-due), calibration CHECKED by
`tools/spikes/density_4b10/verify_facility_real.py`, measured-vs-authored table at
`datasets/facility_real/PROFILE_PROVENANCE.md`. `pilot_scale` keeps its purpose as the
LOOK-AHEAD preset; `facility_real` is the REALISTIC one. **Alternates are
CROSS-TRAINING, not extra machines** — identical machine count and load, so the pair
is a controlled experiment. **Its CONDITIONAL grade is a GENERATOR TRUTHFULNESS
DEFECT, not the past-due orders — 4B.10's claim to the contrary is CORRECTED
(§5a.30)**; NOT fixed, because the inversion is what keeps R-PD1 clause (3)'s guard
non-vacuous.

**THE TWO-STAGE BUDGET IS DERIVED, NOT A CONSTANT (4B.8 CU2).** The caller declares
a TOTAL (`det_total`); stage 1 is capped at total minus a **1/12 RESERVE**; stage 2
gets what the total has left after stage 1 actually ran. The reserve is what keeps
R-SC3(1) true at scale. The MONOLITHIC path passes `cap_stage1=False` (its cost proof
stays uncapped) with a 2.0 total; raising it was measured and REJECTED.

**THE STATUS LINE REPORTS THE COST PROOF (4B.8 CU3 — a RULING, contract 1.9 -> 1.10).**
`solver.status` carries **STAGE 1's** status; Optional `solver.tiebreak_status` /
`tiebreak_skipped_reason` carry stage 2's. **A schedule whose cost is proven optimal
SAYS SO, and an unproven tiebreak never downgrades that claim.** **§5a.23 is
DISCHARGED by 4B.11** — the strip chip and the money-answer rider both read it. What
remains (§5a.29) is that nobody can ASK: there is no optimality INTENT, so
"is this optimal?" falls to synthesis, which cannot see `solver.status`.

**`EARLINESS_PREFERENCE` IS DORMANT (4B.8 CU4, interim only).** The extractor no
longer emits it; `CAPACITY_BLOCKED` carries real occupancy evidence instead. **The
DriverCode member SURVIVES and docs/07 §5a.20 stays OPEN** for the vocabulary
migration.

**§5a.15 DIAGNOSED, NOT FIXED (4B.8 CU5): THE 200-ORDER / 14-DAY INSTANCE IS
FEASIBLE** — a solution in **0.082 deterministic units** once the objective is
dropped, so **NOT an R-SC2 admission defect**; the COST solve finds nothing in 6.0,
a factor of **74**. 4B.12 measured that same shape across nine densities (37x-948x)
and it is the reason CU3's warm start exists.

**R-SC3(2) IS RETIRED — `earliness_value` IS NO LONGER A PRICE** (4B.7, docs/07
v2.52). Stage 1 minimizes COST ALONE on both paths and the coefficient parameter is
DELETED from both signatures so it cannot leak back (measured: the price cost
+73.20% of ledger at 40 orders / +97.61% at 120). **R-SC3(1) stands: stage 2 IS the
tiebreak and runs UNCONDITIONALLY** at every coefficient including 0 and undeclared.
`earliness_value` survives as a **REPORTING rate** on its own labelled line,
`in_ledger: False`, never in `cost_summary.total` nor a delta card's money.
**THE INVARIANT, ASSERTED: the SCHEDULE is byte-identical across every
`earliness_value`** — a failure means the coefficient is back in the objective, and
that is the only way it can return. Discharged with it: §5a.16, .17, .12, .9.

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
  both intake paths (natural roll and gravity admission) and the rolling worker
  WRITES it since 4B.6a, judging each prediction exactly once.
- **EVERY LOAD FIGURE NAMES WHAT IT DID NOT COUNT** (4B.6a). Resumables and
  over-capacity ops consume ZERO coarse minutes, so load is understated — answers,
  tooltips and the band footer say so, and say nothing when nothing is excluded. A
  plant with no declared derate is told loudly its figures assume full utilization
  (a docs/06 §5.9 remediation note, **not a gate rule** — 36 rules, unchanged).
  Resumables are EXCLUDED and NAMED (`coarse_unmodelable`): single-bucket forcing
  would TIGHTEN the relaxation, and that exclusion is what makes clause (1) true.
- Ask path: `coarse-fit` + `bucket-load` joined the closed vocabulary (parse prompt
  **v9**). "When will ORD-X start" got NO new route — it is `why-not-scheduled-yet`,
  carrying the coarse bucket BESIDE the untouched `earliest_window_estimate`
  heuristic (two figures, two methods, never fused).

**THE DELTA CARD SPLITS ITS VERDICT (4B.5 CU1).** `cost_delta_abs` measures the
RE-SOLVE, not the move. Beat two also solves the window WITHOUT the pin (the
BASELINE, cached per incumbent) and the card always shows *window re-optimization*
beside *your move*, summing exactly to the total. **A planner's move is judged
against the baseline, never the stale incumbent.** An unprovable baseline shows the
unsplit total with an explicit "includes window re-optimization" line — never a
silent fused number, never a half split.

**R-F1/R-F2/R-F3 are RULED and RECORDED, not built** (4B.5 CU6; verbatim in docs/04,
summarized in docs/07 §6). The planner-movable frozen boundary (a thaw makes standing
pins, never free work); rush intake as a Demand the SOLVER places; the OUTCOME ->
WINDOW -> PIN ladder with optional reasons. NAMED-QUEUED: the pin register,
amend-submission (pilot-relevant), the boundary-drag gesture, the window constraint.

**The ask path (R-AI5) — two tiers, sealed from each other, and a loop between
them.** Every question is parsed FIRST by a model against the closed intent
vocabulary (`src/mre/contracts/parse.py`), with the conversation history, the live
board selection, the last-answered subject and the OPEN DELTA CARD as context. The
resolution ladder is **card > selection > last answer > history > clarify**; while a
priced card is showing, `open-card` READS IT BACK rather than re-deriving it, so the
two surfaces cannot state different numbers. **No deterministic classifier survives
anywhere** — `Explainer.classify` / `answer` went in 4A.5a and
`rolling_questions.classify_rolling` (the last one) in 4A.5c. They must not come back.

- A **matched** intent dispatches into the unchanged route assembly, render and
  validator — unless the parse reports a **dropped qualifier** (a time scope, an
  "actually", a comparative the route cannot honour), which diverts it to the second
  tier and names it in the rendered-by line. The parse REPORTS; the dispatch decides.
- An **unmatched** intent goes to **labeled open synthesis** (R-AI5(2)): a model
  reasons over the closed read-only tool surface (`src/mre/modules/evidence_tools.py`)
  under a stated budget and drafts structured CLAIMS, hardened claim-by-claim by
  `claim_verifier` — **deterministic code, never a model** — into VERIFIED /
  INTERPRETIVE / FAILED-and-cut. Provenance is visible per claim, the register is
  `synthesis`, and "prove it" re-runs the grounding pass on one claim.
- A matched intent can NEVER fall to synthesis, and an unmatched one NEVER guesses a
  route (pinned by dispatch tests). Without a parser or synthesizer the honest floor
  answers that it could not interpret / could not ground.
- On a **rolling** run, subject resolution reads the document's three regions
  (`RollingVocabulary`): a beyond-horizon tray order resolves as a real subject with a
  BEYOND-HORIZON disposition. **A tray order is never "not in this schedule."** Since
  4B.11 the same route RESOLVES a placed order instead of offering a disjunction.

**THE PROMOTION LOOP (R-AI5(5)/(7)) — the system proposes its own healing; the
proven register is entered only by review.** Every sweep writes a question ledger and
emits `tools/provenance_report.py`: synthesis residue clustered into recurring shapes,
ranked by a frequency-weighted Pareto. **R-AI5(6) is printed in the report's own
header** — clusters whose residue is takes or aggregate reads are
NOT-PROMOTABLE-BY-DESIGN, excluded from the Pareto, never counted as backlog.

- `tools/promotion_dossier.py` drafts a dossier autonomously (`docs/promotions/`) and
  **cannot reach dispatch**. The dossier is the application; the working thread's
  review is the signature. Promotion is a **reviewed vocabulary-class change** (Intent
  + meaning + taxonomy + offer + assembler + authored copy + prompt bump + a
  `PROMOTIONS` entry citing the dossier). **Never automatic.**
- A promoted route runs **shadowed** through probation: the sweep answers its shape
  under both paths and diffs the facts. **Demotion is automatic** on a contradiction —
  one field in `contracts/promotion.py`, and the intent leaves
  `model_selectable_intents()`, so the parse can no longer name it.
- Live: **one** promotion, `lateness-cause`, on probation.

**R-AI5(8) is the hard rule of the tier:** the answering model's beliefs about its
own citations are INPUT to verification, never the label — and the same discipline
governs routing (the parse reports a dropped qualifier; it never decides the
diversion). Both prompts are governed artifacts: changing either is a
vocabulary-class change, reviewed, versioned, committed with its doc update.

**Where history lives — do not duplicate it here:**

- `docs/07-roadmap.md` is authoritative for *what comes next*. Check it before
  picking up work. It is updated same-day per its own W2 rule.
- `docs/04-design-history.md` is authoritative for *what happened and why*. It is
  append-only. **Read the Amendment log tail before touching any area it covers.**
- Session close-outs are written to docs/04 and docs/07 — never narrated here.

**R-DP13 — `PLANNER_DIRECTIVE`, THE CODE THE TAXONOMY LACKED (4B.33, §5a.133,
docs/04 2026-08-03). §5a.130 CLOSED.** `DriverCode` **13 -> 14**, ADDED never
repurposed, docs/02 §4.2 same commit. A `planner_edit` accept's real driver is
*a human directed this placement* — every other member names something the PLANT
or the MODEL did. **THE DRIVER IS A CONSTANT AND THE SIGNATURE NOW SAYS SO:**
`_edit_driver` takes **NOTHING** (it took `cost_delta`), because a signature
accepting a quantity advertises a derivation that no longer happens; R-DP12 is
not weakened, since its rule was *never the incomparable scaled objective* and a
constant trivially is not. **THE PHRASE MAY NAME NO DIRECTION** — *"a planner
directed this placement, and its cost was priced before it was accepted"*, true
at EVERY ledger delta, stating only what is checkable on the record
(`authority`, `chosen.cost_delta`), and saying **"a planner", not "you"** (the
reader is not necessarily the authority). **`COST_TRADEOFF` JOINS
`NO_ALTERNATIVE` IN RETIREMENT FROM THIS SITE** — false at $0.00 AND false of a
dearer accept — while staying correct wherever a cost genuinely decided
(planner merges, the extractor's price-ranked attribution, and
`POST /audit/accept`, where the accepted board IS the cheaper one). **NO CONTRACT
BUMP AND NO docs/06 DOORWAY ARE OWED, BOTH ANSWERED ON THE RECORD:**
`CONTRACT_VERSION` versions the schedule DOCUMENT and `driver` lives on Decision
records the document does not carry; the pipeline-proof rule governs declared
facts about the PLANT, and this classifies an act performed INSIDE the product
(R-CAL1's product-side/IDS distinction on another axis). **LIVE on the Khalil
board:** children `caff8efa` (zero-move, 6.99s) and `e2e18e8c` (+24h, 3.70s),
ledger $1,667,467.80 unchanged on both, and the drill-down voices the phrase
verbatim. **NOT FIXED, named (§5a.135):** no exam bank can reach it — neither
pinned world holds a single `planner_edit` Decision (0 of 32, 0 of 96, measured)
because an accept mints a CHILD at runtime, so the specimen needs a new pinned
world; the `edits`/`edit_cost` routes **do not voice the driver at all**
(`_edit_facts` never carried it and the renderer short-circuits the chain), so
the drill-down is its ONLY live surface; *"why is this bar here?"* still lands on
CLARIFY `no-subject`; and the R-F1 boundary move keeps `FROZEN_COMMITMENT`.

**THE GOLDEN-CSV FLAKE IS FIXED, AND THE BUDGET WAS ALREADY THERE (4B.33,
§5a.134 — §5a.132(e) DISCHARGED).** The per-stage measurement IS the finding:
stage 1, the **cost proof**, has no deterministic cap and proves **OPTIMAL in
0.81s**; stage 2, the earliest-start **tiebreak whose placements ARE
`schedule.csv`**, already carried a **1.953-unit deterministic budget** and
needed **14.56s** of a 30s wall. **THE WALL WAS OVERRIDING A BUDGET THAT WAS
ALREADY CORRECT**, by barely 2x — and under load the solve DOUBLES (73s vs ~35s
measured), putting stage 2 at ~29s against 30s. **That is the coin flip and why
it failed about HALF the time.** **NO MECHANISM ADDED AND NO CLI FLAG NEEDED**:
`test_defaults_reproduce_baseline` now passes `--time-limit 600` (a SAFETY
CEILING ~40x the solve, ~4x the worst case at 77 s/unit), so each stage is
reproducible **for its own reason** — stage 1 because it PROVES, stage 2 because
its DETERMINISTIC budget binds. **THE PREMISE IS ASSERTED:** `_run_mre` fails
loudly if the cost proof stops proving, since then the ceiling becomes
load-bearing again. **NEITHER GOLDEN MOVED** (`sha256 cc6242b4…`; ledger
801,930.00 unchanged), nothing re-anchored. **9 FOR 9** byte-identical (6 quiet,
3 under load). **THE CONTROL IS THE MECHANISM:** the old 30s wall did NOT
reproduce in 10 quiet runs — recorded, not glossed — while **forcing** it to bind
(`--time-limit 8`) gave a byte-different schedule 3 for 3. **THE SHAPE
GENERALISES TO ONE OF THE THREE REMAINING FLAKE MEMBERS:**
`test_scenario_untouched_moves_bounded` needs the full determinism triple AND the
wall lifted; the two SCREENSHOT members are render/timing races a deterministic
budget does nothing for.

**R-DP12 — THE LEDGER IS THE ONLY COMPARABLE NUMBER (4B.32, §5a.129, docs/04
2026-08-03). THE INCOMPARABLE NUMBER WAS ALSO WEARING A DOLLAR SIGN.** Live on
the Khalil board, twice, identically: a ZERO-MOVE accept whose ledger went
**$1,667,467.80 → $1,667,467.80** recorded `driver: NO_ALTERNATIVE` and a
Decision message reading **`(−$7,014,821)`** — so the store the ask layer
testifies from held a sentence claiming a $7M saving for a move that changed
nothing. `delta_abs` is the restricted accept model's SCALED objective minus the
**WINDOW SOLVE's**: different expressions, different op sets. **CU1 — VERDICT
IDENTITY:** under `hold_all_placements` every variable is pinned, so the
objective **cannot change the plan and can only change the WORD**; the accept
now **clears it**, exactly as the card's `validate_held_world` always has
(`cp-sat-pin-all`). That makes the two surfaces **ONE AUTHORITY**, which
**DISCHARGES R-DP10** — and the three discharge conditions (one compiler, one pin
seam, one question) are in docs/04 so **the obligation REVIVES if any lapses**;
it also closes 4B.31 §8(c) (the accept PROVES OPTIMAL, never a budget verdict).
**R-T2's disclosure line is STRUCTURALLY MOOT here, recorded not dropped.**
**CU2:** driver and every dollar derive from `cost_delta.total_delta`; the scaled
objective survives only as **labelled solver telemetry** and is **None, never
0.0**, where the objective was cleared. **`NO_ALTERNATIVE` IS RETIRED FROM THE
ACCEPT** — *"there was no other feasible option"* is a claim about the PLANT that
under a full hold would be manufactured from a property of OUR METHOD. **THE
TAXONOMY HAS NO HONEST CODE AND THE GAP IS RECORDED, NOT PAPERED OVER**
(§5a.130): `COST_TRADEOFF` lands at every delta including $0.00, where it
**over-reads**; the missing member is `PLANNER_DIRECTIVE`, a reviewed
vocabulary-class change NOT taken. The driver is a CONSTANT deliberately — the
variation `delta_abs` supplied was noise with a sign. **CU4:** the R-DP11
property guard asserted `seen[0]`, so a second WIDER build would have passed the
guard written to forbid it — now every build (§5a.131). **NOT FIXED, named
(§5a.132):** the ledger-MOVED branch is **unreachable from a drag on this board
and that was MEASURED** — 54 gestures, **50 refusals and 4 prices, every price
exactly $0.00** — so the dearer/cheaper branches are asserted by unit test, never
observed live; `hold_all_placements=False` keeps its objective correctly and has
NO live coverage; `POST /audit/accept` was not touched (its `delta_abs` is a
LEDGER figure, believed from 4B.25 and not re-derived here); and the
`COST_TRADEOFF` phrase is false of a DEARER accept, pre-existing.
**4B.31 FINDING (g) IS CORRECTED (§5a.132(e) — FIXED 4B.33, §5a.134, where the
cause turned out to be a deterministic budget the wall was OVERRIDING):
`test_defaults_reproduce_baseline::test_schedule_csv_identical` is NOT merely
load-sensitive — on an IDLE machine it is pass/FAIL/pass/FAIL on this tree and
pass/FAIL/pass on a clean detached HEAD worktree, i.e. it fails ~HALF THE TIME
at HEAD with nothing else running.** `_run_mre` pins workers, seed and
PYTHONHASHSEED; the ONLY unpinned thing is `--time-limit 30`, a **WALL** limit,
which the hard rules already call irreproducible. `test_cost_ledger_identical`
passed **six for six** — the LEDGER is stable and only the placement drifts
among tied optima. The fix shape is a deterministic budget in that fixture.

**R-DP11 — THE ACCEPT MODEL IS THE PLAN OF RECORD'S OWN SCOPE (4B.31, §5a.126,
docs/04 2026-08-02 verbatim). NOTHING HAD EVER COMMITTED ON A ROLLING BOARD.**
A card reading *"PROVEN WITHIN BUDGET"* against an accept answering `INFEASIBLE`
turned out not to be about the move at all: a **ZERO-MOVE accept** — pinning a bar
at its own placement — refused on every rolling board (409 in 2.4-2.5s) while the
same gesture on a MONOLITHIC board returned 201. **THE MECHANISM IS SCOPE.**
`apply_planner_edit` built over **the WHOLE BOOK** against the **WINDOW's**
horizon: the Khalil snapshot holds **695 operations and the plan places 386**, so
the **309 beyond-horizon tray ops the rolling engine declined to admit** re-entered
as free work that had to fit 31 days around 386 held placements. Two-cell control:
whole book **INFEASIBLE 0.6s**, plan-of-record scope **OPTIMAL 0.1s**, **zero pin
refusals in both**. A deletion filter reduced the cause to **ONE tray order,
ORD-000062**. **THE FIX WAS SIX SESSIONS OLD AND WIRED TO THREE SURFACES OUT OF
FOUR** — `_restrict_window` (4B.3c CU3) reaches beat one, beat two and the audit;
the ACCEPT had no such parameter. Five clauses; the load-bearing ones: the scope is
**DERIVED INSIDE THE ACCEPT, never passed in** (`sandbox.plan_of_record_scope`,
**None never the empty set**), the published plan is a feasible assignment **BY
CONSTRUCTION**, and on a plan that places every operation the scope is the
**IDENTITY** (90/90 on three monolithic boards — goldens untouched). Live: the
Khalil board commits, ledger **$1,667,467.80 → $1,667,467.80, delta $0.00**, and
card-vs-accept agree on **18 gestures, 0 disagreements**. **THE GUARD NEEDED TWO
MEMBERS (§5a.127):** at 40 and 80 orders the whole book FITS and the zero-move
accept is **GREEN AT HEAD, defect and all** — only `pilot_scale` 200/w7 reproduces
— so the invariant is asserted as a **PROPERTY** (the ops handed to the live
`SolverBuilder.build` == the plan's placed set), **RED at HEAD even on the sparse
fixture**; three negative controls proven red against physically reverted code.
**R-DP10 (verdict authority) IS RULED AND ITS TWO-BEAT CARD IS NOT BUILT** —
criterion 5 unmet, by judgement not blocker; the residue is that the accept
re-solves WITH an objective and can return UNKNOWN where the card's
objective-cleared validation proved OPTIMAL. **Daryn decides.** CU4 shipped: a
refused accept names its blocker in the **4B.24 refusal vocabulary, one
definition** — *"that time is already taken on this machine (ORD-000138) [B1]"*.

**R-F1's MECHANICS, BUILT AT LAST (4B.28, §5a.119, docs/04 2026-08-02
verbatim).** R-F1 was ruled 2026-07-26 and NOTHING HAD EVER BUILT IT — for six
sessions the frozen boundary rendered as a labelled line nobody could touch. It
is a real handle now: hover states it, drag moves it, and the instant + delta
render DURING the drag with the committed boundary still drawn beside the
provisional one. **A THAW CHANGES AUTHORITY, NEVER POSITION** — every committed
assignment the boundary uncovers becomes a STANDING PIN at its exact placement,
**which is why `frozen_boundary.py` contains no solver** and why the child
version SHARES ITS PARENT'S RUN AND SNAPSHOT (the placements ARE the parent's
placements, so the ask path keeps reading the same evidence in the same run dir).
**A FREEZE ABSORBS THE PINS IT CROSSES** — the first release of a standing pin
this product has performed, deliberately narrow: only pins the frozen front now
binds anyway, so no placement is ever left unheld; the general `unpin` verb is
untouched. **THE CEREMONY IS TWO CALLS** — a preview that mutates nothing and an
apply handed the preview's own digest — so the count on screen is the count that
applies and a board that changed under the dialog is REFUSED (4B.25's
`expect_delta_abs` at a second seam). **DEMONSTRATED END TO END on the Khalil
board:** thaw 8 (committed 24 -> 16, 8 pins, **placements identical**), ask
*"why is ORD-000001 pinned?"* -> the boundary move naming its instants and its
planner, re-freeze 8, **absorb all 8**, placements STILL identical. A drag past
the window end refuses by name. **`frozen` NOW OWNS "PINNED"** (parse prompt
**v16**, one MEANING widened, no new intent — the route existed and the assembler
could answer): before it, "why is ORD-000001 pinned?" went to `attribute-lookup`,
which correctly said it could not find that field, because *pinned* is not a
field — it is a fact about AUTHORITY. **NAMED LIMIT: STANDING PINS DO NOT SURVIVE
A SLICE ROLL** — splicing seam 3 is unbuilt, and the thaw gesture now mints
exactly the objects seam 3 must preserve, which makes it the strongest argument
yet for seam 3 being NEXT after the demo.

**SCREEN ROOM, AND THE DROP MAPPING CHOSE THE MECHANISM (4B.28, §5a.121).** Three
docks (tray / coarse / ask) collapse to a labelled edge, persisted per browser,
tray and coarse collapsed by default and ask OPEN. **THE BADGE SURVIVES THE
COLLAPSE** — a collapsed tray reading "BEYOND THE HORIZON 122" is not a hidden
tray, and that is the Glass Box cardinal danger the tray exists to answer.
DOWNTIME COMPRESSION uses **vis-timeline's own `hiddenDates`, not a custom
scale**, and the requirement that decided it is the DROP MAPPING: every
pixel<->instant conversion already goes through `timeline.body.util` and vis
applies hidden ranges INSIDE those functions, so R-DP9's tolerance, 4B.23's time
mapping and the drag's pin stay exact with no second coordinate system. Only
spans where EVERY row is closed fold (hidden dates are an AXIS property). **A
FOLD HAS ZERO WIDTH, SO EVERY SEAM IS MARKED** — two bars either side of a folded
night would otherwise read as ADJACENT, a claim about the plant compression would
be inventing. LINEAR is the default and the toggle persists: verifying a calendar
claim is unanswerable on a folded ruler.

**THE GESTURAL DEBT IS PAID, AND ONE DEFECT WAS FOUND ON THE WAY (4B.28,
§5a.122).** **THE CHUNKED DRAG** was inert because `onPointerDown` tested the
item id against the ASSIGNMENT index and 4B.20 made a chunked bar's items PIECES
— so the gesture never started and vis's Hammer pan took the drag. Dragging any
piece now drags the OPERATION, the pieces travel as one, and the drop **DECLINES
VISIBLY** in a THIRD card register (not proven-impossible red, not failure alarm)
with **no "try again"**, checked from the row before any request. **THE ASK
PATH'S OWN COPY WAS CORRECTED IN THE SAME COMMIT** — it promised *"Dragging the
bar on the board runs the full re-solve, which can"*, which was never true — so
the two surfaces state ONE LIMIT (§5a.118(h) discharged). **R-DP9's TOLERANCE**
was `grid_px x pxToMinutes(1)` ≈ **240 minutes at the default 30-day view** and
is now a **FIXED 5 WORKING MINUTES** (`feel.snap.noop_tol_min`): jitter is a
property of the hand and does not scale with the zoom. A no-op SAYS SO. **THE JOB
PANEL** states every operation of the order from the board's OWN derivation (no
third computation of any quantity, 4B.21's discipline) and its two intent buttons
carry `op_seq` exactly — **§5a.118(c) discharged for board users**. **FOUND, NOT
BRIEFED:** `board.rebind` predated per-chunk rendering and `items.update` INSERTS
on an unknown id, so every accepted edit on a board with a split operation raised
a **PHANTOM MERGED BAR** over the pieces still there; one builder, one remover,
removal by prefix. Also fixed: `board.onSelect` held a SINGLE callback and
overwrote it, so a second subscriber would have silently unsubscribed the ask
panel's deictic scope.

**A GUARD THAT CALLS PAST THE BROKEN LINE PROVES NOTHING (4B.28, §5a.123).** Six
negative controls proven RED against physically reverted code. **A SEVENTH DID
NOT FIRE**: the chunked-drag control's first version drove `drag.grab(op)`
programmatically and stayed GREEN against the reverted defect, because the defect
lives in `onPointerDown`. Rewritten to drive a real pointer on a real chunk
piece, it went red. **The only way to find that out is to revert the fix and
look** — 4B.21 §5a.78's species from the other side.

**THE ASK PATH'S EIGHT, AND NOT ONE NEW INTENT (4B.27, §5a.112).** Ten measured
defects; **eight fixed, one did not reproduce, one NOT BUILT**. Parse prompt
**v14** widens three MEANINGS and adds nothing — `frozen` may be asked about ONE
ORDER, `late-order` also owns "tight", `gap-between` is selected by TWO NAMED
ORDERS — because in all three the route existed and the assembler could already
answer. **THE DELTA CARD CALLED TWO QUANTITIES "LATENESS"**: the total is net
plan tardiness **CLAMPED** (`Σ max(0,l_new)−max(0,l_old)`), the rows are a
**SIGNED** per-order lateness change, so *"no change to lateness"* beside
*"ORD-000040 +1440min"* was two true statements in one word — **and it is NOT
the floor/controllable split, because a move cannot change the floor at all**.
The bare driver phrase got 4B.21's remedy at its EIGHTH site. **THE SOLVE'S
TIMING WAS UNRECORDED, NOT UNREAD** — the rolling `solve_complete` never carried
it (the monolithic one always did) and the M6 RunContext closes in **1.4ms**
because it is the REPORTING context, so fixing the reader's field names alone
would have reported 0.0014s for a 400-second search; now two figures, never
fused (*"10 deterministic units … 416.9 seconds on this machine"*). **R-BK1's
PORTFOLIO IS REACHABLE FROM THE ASK PATH** (§5a.106(g) discharged) — the seam
was the dispatch's DOCUMENT ALLOW-LIST, **4B.21 §5a.78's mechanism a second
time**; live at K=3 it states all three ledgers and the 28.06% spread. **A
PROVED BOARD GETS A DIFFERENT SENTENCE** — the K=1 caveat's first version told
the pinned world another seed might find something cheaper, caught in this
session's own verification. **"TIGHT" IS THE BOARD'S BAND** (`latenessBand`,
−1440), **NOT the opener's at-risk set** — routing one to the other would have
been the fusion class committed while fixing it. **11 of 13 order-taking routes
DROP a second order** and the remedy is DISCLOSURE at one seam, not eleven
two-subject assemblers; PRESS-FAST/PRESS-SLOW survived because it comes from the
EVIDENCE, not the parse. **NOT FIXED (§5a.113):** item 1 (the later-direction
counterfactual) is NOT BUILT — the machinery exists (`local_price`) but on a
dense board a later drag is usually a REFUSAL, so the honest answer is dominated
by refusal branches; item 7 **DID NOT REPRODUCE** (4 probes, all correct) and
its requested keyword-shape remedy would have been a **deterministic
classifier**; the tray pre-emption still rewrites a two-order question (now
disclosed, not answered); the winner's wall (416.9s) EXCEEDS the portfolio's
(399s); Census A's MACHINE axis is unaddressed; `frozen` is rolling-only.

**Carried qualifications (open, owned):**

- Cloud deploy is verified **in-container**, not **in-cloud**: live `az deployment group
  create` from `deploy/azure/` + cloud smoke remain PARKED on the Azure trigger; the
  Bicep is still ARM-unvalidated (Session 2.4 carry, partially retired 2.4b).
- The `raw_data` path bypasses the M0 gate and has no WIP doorway — owned Phase-4 debt
  (RawAdapter retirement / pilot connector); the live gate-free entry points are named in
  docs/04's 4B.2c R-SC1 correction.
- Phase 3's **cold-stranger cold-drive** is MET-BY-PROXY only — a named Phase-4 entry
  condition, not relaxed.
- Daryn's feel-token export is not committed; the cockpit runs on `DEFAULT_FEEL`.
- Two remediation-catalog quality notes carry no resolvable IDS §-cite (quarantined) —
  a design-thread `note_version` fix.
- Pool service must become **slice-aware** before serving sliced-mode schedules.
- `test_n3000` is contention-sensitive (green alone).
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
  (a measurement session changes no test but its own). **4B.33 answered the shape
  question (§5a.135(d)) without fixing them: the deterministic-budget fix
  generalises to THIS member only — it needs the full determinism triple AND the
  wall lifted, a strictly larger fix — while the two SCREENSHOT members are
  render/timing races that a deterministic budget does nothing for.** A SIXTH
  member observed 4B.33:
  `test_accept_self_validation.py::test_negative_control_a_corrupted_plan_is_refused`
  failed once under concurrent load and is green on four consecutive quiet runs
  of its file and green at HEAD.
- Product naming is under GTM review — "MRE" is the working repo name, not a brand.

**Small carry-forwards (do not lose):**

- 4B.28 findings (docs/07 §5a.124 — REPORTED, deliberately NOT fixed; all
  nine in `docs/closeouts/4B.28.md` §7). The two a session should take next:
  **STANDING PINS DO NOT SURVIVE A SLICE ROLL** (above) and **THE FOLD SET IS
  PLANT-WIDE, NOT PER ROW** — only spans where EVERY machine is closed fold,
  which is the only honest choice under an axis-level mechanism, but on a plant
  with staggered shifts compression will quietly do far less than it appears to
  promise and **nothing on screen says so**. Also: the compression-tolerance
  guard proves INVARIANCE, not the demo-board MAGNITUDE (the rolling fixture
  spans ~5 days, so the control fired at 155.5 vs 175.0 minutes, not 240); the
  boundary snaps to the HOUR on an authored token nobody has tuned; the
  confirmation beat states the COUNT but does not NAME the orders (the plan
  carries them); a monolithic boundary move is untested in the BROWSER beyond
  "the handle is not offered"; the job panel's TRAY branch is unexercised live
  (`_derive_maps` keeps one work package per demand, so a part-placed order is
  not producible — 4B.22 B3); *"why is this bar held?"* with no subject still
  lands on CLARIFY `no-subject` (§5a.79's ladder, unchanged); and
  **`--calibrated` is a flag on a SPIKE SCRIPT, not a product path** — minting a
  board under its plant's accepted profile should not require knowing that
  naming K refuses the profile.
- 4B.29 findings (docs/07 §5a.111 — REPORTED, deliberately NOT fixed; all
  eight in `docs/closeouts/4B.29.md` §8). The two a session should take next:
  **THE PROFILE HAS NO EXPIRY** — R-CAL1 rule (3) speaks of an "expired"
  profile and nothing computes one; DRIFT only fires when a search actually
  FAILS, so a profile whose knee has quietly moved UP while still publishing K
  boards is stale and SILENT. An age threshold is a declared coefficient nobody
  has: R-PD1 clause (5)'s shape again. **TWO SYNTHETIC WORLDS SHARE ONE PLANT
  KEY** — `demo_board` and the 170-order control both declare `F001` /
  `SyntheticERP vGen`, so rule (4) keys them identically and one profile would
  overwrite the other in a shared data root. Correct for REAL plants (one
  facility, one calibration, re-measured); a hazard for our measurement worlds,
  worked around here with separate directories rather than fixed in the
  generator. Also: **the AUDIT's K is NOT calibrated** (`AUDIT_K` is a constant
  3 at 3.0 units — a profile calibrates the MAIN solve and says nothing about
  the button a planner presses on purpose); **a MONOLITHIC solve carries no
  calibration block at all** (the block is on the rolling path only, so rule
  (3)'s absence-is-stated guarantee is simply not in force there and nothing
  says so); the ceremony is a CLI and nothing else (no Gatehouse surface, no
  scheduling, no cloud); neither profile was `--save`d into the WORKING data
  root; every wall in both profiles is one laptop and the mid170 arm ran beside
  the test suite; and **every publishable cell in both grids is FEASIBLE**, so
  "10 units is better than 6" means cheaper, never closer to optimal
  (4B.26 §6(g)'s caveat, unchanged).
- 4B.22a findings (docs/07 §5a.86-88 — REPORTED, deliberately NOT fixed; all
  eight in `docs/closeouts/4B.22a.md` §7). The two a session should take next:
  **`order-schedule` DOES NOT VOICE THE PAST-DUE DISPOSITION** (R-PD1 clause 6) —
  *"where is ORD-000040"* returns a four-line itinerary for an order due
  **2025-12-15**, 21 days before the plan begins, finishing **34.8 days late**
  with **$20,860** of tardiness of which **$12,000 is floor**, every fact already
  in the document's own service outcome. **THE CONCENTRATION BAND CANNOT FIRE AT
  ANY DENSITY** — `_opener_load` divides by the machine's WHOLE RESOLVED CALENDAR
  (28,080 min against a plan occupying ~25 days), so the busiest lane on a
  386-bar board reads **39.7%** against `SATURATED = 0.85` and the 50% pre-filter
  drops it first; **4B.20's denominator class at a FIFTH site**, and 4B.16's
  "unexercised at demo density" is REFUTED as the explanation. Also:
  `what-would-change` offered a start of **2025-12-22** on a board whose origin is
  2026-01-05 (a past-due order's upstream floor is its old release date); **beat
  one says "this placement isn't possible here" from `status: UNKNOWN`** and beat
  two then prices the same pin at $2,596.67 (the 2s first-feasible budget was
  enough at 40 orders, not at 386); a dense board **chunks FEWER** operations than
  an empty one (1 vs 2) and **forcing more destroys the solve** (splittable weight
  1 -> 4 turns a FEASIBLE 386-bar board into UNKNOWN at both windows — measured,
  rejected, knob kept); the gate raises *"CUT-01 is in a workload too dense to
  schedule cleanly"* as a DATA-QUALITY finding; the at-risk band has ONE member.
- 4B.22 findings (docs/07 §5a.83 — REPORTED, deliberately NOT fixed):
  **THE RECORD BEHIND THE `why-on-machine` LEAD ANSWERS A DIFFERENT QUESTION** —
  the lead is about WHICH MACHINE (eligibility, "no alternative to weigh") and
  the cited decision's driver is about WHEN (occupancy, "the machine was busy
  with other work"). Both true of the same record; the drill-down now shows a
  planner both, one line apart. The **"recorded driver:"** label makes the
  sentence claim only what is checkable, but whether the chain should carry the
  eligibility decision instead — or both, with their questions named — is a
  `why-on-machine` assembler question 4B.22 did not open.
  **`"how do i fix that"` AFTER A WHOLE-BOARD READ** lands on CLARIFY
  `no-subject` (parse: `remediation` at 0.72). Honest, and measured for the
  first time. The BOARD is the subject and the ladder has no rung for it —
  §5a.79's shape on the other axis.
  **THE B1 FIGURE PRINTS RAW MINUTES** beside its percentage, deliberately: two
  capacity quantities in one sentence are comparable only in one unit (§5a.76's
  reason).
- 4B.21 findings (docs/07 §5a.75-78 — REPORTED, deliberately NOT fixed):
  **TWO DISPOSITION QUESTIONS ARE CLAIMED BY ROUTES THAT DO NOT ANSWER THEM** —
  *"are the fourteen orders with no placement a problem I should act on"* goes
  to `coarse-fit`, and *"what does it mean that work is beyond the horizon"* to
  `coaching`, which replies *"I don't recognize which capability you mean"* and
  lists nine submission fields. Both vocabulary calls. (The third of the three,
  `excluded-orders` answering *"no data-quality problems"* to *"why are some
  orders missing from the schedule entirely"*, WAS fixed.)
  **DRILL-DOWN ANAPHORA — FIXED 4B.22 (§5a.79).** It was: *"show me the evidence
  for that"* after a contracted answer returned *"I don't have a claim of my own
  open to ground"*, because `SynthesisMemory` remembers synthesis answers ONLY.
  **THREE PROSE SITES STILL PRINT RAW MINUTES** (the challenge route, the swap
  take, `rolling_questions`' lateness clause) — left because R-PD1 clause (4)
  states the floor and the controllable part in the SAME unit for comparability.
  **THE `deaf` RIDER FIRES WHEN SIX QUESTIONS ARE ASKED IN ONE SESSION** and two
  legitimately share a route — visible in this session's own verification run.
  §5a.58's boundary, unchanged.
- 4B.20 findings (docs/07 §5a.68-70 — REPORTED, deliberately NOT fixed):
  **THE `machine-schedule` ROUTE ANSWERS "how busy" WITH AN ENUMERATION —
  FIXED 4B.22 (§5a.80)**, from the one definition it now shares with the
  toolbox, and refusing the judgment for want of a declared threshold.
  **`rolling_horizon`'s `busy_minutes` METRIC NAME is under-specified** against
  the new ruling — the arithmetic is correct (it intersects with the open
  windows), and renaming an evidence Metric is a vocabulary-class change.
  **`schedule_csv`'s `duration_min` COLUMN does not say which quantity it is** —
  harmless today because the row IS a chunk, so summing the column gives working
  time. **4B.17's A3 SPECIMEN NO LONGER REACHES TIER TWO** — *"would splitting
  the jobs help"* now parses to `what-would-change` or to synthesis with zero
  tool calls, so re-measuring A3 needs a phrasing that still lands there or it
  measures the parse. The declared/placed **1,500 vs 1,501** difference on
  ORD-000011 op10 is chunk-boundary rounding, labelled correctly on both sides,
  and was not investigated.
- 4B.17 findings beyond the five truth failures (docs/07 §5a.54-62 — REPORTED,
  deliberately NOT fixed): **THE `repeat`/`deaf` BOUNDARY IS KEYED ON STRING
  IDENTITY** (§5a.58) — the same string twice gets the correct lead; the same
  QUESTION reworded gets self-doubt plus the full recitation, so the C(c)
  terseness specimen never fires. Two firings, zero true positives — §5a.42's
  score on the other side of its own split. **§5a.51's "off board selection"
  CLAIM DOES NOT REPRODUCE** (§5a.59): `"how do i change that"` with only a
  selection parses `unmatched` at all six runs. **THE COACHING INVITATION CANNOT
  DECLINE TO FIRE, BY SHAPE** (§5a.61) — `slots=()`, so
  `invitation_line()` can never withhold it; it routes a planner to a null
  answer. **THE CARD ROUTE ANSWERS FIVE QUESTIONS WITH ONE BYTE-IDENTICAL
  RECITAL** (RUBRIC entry 10's question, answered by six runs: it is a recital).
  **THE BINDING-FAMILY CENSUS IS EMPTY HERE AND NOT DERIVABLE FROM THE DOCUMENT**
  (§5a.62): contract 1.11 carries calendars and chunks but not splittability
  (1.12), nor precedence/release for COMMITTED work.
  **`dark-evidence` FIRES ON A PREMISE CORRECTION**, 2 per run — the sidecar
  signal predates the guard, and a correction cites nothing because there is
  nothing to cite. **THE r5 CARD SPECIMEN IS UNEXERCISABLE**: 4B.7 made
  `reopt_delta_abs` 0.00 by construction, so move == total and "which half"
  cannot discriminate — reported, never counted as a pass.
- 4B.16 findings (docs/07 §5a.49-50 — REPORTED, deliberately NOT fixed):
  **THE OPENER CANNOT STATE THE CERTIFICATE GRADE** — it is a submission fact
  the API joins on `/meta` and the schedule document does not carry it, so the
  one word a stranger recognizes is the one the item cannot say. Same seam
  `RECON_GATEHOUSE.txt` Q1 names from the other side.
  **CONCENTRATION IS UNEXERCISED LIVE** — demo density is far below the 85%
  threshold, so it fired on neither measured board and is proven only by unit
  test (the §5a.11 limit again).
  **BOTH ROUTES ARE NOW MEASURED AGAINST A LIVE PARSE (4B.16a Item 2 — the
  "blocked on the key" claim here was the rumour):** 9 of 10 planner phrasings
  reach the intended route on the pinned world. The one that does not is
  `"why can't it be earlier"` -> **`why-here` at 0.95 with `polarity=negative`**,
  which is a genuine route-boundary question (the counterfactual is why-here's
  INVERSE over the same bounds) and NOT fixed — a vocabulary call. Subjectless
  `"how do i fix that"` after a BRIEFING lands on CLARIFY `no-subject`: honest,
  and the contrast with the same follow-up after a `why-here` (which resolves
  from selection) is the finding.
- 4B.15 findings (docs/07 §5a.39-45 — REPORTED, deliberately NOT fixed):
  **THE SYNTHESIS TOOLBOX CANNOT READ A DECLARED FIELD** — measured as Sonnet's
  single bench failure: the parse sent a field question to tier two, which
  honestly reported that per-operation submission data "is not something the
  placement, cost, or lateness tools expose". It is right. The fix is a third
  tool wrapping `attribute_lookup`; left undone because the tool surface is a
  governed artifact this session already changed twice.
  **THE DEAFNESS RIDER FIRES WHEN THE ONE ANSWER IS CORRECT** (three phrasings
  of one question) — humble rather than wrong, but distinguishing "one answer
  because I am confused" from "one answer because it IS the answer" needs a
  signal this session does not have.
  **CLAUDE.md IS OVER ITS 40k CEILING AND STILL GROWING** — 47k before 4B.15, 53k before 4B.16, 57k before 4B.17, 62k before 4B.20, 65k before 4B.21, 70k before 4B.22, 74k after it, ~78k after 4B.22a, 81k after 4B.23, 85k after 4B.24, ~88k after 4B.25, ~92k after 4B.26, ~96k after 4B.29, ~102k after 4B.27, **~110k after 4B.28**. Compression was out of scope for every one of them; it is the largest single item owed at the next phase exit, and the status section is what shrinks first.
  **THE docs/05 TOPIC MAP'S ORDER IS LOAD-BEARING** and mis-ordered once here: a
  day-shift restriction answered as C1/C2 "proven end to end" when the item is
  C4 (model-proven, §8 doorway). Caught and pinned; the class stands.
  **THE CORPUS EXCLUDES 15 FOUNDING `D-nn` DECISIONS** for having no date — the
  fail-closed side, named so a future session can rule on dating them instead.
- 4B.14 findings (docs/07 §5a.34-38 — REPORTED, deliberately NOT fixed):
  **A `chose` VERDICT ON A SPLITTABLE OPERATION IS A LOWER BOUND** — setup is a
  separate R-C3 phase and the fit scan treats working minutes as one divisible
  quantity, so the copy claims only what is computed ("there was open, unheld
  time from T") and never "the solver could have placed it there".
  **THE RUNNER-UP CAN BE A STALE TRUE FACT** — the renderer suppresses it when
  the binding family's near-miss window is more recent, which is a heuristic
  about relevance, not a proof. **`start-reason` WAS NOT RETIRED**; whether it
  and `why-here` should merge is a vocabulary question 4B.14 did not rule on.
  **CLAUDE.md is 45k against its 40k phase-exit ceiling** (43k before this
  session) — the status section is what shrinks first.
- 4B.12 findings (docs/07 §5a.31-32 — REPORTED, deliberately NOT fixed):
  **THE TARDINESS SPLIT NEEDS A THIRD CATEGORY** — at F006's 134.9% utilisation
  "controllable" (15.3M of a 16.9M ledger) means not-already-accrued, NOT
  discretionary; the missing member is `capacity_infeasible` and it is unbuilt for
  R-PD1 clause (5)'s reason — computing it means solving a relaxation and asserting
  its bound as a business fact (§5a.31(g)). **THE a=2 CLIFF IS BRACKETED, NOT
  PINNED** (between 50 and 100 ops/machine; those cells cost 25-30 min each), and
  **F006 at a=2 is UNMEASURABLE under this repo's own wall rule** — four of five
  F004 a=2 rows already truncate at 1984-2787 s on a plant a third the size.
  **PER-FACILITY PARTITIONING is the named conditional follow-up** (the 4B.10
  partition ruling's corollary): CP-SAT's LNS improvement workers live in the
  parallel portfolio the determinism rule disables, which is why a hint cannot
  substitute for them — partitioning buys parallelism without losing
  reproducibility.
- 4B.11 findings (docs/07 §5a.28-30 — REPORTED, deliberately NOT fixed):
  **R-PD1 clause (5) is OPEN** — no age-vs-lateness finding, because the threshold is
  a declared IDS coefficient that does not exist and inventing one authors a business
  fact we do not have; the full pipeline-proof chain is written out in docs/06 §5.9
  (§5a.28). **No optimality ROUTE** — the proof is rendered and voiced but nobody can
  ASK for it; a new intent is a vocabulary-class change (§5a.29).
  **`facility_real`'s CONDITIONAL grade is a GENERATOR truthfulness defect** and
  4B.10's claim that it was correct is CORRECTED — the generator writes
  `created_date = ref` for every order, so a past-due order is emitted with an
  inverted date pair. NOT fixed: that inversion is the only live
  M0-`proceeded_flagged` specimen keeping R-PD1 clause (3)'s guard non-vacuous, so
  whoever fixes it must supply the guard a new specimen in the same commit (§5a.30).
- `OperationSpec.yield_factor` still carries false `observed` provenance (flagged
  2026-07-12, not fixed).
- Sentinel / repeated-identical-value detector (Rep 3's 40× `run_rate_seconds=60.0`).
- Provenance spot-check guard: sampled `observed` values must appear in the cited source.
- W1 scenarios unbuilt: `dwell_heavy`, `calendar_chaos`, `multi_facility_balance`.
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
- 4B.7 findings: **§5a.19 and §5a.21 are DISCHARGED by 4B.8** (the budget is derived,
  the status line reports the cost proof). **STILL OPEN — §5a.20:**
  `EARLINESS_PREFERENCE` names a mechanism that no longer exists; the DriverCode member
  survives while the extractor no longer emits it (4B.8 CU4 made it dormant, interim
  only). Correcting it is a **vocabulary-class change** reaching planner_language /
  explainer / renderers / four AI-voice tests / the exam bank.
  **§5a.22 is DISCHARGED by 4B.17** — recalibrated (from the committed fixture, no
  fresh world needed: the exam target was verified byte-identical to
  `rolling-c362baa4-1b0`), run six times and graded. See the status section.
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
- **§5a.7 IS CLOSED — IT WAS A RUMOUR FOR THREE SESSIONS. THE KEY WORKS; DO NOT
  SCOPE OFF A KEY BLOCKER** (4B.16a). The sweep was NEVER blocked (own loader
  since 4A.5b); pytest was, for one session, fixed 4B.8 (four slow tests pass,
  re-verified 54.7s); `python -m mre.ask` / `mre.ai_exam` had NO loader, which is
  what kept it alive — fixed. **`src/mre/env_local.py` is the ONE reader**; a
  second is a red test (negative control proven). Nothing in the library loads a
  file, correctly — in a container the key comes from the platform secret store,
  so each ENTRY POINT populates the env. `regression_founder_r5` was unrun because
  its expectations were UNCALIBRATED (§5a.22), not for a key — **4B.17 ran it**.
- 4B.6a debts (docs/07 §5a.9, .11): **§5a.9 is DISCHARGED by 4B.7** — the ~7.9%-dearer incumbent is gone, the board
  now sits at the proven optimum 16,481.95 / tardiness 0.00; `rolling_coarse_hot/` binds by
  DECLARED derate 0.10, a contrivance for screenshot coverage, not a discharge of the
  demo-density limit.
- 4B.5 debts: the two-solve BASELINE is not extended to FORCED-ALTERNATIVES pricing
  (same economics, separate audit); the causal vacuity tripwire counts a quantity
  as a DIGIT only, and a driver phrase alone clears it (the founder's own specimen is
  fixed at the assembler, not by the tripwire); CU4(b)'s viewport guard is a standing
  invariant the harness cannot make fail.
- R-AI5 residue: start-reason's early-vs-plain read is still the assembler's (only a
  NEGATIVE polarity is authoritative from the parse); a CLARIFY turn carries no
  subject forward.
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

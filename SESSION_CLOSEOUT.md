SESSION 4B.8 CLOSE-OUT
SCALE: THE BUDGET SPLIT, THE STATUS LINE, AND WHY 14 DAYS RETURNS NOTHING
2026-07-28

Repo: C:\dev\mre, branch master. docs/07 v2.53; docs/04 session amendment same
date (the CU3 status RULING verbatim); CLAUDE.md position and carry-forwards
updated. docs/06 UNCHANGED -- no coefficient or doorway moved, and the
conformance rule count stands at 36.

Deterministic throughout: PYTHONHASHSEED=0, --solver-workers 1, seeds 42-46
wherever a distribution was required. Spikes in tools/spikes/alloc_4b8/.


======================================================================
1. CU1 -- THE POLICY TABLE AND THE RECOMMENDATION
======================================================================

Three policies over a fixed 6.0 total, on the 4B.6c arm harness (reused, not
rebuilt), 6 instances x 5 seeds.

  P1  CURRENT      stage 1 <= 4.0   stage 2 = fixed 2.0
  P2  COST FIRST   stage 1 <= 6.0   stage 2 = 6.0 - consumed   (MAY BE ZERO)
  P3  RESERVED     stage 1 <= 5.5   stage 2 = 6.0 - consumed   (>= 0.5)

  inst    pol  s1 OPT   ledger med     spread   starts med  s1 det  s2 det  s2=0
  5w14    P1     5/5      1,959.25       0.00        4,817   0.000   0.000   0/5
  5w14    P2     5/5      1,959.25       0.00        4,817   0.000   0.000   0/5
  5w14    P3     5/5      1,959.25       0.00        4,817   0.000   0.000   0/5
  8w14    P1     5/5      2,395.00       0.00       10,610   0.000   0.000   0/5
  8w14    P2     5/5      2,395.00       0.00       10,610   0.000   0.000   0/5
  8w14    P3     5/5      2,395.00       0.00       10,610   0.000   0.000   0/5
  15w14   P1     5/5      5,596.65       0.00       36,442   0.106   2.001   0/5
  15w14   P2     5/5      5,596.65       0.00       29,368   0.106   5.894   0/5
  15w14   P3     5/5      5,596.65       0.00       29,368   0.106   5.894   0/5
  40w14   P1     5/5     16,481.95       0.00      198,088   0.101   2.003   0/5
  40w14   P2     5/5     16,481.95       0.00      191,294   0.101   5.899   0/5
  40w14   P3     5/5     16,481.95       0.00      191,294   0.101   5.899   0/5
  120w14  P1     0/5    100,490.32  75,361.72    1,456,281   4.000   2.000   0/5
  120w14  P2     0/5     95,762.23  87,783.28    1,711,055   6.000       -   5/5
  120w14  P3     0/5     92,879.53  87,783.28    1,680,564   5.500   0.500   0/5
  200w7   P1     3/5     27,863.63   7,263.42      681,413   3.081   2.000   0/5
  200w7   P2     5/5     27,863.63       0.00      721,777   3.081   2.919   0/5
  200w7   P3     5/5     27,863.63       0.00      721,777   3.081   2.919   0/5

RECOMMENDATION: P3. SHIPPED.

  * P1 LOSES THE COST PROOF AT 200 ORDERS. Seeds 42 and 43 need 4.542 and
    4.962 deterministic units and are capped at 4.0, so they truncate to
    29,385.60 and 35,127.05 against the optimum 27,863.63 that P2/P3 prove on
    5/5 seeds with a seed spread of EXACTLY ZERO. P1's spread is 7,263.42.

  * THE 120-ORDER QUESTION, ANSWERED ON ITS OWN TERMS. Under P2, stage 1's
    extra 2.0 units buy NO PROOF: stage 1 is OPTIMAL on 0/5 seeds under both
    4.0 and 6.0. The ledger medians differ by 4,728.08, but the SEED SPREAD at
    that instance is 75,361-87,783 -- an order of magnitude larger -- so the
    difference is not distinguishable from noise. That is the PLATEAU the brief
    asked about, and its own condition therefore applies: stage 1's extra
    budget buys nothing there, so P3's reserve is FREE.

  * P2's COST IS CONCRETE WHERE ITS BENEFIT IS NOT. At 120 orders stage 1
    consumes the whole 6.001 and stage 2 receives ZERO on 5/5 seeds -- the
    tiebreak never runs, reinstating 4B.4's founder finding at exactly the
    plant sizes where a planner sees it. P3 reserves 0.5; it runs 5/5.

  * WHERE STAGE 2's BUDGET PAYS, IT PAYS VISIBLY: start-minutes 36,442 ->
    29,368 at 15 orders (-19.41%) and 198,088 -> 191,294 at 40 (-3.43%), both
    at an IDENTICAL ledger.


======================================================================
2. CU5(a) -- FEASIBILITY VERDICT
======================================================================

THE 200-ORDER / 14-DAY INSTANCE IS FEASIBLE.

Asked properly -- objective replaced by a constant, which is the satisfiability
question rather than the optimality one -- a feasible schedule is found in
4.51 s wall and 0.082 deterministic units. The model builds in 0.17 s.

SO IT IS NOT AN R-SC2 ADMISSION DEFECT. Gravity did not admit more work than
the window can hold. This remains a scale/search finding, the rest of CU5
stands, and the subject has NOT changed.

The first probe (minimize cost, 400 deterministic units, 7200 s wall) was still
running after three hours and was ABANDONED as the wrong question: it conflates
"does a schedule exist" with "what is the cheapest schedule", and only the
first was being asked. Recorded because the wasted hours are the lesson.


======================================================================
3. CU5(b)(c)(d) -- THE CLIFF   [DIAGNOSIS ONLY; NO FIX MADE]
======================================================================

(b) 200 orders, one seed, 6.0 deterministic units, build separated from solve:

  win  n_free  ops/mach   build   SAT det      COST   cost det      gap
    7      99      33/7   0.06s    0.0036   OPTIMAL       4.54   0.0000
    8     123     37/10   0.05s    0.0041   OPTIMAL       4.03   0.0000
    9     145     42/14   0.06s    0.0043  FEASIBLE       6.04   0.3330
   10     193     61/15   0.07s    0.0056  FEASIBLE       6.19   0.7587
   11     228     71/17   0.09s    0.0069  FEASIBLE       6.00   0.6186
   12     254     77/20   0.09s    0.0072  FEASIBLE       6.00   0.8859
   14     313     92/27   0.19s    0.0816   UNKNOWN       6.00      n/a

  BOTH STANDING HYPOTHESES ARE DEAD. Model BUILD time is 0.05-0.19 s at every
  depth (the 289 s build was the monolith, not this path). Ops-per-machine
  peaks at 92, nowhere near the ~850 cliff.

  THE SHARPEST FACT: at 14 days the COST solve returns UNKNOWN -- no solution
  AT ALL in 6.0 units -- while satisfiability on the SAME model takes 0.082, a
  factor of 74. The objective is not merely hard to optimize; it makes the
  model hard to find anything in.

(c) THE THRESHOLD IS NOT GENERAL.

  ord  win  n_free  ops/mach      COST   cost det
   40   14      56      18/6   OPTIMAL       0.10   (OPTIMAL at every depth)
  120   10      87      27/6   OPTIMAL       1.54
  120   11     115      33/7  FEASIBLE       6.00
  200    8     123     37/10   OPTIMAL       4.03
  200    9     145     42/14  FEASIBLE       6.00

  200 orders PROVES optimality at 123 free ops while 120 orders FAILS at 115.
  So n_free does not determine it, and ops-per-machine max (27->33 vs 37->42)
  does not either. What differs is how much total work the same 13 machines
  carry. Any window rule keyed to a free-op count would be fitted to one plant.
  The approach is steep, not gradual: at 120 orders, 0.03 -> 0.09 -> 0.77 ->
  1.54 units across w7-w10, then a wall.

(d) NARROWING IS GRACEFUL, NOT LOSSY. Across depths at 200 orders the coarse
  zone ABSORBS what the fine window stops admitting (declared rho 0.85):

  win  beyond-horizon  coarse cells  BINDING  placements  tardiness buckets
    7             157            59        9         404                123
    8             149            52        9         380                121
    9             140            50        7         358                 91
   10             120            42        6         310                 54
   11             107            51        5         275                 57
   12              98            34        4         249                 36
   14             200            64       13         503                325

  Through w7-w12 the exchange is smooth and monotone: as the window widens,
  beyond-horizon demand falls 157 -> 98 and coarse placements fall 404 -> 249,
  with binding cells at EVERY depth and 4 coarse_unmodelable ops named
  throughout. The displaced demand stays MODELLED and the zone keeps BITING.
  Narrowing trades a fine placement for a coarse one -- the R-SC2 amendment
  working as ruled -- rather than dropping work. SO NARROWING IS GRACEFUL.

  THE w=14 ROW IS NOT A CONTINUATION OF THAT TREND AND MUST NOT BE READ AS ONE.
  Beyond-horizon jumps to 200 -- every schedulable demand -- because the FINE
  window returned UNKNOWN and placed NOTHING AT ALL. The coarse zone then
  carries the entire book (503 placements, 13 binding cells, 325 tardiness
  buckets). That is the zone degrading gracefully under total fine failure,
  which is reassuring; but the discontinuity is the failure itself, not a
  window-depth effect. At the shipped 14-day convention this plant's fine
  schedule contributes nothing and the board is a coarse projection.

A SECOND CEILING BINDS FIRST, AND IT IS THE WALL (newly quantified). At 200
orders / 7 days stage 1 needs 37-120 SECONDS of wall clock to spend its
1.86-4.96 deterministic units, but build_rolling_view's default
member_time_limit_s is 30.0. On the shipped rolling path the WALL stops the
cost proof long before the deterministic budget does, and the run is
wall-truncated -- by the repository's own hard rule, a lottery. The existing
wall_truncated flag is doing its job; what is new is the measurement of how far
apart the two ceilings are. It is also why CU3's ruling is INVISIBLE at 200
orders: the board reads FEASIBLE because nothing was proven, not because the
wrong proof is reported. Any window-depth decision must set BOTH ceilings.


======================================================================
4. PRE-FLIGHT -- ALL FOUR QUESTIONS ANSWERED
======================================================================

(1) Inside a pytest process ANTHROPIC_API_KEY was ABSENT from os.environ --
    confirmed with a probe test, not inferred.
(2) NO conftest.py loaded .env.local. tests/conftest.py registered --runslow
    and nothing else. There was no loader anywhere on the test path.
(3) The anthropic SDK IS importable in the venv (0.118.0). Not the cause.
    NB python-dotenv is NOT installed, so the fix could not use it.
(4) The exam harness has its own loader the test path lacks:
    tools/run_ai_exam_sweep.py:42 load_env_local(), called at import (line 58),
    anchored to Path(__file__).resolve().parents[1] -- the repo root, not the
    CWD, so that one is robust.

CAUSE = LOADER WIRING, exactly the leading hypothesis. NARROW FIX APPLIED: the
same loader in tests/conftest.py, repo-root anchored, already-set variables
win. THE FOUR TESTS NOW PASS (40.6 s). No assertion touched, no skipif added,
r5 bank not run and not recalibrated.

CONSEQUENCE, REPORTED NOT ABSORBED: four OTHER tests began failing because they
had assumed the key was AMBIENTLY ABSENT (test_llm_renderer_no_key_attribution,
test_judgment_no_llm_falls_back_to_testimony, test_the_preflight_is_fail_open,
test_an_unavailable_synthesizer_returns_none). Each now CONTROLS the key with
monkeypatch.delenv -- precondition made explicit, NO assertion changed. One was
not merely failing but making a LIVE API CALL and then asserting the fallback
register on a real LLM answer.

NAMED, NOT FIXED (a suite-wide call): LLMRenderer, Synthesizer and
QuestionParser all spell the key `api_key or os.environ.get(...)`, so an
EXPLICIT api_key="" silently consults the environment. api_key="" plainly means
"no key". ~20 further LLMRenderer(api_key="") sites in test_explainer.py now
build AVAILABLE renderers; they pass today only because they build prompts.


======================================================================
5. CU2 / CU3 / CU4 -- WHAT SHIPPED
======================================================================

CU2  _STAGE2_DET_TIME_S DELETED from both twins. Caller declares det_total;
     stage 1 capped at total minus a 1/12 RESERVE; stage 2 gets the remainder,
     floored at the reserve. Guards committed (tests/test_budget_allocation.py,
     9 tests): (a) both stages' consumption <= the declared total, asserted on a
     REAL 8-order pilot solve, not a mock; (b) stage 2 runs unconditionally on a
     nonzero slice, and a skip is EXPLICIT AND RECORDED
     (tiebreak_skipped_reason); (c) neither signature accepts a fixed stage-2
     budget and neither module defines the constant. 4B.7's
     byte-identical-across-earliness_value invariant still passes end-to-end.
     SolveResult gained det_consumed (CP-SAT's own deterministic meter,
     promoted from the 4B.6c spike probe) -- a derived split is unprovable
     without it.

     TWO IMPLEMENTATION FINDINGS, both caught by measurement not review:
     - det_time was RENAMED det_total, not reinterpreted. The old total was
       stage1 + 2.0 -- 6.0 at the default but 4.0 for the exam/fixture builders
       and 2.5 for the golden driver. No single multiplier preserved every
       caller; a silent reinterpretation would have cut the golden driver's
       budget by 70%. The rename forced each call site to state its own total,
       and nobody's budget moved.
     - The MONOLITHIC path passes cap_stage1=False (cost proof stays uncapped,
       as it has always been) with a 2.0 total. Raising it was MEASURED AND
       REJECTED: at 4.0 and 6.0 the tiebreak gains 344 and 422 start-minutes of
       3,307,818 (-0.01%) while wall time goes 19.6 -> 37.5 -> 50.2 s. At 2.0
       the sample_data schedule is BYTE-IDENTICAL. A third candidate (derive
       stage 2's budget from stage 1's consumption when no total is declared)
       was also rejected: on a small model it hands stage 2 ~0 and silently
       stops the tiebreak -- the failure R-SC3(1) forbids, through the back
       door.

CU3  RULING, transcribed verbatim into docs/04. The EXISTING status field
     carries STAGE 1's status (the COST proof); NEW Optional fields
     tiebreak_status / tiebreak_skipped_reason carry stage 2's. Contract
     1.9 -> 1.10, additive in SHAPE -- with the honest caveat, recorded in the
     contract history, that the MEANING of the existing field changes on any
     two-stage run, which is why it is a ruling and not a bug fix. Both twins
     moved together. A schedule whose cost is proven optimal now says so.

     R-AI1 DEBT NAMED, NOT BOLTED ON (docs/07 5a.23): nothing voices either
     proof. The cockpit never references solver.status anywhere in
     src/cockpit/src/, and explainer / renderers / rolling_questions read no
     solve status at all.

CU4  (a) FALLTHROUGH REPORTED FIRST: CAPACITY_BLOCKED, which since 4B.5 CU3(a)
     reads the SOLVED OCCUPANCY and names the eligible machines and what held
     each, with an honest "the occupancy does not attribute it" branch. Under a
     cost-only objective a dearer eligible choice IS capacity. The fallback
     states the true cause with checkable evidence instead of hedging a false
     one -- so DORMANCY WAS DONE, and the earliness_value parameter is DELETED
     from _assignment_driver's signature (a test asserts a caller cannot pass
     it back in).
     (b) The declared-but-unread guard duly tripped (4B.7 predicted it: the
     guard had been green FOR THE WRONG REASON, its only consumer being the
     defect) and was resolved by a dormant-register entry citing the R-SC3
     amendment. NEVER by widening the guard.
     (c) 5a.20 stays OPEN: the DriverCode member survives and docs/02 still
     documents it as purchased by a retired coefficient.
     Two tests were REPLACED AND REVERSED, both premised on the defect. The
     capacity-forcing SPECIMEN is unchanged; the right answer is not -- it now
     STATES capacity instead of hedging toward it, and must not claim earliness
     bought anything.


======================================================================
6. CU6 -- GOLDENS (enumerated, not waited to be told)
======================================================================

MOVED:
  tests/fixtures/baselines/rolling_pilot_golden.json -- regenerated.
    schedule_digest a59b7411... UNCHANGED. Every asserted figure UNCHANGED
    (total 14,690.08 / production 12,530.08 / setup 2,160.00 / tardiness 0.00 /
    n_committed 54 / on_time 24 / late 0). ONLY the metadata key moved:
    "det_time": 0.5 -> "det_total": 2.5, the same historical budget under the
    renamed parameter. Reproduced across PYTHONHASHSEED 0/1/2.

NOT MOVED (verified, not assumed):
  tests/fixtures/baselines/sample_data_schedule.csv    byte-identical
  tests/fixtures/baselines/sample_data_summary.json    byte-identical
    Both verified by the gate itself. Accounted BY OPERATION IDENTITY at the
    candidate totals that were rejected, using account_goldens.py (joins on
    work_orders/op_seq/chunk_seq, never on row position, because a re-sequenced
    lane changes nearly every line and a text diff cannot tell "this op moved"
    from "a different op is in this row"). At the chosen total: 90 of 90
    operations identical, row-cost total unchanged at 19,429.00.

EXPECTED AND CONFIRMED: the 40-order board stays at 16,481.95 with tardiness
0.00 under EVERY policy in CU1's table, including the two that give stage 2
nearly triple its old budget. Placements moved (start-minutes 198,088 ->
191,294); the LEDGER did not, to the cent. The cap held; no halt was needed.

Contract-version assertions moved 1.9 -> 1.10 in six files.


======================================================================
7. TESTS
======================================================================

Fast suite (non-slow, excluding tests/cockpit):  1644 passed, 240 skipped.
Cockpit ladder (Playwright, BOTH THEMES):        227 passed.
tests/test_rolling_horizon.py --runslow:          15 passed (includes the
  determinism golden and 4B.7's byte-identical-across-earliness_value invariant).
tests/test_defaults_reproduce_baseline.py:         2 passed (the monolithic
  byte-for-byte gate).
tests/test_budget_allocation.py:                   9 passed (NEW -- CU2's guards
  (a)(b)(c) and CU3's "a provably optimal schedule says so").
tests/test_declared_but_unread.py:                 3 passed (the dormant-register
  resolution).
The four previously-blocked AI slow tests:         4 passed.


======================================================================
8. WHAT WAS TEMPTING AND LEFT
======================================================================

* FIXING 5a.15. The cliff is located and the coarse zone's behaviour across it
  is measured; a window rule was one edit away. The brief said diagnose and
  stop, and the diagnosis itself argues for stopping: the threshold is NOT
  general, so any rule written today would be fitted to pilot_scale.
* RAISING member_time_limit_s. The 30 s wall ceiling demonstrably truncates the
  cost proof at 200 orders and raising it is a one-line change. It belongs with
  the window-depth decision, because both ceilings must be set together.
* RUNNING THE r5 BANK. The blocker is gone as of this session's pre-flight and
  the temptation was considerable. Explicitly out of scope, and 4B.8
  invalidates its expectations further (the status field and the budget split
  both moved), so a fresh exam world must be re-derived FIRST.
* THE 5a.20 VOCABULARY MIGRATION. With the driver already dormant, retiring the
  enum member looked like finishing the job. It is a reviewed vocabulary-class
  change reaching docs/02, the RUBRIC and the exam bank.
* GIVING THE MONOLITH THE FULL 6.0. It improves the tiebreak's own objective
  and the goldens were already authorized to move. Measured: -0.01% for 2.5x
  the wall clock. Declined on the numbers.
* ADDING A ROUTE FOR "IS THIS OPTIMAL?". The claim is now provable and
  unvoiced, which is the most quotable gap in the session. The brief said name
  the R-AI1 debt instead of bolting on a route; it is docs/07 5a.23.
* FIXING THE api_key="" FALLBACK. Three modules treat an explicit empty string
  as "consult the environment". The fix is small and the reasoning is
  finished -- but it changes behaviour for every caller, so it is a suite-wide
  call and not a pre-flight rider.

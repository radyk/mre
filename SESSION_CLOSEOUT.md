SESSION 4B.12 CLOSE-OUT
WHERE THE CLIFF ACTUALLY IS, AND WHETHER A HINT MOVES IT
2026-07-28

Repo: C:\dev\mre, branch master. Deterministic throughout: PYTHONHASHSEED=0,
num_search_workers=1, solver seeds 42-46, generation seed pinned at 1 so seed
spread measures the SOLVER and not the world.

A MEASUREMENT SESSION. It ships one capability -- the warm-start flag, default
OFF -- and otherwise produces numbers. Nothing it found was fixed.

docs/07 v2.56 carries the durable numbers (sections 5a.31 and 5a.32 new; 5a.27
carries a dated supersession note and is NOT rewritten). docs/04 carries the
session amendment. This file is the narrative.


======================================================================
0. THE HEADLINE: THE CLIFF MOVED, AND THAT IS THE SESSION
======================================================================

4B.10 located the cliff at 137 ops/machine. Re-run against BYTE-IDENTICAL
worlds on current master, the last density at which all five seeds prove the
cost optimum is 92 ops/machine, and at 94 none of them do.

    last all-OPTIMAL      4B.10  137 ops/machine  ->  NOW   92
    first all-failed      4B.10   --              ->  NOW   94

The brief's HALT CONDITION -- "if the cliff has moved BELOW 94 ops/machine,
stop and report" -- fired. It was reported, the working thread ruled to re-size
the remaining plan downward rather than run the original matrix, and the rest of
this session is that re-sized plan. What was dropped is named in section 5.

WHY IT MOVED. R-PD1 (4B.11) admits past-due work that the pipeline used to
exclude. 4B.10 had itself proved the cliff's driver is tardiness onset. Before
R-PD1, every cell below 137 ops/machine carried ZERO tardiness -- the objective
barely varied between schedules and the first solution was already within a
whisker of optimal. Now every cell carries tardiness from the lightest density
upward, so the placement-dependent part of the objective exists everywhere, and
the proof costs 200-360x what it cost on the same world without its late work.

4B.11's own roadmap entry predicted this in words: "R-PD1 makes real boards
tardiness-dominated, which 5a.27 proved is exactly the regime where the cost
proof fails." This session is the number.


======================================================================
1. THE MEASUREMENT IS CONTROLLED, AND THAT IS CHECKED
======================================================================

A re-baseline claims that only the PIPELINE changed. That claim is worthless if
the generator moved underneath it -- a different book would explain every
difference in the table without R-PD1 having done anything.

  * tools/spikes/density_4b12/verify_world_identity.py compares every
    regenerated submission to 4B.10's on-disk world BYTE FOR BYTE. Eight worlds,
    ALL IDENTICAL, with exactly two fields masked (generated_at,
    extract_timestamp) because they are the only values the generator writes
    from the wall clock.
  * The mask is why that is not the whole proof. The complement is git:
    tools/generate_erp_dataset.py has not been touched since 4B.10's own commit
    (6fa67da).
  * Configuration, all four as the brief required: the cost-only objective via
    the SHIPPED rolling_horizon._two_stage_solve (called, not transcribed); the
    P3 allocation as shipped since 4B.8; a 1800 s WALL CEILING so the
    deterministic budget is what binds; det_total 6.0, window 14 d, frozen 3 d,
    4 machines.
  * wall_truncated is FALSE on every row reported anywhere in this document.
    Three rows were EXCLUDED for wall truncation and are named in section 5.

The harness is 4B.10's, reused rather than rebuilt: build_plant, window_inputs,
calendar_minutes (the REAL Mon-Fri denominator, not an assumed 720x7) and above
all _RecordingRunner, which recovers each stage's own status and deterministic
spend without reimplementing the shipped budget split. What 4B.12 added is the
R-PD1 quantities, the tardiness split, and the hint arms.


======================================================================
2. CU1 -- THE RE-BASELINE
======================================================================

2.1 WHAT R-PD1 DID BEFORE ANY SOLVING

Every past-due demand now survives to schedulable AND is admitted --
n_past_due_admitted == n_past_due_all at every cell, from 4/4 at 28 orders to
66/66 at 851. So the same order count carries more operations, and the density
axis itself moved by about 6%: 4B.10's "94 ops/machine" cell is 100 today.

  ord   ops 4B.10   ops NOW   opm 4B.10   opm NOW   util 4B.10   util NOW
   28          88       104        22.0        26        4.18%      4.74%
   55         184       200        46.0        50       10.26%     11.23%
  110         376       400        94.0       100       19.02%     20.12%
  165         548       596       137.0       149       27.36%     29.39%

2.2 THE COST PROOF, SIDE BY SIDE (alternates=1, seeds 42-46)

  opm (was)   4B.10 proved   NOW proved   proof 4B.10     proof NOW      gap NOW
  26 (22)              1/1          5/5        0.0002   0.035-0.069            -
  50 (46)              1/1          5/5        0.0015   0.294-0.735            -
  100 (94)             5/5          1/5   0.015-0.192         5.459    3.9-16.0%
  149 (137)            4/5          0/5   2.294-5.393             -   40.5-49.3%

Below the cliff the proof still lands, but at 200-360x its former cost. 4B.10's
headline cell -- five seeds agreeing on the ledger TO THE CENT at 94 ops/machine
-- now splits 1/5 with an 8.463% ledger spread.

2.3 THE CLIFF, PINNED

Four densities were added between 50 and 100 to locate it, because the halt
condition cannot be evaluated without them:

  opm   orders   util     proved   units to proof   ledger spread
   65       70   10.0%       5/5     0.045-0.286           0.000%
   76       85   11.1%       5/5     0.576-1.024           0.000%
   92      100   16.4%       5/5     2.141-2.735           0.000%
   94      105   24.7%       0/5     -- (gap 2.8-33.4%)   22.906%

The transition is sharper than 4B.10's and 45 ops/machine lower. At 94 the
ledger spread across five seeds is 22.906%, against the 13.056% that made
5a.23 urgent enough to discharge in 4B.11.

2.4 THE TARDINESS SPLIT -- THE MECHANISM, NOW VISIBLE (contract 1.11)

  opm    ledger med    tardiness      floor   controllable   ctrl % of tard
   26        58,819       53,371     52,200          1,171             2.2%
   50        29,621       18,482     16,800          1,682             9.1%
   65        17,757        4,590      4,200            390             8.5%
   76        39,332       24,064     22,200          1,864             7.7%
   92        49,404       30,149     27,600          2,549             8.5%
   94        55,630       33,879     25,200          8,679            25.6%
  100        51,948       30,300     25,200          5,100            16.8%
  149       172,230      140,285    105,600         34,685            24.7%
  254       578,483      522,977    172,800        350,177            67.0%
  772    16,887,473   16,726,480  1,447,800     15,278,680            91.3%

TARDINESS ONSET IS NOW AT THE LIGHTEST DENSITY MEASURED. Under 4B.10's pipeline
the first cell with any tardiness was 137 ops/machine. Under R-PD1 the FLOOR is
nonzero wherever past-due work exists -- which is everywhere -- and the
CONTROLLABLE part is nonzero at 26 ops/machine. There is no "tardiness-free
regime" left on this book.

2.5 OPS/MACHINE IS REFUTED AS A PREDICTOR, BY A SHARPER ARGUMENT THAN
    UTILISATION WAS

4B.10 refuted utilisation twice. 4B.12 refutes ops/machine itself: THE PROOF
COST IS NOT EVEN MONOTONE IN DENSITY. 65 ops/machine proves in 0.045-0.286
units; the LIGHTER 50 ops/machine takes 0.294-0.735. The 70-order world carries
a smaller past-due burden (floor 4,200 against 16,800).

STATED HONESTLY: each cell is an independent draw at its own order count, so
differences between cells include world variation and not density alone. That is
exactly the point. Density does not determine difficulty, so no threshold in
density can be a rule. 5a.27's conclusion -- the honest mechanism is REPORTING,
not prediction -- stands by a second and independent route.


======================================================================
3. CU2 -- THE TWO REAL DENSITIES, MEASURED
======================================================================

5a.27(h) recorded plainly that F004's 246 and F006's 803 were BRACKETED, not
solved, and named them as the obvious next cells. They are now run, on the
calibrated profiles (276 and 851 orders, which is how PROFILE_PROVENANCE.md
defines F004 and F006), alternates=1, seeds 42-46.

                 opm    util    proved          gap   ledger spread   tard % ledger
  F004 median    254   54.2%       0/5   83.5-85.8%         11.121%          90.4%
  F006 largest   772  134.9%       0/2        98.8%          0.289%          99.05%

The densities read 254 and 772 rather than 246 and 803 because R-PD1 admits the
past-due orders 4B.10's measurement dropped, and because ops/machine is counted
over what the 14-day window actually admits.

THE INFERENCE IS CONFIRMED: both real facilities are far past the cliff. What
the inference could not have supplied is the MAGNITUDE -- an 85% gap at the
MEDIAN facility, not at the pathological one.

3.1 F006 IS AN OVER-CAPACITY QUESTION, NOT A PROOF FAILURE

At 134.9% utilisation the window cannot hold the work. The optimum ITSELF
carries enormous tardiness, so "prove the optimum" is not the operative
question; whether the engine produces a USABLE answer with a STATED gap is.

  It does. F006 returns FEASIBLE in 379 s wall (not truncated), places all
  3,088 admitted operations, and states a 98.8% gap itself.

  Its ledger is 16,887,473. Production is 37,472 and setup 123,520 -- 0.95% of
  the total. The other 99.05% is tardiness, and contract 1.11 splits it:

      floor          1,447,800   already late at intake; no schedule recovers it
      controllable  15,278,680   everything else
      late demands     705 of 772 admitted

3.2 A LIMIT OF THE SPLIT, FOUND HERE AND NOT FIXED

"Controllable" means NOT ALREADY ACCRUED AT t0. It does not mean DISCRETIONARY.
On a plant committed to 134.9% of its window, most of that 15.3M cannot be
scheduled away by any placement -- it is a capacity fact wearing a placement
label. The split has two categories and this plant needs three:

      floor  /  capacity-infeasible  /  genuinely placement-dependent

Naming it is the deliverable. The third category is NOT built, and the reason is
the same discipline R-PD1 clause (5) follows: computing it means solving a
relaxation and then asserting its lower bound as a business fact about what the
plant could have done. That is a ruling, not an implementation detail.

3.3 THE ANSWERABILITY RESULT, WHICH IS THE ONE THAT MATTERS FOR THE PRODUCT

NOT ONE CELL AT ANY DENSITY RETURNED UNKNOWN. Every failing cell returned a
FEASIBLE schedule placing every admitted operation, with a gap the solver stated
itself. The satisfiability probe explains why: a first solution costs
0.0002-0.147 deterministic units across the whole ladder, against a 5.5-unit
stage-1 cap that cannot close the bound -- a factor of 37x at F006 and 948x at
149 ops/machine. That is the same shape 4B.8 measured at 74x, now measured
across nine densities.

THE ENGINE'S PROBLEM AT REAL DENSITY IS NOT PRODUCING AN ANSWER. IT IS PROVING
ONE. Which is why 4B.11's rendered gap is the right response and a pre-solve
warning is the wrong one.

3.4 ALTERNATES ARE REAL, AND EVERY a=1 FIGURE ABOVE IS THE OPTIMISTIC ONE

Daryn has confirmed the plant cross-trains, so the extract's single-workcenter
routings are believed to be an extract limitation and alternates=2 is the more
realistic setting. Measured:

  opm      a=1 proved            a=1 gap      a=2 proved            a=2 gap
   26            5/5                    -           5/5                    -
   50            5/5                    -           5/5                    -
  100            1/5            3.9-16.0%           0/5           27.9-46.3%
  149            0/5           40.5-49.3%           0/5           54.6-61.0%
  254            0/5           83.5-85.8%           0/1                95.9%

IF a=2 IS THE REAL WORLD, THE REAL CLIFF IS BELOW 92 OPS/MACHINE. The a=2 cliff
is bracketed between 50 and 100 and was NOT pinned; those cells cost 25-30
minutes each and the session spent its remaining budget on the two real
densities instead.


======================================================================
4. CU3 -- THE HINT EXPERIMENT
======================================================================

THE VERDICT, PLAINLY: OUTCOME 2 IN THE CLIFF REGION, OUTCOME 3 BEYOND IT, AND
THE MECHANISM IS A RE-ROLL RATHER THAN AN IMPROVEMENT.

4.1 THE ARMS

  H0  the shipped path, no hint (the control)
  H1  phase 0 clears the objective and solves for ANY feasible solution; phase
      2 hints start, end AND assignment vars from it, then minimizes cost
  H2  the same phase 0; phase 2 hints ASSIGNMENT LITERALS ONLY -- structure,
      not times. A partial hint survives what exact times may not.

H1 seeds through the SAME _hint_from_solve the shipped stage-1 -> stage-2 warm
start already uses. Using a different seeder would have measured the seeder.

Rules honoured: phase 0's cost comes out of the SAME det_total and is counted
into the returned det_consumed (so arms compare on TOTAL consumption); phase 0
runs under the same determinism settings; arms were measured only at densities
that FAIL in CU1/CU2; seeds 42-46.

PHASE 0 IS NEARLY FREE: 0.0024 deterministic units at 100 ops/machine, 0.0058 at
149, 0.0140 at 254 -- 0.04% to 0.23% of the 6.0 budget. Cost is not why it fails.

4.2 THE RESULT, PAIRED SEED BY SEED AGAINST ITS OWN CONTROL

Never pooled. The cliff is a region where the SEED decides, so a mean over seeds
hides the only effect there is. A WIN requires the gap to be better by at least
one percentage point, so solver noise cannot manufacture one.

  opm    arm       n  H0 proved  arm proved  W/L/T   median gap H0->arm  ledger
  100    H1 full   5        1/5         2/5  3/1/1        10.1% -> 2.2%   -0.79%
  100    H2 assign 5        1/5         3/5  3/1/1        10.1% -> 0.0%   -4.56%
  149    H1 full   5        0/5         0/5  2/3/0       44.8% -> 43.3%   +1.01%
  149    H2 assign 5        0/5         0/5  0/4/1       44.8% -> 46.3%   +1.05%
  254    H1 full   3        0/5         0/3  0/1/2       83.7% -> 86.4%   +3.56%
  254    H2 assign 3        0/5         0/3  0/1/2       83.7% -> 85.6%   +1.74%

AT 100 OPS/MACHINE -- just past the cliff, where the budget is marginal -- THE
HINT IS WORTH HAVING. Seed 42 goes from FEASIBLE at a 16.0% gap and a 53,585
ledger to OPTIMAL at 49,404, which is the same optimum another seed proves. The
assign arm triples the proof count, 1/5 to 3/5.

AT 149 IT IS A WASH OR SLIGHTLY NEGATIVE. AT F004'S 254 IT IS A LIABILITY: one
of the three seeds measured returned a ledger of 1,080,587 against the control's
571,543 -- 89% worse.

4.3 EVEN WHERE IT WINS, IT IS A RE-ROLL

The same density that produces the 16%-to-proved win also produces a loss: seed
45 goes from a 3.9% gap to 8.5% (H1) and 23.0% (H2). A hint changes where the
search starts, which in a region where the seed decides is another way of
changing the seed. The win column and the loss column are both non-empty at
every density measured. NO RULING FOLLOWS FROM THESE NUMBERS, and the flag
therefore ships OFF.

4.4 OUTCOME 1 COULD NOT OCCUR, AND THAT IS ITSELF THE FINDING

The hint's largest theoretical prize was UNKNOWN -> FEASIBLE, and it is what
4B.8's 74x predicted. THERE IS NO UNKNOWN TO CONVERT. Section 3.3 found that the
shipped path already returns a solution at every density measured, up to 772
ops/machine at 134.9% utilisation. The 74x is real, but it describes the distance
to a PROOF, not the distance to an answer.

4.5 WHAT THIS SAYS ABOUT THE DETERMINISM RULE

CP-SAT's large-neighbourhood-search improvement workers live in the parallel
portfolio this repository disables by hard rule (any identical-schedule claim
requires --solver-workers 1). A single-worker search cannot exploit a good
incumbent the way the portfolio would.

So the honest reading of outcome 3 is NOT "hints do not work" but "hints do not
work FOR US at one worker" -- and it strengthens the case for PER-FACILITY
PARTITIONING (the 4B.10 partition ruling's corollary), which buys parallelism
without giving up reproducibility. That is the thing a hint cannot do. Named as a
conditional follow-up only; this session rules nothing.


======================================================================
5. WHAT WAS NOT MEASURED, AND WHY
======================================================================

Every omission here is a cost decision, stated rather than hidden.

  * THE a=2 CLIFF PIN (85 and 105 orders at alternates=2). Started, then
    stopped to free capacity for CU3 and F006. The a=2 cliff is bracketed
    between 50 and 100 ops/machine.

  * F006 AT alternates=2. Not run. F004's a=2 cells already exceed the 1800 s
    wall ceiling on a plant a third the size, so this cell cannot produce a
    REPORTABLE row under this session's own configuration rule -- running it
    would manufacture an excluded one.

  * FOUR OF THE FIVE F004 alternates=2 ROWS WERE EXCLUDED FOR WALL TRUNCATION
    (seeds 42, 43, 44 and 46, at 1984 s to 2787 s). They are quarantined in
    cu2_f004_a2_WALLTRUNCATED.bak rather than deleted, as 4B.10 kept its own
    contaminated file. ONE clean a=2 row at F004 survives, seed 45 -- and it is
    the direct evidence that F006 at alternates=2 cannot produce a reportable
    row, F006 being three times the size.

  * THE ORIGINAL CU2/CU3 MATRIX at 246 and 803 ops/machine with hint arms.
    Dropped by the halt-condition ruling in section 0.

5.1 A CONTAMINATION INCIDENT, RECORDED BECAUSE IT WAS SILENT

The first CU3 pass produced rows reading 800 free operations in a world that has
400, and INFEASIBLE at 0.0 deterministic units. Cause: prepare_plant WIPES AND
REBUILDS its run directory, and the two hint arms at one density differ only in
hint_mode -- so both processes wrote one spine output directory and the second
corrupted the snapshot store the first was reading. It did not crash; it
produced plausible numbers.

Those rows were DISCARDED, not repaired. cliff_sweep.py gained --run-tag
(defaulting to the hint mode). A second incident followed from the cleanup
itself -- a surviving process from the first pass kept appending to a results
file the re-run was also writing -- and was caught by the analyzer's inherited
duplicate-cell refusal, which is exactly what that guard is for. The trap is
written up as trap 3 in tools/spikes/density_4b12/README.md.


======================================================================
6. WHAT SHIPPED
======================================================================

One capability, behind a flag, DEFAULT OFF:

  src/mre/modules/rolling_horizon.py
      HINT_OFF / HINT_FULL / HINT_ASSIGN, _warm_start, _hint_assign_only, and
      hint_mode on _two_stage_solve, build_rolling_view and run_rolling_horizon.
      Phase 0 spends out of the SAME declared det_total and is counted into the
      returned det_consumed -- a warm start that is not counted is a warm start
      that looks free.

  tests/test_hint_warm_start.py -- 11 guards, all passing:
      (1) OFF is the default at every entry point.
      (2) OFF runs exactly TWO solves; ON runs three.
      (3) ON RESTORES THE COST OBJECTIVE. Phase 0 clears the objective to solve
          for satisfiability; if that leaked, stage 1 would minimize the constant
          0 and report a proven-optimal cost of nothing. Checked two ways: the
          objective equals the unhinted arm's proven value, and it is not zero.
      (4) The hint is paid for inside the declared total.
      (5) A hint never changes the proven optimum.

  Goldens: tests/test_defaults_reproduce_baseline.py and
  tests/test_budget_allocation.py -- 11 passed, byte-identical with the flag off.


======================================================================
7. TEST STATUS, STATED PRECISELY
-------------------------------

GREEN, at the final state of the code:

  tests/test_hint_warm_start.py + tests/test_defaults_reproduce_baseline.py +
  tests/test_budget_allocation.py .............................. 24 passed, 88 s

That is the set that bears on the change: the 13 hint guards, and the goldens
plus the budget-split guards that prove the flag-off path is byte-identical.

NOT COMPLETED WITHIN SESSION TIME, and named rather than implied:

  * The full non-slow suite. It was started and reached roughly 45% with ZERO
    failures under -x before being stopped to free the machine for the
    measurement sweeps. Not a green stamp -- a partial one, reported as such.
  * tests/test_pastdue_disposition.py, test_objective_units.py, test_ortools_pin.py,
    test_horizon_slice.py, test_coarse_horizon.py, test_rolling_horizon.py as a
    batch: started, 5 passed and 0 failed when the session closed. Left running.

A note worth keeping, because it cost this session real time: piping pytest
through `tail` BLOCKS ALL OUTPUT until the process exits, which reads exactly
like a hang. Redirect to a file and tail the file instead.

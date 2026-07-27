SESSION 4B.6c CLOSE-OUT -- MEASUREMENT: DOES THE ZERO-COST TIEBREAK COST US?
A measurement session. Its product is this table, not a capability.
2026-07-27

Repo: C:\dev\mre, branch master. No shipped objective changed, no ruling
amended, no golden or fixture moved, no module in src/ touched. ONE test
committed (item 4 authorized it); everything else is measurement.

All solver work ran deterministic: PYTHONHASHSEED=0, one worker, with the wall
ceiling (1800 s) kept far above the DETERMINISTIC budget so the deterministic
budget is what binds. Solver seed was a DELIBERATE REPLICATE VARIABLE.

THE VERDICT, PLAINLY: YES, B COSTS US. Candidate B degrades CP-SAT's search
badly at every scale where the cost-only solve can prove optimality, and the
hour-granularity variant does not rescue it above 15 orders. The seed spread
that justifies this answer is in section 2.


======================================================================
0. THE SETUP (what was actually run)
======================================================================

INSTANCE = ONE WINDOW-0 SOLVE of a pilot_scale plant -- a faithful
transcription of rolling_horizon.build_rolling_view's solve, with the
OBJECTIVE as the only thing that varies between arms. Same spine (gate ->
adapter -> validator -> planner), same gravity admission, same window model
build, same ">= t0" floor, same Extractor pass producing the ledger. One code
path; only the objective swapped.

DEPTHS = the standing rolling convention, window 14 days / frozen 3 days
(tools/build_rolling_exam_run.py), reference date 2026-01-05.

EXCEPTION, and a finding in its own right: at 200 orders the 14-day window
admits 313 free operations and returns UNKNOWN -- NO FEASIBLE SOLUTION AT ALL
-- on the cost-only arm, at 6.0 deterministic units (3 seeds; wall 144 / 195 /
229 s) AND at 20.0 units (1 seed; wall 509 s). The instance yields no ledger
on any arm, so it is EXCLUDED and named here. The third instance is therefore
200 orders at a 7-DAY window, which solves to proven optimality.

ARMS (five; A2h and A2x are the item-2 diagnostics):

  A0   cost only            minimize sum(terms)                        1 solve
  A1   status quo           stage 1 sum(terms) + 5*sum(S)              2 solves
                            stage 2 cap + minimize sum(S)
  A2   candidate B          BIG*sum(terms) + sum(S),
                            BIG = n_free*start_range + 1               1 solve
  A2h  candidate B, hourly  BIGh*sum(terms) + sum(H), H = S // 60      1 solve
  A2x  candidate B, 10x BIG                                            1 solve

S = the free-op start vars. A2h encodes H by LINEAR EQUALITY --
S == 60*H + R with R in [0,59] -- not add_division_equality.

BUDGET = 6.0 DETERMINISTIC UNITS, IDENTICAL ON EVERY ARM AND EVERY SEED. A1
splits it exactly as shipped (4.0 stage 1 + 2.0 stage 2, the shipped det_time
and _STAGE2_DET_TIME_S); the single-solve arms take all 6.0 at once.

151 RUNS TOTAL: 148 comparable runs, all of which produced a ledger, plus the 3
excluded 200-order/14-day probes below. ZERO wall-truncated across all 151 --
nothing was excluded on that ground.

REPLICATES = solver seeds 42, 43, 44, 45, 46. Each run is individually
deterministic; the seed is varied on purpose to give a distribution rather
than a point.


======================================================================
1. THE THREE-ARM TABLE (the product)
======================================================================

Ledger total cost is THE comparison. Raw objective values are in different
units per arm and are never compared across arms.

instance      arm    n  OPT   ledger median         min           max        spread   tardiness med   sum starts med   det med
---------------------------------------------------------------------------------------------------------------------------
5o  w14/f3    A0     5   5         1,959.25    1,959.25      1,959.25          0.00            0.00            6,570      0.00
5o  w14/f3    A1     5   5         1,970.65    1,970.65      1,970.65          0.00            0.00            4,589      0.00
5o  w14/f3    A2     5   5         1,959.25    1,959.25      1,959.25          0.00            0.00            4,817      0.00
5o  w14/f3    A2h    5   5         1,959.25    1,959.25      1,959.25          0.00            0.00            4,817      0.00
5o  w14/f3    A2x    5   5         1,959.25    1,959.25      1,959.25          0.00            0.00            4,817      0.00
---------------------------------------------------------------------------------------------------------------------------
8o  w14/f3    A0     5   5         2,395.00    2,395.00      2,395.00          0.00            0.00           10,610      0.00
8o  w14/f3    A1     5   5         2,411.05    2,411.05      2,411.05          0.00            0.00            7,730      0.00
8o  w14/f3    A2     5   5         2,395.00    2,395.00      2,395.00          0.00            0.00           10,610      0.00
8o  w14/f3    A2h    5   5         2,395.00    2,395.00      2,395.00          0.00            0.00           10,610      0.00
8o  w14/f3    A2x    5   5         2,395.00    2,395.00      2,395.00          0.00            0.00           10,610      0.00
---------------------------------------------------------------------------------------------------------------------------
15o w14/f3    A0     5   5         5,596.65    5,596.65      5,596.65          0.00            0.00           70,329      0.11
15o w14/f3    A1     5   0         5,860.05    5,856.82      5,863.27          6.45            0.00           18,127      6.00
15o w14/f3    A2     5   0        81,396.65    5,596.65     83,996.65     78,400.00       75,800.00           69,743      6.00
15o w14/f3    A2h    5   5         5,596.65    5,596.65      5,596.65          0.00            0.00           29,454      0.35
15o w14/f3    A2x    5   0        81,396.65    5,596.65     83,996.65     78,400.00       75,800.00           69,743      6.00
---------------------------------------------------------------------------------------------------------------------------
40o w14/f3    A0     5   5        16,481.95   16,481.95     16,481.95          0.00            0.00          363,638      0.10
40o w14/f3    A1     5   0        28,547.38   26,373.88     28,846.43      2,472.55       11,975.83          196,183      6.00
40o w14/f3    A2     5   0        27,858.20   27,682.37     27,858.62        176.25       11,376.25          209,197      6.00
40o w14/f3    A2h    5   0        24,893.62   16,481.95     25,892.88      9,410.93        8,411.67          388,137      6.00
40o w14/f3    A2x    5   0        27,858.20   27,682.37     27,858.62        176.25       11,376.25          209,197      6.00
---------------------------------------------------------------------------------------------------------------------------
120o w14/f3   A0     5   0        95,762.23   63,549.10    151,332.38     87,783.28       48,477.92        1,711,055      6.00
120o w14/f3   A1     5   0       189,232.52   94,197.87    204,260.88    110,063.02      142,646.25        2,367,408      6.00
120o w14/f3   A2     5   0       102,878.65   82,618.85    165,403.45     82,784.60       55,953.75        1,998,240      6.00
120o w14/f3   A2h    5   0       197,689.37  122,591.97    286,191.57    163,599.60      150,943.75        2,275,558      6.00
120o w14/f3   A2x    3   0       152,550.53   82,618.85    165,403.45     82,784.60      105,754.17        1,998,240      6.00
---------------------------------------------------------------------------------------------------------------------------
200o w7/f3    A0     5   5        27,863.63   27,863.63     27,863.63          0.00            0.00        1,078,745      3.08
200o w7/f3    A1     5   0        35,406.90   35,406.90     35,406.90          0.00        7,127.92          653,237      6.00
200o w7/f3    A2     5   0        38,870.63   32,818.63     41,778.63      8,960.00       10,965.00        1,168,950      6.00
200o w7/f3    A2h    5   0        33,292.80   33,292.80     33,292.80          0.00        5,429.17        1,148,513      6.00
200o w7/f3    A2x    5   0        39,177.38   32,818.63     41,778.63      8,960.00       11,313.75        1,161,497      6.05
---------------------------------------------------------------------------------------------------------------------------
200o w14/f3   A0     3   0       EXCLUDED -- UNKNOWN on every seed; no ledger on any arm (see section 0)

n = runs, OPT = how many reached OPTIMAL. Generated tables:
tools/spikes/tiebreak_4b6c/TABLE.txt (arms) and TABLE_C.txt (compressor).
Raw rows: arm_results.jsonl (151 runs = 148 comparable + 3 excluded),
compressor_results.jsonl (28 rows, each carrying both C variants = 56 runs).

A2x carries 3 seeds at 120 orders, not 5 -- a deliberate cut to bound solver
time. Its per-seed values at seeds 42/43/44 are IDENTICAL to A2's at the same
seeds, which is exactly what the sensitivity arm is for (section 3b).


======================================================================
2. THE THREE READINGS, STATED AS CONCLUSIONS
======================================================================

READING ONE -- A2 vs A0 ON LEDGER COST. B DEGRADES THE SEARCH.
--------------------------------------------------------------
The claim under test was that A2 and A0 are the same within A0's own
seed-to-seed spread. They are not.

  instance     A0 median   A0 seed spread    A2 median       delta    beyond A0 spread?
  5o            1,959.25            0.00     1,959.25      +0.00%     no (both proven OPTIMAL)
  8o            2,395.00            0.00     2,395.00      +0.00%     no (both proven OPTIMAL)
  15o           5,596.65            0.00    81,396.65   +1354.38%     YES
  40o          16,481.95            0.00    27,858.20     +69.02%     YES
  120o         95,762.23       87,783.28   102,878.65      +7.43%     no (delta 7,116 < spread 87,783)
  200o w7      27,863.63            0.00    38,870.63     +39.50%     YES

On three of the four instances where the cost-only arm proves optimality,
A2's median ledger is worse by 39% to 1354% against a seed spread of EXACTLY
ZERO. THE FINDING IS NEGATIVE. B is not rescued, and no attempt was made to
rescue it.

READING TWO -- A2 vs A0 ON SUM OF STARTS. NOT EVEN RELIABLY BETTER.
-------------------------------------------------------------------
B must be strictly better here, or the tiebreak is priced air in reverse.

  instance   A0 sum starts   A2 sum starts     A2 wins
  5o                 6,570           4,817     +26.68%
  8o                10,610          10,610      +0.00%   (nothing available to win)
  15o               70,329          69,743      +0.83%
  40o              363,638         209,197     +42.47%
  120o           1,711,055       1,998,240     -16.78%   WORSE
  200o w7        1,078,745       1,168,950      -8.36%   WORSE

At the two largest instances B is WORSE than cost-only on the very quantity it
exists to minimize, because it never gets near its own optimum inside the
budget. So B is not "costs money, buys earliness". At pilot volume it is
"costs money, buys nothing".

READING THREE -- A1 vs A0 ON LEDGER COST. THE STATUS QUO'S DAMAGE.
------------------------------------------------------------------
As a percentage of ledger total, across instances rather than on the fixture
alone:

  instance      A0 median     A1 median     A1 costs
  5o             1,959.25      1,970.65       +0.58%
  8o             2,395.00      2,411.05       +0.67%
  15o            5,596.65      5,860.05       +4.71%
  40o           16,481.95     28,547.38      +73.20%
  120o          95,762.23    189,232.52      +97.61%
  200o w7       27,863.63     35,406.90      +27.07%

At 5 and 8 orders A1 PROVES OPTIMAL and the +0.58% / +0.67% is the declared
earliness price honestly paid for a 27-30% start reduction -- R-SC3(2) working
exactly as ruled. From 15 orders up A1 stops proving optimality and the number
stops being a price. At 40 and 120 orders the status quo's ledger is +73% and
+98% against a proven (or better-bounded) cost-only optimum, and nearly all of
the delta is TARDINESS -- 11,975.83 of the 12,065.43 at 40 orders.

This confirms docs/07 section 5a.12 and extends it: the mislabelled reopt half
is not a fixture artifact. It is the shape of the status quo everywhere above
about 15 orders.


======================================================================
3. CORRECTNESS CHECK -- NO DEFECT
======================================================================

Where BOTH A0 and a candidate prove OPTIMAL, B's construction requires
IDENTICAL ledger cost. Every such case in the sweep:

   5o w14   A0 1,959.25 (5/5 OPT)  vs  A2  1,959.25 (5/5 OPT)   OK
   5o w14   A0 1,959.25 (5/5 OPT)  vs  A2h 1,959.25 (5/5 OPT)   OK
   5o w14   A0 1,959.25 (5/5 OPT)  vs  A2x 1,959.25 (5/5 OPT)   OK
   8o w14   A0 2,395.00 (5/5 OPT)  vs  A2  2,395.00 (5/5 OPT)   OK
   8o w14   A0 2,395.00 (5/5 OPT)  vs  A2h 2,395.00 (5/5 OPT)   OK
   8o w14   A0 2,395.00 (5/5 OPT)  vs  A2x 2,395.00 (5/5 OPT)   OK
  15o w14   A0 5,596.65 (5/5 OPT)  vs  A2h 5,596.65 (5/5 OPT)   OK

NO DEFECT. BIG is large enough, nothing overflows, no cost term sits outside
cost_expr. B's argmin IS cost-optimal by construction; it is the SEARCH that
fails, not the encoding. A2 proves OPTIMAL nowhere above 8 orders, so no
A0-vs-A2 optimal comparison exists at 15 orders or beyond -- and that absence
IS the reading-one result.


======================================================================
4. ITEM 2 -- IS BIG THE PROBLEM? NO.
======================================================================

(a) MAGNITUDES AND int64 HEADROOM, NUMERICALLY
----------------------------------------------
|obj| max is an EXACT upper bound computed from the objective proto itself:
sum over terms of |coeff| * max(|lb|,|ub|). int64 max is
9,223,372,036,854,775,807.

  instance  arm   n_free  start_range          BIG               |obj| max         int64 headroom
  5o        A2         6      162,491      974,947      19,896,670,603,041              463,564x
  5o        A2h        6      162,491       16,255         331,731,243,504           27,803,748x
  5o        A2x        6      162,491    9,749,470     198,966,697,260,891               46,356x
  15o       A2        21      152,639    3,205,420     858,135,050,191,774               10,748x
  15o       A2h       21      152,639       53,425      14,302,607,788,274              644,873x
  15o       A2x       21      152,639   32,054,200   8,581,350,473,102,134                1,075x
  40o       A2        56      161,279    9,031,625   2,194,009,607,481,366                4,204x
  40o       A2h       56      161,279      150,529      36,567,292,398,256              252,230x
  40o       A2x       56      161,279   90,316,250  21,940,095,993,639,366                  420x
  200o w7   A2        99      168,439   16,675,462   8,913,924,925,325,124                1,035x
  200o w7   A2h       99      168,439      277,993     148,602,103,604,192               62,068x
  200o w7   A2x       99      168,439  166,754,620  89,139,249,103,362,324                  103x
  120o      A2       184      168,479   31,000,137  28,367,138,968,863,305                  325x
  120o      A2h      184      168,479      516,673     472,789,355,494,714               19,508x
  120o      A2x      184      168,479  310,001,370 283,671,389,409,951,587                   33x

Minimal-BIG A2 keeps at least a 325x margin everywhere measured. A2x (10x BIG)
is down to 33x at 120 orders, and the 200-order/14-day window would carry
n_free = 313 and BIG = 52,733,928 -- roughly a further 3x -- so a 10x BIG at
full pilot volume sits within about one order of magnitude of the int64
ceiling. Named. Not a blocker for the minimal encoding.

(b) BIG SENSITIVITY -- DEGRADATION DOES NOT SCALE WITH BIG
----------------------------------------------------------
A2x is A2 with a 10x coefficient. Per-seed:

  * 5, 8, 15 and 40 orders: IDENTICAL TO THE CENT -- same ledger, same
    sum-of-starts, same deterministic time consumed.
  * 120 orders, seeds 42/43/44: IDENTICAL TO THE CENT (165,403.45 /
    152,550.53 / 82,618.85 on both arms). A2x's differing MEDIAN in the table
    is purely the 3-vs-5 seed count, not a BIG effect.
  * 200 orders w7: results differ per seed, but medians are 38,870.63 (A2) vs
    39,177.38 (A2x) -- a 0.79% gap inside an 8,960.00 seed spread.

CONCLUSION: coefficient magnitude is NOT the mechanism. A 10x weakening of the
LP relaxation changes nothing measurable.

(c) A2h -- THE GRANULARITY VARIANT. A REAL EFFECT THAT DOES NOT SCALE.
----------------------------------------------------------------------
At 15 orders A2h is the session's one genuinely surprising result:

  15 orders   A0   OPTIMAL   ledger 5,596.65             starts 70,329   det 0.11
              A2   FEASIBLE  ledger 81,396.65 (+1354%)   starts 69,743   det 6.00
              A2h  OPTIMAL   ledger 5,596.65 (+0.00%)    starts 29,454   det 0.35
              A1   FEASIBLE  ledger 5,860.05 (+4.71%)    starts 18,127   det 6.00

A2h matches A0's ledger EXACTLY, proves optimality on all five seeds in 0.35
deterministic units, and takes 58.12% off the sum of starts. A2 at minute
granularity blows up on the same instance. That is a real effect from a ~60x
reduction in BIG, and it is recorded.

IT DOES NOT SURVIVE SCALE. From 40 orders up A2h degrades like A2:

  instance     A2h vs A0 ledger     A2h vs A0 sum starts
  40o                  +51.04%       -6.74%  (WORSE on starts)
  120o                +106.44%      -32.99%  (WORSE on starts)
  200o w7              +19.48%       -6.47%  (WORSE on starts)

At 40 orders A2h costs +51% AND produces LATER starts than the cost-only arm.
So the anticipated headline condition -- "A2h matches A0 where A2 does not" --
is met only below the scale that matters. THE DESIGN DOES NOT CHANGE SHAPE.

WHAT THE MECHANISM ACTUALLY IS (diagnosed, not assumed)
-------------------------------------------------------
When tardiness is zero the cost objective is START-INDEPENDENT: production
cost is duration x rate with duration fixed, and setup is a fixed charge per
running op. The cost-only model is therefore a pure FEASIBILITY problem with
an effectively constant objective, and CP-SAT closes it instantly -- A0 proves
OPTIMAL at 5, 8, 15, 40 orders and at 200o/w7, with identical totals across
all five seeds, consuming between 0.00005 and 3.08 of its 6.0 deterministic
units (0.10 at 40 orders -- 1.7% OF THE BUDGET).

Adding ANY start-sum term -- priced at 5 (A1) or lexicographic at BIG (A2,
A2h) -- makes the objective start-dependent and converts that feasibility
problem into a genuine min-sum-of-starts scheduling optimization, which CP-SAT
cannot close in 60x the budget.

The cleanest confirmation is the 120-order row. There the cost-only arm is
ITSELF unable to prove optimality (tardiness > 0, so cost is already
start-dependent) and it carries an 87,783 seed spread -- and exactly there
A2's ledger penalty collapses to +7.43%, INSIDE that spread. The penalty is
large precisely where the cost-only problem was trivial, and vanishes into
noise where it was not. That is a mechanism, not a coincidence.


======================================================================
5. ITEM 3 -- THE COMPRESSOR (C), MEASURED
======================================================================

C: after a solve, walk operations in topological order and pull each as early
as precedence, calendar, resource availability, the frozen boundary and pins
allow, WITHOUT changing the sequence on any machine. Implemented as a SCRATCH
post-processor (tools/spikes/tiebreak_4b6c/compressor.py). Not committed to
any shipped path.

Two variants, both reported. C_free: every free op movable, floored at the
window origin -- the variant comparable to what the solver's tiebreak wins,
since that also moves ops landing in the frozen front. C_frozen: the frozen
front treated as COMMITTED per R-F1 -- those ops fixed, and no movable op
pulled below frozen_end. C_frozen is the shippable shape.

(c) THE OVERTIME CHECK -- the reason to measure rather than assume
------------------------------------------------------------------
The FULL ledger was recomputed by the real Extractor after EVERY accepted
shift. Across 56 compressor runs (28 C_free + 28 C_frozen):

  * 1 REJECTED SHIFT, magnitude +$151.67 (200 orders w7, seed 43 -- the same
    shift in both variants). An op that would have landed in a dearer hour.
  * 0 runs whose ledger rose.
  * Setup and production behaved as predicted (start-invariant); only
    production_overtime_cost could move, and it did, once.

The check is not theoretical. It fired.

(d) BOUNDS, ASSERTED (not claimed)
-----------------------------------
In-harness assertions on every run: fixed ops (frozen front + resumable
chunked ops) do not move AT ALL; under C_frozen no movable op crosses the
frozen boundary into committed territory; no op changes machine; no machine is
reordered. On top of that, EVERY compressed schedule was re-validated by
PINNING all of its placements into a freshly built window model and asking
CP-SAT -- the model's own verdict, not the compressor's. 56/56 VALIDATED
OPTIMAL.

NAMED LIMIT: a window-0 view carries no standing pins, so the literal R-DP8
pin bound is asserted over an empty set. The weight is carried by the
frozen-front bound, which is exactly what R-F1 says those ops become on the
next roll.

DEVELOPMENT NOTE, because it nearly produced a wrong answer: a naive
left-shift that honours precedence, calendar and machine sequence STILL
produced INFEASIBLE schedules. The validation step caught it and CP-SAT's
sufficient_assumptions_for_infeasibility isolated the conflicting pair. The
missing constraint was the SEQUENCE-DEPENDENT SETUP TRANSITION MATRIX
(SolverBuilder._add_transition_constraints -- a 15-minute family changeover on
pilot_scale), which is PAIRWISE over every pair that may share a resource, not
only adjacent ones. Any future C must carry it.

(b) WHAT C WINS, AND HOW IT COMPARES TO THE SOLVER'S TIEBREAK
-------------------------------------------------------------
  instance  from  variant   seed  moved   starts before      after         won   ledger before  ledger after
  15o       A0    C_frozen 42-46      0          70,329     70,329           0       5,596.65      5,596.65
  40o       A0    C_frozen 42-46      0         363,638    363,638           0      16,481.95     16,481.95
  120o      A0    C_frozen    42     60       1,680,564  1,565,638     114,926      63,549.10     63,549.10
  120o      A0    C_frozen    43     45       1,558,104  1,453,308     104,796      95,762.23     79,815.98
  200o w7   A0    C_frozen    42     41       1,032,991    990,091      42,900      27,863.63     27,863.63
  200o w7   A0    C_frozen    43     36       1,113,986  1,077,492      36,494      27,863.63     27,863.63

ON A0's PROVEN-OPTIMAL SOLUTIONS AT 15 AND 40 ORDERS, C MOVES NOTHING -- zero
ops, every seed. Those schedules are ALREADY fully left-packed under
sequence-preserving shifts. On BUDGET-TRUNCATED solutions C does real work,
and at 120 orders seed 43 it took the ledger from 95,762.23 to 79,815.98
(-16.7%) for free.

The comparison item 3(b) asks for: at 40 orders A2 wins 154,441 start minutes
INSIDE the solver where C wins 0 from A0. THE SOLVER'S WIN COMES FROM
RESEQUENCING WORK ON MACHINES, WHICH C BY CONSTRUCTION CANNOT DO. They are not
substitutes.

(e) STACKED -- A2h + C. ADDITIVE, NOT REDUNDANT.
-------------------------------------------------
  instance seed    A0 alone       A0+C     A2h alone      A2h+C    ledger A0   ledger A2h+C
  40o        42     363,638    363,638       348,014    279,807    16,481.95      25,857.78
  40o        43     363,638    363,638       396,624    245,366    16,481.95      21,682.78
  40o        44     363,638    363,638       346,278    341,112    16,481.95      16,481.95
  40o        45     363,638    363,638       400,426    226,445    16,481.95      22,882.78
  40o        46     363,638    363,638       388,137    289,120    16,481.95      25,892.88
  120o       43   1,558,104  1,453,308     1,363,515  1,295,676    95,762.23     100,012.20
  200o w7    42   1,032,991    990,091     1,148,513  1,092,978    27,863.63      33,055.72

C recovers 5,166 to 173,981 start minutes that A2h left on the table, and on
two runs it also cut the LEDGER (40o seed 43: 24,893.62 -> 21,682.78; 120o
seed 43: 123,813.87 -> 100,012.20). So the two are SUBSTANTIALLY ADDITIVE --
A2h's budget-truncated solutions leave slack a left-shift recovers.

But at 40 orders A2h+C is STILL DEARER THAN PLAIN A0 on four of five seeds.
The exception is seed 44, where A2h+C matches A0's proven optimum (16,481.95)
with 341,112 starts against A0's 363,638 -- a 6.2% start win at zero cost. One
seed in five.


======================================================================
6. ITEM 4 -- WHO READS THE OBJECTIVE VALUE?
======================================================================

Under B the raw objective is BIG*cost + starts, which is NOT MONEY.

THE PRODUCER. solve_runner.py:152-159 computes objective and gap and writes
both into the M6 solve_complete event (:192-209). Everything below reads that
one record.

CONSUMERS, BY CALL SITE, and whether each reads OBJECTIVE or LEDGER:

 1. schedule_assembler._solver_block (schedule_assembler.py:714-738) --
    OBJECTIVE (+ gap) into SolverBlock of the contract document, served by
    api/app.py:895. The contract labels it "solver objective (scaled units)"
    (contracts/schedule_document.py:327). Not money on any surface.
 2. sandbox.py:787, 895-898 -- OBJECTIVE, for delta_abs / delta_pct only. The
    dataclass field docs (:85-95) state it is a scaled tardiness-weighted sum
    and must never be shown as dollars; the card's money is cost_delta_abs /
    cost_lines, from the LEDGER.
 3. planner_edit.py:143, 255-258 -- OBJECTIVE, same discipline (:62).
 4. forced_alternatives.py:319, 444-448 -- OBJECTIVE, objective_delta_pct.
 5. solution_pool.py:158, 214-218, 257-260 -- OBJECTIVE, AND AS A CONSTRAINT.
    int(incumbent_objective * (1 + tolerance_pct/100)) is handed to
    add_objective_upper_bound, which applies that number to
    sum(var_map.objective_terms) (solver_builder.py:209-215).
 6. api/app.py:1029, 1065, 1116 and api/registry.py:97-98, 440-470 --
    pass-through and persistence of member objective / delta_pct. No
    arithmetic, no currency formatting.
 7. Cockpit: drag/ghosts.js:39 (delta_pct only); drag/sandboxui.js:306-310,
    395-410 explicitly refuses to render delta_abs as money and degrades to a
    labelled relative-percentage headline.
 8. __main__.py:456 -- a log line.
 9. tools/solver_gap_probe.py:200, 298-307 -- sums per-facility OBJECTIVE and
    compares to the monolith's. Self-consistent under B only if every shard
    uses the same encoding.
10. coarse_horizon.py:560, 794 -- the COARSE model's own objective, a separate
    model. Untouched by B (clause 4, import-direction test).

NOTHING READS THE OBJECTIVE AS MONEY. The Phase-3 exit audit fixed that and
the discipline is documented at every site. So the letter of item 4's trigger
finds nothing.

But the read found two live UNIT problems that B would make far worse, and one
of them is a defect today. Both are now PINNED (not fixed) by
tests/test_objective_units.py -- THE ONE COMMITTED TEST OF THIS SESSION, four
tests, all passing.

(a) THE ROLLING PATH RECORDS A MINUTE COUNT AS ITS OBJECTIVE.
    solver_builder.solve_two_stage deliberately rebuilds its result to carry
    STAGE 1's objective with stage 2's placements (:409-418), precisely so the
    recorded objective stays the COST objective.
    rolling_horizon._two_stage_solve returns the stage-2 SolveResult WHOLE
    (:166-172) -- and stage 2 minimizes sum(free-op starts), so .objective is
    a sum of START MINUTES. build_rolling_view writes that value into its M6
    solve_complete payload (:574-576) and WindowMetric.objective carries it
    (:973). On a rolling board every consumer above therefore sees an
    "incumbent objective" that is a minute count, not cost in any units.
    MEASURED on a hand-built model: cost 300 constant, coefficient 5, start
    forced to 20 -- monolithic records 400, rolling records 20.

(b) THE POOL'S COST BOUND IS LOOSER THAN ITS STATED TOLERANCE whenever a
    positive earliness_value is declared, because the bound's SOURCE (stage-1
    objective = cost + coeff*starts) is not in the units of the expression it
    bounds (sum(objective_terms) = cost). Worked example in the test: a stated
    5% tolerance is really 40%. Under B this becomes vacuous -- a BIG*cost
    scaled number bounding cost -- which is exactly the silent change the pin
    now blocks.


======================================================================
7. ITEM 5 -- DIRECTION NUMBERS (report only, NO recommendation)
======================================================================

First, so it is not measured pointlessly: minimizing sum of COMPLETIONS is the
SAME objective as minimizing sum of starts, since completion = start + fixed
duration. It is not an alternative and was not measured as one.

Total dwell = sum over ops with at least one placed predecessor of
(start - latest predecessor completion). WIP = work packages started but not
complete over the window; mean is time-weighted.

  instance   arm    dwell median (min)   mean WIP (wp)   peak WIP   sum starts
  5o         A0                  2,298            2.04          3        6,570
  5o         A1                  1,067            1.64          3        4,589
  5o         A2/A2h/A2x            839            1.52          3        4,817
  8o         A0                  1,902            1.28          2       10,610
  8o         A1                  1,902            1.28          3        7,730
  8o         A2/A2h/A2x          1,902            1.28          2       10,610
  15o        A0                  8,639            0.91          6       70,329
  15o        A1                  4,062            5.23          8       18,127
  15o        A2                  3,254            0.22          4       69,743
  15o        A2h                 2,428            1.80          4       29,454
  40o        A0                 23,980            2.52          9      363,638
  40o        A1                 24,088            1.20          9      196,183
  40o        A2                 17,983            0.84          8      209,197
  40o        A2h               165,944            4.19         12      388,137
  120o       A0                398,593           11.69         29    1,711,055
  120o       A1                173,451            6.37         17    2,367,408
  120o       A2                217,144            5.83         21    1,998,240
  120o       A2h               222,515            6.02         16    2,275,558
  200o w7    A0                236,817            7.20         14    1,078,745
  200o w7    A1                146,229            7.26         12      653,237
  200o w7    A2                362,689           10.64         18    1,168,950
  200o w7    A2h               308,292            9.45         17    1,148,513

Dwell before and after compression (C_frozen, selected):

  40o  A2h  seed 42:  152,140 ->  83,933    mean WIP 3.94 -> 2.38    peak 12 -> 12
  40o  A2h  seed 43:  223,736 ->  72,478    mean WIP 7.87 -> 3.92    peak 14 -> 14
  40o  A2h  seed 45:  197,474 ->  33,613    mean WIP 6.92 -> 1.76    peak 11 -> 11
  120o A0   seed 42:  398,593 -> 328,136    mean WIP 12.11 -> 10.81  peak 29 -> 29
  120o A0   seed 43:  498,003 -> 400,588    mean WIP 12.06 -> 9.90   peak 40 -> 40
  200o A0   seed 42:  201,549 -> 161,087    mean WIP 6.23 -> 7.07    peak 16 -> 16
  200o A2h  seed 42:  308,292 -> 253,082    mean WIP 9.45 -> 9.12    peak 17 -> 16
  15o and 40o from A0: unchanged (C moved nothing)

Numbers only. No recommendation. Direction -- earlier-is-better versus JIT --
is settled at the board.


======================================================================
8. WHAT WAS TEMPTING, AND LEFT
======================================================================

* FIXING rolling_horizon._two_stage_solve to return stage 1's objective like
  its monolithic twin. A one-line change, plainly a defect, sitting right in
  front of me. LEFT -- it moves rolling telemetry and everything that reads
  it, which is not a measurement session's call. Pinned instead.
* SCOPING OR FIXING the pool's objective upper bound. LEFT, pinned.
* REMOVING OR REPRICING the shipped earliness term, despite reading three
  showing +73% and +98% ledger damage at 40 and 120 orders. Explicitly out of
  scope; R-SC3 stands until the ruling moves.
* RELABELLING reopt_delta_abs (docs/07 section 5a.12). Out of scope; this
  session strengthens the case rather than acting on it.
* SHIPPING C. It is measured and it works (56/56 validated, one rejected
  shift, ledger never rose, -16.7% on one truncated instance), but item 3 says
  scratch and it stayed scratch.
* RAISING THE DETERMINISTIC BUDGET so the 200-order 14-day window produces
  something. It returns UNKNOWN at 6.0 AND at 20.0 units. That is a real
  product finding about the shipped window depth at pilot volume; chasing a
  budget that closes it is a different session.
* THE r5 BANK -- not run, per scope.
* ANY GOLDEN MOVE OR FIXTURE REGENERATION -- none.


======================================================================
9. WHAT CHANGED IN THE REPO
======================================================================

SUITE STATE. Python suite (tests/, excluding tests/cockpit and test_n3000):
1627 passed, 238 skipped, 1 FAILED in 703 s --
tests/test_scenario.py::test_scenario_untouched_moves_bounded. It passes in
ISOLATION and as a whole file (32/32), and no module in src/ changed this
session, so it is not caused by this work. It is a THIRD member of the
documented parallel-load flake class, and its root cause is structural rather
than incidental: the fixture solves with time_limit_seconds=30.0 and NO pinned
workers or seed (tests/test_scenario.py:341-344) -- CP-SAT default PARALLEL
search under a WALL-CLOCK limit, which this project's own hard rules say is not
reproducible. Under load it reaches a different tied-optimal placement and the
"moves <= 3" bound breaks. The fix is deterministic mode in that fixture, not a
wider bound. NOT fixed here; recorded in CLAUDE.md's carry-forwards.

* tests/test_objective_units.py -- NEW, the one committed test (4 tests).
* tools/spikes/tiebreak_4b6c/ -- NEW, measurement only, unreachable from src/:
  arm_harness.py, compressor.py, run_compressor.py, analyze.py, analyze_c.py,
  the raw *.jsonl, and the generated TABLE.txt / TABLE_C.txt.
* SESSION_CLOSEOUT.md -- this file.
* docs/04-design-history.md -- one amendment. docs/07-roadmap.md -- section 5a
  debts and position.
* NO SHIPPED MODULE CHANGED. No objective, no ruling, no golden, no fixture.


======================================================================
10. HARNESS CAVEATS, NAMED
======================================================================

* The harness's A1 arm reports STAGE 1's objective (the monolithic
  convention), whereas shipped rolling_horizon._two_stage_solve reports stage
  2's. This is a TELEMETRY difference only -- it does not touch the solve, the
  placements, the ledger or any arm comparison -- and it is the same
  divergence section 6(a) reports.
* One harness bug was found and fixed mid-session: protobuf repeated fields
  reject negative indexing, so v.proto.domain[-1] raised inside a try/except
  and silently collapsed BIG to 1. Every affected row was discarded and
  re-run; the fix is commented at the site so it cannot recur silently.
* Wall times are honest but machine-specific and some were measured with a
  second single-worker solve running. The DETERMINISTIC time consumed is the
  reproducible measure and is reported beside them.
* A2x carries 3 seeds at 120 orders rather than 5, stated at the table.
* The compressor was run at 15 and 40 orders on 5 seeds and at 120 and 200o/w7
  on 2 seeds -- a deliberate cut, stated rather than silently dropped.

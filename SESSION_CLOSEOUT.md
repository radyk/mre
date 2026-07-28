SESSION 4B.10 CLOSE-OUT
THE REAL SHAPE: FEW MACHINES, DEEP QUEUES
2026-07-28

Repo: C:\dev\mre, branch master. Deterministic throughout: PYTHONHASHSEED=0,
num_search_workers=1, generation seed pinned at 1 so seed spread measures the
SOLVER and not the world. R-SC1 stands: raw_data/ was read with pandas as
INTELLIGENCE only -- nothing was submitted, gated or solved from the extract,
and RawAdapter was not revived.

Unlike 4B.9 this close-out is NOT the whole deliverable. 4B.9's numbers and
4B.10's own are durable in docs/07 sec 5a (items 24-27) as the brief's first
act required. This file is the narrative.


======================================================================
1. THE HEADLINE -- UTILISATION, AND WHY IT REFRAMES LESS THAN FEARED
======================================================================

The brief asked for utilisation first because if a real 14-day window is
structurally over-capacity, the difficulty is the PLANT and the honest product
answer is a shorter window with tardiness priced rather than a deeper one.

THE ANSWER IS: IT DEPENDS ON THE FACILITY, AND THE TWO CASES MUST NOT BE
CONFLATED.

  F006, the LARGEST facility (851 orders, 4 machines, 803 ops/machine at 14
  days) sits at 112.5% -- STRUCTURALLY OVER-CAPACITY. No solver fixes that.

  F004, the MEDIAN facility (276 orders, 4 machines, 246 ops/machine, 984 ops
  in a 14-day window) sits at 32.6% -- COMFORTABLY FEASIBLE. And 4B.8's cost
  objective returned UNKNOWN at 313 free ops. THERE THE DIFFICULTY IS OURS.

  Book-wide 14-day utilisation on normal work is 210.4%; 5 of 11 facilities are
  over 100%; the median facility BY UTILISATION sits at 99.4%, precisely at the
  boundary.

But the reason this reframes less than the brief feared is section 3: on the
real shape, at the extract's own single-machine routings, THE SOLVER DOES NOT
STRUGGLE AT ALL.

-- BEFORE ANY OF THAT: TWO MEASUREMENT FACTS THAT HAD TO BE SETTLED FIRST --

(a) THE DURATION SEMANTICS ARE DETERMINED, NOT AMBIGUOUS. The brief allowed for
    reporting both readings. Only one survives. ProductionMinutes is PER LOT
    (per CostingLotSize units) and the full rate applies to EACH operation
    independently; SetUpMinutes is per operation:

        op_minutes    = SetUpMinutes + (WoQuantity / CostingLotSize) * ProductionMinutes
        order_minutes = n_active_routing_lines * op_minutes

    Three independent lines of evidence agree:
      1. The previous-generation PRODUCTION code computes exactly this, per
         routing line, inside its per-line loop -- legacy/Formatnewjobs.py:68,
         proc_time = int((wo_quantity / casting_lot_size) * production_minutes),
         with setup_minutes taken per line.
      2. The repository already RULED it: legacy_author_definition_v1,
         docs/04:693-701, confirmed 2026-07-07, implemented at
         raw_adapter.py:621 and reproduced by the IDS adapter's own fallback
         (ids_adapter.py:426).
      3. THE DATA ITSELF. log-log correlation of ProductionMinutes against
         CostingLotSize is r = +0.683 (n = 20,131), and median PM rises
         monotonically with the lot band: lot 1 -> PM 1; 1k-10k -> 51;
         10k-50k -> 874; 50k+ -> 1,663. A per-ORDER or per-UNIT figure would be
         INDEPENDENT of lot size. It is not.

(b) A SENTINEL CLASS CARRIES 94% OF THE COMPUTED LOAD, AND THE ADAPTER DOES NOT
    CATCH IT. 1,434 of 20,743 products (6.9%) read
    CostingLotSize = SetUpMinutes = ProductionMinutes = 1 -- ALL THREE COLUMNS
    EXACTLY 1 ON 100.0% OF THOSE ROWS, against a median ProductionMinutes of 549
    for every other product (only 0.31% of which read 1). 227 open orders (7.01%)
    use them and they carry 93.56% OF ALL COMPUTED MACHINE-MINUTES. The largest,
    PP10293020, is WoQuantity = 10,000,000 at lot=1, PM=1 -> 30,000,003 minutes
    (41,667 shifts) for a single order.

    NO EXCLUSION RULE WE HAVE WOULD CATCH THEM. The extract is not submitted
    (R-SC1), so this is a statement about what WOULD happen: the retired
    adapter's exclusions fire on CostingLotSize == 0 (131 orders) or a missing
    product (104), and a lot=1 row is well-formed and passes both.
    This is the repeated-identical-value fingerprint the
    carry-forwards already warn about, found in the wild, and every utilisation
    figure in this session is taken with the class removed and said so.

    Separately and legitimately: 13 orders (0.40%) have credible costing but a
    single operation longer than a 14-day window on one machine (WR10000141:
    1.1M units, lot 25,000, PM 1,350 -> 82.6 shifts on ONE op). That is real
    resumable work, exactly R-C3's case, not a defect.

FULL TABLES: docs/07 sec 5a.25.


======================================================================
2. `facility_real` -- THE PRESET WITH THE REAL SHAPE
======================================================================

pilot_scale IS UNTOUCHED AND PROVEN SO. Generating pilot_scale at 200 orders
from the working tree and from git HEAD produces byte-identical output in every
file; the only difference anywhere is manifest.json's `extract_timestamp`, a
wall-clock stamp. tests/test_generate_erp_dataset.py and
tests/test_defaults_reproduce_baseline.py: 31 passed, 1 skipped.

The two presets are now LABELLED and both keep their purpose:

  pilot_scale    the LOOK-AHEAD preset. Its due-date spread is DELIBERATELY
                 wider than the book's (generate_erp_dataset.py:1197-1200,
                 "the regime where a longer look-ahead actually buys cost").
                 It carries every regression golden we own.
  facility_real  the REALISTIC preset. 4 machines, 4-op routes, the book's
                 due-date histogram, and PAST-DUE ORDERS.

FOUR VARIANTS, added never repurposed:

  facility_real          276 orders, 4 machines, alternates=1, 7.83% past due
                         -- F004, the MEDIAN facility
  facility_real_large    851 orders  -- F006, the LARGEST
  facility_real_alt      276 orders, alternates=2 -- CROSS-TRAINED
  facility_real_pastdue  400 orders, 25.2% past due -- F005's book

CALIBRATION IS CHECKED, NOT ASSERTED.
tools/spikes/density_4b10/verify_facility_real.py prints the generated shape
beside each measured target. At 276 orders, seed 1:

  metric                 GOT     TARGET   source
  ops per order         4.00       4.00   exactly 4 at every 4-machine facility
  due <= 7 days        51.8%      50.1%   book histogram
  due <= 14 days       92.0%      90.0%   book histogram
  median lead           7 d        7 d    book quantile
  p75 lead              9 d        9 d    book quantile
  past due             7.61%      7.83%   book
  setup median / p75 / p90    5 / 20 / 30 exactly F006's ladder
  setup mean            12.8       12.4   F006 normal tier
  run median / p90    0.5 / 4.9  0.5 / 4.7 F006 normal tier
  op minutes mean       15.3   13.2-14.4  F004 / F006
  14-day utilisation    38.7%      32.6%  F004 (7-day denominator, as sec 5a.25)

A MEASURED-vs-AUTHORED table is written at
datasets/facility_real/PROFILE_PROVENANCE.md, naming every authored value: the
720-minute day and Mon-Fri week (the extract has NO calendars), machine cost
rates, cross-training, customers and priorities, the absence of setup families
and splittable flags, the coarse-horizon coefficients, quantity truncation at
5,000 units and past-due depth truncation at 60 days.

TWO DEPARTURES FROM THE BOOK, both forced by the data and both named:

  1. ROUTE LENGTH p90/max. The book is p90 8, max 12 -- but MEASURED: across the
     134 routes open work uses, the ratio of routing lines to DISTINCT
     workcenters is EXACTLY 1.00. No route ever revisits a workcenter. So an
     8-op route needs 8 machines, and every 4-machine facility in the extract
     (F004, F006, F00A -- 1,720 orders) has a route length of EXACTLY 4 on 100%
     of orders. Route length and machine count are COUPLED in the book and the
     preset couples them the same way. Building a 4-machine plant with 8-op
     routes would model a facility that does not exist.
  2. THE SENTINEL CLASS IS NOT REPRODUCED. A preset calibrated to it would be
     calibrated to a data defect.

ALTERNATES ARE MODELLED AS CROSS-TRAINING, NOT EXTRA MACHINES. With
alternates=2 an operation is eligible on its own stage plus the next, cyclically.
MACHINE COUNT AND TOTAL LOAD ARE IDENTICAL ACROSS THE TWO SETTINGS -- verified:
both arms report 572 ops, 8,671 required minutes, 43.0% utilisation at 7 days,
and differ only in eligible-machines-per-operation (1 vs 2). The comparison in
section 3 is therefore a CONTROLLED experiment on assignment combinatorics
alone. The extract's single-workcenter routings are believed to be an EXTRACT
LIMITATION rather than a plant fact, so both are built and neither is assumed
real.


======================================================================
3. THE DENSITY SWEEP -- THE CLIFF IS NOT WHERE ANYONE LOOKED
======================================================================

CONFIGURATION, all three as the brief required, or the measurement is void:
  * COST-ONLY objective -- the sweep calls the SHIPPED
    rolling_horizon._two_stage_solve, which sets no objective of its own.
  * P3 ALLOCATION -- the shipped 4B.8 split (stage 1 capped at det_total minus
    a 1/12 reserve; stage 2 gets the remainder). Not transcribed: called.
  * WALL CEILING RAISED to 1800 s so the DETERMINISTIC budget binds.
    member_time_limit_s defaults to 30.0 while stage 1 needs 37-120 s at 200
    orders, so every prior measurement on the shipped path was wall-truncated.
    wall_truncated is FALSE on every reported row; analyze.py excludes any row
    where it is not, and refuses a file containing a duplicated cell at all.

Window 14 d, frozen 3 d, det_total 6.0, 4 machines, generation seed pinned at 1.

A METHOD NOTE, because it matters. A first pass of this sweep was DISCARDED: a
backgrounded process outlived its shell and ran concurrently with its
replacement, duplicating cells and contending for CPU. The specimen is kept at
density_CONTAMINATED.jsonl.bak and analyze.py now refuses duplicated cells
rather than averaging over them. The discard cost nothing scientifically and
proved the design: DETERMINISTIC UNITS REPRODUCED TO EVERY DIGIT across the two
runs (0.001531178799999749; 0.015006761634700314; 2.4746173155819227) while
wall times differed by up to 1.6x. That is exactly why the measurement is on
deterministic units and the wall clock is only a truncation check.

-- Q1: WHERE IS THE CLIFF? --

At alternates=1 (the extract as measured) it is between 94 and 137 OPS PER
MACHINE -- and the multi-seed pass showed it is NOT A LINE. It is a REGION where
the budget is marginal and THE SEED DECIDES.

   ops/machine  util    n   proved   units to proof (range)    ledger spread
        22      4.2%    1     1/1     0.0002                        --
        46     10.3%    1     1/1     0.0015                        --
        94     19.0%    5     5/5     0.015 - 0.192  (med 0.041)     0.000%
       137     27.4%    5     4/5     2.294 - 5.594  (med 3.049)    13.056%

Below the cliff the proof is free: three orders of magnitude of headroom at 94
ops/machine, and five seeds agree on the ledger TO THE CENT. At 137 the proof
costs 2.294-5.594 units against a 5.5-unit stage-1 cap -- FOUR SEEDS FIT AND ONE
DOES NOT. Seed 42 exhausts the budget, returns FEASIBLE with an 11.47% gap, and
lands on a ledger of 33,298.77 where the other four PROVE the optimum at
29,453.35 -- IDENTICAL TO THE CENT ACROSS ALL FOUR. That is a 13.056% penalty
decided by nothing but the random seed.

This is the same failure mode 4B.8's CU1 measured for the OLD budget split at
200 orders (two seeds needing 4.542/4.962 units against a 4.0 cap), now
reproduced on the REAL SHAPE at the REAL density against the NEW cap. The 1/12
reserve did not create it and does not cure it: the instance simply costs more
than the budget on some seeds.

BOTH REAL FACILITIES ARE PAST IT: F004, the median, runs 246 ops/machine in a
14-day window; F006, the largest, runs 803.

COVERAGE, STATED RATHER THAN HIDDEN. 15 rows, wall_truncated FALSE on all 15.
MEASURED: 22 / 46 / 94 / 137 ops per machine (orders 28 / 55 / 110 / 165); BOTH
alternate settings at 22 / 46 / 94; alternates=1 at 137; seeds 42-46 at BOTH
bracket densities (94 and 137) for alternates=1.
NOT MEASURED: anything above 137 ops/machine, alternates=2 at 137 and above, and
seeds 43-46 at the two lightest densities. Every cell above the cliff spends the
full budget and the alternates=2 cells there run to tens of minutes each, so the
session spent its time LOCATING the cliff and PRICING its mechanism rather than
characterizing how bad it gets past it.

CONSEQUENCE FOR THE HEADLINE CLAIM, AND IT MATTERS: F004's 246 and F006's 803
ops/machine are BRACKETED, NOT DIRECTLY SOLVED. "Both real facilities are past
the cliff" follows from the cliff sitting at 137 PLUS the assumption that
difficulty does not DECREASE with density above it. That assumption is
consistent with the 22->137 series and with 4B.8's higher-density results, but
IT IS AN INFERENCE, NOT A MEASUREMENT. Those two densities are the obvious next
cells to run.

-- Q2: DO ALTERNATES HELP OR HURT? BOTH, AND THE RATES DIFFER WILDLY --

This is a controlled comparison: machine count and total load are IDENTICAL
across the two arms (verified: same ops, same required minutes, same
utilisation), so only assignment combinatorics change.

   ops/machine   ledger a=1   ledger a=2   delta     proof a=1   proof a=2  ratio
        22            4,650        4,606   -0.93%       0.0002      0.0006     3x
        46           10,229       10,120   -1.07%       0.0015      0.0802    52x
        94           20,379       20,085   -1.44%       0.0150      2.4746   165x

The a=1 / a=2 columns are the SEED-42 PAIR, so the ratio is a like-for-like
comparison. Stated honestly: alternates=2 was measured at ONE seed, while
alternates=1 has five at 94 ops/machine spanning 0.015-0.192 units, so against
that whole range the a=2 cost is 13x-165x, MEDIAN 60x. The direction is not in
doubt at any seed; the exact multiple is a one-seed figure and is labelled so.

ALTERNATES HELP THE LEDGER AND HURT THE SEARCH, and the two rates are not
comparable. The saving grows slowly (0.93% -> 1.44%); the proof cost grows by
one to two ORDERS OF MAGNITUDE over the same span. At 94 ops/machine
cross-training buys 1.44% of ledger while consuming 2.47 of a 5.5-unit budget --
a density at which alternates=1 is still spending under 0.2. Cross-training is
worth having for the schedule it produces; it is not free, and on this shape it
is what exhausts the budget first.

-- Q3: DOES THE CLIFF TRACK UTILISATION? NO -- AND THE REFUTATION IS CLEAN --

The most valuable possible outcome would have been a load ratio computable
BEFORE solving that the gate could warn on. It is not utilisation, and the sweep
refutes it twice over without needing a curve fit.

FIRST REFUTATION -- ELIGIBILITY IS INVISIBLE TO LOAD.
  At 110 orders the two arms have IDENTICAL utilisation (19.02%) and IDENTICAL
  ops per machine (94), and their proof costs differ by 165x (seed 42 pair).
  No function of utilisation or op count can separate two cells whose load
  numbers are the same. Whatever predicts difficulty must read the ELIGIBILITY
  STRUCTURE, which utilisation does not see.

SECOND REFUTATION, AND IT IS FATAL TO THE WHOLE IDEA -- THE SEED DECIDES.
  At 137 ops/machine, five runs differing ONLY in the solver's random seed split
  4 OPTIMAL / 1 FEASIBLE, with a 13.056% ledger spread. EVERY PRE-SOLVE QUANTITY
  IS IDENTICAL ACROSS THOSE FIVE RUNS. No rule computable before solving can
  distinguish them, because there is nothing to distinguish.

The analyzer states both verdicts itself:
    UTILISATION separates the two classes cleanly : False
    OPS/MACHINE separates the two classes cleanly : False

SO THE HOPED-FOR GATE WARNING DOES NOT EXIST IN THIS FORM. The cliff is not a
line in density to be predicted; it is a REGION where the budget is marginal.
What CAN be known is not predicted but REPORTED: the solve itself knows whether
it proved the cost optimum, and since 4B.8 CU3 the status field carries exactly
that. WHICH MAKES sec 5a.23 -- "provably optimal is a claim the system can now
make and NOTHING VOICES" -- considerably more serious than it looked when it was
written. At real density the difference between a proved and an unproved window
is 13% of the ledger, and no surface says which one the planner is looking at.

-- 3b: WHAT DOES PREDICT IT -- THE ONSET OF TARDINESS --

The sweep shows a perfect correlation. EVERY cell with tardiness = 0 proved the
cost optimum; the FIRST cell with tardiness > 0 (7,049 minutes across 8 late
demands) failed outright. A correlation over one sweep is not a mechanism, so it
was PRICED, in two experiments -- and the second one CORRECTED the first
explanation rather than confirming it, which is why both are reported.

(1) THE COUNTERFACTUAL (tardiness_counterfactual.py). The same instance solved
    twice, changing ONLY the tardiness weight (PRICED = the shipped cost model;
    FREE = base_weight and every commitment-class multiplier set to 0):

      165 orders / 137 ops per machine / alternates=1 / seed 42
        PRICED   FEASIBLE   5.5937 units spent   gap 11.47%   never proved
        FREE     OPTIMAL    4.7216 units         gap 0        PROVED

    Removing the tardiness price turns an unprovable instance into a provable
    one. Tardiness is the driver.

(2) BUT THE OBVIOUS EXPLANATION WAS WRONG, AND THE DATA SAID SO. The tempting
    reading was that with one eligible machine per operation the rest of the
    objective is a CONSTANT -- which predicts a NEAR-INSTANT proof. FREE took
    4.72 units, so that reading had to be tested rather than asserted.
    objective_variance.py evaluates sum(objective_terms) at several DIFFERENT
    feasible solutions of the same model:

      alternates=1, 165 orders, 548 free ops
        eligible-set sizes: {1: 548}   -- the assignment IS forced, checked
        TARDINESS PRICED   3 solutions, spread 4,973,436 .. 5,888,641  = 18.402%
        TARDINESS FREE     3 solutions, spread 2,967,852 .. 2,970,665  =  0.095%

    SO THE OBJECTIVE IS NOT CONSTANT -- IT IS NEARLY FLAT. The correct statement
    is: AT alternates=1 THE PLACEMENT-DEPENDENT PART OF THE COST IS ALMOST
    ENTIRELY TARDINESS. Freeing tardiness collapses the spread across feasible
    solutions by a factor of 194 (18.402% -> 0.095%); a small non-tardiness
    variation survives, so a "constant objective" claim would have been false.

    This is why the cliff sits where it does. Below it nothing is late, the
    objective barely moves between schedules, and the first solution is already
    within a whisker of optimal -- CP-SAT closes it in 0.0002-0.015 units. Above
    it tardiness dominates, the objective spreads 18%, and the search is a real
    combinatorial optimization the budget cannot finish. Note also that proving
    a NEARLY-FLAT objective is not free either: the FREE arm still needed 4.72
    units to close a 0.095% spread.

    And it explains the alternates result in the same breath: at alternates=2
    the machine rates DIFFER (52/55/58/61 $/h), so production cost varies by
    ASSIGNMENT even at zero tardiness -- which is exactly why 94 ops/machine
    costs 165x more to prove there.

A CAVEAT THAT MUST TRAVEL WITH THIS FINDING. The decomposition above is a
property of facility_real's authored physics -- and those choices FAITHFULLY
mirror the extract, which carries no setup families, no changeover matrix and no
overtime windows at all (docs/07 sec 5a.24). But a real plant that DOES price
changeovers would carry a placement-dependent cost term even at alternates=1,
and its cliff would not sit where this one does. What generalizes is the SHAPE
of the rule -- difficulty turns on how much of the objective actually varies
with placement -- not the number 137.


======================================================================
4. PAST-DUE WORK, FINALLY EXERCISED
======================================================================

REPORT ONLY. The ghost-job re-ruling is a design conversation; this session's
job was to hand it a live specimen and a number instead of a hypothetical.

Until now no fixture could ask. pilot_scale's lead_min = 4 makes a past-due
order structurally impossible, and the retired RawAdapter filtered past-due rows
on intake (raw_adapter.py:7) -- two independent blind spots over the 272 real
past-due orders (7.83% of the book; F005 carries 25%).

SPECIMEN WORLD: facility_real_pastdue, 60 orders, 21 past due.

(a) DOES IT GET SCHEDULED LATE, OR VANISH? IT VANISHES -- 21 of 21, before the
    solver. Not scheduled late, not partially placed.

(b) WHERE? TWO SITES, NOT ONE, AND THEY DISAGREE. The same finding code is
    raised twice with OPPOSITE dispositions:

      M0, the conformance gate. Rule ids.order_dates_internally_consistent
      raises ONE TEMPORAL_IMPOSSIBILITY / WARNING covering all 21 orders,
      outcome "degraded", DISPOSITION = proceeded_flagged. The submission grades
      CONDITIONAL with go = True. The gate SEES the past-due orders, names them,
      and DELIBERATELY PASSES THEM ON.

      M3, the validator (src/mre/modules/validator.py:186-221, Check 1). A
      Demand whose due < reference_date AND which carries no
      in_progress/complete wip_operations is added to excluded_demand_ids with
      DISPOSITION = EXCLUDED. PreparedPlant.schedulable_demands
      (rolling_horizon.py:385) then subtracts that set and the order is gone.

    SO THE GATE'S `proceeded_flagged` PROMISE IS NOT HONOURED DOWNSTREAM. M0
    says "proceed with these, flagged"; M3 removes them; nothing reconciles the
    two. It is not gravity admission -- the demand never reaches _admit. The
    ONLY escape is the docs/06 sec 5.13 wip_status doorway, which the extract
    cannot populate because it carries no WIP field of any kind.

    (A CONDITIONAL grade on facility_real is therefore CORRECT and expected --
    it is the past-due orders, not a defect in the preset. pilot_scale, which
    cannot produce one, grades ACCEPTED. Both carry costing grade C2.)

(c) IS IT CERTIFICATE-VISIBLE? NO. The assembled contract-1.9 rolling document
    is 111,839 characters and contains ZERO occurrences of the specimen's order
    id, of TEMPORAL_IMPOSSIBILITY, or of the strings "excluded", "past due",
    "past_due" or "temporal". RollingVocabulary.resolve('ORD-000014') returns
    None -- the order is not a known subject. It is not beyond-horizon either,
    so 4B.5's guarantee that "a tray order is never NOT IN THIS SCHEDULE" does
    not cover it.

(d) IS IT AI-ANSWERABLE? PARTLY, AND ONLY BY THE AGGREGATE DOOR. Measured
    against the live ask path with a key present:

    "where is ORD-000014?"
        -> "Nothing scheduled for ORD-000014."
        True, and INDISTINGUISHABLE from an order that was simply not placed.

    "why isn't ORD-000014 scheduled yet?"
        -> "isn't in the beyond-horizon list -- it's either already in the
            current window (committed or active) or not part of this schedule."
        A disjunction NEITHER BRANCH OF WHICH IS TRUE, pointing back at the
        route above, which then says nothing.

    "which orders are already late?"
        -> "No late orders found in this schedule."
        In a world where 35% of the book is ALREADY PAST DUE. A trailing note
        counts exclusions but names them BY RAW CANONICAL UUID.

    "why was <id> excluded?"
        -> REACHES IT. Route `excluded-orders`, register testimony, 21 records,
           every order named by ORDER ID with its reason.

(e) THE CATEGORY ERROR, WHICH IS THE FINDING THAT MATTERS. The one working door
    answers "21 data-quality problem(s) ... has dates that can't both be true
    ... Want the fix-first ordering?". A released work order that is genuinely
    late IS NOT A DATA DEFECT AND HAS NO FIX -- it is the plant's actual
    position, 7.83% of this book and a quarter of F005's. This is the SAME
    shelving error docs/07 sec 5a.1 already names for --horizon-days: a
    real-world category filed as a data-defect category.

    Three further consequences, all measured: the answer is an AGGREGATE (asking
    about ONE order returns all 21, subject resolved as "excluded orders"); the
    per-order placement routes never reach it; and the lateness route actively
    contradicts it.

    NOT RE-RULED HERE. Fix shape for the design conversation: a past-due
    unstarted demand needs a disposition of its own -- distinct from both a data
    defect and a beyond-horizon tray order -- and the per-order placement routes
    need to voice it, or the most operationally urgent work in the book stays
    invisible to every question a planner would actually ask about it.

ONE UNDIAGNOSED OBSERVATION, reported not explained: the trailing note on the
aggregate lateness answer read "60 of 102 orders are scheduled; 42 excluded" in
a world of 60 demands with 21 past due. The evidence store holds 22
TEMPORAL_IMPOSSIBILITY findings across 22 DISTINCT demand subjects, so the
records are not duplicated and the note's arithmetic does not reconcile with the
world. Root cause NOT established; recorded so it is not lost.


======================================================================
5. WHAT WAS NOT DONE
======================================================================

  * No window_days change and no window rule. This session measured.
  * pilot_scale, its goldens and every existing fixture untouched (proven
    byte-identical against HEAD).
  * Ghost jobs NOT re-ruled -- specimen and number only, per the brief.
  * The hint experiment, the r5 bank, the sec 5a.20 vocabulary migration and
    splicing seams: all out of scope, none touched.
  * RawAdapter not revived; the extract not submitted. R-SC1 stands.

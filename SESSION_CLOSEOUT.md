SESSION 4B.11 CLOSE-OUT
THE HONESTY BUNDLE: THE PROOF RENDERED, THE LATE WORK SCHEDULED,
THE ARITHMETIC RECONCILED
2026-07-28

Repo: C:\dev\mre, branch master. Deterministic throughout: PYTHONHASHSEED=0,
num_search_workers=1, solver seed 42, generation seed pinned at 1.

The ruling R-PD1 is transcribed verbatim in docs/04 with the session amendment.
docs/07 v2.55 carries the durable numbers (sections 5a.28-30 new; 5a.23 and
5a.26 discharged). This file is the narrative.


======================================================================
1. THE THREE ANSWERS -- BEFORE AND AFTER, VERBATIM
======================================================================

Specimen: facility_real_pastdue, 60 orders, 21 already past due, reference
date 2026-01-05. Driven at the ROUTE level so the measurement is deterministic
and does not depend on a model parse. Full transcripts in
_4b11_scratch/BEFORE.txt and AFTER.txt; the probe is
tools/spikes/pastdue_4b11/probe.py and it is the SAME script both times.

-- Q1: "where is ORD-000014?" ----------------------------------------

BEFORE
    Nothing scheduled for ORD-000014.

AFTER
    ORD-000014: 4 operation(s) across 4 machine(s):

      [FR-M1]
        seq= 10  2026-01-05 07:42 -> 2026-01-05 08:03  ORD-000014
      [FR-M2]
        seq= 20  2026-01-05 08:04 -> 2026-01-05 08:26  ORD-000014
      [FR-M3]
        seq= 30  2026-01-05 08:27 -> 2026-01-05 08:48  ORD-000014
      [FR-M4]
        seq= 40  2026-01-05 08:49 -> 2026-01-05 08:55  ORD-000014

-- Q2: "why isn't ORD-000014 scheduled yet?" -------------------------

BEFORE
    ORD-000014 isn't in the beyond-horizon list - it's either already in the
    current window (committed or active) or not part of this schedule. Ask
    about its placement directly to see which.

    (A disjunction NEITHER BRANCH OF WHICH IS TRUE, pointing at a route that
    then said "Nothing scheduled".)

AFTER
    ORD-000014 IS scheduled - it's committed in the frozen zone, not waiting
    beyond the horizon. It finishes 85495 minutes past its due date - but
    84960 of those were already unavoidable when this window opened (it was
    ALREADY PAST DUE), so this schedule adds 535. Ask "where is ORD-000014?"
    for the operation timeline.

-- Q3: "which orders are already late?" ------------------------------

BEFORE
    No late orders found in this schedule.

    Note: 60 of 102 orders are scheduled; 42 excluded
    (01D65946-E8F2-5832-829B-B7D797104857, 0DEE42A9-6527-50B3-BD7C-DDCEB9DD94A6,
    0F093432-1125-5023-A198-205F5E637507, 12B5E06C-23C3-5DC3-84DE-61EFE2524EEE
    ...) - ask "why was 01D65946-E8F2-5832-829B-B7D797104857 excluded?" for
    the reason.

AFTER
    21 late order(s):
      - ORD-000004 (+22664 min; 21600 already past due at the start, 1064 added here)
      - ORD-000006 (+15122 min; 14400 already past due at the start, 722 added here)
      - ORD-000007 (+616 min)
      - ORD-000011 (+62721 min; 61920 already past due at the start, 801 added here)
      ... 17 more ...

    20 of those were ALREADY PAST DUE before this window opened - that is the
    plant's position, not a data problem, and the work is scheduled. Of the
    total lateness, 492480 minute(s) were unavoidable at the start and 18414
    minute(s) are what this schedule adds.

    Want the cause chain for the worst one? Ask "why is ORD-000014 late?"

A detail the data forced and the copy respects: 21 orders are late but only 20
carry a floor. ORD-000007 was past due by ONE SECOND -- due 2026-01-04T23:59:59
against a horizon start of 2026-01-05T00:00:00, because due dates are stored
end-of-day -- so its floor truncates to 0 minutes and all 616 minutes of its
lateness are genuinely this schedule's. The answer says 20, and 20 is right.

-- and a fourth, which CU4(d) asked for --

BEFORE  "why was ORD-000014 excluded?" returned ALL TWENTY-ONE exclusions with
        the subject resolved as "excluded orders" -- a one-order question
        answered with an aggregate.

AFTER   ORD-000014 wasn't excluded - it IS in this schedule. Ask "where is
        ORD-000014?" for its operation timeline.


======================================================================
2. DID GRAVITY PRIORITIZE THE PAST-DUE WORK, OR DID IT HAVE TO BE TOLD?
======================================================================

IT DID NOT HAVE TO BE TOLD, AND THE ADMISSION POLICY WAS NOT TOUCHED.

Measured, not assumed. All 21 past-due demands are admitted by the BASE rule
in rolling_horizon._admit -- "due <= window_end" -- unconditionally, before
gravity runs at all. They are counted in reasons["base"], not in
reasons["a_must_start"].

The brief anticipated that gravity's must-start-by pull would be what admits
them ("its must-start-by is passed, so gravity pulls it hardest"). That turns
out to be true but irrelevant: gravity's pull exists for work that would
otherwise fall OUTSIDE the window, and past-due work is inside it by
definition. Nothing had to be added, and nothing was.

ORDERING within the window is the solver's job, via the tardiness weight, and
it does prioritize: of the 21 past-due orders placed, 7 land in the first
quarter of the window by start time, and 4 of the first 8 starts on the whole
board are past-due orders.

Measured:
    past-due orders PLACED in window 0 : 21 of 21
    past-due orders in the TRAY        : 0
    past-due orders NOWHERE            : 0


======================================================================
3. THE 42 -- ROOT CAUSE, PLAINLY
======================================================================

4B.10 reported it undiagnosed: a trailing note reading "60 of 102 orders are
scheduled; 42 excluded" in a world of 60 demands with 21 exclusions.

TWO INDEPENDENT ERRORS, BOTH IN Explainer._excluded_summary, AND THEY
COMPOUNDED.

(1) THE COUNT CAME FROM A TOKEN SET. _excluded_labels holds every STRING that
    names an excluded demand -- its canonical UUID *and* its ORD- id -- so that
    a planner who pastes either one is understood. That is correct for
    MATCHING. Counting it counted every order twice: 21 x 2 = 42. The names
    shown were whichever half sorted first, and digits precede letters, so the
    planner saw UUIDs.

(2) `scheduled` COUNTED EVERY DEMAND IN THE SNAPSHOT, excluded ones included,
    and `total` was then that number PLUS the exclusions -- double-counting
    them a second time: 60 + 42 = 102 in a 60-order world.

Neither number was arbitrary; both were wrong for reasons that read as
reasonable at the line where they were written. That is what makes the class
worth naming rather than just fixing.

THE FIX. The match set survives unchanged, for matching. Display and counting
now go through _excluded_records, keyed by the RESOLVED ORDER -- because the
same order is excluded in two id-spaces by two layers (the M0 gate's subjects
are submission-space ORD- ids; the validator's are canonical UUIDs), and keying
on the raw subject id counted one order twice and labelled one copy with a
truncated id nobody recognizes. That was the first attempt, and it produced
"(unnamed demand ORD-0000)" in the output -- caught by the probe, not by
reasoning.

THE INVARIANT NOW ASSERTED: scheduled + count == total, AND total == demands in
the snapshot.

PROVED, NOT ASSUMED. R-PD1 dissolves the note on the specimen itself -- nothing
is excluded there any more, so re-running it shows the note ABSENT rather than
CORRECT. The reconciliation is therefore proved on a purpose-built world with
three genuine data-defect exclusions (quantity <= 0, which clause (2) permits):

    demands in snapshot     : 60
    excluded_demand_ids     : 3
    _excluded_labels (match): 6
    note                    : 3 excluded, 57 scheduled, 60 total
    scheduled + count == total : True
    total == demands in world  : True
    every name is an ORDER ID  : True

    Note: 57 of 60 orders are scheduled; 3 excluded (ORD-000001, ORD-000002,
    ORD-000003) - ask "why was ORD-000001 excluded?" for the reason.

A THIRD DEFECT fell out of the same investigation and is fixed at its own site.
planner_language.finding_subject_label appended the evidence's demand_id to the
subject list even when the subject had ALREADY resolved, producing

    ORD-000004, 0f093432-1125-5023-a198-205f5e637507 has dates that can't both
    be true

-- the order named correctly, then again in a vocabulary the planner cannot
use, and an invitation to paste the UUID back. That fallback exists for the
REJECTED run, where nothing resolves and the ERP-space id is the only identity
there is; it is now skipped when it would merely repeat a subject already
named.


======================================================================
4. WHAT R-PD1 ACTUALLY COST, AND THE SECOND EXCLUSION SITE
======================================================================

validator.py Check 1 no longer excludes anything. It raises one
PAST_DUE_AT_INTAKE finding (INFO, proceeded_flagged) plus two metrics. Checks
2-6 are untouched: a quantity <= 0 is still malformed and still excluded, which
is exactly what clause (2) permits.

THE FINDING CODE IS ADDED, NEVER REPURPOSED, AND THE DISTINCTION IS THE POINT.
M0 raises TEMPORAL_IMPOSSIBILITY for due < release/created -- a date pair that
genuinely cannot both be true. M3 was raising the SAME code for
due < reference_date -- a demand that is merely LATE. One code, two meanings,
and only one of them a defect. The consequences were concrete: the authored
phrase "has dates that can't both be true" is FALSE of an overdue order, and 21
real orders were filed into a fix-first remediation queue for a condition that
has no fix. PAST_DUE_AT_INTAKE is finding code 19 (docs/02 section 4.3), with a
catalog entry carrying remediation_applies: false and the rationale the
catalog's own out-with-rationale pattern requires.

A SECOND EXCLUSION SITE WAS FOUND AND CLOSED, AND IT WOULD HAVE SILENTLY UNDONE
THE FIRST. Check 5's resumable window-fit test asks "does this work fit BEFORE
THE DUE DATE?" against elapsed_days = max(0.0, due - now). For a past-due
demand that floor makes available_minutes exactly 0.0, so ANY positive duration
exceeds it. Once Check 1 stopped excluding, every past-due RESUMABLE demand
would have fallen straight into Check 5 and been excluded there as
INFEASIBLE_SUBSET -- the same removal wearing a different finding code, and the
session would have shipped believing the ruling was implemented. The
NON-resumable single-window test is deliberately NOT skipped: it asks whether
one operation exceeds the longest contiguous window on EVERY eligible resource
(docs/05 R-C3), which is a structural impossibility independent of any due
date, and a genuine defect class.

SCHEDULING PAST-DUE WORK MUST NEVER MEAN MODELLING PAST TIME.
SolverBuilder._compute_horizon floored horizon_start at the reference date only
when one was supplied. Until now no released-long-ago order could contribute
its earliest_start, because it had been excluded; with one admitted, sample_data
dragged the horizon to 2024-12-20 -- a 600-day horizon, most of it empty
history. The floor now applies unconditionally, falling back to today when no
reference date is given, which is the same default the validator has always
used for its own. Every production path supplies one, so behaviour there is
byte-identical.

TWO FIXTURES WERE BUILDING AGAINST TWO CLOCKS, AND THE RULING IS WHAT
REVEALED IT. Every shipped SolverBuilder caller passes a reference date --
__main__, scenario, sandbox, solution_pool -- but two test fixtures constructed
SolverBuilder() bare while pinning a reference date everywhere else in the same
run. That mismatch was invisible for as long as past-due work was excluded,
because nothing could then drag min(earliest_start) away from the pinned date.
With WO-PAST-001 schedulable it surfaced twice, and neither symptom looked like
a clock problem:

  test_schedule_persist  the extractor's tardiness floor came out None, because
                         the floor is measured from t0 and the builder's t0
                         (2024-12-20) preceded the order's due date. The
                         arithmetic was right; the clock was wrong.

  test_scenario          a 775,841-minute PHANTOM TARDINESS DELTA on a diff
                         whose entire purpose is to compare two solves -- the
                         base built against min(earliest_start) while the
                         scenario re-solve, which reads the date back off M3's
                         config, built against the pinned one.

Both are fixed in the fixtures, which now pass the date they already pinned. The
lesson is worth more than the fix: an unfloored horizon does not fail loudly, it
produces confident numbers measured from a clock nobody chose.

CLAUSE (3)'S GENERAL GUARD is committed in tests/test_pastdue_disposition.py
and it is deliberately ignorant of what past-due means. It asserts a property
of ANY run: a demand the gate passed as proceeded_flagged is either still
schedulable, or was removed by a module that said so, in a record, by name
(excluded_by_module in the finding's evidence). It is checked for NON-VACUITY
in the same file, because a guard that compares two empty sets passes for the
wrong reason -- and the gate speaks submission-space order ids while the rest
of the pipeline speaks canonical UUIDs, so the join is exactly where a silent
vacuous pass would have come from.


======================================================================
5. THE TARDINESS SPLIT, AND A TEST THAT CORRECTED ITSELF
======================================================================

Contract 1.10 -> 1.11. cost_summary gains tardiness_floor and
tardiness_controllable; ServiceOutcomeBlock gains tardiness_floor_min /
tardiness_floor_cost. Present TOGETHER or not at all, summing to tardiness to
the cent, and ABSENT on any book with no past-due demand -- so every monolithic
document with an on-time book is byte-identical to its 1.10 self.

THE SPLIT DOES NOT CHANGE THE MODEL. It makes a decomposition the pipeline
already contained legible. solver_builder has always clamped
due_min = max(0, due - horizon_start), so a past-due fulfillment's objective
term measures completion from t0 -- the CONTROLLABLE part alone -- while the
extractor has always priced lateness from the DECLARED due date. The floor was
never in the objective. Nobody had noticed because no fixture could produce a
past-due order.

THE BRIEF'S STATED TEST WAS THE WRONG TEST, AND THE DATA SAID SO RATHER THAN AN
ARGUMENT. The instruction: solve with the floor included and excluded;
PLACEMENTS MUST BE IDENTICAL, and if they are not, the decomposition is wrong.

First attempt, 60 orders: BOTH arms returned FEASIBLE (gaps 24.6% and 1.0%) and
237 of 240 placements differed. That measures two truncated searches stopping
in different places -- precisely what 4B.10 section 5a.27 measured about seeds
-- and says nothing whatever about an argmin. An argmin claim can only be
tested where the argmin is actually found.

At 12 orders both arms PROVE OPTIMAL:

    arm A (floor excluded -- the shipped clamp)   OPTIMAL   objective   406,973
    arm B (floor included -- clamp removed)       OPTIMAL   objective 7,406,813
    B - A                                                            6,999,840
    predicted sum (weight x floor minutes)                            6,999,840

Placements still differ (34 of 48). That is a TIE, not a refutation. Since
f_B(x) = f_A(x) + C for every feasible x, min f_B = min f_A + C, and observing
precisely that equality is what confirms C really is independent of x; it
follows that argmin f_B == argmin f_A AS SETS -- A's placement is optimal for B
and B's for A, both at cost A*. The two arms returned different members of one
argmin set because a large added constant changes CP-SAT's search trajectory,
not which schedules are optimal.

So placement identity would have been SUFFICIENT but is not NECESSARY, and
requiring it would have manufactured a false failure out of an arbitrary
tie-break. The exact-offset identity is the stronger claim and it holds.
tools/spikes/pastdue_4b11/floor_invariance.py takes its verdict on that, exits
0, and prints the reasoning above so the next reader does not have to
reconstruct it.

WHY THE SPLIT HAD TO EXIST BEFORE THE SCHEDULING CHANGE SHIPPED. On the
regenerated sample_data baseline, WO-PAST-001 is 776,681 minutes late and
776,160 of those are FLOOR. Unsplit, that one order tells a planner their
schedule caused $777,521 of lateness when it caused $521 of it.


======================================================================
6. THE COST PROOF, RENDERED (section 5a.23 DISCHARGED)
======================================================================

4B.10 measured 13.056% of ledger decided by nothing but the solver seed -- four
seeds proving 29,453.35 to the cent, one returning FEASIBLE at 33,298.77 with
an 11.47% gap, every pre-solve quantity identical. The solve knew which it got;
the status field had carried it since 4B.8 CU3; nothing rendered it.

src/mre/modules/cost_proof.py is the single definition, consumed by two
surfaces so they cannot state different things about the same solve.

THE COCKPIT. A chip in the top strip, beside the certificate grade rather than
in a diagnostics drawer, because it qualifies every number on the board. Label
and title are composed SERVER-SIDE and arrive on /meta; the JS composes no
wording at all. Outlined rather than filled, in its own tokens, so it cannot
read as a second grade -- the certificate grade is a statement about the DATA,
this one is about the SEARCH, and reading them as the same kind of claim would
be its own confusion.

    proved     "cost optimum proved"
    unproved   "optimum not proved - gap 20.6%"
    no solve   "no solve"

THE ANSWER SURFACE. An unprompted rider appended by the ONE delivery seam both
renderers share -- the same place apply_repeat_riders lives, and for the same
reason: the template path and the LLM path must not be able to disagree about
whether this schedule's numbers are proven. The rule is deliberately narrow. It
fires only when the board is UNPROVED and the delivered text states money. A
proved board adds nothing, because the strip already says so and a rider on
every answer is noise. "ORD-14 is on M-02" is not a cost claim.

THE ASYMMETRY IS THE POINT: the surface volunteers the thing that WEAKENS its
own number, and stays quiet about the thing that would flatter it.

Every bundle leaving Explainer.route carries the proof, stamped at the ONE
dispatch rather than in forty assemblers -- so a route added tomorrow inherits
it and no assembler can forget. It is read from the M6 solve_complete event,
the same record schedule_assembler._solver_block builds the document's solver
block from, so the board and the answer agree because they read one record
rather than because two derivations were kept in step.

THE ROLLING PATH COULD NOT STATE A GAP AT ALL until this session:
assemble_rolling_document wrote SolverBlock(gap=None) unconditionally, so an
unproved rolling board could say "not proved" and never "by how much" --
precisely the 13.056% that made this urgent. RollingView now carries stage 1's
objective and gap, the M6 event records the gap, and the assembler passes both
through. On the specimen that reads FEASIBLE / gap 20.6%, so the board a
planner would actually be shown is one of the unproved ones.

NO NEW ROUTE WAS BUILT. A planner still cannot ASK "is this optimal?" -- the
intent is not in the closed vocabulary, so the question falls to synthesis,
which cannot see solver.status. That is a vocabulary-class change and the
brief's own instruction was to name the debt rather than bolt a route on at the
end of a session that had already moved a contract. It is docs/07 section
5a.29, with the fix shape written out.


======================================================================
7. THE sample_data BASELINE WAS REGENERATED, AND THE BRIEF'S PREMISE
   WAS WRONG
======================================================================

Acceptance criterion 7 said pilot_scale and every monolithic golden would be
BYTE-IDENTICAL, on the premise that no monolithic fixture carries past-due
work. THAT PREMISE IS FALSE. sample_data carries WO-PAST-001
(ScheduleDate 2025-01-15) as seeded defect 3, and clause (1) schedules it. The
golden could not survive the ruling. Saying so is more useful than a criterion
quietly dropped.

Worth noting: sample_data_v2/DEFECTS.md has declared defect 3's expected
disposition as proceeded_flagged since it was written. The implementation had
drifted to excluded. R-PD1 restores what the catalog said.

THE REGENERATION IS ACCOUNTED FOR BY CONSTRUCTION, NOT BY INSPECTION.
Re-running the exact gate pipeline against sample_data with the single row
WO-PAST-001 REMOVED reproduces the PREVIOUS golden BYTE-FOR-BYTE and its ledger
to the cent:

    total 24,769.00 = production 19,429.00 + setup 4,500.00 + tardiness 840.00

So every difference between the old golden and the new one is attributable to
one order being admitted, and to nothing else in the pipeline. Both runs
reproduce across repeated invocations under pinned determinism.

The new golden:

    total 801,930.00 = production 19,759.00 + setup 4,650.00
                       + tardiness 777,521.00

pilot_scale is untouched, and so is every rolling golden.


======================================================================
8. WHAT WAS TEMPTING AND LEFT
======================================================================

FIXING THE facility_real GENERATOR. 4B.10 recorded that a CONDITIONAL gate
grade "is CORRECT for it (the past-due orders), not a defect". That is wrong,
and inspection of the rule shows why: M0's
ids.order_dates_internally_consistent checks due < release/created, NOT
due < reference_date. The generator writes created_date = ref.isoformat() for
EVERY order, so a past-due order is emitted as created ON the reference date
and due before it -- a genuine date inversion, and the gate is right to flag
it. A real backlog order was created before it was due. This is the same defect
docs/04's 2026-07-10 amendment already fixed once, for the stale_due_dates
anomaly.

It was very tempting: it is a four-line change, it would make facility_real
grade ACCEPTED, and it would remove a spurious CONDITIONAL from a preset added
one session ago. It was left alone because that inversion is what makes the
specimen's M0 proceeded_flagged finding EXIST, and clause (3)'s general guard
needs a live one to be non-vacuous. Fixing both in one session would have left
the guard passing for the wrong reason -- which is the exact failure mode the
guard exists to catch. Reported as section 5a.30 with the constraint that
whoever fixes it must supply the guard a new specimen in the same commit.

IMPLEMENTING CLAUSE (5), THE AGE FINDING. The book's minimum due date is -1573
days, so the distinction between "three days late" and "four years unclosed" is
real and visible in the data. But the threshold is a business judgment only a
human may state, exactly as earliness_value and the coarse zone's
capacity_derate are, and there is no defensible default. Emitting an age
finding with no declared pathway would be evidence with nothing behind it.
Clause (5) is left OPEN, and docs/06 section 5.9 records the full six-step
pipeline-proof chain implementing it would require, so the next session starts
from a specification rather than an intention.

BOLTING ON AN OPTIMALITY ROUTE. The language already exists in
cost_proof.chip() and cost_proof.rider(); adding an intent would have taken
twenty minutes. It is a vocabulary-class change -- Intent, meaning, taxonomy,
offer, assembler, authored copy, a parse-prompt version bump, reviewed and
committed with its doc update -- and the brief said to name it. Named as
section 5a.29.

FIXING scenario.py's --horizon-days EXCLUSION. R-PD1 clause (2) makes it a
named ruling violation rather than an untidy category, and clause (3) makes it
a worse one: it raises NO finding of any kind, so nothing names the module that
removed the demand or the reason. The general guard would catch it if applied
to that path. Out of scope; section 5a.1 is updated to say it is now the same
pattern, on a production entry point.

RUNNING THE r5 BANK. Still deferred, and now further invalidated: the contract
moved to 1.11 and the sample_data baseline was regenerated, so a fresh exam
world differs from the r5 world in more than the card figures. The standing
ordering holds -- re-derive from a fresh world FIRST, then grade.


======================================================================
9. TESTS
======================================================================

    1687 passed, 240 skipped, 0 failed  (full suite, PYTHONHASHSEED=0)

tests/test_pastdue_disposition.py is new: 35 tests over the specimen, covering
clauses (1), (2), (3), (4) and (6), the exclusion arithmetic, and the cost
proof. Its clause (3) guard checks its OWN non-vacuity, because a guard that
compares two empty sets passes for the wrong reason -- and the gate speaks
submission-space order ids while the rest of the pipeline speaks canonical
UUIDs, which is exactly where a silent vacuous pass would have come from.

Tests that asserted the OVERTURNED behaviour were rewritten rather than
deleted, and each carries the ruling that changed it in its own docstring:

    test_validator          TestSeededDefect3_TemporalImpossibility
                            -> TestSeededDefect3_PastDueAtIntake
    test_schedule_persist   TestGhostJobExclusion -> TestPastDueIsScheduled
                            (it now asserts the opposite, and says so)
    test_wip_solver         test_temporal_impossibility_still_fires...
                            -> test_past_due_is_scheduled_whether_or_not_...
    test_integration        defect3 now expects PAST_DUE_AT_INTAKE
    test_dq_report          the report must still MENTION it, under the new code
    test_vocabularies       18 -> 19 codes, with the reason
    test_remediation_catalog  the count assertion now names the invariant it
                            was really testing: every code has an entry, even
                            when that entry's job is to say NO fix applies

Two fixtures were corrected rather than their tests weakened
(test_schedule_persist, test_scenario): both now pass the reference date they
had already pinned, as every shipped SolverBuilder caller does.

The cockpit builds clean (vite). The Playwright screenshot harness and the
--runslow ladder were not run beyond the committed suite.

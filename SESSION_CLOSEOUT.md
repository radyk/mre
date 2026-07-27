SESSION 4B.6 CLOSE-OUT -- THE COARSE ZONE
R-SC2's parked far-horizon look-ahead clause, discharged
2026-07-27

Repo: C:\dev\mre, branch master. Contract 1.8 -> 1.9. IDS registry v0.3 -> v0.4
(35 -> 36 rules). Parse prompt v8 -> v9. docs/07 v2.48; docs/04 two amendments
same date; CLAUDE.md position updated.

All solver work ran deterministic: PYTHONHASHSEED=0, --solver-workers 1, seed 42.

======================================================================
SUMMARY -- claimed vs proven, per CU
======================================================================
  CU1  the coarse model       DELIVERED + a correction to the ruling itself
  CU2  contract 1.9           DELIVERED, with an approved deviation (pre-flight 2)
  CU3  prediction store       DELIVERED (store + skeleton; NOT yet wired to a worker)
  CU4  relaxation guard       DELIVERED + negative control proven red
  CU5  reachability + render  DELIVERED (no R-AI1 debt); band NOT screenshot-tested
  CU6  docs                   DELIVERED (docs/01, 04, 06, 07, CLAUDE.md)

======================================================================
PART 0 -- PRE-FLIGHT FINDINGS (all three, reported explicitly)
======================================================================

TWO OF THE THREE TRIPWIRES FIRED. Both were reported to the working thread
BEFORE any code was written, and the session proceeded on its instruction.

(1) `excluded_demand_ids` DOES appear in the ROLLING path.

    LITERALLY TRUE, SEMANTICALLY NOT. It is a PreparedPlant field
    (rolling_horizon.py:195), defines `schedulable_demands` (:205), is set from
    the validator's result (:262/:288), and is read by the completeness
    invariant (schedule_assembler._assert_rolling_completeness:542,560-562).

    BUT NO ROLLING-PATH SITE EVER WRITES IT. Exclusion is decided in
    validator.py (five sites) and nowhere else on that path. The disposition
    story is therefore exactly as the design believed: gate/validator EXCLUDES,
    the rolling path only CLASSIFIES what survives into committed / active /
    beyond-horizon. The coarse zone's scope (beyond-horizon = schedulable minus
    placed) is unaffected.

    Per the working thread's addition (C), that distinction is now LOCKED WHILE
    IT IS TRUE: test_no_rolling_path_site_writes_excluded_demand_ids fails the
    day someone files horizon work as exclusion.

(2) `earliest_window_estimate` was ALREADY POPULATED -- universally.

    THE DESIGN'S PREMISE WAS FALSE. schedule_assembler._earliest_window_estimate
    (due minus ceil(working_min/720), clamped to the reference origin) is called
    unconditionally for every tray entry; it is absent only when a demand has no
    due date. It has consumers and guards: rolling_questions.py:195 renders it,
    test_rolling_document.py:40 and test_rolling_dispatch.py:188 pin it, and all
    14 tray entries of the committed rolling fixture carry a value.

    CU2 as briefed would have SILENTLY REPURPOSED a live field whose meaning is
    a different method's estimate. Reported and stopped before overwriting.
    RULED IN-SESSION: the coarse bucket sits BESIDE it as
    BeyondHorizonItem.coarse; earliest_window_estimate is byte-unchanged, and a
    test asserts it field-by-field against the original function.

(3) The gravity setup-family-affinity debt WAS already recorded.

    docs/04 carries an explicit "Named debt -- per-component gravity ablation"
    block (4B.2c amendment, ~line 6710) and docs/07 mentions it at v2.31/v2.32.
    The brief's "record it if it exists only in close-out prose" clause
    therefore did NOT fire.

    It was NOT in CLAUDE.md's carry-forward list. Since this session built a
    mechanism adjacent to gravity, it is now in CLAUDE.md and in the new
    docs/07 section 5a.

(A) SECOND FINDING, unasked, reported per the working thread's instruction:
    `--horizon-days` writes `excluded_demand_ids`.

    (i)   PRODUCTION path, not scenario generation. src/mre/__main__.py:251-300
          adds every demand due beyond reference_date + N days to
          v_result.excluded_demand_ids, and it is reachable through the API
          (SolveRequest.horizon_days -> app.py:854-855). scenario.py:278-293
          only REPRODUCES the base run's slice for what-if parity.
    (ii)  YES, precisely. What it removes is demand due beyond the horizon --
          exactly the population the coarse zone exists to price. On that path it
          is filed in the same set that carries gate exclusions: a horizon
          category shelved as a DATA-DEFECT category. It is not silent (a
          MODEL_SIMPLIFICATION / POLICY_RULE Decision records the deferred
          count), but the shelf is wrong: a demand deferred by a planning horizon
          is not a demand we could not read.
    (iii) NOT reachable from a rolling run. app._execute_rolling_solve goes
          through prepare_plant / build_rolling_view and never passes
          --horizon-days; only the monolithic worker does. The coarse zone is
          NOT starved by it.

    RECORDED as docs/07 section 5a item 1 with its fix shape, plus one line in
    CLAUDE.md. NOT FIXED -- out of scope, as instructed.

======================================================================
PART 1 -- PER-CU: CLAIMED vs PROVEN
======================================================================

----------------------------------------------------------------------
CU1 -- THE COARSE MODEL (src/mre/modules/coarse_horizon.py)
----------------------------------------------------------------------
CLAIMED: a bucketed relaxation over every op of every beyond-horizon demand;
declared bucket length; real calendar minutes as a number; eligibility by
variable existence; coarse precedence; bucket tardiness; two runs per slice;
unmodelable ops flagged and named; determinism.

PROVEN:
  * Built and running on a real plant. 40-order pilot_scale, window 7 / frozen 2:
    38 beyond-horizon demands, 83 ops in scope, 82 modeled, 1 unmodelable.
  * Capacity is REAL working minutes -- a unit test asserts a 5-day 07:00-19:00
    calendar yields 5x720 = 3600 min/week and is strictly less than 7x1440. A
    resource with no resolvable calendar gets FULL wall-clock minutes, which is
    deliberately permissive (zero would tighten and break clause 1); also tested.
  * Eligibility carried by VARIABLE EXISTENCE -- no variable is created for an
    ineligible (op, res) pair, so the aggregation error is structurally
    unrepresentable. The guard checks it independently.
  * Two runs per slice, both persisted. proves_infeasible is the ONLY gate the
    negative escapes through -- four unit tests: complete proof (True), planning
    (False), wall-truncated (False), FEASIBLE (False).
  * CROSS-HASHSEED DETERMINISM PROVEN (PYTHONHASHSEED 0/1/2, three subprocesses,
    digest over both runs' placements plus the certificate block). Not
    same-seed-both-sides.
  * A MEASURED PROPERTY, pinned as a test: the derate is NON-MONOTONIC. rho 0.20
    OPTIMAL (82 ops), rho 0.15 INFEASIBLE (80 ops), rho 0.10 OPTIMAL with 19 ops
    gone as exceeds_bucket_capacity. Below a threshold, ops stop fitting in ANY
    single derated bucket and LEAVE the model. Without the unmodelable COUNT the
    0.10 result reads as "it fits".

CORRECTION TO THE RULING, found in implementation and recorded in docs/04:
  The ruling asserts that all three out-of-scope omissions "relax in the
  PERMISSIVE direction, which is what keeps clause (1) true". For
  family-presence setup and the makespan bound that holds. For CROSS-BUCKET
  ALLOCATION OF RESUMABLES IT DOES NOT: forcing a splittable op into one bucket
  is a TIGHTENING against a fine model that may split it across a boundary, so
  the claim would have been FALSE rather than merely unproven. Resumable ops are
  therefore EXCLUDED outright under the named sub-disposition
  coarse_unmodelable(resumable_out_of_scope) -- a CONSTRUCTION that makes clause
  (1) true, rather than an assertion that it already was.

UNDERDELIVERED / NAMED:
  * coarse_horizon.py carries its OWN narrow CP-SAT surface (confined to
    _solve_coarse). CLAUDE.md quarantines ortools to solver_builder /
    solve_runner. This is a STATED DEVIATION -- in the module docstring, docs/04
    and CLAUDE.md -- not an oversight. Nothing there returns an ortools type.
  * At 200 orders the proof run returns FEASIBLE, not OPTIMAL, within its
    deterministic budget: its tardiness is an UPPER BOUND. The contract carries
    figures_are_upper_bounds and every surface states it, but the session did NOT
    tune a budget that reaches OPTIMAL at that size.

----------------------------------------------------------------------
CU2 -- CONTRACT 1.8 -> 1.9 (additive)
----------------------------------------------------------------------
CLAIMED: beyond-horizon entries gain coarse placement; earliest_window_estimate
populated from the coarse bucket; monolithic goldens byte-identical.

PROVEN:
  * CoarsePlacementBlock (start bucket + its dates, completion bucket, resource
    WITNESS, coarse tardiness in BUCKETS, run_label, sub_disposition, named
    unmodelable reason) and CoarseZoneBlock (both coefficients WITH PROVENANCE,
    bucket grid, per-run status, infeasibility_proven, figures_are_upper_bounds,
    wall_truncated, unmodelable_count, density band, binding cells). Both
    Optional, both None when the coarse zone did not run.
  * CLAUSE (5) ENFORCED BY SHAPE: a test asserts no currency field exists
    anywhere on the coarse surface, so no consumer can sum coarse into
    cost_summary even by accident.
  * MONOLITHIC GOLDENS: UNAFFECTED and verified. They are schedule.csv
    byte-comparison plus the cost ledger (test_defaults_reproduce_baseline), not
    document JSON. The coarse blocks are unreachable on that path -- a monolithic
    document has no RollingBlock -- and that is asserted structurally.
  * Contract docstring updated in the same commit.

DELIBERATE DEVIATION FROM THE BRIEF (approved in-session, see pre-flight 2):
  earliest_window_estimate is NOT populated from the coarse bucket. It keeps its
  1.7 meaning; the coarse bucket is a SEPARATE field. A test asserts the
  heuristic is byte-unchanged for every tray entry.

----------------------------------------------------------------------
CU3 -- PREDICTION PERSISTENCE + THE CONFORMANCE SKELETON
----------------------------------------------------------------------
CLAIMED: ships in THIS unit, not later. Non-negotiable.

PROVEN -- SHIPPED (src/mre/modules/coarse_predictions.py):
  * Append-only JSONL store under the run dir, keyed (run_id, demand_id, op_id,
    bucket_index, resource_witness, run_label), plus sweep_data_root for the
    cross-roll read the document cannot provide (the document is a window-0 view
    by ruling; the audit is inherently cross-roll). Round-trip tested.
  * BOTH INTAKE PATHS. rolling_horizon.gravity_admitted_demand_ids (new, pure
    arithmetic over _admit, feeding NOTHING back into admission) supplies path
    (b) as a FACT FROM THE ADMISSION MECHANISM rather than an inference from the
    gap's sign. Both the path and the gap are recorded per realization, so a
    gravity disagreement is stored as what it is: two mechanisms on record
    disagreeing about the same job.
  * A mirrored planning run (rho == 1.0: the model is byte-identical and is
    COPIED, not re-solved) is EXCLUDED from prediction minting -- recording it
    would double-count the proof run in every error bar. CoarseRun.mirrors_proof
    says so on the surface, and a test pins it.
  * The report skeleton computes the four named figures and SAYS WHEN A FIGURE IS
    UNDEFINED rather than printing a confident 0 (tested).

UNDERDELIVERED, and stated by the report about itself:
  * Slip attribution is CONSERVATIVE and mostly returns `unattributed`. A
    confident attribution needs the FINE solve's binding constraints, which this
    store does not carry. The report emits a note saying exactly that when every
    slip is unattributed.
  * The coarse-vs-fine cost error is computed ONLY when the fine figure is
    supplied in BUCKETS. Clause (5) forbids fusing the ledgers, so the comparison
    is made in the coarse unit or not at all; otherwise the report says why.
  * THE STORE SHIPS BUT NO ROLL HAS WRITTEN TO IT IN PRODUCTION -- the wiring into
    the API rolling worker is NOT done. The honest limit: the mechanism exists and
    is tested, the history does not exist yet. Six weeks of history is recoverable
    from here; it was not before.

----------------------------------------------------------------------
CU4 -- THE RELAXATION GUARD
----------------------------------------------------------------------
CLAIMED: a property test making clause (1) a theorem; a negative control proving
it can fail; a second test showing rho < 1 can declare a fine-feasible instance
infeasible.

PROVEN -- all three, with numbers:
  * GUARD: a fine-feasible schedule from reference_solve maps to a coarse
    allocation and is coarse-FEASIBLE at rho = 1.0. Measured: 87 ops mapped, 1
    excluded as unmodelable (COUNTED, not silently skipped), 0 violations.
  * NEGATIVE CONTROL: a stubbed capacity tightening (_capacity_scale, which
    exists for no other purpose and says so in its docstring) makes the guard go
    RED with 13 violations, at least one of class `capacity:`. The guard CAN fail.
  * CLAUSE (2)'s NECESSITY, demonstrated not asserted: at rho = 0.15 the planning
    run returns INFEASIBLE with 80 of 82 ops STILL MODELED -- so the verdict is a
    real aggregate-capacity refutation, not an artifact of ops dropping out -- on
    the same instance the proof run places comfortably. proves_infeasible is
    False for it.

(B) THE SET IS NON-TRIVIAL -- COUNT STATED, as instructed:
  * 38 beyond-horizon demands; 83 coarse ops in scope (82 modeled, 1
    unmodelable). Floors asserted (MIN_BEYOND_DEMANDS=10, MIN_COARSE_OPS=25) so
    the suite cannot go green over an empty tray.
  * STATED HONESTLY: at this density the plant is FAR TOO LIGHT for the coarse
    zone to bind. Total load is ~8% of derated capacity (17,991 min against
    225,360), coarse tardiness is 0, and no cell reaches capacity. At 200 orders
    it bites properly: 404 ops, 123 bucket-tardiness, cells at ~100%, and rho =
    0.5 goes INFEASIBLE. The teeth at 40 orders come from the clause-(2) and
    non-monotonicity tests, NOT from the headline guard.
  * The (A) horizon cutoff is NOT what starves it -- --horizon-days is not
    reachable on the rolling path, so there is no second count to report.

----------------------------------------------------------------------
CU5 -- REACHABILITY (R-AI1) + RENDERING
----------------------------------------------------------------------
CLAIMED: three questions answerable; name the R-AI1 debt where the taxonomy does
not reach; a density band, never a bar; tokens.

PROVEN:
  * Two intents join the CLOSED vocabulary as a reviewed vocabulary-class change,
    registered at ALL SIX sites (Intent, INTENT_MEANINGS, ROUTE_TAXONOMY,
    ROUTE_OFFERS, ROLLING_INTENTS, ROLLING_ROUTES) with parse prompt bumped
    v8 -> v9 and its reasoning recorded in the prompt's own version log. A test
    asserts every site carries them AND that the prompt was bumped.
  * "will it fit?" -- PROOF RUN ONLY. A proven negative answers "No -- and this
    one I can prove" and names the resource-week with its load and capacity. A
    proof run that PLACES the book is NOT converted into a yes: the answer says
    it "can only ever prove that something DOESN'T fit, never that it does". A
    truncated check refuses both ways. All asserted.
  * "why is week N full?" -- the binding constraint stated as ARITHMETIC (load
    against derated capacity), with rho and its PROVENANCE in every capacity
    sentence. An unfull week is not called full (asserted).
  * "when will ORD-X start?" -- NO NEW ROUTE, deliberately. It is already
    why-not-scheduled-yet, whose answer now carries the coarse bucket BESIDE the
    due-date heuristic; the resource WITNESS is never voiced (asserted).
  * NO R-AI1 DEBT IS LEFT OPEN: all three shapes reach the taxonomy.
  * A test asserts no coarse answer mentions money -- clause (5) at the language
    surface, not just the schema.
  * RENDERING: src/cockpit/src/coarse.js docks a density band -- a resource x
    bucket grid whose cell ALPHA carries utilization, every cell's arithmetic in
    its tooltip, never on the timeline, no drag affordance, and a probe() that
    asserts zero bar elements. Vite build clean (33 modules). All new
    colour/spacing/motion are design tokens (tokens.css + both themes).

UNDERDELIVERED:
  * The band has a probe() but NO PLAYWRIGHT SCREENSHOT TEST. The cockpit harness
    was not extended: the committed rolling fixture predates the 2026-07-26
    determinism fix and does not reproduce (a carried 4B.5 debt), so no fixture
    carries a coarse_zone to screenshot. The band is verified by build + probe
    shape only, NOT VISUALLY.
  * Feel is Daryn's at the panel, as instructed -- tokens are placed, values are
    a first pass.

----------------------------------------------------------------------
CU6 -- DOCS
----------------------------------------------------------------------
PROVEN:
  * docs/04: the R-SC2 amendment transcribed VERBATIM under its own dated
    heading, plus the full session amendment (pre-flight findings, the ruling
    correction, per-CU detail, measured numbers). Append-only respected.
  * docs/06: rho as a declared coefficient with the section-8 PIPELINE-PROOF rule
    satisfied IN FULL -- doorway (5.9 example + prose), gate check
    (ids.coarse_horizon_coefficients_sane), adapter translation with truthful
    provenance, generator scenario with truth manifest (pilot_scale declares
    bucket_days 7 / capacity_derate 0.85) AND an anomaly generator
    (bad_coarse_horizon: a percentage where a fraction belongs), plus a
    schedule-level assertion. Registry v0.3 -> v0.4, 35 -> 36 rules, with the
    count assertions and the docs/06 header moved together.
  * docs/01: two CostModel attribute rows, both Optional-with-null so a numeric
    default cannot erase the declared/defaulted distinction.
  * docs/07: v2.47 -> v2.48 entry, plus a NEW section 5a "Carry-forwards owned
    here" holding all six named debts with reasoning and fix shapes.
  * CLAUDE.md: position, coarse-zone summary, quick reference, and the debts.
    24,004 chars against the 40k ceiling.

======================================================================
PART 2 -- ACCEPTANCE, ITEM BY ITEM
======================================================================
1. Monolithic goldens byte-identical.                            MET.
   test_defaults_reproduce_baseline green; coarse blocks unreachable on that
   path and asserted structurally.
2. The 4B.3a completeness invariant passes unchanged.            MET.
   NOT weakened. An unmodelable op keeps its demand's beyond-horizon
   disposition, so the counting test passes as written.
3. CU4's guard passes AND its negative control goes red.         MET.
   0 violations green / 13 violations red under the stubbed tightening.
4. Cross-hashseed determinism on both coarse runs.               MET.
   PYTHONHASHSEED 0/1/2, digest over both runs' placements + certificate.
5. Coarse and fine currency in separate ledger lines; no fused   MET.
   figure anywhere, including the AI layer.
   Enforced BY SHAPE (no currency field on the coarse surface at all) and
   asserted at the language surface too.
6. rho appears in the certificate; a hidden default is a         MET.
   failure.
   certificate_block carries value AND provenance; the defaulted rho is 1.0,
   a NO-OP derate, so an undeclared plant gets no invented margin.
7. Pre-flight findings reported explicitly, all three.           MET. Part 0.

======================================================================
PART 3 -- TEST RESULTS
======================================================================
FINAL: 1614 passed, 227 skipped, 0 FAILED. Run TWICE, independently, after the
last code edit -- 636s and 670s. Both clean.

Mid-session the suite showed 5 failures; all five are fixed and accounted for:
  * FOUR were contract-version string assertions (1.8 -> 1.9) in
    test_api_endpoints / test_rolling_document / test_schedule_document.
  * ONE was the declared-but-unread ARCHITECTURAL GUARD, and IT WAS RIGHT: the
    two new CostModel attributes are read by coarse_horizon, which sits outside
    the fine pipeline BY DESIGN under clause (4). Resolved with a
    dormant-register entry citing the real consumer AND the clause -- NOT by
    widening the guard's consumer list, which would have blurred exactly the
    distinction clause (4) exists to hold.

Coarse suite:      tests/test_coarse_horizon.py -- 47 passed (28 fast + 19 slow,
                   --runslow, 392s).
Cockpit:           vite build clean, 33 modules transformed.
Doorway, live:     the gate rule was exercised end-to-end on a generated
                   submission -- clean pilot_scale ACCEPTED with
                   capacity_derate 0.85; the bad_coarse_horizon anomaly
                   (a percentage where a fraction belongs) -> CONDITIONAL with
                   a VALUE_OUT_OF_RANGE finding naming the derate; and the
                   declared 0.85 / 7d arrives at CoarseCoefficients with
                   DECLARED provenance through gate -> adapter -> CostModel.

NOT RUN: the cockpit Playwright screenshot ladder (no fixture carries a
coarse_zone -- see CU5).

======================================================================
PART 4 -- OUT OF SCOPE (named, not built) -- honored
======================================================================
* Setup in the coarse model; cross-bucket allocation for resumables (EXCLUDED
  and named instead -- see the CU1 correction); the WP makespan bound. Gated on
  CU3 data; recorded in docs/07 5a.4.
* Any coupling from coarse output into gravity admission (clause 4). Enforced as
  an import-direction test; the UNLOCK CONDITION is written down in docs/07 5a.3
  so a future coupling is a decision, not a drift.
* Accept/publish splicing seams 1, 3, 5.
* Rendering-model changes beyond the density band.
* The --horizon-days exclusion mis-shelving: NAMED, not fixed, as instructed.

======================================================================
PART 5 -- EVERY DEBT NAMED HERE ALSO LANDS IN docs/04 OR docs/07
======================================================================
A debt named only in close-out prose does not exist. Checked, same commit:

  ortools deviation in coarse_horizon      -> docs/04 amendment + CLAUDE.md
  resumable exclusion / ruling correction  -> docs/04 amendment (its own block)
  --horizon-days mis-shelving              -> docs/07 5a.1 + CLAUDE.md
  gravity per-component ablation           -> docs/07 5a.2 + CLAUDE.md
  coarse-to-gravity unlock condition       -> docs/07 5a.3
  three deferred coarse refinements        -> docs/07 5a.4 + CLAUDE.md
  coarse unexercised at demo density       -> docs/07 5a.5 + CLAUDE.md + docs/04
  slip attribution mostly unattributed     -> docs/07 5a.6 + CLAUDE.md + docs/04
  CU3 store not yet wired into the worker  -> docs/04 CU3 limits + this close-out
  no screenshot test for the density band  -> docs/04 CU5 + this close-out
  proof run FEASIBLE not OPTIMAL at 200    -> docs/04 CU1 + the contract field

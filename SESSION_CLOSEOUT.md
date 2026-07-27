SESSION 4B.6a CLOSE-OUT -- CONSOLIDATION
Wire the history, voice the exclusions, move the goldens once
2026-07-27

Repo: C:\dev\mre, branch master. docs/07 v2.49; docs/06 v0.6a; docs/04 one
amendment same date; CLAUDE.md position, quick reference and carry-forwards
updated.

All solver work ran deterministic: PYTHONHASHSEED=0, one worker, seed 42, with
wall ceilings kept generous so the DETERMINISTIC budget is what binds.

This session shipped NO new capability. Its product is that three carried debts
stopped compounding and one measurement landed.


======================================================================
CU1 -- WIRE THE PREDICTION STORE
======================================================================

CLAIMED: a rolling solve that runs a coarse zone mints predictions and judges
earlier rolls' predictions against this window; three constraints tested;
accrual proven over consecutive rolls with the record count stated.

PROVEN. tests/test_coarse_history_wiring.py -- 7 slow tests, green.

What was built:
  * coarse_predictions.record_roll_history() -- the ONE entry point the rolling
    worker calls, strictly AFTER the document is assembled, persisted and
    registered. It never raises. (The orchestration lives in the module, not in
    app.py, so the API surface stays thin.)
  * app.py _execute_rolling_solve builds the zone when asked, passes it to the
    assembler, then records history as a side-channel.
  * Two new SolveRequest fields, named rather than smuggled:
      coarse          -- the coarse zone was module-level only; now opt-in per
                         solve, so a rolling run can publish the 1.9 blocks.
      reference_date  -- before this, EVERY solve of a submission used the
                         manifest's date, so two solves rendered the SAME window
                         and the plant never actually rolled. Cross-roll history
                         cannot accrue against a clock that does not move.
  * CoarseRealization gained run_label + key(). With rho declared below 1.0 the
    proof and planning runs BOTH predict the same op; without the label their
    two realizations are indistinguishable rows and the dedup collapses them.

(a) DOCUMENT BYTE-IDENTICAL, store on and off -- PROVEN.
    Two full worker runs of the same submission at the same reference origin,
    one with record_roll_history replaced by a no-op. Exactly TWO fields are
    normalized before the comparison: run_id and schedule_id, the two the
    registry mints per run and cannot repeat. Nothing else. The test also
    asserts the two data roots really did differ in what was written, so it
    cannot pass by both sides writing nothing.

(b) WRITE FAILURE LOSES NO SCHEDULE AND IS NOT SWALLOWED -- PROVEN.
    OSError injected into record_predictions. The run stays SUCCEEDED; the
    schedule is registered and readable with its coarse zone and its assignments
    intact; the failure is on run.result.coarse_history.error and a WARNING is
    logged. Silent failure here would be worse than no store at all -- it
    manufactures a false belief that history is accruing.

(c) BOTH INTAKE PATHS, END TO END THROUGH THE WORKER -- PROVEN.
    Not the unit-level substitute. The gravity-admitted set is read from
    rolling_horizon.gravity_admitted_demand_ids -- a FACT from the admission
    mechanism, never inferred from a gap's sign.

IT ACCRUES -- RECORD COUNTS STATED.
pilot_scale 40 orders, window 7 / frozen 2, ONE data root, three rolls:

    roll 0 (2026-01-05)   164 predictions written     0 judged
    roll 1 (2026-01-12)    64 predictions written   100 judged
                             -- 62 natural roll, 38 GRAVITY ADMISSION
    roll 2 (2026-01-19)     0 predictions written    80 judged (128 pending)

    store after three rolls: 228 predictions, 180 realizations,
    ZERO duplicate realization keys (a prediction is judged exactly once,
    however many rolls sweep past it).


======================================================================
CU2 -- VOICE WHAT WAS NOT COUNTED
======================================================================

CLAIMED: every capacity answer that states load or utilization names the
uncounted population, both directions tested; the band tooltip carries the same
caveat; the absent derate is loud and is NOT a gate finding.

PROVEN. tests/test_coarse_horizon.py (TestUncountedPopulation,
TestNoDerateDeclared -- 11 new tests) + tests/cockpit/coarse.spec.mjs.

(a) Every capacity-answer branch now names it: how many ops, and that their
    MINUTES are counted in no figure above. Four branches covered, including the
    zero-load one -- "nothing lands in that week" is the most misleading
    sentence to say over a partial population. BOTH DIRECTIONS tested: the
    caveat is present when unmodelable_count > 0 and absent when it is 0.

    On the PROVEN-INFEASIBLE branch the exclusion is named in the HONEST
    DIRECTION -- leaving work out can only make a refutation stronger, never
    weaker -- so the caveat does not read as a hedge on a proof.

(b) The density band's per-CELL tooltip carries it, not only the footer: a
    planner reading one cell would otherwise never see it. The band's probe
    reports unmodelableCount and cellsWithUncountedNote so the harness asserts
    EVERY cell has it, not just that the band mentions it somewhere.

(d) NO DERATE DECLARED is loud in three places: a coarse_capacity_derate_note on
    the certificate's coefficient block, the band header ("no capacity margin
    declared -- figures assume every available minute is usable"), and every
    capacity answer, which also names the remedy. No default margin is invented:
    clause 3 stands and the defaulted rho is still 1.0.

    NOT A GATE FINDING -- PROVEN. The registry stays at 36 rules (asserted). A
    real gate run over clean_small, which declares nothing, stays ACCEPTED with
    ids.coarse_horizon_coefficients_sane silent. The entry is an INFORMATIONAL
    remediation note in docs/06 sec 5.9, not a registry rule -- and it could not
    have been a catalog note either: test_no_orphan_rule_notes requires every
    catalog note to name a registry rule, which is exactly the discipline that
    keeps "informational" from quietly becoming "checked".


======================================================================
CU3 -- PIN THE BINDING BEHAVIOUR
======================================================================

CLAIMED: a slow deterministic 200-order test asserting cells reach capacity,
bucket-tardiness nonzero, rho 0.5 INFEASIBLE; and the non-monotonicity property
still pinned and still passing at this density.

PROVEN, with one qualification stated rather than smoothed.
tests/test_coarse_binding.py -- 5 slow tests, 4m29s, green.

Measured, and asserted as SHAPE and thresholds set well clear of the figures so
an ordinary solver tie cannot move them:

    157 beyond-horizon demands; 408 coarse ops (404 modeled, 4 unmodelable)
    peak machine-week utilization 0.998; 9 binding cells
    coarse tardiness 123 buckets over 41 demands; status FEASIBLE, so the
      figures are flagged UPPER BOUNDS
    rho 0.5 INFEASIBLE with all 404 ops STILL MODELED -- an aggregate-capacity
      refutation, not ops leaving the model -- and proves_infeasible False,
      because it is a planning run

All four reproduce 4B.6's prose figures exactly.

THE QUALIFICATION: the 40-order non-monotonicity STATUS LADDER (0.20 OPTIMAL /
0.15 INFEASIBLE / 0.10 OPTIMAL) does NOT reproduce at 200 orders -- all three
are INFEASIBLE, the book being far too heavy for the leftovers to fit either.
What the 40-order test actually PINS is the MECHANISM, and both of its
assertions hold here: 0.15 INFEASIBLE (393 modeled, 11 exceeds_bucket_capacity)
and 0.10 pushing more ops out (357 modeled, 47). The 40-order test remains the
pin for the status ladder.


======================================================================
CU4 -- THE GOLDENS MOVE (the highest-risk work in this session)
======================================================================

CLAIMED: regenerate tests/cockpit/fixtures/rolling/ under one-time
authorization, account for EVERY moved figure, replace the synthesized
attribution split with real figures, add the band's screenshot coverage, re-run
the full cockpit ladder both themes.

PROVEN. No unexplained movement; the session did not halt.


--- Step 1: BEFORE digests (sha256, first 16 chars) ---

    schedule.json     908f9f8e4f17ba52
    sandbox.json      19bbe81d4aa4ca30
    feasibility.json  4d398e11916b59e5
    gesture.json      5128886ca98a0b71
    interaction.json  d2906b1e52c94cd0
    meta.json         9d2bbb4ec218c1f1
    asks.json         66efa92a5fe6b92f

--- Step 2: AFTER digests ---

    schedule.json     64cd69f051d631cf
    sandbox.json      eccb1bcba592c7aa
    feasibility.json  338c0bf124830637
    gesture.json      bf2e67f18dd17ce9
    interaction.json  b07b97c40e43db36
    meta.json         b5d017280a33f5e6
    asks.json         efe6fbaf3d7acc75

    Same scenario (pilot_scale, 40 orders, seed 1), same reference origin
    (2026-01-05), same window 14 / frozen 3, deterministic seed 42.


--- Step 3: THE ACCOUNTING -- every moved figure ---

A positional diff reported 639 moved values, which tells you nothing once a list
is ordered differently. Keyed BY OPERATION IDENTITY the picture is exact:

    56 assignments before, 56 after -- THE SAME 56 OPERATIONS.
    None arrived. None left.
    The same 26 orders on the board.
    The same 14-order beyond-horizon tray, order for order.
    Of the 56: 3 changed machine, 49 changed start, 16 changed commitment state.

Every difference attributes to one of the two permitted causes.

CAUSE 1 -- CONTRACT 1.8 -> 1.9, ADDITIVE FIELDS.
    contract_version 1.8 -> 1.9 (schedule.json and meta.json)
    + rolling.coarse_zone                  (1 added key)
    + rolling.beyond_horizon[i].coarse     (14 added keys, one per tray item)
    ZERO keys were REMOVED from schedule.json.

CAUSE 2 -- THE 2026-07-26 DETERMINISM FIXES.
    The committed schedule.json was built at Session 4B.3c (commit 4301e6f),
    BEFORE the determinism errand (commit 65982e5). This accounts for:

        rolling.committed_count              38 -> 42
        rolling.active_count                 18 -> 14
        cost_summary.production_regular  14466.95 -> 14381.40
        cost_summary.tardiness            9800.83 -> 11975.83
        cost_summary.total               26507.78 -> 28597.23

    and, downstream of the changed board, every identity in gesture.json,
    feasibility.json, sandbox.json, interaction.json and asks.json -- the
    gesture op moved from 8ad19d5c to 2a163c51 because the board it is picked
    from changed, and the canned "why is ORD-000021 on CUT-01" became
    ORD-000027 for the same reason.

THE COST FIGURES ARE FIGURES THAT SHOULD NOT HAVE DEPENDED ON ORDERING, so
"the fixture was stale" was NOT accepted as their explanation. Three things
were established instead:

  1. AN ATTRIBUTION EXPERIMENT, to separate the two candidate causes.
     Rebuilt under the CURRENT code at the OLD 10s wall ceiling: the split is
     ALSO 42/14, and wall_truncated comes back True. So raising the ceiling is
     NOT the mover -- it only removes the truncation flag, i.e. it changes the
     CLAIM the fixture can make, not the numbers. The ordering fixes are the
     mover.

  2. WHY A COST FIGURE CAN MOVE AT ALL. solver.status is FEASIBLE, not OPTIMAL.
     The cost is an INCUMBENT, and which incumbent CP-SAT returns is a function
     of variable-creation order -- precisely what was hash-dependent before
     2026-07-26 and is explicitly sorted now. Two legitimate incumbents of a
     search that never proved an optimum.

     NAMED, NOT GLOSSED: the regenerated incumbent is ~7.9% DEARER than the one
     it replaced. That is a real change in what the demo board shows. It is
     recorded in docs/07 sec 5a.9.

  3. THE NEW FIXTURE REPRODUCES -- which is what the debt was actually about.
     A digest over committed + active placements, the tray, the cost ledger and
     the coarse certificate is IDENTICAL across PYTHONHASHSEED 0 / 1 / 2:

         4863367aa342f96d6334ee4f7660b30d62e995d3664d5a66c468d7ddb0ebe1ed

     Two independent full regenerations produced BYTE-IDENTICAL schedule.json,
     interaction.json, gesture.json, meta.json and asks.json. The ONLY bytes
     that differ between passes are elapsed-time measurements (wall_time_s and
     baseline_wall_time_s in sandbox.json / feasibility.json) -- measurements of
     the machine, which cannot be deterministic. They are deliberately NOT
     normalized away, because a synthesized zero there is precisely the defect
     step 4 removes.


--- Step 4: THE SYNTHESIZED ATTRIBUTION SPLIT IS GONE ---

4B.5 hand-inserted reopt_delta_abs -9500.0 / move_delta_abs -294.53 into the
fixture because it could not be regenerated, so the decomposition-sums invariant
had NEVER ONCE run against numbers a solver produced. The regenerated card
carries a real sandbox_pin_resolve(baseline=True) -- two solves of the same
window, one with the pin and one without:

    total  -11953.08  =  reopt  -11975.83  +  move  +22.75
    baseline_total_cost 16621.40, baseline_wall_time_s 0.987

Note the shape, which the synthesized pair could not have shown: a move that
COSTS money sitting inside a re-optimization that saves it. That is exactly the
confusion 4B.5 CU1 existed to end.

tests/cockpit/attribution.spec.mjs now asserts the sum ON THESE FIGURES, asserts
the two synthesized values are gone (a guard against a future hand-edit
restoring them), asserts a real baseline solve happened (baseline_wall_time_s >
0), and asserts an "unavailable" card stays UNSPLIT rather than half-split.


--- Step 5: THE DENSITY BAND'S FIRST SCREENSHOT COVERAGE ---

tests/cockpit/coarse.spec.mjs -- 5 tests x 2 themes, green. Screenshots written:
cb1_band_populated, cb2_band_empty, cb3_band_binding_cell (each __light/__dark).

    POPULATED -- a grid of load cells and ZERO bar elements (clause 6); the
                 title reads "load, not placement"; the word "scheduled" appears
                 nowhere in the band.
    EMPTY     -- a coarse zone over an empty tray renders its header and no
                 rows: it claims nothing rather than hiding.
    BINDING   -- a hot cell's tooltip states load against DERATED capacity in
                 minutes with its percentage, says "not a placement", and
                 carries the CU2(b) uncounted caveat -- on every cell, not just
                 in the footer.
    plus      -- the derate provenance is asserted on the band (clause 3), and
                 a band with nothing excluded is asserted to invent NO caveat.

The binding state needed a fixture that binds, and the real board does not: at
the plant's declared 0.85 the demo book loads the coarse zone to a few percent
and no cell is hot. A NEW fixture set was added -- rolling_coarse_hot/, the SAME
40-order plant with a DECLARED derate of 0.10: 18 density cells, 5 binding cells
(0.958 to 1.000), unmodelable_count 5, tardiness 3 buckets, and both tray
sub-dispositions present. It is an ADDITION, not a moved golden. The real board
keeps its real 0.85 and its zero binding cells -- which is what makes the
"invents no caveat" direction testable on the same run.

rolling_empty/ now also carries a coarse zone; its tray is blanked BEFORE the
zone is built, so the empty band matches the tray it belongs to rather than
showing load for orders the document says are not there.


--- SCOPE NOTE: rolling_empty/ ALSO MOVED, and it is disclosed here ---

The authorization named tests/cockpit/fixtures/rolling/. rolling_empty/ moved
too, because CU4 step 5 requires an EMPTY-BAND screenshot and a band cannot be
empty in a document that carries no coarse zone at all -- so that fixture had to
gain one. It is a consequence of the CU's own step 5, not a second golden taken
on the side, and it is accounted for to the same standard:

    schedule.json  85518088c90e045d -> b228fd9c86e1f298
    meta.json      fd2cbb29b284f8fe -> ddfe8c9bcfdd967a

    THE SAME 18 operations, none arrived, none left.
    committed/active unchanged at 18 / 0. Tray unchanged at 0. Tardiness
    unchanged at 0.00.
    5 of the 18 ops swapped (machine, start) -- the same tied-incumbent
    ordering class as above -- moving production_regular by +$7.65
    (5251.08 -> 5258.73, 0.15%).
    ADDED: rolling.coarse_zone (2 buckets, 0 density cells, 0 binding, 0
    unmodelable -- which IS the empty state) and contract_version 1.8 -> 1.9.
    ZERO keys removed.

No other golden moved. tests/cockpit/fixtures/rolling_coarse_hot/ is a NEW
fixture set, not a moved one.


--- Step 6: THE FULL COCKPIT LADDER, BOTH THEMES ---

    225 passed (3.7m) -- including the 10 new coarse-band tests and the 2 new
    real-figure attribution tests.


--- Two incidental fixes found doing this work ---

  * build_rolling_fixture.py now RAISES on a wall-truncated view or coarse run.
    A fixture that cannot be reproduced is not a golden.
  * Its print strings became plain ASCII. The tool DIED mid-run on a cp1252
    console at an arrow character -- the same defect class an earlier errand
    fixed elsewhere, found here only because the tool was finally run.


======================================================================
CU5 -- THE r5 CORPUS BANK
======================================================================

(a) DELIVERED. The bank gains the question CU5 named: with a delta card open,
    ask what the MOVE cost. The bank is now 27 questions.

    This is the untested intersection of 4B.5's CU1 and CU2. The runner's
    synthesized card carries total -11,975.83 = reopt -11,600.00 + move
    -375.83, and the substantive expectation written into the bank is that the
    answer voices 375.83 as what the move cost and names 11,600.00 as the part
    the planner did not cause. If it voices the TOTAL, the defect the card fixed
    is alive in the conversational channel and the two surfaces state different
    things about one move.

(b) NOT DELIVERED. HALTED per CU5(c).

    NO ANTHROPIC_API_KEY IS AVAILABLE in this environment. Without one the exam
    runner builds neither a parser nor a synthesizer (both are gated on the key
    in ExamRunner.__init__), so every question would land on the honest
    could-not-interpret floor and the resulting "grade" would measure the
    absence of a key rather than the system.

    The bank is recorded as UNRUN AFTER TWO SESSIONS in docs/07 sec 5a.7. Not
    skipped silently. Not marked delivered.


======================================================================
CU6 -- THE RESUMABLE FRACTION (report only; no code changed)
======================================================================

DELIVERED. pilot_scale, window 7 / frozen 2, measured over the beyond-horizon
population the coarse zone actually runs on:

  40 orders   -- 38 beyond demands, 83 coarse ops, 19,191 coarse minutes
      resumable_out_of_scope     1 op   ( 1.2%)    1,200 min  ( 6.3%)
      exceeds_bucket_capacity    0      ( 0.0%)        0 min  ( 0.0%)
      no_eligible_resource       0      ( 0.0%)        0 min  ( 0.0%)

 200 orders  -- 157 beyond demands, 408 coarse ops, 83,180 coarse minutes
      resumable_out_of_scope     4 ops  ( 1.0%)    4,500 min  ( 5.4%)
      exceeds_bucket_capacity    0      ( 0.0%)        0 min  ( 0.0%)
      no_eligible_resource       0      ( 0.0%)        0 min  ( 0.0%)

 (exceeds_bucket_capacity measured at BOTH rho 1.0 and the declared rho 0.85.)

THE READING. By op count the exclusion is ~1%. By MINUTES -- the number that
matters -- it is 5 to 6%, FIVE TIMES what the count suggests. That is the
predicted shape: resumables average ~1,125 minutes against a ~210-minute
population mean, so an op-count percentage understates the capacity blindness by
exactly the factor the brief anticipated, which is why the count alone would
have been a misleading statistic.

In absolute terms it is small. CROSS-BUCKET ALLOCATION FOR RESUMABLES STAYS A
QUEUED REFINEMENT, NOT AN URGENT CORRECTION, at this plant's parameters.
exceeds_bucket_capacity excludes NOTHING at any realistic rho on this plant --
it only bites below ~0.15, where it is the non-monotonicity MECHANISM rather
than a capacity blind spot.

The decision returns to the working thread. No code changed.


======================================================================
CU7 -- DOCS
======================================================================

DELIVERED.
  docs/04  session amendment appended (append-only respected;
           635,631 -> 653,347 chars).
  docs/06  v0.6a -- the NO CAPACITY MARGIN DECLARED remediation entry in sec 5.9
           (informational, NOT a registry rule; the rule count is asserted
           unchanged at 36) plus a header change note.
  docs/07  v2.49 summary entry; sec 5a items 5 and 6 updated to reflect what
           this session discharged, items 7 to 11 added.
  CLAUDE.md  position, quick reference (the coarse flag, reference_date, where
           predictions land), coarse-zone bullets, carry-forwards. 25.9k chars,
           well under the 40k ceiling.


======================================================================
ACCEPTANCE
======================================================================

 1. Store wired; consecutive rolls prove accrual; count stated.         MET
    (three rolls: 228 predictions, 180 realizations)
 2. Document byte-identical with the store on and off.                  MET
 3. Capacity answers name the uncounted population, both directions.    MET
 4. No-derate absence loud and NOT a gate finding; 36 rules unchanged.  MET
 5. 200-order binding test green and deterministic.                     MET
 6. Fixture regenerated, every moved figure accounted for; band
    screenshots exist; attribution split asserted on real figures.      MET
 7. r5 bank run and graded, OR halted and recorded per CU5(c).          HALTED
    and recorded. The added question is delivered; the run is not.
 8. Resumable fraction reported by count AND by minutes, both
    densities.                                                          MET


UNDERDELIVERED, NAMED IN FULL

  * CU5(b): the bank is UNRUN. Blocked on ANTHROPIC_API_KEY, nothing else. It
    is now unrun after two sessions and is docs/07 sec 5a.7.
  * CU3's non-monotonicity clause asked that the 0.20 / 0.15 / 0.10 property
    "still pass at this density". The MECHANISM does and is asserted; the full
    STATUS LADDER does not reproduce at 200 orders, and the 40-order test
    remains its pin. Stated, not smoothed.


======================================================================
DEBTS OPENED BY THIS SESSION (in docs/04 and docs/07 sec 5a, same commit)
======================================================================

  * record_roll_history sweeps the WHOLE data root on every rolling solve to
    find prior rolls' predictions. O(runs) per solve; fine at demo size, needs
    an index or a per-submission scope before a pilot data root grows.
  * The regenerated window incumbent is ~7.9% dearer than the fixture's old one.
    Explained and reproducible, but it changes what the demo board shows.
  * rolling_coarse_hot/ binds because it DECLARES rho 0.10, not because the
    plant is loaded. A contrivance that buys screenshot coverage; it does not
    retire the demo-density limit (CU3 covers that at 200 orders instead).
  * tools/build_rolling_exam_run.py does not pass the new coarse flag, so the
    pinned rolling exam world has no coarse zone and its coarse routes answer
    "I haven't run the coarse look-ahead" -- honest, and a test of nothing.


======================================================================
TESTS
======================================================================

  NEW python
    tests/test_coarse_history_wiring.py    7 slow, green
    tests/test_coarse_binding.py           5 slow, green (4m29s)
    tests/test_coarse_horizon.py          +11 (CU2), green

  NEW cockpit JS
    tests/cockpit/coarse.spec.mjs          5 x 2 themes, green
    tests/cockpit/attribution.spec.mjs    +2, green

  FULL SUITES, both green after every edit:
    python non-slow    1624 passed, 239 skipped (11m37s)
    cockpit ladder      225 passed, both themes (3.7m)
    plus the two slow files above run explicitly with --runslow.

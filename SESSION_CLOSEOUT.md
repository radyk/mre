SESSION 4B.6b CLOSE-OUT -- ERRAND: FOUR ANSWERS
A findings session. Its product is knowledge, not capability.
2026-07-27

Repo: C:\dev\mre, branch master. docs/07 v2.50; docs/04 one amendment same date;
CLAUDE.md position and carry-forwards updated. No docs/06 change (no gate rule
moved; the registry is still 36 rules).

All solver work ran deterministic: PYTHONHASHSEED=0, one worker, seed 42, with
wall ceilings kept generous so the DETERMINISTIC budget is what binds.

ONE thing changed behaviour (item 3). Items 1, 2 and 4 report and stop. Nothing
tempting was fixed; the tempting fixes are named at the bottom.


======================================================================
ITEM 1 -- IS THE BASELINE DELTA A MEASUREMENT OR AN IDENTITY?
======================================================================

VERDICT, plainly: NOT MECHANICAL. The identity is falsified both empirically and
by code-read. But BENIGN is not right either -- its premise ("the published
incumbent is simply poor") is false. The truth is a third thing, worse than
BENIGN and better than MECHANICAL:

    reopt_delta_abs is a REAL measurement of a REAL quantity, and the card
    puts the WRONG NAME on it. It is not window re-optimization the planner
    did not cause. It is what the incumbent paid, in ledger dollars, for a
    DECLARED priced objective term that the baseline solve does not carry
    and the ledger does not print.

4B.5's headline fix does NOT reopen. See "what does not reopen" below.

----------------------------------------------------------------------
(a) EMPIRICAL -- four instances, and the identity BREAKS
----------------------------------------------------------------------

Each row: build the rolling world (persisted window-0 solve), read the
incumbent's persisted schedule summary, then run the REAL
sandbox.baseline_window_solve over the same window holding the same committed
frozen front, and compare against (incumbent_total - incumbent_tardiness).

  inst  plant                  win   incumbent   inc.tard    baseline   total-tard    diff   base.tard
  A     40 orders, seed 1      14/3  28,597.23  11,975.83  16,621.40   16,621.40    0.00     0.00
  A'    A, no standing pins    14/3  28,597.23  11,975.83  16,481.95   16,621.40  -139.45    0.00
  B     200 orders, seed 1      7/2  35,406.90   7,127.92  28,684.40   28,278.98  +405.42   361.67
  C     80 orders, seed 7      10/2  14,514.75       0.00  14,514.75   14,514.75    0.00     0.00
  D     120 orders, seed 3      7/2  31,306.22  13,312.08  17,994.13   17,994.13    0.00     0.00

Instance A reproduces the shipped fixture's figures to the cent (16,621.40,
difference 0.00), which validates the harness before anything is concluded.

DEGENERATE INSTANCES, named as the brief asked:
  * C is degenerate in exactly the way warned about -- its incumbent carries
    ZERO tardiness, so total-tardiness IS total and the test is vacuous. It was
    replaced by D.
  * rolling_coarse_hot was rejected as degenerate BY CONSTRUCTION, not by luck:
    it is the same 40-order plant as A with only a different DECLARED coarse
    coefficient, and coarse never constrains fine (an import-direction test), so
    its window solve and its sandbox baseline are A's to the cent. It could
    never have been a second data point. D was built instead.

B SETTLES IT. The baseline's own tardiness component is 361.67 -- present,
computed, NONZERO -- and baseline - (incumbent - tardiness) is +405.42. There is
no identity.

A' settles a second thing that matters for reading the fixture: release the
standing pins and PRODUCTION moves too (-139.45). So even the "production
unmoved to the cent" half of the fingerprint is a property of the pin set, not
of the code.

----------------------------------------------------------------------
(b) CODE-READ -- the call chain, not a conclusion
----------------------------------------------------------------------

  sandbox.sandbox_pin_resolve                     sandbox.py:939-944
    -> sandbox.baseline_window_solve              :326   (cached per incumbent)
       -> _baseline_window_solve_uncached         :370
          -> SnapshotStore.load_snapshot
          -> _restrict_window(ops, wps, fuls, demands, restrict_op_ids)   :242
          -> SolverBuilder(reference_date).build(wps+ops+edges,
                 resources+pools, cals, fuls+demands, constraints,
                 cost_model)                                              :425
          -> apply_solution_hints + standing_pins.apply_standing_pins  :431-435
          -> SolveRunner(time_limit_seconds=budget_s, workers, seed)
                 .solve(model, var_map, r_rep)                            :450
          -> Extractor().extract(..., is_scenario=True)                   :465
          -> ledger = er.cost_ledger ; total = ledger["total_cost"]   :473-474

Extractor.extract (extractor.py:390-399):

    total_cost = production_cost + setup_cost + tardiness_cost
    cost_ledger = {total_cost, production_cost, production_regular_cost,
                   production_overtime_cost, setup_cost, tardiness_cost}

So the tardiness term IS in the baseline's ledger, and it is the SAME ledger
code the incumbent's own summary was written by -- one implementation, no second
path, no omission.

Two structural facts fell out of the read, and both change how the fixture's
fingerprint should be read:

  * setup_cost = new_setup_ops * setup_fixed (extractor.py:382-387) is a function
    of the OPERATION SET only. It cannot move under re-placement at all.
    "Setup unmoved to the cent" is guaranteed by construction and is evidence of
    nothing.
  * incumbent_total is the PERSISTED schedule summary (sandbox.py:1058-1059);
    baseline.total_cost is a fresh in-memory extract of a window-restricted
    re-solve. Same ledger code, different provenance.

----------------------------------------------------------------------
(c) THE BUDGET PROBE -- the gap is not a search gap
----------------------------------------------------------------------

The fixture's window re-solved at 1x / 2x / 4x / 8x the deterministic budget:

  det budget   window status   incumbent   inc.tard    baseline    reopt delta
  2.0s  (1x)   FEASIBLE        28,597.23  11,975.83   16,621.40   -11,975.83
  4.0s  (2x)   FEASIBLE        28,547.38  11,975.83   16,571.55   -11,975.83
  8.0s  (4x)   FEASIBLE        28,594.62  11,976.67   16,617.95   -11,976.67
  16.0s (8x)   FEASIBLE        28,853.83  11,975.83   16,878.00   -11,975.83

The gap does NOT close. At 8x budget the incumbent is DEARER on the ledger
(28,853.83). The window solve never reaches OPTIMAL at any budget; the baseline
proves OPTIMAL in 0.03-1.5s on every instance tried. The fixture is NOT
budget-starved, and the ~1% wobble across budgets is the fingerprint of a ledger
that is not the thing being minimized.

That is what forced the third answer: neither "the incumbent is poor" nor "the
term is missing" survives this table.

----------------------------------------------------------------------
THE ACTUAL CAUSE -- an objective mismatch, proven by a forced variable
----------------------------------------------------------------------

The two solves minimize DIFFERENT OBJECTIVES.

  * The incumbent (rolling_horizon._two_stage_solve, :150-151) minimizes
        sum(objective_terms) + earliness_coeff_scaled * sum(free op start vars)
    where the coefficient is the plant's DECLARED refinements.earliness_value
    (R-SC3; pilot_scale declares 0.05 $/min-of-start, scaled to 5).
  * The baseline is built by SolverBuilder.build, whose own objective is
    sum(objective_terms) ALONE. There is no earliness term in the builder.
  * The extractor's cost ledger has NO EARLINESS LINE AT ALL. earliness_value is
    read at extractor.py:101 and used ONLY to classify a driver (:637-639).

So the incumbent spends ledger dollars buying early starts at a price the plant
declared; the ledger never shows what it bought; and a baseline that is not
charged for early starts beats it on the ledger essentially always.

The falsifiable prediction that follows -- force earliness_value to 0 and the
two solves optimize the same objective, so the delta should collapse -- was run:

  earliness        incumbent   inc.tard    baseline    reopt delta
  declared 0.05    28,597.23  11,975.83   16,621.40   -11,975.83
  forced   0.00    16,481.95       0.00   16,481.95         0.00

EXACTLY zero. The entire $11,975.83 "window re-optimization" on the shipped
fixture is the declared earliness price, invisible in the ledger.

This also explains, retroactively, the 4B.6a carry-forward that the regenerated
fixture's incumbent is ~7.9% dearer than its predecessor and wobbles ~1% with
budget: the ledger is a bystander to what the window solve is minimizing.

----------------------------------------------------------------------
WHAT DOES NOT REOPEN
----------------------------------------------------------------------

4B.5 CU1's ruling stands. move_delta_abs = pinned - baseline is
apples-to-apples: the pinned re-solve and the baseline are BOTH built by
SolverBuilder under the earliness-free objective. A planner's move is still
judged against the baseline and never against the stale incumbent, and the
founder's specimen (two different gestures, identical cards to the cent) is
still fixed. What is wrong is the LABEL on the other half.

NOT FIXED HERE, on purpose. Changing what the card measures is a working-thread
decision. Three shapes exist that I can see -- price earliness into the ledger
as its own line; build the baseline under the SAME objective the window solve
used; or relabel the half honestly -- and whichever lands should move together
with 4B.5's open debt that the two-solve baseline was never extended to
forced-alternatives pricing. Filed docs/07 section 5a.12.


======================================================================
ITEM 2 -- DO IDENTITIES SURVIVE A NEW SUBMISSION?
======================================================================

VERDICT, plainly: THEY SURVIVE. Cross-submission accrual works today, across
three genuinely different submissions with real data deltas. Splicing seam 3 is
NOT blocked on re-keying the store to IDS-visible identity, and no id derivation
was changed. The seam that IS open is RETIREMENT, not identity.

----------------------------------------------------------------------
(a) THE DERIVATION, VERBATIM
----------------------------------------------------------------------

One namespace, in both minting sites:
uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

  # adapter.py:74-77
  def _stable_id(namespace: str, value: str) -> str:
      """Deterministic UUID5 from a namespace+value pair."""
      ns = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # URL namespace
      return str(uuid.uuid5(ns, f"{namespace}:{value}"))

  # planner.py:50-54
  _NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
  def _uid(*parts: str) -> str:
      return str(uuid.uuid5(_NS, ":".join(parts)))

  # ids_adapter.py:616   demand_id = _stable_id("demand", ext_oid)
  # ids_adapter.py:450   spec_id   = _stable_id("operationspec",
  #                                   f"{route_id}:{ext_pid}:{seq}")
  # planner.py:182       wp_id     = _uid("wp", *[d["id"] for d in batch])
  # planner.py:203       op_id     = _uid("op", wp_id, spec_id)
  # planner.py:268       ful_id    = _uid("fulfillment", demand["id"], wp_id)

Under identity_v1 every batch is a singleton (planner.py:112-113,
batches = [[d] for d in demands.values()]), so the closed forms are:

  Demand        = uuid5(NS, "demand:" + order_id)
  WorkPackage   = uuid5(NS, "wp:" + Demand)
  OperationSpec = uuid5(NS, "operationspec:" + route_id + ":" + product_id
                              + ":" + sequence)
  Operation     = uuid5(NS, "op:" + WorkPackage + ":" + OperationSpec)

NOTHING in any of those strings is a submission id, a run id, the manifest
reference_date, the extract_timestamp, an ingest timestamp, or a row ordinal.
Quantity, due date, release date, priority class and customer move none of them.

What DOES move an id (stated so it is not rediscovered later):
  * re-routing an order (route_id) or re-parting it (product_id) re-mints every
    one of its OPERATION ids, while its DEMAND id is unchanged;
  * a renumbered sequence re-mints that operation;
  * under a MERGE policy (merge_by_family_v1/v2 -- NOT the supported doorway's),
    wp_id is a function of the WHOLE batch, so adding or removing ONE order in a
    batch re-mints every operation id in it. That is the real fragility and it
    is not on the supported path today.

Note in passing: adapter.py's comment says "URL namespace" for what is actually
the RFC-4122 DNS namespace. Cosmetic; the VALUE is what matters and it is
stable. Not touched.

----------------------------------------------------------------------
(b) EMPIRICAL -- three days, three submissions, one data root
----------------------------------------------------------------------

Same plant, advancing reference_date, a real data delta each day, cumulative:
  day 1  ref 2026-01-05  orders 1..40
  day 2  ref 2026-01-06  ORD-000001 completed and dropped, ORD-000041 added
  day 3  ref 2026-01-07  ORD-000002 also completed, ORD-000042 added

Each solved as its OWN submission (its own spine run, its own run dir) into ONE
data root, exactly as the API's rolling worker does it: prepare_plant ->
build_rolling_view -> build_coarse_zone -> record_roll_history. Window 7 /
frozen 2, coarse on at the plant's declared rho 0.85, deterministic.

  roll                predictions   prior pending seen   realizations written
  day 1 (2026-01-05)      164             0                     0
  day 2 (2026-01-06)      142           164                    18
  day 3 (2026-01-07)      114           288                    60

MATCH COUNTS, as asked:

  * Predictions from submission 1 REALIZED against submissions 2 and 3:
    48 of 164 (18 judged by day 2, 30 by day 3). 78 realizations in total.
  * Permanently pending: day 1, 116 of 164; day 2, 112 of 142; day 3, all 114
    (nothing later exists to judge them).
  * ID STABILITY, measured rather than assumed: 33 demands were predicted by
    more than one run, and ALL 33 share at least one operation id across runs.
    That is the code-read confirmed end to end.
  * THE COMPLETED ORDER'S PREDICTIONS ARE ORPHANED. ORD-000001 minted 4
    predictions on day 1, is absent from days 2 and 3, and got ZERO
    realizations. ORD-000002 the same, with 8. They are neither judged nor
    retired. They stay in prior_predictions_pending forever and are re-swept on
    every subsequent solve.
  * THE NEW ORDERS COLLIDED WITH NOTHING. A new order id mints a fresh demand id
    by construction. ORD-000041 minted zero coarse predictions -- it was
    admitted into the FINE window on both days it existed, so it never entered
    the tray. ORD-000042 minted 6 on day 3, in the tray, with no later roll to
    realize it.

ONE MORE, unprompted but material: all 78 realizations came back
intake_path = gravity_admission, none natural_roll. The definition is behaving
correctly (gravity_admitted = admitted(gravity) - admitted(no gravity),
rolling_horizon.py:752-769) -- on a 7-day window nearly everything admitted is
admitted by gravity. But it means clause (7)'s "two mechanisms disagreeing"
count reads ~100% and carries no signal at that window length. Anything built on
that count must print the window length beside it. Filed section 5a.14.

HALT CONDITION HONOURED: no id derivation was touched, and no mapping layer was
added. There was nothing to paper over -- the ids held.


======================================================================
ITEM 3 -- THE ONE THING THIS SESSION FIXED
======================================================================

(a) tools/build_rolling_exam_run.py

    Builds a coarse zone at the submission's DECLARED coefficients and passes it
    to assemble_rolling_document; fails the build if either coarse run was
    stopped by the WALL clock (a wall-truncated run is a lottery wearing a
    determinism label); and fails it again if the assembled document comes back
    without a zone. The registered solve now sends "coarse": true and an
    explicit "reference_date" (2026-01-05 -- the manifest's own value today, so
    it changes nothing now and stops the world drifting if the generator's
    default ever moves).

    VERIFIED BY RUNNING IT:
      rolling-exam: building the coarse zone (declared coefficients) ...
      rolling-exam: 56 bars, 42 committed, 14 active, 14 in the tray
      rolling-exam: coarse zone rho=1 (defaulted) cells=10 binding=0
                    unmodelable=0 tardiness_buckets=0
      rolling-exam: determinism verified (identical split and placements)

    and the written document.json is contract 1.9 with rolling.coarse_zone
    present and all 14 tray items carrying a coarse placement.

    RESIDUE, named and filed (section 5a.10): the pinned submission under
    _ai_exam_scratch/ predates the generator's refinements.coarse_horizon block,
    so the exam world runs at rho 1.0, provenance "defaulted" -- correct
    behaviour (an undeclared plant is never given an invented margin), and it
    exercises the docs/06 section 5.9 "figures assume full utilization" voice,
    but it grades no BINDING answer. Measured: a fresh generate at the same seed
    differs from the pinned submission in exactly two things -- the manifest's
    extract_timestamp and the cost model's coarse_horizon (declared 0.85) --
    with every table byte-identical. Since coarse_horizon never enters the fine
    solve, --fresh would give the exam world its declared derate with the fine
    world PROVABLY unchanged. Left alone: the world the r5 bank's expectations
    were calibrated against is not this session's to move.

(b) src/mre/ai_exam/runner.py::_exam_card

    Was a SYNTHESIZED card: -11,975.83 = -11,600.00 + -375.83, a move that saves
    inside a re-optimization that saves. The SHIPPED card (captured from a real
    sandbox_pin_resolve into tests/cockpit/fixtures/rolling/sandbox.json) is
    -11,953.08 = -11,975.83 + 22.75 -- a move that COSTS $22.75 inside a
    re-optimization that saves $11,975.83. The synthesized pair could not express
    that sign disagreement, which is the case the CU1 split exists for.

    The runner now feeds the shipped figures, plus the fields the shipped
    surface actually sends and the synthesized card omitted: message,
    correlation_id, cost_lines, a POPULATED affected_orders (four orders by
    name, two with tardiness savings and two with lateness moves at zero
    tardiness delta), and the real dominant_driver with its hedge. Test-realism
    law: a context test feeds ONLY what the shipped surface sends, in the shapes
    it sends them. Both decompositions close exactly -- the two parts sum to the
    total, and the five cost lines sum to the total. Only the identity fields
    still vary with the bank's directive.

    The r5 bank's comment block quoted the synthesized figures and its
    substantive expectation was written around them; it was corrected in the
    same commit, including the sign.

    Item 1 came back not-MECHANICAL, so (b) was in scope. Had it come back
    MECHANICAL the shipped card's own figures would themselves have been in
    question and (b) would have been skipped.

(c) The bank was NOT run. No ANTHROPIC_API_KEY. Section 5a.7 unchanged, except
    that it is now UNRUN AFTER THREE SESSIONS.


======================================================================
ITEM 4 -- IS THE DATA-ROOT SWEEP PERF OR CORRECTNESS?
======================================================================

VERDICT, plainly: CORRECTNESS, in a multi-tenant pilot data root. Re-filed as
such in docs/07 section 5a.8, superseding its 4B.6a filing as O(runs)
performance. The performance reading survives on top of it.

  * IS THE SWEEP SCOPED? By nothing. record_roll_history(data_root=
    registry.data_root, ...) (app.py:974-977) calls sweep_data_root =
    root.rglob("coarse_predictions.jsonl") (coarse_predictions.py:169-178) and
    filters on exactly one thing: p.run_id != run_id (:360). Not by submission,
    not by plant, not by facility.
  * WHAT DOES A REALIZATION MATCH ON? op_id ALONE --
    pl = placed.get(pred.op_id) (:230). Nothing else is compared before the row
    is written: not the demand, not the plant, not the bucket grid.
  * CAN TWO PLANTS SHARING ORDER NUMBERING COLLIDE? Yes, by construction. From
    item 2(a), Operation = f(order_id, route_id, product_id, sequence). There is
    no plant term anywhere in it.

THE CONSTRUCTED CASE. Two plants, same scenario catalogue (the realistic
multi-site case: one company, one ERP, one part and route numbering), different
seed so the order BOOK genuinely differs, one data root. Plant P solved first
with a 5-day window (40 demands in the tray, 174 predictions); plant Q second
with a 45-day window (96 operations placed, empty tray).

    Q'S ROLL WROTE 20 REALIZATIONS AGAINST P'S PREDICTIONS.

    demand-id overlap     40 of 40
    operation-id overlap  10
    resource-id overlap   15 of 15

The rows are nonsense on their face -- predicted_bucket 1 -> realized_bucket -1,
gap -2, with a "realized resource" belonging to the other plant -- and they land
in the conformance report's realized_fraction, its slip census and its
gravity-disagreement count.

NOT FIXED. The fix needs a scope key on the store AND a decision about what
plant identity IS in the canonical model: the manifest's facility_scope is the
only candidate and nothing downstream reads it.


======================================================================
ITEM 5 -- THE COUNTS RECONCILED
======================================================================

PYTHON: tests/test_coarse_horizon.py collects 47 -> 57 = +10, not the +11 the
4B.6a close-out claimed. No parametrize in the file; the git diff adds exactly
10 def test_ blocks. Nothing removed, nothing newly skipped (38 pass / 19 skip
today; all 19 are pre-existing --runslow gates). The suite delta 1614 -> 1624 is
exact -- the close-out over-counted by one.

COCKPIT: coarse.spec.mjs carries 5 tests and runs in the light and dark projects
(10); attribution.spec.mjs gained 2 and runs in the theme-free logic project
(2). 12 new against a reported 215 -> 225. The ladder collects 227 today and
runs them all, so the close-out's "225 passed" is two short of what the ladder
reports. Nothing removed, nothing skipped: the harness's only test.skip
(rolling.two_beat.spec.mjs:167) is conditional on a missing forced
contradiction, and the fixture captures one, so it never fires.


======================================================================
TESTS
======================================================================

  NO NEW TESTS, deliberately. This session added no capability, and the four
  items are investigations whose evidence is measured figures in docs/04 rather
  than assertions. The item-1/2/4 probes are scratch harnesses, not committed:
  they generate plants and solve them (the slow ladder's job), and none of them
  asserts a behaviour worth pinning -- item 1's finding is that a figure is
  MISLABELLED, and pinning a mislabelled figure would be worse than not pinning
  it.

  FULL SUITES:
    python non-slow    green, unchanged at 1624 passed / 239 skipped
    cockpit ladder     227 collected; 226 passed + 1 failed
                       ([light] planner.spec.mjs:128 "CU4 -- the due marker",
                       the standing 4A.3 member of the parallel-load
                       screenshot-flake class), re-verified GREEN in isolation
                       (planner.spec.mjs 16/16 in 34.2s)

  No test asserts on _exam_card and none imports build_rolling_exam_run, so
  neither behaviour change could move a suite figure -- and neither did.


======================================================================
CHANGED FILES
======================================================================

  tools/build_rolling_exam_run.py                 item 3(a)
  src/mre/ai_exam/runner.py                       item 3(b) -- _exam_card
  tests/ai_exam/banks/regression_founder_r5.txt   item 3(b) -- the comment and
                                                  substantive expectation,
                                                  corrected to the shipped
                                                  figures and their signs
  docs/04-design-history.md                       amendment (append-only)
  docs/07-roadmap.md                              v2.50; section 5a items 8, 10,
                                                  11 rewritten, 12/13/14 added
  CLAUDE.md                                       position + carry-forwards
  SESSION_CLOSEOUT.md                             this file

  No golden moved. No fixture regenerated. No test file changed except the bank
  comment above.


======================================================================
TEMPTING, AND LEFT (as the brief required)
======================================================================

  1. Fixing the earliness/ledger mismatch behind item 1. Three shapes, all
     working-thread calls; naming it was the deliverable.
  2. Relabelling the delta card's reopt half. Same reason.
  3. Scoping the prediction store's sweep by submission or plant (item 4). It
     needs a plant-identity decision first.
  4. Retiring orphaned predictions for completed orders (item 2). Needs item
     4's scope key first, or it would retire another plant's predictions.
  5. Running build_rolling_exam_run.py --fresh so the exam world declares its
     0.85 derate. Measured to be free (only extract_timestamp and
     coarse_horizon differ, and coarse never touches the fine solve) -- but it
     is the world the r5 bank was calibrated against, so it is not mine to move.
  6. Fixing adapter.py's "URL namespace" comment (it is the DNS namespace).
     One word, and noise in a findings commit.

  Nothing else changed.

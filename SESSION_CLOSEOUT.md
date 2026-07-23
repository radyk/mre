SESSION 4B.4 CLOSE-OUT
R-SC3 extended to ALL solve paths (the monolithic floor) + the founder's
conversational fixes
2026-07-23

Deterministic settings for all solver work: PYTHONHASHSEED=0, --solver-workers 1,
--solver-seed 42/0.

======================================================================
SUMMARY
======================================================================
The founder's live listening session (2026-07-23, monolithic run) surfaced one
solver finding (the R-SC3 earlier-start floor was implemented on the rolling path
only; the monolithic schedule of record parked cost-equal work arbitrarily) and a
set of conversational failures. This session closed the solver gap first
(everything waited on its goldens), then the conversational fixes.

Result: non-slow Python 1243 passed, 0 failed. All affected slow ladders green.
Monolithic golden regenerated with cost identity verified and stated; rolling
goldens byte-identical.

======================================================================
CU1 - MONOLITHIC TWO-STAGE PARITY
======================================================================
CLAIMED: lift the two-stage shape into the monolithic solve path; audit every
solve call-site; regenerate monolithic goldens deliberately with cost identity
verified; rolling goldens byte-identical.

PROVEN:
- solver_builder.solve_two_stage added: a shared, reporter-aware helper mirroring
  rolling_horizon._two_stage_solve. Stage 1 minimizes cost (+ the declared
  earliness_value term when a positive coefficient is declared, omitted at 0),
  recorded to the M6 reporter so the solve_complete objective the assembler and
  _incumbent_objective read stays the COST objective. Stage 2 caps that optimum at
  round(best) and re-minimizes the SUM of free-op starts, warm-started via add_hint,
  under a deterministic budget (_STAGE2_DET_TIME_S = 2.0); on exhaustion the stage-1
  incumbent stands. The returned SolveResult carries stage 1's objective/telemetry
  with stage 2's placements.
- __main__ (CLI + API monolithic schedule of record) uses it. No pins in that path,
  so the earliness sum is over every op start.
- Per-site audit (stated in docs/04):
    __main__ monolithic solve            -> STAGE 2 (the fix)
    sandbox.feasibility_ghost (beat one) -> exempt (first-feasible probe)
    sandbox.sandbox_pin_resolve (beat 2) -> exempt (warm-starts from the two-stage
                                            incumbent; prices a CHANGE vs the record)
    scenario re-solve                    -> exempt (what-if diffed vs incumbent)
    planner_edit accept                  -> exempt (commits a pinned placement)
    solution_pool                        -> exempt (DIVERSITY is its 2nd objective)
    forced_alternatives                  -> exempt (per-machine pricing probe)
    demo.py                              -> exempt (standalone demo wrapper)
  All re-solve exemptions validated green on their slow ladders.
- Golden regen: sample_data_schedule.csv regenerated. Cost ledger IDENTICAL pre/post
  (total 24769.00, production 19429.00, setup 4500.00, tardiness 840.00 - every
  value unchanged; test_cost_ledger_identical passes untouched). Per-op production
  cost unchanged on every row. New CSV byte-identical across two subprocess rolls.
  Rolling goldens BYTE-IDENTICAL (rolling determinism golden green; rolling_two_beat
  goldens survive).
- Tests: tests/test_two_stage_monolithic.py (fast, hand-built CP-SAT model) - (a)
  cost-equal earlier slot is TAKEN (start sum is the provable minimum), (b)
  cost-neutrality vs stage-1-only epsilon 0, (c) determinism run-to-run, + the
  stage-2-skipped path. End-to-end proof: test_defaults_reproduce_baseline.

NAMED / NUANCE (not a shortfall, stated honestly):
- The task close said "only placements may differ, only earlier". The floor
  minimizes the SUM of starts (the same objective rolling uses) - a GLOBAL minimum,
  so it is NET-earlier, not per-op monotonic: it may push one cost-equal op later to
  pull others earlier when that lowers the total (sample_data: 30 earlier, 13 later,
  47 same, 3 equal-cost machine swaps). This is faithful to the ratified rolling
  floor; a per-op-monotonic rule would create two DIFFERENT floors. Cost identity
  (the load-bearing invariant) holds exactly.
- The 4B.3a earliness_forcing hedge fixture broke because post-CU1 the monolithic
  path now PRICES a declared earliness_value (correct R-SC3 behavior) and 0.05/min
  moved ORD-06 off the dearer machine. Re-tuned to 0.004 (< 0.005 => coefficient
  rounds to 0 => placement unmoved, raw value > 0 => the docs/02 4.2 ATTRIBUTION
  still fires), isolating attribution from placement. Documented in the fixture and
  docs/04.

======================================================================
CU2 - THE RECOMMENDATION-SHAPE GUARD
======================================================================
CLAIMED: advice-seeking phrasings route to an honest scoping answer, never the
late-orders recital; four founder phrasings join the corpus (recital = fail); the
clarify template must never echo a frustrated/meta sentence verbatim.

PROVEN:
- New `advice` route (_ADVICE_TRIGGERS in explainer.classify, checked after
  triage/remediation/briefing, before the edit/late/schedule branches). The answer
  states what the product can do today (explain why each late order is late; what it
  waits on; price a what-if on the board) and that intervention recommendation is
  not yet supported. Conversational register, no === headers. Does NOT recommend
  interventions (4A.3, out of scope).
- All four founder phrasings route to `advice` (TestSession4B4.test_cu2_advice_...)
  and three are folded into test_cu10_zero_confident_wrong.
- Frustration echo: ask_fallback_copy.safe_parsed drops the verbatim echo when the
  question carries frustration/meta markers; renderers use the _NO_ECHO lead
  variants for clarify/near-miss/unsupported. Proven by
  test_cu2_clarify_never_echoes_frustration.

======================================================================
CU3 - FALLBACK TAXONOMY SPLIT + CHEAP META ROUTES
======================================================================
CLAIMED: split the fallback (entity-miss vs shape-unrecognized vs shape-unrouted);
add solve-time + machine-count meta routes; maintenance -> shape + honest not-yet.

PROVEN:
- solve-time, machine-count, maintenance routes added BEFORE the bare-"schedule"
  branch, so the four founder phrasings ("how long did this take to solve", "how
  many machines", "is there any maintenance scheduled", "does this use workcenters")
  no longer get "I don't see any scheduled operations matching that".
- machine-count: a real answer - counts + lists the resource entities in planner
  vocabulary.
- solve-time: an answer or an honest not-yet.
- maintenance: shape-recognized + honest not-yet naming the per-machine downtime
  route that DOES exist.
- Tests: TestSession4B4 CU3 specimens + three corpus rows.

NAMED / NUANCE:
- solve-time reads the M6 run's open->close wall time via EvidenceIndex.runs() (the
  run duration), not the solve_complete payload's wall_time_s directly - the index
  does not reliably expose payload-only events after load(). This is a close,
  honest approximation of "how long the solve took" (it includes reporter overhead);
  it degrades to an honest not-yet when unavailable.
- The explicit three-way fallback MESSAGE split (entity-miss / shape-unrecognized /
  shape-unrouted) was addressed by ROUTING the recognized shapes to their own
  answers rather than by adding a third distinct message string. The category-error
  insult is removed for the named cases; the generic capability menu remains for
  truly unrecognized shapes.

======================================================================
CU4 - ENTITY-BINDING RECENCY + REPAIR-ON-CORRECTION
======================================================================
CLAIMED: (a) anaphora binds by TYPE first then recency; (b) no type-matching
referent -> ask, never cross-type bind; (c) a correction re-binds and re-answers
the prior question, never a menu-dump.

PROVEN:
- Typed anaphora: _typed_deictic + _last_typed_subject in resolve_followup. "that
  machine" binds only to a machine referent (then recency), "that order" only to an
  order. No type-matching referent -> clarify (CLARIFY_NO_SUBJECT). The founder's
  "why are there no jobs on that machine" now binds to the machine (with the order
  turn MORE recent, so untyped recency would have wrongly bound the order).
- Correction: _CORRECTION_RE checked BEFORE the order/machine short-circuit (so the
  wrong referent Y in the same sentence does not re-fire the confident-wrong
  answer). Re-answers the PRIOR question with the corrected referent.
- Tests: TestSession4B4 CU4 specimens (typed bind, correction re-answers) + a corpus
  row for the founder's exact "that machine" sequence.

NAMED / NUANCE:
- The correction re-answers only when the corrected referent fills what the prior
  route needs. A CROSS-TYPE correction (a machine handed to an order route) cannot
  re-answer the same question, so it clarifies (never a menu-dump, never a
  confident-wrong re-run) rather than fabricating a mismatched route. This is the
  honest handling; a full same-question re-answer across types would require an
  unstated route mapping this session did not invent.

======================================================================
CU5 - FOLLOW-UP CONTEXT (LIST-EXPANSION SLICE)
======================================================================
CLAIMED: the interpreter carries the last route; a short elliptical follow-up
("list them", "which ones", "the numbers", "show me") re-fires the last route in
list/expanded form; scoped strictly to list-expansion.

PROVEN:
- _LIST_EXPAND in resolve_followup (after the classify short-circuit): re-fires the
  canonical question of the last answered route (params from the last subject).
- Founder's pair: "how many late orders" (route late-orders) -> "can you list the
  numbers" re-fires late-orders. Proven by test_cu5_list_expansion_re_fires_last_route.

======================================================================
CU6 - RIDERS
======================================================================
CLAIMED: (a) state earliness once, per-row only when rows differ; (b) "Customer:
not specified" gains a coaching line citing the customers doorway; (c) docs/04 debt
entries.

PROVEN:
- (a) renderers.py schedule rows: per-row lateness shown only when rows DIFFER
  (single row keeps its marker; multiple same-value rows suppress the repetition).
  The header already states it once. Proven by
  test_cu6a_earliness_not_repeated_per_segment (and test_renderer_shows_late_marker
  still green - single-row late orders keep their marker).
- (b) "Customer: not specified - declare customers in the submission's customers
  file to see one here" (jurisdiction rule: coach the IDS requirement).
- (c) docs/04 debt entries written (not built): the absence-explaining route pair
  ("why the gap X-Y" / "why is machine M unused", the manned-idle Metric grounding
  the latter); the calendar-awareness cluster; the action bridge promotion (4A.3 -
  this listening session is standing evidence it is next).

======================================================================
OUT OF SCOPE (named only, not built)
======================================================================
- The action bridge (4A.3) - intervention recommendation.
- Full conversational context beyond CU5's list-expansion slice.
- The calendar/absence routes beyond docs/04 debt entries.
- Any ledger change.

======================================================================
VERIFICATION
======================================================================
- Non-slow Python: 1243 passed, 0 failed (+4 test_two_stage_monolithic).
- Slow: test_ai_voice 63 passed (+11 Session 4B.4 specimens); test_glass_box +
  test_ask_chain_api 34 passed; rolling_horizon + scenario + planner_edit +
  standing_pins + forced_alternatives 81 passed / 1 skip; sandbox + multi_route +
  multi_route_rates + rolling_two_beat + solution_pool 40 passed.
- Monolithic golden regenerated with cost identity verified and stated.
- Rolling goldens byte-identical (verified: rolling determinism golden green).

Same-commit spec: docs/04 (R-SC3 extension note, named regen, CU6c debts, this
amendment), docs/07 v2.38, CLAUDE.md.

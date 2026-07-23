SESSION 4B.3c CLOSE-OUT -- rolling parity: sliced runs become first-class citizens
Date: 2026-07-23
Repo: C:\dev\mre  (branch master)

================================================================================
SUMMARY
================================================================================
Retired the three named debts that were, in truth, one fact: a rolling-horizon
run was a second-class citizen in persistence and the API. prepare_plant ran
M0-M4 only and build_rolling_view extracted in-memory with snapshot_writer=None,
so no window-0 canonical snapshot existed; a rolling document carried no
interaction payload, so the cockpit could not compute Tier-0 on a sliced board;
and the M10 Explainer read persisted snapshots only, so both "ask why" (4B.3b)
and the rolling questions (4B.3a) routed to named-debt responses. This session
makes a rolling run first-class -- persisted, interaction-bearing,
sandbox-gestured, conversationally answerable.

Deterministic throughout (PYTHONHASHSEED=0, workers 1, seed 42/0). Schedule
contract bumped 1.7 -> 1.8 (additive). Monolithic AND rolling goldens
byte-identical.

ACCEPTANCE BAR (the sentence this session was graded against):
  a rolling run on pilot_scale, served through the API, renders a sliced board
  where a sandbox gesture produces a feasibility ghost, then a priced layered
  card, and "ask why" plus "why isn't {order} scheduled yet?" receive live
  conversational answers grounded in the run's evidence.
STATUS: MET end to end, proven through the HTTP API (test_api_endpoints.py::
TestRollingTwoBeatAPI drives the served rolling document + interaction + the
two-beat + the rolling questions; test_rolling_two_beat.py drives the module
layer incl. the forced contradiction and the why-on-machine grounding). One
honest residual on the beat-two cost delta is named below; it does not fail the
bar.

================================================================================
PER-CU: CLAIMED vs PROVEN
================================================================================

CU1 -- the rolling run persists a real window-0 snapshot
  CLAIMED  the rolling path executes the full spine for the current window
           (M0 gate through solve and extraction); an identified canonical
           snapshot with evidence records, basis rules intact; the run
           registered like any run; frozen-front commitment state persists; the
           completeness invariant holds against the PERSISTED document;
           determinism -- if persisting changes any byte it is a defect.
  PROVEN   build_rolling_view gains persist=True (the API rolling worker sets
           it). When set: the Extractor runs is_scenario=False,
           snapshot_writer=store.extend_snapshot(snap_id) + an M7 reporter, so
           Assignment/ServiceOutcome/Schedule entities land in the canonical
           snapshot and assignment Decisions land in evidence (RECONSTRUCTED
           basis); an M5 run records the builder's ACTUAL horizon_start (the grid
           the placements are written in) and an M6 solve_complete event records
           the objective. test_window0_persists_a_readable_run asserts the
           snapshot + evidence are readable by the sandbox helpers (_placements /
           _m5_horizon / _incumbent_objective) and that placements == the window
           op set (nothing beyond leaks in). Determinism: a direct probe showed
           the persist digest == the no-persist digest (identical), so
           persistence OBSERVES, never influences; the rolling-determinism golden
           is byte-identical (test_rolling_determinism_golden green).
           test_completeness_invariant_holds_on_the_PERSISTED_document counts the
           on-disk artifact.
  STATUS   DELIVERED.

CU2 -- the rolling document gains its interaction payload
  CLAIMED  the rolling document carries the interaction payload for the ACTIVE
           WINDOW; committed bars and tray items remain non-targets; additive
           contract bump; monolithic goldens byte-identical.
  PROVEN   assemble_rolling_document builds _interaction_block over the
           ACTIVE-WINDOW asgn_blocks only, so committed (frozen-front) bars carry
           NO interaction op and are non-targets BY CONSTRUCTION (the gesture
           surface only builds targets for ops in the payload); occupancy still
           comes from assignments[] (committed included), so committed work blocks
           a drop. Schedule contract 1.7 -> 1.8 (additive: interaction has existed
           since 1.2, split since 1.3; no new field). Monolithic
           defaults-reproduce-baseline golden byte-identical.
           test_rolling_document_carries_interaction_for_the_window asserts the
           payload ops == the active set and no committed op leaks in.
  STATUS   DELIVERED.

CU3 -- the two-beat endpoints accept a rolling schedule
  CLAIMED  POST .../sandbox/feasibility and the beat-two path work against a
           rolling schedule id; beat one first-feasible against the active window
           with committed work held via standing pins; beat two prices against the
           persisted window-0 incumbent; all 4B.3b invariants re-proven;
           no-committed-work now load-bearing; the forced infeasible contradiction
           demonstrable by gesturing at a committed slot on a REAL rolling run.
  PROVEN   feasibility_ghost/sandbox_pin_resolve gain restrict_op_ids (a shared
           _restrict_window) so the sandbox re-solves the WINDOW against the
           persisted incumbent -- aligned because the builder derives the same
           horizon over the same ops. The API's _rolling_gesture_context reads the
           persisted document and hands the endpoints the window op set + the
           frozen-front placements as standing pins. Beat one RELAXES the frozen
           front; beat two HOLDS it (committed_pins joined with any accepted-edit
           lineage pins). test_two_beat_runs_against_a_rolling_schedule proves
           no-money-by-construction, correlation, decomposition-sums-exactly, and
           no_committed_work_changes (asserted against the moves -- LOAD-BEARING,
           the frozen front is real committed work).
           test_forced_infeasible_contradiction_on_a_committed_slot forces the
           contradiction end to end on a real rolling run: gesture an active op at
           a committed slot -> beat one feasible, beat two infeasible NAMING the
           blocking commitment. test_forced_alternative_inherits_the_two_beat_
           shape_on_rolling proves the cross-machine pin runs the identical path.
           Playwright: rolling.two_beat.spec.mjs drives the full flow on the
           rolling fixture board, both themes.

           HONEST NUANCE (the "beat one holds committed via standing pins"
           wording): the CU brief phrased beat one as holding the frozen front,
           but the 4B.3b mechanism -- which this CU wires, not redesigns -- has
           beat one RELAX committed work so beat two can contradict it. Holding it
           in beat one too would make both beats infeasible on a committed-slot
           drop (no contradiction). The delivered behaviour (beat one relaxes,
           beat two holds) is what makes the forced contradiction real; that is
           the correct reading of "the mechanism 4B.3b proved rolling-ready."
  STATUS   DELIVERED.

CU4 -- the Explainer reads the rolling run (retires the R-AI1 entry)
  CLAIMED  the Interpreter/Explainer resolves questions against the persisted
           rolling snapshot + document; (a) why isn't {order} scheduled yet; (b)
           what's beyond the horizon / what's frozen; (c) ask why from the
           beat-two card reaches the conversational layer; zero-confident-wrong;
           two audit specimens (one answerable, one that must hedge); docs/04
           R-AI1 entry RETIRED.
  PROVEN   The three sliced-world routes (beyond-horizon, why-not-scheduled-yet,
           frozen) are registered in ROUTE_TAXONOMY (a closed set, not an ad-hoc
           bolt) and answered from the document via rolling_questions in a
           deterministic /ask pre-route (_try_rolling_answer), logged to the
           question ledger. why-not-scheduled-yet resolves the order name against
           the document's own vocabulary (the relevance guard) and HEDGES.
           Everything else falls through to the Explainer over the persisted
           window-0 snapshot exactly as a monolithic run:
           test_ask_why_on_machine_is_grounded_on_the_persisted_run proves CU4(c)
           "ask why" is a REAL grounded answer (the persisted assignment Decisions
           are the evidence), not a named-debt tip. Audit specimens:
           test_rolling_ask_why_not_scheduled_yet_is_answerable_for_a_tray_order
           (answerable) and test_rolling_ask_why_not_hedges_for_an_already_placed_
           order + test_rolling_ask_why_not_declines_cleanly_for_an_unknown_order
           (must hedge/decline). Frontend: the cockpit ask-why button auto-bridges
           to the ask panel on a rolling board (main.js onAskWhy -> panel.run of a
           composed "why is {order} on {machine}?"); rolling.two_beat.spec.mjs
           asserts the panel answers. docs/04 RETIRES the 4B.3a R-AI1 entry and
           its 4B.3b ask-why extension (both blocked consumers now unblocked).
  STATUS   DELIVERED. Scope of CU4(c) on the frontend: the ask-why auto-bridge is
           scoped to the rolling board (this session's subject); a monolithic card
           keeps its panel-pointer tip (the panel answers there too). The deeper
           "answer second-order questions FROM the sandbox card object itself"
           (which alternative, which ledger line moved, which family broke) is
           served today by asking the grounded Explainer (why-on-machine) + the
           existing edit-cost/edit-summary routes after accept; a card-object
           query API is not built and is named here.

CU5 -- riders
  CLAIMED  (a) the affected_orders column label says lateness/tardiness impact,
           never "cost impact"; fix if it overclaims. (b) name the per-order
           production-dollar debt in docs/04.
  PROVEN   (a) sandboxui.js: the affected-orders header now reads
           "affected orders -- lateness / tardiness impact" and the empty-cell
           fallback reads "no lateness change" (was "no cost change"). No header
           read "cost impact" before; the overclaim was the fallback string, now
           fixed. (b) docs/04 and CLAUDE.md name the debt: the extractor's ledger
           does not roll production cost per order (only tardiness is per-Demand),
           so the card's who-pays layer is tardiness-truth per order plus a
           whole-plan cost decomposition; a per-order production column is a ledger
           change, not this session.
  STATUS   DELIVERED.

================================================================================
UNDERDELIVERED / NAMED GAPS (explicit)
================================================================================
1. BEAT-TWO COST DELTA on a suboptimal incumbent. Beat two re-solves the active
   window holding only the committed front, so on a FEASIBLE (not proven-optimal)
   window-0 incumbent it can find a globally cheaper window arrangement and report
   a large favourable cost_delta that reflects re-optimizing the window, not the
   drag alone. This is HONEST (it is the true window cost with the op pinned vs
   the incumbent) and is the same behaviour the monolithic sandbox has on a
   suboptimal incumbent; a better-solved incumbent shrinks it. Not a defect;
   named so the number is read correctly.

2. CU4(c) DEEPER SANDBOX-CARD QUESTIONS. "ask why" reaches a real grounded
   why-on-machine answer; querying the sandbox RESULT OBJECT for second-order
   facts (which alternative, which ledger line moved, which family broke) has no
   dedicated API -- those are answered via the grounded Explainer + the existing
   edit-cost routes after accept. Named, not built.

3. CU5b PER-ORDER PRODUCTION-DOLLAR ATTRIBUTION. The ledger does not roll
   production cost per Demand; the card's who-pays layer is tardiness-truth per
   order + a whole-plan cost decomposition. A ledger change, not this session.

4. FRONTEND ASK-WHY BRIDGE SCOPE. The auto-bridge fires on a rolling board; the
   monolithic card keeps its panel-pointer tip (the panel answers either way).
   Extending the auto-bridge to monolithic cards is a trivial follow-up.

================================================================================
TEST RESULTS
================================================================================
Non-slow Python suite ............ 1239 passed, 0 failed, 20 skipped
                                   (the new rolling tests are SLOW -- a real solve
                                    + persist per fixture -- so the non-slow count
                                    is unchanged, as with 4B.3b)
Slow -- test_rolling_two_beat .... 11 passed (CU1 persisted-run readability +
                                   persisted-document completeness, CU2
                                   interaction payload, CU3 two-beat + no-committed
                                   + FORCED contradiction + forced-alt, CU4 rolling
                                   routes + why-not hedge/decline + why-on-machine
                                   grounding)
Slow -- TestRollingTwoBeatAPI .... 3 passed (served rolling doc + interaction, the
                                   two-beat through the HTTP surface, rolling
                                   questions through /ask)
Slow -- test_two_beat ............ 15 passed (4B.3b, unchanged)
Slow -- test_rolling_document .... green
Monolithic golden (baseline) ..... green (byte-identical)
Rolling determinism golden ....... green (byte-identical)
Cockpit JS (Playwright) .......... 176 passed  (was 168; +8 rolling two-beat,
                                   both themes)

================================================================================
FILES CHANGED
================================================================================
Backend:
  src/mre/modules/rolling_horizon.py     build_rolling_view(persist=...) -- window-0
                                         persisted as a first-class run (M5/M6/M7
                                         evidence + snapshot writer); RollingView
                                         gains win_horizon_start/end + persisted
  src/mre/modules/schedule_assembler.py  assemble_rolling_document builds the
                                         interaction payload over active-window ops;
                                         contract_version=CONTRACT_VERSION
  src/mre/modules/sandbox.py             _restrict_window + restrict_op_ids on
                                         feasibility_ghost / sandbox_pin_resolve
  src/mre/contracts/schedule_document.py CONTRACT_VERSION 1.7 -> 1.8 + history entry
  src/mre/modules/explainer.py           ROUTE_TAXONOMY += the three rolling routes
  src/mre/api/app.py                     _rolling_gesture_context + rolling wiring on
                                         both sandbox endpoints; _try_rolling_answer
                                         + _rolling_order_ref pre-route in /ask;
                                         persist=True in _execute_rolling_solve
Frontend:
  src/cockpit/src/interaction.js         thread onAskWhy into the controller
  src/cockpit/src/main.js                onAskWhy bridge (rolling board -> panel.run)
  src/cockpit/src/drag/controller.js     askWhy falls through to a tip only when the
                                         bridge doesn't handle it; tip text updated
                                         (R-AI1 debt retired)
  src/cockpit/src/drag/sandboxui.js      CU5a affected-orders label + fallback text
Tools / fixtures:
  tools/build_rolling_fixture.py         persist + capture the real two-beat
                                         (interaction/feasibility/sandbox/gesture +
                                         a forced contradiction); meta 1.8; strip
                                         inline interaction from schedule.json
  tests/cockpit/fixtures/rolling/*       regenerated (PYTHONHASHSEED=0) + new
                                         interaction.json / feasibility.json /
                                         sandbox.json / gesture.json
  tests/cockpit/fixtures/rolling_empty/* regenerated
Tests:
  tests/test_rolling_two_beat.py         new (11 slow)
  tests/test_api_endpoints.py            + TestRollingTwoBeatAPI (3 slow); 1.8 asserts
  tests/test_rolling_document.py         1.8 assert
  tests/test_schedule_document.py        1.8 assert
  tests/cockpit/rolling.two_beat.spec.mjs new (4 tests x both themes)
  tests/cockpit/gesture.spec.mjs         ask-why test title/comment updated (assertion
                                         unchanged -- new tip still says "conversational
                                         layer")
  tests/cockpit/playwright.config.mjs    testMatch += rolling.two_beat
Docs:
  docs/04-design-history.md              2026-07-23 Session 4B.3c amendment
                                         (R-AI1 retirement + CU5b debt)
  docs/07-roadmap.md                     v2.37
  CLAUDE.md                              position

================================================================================
COMMIT
================================================================================
Committed to master (4301e6f) and pushed.

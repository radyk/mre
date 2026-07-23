SESSION 4B.3b CLOSE-OUT -- the two-beat sandbox (R-T2 implemented)
Date: 2026-07-23
Repo: C:\dev\mre  (branch master)

================================================================================
SUMMARY
================================================================================
Made the Tier-2 sandbox and forced-alternative gestures a TWO-BEAT interaction
per R-T2. Beat one is a first-feasible feasibility ghost that carries NO money
by construction; beat two is the priced, layered delta card; a beat-two
contradiction is shown, never silently reconciled; beat one mints nothing.

No solver / model / schedule-document contract changes. The two-beat rides
module dataclasses + new API endpoints, so the monolithic AND rolling goldens
are byte-identical. Deterministic throughout (PYTHONHASHSEED=0, workers 1,
seed 42/0).

Headline scope note (read first): the session framed the two-beat "against the
ACTIVE WINDOW of a rolling document." The two-beat MECHANISM is rolling-correct
(committed work is held immovable via standing pins; the infeasible
contradiction IS a committed-work conflict), but wiring it against a LIVE
rolling document is blocked by two prerequisites the rolling path does not yet
build (no persisted window-0 incumbent; no interaction payload on a rolling
document). Those are the same connector-era work as the R-AI1 debt. The two-beat
is therefore DELIVERED and PROVEN on the substrate where the Tier-2 sandbox lives
today -- real monolithic solves + the gesture fixtures -- and is rolling-ready.
This is named as debt, not silently skipped. See "UNDERDELIVERED / NAMED GAPS".

================================================================================
PER-CU: CLAIMED vs PROVEN
================================================================================

CU1 -- beat one: the feasibility ghost (backend + board)
  CLAIMED  first-feasible endpoint; response type carries NO money by
           construction; renders in the R-M1 ghost class with a non-monetary
           provisional state; beat one mints nothing.
  PROVEN   feasibility_ghost() + POST /schedules/{id}/sandbox/feasibility. Uses
           CP-SAT stop_after_first_solution (additive default-off SolveRunner
           knob) under FEASIBILITY_BUDGET_S=2.0 / max_deterministic_time=1.0.
           FeasibilityGhost dataclass has no cost/delta/price/objective field.
           test_feasibility_ghost_has_no_monetary_field asserts field ABSENCE
           against _MONEY_FIELD_TOKENS (not emptiness). test_beat_one_mints_
           nothing: no child snapshot, no new canonical entity, zero Decision
           records. Board: .carry-bar.pricing-ghost register + a non-monetary
           "checking feasibility... / pricing..." card state; wording + motion
           are feel tokens. Proven by test_two_beat (fast + slow), the API test
           TestTwoBeatSandbox, and gesture.spec "R-T2 beat one".
  STATUS   DELIVERED.

CU2 -- beat two: the priced delta card (layered)
  CLAIMED  full budgeted re-solve correlated to beat one; an always-visible
           decision-sufficient layer; a detail layer whose cost lines sum
           exactly to the verdict; "ask why" hands second-order questions to the
           conversational layer; supersession is a perceivable transition.
  PROVEN   sandbox_pin_resolve enriched (one in-memory extract diffed vs base).
           Always-visible: cost_delta_abs; feasible/rejected; the moved-op
           placement; dominant_driver in driver_phrase language, HEDGED by price
           rank (docs/02 4.2, EARLINESS_PREFERENCE); affected_orders (top-N,
           per-Demand tardiness-$ + lateness-min deltas); lateness_delta_min;
           no_committed_work_changes ASSERTED against the moved-set. Detail:
           cost decomposition by ledger line (tardiness / setup / production-
           regular / production-overtime + explicit "other placement changes"
           REMAINDER) summing EXACTLY to cost_delta_abs -- test_beat_two_
           decomposition_sums_exactly enforces it (rollup_of). Correlation:
           two beats share correlation_id (test + API test). Supersession:
           .delta-card.superseded transition, sandbox.supersede_ms feel token.
           "Ask why": ships and routes to a graceful named-debt response (see
           the R-AI1 note below). Frontend layered card proven in gesture.spec
           "R-T2 CU2" (always-visible decision-sufficient; detail collapsed).
  STATUS   DELIVERED, with two honest limitations named:
           (a) affected_orders carries per-Demand TARDINESS and LATENESS deltas
               (the per-Demand truth from the service outcomes); it does NOT
               carry per-order PRODUCTION dollars, which the ledger does not roll
               up per order. Cost-by-line decomposition (whole-plan) is exact;
               per-order is tardiness/lateness only.
           (b) the "ask why" hand-off is the graceful named-debt path, not a live
               conversational hand-off (R-AI1 connector debt, extended not
               double-booked).

CU3 -- the contradiction path (R-T2(4))
  CLAIMED  beat-two infeasible => R-M1 rejection; materially-moved => the ghost
           visibly relocates; build a deterministic fixture forcing EACH; if the
           infeasible case cannot be forced, prove the code path with a unit test
           and name the gap.
  PROVEN   INFEASIBLE: FORCED end-to-end on the distinct fixture (two ops on one
           resource; hold B as a standing pin, drop A onto B's slot -> beat one
           feasible [relaxed], beat two infeasible [holds B]).
           test_contradiction_infeasible_is_forced_via_a_standing_pin RUNS (not
           skips -- verified with -rs). Frontend: R-M1 snap-back with reason
           (gesture.spec "CONTRADICTION (infeasible)").
           MOVED: the inverse of the session's expectation was found and named --
           a pinned op is pinned to the SAME (resource,start) in BOTH beats, so
           under exact-pin semantics the pinned op can NEVER relocate between
           beats. Forcing a real backend relocation of the pinned op is therefore
           impossible with current constraint coverage. Per the session's
           fallback: the MOVED code path is proven at UNIT level
           (TestContradictionDetector, hand-built inputs, both branches) and
           exercised in the frontend via a canned feasibility.json whose ghost
           start is shifted relative to the pin (gesture.spec "CONTRADICTION
           (moved)" asserts .carry-bar.relocating before the card lands). What
           DOES diverge in a real solve is the CONSEQUENCE set (neighbours settle
           differently because beat two holds committed work); the moved-set
           already renders that.
  STATUS   DELIVERED. Infeasible forced end-to-end; moved unit-proven + frontend-
           exercised, with the "pinned op cannot relocate between exact-pin beats"
           gap named here and in docs/04.

CU4 -- forced alternatives inherit the shape
  CLAIMED  the forced-alternative gesture (pin an op to a chosen resource) runs
           the IDENTICAL two-beat path; one end-to-end test.
  PROVEN   A cross-machine pin is exactly a chosen-resource pin through the same
           feasibility_ghost() -> sandbox_pin_resolve() path, no parallel
           machinery. test_forced_alternative_gesture_runs_the_same_two_beat_path
           (beat one feasible, beat two prices it, decomposition still sums
           exactly). Cockpit drop-onto-a-priced-ghost renders the same layered
           card (gesture.spec "CU4").
  STATUS   DELIVERED.

CU5 -- tests + screenshots
  CLAIMED  Playwright both themes (ghost / supersession / layered card /
           rejection / forced-alt); Python (no-money contract; mints-nothing;
           correlation; decomposition-sums; no-committed-work; both contradiction
           fixtures or the named fallback; forced-alt e2e); deterministic;
           beat-two reproducible under the seed.
  PROVEN   Python tests/test_two_beat.py: 9 fast (no-money contract, correlation
           determinism, contradiction detector both branches) + 6 slow
           (correlation, decomposition-sums-exactly, no-committed-work-with-a-
           standing-pin, mints-nothing, forced infeasible contradiction, forced-
           alt e2e) -- 15 passed, no skips. tests/test_api_endpoints.py
           TestTwoBeatSandbox (3): beat-one no-money key, correlation +
           decomposition, 404. Cockpit gesture.spec: 6 new tests x both themes
           (feasibility ghost / layered card / infeasible + moved contradictions
           / ask-why named-debt / forced-alt). Determinism: beat one uses
           workers=1 + seed 0 + max_deterministic_time; beat two matches the
           existing deterministic sandbox.
  STATUS   DELIVERED.

================================================================================
UNDERDELIVERED / NAMED GAPS (explicit)
================================================================================
1. ROLLING ACTIVE-WINDOW wiring is NAMED DEBT, not delivered against a live
   rolling document. Two prerequisites are missing on the rolling path:
     (a) the rolling snapshot persists NO window-0 assignments (prepare_plant
         runs M0-M4 only; build_rolling_view extracts in-memory with
         snapshot_writer=None) -- so the sandbox has no incumbent to warm-start /
         diff against;
     (b) a rolling document carries no interaction payload -- so the cockpit
         cannot compute Tier-0 for a rolling board.
   Both are the same connector-era work as the R-AI1 debt (a rolling run
   persisting a canonical snapshot the Explainer reads). The two-beat MECHANISM
   is rolling-ready (committed work held immovable via standing pins; the
   infeasible contradiction IS a committed-work conflict), and is delivered +
   proven on real monolithic solves + the gesture fixtures.

2. "ASK WHY" hands off to a graceful NAMED-DEBT response, not a live
   conversational hand-off. The Interpreter/Explainer reads a persisted snapshot,
   not the live sandbox context. This is the SAME R-AI1 rolling-explainer
   connector debt; the docs/04 4B.3a entry was EXTENDED with this second blocked
   consumer (not double-booked). The affordance ships and states the debt; the
   sandbox context is stashed on the hook for a future bridge.

3. The MATERIALLY-MOVED contradiction of the PINNED op cannot occur in a real
   solve (the op is pinned to the same placement in both beats). Proven at unit
   level + frontend-exercised; the real-solve divergence is the consequence set,
   which the moved-set already shows. Named in docs/04 and CU3 above.

4. affected_orders is per-Demand tardiness/lateness only (no per-order production
   dollars -- the ledger does not roll production per order). The whole-plan cost
   decomposition IS exact and per-line.

================================================================================
TEST RESULTS
================================================================================
Non-slow Python suite ............ 1239 passed, 0 failed, 20 skipped  (was 1227; +12)
Slow two-beat (test_two_beat) .... 15 passed, 0 skipped
Slow sandbox + planner_edit ...... 23 passed
Monolithic golden (defaults) ..... green (byte-identical)
Rolling document + API ........... green
Rolling determinism golden ....... green (byte-identical)
Cockpit JS (Playwright) .......... 168 passed  (was 156; +12, both themes)

================================================================================
FILES CHANGED
================================================================================
Backend:
  src/mre/modules/solve_runner.py        + stop_after_first_solution knob
  src/mre/modules/sandbox.py             FeasibilityGhost + feasibility_ghost() +
                                         correlation_id_for + beat_two_contradicts
                                         + enriched SandboxResult / priced card
  src/mre/api/app.py                     FeasibilityRequest + POST .../sandbox/
                                         feasibility; correlation_id on SandboxRequest
Frontend:
  src/cockpit/src/api.js                 postFeasibility
  src/cockpit/src/interaction.js         wire postFeasibility into the api object
  src/cockpit/src/drag/controller.js     twoBeat / _beatTwo / applyResultTwoBeat /
                                         beatTwoContradicts (JS mirror) / askWhy /
                                         markCarryGhost + state() probe
  src/cockpit/src/drag/sandboxui.js      showPricing + the layered showResult
  src/cockpit/src/drag/feel.js           sandbox.{feasibility_budget_s, detail_open,
                                         supersede_ms} + --sandbox-supersede mirror
  src/cockpit/src/drag.css               R-T2 ghost / superseded / layered-card styles
Tests:
  tests/test_two_beat.py                 new (15 tests)
  tests/test_api_endpoints.py            + TestTwoBeatSandbox (3)
  tests/cockpit/gesture.spec.mjs         + 6 R-T2 tests; 2 existing tests open the
                                         new detail disclosure
  tests/cockpit/fixture-server.mjs       /sandbox/feasibility route + beat-two enrich
  tests/cockpit/fixtures/distinct/feasibility.json   new (forces the CU3 cases)
Docs:
  docs/04-design-history.md              2026-07-23 Session 4B.3b amendment
  docs/07-roadmap.md                     v2.36
  CLAUDE.md                              position

================================================================================
COMMIT
================================================================================
Committed to master and pushed.

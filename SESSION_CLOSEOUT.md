SESSION 4B.3a CLOSE-OUT  --  the cockpit renders the sliced world (read-only)
Date: 2026-07-23        Repo root: C:\dev\mre        Branch: master

===============================================================================
FIRST ERRAND -- repository relocation confirmation (mandated)
===============================================================================
git fsck --full            : CLEAN (exit 0)
non-slow suite (relocation): 1219 passed, 0 failed, 117 skipped
                             (matches the 4B.2d baseline; includes
                             test_render_fail_closed.py with the SDK installed)

Relocation defect found + fixed: the editable install path finder
  __editable__.mre-0.0.1.pth (user site-packages) still pointed at
  C:\Users\radke\OneDrive\Documents\PythonProjects\mre\src -> "import mre" failed
  and the WHOLE suite errored on collection. Repointed at C:\dev\mre\src.
  No in-repo file referenced the retired path.

===============================================================================
PER-CU  --  claimed vs proven
===============================================================================

PART 1  R-T2 transcription
  Claimed  : transcribe R-T2 (two-beat Tier-2 contract) verbatim into docs/04.
  Proven   : DONE. Verbatim in docs/04 2026-07-23 amendment, marked
             "IMPLEMENTED IN 4B.3b, recorded now". Not implemented this session
             (correct -- 4B.3a is read-only, no Tier-2).

CU1  the rolling schedule document (the spine)
  Claimed  : (a) per-assignment commitment state + document-level beyond-horizon
             list; (b) window metadata; (c) COMPLETENESS INVARIANT enforced with
             a counting test; assembler consumes a RollingResult/view; API serves
             it via the existing registry; monolithic docs byte-identical.
  Proven   : DONE.
    - contract 1.6 -> 1.7 additive: AssignmentBlock.commitment_state
      (committed | active_window; None on monolithic), ScheduleDocument.rolling
      (RollingBlock: frozen_until, window span, reference origin, window/frozen
      days, committed/active counts, beyond_horizon list of BeyondHorizonItem).
    - rolling_horizon.build_rolling_view (solve window 0; same _admit +
      _two_stage_solve as the full roll) -> RollingView.
    - schedule_assembler.assemble_rolling_document (duck-typed; no import cycle).
    - COMPLETENESS INVARIANT: _assert_rolling_completeness RAISES on overlap or a
      demand in no bucket; test_rolling_document::test_completeness_invariant_
      every_demand_counted COUNTS the partition.
    - API: SolveRequest.sliced=true -> _execute_rolling_solve registers a
      contract-1.7 document (test_api_endpoints::TestRollingSolve).
    - Monolithic goldens byte-identical (test_defaults_reproduce_baseline green;
      every 1.7 field None/empty-defaulted).
  Tests    : test_rolling_document.py (1 fast + 4 slow), TestRollingSolve (slow).
  Note     : the rolling document renders the plant AS OF the reference origin
             (window 0) -- "committed" = the frozen front (imminent, locked),
             not committed-PAST work from prior rolls. This is the state a
             rolling planner sees now; it is the honest current-window view and
             is what populates the tray. Named here so it is understood, not a
             surprise.

CU2  the board renders it (read-only)
  Claimed  : committed bars distinct/static; labeled frozen-front marker;
             active-window bars normal; a docked beyond-horizon TRAY (empty state
             shows zero, not hidden); tokens; Playwright coverage of mixed board,
             boundary marker, populated tray, empty tray.
  Proven   : DONE.
    - board.js: committed bars carry a LOCKED class (teal inset edge + faint
      veil, static, no gesture); active_window bars render normally.
    - markers.js setFrozen: a labeled teal boundary line at frozen_until,
      0px drift tracking.
    - tray.js: docked panel, count badge, one row per future order (work_order +
      due, planner vocabulary, no UUID); empty state "Nothing beyond the horizon".
    - tokens.css + theme-light/theme-dark: all new colors/geometry tokenized.
    - legend gains committed + frozen swatches on a rolling board.
    - Fixture is a REAL assembled contract-1.7 document
      (tools/build_rolling_fixture.py): populated = 40-order pilot_scale
      window-10/frozen-1 -> 12 committed + 26 active + 22 in tray;
      empty = 18 bars, empty tray. Committed so CI needs no solver.
  Tests    : tests/cockpit/rolling.spec.mjs (5 tests x 2 themes = 10). Full
             cockpit JS suite 146 -> 156, all green (both themes).
  Fixed    : a LATENT fixture-server crash -- the interaction endpoint wrote
             headers (200) before a load() that fails when a fixture has no
             interaction.json (a 1.7 rolling doc carries none) -> the whole
             server died with ERR_HTTP_HEADERS_SENT (every test after the first
             got CONNECTION_REFUSED). Fixed to loadMaybe + 404 (mirrors the real
             API).

CU3  AI reachability (R-AI1)
  Claimed  : answer "what's beyond the horizon?", "why isn't {order} scheduled
             yet?" (hedged), "what's frozen?"; route through existing taxonomy
             where it reaches, else name the R-AI1 debt.
  Proven   : PARTIAL BY DESIGN (debt named, per the instruction).
    - rolling_questions.py answers all three deterministically, planner-voiced,
      ID-free, hedged (the beyond-horizon estimate is never presented as a
      placement). test_rolling_questions.py (7 fast units) against the REAL
      committed fixture. The cockpit exercises it hermetically via the rolling
      fixture asks.json.
  UNDERDELIVERED / NAMED R-AI1 DEBT (docs/04):
    - NOT wired into the free-phrasing Interpreter, the question ledger, or the
      deterministic ROUTE_TAXONOMY. The M10 Explainer answers over a persisted
      canonical snapshot + evidence index; a rolling run's sliced state lives in
      the schedule document's RollingBlock, NOT in a snapshot the Explainer reads.
      Clean taxonomy wiring requires rolling runs to persist a canonical snapshot
      the Explainer reads (the connector-era work). No ad-hoc route was bolted
      onto the router -- the debt is named instead, exactly as the prompt
      directed ("where it cannot [route], name the R-AI1 debt explicitly").

CU4a  pyproject dev extras
  Claimed  : add anthropic; same-commit lock update if a lock covers dev.
  Proven   : DONE. anthropic>=0.40 added to [project.optional-dependencies].dev.
             No lock covers dev extras -- requirements.lock is the RUNTIME lock,
             and anthropic is correctly ABSENT from it (the runtime import is
             lazily/try-guarded, fail-closed). So no lock update was needed.

CU4b  the audit-corpus attribution-limitation specimen
  Claimed  : a capacity-forced op on a dearer machine with earliness_value > 0,
             asked "why is this op on the dearer machine?"; graded-correct answer
             HEDGES (attributes the preference AND names capacity pressure may
             bind); a confidently unhedged single-cause answer grades wrong.
  Proven   : DONE.
    - Product change: planner_language.driver_hedge / DRIVER_ATTRIBUTION_HEDGE;
      explainer._explain_why_on_machine appends the hedge when the driver is
      EARLINESS_PREFERENCE. Answer now reads: "... a declared earliness
      preference ... -- though I'm attributing this by price alone, so I can't be
      certain the earlier start was the real reason rather than the cheaper
      machine simply being busy at the time (capacity pressure can bind here
      too)."
    - Fixture: glass_box mutated (earliness_value=0.05, PRESS-SLOW $60->$61). The
      rate delta is economically negligible (monolithic solves don't add
      earliness to the objective; the extractor uses it only for attribution), so
      ORD-06 stays capacity-forced onto PRESS-SLOW but is attributed
      EARLINESS_PREFERENCE by price rank (docs/02 section 4.2).
    - Specimen: TestAuditCorpusEarlinessHedge + an entry in the standing
      zero-confident-wrong corpus (test_cu10_zero_confident_wrong). Both pass.

===============================================================================
VERIFICATION
===============================================================================
Full non-slow Python suite : 1227 passed, 0 failed, 123 skipped  (+8 vs 1219)
Monolithic solver goldens  : byte-identical (test_defaults_reproduce_baseline)
Slow rolling ladder        : green (determinism golden, frozen-front, absolute
                             origin, gravity counterfactual, roll-converges,
                             + 4 new rolling-document + 1 rolling-API)
Slow AI ladder             : green (earliness hedge specimen + zero-confident-
                             wrong corpus incl. the new specimen)
Cockpit JS (Playwright)    : 156 passed (light + dark)  (+10 rolling)

===============================================================================
SAME-COMMIT SPEC / DOC UPDATES
===============================================================================
src/mre/contracts/schedule_document.py : contract 1.6 -> 1.7 (version history)
docs/04-design-history.md              : relocation + R-T2 verbatim + 4B.3a
                                         amendment + R-AI1 debt
docs/07-roadmap.md                     : v2.34 -> v2.35
CLAUDE.md                              : repo root + 4B.3a position block

===============================================================================
FILES
===============================================================================
New:
  src/mre/modules/rolling_questions.py       (CU3 answers)
  src/cockpit/src/tray.js                     (CU2 beyond-horizon tray)
  tests/cockpit/rolling.spec.mjs              (CU2 Playwright)
  tests/cockpit/fixtures/rolling/*            (real contract-1.7 fixture)
  tests/cockpit/fixtures/rolling_empty/*      (empty-tray fixture)
  tests/test_rolling_document.py              (CU1)
  tests/test_rolling_questions.py             (CU3)
  tools/build_rolling_fixture.py              (regenerates the committed fixture)
Modified (spine):
  src/mre/contracts/schedule_document.py      (contract 1.7)
  src/mre/modules/rolling_horizon.py          (build_rolling_view + RollingView)
  src/mre/modules/schedule_assembler.py       (assemble_rolling_document)
  src/mre/api/app.py                          (SolveRequest.sliced +
                                               _execute_rolling_solve)
  src/mre/modules/explainer.py                (CU4b hedge)
  src/mre/modules/planner_language.py         (CU4b driver_hedge)
Modified (cockpit read layer):
  src/cockpit/src/board.js, main.js, markers.js
  src/cockpit/src/cockpit.css, tokens.css, theme-light.css, theme-dark.css
Modified (harness + tests + config):
  tests/cockpit/fixture-server.mjs            (interaction loadMaybe+404 fix)
  tests/cockpit/playwright.config.mjs         (rolling spec on light+dark)
  tests/test_ai_voice.py                      (CU4b specimen + corpus)
  tests/test_api_endpoints.py                 (contract 1.7 asserts + rolling test)
  tests/test_schedule_document.py             (contract 1.7 assert)
  pyproject.toml                              (anthropic dev extra)
  src/cockpit/package-lock.json               (npm removed a stale
                                               @playwright/test entry not in
                                               package.json -- benign cleanup)

===============================================================================
NOT DONE / DEFERRED (named)
===============================================================================
- CU3 taxonomy/interpreter/ledger wiring: NAMED R-AI1 DEBT (above). The three
  rolling questions are answerable deterministically today; the free-phrasing +
  ledger integration waits on rolling runs persisting an Explainer-readable
  snapshot.
- R-T2 implementation: 4B.3b (this session is read-only by design).
- The rolling document is the current-window (window-0) view; a mid-roll view
  with committed-PAST bars is not modeled (the frozen front is the commitment
  the planner is locked into now). Named under CU1.

SESSION 4A.5c CLOSE-OUT
R-AI5 part 3: telemetry, the Pareto, the promotion pipeline -- the arc closes
2026-07-26

Deterministic settings for all solver work: PYTHONHASHSEED=0, --solver-workers 1,
--solver-seed 0 (the glass_box pinned world the sweep asks against); seed 42 for the
pinned ROLLING run.

Scope: backend + contracts + two governed-prompt bumps + banks + tests + cockpit +
docs. NO solver / model / schedule-contract change. NO golden moved -- the pinned
rolling run is a NEW fixture, built by a committed script into gitignored scratch,
exactly as the monolithic exam world is.

======================================================================
SUMMARY
======================================================================
Parts 1 and 2 both WROTE per-claim provenance to the question ledger and neither
READ it back. R-AI5(5) makes that provenance the standing prioritization for
promoting recurring shapes; R-AI5(7) makes the promotion loop autonomous up to a
human gate and the demotion automatic past it. Three things were open: the
telemetry, the loop, and one keyword matcher. All three are closed.

  the ledger  -> now carries what the PARSE named, because every second-tier answer
                 takes the same route and the route alone cannot tell two shapes
                 apart
  the report  -> emitted automatically at the end of every sweep: residue clustered
                 into recurring shapes, ranked by a frequency-weighted Pareto, with
                 R-AI5(6)'s protection printed in its own header
  the loop    -> dossier (autonomous) -> review (human) -> probation shadow ->
                 demotion (automatic). Walked end to end once, for real.
  the matcher -> classify_rolling is DELETED. No deterministic classifier remains
                 anywhere in the ask path.

The one promotion this session performed was not chosen by a designer. The telemetry
ranked it first, a machine drafted its dossier, and the working thread signed it.

AND THEN THE SWEEP FOUND WHAT THE DOSSIER COULD NOT. With `lateness-cause` nameable,
"but why" -- a DEEPEN follow-up on one selected order, one turn after that order's
cause chain -- parsed as `lateness-cause` and answered about the whole plan. The
dossier was clean, the harness validation was clean, the shadow diff was clean, and
the promotion still broke a question that was NOT the promoted shape. That is the
entire argument for R-AI5(7)'s asymmetry, and this session produced it by accident on
the first cycle.

======================================================================
PART 1 -- PER-CU: CLAIMED vs PROVEN
======================================================================

CU1 -- provenance telemetry + the Pareto (R-AI5(5)/(6))
-------------------------------------------------------
CLAIMED: a standing report, runnable against any ledger AND emitted automatically at
         the end of every ai_exam sweep beside the sidecar; questions by tier;
         synthesis residue clustered into RECURRING SHAPES with the clustering
         method stated honestly; per-cluster frequency, verified/interpretive ratio
         and exemplars; the frequency-weighted Pareto ordering; R-AI5(6) IN THE
         REPORT ITSELF, marking takes/aggregate reads NOT-PROMOTABLE-BY-DESIGN and
         never counting them as backlog; a test proving a hand-built ledger yields
         the expected clusters and ordering.
PROVEN:  src/mre/contracts/question_ledger.py -- ParseProvenance (intent, nearest,
         subject_kinds, polarity, followup_of, confidence, prompt_version,
         dropped_qualifier). SynthesisProvenance claims gain `kind`, so the report
         can tell an interpretive FACT from an interpretive CONCLUSION.
         src/mre/modules/provenance_report.py -- LedgerRow, ShapeCluster, cluster(),
         pareto(), tier_counts(), render_report(), report_payload(), write_report();
         plus rows_from_sweep(), which reconstructs rows from a committed sweep's
         transcripts and FLAGS every one of them `adjacency-unknown` rather than
         presenting a weaker method as the same one.
         tools/provenance_report.py -- the CLI. tools/run_ai_exam_sweep.py writes
         ledger.jsonl and emits PROVENANCE.txt + PROVENANCE.json; when there are no
         ledger rows it prints SKIPPED, never clean.
         The method, printed in the report: adjacency + subject kinds + DOMINANT
         TOOL, with the reason the whole call SET is not the key (it split "why so
         many late orders" from "cant you just make it cheaper" into two clusters of
         one), and the statement that the method is not semantic, splits shapes and
         therefore UNDER-states frequency.
         Weight = frequency x verified share, with the reason stated.
         R-AI5(6): three protection reasons, each a statement about the EVIDENCE;
         protected clusters excluded from the Pareto; the ruling quoted in the
         header; the dossier generator REFUSES to draft a protected cluster.
         tests/test_provenance_report.py -- 13 tests over hand-built ledgers: the
         three cluster keys, the dominant-tool rule, synthesis-only clustering, each
         protection reason, the header text, frequency-weighted-not-frequency
         ordering, cumulative-over-promotable-only, deterministic tie-breaking, the
         JSON twin, and reconstruction flagging.

CU2 -- the promotion pipeline (R-AI5(7))
----------------------------------------
CLAIMED: (a) autonomous dossier generation -- frequency, exemplars, the
         evidence-assembly pattern from verified tool-call transcripts, a DRAFT
         route on a clearly marked path, harness validation replaying the cluster's
         historical questions under the draft vs their synthesis answers, diffed for
         fact agreement and provenance strengthening; a committed artifact NEVER
         wired into dispatch. (b) the gate as documented process, and ONE FULL CYCLE
         PERFORMED as the proof, with the dossier cited as authority. (c) probation
         metadata, both paths run and diffed during probation, a loud sidecar signal
         on divergence, demotion as a mechanical flag flip -- automatic on
         divergence, never automatic in the other direction, both tested.
PROVEN:  (a) tools/promotion_dossier.py -- writes
         docs/promotions/aggregate-lateness-2026-07-26.md and
         docs/promotions/drafts/aggregate-lateness_route_draft.py (a path nothing
         imports). Validation: `--validate-with lateness-cause` replayed both
         historical questions against the pinned world -- 0 raised, 0 contradicted,
         2 of 2 strengthened provenance, CLEAN.
         (b) THE CYCLE, in order: 4A.5b banks replayed with the candidate intent
         DEMOTED (the session's own flag, reproducing the pre-promotion vocabulary);
         the report ranked `late-orders|no-subject|lateness_set` first by frequency
         AND weight; the dossier was drafted and validated; the working thread
         reviewed it; `lateness-cause` joined Intent + INTENT_MEANINGS +
         ROUTE_TAXONOMY + ROUTE_OFFERS + the assembler
         (Explainer._explain_lateness_cause) + AUTHORED copy + parse prompt v7 + a
         PROMOTIONS entry citing the dossier, status `probation`. The gate is
         documented as process in the docs/04 amendment.
         (c) src/mre/contracts/promotion.py -- ProbationStatus, Promotion,
         PROMOTIONS, demoted_intents(), shadowed_intents(), ShadowDiff,
         PROBATION_SWEEPS. src/mre/modules/shadow.py -- diff_claims() (THE ONE DIFF,
         used by both the probation and the dossier's validation), shadow_diff(),
         run_shadow(). Demotion: Promotion.demote() -> the intent leaves
         model_selectable_intents() -> the prompt stops offering it -> the parse
         cannot name it -> the shape returns to synthesis; a demoted id emitted from
         memory coerces to `unmatched`.
         tests/test_promotion.py -- 32 tests: the gate's paperwork (every promotion
         cites a dossier that EXISTS on disk; a promoted intent is a real route in
         all four tables; exactly one promotion this session; the generator writes
         only under docs/promotions/ and changes no vocabulary on import), demotion
         in four aspects, the absence of any promote() transition, and the diff --
         agreement, contradiction, only-one-side, interpretive-never-diverges,
         cut-never-diverges, agreement-wins, the unit gate, the timestamp strip, the
         entity-ref strip, money with and without a symbol, rounding, thousands
         separators, list-facts excluded, provenance strengthening, and
         UNCHECKED-never-clean.

CU3 -- felt-bar residue
-----------------------
CLAIMED: (a) the tier announces itself immediately -- an authored "reading the
         evidence" state the moment synthesis begins, replaced by the answer, an
         honest non-answer beat first and never a fake answer; ship the two-phase
         version and name the residue if streaming is disproportionate. (b) the
         synthesis couldn't-answer keeps the nearest-capabilities offers, authored,
         absence-tested. (c) a stated-qualifier-dropped signal in the parse contract
         (prompt v7) diverting a near-miss match to synthesis, with the rendered-by
         naming why; tested on the two founder shapes plus negatives; the two unmet
         expectations flip to met.
PROVEN:  (a) POST /schedules/{id}/ask/preflight (api/app.py::_preflight) returns
         {tier, waiting, intent} -- parse only, no assembly, no answer.
         interpreter.tier_of() computes the tier from the SAME dispatch rules the
         answer follows. interpreter.ParseMemory + PARSE_MEMORY make it cost NO
         EXTRA MODEL CALL. ask_fallback_copy.WAITING_SYNTHESIS /
         WAITING_SYNTHESIS_DIVERTED / WAITING_ROUTE. Cockpit: api.js askPreflight()
         (resolves to the route tier on any failure), askpanel.js appendWaiting() +
         removal on both success and error, cockpit.css .waiting with a
         reduced-motion branch. Fixture server serves the endpoint. RESIDUE NAMED:
         the beat states the tool BUDGET, not a live count.
         (b) ask_fallback_copy.SYNTHESIS_FLOOR_DOORS; offers carried on every
         synthesis bundle and rendered ONLY on the couldn't-answer; chosen by what
         the planner named; absence-tested.
         (c) ParsedQuestion.dropped_qualifier; parse_prompt.md v7 rule 9 (three
         admitted families, four explicit non-qualifiers, "you report; you do not
         decide"); dispatch step 4b; _rendered_by names the qualifier.
         tests/test_felt_bar.py -- 30 tests. BOTH FOUNDER SHAPES ARE MET IN THE
         LIVE SWEEP.

CU4 -- the rolling pre-route retires
------------------------------------
CLAIMED: the prerequisite first -- subject resolution gains the ROLLING document's
         vocabulary (window-0 + tray + committed) so a tray order resolves as a real
         subject with a BEYOND-HORIZON disposition instead of absent; then
         classify_rolling dies, the rolling intents join the parse vocabulary with
         authored meanings, dispatch reaches the existing answerers, and the
         deterministic matcher is DELETED, not bypassed; a pinned rolling run;
         tray-order questions parse and answer; the founder's sliced-board
         phrasings; the absent-vs-beyond-horizon distinction pinned.
PROVEN:  rolling_questions.RollingVocabulary (three regions, unique-substring
         resolution, falsy on a monolithic document);
         contracts.parse.SubjectDisposition + SubjectRef.disposition/beyond_horizon;
         question_parser.bind_subjects(rolling=...); interpreter dispatch step 0 (the
         tray check, ahead of every honest-failure branch) and step 4c (the three
         rolling intents); Explainer._rolling_bundle; the `rolling` subject type on
         the authored-copy and header-only render paths.
         classify_rolling and its three trigger tuples are DELETED, and
         tests/test_rolling_questions.py asserts the SYMBOL'S ABSENCE.
         tools/build_rolling_exam_run.py builds the pinned run (pilot_scale, 40
         orders, window 14d / frozen 3d, deterministic seed 42, window 0 persisted;
         56 bars -- 38 committed, 18 active, 14 in the tray).
         tests/ai_exam/banks/sweep_rolling.txt -- 17 questions, 17 graded.
         tests/test_rolling_dispatch.py -- 16 tests including the pin from both
         sides.

CU5 -- the arc-closing sweep
----------------------------
CLAIMED: the ENTIRE bank set + a rolling bank (12+ questions) + probation shadow
         checks, live; every mechanical signal strictly-no-worse than
         2026-07-26-synthesis; the two adjacent-match expectations MET; the promoted
         route's shadow diff clean; the provenance report emitted and committed;
         latency, parse quality, tier counts and the first REAL Pareto stated.
PROVEN:  tests/ai_exam/sweeps/2026-07-26-arc-close/ -- 7 banks, 321 questions, live.
         109/110 graded expectations met; 92/93 on the SHARED expectations, up from
         the baseline's 90/93; 17/17 on the new rolling bank. Both adjacent-match
         expectations MET. Shadow: 3 shadowed, 3 clean, 0 diverged, 0 unchecked.
         PROVENANCE.txt + .json committed.
UNDERDELIVERED, EXPLICITLY: "every mechanical signal strictly-no-worse" is NOT
         achieved. ungrounded-load-bearing went 0 -> 3. See PART 3.

CU6 -- docs + the arc close
---------------------------
PROVEN:  docs/04 amendment (append-only, 416 insertions, 0 deletions); docs/07 v2.46
         same-day; CLAUDE.md's ask-path paragraph in final form + the
         promotion/demotion process + position; RUBRIC.md gains GRADING A PROMOTED
         ROUTE, the two new sidecar signals, precedent 6 RESOLVED, and three new
         OPEN entries stating the CU3 items' expected behaviours for round five.

======================================================================
PART 2 -- THE CU5 TABLES
======================================================================

PER BANK
  bank                    q   graded   route med   synth med   findings
  regression_founder     28      --      1580 ms     8212 ms   clean
  regression_founder_r4  15    15/15     1389 ms        --     clean
  sweep_rolling          17    17/17     1233 ms        --     absent-entity 1 *
  sweep_routes          120      --      1310 ms        --     clean
  sweep_scenarios        49    47/48     1607 ms     6571 ms   expect-miss 1
  sweep_synthesis        30    30/30     1084 ms    11736 ms   u-l-b 1
  sweep_traps            62      --      1625 ms     8518 ms   absent-entity 3,
                                                               u-l-b 2
  TOTAL                 321   109/110
  * the rolling bank's OWN deliberate control ("why is ORD-999999 late"), graded MET
    as unknown-entity -- the other side of the tray pin.

MECHANICAL SIGNALS (vs the 2026-07-26-synthesis baseline)
  exception                 0   (baseline 0)
  empty                     0   (baseline 0)
  validator                 0   (baseline 0)
  dark-evidence             0   (baseline 0)
  dead-door                 0   (baseline 0)
  target-unloadable         0   (baseline 0)
  failed-claim-rendered     0   (baseline 0)
  shadow-divergence         0   (new signal)
  shadow-unchecked          0   (new signal)
  absent-entity             3 on the SHARED banks -- IDENTICAL to the baseline's 3
                            (+1 in the new rolling bank, its own control)
  expect-miss               1   (baseline 3)
  ungrounded-load-bearing   3   (baseline 0)  <-- WORSE. Named in PART 3.

LATENCY, BY TIER (the probation shadow EXCLUDED -- a planner never pays it)
  parse + contracted route    n=287   median  1377 ms   p90  2791 ms
  parse + synthesis           n= 34   median  9297 ms   p90 18299 ms
  baseline: route n=272 median 1275 / p90 2502; synthesis n=32 median 9659 / p90
  16030. Essentially unchanged -- which matters, because that gap is what the CU3(a)
  first beat exists for.

PARSE QUALITY
  parses 334, calls 335, retries 1, malformed 2, clarifies 10, unavailable 0,
  median 1159 ms.
  baseline: 317 / 317 / 0 / 0 / 6 / 1050 ms. Slightly worse on retries, malformed
  and median, on a prompt that grew by a new intent and a new rule. Single-digit
  counts on a live model; stated, not excused.

TIER COUNTS
  contracted routes 276 | synthesis 34 (10 honest couldn't-answers) | honest floor 11
  claims 99 -- VERIFIED 36, INTERPRETIVE 58, FAILED-and-cut 5 (3 load-bearing, each
  said out loud). 91 tool calls, 0 budget exhaustions, 0 timeouts.
  Verified share 38% (baseline 43%).
  tool histogram: machine_occupancy 22, placements_for_machine 15,
  entity_vocabulary 14, cost_ledger 13, lateness_set 13, placements_for_order 7,
  placements_in_window 4, fetch_record 2, calendars 1.

PROBATION (R-AI5(7))
  lateness-cause: shadowed 3, clean 3, DIVERGED 0, unchecked 0, provenance
  strengthened 1. PROBATION_SWEEPS = 2, so this sweep and one more serve the window.

THE FIRST REAL PARETO (PROVENANCE.txt, committed)
  34 synthesis answers -> 30 shapes: 13 promotable, 17 NOT-PROMOTABLE-BY-DESIGN
  (10 predominantly interpretive, 5 conversational, 2 takes). More than half of what
  the second tier answers is residue R-AI5(6) protects -- a report ranking by
  frequency alone would have listed all 17 as backlog.

  rank  weight  cum%   frequency  cluster
  1     1.33    15%    2          unanchored|no-subject|cost_ledger
  2     1.00    26%    2          unanchored|no-subject|lateness_set
  3     0.86    35%    2          lateness-cause+schedule|no-subject|cost_ledger

  Next candidate: a MONEY-shaped read ("how does the setup cost compare to the
  tardiness cost"), asked 2x, 67% grounded. NOT promoted -- one proof cycle was
  pre-authorized. Note also that `lateness-cause` now appears in five clusters'
  adjacency: the promoted intent immediately became a near neighbour for much of the
  remaining residue, which is worth reading twice before promoting the next one.

======================================================================
PART 3 -- VERIFICATION
======================================================================
Full non-slow Python suite     see below
Slow AI + rolling ladders      --runslow on the AI-track + rolling modules
Cockpit JS (Playwright)        178 passed, light + dark
New tests                      tests/test_provenance_report.py 13,
                               tests/test_promotion.py 32,
                               tests/test_felt_bar.py 30,
                               tests/test_rolling_dispatch.py 16 -- 91 new
Sweep                          committed under
                               tests/ai_exam/sweeps/2026-07-26-arc-close/, with
                               ledger.jsonl + PROVENANCE.txt + PROVENANCE.json
Goldens                        none moved -- no golden file appears in the diff. The
                               pinned rolling run is a NEW fixture in gitignored
                               scratch, produced by a committed builder.
Payload                        the cockpit ask payload is unchanged; the ask
                               RESPONSE gains a read-only `shadow` block (probation
                               only); a NEW endpoint POST .../ask/preflight is
                               additive and optional -- calling /ask directly is
                               unchanged and still correct.

======================================================================
PART 4 -- UNDERDELIVERED, RESIDUE, OUT OF SCOPE
======================================================================
UNDERDELIVERED (explicitly):
  - "Every mechanical signal strictly-no-worse than 2026-07-26-synthesis" is NOT
    met. ungrounded-load-bearing went 0 -> 3: "what's the optimal plan", "find me a
    faster schedule", "whats the busiest day in this schedule". In each the tier
    drafted a conclusion, the verifier cut it, and the answer SAID so -- the
    mechanism working on three questions that deserve it. But the RUBRIC reads a
    rising count as the tier reaching past its evidence, and two of the three are
    optimality questions, which is exactly where reaching is tempting. It is a
    live-model property, not a code regression (the same questions grounded on the
    4A.5b run). Every TRUTH-FLOOR tripwire is no-worse; this one is not, and the bar
    was not relaxed to say otherwise.
  - Parse counts are slightly worse: retries 0 -> 1, malformed 0 -> 2, median 1050
    -> 1159 ms, clarifies 6 -> 10.
  - One graded expectation remains unmet and was NOT relaxed: "are you sure about
    that" reaches `prove-it` rather than the `verification` clarify. Both are honest
    and neither capitulates; RUBRIC precedent entry 4, still OPEN for the founder.
  - Two bank expectations WERE changed, and the reason is stated in the bank itself:
    the two flagship aggregate-lateness questions moved from `route=synthesis` to
    `intent=lateness-cause route=lateness-cause`. That is not a bank edited to match
    behaviour -- the thing that changed is the product, by a reviewed vocabulary
    change with a cited authority. A bank still expecting `synthesis` there would be
    asserting the promotion did not happen.
  - The sidecar still flags the rolling bank's DELIBERATE absent-order control. It
    could suppress an absent-entity finding on a turn whose EXPECT line asks for
    `unknown-entity` -- the behaviour is graded there -- and it does not yet.
  - test_scenario_untouched_moves_bounded failed once under concurrent load and
    passes in isolation: a new member of the standing contention-sensitive class
    alongside test_n3000.

RESIDUE / NAMED LIMITS:
  - Clustering UNDER-states frequency by design; merging split shapes is a human's,
    in a dossier.
  - The shadow diff compares only quantities BOTH sides state about the same
    labelled thing; on the promoted shape that is ONE shared quantity across three
    probation questions. The teeth are real but narrow.
  - The two-phase first beat names the tool BUDGET, not a live count. A ticking
    "(N tools consulted)" needs streaming or background execution of the ask.
  - The promoted route is measured against ONE world's late set (a single late
    order): its premise check is well-exercised, its cause MIX is not.
  - A dossier's harness validation cannot see collateral damage to neighbouring
    intents. That is what the review gate is for, and this session proved it.

OUT OF SCOPE (named, not built):
  - Any promotion beyond the one pre-authorized proof cycle. The Pareto's current
    head is left for the next session.
  - Per-claim cockpit badge ELEMENTS (tokens shipped in 4A.5b).
  - Rendering-model changes. Anything on the 4B queue.

======================================================================
THE ARC
======================================================================
4A.5a retired the classifier and made every question parse first. 4A.5b gave the
unmatched question a tier and made every one of its sentences earn its label. 4A.5c
made the residue legible, gave the system a way to propose its own routes and an
automatic way to take them back, and killed the last keyword matcher in the ask
path. R-AI5's eight clauses are implemented. The working thread returns to the 4B
mission.

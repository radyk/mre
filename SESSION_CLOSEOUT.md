SESSION 4A.5a CLOSE-OUT
R-AI5 part 1: the LLM-first parse layer (the classifier retires)
2026-07-25

Deterministic settings for all solver work: PYTHONHASHSEED=0, --solver-workers 1,
--solver-seed 0 (the glass_box pinned world the sweep asks against).

Scope: backend + contracts + banks + tests + docs. NO solver / model /
schedule-contract / frontend-substrate change. NO golden moved. The cockpit ask
payload is UNCHANGED -- the panel already sends selection + last_answered_subject,
which is exactly what the parse reads.

======================================================================
SUMMARY
======================================================================
Four founder exam rounds proved a structural fact: every major conversational
failure -- polarity inversion, hypothesis mis-routing, subject-binding outranking
intent, a menu that could not match its own items -- was the deterministic
keyword/precedence router failing to understand INTENT, which is a natural-language
problem being solved with string matching. Patches fixed specimens; the class
survived. R-AI5 was co-designed and ruled in the working thread. This session
implements part 1: the parse layer. Parts 2 (synthesis + verification) and 3
(telemetry + promotion) are Sessions 4A.5b and 4A.5c.

The ask path is now exactly:

    parse (one LLM call, closed vocabulary)
      -> dispatch(intent)
      -> the EXISTING route assembly
      -> the EXISTING render + validator

with no deterministic-classifier fallback and no silent path between the tiers.

======================================================================
PART 1 -- R-AI5 TRANSCRIBED
======================================================================
CLAIMED: R-AI5 appended to docs/04 verbatim, FIRST, before this session's
         amendment.
PROVEN:  docs/04-design-history.md, "Amendment -- 2026-07-25: R-AI5 ruling --
         LLM-FIRST INTERPRETATION OVER A VERIFIED EVIDENCE CORE"; all eight
         clauses between the RULING TEXT BEGINS / ENDS markers; byte-appended
         (the pre-append bytes are a verbatim prefix of the post-append file --
         asserted in the append itself), CRLF preserved.

======================================================================
PART 2 -- PER-CU: CLAIMED vs PROVEN
======================================================================

CU1 -- the parse contract + the parser
--------------------------------------
CLAIMED: a typed ParsedQuestion contract in the contracts package; intent as an
         enum generated from ROUTE_TAXONOMY; typed subjects resolved against the
         run's vocabulary (the "order N"/fuzzy resolution moving INSIDE the
         parse); polarity; follow-up linkage; confidence; a clarify payload; one
         LLM call at temperature 0; a prompt built from the intent vocabulary WITH
         each intent's one-line meaning, governed and versioned in the repo, plus
         conversation context, selection and last_answered_subject; strict JSON;
         one retry then the clarify path; never a guess, never a crash.

PROVEN:  src/mre/contracts/parse.py -- ParsedQuestion (pydantic, extra=forbid)
         with Intent / SubjectKind / SubjectSource / Polarity / FollowupKind /
         ClarifyReason, SubjectRef(kind, raw, ref, source, pointed),
         ClarifyPayload, INTENT_MEANINGS, MODEL_SELECTABLE_INTENTS.
         src/mre/modules/parse_prompt.md -- header names R-AI5(1),
         prompt_version: 1, and the review discipline; body carries {INTENTS},
         {CONTEXT}, {QUESTION}; everything above the ## PROMPT marker is never
         sent.
         src/mre/modules/question_parser.py -- QuestionParser (one call,
         temperature=0, retry-once-then-clarify), ParserStats, bind_subjects,
         build_parsed, extract_json, render_intents, render_context.
         Tests (tests/test_parse_contract.py): vocabulary parity Intent ==
         ROUTE_TAXONOMY; every selectable intent has an authored meaning;
         unknown-entity never offered to the model; the prompt header names the
         ruling and the discipline; the rendered vocabulary carries every intent;
         the context renders all three channels; confidence clamped; bad enum
         members degrade without raising; clarify reasons closed; extra fields
         forbidden; named / "order N" / machine resolution; binding priority
         selection > last-answer > history; typed binding never cross-type; one
         malformed emission retries then succeeds; two malformed emissions
         clarify; an out-of-vocabulary intent counts as malformed; a raising
         client never escapes; no key = unavailable.

         DELIVERED BEYOND THE BRIEF (named; both sit inside CU1's remit, since
         R-AI5(1) puts subject resolution inside the parse): the intent list
         rendered into the prompt appends each intent's REQUIRED SUBJECT, derived
         from ROUTE_TAXONOMY rather than re-authored; and a token-wise machine
         fallback resolves "the paint line" to PAINT-01. Both were sweep findings.

CU2 -- dispatch replaces classification
---------------------------------------
CLAIMED: parse -> dispatch(intent) -> the EXISTING route assembly -> the EXISTING
         render + validator; classify's keyword/precedence machinery and
         resolve_followup's deictic/correction/menu/list-expand rules DELETED, not
         bypassed-and-kept; their behaviours become parse-contract fields the
         dispatch honours; their tests re-pointed at the parse layer; an unmatched
         intent gets the honest unsupported answer (NO synthesis this session); a
         confirmation-of-take routes to an authored acknowledgment naming the
         gesture and the sandbox; the expedite-an-early-order branch joins the
         advice route's authored copy.

PROVEN:  Explainer.classify() and Explainer.answer() are GONE (a comment stands
         where they were, naming why there is no private question-to-route shim).
         interpreter.resolve_followup() and every rule it used are GONE
         (_typed_deictic, _demonstrative_deictic, _substitute_typed,
         _substitute_pronoun, _last_subject, _last_route, _has_ellipsis,
         _CORRECTION_RE, _BARE_WHY_RE, _VERIFY_RE, _SET_PRONOUN_RE, _LIST_EXPAND,
         _COST_FOLLOWUP). The trigger tables are GONE (schedule, optimality,
         certificate, triage, remediation, excluded, edit-summary, edit-cost,
         ledger, briefing, inventory, integrity, attribute, drill-down,
         start-reason, advice, solve-time, machine-list, maintenance, contest,
         status, hypothesis, gap, idle), as is _is_hypothesis. Two marker sets
         survive, named as ROUTE-INTERNAL parameter reads inside assemblers that
         have already been reached: _swap_move_kind (swap-vs-move framing) and the
         new _remediation_limit ("just the worst one"). No `.classify(` call and no
         Explainer `.answer(` call remains anywhere in src/ or tests/.
         New dispatch (interpreter.py): Dispatched(route, bundle, note,
         routed_question); route_params(); routed_text() -- the planner's own
         sentence with resolved refs substituted, canonical only when the turn
         re-fires a previous question or a pointed subject has no words;
         _subject_note() -- keeps the literal "board selection" phrase askpanel.js
         keys its badge on; _required_slots() -- integrity-check and downtime
         answer plant-wide, gap-between needs an order OR the machine;
         _nearest_offers() -- defaults chosen by what the planner named.
         Three honesty failures separated rather than blended: a POINTED subject
         with nothing live CLARIFIES; a NAMED subject that is not here gets the
         absent answer; a slot nobody mentioned gets the nearest-capabilities
         bridge.
         Authored branches: _explain_confirm_take + the confirm_take renderer
         branch + CONFIRM_TAKE_* copy; _expedite_early_facts + the advice
         renderer's early branch + ADVICE_EXPEDITE_* copy. Both joined
         _AUTHORED_COPY_SUBJECTS, so neither can be LLM-reworded.
         Vocabulary additions: confirm-take, and schedule (the whole-plan listing
         was a route() destination the taxonomy never named, so no parse could
         have reached it).
         Tests: tests/test_interpreter.py rewritten as dispatch tests -- 18
         matched intents reaching their assemblers, every clarify reason, unmatched
         with and without nearest, low confidence, absent entity,
         pointed-with-nothing-live vs required-slot-never-mentioned, all six
         follow-up linkages, the bound-subject-never-picks-the-intent regression
         (the round-four terminal bug), the confirm-take bridge and its copy, and
         run_ask's guarantees (parsed exactly once; no parser = honest refusal, not
         a keyword guess; the resolution visible on the bundle; the ledger records
         source=parse; the parse contract rides back on the result).

         RE-POINTED TEST INVENTORY (the full list):
           tests/parse_doubles.py             NEW: FakeClient (canned emissions,
                                              everything downstream real),
                                              ScriptedParser (question ->
                                              ParsedQuestion), assemble()
           tests/test_parse_contract.py       NEW: the parse contract + parser
           tests/test_interpreter.py          rewritten as dispatch tests
           tests/test_ai_voice.py             CORPUS_PARSE table added; every
                                              ANSWER assertion kept; the deictic
                                              regex and hypothesis-detector units
                                              replaced by binding-priority and
                                              route-internal-parameter units;
                                              TestSwapMoveClassify became
                                              TestSwapMoveDispatch
           tests/test_explainer.py            91 sites name their route via
                                              assemble(); the REPL dialogue turn
                                              scripts its parse
           tests/test_certificate_conversation.py, tests/test_edit_question_domain.py,
           tests/test_unguarded_edges.py      name their route explicitly
           tests/test_api_endpoints.py        scripts the parse at the ENDPOINT
           tests/test_ask_chain_api.py        scripts the parse at the ENDPOINT
           tests/ai_exam/test_real_doors.py   the door proven from both sides
           tests/ai_exam/test_runner.py       end-to-end turns supply their parse;
                                              the door check gains its own tests

         ONE GUARANTEE RESTATED RATHER THAN KEPT, and it matters: "a taxonomy-shaped
         question routes deterministically with the whole AI layer broken" is GONE,
         because the keyword fallback that made it true is gone on purpose. What is
         unbreakable now is the HONESTY -- with both the parse layer and the
         renderer forcibly raising, the endpoint still returns 200, a rendered
         answer, and zero citations
         (test_a_broken_ai_stack_answers_honestly_never_a_5xx).

CU3 -- the founder's round-four regressions
-------------------------------------------
CLAIMED: tests/ai_exam/banks/regression_founder_r4.txt -- the round-four session as
         a conversation script (SELECT where the board selection was active), with
         graded expectations per turn.
PROVEN:  15 questions, 15 EXPECT lines, parses clean. Threads: the expedite pursuit
         on an already-early order (four turns, selection live -- ORD-000036
         adapted to the world's early control ORD-13, phrasing preserved), the
         capability question with a STALE selection, the confirmation-of-take turn,
         "why is this order late" via selection, plus two controls (the same deixis
         with NO selection must ask; the expedite question NAMING a late order must
         not take the early branch).
         The grading mechanism is new: an EXPECT script directive (script.py, with
         a closed EXPECT_KEYS set -- an unknown key is a parse finding, never a
         silently ignored expectation) attaches to the next question;
         sidecar.check_expectation emits expect-miss. It grades ROUTING ONLY --
         intent, typed subjects, follow-up linkage, route -- never prose (R-AI4(2)).
         SWEEP RESULT: 15/15 expectations MET, sidecar clean. The terminal bug is
         closed: "is there any way i can get this done faster" with ORD-13 selected
         parses to intent=advice with ORD-13 as a PARAMETER.

CU4 -- goal-pursuit scenario banks
----------------------------------
CLAIMED: multi-turn GOAL-PURSUIT scripts, not per-route probes; at least 8
         scenarios, 5-10 turns each, against the pinned glass_box world; committed
         as versioned banks with dated headers.
PROVEN:  tests/ai_exam/banks/sweep_scenarios.txt -- 8 scenarios, 49 questions, 48
         EXPECT lines, dated header (2026-07-25) naming the taxonomy and the world.
         The eight: expedite-for-a-customer; investigate-a-capability;
         chase-a-cause-to-its-root; challenge-a-take; a planner who never uses
         canonical ids; a selection live throughout (the subject must parameterize
         where relevant and be IGNORED where not); triage-the-submission; the
         frustrated planner.
         UNDERDELIVERED, named: the brief said "banks" plural; this is ONE bank
         file holding all eight scenarios rather than eight files. Scenario count,
         turn lengths, dated header and versioning are as specified; only the file
         split is not.

CU5 -- the acceptance bar: the full re-baseline sweep
-----------------------------------------------------
CLAIMED: the ENTIRE bank set -- 4A.3b regression + sweeps + the r4 regression + the
         new scenario banks -- live, against the pinned glass_box world, committed
         under tests/ai_exam/sweeps/<date>-llm-parse/.
PROVEN:  tests/ai_exam/sweeps/2026-07-25-llm-parse/ -- five transcripts, five
         sidecars, SWEEP.json. Target out-dir:gb_pinned, snapshot snap-exam, built
         with PYTHONHASHSEED=0 --solver-workers 1 --solver-seed 0. Driver:
         tools/run_ai_exam_sweep.py, one shared parser across the sweep so the
         parse counts are the sweep's, not one bank's.

PER-BANK, AGAINST GRADED EXPECTATIONS

  bank                     questions   graded   met   sidecar
  regression_founder              28        0     -   clean
  regression_founder_r4           15       15    15   clean
  sweep_routes                   120        0     -   clean
  sweep_scenarios                 49       48    46   expect-miss=2
  sweep_traps                     62        0     -   absent-entity=3
  TOTAL                          274       63    61

MECHANICAL SIDECAR COUNTS vs THE POST-REPAIR BASELINE
(baseline tests/ai_exam/sweeps/2026-07-24-post-repair/, 210 questions;
 new 274 questions -- the same three banks plus the two new ones)

  signal              baseline   new    verdict
  exception                  0     0    no regression
  empty                      0     0    no regression
  validator                  0     0    no regression
  absent-entity              3     3    no regression -- the SAME three honest
                                        refusals (ORD-99, ORD-88, ORD-000038)
  dark-evidence              0     0    no regression
  dead-door                  0     0    no regression, and stronger: the check now
                                        runs the REAL parse over each distinct
                                        offered follow-up instead of the retired
                                        classifier, and reports itself SKIPPED --
                                        never clean -- when no parser is available
  target-unloadable          0     0    no regression
  expect-miss                -     2    new signal, no baseline

  The bar was strictly-no-worse mechanically. It is met on every baseline signal,
  on a bank set 30% larger.

PARSE-SPECIFIC COUNTS (whole sweep, one shared parser)
  parses                286
  model calls           288
  retries                 2      0.7% of parses needed a second call
  malformed emissions     4      1.4% of calls did not validate
  clarify rate           11      3.8% of parses emitted a clarify payload
  unavailable             0
  median parse latency  1014 ms
  live LLM calls (parse + render), 357 total:
    regression_founder 42 | r4 19 | routes 153 | scenarios 65 | traps 78

THE TWO SURVIVING expect-miss FINDINGS -- triaged, NOT fixed, NOT relaxed away
  1. "is there a minimum piece size" (S2, after a splittable thread): the parse
     named coaching but bound the concept "piece size", for which the capability
     registry has no trigger, so the answer is the honest what-I-can-coach list.
     The cure is a registry trigger -- authored vocabulary, outside the parse layer.
  2. "whats holding CUT-01" (S3): parsed as start-reason -- an order-shaped intent
     -- with only a machine named, so the honest result is the nearest-capabilities
     bridge (which now offers machine routes, not the plan-wide defaults). A
     residual parse miss after the required-subject annotation, recorded rather
     than papered over.

PARSE-LAYER DEFECTS THE SWEEP FOUND AND THIS SESSION FIXED
(the instrument exception: parser/dispatch defects found by the sweep are in scope)
  - an intent whose required subject the planner never named -> the rendered
    vocabulary now states each intent's required subject, derived from the taxonomy
  - drill-down over-attracting "tell me about X" -> its authored meaning sharpened
  - drill-down, legitimately reached, footnoting its composed finding body's list
    ordinal as a record (2 validator fallbacks) -> the recurring disease with the
    recurring cure (4A.3c CU3): drill_down joins the authored-copy render path
  - colloquial machine names ("the paint line") not resolving -> token-wise fallback
  - a clarify emitted alongside unmatched (a dead end by construction) -> forbidden
    in the prompt and dropped in the parser
  - a nearest-capabilities bridge that ignored the subject just named -> defaults
    chosen by what the planner named
  Progression across the three sweep runs:
    expect-miss  9 -> 3 -> 2
    validator    3 -> 0 -> 0
    graded    54/63 -> 60/63 -> 61/63

ONE TRANSIENT, NAMED: the second run recorded one `exception` -- "when does it
finish" timed out after 120s. It did not reproduce on the third run against the same
bank and the same world, and the parse median is ~1s; it reads as an outbound-call
stall, not a parse-layer defect. Recorded rather than silently dropped.

CU6 -- riders
-------------
CLAIMED: docs/04 (R-AI5 verbatim FIRST, then the amendment naming the classifier
         retirement, the parser prompt as a governed artifact, the re-pointed test
         inventory); docs/07 same-day; CLAUDE.md (position + the ask-path
         architecture line); the parse prompt file's header naming R-AI5(1) and its
         review discipline.
PROVEN:  docs/04 -- R-AI5 verbatim, then "2026-07-25 -- AI-track Session 4A.5a"
         (pure append, prefix-verified, CRLF preserved).
         docs/07 -- v2.44 entry inserted above v2.43, status line bumped.
         CLAUDE.md -- position updated; a new "The ask path (R-AI5)" paragraph
         states the pipeline, that there is no classifier fallback, and that the
         prompt is a governed artifact; R-AI5 residue added to the carry-forwards.
         11,811 chars, well under the 40k ceiling.
         parse_prompt.md -- header carries R-AI5(1), prompt_version and the review
         discipline.
         RUBRIC.md -- dead-door redefined for the parse-based check; expect-miss
         documented; the parse-specific counts named as instrumentation, not a
         grade.
         pyproject.toml -- mre.modules package-data so the governed prompt ships.

======================================================================
PART 3 -- VERIFICATION
======================================================================
Full non-slow Python suite     1329 passed, 20 skipped, 179 deselected (10:12)
Slow AI-track suites            163 passed -- test_ai_voice, tests/ai_exam,
                                test_ask_chain_api with --runslow
Cockpit JS (Playwright)         178 passed (2.4m), light + dark
Sweep                           committed under
                                tests/ai_exam/sweeps/2026-07-25-llm-parse/
Goldens                         none moved -- no golden file appears in the diff
Payload                         the cockpit ask payload is unchanged

======================================================================
PART 4 -- UNDERDELIVERED, RESIDUE, OUT OF SCOPE
======================================================================

UNDERDELIVERED (explicitly):
  - CU4 asked for "banks" plural; delivered as ONE bank file containing all eight
    scenarios. Content, count, turn lengths, dated header and versioning as
    specified; the file split is not.
  - Two graded expectations remain unmet (both named and triaged above). They are
    recorded as sweep findings rather than relaxed away.

NAMED RESIDUE (carried, not fixed -- also recorded in docs/04 and CLAUDE.md):
  - The ROLLING pre-route (rolling_questions.classify_rolling) is still a
    deterministic keyword matcher on rolling documents. R-AI5 residue for a later
    session; the glass_box world is monolithic, so the sweep never exercises it.
  - start-reason's early-vs-plain distinction is still the assembler's own wording
    read; only a NEGATIVE polarity is authoritative from the parse.
  - A CLARIFY turn carries no subject forward (it answered nothing); the parse
    reading the referent back out of the recent turns is the mitigation, not a fix
    to the carry channel.
  - The capability registry has no "minimum piece size" trigger.
  - The exam harness now costs one model call per QUESTION even where a run used to
    be "deterministic": there is no keyword floor left to exercise offline, so every
    offline test that drives the ask path supplies a scripted parser.

OUT OF SCOPE (named, not built):
  - Labeled open synthesis and claim-level verification (R-AI5(2)/(3)) -- 4A.5b.
  - Provenance telemetry, the per-claim visual surface, the promotion loop
    (R-AI5(4)-(7)) -- 4A.5c.
  - "Prove it".
  - Any new route content beyond CU2's two authored branches.
  - Model choice for the RENDERING path.

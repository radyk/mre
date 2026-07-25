SESSION 4A.3c CLOSE-OUT
Sweep repairs: the first triaged errand list
2026-07-24

Deterministic settings for all solver work: PYTHONHASHSEED=0, --solver-workers 1,
--solver-seed 0 (the glass_box pinned world uses seed 0, matching test_ai_voice).

======================================================================
SUMMARY
======================================================================
The first exam sweep (Session 4A.3b: 210 probes, live LLM, pinned glass_box world)
was triaged in the working thread per R-AI4(2). This session executes the errand
list. Discovery already happened; this is repair. After this session the sweep
re-ran and the repairs show as landed.

Backend + one cockpit panel field + tests + docs. NO solver/model/contract/
frontend-substrate change. NO golden moved. Every CU has committed transcript
evidence behind it (tests/ai_exam/sweeps/2026-07-24/).

======================================================================
PER-CU: CLAIMED vs PROVEN
======================================================================

CU1 -- the "but why?" defect: resolved-subject context + the test-realism re-audit.
  CLAIMED: (a) the panel sends the prior answer's resolved subject back as
           last_answered_subject; the interpreter resolves at priority
           selection > last answered > history > clarify; the runner carries it
           exactly as the panel does. (b) re-audit test_ai_voice's context/follow-up
           fixtures, refactoring any that feed data the cockpit does not send. (c) a
           slow chain specimen.
  PROVEN : (a) AskRequest.last_answered_subject (api/app.py) threads to the context;
           _last_subject / _typed_subject_with_source / _last_typed_subject in
           interpreter.py take the new argument at the fixed priority; askpanel.js
           computes lastAnswered via resolvedSubject(bundle) and sends it; runner.py
           resolved_subject() mirrors askpanel.js ORDER_SUBJECTS/MACHINE_SUBJECTS
           EXACTLY (ambiguous "schedule" labels carry nothing -- never a guess), and
           the runner carries it across turns (reset by RESET). (b) FIVE fixtures
           refactored to realistic context (subject on last_answered_subject, not an
           order in history): test_cu4_start_earlier_via_context,
           test_4b_cu5_bare_why_resolves_to_cause_chain,
           test_4b_cu5_set_reference_clarifies, test_4b_cu5_verification_clarifies,
           and their three parametrized twins in the zero-confident-wrong corpus.
           NONE became a KNOWN GAP -- the product fix makes them pass for the right
           reason (the enriched-history versions passed for behavior reality lacked).
           (c) test_cu1_but_why_resolves_via_last_answered_subject (slow, in
           tests/ai_exam/test_runner.py) drives "why is ORD-05 late" -> "but why?"
           through the runner's real carry: the follow-up DEEPENS (route late-order,
           resolved_question names ORD-05), never CLARIFIES.
  EVIDENCE: first sweep transcript L48 "but why?" -> CLARIFY (the defect);
           post-repair transcript Q[48] "but why?" -> "interpreted as: why is ORD-05
           late? (resolved against ORD-05)", route late-order.

CU2 -- dark evidence: answers about placements light their bars (29 sweep findings).
  CLAIMED: order-schedule / start-reason / machine-schedule populate cited_refs from
           the assignment Decisions they narrate, through the existing lit-bars
           channel; machine-schedule caps at the ops it lists; dark-evidence -> 0 for
           these routes.
  PROVEN : _explain_start_reason carries _assignment_records(order); _schedule_query
           carries _assignment_records_for_ops(narrated_ops, narrated_demands) -- real
           assignment Decisions whose operation subject is a SHOWN row, so the lit set
           is exactly the listed rows (capped when the listing truncates). Prose stays
           deterministic and unchanged: schedule + start_reason are header-only and on
           the authored-copy render path (records feed lit-bars, never an LLM rewrite
           of a table nor a redundant evidence-chain dump under a table that already
           lists the rows). test_cu2_narrating_routes_light_their_bars (slow) asserts
           lit_bars > 0 and no dark-evidence for all three routes.
  EVIDENCE: first sweep sidecar dark-evidence=29 (lines 36/58/60/105/107/133/134/135/
           ...); post-repair sidecar dark-evidence=0. Post-repair transcript spot
           check: machine-schedule lit-bars=5, start-reason lit-bars=2,
           order-schedule lit-bars>0.

CU3 -- the findings-register validator rate (11 fallbacks, ~11% of live renders).
  CLAIMED: extend the register's payload so findings/certificate testimony stops
           fabricating; target the findings-register validator-fallback rate to ~zero;
           if a residual class survives, name and pin it rather than widen the
           validator.
  PROVEN : the transcript diagnosis was exact -- the LLM footnoted the finding-list
           ORDINAL as a record ("fabricated record citation '1'"), failing the
           citation floor and falling back to the template ANYWAY (so findings never
           delivered LLM fluency live). The composed findings body is authored
           planner-voiced sentences, the same KIND of composed authored copy every
           other register in this codebase short-circuits verbatim; "findings" joins
           LLMRenderer._AUTHORED_COPY_SUBJECTS -> rendered verbatim, a DETERMINISTIC
           ~zero fallback rate. This is the "register's equivalent" cure the errand
           permitted; enriching pre-computed facts would not reliably stop a model
           from footnoting a list ordinal, and the fix never widens the validator's
           tolerance (the floor's strictness is the floor).
  RESIDUAL NAMED: the remediation route's own number-validator (_render_register) is
           LEFT INTACT -- it is the fail-closed floor working as designed, not a
           defect to repair by weakening it. On the first sweep it fired once
           (L176 "what's the fix for these findings"); on the post-repair sweep it did
           not fire (LLM run-to-run variance -- the floor is intact regardless).
  EVIDENCE: first sweep sidecar validator=11 (findings/certificate testimony);
           post-repair sidecar validator=0; post-repair transcript has zero
           "LLM validation failed" lines.

CU4 -- the "order N" resolver (the founder's live register, a 4A.3b KNOWN GAP).
  CLAIMED: "swap order 5 and order 4" / "order 15" / "ord 23" resolve to canonical ids
           by numeric inference against the pinned world; flip the KNOWN GAP; guard
           against quantity forms ("show 5 late orders").
  PROVEN : _build_order_number_index maps each order's trailing number to its ref
           (unique numbers only -- ambiguous drops, never guessed); rewrite_fuzzy_orders
           gains an _ORDER_N_RE pass that resolves "order N" / "ord N" against that
           index and surfaces the same visible "assuming ORD-05" assumption. Resolution
           is against the world's real ids, zero-padding inferred from the ref; an
           absent number is left untouched (honest unresolved). The 4A.3b KNOWN GAP
           test flipped to test_solve5_natural_language_order_numbers_resolve_and_swap;
           test_bare_order_number_resolves_to_the_canonical_ref added; the negative
           guard test_order_number_does_not_swallow_a_quantity pins "show 5 late
           orders" (a count, never ORD-05). Side effect NAMED: "order 2001" now
           resolves deterministically, so one test_interpreter LLM-miss fixture was
           re-pointed to "job 2001" (a genuine miss) to keep exercising the paraphrase
           path.
  EVIDENCE: post-repair transcript Q[43] "why not just swap order 5 and order 4" ->
           "interpreted as: why not just swap ORD-05 and ORD-04 (assuming ORD-05,
           ORD-04)", route swap-move.

CU5 -- the loop closes: re-sweep + the precedent log.
  CLAIMED: re-run the full 210-probe bank live against the same pinned world; commit
           under sweeps/<date>-post-repair; report the mechanical deltas; seed the
           founder-precedent log with the three working-thread judgment calls.
  PROVEN : re-ran LIVE (LLM on, real key from .env.local; 72 live calls -- fewer than
           the first sweep's 96 because findings + schedule are now deterministic
           authored copy) against the SAME pinned glass_box solve (out-dir gb_pinned,
           snapshot snap-exam, workers 1 seed 0). Transcript + sidecar committed under
           tests/ai_exam/sweeps/2026-07-24-post-repair/. RUBRIC.md founder-precedent
           log seeded with three OPEN entries (lit-bars feel at volume; invitation
           frequency across broadened coverage; take frequency 28/42 renders).
  NEW FINDINGS THE REPAIRS SURFACED: none. The post-repair sweep surfaced no new
           mechanical finding class -- absent-entity is the only remaining kind, and it
           is unchanged (the deliberate wrong-entity traps, correctly refused).

CU6 -- rider: docs.
  PROVEN : docs/04 2026-07-24 Session 4A.3c amendment (append-only) covering the CU1
           test-realism discipline (a named standing discipline), the CU2 lit-bars
           ruling, the CU3 register-equivalent cure, the CU4 resolver forms; docs/07
           v2.42 same-day; CLAUDE.md status block; this close-out.

======================================================================
THE MECHANICAL DELTAS (sidecar, first sweep -> post-repair)
======================================================================
target : glass_box clean solve, out-dir gb_pinned, snapshot snap-exam (workers 1,
         seed 0)
         (the pinned world is identical; only the code under test changed)

                    first sweep    post-repair    verdict
  dark-evidence         29             0          repaired (CU2)
  validator             11             0          repaired (CU3)
  absent-entity          3             3          unchanged (honest refusals -- the
                                                  wrong-entity traps ORD-99 / ORD-88 /
                                                  ORD-000038, correctly refused)
  llm calls             96            72          fewer -- findings + schedule are now
                                                  deterministic authored copy

A clean-but-for-the-traps sidecar is NOT a passing grade -- these counts are seeds,
not verdicts. Conversation quality across the broadened coverage is still Claude's
read and the founder's call (the three OPEN precedent-log entries).

======================================================================
VERIFICATION
======================================================================
  Full non-slow Python suite: 1278 passed, 198 skipped, 0 failed (807s).
  Slow test_ai_voice + test_explainer + ai_exam runner: 262 passed (incl. the flipped
    CU4 specimen, the refactored CU1 fixtures, the CU1 chain + CU2 lit-bars
    end-to-end specimens).
  Slow test_glass_box + test_ask_chain_api: 34 passed.
  Cockpit JS (build + Playwright, both themes): green, incl. the panel's
    last_answered_subject payload assertion.
  Post-repair sweep committed: tests/ai_exam/sweeps/2026-07-24-post-repair/.
  No golden moved. No solver/model/contract/frontend-substrate change.

======================================================================
OUT OF SCOPE (named, not built)
======================================================================
  - Anything the post-repair re-sweep newly discovered: nothing new surfaced this
    time, but any future discovery is the next errand list.
  - Invitation / take frequency tuning: founder judgment, round four (the OPEN
    precedent-log entries).
  - The docs/05 structured-constraint surface (prose-locked).
  - Harness features beyond CU1's state carry.

======================================================================
LESSON
======================================================================
A test that feeds context the shipped surface never sends vouches for behavior reality
lacks -- the "but why?" specimen passed on enriched history while the real product
clarified, and only the sweep, firing the honest carry, caught it. The cure is
two-sided: fix the PRODUCT (carry the resolved subject the way the panel now does) and
re-audit the TESTS to the real payload, so green means the founder would hear the same.
And the recurring disease has one recurring cure -- when an answer is composed authored
copy, render it verbatim; the LLM's fluency is not worth a fabricated citation, and the
validator that catches the fabrication is the floor, never the thing you loosen.

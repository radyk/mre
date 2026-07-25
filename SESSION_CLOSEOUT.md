SESSION 4A.3b CLOSE-OUT
The exam harness: evaluation at machine speed, judgment where it belongs
2026-07-24

Deterministic settings for all solver work: PYTHONHASHSEED=0, --solver-workers 1,
--solver-seed 0 (the glass_box pinned world uses seed 0, matching test_ai_voice).

======================================================================
SUMMARY
======================================================================
The AI layer is the product differentiator and the bar is "fantastic" -- yet it had
the slowest evaluation loop in the system. Solver changes get machine-speed verdicts
(goldens, counterfactuals); conversational changes waited for a founder listening
session of ~a dozen questions an evening. Three founder rounds found every major seam,
all DISCOVERY failures a corpus that grades only questions someone already added is
structurally blind to. This session builds the instrument that inverts the economics:
automated sweeps discover at scale, Claude triages transcripts against the rulings, the
founder judges the felt bar from a short triaged list.

Backend + tests + docs. NO solver/model/contract/frontend-substrate change. NO golden
moved. The one behavioral change to shipped answers is CU4 (invitation coverage) --
additive authored copy on two more route families, each opening a live route.

======================================================================
PER-CU: CLAIMED vs PROVEN
======================================================================

PART 1 -- R-AI4 transcribed verbatim into docs/04 (append-only).
  CLAIMED: the four clauses (two axes; roles; fluency not engagement; audits against
           the pinned document, never a re-solve).
  PROVEN : appended verbatim to the docs/04 Amendment log, followed by the Session
           4A.3b amendment. docs/04 grew, was not truncated.

CU1 -- the runner (src/mre/ai_exam/).
  CLAIMED: python -m mre.ai_exam fires a question script through the REAL ask path,
           state persisting across the file; SELECT/RESET/comment directives; a
           plain-ASCII transcript + a mechanical findings sidecar; failures captured
           not crashed; --limit + per-question timeout + a live-call count.
  PROVEN : built as script.py (parser), runner.py (ExamRunner + RunTarget + the
           per-question ThreadPoolExecutor timeout + a live-call counter that wraps
           the real anthropic client -- honest, never a mock), sidecar.py (six
           mechanical checks), report.py (transcript + sidecar), __main__.py (CLI:
           --run <id> via the Registry, or --out-dir for CI). Proven by
           tests/ai_exam/test_runner.py (14 fast + 5 slow end-to-end) and by the first
           sweep running 210 questions live. FIDELITY NAMED: history turns are built
           the way the cockpit builds them (order/machine from the ACTIVE board SELECT,
           not the answer's resolved subject) -- the honest choice; enriching beyond
           what the panel sends would let the harness pass follow-ups the shipped
           product fails.
  FOUND + FIXED (the instrument, per CU5's exception): a wiped/missing run dir makes
           the Explainer fall to empty-vocabulary certificate-only mode and every
           entity question silently misroutes. The runner now reads Vocab.healthy and
           fires a loud `target-unloadable` finding, running NOTHING, rather than emit
           a transcript of garbage. Discovered mid-build (the scratchpad temp dir was
           volatile between shell calls) -- exactly the silent-degradation trap the
           codebase fights; a slow test pins it.

CU2 -- the banks (tests/ai_exam/banks/, versioned, dated headers).
  CLAIMED: founder rounds 1-3 verbatim (incl. typos) as conversation scripts +
           paraphrase fans + trap probes; hundreds of probes.
  PROVEN : regression_founder.txt (28 questions, the founder findings verbatim; pilot
           ids adapted to glass_box, phrasing exact), sweep_routes.txt (120),
           sweep_traps.txt (62). 210 probes total, 182 sweep (> the 150 floor). All
           parse clean (0 parse errors).

CU3 -- the rubric (tests/ai_exam/RUBRIC.md) + the mechanical pre-triage.
  CLAIMED: the truth-floor checks + five conversation dimensions + four output buckets
           (verbatim) with graded examples from real transcripts; the sidecar built.
  PROVEN : RUBRIC.md authored (plain ASCII): the truth checks T1-T3, the C1-C5
           dimensions, the DEFECTS / CONVERSATION FAILURES / JUDGMENT CALLS / EXEMPLARS
           buckets, graded examples (round one's filing-cabinet as the canonical
           truth-passes/conversation-fails anchor), and an empty founder-precedent log
           to fill after the listening session. The sidecar is built and tested (the
           six checks, tests/ai_exam/test_runner.py::TestSidecar).

CU4 -- invitation generalization (R-AI4(3)).
  CLAIMED: coverage beyond the three 4A.3-pre routes; contextual composition; a
           real-doors reverse-guard; silence discipline.
  PROVEN : coaching + gap-between join late-orders/why-late/data-problems; swap-move is
           NOT double-invited; lookups stay silent. Invitations are authored patterns
           (ask_fallback_copy.INVITATIONS) slot-filled from the answer's own facts via
           invitation_line. tests/ai_exam/test_real_doors.py asserts every pattern's
           probe classifies to its documented live route (fast, no solve). Rendered
           live in the sweep; three test_ai_voice specimens added (coaching invites,
           gap invites, swap does not double-invite). Existing invitation/coaching/
           lookup-silence tests un-regressed.

CU5 -- the first sweep + the proof of the loop.
  CLAIMED: run the runner against a pinned world (regression + >= 150 sweep probes),
           commit transcript + sidecar under sweeps/<date>/, fix NOTHING discovered,
           report the mechanical counts.
  PROVEN : ran LIVE (LLM on, real key from the gitignored .env.local; network
           available) -- 210 questions, 96 live LLM calls -- against a pinned glass_box
           clean solve (snapshot snap-exam, workers 1 seed 0). Transcript + sidecar
           committed under tests/ai_exam/sweeps/2026-07-24/. NOTHING found by the sweep
           was repaired (discovery, not repair; the next session's errand list).

CU6 -- riders.
  CLAIMED: (a) name the parallel-load screenshot-flake class as standing debt;
           (b) the corpus gains the solve-#5 swap phrasings, world-adapted.
  PROVEN : (a) named in the docs/04 amendment (two members: 3.1c 0-bars, 4A.3 planner
           due-marker; both pass in isolation, race only under parallel harness load;
           a harness-era cleanup candidate). (b) the solve-#5 natural-language swap
           phrasings ("swap order 5 and order 4") are in regression_founder.txt AND
           pinned in test_ai_voice as a KNOWN GAP -- they do NOT yet route to swap-move
           ("order 5" does not resolve to ORD-05); report, not repair.

======================================================================
THE FIRST SWEEP'S MECHANICAL COUNTS (the sidecar, NOT a grade)
======================================================================
target   : glass_box clean solve, snapshot snap-exam (workers 1, seed 0)
llm mode : live (96 live calls; 42 answers rendered by the LLM, 28 carried "My take:")
questions: 210

  dark-evidence  = 29  -- order-schedule / start-reason / machine-schedule answers
                         populate no cited_refs (light 0 bars). A real dark-lit-bars
                         SEED for triage: should "when does ORD-05 finish" highlight
                         ORD-05's bar? A working-thread judgment; fixed nothing.
  validator      = 11  -- LLM findings/certificate testimony that failed number/
                         timestamp/machine validation and fell back to the template
                         (the fail-closed floor working, ~11% of live renders). A real
                         seed: the LLM struggles with the findings register; fixed
                         nothing.
  absent-entity  =  3  -- ORD-99 / ORD-88 / ORD-000038, the deliberate wrong-entity
                         traps. Each answer honestly refused ("ORD-99 isn't in this
                         schedule"); the sidecar correctly seeds the confirmation.

A clean sidecar would NOT be a passing grade; these counts are seeds for Claude's and
the founder's triage, not verdicts.

HEADLINE DISCOVERY (fixed nothing): "but why?" after "why is ORD-05 late" (no board
selection active) CLARIFIES rather than resolving to the cause chain -- because the
harness faithfully reproduces the cockpit's SELECTION-ONLY history (order/machine come
from the board selection, not the answer subject). This exposes a test-vs-reality gap:
the 4A.2b unit test that asserts "but why?" resolves passes an ENRICHED context the
cockpit would not send without a selection. Exactly the kind of DISCOVERY failure the
exam exists to find; on the working thread's errand list.

======================================================================
VERIFICATION
======================================================================
  tests/ai_exam/test_real_doors.py ............ 9 passed (fast)
  tests/ai_exam/test_runner.py (fast) .......... 14 passed
  tests/ai_exam/test_runner.py (slow e2e) ...... 5 passed
  test_ai_voice CU4 + CU6b specimens (slow) .... 4 passed
  existing invitation/coaching/swap/idle (slow)  22 passed, un-regressed
  non-slow Python suite ........................ 1278 passed, 194 skipped, 0 failed
                                                 (baseline 1255 + 23 new fast tests)
  first sweep transcript + sidecar ............. committed (sweeps/2026-07-24/)

Same-commit docs: R-AI4 verbatim + the Session 4A.3b amendment + the flake-class debt
(docs/04); docs/07 v2.41; CLAUDE.md status block.

======================================================================
OUT OF SCOPE (named, not built)
======================================================================
  - Repairing anything the sweep discovered (the next session's errand list, triaged
    in the working thread): the 29 dark-evidence routes, the 11 validator fallbacks,
    the "but why?" selection-only-history gap, the natural-language "order N" swap gap.
  - CI-asserting LLM PROSE: the exam asserts the deterministic layer + structural
    properties only (take present, no uncited numbers, validator verdict, real doors)
    -- never prose matching. The transcript carries quality judgment to humans/Claude.
  - Automated conversation-quality scoring (R-AI4(2): grading is Claude's and the
    founder's, not a metric's).

======================================================================
LESSON
======================================================================
The differentiator had the slowest feedback loop, and a corpus that grades only known
questions is blind to discovery by construction. The cure is the product's own
philosophy turned on itself: fire hundreds of probes at machine speed, let the
mechanical floor (validator, fabrication, dark bars, dead doors) catch what is
checkable without judgment, and reserve human judgment for the felt bar -- evidence
first, judgment labeled, the founder the final arbiter. And an instrument that can
silently score a wiped run as "answered" is worse than none: make the dead target fire
loud, like everything else here.

# AI EXAM RUBRIC (Session 4A.3b, CU3 -- implements R-AI4(1))

The authored rubric Claude triages a sweep transcript against. It is a living
document: it evolves by amendment like everything else in this repo, and founder
verdicts on judgment calls are recorded here as precedent so calibration compounds.

Grading is Claude's and the founder's, NOT a metric's (R-AI4(2)). Nothing in this
file is asserted by an automated test on prose -- the sidecar's mechanical checks
(below) are the only machine-graded part, and they never grade conversation.

Plain ASCII. No box-drawing, no emoji.

------------------------------------------------------------------------------
THE TWO AXES (R-AI4(1))
------------------------------------------------------------------------------

TRUTH is the floor. Binary, non-negotiable. A truth miss is a DEFECT regardless
of how good the prose is. Checks:

  T1  Every cited fact is correct against the PINNED RUN's persisted document
      (never a re-solve -- R-AI4(4), the CU7a protocol as law). Timestamps,
      lateness/slack figures, machine names, order ids, cost numbers.
  T2  No fabrication. No cited record id that is not on the bundle; no order /
      machine / customer that is not in the pinned world; no invented cause,
      blocker, or number.
  T3  Hedges where the heuristic is a heuristic. An attribution by price rank
      (EARLINESS_PREFERENCE where capacity may bind), an "unexplained" gap, a
      manned-idle scope -- each must hedge, never vouch a cause it cannot prove.

CONVERSATION is the goal. A truthful answer that fails conversation FAILS the bar.
Five dimensions:

  C1  RESPONSIVENESS -- the question asked, at the level asked. A direct question
      leads with the asked quantity (not a table the reader must mine). A "how
      many" gets a count; a "why" gets a cause; a "what should I do" gets scoped
      advice, never a status recital.
  C2  REGISTER FIT -- the ladder's rungs present where earned, absent where not.
      Testimony is the base (always). "My take:" earns its place above the facts
      on causal / diagnostic / advice answers, and is ABSENT on lookups. An
      invitation may end a diagnostic answer; lookups end in silence.
  C3  CONTEXT CARRY -- follow-ups, corrections, deixis, selection, menus resolve
      the way the conversation implies. A live board selection wins over stale
      history and the answer SAYS which context won. A correction re-answers the
      prior question; an unresolvable ellipsis clarifies, never guesses.
  C4  HUMAN SURFACE -- planner units and one voice. No evidence-speak (module
      ids, UUIDs, raw driver/finding codes, "=== q ===" headers), no template
      nonsense ("Nothing scheduled for all"), no markdown leakage.
  C5  GRACEFUL EDGES -- honest scoping over a confident wrong answer. A category
      error (a machine name where an order is asked) is redirected, never
      answered as if valid. An unsupported question (optimality, "a better
      schedule") refuses; it never dumps the schedule. An absent entity is named
      as absent, never answered globally.

------------------------------------------------------------------------------
OUTPUT BUCKETS (verbatim -- where each triaged turn goes)
------------------------------------------------------------------------------

DEFECTS
  Truth failures (T1-T3) or hard-ruling violations (M10 write path, register
  blending, a fabricated citation, a confident-wrong answer). -> a corpus
  specimen in tests/test_ai_voice.py AND a line on the next session's errand list.
  These are not judgment calls; they ship no matter the prose.

CONVERSATION FAILURES
  Truthful but non-responsive, robotic, or context-dropping (a C1-C5 miss that is
  not a truth miss). -> triaged by FREQUENCY and SEVERITY. A robotic answer that
  recurs across a whole route fan is a pattern; a one-off awkward phrasing is a
  note. High-frequency / high-severity failures become corpus specimens; the rest
  become errand-list items ranked by how often the sweep hit them.

JUDGMENT CALLS
  Compliant on both axes but felt-quality-uncertain -- a "My take:" that may be
  too strong, an invitation that may be one too many, a hedge that may read as
  wishy-washy. -> the FOUNDER, target UNDER TEN per sweep. Claude proposes a
  crisp question ("is this take earned or presumptuous?"), never a verdict.

EXEMPLARS
  The best answers -- kept deliberately as calibration anchors and as
  graded-correct corpus candidates. An exemplar is what "fantastic" looks like on
  this route; the next sweep is measured against it.

------------------------------------------------------------------------------
GRADED EXAMPLES (drawn from the founder's real transcripts)
------------------------------------------------------------------------------

The canonical TRUTH-PASSES / CONVERSATION-FAILS case (round one, the Glass Box
close): the "filing cabinet" answer. Every fact correct, every citation real --
and it read like a database dump ("Total findings: N | Codes: ..."), answered the
noun instead of the question, and wore the machine's vocabulary. TRUTH: pass.
CONVERSATION: fail on C1 (not the question) and C4 (evidence-speak). Bucket:
CONVERSATION FAILURE, high frequency (it recurred across every findings answer) ->
became the CU2 subject-bearing render + the audit corpus. This is the shape the
rubric exists to catch: correct is not the same as good.

DEFECT example (round three, CU7a): a blocked-by claim stitched from unrelated
facts (a real shared-machine kernel + an adjacency and timestamp that belonged to
a third order). TRUTH: fail on T2 (fabricated adjacency). Bucket: DEFECT.
Note the protocol it also taught: audit the claim against the PINNED run's
persisted document, never a deterministic re-solve of a different world (the
re-solve was itself the source of the false "fabrication" verdict). R-AI4(4).

RESPONSIVENESS example (round three): "how many orders are late" -> a status
recital instead of a count; "what should I do about lateness" -> the are-there-
late-orders list. TRUTH: pass. CONVERSATION: fail on C1. Bucket: CONVERSATION
FAILURE -> the advice route + the count-leads-with-the-count fixes.

CONTEXT example (round three): "whats the end time of this order" with a live
selection -> must bind the selection, answer that order, and say "[from board
selection]". A miss here (binding stale history, or clarifying when a selection
was present) is a C3 CONVERSATION FAILURE.

REGISTER example (R-AI3): "My take:" detached the moment the LLM became the
default, because nothing guarded the delivery path it rode. A causal answer with
no take where one is earned is a C2 CONVERSATION FAILURE; a take blended INTO the
testimony (no label) is a DEFECT (register blending).

------------------------------------------------------------------------------
THE MECHANICAL PRE-TRIAGE (the sidecar -- what the runner emits, machine-checked)
------------------------------------------------------------------------------

The runner writes a findings sidecar (JSON) beside every transcript. It carries
only what is checkable WITHOUT judgment, and it SEEDS Claude's triage -- it never
grades conversation. The six signals:

  exception        -- the ask path raised or timed out (a truth-floor tripwire)
  empty            -- the answer body is empty
  validator        -- an LLM testimony failed validation and fell back / warned
  absent-entity    -- the interpreted-as line names an order absent from the
                      pinned document (a fabricated resolution)
  dark-evidence    -- an evidence-shaped route (late-order, why-on-machine,
                      order-schedule, machine-schedule, start-reason) cited zero
                      records and lit zero bars
  dead-door        -- an invitation offered a follow-up that classifies to no
                      route (the reverse-guard applied to output)
  target-unloadable-- the pinned run did not load; NO questions were fired
                      (the instrument refuses to emit garbage)

A clean sidecar is NOT a passing grade -- it means nothing tripped the mechanical
floor. Conversation quality is still Claude's read and the founder's call.

------------------------------------------------------------------------------
FOUNDER PRECEDENT LOG (judgment-call verdicts, newest last)
------------------------------------------------------------------------------

(empty -- the first sweep's judgment calls will be recorded here after the
founder's listening session. Each entry: the route, the question, the answer's
disputed property, and the founder's verdict, so a future sweep grades the same
way.)

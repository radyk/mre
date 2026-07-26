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
GRADING A SYNTHESIS ANSWER (Session 4A.5b -- R-AI5(2)/(3)/(4))
------------------------------------------------------------------------------

A synthesis answer is the SECOND TIER: no contracted route covered the question,
so the assistant reasoned to an answer from read-only evidence and every claim was
verified before it rendered. Such an answer is graded DIFFERENTLY per claim, and
the two axes above still apply -- but they apply to the right thing.

  VERIFIED claims are graded as TESTIMONY. Every truth check (T1-T3) applies
  unchanged: a verified claim that is wrong against the pinned document is a
  DEFECT, exactly as a cited route answer would be. The provenance label promises
  the planner that the sentence grounds in the named record; that promise is the
  whole product.

  INTERPRETIVE claims are graded on GROUNDEDNESS OF REASONING and USEFULNESS
  (R-AI3), never on being provably optimal. The questions to ask are: does the
  reading follow from what was actually read? Is the leap named as a leap? Would a
  scheduler with the same evidence in front of them find it a reasonable read --
  not the only possible one? An interpretive claim is NOT a defect for being an
  opinion; that is what the label is for (R-AI5(6): interpretive residue is
  first-class conversation, protected, not minimized). It IS a defect when it
  wears certainty it has not earned, when it contradicts a verified claim beside
  it, or when it could have been proven and simply was not cited.

  A MIXED answer is the expected shape. Facts proven, conclusion labeled. An
  answer that is all-interpretive where the tools could have grounded it is a
  CONVERSATION FAILURE (the reasoning skipped the evidence); an answer that is
  all-verified with no reading at all is usually a question that wanted a route.

  THE COUNT OF CUT CLAIMS IS NOT A GRADE. Claims are cut by the verifier, before
  anyone reads them; a draft with two cuts and three verified claims may be a
  better answer than one with none. What IS graded: whether the answer says so
  when something load-bearing was cut, and whether what survived still hangs
  together as an answer to the question asked.

  "PROVE IT" is graded on C1 and T2: it must show the record behind a verified
  claim, or name an interpretive claim as inference and list what it was read
  from. A prove-it turn that produces new claims instead of grounding the old one
  has changed the subject.

  WHAT THE LABEL MUST NEVER BE. Provenance comes from verification against
  independently assembled evidence (R-AI5(8)). A claim labeled verified because
  the model was confident, or interpretive because it hedged, is a DEFECT of the
  hardening pass, not a conversation note -- report it as such.

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
  dead-door        -- an invitation offered a follow-up that PARSES to no intent
                      (the reverse-guard applied to output). Session 4A.5a: this
                      now runs the REAL parse layer over each distinct offered
                      question -- what a planner clicking it would hit -- and is
                      reported SKIPPED, never clean, when no parser is available.
  expect-miss      -- a bank's own EXPECT line did not match what the parse named
                      or where the dispatch sent it (Session 4A.5a CU3). ROUTING
                      only: intent, typed subjects, follow-up linkage, route. It
                      never grades prose, and a miss is a finding to triage, not
                      a verdict.
  target-unloadable-- the pinned run did not load; NO questions were fired
                      (the instrument refuses to emit garbage)
  failed-claim-rendered
                   -- a claim the verifier CUT reached the answer surface
                      (Session 4A.5b). By construction it cannot; this is the
                      guard on that construction and it is a truth-floor
                      tripwire, never a quality read.
  ungrounded-load-bearing
                   -- a synthesis answer's own reasoning rested on a claim that
                      could not be grounded, so it was cut. The answer is
                      required to SAY so. A rising count means the tier is
                      reaching past its evidence.

A clean sidecar is NOT a passing grade -- it means nothing tripped the mechanical
floor. Conversation quality is still Claude's read and the founder's call.

Session 4A.5a also added PARSE-SPECIFIC COUNTS to every transcript and sidecar
(parses, model calls, retries, malformed emissions, clarifies, median latency).
They are instrumentation, not a grade: a rising clarify rate may mean the parse got
more honest or that the prompt got worse, and only reading the transcript tells you
which.

Session 4A.5b added the same for the SECOND TIER: synthesis answers, claims by
verdict (verified / interpretive / failed-and-cut), the ungrounded-load-bearing
count, the tool-call histogram, and TOTAL conversational latency split by tier
(parse+route vs parse+synthesis). Read them the same way. A high interpretive share
is not a failing grade -- it is what an honest reading of thin evidence looks like,
and R-AI5(6) protects it. A high VERIFIED share on questions whose answers are
really judgments would be the worrying direction.

------------------------------------------------------------------------------
FOUNDER PRECEDENT LOG (judgment-call verdicts, newest last)
------------------------------------------------------------------------------

Each entry: the route, the question, the answer's disputed property, and the
founder's verdict (OPEN until the listening session rules), so a future sweep
grades the same way.

OPEN (Session 4A.3c, awaiting round-four verdicts -- the three working-thread
judgment calls the repairs surfaced):

  1. LIT-BARS FEEL AT VOLUME (C-cross, all narrating routes).
     Route: order-schedule / start-reason / machine-schedule.
     Question (e.g.): "whats running on CUT-01".
     Disputed property: CU2 now lights EVERY narrated placement's bar. On a busy
     machine that is many bars at once. Is the simultaneous highlight informative
     or noisy? Should a long listing cap the lit set (e.g. only the late rows), or
     is lighting exactly what the answer lists the right contract?
     Verdict: OPEN.

  2. INVITATION FREQUENCY ACROSS BROADENED COVERAGE (C2).
     Route: coaching / gap-between / late-orders / why-late / data-problems.
     Disputed property: 4A.3b CU4 widened invitations to more route families.
     Across a whole conversation, does the "Want ...? Ask ..." offer land as
     helpful fluency or as a tic? Is one-per-answer still too many when several
     answers in a row each carry one?
     Verdict: OPEN.

  3. TAKE FREQUENCY (C2).
     Route: late-order / swap-move / advice (the "My take:" carriers).
     Disputed property: the first sweep rendered 28 "My take:" lines across 42 LLM
     renders. Is a take on ~two-thirds of causal/diagnostic answers the right
     density, or does it dilute the ones that matter? Which answers earn silence?
     Verdict: OPEN.

OPEN (Session 4A.5b, from its own sweep):

  4. "ARE YOU SURE ABOUT THAT" -- REFUSE TO VOUCH, OR MEET IT WITH EVIDENCE? (C5/T3)
     Route: contested-fact (was: the `verification` CLARIFY).
     Question: "are you sure about that", one turn after being told ORD-13 is on
     time.
     Disputed property: the bank's EXPECT line (written in 4A.5a) wants the
     `verification` clarify -- "I can't confirm a previous statement as correct; I
     answer from the evidence, not my own claims." The parse now reads it as
     `contested-fact` and the answer is: "Good news -- the record actually has
     ORD-13 finishing on time, 11.7 days early (due 2026-01-16), not late." Both
     are honest and neither capitulates. The clarify is stricter about the
     assistant never vouching for itself; the contested-fact answer is more useful
     and re-grounds the claim in the record rather than declining. Which is the
     right register for a planner who is unsure -- and if it is the second, the
     bank's expectation is the thing that is stale, not the behaviour.
     Verdict: OPEN. (The expectation was deliberately NOT relaxed in-session; it
     is recorded as the sweep's one remaining scenario miss.)

  5. A HYPOTHESIS STATEMENT: SCOPE THE ADVICE, OR REASON ABOUT IT? (C1)
     Route: synthesis (was: advice).
     Question: "maybe if splitting is allowed less orders would be late".
     Disputed property: 4B.4 routed hypothesis-statements to `advice`, which scopes
     what to DO about lateness. The second tier now takes it instead and answers
     the hypothesis on the evidence: names the one late order and its placement
     with citations, then reasons -- labeled -- that splitting could help if the
     pieces fit earlier gaps, and might not if the bottleneck is capacity rather
     than flexibility. The second engages the planner's actual conjecture and
     hedges it; the first tells them what to do about lateness generally. Which
     does a planner thinking out loud want -- and should the synthesis answer END
     by naming the coaching door (how splittable is declared)?
     Verdict: OPEN. (This is the ONLY route move in the founder-regression bank;
     the 120-question route fan moved nothing at all.)

  6. SYNTHESIS ON A FRUSTRATION TURN (C5).
     Route: synthesis, unanswerable.
     Question: "this is not helpful".
     Disputed property: an unmatched intent now reaches the second tier, which
     reads nothing, finds nothing to ground, and answers "I couldn't answer that
     one from the evidence... I'd rather say so than guess." Before this session
     the same turn got the near-miss bridge with two concrete offers. The new
     answer is honest but colder, and it offers no door. Should the unanswerable
     synthesis floor carry the nearest-capabilities offers, or does bolting them
     on blend two authored bodies?
     Verdict: OPEN.

(Resolved entries accrete below as the founder rules; newest last.)

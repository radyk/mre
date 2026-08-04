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

  C6  PREMISE INTEGRITY -- a question that ASSERTS something before it asks is
      checked before it is answered, and the check has TWO sides. Added by the
      listening docket (Session 4A.x); see the amendment at the foot of this
      file for the four measured specimens.

      C6a  A FALSE premise is CORRECTED, and the correction comes FIRST. Where
           the planner is right, say so plainly and before the explanation
           (R-AI3(4)). The correction is a LEAD, not a refusal: the answer they
           asked for still follows it, because an answer about one direction is
           not wrong, it is narrow.
      C6b  A TRUE premise is LEFT ALONE. An answer that "corrects" a premise
           that holds is the same defect wearing the other sign, and a check
           that always fires grades nothing. A committed or pinned bar really
           cannot be moved by a planner; saying so is the right answer.
      C6c  A premise the product CANNOT decide says which -- never "it can" and
           never "it can't". A chunked operation cannot be priced as a local
           move in either direction; that is a limit of our method, and a claim
           about the plant may not be manufactured from it (the ruled species:
           CostProof 4B.18, partitions 4B.21, FeasibilityGhost 4B.23).
      C6d  EVERY ASSUMPTION THE LADDER MADE IS DISCLOSED, not only the subject.
           Subject, GRAIN (which operation) and DIRECTION (which way) are three
           resolutions; disclosing one of three and calling it an INTERPRETED AS
           line is what let a direction assumption ride invisibly. A resolution
           the planner STATED is never read back to them -- only a DEFAULTED one
           earns a line, which is what keeps the line short enough to be read.

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
GRADING A PROMOTED ROUTE (Session 4A.5c -- R-AI5(7))
------------------------------------------------------------------------------

A PROMOTED route is a contracted route that used to be synthesis residue. It is
graded as TESTIMONY like any other route -- and it carries one extra question no
other route does, because it replaced something.

  DID THE PROMOTION KEEP THE HEDGES? The shape was answerable by the second tier
  only because the tier LABELED what it could not prove. A promoted route that
  states as testimony what synthesis could only read has laundered a take into
  the proven register, and that is a DEFECT of the promotion, not a conversation
  note. For `lateness-cause` specifically, two hedges were made conditions of
  promotion in its dossier: the PREMISE CHECK ("why are so many late" asked of a
  plan with one late order is answered by saying so first) and the NAMED
  UNATTRIBUTED set (an order whose hold the solved occupancy does not show is
  said to be unattributable, never given an invented mechanism). Either one
  missing is a defect.

  IS IT BETTER THAN WHAT IT REPLACED? A promotion should buy CITATIONS and
  SPEED -- the same facts, proven, in ~1.3s instead of ~10s. If the contracted
  answer says less than the synthesis answer did and proves no more, the shape
  was not ready and the honest move is demotion, not a patch.

  THE SHADOW IS NOT A GRADE. During probation the sweep answers the shape both
  ways and diffs the FACTS (`shadow:` on the transcript line). A clean diff means
  the two readings of the same evidence agree; it says nothing about whether the
  answer is good. A DIVERGED diff is not a judgment call at all -- R-AI5(7) makes
  it automatic demotion, and it is reported as a defect.

  WHAT A DEMOTION IS NOT. A demoted shape returning to synthesis is the system
  working, not a failure to report as regression. The failure would be a
  divergence that fired and was argued with.

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
  shadow-divergence-- a PROMOTED route on probation contradicted its synthesis
                      shadow on a shared quantity (Session 4A.5c). The LOUD one:
                      R-AI5(7) makes demotion automatic on divergence, so this
                      is not a note to triage, it is the trigger. Read the diff,
                      then flip the flag in PROMOTIONS.
  shadow-unchecked -- the probation shadow could not run (no synthesizer). The
                      sweep does NOT count toward the probation window. A window
                      nobody watched is not a window served.
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

RESOLVED (Session 4A.5c, ruled by the working thread and implemented):

  6. SYNTHESIS ON A FRUSTRATION TURN (C5) -- RULED: KEEP THE DOORS.
     Verdict: the unanswerable synthesis floor CARRIES the nearest-capabilities
     offers. Honest and warm are not in tension, and the offers are the same
     authored surface part 1's bridge uses rather than a second authored body.
     Implemented 4A.5c CU3(b); absence-tested where no doors exist.
     ROUND FIVE GRADES: on any unanswerable synthesis turn, the answer must say
     it could not ground an answer AND offer at least one concrete follow-up
     chosen by what the planner named. A floor with no doors is now a
     CONVERSATION FAILURE (C5), not a judgment call. A floor that offers doors
     unrelated to the subject the planner named is the same failure wearing
     politeness.

OPEN (Session 4A.5c, for round five -- the CU3 items' expected behaviours are
stated so round five grades them rather than re-discovering them):

  7. THE FIRST BEAT: IS ~10s WITH A WAITING LINE ACCEPTABLE? (C1/C4)
     Route: synthesis (any second-tier answer).
     Disputed property: the ask now two-phases. The moment the parse says the
     second tier will answer, the panel shows an authored non-answer -- "Reading
     the evidence -- no contracted answer covers that one, so I'm working it out
     from the records (up to 12 reads)" -- replaced by the answer when it lands.
     EXPECTED BEHAVIOUR round five grades: (a) the line appears BEFORE the wait,
     not with the answer; (b) it never states a fact about the schedule, a
     progress percentage, or a promise about what will be found; (c) it does not
     appear at all on a contracted answer; (d) it is gone the instant beat two
     lands, including on an error.
     The founder question: does the line make ten seconds feel attended-to, or
     does naming the wait make it feel longer? And is "up to 12 reads" useful
     honesty or machine-talk on the answer surface?
     NAMED RESIDUE: the count is a BUDGET, not a live counter. A real "(N tools
     consulted)" ticking upward needs either streaming or background execution of
     the ask, both disproportionate here; the actual count lands on the answer's
     rendered-by line. If the founder wants the live count, that is the work.
     Verdict: OPEN.

  8. THE ADJACENT-MATCH GUARD: IS A REASONED ANSWER BETTER THAN A NEAR ONE? (C1)
     Route: synthesis (was: late-orders / downtime).
     Questions: "how many orders will be late next month"; "how much of CUT-01s
     week is actually working time".
     Disputed property: both used to reach the nearest contracted route and be
     answered, correctly, about something slightly different -- with citations,
     which made the near-miss harder to notice. The parse now reports the
     qualifier the route cannot honour and the dispatch diverts to the second
     tier, whose answer names the qualifier in its rendered-by line.
     EXPECTED BEHAVIOUR round five grades: (a) the answer engages the QUALIFIER
     ("next month", "actually working time") or says honestly that the evidence
     does not carry it; (b) the rendered-by line names the qualifier; (c) a
     qualifier the route DOES honour ("what's running on CUT-01 tomorrow") must
     NOT divert -- a guard that fires too often is a second way to lose a proven
     answer, and that failure would look like slowness plus hedging.
     The founder question: a planner asked a question the plan cannot answer.
     Is a labeled reading of the adjacent evidence the right response, or would
     they rather have the near answer with the mismatch stated plainly?
     Verdict: OPEN.

  9. THE PROMOTED ROUTE'S SECOND TURN (C1/C2).
     Route: prove-it, following `lateness-cause`.
     Disputed property: before the promotion, "why so many late orders" was a
     synthesis answer and "how do you know that" opened the record behind one of
     its claims. Now the first answer is contracted and cites its records
     inline, so the prove-it turn has no claim of OURS open to ground and gives
     the honest no-target copy.
     EXPECTED BEHAVIOUR round five grades: the no-target copy must point at the
     citations already on the previous answer, not read as a shrug.
     The founder question: is that a downgrade the planner feels? A promotion
     buys citations on turn one and spends the grounding pass on turn two.
     Verdict: OPEN.

(Resolved entries accrete below as the founder rules; newest last.)

 10. THE OPEN DELTA CARD (C1/C3). Session 4B.5 CU2.
     Route: open-card.
     Questions: "what orders are affected in this move"; "whats the delta";
     "these orders -- which ones are they".
     Disputed property: a priced card is on the board showing the placement, the
     cost split and the affected set, and the founder's question about it reached
     `swap-move` -- a route that weighs two orders' slack and has never heard of
     the card. The answer was already computed and on screen. The card is now the
     TOP of the resolution ladder and `open-card` reads it back.
     EXPECTED BEHAVIOUR round six grades: (a) the answer VOICES the card -- every
     figure in it is the card's own, so the two surfaces can never state
     different numbers; (b) it splits the cost the way the card does (window
     re-optimization vs your move) rather than quoting the fused total; (c) with
     NO card open the same words are not answered as a card question and no stale
     card is remembered; (d) a card open does not capture questions that name a
     different intent -- it is a channel, not a mode.
     The founder question: is reading the card back the right answer, or does a
     planner asking about a card in front of them want something the card does
     NOT already show (the alternatives, the next move)? If the latter, this
     route is a bridge and not a destination.
     Verdict: OPEN.

 11. THE VACUOUS CAUSAL ANSWER (T3/C1). Session 4B.5 CU3.
     Routes: why-on-machine, late-order, start-reason, gap-between.
     Question: "why is ORD-000008 on PAINT-02?"
     Disputed property: answered "because the machine was busy with other work
     [record: bafa03f1...]". The record was real and the clause was the authored
     CAPACITY_BLOCKED driver phrase carried verbatim, so nothing was fabricated
     and every fabrication check passed it. It named no machine, no alternative
     and no quantity -- and the machine it refers to is one the order is not on.
     TWO FIXES, and they are not substitutes: the assembler now reads the
     capacity story out of the solved occupancy, and a vacuity tripwire fails a
     causal answer closed to the template when it names no driver, no entity
     beyond the question's own subjects and no quantity.
     EXPECTED BEHAVIOUR round six grades: (a) a capacity-forced placement NAMES
     the eligible machines that were occupied and what held them; (b) where the
     occupancy does not attribute it, the answer says so and does not invent a
     mechanism; (c) where the machine is the ONLY eligible one, that is stated as
     a capability fact -- no rearrangement of the plan would have changed it;
     (d) no causal answer anywhere in the sweep consists of a driver phrase and
     nothing else.
     NAMED LIMIT: the tripwire alone would NOT have caught the founder's
     sentence, because a driver phrase counts as saying something. A floor cannot
     also be a ceiling; the vocabulary fix is what catches it.
     The founder question: is naming the blocked alternatives the answer they
     wanted, or does "why is it here" really mean "could it have been anywhere
     else, and what would that have cost"? The second is a priced question and a
     different route.
     Verdict: OPEN.

 12. THE REPEAT RIDERS (C2/C5). Session 4B.5 CU5.
     Routes: any re-fired within two turns; advice -> coaching.
     Disputed property: three founder-caught shapes, one theme -- answering the
     sentence rather than the turn. (a) "so you can't tell me if overtime will
     help", asked after the advice scoping answer, re-fired that same answer
     verbatim; it names a capability and is now coaching. (b) a route asked twice
     running delivered itself word for word. (c) a count re-asked recited its
     whole list again.
     EXPECTED BEHAVIOUR round six grades: (a) the push-back reaches the named
     capability's coaching and reads as having heard the objection, not as a
     topic change; (b) the varied lead reads as acknowledgement, never as
     impatience or as a new fact -- the body beneath it is byte-identical; (c)
     "13 -- want the list?" reads as attentive rather than curt, and the offer
     is real (terseness must never cost the planner the detail).
     The founder question: does the varied lead help, or is silence about the
     repetition better than commenting on it? A system that notes it is being
     asked twice can read as impatient.
     Verdict: OPEN.

------------------------------------------------------------------------------
RECALIBRATION LOG -- regression_founder_r5 (Session 4B.17, 2026-07-30)
------------------------------------------------------------------------------

The bank was committed 4B.5 and had never been graded. docs/07 section 5a.22
named its expectations invalidated three times over. This is the append-only
record of every expectation that moved, its cause, and its old text. Nothing
above this line was rewritten.

THE FOUR RULES THIS RECALIBRATION FOLLOWED

  (a) THE QUESTION TEXT DOES NOT CHANGE. Not one of the 27 original question
      lines was edited. Where a premise was false and the product now corrects
      it, the EXPECTATION moved and the specimen stayed wrong on purpose.
  (b) EVERY CHANGE IS LOGGED HERE with the session that caused it and the old
      text. Nothing was rewritten in place.
  (c) NO EXPECTATION WAS COPIED FROM CURRENT OUTPUT. Every figure below was
      re-derived from the pinned world's PERSISTED document (R-AI4, no
      re-solve) or quoted from the close-out of the session that shipped the
      behaviour. The bank was recalibrated BEFORE it was run for the first
      time, so there was no output to fit to.
  (d) WHERE THE RIGHT EXPECTATION COULD NOT BE DERIVED, the slot is marked
      UNGRADED with its reason. Counted at the bottom.

THE ONE WORLD FACT THAT MOVED THE MOST EXPECTATIONS

  NOTHING IS LATE ON THE PINNED BOARD. All 26 placed demands finish before
  their due date (worst slack ORD-000011, 502 minutes), tardiness is $0.00,
  tardiness_floor is absent, and the solver closed the bound (OPTIMAL, gap
  0.0, ledger 16,481.95). Nine of the bank's questions are about lateness.
  Every one of them is now a FALSE-PREMISE specimen, graded on 4B.13's premise
  correction and its region note rather than on a list.

CHANGES, in bank order

 R1. THE CARD'S FIGURES (section A, all six card turns). Cause: 4B.7 retiring
     R-SC3(2) -- the earliness coefficient left the objective, so the window
     solve and the sandbox baseline minimize the same expression and
     reopt_delta_abs is 0.00 BY CONSTRUCTION (docs/07 section 5a.12's
     discharge). Re-read from the committed capture
     tests/cockpit/fixtures/rolling/sandbox.json; the constants live in
     src/mre/ai_exam/runner.py.
       WAS: total -11,953.08 = reopt -11,975.83 + move +22.75;
            four affected orders (ORD-000011 -9,800.42, ORD-000003 -2,175.42,
            ORD-000022 0.00, ORD-000028 0.00); lateness_delta_min -28,742;
            moves 7.
       NOW: total +32.20 = reopt 0.00 + move +32.20; affected_orders EMPTY;
            lateness_delta_min 0; moves 1.
     CONSEQUENCE WORTH MORE THAN THE FIGURES: the 4B.6a specimen "what did the
     move itself cost, not the re-solve" NO LONGER DISCRIMINATES. Move equals
     total on every card the shipped product can now produce, so an answer
     quoting the total is indistinguishable from one quoting the move. It is
     reported as unexercisable rather than counted as a pass; what it still
     grades is the SIGN (a cost stated as a cost) and the honouring of the
     question's own exclusion.

 R2. "what orders are affected in this move" (section A). Cause: R1's empty
     affected set.
       WAS: the affected orders BY NAME, with what happens to each, read back
            from the card.
       NOW: reads the card back and says plainly that NO order's service
            outcome changes. Naming an order here is FABRICATION.

 R3. "these orders -- which ones are they" (section A). Same cause as R2.
       WAS: name them.
       NOW: resolve the ellipsis to the card and answer that the affected set
            is empty.

 R4. "whats the delta" with NO CARD OPEN (section A). Cause: a bank AUTHORING
     BUG found during this recalibration, not a product change. The line read
     EXPECT route=open-card directly beneath a comment reading "must reach a
     plan route (or the reasoning tier) -- never open-card". The machine
     expectation asserted the defect the comment forbids, so a run would have
     graded the failure as the pass.
       WAS: EXPECT route=open-card
       NOW: no EXPECT line. UNGRADED BY MACHINE, two reasons: EXPECT can only
            assert equality and this expectation is a negative; and which route
            SHOULD take a subjectless "whats the delta" with no card is not
            derivable from the document (clarify, version-diff, edit-summary
            and the second tier are all defensible). Hand-graded on two
            clauses: no card is invented, and no figure from the closed card
            appears.

 R5. "which orders are late" / "how many orders are late" / "how many are late
     again" / "what should i do about the late orders" / "what should i do
     about it" / the four-turn seal (sections A and C). Cause: the pinned world
     has no late orders, plus 4B.13 Item 3 (lateness_set separates not-late
     from not-scheduled) and the lateness-cause promotion's premise-check
     condition.
       WAS: the number and an offer ("13 -- want the list?"), not the full
            recitation a second time.
       NOW: the count is ZERO. The answer says nothing is late and names its
            region -- 26 placed in this window, 14 beyond the horizon that are
            neither late nor on time. An offer to list an empty set is a
            defect, not attentiveness. Advice about "the late orders" corrects
            the premise before scoping.

 R6. "why is this one late" with a card open over a stale selection (section
     A). Cause: the same world fact. ORD-000023 finishes 2026-01-05 16:51
     against a due date of 2026-01-14 -- 13,388 minutes early.
       WAS: the answer resolves against the CARD's order and says so.
       NOW: unchanged on the ladder clause, PLUS a premise correction --
            ORD-000023 is not late. Binding the card's order and then inventing
            a cause for a lateness that does not exist is a truth failure, not
            a context win.

 R7. "why is ORD-000023 on MILL-01" and "why did ORD-000009 end up on CUT-01"
     (section B). Cause: 4B.13 Item 1(i), the premise guard. Both premises are
     false against the persisted document: ORD-000023 runs PRESS-FAST only;
     ORD-000009 runs MILL-02, ASM-01 and FINISH-01, and CUT-01 -- the busiest
     machine on the board -- carries none of it.
       WAS: the answer names the eligible machines that were occupied and WHAT
            held them -- or says plainly that the occupancy does not attribute
            it.
       NOW: the answer CORRECTS the premise in its first clause, lists the real
            placements as evidence, and offers the question that would get the
            cause. A correction the planner cannot see -- silently answering
            about PRESS-FAST instead -- is the premise ECHO wearing a right
            answer.

 R8. "why is ORD-000012 on PAINT-01" (section B, the control). Cause: 4B.13
     Item 1's third fix (the only-eligible-machine case got its own lead
     instead of a capacity claim the next sentence contradicted). PAINT-01 is
     the only machine qualified to run that step.
       WAS: names the eligible machines that were occupied and what held them.
       NOW: the only-eligible LEAD as a CAPABILITY fact -- no alternative to
            weigh -- with the evidence chain for the decision about THIS
            operation. On this board there are no blocked alternatives, so
            naming any would be fabrication.

 R9. "but why" after it (section B). Cause: R8 changed what the chain is.
       WAS: about THAT chain, not about the plan's aggregate lateness.
       NOW: same rule, and now checkable in both directions -- aggregate
            lateness on this board is ZERO, so an aggregate answer here is
            non-responsive AND false.

R10. "what should i do" twice running (section C(b)). Cause: 4B.15 section
     5a.42 -- the repeat detector was INVERTED (four measured firings, zero
     true positives, escalating to "Still the same; nothing has changed since
     you asked") and the scold was deleted.
       WAS: the second answer is not the first answer verbatim.
       NOW: the same, PLUS the varied lead must read as acknowledgement or
            self-doubt and never as a scold. This is the same QUESTION twice,
            so repeat is the correct signal; deaf (the same delivered ANSWER to
            a DIFFERENT question) is not.

R11. "how many machines are there" / "how many machines" (section C(c)).
     Cause: 4B.13 Item 4 -- both facts, both labelled, idle machines named.
       WAS: no substantive expectation was written; the turn carried only
            EXPECT intent=machine-count.
       NOW: 15 declared, 10 carrying work, and the 5 idle ones NAMED (CUT-02,
            CUT-03, FINISH-03, HEAT-02, PRESS-SLOW). A bare "15" misleads a
            planner reading a board with ten lanes; a bare "10" hides five
            machines they own.

R12. THE HEADER'S WORLD VOCABULARY. Cause: the bank still described the
     279dec02 world.
       WAS: "machines: CUT-01, MILL-01, MILL-02, ASM-01, HEAT-01, PAINT-01,
            FINISH-01, FINISH-02" (eight) and a committed/active list.
       NOW: 15 declared / 10 carrying work, enumerated, with the idle five, the
            14-order tray by name, the reference date and window, the weekday
            anchors (Jan 13 is a Tuesday, Jan 15 a Thursday), and the four
            placements the section-B and section-D specimens turn on. The old
            header would have had a reader grading against a plant that does
            not exist.

SPECIMENS ADDED (Session 4B.17, verbatim -- eight named by the brief, of which
two were ALREADY BANKED)

  ALREADY PRESENT, expectations recalibrated (see R7):
    "why is ORD-000023 on MILL-01"
    "why did ORD-000009 end up on CUT-01"
  ADDED:
    "why is ORD-000023 on MILL-99"                 -> section B (4B.13)
    "why does ORD-000011 go through downtime"      -> section D (4B.13)
    "it seems it should be able to start on tuesday
     after op10 finishes"                          -> section D (4B.14)
    "how do i change that"                         -> section D (4B.16)
    "what should I be worried about"               -> section D (4B.16)
    "would overtime on CUT-01 help"                -> section D (4B.15)

  The bank goes from 27 questions to 33. Three of the product's newest routes
  (why-here, what-would-change, briefing) had NO regression coverage before
  this, which is the deeper reason the bank needed recalibration rather than a
  re-run.

UNGRADED, WITH REASONS (rule (d))

  FULLY UNGRADED BY MACHINE: 1 question.
    "whats the delta" with no card open -- see R4. The expectation is a
    negative and EXPECT cannot express one; the correct destination is not
    derivable. Hand-graded on two clauses.

  PARTIALLY UNGRADED (subject binding graded, intent/route deliberately not):
  2 questions.
    "why does ORD-000011 go through downtime" -- which route owns "why does X
    go through downtime" was never ruled; 4B.14 explicitly declined to rule
    whether start-reason and why-here should merge, and downtime is
    machine-scoped. EXPECT order=ORD-000011 only.
    "would overtime on CUT-01 help" -- unanswerable by any contracted route
    today; which route should take it is a vocabulary call the commissioning
    brief put out of scope. EXPECT machine=CUT-01 only, because that is what a
    correct parse must do whichever route wins.

  So: 33 questions, 32 carrying a machine expectation, 30 of those constrained
  on intent or route.

------------------------------------------------------------------------------
AMENDMENT -- C6 PREMISE INTEGRITY (the listening docket, Session 4A.x, 2026-08-03)
------------------------------------------------------------------------------

Nothing above this line was rewritten. C6 was ADDED to the CONVERSATION axis
because the four specimens below are all TRUTHFUL -- every figure in every one
of them is correct against the persisted document -- and all four fail a planner
anyway. T1-T3 cannot see them; C1 comes closest and does not reach, because the
answers ARE responsive to a question, just not the one that was asked.

THE FOUR, MEASURED VERBATIM ON THE DEMO BOARD (rolling-db5395dc-2ae) BEFORE ANY
FIX. The full transcripts are in docs/closeouts/4a-listening-docket.md section 2.

  S1  Q: "why cant ORD-000126 op30 start earlier"
      A: "Answering about ORD-000126 op10 on CUT-01 -- the first of its 3
          operations. Nothing prevented ORD-000126 op10 from starting earlier..."
      True about op10. The planner asked about op30. -> C6d (the GRAIN).

  S2  Q: "why cant this be moved", with ORD-000128 op20 selected
      INTERPRETED AS: "why cant ORD-000128 be moved [from board selection]"
      Three resolutions made, one disclosed. -> C6d (the DIRECTION and the
      GRAIN both silent, in the same line that named the subject).

  S3  the same question presupposes the bar cannot move; it can. -> C6a.

  S4  the same question owes a TWO-direction answer. -> C1 and C6a together.

HOW A GRADER APPLIES C6 WITHOUT TURNING IT INTO A MACHINE CHECK. C6 is graded
like every other conversation dimension: by reading (R-AI4(2)). The question to
ask of a turn is not "did the premise block appear" -- it is:

  * did the question ASSERT anything? (most do not; C6 then does not apply and
    an answer that carries a premise block would be the defect)
  * if it did, is the assertion true? and does the answer act on the ANSWER to
    that, rather than on the shape of the question?
  * is a resolution the answer relied on visible to the person who did not make
    it?

A C6 miss where the assertion was FALSE is a DEFECT bucket item, not a
conversation-failure one: an answer that explains why something cannot be done
when it can be done is confident-wrong, and confident-wrong ships regardless of
prose. A C6b miss -- correcting a premise that HOLDS -- is the same bucket for
the same reason.

WHAT THIS AMENDMENT DOES NOT DO. It adds no expectation to any existing bank and
changes no question text (rule (a) of the r5 recalibration, carried). The
specimens live in a NEW versioned bank, tests/ai_exam/banks/sweep_mobility_v1.txt,
which at the time of writing is UNRUN -- the session's API credit was exhausted
before the sweep. That is recorded in the close-out as an owed run, not as a
result.

===============================================================================
AMENDMENT -- axis C7: CLAIM CLASS (Session 4A teaching-graft (a), 2026-08-03)
===============================================================================

R-TG1 gives open synthesis a second claim class. A sentence of domain knowledge
-- how scheduling, optimization and plants behave in general -- is not a read of
this board and must not be dressed as one. The axis grades whether the answer
puts each sentence in the class it belongs to.

WHY IT IS A NEW AXIS AND NOT A CASE OF C2 (provenance). C2 asks whether a claim's
provenance is visible and correct. C7 asks a prior question: which KIND of thing
the sentence is. A general-knowledge sentence can have perfectly visible
provenance -- "[synthesis -- read from: 0f093432, ff8a63c4]" -- and that
provenance is a lie about what the sentence is, which C2 cannot see, because the
records really were read and the marker really is the one the tier uses.

MEASURED AT HEAD, before the class existed, on the demo board `rolling-db5395dc-2ae`:
ten domain-inviting probes, seven synthesis answers, SEVEN unlabeled
general-knowledge sentences shipped -- five wearing "[synthesis -- read from:
<ids>]" and two wearing "[synthesis -- my reading, no record states this]" beside
a sample note reading "(based on the 26 row(s) constraint_catalog returned, not
the whole plan)". That note sat beside a sentence about why exact methods scale
poorly on combinatorial problems.

WHAT C7 ASKS

  * is every general-knowledge line marked, with a marker naming BOTH halves
    (what it is, and what it is not)?
  * does any marked line carry an order, a machine, a time, money, or a figure
    this run computed? (a marked line that does is the ESCAPE HATCH: an
    unverified board claim wearing a label that forbids checking it)
  * do the board claims in the same answer keep their citations? (a change that
    quietly relabeled board claims as general would look tidy and be the worst
    outcome available)
  * do contracted answers render no general marker at all?

A C7 miss of the second kind is a DEFECT bucket item, not a conversation-failure
one, for the same reason a false premise is: it ships an unfalsifiable claim
about the plant.

WHAT THIS AMENDMENT DOES NOT DO. It adds no expectation to any existing bank and
changes no question text (rule (a) of the r5 recalibration, carried). The
specimens live in a NEW versioned bank, tests/ai_exam/banks/sweep_teaching_v1.txt,
whose four expectation families are graded by
tools/spikes/teaching_graft_a/grade_gk_sweep.py -- the exam grammar's EXPECT
lines grade ROUTING only, and C7 is about claim classes, so the grader reads the
same run's rendered answers and per-turn claim counts.

ONE EXPECTATION IN THAT BANK IS UNGRADED FOR ROUTING, BY DESIGN, and it is
logged here because it moved: "why do late orders tend to snowball on a board
like this one" was written as a domain probe and reached `lateness-cause` on the
live parse. It is a board question as much as a domain one. The route
expectation was REMOVED rather than set to either value -- asserting the route
intended would fit the expectation to the author, and asserting the route
observed would fit it to the output, which recalibration rule (c) forbids. The
question text is unchanged and the answer is still graded, as a control.

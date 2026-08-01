# Question-parse prompt — a GOVERNED ARTIFACT (R-AI5(1))

    prompt_version: 14
    ruling:         R-AI5(1) — every question is parsed FIRST by a language model
                    against a CLOSED intent vocabulary, with the conversation
                    history, live board selection, and last-answered subject as
                    context. The parse emits a closed contract — never an answer.
    introduced:     Session 4A.5a (2026-07-25)
    v2:             Session 4A.5b (2026-07-26) — the follow-up vocabulary gains
                    `prove-it` (R-AI5(4): "prove it" is always available and
                    triggers the grounding pass conversationally).
    v3:             Session 4A.5b (2026-07-26), from its own sweep — two repairs.
                    (a) The prompt never told the model that an UNMATCHED question
                    is now ANSWERED (R-AI5(2)'s second tier), so it kept stretching
                    aggregate and comparison questions into the nearest contracted
                    route: "which machine is the bottleneck" -> `advice`, "is the
                    work spread evenly" -> `inventory`, "whats the busiest day" ->
                    `briefing`. Rule 7 now says what unmatched costs and what it
                    buys. (b) `prove-it` was never emitted: every ask-for-grounds
                    landed on the `verification` clarify, whose wording it sat too
                    close to. The two are now separated by what the planner wants
                    back — the grounds, or a yes/no.
    v4:             Session 4A.5b (2026-07-26), from the same sweep after v3.
                    `prove-it` was recognized and then thrown away: asked "how do
                    you know that" the model emitted `"intent": "prove-it"`, an id
                    the vocabulary did not carry, so the parse was discarded as
                    malformed TWICE and the planner got "I couldn't make out what
                    that one was asking" — for the one question the system is best
                    at answering. `prove-it` is now an Intent as well as a
                    follow-up kind (the pair `confirm-take` already set), so the
                    gesture the model can name is nameable. A vocabulary-class
                    change: `Intent`, `INTENT_MEANINGS`, `ROUTE_TAXONOMY` and
                    `ROUTE_OFFERS` in the same commit as this bump.
    v5:             Session 4A.5b (2026-07-26), same sweep, same class seen twice
                    more: `{"intent": "list-expand", "followup_of":
                    "list-expand"}`. The model names the GESTURE correctly and
                    files it in the wrong field. The OUTPUT block now says plainly
                    which names belong to which vocabulary, and the parser treats a
                    follow-up kind in the intent field as a MISFILING rather than
                    garbage (intent -> `unmatched`, linkage kept) instead of
                    discarding a correct reading twice and clarifying.
    v6:             Session 4A.5b (2026-07-26), fourth sweep — the cost of v4.
                    With `prove-it` nameable, it over-attracted: "but why" on the
                    founder's own round-four bank (ORD-05 selected, one turn after
                    its cause chain) parsed as `prove-it` and dead-ended on "I
                    don't have a claim of my own open to ground" — the exact class
                    4A.5a existed to kill. `deepen` and `prove-it` are now
                    separated by WHAT IS BEING QUESTIONED: a deeper cause in the
                    plant, or where the assistant's sentence came from. The test:
                    if the question would still make sense asked of the schedule
                    rather than of the assistant, it is not `prove-it`.
    v7:             Session 4A.5c (2026-07-26) — two changes, both reviewed.
                    (a) THE ADJACENT-MATCH GUARD (rule 9, new field
                    `dropped_qualifier`). The 4A.5b sweep's two surviving unmet
                    expectations were the same shape and neither was a mis-parse:
                    "how many orders will be late NEXT MONTH" -> `late-orders`,
                    which answers about THIS plan; "how much of CUT-01s week is
                    ACTUALLY working time" -> `downtime`, which answers the
                    complement. In both the nearest intent really IS the nearest
                    one, and answering as it answers a question the planner did
                    not ask — with perfect citations, which is the failure mode
                    rule 7 already names for `unmatched`, wearing a different
                    hat. The model now REPORTS the stated qualifier the intent
                    drops; the DISPATCH decides to divert (R-AI5(8)'s discipline
                    applied to routing: the model reports, it never grades).
                    (b) `lateness-cause` joins the vocabulary — the ONE promoted
                    shape (R-AI5(7)), with its dossier as the authority. Rule 7's
                    "why are so many late" example moves from an `unmatched`
                    illustration to a named intent, and `late-orders`' meaning is
                    sharpened against it.
    v8:             Session 4B.5 (2026-07-26) — THE OPEN DELTA CARD joins the
                    resolution ladder (CU2). The founder asked "what orders are
                    affected in this move" with a priced card on screen showing
                    exactly that, and it parsed as `swap-move` — a route that
                    reasons about two orders' slack and has never heard of the
                    card. The answer was already computed and in front of them.
                    The context block now names the OPEN DELTA CARD first, at the
                    top of the resolution ladder (card > selection > previous
                    answer > history), and `open-card` joins the vocabulary as
                    the route that reads it back. Reachable only while a card is
                    open, which the context block states and the DISPATCH
                    enforces — the model reports what it sees, it never decides
                    whether the card is really there. A vocabulary-class change:
                    `Intent`, `INTENT_MEANINGS`, `SubjectSource`,
                    `ROUTE_TAXONOMY`, `ROUTE_OFFERS`, the assembler and its
                    authored copy in the same commit as this bump.
    v9:             Session 4B.6 (2026-07-27) — THE COARSE ZONE joins the
                    vocabulary (R-SC2 coarse-zone amendment, R-AI1). Beyond-
                    horizon demand is now coarsely PLACED rather than merely
                    listed, which makes two questions answerable that previously
                    had no route at all and would have fallen to the second tier
                    for want of a vocabulary entry, not for want of grounds:
                    `coarse-fit` ("will it fit", "can we take this on") and
                    `bucket-load` ("why is week 3 full", "what's filling up
                    March"). Both are ROLLING intents — they speak about the
                    sliced world, whose state lives in the document's
                    RollingBlock rather than in the window-0 snapshot.
                    Deliberately NOT added: a route for "when will ORD-X start".
                    That is already `why-not-scheduled-yet`, whose answer now
                    carries the coarse bucket beside the due-date heuristic; a
                    third route for it would be the ad-hoc bolt-on this ruling
                    forbids. The asymmetry of the coarse model is carried in the
                    MEANINGS so the model does not learn a false symmetry: a
                    coarse refutation is a proof, a coarse placement is not a
                    promise. A vocabulary-class change: `Intent`,
                    `INTENT_MEANINGS`, `ROUTE_TAXONOMY`, `ROUTE_OFFERS`,
                    `ROLLING_INTENTS`, the two answerers and their authored copy
                    in the same commit as this bump.
    v10:            Session 4B.13 (2026-07-29) — `solve-optimality` joins the
                    vocabulary, discharging docs/07 §5a.29. 4B.11 rendered the
                    cost proof on the strip chip and as an unprompted money
                    rider, but nobody could ASK for it: "is this schedule
                    optimal?" — the first question a cold stranger asks after
                    seeing that badge — had no route and fell to open synthesis,
                    which cannot see `solver.status`. On the pinned exam world it
                    therefore improvised its own definition ("optimal on the
                    dimensions that matter most") over a lateness count that was
                    itself false, and arrived at the right verdict by the wrong
                    road. The proof existed, was correct, and was unreachable by
                    asking. The MEANING is written to hold the boundary the
                    answer depends on: this intent is about the SOLVER'S PROOF of
                    the cost optimum, not about whether the plan is good or
                    whether orders are late — those remain `advice`,
                    `late-orders` and the second tier. A vocabulary-class change:
                    `Intent`, `INTENT_MEANINGS`, `ROUTE_TAXONOMY`, `ROUTE_OFFERS`,
                    the assembler, its authored copy and the docs/07 §5a.29
                    discharge in the same commit as this bump.

    v11:            Session 4B.14 (2026-07-29) — TWO changes, one root. `why-here`
                    joins the vocabulary and `contested-fact` gains
                    `contested_claim`.

                    (a) THE BLOCKER ANALYSIS. `start-reason` knew one causal
                    story, resource contention, and the plant has at least six
                    (docs/05 A4, A1/A2, R-F1, A7/F1, B1, C1/C2, C3). When the
                    true cause was one of the other five it reached for the only
                    one it had and rendered it fluently, with citations. Measured
                    on the pinned board: ORD-000013's op20 waits for Thursday
                    because it needs 7h11m in one piece and 4h54m remained before
                    PAINT-01 closed — a chunk-fit cause explained as contention,
                    citing a timestamp four days off. `why-here` answers the
                    question actually being asked — what is the BINDING
                    CONSTRAINT on this starting earlier — and draws the
                    distinction the product could not: COULDN'T versus
                    CHOSE-NOT-TO. The two MEANINGS are written as a pair so the
                    model learns the boundary rather than a synonym: a question
                    naming an earlier time, an alternative day, or asking what
                    PREVENTS something is `why-here`; "why does it start when it
                    does" and "why so early" stay `start-reason`.

                    (b) DISAGREEMENT IS NOT RE-PARSED. Measured live: "it seems
                    it should be able to start on tuesday after op10 finishes" —
                    a challenge to the system's reasoning, carrying the correct
                    hypothesis — parsed as `contested-fact`, whose assembler knew
                    only lateness, and came back "is ORD-000013 really on time?
                    Yes - the record agrees." An affirmative that reads as
                    agreement while addressing nothing that was said. The intent
                    was right; the assembler had one proposition. The parse now
                    REPORTS which claim is disputed and the dispatch answers a
                    `timing` contest with the blocker analysis, on the planner's
                    own terms (R-AI5(8): the parse reports, the dispatch
                    decides). A vocabulary-class change: `Intent`,
                    `ContestedClaim`, `INTENT_MEANINGS`, `ROUTE_TAXONOMY`,
                    `ROUTE_OFFERS`, the assemblers, their authored copy, the
                    predicate-coverage vocabulary and this bump, one commit.

    v12:            Session 4B.15 (2026-07-29) — `attribute-lookup` joins the
                    vocabulary and `coaching`'s meaning is WIDENED. One root:
                    the coaching route was swallowing questions it could not
                    answer, and had no competitor.

                    (a) ATTRIBUTE LOOKUP. Measured live, five consecutive turns
                    went to `coaching`, four of them asking for a VALUE: "is
                    ORD-000013 op20 splittable" got capability documentation
                    with a scold; "how long does op20 take" got the order card.
                    Both are fully specified and zero-ambiguity, and the blocker
                    analysis quoted BOTH answers one exchange later off the same
                    snapshot. There was no route that reads a declared field off
                    an entity and states it. The meaning is written to separate
                    it from its two neighbours — it asks for a VALUE, not for
                    how to change one (`coaching`) and not for a whole order's
                    card (`order-attributes`) — because that boundary is where a
                    new vocabulary member costs something.

                    (b) CAPABILITY QUESTIONS ARE CATALOG QUESTIONS. `coaching`
                    meant "how do I enable X", so "can two machines share one
                    operator" — a question about what the PRODUCT can model —
                    fell to synthesis, which had no constraint catalog and
                    answered a confident YES describing alternates, while the
                    blocker analysis on the same board correctly listed B3/B5
                    operator pools among the families it does not weigh. The
                    meaning now covers "can it handle X" as well, and the route
                    grounds every capability claim in docs/05's own verdict,
                    proof-status and doorway columns. A vocabulary-class change:
                    `Intent`, `INTENT_MEANINGS`, `ROUTE_TAXONOMY`,
                    `ROUTE_OFFERS`, the assemblers, their authored copy and this
                    bump, one commit.

    v13:            Session 4B.16 (2026-07-29) — `what-would-change` joins the
                    vocabulary and `briefing`'s meaning is WIDENED. Two items,
                    one theme: the questions a planner asks NEXT.

                    (a) THE COUNTERFACTUAL. 4B.14's `why-here` answers "what is
                    holding this here" and answers it well; the question that
                    follows it is "so what would have to be different?", and
                    that had no route. It would have fallen either to
                    `swap-move` (which weighs a board move between two orders
                    and prices it in the sandbox) or to `advice` (which is
                    about the plan, not one operation) — both of them the
                    adjacent-match failure rule 7 already names, and both of
                    them answering with something the planner could not act
                    on. `what-would-change` reports the change that would move
                    the BINDING bound, with its threshold and the arithmetic,
                    over the same computed bounds and no new ones. The two
                    MEANINGS are written as a pair, as 4B.14 wrote `why-here`
                    against `start-reason`: the boundary is diagnosis versus
                    remedy about the same operation, and it is where a new
                    vocabulary member costs something.

                    (b) THE OPENER. `briefing` meant "what should I worry about
                    today", so the other three ways a planner opens a board —
                    "how does this schedule look", "anything I should know",
                    "what's the state of things" — were shape reads that rule 7
                    correctly sends to `unmatched`, where the second tier
                    reasons out an answer the document could have testified to.
                    The route now answers the whole family from the document:
                    every item it supports, ranked by consequence, each line
                    carrying its number. A vocabulary-class change: `Intent`,
                    `INTENT_MEANINGS`, `ROUTE_TAXONOMY`, `ROUTE_OFFERS`, the
                    two assemblers, their authored copy, the predicate-coverage
                    map and this bump, one commit.

    v14:            Session 4B.27 (2026-08-01) — three MEANINGS widened, and NOT
                    ONE NEW INTENT. All three defects were the same shape: the
                    route existed, the assembler could answer, and the meaning
                    did not say enough for the parse to hand it what it needed.
                    Paying a vocabulary-class change for any of them would have
                    bought a second way to reach an answer we already had.

                    (a) `frozen` MAY BE ASKED ABOUT ONE ORDER. "ord-11 is not in
                    the frozen zone, why not?" reached the route correctly and
                    got a whole-board census — 41 committed, 345 active — with
                    the named order nowhere in it. The route declared no params
                    and the meaning named no subject, so the parse extracted
                    none. The boundary comparison is one line off a contract
                    field that was always there.

                    (b) `late-order` ALSO OWNS "TIGHT". "tight" is a word the
                    BOARD puts on a bar (within one working day of its due date,
                    not past it). "Why is this order tight" went to `why-here`,
                    which answered about placement and never used the word.
                    `late-order` already computed the arithmetic — it states the
                    slack in minutes correctly — and only lacked the name.

                    (c) `gap-between` IS SELECTED BY TWO NAMED ORDERS. "why
                    can't ord-11 start right after ord-19" went to `why-here`,
                    which has one order slot, and the second order was dropped
                    with nothing on the surface saying so. `gap-between` has
                    slots for both; the meaning now says that naming two orders
                    in a relative-timing question is what selects it.

                    Item 4's general remedy is NOT here and is deliberately not
                    a parse change: 11 of the 13 order-taking routes have no
                    second slot, and most of them genuinely answer about one
                    thing. The dispatch now DISCLOSES a subject it heard and
                    cannot weigh, at the one seam every route passes.

## Review discipline

This file is a reviewed artifact, exactly like the driver/finding vocabularies and
the authored fallback copy. It is not tuning surface.

  * A change here is a **vocabulary-class change**: reviewed, committed with the
    spec/`docs/04` update in the same commit, and `prompt_version` bumped.
  * The intent vocabulary and its one-line meanings are **not** authored here —
    they live in `mre.contracts.parse` (`Intent`, `INTENT_MEANINGS`) and are
    rendered into `{INTENTS}` below, so a route added without a meaning fails the
    parity test rather than silently becoming unreachable.
  * The model may only ever emit a member of the closed vocabulary. Anything else
    is a malformed emission: retried once, then the clarify path. Never a guess.
  * Nothing in this prompt may ask the model for an ANSWER, a fact, a number, or a
    judgment about the schedule. It names an intent and its subjects. R-AI5(8):
    the model routes to facts and voices answers; it never grades its own claims.

Placeholders substituted at call time: `{INTENTS}`, `{CONTEXT}`, `{QUESTION}`.
Everything after the `## PROMPT` marker is the prompt body; everything above it is
documentation and is never sent.

## PROMPT

You are the interpretation layer of a manufacturing production-scheduling
assistant. A production planner is talking to it about a solved schedule.

Your ONLY job is to read the planner's latest question and name what they are
ASKING FOR. You never answer, never state a fact about the schedule, never invent
an order, machine, customer, or number.

INTENT VOCABULARY (closed — you may name exactly one of these ids):
{INTENTS}

CONVERSATION CONTEXT:
{CONTEXT}

THE PLANNER'S LATEST QUESTION:
{QUESTION}

RULES

1. INTENT FIRST. Decide what the planner wants to KNOW or DO. A subject that is
   present in the question or the context (an order id, a selected bar) is a
   PARAMETER of the intent — it never picks the intent. "Is there any way I can
   get this done faster" while an order is selected is an `advice` question about
   that order; it is not an order lookup.

2. SUBJECTS ARE TYPED. List every subject the intent needs, in the order the
   planner named them, each with a `kind` of order / machine / customer / concept:
     - `raw` is the planner's own words for it ("ORD-05", "the big press",
       "order 5", "this order", "wip").
     - `from_context` is true when the planner pointed at something instead of
       naming it ("this order", "it", "that machine", or an intent that plainly
       applies to whatever is selected). The system binds it from the board
       selection, then the last answered subject, then the history — you do not
       guess which.
     - Do NOT invent a subject. If the planner named none and the intent needs
       none, return an empty list. If an intent needs one and neither the question
       nor the context supplies it, use the `clarify` field with reason
       `no-subject`.
     - A CONCEPT subject is a capability the submission can declare (splitting,
       overtime, alternates, customers, earliness, spanning downtime, WIP). It is
       never bound from the board — a capability is not something you can select.
     - THE RESOLUTION LADDER, highest first: the OPEN DELTA CARD, then the board
       selection, then the subject of the previous answer, then the history. You
       do not apply it — you only mark a subject `from_context` and the system
       binds it in that order. Knowing the order matters for one thing: when a
       delta card is open, "this" and "it" are about that move.
     - THE RECENT TURNS ARE YOURS TO READ. When the planner refers back to
       something a turn or two ago ("is there a minimum piece size" after talking
       about splitting; "show me its dates" after asking about ORD-13), NAME it
       yourself from the conversation: put the order id or the capability in `raw`
       with `from_context` false. `from_context` is for what is SELECTED on the
       board, not for what was said. Only give up when the conversation truly
       does not contain the referent.

3. AN INTENT YOU CANNOT SUPPLY THE SUBJECT FOR IS THE WRONG INTENT. Each entry in
   the vocabulary says what it needs. If the planner named a machine and the intent
   you were reaching for needs an order, pick the intent that fits what they named.
   Naming an order-shaped intent with only a machine in hand produces a dead end,
   not an answer.

4. POLARITY, where the intent carries one. `positive` = explain the property as it
   stands ("why is ORD-05 late", "why is ORD-13 running so early"). `negative` =
   explain the inverse or the absence ("why is ORD-13 NOT late", "why can't ORD-05
   start sooner", "why is nothing on CUT-01"). Otherwise null. Getting this wrong
   inverts the answer, so read the sentence, not the keywords.

5. FOLLOW-UP LINKAGE — how this question attaches to the one before it:
     `none`         self-contained.
     `deepen`       asks for more about the previous answer's subject ("but why?",
                    "and what would fix it?").
     `correction`   re-binds a referent and re-asks the PREVIOUS question ("no, I
                    meant ORD-05", "I was asking about the machine not the job").
                    Name the intent of the question being CORRECTED, and the
                    corrected subject.
     `list-expand`  asks the previous answer to enumerate ("list them", "which
                    ones", "the numbers"). Name the PREVIOUS answer's intent.
     `menu-select`  names an item from a menu the previous answer listed ("what
                    about wip" right after a list of capabilities). Name the
                    intent that menu belongs to (usually `coaching`) and the item
                    as a concept subject. An ORDINAL ("the second one") is NOT a
                    selection — the menu order is not a contract: clarify with
                    reason `ambiguous-subject`.
     `confirm-take` the planner is repeating the assistant's OWN prior suggestion
                    back as a question to confirm it ("so move the first operation
                    to an earlier start time?"). This is a confirmation, not a new
                    instruction.
     `prove-it`     the planner asks for the GROUNDS of something the assistant
                    just said: "prove it", "how do you know that?", "how do you
                    know?", "says who?", "which record says that?", "where does
                    that come from?", "show me where that comes from", "on what
                    basis?", "back that up". What they want back is the EVIDENCE,
                    and the system has a grounding pass that gives it to them —
                    so this is always the right read for that family.
                    NOT "but why" / "why is that" / "and why does that happen".
                    Those ask for a deeper CAUSE IN THE PLANT and are `deepen`:
                    the planner accepts what you said and wants the next link in
                    the chain. `prove-it` asks where your SENTENCE came from, not
                    why the world is the way you described it. If the question
                    would still make sense asked of the schedule itself rather
                    than of you, it is not `prove-it`.
                    Two neighbours it is NOT. `contested-fact`: the planner
                    asserts a DIFFERENT status of the plan and wants the evidence
                    for it ("isn't ORD-05 on time?") — that is about the schedule,
                    not about your sentence. The `verification` clarify: the
                    planner wants a YES/NO on whether you were right ("are you
                    sure?", "is that correct?") and the honest answer is that the
                    assistant does not vouch for its own claims. The line between
                    them is what comes back: the GROUNDS -> `prove-it`; a verdict
                    on the assistant -> `verification`.

6. CLARIFY INSTEAD OF GUESSING. Set `clarify` (and still give your best `intent`)
   when you cannot commit. Never set it together with intent `unmatched` — an
   unmatched question is already answered honestly, and asking the planner to
   disambiguate something you have no route for is a dead end. `detail` is at most
   a short phrase: for `set-reference` it is the referring words themselves ("10 of
   those"), otherwise a few words. Never a paragraph, never an explanation of your
   reasoning. Reasons:
     `no-subject`         the intent needs a subject and nothing supplies one.
     `ambiguous-subject`  two or more referents fit and nothing decides between
                          them (including a menu ordinal).
     `set-reference`      the referent is a GROUP, not one entity ("10 of those",
                          "how many of them are critical").
     `verification`       the planner asks you to VOUCH for your own previous
                          claim — a yes/no on whether you were right ("is that
                          correct?", "are you sure?"). If instead they are asking
                          HOW you know or WHERE it came from, that is not a
                          clarify at all: it is `followup_of: prove-it`.
     `ambiguous-intent`   two intents fit equally and the difference matters.

7. UNMATCHED IS AN ANSWER, NOT A REFUSAL. This is the rule most worth getting
   right. An `unmatched` question is NOT turned away: the system answers it by
   reasoning over the schedule's evidence directly and labelling what it proved
   against what it inferred. So `unmatched` costs the planner nothing, while
   stretching their question into a nearby route answers something they did not
   ask — with perfect citations, which makes it worse, not better.

   Use `unmatched` whenever the question is about the plan but no id above IS the
   question. Aggregates and shape reads ("which machine is the bottleneck", "is
   the work spread evenly", "whats the busiest day", "is there anything unusual
   about this schedule"), comparisons between two things, cause questions across
   the whole plan ("whats driving the lateness"), money questions beyond a single
   edit ("where is the money going"), and hypotheticals about the PLANT or the
   plan ("what if we hired a shift", "make it cheaper") are all `unmatched`. Put
   the closest one or two ids in `nearest` anyway — they are used if the reasoning
   tier is unavailable.

   Two exceptions worth knowing, because both are contracted now. A hypothetical
   about ONE OPERATION'S PLACEMENT ("what if it were splittable", "what would it
   take to get this earlier") is `what-would-change`. A question about the
   SOLVER'S PROOF ("is this optimal", "did it finish") is `solve-optimality`.

   The contracted routes are for the question they NAME, not for the neighbourhood
   they sit in. `late-orders` lists which orders are late or counts them; it is not
   the answer to "why are so many late" — that is `lateness-cause`, its own intent.
   `briefing` is the whole-board read a planner opens with; it is not the answer to
   a SHAPE question about the plan ("is this plan front-loaded", "is the work
   spread evenly" — those are `unmatched`). `inventory` counts things. When in
   doubt between a route and `unmatched`, choose `unmatched`.

8. CONFIDENCE is your own read of the intent match, 0.0 to 1.0. Be honest: below
   about 0.45 the system will treat the parse as unmatched rather than answer.

8b. A DELTA CARD ON SCREEN IS PART OF THE QUESTION. When the context block says a
   priced move is showing, a question about "this move", "these orders", "the
   delta", "what else moved", "what does this cost" or "is it worth it" is
   `open-card` — the system reads the card back to them. It is NOT `swap-move`
   (that weighs a move the planner has not made yet), NOT `edit-cost` (that is
   about an edit already accepted), and NOT a plan-wide question.

   The card must be OPEN. When the context block says "none", the same words are
   about the plan and you pick the intent that fits them; naming `open-card` with
   no card open buys the planner nothing but a sentence saying so.

9. REPORT A QUALIFIER THE INTENT DROPS. Sometimes the nearest intent really is the
   nearest one, and it still cannot honour something the planner SAID. Put those
   words — just the words — in `dropped_qualifier`. Leave it "" when the intent
   covers the whole question, which is the normal case.

   What counts, and only these three:
     - A TIME SCOPE the intent does not take. "how many orders will be late NEXT
       MONTH" is `late-orders`, and `late-orders` answers about THIS plan.
       -> dropped_qualifier: "next month"
     - AN "ACTUALLY" / "REALLY" that asks for the complement or the true figure
       rather than the one the intent reports. "how much of CUT-01's week is
       ACTUALLY working time" is nearest `downtime`, and `downtime` reports the
       closures, not the working time.
       -> dropped_qualifier: "actually working time"
     - A COMPARATIVE the intent cannot make. "is CUT-01 busier than PRESS-01" is
       nearest `machine-schedule`, which describes ONE machine.
       -> dropped_qualifier: "busier than PRESS-01"

   What does NOT count — be strict, because a false report costs the planner a
   proven answer and gives them a reasoned one instead:
     - A subject the intent takes. "why is ORD-05 late" -> "" (the order is a
       parameter, not a dropped qualifier).
     - A scope the intent DOES honour. "what's running on CUT-01 tomorrow" -> "":
       `machine-schedule` reads the question's own date filter.
     - Politeness, urgency, or framing ("quickly", "I need to know", "can you").
     - Your own uncertainty. If you are unsure of the INTENT, that is what
       `confidence` and `unmatched` are for.

   You report; you do not decide. The system reads this field and may send the
   question to the reasoning tier instead of the route — that is its call, not
   yours.

10. WHEN THE PLANNER DISAGREES, SAY WHAT WITH. `contested-fact` covers every turn
   that DISPUTES something the assistant just said, and the system must know which
   claim is under challenge or it will answer an adjacent question and sound like
   it agreed. Set `contested_claim`:

     - `lateness` — a STATUS is disputed. "isn't ORD-05 on time?", "I thought that
       one was fine", "you said it was late".
     - `timing` — the assistant's account of WHEN or WHY something is placed is
       disputed. "it seems it should be able to start on tuesday after op10
       finishes", "but the machine was free all afternoon", "that can't be right,
       nothing was running then", "surely it could go earlier than that".
     - `other` — a dispute that is neither. The system will say it cannot evaluate
       the challenge, which is the honest answer; do not stretch it into one of
       the two above to make it answerable.

   Set it on `why-here` too, not only on `contested-fact`. A challenge to the
   system's reasoning very often names the right route by itself — "it seems it
   should be able to start on tuesday after op10 finishes" IS a blocker question
   — and the answer still needs to know it is answering a PUSH-BACK rather than
   a fresh question, so it can say plainly where the planner is right.

   Leave it null on every other intent. A turn that merely ASKS about lateness or
   timing is not a contest — this field needs the planner to be pushing back on
   something already said.

OUTPUT — strict JSON, no prose, no code fence. `intent` must be one of the
vocabulary ids listed at the top; the follow-up names (`deepen`, `list-expand`,
`menu-select`, `correction`) are values for `followup_of`, never intents.
(`confirm-take` and `prove-it` are members of BOTH vocabularies: when one of those
is what the planner is doing, name it in both fields.)

{
  "intent": "<one id from the vocabulary>",
  "subjects": [{"kind": "order|machine|customer|concept",
                "raw": "<the planner's words>",
                "from_context": true|false}],
  "polarity": "positive" | "negative" | null,
  "followup_of": "none|deepen|correction|list-expand|menu-select|confirm-take|prove-it",
  "confidence": 0.0,
  "nearest": ["<id>", "<id>"],
  "dropped_qualifier": "",
  "contested_claim": null | "lateness" | "timing" | "other",
  "clarify": null | {"reason": "no-subject|ambiguous-subject|set-reference|verification|ambiguous-intent",
                     "detail": "<a short phrase, never a sentence>"}
}

# Session 4A — teaching graft (b): the depth licence and the teaching intent

**2026-08-04.** R1 item 2, session (b) of four (docs/07 §5b). docs/07 v2.89,
§5a.165-169. docs/04 2026-08-04 **R-TG2, R-TG3 and R-TG4 ruled and BUILT**.
Contract unchanged **1.15**; no docs/06 doorway owed; both answered on the
record. Parse prompt **v17 → v18**; synthesis prompt **v6 → v7**. RUBRIC gains
axis **C8 ANSWER SHAPE**. Minted nothing. Cockpit untouched, not re-run.

---

## 1. The finding, stated plainly

**The product's answers are true, grounded, correctly routed and correctly
classed, and some of them are still unusable.** Session (a) closed the last gap
C1–C7 could see. This session's three measurements are all about a gap none of
them can:

**THE BOSS QUESTION, on the demo board, at HEAD.** Asked *"there are a lot of
orders late what reason can i give my boss and what will help lessen the
impact"*, the product returned **134 content lines** — a three-line cause mix,
**~95 hold-pair lines** (*"ORD-000002 was held on CUT-02 until 2026-01-09 12:51
by ORD-000248, and started at 2026-01-09 12:51"*, ninety-five times), the
unattributed list, the money, and then `Evidence chain (614 record(s)):` followed
by fifty rendered records. It is the longest answer in every committed sweep by a
factor of three and a half over the next one.

**Every line of it is true.** Every figure is grounded, the route is right, every
claim is in the right class. The planner asked for a sentence they could say to a
person and a lever they could pull. **The goal was audience-shaped and the answer
was completeness-shaped.**

**TEN DOMAIN PROBES, LIVE PARSE, PROMPT v17:** `coaching` 5 / `unmatched` 4 /
`lateness-cause` 1. Half of the questions asking to be taught something reached
`coaching`, whose meaning is *what this product can model* and whose answer is a
docs/05 lookup — measured across 102 turns at a **median of 3 content lines,
maximum 3**. *"How does a rolling horizon normally work"* got three lines about
what a submission can declare.

**86 SYNTHESIS ANSWERS across all nine committed sweeps.** Kept claims, excluding
the 25 floor answers that kept none: 2→7, 3→13, **4→18, 5→19**, 6→4. Synthesis
prompt rule 6 has asked for "three to six claims" since v1, and 38% of real
answers sit at the top of that range. The exhortation is followed loosely and
bounds nothing — 4A.y's 0-of-5 shape, one layer over.

## 2. The census tables

**(a) ROUTING AT HEAD** (`tools/spikes/teaching_graft_b/census_routing.py`,
24 probes, live parse, `rolling-db5395dc-2ae`, prompt v17):

| family | n | where it went |
| --- | --- | --- |
| T teaching | 10 | `coaching` 5 · `unmatched` 4 · `lateness-cause` 1 |
| M mixed (board + teaching) | 4 | `unmatched` 3 · `late-order` 1 |
| B board (control) | 6 | six different contracted routes, correct |
| G goal (names a person) | 4 | `advice` 2 · `lateness-cause` 1 · `briefing` 1 |

**G REACHES THREE ROUTES.** That single row is why R-TG4 attaches to the QUESTION
FAMILY and not to a route: a rule wired to `lateness-cause`, where the founder's
question landed, would have covered one third of its own family and looked
finished. 4A.y's Item 1, paid forward rather than repeated.

**(b) LENGTH** (`census_lengths.py`, 1,567 turns, nine sweeps):

| register | n | min | p25 | med | p75 | p90 | max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| testimony | 1411 | 1 | 1 | **3** | **5** | 8 | **134** |
| synthesis | 98 | 1 | 4 | **5** | 6 | 6 | 10 |
| judgment | 37 | 2 | 2 | 3 | 4 | 4 | 4 |
| remediation | 21 | 2 | 2 | 2 | 3 | 3 | 4 |

In CHARACTERS the picture inverts: synthesis median **656** against testimony's
**282**, p90 1320 against 600. **Synthesis answers are fewer lines and much
longer ones** — which is exactly the thing the demo verdict was about, and it is
why the cap is stated in claims and its character consequence is named as a limit
rather than claimed as a fix (§5(g)).

**SHORT = 4 is chosen from this**: it is the median real synthesis answer, so it
leaves the median untouched, binds on the upper 38%, and lands a capped answer at
~5 content lines — testimony's own p75, the band that was praised in the demo the
same week synthesis length was not.

**(c) MARKERS** (same 24 probes, the SHIPPED predicates):

| marker set | T (10) | M (4) | B (6) | G (4) |
| --- | --- | --- | --- | --- |
| teaching union (`in general`/`explain`/`what is a`/`why do <plural>`) | **8** | **4** | 0 | 0 |
| `audience` (the shipped `names_an_audience`) | 0 | 0 | 0 | **3** |
| board entity named | 0 | 2 | 3 | 1 |

**FALSE-POSITIVE RISK.** The teaching union is 0/10 across board and goal probes
and the audience marker is 0/20 across everything that is not a goal question.
Both are SPECIFIC and neither is fully sensitive, and that asymmetry is chosen: a
missed marker leaves an answer exactly as it is today, and a false one reshapes
an answer nobody asked to have reshaped.

**AND THE TEACHING MARKERS ARE NOT WIRED TO ANYTHING.** That is the ruling, not
an omission — see §3.

## 3. R-TG2: teaching is a second-tier intent, not a route

`teaching` joins the closed vocabulary. It is NOT in `ROUTE_TAXONOMY`: there is
no contracted evidence assembly for *"how does this normally work"*, and
inventing one would author domain prose as **testimony**, which is R-TG1's defect
one layer up — there the label was a marker, here it would be the register
itself.

So it joins `contracts.parse.SECOND_TIER_INTENTS`, and **the set is a NAME for
something that already existed**: `unmatched` was always a declared door to the
tier, and the parity test subtracted it with a comment where a name should have
been. A companion guard asserts that no member has a taxonomy entry, because a
route reachable two ways would answer differently in each.

**THE MARKERS DO NOT ROUTE.** The census makes them tempting — 8/10 sensitivity
with zero false positives on 16 non-teaching probes. Wiring them would be the
deterministic classifier R-AI5(2) deleted, returning under a new name. **The seam
may refuse a proposal; it may not manufacture one.** That is session (a)'s
sentence at the routing layer, and it means the five `coaching` landings are
fixed by the PROMPT or not at all — visibly, measurably, with the failure in a
transcript rather than papered over by a keyword.

**LIVE AFTER v18: 5 of 5**, at conf 0.95–0.98, including both probes v17 sent to
`coaching`. Both `coaching` controls stayed on `coaching`.

## 4. R-TG3: the depth licence, and the A/B that shows who is doing the work

LONG = 8 claims for `teaching` and nothing else; SHORT = 4 for everything else
that reaches the tier. The bound lives at the **dispatch seam**, after the model
drafts and after the verifier labels, so nothing in it can change what a claim
IS — only how many reach the page.

**THE HONEST HALF IS THE DISCLOSURE.** A deferred claim is not a cut claim: a cut
one failed verification, a deferred one PASSED and is surplus to the budget. One
word over both would be this repo's sixth measured category fusion. The count
reaches the page and the rest is offered. **And the negative is its own clause:
the closer is ABSENT when nothing was withheld**, because a closer on an uncut
answer is a false statement about our own process.

**THE A/B IS THE MEASUREMENT THAT MATTERS**
(`tools/spikes/teaching_graft_b/cap_ab.py`; same probes, rule 6 swapped back to
its v6 text and nothing else changed; the governed prompt restored and asserted
byte-identical by sha256):

| arm | kept claims | deferred | closers |
| --- | --- | --- | --- |
| **v7 (shipped)** | 4, 4, 3 | 0, 0, 0 | **0** |
| **v6 (control)** | 4, 4, 5 | **2, 4, 0** | **2** |

**The prompt is doing the work and the seam is the floor under it.** That is the
architecture R-TG3 asks for, and it is exactly why the shipped arm has no live
closer specimen — reported in §5(c) rather than hidden. The third pair is the
licence in one row: that probe (*"why might tardiness cluster on bottleneck
machines"*) parses to `teaching`, so its five claims sit inside the LONG budget
and are correctly untrimmed on **both** arms.

The control arm's closer, verbatim: *"I've kept this short — there are 4 more
points behind it. Ask and I'll walk through the rest."*

## 5. R-TG4 live: 134 lines becomes 8

**THE BOSS QUESTION, AFTER, VERBATIM** (demo board, `route=lateness-cause`):

> You asked what to say to my boss. Here is the one-sentence version, and the one
> thing that would move it most.
>
> 102 of the 158 orders scheduled in this window finish after their due date. For
> 58 of them the recorded driver is the same one: the machine was busy with other
> work.
>
> The single biggest lever this board evidences:
>   ORD-000091 carries the largest tardiness cost on the board at $147,776.67 —
>   more than any other single order.
>   It was held on CUT-02 until 2026-01-08 08:57 by ORD-000219; that is the
>   specific hold to attack if you want this number down.
>
> The order-by-order breakdown is behind this — 99 orders with a concrete hold
> recorded, plus the full evidence chain. Ask for it and I'll lay it out.
>
> Note: the cost figures above are not proven optimal — the solver ran out of
> budget with a gap of 89.6% still open…

**THE COST-PROOF RIDER STILL FIRES** (4B.11), which is right: the answer states
money on an unproved board, and shortening an answer must not shorten its
honesty.

**THE EVIDENCE IS SUPPRESSED, NOT CLEARED.** `ordered_records` is untouched — 614
records, 460 lit bars — so the same bars light, the same refs are cited, and a
*"show me the evidence"* opens exactly the records the offer just offered. What
changed is ORDER and BUDGET.

**A TEACHING ANSWER AT FULL DEPTH**, same board, three labeled general claims and
the invitation:

> Scheduling problems resist proof of optimality mainly because the search space
> … `[general knowledge — how scheduling works in general, not a fact about this
> plan]`
> …
> That is how it works in general — you know this plant and I don't, so if any of
> it doesn't match what you see here, say so and I'll look at what your board
> actually does.

**THE PARSE REPORTS `audience`, AND THE FLOOR IS REDUNDANT TODAY.** Eight probes
at v18: the model reports the field on **4 of 4** goal questions and **0 of 4**
others, every value string-identical to what the floor computes — *"my boss"*,
*"the customer"*, *"the production meeting"*, *"my manager"*. 4A.y measured a
freshly-prompted field reported 0 times in 5; this one is followed. The floor
stays, because a floor is for the day the model changes, and it is recorded as
having caught nothing rather than as the thing doing the work.

**AN UNCUT SHORT ANSWER WITHOUT THE CLOSER**: every one of the eight synthesis
answers in the v2 sweep and all four v7-arm probes — `deferred=0`, no closer,
graded `g_no_false` **8/8**.

## 6. The bank and the guards

`tests/ai_exam/banks/sweep_teaching_v2.txt` — 19 turns, demo board, graded by
`tools/spikes/teaching_graft_b/grade_depth_sweep.py`:

| | |
| --- | --- |
| routing expectations | **15/15** |
| (e) LONG — a teaching answer is uncapped and invites push-back | **12/12** |
| (f) SHORT — every other tier answer inside the cap, closer correct where it bound | **3/3** |
| (g) NO FALSE — the closer absent wherever nothing was withheld | **9/9** |
| (h) AUDIENCE — account, lever, offer; no chain, no hold list | **9/10** (§7(b)) |
| (i) UNTOUCHED — no testimony answer renders cap machinery | **10/10** |

**THE SWEEP WAS RUN TWICE AND THE COMMITTED ONE IS THE SECOND**, against the
frozen tree after the three defects §7(f) records were fixed — 4B.34's
stale-`dist` lesson, which is that evidence taken before the last fix is
evidence about a build nobody shipped. The first run is what §7(e) reports.

**39 guard functions (49 test cases)** in `tests/test_depth_licence.py`,
written from the rulings.
**13 negative controls proven RED** against physically reverted code
(`tools/spikes/teaching_graft_b/negative_controls.py`), every restore
byte-identical by sha256. **One of them is pointed at a real pointer rather than
past it** (4B.28 §5a.123): the closer control reverts the RENDERER's condition,
not the seam's, because a control calling `answer_budget.apply` directly would
stay green against a renderer that had stopped reading `deferred`.

**TWO PRE-EXISTING TESTS WERE UPDATED BECAUSE THEY STATE THE OLD BEHAVIOUR AND
THE UPDATE IS THE RULING** — both are the parity assertion
(`test_parse_contract.py` and `test_interpreter.py`), and in both the change is
from a bare `unmatched` subtraction to the named `SECOND_TIER_INTENTS`, which is
the vocabulary change itself. A THIRD file changed for a different reason: the
exam runner's sweep totals now carry `deferred` beside `failed_and_cut`, never
folded into it, because a sweep reporting them together would say the tier could
not ground what it simply did not print.

## 7. Carry-forwards (REPORTED, deliberately NOT fixed)

**(a) THE `briefing` ACCOUNT IS THE TOP-RANKED WORRY, AND ON THIS BOARD IT IS THE
WRONG SENTENCE TO SAY IN A ROOM.** Measured live: *"what do i say in the
production meeting tomorrow about the late orders"* leads with **"The cost
optimum is NOT proved — the solver stopped with a gap of 89.6% still open."**
True, ranked #1 by consequence, and not what anybody opens a production meeting
with. **R-TG4 deliberately does not re-rank**: picking a different opener item
because the planner said "late orders" is a relevance classifier reading the
question text, and no amount of usefulness makes that legal here. So it is a
finding about the OPENER's ranking, and it is the sharpest thing this session
leaves standing.

**(b) A GOAL QUESTION ABOUT ONE ORDER CLARIFIES.** *"what should i tell the
customer about ORD-000091"* parses `order-attributes` at 0.72 with
`clarify=ambiguous-intent` and answers *"I can read that two ways… the facts as
they stand, or what to do about them."* The shape never runs — correctly, since
a clarify assembles no facts to compose from — and unhelpfully, since a person
who has to speak to a customer wants both. The graded miss is **kept** at 9/10
rather than fitted away; re-deciding a clarify is a routing change this session
did not open.

**(c) THE SHIPPED ARM HAS NO LIVE CLOSER SPECIMEN.** §4's A/B is why. The
mechanism is proven by 45 guards and 13 negative controls and observed in the
wild only on the v6 control arm. This is the honest form of session (a)'s
carry-forward (b), and a later session should re-measure rather than assume the
cap is exercised.

**(d) TWO SURFACES NOW RANK "the biggest lever" ON DIFFERENT AXES.**
`lateness-cause` ranks on MONEY (the largest tardiness line); `advice` ranks on
MINUTES, via `_advice_take`'s worst slip. Both self-describe in their own copy
and neither is wrong, but "the single biggest lever" now means two things one
route apart. A session should rule on whether one axis wins.

**(e) THE FIRST SWEEP RUN LOST A TURN TO AN OUTAGE, AND IT DID NOT REPRODUCE.**
*"is the work spread evenly across the machines"* came back `route=OUTAGE`,
`register=system` — the provider was unreachable for that one call, R-OF1's
floor did exactly its job, and the routing grade read 14/15 for an
infrastructure reason rather than a routing one. On the committed re-run it
answers normally and the grade is 15/15. Recorded because a transient that is
not written down is a transient the next session re-diagnoses.

**(f) THE `advice` AUDIENCE SHAPE PUT THE ACCOUNT'S DETAIL UNDER THE LEVER'S
HEADER — FOUND LIVE, FIXED IN THE SAME COMMIT.** With the take promoted to lever,
the opener item's own detail line (*"against a ledger of 1,667,467.80, that bound
leaves up to 1,494,205.31 on the table"*) rendered directly beneath *"the single
biggest lever this board evidences"*, beside a sentence about ORD-000112 — two
true lines under one header, and the header was wrong about the second.
`account_detail` and `lever_detail` are now separate fields. Recorded because the
only way to find it was to run the fixed code against a real board and read the
output, which is (a) §7's lesson at a second site.

**(g) A SYNTHESIS CLAIM IS TRUNCATED AT 600 CHARACTERS MID-SENTENCE**
(`_coerce_claims`), seen live on a comparison answer whose final claim ends
*"…than"*. Pre-existing, unrelated to the budget, recorded because it was seen.

**(h) THE CAP COUNTS CLAIMS, NOT CHARACTERS.** Synthesis lines run ~130 chars
against testimony's ~94, so four claims is ~520 characters against testimony's
median of 282. The budget governs HOW MANY things are said, not how long each is.
The character distribution is in `census_lengths.json` for a session that wants
to rule on the other axis.

**(i) OUT OF SCOPE AND UNTOUCHED, PER THE BRIEF:** the "did the planner's model
improve" exam axis, the fenced specimen world and the direction-(i) live-specimen
hunt (session c); multi-turn grounding and answer-memory pedagogy (session d);
`_sample_note`'s board-claim defect (R1 item 3); the epistemic-position fourth
class (session (a) carry (a)).

## 8. What the summary would undersell

**THE HARDEST DECISION IN THIS SESSION WAS TO BUILD LESS THAN THE CENSUS
INVITED.** The teaching markers score 8/10 with zero false positives across 16
probes. Wiring them would have taken the routing from 5/5 to something arguably
better and would have been a deterministic classifier — the thing this codebase
deleted twice and wrote a hard rule about. The same call recurs in R-TG4: the
`briefing` account is measurably the wrong sentence for a production meeting, and
fixing it means reading the question's words to pick an opener item. **Both were
refused, and both refusals are why the failures in §7 are visible.** A product
that quietly patches its measurements stops being able to measure.

**THE LEVER WAS ALREADY COMPUTED, AND THAT IS THE SHAPE OF THE WHOLE ITEM.**
`_advice_take` has produced *"ORD-000112's 27060-minute slip traces to
ORD-000252 holding CUT-01 until 2026-01-27 19:00 — pulling that earlier is the
single biggest lever the board gives you today"* for sessions. It was the twelfth
line of a twelve-line answer. Nothing was missing from this product except an
opinion about what to say first.

**THE A/B IS THE RESULT I DID NOT EXPECT.** The plan was: prompt asks, seam
enforces, and the seam catches what the prompt misses. What the measurement shows
is that the prompt catches essentially all of it and the seam caught none — on
this board, with these probes, with this model. That does not make the seam
theatre; it makes it a floor, and floors are for the day the model changes. But
it does mean the honest report of this session is *the words did the work*, not
*the mechanism did the work*, and saying otherwise would be exactly the
mechanism-shaped self-flattery this repo keeps catching.

## 9. Numbers

- **Python: 2631 passed / 291 skipped / 0 failed** (1399s), against the session
  (a) baseline of **2581/291/0** — **+50**. The delta is the new guard file plus
  the second-tier parity guard; no skip moved.
- **FILLED IN SESSION (c), AND IT DOES NOT MATCH THE NUMBER THIS SESSION'S
  CLAUDE.md STATUS LINE CARRIES.** That line reads **2629/291/0 (+48)**; the
  measurement above was taken by session (c) against this session's tree with
  nothing of its own added yet (`python -m pytest -q`, collection at the frozen
  bytes), and it reads **2631 (+50)**. Two tests' difference, unexplained, and
  recorded here rather than reconciled by picking one — a count that moved
  between two runs of the same tree is a fact about the harness worth keeping,
  and the SUITE_LINE placeholder existed precisely because no figure had been
  taken against frozen bytes when the close-out was written. Session (c)
  measures its own delta from **2631**.
- **TWO EARLIER FULL RUNS EACH REPORTED A FAILURE AND NEITHER WAS REAL, WHICH IS
  WORTH RECORDING RATHER THAN GLOSSING.** `test_relevance_guard.py::
  test_both_renderers_apply_the_floor_or_neither_does` reads its subject with
  `inspect.getsource`, which resolves line numbers against a `linecache` read of
  the file on disk — so a run whose source changes under it compares old line
  numbers to new bytes and reports a fragment of a different function. It passes
  in isolation and at the frozen tree. `test_corpus.py::TestCurrency::
  test_index_matches_the_live_docs` was REAL and is fixed: docs/04 was amended
  after the index build, so the index was rebuilt again. The lesson is the
  cheap one — **do not read a full-suite result taken while the tree was still
  moving**, and the final figure above is from a run against frozen bytes.
- **Cockpit: UNTOUCHED, NOT RE-RUN.** No `src/cockpit/` file changed.
- **13 negative controls proven RED**; every restore byte-identical by sha256.
- **Sweep:** 19 turns, 9 synthesis answers, 24 general-knowledge claims, 3
  verified, 10 interpretive, 8 cut, **0 deferred**. Committed at
  `tests/ai_exam/sweeps/2026-08-04-teaching-v2/`, with the A/B and the live
  probes beside it.
- **Minted nothing.** No new run, no new schedule, no new board.
- Governed artifacts: parse prompt **v18**, synthesis prompt **v7**, corpus index
  rebuilt (docs/04 amended).

# Session 4A teaching-graft (e2) — the measurement errand

**2026-08-05.** R-TG7 ruled and BUILT, plus the founder's W4 lead-order
arbitration. Contract unchanged **1.15**; no docs/06 doorway owed.
**Both governed prompts unchanged — parse v18, synthesis v9** — this errand
being authored copy and deterministic seams throughout. `DriverCode` unchanged.

A small session with a strict rule: **four measurements before anything is
built, and everything conditional is conditioned on a number taken this session
rather than on judgment.** Two of the four changed what got built.

---

## 1. M1 — the run-1 GK label. Verdict: **(b), defect confirmed**

The (e) close-out §4 quotes, as proof R-TG6 worked, the first claim of run 1:

> *"A job becomes impossible to move for one of a small number of specific
> reasons **this product actually computes**, not just a lock: it can be
> explicitly frozen or pinned to a resource, it can be excluded from resources
> it would need, or it can be boxed in by its own precedence chain, release
> date, or calendar with no later opening long enough to hold it."*
> `[general knowledge]`

**The artifact.** The live JSON did not outlive (e)'s session — the run was
scratch and the (e) commit carries only `negative_controls.py` in its spike
directory. The surviving record is the close-out's own §4 block, and it is
sufficient for both halves of M1.

**Was it cited? No, and the label proves it.** `gk_disqualifiers`' FIRST clause
disqualifies any claim carrying record ids from the general-knowledge class
("it cites this run's records"). A sentence that rendered under
`[general knowledge]` therefore cannot have been cited — and the *second* claim
of the same answer rendered under `[record: 6af3d3e4…]`, so the label is not an
artifact of the quotation.

**Did `product_behavior_disqualifiers` fire? No**, and
`tools/spikes/teaching_graft_e2/m1_predicate_check.py` shows why, per pattern:

| pattern | result |
|---|---|
| (a) it states what this product does | miss |
| (b) it cites this product's constraint catalog | miss |
| (c) it names this product's declared schema | miss |

It missed **twice over**. Pattern (a)'s second alternation requires
`th(is|e) (product|system|engine|scheduler)` followed *immediately* by a verb
from a closed list — and "computes" is not in the list, and "actually" sits
between the noun and the verb. The first alternation wants a preposition before
"this product"; here the preceding word is "reasons".

### Being true is not the discriminator

The temptation is to say the sentence is fine because it is correct. Both of
(e)'s own 2-of-99 census specimens were correct too, and the close-out says so:
*"Both are TRUE. Both are unlabelled-as-what-they-are."* R-TG6 (i)'s subject is
the LABEL. `[general knowledge]` means *there is nothing here to check this
against*, and for a sentence enumerating what this product computes there always
is — the docs/05 catalog, and the mobility floor's own verdict vocabulary.

**This is §5(a) of the (e) close-out, one clause on.** There, the (iii) map
missed its own fix's first live output. Here, the (i) predicate misses the
answer the close-out printed as its headline success. Both were found the same
way: by running the thing over its own artifacts instead of reasoning about it.

---

## 2. M4 — the W4 surface inventory. **The "two sites" claim did not hold**

(e) §2(d): *"Two, both in `renderers.py`, both rendering from the same `chose`
verdict … Both are fixed."* M4 was specified to verify that, and it was verified
by census rather than by re-reading — an AST walk over every function in
`renderers.py` that renders a "nothing prevented it / not prevented / nothing
was holding / was not forced / nothing has to change" assertion, cross-checked
against whether the function is guarded by `counterfactual_contradicts_driver`
(`tools/spikes/teaching_graft_e2/m4_w4_site_census.py`).

**Six hits. Two are docstrings.** One is the guard's own docstring; one is
`_challenge_lead`'s. Of the four real emitters:

| site | guarded at (e) HEAD | renders a driver line |
|---|---|---|
| `_render_why_here` (`chose` branch) | yes | yes |
| `_mobility_correction` (the lead) | yes | yes |
| **`_render_counterfactual`** | **NO** | **yes** |
| `mobility_lead_line` (earlier-open) | no | no |

**THE THIRD SITE IS THE IDENTICAL DEFECT ON A DIFFERENT ROUTE, AND IT WAS
LIVE.** `what-would-change` said:

> *"Nothing has to change for X op10 to start earlier: … **It was not prevented
> from going earlier — the solver preferred this placement.**"*
> *"The assignment decision records its driver as CAPACITY_BLOCKED."*

One line apart. This is 4B.14 §5a.34's rule arriving again — *a defect class
fixed at one seam is not fixed* — and it is exactly why M4 was written as a
census. It is guarded now, through the same one definition, in the arbitrated
order.

**THE FOURTH SITE IS NAMED AND NOT FIXED.** `mobility_lead_line`'s earlier-open
branch asserts *"Nothing was holding {name} back"* and **has no driver in
hand**: `_mobility_facts` returns fifteen keys and none of them is a driver.
Guarding it means plumbing the assignment decision's driver into the
mobility-lead payload, which is a change to what the floor computes rather than
to how a renderer orders two paragraphs — outside this errand's arbitrated
scope. It is pinned by a test that **fails the day the payload gains a driver**,
so the next session finds it rather than rediscovering it.

Note the shape of this one: it makes the wrong-leaning assertion and never
prints the contradicting record beside it. Less visibly wrong than the specimen
W4 was built for — and, for that reason, with nothing on screen for a planner to
notice.

---

## 3. M2 — the v9 prompt, re-swept live. (e) §8(g) discharged

Both teaching sweeps, current bank versions, against the demo board
`rolling-c32a6140-b6b`.

**`sweep_teaching_v3` (C9 transfer, 16 turns):**

| | (c2), committed | (e2), v9 |
|---|---|---|
| routing | 8/8 | **8/8** |
| m1_principle | 4/4 | **4/4** |
| m2_attached | 4/4 | **4/4** |
| m3_real_door | 4/4 | **4/4** |
| m4_pair_valid | 4/4 | **4/4** |
| m5_attempt | 4/4 | **4/4** |
| controls | 2/2 | **2/2** |

`problems: []`. Hunt A (direction (i) refusals) **0**, Hunt B (closer firings)
**0**, teaching turns with no board claim **0** — unchanged on all three, so the
closer still has no live specimen under any prompt this repo has shipped.

**`sweep_teaching_v2` (session (b)'s depth families, 19 turns):**

| family | (b) | (c2) | (e2), v9 |
|---|---|---|---|
| routing | 15/15 | 15/15 | **15/15** |
| e_long | 12/12 | 12/12 | **12/12** |
| f_short | 3/3 | 3/3 | **3/3** |
| g_no_false | 9/9 | 9/9 | **9/9** |
| h_audience | 9/10 | 9/10 | **9/10** |
| i_untouched | 10/10 | 10/10 | **10/10** |

**Identical, including the miss** — byte-for-byte the same single problem line,
`[h_audience] line 130: no audience lead — CLARIFY`, the specimen (b) kept
deliberately rather than fitting away. Three sessions of prompt change have now
moved this table not at all.

### The three fractions, over **14 teaching answers**

| | |
|---|---|
| (i) empty-collapse turns | **0 / 14** |
| (ii) product-naming GK sentences | **0 / 14** (0 of 14 GK claims) |
| (iii) `SYNTHESIS_FLOOR_REFUTED` rendered | **0 / 14** |

A teaching turn is identified from the **parse intent the transcript records**,
never from the question's wording — re-deciding it here would be a second
classifier disagreeing with the first.

**(ii) = 0 IS WHAT DECIDED F1's SCOPE.** M2 surfaced no new construction, so the
widening lands on M1's alone. It also says the M1 species is genuinely rare in
the wild, which matches (e)'s 2-of-99.

---

## 4. M3 — the (ii) floor read at demo density. (e) §8(d) discharged

`Explainer.order_mobility_verdicts`, three repetitions, quiet machine
(`tools/spikes/teaching_graft_e2/m3_floor_read_cost.py`):

| | single order | capped worst case (3, the R-TG6 cap) |
|---|---|---|
| fenced world (9 orders, 3 machines) | 12.7 ms median | **22.9 ms** median, spread 4.6 |
| demo board (386 bars) | 287.3 ms median | **295.6 ms** median (244.0–306.6), spread 62.6 |

Against a synthesis median of **24,615 ms** measured in this session's own sweep
on that same board, the capped worst case is **~1.2%** of the answer it rides
on — and it is paid only on a claim that BOTH asserts free mobility AND names an
order this run knows, so most teaching answers pay nothing at all.

**Under the 2 s threshold, so no docket line is filed, and NOTHING WAS
OPTIMIZED.** M3 measures; the docket decides. (A first pass taken while a sweep
was running gave 246.8 ms median with a much worse first-call spread; the table
above is the clean re-run, and the contended figures are recorded here rather
than discarded.)

---

## 5. What was built

| | |
|---|---|
| **F1** | `product_behavior_disqualifiers` widened by exactly two things — the verbs that assert a COMPUTATION we perform, and ONE intervening word. |
| **F2** | R-TG7: `SYNTHESIS_FLOOR_REFUTED_EMPTY` + its door, and `TemplateRenderer._empty_teaching_floor`, the gated branch. |
| **F3** | The recorded driver LEADS at all three sites, one definition, the disagreement and the refusal unchanged. |

### F1, and its census re-earned

The (e) standard is that **a widened predicate re-earns its census; it does not
inherit one.** `tools/spikes/teaching_graft_e2/census_precision.py` is the
standing version of the two censuses (the scripts that produced (e)'s numbers
were scratch). Over the committed corpus **extended with this session's own
sweeps** — 50 transcripts, **562 rendered claim lines, 522 unique, 121 of them
general knowledge**:

| | before F1 | after F1 |
|---|---|---|
| `product_behavior_disqualifiers` on GK claims | 2 | **3** |
| `floor_contradictions` on all claim lines | 0 | **0** |
| firings on the 401 NON-GK claim lines | 2 | **2** |

The third firing was found by the census, not by the brief:

> *"The scheduler itself does not pick a tiebreak rule from a menu — it is the
> solver's objective (tardiness, setup cost, overtime) plus hard constraints
> like machine capacity and precedence that determine which order's operation
> gets the earlier slot…"*

It names our ledger's own components. It is the same species, wearing the same
wrong label, and it is caught by the intervening-word allowance rather than by
the verb list — so both halves of the widening earned their place independently.

**A reconstruction note, stated rather than glossed.** This census is a
re-implementation, not (e)'s script. It finds **the same two specimens** and the
same zero, which is the signal; its totals differ from (e)'s stated 99 / 485
(this one reads 107 / 455 over the same committed corpus) because the extraction
boundary — what counts as a claim line, how the footer note is excluded, how
uniqueness is taken — is drawn slightly differently. The numbers above are this
script's, and it is committed so the next widening is priced against the same
ruler.

### F2 — R-TG7, and what the card says

Rendered from the real renderer:

> *"I drafted an answer to that and cut every line of it — including a general
> rule about how this product decides what can move, which contradicted what
> this product actually computes. I'd rather leave the question open than teach
> you a rule I can show you is wrong."*
>
> *"Name a bar — an order and an operation — and I'll show you the mobility
> verdict this run computed for it. That is what the rule of thumb was standing
> in for, and unlike the rule it is something you can check."*
>
> *Here's what I can do that's closest:*
> *  - why can't ORD-BOX op20 be moved*

Three gates, all read and none assumed: the **LONG licence** (granted to
`teaching` and to nothing else, so this is the parse's decision quoted rather
than a second classifier), an **empty claim set**, and **at least one
floor-refuted cut**. Without the third the ordinary floor is correct — nothing
was refused, so the card's central sentence would be false.

**"Including", not a count and not "all of them."** The gate is ANY refuted cut,
which is the same precedence R-TG6 already gave the mixed-answer disclosure. Two
precedence rules for one fact is how the two drift apart, so the wording had to
be true of a mixed set.

**The partial line still travels.** *"Every line was refused"* and *"the budget
ran out before I finished looking"* are different facts, and dropping the second
because the first is more interesting is how a floor starts lying by omission.

**It does not enter `ANSWER_MEMORY`** — and this turned out to be **already
true** rather than newly built: an answer with no surviving claims sets
`unanswerable` in `Synthesizer.answer`, and the dispatch's memory write is gated
on `not answer.unanswerable`. What is new is that **two tests assert it**, one
per half, because the property is now load-bearing: there is nothing here for a
drill-down to open, and remembering the card would erase the last real answer a
planner could still point at (R-OF1's rider, at the neighbouring floor).

### F3 — before and after, quoted from live fenced-world runs

Same probe both times (`ORD-EARLY:BOX-01:10`, *"why cant this be moved"*), the
BEFORE taken with this session's `renderers.py` stashed. **Both sites appear in
one answer**, which is why the specimen is worth quoting whole.

**The LEAD:**

> **BEFORE** — *"It may be movable — BOX-01 had open, unheld time before where
> ORD-EARLY op10 sits. But the assignment decision records its driver as
> CAPACITY_BLOCKED, which names a constraint rather than a preference, so the
> record and my calendar scan do not agree about this bar."*

> **AFTER** — *"The assignment decision for ORD-EARLY op10 records its driver as
> CAPACITY_BLOCKED, which names a constraint rather than a preference. My own
> scan disagrees — BOX-01 had open, unheld time before where ORD-EARLY op10
> sits — so it may be movable, but the record and my calendar scan do not agree
> about this bar."*

**The BODY:**

> **BEFORE** — *"Holding every other placement where it is, BOX-01 had open,
> unheld time from 2026-01-10 07:00 — so as far as this scan of the calendar
> goes, ORD-EARLY op10 was not forced into Monday 2026-01-12 07:00."* /
> *"But the assignment decision records its driver as CAPACITY_BLOCKED…"*

> **AFTER** — *"The assignment decision records its driver as CAPACITY_BLOCKED,
> which names a constraint rather than a preference."* / *"My own scan reads it
> the other way: holding every other placement where it is, BOX-01 had open,
> unheld time from 2026-01-10 07:00, so as far as that scan goes ORD-EARLY op10
> was not forced into Monday 2026-01-12 07:00. Those two readings disagree, and
> I can't tell you which the solver acted on — so I won't tell you nothing was
> holding it."*

**The argument for the order.** The driver is a RECORD — something this run
wrote down, that a planner can go and look at. The scan is OUR OWN derivation,
computed now, from a model that holds everything else still. Leading with the
derivation makes the record read as a caveat on our finding; leading with the
record makes our finding read as what it is, **a second opinion**. The
disagreement disclosure and the refusal to adjudicate are **byte-for-byte the
ruling (e) made** — only the order moved.

---

## 6. Guards and controls

- **`tests/test_floor_truth_e2.py` — 33 tests, all green.**
  `tests/test_floor_truth.py` is **untouched** and still green (42).
- **6 negative controls proven RED**
  (`tools/spikes/teaching_graft_e2/negative_controls.py`), each asserted **GREEN
  AT HEAD before its seam was reverted**, every restore **byte-identical by
  sha256**. Works in bytes, detects the file's line ending rather than assuming
  it, and ANCHOR NOT FOUND is a failure and never a skip — (e)'s harness
  lesson, inherited whole. (e)'s own five controls are not re-run here; that
  file still owns those seams and is unchanged.
- The controls aim at **seams, not callers**: the F3 controls revert the copy at
  each of the three sites individually, so a fix landing at two of three cannot
  pass.

### Suites

Measured on **this tree**, both **unchunked**. Baseline: the (e) session's own
after-run at this commit, **2735 passed / 305 skipped / 0 failed** in 15m01s.
After: **2768 passed / 305 skipped / 0 failed** in 14m54s.

**+33 passed exactly, and the new guard file collects exactly 33.** Collection
confirms it independently: **3073 with the file, 3040 without it** — and 3040 is
byte-for-byte the number (e) recorded, so the baseline is the same tree in the
same state. **No residual**: nothing else moved, in either direction.

`test_corpus`'s currency guard is **green 22/22** — the corpus index was rebuilt
after the docs/04 and docs/07 amendments and **before** the suite started, which
is the ordering three previous sessions learned the hard way.

The suite ran while nothing else did. It produced no output until it finished,
because pytest buffers under `-q`; that is the census micro-session's recorded
observation and not a hang.

### Line endings — one thing caught in passing

`docs/07-roadmap.md` is CRLF in the working tree (autocrlf) and LF in the repo
blob. A Python rewrite that preserved newlines on both read and write therefore
still left 94 bare-LF lines in a CRLF file. Caught by counting bytes rather than
by trusting `newline=''`, and normalized before commit. `docs/04` is pure LF in
the working tree and its append was correct. **This is (e) §5(c)'s lesson at the
docs layer**: working in bytes is necessary and is not sufficient — you have to
look at what the file actually is.

---

## 7. Minted / untouched

- **MINTED NOTHING.** `_data` unchanged; both pinned boards read-only
  throughout. The demo board was swept and timed, never written.
- The fenced world `_ai_exam_scratch/mobility_pinned` was solved read-only for
  the F3 before/after; no dataset was mutated.
- **Cockpit UNTOUCHED, not re-run.**
- New sweep artifacts at `tests/ai_exam/sweeps/2026-08-05-teaching-e2/`.

---

## 8. NOT FIXED, named

**(a) THE FOURTH W4 SITE.** `mobility_lead_line`'s earlier-open branch asserts
*"Nothing was holding {name} back"* with no driver in hand. Plumbing, named,
pinned by a test that fails the day the payload gains a driver.

**(b) THE WIDENED PREDICATE IS STILL A PATTERN MAP.** One intervening word, a
closed verb list. A paraphrase outside it ships — exactly as (iii)'s map does,
and the honest character of both is their bound. Two intervening words is
untested and untaken, because it was not measured.

**(c) R-TG7's CARD HAS NO LIVE SPECIMEN FROM THIS SESSION.** M2 measured
empty-collapse **0 of 14**, so the card is proven by guard, by negative control
and by a rendered sample — never observed in the wild here. (e)'s single live
occurrence remains its only field sighting.

**(d) F1 MAKES THE EMPTY COLLAPSE MORE LIKELY, BY CONSTRUCTION.** It drops a
shape the model was demonstrably shipping. That is why F2 was unconditional and
why the brief sequenced them together — but whether the two balance out is a
measurement no session has taken, and the honest reading of (c) and (d) together
is that the floor was built before the load arrived.

**(e) THE (e) CARRY-FORWARDS THIS SESSION DID NOT TOUCH** are unchanged:
§5a.194(a) the one-floor map, (c) W2's claim scope, (f) the exam bank's
inability to grade a relational expectation (a third Q7-input line for the
ladder session's R-EX2 format work), and (h) Q3, teaching persistence.

---

## 9. What a summary would undersell

That **the two findings are the same finding twice.** M1 found that (e)'s
predicate missed the sentence (e) printed as its proof of success. M4 found that
(e)'s census of "two sites" missed a third that was live on a shipped route.
Neither is carelessness — the (e) session was unusually rigorous, and it caught
its own map missing its own fix's first output *within the session*. The pattern
is narrower and less comfortable than that: **a session that has just built a
check is the worst-placed observer of what the check does not catch**, because
the specimens it reaches for are the ones it built the check from.

The only thing that found either of these was pointing an instrument at the
previous session's own artifacts and reading the output. M1 is a nine-line
script. M4 is an AST walk. Between them they cost less than an hour and they
found a false label shipping in the close-out's headline quote and a live defect
on a production route.

And that **the errand's discipline did real work.** The brief said: take all
four measurements before any fix lands, and condition everything on a number.
M2's (ii) came back **0 of 14** — which is what stopped F1 from being widened
past its one measured construction, and the temptation to widen further was
real, because a bigger pattern feels safer. It is not safer. It is just bigger,
and the census is the only thing that knows the difference.

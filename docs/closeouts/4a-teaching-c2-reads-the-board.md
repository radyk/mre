# Micro-session 4A — teaching graft (c2): the teaching answer reads the board

**2026-08-04.** R1 item 2, the fix session (c) measured and deliberately refused
to make. docs/07 v2.91, §5a.177-180. docs/04 2026-08-04 **R-TG5 ruled and
BUILT**. Contract unchanged **1.15**; no docs/06 doorway owed. Parse prompt
**UNCHANGED (v18)**; synthesis prompt **v7 → v8**. RUBRIC axis C9 gains **M5 THE
ATTEMPT**. **No seam change, no dispatch change, no new intent, no new claim
class.** Minted nothing. Cockpit untouched, not re-run.

---

## 1. What was wrong, and it was a composition and not a component

Session (c) built RUBRIC axis C9 and its first measurement was a finding:
**M2 0 of 4**. All four transfer-pair teaching answers carried a labelled
general-knowledge principle and **not one carried a single board claim** — zero
verified, zero interpretive, zero lit bars, zero cited records, and two of the
four made no tool call at all. On turn 51 the depth licence granted **eight**
claims and the answer shipped **one**. Asked six times, the same question came
back once on the **unanswerable floor**, because every board-flavoured sentence
it drafted was cut by R-TG1 direction (ii) for citing nothing and nothing was
left to render.

Three rulings, each correct alone:

* **R-TG1** gives domain knowledge a class, and drops an uncited
  board-flavoured sentence.
* **R-TG3** grants `teaching` the long budget.
* **R-TG2** routes the question to the second tier at all.

**Nothing anywhere made a teaching answer look at the plant.** The composition
hands the longest budget to the answers with the least to say — and the tail is
worse than the mean, because a tier that reads nothing drafts sentences that are
all cut, and an answer with nothing left says it could not answer.

The proof that this is about the QUESTION and not the ROUTE was already in
session (c)'s own sweep: the three HUNT probes route to `teaching` too, and they
*do* read the plant. They name a figure, a machine or an order. The transfer
probes say "an operation", "one order", "two orders competing".

---

## 2. The ruling (R-TG5, docs/04, verbatim there)

A teaching-intent answer must **ATTEMPT** a read aimed at finding an instance of
the principle on this board. Then: **case found**, it grounds it — the principle
as `general_knowledge`, the instance beside it as an ordinary cited board claim;
**no case found**, it teaches generally and says so in one line, which is a
disclosure and not an apology.

Three clauses carry the weight.

**THE ATTEMPT IS WHAT IS REQUIRED, NEVER THE GROUNDING.** A board with no
instance of the principle is a fact about the board. The inverse defect — citing
a record that does not really show the principle, to make M2 green — is
explicitly worse, and the prompt says why: *a planner can check a missing example
against nothing, and a wrong one against their board.*

**THE NO-CASE LINE CITES THE READ THAT FOUND NOTHING**, and this is not a style
note. *"Nothing on this board is in that position"* is a statement about the
planner's plant; uncited it carries no board content and **R-TG1 direction (ii)
drops it**. An uncited disclosure is a disclosure the planner never sees. This is
the one place session (a)'s named limit — the taxonomy has no class for a
sentence about our own epistemic position — reaches the prompt, and the answer is
to **ground** the sentence rather than open a fourth class.
`tests/test_teaching_reads_board.py` asserts both halves against the live
verifier, so if that behaviour ever changes the clause is wrong and a test says
so.

**THE CATALOG IS NOT THE BOARD**, and that clause is in the prompt because the
first live draft of v8 failed exactly that way — see §3.

### Why this one is in the prompt when R-TG3 is at the seam

R-TG3 put the depth licence at the dispatch seam because an instruction a model
can forget will be forgotten. This ruling goes the other way, and the reason is
the shape of what would be enforced. **A deterministic did-it-read gate can only
count calls, and a rule that counts calls is satisfied by making one.** The
cheapest way past it is an empty read followed by the same answer; the
second-cheapest is the stretch clause 3 says is worse than the defect. So the
prompt asks, **nothing is enforced**, the sweep measures the rate, and this
close-out reports it. A guard asserts the absence of the gate, so a session that
adds it has to delete a test that explains why it is not there.

---

## 3. The first draft of the fix was wrong, and the live probe said so

v8's rule 14 as first written said *make at least one read aimed at finding an
instance*. Asked P1's teaching question, the model went from **one tool call to
three** — `constraint_catalog` and `spec_lookup`, twice over — and shipped
**zero board claims**, exactly as before.

It had obeyed the rule. `constraint_catalog` is a read, and rule 9 makes it
mandatory before a capability claim, so reaching for it is trained behaviour. It
reads **the product's own documentation** and has never seen this plant.

**A CALL-COUNTING RULE IS SATISFIED BY A CALL**, which is the same argument that
kept the gate out of the seam, arriving one layer up and in the prompt's own
words. Rule 14 now names the distinction, and the grader's M5 **subtracts the two
documentation tools** before deciding whether a teaching answer read anything.
The clause exists because of a measurement, not because of foresight.

---

## 4. The before and after — same instrument, same board, same grader

`sweep_teaching_v3` against the demo board `rolling-db5395dc-2ae`. The BEFORE is
session (c)'s committed run; the AFTER is this session's, with the grader
extended by M5 and by the no-board-claim report (the diff is stated in §5).

| | BEFORE (c, v7) | AFTER (c2, v8) |
|---|---|---|
| routing | 8/8 | **8/8** |
| m1_principle | 4/4 | **4/4** |
| **m2_attached** | **0/4** | **4/4** |
| m3_real_door | 4/4 | **4/4** |
| m4_pair_valid | 4/4 | **4/4** |
| **m5_attempt** | *(not measured)* | **4/4** |
| controls | 2/2 | **2/2** |

`problems: []`. All four teaching answers read this run — 2 to 4 board reads
each — and all four carried a board claim beside the principle.

**AND THE CUTS FELL.** Across the sweep, `failed_and_cut` **7 → 3** and
`verified` **4 → 6**. That is the mechanism, visible: the sentences now cite, so
R-TG1 direction (ii) has less to drop. Session (c)'s answers were not being
censored for being wrong; they were being dropped for being ungrounded, and
nothing had asked them to go and get grounded.

### The floor tail, and turn 51

The same teaching question, asked **six times cold** (`floor_tail.py`, RESET
between every ask):

| | BEFORE (c, v7) | AFTER (c2, v8) |
|---|---|---|
| unanswerable-floor hits | **1/6** | **0/6** |
| read this run | *(not measured)* | **6/6** |
| carried a board claim | *(not stated; turn 51 was 0)* | **6/6** |
| kept claims | turn 51 shipped **1** | **[2, 3, 4, 4, 4, 3]** |

The floor answer is gone because the reason for it is gone. It was never a bug in
the floor: the floor fired correctly on an answer whose every claim had been cut,
and the cuts were correct too. What was missing was the read.

### One answer, in the new shape (run 1, P2, verbatim)

> One order running late tends to make others late because the machines they
> share are sequenced back-to-back: a delay to one operation's end pushes the
> start of whatever is queued right after it on the same machine, and that pushes
> the next, and so on down the line.
> `[general knowledge — how scheduling works in general, not a fact about this plan]`
>
> On PAINT-02, ORD-000206's paint operation on 2026-02-02 is scheduled with only
> a 15-minute gap after the previous order's operation on that machine … so any
> slip in one operation's finish has essentially no slack before it collides with
> the next order's slot. `[record: a3062a95…]`
>
> PAINT-02 runs at 57.3% utilization over the whole plan (8,236 working minutes
> against 14,377 open capacity minutes), but the individual gaps between
> consecutive operations on it are mostly tight — 15, 34, 0, 9, 15 minutes — so
> the low average utilization does not mean there is slack sitting between any
> two specific jobs. `[record: d9cc6ac1…]`

The third claim is the one worth noticing. Nobody asked about PAINT-02's
utilization; the model went looking for the principle, found the average did not
show it, and said so — which is the difference between an illustration and a
decoration.

### A GENUINE NO-CASE ANSWER, and it is on the fenced world

The demo board produced **no** no-case turns: the principles all had instances.
The fenced world `datasets/mobility_box` has **tardiness $0.00**, so the
propagation principle has no instance there by construction. Asked
*"in general, why does one order running late tend to make other orders late as
well"* against it, the fourth claim is the disclosure — **cited**:

> Right now none of this plant's 9 scheduled orders are actually late, so this
> board is not currently showing a delay propagating end to end — only the tight,
> zero-slack coupling that would carry one if it happened.
> `[record: c1d26f05…]`

beside the labelled principle and a real zero-gap pair on PACK-01. It **did not
stretch**: it says in terms that the board is not showing propagation, and offers
the coupling that would carry it as the nearest true thing. That is clause 2 and
clause 3 firing together on the one board built to make a rare case ordinary.
(This is also the smoke test the brief's §2 item 5 asks for: `ask_probe.py` runs
correctly at v8 on the fenced world, so the founder round is runnable as it
stands.)

---

## 5. What the grader gained, and what it deliberately did not

M5 is **the attempt**, not the grounding, and M2 keeps its co-occurrence bound
word for word. What separates *"there was no case and the answer said so"* from
*"the answer never looked"* is M5 and M2 read together — and it separates them
**because of the ruling's own shape**: a disclosed no-case cites, so it lands as
a board claim.

The grader does **not** try to recognise a disclosure by its wording. There is no
fixed sentence to match, and a check that matched one would be measuring whether
the model used our phrasing. Instead every teaching turn carrying no board claim
is **REPORTED VERBATIM** under `no_board_claim_turns`, with its reads and its
answer, for a person to read. `classify_teaching_turn` is a pure function so that
the branch can be premise-tested with injected turns rather than believed because
it was written down — including the manual-only shape from §3, which is the one a
call-counting check would have passed.

---

## 6. Non-regression

**Session (b)'s depth families, re-swept** (`sweep_teaching_v2`, 19 turns, same
board, same grader):

| family | (b), committed | (c2), after v8 |
|---|---|---|
| routing | 15/15 | **15/15** |
| e_long | 12/12 | **12/12** |
| f_short | 3/3 | **3/3** |
| g_no_false | 9/9 | **9/9** |
| h_audience | 9/10 | **9/10** |
| i_untouched | 10/10 | **10/10** |

**Identical, including the miss.** The single problem line is byte-identical to
(b)'s: `[h_audience] line 130: no audience lead — CLARIFY`, which is the
*"what should i tell the customer about ORD-000091"* specimen (b) kept
deliberately rather than fitting away. A prompt change can move compression, and
this one did not: `g_no_false` is clean and `f_short` is inside the cap.

**The hunts, in the same run:** direction (i) refusals **0**, closer firings
**0** — unchanged from (c)'s two runs, and the closer still has no live specimen
under any prompt this repo has shipped.

**The three HUNT probes still read the board**, which was the non-regression that
mattered most: they were the answers that already behaved, and a rule aimed at
the ones that did not must not disturb them. Turns 116/119/122, both after-runs,
made **2/2/3 board reads** and carried **3+ verified-or-interpretive claims**
each, with **zero cut** on five of the six observations.

**AND ONE THING MOVED THAT IS WORTH SAYING RATHER THAN GLOSSING.** Their
LABELLED GENERAL claim is not stable: `general_knowledge` reads 0/1/1 on run 1
and 1/0/0 on run 2, so two of the three shipped no labelled principle in the
graded run. They are ungraded by design — the grader `continue`s past them before
M1 ever applies — and (c) established that this tier varies turn to turn. It is
recorded because a rule about teaching answers landed in the same commit, and a
reader should be able to see that these three moved and that nothing here proves
which way.

**Contracted testimony and the all-board controls are untouched** — `controls
2/2` in the C9 grade (a contracted answer carries no teaching machinery; a
non-teaching second-tier answer is not required to carry a principle) and
`i_untouched 10/10` in the depth grade.

---

## 7. The negative control

Rule 14 **physically excised** from the governed artifact, the same four
transfer-pair teaching questions asked on both arms, prompt restored in a
`finally` and **the restore asserted byte-identical by sha256**
(`bcfaecdf09e84639…`, `restore_identical: true`).

| | v8 (shipped) | rule 14 excised |
|---|---|---|
| read this run | **4/4** | **2/4** |
| carried a board claim | **4/4** | **2/4** |
| board claims per probe | [1, 2, 1, 3] | **[0, 0, 1, 1]** |
| board reads per probe | [4, 3, 1, 3] | **[0, 0, 1, 1]** |

**P1 and P2 collapse to session (c)'s exact shape** — zero reads, zero board
claims, the principle alone.

**AND IT FIRES ON TWO PAIRS OF FOUR, NOT FOUR.** P3 and P4 still made one read
and carried one board claim with the rule gone. That is reported as it happened
and not re-rolled: this is a live model on both arms, and session (c) established
that turn-to-turn variance in this tier is real and not small (direction (i)
refused twice in a hunt and zero times in two sweep runs of the same probe). The
control shows the rule moving the measurement; it does not show it moving every
probe every time, and the brief asked for the honest number. **The committed
BEFORE sweep remains the baseline of record** — it is four answers measured
before this session existed, which no control arm run under this session's hand
can replace.

---

## 8. What the summary would undersell

**THE FIX IS ONE RULE AND THE SESSION IS THE MEASUREMENT.** The diff that changes
behaviour is a single prompt rule. Everything else here is instrument: a check
that matches the ruling, a pure function so the check can be tested, a control
that takes the rule out again to see whether it was the rule. A one-rule change
that nobody measured would be indistinguishable from a lucky afternoon with a
language model.

**THE FIRST DRAFT FAILED IN THE SHAPE THE RULING HAD ALREADY NAMED.** R-TG5
refuses a seam gate because a call-counting rule is satisfied by a call. The
first draft of the prompt rule was itself a call-counting rule, and the model
satisfied it with three lookups of our own documentation. The argument was
written down before the specimen appeared and the specimen still had to appear
before the clause did — which is the honest order, and it is why the live probe
ran before the sweep and not after.

**THE SESSION DID NOT TOUCH THE THING IT WAS MEASURING.** Session (c) refused to
edit the synthesis prompt because two of its findings were about what that prompt
produced. This session edits it, and therefore treats (c)'s committed sweeps as
the baseline of record rather than re-running the BEFORE arm under its own hand.

---

## 9. Numbers

- **Python: 2658 passed / 305 skipped / 0 failed** (996.6s, default
  `python -m pytest -q`), against session (c)'s **2643/305/0** measured the same
  way. **+15 passed, skips unchanged**, and `tests/test_teaching_reads_board.py`
  collects **15** — so the delta is exactly this session's guard file and nothing
  moved underneath it. (Session (c) carried an unaccounted skip in its own delta;
  this one has none, which does not explain (c)'s and is not claimed to.)
- **ONE FAILURE WAS SELF-INFLICTED AND IS RECORDED RATHER THAN QUIETLY
  RE-RUN.** The first full run came back **2657/305/1**, failing
  `test_corpus.py::TestCurrency::test_index_matches_the_live_docs` — because the
  corpus index was rebuilt for the docs/04 and docs/07 amendments **while that
  run was in flight**, so the test compared a live doc against an index from
  four minutes earlier. Rebuilt, `tests/test_corpus.py` **22/22**, and the clean
  full run above is the run of record. The guard did exactly its job; the
  operator sequenced badly.
- **`--runslow` NOT RE-RUN.** Session (c) proved
  `test_ai_voice.py::TestAuditCorpusClean::test_cu5_split_jobs` red **at HEAD**
  and pre-existing (a live-parse routing outcome). This session changed the
  synthesis prompt and not the parse prompt, and that test is about where
  *"are there any split jobs"* routes — a parse decision. Not re-measured, and
  therefore **not claimed either way**.
- **ONE `src/` CHANGE, ONE FILE:** `src/mre/modules/synthesis_prompt.md` — a
  version bump, a documentation block, and rule 14. **No Python under `src/`
  changed at all**; `src/mre/corpus_index.json` is regenerated package data.
  Current prompt sha256 `bcfaecdf09e84639…`, equal to the hash the negative
  control asserted on restore.
- **Negative control: 1, and it fired on 2 of 4 probes** — §7, reported with its
  variance rather than re-rolled. Restore byte-identical by sha256.
- **Guards: `tests/test_teaching_reads_board.py`, 15 tests**, including the two
  that assert the R-TG1(ii)/R-TG5 interaction against the LIVE verifier (an
  uncited disclosure is cut; the same sentence cited is not) and the one that
  asserts **the absence of the seam gate**.
- **Sweeps, committed at `tests/ai_exam/sweeps/2026-08-04-teaching-c2/`:**
  * `sweep_teaching_v3` — **two runs**, 16 turns each. Run 2 is the graded one;
    run 1 is kept because it was graded by an intermediate grader (before
    `classify_teaching_turn` was factored out) and is an independent sample.
  * `sweep_teaching_v2` — session (b)'s depth families, re-swept, 19 turns.
  * `floor-tail.json` — the six cold asks.
  * `rule14-control.json` — the negative control, both arms, with the restore
    hash.
  * `no-case-specimen-mobility-box.txt` — the found-none disclosure, verbatim.
- **Cockpit: UNTOUCHED, not re-run.** No `src/cockpit/` file changed.
- **MINTED NOTHING.** No registry run, no registered schedule, no `_data` write.
  The fenced world was **read** (`_ai_exam_scratch/mobility_pinned`, snapshot
  `snap-mobility`) and not rebuilt; both pinned boards are untouched.
- Governed artifacts: **parse prompt v18 UNCHANGED**; synthesis prompt
  **v7 → v8**. Corpus index rebuilt (docs/04 and docs/07 amended).

---

## 10. Carry-forwards

**(a) RULE 6 AND RULE 14 DISAGREE ABOUT WHAT GOES FIRST, AND THE MODEL SPLITS
2–2.** Rule 6 says put the answer in the first claim. On a teaching question the
principle arguably *is* the answer, and rule 14 asks for the board case as well.
Measured on run 1: **P2 and P4 lead with the principle; P1 and P3 lead with the
board case.** Both readings are defensible and nothing in the prompt chooses.
Naming the opener would be a fifth rule about ordering, and this session did not
open it.

**(b) THE LONG BUDGET STILL DOES NOT BIND.** `deferred` is **0** across both
sweeps and kept claims run 2–4 against a licence of **8**. R-TG3's ceiling
remains a floor with no load on it — session (c) §6.2's finding, now measured a
third time. Rule 14 raised what an answer SAYS without raising how MUCH it says,
and that is not a complaint about either rule; it is the observation that the two
levers are independent and only one of them is doing anything.

**(c) THE STRETCH IS UNMEASURED IN THE WILD.** Clause 3 forbids citing a record
that does not really show the principle, and **nothing mechanical can catch it** —
M2 is co-occurrence only and says so twice. The four after-answers were read and
none stretches. Four read answers are not a rate, and the founder round is where
this gets a real reading.

**(d) M5 COUNTS A READ, NOT A RELEVANT READ.** An answer that called
`lateness_set` and then talked about something else would pass. Subtracting the
two documentation tools is the only aboutness M5 has, and it is deliberately
crude — a check whose name over-claims is the defect class this repo keeps
finding, and M5's name is "the attempt" for that reason.

**(e) `SYNTHESIS_UNPLACEABLE` STILL FIRES ON MOST TEACHING ANSWERS.** *"Part of
what I drafted was neither something I could check against your board nor general
scheduling knowledge…"* — cuts fell 7 → 3 but did not reach zero, and the line
appears wherever one claim is dropped. Pre-existing and correct; noted because it
now sits under answers that are otherwise fully grounded, which is a different
reading experience from sitting under an answer that grounded nothing.

**(f) THE HUNT PROBES' LABELLED PRINCIPLE IS NOT STABLE** — §6. Ungraded by
design, recorded because it moved in the same commit as a rule about teaching
answers.

**Session (c)'s own carry-forwards (b)–(g) are untouched and still stand**: the
fenced world is not registered, `edit-summary` prints a truncated operation uuid,
*"why is ORD-PACK pinned"* answers about the frozen front, the hunt-A specimen is
a coin flip, a count named in the question is not tracked, and `_open_windows`'
fortnight pad is unexamined. **Session (d) — multi-turn — is untouched, as
briefed.**

# Session 4A — teaching graft (a): the general-knowledge claim class

**2026-08-03.** R1 item 2, session (a) of four (docs/07 §5b). docs/07 v2.88,
§5a.162-164. docs/04 2026-08-03 **R-TG1 ruled and BUILT** plus the **R-OF1
rider**. Contract unchanged **1.15**; no docs/06 doorway owed; both answered on
the record. Parse prompt unchanged **v17**; synthesis prompt **v5 → v6**. RUBRIC
gains axis **C7 CLAIM CLASS**. Minted nothing.

---

## 1. The finding, stated plainly

**Ten domain-inviting probes against the demo board `rolling-db5395dc-2ae`, at
HEAD, before a line of this ruling existed. SEVEN SENTENCES OF GENERAL
SCHEDULING KNOWLEDGE SHIPPED ACROSS SEVEN SYNTHESIS ANSWERS, NOT ONE OF THEM
LABELLED AS SUCH.**

Four carried no board content at all; three were mixed into a sentence that also
quoted a board figure. Every one wore a marker that asserts board grounding:

| marker | count | what it says |
| --- | --- | --- |
| `[synthesis — read from: 0f093432, ff8a63c4, e96a85fc]` | 5 | this sentence came out of these records of yours |
| `[synthesis — my reading, no record states this]` | 2 | this is my reading **of this plan** |

Of the ten probes, three were taken by contracted routes (`advice`,
`lateness-cause`, `coaching`) and one synthesis probe declined on the capability
floor at **0 tool calls**. Across the seven answers, **26 claims: 2 VERIFIED, 24
INTERPRETIVE, 0 general** — because there was no general.

**The sharpest specimen.** Asked *"in general, what makes a scheduling problem
hard to prove optimal"*, the tier returned:

> A second, separate reason is that most practical objectives (tardiness, setup
> cost, overtime) are themselves non-convex and discontinuous, so even checking
> that a candidate schedule cannot be improved requires exploring combinatorial
> neighborhoods rather than following a gradient — this is why exact methods
> scale poorly … **(based on the 26 row(s) constraint_catalog returned, not the
> whole plan)  [synthesis — my reading, no record states this]**

The sentence is true and useful. It rests on no row of anybody's catalog. The
marker is the honest one we have, and beside it the sample note asserts the claim
was read off 26 rows of *this plan's* constraint catalog.

**THE MODEL WAS NOT AT FAULT.** There was no class for the sentence to be, so the
honest thing it had to say was said in the only vocabulary the surface offered,
and that vocabulary means *I read this off your board*. The exposure was
structural, live, and it is what this session closes.

## 2. The census (what happened to such a claim at HEAD)

`synthesizer._coerce_claims` → `kind` defaults to `FACT`. `claim_verifier.
verify_claim` → `cited` empty, so the scope is the WHOLE consulted set.
`extract_assertions` finds no entity, no timestamp, no duration, no money → the
checkable list is EMPTY → **branch 3, `INTERPRETIVE`**, reason *"no assertion
this run's records can check"*. The renderer then reads `consulted_record_ids`
(the whole consulted set, up to 12) and prints `[synthesis — read from: <ids>]`.

So the path is not that an unbacked claim slipped through a gap. **It ships by
design, correctly labelled under the taxonomy that existed, and the taxonomy was
wrong.** Only when the consulted set is empty does the second marker appear, and
it is barely better: *my reading* still means a reading of this plan.

## 3. The ruling — R-TG1 (docs/04 2026-08-03, verbatim there)

Three kinds of sentence. Board claim and board-derived inference: unchanged.
**General-knowledge claim: UNVERIFIABLE BY DESIGN** — verification is SKIPPED and
the claim is LABELLED; it may never fail, and may never pass unlabelled.

`ClaimKind.GENERAL_KNOWLEDGE` is the model's **PROPOSAL**;
`ClaimStatus.GENERAL_KNOWLEDGE` is the verifier's **VERDICT**. Different objects
on purpose — R-AI5(8) at a second seam.

**ONE DETERMINISTIC PREDICATE, READ BOTH WAYS** (`gk_disqualifiers`). Two
predicates would drift.

**(i)** A claim carrying board content may not wear the label. Board content is a
citation, a named order or machine, a timestamp, a currency figure, or **a number
this run computed**. The last clause closes the escape hatch. A refused proposal
is **not cut** — it falls through to ordinary board verification, and the refusal
and its reason are recorded, because a disqualification that leaves no trace is a
check nobody can audit.

**(ii)** A claim citing nothing, grounding nothing and naming nothing on this
board is **DROPPED** unless it was proposed. A CONCLUSION gets no exemption —
without that, the model calls its general sentence a conclusion and ships it
unlabelled, which is what two of the four pure specimens did.

**Why (ii) is a drop and not an auto-label.** The verifier can prove the label's
second half (*not a fact about this plan*); only the author can make the first
(*this is how scheduling works*). *"Things are pretty tight right now"* carries no
board content either, and it is a vague assertion about the plant. **The verifier
may REFUTE a proposal and may not MANUFACTURE one.**

## 4. Live on the demo board

**(a) A MIXED ANSWER, EACH LINE LABELLED FOR WHAT IT IS** — `sweep_teaching_v1`
Q[47], verbatim:

> Across the whole plan, 102 of 158 scheduled orders are late, 56 are on time or
> early, and a further 122 orders have no placement at all in this schedule.
> `[synthesis — read from: aec9d551]`
>
> The single largest tardiness cost line, ORD-000091 at 147,776.67, comes from
> its final operation on PAINT-01, which does not start until 2026-01-15 17:21 …
> `[synthesis — read from: 47a25482, 6ca007d1, 6cfd554b]`
>
> PAINT-01 runs at 79.4% utilization over the plan (12,410 working minutes
> against 15,626 open minutes) … `[record: 7c78eed8...]`
>
> Total tardiness cost across the plan is 1,580,665, against production cost of
> 71,362.8 and setup cost of 15,440 … `[synthesis — read from: 3c67fcfd]`
>
> In a job shop, a heavily loaded machine that many order routings pass through
> becomes a queueing point: once its utilization climbs, small variations in
> arrival timing or upstream delay compound into growing wait time before that
> machine … **`[general knowledge — how scheduling works in general, not a fact
> about this plan]`**
>
> *Where a line is marked general knowledge it draws on how scheduling and plants
> behave generally — not on this plan's records, so there is nothing here to
> check it against.*

**(b) AN ALL-BOARD ANSWER, UNCHANGED** — *"which order carries the largest single
tardiness cost line on this board"*: 3 claims, 1 verified, 2 interpretive, **0
general**, no marker, no footer note. The first line reads `ORD-000091 carries the
largest single tardiness cost line on this board, at 147776.67 … [record:
47a25482...]` — the same shape it had at HEAD.

**(c) TESTIMONY UNTOUCHED** — *"why is ORD-000128 op20 placed here"* returns the
`why-here` chain, `register: testimony`, `renderer: template — authored copy —
rendered verbatim`, no general marker anywhere. The machinery is unreachable from
the contracted path, because no model drafts claims there at all.

**The same ten probes, after:** 17 general claims labelled, 7 cut. **The probe
that got the capability card now answers** — *"how do schedulers normally decide
which job to run first"* declined at HEAD not for want of knowledge but for want
of a place to put it.

## 5. The bank

`tests/ai_exam/banks/sweep_teaching_v1.txt` — 14 turns, demo board, graded by
`tools/spikes/teaching_graft_a/grade_gk_sweep.py` (the exam grammar's EXPECT
lines grade ROUTING only, and C7 is about claim classes).

| | |
| --- | --- |
| routing expectations | **13/13** |
| (a) LABELED — every general claim reaches the page wearing the marker, both halves | **27/27** |
| (b) CITED — board claims in the same answers keep their citations | **9/9** |
| (c) NO HATCH — no marked line names an order, a machine or a time | **17/17** |
| (d) UNTOUCHED — no contracted answer renders a general marker | **5/5** |

Sweep committed at `tests/ai_exam/sweeps/2026-08-03-teaching-v1/`.

**(b) is the guard that matters most and is easy to miss:** a change that quietly
relabelled board claims as general would pass (a) and be the worst outcome
available.

## 6. Guards and controls

**33 tests** in `tests/test_general_knowledge_claims.py`, written from the ruling.
**7 negative controls proven RED** against physically reverted code
(`tools/spikes/teaching_graft_a/negative_controls.py`), every restore
byte-identical by sha256.

**THE HARNESS FOUND ITS OWN BUG FIRST, AND IT IS 4A.y's LESSON FROM THE OTHER
SIDE.** This repo mixes line endings per file — measured: `claim_verifier.py` is
pure LF, `renderers.py` and `interpreter.py` pure CRLF, no file mixed. A
multi-line byte anchor written with `\n` matched in one file and silently did not
in another. It surfaced as `[SETUP FAIL] anchor not found`, which is the only
reason it was not read as *the guard cannot fire*. 4A.y's translation happened on
the WRITE; this one happened on the READ.

**THREE PRE-EXISTING ASSERTIONS WERE UPDATED BECAUSE THEY STATE THE OLD
BEHAVIOUR AND THE UPDATE IS THE RULING** — five test bodies in
`tests/test_synthesis.py`, each carrying a fixture claim ("The cutting line is
the constraint", "The plan looks tight") that direction (ii) now cuts. In four of
the five the test's SUBJECT is elsewhere (the malformed nudge, memory staleness,
prove-it precedence), so the fixture gained board content rather than the
assertion being weakened. The fifth, `test_counts_report_every_outcome`, now
carries four outcomes because there are four.

## 7. Two things the ruling broke and had to fix in the same commit

**THE FORCED CLOSE ASKED FOR A SENTENCE (ii) NOW CUTS.** `_forced_close` told the
model *"Say plainly in one claim what you did not get to look at"* — a claim about
our own read. It should be cut: R-AI1's rule is that the words about our own
process are ours and computed, and `SYNTHESIS_PARTIAL` already renders that fact
from the toolbox's own call log. The instruction is removed, and the unanswerable
branch now states the budget/timeout fact, which it never did — reachable only
once an uncitable sentence stopped always surviving to keep the answer non-empty.

**A CUT NAMES WHICH KIND OF CUT IT WAS — FOUND LIVE, AFTER THE FIX WENT IN.**
Direction (ii) cuts the tier's own honest limit statements:

> Whether a large gap here reflects a genuinely weak schedule versus a loose
> bound is something I cannot check against this run.

That sentence is neither a board claim nor domain knowledge. The answer then
said *"one step of my reasoning didn't hold up against the records"* — **false in
its first clause: the step never reached the records to fail against them.** A
second authored line (`SYNTHESIS_UNPLACEABLE`) says what actually happened; a
genuine grounding failure is the stronger fact and wins a mixed answer.

## 8. The R-OF1 rider

A `system`-register card does not enter `ANSWER_MEMORY`. Nothing was read,
reasoned or advised, so nothing may ground a drill-down — and the sharper half is
that remembering it would **ERASE the last real answer**, the one the planner is
still looking at and the only one a *"show me the evidence"* could mean. **Keyed
on the REGISTER, not a route name**, so a card that earns `system` later inherits
the rule. This discharges docs/07 §5a.161(b).

## 9. What the summary would undersell

**The class is not a label, it is a place.** The obvious reading of this session
is "we added a tag". What actually changed is that a sentence now has somewhere to
be — and the measure of that is the probe the tier REFUSED at HEAD. *"How do
schedulers normally decide which job to run first"* got the capability card,
0 tool calls, *"I don't have a tool that reaches it"*. That was honest and it was
a loss: the tier knew the answer and had no honest way to say it. It answers now.

**The hard part was not (i), it was (ii).** Direction (i) is a filter and it reads
like the whole item. Direction (ii) is the one that closes the exposure, and it is
the one that cost something: it drops a class of sentence the product used to
ship, including sentences that were true. Every one of the five updated tests, the
`_forced_close` change and the `SYNTHESIS_UNPLACEABLE` line are (ii)'s blast
radius, and finding the last of them required running the fixed code against a
real board and reading the output.

**The verifier may refute and may not manufacture.** That is the sentence to
carry forward. It is why (ii) drops rather than auto-labels, and it is the same
shape as the parse layer's discipline — the model proposes, the deterministic
seam disposes, and where the model proposed nothing the deterministic seam does
not invent one.

## 10. Carry-forwards (REPORTED, deliberately NOT fixed)

**(a) THE TAXONOMY HAS NO HOME FOR A SENTENCE ABOUT OUR OWN EPISTEMIC POSITION.**
The immediate harm is fixed (§7); the gap is not. A fourth class is a
vocabulary-class change this session did not open. R-DP12 §5a.130's shape on
another axis.

**(b) DIRECTION (i) HAS NO LIVE SPECIMEN FROM THIS SESSION.** Under prompt v6 the
model keeps figures out of general sentences, which is what rule 13 asks — so
across every post-change probe run, **no proposal was refused**. It is proven by
unit guard and by a negative control against reverted code, never observed in the
wild. A later session should look for one rather than assume the clause is
exercised.

**(c) `_sample_note` IS ANSWER-LEVEL PROVENANCE IN PER-CLAIM CLOTHES, STILL.** It
picks the LARGEST tool call of the whole session regardless of what the claim
touched — which is how the §1 specimen came to read *"based on the 26 row(s)
constraint_catalog returned"*. R-TG1 removes that specimen from the general path
(a general line gets no sample note at all) and **leaves the defect standing for
board claims**: 4B.5 CU5(d)'s class at a site it did not reach.

**(d) THE CONTROL FAMILY RAISED A `validator` FINDING** on *"which orders are late
and by how much"* — LLM testimony failed validation and fell back to the template.
Pre-existing, contracted path, unrelated to this item, and the fail-closed
behaviour working. Recorded because it was seen.

**(e) THE NUMBER CLAUSE IS CONSERVATIVE BY CHOICE.** It refuses a general sentence
quoting any figure this run computed, including an unrelated small integer.
Over-refusal falls back to the behaviour that already shipped; under-refusal is
the hatch. Named so a later session tightens it deliberately, if at all.

**(f) OUT OF SCOPE AND UNTOUCHED, PER THE BRIEF:** the depth licence and answer
length (session b), the teaching intent in the parse vocabulary (session b), the
did-the-planner's-model-improve exam axis and the fenced specimen world (session
c), multi-turn grounding (session d). Answers may read longer here because a class
exists for sentences previously dropped or mislabelled; **no length policy was
written.**

## 11. Numbers

- **Python: 2581 passed / 291 skipped / 0 failed** (20:44), against the recorded
  family-floor baseline of **2548/291/0** — **+33**, which is exactly the 33 new
  guards in `tests/test_general_knowledge_claims.py`. No skip moved. HEAD was
  ALSO measured independently in a detached worktree: **2515 passed / 295 skipped
  / 0 failed** — not directly comparable, because a worktree has no `_data` and
  the data-dependent tests skip there; the comparable fact from it is **zero
  failures at HEAD**.
- The full-suite run was started before a comments-only rewrap of the
  `claim_verifier` module docstring. `tests/test_general_knowledge_claims.py`,
  `tests/test_synthesis.py` and `tests/test_corpus.py` (111 tests) and all seven
  negative controls were re-run against the exact committed bytes and are green /
  red respectively. Said here rather than glossed.
- **Cockpit: UNTOUCHED, NOT RE-RUN.** No `src/cockpit/` file changed.
- **Minted nothing.** No new run, no new schedule, no new board.
- Sweep: 14 turns, 9 synthesis answers, 17 general-knowledge claims, 4 verified,
  14 interpretive, 7 cut.

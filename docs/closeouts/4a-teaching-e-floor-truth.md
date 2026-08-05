# Session 4A teaching-graft (e) — the teaching answer may not contradict the floors

**2026-08-05.** R-TG6 ruled and BUILT, plus the founder's felt-bar ruling (W6).
Contract unchanged **1.15**; no docs/06 doorway owed. Parse prompt unchanged
**v18**; synthesis prompt **v8 → v9** (rule 15). `DriverCode` unchanged.

Origin: the **C9 founder round**, run by Daryn 2026-08-04/05 on the fenced world
`datasets/mobility_box`, four clean pairs. Its artifacts are committed as the
round's record at `tools/spikes/teaching_graft_c/c9_answers/q7.md … q10.md`,
with the prediction line filled in under Q9 in `founder_round_c9.md`.

---

## 1. What the round found

The C9 axis was built (session (c), R-EX1) to grade whether a planner could
PREDICT THE NEXT CASE, and its hypothesis H1 named the failure it was most afraid
of. The round found exactly that failure:

**A teaching answer stated a principle that is FALSE of this product, and this
product's own deterministic floor had proven it false on the same board three
questions earlier.**

Q7 (`ORD-BOX:BOX-01:20`, testimony) — the mobility floor computes **BOXED_IN**:
bound earlier by op10, nothing later, **no lock and no pin anywhere in it**. The
fenced world was built so that exactly this is true (R-SW1).

Q9 (`what makes a job impossible to move at all`, synthesis, teaching intent),
minutes later, wearing the general-knowledge label:

> *"In this product, a job becomes immovable **only** through a
> `frozen_assignment` or pinned constraint declared in `locks.csv` … nothing else
> in the catalog removes an operation's mobility outright."*

Seven tool calls, every one hunting for LOCK RECORDS. The machinery that had
already answered the question was never consulted. The same answer then offered
ORD-BOX — the boxed-in bar — as an example of a job that is *not* stuck.

**THE FOUNDER READ Q9 AND REPORTED HIMSELF SATISFIED.** That is the harm profile
and it is why this outranked the persistence question: not a visible error, a
confident reader carrying a wrong rule out of the room.

---

## 2. Census before fix

**(a) GK-mislabelled product claims.** The predicate was run over **every unique
general-knowledge claim shipped across every committed sweep — 99 of them**. It
fires on **2**, and both are genuine product claims wearing the wrong label:

| claim (truncated) | why it is a product claim |
|---|---|
| "Freezing is implemented through explicit lock records … `lock_type` such as 'frozen'…" | our declared schema |
| "The constraint catalog does not have a specific 'bottleneck machine' item — it lists disjunctive capacity … as in-core and proven" | our catalog's own status words |

Both are TRUE. Both are unlabelled-as-what-they-are, and both are DROPPED only
because uncited — a citation sends them down the path 4B.15 §5a.43 already built.

**(b) The (iii) map's precision.** Run over **485 unique claim lines** (all
registers, every committed sweep): **0 false positives**. It fires on all three
measured specimens — the founding GK sentence, the same rule as a CITED board
claim (q9.md's first line), and the paraphrase this session's own fix produced.

**(c) Floors with a verdict vocabulary a teaching answer could contradict.**
Mobility (`mobility_premise`, five verdicts) is the only one with a verdict
vocabulary in this sense today. R-OF1's three outage floors are states of OUR
reachability, not verdicts about the plant; R-FF1 scopes which routes get the
mobility check, not a second vocabulary. **The map has one entry, and the cost of
the next is one authored tuple plus its false-positive census** — the census is
the expensive half and it is what makes the entry honest.

**(d) Specimen-C emitters.** Two, both in `renderers.py`, both rendering from the
same `chose` verdict: the why-here LEAD (`_mobility_correction`) and the
"Earlier —" BODY. Both had `chosen_driver` in hand. Both are fixed.

---

## 3. What was built

| | |
|---|---|
| **W1** R-TG6 (i) | `product_behavior_disqualifiers` — a SEPARATE predicate from `gk_disqualifiers`, on a disjoint axis. Uncited product claim → DROP. |
| **W2** R-TG6 (ii) | `mobility_contradictions` + `Explainer.order_mobility_verdicts` — the floor is ASKED, per operation, never re-derived. |
| **W3** R-TG6 (iii) | `floor_contradictions` — the authored map, one entry, applied to EVERY claim whatever label it wears. |
| **W4** | `CONSTRAINT_NAMING_DRIVERS` + `counterfactual_contradicts_driver`; both emitting sites re-authored. |
| **W5** | `_no_later_reason` (three states) + `_no_later_clause` (one definition, two call sites). |
| **W6** | preamble removed; GK note and teaching invitation scoped to the first synthesis answer of a conversation; `SYNTHESIS_FLOOR_REFUTED` as a third cut kind. |

### The design decision that mattered most

**R-TG6 (i) IS NOT A SIXTH CLAUSE OF `gk_disqualifiers`, AND THAT WAS THE FIRST
THING GOT RIGHT.** That function is R-TG1's board-content predicate and direction
(ii) drops a claim precisely when it has NO board content. A product-behavior
claim has no board content. Folding it in would have made direction (ii) see
board content where there is none, and the founding sentence would have stopped
being dropped and started shipping as INTERPRETIVE — *"my reading, no record
states this"*. **A different false label on the same false sentence.**

### The (iii) verdict: BUILT, and bounded

The brief allowed an honest-failure path. It was not needed, but the thing built
is smaller than "check general sentences against a verdict vocabulary" and the
close-out states the difference rather than letting the ruling's wording imply
more:

- It is an **authored map**, not an entailment checker. Building the latter means
  scoring the entailment with the weights that wrote the answer — the LLM judge
  R-EX1 wrote down and refused.
- It is falsified **by the vocabulary, not by the board**, which is the stronger
  claim: `VERDICT_BOXED_IN` existing in `mobility_premise` refutes "only a lock
  immobilizes" on every board, including boards holding no specimen.
- **It holds the shapes a model has been SEEN to use.** It was widened once, by
  measurement, mid-session — see §5. A paraphrase outside the map ships.

---

## 4. Before / after, quoted verbatim from live fenced-world runs

**W5 — Q7's later-direction sentence.**

> **BEFORE** — *"Later: no opening on BOX-01 fits the whole operation after where
> it sits now either — so "can't be moved" is fair…"*

> **AFTER** — *"Later: BOX-01 is not open at all after 2026-01-13 19:00 — its
> calendar closes there and does not reopen anywhere in the span this plan
> covers, so the whole operation has nowhere later to go. **This is not a busy
> machine; there is no time on it to compete for.** So "can't be moved" is fair…"*

**W4 — Q8, the lead and the body.**

> **BEFORE** — *"It can be moved — nothing was holding ORD-EARLY op10 back."* …
> *"Nothing prevented ORD-EARLY op10 from starting earlier."* … *"The assignment
> decision records its driver as CAPACITY_BLOCKED."*

> **AFTER** — *"It may be movable — BOX-01 had open, unheld time before where
> ORD-EARLY op10 sits. But the assignment decision records its driver as
> CAPACITY_BLOCKED, which names a constraint rather than a preference, so the
> record and my calendar scan do not agree about this bar. Here is what each
> says."* … *"Holding every other placement where it is, BOX-01 had open, unheld
> time from 2026-01-10 07:00 — so as far as this scan of the calendar goes,
> ORD-EARLY op10 was not forced into Monday 2026-01-12 07:00. But the assignment
> decision records its driver as CAPACITY_BLOCKED. Those two readings disagree,
> and I can't tell you which the solver acted on — **so I won't tell you nothing
> was holding it.**"*

**Q10 (`ORD-PACK:PACK-01:10`, LATER_OPEN) is BYTE-IDENTICAL to the committed
q10.md.** The control holds.

**R-TG6 — Q9, the founding question, three cold runs after the fix. The wrong
rule appears 0 times in 3 runs.** Run 1:

> *"A job becomes impossible to move for one of a small number of specific
> reasons this product actually computes, **not just a lock**: it can be
> explicitly frozen or pinned to a resource, it can be excluded from resources it
> would need, or **it can be boxed in by its own precedence chain, release date,
> or calendar with no later opening long enough to hold it**."*
> `[general knowledge]`
>
> *"ORD-BOX shows the boxed-in shape directly: its FEED-01 operation ends at
> 2026-01-13 09:52 and its BOX-01 operation starts the same minute, with zero gap
> between them — a chain like this has no slack to move into **even though
> neither operation carries a lock**."* `[record: 6af3d3e4…]`

Run 2 also names the UNDECIDABLE verdict, grounds on BOX-01's closure block (W5's
own fact, reached independently), and carries the new cut line:

> *"I drafted a general rule about how this product decides what can move, and it
> contradicted what this product actually computes — so I cut it. Ask me about a
> specific bar and I'll show you the verdict itself rather than a rule of thumb
> about it."*

This is R-TG5 and R-TG6 working together: the principle is labelled, the instance
is cited, and **the principle is now the one the floor actually computes.**

---

## 5. Two things this session got wrong first, and how it found out

**(a) THE (iii) MAP MISSED ITS OWN FIX'S FIRST OUTPUT.** With W1/W3 in, the very
next live Q9 said the same false thing in a construction the map did not hold:

> *"the immovability comes from a lock or the frozen zone, **not from** anything
> intrinsic to a job's lateness or timing"*

Exclusive by contrast rather than by "only". The map was widened by MEASUREMENT
(two alternations, then the 485-line precision census re-run: still 0 false
positives) and the specimen is kept in the guard file. **This is the honest
character of a pattern map and it is why the close-out says so twice.**

**(b) W5's DISCRIMINATOR WAS WRONG TWICE BEFORE IT WAS RIGHT.** First attempt:
"no open window after the operation ends" — but BOX-01 has open time on the
afternoon of the 13th before the rebuild, so it did not fire. Second: "the
machine's calendar ends before the last placement in the plan" — measured, BOX-01
stays open until **19:00** on the evening the plan's last bar ends at **18:33**,
so a machine gone for a fortnight was called merely busy. The right comparator is
the **scan horizon** (`_open_windows`' own fortnight pad), and the pad is now one
named constant with two readers so the two cannot drift.

**(c) THE CONTROL HARNESS WENT STALE MID-SESSION AND CAUGHT ITSELF.** The five
controls ran 5/5 early. Later — after `git stash push` / `stash pop`, taken to
measure the HEAD baseline in this same checkout — three of them reported **ANCHOR
NOT FOUND**. The stash round-trip had renormalized `claim_verifier.py` from LF to
CRLF, and three anchors authored with `\n` no longer matched a byte of the file
they were aimed at.

**They reported it rather than passing falsely, which is the only reason it was
noticed.** 4A-(a)'s lesson was *work in bytes, not text*; this session's addition
is that **working in bytes is not enough if the bytes are hardcoded** — the
harness now DETECTS the file's line ending and translates the anchor, and
ANCHOR-NOT-FOUND is a failure, never a skip. Re-run after the fix: **5/5, every
restore byte-identical.**

All three were found by running the thing, not by reasoning about it.

---

## 6. Guards and controls

- **`tests/test_floor_truth.py` — 42 tests, all green.** Holds the founding pair
  as a regression, the premise test that `assess` really does produce a lockless
  BOXED_IN, the UNDECIDABLE-contradicts-nothing clause, the driver set's
  membership against the real `DriverCode` vocabulary, and W6's absence
  assertions.
- **5 negative controls proven RED**
  (`tools/spikes/teaching_graft_e/negative_controls.py`), each asserting the
  guard was GREEN AT HEAD before reverting, **every restore byte-identical by
  sha256**. Works in BYTES, never text — this repo mixes line endings per file
  (`claim_verifier.py` LF, `renderers.py`/`interpreter.py` CRLF) and 4A-(a)'s
  harness lesson is on the read as well as the write.
- **Suites, both measured on THIS tree.** Baseline at HEAD (session work stashed,
  same checkout — a worktree would be wrong here, since the editable install
  would still import the edited source, (d.1)'s recorded mistake):
  **2693 passed / 305 skipped / 0 failed** in 14m02s. After:
  **2735 / 305 / 0** in 15m01s, **unchunked**. **+42 passed exactly**, and
  collection confirms it independently (3040 vs 2998 with the new file ignored =
  42). **No residual.**
- **Five pre-existing test bodies were not touched**; one test HELPER was
  (`test_general_knowledge_claims._render` now clears the session, because since
  W6 "first answer of a conversation" is a claim the product reads and those
  renders share one session id against a process-wide memory).

---

## 7. Minted / untouched

- **MINTED NOTHING.** `_data` unchanged; both pinned boards untouched and not
  read. The fenced world was solved read-only; no negative control mutated a
  dataset this session (the controls revert SOURCE, not data).
- **Cockpit UNTOUCHED, not re-run.**
- Live measurement used the fenced world `_ai_exam_scratch/mobility_pinned` only.

---

## 8. NOT FIXED, named

**(a) THE (iii) MAP IS ONE FLOOR AND ONE SENTENCE SHAPE.** A paraphrase outside
the two measured constructions ships. There is no general check and building one
means building the judge R-EX1 refused. The next floor's entry costs one authored
tuple plus its own false-positive census; **the census is the expensive half.**

**(b) THE DROP CAN EMPTY A TEACHING ANSWER.** Measured live: one Q9 run cut every
claim and collapsed to the capability card — *"I couldn't answer that one from
the evidence"* — which is honest and useless. Rule 15 is what prevents it and the
seam is the floor under it; but **the failure mode is real and rule 15 is a
prompt, so it will not always hold.** No floor was built for "the seam cut
everything on a teaching question", and whether one is owed is unruled.

**(c) W2 IS CLAIM-SCOPED.** A mobility assertion in claim N and the entity in
claim N+1 is not caught — the founding specimen happens to carry both in one
claim. Widening to answer scope means deciding which claims a mobility assertion
governs, which is an authorship question, not a seam one.

**(d) THE (ii) FLOOR READ IS NOT FREE** and is paid per named order (capped at 3)
on any claim asserting free mobility. On the fenced world that is milliseconds;
on a 386-bar board each `mobility_verdict` is a blocker analysis, and nobody has
measured it at demo density.

**(e) W4 STATES A DISAGREEMENT IT CANNOT RESOLVE.** That is the ruling — this
product genuinely cannot tell which reading the solver acted on — but it means a
planner now reads two paragraphs where they used to read one confident sentence,
and whether the counterfactual or the record should LEAD is not decided.

**(f) THE EXAM BANK STILL CANNOT GRADE THIS.** The C9 pair is a regression in a
unit test, not in a sweep, because the grammar has no way to say *"this sentence
must not be the same claim as that one"* and no expectation can reference an
earlier turn's content. **This is a third Q7-input line for the ladder session's
format work** (R-EX2, relational expectations), alongside (d.1)'s missing-world
finding and the census micro-session's.

**(g) THE TEACHING SWEEPS WERE NOT RE-RUN.** Non-regression is asserted by the
2735/305/0 suite and by the 485-line precision census over the committed sweep
CORPUS, not by re-sweeping live. A re-sweep would measure the v9 prompt, which is
worth doing and is a separate measurement.

**(h) Q3 (teaching persistence) REMAINS OPEN** and was out of scope by the
brief's own wall, as were F1/F2, the certificate contract (S-02/S-03), and the
rolling-child accept defect.

**Parking lot, one line each:** `dev_cockpit.ps1` solves when it should also be
able to just serve — a `--serve-only` mode or a separate script (R4). The
accidental registry mints `ab695e51` / `65beb694` want a sweep; no one-command
cleanup exists today (R4).

---

## 9. What a summary would undersell

That **both sentences in the W4 specimen are true.** The temptation is to read
"nothing was holding it back" beside "CAPACITY_BLOCKED" as a bug — one of them
wrong, delete it, done. Neither is wrong. They are different propositions
computed by different machinery, and the product had no way to say so, so it said
both flatly and let the planner discover the contradiction. The fix is not a
correction; it is the product learning to admit that two of its own instruments
disagree. That is a harder thing to build and a much harder thing to write, and
it is the shape most of this session's work took.

And that **the founder was satisfied.** Every other defect in this repo's history
was found by someone noticing something wrong. This one was found by an
instrument built on purpose to catch the case where nobody notices — and it
worked on its first run. The C9 axis paid for itself in one round.

# Session 4A teaching-graft (c) — the exam learns to grade understanding

**2026-08-04. R1 item 2, session (c) of four.** docs/07 v2.90, §5a.170-176;
docs/04 2026-08-04 **R-SW1 and R-EX1 ruled and BUILT**. Contract unchanged
**1.15**; no docs/06 doorway owed; **both governed prompts UNCHANGED** (parse
v18, synthesis v7). RUBRIC gains axis **C9 DOES THE ANSWER TEACH?**

This session builds no ruling about how the product answers. It builds the two
things four prior sessions had owed and deferred — a world in which the
unobserved verdicts exist, and an exam axis for the thing the graft was for —
and then reports what they measured, including the parts that are unflattering.

---

## 1. Housekeeping: session (b)'s SUITE_LINE, and the two tests nobody can find

Session (b) shipped `docs/closeouts/4a-teaching-b-depth-license.md` §9 with the
literal placeholder `SUITE_LINE`. It is filled: **2631 passed / 291 skipped / 0
failed** in 1399s, measured by this session against (b)'s tree with nothing of
its own added yet.

**IT DOES NOT MATCH THE NUMBER (b)'s CLAUDE.md STATUS LINE CARRIES,** which reads
**2629/291/0 (+48)**. Two tests, unexplained. Both figures are now in the (b)
close-out and neither has been quietly picked over the other: the placeholder
existed precisely because no run against frozen bytes had been taken when that
close-out was written, and a count that moves between two runs of one tree is a
fact about the harness worth keeping. **This session measures its own delta from
2631.** Acceptance 6 of session (b) is met.

---

## 2. The fenced world — and why no board could ever have shown these verdicts

`mobility_premise.assess` returns five verdicts. 4A.x censused both pinned boards
and found two of them at zero:

| verdict | demo (386 bars) | exam (56 bars) |
|---|---|---|
| `held` | 24 | 45 |
| `later-open` | 361 | 9 |
| `undecidable` | 1 | 2 |
| **`boxed-in`** | **0** | **0** |
| **`earlier-open`** | **0** | **0** |

**THE CAUSE IS STRUCTURAL AND IT IS THE FIRST THING THIS SESSION LEARNED.** Both
verdicts require `later_at` to be `None`. `later_at` is scanned over a machine's
resolved open calendar **padded a fortnight past the last placement**
(`Explainer._open_windows`). On a plant that keeps working there is therefore
*always* room later, and `later-open` absorbs every bar that is neither held nor
chunked. These two verdicts are not rare. On a plant that keeps working they are
**impossible**, and no amount of asking either pinned board would have produced
one.

So the specimen world is a plant that **stops**. `datasets/mobility_box`:

* nine orders, three machines, one facility, hand-authored in the `glass_box`
  tradition — predictions written before the solve, a test that pins them, and a
  README that says *if the solve ever contradicts a prediction, that is a
  finding; do not rewrite the prediction*;
* `BOX-01` goes down for a rebuild on **2026-01-14** and does not come back
  inside anything the analysis can see (23 closure rows to 2026-02-13; the
  padded window ends 2026-01-27);
* gate **ACCEPTED / C2 / 0 findings**; solve deterministic (`--solver-workers 1
  --solver-seed 0`), ledger **$6,160.00**, **tardiness $0.00** — nothing is late,
  so lateness is never a second explanation for any placement;
* **reproduces byte-identically across `PYTHONHASHSEED` 0 and 1** —
  `schedule.csv` sha256 `54ddd7f596a7780c…`, measured, not assumed.

Census at the world's HEAD:

```
ORD-FILL-1..5  BOX-01   later-open     earlier=could_not  later_at=2026-01-10 07:00
ORD-EARLY      BOX-01   earlier-open   earlier=chose      later_at=None
ORD-BOX  op20  BOX-01   boxed-in       earlier=could_not  later_at=None
ORD-BOX  op10  FEED-01  later-open
ORD-PACK       PACK-01  later-open
ORD-SPAN       PACK-01  undecidable

TALLY {"boxed-in": 1, "earlier-open": 1, "later-open": 7, "undecidable": 1}
```

`held` is unreachable in a monolithic solve (no frozen front, no pins) and has 24
and 45 live specimens on the rolling boards already. Named, not counted as
missing.

### 2.1 The `earlier-open` specimen's mechanism is the interesting part

`earlier-open` means *nothing prevented it and the solver chose*. That is only
producible where the earlier room exists **and costs more** — stage 2 minimises
starts subject to stage 1's cost, so genuinely free earlier room is always taken
and the verdict can never appear.

Here the five fillers are each due on the day they run, so Monday to Friday is
spoken for and moving one costs three days of tardiness; and the only other
opening before `ORD-EARLY`'s Monday is a **Saturday overtime window at a declared
1.5x premium**. Measured:

```
ORD-EARLY op10: verdict=chose  slack=2880.0  actual=2026-01-12 07:00
    release   2026-01-05 00:00
    resource  2026-01-05 00:00
    calendar  2026-01-05 07:00
    chunkfit  2026-01-10 07:00  "it needs 7h01m in one piece and BOX-01 had
                                 only 19m left when it came free at
                                 2026-01-09 18:41"
   binding: chunkfit 2026-01-10 07:00
```

### 2.2 The premise tests, and the two negative controls

`tests/test_mobility_box.py`, **25 tests**, asserts the MECHANISM per story and
never the verdict string alone — for `boxed-in`, the binding family is
*precedence* at 09:51 with the actual start at 09:52 AND `BOX-01` has no open
window whatsoever after 19:00; for `earlier-open`, the binding family is
*chunk-fit* on the Saturday with slack 2,880 AND every free window after the bar
is measurably shorter than the bar.

Two negative controls **mutate the committed dataset, re-solve, and prove the
specimen collapses**:

* delete the 23 closure rows → `ORD-BOX` op20 stops being `boxed-in`;
* delete the one `2026-01-10,added,overtime` row → `ORD-EARLY` stops being
  `earlier-open` and `chose` becomes `could_not`.

A premise test that cannot go red is a decoration.

### 2.3 The two verdicts, live and verbatim

**`boxed-in`** — `sweep_mobility_v3`, `ORD-BOX` op20 selected, *"why cant this be
moved"*. The whole answer; the last paragraph is the one that had never had a
board to render against:

> Earlier — what's stopping it:
> ORD-BOX op20 couldn't start before Tuesday 2026-01-13 09:52: op10 finishes at
> 2026-01-13 09:51.
> Before that: its release date is 2026-01-13 00:00.
>
> What pushed it, in order:
>   2026-01-13 00:00  release date [docs/05 A4] — its release date is 2026-01-13 00:00
>   2026-01-13 09:51  an earlier step [docs/05 A1/A2] — op10 finishes at 2026-01-13 09:51
>
> **Later: no opening on BOX-01 fits the whole operation after where it sits now
> either — so "can't be moved" is fair, and the reason above is the whole of it.**
> This counts free time on BOX-01 only; a move to another machine is a different
> question, and one I'd answer as a swap.

The planner who said *"this can't be moved"* about this bar is **right**, and
this is the first board on which the product agrees with them from measurement
rather than from a unit test. On the `frozen` route the family floor (4A.y,
R-FF1) says the same thing in its own shape: *"On the premise first: "can't be
moved" is fair — no opening on BOX-01 fits the whole of ORD-BOX op20 after where
it sits now, and nothing shows it could have gone earlier."*

**`earlier-open`** — `ORD-EARLY` selected, same question, **after** the fix in §3:

> **It can be moved** — nothing was holding ORD-EARLY op10 back. BOX-01 had open,
> unheld time before where it sits, so this placement was the solver's choice
> rather than the only option. Here is what that looks like.
>
> Earlier — what's stopping it:
> Nothing prevented ORD-EARLY op10 from starting earlier. Holding every other
> placement where it is, BOX-01 had open, unheld time from 2026-01-10 07:00 — the
> solver chose Monday 2026-01-12 07:00 rather than being forced into it.
>
> What pushed it, in order:
>   …
>   2026-01-10 07:00  no window long enough [docs/05 C3] — it needs 7h01m in one
>                     piece and BOX-01 had only 19m left when it came free at
>                     2026-01-09 18:41
>
> **Later: there is no room that way. No opening on BOX-01 fits the whole
> operation after where it sits now — so the only direction open to ORD-EARLY
> op10 is the earlier one above.** This counts free time on BOX-01 only; a move to
> another machine is a different question, and one I'd answer as a swap.

---

## 3. The first question ever asked of the world found a defect

`sweep_mobility_v3`, first run, `ORD-EARLY` selected, *"why cant this be moved"*:

> **It can be moved** — nothing was holding ORD-EARLY op10 back. BOX-01 had
> open, unheld time before where it sits, so this placement was the solver's
> choice rather than the only option. Here is what that looks like.
>
> …
>
> Later: no opening on BOX-01 fits the whole operation after where it sits now
> either — so **"can't be moved" is fair**, and the reason above is the whole of
> it.

Both sentences authored. Both rendered. One bar, one screen. The lead refutes the
planner's premise and the closing paragraph re-asserts it.

`TemplateRenderer._render_mobility_later` enumerated HELD, UNDECIDABLE and
LATER_OPEN and treated **everything else** as BOXED_IN — the comment above the
fall-through said so in terms. `earlier-open` had never rendered against a solve,
so nothing had ever reached it.

**TWO RENDERERS WERE BUILT FROM ONE VERDICT AND ONLY ONE OF THEM ENUMERATED IT.**
`renderers.mobility_lead_line` — the family floor, 4A.y — handles all five and
returns `None` for anything else. The in-shape paragraph handled three and
defaulted. Fixed:

* `earlier-open` gets its own branch — *"Later: there is no room that way. No
  opening on BOX-01 fits the whole operation after where it sits now — so the
  only direction open to ORD-EARLY op10 is the earlier one above."*
* `boxed-in` becomes explicit;
* **an unrecognised verdict says nothing at all** (`lines.pop()` of its own
  separator). 4B.23's fail-safe rule at the seam that was violating it: a default
  which asserted *"can't be moved is fair"* is exactly how a claim about the
  PLANT gets manufactured from a gap in OUR vocabulary.

The guard is the PROPERTY over all five verdicts: **the paragraph may say the
premise is fair if and only if the verdict says the premise holds**, parametrised
over `mobility_premise.assess`'s own output, plus a control that an unknown
verdict renders empty.

**157 EXISTING MOBILITY TESTS WERE GREEN BEFORE THE FIX AND AFTER IT.** None
covered the branch.

**AND THE CENSUS SAYS THERE IS NO THIRD SEAM.** Every site in `src/mre/` that
branches on a mobility verdict: `renderers.py:508/519/526`
(`mobility_lead_line` — all five plus a None default) and
`renderers.py:2818/2836/2846/2863/2893` (the LATER paragraph — now all five plus
a say-nothing default). `explainer.py` reads `holds`/`refutes` and asserts
nothing itself. A defect class fixed at one seam is not fixed (4B.14 §5a.34);
here it was two seams and one of them was already right.

Live after, `sweep_mobility_v3`, all eleven turns:

| bar | turns | says `"can't be moved" is fair` |
|---|---|---|
| ORD-BOX (boxed-in) | 4 | **4** |
| ORD-EARLY (earlier-open) | 4 | **0** |
| ORD-PACK / ORD-SPAN (controls) | 2 | 0 |

`sweep_mobility_v2` re-swept against the demo board: **20/20 met**, unchanged
from 4A.y — the fix moves nothing on a board where the branch cannot fire.

---

## 4. RUBRIC axis C9, and the boundary it states out loud

C8's own closing paragraph handed this axis to this session by name and declined
to reach for it. C9 asks: **after reading the answer, could the planner predict
the system's behaviour in a case the answer did not cover?**

The instrument is a **transfer pair** fired with the conversation **cleared**
between halves. Q1 is a teaching question; Q2 asks a different subject whose
answer follows from Q1's principle. Asked cold, Q2's answer is the **ground truth
about the uncovered case**, produced independently of anything Q1 said — so the
grading question is about Q1: *would a planner who read only Q1 have predicted
this?* Asked in one conversation instead, a correct Q2 would prove only that the
model can carry its own sentence forward, which is a memory property and is
session (d)'s subject. **Q2 is the answer key, not the thing graded**; a Q2 the
product cannot answer INVALIDATES its pair rather than failing it.

**Mechanical (M1–M4), and each bounded by what it does not show.** M2 in
particular checks **co-occurrence only**, and the amendment says in terms that a
green M2 is never evidence that the principle is ABOUT the instance. M3 is the
sidecar's existing `dead-door` check, reused rather than reinvented.

**Human-only (H1–H3):** is the principle TRUE of this product; does it PREDICT
Q2; could the planner predict a THIRD case.

**THE LLM JUDGE IS WRITTEN DOWN AND REFUSED.** Showing a model Q1 and Q2 and
asking whether the first predicts the second would produce a number this
afternoon. Refused for R-AI4(2)'s reason — this repo grades conversation by
reading, and a judge is a metric wearing a reader's clothes — and for one more
specific to this axis: the thing being graded is whether an explanation transfers
**to a human**; a model asked "does A predict B" scores the ENTAILMENT, and
scores it with the same weights that wrote A. A judge that shares an author with
the work is the work marking itself.

The honest instrument is the founder round, and it ships **unrun** at
`tools/spikes/teaching_graft_c/founder_round_c9.md` — ten questions, two worlds,
with a blank prediction line under every Q1 and the rule that it is filled in
before Q2 is read. Its commands were corrected mid-session after
`python -m mre.ask` turned out to have neither a selection channel nor a schedule
lookup; `tools/spikes/teaching_graft_c/ask_probe.py` is the command that works on
both worlds, and it is committed and smoke-tested.

---

## 5. The first C9 measurement, and it is a finding

`sweep_teaching_v3`, demo board, **two independent runs**:

```
routing 8/8   m1_principle 4/4   m3_real_door 4/4   m4_pair_valid 4/4
controls 2/2                     m2_attached  0/4
```

**Every one of the four transfer-pair teaching answers carried a labelled
general-knowledge principle and not one carried a single board claim.** Zero
verified, zero interpretive, zero lit bars, zero cited records — and **two of the
four made no tool call at all**.

| turn | intent | lit | rec | claims |
|---|---|---|---|---|
| 51 | teaching | 0 | 0 | gk=1 cut=3 tools=1(constraint_catalog) |
| 64 | teaching | 0 | 0 | gk=3 cut=1 tools=0 |
| 75 | teaching | 0 | 0 | gk=3 cut=1 tools=0 |
| 86 | teaching | 0 | 0 | gk=3 cut=1 tools=4(spec_lookup…) |
| 116 | teaching | 0 | 0 | ver=1 int=2 gk=1 tools=2(cost_ledger, lateness_set) |
| 119 | teaching | 5 | 4 | ver=1 int=1 gk=1 tools=1(machine_occupancy) |
| 122 | teaching | 4 | 2 | ver=1 int=2 gk=1 tools=3 |

Turns 116/119/122 are the HUNT probes and they route to `teaching` too — and they
*do* read the board. **THE DIFFERENCE IS THE QUESTION, NOT THE ROUTE.** Those
name a figure, a machine or an order, so the loop reads the plant. The transfer
probes are phrased purely generally ("an operation", "one order", "two orders"),
so it reads nothing, and any board-flavoured sentence the model then drafts is
cut by R-TG1 direction (ii) for citing nothing.

**R-TG3 GRANTS DEPTH BY INTENT AND NOTHING MAKES A TEACHING ANSWER LOOK AT THE
PLANT.** Each ruling is correct alone; together they hand the longest budget
(LONG = 8) to the answers with the least to say. On turn 51 the licence granted
eight and the answer shipped **one**.

**AND THE FAILURE MODE HAS A WORSE TAIL, MEASURED.** Asking P1's teaching
question a further four times directly, one of the four came back on the
**unanswerable floor**:

> I couldn't answer that one from the evidence. I read what I could and none of
> it grounds an answer I'd stand behind, so I'd rather say so than guess.
> I looked at: constraint_catalog.

Every claim it drafted was cut, so nothing was left to render. **Six observations
of one question: five principles, one "I couldn't answer that".** The tier is
telling a planner it cannot answer a question it answers most of the time — not a
new defect, but the same root cause (a teaching answer reads nothing, so every
board-flavoured sentence it drafts is unciteable and cut) arriving at its worst
outcome instead of its mild one.

**NOT FIXED, and the reason is the same one that kept both prompts untouched all
session:** the remedy is a synthesis-prompt change, and two of this session's
findings are about what that prompt produces. Editing it would have measured the
edit.

---

## 6. The two hunts, reported either way

### 6.1 R-TG1 direction (i) has a live specimen at last — two — and it is a coin flip

Session (a) shipped the GK-label-on-entity refusal and reported it had never
fired outside injected-output guards. Six adversarial probes mixing idiom with
named entities produced **two refusals**, both quoted verbatim:

> **A machine loaded to over 90% utilization has almost no slack, so any
> variability upstream — a late input, a longer-than-planned run, a rush order —
> has nowhere to absorb and instead pushes straight through as delay to
> everything queued behind it, which is the classic signature of a bottleneck
> resource.**
>
> → *offered as general knowledge and refused the label because it states a
> figure this run computed (90) — checked as a claim about this plan instead: no
> assertion this run's records can check*

> **Utilization near 90%+ is a widely used rule-of-thumb threshold in queueing
> and operations literature beyond which waiting times and schedule fragility
> grow sharply, because the effective buffer against variability shrinks toward
> zero.**
>
> → *offered as general knowledge and refused the label because it states a
> figure this run computed (90) …*

**IN BOTH, THE 90 IS QUEUEING THEORY'S OWN NUMBER, NOT A BOARD READING.** So the
first two live firings of direction (i) are the **conservative arm** — the
over-rejection session (a) declared it had chosen on purpose, failing toward
ordinary verification exactly as predicted. Neither claim was cut; both landed
INTERPRETIVE and shipped. The escape-hatch closure the clause was written for
still has no wild specimen.

**AND IT DOES NOT REPRODUCE.** The same probe, in the same session's sweep, did
not refuse: two runs of `sweep_teaching_v3` observed **0**. Whether the model puts
a number inside a general sentence varies turn to turn. The specimen is real and
the guard remains the real evidence.

**No prompt was weakened to produce it.**

### 6.2 The closer still has no live specimen, and the cap is a floor with no load on it

Five probes engineered to overflow SHORT = 4 — per-machine breakdowns on three
axes, *"list every distinct problem on this board, one line each, and do not
merge them"*, *"what are the five separate things going wrong"*:

```
B1 drafted=4 cut=0 deferred=0 kept=4
B2 drafted=4 cut=2 deferred=0 kept=2
B3 (routed to briefing — contracted, no synthesis)
B4 drafted=4 cut=1 deferred=0 kept=3
B5 drafted=5 cut=1 deferred=0 kept=4
```

**Deferred 0 on every one.** With session (b)'s A/B that is **eight targeted
attempts and zero firings**. Even a question that explicitly instructs *do not
merge them* comes back at four. What that implies about the cap's current
bindingness is plain: **on the shipped prompt the cap never binds, and rule 6 is
doing all of the compressing.** The cap is **left alone**, for the reason (b)'s
A/B gave — a floor is for the day the model changes — and because moving it now
would be tuning against a measurement that says it is not in the path.

Worth noting from B5: the planner asked for **five** things, the model drafted
five, one was cut, and the answer delivered four **without saying so**. A count
named in the question is a promise the answer does not track. Carried, not fixed.

---

## 7. PLANNER_DIRECTIVE has a specimen

4B.33 §5a.135(a) measured **0 `planner_edit` Decisions in 32 and in 96** across
both pinned worlds, so the driver it had just added was unreachable from any exam
question. `tools/spikes/teaching_graft_c/mint_edited_world.py` runs the **real
accept** — `planner_edit.apply_planner_edit`, the function
`POST /schedules/{id}/accept` calls — over the fenced world with a zero-move pin:

```
accepting a ZERO-MOVE pin: ORD-PACK op10 on PACK-01 at 2026-01-05T07:00:00Z
child snapshot : snap-edit-557be92cd4b8
cost delta     : 0.0
delta_abs      : None   (None under a full hold — R-DP12)
evidence index : 31 record(s), 11 decision(s)

planner_edit | PLANNER_DIRECTIVE | observed | Planner edit: pinned op bae60fca
    to ad84e0ce @ 2026-01-05T07:00:00+00:00 (+$0)
```

**IT REPRODUCES THE ACCEPT'S EVIDENCE AND NOT ITS REGISTRY BOOKKEEPING** — no
run row, no registered schedule, no lineage pins, no assembled document. Stated,
not glossed: the fenced world is monolithic and outside `_data`, like `gb_pinned`,
and what an exam grades is what the ask path testifies FROM. The lineage, the
newer-schedule banner and the picker need a registered board; that is a different
piece of work and it is §5a.176(b).

Two things measured on it live and **not fixed**: `edit-summary` voices the edit
(*"You accepted 1 edit(s) on this version (+$0 total): pinned op bae60fca to
PACK-01 — +$0 — moved 1 op(s) — by daryn@mre.local"*), and **`why-here` on the
pinned bar never mentions that a human pinned it** — it explains the placement by
release date and calendar. That is 4B.33's own named limit, now visible on a board
that actually has the Decision.

---

## 8. What the summary would undersell

**THE WORLD IS THE DELIVERABLE, NOT THE VERDICTS.** It would be easy to read this
session as "two enum values were observed". What was actually built is a world in
which a class of answer that had never executed against a solve now does — and it
found a self-contradicting answer on its first question. The `later-open`
absorption is not a quirk of two boards; it is a property of every board that
keeps working, which means every board this product has ever been demonstrated
on. There will be more branches like that one, and the only instrument that finds
them is a world built to make the rare case ordinary.

**THE HARDEST DECISION WAS AGAIN TO BUILD LESS.** The C9 measurement (§5) is a
clear, reproducible, one-prompt-line fix: tell the synthesis prompt that a
teaching answer must read the board. It was not taken, because the same prompt is
what §5 and §6.2 are measuring, and a session that edits its own instrument
reports on the edit. Session (b) refused to wire the teaching markers to routing
for the same reason; this is that discipline applied to a change that would have
looked like an improvement.

**THE M2 CHECK IS DELIBERATELY WEAKER THAN THE THING IT IS NEAR.** It would have
been easy to write a check called "the principle is attached" and let a green
result stand as evidence that it is. What it actually reads is whether two kinds
of claim appear in one answer. The RUBRIC says so in terms, twice, because a
check whose name over-claims is the same defect class as an answer whose marker
does — and this repo has now found that one six ways.

**THE HUNT RESULTS ARE HALF A NEGATIVE AND THAT IS THE POINT.** One hunt found
its specimen and the specimen turned out not to reproduce; the other found
nothing across eight attempts. Neither was pursued by weakening the artifact that
would have produced it. A session that reports "found it" for one and "did not
find it" for the other, with the same effort behind both, is what makes either
statement worth reading.

---

## 9. Numbers

- **Python: 2643 passed / 305 skipped / 0 failed** (1614s, default mode
  `python -m pytest -q`), against this session's corrected session-(b) baseline
  of **2631/291/0** measured the same way. **+12 passed and +14 skipped, and
  `tests/test_mobility_box.py` collects 25** (12 fast, 13 slow) — so one skip in
  that delta is not this session's and is unaccounted for. Recorded rather than
  rounded off: this is the second count discrepancy the session met (see §1), and
  a suite whose skip count moves under it is worth someone's attention.
- **`--runslow` IS NOT GREEN, AND IT IS NOT GREEN AT HEAD.**
  `tests/test_ai_voice.py::TestAuditCorpusClean::test_cu5_split_jobs` fails —
  *"are there any split jobs"* is routed to `inventory` by the live parse and the
  answer never says "split". **Proven pre-existing** by reverting this session's
  only `src/` change and re-running (still red; the restore was byte-identical by
  sha256). Recorded, not fixed: it is a routing/parse outcome and this session
  changed neither prompt.
- **One `src/` change, one file:** `renderers.py`,
  `_render_mobility_later` — one new branch, one made explicit, one fail-safe.
- **Negative controls: 3, all proven RED against the mechanism they guard.** Two
  mutate the committed dataset and re-solve (the outage rows; the overtime row);
  one is the unknown-verdict control, which renders the boxed-in copy before the
  fix and nothing after it.
- **Sweeps, all committed at `tests/ai_exam/sweeps/2026-08-04-teaching-c/`:**
  * `sweep_mobility_v3` — the fenced world, 11 turns, **routing 10/10**, both new
    verdicts live. The **PRE-FIX** transcript is kept beside it as the specimen of
    the defect in §3.
  * `sweep_mobility_v2` — re-swept against the demo board, 21 questions,
    **20/20**, dark-evidence 2 (the known pair).
  * `sweep_teaching_v3` — two runs, 16 turns each. Run 2 is the graded one;
    run 1 is kept because its grader had a pair-matching bug (M4 0/4) and its
    hunt counts are an independent sample.
  * `hunt-specimens.txt` / `hunt-records.json` — the standalone hunts, 11 probes.
- **Cockpit: UNTOUCHED, not re-run.** No `src/cockpit/` file changed.
- **Minted worlds — permanent vs disposable.** PERMANENT (committed):
  `datasets/mobility_box` (the dataset). REBUILDABLE FROM IT, gitignored:
  `_ai_exam_scratch/mobility_pinned` (snapshot `snap-mobility`) and
  `_ai_exam_scratch/mobility_edited` (child snapshot
  `snap-edit-557be92cd4b8`). DISPOSABLE: every world the negative controls solve
  into pytest tmp dirs. **NOTHING WAS MINTED IN `_data`** — no registry run, no
  registered schedule, and both pinned boards are untouched.
- Governed artifacts: **parse prompt v18 and synthesis prompt v7, both
  UNCHANGED.** Corpus index rebuilt (docs/04 and docs/07 amended).

---

## 10. Carry-forwards (docs/07 §5a.176)

**(a) THE TEACHING ANSWER READS NOTHING** — §5, the sharpest item left standing.
**(b) THE FENCED WORLD IS NOT REGISTERED** — invisible to the cockpit and every
rolling surface; `held` and R-F1 are unreachable on it by construction.
**(c) `edit-summary` PRINTS A TRUNCATED OPERATION UUID** where every other
planner surface prints an order and an op number.
**(d) *"why is ORD-PACK pinned"* ON THE EDITED WORLD** answers *"this isn't a
rolling schedule, so nothing is frozen"* — true of the frozen front, silent about
the pin the same run recorded.
**(e) THE HUNT-A SPECIMEN IS A COIN FLIP** — §6.1.
**(f) A COUNT NAMED IN THE QUESTION IS NOT TRACKED** — §6.2, B5.
**(g) `_open_windows`' FORTNIGHT PAD IS WHAT MAKES `later-open` UNIVERSAL** and
is unexamined. It is a reasonable scan bound, and it is also the reason a real
plant's last week before a shutdown reads as freely movable. Named, not ruled.

**Session (d) — multi-turn — is untouched by this session, as briefed.**

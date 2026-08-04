# FOUNDER LISTENING ROUND — C9: does the answer TEACH?

**Prepared by Session 4A teaching-graft (c), 2026-08-04. NOT RUN by the session.**

This is a script for Daryn to run, not a result. The session that wrote it did
not simulate it, did not predict its outcome, and does not have an entry in any
close-out saying how it went. RUBRIC axis C9 says why: the mechanical half of
C9 is graded by a script and the rest is graded by a person reading, and the one
part nobody may automate is **whether an explanation transferred to a human**.
An LLM judge would produce a number today and it would be the work marking
itself. This is the honest instrument instead.

Budget: **10 questions**, two boards, about 30 minutes.

---

## Before you start — the one rule that makes this measure anything

For every PAIR below, **write down your prediction after reading Q1's answer
and before reading Q2's**. One line is enough. If you read Q2 first, or read
both and then decide what you would have predicted, the round measures nothing:
hindsight makes every explanation look sufficient. That failure mode is the
entire reason this is a script and not a conversation.

There is a blank prediction line under each Q1. Use it.

---

## Setup

One command per question. It clears conversation state first, so every
invocation is a cold turn:

```
python tools/spikes/teaching_graft_c/ask_probe.py --run rolling-db5395dc-2ae "<question>"
```

`--select ORDER[:MACHINE[:SEQ]]` supplies the board selection that clicking a
bar would send. (`python -m mre.ask` is NOT the command for this round — it has
no selection channel and cannot resolve a schedule id. The cockpit can do both
for a registered board and cannot show the fenced world at all, which is a
monolithic run outside the registry. That is why this script exists.)

Two worlds:

* **THE DEMO BOARD** `rolling-db5395dc-2ae` — 386 bars, real density. Q1–Q6.
* **THE FENCED WORLD** `_ai_exam_scratch/mobility_pinned` (snapshot
  `snap-mobility`) — nine orders, three machines, built this session so the two
  mobility verdicts that had never been observed have a specimen. Q7–Q10.
  Build it with:

```
python -m mre --submission datasets/mobility_box \
    --out _ai_exam_scratch/mobility_pinned --snapshot-id snap-mobility \
    --solver-workers 1 --solver-seed 0 --time-limit 600

python tools/spikes/teaching_graft_c/ask_probe.py \
    --out-dir _ai_exam_scratch/mobility_pinned --snapshot-id snap-mobility \
    --select ORD-EARLY:BOX-01:10 "<question>"
```

Read `datasets/mobility_box/README.md` **after** the round, not before — it
tells you the answers.

---

## PAIR 1 — mobility (demo board)

### Q1
> what generally decides whether an operation can be moved earlier on a board like this one

**What to listen for**
- Does it name the *kinds* of thing that hold a bar (a previous step, the
  machine being busy, the calendar, a minimum piece size, a commitment), or does
  it only tell you about one bar?
- Does a principle appear at all, or is every sentence a fact about this board?
- If it hands you a rule, does the rule sound like it is about **our solver**, or
  about scheduling in the abstract? (A plausible sentence that misdescribes what
  this product actually computes is a DEFECT, not a style miss — RUBRIC C9/H1.)

**Your prediction for Q2, written BEFORE you read it:**

    ______________________________________________________________

### Q2
> why cant ORD-000128 op20 start earlier

**Grade the PAIR, not Q2.** Would someone who had read only Q1 have predicted
this? If Q1 gave you a list and Q2's reason is on it, that is transfer. If Q2's
reason is something Q1 never mentioned, Q1 taught you an incomplete model and
the gap is the finding.

---

## PAIR 2 — propagation (demo board)

### Q1
> in general, why does one order running late tend to make other orders late as well

**What to listen for**
- A mechanism, not a sentiment. "Delays cascade" is a restatement; "a machine
  with one eligible lane serialises everything routed to it, so the second order
  waits for the first regardless of its own due date" is a mechanism.
- Is the general sentence **attached** to this board — can you see the mechanism
  operating in something it names?

**Your prediction for Q2:**

    ______________________________________________________________

### Q2
> why is ORD-000112 late

---

## PAIR 3 — contention (demo board)

### Q1
> how does a scheduler decide which of two orders competing for the same machine goes first

**What to listen for**
- Does it distinguish *what the objective prices* from *what the constraints
  forbid*? That distinction is the one a planner needs to predict anything, and
  it is the one most easily lost.
- Does it claim a priority rule this product does not have?

**Your prediction for Q2:**

    ______________________________________________________________

### Q2
> why is ORD-000252 on CUT-01 when it is

---

## Q7–Q10 — THE FENCED WORLD (`_ai_exam_scratch/mobility_pinned`)

This board exists so that "this can't be moved" has one bar where it is **true**
and one where it is **false**, and the difference is small enough to hold in your
head. Nine orders. `BOX-01` goes down for a rebuild on Wednesday 14 January and
does not come back.

### Q7 — the bar that really is stuck
> `--select ORD-BOX:BOX-01:20` — **why cant this be moved**

**What to listen for**
- Does it **agree with you**? The premise is true here. An answer that
  "corrects" a true premise is a defect.
- Does it tell you *both* reasons — the step before it, and the machine
  shutting — or only one?

### Q8 — the bar that is not stuck
> `--select ORD-EARLY:BOX-01:10` — **why cant this be moved**

**What to listen for**
- It should tell you the bar CAN move, and **which way** — earlier only.
- **This is the turn that found a bug the day the board was built.** Before the
  fix, the answer opened *"It can be moved"* and closed *"so 'can't be moved' is
  fair"*, about one bar, on one screen. Read the whole answer, not the first
  line. Do the two ends still agree?

### Q9 — the transfer question, with a knowable answer key
> what makes a job impossible to move at all

**Your prediction:** having read Q7 and Q8, write down what you expect this to
say — then read it.

    ______________________________________________________________

**What to listen for**
- Does it give you the rule (**both** directions have to be shut), or does it
  list this board's two bars?
- Could you now look at a THIRD bar and say which kind it is before asking? That
  is C9/H3 and it is the axis's actual subject.

### Q10 — the one that should be short
> `--select ORD-PACK:PACK-01:10` — **why cant this be moved**

**What to listen for**
- Nothing dramatic. This is the ordinary case (there is room later). If this
  answer is as long as Q9's, depth was spent because it was available rather
  than because it was asked for — C8b, from the other side.

---

## What to write down at the end

Three lines, no more:

1. Of the four predictions you wrote, **how many did the product's own answer
   match**? (This is the round's headline. It is not a score out of four — with
   four pairs it is an anecdote — but a 0 or a 4 is worth knowing.)
2. **Did any answer state a principle that is FALSE of this product?** Quote it.
   That is a DEFECT-bucket item and it outranks everything else on this page.
3. **After Q9, could you classify a bar you had not asked about?** Yes/no, and
   what you would have needed.

Hand those three lines to the next session. They are the calibration; the
transcripts are not.

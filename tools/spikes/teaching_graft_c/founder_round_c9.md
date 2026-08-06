# FOUNDER LISTENING ROUND — C9: does the answer TEACH?

**Prepared by Session 4A teaching-graft (c), 2026-08-04. NOT RUN by the session.**

> **HISTORICAL as of 2026-08-06 (W2.3). Deliberately NOT re-pointed at the gen-3
> demo board `rolling-9fdee7aa-ec5`.** This round's board is `rolling-c32a6140-b6b`,
> which is still pinned and still reproduces; re-pointing a protocol after its
> round is a rewrite of the record, not maintenance. A future C9 round writes
> its own file.

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
python tools/spikes/teaching_graft_c/ask_probe.py --run rolling-c32a6140-b6b "<question>"
```

`--select ORDER[:MACHINE[:SEQ]]` supplies the board selection that clicking a
bar would send. (`python -m mre.ask` is NOT the command for this round — it has
no selection channel and cannot resolve a schedule id. The cockpit can do both
for a registered board and cannot show the fenced world at all, which is a
monolithic run outside the registry. That is why this script exists.)

Two worlds:

* **THE DEMO BOARD** `rolling-c32a6140-b6b` — 386 bars, real density. Q1–Q6.
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
Whether an operation can move earlier is generally decided by four things together: its predecessors finishing in time (precedence and any min/max lag), the machine having open capacity at the earlier time, the operation's eligibility/setup match for that slot, and any pin or frozen constraint holding it in place.  [general knowledge — how scheduling works in general, not a fact about this plan]
On PAINT-02, ORD-000206's paint operation runs 2026-02-02 17:25 to 19:00 and is preceded by only a 15-minute gap after ORD-000222 ends at 17:10 — that gap is fully open capacity (idle_open_minutes_before 15), so there is no slack there to pull the operation earlier without first opening space upstream on the same machine.  [synthesis — read from: e3dc5dec, dbe7e153, a740525e]
PAINT-02 overall is at 57.3% utilization (8236 working minutes against 14377 open capacity minutes) across the plan, so the machine has open time elsewhere on its calendar, but the specific slot immediately before ORD-000206's operation is already packed.  [synthesis — read from: d9cc6ac1]
The real constraint on moving ORD-000206's PAINT-02 operation earlier is not the machine's average load but whether an actual open slot exists before 17:25 on 2026-02-02 that also comes after its CUT-01 operation finishes (2026-01-15 17:00) and satisfies its PAINT_BLUE setup family — the board shows the gap right before it is already open capacity fully used, meaning any earlier move needs a different, further-back slot rather than squeezing this one. (based on the 60 row(s) lateness_set returned, not the whole plan)  [synthesis — read from: 849c0ff5, 5efee06d, a740525e]
**Your prediction for Q2, written BEFORE you read it:**
there must be time available or another machine in which it can go on. otherwise it must change places with an existing operation
    ______________________________________________________________

### Q2
> why cant ORD-000128 op20 start earlier

**Grade the PAIR, not Q2.** Would someone who had read only Q1 have predicted
this? If Q1 gave you a list and Q2's reason is on it, that is transfer. If Q2's
reason is something Q1 never mentioned, Q1 taught you an incomplete model and
the gap is the finding.
testimonytestimony
ORD-000128 op20 couldn't start before Tuesday 2026-01-13 16:09: op10 finishes at 2026-01-13 16:08.
Before that: its release date is 2025-12-04 00:00.

What pushed it, in order:
  2025-12-04 00:00  release date [docs/05 A4] — its release date is 2025-12-04 00:00
  2026-01-13 16:08  an earlier step [docs/05 A1/A2] — op10 finishes at 2026-01-13 16:08

Not weighed here (docs/05): B3/B5 secondary and cumulative resources (tools, operator pools); B7/B8 sequence-dependent changeover; C4 time-window operation restrictions; F3 SameResource linkage.
[rendered by: template — authored copy — rendered verbatim | register: testimony]
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
ynthesissynthesis
No contracted answer covers that one, so this is me reading the evidence directly — each line below says what backs it.

One order's lateness pushes into others mainly because they share the same downstream machine: once that machine's calendar fills up, an order arriving late for its slot there has to wait for the next open slot, which is usually already booked by other orders.  [general knowledge — how scheduling works in general, not a fact about this plan]
On PAINT-02, operations are packed close together — most show only 0 to 15 minutes of open capacity before they start — so there is little slack anywhere on that machine to absorb a late-arriving job without pushing something else back. (based on the 60 row(s) lateness_set returned, not the whole plan)  [synthesis — read from: d9cc6ac1]
ORD-000206 shows this directly: its cutting operation on CUT-01 finished 15 January, but its paint operation on PAINT-02 is not scheduled until 2 February — a large gap between the two operations that leaves the order 55,860 minutes late against its 25 December due date.  [synthesis — read from: a740525e, 440fbc69, d9cc6ac1]

Where a line is marked general knowledge it draws on how scheduling and plants behave generally — not on this plan's records, so there is nothing here to check it against.

Part of what I drafted was neither something I could check against your board nor general scheduling knowledge, so I left it out rather than state it with a label that would have been wrong either way.

That is how it works in general — you know this plant and I don't, so if any of it doesn't match what you see here, say so and I'll look at what your board actually does.
[rendered by: synthesis (claude-sonnet-5) — 3 tool call(s) | register: synthesis]
**Your prediction for Q2:**
because of the nature of serial operations
    ______________________________________________________________

### Q2
> why is ORD-000112 late
testimonytestimony
ORD-000112 finished 27060 minutes (451.0h) past its due date (2026-01-11T23:59:59Z) [record: c34667f1...]. It couldn't start until 2026-01-28 07:00 because CUT-01 was held by ORD-000252 until 2026-01-27 19:00 [record: 22bed92e...].

My take: pull ORD-000252's start earlier on CUT-01, or accept the 27060 minutes late — nothing else frees this slot.
[rendered by: LLM (claude-haiku-4-5-20251001) | register: testimony]
lit 2 bar(s) · on: CUT-01, PAINT-01 · alternatives weighed: CUT-02, CUT-03
---

## PAIR 3 — contention (demo board)

### Q1
> how does a scheduler decide which of two orders competing for the same machine goes first

**What to listen for**
- Does it distinguish *what the objective prices* from *what the constraints
  forbid*? That distinction is the one a planner needs to predict anything, and
  it is the one most easily lost.
- Does it claim a priority rule this product does not have?
On this plan a scheduler (the solver) never leaves two orders literally competing for a machine — it resolves the conflict up front into a strict one-after-another sequence, as seen on CUT-01 where ORD-000209 runs 2026-01-05 07:00-08:40 and ORD-000063 starts immediately after at 08:40, with no overlap.  [record: e01f48d8...]
Generally, when two operations compete for the same machine, a scheduler orders them using a mix of hard constraints (release dates, due dates, precedence, calendars) and objective-driven tie-breaks (which order minimizes total tardiness, setup cost, or keeps the tightest-due order from slipping) — this is a sequencing decision the optimizer makes for every machine, not something worked out order-by-order by a human.  [general knowledge — how scheduling works in general, not a fact about this plan]
So the practical answer for a planner: the two orders' relative order on a machine is not a free choice you make per pair — it falls out of the whole schedule's optimization given due dates, release dates, precedence and setup costs, and the disjunctive-capacity rule guarantees the machine only ever does one of them at a time, exactly as CUT-01 shows.  [synthesis — read from: 23c8ac93, 150c5ea6, 7ed22bf5]

Where a line is marked general knowledge it draws on how scheduling and plants behave generally — not on this plan's records, so there is nothing here to check it against.

That is how it works in general — you know this plant and I don't, so if any of it doesn't match what you see here, say so and I'll look at what your board actually does.
[rendered by: synthesis (claude-sonnet-5) — 3 tool call(s) | register: synthesis]
**Your prediction for Q2:**
based on whats more important and more efficient for the entire order population
    ______________________________________________________________

### Q2
> why is ORD-000252 on CUT-01 when it is
synthesissynthesis
I couldn't answer that one from the evidence. I read what I could and none of it grounds an answer I'd stand behind, so I'd rather say so than guess.
I looked at: entity_vocabulary, placements_for_order.

Here's what I can do that's closest:
  - check which machine ORD-000252 is on, and how that machine was chosen
  - show when ORD-000252 starts and finishes
[rendered by: synthesis (claude-sonnet-5) — 2 tool call(s) | register: synthesis]
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
because there is not ime and it must finish before the next operation
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

# Session 4A.y — the floor is family-scoped

**2026-08-03.** The founder listening round the docket owed. Five specimens, one
seam. Rulings **R-FF1 through R-FF4** are verbatim in `docs/04-design-history.md`
(2026-08-03); the roadmap entry is `docs/07-roadmap.md` v2.86, §5a.153-158.
Contract unchanged at **1.15**; parse prompt unchanged at **v17**; no docs/06
doorway owed.

**No child was minted, no board was re-solved, both pinned worlds are
untouched.** (Standing clause, 4B.35.)

---

## 1. The seam, stated once

The listening docket (4A.x) built the mobility premise check and wired it to
`why-here`. Its own closing paragraph named the limit — *"The premise check is
scoped to `why-here`"* — and filed it as a carry-forward. That reading was too
generous to itself. **The check was not scoped to a route by choice; it was
scoped to a route because that is where its four specimens happened to land.**
And which route a mobility question lands on is a MODEL's decision, made per
turn, sensitive to the conversation before it.

So the docket did not build a floor. It built a floor under one door of three.

Everything below follows from that, including the two findings the brief did not
ask for: the disclosure the docket added had **never been rendered in the
cockpit at all**, and the premise check that has existed since 4B.13 was
**verifying at a different grain from the one the answer asserted**.

---

## 2. The census that is the ruling

Eighteen phrasings a planner might type, run through the **live parse** against
the demo board `rolling-db5395dc-2ae` with ORD-000128 op20 selected. Each row is
one real ask through `_answer_question` — the same seam the API's `/ask` calls.

| | reached | premise check at HEAD | after |
|---|---|---|---|
| `why-here` | 11 | 6 | **11** |
| `frozen` | 5 | **0** | **5** |
| `what-would-change` | 2 | **0** | **2** |
| **total** | **18** | **6** | **17** |

**Twelve of eighteen mobility questions got no premise check at HEAD.** Six
failed the VOCABULARY, six failed the ROUTE SCOPE — and *"why is this bar pinned
down here"* failed **both**, which is the reason neither item alone would have
been enough and the reason they are one session.

The eighteenth, after, is `jammed`. It is excluded by ruling, not by oversight —
see §6.

---

## 3. The five specimens, measured at HEAD

### F1 — route bypass. REPRODUCED, on the route the founder saw.

```
Q: why cant ORD-000128 op20 be moved          [ORD-000128 op20 selected]
route: what-would-change
A: ORD-000128 op20 is held at 2026-01-13 16:08 by an earlier step [docs/05 A1/A2].
   To move it earlier, one of these has to change: …
```

Every word true, and the premise is false: MILL-01's next opening long enough for
the whole operation is **2026-01-23 16:21**. No correction, no disclosure, one
direction. *"This cant move can it"* reproduces it identically.

**Honest limit, recorded rather than glossed:** the founder's own phrasing
(*"why cant this be moved"*) routed to `why-here` in all four history
reconstructions I attempted, so **the exact transcript that produced their
routing did not reproduce.** The CLASS reproduces deterministically on two other
phrasings. The specimen is confirmed; the transcript is not, and nothing here
claims otherwise.

### F2 — the grain-blind premise. Worse than reported.

```
Q: why is ORD-000126 op30 on CUT-01
A: ORD-000126 is on CUT-01 because it was the cheaper option once every cost
   was weighed.
   This is about op30 on CUT-01; the evidence below is that step's own
   assignment decision.                                    [record: dd33a21c…]
```

op30 runs on **FINISH-01**. op10 is the step on CUT-01.

The brief called this "op10's record wearing op30's name". It is sharper than
that. **The second sentence does not imply the grain — it asserts it**, calling
another step's record *"that step's own"*. And the answer is byte-identical in
structure to the TRUE answer for op10, which I measured beside it: same lead,
same driver phrase, same scoping sentence with one number substituted. A planner
comparing the two has nothing to go on.

Two answers earlier, the same board had said — correctly — that op30 runs on
FINISH-01.

### F3 — the disclosure, gated. And a second defect underneath it.

```
Q: when does ORD-000126 op30 finish
   resolution_note: "answered for the whole of ORD-000126 — you named op30 and
                     this route answers at order level"
   rewritten:       NO
   shown:           NOTHING
```

Both renderers gate the block on `resolved_question != question`, and a grain
disclosure needs no rewrite. That is the brief's finding and it is correct.

**What the brief did not know: in the cockpit the note had never been rendered
at all.** `appendResolved` took the note and reduced it to a substring test —

```js
const src = note && note.includes("board selection") ? "  [from board selection]" : "";
```

— three words standing in for a sentence. So the listening docket's disclosure,
built and tested and quoted in its own close-out §5, **was invisible in the
product it was built for**. Those quotations came from the exam-report path.
The docket's *"nothing is broken in the product"* is corrected, twice over.

### F4 — the vocabulary. Reproduced.

`why is this bar trapped here` → `why-here`, no premise check, no disclosure.
Four siblings measured with it: *trapped*, *wedged*, *pinned down*, *nothing can
move this*.

### F5 — the cross-subject repeat. Reproduced live, in sequence.

```
1. why cant this be moved  [ORD-000128 op20]  -> answer
2. why cant this be moved  [ORD-000073 op10]  -> "Same answer as a moment ago —"
3. why cant this be moved  [ORD-000177 op10]  -> "Same answer — nothing in the
                                                  plan has moved since you asked —"
```

Three different bars. Three genuinely different answers — a held bar, a chunked
bar, an unattributable one. Two of the three opened by telling the planner
nothing had changed.

---

## 4. What shipped

- `mre/modules/interpreter.py` — `_MOBILITY_FAMILY_INTENTS`;
  `_apply_mobility_floor` / `_attach_mobility_lead` (called from BOTH dispatch
  paths); `_same_subject`; `bundle_repeat` takes the resolved subject;
  `_with_assumptions` discloses an ASSUMED direction, never over a LATER answer.
- `mre/modules/mobility_premise.py` — `states_direction` (new); five phrases and
  two words added; `jammed` and bare `pinned` excluded, each with its reason.
- `mre/modules/explainer.py` — `mobility_verdict` (the route-neutral verdict,
  one definition with `_mobility_facts`); `_verify_placement_premise` takes the
  asked grain and returns three shapes of falsehood; the binding site cites the
  asked step or nothing.
- `mre/modules/renderers.py` — `mobility_lead_line` / `apply_mobility_lead` at
  the shared delivery seam; the premise-correction renderer speaks at the asked
  grain; the `grain_unmatched` sentence.
- `mre/ai_exam/report.py`, `src/cockpit/src/askpanel.js`, `cockpit.css` — the
  disclosure ungated, and rendered verbatim in the cockpit for the first time.
- `mre/ai_exam/runner.py`, `askpanel.js` — history turns carry `op_seq`.
- `tests/test_family_floor.py` — NEW, **55 tests**.
- `tests/ai_exam/banks/sweep_mobility_v2.txt` — NEW, 21 questions. **RUN.**

---

## 5. The five specimens, re-asked live after the fix

Same board, same seam. Verbatim.

### F1 — every family route now corrects the premise

```
Q: why cant ORD-000128 op20 be moved            route: what-would-change
A: On the premise first: it can be moved. ORD-000128 op20 has room LATER — the
   first opening on MILL-01 long enough for the whole operation is Friday
   2026-01-23 16:21, computed from that machine's open calendar minus everything
   already placed on it [docs/05 C1/C2, C3]. That is where it could go, not what
   it would cost.

   ORD-000128 op20 is held at 2026-01-13 16:08 by an earlier step […]
```

```
Q: is this bar immovable                        route: frozen
A: On the premise first: it can be moved. ORD-000128 op20 has room LATER — […]

   ORD-000128 is placed, but after the frozen boundary (2026-01-06) — it sits in
   the active part of this window […]
```

Note what the lead does **not** say. `why-here`'s inline version ends *"and that
is what I've explained below"*, which is true of `why-here` and false of the
other two. The lead states the premise and stops.

Note also that the `frozen` answer carries **two grains** — the lead about op20,
the body about the order — and the lead names its own operation, which is what
makes that legible instead of ambiguous.

### The stated-direction control, unchanged and now guarded

```
Q: why cant this move later                     route: what-would-change
A: The next place ORD-000128 op20 could sit on MILL-01 is Friday 2026-01-23
   16:21 — the first opening after where it is now with room for the whole
   operation.
   Not there: a later start would run ORD-000128 straight into the next step of
   its own routing […]
```

No correction. No *"read as EARLIER"*. The planner said which way.

### F2 — corrected at the grain it was asserted at

```
Q: why is ORD-000126 op30 on CUT-01
A: ORD-000126 op30 isn't on CUT-01 — it runs on FINISH-01.

     - CUT-01     (op 10)  2026-01-13T16:08:00Z -> 2026-01-13T18:44:00Z
     - MILL-01    (op 20)  2026-01-15T07:00:00Z -> 2026-01-15T10:28:00Z
     - FINISH-01  (op 30)  2026-01-15T10:29:00Z -> 2026-01-15T13:00:00Z

   Did you mean one of those? Ask "why is ORD-000126 op30 on FINISH-01?" and
   I'll give you the cause.
```

Both controls green live: *"why is ORD-000126 on HEAT-02"* still gets the
order-grain correction in its old words, and *"why is ORD-000126 op30 on
FINISH-01"* still gets the cause.

### F3 — the note is shown

```
Q: when does ORD-000126 op30 finish
   interpreted as: (answered for the whole of ORD-000126 — you named op30 and
                    this route answers at order level)
```

### F4 — trapped

```
Q: why is this bar trapped here                 route: why-here
   note: … and about op20, the operation selected on the board; read as EARLIER
         — you didn't say which way […]
A: It can be moved — ORD-000128 op20 has room LATER: […]
```

### F5 — the sequence, and the genuine re-ask

From the exam sweep, four consecutive turns:

```
1. why cant this be moved  [ORD-000128 op20]  -> (no rider) "It can be moved — …"
2. why cant this be moved  [ORD-000073 op10]  -> (no rider) "Earlier — …"
                                                  "Later: … sits inside the
                                                   committed front [R-F1]"
3. why cant this be moved  [ORD-000177 op10]  -> (no rider) "Later: I can't tell
                                                   you. … runs in 3 pieces"
4. why cant this be moved  [ORD-000177 op10]  -> "Same answer as a moment ago —"
```

Turn 4 is the same question about the same bar. The rider is right there and
nowhere else.

---

## 6. What the summary would undersell

**THE JAMMED EXCLUSION IS THE HONEST PART OF ITEM 4.** Five of the six measured
vocabulary misses were added. `jammed` was not, and it is the one phrasing of
eighteen that still gets no premise check. A jam is a thing that happens to a
MACHINE — *"why is CUT-01 jammed"* asserts a plant fact, not a claim about a
bar's mobility — and the rule this vocabulary is held to is that every entry can
ONLY be asserting immobility. A phrase-shaped workaround (*"jammed here"*,
*"jammed in"*) would have got the census to 18 of 18 by fitting the vocabulary to
my own probe's wording rather than to the language. **17 of 18 with a reason
beats 18 of 18 with a fit.**

**THE VOCABULARY IS HALF THE GATE, AND THE BRIEF'S TRUE-NEGATIVE CONTROL PROVED
IT.** The brief asked that *"the data seems stuck in December"* not trigger the
floor. It matches the vocabulary — `stuck` is in it and has been since the
docket. What stops it is the INTENT: it routes to `data-problems`, nowhere near
the family, and there is no bar to assess. The control is therefore asserted at
the real gate, and the finding is that a keyword test asked to judge what a
sentence is ABOUT would be exactly the deterministic classifier R-AI5 forbids and
this codebase has deleted three times. **The gate is a conjunction, and only one
of its terms is a keyword.**

**THE PARSE INVENTED A DIRECTION.** The docket's headline measurement was that
the model reported `move_direction` in **0 of 5** mobility phrasings. This round
found the mirror: *"this cant move can it"* came back **`EARLIER`**. Because the
dispatch read the field as a report of what was SAID, a stated direction and an
invented one were the same value — and the check was skipped on precisely the
question it exists for. Both failures have one cure, and it is not a better
prompt: **the direction a planner stated is a property of their sentence, and
their sentence is right there.** The parse's report is still kept verbatim and
still branches the route; what moved is only who decides whether a disclosure is
owed.

**`frozen` RETURNS BEFORE THE SEAM THAT EVERY ROUTE PASSES.** The rolling intents
have their own early return in `dispatch`, ahead of both the floor and
`_with_assumptions`. So five of eighteen phrasings got no premise check **and no
disclosure of anything** — including the grain the docket had just spent a
session carrying. This is 4B.21 §5a.78's mechanism for the third time: a guard,
or a disclosure, or a floor, computed at "the one seam every route passes",
except the routes that return early. It is worth stating as a habit rather than
an incident: **whenever a session says "computed once, where every route
passes", the next question is which routes return before it.**

**THE CONTROL HARNESS CORRUPTED A FILE ON ITS FIRST RUN.** `Path.write_text`
translates newlines on Windows, so restoring an LF-ending file wrote it back as
CRLF — every line of `report.py` rewritten by the harness whose entire job is to
leave the tree as it found it. It was caught by the harness's own restore
assertion (which is why the assertion is there), repaired, and the harness made
byte-faithful. Named because the failure mode is silent in `git diff` — git
normalises on read, so the working tree was rewritten and the diff looked clean.

---

## 7. Verification

| | |
|---|---|
| Python, this tree | **2524 passed / 291 skipped / 0 failed** |
| Python, HEAD in this tree | 2469 / 291 / 0 (**+55**) |
| New guard file | `tests/test_family_floor.py`, 55 tests |
| Negative controls | **8, all proven RED** against physically reverted code; every file restored byte-identical (sha256), verified in-harness |
| Premise tests | 4 (the fixture's placements, its missing step, its verdict, and that the verdict is the SAME object `why-here` computes) |
| Cockpit | **363 passed / 4 failed of 367** — 2 the known deictic pair (red at HEAD since 4B.23), 2 the standing parallel-load flake class, **proven green 8/8 in isolation** |
| Corpus index | rebuilt twice (docs/04 and docs/07 both changed) — `tests/test_corpus.py` 22 passed |
| Exam sweep | **RUN**: `sweep_mobility_v2`, 21 questions, **20/20 expectations met**, sidecar `dark-evidence=2` |
| Minted | **NOTHING** — no child, no re-solve, both pinned worlds untouched |

**The baseline, measured rather than assumed.** The brief set the bar at 2468,
which is the docket's figure for this tree. A full run at HEAD **with this
session's product changes and before the new test file** returned **2469** — the
+1 is a test that had been collected-and-skipped becoming live, not a test added.
The final 2524 is 2469 + the 55 new guards.

**The negative controls, one line each — each names the branch class it reverts:**

| | reverted to | tests that went red |
|---|---|---|
| A | the family is `{why-here}` | 5 |
| B | the rolling branch returns before the floor | 2 |
| C | trust `move_direction` as a report of speech | 4 |
| D | verify the premise at order grain only | 3 |
| E | fall back to another step's record | 1 |
| F | the exam report gates the note on the rewrite | 1 |
| G | `trapped` / `wedged` unrecognised | 3 |
| H | compare the question text alone | 2 |

---

## 8. Carry-forwards

Full list at `docs/07-roadmap.md` §5a.158. The two a next session should take
first:

**(a) `boxed-in` AND `earlier-open` ARE STILL UNREACHABLE ON BOTH PINNED BOARDS.**
§5a.152(b), unchanged — this round did not build the specimen world where a bar
is genuinely fenced in both directions, and until someone does, two of the five
verdicts are asserted by unit test and have never been observed live. It was the
docket's own top carry-forward and it is still owed.

**(b) THE HONEST-OUTAGE FLOOR MESSAGE.** R1 item 1's last sub-item, and the only
part of that item still open. It was explicitly this session's ride-only-if-time
work; the five items consumed the session and it did not ride. The capability
floor still says *"I don't have a tool that reaches it"* when the truth is *"I
can't reach my language model — an outage, not a limit of what I can answer"*.
Three-screenshot specimen on file.

Also open, and named in §5a.158: `jammed` (by ruling); the founder's exact F1
routing not reproducing; `frozen` answering at order grain beside an
operation-grain lead; the true-negative control living at the intent gate rather
than the vocabulary; and the two cockpit flakes.

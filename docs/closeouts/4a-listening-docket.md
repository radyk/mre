# Session 4A.x — the listening docket

**2026-08-03.** Four measured specimens, one seam, one disease. Rulings R-LD1
through R-LD4 are verbatim in `docs/04-design-history.md` (2026-08-03); the
roadmap entry is `docs/07-roadmap.md` v2.83, §5a.148-152. Contract unchanged at
**1.15**; parse prompt **v16 → v17**; RUBRIC gains axis **C6**.

**No child was minted, no board was re-solved, both pinned worlds are
untouched.** (Standing clause, 4B.35.)

---

## 1. The disease, stated once

Every one of the four specimens is TRUTHFUL. Every figure in every one of them
is correct against the persisted document. All four fail a planner anyway,
because they answer a question that was not asked — and they do it wearing the
full apparatus of correctness, which is what makes them undetectable from the
outside.

That is why this session's output includes a **new rubric axis** rather than a
new check. T1–T3 cannot see any of these. C1 comes closest and does not reach:
the answers ARE responsive, just to the wrong question.

---

## 2. The four specimens, measured at HEAD

All against the demo board `rolling-db5395dc-2ae` (the Khalil board), through
the real API's `_answer_question`, template renderer, live parse.

### S1 — the grain

```
Q: why cant ORD-000126 op30 start earlier
route: why-here | conf 0.95
parse subjects: [order "ORD-000126" -> ORD-000126,
                 order "op30" -> null]        <-- the parse's own workaround

A: Answering about ORD-000126 op10 on CUT-01 — the first of its 3 operations.
   Nothing prevented ORD-000126 op10 from starting earlier. Holding every other
   placement where it is, CUT-01 had open, unheld time from 2025-12-22 07:00 —
   the solver chose Tuesday 2026-01-13 16:08 rather than being forced into it.
```

ORD-000126 op30 is on FINISH-01, 2026-01-15 10:29 → 13:00. The answer is about a
different operation on a different machine on a different day. **The bridging
sentence is the sharpest part**: it announces a fallback ("the first of its 3
operations") as though nobody had named one, when one had been named in the
question it is answering.

### S2 — the undisclosed direction, and the undisclosed grain

```
Q: why cant this be moved          [SELECT order=ORD-000128 machine=MILL-01 seq=20]
route: why-here | conf 0.92
note: resolved against ORD-000128 (from board selection)

A: ORD-000128 op20 couldn't start before Tuesday 2026-01-13 16:09: op10
   finishes at 2026-01-13 16:08.
```

Three resolutions were made. **One was disclosed.**

### S3 — the uncorrected premise

The premise of that question is false. MILL-01's next opening long enough for
op20's 140 working minutes is **2026-01-23 16:21** — computed from the same free
-time scan the blocker analysis uses. The bar can move. What cannot move is the
bar *earlier*, and nothing said so.

### S4 — one direction

Even with S2 and S3 fixed, the answer speaks about one direction of a question
that names none.

---

## 3. The census that opened each item

**Item 1 — the subject-resolution path, three seams.**

| seam | at HEAD |
|---|---|
| `ParsedQuestion` / `SubjectRef` | **no field** for an operation |
| `route_params` | **never sets `op_seq`** — not once, for any question |
| assemblers reading `params["op_seq"]` | **8** (`start-reason`, `why-here`, `what-would-change` ×2, `contested-fact`, `attribute-lookup`, `why-on-machine`, `_named_target_is_later`) |
| live suppliers | board SELECTION (5 intents, `_OPERATION_SCOPED_INTENTS`) and **2** per-route text re-scans |

**Is 4B.21 A5 the same mechanism? NARROWED, NOT THE SAME — and the answer is a
code path.** A5 gave `why-on-machine` `op_seq_in(asked_question)` inside the
assembler (`explainer.py:1601-1608`). That is a per-route recovery of a value the
dispatch never carried. The general defect — `route_params` emitting nothing —
was untouched and is what S1 rides. **A5 is closed for its route and open as a
class**; this session closes the class. (Answer to the acceptance criterion: not
the same mechanism, same disease, and the code path is named above.)

**Item 3 — premise checks at HEAD. There are two.**

| check | claim shape | route |
|---|---|---|
| `Explainer._verify_placement_premise` (4B.13) | *X is on Y* — a stated PLACEMENT | `why-on-machine` |
| `_explain_lateness_cause`'s `premise_holds` | *many orders are late* | `lateness-cause` |

Neither is about mobility. **Why this one passed through: the vocabulary is one
claim shape long, and mobility was never added to it.** `predicate_coverage`'s
three topics are the adjacent machinery and none of them is a premise — they
grade whether a named PREDICATE went unaddressed, not whether an ASSERTION is
true.

**Item 2 — stated-vs-defaulted, per field.**

| field | marks stated vs defaulted at HEAD? | disclosed? |
|---|---|---|
| subject | yes (`SubjectSource`) | **yes** |
| grain | no field at all | no |
| direction | yes (`MoveDirection.UNSTATED`) but **only on `what-would-change` / `swap-move`** | no |
| timeframe | `dropped_qualifier` (diverts, does not disclose a default) | n/a |

So the contract already had the marking for direction and simply never carried
it on the intent where it mattered, and had no marking at all for grain. **That
asymmetry is the whole of Item 2's real work.**

---

## 4. What shipped

- `mre/contracts/parse.py` — `SubjectRef.op_seq`; `ParsedQuestion.named_op_seq`;
  `MoveDirection` widened in scope (not in members) to the mobility family.
- `mre/modules/mobility_premise.py` — NEW, pure: five verdicts, the ordering
  ruling, and `asks_about_moving` (the floor).
- `mre/modules/interpreter.py` — `route_params` carries the grain (parse, then
  text); `_GRAIN_HONOURING_INTENTS`; the mobility floor; `_with_assumptions`.
- `mre/modules/explainer.py` — `_explain_why_here` takes `move_direction`;
  `_mobility_facts`.
- `mre/modules/renderers.py` — the correction lead, the labelled parts, the
  LATER half and its invitation.
- `mre/modules/parse_prompt.md` — **v17**: rule 2 gains the grain, rule 11 gains
  `why-here`.
- `mre/modules/question_parser.py` — binds `op_seq`, fail-closed.
- `mre/ai_exam/script.py` + `runner.py` — `SELECT … seq=`.
- `mre/api/app.py` — `_parse_meta` surfaces `op_seq` and `move_direction`.
- `tests/test_listening_docket.py` — NEW, 54 tests.
- `tests/ai_exam/banks/sweep_mobility_v1.txt` — NEW, 15 questions. **UNRUN.**
- `tests/ai_exam/RUBRIC.md` — **C6 PREMISE INTEGRITY** + amendment.

---

## 5. The four specimens, re-asked verbatim after the fix

### S1 — speaks about op30

```
Q: why cant ORD-000126 op30 start earlier
parse subjects: [order "ORD-000126" -> ORD-000126, op_seq: 30]   <-- one subject

A: ORD-000126 op30 couldn't start before Thursday 2026-01-15 10:29: op20
   finishes at 2026-01-15 10:28.
   Before that: its release date is 2025-12-05 00:00.
```

No bridging sentence, because nothing fell back. The live parse now puts the
grain on the order subject; the phantom second subject is gone.

### S2/S3/S4 — one answer, all three

```
Q: why cant this be moved          [SELECT order=ORD-000128 machine=MILL-01 seq=20]
note: resolved against ORD-000128 (from board selection); and about op20, the
      operation selected on the board; read as EARLIER — you didn't say which
      way, and this is the direction I can compute a bound for

A: It can be moved — ORD-000128 op20 has room LATER: the next opening on MILL-01
   long enough for the whole operation is Friday 2026-01-23 16:21. What's blocked
   is moving it EARLIER, and that is what I've explained below.

   Earlier — what's stopping it:
   ORD-000128 op20 couldn't start before Tuesday 2026-01-13 16:09: op10 finishes
   at 2026-01-13 16:08.
   Before that: its release date is 2025-12-04 00:00.

   What pushed it, in order:
     2025-12-04 00:00  release date [docs/05 A4] …
     2026-01-13 16:08  an earlier step [docs/05 A1/A2] …

   Not weighed here (docs/05): B3/B5 …; B7/B8 …; C4 …; F3 ….

   Later: there is room. The first opening on MILL-01 where the whole operation
   fits after where it sits now is Friday 2026-01-23 16:21 — computed from
   MILL-01's open calendar minus everything already placed on it, under the same
   minimum-piece rule the solver applies [docs/05 C1/C2, C3].
   That is WHERE it could go, not what it would cost. Ask "what would pushing
   ORD-000128 op20 out cost?" and I'll hold every other placement, move that one
   bar and price the difference — or drag it on the board and the card prices
   the same move.
```

### The true-premise control, live

```
Q: why cant this be moved          [SELECT order=ORD-000073 machine=PRESS-FAST seq=10]

A: [no correction]
   Earlier — what's stopping it: … (the chain, unchanged)
   Later: it can't go there either, and "can't be moved" is fair — ORD-000073
   op10 sits inside the committed front (frozen through 2026-01-06 00:00).
   Committed work is moved by moving the frozen boundary, not by moving the bar
   [docs/05 R-F1].
```

### The undecidable branch, live

```
Q: why cant this be moved          [SELECT order=ORD-000177 machine=CUT-01 seq=10]

A: [no correction]
   Earlier — …
   Later: I can't tell you. ORD-000177 op10 runs in 3 pieces, and a chunked
   operation can't be priced as a local move in either direction — the pauses are
   closures the solver placed, and shifting the bar doesn't re-derive them. That
   is a limit of what I can compute, not a statement that the plant has no room.
```

### The grain disclosure, three routes

```
"why is ORD-000126 op30 on FINISH-01"  -> why-on-machine   note: (empty — it honours the grain)
"when does ORD-000126 op30 finish"     -> order-schedule   note: answered for the whole of
                                          ORD-000126 — you named op30 and this route answers
                                          at order level
"is ORD-000126 op30 splittable"        -> attribute-lookup note: (empty)
```

---

## 6. The measurement the summary would undersell

**THE PREMISE IS FALSE ON 361 OF 386 BARS.** A census of `mobility_premise`'s
verdict over every placed operation on both pinned worlds:

| board | held | later-open | undecidable | boxed-in | earlier-open |
|---|---|---|---|---|---|
| demo `rolling-db5395dc-2ae` (386 bars) | 24 | **361** | 1 | **0** | **0** |
| exam `rolling-c362baa4-1b0` (56 bars) | 45 | 9 | 2 | **0** | **0** |

The 24 held are exactly the committed count. So *"why can't this be moved"*,
asked of almost any active bar on the demo board, was answered with an
earlier-only chain over a premise that was false — **94% of the board**. That is
not an edge case this session hardened; it is the common case.

And the other half of the same table is the honest limit: **`boxed-in` and
`earlier-open` do not occur on either board.** Both are asserted by unit test and
have never been observed live. 4B.32 §5a.132's discipline, recorded rather than
glossed.

**THE PARSE WOULD NOT CARRY THE DIRECTION — 0 OF 5.** Prompt v17 asks for it, and
five phrasings a planner actually types all returned `null` while `swap-move`,
where the field has been asked for since 4B.30, set it correctly. The model is
not refusing the field; it does not read a mobility question as a MOVE question.
**A disclosure that depends on a model remembering a field is a disclosure that
will silently stop** — which is why the floor exists and why it is not a
classifier: it runs after routing, adds a check to a route already running, and
can never route.

**TWO NEGATIVE CONTROLS DID NOT FIRE ON THEIR FIRST RUN,** and both are worth
more than the four that did.

- The uncorrected-premise control asserted the answer did not *start with* the
  chain. With the correction physically reverted it still did not — because Item
  4's own `Earlier —` label sits above it. **The control was calling past the
  broken line** (4B.28 §5a.123), found the only way that is findable: by
  reverting the fix and looking.
- The true-premise control reverted `assess`'s HELD branch, which is not the
  load-bearing half: `_mobility_facts` SKIPS the calendar scan for a held bar, so
  `later_at` stayed None and the verdict fell to `boxed-in` — no correction, test
  green, nothing proven. The effective revert is the skip.

Both rewritten; all six red.

---

## 7. Verification

| | |
|---|---|
| Python, this tree | **2468 passed / 291 skipped / 0 failed** |
| Python, HEAD in this tree | 2411 / 291 / 0 (**+57**) |
| New guard file | 54 tests, all green |
| Negative controls | **6, all proven RED** against physically reverted code; files restored byte-identical (`diff -q`, clean); 54 green after |
| Premise tests | 3 (the fixture bar really has room later; really is bound earlier; really has >1 operation) |
| Cockpit | **untouched, not re-run** |
| Corpus index | rebuilt (docs/04 changed) — `tests/test_corpus.py` 22 passed |
| Exam sweep | **NOT RUN — see §8** |

**A note on the baseline, measured rather than assumed.** CLAUDE.md records
4B.35's Python figure as 2416/291/0. This tree's HEAD (commit `2e73350`) collects
**2702 = 2411 + 291**, and a full run at HEAD — in a detached worktree with the
real `_data` junctioned in, so collection matches — returned **2409 passed / 2
failed / 291 skipped**. Both failures are worktree-path artifacts
(`test_corpus.py::test_index_matches_the_live_docs` and
`test_env_local_one_reader.py::test_anchored_to_repo_root_not_cwd`, the two tests
that anchor to a repo root a worktree resolves differently), so **the HEAD
baseline in this tree is 2411/291/0** — exactly what the first in-tree run
returned before any test file was added. The 5-test difference from 4B.35's
recorded figure predates this session: nothing here removed a test, and the only
pre-existing test file touched is `tests/ai_exam/test_runner.py` (+3).

---

## 8. What this session did NOT do

**(a) THE EXAM SWEEP WAS NOT RUN. This is the one acceptance criterion the
session did not meet, and it is not a judgement call.** The Anthropic API credit
balance was exhausted partway through the session:

```
400 invalid_request_error: Your credit balance is too low to access the
Anthropic API.
```

Every live measurement quoted in §2, §5 and §6 completed **before** that point —
the four specimens at HEAD, the four re-asks, the three branch specimens, the
0-of-5 direction measurement and both board censuses (the censuses call the
assembler directly and need no model at all). What did not run is the sweep.

`tests/ai_exam/banks/sweep_mobility_v1.txt` is committed, versioned, and
**UNRUN**: 15 questions across the four items, with graded `EXPECT` lines, both
sides of the premise guard, and the three `SELECT … seq=` specimens the exam
script could not express until this session. It parses clean (0 parse errors,
verified offline). **It is owed.** The founder-listening round the brief
requested is likewise not done, for the same reason.

**(b)–(h)** are in `docs/07-roadmap.md` §5a.152 and are not repeated here. The
two a next session should take first: **the unrun bank**, and **`boxed-in` /
`earlier-open` being unreachable on both pinned worlds** — a specimen world where
a bar is genuinely fenced in both directions is the only thing that turns those
two verdicts from asserted into observed.

---

## 9. Is 4B.21 A5 closed?

**Narrowed, and now closed as a class.** A5's own route (`why-on-machine`) was
fixed in 4B.21 by a text re-scan inside the assembler, and it worked — that route
was the one route answering a typed grain correctly at HEAD. What A5 did not do,
and did not claim to do, is carry the grain at the dispatch, which is why every
other operation-scoped route still answered about op10. That carry exists now.

**What remains open from A5's own §5a.83 is untouched:** the `why-on-machine`
lead is about ELIGIBILITY and its cited record's driver is about OCCUPANCY, so
the drill-down still shows a planner two propositions about one record. That is a
`why-on-machine` assembler question, not a grain question, and this session did
not open it.

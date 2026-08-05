# Session 4A teaching-graft (d.2) — the format, the ladder, and what a clarify eats

**2026-08-05.** **R-EX2 and R-LD6 ruled and BUILT**, plus rider R1. Contract
unchanged **1.15**; both governed prompts unchanged (**parse v18**, **synthesis
v9**) — every seam here is deterministic code or authored copy; `DriverCode`
unchanged; no docs/06 doorway owed.

One subject in three parts: **what a turn leaves behind for the next turn, and
what a bank may assert about it.**

---

## 0. The standing-law predicate audit, run FIRST — and it was not clean

The brief made a standing law of (e2) §9's lesson: *a session that has just
built a check is the worst-placed observer of what the check does not catch.* So
every predicate built in session N is run over session N's **own** artifacts in
session N+1. This session's instance —
`tools/spikes/teaching_graft_d2/predicate_audit.py` over
`tests/ai_exam/sweeps/2026-08-05-teaching-e2`, **67 claim lines, 14 general
knowledge**:

| | |
|---|---|
| `product_behavior_disqualifiers` — the **(e2)-widened** version | **0 of 14** |
| `floor_contradictions` — the (iii) map | **0 of 67** |

**And at least one of the 14 is a member of the species it was widened to
catch.** Claim 3 of `sweep_teaching_v2`, wearing `[general knowledge]`:

> *"…but a mixed-integer or constraint-based **scheduler like this one** instead
> searches globally for the sequence and assignment combination that minimizes a
> stated cost objective — so there usually is no single 'first job' rule the
> planner can point to; **the ordering is an output of the optimization, not an
> input rule it followed**."*

That asserts what THIS product does, and it is checkable — against docs/05, and
against the solver builder. It misses by a **third construction**, independent of
both of (e2)'s two widenings: the deictic is **postposed** (`scheduler like this
one`), and pattern (a) wants `th(is|e) (product|system|engine|scheduler)` — the
pointer before the noun.

**Not widened here, and that is the discipline rather than the omission.**
(e2)'s own standard is that a widened predicate **re-earns** its census; this
session held no census budget, and widening on a single specimen is precisely
the temptation that errand was written to refuse. Filed as §5a.211(a) with the
specimen quoted.

The audit took nine minutes. Its value is not that it was clean.

---

## 1. Part B — the ladder, measured before decided

The (d.0) recon found all four rungs (card > selection > last-answer > history)
**empty on all six turns** of a typed conversation, and resolution working
anyway. D-03/D-04 left open whether the ladder is dead code or a mis-wired
resolver. The brief said MEASURE FIRST. Four conversations, one per rung, each
constructed to make exactly that rung the top non-empty one
(`ladder_probe.py`, `carry_probe.py`):

| rung | construction | result |
|---|---|---|
| **CARD** | a priced move open, nothing else live | binds, `source=card`, *"resolved against ORD-000252 (from the move you have open)"* |
| **SELECTION** | a bar selected, no card | binds, `source=selection`, *"(from board selection); and about op10…"* |
| **LAST-ANSWER** | `why is ORD-000252 late` → `demand`, then a pointed follow-up | binds, `source=last-answer`, *"resolved against ORD-000252"* |
| **HISTORY** | a bar selected on turn 1, then the selection CLEARED | binds, `source=history`, *"(from earlier in this conversation)"* |

**All four rungs are reachable, consumed, and disclosed. Nothing is deleted.**

**THE FIRST L3 ATTEMPT FAILED, AND THAT FAILURE IS THE SESSION IN MINIATURE.**
It used *"when does ORD-000252 finish"*, which answers on `order-schedule` with
`subject_type="schedule"` — not one of the five the carry accepts — so the rung
stayed empty and the follow-up landed on **CLARIFY**. A planner who typed an
order one turn earlier was asked which order. That is D-03's sharpest form, and
it is the same shape as Part C's founder specimen.

A code census then settled the denominator: **45 distinct `subject_type` literals
in `explainer.py`, 5 carried** (the (d.0) dossier's "5 of 33" undercounted the
denominator, not the gap), and all five ARE emitted, by six routes. So the rung
is reachable but **narrow**, which is a different verdict from "dead".

### The outage question, answered by measurement

The brief's decision frame would keep a rung that gives *"resolution when the
parse tier is down"*. It does not. `outage_resolver_probe.py` drives the shipped
`QuestionParser(_client=…)` seam with a transport double, with the LAST-ANSWER
rung **full**:

```
T2 (model UNREACHABLE) 'why cant this be moved earlier'
   route=OUTAGE  intent='unmatched'  register=system
   subjects bound: (none)
```

R-OF1's outage floor answers before any resolution can happen. **The ladder is
not a fallback for an unreachable model and may not be described as one.** What
it does buy is DETERMINISM — P2's byte-identical answers across three
conversational positions where the selection rung binds.

### D-04 is reported as NOT a defect

`askHistory`'s order/machine come from the live board selection, not from the
turn's own subject. (d.0) filed that as silent state loss. It is a **channel
distinction**: HISTORY remembers *what the planner was looking at*; LAST-ANSWER
remembers *what the last turn was about*. Making history carry subjects would
fuse two questions into one channel — a category fusion, this repo's own named
class, five in six sessions. R-LD6 clause (4) states the contract instead.

---

## 2. Part C — the clarify-carry hypothesis: confirmed, and reframed

The founder specimen: *"why is ORD-000252 on CUT-01 when it is"* → CLARIFY; two
turns later *"why is it scheduled when it is"* → **asked WHICH ORDER**.

**The three-turn reproduction did NOT reproduce.** Turn 2 (*"is ord 252 late"*)
named the order again and answered on `late-order` → `demand`, one of the five,
so turn 3 resolved cleanly. **The intervening turn re-supplied what turn 1 had
dropped** — which is why the founder's conversation needed a turn 2 that does
not carry, and why reporting "refuted" here would have been wrong.

So it was isolated to a **held pair, one word apart**, 3 runs of 3
(`clarify_pair.py`):

| arm | turn 1 | parse bound | carry into turn 2 | turn 2's route |
|---|---|---|---|---|
| **A** | *"…on CUT-01 **when it is**"* → CLARIFY | `ORD-000252` | **`{}`** | **`why-here`** |
| **B** | *"…on CUT-01"* → `why-on-machine` | `ORD-000252` | `{order: ORD-000252}` | **`start-reason`** |

**In both arms the product resolved the order from the planner's own typing.**
The clarify's bundle truthfully renders `subject_external_name="?"` — it could
not answer — and the carry channel reads the **bundle**. So the deterministic
memory of an order the planner had just named was empty one turn later, and
**the identical follow-up sentence reached two different routes, 3 of 3**.

Arm A resolved at all only because the parse model re-read the order out of the
RECENT TURNS block. **That is the layer with nothing underneath it**, and it is
what failed in the founder's longer conversation.

**Verdict: the hypothesis is CONFIRMED at the mechanism and REFRAMED in its
consequence.** The clarify does eat the subject. What a planner sees is not
always "which order?" — sometimes it is a different answer to the same question,
which is worse, because nothing on screen says anything happened.

### The fix, at the seam the brief named

R-LD6 clause (5). `interpreter.carry_subject` — **one definition, three readers**
(the ask meta computes it, the panel reads it, the exam runner reads it):

1. the answer's own resolved subject where the bundle names one — **the shipped
   behaviour, unchanged and first**;
2. failing that, **the subject the PARSE resolved for that question** — unique
   per kind (two distinct resolved orders carry NO order), with unresolved
   siblings removed before the count is taken, so a typo beside a real id does
   not cost the planner the real id.

**Additive by construction**: clause (2) can only fill a carry that would
otherwise have been empty. That is what makes the change provable rather than
merely tested. After it, both arms carry the order and both reach
`start-reason`, 3 of 3.

**A side effect worth naming.** Re-running the recon's P2b (`p2b_after.py`), the
middle arm now binds off the **ladder** (`source=last-answer`) where it used to
bind off the model. The (d.0) dossier's headline — *"the product's cross-turn
understanding is a model behaviour wearing deterministic clothes"* — now has a
deterministic backstop under one of its two specimens. R-LD5's disclosure rule
holds on all three arms, and the true negative (an unrelated turn before the
probe) still correctly CLARIFIES, so clause (2) did not over-carry.

---

## 3. Part A — R-EX2, and the proof it was worth ruling

Three elements, all built (`script.py`, `runner.py`, `sidecar.py`, `report.py`,
`__main__.py`):

1. **`REBIND <schedule>`** as a sequence step — `main.js::onVersionChange`
   reproduced (rebind, clear the selection, touch nothing else). An unresolvable
   rebind is a loud `rebind-failed` finding and **the run stops**.
2. **Three relational forms**, 1-based within the current conversation:
   `BODY_SAME_AS` / `BODY_DIFFERS_FROM`, `RECORDS_FROM`, `RECORDS`.
3. **No prose assertions, enforced** — `EXPECT_KEYS` is closed, so a prose
   expectation cannot be written down.

Two details that are the ruling rather than the implementation:

* **`RECORDS_FROM` requires a NON-EMPTY set.** The empty set is a subset of
  everything, so a pure subset test would pass a turn that opened **nothing** —
  which is the exact defect (D-01) the form was written to catch, reported as a
  pass.
* **An unresolvable reference is a MISS, not a skip**, and **an empty body is
  UNEVALUABLE in both directions**. A bank that grades nothing must never read
  like a bank that passed.

### The headline proof

`sweep_crossversion_v1.txt` runs at HEAD — **4/4, clean**, across a real
`REBIND` between the demo board and the exam world, with the post-rebind
prove-it answering:

> *"The answer you're pointing at was about the PREVIOUS VERSION of this plan —
> the board was replaced between that turn and this one, so its records describe
> a schedule you are no longer looking at and I won't open them against this
> one."*

Then the same bank, with **R-MT1's composite store key reverted to
session-only** — the state (d.0) measured:

```
records: expected 0, got 102
```

**102 is the recon's own number.** Board A's lateness record ids served to a
planner looking at board B. The (d.1) bank's header called this *"not a missing
EXPECT key; it is a missing world"*; it is a bank sequence now, and it catches
the defect.

`sweep_relational_v1.txt` — the queued founding specimens encoded and run live —
**11/11 met, sidecar clean**, with every form carrying real values: `RECORDS_FROM`
over a non-empty set (1 record, both turns); `BODY_DIFFERS_FROM` on the
certificate pair whose two turns cite the **same four records** and so genuinely
could have been identical; `RECORDS=0` on the cold refusal; `BODY_SAME_AS` on the
deaf pair; and the founder's clarify pair in both arms.

### What R-EX2 does NOT do, stated in the bank itself

**C9's transfer pair is still not bank-expressible, by construction.** Its two
halves are separated by a cleared conversation — that separation IS the axis —
and a relational index does not cross a `RESET`. What is discharged is the
narrower (e2) §8(e) item, *"the exam bank cannot express 'these two answers must
not be the same'"*: `BODY_DIFFERS_FROM` says exactly that, within one
conversation. Across a reset it is two blocks stating the same expectation, and
block E of `sweep_relational_v1.txt` says so rather than leaving it to be
rediscovered.

`sweep_carried_state_v1.txt` is **left as it was**, with a superseded-in-part
header. It is the committed evidence that the format could not express these
things, and rewriting it into the new forms would erase the argument that got
them built.

---

## 4. Rider R1 — the fourth W4 site, sized then fixed

(e2) §8(a) named `mobility_lead_line`'s `earlier-open` branch and left it: no
driver in hand.

| world | placements | `earlier-open` | …with a blocker-naming driver |
|---|---|---|---|
| demo board `rolling-c32a6140-b6b` | 386 | **0** | **0** |
| fenced specimen world (R-SW1) | 10 | **1** | **1 — ORD-EARLY op10, CAPACITY_BLOCKED** |

**The demo board's zero is a tautology**, and the rider's rule cannot be applied
to it honestly: `earlier-open` needs `later_at` to be None, which no plant that
keeps working produces, so the numerator's SET is empty. The fenced world is the
only board where the branch renders — and there it is **1 of 1**. Every time
that sentence has rendered against a solve, it has contradicted the record
sitting beside it. So: nonzero, fix it.

**AND THE FIRST INSTRUMENT PRODUCED A FALSE ZERO.** Reading `row["driver"]` off
the enriched assignment returned `(none)` for a bar (e2) §5 quotes as recording
CAPACITY_BLOCKED. The three guarded sites read `key_facts["chosen_driver"]`
(`_first_assignment_driver`); reading what they read gave the 1. **A zero
produced by an instrument that cannot see the value is not a zero** — this
session's own standing law, caught on this session's own rider, one hour after
writing it down.

**The plumbing was not a floor change at all**: `analysis` is already an argument
to `_mobility_facts`, so the payload gains `chosen_driver` (sixteen keys) and the
site goes through the **same one definition**, in the **same arbitrated order**.
Live on the fenced world, through the real path:

> *"On the premise first: the assignment decision for ORD-EARLY op10 records its
> driver as CAPACITY_BLOCKED, which names a constraint rather than a preference.
> My own scan disagrees — BOX-01 had open, unheld time before where it sits — so
> it may be movable, but the record and my calendar scan do not agree about this
> bar, and I can't tell you which the solver acted on."*

A preference driver is silent and an unrecognised one claims nothing, unchanged.
(e2)'s tripwire fired as designed and is **replaced by the real guard**.

---

## 5. Guards and controls

* **`tests/test_relational_bank_format.py` — 53 tests, all green**, R-EX2 and
  R-LD6 in one file because they meet at one question.
* **12 negative controls proven RED** (`negative_controls.py`), each asserted
  **GREEN AT HEAD** before its seam was reverted, every restore **byte-identical
  by sha256**, working in BYTES and detecting each file's own line endings.
* **Two controls stayed green on the first attempt, and BOTH failures were the
  GUARD's, not the seam's.** One searched the whole of `askpanel.js` for
  `meta.carry_subject` and passed on the explanatory **comment**; the other
  searched `_mobility_facts`'s source text and passed on the same. Both guards
  were rewritten to read CODE — the panel's function body with comments
  stripped, and the payload's keys off the **AST**. **4B.28 §5a.123 caught in
  the act, twice, in one session**, and the only thing that caught it was
  running the control instead of trusting the assertion.
* The live control is the load-bearing one and it is **not skippable silently**:
  `--no-live` prints that the cross-version bank's ability to catch R-MT1's
  defect is UNPROVEN in that run.

### Sweeps re-run where instruments changed

`sweep_mobility_v3` on the fenced world, because the renderer changed:
**10/10 met, `ungrounded-load-bearing: 1`** — byte-for-byte the committed
`2026-08-04-teaching-c` baseline. The fixed lead renders inside that transcript
(line 192), so the sweep exercised the change and did not move.

(d.1)'s W6 / carried-state guards after Parts B and C:
`test_carried_answer_state.py`, `test_certificate_route.py`,
`test_conversational_riders.py` — **80 passed**.

### Suites

Measured on **this tree**, **unchunked**. §7 carries the numbers, the derivation
of the baseline, and the cockpit run.

---

## 6. Minted / untouched

* **MINTED NOTHING.** No schedule, no run, no snapshot, no registry row. Both
  pinned worlds were read live and never written.
* New sweep artifacts under `tests/ai_exam/sweeps/2026-08-05-relational-d2/`;
  scratch transcripts under `_ai_exam_scratch/d2/` (untracked).
* **The cockpit's `askpanel.js` WAS touched** — one function, `resolvedSubject`,
  which now reads the product's `carry_subject` first. **The cockpit suite was
  therefore run** (§7). The cockpit **rendering surface was not opened**, which
  is why rider R2 stays queued (§8(f)).
* `tools/spikes/multiturn_recon/conv.py` was updated to call `carry_subject`
  rather than hold its own copy of the rule — a harness holding its own copy of
  a rule is how the rule drifted in the first place.

---

## 7. Counts

**Baseline for this tree: 2772 passed / 305 skipped / 0 failed.** The figure
carried into the session was (e2)'s **2768/305/0**, and the maintenance commit
between them added `tests/test_claude_md_budget.py`, which collects exactly
**4** — so the baseline here is 2768 + 4, derived rather than assumed.

**After: `python -m pytest -q` → 2825 passed, 305 skipped, 0 failed** in
24m23s, unchunked.

**+53 exactly, and `tests/test_relational_bank_format.py` collects exactly 53.**
Collection confirms it independently and from the other side: **3130 with the
new file, 3077 without** — and 3077 is (e2)'s recorded 3073 plus the
maintenance commit's 4, which lands on the number without adjustment.
`test_floor_truth_e2.py` still collects **33**, unchanged: the fired tripwire
was replaced one-for-one by its real guard. **NO RESIDUAL** — nothing else
moved, in either direction.

### The cockpit suite, because `askpanel.js` was touched

**366 passed, 3 failed** on the full run. **None of the three is this session's.**

* `cockpit.spec.mjs::deictic` (light AND dark) — **PROVEN PRE-EXISTING**: it
  reproduces with `askpanel.js` stashed back to HEAD. The spec expects the
  resolved question `"why is ORD-000012 on F001-RES001?"` and gets *"why is
  ORD-000012 **placed where it is** on F001-RES001?"*, which is a rewrite-text
  expectation, not a carry one. Reported, not fixed — it is not this session's
  subject and adjusting it would be fitting an expectation to output.
* `beat_two.spec.mjs::Try again re-runs the SAME pin` (dark only; light passed
  the same test in the same run) — **did not reproduce**: the spec file re-run
  on its own **with this session's change in place** is 22/22 green. The
  standing parallel-load flake class, named rather than swallowed.

The `carriedstate.spec.mjs` pair — the specs that actually guard R-MT1's rebind
behaviour, the neighbouring seam — is **2/2 green**.

`test_corpus`'s currency guard is **green 22/22** — the corpus index was rebuilt
after the docs/04 and docs/07 amendments and **before** the suite started, which
is the ordering four previous sessions learned the hard way. Docs were not
touched while the suite ran.

**CLAUDE.md diff: +19 lines, and R-CM1 says a session adding more than ~15 says
so in its close-out.** This is that sentence. Every added line is pointer-form —
two ruling codes, two discipline lines, two table rows and a status pointer —
and one stale line was CORRECTED rather than carried (the (a)–(e2) carry-forward
row said the fourth W4 site was unfixed; it is fixed, so the row now names what
actually remains). The file stands at **35,167 characters** against the 150,000
budget.

---

## 8. NOT FIXED, named

**(a) THE PRODUCT-BEHAVIOR PREDICATE HAS A THIRD MISSING CONSTRUCTION** — the
postposed deictic, specimen in §0. Widening it needs its own census, which is
the expensive half, and widening on one specimen is what (e2) refused.

**(b) C9's TRANSFER PAIR IS STILL NOT BANK-EXPRESSIBLE**, by construction — see
§3. Written into the bank as a bound.

**(c) `RECORDS_FROM` IS A SUBSET TEST, NOT AN EQUALITY.** A turn serving a
strict subset of the referenced turn's records passes. That is right for a
drill-down opening one item of a list and wrong for a prove-it that should open
all of them, and no form distinguishes them today.

**(d) `sweep_crossversion_v1.txt` NAMES TWO SCHEDULE IDS IN ITS OWN TEXT.**
Every other bank is board-agnostic. This one cannot be, and the file says so —
but it means the bank rots the day either pinned world is re-minted.

**(e) THE CROSS-VERSION BANK PRODUCED A `validator: 1` FINDING ON ONE RUN OF
THREE** and `clean` on the others — an LLM renderer validation fallback,
run-to-run, not investigated. Recorded rather than dropped, because the number
moved.

**(f) RIDER R2, THE (d.1) DIVIDER, IS LEFT QUEUED**, and its condition is stated
rather than implied: the rider was conditional on the ask panel already being
open. This session changed one function in `askpanel.js` without opening the
rendering surface the divider belongs to, and opening a surface for a rider is
what the rider's own wording forbids.

**(g) A PRE-EXISTING COCKPIT RED, PROVEN NOT MINE AND LEFT ALONE.**
`cockpit.spec.mjs::deictic` expects a resolved question this product no longer
emits (*"placed where it is"* is now in the rewrite). It reproduces with
`askpanel.js` reverted to HEAD, so it is not this session's; and adjusting the
expectation to match today's output is exactly the move RUBRIC §(c) forbids.
Owner: whichever session owns the deictic rewrite copy.

**(h) Q3 (teaching persistence) and F1 (the term-explanation gap) UNTOUCHED** —
(d.3)'s subject, one line to the parking lot as the brief directs. Also parked:
the certificate-contract session (S-02/S-03), the one-floor (iii) map's next
entry, W2 claim-scope widening.

---

## 9. What a summary would undersell

**That the ladder was never the thing that was broken, and the fix was one rung
lower than the argument was about.** Six sessions of comments describe a
four-rung resolver; (d.0) found all four empty and concluded the ladder might be
dead. It is not dead — every rung binds, and the probe that proved the
last-answer rung works is the same probe that first failed to populate it. The
defect was never in the ladder's ORDER or its CONSUMPTION. It was in **what gets
put on the third rung**: five subject types out of forty-five, read off the
bundle, so any turn the product could not fully answer contributed nothing —
even when it had resolved the planner's order perfectly well. A summary saying
"the resolution ladder was fixed" would describe a machine that was already
working.

**That the founder's specimen was right about the mechanism and wrong about the
symptom, and both halves mattered.** The hypothesis was "a clarify eats the
subjects" and it is true. But the visible consequence in the reproduction was not
*"which order?"* — it was **the same question getting a different answer**,
3 runs of 3, with nothing on screen to say anything had happened. That is a
worse defect than the one reported, and it was only visible because the pair was
held to one word of difference. A three-turn reproduction of the founder's exact
words came back clean and would have been filed as "refuted".

**That the two negative-control failures are the session's best result.** Twelve
controls, ten red first time. The two that stayed green were both guards
watching a COMMENT or an identifier that survived the revert — a guard proving a
sentence rather than a behaviour. Nothing in the test output distinguishes such a
guard from a real one; only reverting the seam does. The repo has a named law for
this (4B.28 §5a.123) and it caught its own law being broken twice in one
afternoon, which is the strongest argument available for why the control step is
not optional.

**That the predicate audit's finding is the same shape as (e2)'s and (e)'s, for
the third session running.** (e)'s map missed its own fix's first live output.
(e2)'s widened predicate missed the sentence (e) printed as its headline
success. This session's audit found the (e2)-widened predicate missing a third
construction in (e2)'s own transcripts. Three sessions, three misses, each found
by pointing the instrument at the previous session's artifacts rather than
reasoning about the pattern. **The lesson is not that these predicates are bad.
It is that a pattern map's bound is invisible from inside the session that drew
it**, and the only cheap way to see it is to wait one session and look.

# Session W2.2 — the dollar story, and the three rollups

**2026-08-05.** R-SP1 **AMENDMENT 1** ruled and BUILT. W2 (docs/07 §5b),
follow-on to W2.1, arbitrated by Daryn the same day. It completes W2.1's own
**§7(a)** and **§7(b)** exactly as those were scoped — price the first incumbent
with the real ledger, and land the three M7 rollups the summary screen was
naming as gaps.

**Contract 1.16 → 1.17** (`solver.progress` priced pair, `statistics`,
`ResourceLane` utilization). **docs/02 AMENDED** (§4.4/§4.5). Parse prompt
**v19** and synthesis prompt **v9** unchanged.

---

## 0. The predicate audit, stated first — and it found two holes

The cadence says the NEXT session audits the previous one's predicates, because
the builder is the worst-placed observer. W2.1 shipped two: the no-dollar-sign
cockpit assertion and `STORED_SOURCES`/`sourcesOf`. Both were **green at HEAD**.
Both were also **wrong**, and one was proven so by injection rather than by
reading:

**(1) The money guard was ENUMERATED, not SCOPED.** It asserted over three
selectors — `#sm-trail`, `#sm-progress-story`, `#sm-proof-floor` — while the
progress section had grown four more (`#sm-window-key`, `#sm-clause-2`,
`#sm-clause-3`, `#sm-trail-cap`). A `$` injected into the window-key line left
the guard **GREEN**:

```
injected  src/cockpit/src/summary.js  (sha256 55bdae94b748aa34)
[light] › no dollar sign touches the trail (R-DP12 / R-SP1 clause 3)  ✓ 1 passed
restored  sha256 55bdae94b748aa34  — byte-identical, git clean
```

Fixed structurally rather than by lengthening the list: the trail furniture now
lives in a real container, `#sm-trail-zone`, and the guard asserts the **zone**.
A zone can be asserted whole; a list has to be remembered. This mattered
immediately — Part A puts dollars in the *headline* while the trail below stays
in solver units, so the boundary needed to be a thing, not a convention.

**(2) `sourcesOf` hand-walked four branches.** Any figure added outside money /
portfolio / progress / stats would have passed "every figure names a stored
field" **by never being looked at** — and this session adds figures. Rewritten
to walk the model recursively for `*Source` keys, with a companion
`unsourcedFigures()` asserting the converse (nothing shown is uncited). A new
branch is now covered by existing.

Stale-process check clean. **Baseline measured on THIS tree: 2937 passed / 305
skipped / 0 failed** (1218s), matching the brief's reference at `864f02a`.

---

## 1. Part A — the dollar story

### The axis the brief said to stop on, and why it held

> *"if the extractor needs a field a mid-search snapshot cannot supply, STOP on
> that axis and say so rather than approximating a price"*

It needs nothing a snapshot cannot supply. `VariableMap.extract` reads its values
through `solver.Value(v)` **and nothing else**, and a
`CpSolverSolutionCallback` provides exactly that accessor. The first incumbent is
therefore captured by the *same function* that reads the final solution: no
second reader that could disagree with the first, no field the snapshot has to
invent. That is what makes the amendment's premise literally true rather than
nearly true, and it is why `plan_pricing` has **no arithmetic of its own** — it
runs the real `Extractor`, unmodified, and returns its ledger total.

### The self-proof, which is the whole license

The bridge marshals a dozen arguments. A forgotten one would still return a
plausible number, and the first plan's price — which nobody can check
independently — would be wrong in the same direction. So the bridge is pointed
at the one placement set whose price is already known:

```
re-price the FINAL plan through the bridge  ==  the shipped ledger total, to the cent
```

Verified on the rolling path by `test_THE_BRIDGE_SELF_PROOF_...`, and live on the
monolithic specimen: the bridge's `final_plan_cost` and M7's ledger both read
**$6,160.00**.

### The rule that moved the emission seam

**WHOEVER KNOWS THE SHIPPED PLAN EMITS THE TRAIL.** W2.1 emitted the monolithic
trail inside `SolveRunner`, beside its own `solve_complete`. That was right while
the trail was objective-space only; it cannot survive pricing, because on a
two-stage solve the shipped plan is **stage 2's** placements and stage 1's runner
has not seen them. Pricing a "final" that is not the plan the board publishes
would put a number on the screen that no ledger agrees with.

`SolveRunner` gained `defer_progress`; `solve_two_stage` sets it; the caller
emits once stage 2 has returned. A single-stage caller knows the shipped plan
immediately and still emits inline. One rule, one sentence.

### The evidence

`solve.first_plan_cost` **rolls up** `solve.final_plan_cost` +
`solve.plan_cost_improvement`, consolidator-verified — the same mechanism W2.1
used for the objective-space story, and the same reason: the wording is a
promise, the rollup is the mechanism. Clause (2) cannot become a difference
against a customer baseline and still decompose.

**The W2.1 objective-space metrics stay**, with different names and a different
unit (`objective_units` vs `currency`). Two measures, two names; no reader has
to guess which a number is. R-DP12 is untouched and still load-bearing — it is
precisely *because* the scaled objective may not reach a planner surface as money
that the ledger-priced pair had to be built rather than the objective rescaled.

### The screen

Four honest states, all asserted, screenshots in both themes:

| state | what renders |
|---|---|
| **priced** | two real ledger costs and their difference, above the zone |
| **unpriced** | the objective-space percentage, exactly as W2.1 shipped it |
| **flat** | one plan, told, with the proof floor |
| **absent** | a pre-trail board, saying so, reconstructing nothing |

Clause (2) renders **verbatim and unchanged** in the priced regime — it is what
keeps a dollar figure from reading as a saving against the customer's process.
Clause (3) gains a **second string** for the priced regime (not a branch inside
one) because it now says something genuinely different: both figures above are
real ledger costs, the trail below is a different measure, *and the two are
never mixed*.

---

## 2. Part B — the three rollups

`plan_statistics` composes the payload once; both assemblers read it — the
rolling one off the view, the monolithic one out of the Schedule's
`summary_metrics`. One producer, two readers, W2.1's pattern.

| rollup | discipline it inherits |
|---|---|
| `service.demands_counted` = late + on-time | consolidator-verified; kept DISTINCT from R-PD1's tardiness split, which decomposes a **cost**, not a count |
| `resource.utilization` | a RATIO, so not a rollup: both components ride beside it and **the denominator is on the record** (4B.20) |
| `setup.changeover_minutes` | shares a **population** with the setup charge — see the finding below |

Where no calendar was supplied there is **no ratio at all**; the components are
still emitted. A 0.0 would be a claim about the plant manufactured from a fact
about our inputs. Idle machines appear at 0% rather than vanishing.

The cockpit's own per-visible-window utilization is left exactly as it was: a
different, correct answer to a different question. The screen prints the
server's definition and says the two may differ.

---

## 3. THE FINDINGS

### (a) "minutes summed where cost is summed" had no minutes to sum

The brief asked for changeover minutes *"beside the setup COST the extractor
already computes — same source walk, minutes summed where cost is summed"*. The
charge is

```python
setup_cost = new_setup_ops * setup_fixed
```

— a **fixed fee per running operation**. There is no changeover *time* anywhere
in the ledger: the cost walk counts OPERATIONS, it does not sum MINUTES.

So what the same-source-walk discipline actually buys is not a shared summation
but a **shared population**. The minutes come from each operation's own
`setup_duration` (resource-specific where declared), over *exactly* the
WIP-filtered set the charge is billed on — `wip_status not in (complete,
in_progress)`, because a setup that happened before the reference date is sunk
(docs/06 §5.13). Filter the two differently and the plant's changeover time and
its changeover bill describe different plans. Guarded at the extractor, and
NC8 reverts the filter.

### (b) The extractor prices a plan that places nothing

A guard written to assert that a degenerate placement set would **fail** came
back the other way: the extractor prices it, as a plan where every demand is
late, returning a confident **$1,520.00** on the 40-order window.

A capture that silently came back empty or partial would therefore not raise. It
would produce a plausible first-plan price that is not a price of this plan at
all — with a dollar sign on it. So the amendment's premise (*both endpoints are
placements of the same plan*) is now **checked**: the caller passes the operation
set the final plan placed, and a capture that does not place the same ones is
REFUSED, falling back to the objective-space story.

### (c) Four of nine negative controls came back wrong, and each was a real hole

Written, they read as nine seams covered. Run:

* **NC2** dropped `overtime_windows` and the self-proof stayed GREEN — a fact
  about the **specimen**, which prices no overtime. *The self-proof is only as
  strong as the features its specimen exercises.* Re-pointed at `cost_model`;
  the limit is carried (§4a).
* **NC5** stripped `rollup_of` from the dollar metric and everything stayed
  green: the only decomposition anyone checked was the block's own arithmetic.
  **The dollar metric rollup had no test at all.** W2.1 gave the objective-space
  rollup one; the control collected the debt.
* **NC9** swapped utilization's numerator for the ELAPSED span and stayed green,
  because the guard used unchunked ops where the two coincide. Only a
  **resumable** op can see the difference — 4B.20's lesson landing on 4B.20's
  own guard, one session after it was written.
* **NC7** never matched: a literal em dash spelled as `—` inside a bytes
  literal is six ASCII characters. ANCHOR NOT FOUND is a **failure** in this
  harness, not a skip, which is the only reason it was seen.

Three new guards were written to close the holes. Final: **9/9 red, every
restore byte-identical.**

---

## 4. Suites, controls, children

| | before | after |
|---|---|---|
| Python | 2937 / 305 / 0 | **2968 / 305 / 0** (842s) |
| cockpit | 407 / 0 | **434** (433 + 1 load-flake, green alone) |

Python delta **+31**, all new tests, none removed: `test_plan_pricing.py`
(**6**), `test_plan_statistics.py` (**22**), and `test_solve_progress.py`
17 → 20 (**+3**, the guards the negative controls exposed). 2937 + 31 = 2968,
so the delta is fully accounted for and there is no residual. Cockpit delta **+27**: `summarymodel.spec.mjs` 14 → 23,
`summary.spec.mjs` 12 → 21 per theme. Eight `"1.16"` literals bumped to
`"1.17"`.

The one cockpit failure was `cockpit.spec.mjs` CU2 (dark) under full-suite load;
**green alone in 663ms**. That is the standing parallel-load flake class, not a
regression, and it stays on the debt list rather than being called fixed.

**Negative controls: 9/9 proven RED, every restore byte-identical**
(`tools/spikes/dollar_story_w22/negative_controls.py`).

**Children minted: one.** `_ai_exam_scratch/w22_specimen` — a scratch monolithic
solve of `datasets/mobility_box`, deterministic, **not registered**, not in
`_data`:

```
priced=True   $41,288.42 -> $6,160.00   saved $35,128.42 (85.1%)
objective-space, unchanged beside it:  4,073,055 -> 616,000  (objective_units)
dollar rollup exact   service rollup exact   bridge final == M7 ledger, to the cent
```

W2.1's specimen (`w21_trail_specimen`) was **not re-solved** and stands as the
real second-generation (unpriced) fixture. Pinned worlds untouched, not
re-solved, not re-minted.

---

## 5. Carry-forwards (REPORTED, deliberately NOT fixed)

**(a) THE SELF-PROOF IS ONLY AS STRONG AS ITS SPECIMEN'S FEATURE COVERAGE.**
Proven by NC2. A specimen exercising overtime, WIP and a declared setup matrix
would harden it. Named, not built.

**(b) ANY FUTURE "CHANGEOVER MINUTES SAVED" CLAIM STILL NEEDS A COMPARATOR.**
B3 supplies the minutes; it does not supply a baseline, and the fee-per-operation
shape means minutes and money do not move together. R2 item 3's cross-reference
is updated to say so.

**(c) LOSING PORTFOLIO MEMBERS ARE STILL UNPRICED** — and now doubly so: no
trail (W2.1 §7(e)) and no first-plan price. Correct by construction; only the
winner is re-solved with `persist=True`.

**(d) THE CAPTURE IS UNCONDITIONAL.** Every solve now takes one `extract` at its
first incumbent, including solves nobody will ever price (sandbox, sensitivity,
pool). One pass over the variable map, not measured as a cost. Gating it on
caller intent is the fix if it ever appears in a latency budget.

**(e) THE WALL-COST DISCLOSURE IS UNEXERCISED LIVE.** `capture_note` fires only
on a priced trail whose solve was WALL-truncated. Every specimen here bound on
its deterministic budget, so the sentence is guarded by fixture and by a cockpit
spec — never yet by a real wall-stopped board.

**(f) THE ASK LAYER STILL CANNOT BE ASKED** (W2.1 §7(c), unchanged). The trail
and now its dollars are evidence; no route reaches them. A future R1 item.

---

## 6. What a summary would undersell

**The dollar figure is not a saving.** It is the distance between the solver's
own first workable plan and the plan it finished on. The first plan is not what
a planner would have produced — it is the first thing CP-SAT could make legal,
often seconds in, and on the specimen it was 6.7× the final bill. Clause (2)
says this in body text beside the number for exactly that reason, and the
temptation to drop the label once the figure became dollars is the strongest
this screen has yet presented.

**Two measures now sit on one screen**, and the whole design is about keeping
them apart: currency above the zone, the solver's own score inside it, and a
sentence naming the boundary. That is a structure that degrades quietly — a
future contributor adding one figure to the wrong side would not obviously break
anything. `#sm-trail-zone` exists so a test can catch it; it is worth keeping.

**The rollups are honest and thin.** Three figures replaced three named gaps,
and the gap machinery was deliberately left in the code with an empty list. The
next statistic nobody stores should be named on the screen, not summed into it —
that was W2.1's rule, and landing three rollups does not retire it.

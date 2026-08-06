# Session W2.1 — the solve-progress ledger and the summary screen (v1)

**2026-08-05.** R-SP1 ruled and BUILT. W2 screens work (docs/07 §5b, **R2 queue
item 1**), executed from the R1 room at Daryn's direction — one line to the map
noting so. The Khalil MUST-tier item: **the optimizer's contribution was
invisible**, and this session makes it visible without fabricating a number.

**Contract 1.15 → 1.16** (`solver.progress`). **docs/02 AMENDED** (§4.5). Parse
prompt **v19** and synthesis prompt **v9** both unchanged — nothing here touches
the ask path, deliberately. The trail being askable *evidence* is what makes a
future route possible; building the route was out of scope and stays out.

---

## 0. The standing-law spot-check, stated first

The certificate session (S-02/S-03) built the last new predicates, so its
negative-control script was re-run at HEAD before anything else was touched:

```
6/6 controls proven red, every restore byte-identical
```

NC1–NC6 all RED; every restore byte-identical by sha256. No drift.

Stale-process check: clean (nothing on :8000 or :5175). **Baseline measured on
THIS tree**, HEAD-equivalent (the session's own new test files ignored so the
collected set matches 953833e):

```
2903 passed, 305 skipped, 0 failed   in 812.68s
```

— exactly the reference the brief carried. *(Note: the first baseline run's
output file was deleted mid-run by another Claude process's startup cleanup;
it was re-run to a session-controlled path rather than reported from memory.)*

---

## 1. THE FINDING THAT CHANGED THE RULING

**The brief's clause (2) specified the story in dollars, and standing law
forbids it.**

Clause (2) as drafted fixes the form as *"first plan found at \$X, improved to
\$Z."* A trail point is `solver.ObjectiveValue()` — the **scaled CP-SAT
objective** (`_COST_SCALE = 100`, plus gravity and priority weighting).
**R-DP12 clause (3)** admits that number only as *labelled solver telemetry*, and
clause (2) of the same ruling says scaled-objective arithmetic **never reaches a
planner surface**.

This is not a units quibble. R-DP12's own motivating specimen is a **zero-move
accept on the Khalil board** whose ledger did not change by one cent —
\$1,667,467.80 → \$1,667,467.80 — while the scaled objective moved by
**−7,014,821**, and that difference was printed *with a dollar sign* in a
planner-voiced message. The two quantities are not proportional. A dollar sign on
a trail point would be a manufactured number of exactly the class R-DP12 exists
to end.

**Resolved by tightening R-SP1 in place** (the brief's own instruction), with a
new **clause (3)**:

- the trail renders in the **solver's own units**, labelled;
- improvement renders as a **percentage of the first incumbent** — the same
  objective-space ratio the shipped **gap rider** already puts in front of a
  planner (`CostProof.rider`: *"…could be up to G% cheaper"*);
- the **ledger is the only currency on the screen**. It belongs to the finished
  plan and is never differenced against an earlier incumbent.

**What it costs.** The headline reads

> The solver's first workable plan scored 1,240,000; it finished on a plan
> scoring 980,000 — 21.0% better by its own cost measure.

rather than a dollar figure. That is weaker copy and it is the true one.

**Guarded on both sides, including the converse.**
`test_no_authored_string_in_this_module_carries_a_dollar_sign` in Python; a DOM
assertion over `#sm-trail`, `#sm-progress-story` and `#sm-proof-floor` in the
cockpit — *and* an assertion that `#sm-total` **does** contain `$`, so the guard
cannot be satisfied by a screen with no money on it at all.

**What would make the story dollars is named and carried** — §7(a).

---

## 2. Clause (7): the trail is stage 1's

Added in-room for the same reason clause (3) was. An R-SC3 solve runs two stages
and **only stage 1 minimizes cost**; stage 2 minimizes Σ free-op **start
minutes**. A concatenated trail would show a cost search collapsing into a minute
count and call the difference improvement — which is **4B.7 §5a.16's defect**
(`.objective` was a MINUTE COUNT for every downstream reader) reintroduced
through a new surface.

Both two-stage helpers construct a fused `SolveResult` (stage 1's objective with
stage 2's placements) and both now carry `incumbent_trail=s1.incumbent_trail`
explicitly; the other return paths use `replace(s1, …)` and inherit it. The
guard is structural rather than by inspection: **the trail's last point must
equal the view's `objective`**, and a stage-2 trail's last point is a minute
count, so it cannot.

Phase 0's warm-start trail is discarded on purpose — it is a satisfiability
solve, not a cost search.

---

## 3. W1 — the callback and the ledger

**The per-record ping was already there and was not a record of the search.**
`_SolutionCallback` has emitted one `improving_solution` Event per incumbent
since `solve_runner.py` was written — with **no elapsed time, no terminal bound
beside it, no collection and no reader**. That Event is left byte-unchanged
(evidence is append-only); `trail` is the collection it always needed.

`SolveResult.incumbent_trail` is `[{index, objective, elapsed_s}]`, EMPTY on a
solve that found nothing — an empty list, never a manufactured first plan.
`RollingView` gained `incumbent_trail` and `best_bound` (the view could state a
`gap` but not the floor the gap was a ratio over).

### Clause (6) — both proofs, quoted

Specimen: an **eight-job weighted single-machine tardiness model**, chosen
deliberately over the two-stage tests' constant-cost model — that one is
cost-flat by design and yields ONE incumbent, which is the wrong specimen for a
sequence proof.

**Proof A — the sequence is reproducible.**

```
46 incumbents, 6515 -> 530, monotone descending
run 1 sequence == run 2 sequence   (byte-identical, workers=1 seed=42)
```

Elapsed times are asserted only to be **present and non-decreasing**, never by
value: they are facts about a laptop, and the hard rules already say a wall-clock
figure is not reproducible.

**Proof B — the observer does not perturb.**

```
watched   = SolveRunner(...).solve(m, vm, None)      # callback attached
bare      = cp.CpSolver().Solve(m)                   # NO CALLBACK
watched.objective                == solver.ObjectiveValue()
watched.solve_values.op_start_minutes == bare.op_start_minutes
watched.solve_values.op_end_minutes   == bare.op_end_minutes
```

Every golden and every pinned world's placement digest rests on this.

**The specimen's adequacy is its own test.** Both proofs would pass vacuously on
a one-incumbent trail, so
`test_the_specimen_actually_produces_a_trail_worth_asserting` fails loudly if the
model ever stops exercising the property. *An empty denominator is not a clean
bill* (4A-(d.3) §5a.212), and a one-element sequence is that shape.

---

## 4. W2 — the trail enters evidence

Same three-part decomposition S-02 made for the gate verdict, and for the same
reasons. The full reasoning lives in `src/mre/modules/solve_progress.py`'s module
docstring and in docs/02 §4.5.

| part | record | content |
|---|---|---|
| the trail | **Event** §4.5 | `solve_progress` — incumbents, `stage`, `window_key`, bound, gap, budgets, `trail_provenance` |
| the scalars | **Metric** §4.4 | `solve.first_incumbent` **rolling up** `solve.final_incumbent` + `solve.incumbent_improvement`; `solve.incumbents_found` |
| the file | **Artifact** §4.6 | `solve_progress.json`, sha256 taken **from the file** |

docs/02 §4.5 already anticipated the record — *"long solves stream improving
solutions and telemetry here."*

**Four refusals, each for its own reason.** A **Finding** — every code names a
defect and a flat search is not one (clause 4: a flat story is a true story); a
finding code would turn a fact into a complaint. The shipped `SOLVER_NONOPTIMAL`
finding is untouched: an unclosed gap IS defect-shaped, and it is a different
statement. A **Decision** — an incumbent is not a deliberation; there are no
alternatives to enumerate and `driver` is mandatory-exactly-one over codes that
all name *scheduling* causes. A **Metric for the trail itself** — `value` is a
float, a trail is a sequence. A **new record type** — nothing here needs one.

**THE ROLLUP IS WHAT MAKES CLAUSE (2) STRUCTURAL.** `first = final +
improvement` decomposes exactly and the consolidator verifies it, so
`improvement` cannot quietly become a difference against a customer baseline and
still decompose. The wording is a promise; the rollup is the mechanism.
`solve.incumbent_improvement` is emitted **even at zero** — a flat search has a
measured nought, and §4.4's rule applies unchanged.

`trail_provenance` names the class and the source: **`derived`** from
`CpSolverSolutionCallback`. Not `observed` — nothing about the plant was
measured.

### The live specimen, end to end

`datasets/mobility_box`, deterministic (`workers=1`, `seed=42`), fresh scratch
run — **the only child this session minted**, unregistered, not in `_data`:

```
_ai_exam_scratch/w21_trail_specimen
  15 incumbents   4,073,055 -> 616,000   84.9% by the solver's own measure
  bound 616,000   gap 0.0 (OPTIMAL)      window_key None  (monolithic)
  metrics: first 4,073,055 == final 616,000 + improvement 3,457,055   EXACT
  artifact solve_progress.json  sha256 verifies from the FILE bytes  no "$"
```

**This specimen is what found a one-seam fix.** The first pass wrote the artifact
on the **rolling** seam only; the monolithic run came back with the Event and the
Metrics present and **no `solve_progress.json`**. Fixed at the caller that owns
an out_dir (`__main__`, beside the certificate) — the division
`write_certificate_json` already uses, because `SolveRunner` has no directory and
inventing one would put a run's artifact somewhere the run does not own. *A
defect class fixed at one seam is not fixed* (4B.14 §5a.34).

### The pinned worlds, measured rather than assumed

All three real boards carry a `solver` block with **no `progress` key** — the
absent-trail side, permanently (clause 5). **None was re-solved or re-minted.**

| board | contract | `progress` |
|---|---|---|
| `rolling-c32a6140-b6b` (demo) | 1.15 | absent |
| `rolling-e9ccc879-a4b` (exam) | 1.15 | absent |
| `rolling-c9973708-865` (previous demo) | 1.12 | absent |

A pre-1.16 document still parses, and that is its own guard
(`test_a_pre_1_16_document_still_parses`).

---

## 5. W3/W4 — the summary screen

One read-only, post-solve screen, reachable by one door: a `summary` button on
the top strip, opening over the board it was painted for. Rendered **from run
artifacts only** — `summarymodel.js` is a pure selector layer with no DOM, no
fetch and no arithmetic the server did not already do, tested separately in the
Playwright `logic` project.

**Dollars first**, asserted by geometry (`money.y < progress.y < stats.y`): the
ledger total and its stored decomposition, with the R-PD1 tardiness split
rendered as an indented sub-row of tardiness (it *decomposes* the charge, it does
not add to it) and the R-BK1 portfolio story where one exists — losing members
published with their reasons, and a one-member spread rendered as *"not enough
publishable members"*, never `0.00`.

**Three honest states**, each screenshotted in both themes
(`tests/cockpit/shots/summary_trail_{present,flat,absent}__{light,dark}.png`):

| state | what it says |
|---|---|
| **present** | the headline, the trail table, the curve, the proof floor |
| **flat** | *"…found one workable plan… and did not improve on it within its budget"* — no table, no curve, but the proof floor still renders |
| **absent** | *"This plan was solved before the solver kept a record of its own search… Nothing was reconstructed in its place."* No trail furniture at all |

The absent state is asserted against the **committed fixture, unrewritten** —
which *is* a pre-change board, so the state is exercised by the real thing rather
than by a stub.

**Clause (2) and (3) labels render VERBATIM**, exact-match: a paraphrase is a
different claim, and they are the disclosure that makes the percentage
publishable at all. All authored copy is composed **server-side**
(`solve_progress.headline` / the two label constants), exactly as `CostProof.chip`
is, so two surfaces cannot state different things. The only copy the cockpit owns
is the absent state's — which has no block by definition and makes no claim about
the search.

**No silent caps.** A real search produces dozens of incumbents (46 on an
eight-job specimen). The table shows **12**, sampled evenly, **always keeping the
first and the last**, and says so: *"Showing 12 of 46 improvements… The curve
below plots all 46; the full trail is stored with the run."* The curve is never
capped.

**The pre/post wall** is asserted by counting: the screen's only interactive
element is `close`. No solve button, no parameter, no Gatehouse element.

### The v1 statistics row — and what it refuses to show

**Rendered** (every figure a direct read of a stored contract field, and every
DOM node carrying its `data-source`): tardiness cost + the R-PD1 unavoidable
share, changeover **cost**, committed operations, operations in this window,
orders beyond the horizon.

**NAMED AS GAPS, not computed and not dropped** — three of the four the brief
asked for, because **nothing stores them**:

| asked for | why it is not shown | where it should come from |
|---|---|---|
| late / on-time counts | the document carries per-order lateness, not a tally | an M7 rollup (`service.late_demands` / `service.on_time_demands`) beside the per-demand `lateness_minutes` metric it already emits |
| utilization by machine | no board-scope figure exists; the cockpit's own is recomputed per **visible window** — a different denominator (4B.20) | an M7 rollup that **names its denominator** |
| total changeover minutes | `setup_min` is per bar; the ledger carries setup **cost** | an M7 rollup beside the setup cost the extractor already computes |

An honest gap beats a number with no provenance, and a gap that is silently
dropped is neither. The rule is enforced structurally, not by discipline:
`sourcesOf()` returns every document path the model read, and a test asserts the
whole set against a declared `STORED_SOURCES` list — a figure computed in the
frontend would have no source string and would fail.

**R2 queue item 3 (setup-grouping visual, "total changeover minutes shown") owes
the third rollup as a prerequisite.** That cross-reference is now written into
the queue rather than left for the next session to rediscover.

---

## 6. Suites, controls, children

| | before | after |
|---|---|---|
| Python | 2903 passed / 305 skipped / 0 failed | **2937 passed / 305 skipped / 0 failed** (1761s) |
| cockpit | 367 passed / 2 (named load-flake pair) | **407 passed / 0** |

Python delta itemized: **+34**, all new tests, no test removed and no
behaviour change to an existing one — `test_solve_progress.py` (**17** items:
15 functions, one parametrized ×3), `test_solve_progress_determinism.py`
(**6**), `test_solve_progress_document.py` (**11**). 2903 + 34 = 2937, so the
delta is fully accounted for and there is no residual. Cockpit delta: **+38** — `summarymodel.spec.mjs` (14, logic
project) and `summary.spec.mjs` (12 × two themes). The two named load-flake
members were **green in this run**; that is one observation, not a fix, and the
class stays on the debt list.

Seven `"1.15"` literals were updated to `"1.16"` across
`test_api_endpoints.py` (5), `test_frozen_boundary.py` (1) and
`test_schedule_document.py` (1). No golden was regenerated and no pinned world
was touched.

**Negative controls: 7/7 proven RED, every restore byte-identical**
(`tools/spikes/solve_progress_w21/negative_controls.py`):

```
NC1  the callback COLLECTS the incumbent (the trail itself)
NC2  the clause (2) disclosure (the label that keeps the % honest)
NC3  the METRIC ROLLUP that makes clause (2) structural
NC4  clause (7): the fused return carries STAGE 1's trail
NC5  the artifact digest taken from the FILE, not the string
NC6  the trail's EMISSION at the monolithic seam
NC7  the assembler's READ of the trail (contract 1.16 wiring)
```

NC1/NC6 revert the collection and the emission **independently**, and NC6/NC7 the
write and the read: a trail can be collected correctly and never reach evidence,
or reach evidence and never be read, and those are three different defects with
three different fixes.

**A process slip, reported.** Two full suite runs were started and then
discarded: the first because a docs/07 edit landed while it was in flight
(*docs never during suites* — the corpus currency gate is the mechanism, and a
number measured against a tree that no longer exists is not a number), the
second because a guard was added after collection. Both were killed rather than
reported. The figure above is a clean run over the final tree, and the corpus
was rebuilt and its currency gate re-run after the measured numbers were written
back into docs/07 (prose-only, no code).

**Children minted: one.** `_ai_exam_scratch/w21_trail_specimen` — a scratch
monolithic solve of `datasets/mobility_box`, deterministic, **not registered**,
not in `_data`. Pinned worlds untouched and not re-solved; capsules untouched.

---

## 7. Carry-forwards (REPORTED, deliberately NOT fixed)

**(a) PRICING THE FIRST INCUMBENT IS WHAT WOULD MAKE THE STORY DOLLARS.** It
needs an extractor run inside the solution callback — one per incumbent, dozens
per solve at demo density — and it interacts with clause (6)'s non-perturbation
promise on any **wall-limited** solve (under a deterministic budget the search is
unaffected, but callback cost is wall cost). Its own item, in R2 or R4. This is
the single change that would turn *"21% better by its own cost measure"* into a
dollar figure a founder can read.

**(b) THREE OF THE FOUR v1 STATISTICS ARE NOT STORED ANYWHERE.** Named on the
screen with the M7 rollup each should come from (§5). R2 item 3 owes the
changeover one.

**(c) THE TRAIL IS NOT ASKABLE.** It is evidence, so a route *could* be built,
and the brief scoped it out deliberately — *"how much did the solver improve this
plan"* currently reaches no route. A future R1 item (glossary + route), not a
contract change.

**(d) ROLLING RECORDS ONE WINDOW'S TRAIL, BECAUSE A ROLLING SOLVE IS ONE
WINDOW.** `build_rolling_view` solves window 0. Clause (1)'s no-summing rule is
therefore *enforced* by `window_key` against a future multi-window roll rather
than *exercised* by one today. A bound, not coverage.

**(e) THE PORTFOLIO'S LOSING MEMBERS HAVE NO TRAIL.** Members run in their own
processes and return only a `PortfolioMember`; only the winner is re-solved with
`persist=True`, and that re-solve is the trail the board carries. Correct and
cheap — but *"what did seed 43's search do"* is unanswerable by construction.

**(f) THE `improving_solution` EVENT IS NOW REDUNDANT AND STAYS.** It carries a
strict subset of what the trail carries. Removing it would be an evidence-shape
change with no reader to protect and a golden record-count to churn; left alone
under append-only, and named here so it is a decision rather than an oversight.

---

## 8. What a summary screen would undersell

Three things it does not say, and should be read as not saying:

**It does not say the plan is good.** It says what the search did and what the
plan costs. A search that improved 84.9% on its own first attempt may still be
sitting a long way from the optimum — which is exactly why the **proof floor and
gap render with the story** rather than beneath it.

**It does not say the solver beat anyone.** That is clause (2), and it is the
whole reason the label is on the screen in body text rather than as fine print.
The honest customer-baseline comparison is the pilot-phase import-and-price
feature, and nothing here is a down payment on it.

**Its statistics row is thinner than a customer will expect**, and the gaps are
visible on purpose. The temptation was to sum `setup_min` across bars and print a
changeover total — one line of JavaScript, and a number with no denominator, no
provenance and no owner. The row names what it cannot source instead, and the
next session inherits three concrete rollups rather than three numbers it would
have to audit.

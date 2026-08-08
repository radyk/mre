# SESSION R4.1 — the scope guard and the frame invariant (D1, D5)

**2026-08-08** · first fix session off the R4.0 dossier (docs/07 §5b item 0) ·
HEAD at start `d4639b1` · ruling **R-SG1** (docs/04 2026-08-08) ·
§5a.251-257

**No contract change. Prompts unchanged (parse v19 / synthesis v9). No
vocabulary change** — `infeasible_this_horizon` is untouched, which is R4.3's
subject. **No pinned world was written to**: the gen-3 re-pool STOP was taken
(§4). Five `src/` files changed, one test file added, three probes committed.

---

## 0. The predicate audit, stated first

R4.0 committed `p2_frame` with a ground-truth reader it had already caught being
blind once, so this session re-ran it and then audited it.

| predicate | result at HEAD |
| --- | --- |
| `verify_gen3.py` identity half | **PASS** — digest `8071cdaa…`, ledger $1,667,467.80, contract 1.17 |
| `p2_frame`, gen-3 | 25 probes / 7 refusals / **0 false** · frame offset **+0 min** · scope 386 |
| `p2_frame`, gen-2 | 25 probes / 7 refusals / **0 false** · frame offset **+0 min** · scope 386 |

**The conclusion holds. The instrument was weaker than the claim, in two ways.**

**One — it counts one direction and one sentence family.** It flags a refusal
saying *"not open at that time"* when the calendar is open. It cannot see a
false refusal wearing the other sentence (*"closes before this would finish"*),
and it cannot see a **false permission** — `relaxed_refusal` returning `None`
where the calendar is shut, which is the direction that puts a planner on a
closed machine. Re-run as a full 2×2 against the same independently computed
ground truth:

```
probes total                              : 50
correct refusal   (refused, does not fit) : 14
correct pass      (passed,  fits)         : 36
FALSE REFUSAL     (refused, DOES fit)     :  0
FALSE PERMISSION  (passed,  does NOT fit) :  0
--> agreement                             : 50 of 50
```

So the claim is true and is now stronger than the instrument that produced it
could establish.

**Two — "20 of 20" is not what the close-out says it is.** It reproduces exactly
as ONE board at `--n 4`. R4.0 reports it as "both correctly-framed boards",
which at the default `--n 5` is 50 probes. The number is real; its denominator
is mis-stated.

---

## 1. Both ladders

Every number is `passed / skipped / failed`.

| ladder | baseline (R4.0) | after (this tree) | delta |
| --- | --- | --- | --- |
| no `--runslow` | 2970 / 305 / 0 + 1 xf | **2989 / 309 / 0** + 1 xf · 15m49s | +19 passed, +4 skipped |
| `--runslow` | 3248 / 21 / **6** + 1 xf | **3272 / 21 / 5** + 1 xf · 52m51s | +24 passed, **−1 failed** |

**Both ladders balance against the same collection**:
`3272 + 21 + 5 + 1 = 2989 + 309 + 1 = 3299`.

The fast ladder's `+19 / +4` is exactly this session's new file (19 fast tests,
4 slow ones skipped without the flag). The slow ladder's `+24` is those 23 plus
**one recovery**: `test_two_beat_gesture_through_the_api`, the errand's C4 item
5, which the R-T2 correlation fix turns green.

**The five that remain are EXACTLY the errand's six minus that one**, by name —
no new red, and nothing of mine among them:

```
tests/test_ai_voice.py::TestAuditCorpusClean::test_cu5_split_jobs
tests/test_ai_voice.py::TestSession4B4::test_cu3_machine_count_answers
tests/test_ai_voice.py::TestSession4A3::test_cu4_unknown_capability_lists_what_can_be_coached
tests/test_ai_voice.py::test_cu10_zero_confident_wrong
tests/test_ask_chain_api.py::TestAskFailClosedWithRealKey::test_better_schedule_question_refuses_not_a_listing
```

Each is an AI-layer / sandbox product finding already named and routed in
docs/07 §5b; none is live-LLM. **Cockpit: not run as a suite** — no cockpit
source file was touched.

**Neither ladder was re-run after the doc edits**, and that is stated rather
than left to be assumed: the only documents this session touched after the run
are `docs/04`, `docs/07`, `CLAUDE.md` and this close-out, the corpus index was
rebuilt BEFORE the ladders (943 passages), and the close-out itself is not one
of the five documents the index covers.

**The baseline was NOT measured by this session, and that is an accommodation
rather than an omission.** The attempt was killed by a 10-minute tool timeout
against a ~60-minute ladder, and `pytest -q` had buffered its output to nothing.
Rather than serialize another hour of dead time — no `src/` or `docs/` edit is
safe during a suite — the baseline is taken as R4.0's measured figures,
justified by the fact that **`git diff 9854e9d..HEAD -- src/` is
`corpus_index.json` and nothing else**: no `src/` CODE file changed between
R4.0's measurement and this session's start. Any new red is attributed
per-test by re-running it against stashed HEAD.

---

## 2. W1 — the scope guard, and the census re-run at fix time

**The census was re-run rather than inherited, and it found a tenth site.**
Enumerated from every `SolverBuilder(...).build` call in `src/`:

| site | scope source |
| --- | --- |
| `sandbox.py:660` baseline · `:1127` audit · `:1474` beat one · `:1721` beat two | caller-supplied |
| `local_price.py:235` held world · `:595` validation rebuild | inherited `build_args` |
| `planner_edit.py:197` | self-derived (4B.31) |
| **`forced_alternatives.py:397`** | **self-derived — this session** |
| **`solution_pool.py:207`** | **self-derived — this session** |
| **`rolling_horizon.py:1868` `_final_extract`** | **self-derived (`sched`) — the tenth** |

`_final_extract` is a real post-solve rebuild against the committed placements.
R4.0's nine did not include it. It needed no change: its scope comes from the
scheduled demands, and its pin arithmetic reads `hstart = var_map.horizon_start`
— **the builder's own origin**. It is the only site in the product that does
that, which makes it clause (5) written before there was a clause, and it is the
shape the ruling now prefers.

The different class, confirmed and left: `scenario.py:355` (a full pipeline
re-run computing its own horizon — R4.0 named this and it is correct),
`__main__.py:443`, `demo.py:201`, and `rolling_horizon._build_window` (the
window build *inside* the rolling solve, scoped to its own admitted set).

---

## 3. W2 — the frame invariant

`standing_pins.assert_frame(var_map, horizon_start, site=…)` raising
`FrameMismatch`. `standing_pins` is the home because it already declares itself
"the SINGLE seam through which pins are applied" and imports no ortools.

**The crossing census — eight sites**, each now asserting: `sandbox` ×4,
`planner_edit` ×2, `solution_pool` ×1, `local_price` ×2.

**`forced_alternatives` does not cross.** Its cut is a pure assignment literal
(`add_forced_alternative_cut` touches no time) and `apply_solution_hints`
re-derives its minutes from `var_map.horizon_start` inside the builder. Its
assertion is a **floor against a future edit** and says so at the site, rather
than being counted as a fix.

**`solution_pool` is the only site that carried both defects** — unscoped, and
crossing: `incumbent_starts_min` is measured from the evidence origin and then
handed to `add_start_diversity_cut` against `var_map.op_start`.

### The proof, on the specimen that produced the false sentence

Beat one on a scratch copy of child `b5daba66` (run dir `ada15460-…`), called
exactly as the API calls it for a document with no rolling block
(`restrict_op_ids=None`), at 4x's own specimen — op `004733d3-aa3` on
`fd34d391-ffa` at `2026-01-08T09:52`:

**Before** (assertion physically removed):

```
NO EXCEPTION — the gesture returned a verdict:
  feasible : False
  verdict  : impossible
  message  : this placement isn't possible here — the machine is not open at
             that time [C1/C2]
```

**After**:

```
RAISED FrameMismatch
  site            : sandbox beat one
  evidence origin : 2026-01-05 00:00:00+00:00
  builder origin  : 2025-12-01 00:00:00+00:00
  offset (minutes): -50400
```

Restored by captured bytes; `sandbox.py` sha256
`12546ade4307eecce9966f8aa25952727dabeeae1f5d3551eceab92683c7cd70` before and
after.

---

## 4. W4 — the gen-3 re-pool: the STOP was taken

**`rolling-9fdee7aa-ec5` was never written to.** Its capsule stands as its
record, unchanged, and the placement digest `8071cdaa…` was re-verified at HEAD.

The brief's sequence was write-the-pool, then STOP before re-capsuling if any
member still refuses. **The order was deliberately reversed** — the pool was
rebuilt on a scratch copy first — and the reversal is what turned up two reasons
not to write it at all:

1. **4 of 8 members still refuse** at the API's default 10s member budget, and
   the refusal is a **mislabel**: all four are `UNKNOWN` (budget exhausted),
   published as `infeasible_this_horizon`. At 120s all four price.
2. **The four that do price carry a delta of about −5.87%** — "moving off the
   incumbent machine is cheaper" — because the denominator is a different model
   (§5).

Four false "no road" verdicts and eight misleading negative deltas, on the board
a demo runs on, is exactly the harm the STOP exists to prevent. Gen-3 stays
ghost-less until R4.3, at which point the re-pool is worth doing with a raised
member budget.

**This means the pinned world never entered the state the brief contemplated**,
which is stated here rather than left to be inferred from a missing capsule.

---

## 5. What the fix bought, and what it exposed

Gen-3: snapshot **695** operations, plan of record **386** — the old rebuild
carried 309 operations the incumbent never placed.

| pool | before (R4.0) | after |
| --- | --- | --- |
| alternatives, default 10s budget | 0 of 8 publishable | **4 of 8** |
| alternatives, 120s budget | — | **8 of 8 priced** |
| near-optimal, k=3 | `empty`, 3 of 3 INFEASIBLE | **`ready`**, 3 of 3 FEASIBLE |

### D2 is no longer latent, and this session is why

R4.0 recorded that all eight gen-3 members returned a genuine `INFEASIBLE` and
therefore classed the three-state fusion as latent. **With the model correct,
four of the eight return `UNKNOWN`** and are still published as a fact about the
plant. R4.3 inherits a live defect on the demo board rather than a theoretical
one.

### A second finding the fix EXPOSED but did not cause

`objective_delta_pct` divides the ghost's 386-op objective by
`_incumbent_objective(evidence)`. On gen-3 that record is the **winning
portfolio member's rolling-window solve at an 89.6% gap** — a different model.
The pair is not comparable, and the symptom is the negative sign.

It is not a regression: before the fix the denominator was equally mismatched (a
695-op model against the same record) and the numerator never existed, because
every member was infeasible. **R-DP12 already says the ledger is the only
comparable number**; pricing ghosts by ledger is the fix and is not this
session's.

---

## 6. W5 — the riders

### (a) The R-T2 correlation break

Both beats already keyed on their RESOLVED pin — which is what R-T2 requires,
and beat two's own comment settles it. **They disagreed on the spelling of the
instant**: beat one round-trips through `datetime` (`…+00:00`), beat two passes
the document's string verbatim (`…Z`). Measured: `corr-113002438e3b8b51` vs
`corr-8122788d7442d7d1`.

A correlation id names a GESTURE, and an instant is a point in time rather than
a spelling, so canonicalization lives in `correlation_id_for` — the one function
both beats call, and the only place that can make them *unable* to disagree.
`test_two_beat_gesture_through_the_api` is **green**.

### (b) Q6 — measured, with a positive control

| cell | gesture | placements | untouched moved |
| --- | --- | --- | --- |
| A | zero-move | held | **0** of 385 |
| B | zero-move | free | 0 of 385 |
| C | **real move** | **held** | **0 of 385** |
| D | real move | free | **238 of 385** |

**No — C5's finding does not touch R-T2's hold-everything-else contract.** Pins
are hard constraints and they hold. Cell D is the positive control and is the
only reason cell C's zero means anything.

**Side measurement worth keeping:** the unpinned accept path moves 238 of 386
placements at workers=1 — far beyond C5's 43. That is a direct measure of what
`hold_all_placements` (4B.24) buys.

**And this probe failed the same way R4.0's did, first.** Its hand-rolled reader
looked only at `assignment["resource_id"]`, which snapshot entities do not carry
(it lives under `resource_assignments`), read **0 placements from 386 bars**, and
reported *0 movers* — a clean bill from an empty set, on the probe written
specifically to stop inferring Q6 from a code read. It now uses the shared
`_placements` and RAISES on an empty read.

---

## 7. Tests and negative controls

`tests/test_scope_guard_and_frame.py` — **23 tests** (19 fast, 4 slow).

| control | reverted | result |
| --- | --- | --- |
| frame assertion (beat one) | physically removed | **RED** — b5daba66 emits the false sentence again |
| scope guard (both builders) | derivation removed | **RED** — `test_the_near_optimal_pool_is_not_empty_on_a_rolling_board`: `pool empty: ['INFEASIBLE','INFEASIBLE']` |
| correlation canonicalization | reverted to raw string | **RED** — 2 of 7 `TestCorrelationInstant` |

All restores by captured bytes, sha256-verified:
`sandbox.py 12546ade…`, `forced_alternatives.py 68813d4c…`,
`solution_pool.py 9ab16924…`.

**Two of the four slow tests do NOT discriminate, and say so in their own
docstrings.** `test_the_alternatives_pool_publishes_on_a_rolling_board` and
`test_the_scoped_rebuild_reproduces_the_incumbent` still pass with both scope
derivations reverted, because 40 orders over a 14-day window fit even unscoped.
They are post-conditions. The counterfactual at demo density is the gen-3
measurement in §5, not a test. A denser rolling fixture would make all three
discriminate and was not built — named as a carry-forward rather than papered
over, because a passing test that cannot fail is exactly the empty-denominator
shape this repo keeps catching.

---

## 8. Children minted, all named

| what | where | disposition |
| --- | --- | --- |
| gen-3 run-dir copies ×3 | `<scratch>/r41_scratch/gen3_copy`, `r41_pool/gen3_copy`, `r41_scratch/q6_copy` | byte copies; pools + accepts written into them |
| `b5daba66` copies ×3 | `<scratch>/r41_scratch{,_ctrl,_re}/b5daba66_copy` | byte copies; beat-one evidence |
| Q6 accept children ×4 | `<scratch>/r41_scratch/q6_child_*` | scratch only, NOT registered |
| slow-test rolling board | pytest tmp | fixture-scoped, discarded |

**`_data` was read but never written.** The registry is unchanged at 10
schedules; both pinned worlds are byte-untouched.

---

## 9. What a summary would undersell

**The scope fix did not make the pools right. It made them wrong in a way you
can see.** Before, the gen-3 alternatives pool published nothing and the reason
was invisible — `infeasible_this_horizon` on all eight, which reads like a fact
about a tightly-packed plant. Now four members publish, four are mislabelled
`UNKNOWN`s, and every price carries a delta whose sign is impossible. That is
strictly better, because each of those is a specific, locatable defect with a
measurement attached, and the previous state was one indistinguishable
non-answer. But nobody should read "8 of 8 roads are open" as "the ghost pool
works".

**The most useful thing found was already correct.** `_final_extract` has been
doing clause (5) — reading the builder's own origin for its pin arithmetic —
since before anyone wrote down that there were two origins. The ruling's
preferred shape was already in the codebase, at the one site nobody had
censused, and R4.0's nine-site census missed it precisely because it was not
broken. **A census that only enumerates suspects will not find the site that
shows you the answer.**

**The frame invariant is a refusal, not a repair.** It converts every one of the
nine `derive_base_context` callers R4.0 named from silently-wrong into
loudly-broken. That is the design and R4.2 is what fixes them — but it should be
said plainly that after this session, a planner on an accept-derived child gets
an error instead of a wrong answer, and not yet a right answer.

**And the pattern repeated inside this session.** R4.0's close-out ends with the
confession that its first instrument was blind and produced a zero from an empty
denominator. The Q6 probe here did the identical thing — different module,
different key, same shape — and was caught only because the rule says to check
whether the instrument can see a nonzero at all. Cells C and D exist for that
reason. **Twice in two sessions is not bad luck; it is what writing a probe
against an unfamiliar entity shape costs**, and the cheap defence is a positive
control, not more care.

---

## 10. Carry-forwards

1. **A denser rolling fixture** would make three of the four slow tests
   discriminate; two currently cannot go red. (§7)
2. **The ghost delta's denominator** is a different model from its numerator —
   priced members read "cheaper to move off the incumbent". R-DP12 says price by
   ledger. (§5)
3. **D2 is live on the demo board**, not latent: 4 of 8 gen-3 members are
   `UNKNOWN` published as `infeasible_this_horizon`. R4.3. (§5)
4. **Gen-3 has no ghosts** and no lineage child. The re-pool is worth redoing
   after R4.3, with a raised member budget. (§4)
5. **The `--runslow` baseline was inherited, not measured.** (§1)
6. **`local_price.py:595` asserts against `world.horizon_start`** — it catches
   builder drift on a rebuild, not a world loaded in the wrong frame. That case
   is caught at `:235`. The two look interchangeable and are not.

# SESSION R4.0 — RECON: the rolling interaction stack

**2026-08-07** · opens the R4 solver room (docs/07 §5b) · HEAD at start `4d7cc4e`

**RECON. No `src/` CODE file changed, no ruling, no contract change, prompts
unchanged (parse v19 / synthesis v9). Every pinned world READ-ONLY. Probe code
committed under `tools/spikes/rolling_stack/`; every mutable probe ran on a
named scratch copy.** The only tracked `src/` change is `corpus_index.json`,
regenerated from docs/04 and docs/07 by `tools/build_corpus_index.py`, as the
currency hook requires.

---

## 0. The predicate audit, stated first

The maintenance errand (2026-08-06) built two predicates and this is the next
session, so both were re-run at HEAD before anything else — and then audited,
which is the half that matters.

| predicate | result at HEAD |
| --- | --- |
| C3 `test_the_normalization_still_catches_a_moved_placement` | **PASSED** |
| C5 `test_scenario_untouched_moves_bounded` | **XFAILED** (strict), reason text intact |

Both hold. The errand's claims about them are true: the C3 control does
discriminate in both directions, and the C5 fixture does assert the recovery it
says it asserts — `base_context.get("solver_workers") == 1` and
`solver_seed == 0` (`tests/test_scenario.py:374,377`).

**And the audit found the gap, at the same function.** The errand's C5 lesson
was that `derive_base_context` recovers only what a run context actually
*recorded*, and it fixed that for the two solver-pinning fields. It did not
census what else the same function silently fails to recover. **`reference_date`
is a second member of that class**, it is lost on every accept-derived child,
and it is the direct cause of the false refusal sentence this recon was sent to
diagnose (§3.4). The fixture asserts recovery of exactly two fields; a third was
already broken in production when it was written.

That is this repo's own law — *a defect class fixed at one seam is not fixed* —
turned on the errand's own artifact by the next session, which is precisely what
the discipline is for.

---

## 1. Both ladders

Every number is `passed / skipped / failed`, measured on this tree.

| ladder | reference | baseline (this tree) | after |
| --- | --- | --- | --- |
| no `--runslow` | 2970 / 305 / 0 + 1 xf | **2970 / 305 / 0** + 1 xf · 19m05s | **2970 / 305 / 0** + 1 xf · 15m47s |
| `--runslow` | 3247 / 21 / 7 + 1 xf | **3248 / 21 / 6** + 1 xf · 60m11s | not re-run — see below |

**Unchanged, which is the expected result** — this recon changed no `src/` CODE
file and added no test, so anything else would have needed explaining.

The fast ladder was **re-run after the doc edits and the corpus-index rebuild**
(the only tracked `src/` change) — identical, and it is the ladder that carries
the currency gate and the CLAUDE.md budget, i.e. the two guards those edits could
plausibly have broken.

**`--runslow` was NOT re-run after the edits, and that is a stated limit rather
than an omission**: it costs an hour, the edits are documentation plus a
generated index, and no `--runslow`-only test reads either. Said here rather than
left for a reader to assume both rows are *after* numbers.

**The one delta is `-1 failed / +1 passed`, and it is not mine.** The errand's
seventh red was `test_chunking_scale_ladder::test_n3000`, which the errand itself
named a contention artifact (green alone, red under full-suite load). It is green
here. **The six that remain are EXACTLY the errand's six C4 items**, by name:
`test_cu5_split_jobs`, `test_cu3_machine_count_answers`,
`test_cu4_unknown_capability_lists_what_can_be_coached`,
`test_cu10_zero_confident_wrong`, `test_two_beat_gesture_through_the_api`,
`test_better_schedule_question_refuses_not_a_listing`.

**Both ladders balance against the same collection**, exactly as the errand's do:
`3248 + 21 + 6 + 1 = 2970 + 305 + 1 = 3276`.

**Cockpit: not run as a suite** — no cockpit source file was touched.

Note that item 5 of that list, the R-T2 correlation break, is the fix-ready item
this recon's §4.4 routes onto R4.1.

---

## 2. PART A — the three maps

### A1. The feasibility path — DUPLICATED, not shared

The brief asked whether the alternatives pool and the planner nudge share one
feasibility path. **They do not.** They are two independent rebuilds that happen
to make the same class of mistake:

| | alternatives ghost | planner nudge (beat one) |
| --- | --- | --- |
| entry | `POST /schedules/{id}/alternatives` | `POST /schedules/{id}/sandbox/feasibility` |
| loader | `forced_alternatives._load_alt_context` (`:293`) | `sandbox.feasibility_ghost` (`:1426`) |
| **window restriction** | **NONE** | `_restrict_window(…, restrict_op_ids)` (`:1443`) |
| model build | `SolverBuilder(...).build` (`:397`) | `SolverBuilder(...).build` (`:1474`) |
| refusal verdict | `infeasible_this_horizon` (`:437`, `:441`) | `relaxed_refusal` (`local_price.py:411`) |

Both build over the entities the loader handed them, at a horizon read from the
base run's **M5 evidence** (`solution_pool._m5_horizon`, `:387` — the *last* M5
`run_context_open`). Neither asserts that the horizon it read is the horizon the
builder then derives.

**The checks a candidate passes, in order** (`local_price.relaxed_refusal`, and
its held-world sibling `structural_refusal`): eligibility → calendar (open? long
enough?) → [held world only: occupancy → precedence → frozen front]. Beat one
deliberately tests only the two that survive its relaxation; the docstring at
`local_price.py:413-432` states why, and it is correct.

The **frozen zone** is not a check on this path at all — beat one relaxes it by
design (R-T2(4)), and committed pins reach only beat two. So of the brief's five
candidate frames, only two are live for beat one: the **calendar** and the
**model's own scope/origin**.

### A2. The verdict vocabulary — three facts, one sentence

`forced_alternatives.py:433-442` maps **three distinct states** onto
`infeasible_this_horizon`:

1. `applied is False` — there was nothing to cut (single-eligibility op, or not
   eligible on the required machine). *No alternative exists.*
2. `status == "INFEASIBLE"` — CP-SAT proved it. *The road is closed.*
3. `status == "UNKNOWN"` — the budget ran out. *We do not know.*

The repo has ruled this shape three times already (`unreadable` 4B.18,
`undetermined` 4B.23, `UNDECIDABLE` 4A.x): **an unrecognised or unproven value
fails SAFE and says nothing about the plant.** Here (3) is reported as a fact
about the plant.

**Named as found by code read, not as the cause of S1**: on the gen-3 specimen
all eight members recorded a genuine `INFEASIBLE` (§3.1), so this fusion is a
latent adjacent defect, not the one that emptied the pool.

The refusal *sentence* is derived from the failing check, not authored
generically — `relaxed_refusal` returns `None` rather than guess, and the caller
then says the plant refused without naming a cause (`sandbox.py:1536-1538`).
**That design is sound and is vindicated by measurement in §3.4.**

### A3. The accept/child path — where kind and calibration are set

A rolling board is assembled by `assemble_rolling_document(plant=, view=, …,
portfolio=, calibration=)` (`api/app.py:1304`), which needs a `RollingView`.

Both accept ceremonies —
`_execute_accept` (`app.py:1627`) and `_execute_audit_accept` (`app.py:1812`) —
instead call `schedule_assembler.build_document_from_run` (`:308`), which calls
`assemble_schedule_document`: **the monolithic assembler, which has no
`rolling`, `coarse_zone`, `portfolio` or `calibration` parameter at all.**

The **what-if** path (`app.py:1533`) uses the same assembler, so a scenario of a
rolling board is monolithic too. Not probed here — it is adjacent to the standing
*"pool service must become slice-aware"* debt and is named, not claimed.

So a child of a rolling, calibrated parent is monolithic and uncalibrated **by
construction**. S3 is fully explainable statically, as the brief predicted — and
§3.5 confirms it live at contract 1.17.

---

## 3. PART B — the traces

All probes are committed under `tools/spikes/rolling_stack/`. Artifacts and
exact invocations are named per trace.

### 3.1 P1 — one candidate, walked (`p0_horizons.py`, `p1_no_cut_control.py`)

Against the pinned gen-3 board `rolling-9fdee7aa-ec5` (read-only, in-process):

```
horizon (M5 evidence)   2026-01-05 → 2026-02-05   (31 days)
snapshot operations     695
incumbent assignments   386          UNPLACED: 309
placements outside the rebuilt horizon    0 / 386
```

The horizon is **not** the problem: every placement is inside it. The rebuild
carries **695 operations into a model whose incumbent only ever placed 386.**

**The control the product never ran** — the same rebuild with *no cut at all*:

| cell | status | wall |
| --- | --- | --- |
| A. no cut, hints on | **INFEASIBLE** | 2.15s |
| B. with the forced-alternative cut (the member) | **INFEASIBLE** | 0.88s |
| C. no cut, no hints | **INFEASIBLE** | 0.83s |

**The rebuild cannot reproduce a plan the board already has.** So the cut is not
what made the member infeasible, and `infeasible_this_horizon` is not a
statement about the alternative.

### 3.2 P4 — the frame hypotheses, tested directly (`p1b_scope_bisect.py`)

The brief named four frame candidates. Bisected on gen-3:

```
last due date            2026-02-02   (3 days BEFORE horizon_end)
demands due past horizon_end          0 / 280
FULL   scope   695 ops / 280 demands
PLACED scope   386 ops / 158 demands
```

| cell | scope | horizon | status |
| --- | --- | --- | --- |
| A | FULL 695 | recorded (today) | INFEASIBLE |
| B | FULL 695 | stretched to last due + 14d | **INFEASIBLE** |
| C | PLACED 386 | recorded | **FEASIBLE** |
| D | PLACED 386 | recorded **+ the cut** | **FEASIBLE** |

* **(c) horizon — REFUTED.** No demand is due past `horizon_end`, and stretching
  the horizon does not rescue the model. The diagnosis the brief flagged as
  "genuinely different — a policy problem, not a bug" does **not** apply.
* **(a) timezone — REFUTED on this board.** Measured offset between the
  M5-evidence origin and the builder's own: **0 minutes** (§3.3). R-TZ1 is not
  implicated here. *(It becomes the story on the accept child — §3.4 — but as a
  lost reference date, not a timezone.)*
* **(b) frozen zone — NOT LIVE.** Beat one relaxes it by design; the
  alternatives path has no frozen-zone check.
* **(d) capacity/self-collision — NOT REACHED.** The model is infeasible before
  any single candidate's occupancy matters.

**SCOPE is the load-bearing error**, and it is the one frame that matches the
incumbent.

### 3.3 P1c — how much the planner is actually denied (`p1c_all_targets.py`)

Every target in W2.3's preserved pool `alt-59f5047474e7`, re-run against
`plan_of_record_scope` instead of the whole snapshot:

```
the product published : 0 of 8 publishable
correctly scoped      : 8 of 8 FEASIBLE
```

All eight targets are 3-way eligible, all eight cut applied, and all eight move
to a **different** machine (seven to `3f032ed0-20f`, one to `df5aa682-bc1`).

**Feasibility only.** These ran under `stop_after_first_solution`, so no
objective is reported as a price — R-T2 forbids pricing a truncated search, and
the point here is that the verdict was wrong, not what the road costs.

**A second consumer, measured not inferred.** `solution_pool.warm_solution_pool`
— the near-optimal pool, an independent surface with the same unscoped rebuild —
on a scratch copy of gen-3: **status `empty`, 3 of 3 members INFEASIBLE.**

### 3.4 P2 — one nudge, replayed (`p2_frame.py`, `p2_nudge_replay.py`)

`sandbox.py` and `local_price.py` are **byte-identical to what 4x ran**
(`git diff 9a26122..HEAD` touches neither). So S2's 160 refusals are a fact
about a *world*, not about the code — and the world is the one 4x's own script
walks onto.

`replay_demo_lineage.py` runs EDIT 2's ladder against **`active_bars(doc2)`**,
where `doc2` is the **child** minted by EDIT 1 — `b5daba66`, 40 ops × 4 offsets
= **160**, exactly the reported count. And `b5daba66` has **no rolling block**,
so `api._rolling_gesture_context` returns `(None, [])` and beat one is handed
`restrict_op_ids=None`.

**Three cells, the real `feasibility_ghost`, on named scratch copies:**

| cell | scope | reference_date | probes | impossible | FALSE sentences |
| --- | --- | --- | --- | --- | --- |
| gen-2 parent, restricted (correct) | 386 | present | 32 | 7 | **0** |
| `b5daba66` child, unrestricted | 695 | **LOST** | 24 | **24** | **23** |
| child, unrestricted, ref restored | 695 | forced | 16 | 16 | **0** (11 unattributed) |

**4x's exact specimen, both ways.** Op `004733d3-aa3` on `fd34d391-ffa` at
`2026-01-08T09:52`:

* on the correctly-scoped parent → **`possible` / FEASIBLE**;
* on the monolithic child → **`impossible`, "the machine is not open at that
  time"** — the recorded false sentence, reproduced on demand.

**The mechanism, quantified.** On the child, `derive_base_context` recovers no
`reference_date`, so `SolverBuilder._compute_horizon` loses its floor and drags
the origin back to the earliest release in the *whole plant*:

```
horizon_start (M5 evidence)     2026-01-05
var_map.horizon_start (builder) 2025-12-01
OFFSET                          -50,400 minutes  (35 days)

var_map calendar windows span   minutes  50,820 .. 94,740
expressible pins span           minutes       0 .. 44,640     ← DISJOINT
```

`pin_start_min` is measured from the evidence origin; `cal_windows` from the
builder's. Every pin a planner can express lands strictly **before the first
calendar window in the model's frame**, so `open_at` is `None` every time and
the sentence is "the machine is not open at that time" — always, for every op,
at every instant.

**THE CHECK AND THE SENTENCE, SEPARATED.** The brief asked which was wrong. The
third cell answers it: restore the reference date alone, leave the scope broken,
and **all 23 false sentences vanish** while **16 of 16 refusals remain**.

* the **wrong check** is caused by the lost **scope** (695 ops → infeasible);
* the **false sentence** is caused by the lost **reference date** (frame offset);
* and `relaxed_refusal` is **innocent**. It is truthful about whatever model it
  is handed, and when it cannot attribute a refusal it returns `None` — 11 times
  in that cell, exactly as its docstring promises. Both defects are upstream.

On the correctly-framed boards its verdicts matched an independently computed
calendar **20 of 20** (`p2_frame.py`, gen-3 and gen-2).

> **My own instrument failed this test first.** `p2_frame`'s ground-truth reader
> initially read `calendar["windows"]`, a key that does not exist — the real one
> is `horizon_resolved` — and returned **0 windows for every machine**, which
> made every refusal look correct and reported *0 false sentences* from an empty
> denominator. That is (d.2)'s rule landing on this session's own probe, at the
> same site W2.3's rider hit it. The reader now **raises** rather than returning
> `[]`.

### 3.5 P3 — one accept, traced (`p3_accept_child.py`)

The real accept path (`apply_planner_edit` → `build_document_from_run`) driven
in-process on a scratch copy of gen-2. **At HEAD, contract 1.17** — this is not
a 1.15-era artifact:

| | parent `rolling-c32a6140-b6b` | child (scratch) |
| --- | --- | --- |
| contract | 1.15 | **1.17** |
| rolling block | **True** | **False** |
| `solver.calibration` | **present** | **absent** |
| `reference_date` | `2026-01-05T00:00:00Z` | **`None`** |
| assignments | 386 | 386 |

```
derive_base_context(child/runs) → {'time_limit': 120.0,
                                   'solver_workers': 1, 'solver_seed': 42}
reference_date recoverable      → False
```

Those are **exactly the two fields the maintenance errand taught the run context
to record**, and not the third. The accept drops all three inheritances, and the
lost `rolling` block is what hands the next gesture `restrict_op_ids=None`.

### 3.6 P5 — the consumer census, and which instrument was lying

**Guard 1 — the window restriction.** Nine post-solve sites rebuild the base
model from a snapshot. Seven restrict; two do not:

| site | restricted? |
| --- | --- |
| `sandbox.py:660` baseline · `:1127` audit · `:1474` beat one · `:1721` beat two | ✓ caller-supplied |
| `local_price.py:235` held world · `:595` rebuild | ✓ (inherits `build_args`) |
| `planner_edit.py:197` | ✓ **self-derived** (`plan_of_record_scope`, 4B.31) |
| **`forced_alternatives.py:397`** | **✗** |
| **`solution_pool.py:207`** | **✗** |

`scenario.py:355` is a **different class** — a full pipeline re-run that computes
its own horizon, not a rebuild against an incumbent. Named, not claimed; it is
adjacent to the standing *"pool service must become slice-aware"* debt.

**This is 4B.31's finding, one seam further on.** `plan_of_record_scope`'s own
docstring (`sandbox.py:452-471`) records that `_restrict_window` "existed for six
sessions and three of the four Tier-2 surfaces were wired to it", the fourth
being the accept — which "refused every accept on every rolling board ever
minted". **The census that found the fourth did not extend to the two pool
builders**, so the class was declared fixed with two members still open.

**Guard 2 — the root-run walk.** `derive_base_context` is called at **11** sites.
**Two** walk to the root run first (`app.py:1588` accept, `:1786` audit accept) —
and `app.py:1582-1586` *names the trap*: "an accept run records no M3/M4
pipeline, so re-deriving from a chained parent would lose the reference date (the
3.3b wall-clock trap)". **Nine do not**, including every sandbox seam
(`sandbox.py:648`, `:1446`, `:1689`), `local_price.py:221`,
`forced_alternatives.py:316`, `solution_pool.py:155`, `ask.py:295`,
`whatif.py:93`, `app.py:1518`. All nine are safe on a base run and wrong on an
accept-derived child.

**WHICH INSTRUMENT WAS LYING.** Measured on gen-3, one board, four instruments:

| instrument | says |
| --- | --- |
| the mobility floor (W2.3) | 154 of 386 bars are multi-eligible |
| beat one, correctly restricted | **25 of 32** nudges `possible` |
| the alternatives pool | 0 of 8 publishable |
| the near-optimal pool | 0 of 3, status `empty` |

**The floor and the sandbox agree; the two pool builders are the outliers**, and
8 of 8 of their verdicts flip to feasible when scoped. The mobility floor was
telling the truth about the plant. The pools were telling the truth about a
model of a plant that does not exist.

---

## 4. PART C — the dossier

### 4.1 The defect ledger

| # | defect | seam | severity |
| --- | --- | --- | --- |
| **D1** | the incumbent rebuild is **unscoped** — whole snapshot, not the plan of record | `forced_alternatives.py:293,397`; `solution_pool.py:155,207` | **planner-visible wrong verdict + blocked interaction** |
| **D2** | `infeasible_this_horizon` **fuses three states** (no alternative / proved closed / budget exhausted) | `forced_alternatives.py:433-442` | planner-visible wrong verdict *(latent — not S1's cause)* |
| **D3** | the accept mints a **monolithic, uncalibrated, dateless child** | `app.py:1627`, `:1810` → `schedule_assembler.py:308,340` | metadata loss — **and the carrier of D1/D4 onto the nudge path** |
| **D4** | `reference_date` is **unrecoverable** from an accept child's run dir | `scenario.py:135-138`; 9 of 11 callers do not walk to root | **planner-visible FALSE statement about the plant** |
| **D5** | the **frame is assumed, never asserted**: `pin_start_min` from M5 evidence vs `cal_windows` from the builder's own origin | `sandbox.py:1448,1462` vs `solver_builder.py:609,1091-1134` | the missing invariant underneath D1 and D4 |

### 4.2 Do S1/S2/S3 map to one root, two, or three?

**Two roots, one shared mechanism, one shared missing invariant.**

* **S1** (empty ghost pool) = **D1**, with D2 latent alongside it.
* **S3** (monolithic child) = **D3**.
* **S2** (160 refused nudges) = **D3 → both other defects at once**: losing the
  rolling block reproduces D1's mechanism at the sandbox (the wrong **check**),
  and losing the reference date produces D4 (the false **sentence**).

So S2 and S3 share a root; S1 has its own. **But S1's mechanism and S2's
check-failure are the same unscoped rebuild reached through two different doors**
— which is why the fix is one idea applied at two seams, not two fixes.

Underneath all of it is **D5**: nothing anywhere asserts that the frame the pin
is expressed in is the frame the model was built in. D1 and D4 are two different
ways of breaking an invariant no one checks.

**The false-sentence attribution, settled: the sentence is innocent** (§3.4).
This matters for who owns the fix — it is not the copy, and it is not
`relaxed_refusal`.

### 4.3 The design questions a fix session must settle (named, not answered)

1. **What should `infeasible_this_horizon` MEAN on a rolling board?** At minimum
   it must stop absorbing `UNKNOWN`. The repo's third-state law says the budget
   case gets its own name. This is a **vocabulary-class change** (contract +
   `ghosts.js`), reviewed as one.
2. **May an alternatives pool offer next-window placements?** Today the question
   is moot because the scope is wrong. Once scoped to the plan of record, a
   genuinely-beyond-window alternative is out of scope *by construction* — so
   the fix session must say whether that is the intended policy or an accepted
   narrowing, and say it on the pool.
3. **What does a child inherit at accept?** rolling block, calibration,
   reference date. **R-CAL1 interaction is live**: the ruling says calibration
   must be DECLARED *including when the answer is no*, and a child that silently
   drops the block declares nothing. This one needs a ruling, not just a patch.
4. **Caller-supplied or self-derived scope?** 4B.31 already answered this for
   the accept (`plan_of_record_scope`, derived from the plan itself, precisely
   because "a guarantee a caller can forget is not a guarantee"). The same
   answer is available to both pool builders and should be taken deliberately.
5. **Should the frame be asserted?** A cheap invariant — assert
   `var_map.horizon_start == horizon_start` wherever pin arithmetic crosses the
   two — would have turned all of S2 into a loud failure at the first probe.
6. **Does C5's finding touch R-T2's hold-everything-else contract?**
   **NAMED, NOT MEASURED** — the brief allowed either. C5 measured that
   single-worker CP-SAT does not follow warm-start hints tightly (43 untouched
   moves vs 4 at workers=8); R-T2's local price claims "nothing else moved". The
   sandbox's beat-two *pins* rather than *hints*, so the two may not collide at
   all — but that is an inference from a code read, and it is exactly the kind of
   inference this recon has now twice found to be wrong. It needs its own
   measurement.

### 4.4 The proposed fix-session split

The brief expected *feasibility root → sentence/vocabulary → accept-child*. **The
evidence redraws it**: the accept-child IS the feasibility root for S2, so it
moves up, and the vocabulary work moves last because it is the only one that
touches the contract.

| session | subject | opens | why here |
| --- | --- | --- | --- |
| **R4.1** | **the scope guard and the frame invariant** (D1, D5) | `forced_alternatives.py`, `solution_pool.py`, `sandbox.py` | widest blast radius; restores the drag-price-accept loop on every rolling board; **8 of 8 measured roads come back**. Carries the negative control: the unscoped build must be *proven* the wrong model, not assumed. |
| **R4.2** | **what a child inherits at accept** (D3, D4) | `app.py`, `schedule_assembler.py`, `scenario.py` | unblocks lineage (S2, S3) and gen-3's deferred child; needs R4.1's frame assertion in place to *prove* the child is sound rather than assert it. Carries the R-CAL1 ruling. |
| **R4.3** | **the verdict vocabulary** (D2) | `forced_alternatives.py`, `contracts/`, `ghosts.js` | last because it is the only contract/vocabulary change, and because R4.1 changes which verdicts are even reachable. |

**The diagnosed R-T2 correlation fix** (`sandbox.py:1309` vs `:1463`, the
errand's C4 item 5 — fix-ready, not this recon's subject) **rides R4.1**, which
is the session that opens `sandbox.py`.

---

## 5. Scratch children minted, all named

| what | id / path | disposition |
| --- | --- | --- |
| gen-2 run-dir copy | `<scratch>/r4_scratch/gen2_copy` | byte copy; beat-one evidence written into its own `sandbox/` |
| gen-3 run-dir copy | `<scratch>/r4_scratch/gen3_copy` | byte copy; near-optimal pool built into it |
| `b5daba66` run-dir copy | `<scratch>/r4_scratch/b5daba66_copy` | byte copy; beat-one evidence |
| **accept child (P3)** | **`552b490b-01de-474b-ae58-f2d8113c4616`** | scratch only — **NOT registered**, not in `_data` |

**No pinned world was written to.** Every probe that needed a mutable board ran
on a copy under the session scratchpad; the only in-place reads against `_data`
were `p0`, `p1`, `p1b`, `p1c` and `p2_frame`, none of which writes. The registry
is unchanged at 10 schedules.

---

## 6. What a summary would undersell

**The two pinned worlds were never broken.** Everything this recon found is a
defect in code that *reads* a board, not in any board. Gen-3's plan is still
gen-2's plan, still digest `8071cdaa…`. The product has been telling planners
that 8 real roads are closed and that open machines are shut — on boards that
were correct the whole time.

**The most useful finding is a docstring.** `plan_of_record_scope`
(`sandbox.py:452-471`) is a written confession of this exact defect class, found
in 4B.31, with the sentence *"a guarantee a caller can forget is not a
guarantee"* in it. The fix that comment describes was applied to the seam that
was looked at. Two more seams — both of them the ones a planner touches to see
alternatives — were never censused. **The repo diagnosed this class, wrote down
the correct general remedy, and then applied it locally.** That is a more
expensive lesson than any single bug here.

**Three guards, each partially applied, and the rolling stack is where the gaps
meet.** The window restriction: 7 of 9 sites. The root-run walk: 2 of 11 sites,
with the trap *named in a comment* at one of the two. The frame invariant: 0 of
anywhere. Any one of the three, applied completely, would have prevented the
whole of S1 and S2.

**4x's false sentence was not a flake and not a mystery — it was the only
honest thing in the room.** A world had been built in a frame 35 days from the
one the planner's pin was expressed in, and every calendar window in that model
sat past every instant a planner could name. `relaxed_refusal` looked at that
model and reported exactly what it saw. The 4x close-out was right to call the
sentence false and right to refuse to diagnose it in passing; what it could not
see is that the sentence was *faithful*, and that the lie had been told one
gesture earlier, by the accept.

**And this session's own first instrument was blind in the same way its
subject is.** `p2_frame` read a calendar key that does not exist and returned a
clean bill from an empty denominator — the same shape as the defect it was
pointed at, caught only because the repo's law says to check the denominator.
The first number this recon produced was *0 false sentences*, and it was wrong.

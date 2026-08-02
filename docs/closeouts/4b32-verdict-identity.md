# Session 4B.32 — verdict identity, and the honest driver

2026-08-03 · repo `C:\dev\mre` · branch `master`
Rulings: **R-DP12** (new, built) · **R-DP10** (DISCHARGED BY IDENTITY) · **R-T2**
disclosure line (recorded STRUCTURALLY MOOT on this path)
Contract: **unchanged at 1.15** · Parse prompt: **unchanged at v16** · **No new
vocabulary**

---

## 0. The one-sentence finding

The incomparable number was not only *selecting* the Decision's driver — it was
being **printed with a dollar sign** in the record the ask layer testifies from,
so a zero-move accept on the Khalil board wrote a planner-voiced sentence
claiming a **$7,014,821 saving for a move that changed the ledger by $0.00**.

---

## 1. CU2 — the census (acceptance criterion 1)

Every consumer of `delta_abs` / `delta_pct` / `solve_result.objective` **on the
accept path**. (The `cost_delta_abs` / `reopt_delta_abs` / `move_delta_abs`
family belongs to the sandbox CARD and is a different, already-ledger-based
quantity — out of scope and untouched. `POST /audit/accept`'s `expect_delta_abs`
is a LEDGER figure on a different ceremony — see §7(d).)

| # | consumer | what it did with the number | disposition |
|---|---|---|---|
| 1 | `planner_edit.py` — `delta_abs = solve_result.objective − _incumbent_objective(evidence)` | subtracted two objectives of **different expressions over different op sets** | **RE-BASED.** Computed only where an objective exists; **None** under a held accept (never 0.0) |
| 2 | `planner_edit.py` — `driver = COST_TRADEOFF if delta_abs > 0 else NO_ALTERNATIVE` | **selected the Decision's driver** | **RETIRED.** `_edit_driver(cost_delta)` — the ledger (§4) |
| 3 | `planner_edit.py` — Decision `message`, `f"(±${abs(delta_abs):,.0f})"` | **printed the scaled objective as DOLLARS**, planner-voiced | **RE-BASED to the ledger** (`cost_delta.total_delta`) |
| 4 | `planner_edit.py` — `chosen["delta_abs"]`, `chosen["delta_pct"]` | Decision payload | **KEPT, LABELLED** solver telemetry; `chosen["objective_cleared"]` added beside it so the record says which question was asked |
| 5 | `PlannerEditResult.objective / .delta_abs / .delta_pct` | returned to the API worker | **KEPT, LABELLED**; `objective` is **None** when cleared (CP-SAT answers 0.0 for an objectiveless model, and 0.0 would read as a real total) |
| 6 | `api/app.py::_execute_accept` → `registry.finish_run(result={"delta_abs": …})` | run result row | **KEPT** + **`cost_delta_total` ADDED** — the run row now carries what the accept actually cost |
| 7 | `api/app.py::_execute_accept` → response `decision.delta_abs/delta_pct` | accept response to the cockpit | **KEPT, LABELLED.** `sandboxui.js::showAccepted` already reads `cost_delta.total_delta` only, and says so in its own comment |
| 8 | `explainer.py::_edit_facts` → `key_facts["delta_abs"]` | fed the `edits` / `edit_cost` ask-path bundles | **DROPPED.** Both renderers already state `cost_delta.total_delta`; the field was carried and never voiced, so the rule held only because nobody happened to read it — §5a.72's exact mechanism |
| 9 | `renderers.py` | — | **no consumer.** Every `delta_abs` in that file is `cost_delta_abs`/`reopt_`/`move_` (the card) |

**#8 is the one the census earned.** Nothing was wrong on screen; what was wrong
was that a planner-facing bundle carried the telemetry field, so R-DP12 clause
(3) would have been true by inspection rather than by shape — and on a held
accept the field is now `None`, which a future reader would have rendered as a
figure.

---

## 2. CU1 — verdict identity: clearing the accept's objective

`apply_planner_edit`, under `hold_all_placements`, now calls
`model.clear_objective()` before solving — exactly what
`local_price.validate_held_world` (`cp-sat-pin-all`) has always done.

**Why the objective was never doing anything there.** With every placement of
the plan of record pinned and the planner's drop pinned, the model has one
assignment left. An objective over a fully pinned model **cannot change the
plan**. The only thing it can change is the **word** the solve returns — turning
a proof question into a search question under a budget, so the accept could
answer `UNKNOWN` where the card had proved `OPTIMAL`.

Confirmed at the primitive: a CP-SAT model with no objective returns
`OPTIMAL` and `ObjectiveValue() == 0.0` — which is precisely why `delta_abs`
had to become **None** and not 0.0.

**The condition is "is anything free to move", never "is this board rolling."**
Without the hold this is a genuine window search and the objective stays. One
rule, both board classes — R-DP11's own discipline.

**Ordering.** CU1 and CU2 landed in **one commit**, CU2's re-basing written
first: clearing the objective without re-basing the driver would have traded a
wrong number for a missing one.

---

## 3. R-DP10 — discharged by identity, with its revival conditions stated

R-DP11 made the card and the accept compile the same model over the same scope.
CU1 makes them ask it the same question. The two-beat card is **not built**, and
after this it need not be — but the discharge is **conditional and the conditions
are written into docs/04**:

1. **One compiler** — both build through `SolverBuilder` over
   `plan_of_record_scope(assignments)`, derived not passed (R-DP11 clause 3).
2. **One pin seam** — both pin through `standing_pins.apply_pin` over the same
   incumbent placement map.
3. **One question** — both clear the objective and ask feasibility alone.

**If any of the three lapses, R-DP10's two-beat obligation revives in full.**
This is a discharge by *identity*, not by a judgement about how often two
authorities happened to agree.

**R-T2's disclosure line is recorded STRUCTURALLY MOOT on this path, not
dropped** — there is no second verdict for it to disclose. It becomes owed again
the moment a discharge condition lapses. R-T2 itself is unchanged and still binds
wherever two beats do exist.

---

## 4. The driver: what a $0.00 accept now records, and what the taxonomy lacks

**`COST_TRADEOFF`, at every ledger delta including $0.00.**

**Why not `NO_ALTERNATIVE` (what HEAD recorded).** It voices as *"there was no
other feasible option"* — a claim about the **PLANT** that an accept never
establishes. Worse, under `hold_all_placements` it would be asserting it from a
property of **OUR METHOD**: every placement is pinned, so of course nothing else
was reachable. Manufacturing a plant claim from a method fact is the disease.

**Why `COST_TRADEOFF` is the least-wrong, and where it over-reads.** It claims
only that the cost consequence was priced and weighed — true of every accept,
because the card prices one before the button exists. At **$0.00** the
`planner_language` phrase *"it was the cheaper option once every cost was
weighed"* describes a comparison that came back **level**, so it over-reads.

**THE TAXONOMY HAS NO HONEST CODE FOR THIS DECISION, AND I AM NOT STRETCHING ONE
TO FIT.** A `planner_edit`'s real driver is *a human directed this placement*.
The missing member is a **`PLANNER_DIRECTIVE`** code; adding one is a reviewed
vocabulary-class change (docs/02 §4.2 + `planner_language` + the exam bank) that
this session did not take. Recorded as **§5a.130** and carried forward.

**The driver is therefore a CONSTANT here, deliberately.** The variation
`delta_abs` supplied was not information — it was noise with a sign. The number
rides `chosen.cost_delta`, so the size of the trade-off stays checkable by
anyone who wants it.

---

## 5. Live confirmation (acceptance criterion 7)

`rolling-db5395dc-2ae` — **the Khalil board** — driven through
`POST /schedules/{id}/accept`, exactly as the cockpit calls it. HEAD was measured
by physically stashing the fix and restarting the API on HEAD source.

### 5a. Zero-move accept, before and after

| | HEAD (measured **twice**, identical) | after R-DP12 |
|---|---|---|
| HTTP / wall | 201 · 12.0 s / 6.2 s | 201 · **6.97 s** |
| verdict | OPTIMAL | OPTIMAL |
| ledger | $1,667,467.80 → $1,667,467.80 | $1,667,467.80 → $1,667,467.80 |
| ledger delta | **$0.00** | **$0.00** |
| **`driver`** | **`NO_ALTERNATIVE`** | **`COST_TRADEOFF`** |
| Decision message | `… (−$7,014,821)` | `… (+$0)` |
| `delta_abs` / `delta_pct` | −7,014,821.0 / −5.8764 % | **None** / **None** |
| `objective_cleared` | *(key absent)* | **True** |

HEAD's message, verbatim from the store:

```
Planner edit: pinned op 0947fa39 to 3f032ed0 @ 2026-01-06T07:00:00+00:00 (−$7,014,821)
```

**The after-driver justified against the taxonomy:** see §4. `COST_TRADEOFF`
claims the cost consequence was priced and weighed (true); `NO_ALTERNATIVE`
claimed the plant left no choice (false, and manufactured from our own pinning).

### 5b. One real gesture (+24 h class), card → accept

* op `0947fa39` (ORD-000029) → `3f032ed0` @ **2026-01-07T07:00:00Z** (its own
  machine, +24 h).
* **Card** (`POST /sandbox`): `outcome=verdict`, `attribution=local`,
  validation **`OPTIMAL`**, `cost_delta_abs = $0.00`, 9.17 s.
* **Accept** (`POST /accept`): **201 in 4.89 s**, child
  `2c383b70-6153-4cc9-a79f-7e96ccb4021e`, ledger **$1,667,467.80 →
  $1,667,467.80**, `moved_count 1`, `driver COST_TRADEOFF`,
  `objective_cleared True`, `delta_abs None`.
* **Card promise and accepted ledger agree to the cent.**

### 5c. This session's own live children (kept as evidence)

* `cf705b58-fc3e-407a-9792-22c4115f43cc` — the after-fix zero-move accept.
* `2c383b70-6153-4cc9-a79f-7e96ccb4021e` — the +24 h gesture accept.

The two **HEAD-measurement** children (`0aa785b0-…`, `d37c6fa7-…`) were
**deleted** after their Decisions were transcribed: they carry the defective
`NO_ALTERNATIVE` driver and the dollar-signed scaled objective, and leaving them
in the store would leave exactly the artefact §7(b) is about. (`d37c6fa7` was
minted by accident — the probe script had no `__main__` guard and an `import`
re-ran it. It reproduced HEAD identically, which is the only reason it is worth
mentioning.)

---

## 6. The guard

`tests/test_accept_self_validation.py`, **14 tests** (was 9), slow-marked.

New:

* `test_the_held_accept_model_carries_no_objective` — **the property.** Spies the
  model the LIVE accept hands `SolveRunner.solve` and asserts
  `Proto().has_objective()` is False on **every** solve.
* `test_a_held_accept_proves_rather_than_searches` — the residue closed:
  `status == OPTIMAL` (never UNKNOWN/FEASIBLE), `objective is None`,
  `delta_abs`/`delta_pct` None.
* `test_the_driver_follows_the_ledger_not_the_objective` — reads the Decision
  **from its own evidence sink** (the record as it lands, not the result object)
  and asserts `driver == COST_TRADEOFF`, `chosen.delta_abs is None`,
  `objective_cleared is True`, and that no `$7,0…` figure appears in the message.
* `test_premise_the_two_numbers_disagree_in_sign_on_this_board` — **the premise.**
  Solves the held plan-of-record model WITH its objective and asserts
  `objective − incumbent_objective < 0` beside a ledger delta of $0.00. Without
  this the driver test could pass on a fixture where the two numbers happen to
  agree and would be proving nothing.
* `test_the_driver_is_never_the_plant_claim_at_any_ledger_delta` — the branches
  the demo board **cannot reach** (§7(a)), asserted rather than measured, and
  said so in the docstring.

Widened (CU4, closing 4B.31 §8(d)): `test_accept_compiles_only_the_plan_of_record`
now asserts **every** observed build, not `seen[0]`.

### Negative controls — FIVE, proven RED against physically reverted code

| control | reverted | result |
|---|---|---|
| 1–3 | the whole R-DP12 block removed from `planner_edit.py` (`git stash`) | **3 failed, 10 passed** — and the driver control reported the real specimen: `AssertionError: the driver is NO_ALTERNATIVE`; the objective control `assert [True] == [False]`; the proof control `assert 4175561.0 is None` |
| 4 | R-DP11's `_restrict_window` call **physically deleted** | `compiles_only[sparse]`, `compiles_only[dense]`, `incumbent_revalidates` — **3 failed** |
| 5 | a **second, whole-book `SolverBuilder.build`** injected AFTER the correct one | **RED**, naming *"build #2 of 2 … compiled 88 operations for a plan that places 56; 32 of them are work this board never admitted"* — **and `seen[0]` would have been green**, which is the entire point of CU4 |

Control 5 is the one that proves the widening. Fix restored → **14 passed**.

---

## 7. Findings REPORTED, deliberately NOT fixed

**(a) THE LEDGER-MOVED BRANCH IS UNREACHABLE FROM A DRAG ON THE DEMO BOARD, AND
IT WAS MEASURED, NOT ASSUMED.** I wanted a live accept that moved the ledger, so
the non-zero driver and message branches would be observed rather than asserted.
**54 gestures**: +24 h on 20 arbitrary active bars, +24 h on 22 bars belonging to
the latest orders (ORD-000206 at 55,860 min late among them), then
+48/+96/+168 h on the four that had priced. Result: **50 refusals and 4 prices,
every price exactly $0.00.** The refusals are the ruled families —
*"that time is already taken on this machine"* [B1], *"the machine is not open at
that time"* [C1/C2], *"the next step in this order is already scheduled before
this one would finish"* [A1/A2]. Under R-T2 clause (2) the only drops that
survive the gate land in genuinely open time on their own machine, which moves
neither production nor setup, and a successor's precedence refuses any drag long
enough to move tardiness. **So the dearer and cheaper branches are asserted by
unit test, never observed live**, and this close-out says so rather than letting
the live gesture imply coverage it does not have.

**(b) OLD ROLLING-ERA DECISIONS ARE NOT REPAIRED; THE ONES THIS THREAD CONTROLLED
WERE DELETED.** Every `planner_edit` Decision minted on a rolling board between
4B.31 and this session carries `NO_ALTERNATIVE` and a dollar-signed scaled
objective. All of them lived in 4B.31's four probe children plus this session's
two HEAD-measurement children; **all six are gone (rows and dirs, with a
dangling-reference sweep)**. No repair pass and no tombstone mechanism exists for
any that might survive in another data root. **Whether the evidence store should
carry a tombstone is open** — §9 carry-forward, unchanged in substance and now
narrower in fact.

**(c) `hold_all_placements=False` KEEPS ITS OBJECTIVE, CORRECTLY, AND IS
UNEXERCISED.** No shipped caller passes False (`AcceptRequest` defaults True
since 4B.24), so the branch that keeps the objective — and its `delta_abs` — has
no live coverage. Correct by construction, uncovered by measurement.

**(d) `POST /audit/accept` WAS NOT TOUCHED.** Its `expect_delta_abs` is a LEDGER
figure on a different ceremony (4B.25 Item 4a), so R-DP12 clause (1) is stated
for the accept path only. **Nobody re-derived that in this session** — it is
believed from 4B.25's own account, not measured here.

**(e) THE `COST_TRADEOFF` PHRASE ITSELF IS UNCHANGED.** *"it was the cheaper
option once every cost was weighed"* is false of a DEARER accept — which HEAD
also recorded as `COST_TRADEOFF`, so this is pre-existing and not introduced. It
is the same sentence a `PLANNER_DIRECTIVE` code would replace (§4).

**(f) THE `objective_cleared` FLAG IS EVIDENCE, NOT A CONTRACT FIELD.** It rides
`chosen` and the M6 Reporter config. It is deliberately **not** on the schedule
document — no contract bump was owed and none was taken.

---

## 8. What the summary would undersell

Three things.

**The number was wearing dollars.** The brief describes finding (a) as an
incomparable number *selecting a driver* — harmless on the card, wrong in the
evidence. It was also being formatted `(−$7,014,821)` into the Decision's own
planner-voiced message. The store held a sentence claiming a seven-figure saving
for a move that changed nothing, and the ask layer reads that store.

**The census earned exactly one fix, and it was invisible.** Eight of nine
consumers were already correct or already labelled. The ninth —
`explainer._edit_facts` — was carrying the telemetry field into a planner-facing
bundle that never voiced it. Nothing was wrong on screen. What was wrong was that
the rule was true *because nobody read the field*, which is §5a.72's mechanism
verbatim: a name written once, by whoever needed a number, and never re-read as a
claim.

**The negative control that mattered was the one for the guard, not for the
fix.** Reverting R-DP12 turned three tests red, which is table stakes. The
control worth the time was injecting a **second, wider build after the correct
one**: the old `seen[0]` assertion was green against it, the widened one names
*"build #2 of 2"*. That is 4B.28 §5a.123's lesson from the other end — the only
way to learn whether a guard bites is to break the thing it guards and look.

---

## 9. Carry-forwards (named, not dropped)

* **`PLANNER_DIRECTIVE`** — the driver code the taxonomy lacks (§4, §5a.130). A
  reviewed vocabulary-class change: docs/02 §4.2, `vocabularies.DriverCode`,
  `planner_language.DRIVER_PHRASING`, the exam bank.
* **A tombstone (or repair pass) for pre-R-DP12 rolling `planner_edit`
  Decisions** — §7(b). None survive in this data root; the mechanism does not
  exist for any that survive elsewhere.
* **Specimen C proper** — the recorded `CAPACITY_BLOCKED` driver vs the
  counterfactual's *nothing-prevented-it*. **Unchanged disposition, still
  queued** (§5a.83's shape). This session stopped NEW wrong drivers on the accept
  path; it repaired no old Decision anywhere.
* **The planner-facing "why not" graduation question** (4B.31 §2d / §5a.128(h)) —
  still an open question, not a decision.
* **The parallel-load flake fix shape** — a deterministic budget in the fixture,
  not a wider tolerance (4B.31 finding (g), which sharpened it by finding a
  member with workers and seed already pinned). Queued; **a session changes no
  test but its own.**
* **`--calibrated` is a flag on a spike script, not a product path** — untouched
  4B.28 carry.

---

## 10. Verification

**Acceptance criteria**

| # | criterion | status |
|---|---|---|
| 1 | CU2 census table | ✅ §1 — nine consumers, disposition each |
| 2 | objective-cleared property test RED at HEAD → GREEN; control red on reverted code | ✅ §6 |
| 3 | driver-follows-ledger test RED at HEAD on a sign-disagreement rolling fixture | ✅ §6 — with its own sign premise |
| 4 | dense-fixture zero-move accept OPTIMAL, never UNKNOWN, wall recorded | ✅ §6 (`test_a_held_accept_proves_rather_than_searches`); live wall 6.97 s (§5a) |
| 5 | widened scope guard green; `seen[0]` gap closed | ✅ §6, control 5 |
| 6 | docs/04 three amendments dated + appended | ✅ 2026-08-03: R-DP10 discharge, R-T2 moot record, R-DP12 |
| 7 | LIVE on the Khalil board, drivers before and after | ✅ §5 |
| 8 | housekeeping per §6 of the brief | ✅ §11 |
| 9 | suites at/above 4B.31's 2410 baseline; slow ladders green; goldens; cockpit count | ◑ **2410 passed / 291 skipped / 0 failed**, both slow ladders green (46, 56), cockpit **306/2** (the named "deictic" pair). **The schedule-CSV golden is NOT byte-identical** — pre-existing, proven on a HEAD worktree, §10a |
| 10 | commit + push + close-out as a file | ✅ |

**Collected:** 2701.

**Non-slow Python suite: 2410 passed / 291 skipped / 0 failed.** Run in **four
foreground chunks plus `tests/ai_exam/`** (586+691+597+505+31 passed;
173+38+29+44+7 skipped), because every background invocation of the whole suite
was killed at ~10 minutes by the harness. 586+691+597+505+31 + 173+38+29+44+7 =
**2701 = collected**, so nothing was silently dropped.

Against 4B.31's baseline (2410 passed / 286 skipped / **2 failed**): **the same
2410 passed, +5 skipped, and neither failure reproduced.** The +5 are this
session's five new slow-marked guards, which the non-slow run skips — the
arithmetic closes exactly. 4B.31's corpus failure is green because
`tools/build_corpus_index.py` was re-run after the docs edits (5 documents, 676
passages); its other failure is §10a below.

**Slow ladders, green:**

* `test_planner_edit` + `test_standing_pins` + `test_accept_self_validation` +
  `test_edit_snapshot_id` — **46 passed**, 209 s (was 41; +5 guards).
* `test_sandbox` + `test_rolling_two_beat` + `test_scenario` — **56 passed**,
  201 s.

**Cockpit Playwright: 306 passed / 2 failed** of 308, 5.9 m. The two are
`cockpit.spec.mjs:111` "deictic" × {light, dark} — **red at HEAD since 4B.23** and
already named in CLAUDE.md as not from that session either. **No JS changed in
this session.** Identical to 4B.31's result.

### 10a. The goldens — and a CORRECTION to 4B.31 finding (g)

`test_cost_ledger_identical` — **the substantive modularity-gate claim — passed
in every single run**, six for six. The ledger is stable.

`test_schedule_csv_identical` — **NOT byte-reproducible, and 4B.31's
characterisation of it is CORRECTED.** 4B.31 recorded it as load-sensitive and
"passes on a quiet machine on both trees". Measured here on a **quiet** machine:

| tree | runs | result |
|---|---|---|
| this session's tree | 4 | pass · **FAIL** · pass · **FAIL** |
| **clean detached `HEAD` worktree** | 3 | pass · **FAIL** · pass |

**It fails roughly half the time on an idle machine at HEAD.** So it is not this
session's code (proven on a HEAD worktree, as 4B.31 did) and it is not merely
load — it is genuinely nondeterministic run to run. **The diagnosis is unchanged
and this strengthens it:** `_run_mre` already pins `--solver-workers 1
--solver-seed 42` and `PYTHONHASHSEED=0`; the one thing it does not pin is
`--time-limit 30`, a **WALL** limit, which the repo's own hard rule says makes a
solve irreproducible. The search truncates at a different node run to run and
returns a different tied-optimal placement at the same cost. **The fix shape is a
deterministic budget in that fixture, not a wider tolerance — and it is NOT
fixed here, because a session changes no test but its own.** This is now the
sharpest specimen of the parallel-load flake class and it should be the next
session's cheapest win.

---

## 11. Housekeeping (brief §6)

`registry.sqlite` backed up to the session scratchpad before any deletion.

**Deleted, rows AND dirs:** `15e16a90-…` (monolithic control), `1f945619-…` and
`fa3e0821-…` (children of the Khalil board), `43ee9ffd-…` (child of
`rolling-d10efd24-6f4`) — 4B.31's four; plus this session's two HEAD-measurement
children `0aa785b0-…`, `d37c6fa7-…`.

**Pre-flight, all empty:** no schedule had any of them as a parent; no pool
referenced them; no run chained off their runs; no other schedule shared their
runs. All four 4B.31 runs were `kind=accept`.

**Post-verification:**

```
residue for 15e16a90 / 1f945619 / fa3e0821 / 43ee9ffd : NONE
dangling parent_schedule_id: []      dangling schedules.run_id : []
dangling runs.base_run_id  : []      dangling pools.schedule_id: []
schedules with a missing document: []
rolling-db5395dc-2ae UNTOUCHED — ledger 1,667,467.80  bars 386  contract 1.15
rolling-c362baa4-1b0 UNTOUCHED — ledger    16,481.95  bars  56  contract 1.11
```

`GET /schedules` lists 22 schedules, every document resolvable — **the picker
shows no orphans**, and the API starts clean on the same data root.

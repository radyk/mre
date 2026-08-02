# Session 4B.31 — accept integrity: the incumbent must re-validate

2026-08-02 · repo `C:\dev\mre` · branch `master`
Rulings: **R-DP11** (new, built) · **R-DP10** (new, ruled — implementation owed)
Contract: **unchanged at 1.15** · Parse prompt: **unchanged at v16**

---

## 0. The one-sentence finding

The accept compiler built its model over **the whole book** while the rolling
engine had published a plan for **a subset** — so on every rolling board this
product has ever minted, the accept model was infeasible *with no edit at all*,
and **nothing had ever committed on a rolling board**.

---

## 1. CU0 — the blast radius

The probe replaced the reported gesture with the most trivial accept there is: a
**ZERO-MOVE accept**, pinning a non-committed bar at exactly its own placement.
Driven through the live API, exactly as the cockpit calls it.

| board | kind / contract | zero-move accept | wall |
|---|---|---|---|
| `rolling-b4dd3010751f` | rolling, 1.15 (ceremony child of Khalil) | **REFUSED** — 409, `INFEASIBLE` | 2.5 s |
| `rolling-d10efd24-6f4` | rolling, 1.14 | **REFUSED** — 409, `INFEASIBLE` | 2.4 s |
| `87c705b9-…` | **monolithic**, 1.8 | **ACCEPTED** — 201, ledger delta $0.00 | 2.4 s |

**Specimen B was the whole story.** The hypothesis in the brief — that prior
accept proof ran on monolithic fixtures only — is CONFIRMED: every fixture in
`tests/test_planner_edit.py` is `clean_small`, monolithic; and the registry's
only `snap-edit-*` children are all contract-1.8 monolithic boards.

---

## 2. CU1 — the diagnosis, by evidence

### 2a. The shape

Khalil board `rolling-db5395dc-2ae`, snapshot `snap-rolling`:

    demands=280  workpackages=280  operations=695  assignments=386
    OPERATIONS IN SNAPSHOT WITH NO PLACEMENT: 309
    M5 horizon: 2026-01-05 .. 2026-02-05  (31 days, = window 10 + 21-day tail)

`apply_planner_edit` built `SolverBuilder().build(wps + ops + edges, …)` over all
695. Every operation the builder emits is **mandatory** —
`new_int_var(wp_earliest_min, horizon_minutes − duration)`, no presence literal —
so the 309 unadmitted tray operations had to be placed inside the window's 31
days, around 386 placements held hard by `hold_all_placements`.

### 2b. The two-cell experiment

| cell | model | pins held | pins refused | verdict |
|---|---|---|---|---|
| **A** | the accept model as shipped (**whole book**, 695 ops) | 386 | 0 | **INFEASIBLE**, 0.6 s |
| **B** | restricted to the ops the plan **places** (386 ops) | 386 | 0 | **OPTIMAL**, 0.1 s |

Zero pin refusals in both cells: the incumbent placements were never inconsistent
with each other. A domain census found **no empty start-variable domains** (695
of 695 ordinary, 0 degenerate), so this was a genuine conflict, not a
construction artifact.

### 2c. THE CORE, VERBATIM

Deterministic deletion filter over the 122 unadmitted demands — binary search to
the smallest infeasible prefix (23), then delete-one-out — 32 solves, 44 s,
`workers=1`, `seed=42`, sorted candidate order:

```
ground: 158 placed demands / 386 pinned ops
candidates: 122 demands the rolling engine did not admit

all 122 candidates  -> INFEASIBLE
zero candidates (plan of record alone) -> OPTIMAL
  prefix  61 -> INFEASIBLE
  prefix  31 -> INFEASIBLE
  prefix  16 -> OPTIMAL
  prefix  24 -> INFEASIBLE
  prefix  20 -> OPTIMAL
  prefix  22 -> OPTIMAL
  prefix  23 -> INFEASIBLE

smallest infeasible prefix: 23

=== CORE: 1 unadmitted demand(s), 32 solves, 44s
  ORD-000062  due=2026-01-25 release=None ops=3

These, together with the 386 held placements of the plan of record and
the window horizon 2026-01-05..2026-02-05, cannot all hold.
```

**One tray order the planner cannot see, and never asked to schedule, was enough
to refuse every accept on the board.**

### 2d. The mechanism named

**Not (1), not (2), not (3) — it is SCOPE.** No freeze-seam transition pair, no
committed-bar compilation conflict, no working-time-vs-span divergence. The
accept model simply contained work the plan of record does not place.

Assumption-literal instrumentation was **not needed and was not built**: the
two-cell control plus the deletion filter answered the question with fewer moving
parts, and `AddNoOverlap` cannot carry `OnlyEnforceIf` anyway. Whether the
diagnostic build should graduate to a planner-facing "why not" is carried
forward, not decided (§6).

---

## 3. CU2 — the fix, in the shared compile path

`sandbox._restrict_window` has existed since **4B.3c CU3** and its docstring
states this exact requirement. `api/app.py::_rolling_gesture_context` computes
the scope and hands it to **three** Tier-2 surfaces — the feasibility ghost
(beat one), `price_drop` (beat two) and `audit_incumbent`. **The fourth is the
ACCEPT, and it had no such parameter at all.**

Two changes, both in the shared path, no per-board-class special case:

* `sandbox.plan_of_record_scope(assignments)` — the one definition of "the
  operations the published plan places". Returns **None, never the empty set**,
  for a plan that places nothing.
* `planner_edit.apply_planner_edit` **derives** that scope from the base
  snapshot's own assignments and applies `_restrict_window`. **Derived, not
  passed in** — the identical restriction was already available to a caller, and
  a caller forgot it for six sessions.

**Where the guarantee lives:** `src/mre/modules/planner_edit.py`, immediately
after the base entities are loaded and before anything is built. Nothing between
the load and the build can bypass it.

**Monolithic is the identity, by construction and by measurement:** every
monolithic board in the registry places every operation it holds (90/90 on three
of them), so the restriction keeps the whole book and the compiled model is
unchanged.

---

## 4. The guard — and why it needed two members

`tests/test_accept_self_validation.py`, **9 tests**, slow-marked.

**The behavioural test alone would not have caught this.** Measured:

| fixture | ops / placed | zero-move accept **at HEAD** |
|---|---|---|
| `pilot_scale` 40, w14/f3 | 88 / 56 | **GREEN** (OPTIMAL, 1.2 s) — the whole book fits |
| `pilot_scale` 80, w10/f2 | 199 / 50 | **GREEN** (FEASIBLE, 20.4 s) |
| `pilot_scale` 200, w7/f2 | 507 / 99 | **RED** (INFEASIBLE, 1.6 s) |
| `demo_board` 120, w7/f2 | 300 / 99 | RED, but `UNKNOWN` after 60.9 s — a budget verdict, not a proof; rejected as a fixture |

So the guard is:

1. **THE PROPERTY** — `test_accept_compiles_only_the_plan_of_record`, run on
   **both** a sparse and a dense fixture. It watches the real `SolverBuilder.build`
   the live accept performs and asserts the operation set equals the plan's
   placed set. **This bites at 40 orders, where the behavioural test is green.**
2. **THE BEHAVIOUR** — `test_incumbent_revalidates` on the dense fixture: a
   zero-move accept succeeds and moves the ledger by $0.00.

Plus premise tests (`test_premise_the_board_carries_work_it_did_not_place`,
`test_premise_the_dense_book_does_not_fit_the_window_horizon` — the latter
asserts INFEASIBLE-whole-book *and* FEASIBLE-scoped, i.e. the fixture really
reproduces the Khalil shape), an identity test for clause (4), and a None-vs-empty
test for clause (3).

### Negative controls, proven RED against physically reverted code

The R-DP11 block was **physically deleted** from `planner_edit.py` and the suite
re-run:

```
FAILED tests/test_accept_self_validation.py::test_accept_compiles_only_the_plan_of_record[sparse]
FAILED tests/test_accept_self_validation.py::test_accept_compiles_only_the_plan_of_record[dense]
FAILED tests/test_accept_self_validation.py::test_incumbent_revalidates
3 failed, 6 passed
```

**Three controls red, and the sparse one is the point of the exercise.** Fix
restored → 9 passed.

A fourth control guards the guard: `test_negative_control_a_corrupted_plan_is_refused`
overlaps one placement onto another on the same machine and asserts the accept
refuses. Paired with `test_incumbent_revalidates` (same fixture, same bar,
uncorrupted → accepts), that pair is what discriminates "the accept still checks
things" from "the accept stopped checking".

---

## 5. Live confirmation (criterion 7)

**`rolling-db5395dc-2ae` — THE KHALIL BOARD — now commits.**

* **Zero-move accept:** HTTP **201 in 4.1 s**, ledger **$1,667,467.80 →
  $1,667,467.80**, delta **$0.00**, child `1f945619-b09c-4dc4-934b-95e13903be30`.
* **A real gesture, end to end:** ORD-000029 op10, +24 h on its own machine
  (CUT-03). Card (`POST /sandbox`) → `cp-sat-pin-all` **OPTIMAL in 0.77 s**;
  Accept (`POST /accept`) → **201 in 1.51 s**; child `fa3e0821-…`, **386 bars**,
  child ledger **1,667,467.80**, moved_count 1. Offer and accepted ledger agree.
* `rolling-d10efd24-6f4` commits too (201 in 2.6 s).

**THE ORIGINAL SPECIMEN A GESTURE WAS NOT REPRODUCED EXACTLY, AND THAT IS
STATED.** The brief gives it as "ORD-000134 op10 → CUT-03 @ Jan 27, 02:00". On
this board **02:00 is a closed-calendar instant** and the local pricer refuses it
by name (`the machine is not open at that time [C1/C2]`), so that cannot be the
instant behind a card reading "PROVEN WITHIN BUDGET". The exact instant is not
recoverable from the report. What replaced it is stronger and covers it: a
**zero-move** accept refused on the same board, which no gesture can explain.

### The two authorities now agree — 18 gestures, 0 disagreements

Six bars × {+4 h, −4 h, +24 h}, each priced by `local_price` and then put through
the real accept:

* 1 priced and accepted (`PRICED OPTIMAL` / `ACCEPT OPTIMAL`);
* 17 refused by both, in the **same docs/05 family** each time (B1 / C1-C2 / A1-A2).

**The card's authority was never a cheap check.** `validate_held_world` is a full
model with every placement pinned and the objective cleared (`cp-sat-pin-all`).
It was **the right method on the wrong model** — the same one defect.

---

## 6. CU3 / R-DP10 — RULED, NOT BUILT. This is the scope I did not deliver.

**R-DP10 is transcribed in docs/04** (verdict authority: no proof-class word
without an accept-grade solve). **The two-beat card is NOT built**, and criterion
5 is **not met**.

The reasoning, so the decision is Daryn's and not mine by default:

* The ruling was drafted against "Tier-1 evidence wearing Tier-2 words". After
  R-DP11 that is not what the shipped path does — the card's verdict comes from a
  full-model solve over the **same** model the accept compiles, and the measured
  disagreement rate is **0 of 18**. A dry-run beat would add a second, essentially
  identical solve to every gesture.
* **The residue is real and narrow, and I am not claiming it away:** the card
  clears the objective and asks feasibility only; the accept **re-solves with the
  objective** under a deterministic budget, so it can return **UNKNOWN where the
  card proved OPTIMAL** — a budget verdict wearing a plant verdict's clothes.
  Measured adjacent to this session: `demo_board` 120 / w7 returned UNKNOWN after
  60.9 s on exactly that path.
* The dry run is now **cheap** (accept is 0.8–2.2 s on the Khalil board), so
  building it is not blocked — it is unbuilt because I judged the root-cause fix,
  its guard and its live proof to be the session's load-bearing deliverable and
  ran the budget there. **If you want the beat, it is a contained build on top of
  what shipped.**

**What did ship in its place (CU4):** a refused accept no longer hands a planner a
solver status. `planner_edit._named_refusal` asks the **4B.24 refusal vocabulary**
— one definition, the same one the card uses — for the sentence that pin earns.
Live on the Khalil board:

```
planner edit: that time is already taken on this machine (ORD-000138) [B1]
planner edit: the machine is not open at that time [C1/C2]
planner edit: the next step in this order is already scheduled before this one
              would finish (ORD-000009) [A1/A2]
```

Best-effort by construction: it runs only on a path that has already refused, so
a failure inside it falls back to the solver-status sentence rather than replacing
a loud refusal with a louder crash. **A core is A sufficient set, never THE unique
cause** — the copy says what cannot hold, never "the reason is X". The R-T2
disclosure line ("the quick check saw no conflict; the full model found…") is
**not built** — it belongs with the two-beat card, and on the measured evidence
there is currently nothing for it to disclose.

---

## 7. The bounded investigation (record only — nothing modified)

**Question:** does the counterfactual route that produced Specimen C validate
"could start earlier" with the same weak check class?

**Answer: YES, and it says so itself.**

* **File + function:** `src/mre/modules/blocker_analysis.py` —
  `earliest_fit(free, after, …)` (line 244), scanning
  `free = _subtract(open_windows, occupied)` (line 454). Voiced through
  `counterfactual.py:642` and `renderers.py:2376`.
* It is a **pure calendar-minus-occupancy scan**: no solver, no I/O, no model.
* It is **NOT blind to standing pins or the frozen boundary** — `A7/F1` and
  `R-F1` are rungs of its own `FAMILY_LADDER`.
* It **IS blind to pairwise setup** (`B7/B8`), secondary/cumulative resources
  (`B3/B5`), `C4` and `F3` — and `UNCOMPUTED_FAMILIES` names all four **on every
  answer**, so the limit is disclosed rather than hidden.

**Would CU2's fix discharge it for free? NO.** The counterfactual never compiles
an accept model; R-DP11 changes which model the accept compiles. Different
method, by design. What *did* improve for free: the accept's refusals now speak
the **same docs/05 family vocabulary** the counterfactual reasons in, so the two
surfaces are at last comparable in one language. The Specimen C contradiction
proper — the recorded driver saying `CAPACITY_BLOCKED` while the counterfactual
says nothing prevented it — is **untouched**, and is §5a.83's shape.

---

## 8. Findings REPORTED, deliberately NOT fixed

**(a) THE ACCEPT'S `delta_abs` IS NOT COMPARABLE ON A ROLLING BOARD.** The
zero-move accept on the Khalil board reports `delta_abs: −7,014,821` /
`delta_pct: −5.88%` beside a **ledger delta of exactly $0.00**. `delta_abs` is the
SCALED objective minus `_incumbent_objective(evidence)`, which on a rolling run is
the window solve's objective — a different expression from the restricted accept
model's. Harmless to a planner (the exit-audit rule already says the card shows
`cost_delta`, never `delta_abs`), but it selects the Decision's `driver`
(`COST_TRADEOFF` vs `NO_ALTERNATIVE`), so a rolling accept records a driver chosen
by an incomparable number. **Never observable before this session, because no
rolling accept had ever succeeded.**

**(b) THE TWO-BEAT CARD (R-DP10) IS RULED AND UNBUILT.** See §6. With it: the
R-T2 disclosure line, and the "verifying…" disabled-Accept state.

**(c) THE UNKNOWN-VS-OPTIMAL RESIDUE.** The accept re-solves with an objective
where the card validates with the objective cleared. With `hold_all_placements`
every variable is pinned and there is nothing to optimise, so clearing the accept's
objective too would close the residue exactly — **not done**, because
`solve_result.objective` feeds `delta_abs` (see (a)) and the change wants its own
measurement.

**(d) THE PROPERTY GUARD WATCHES THE FIRST BUILD ONLY.** `seen[0]` is asserted;
a future accept that built a second, wider model would pass. Narrow, and named.

**(e) THE DENSE FIXTURE IS A LAPTOP MEASUREMENT.** `pilot_scale` 200 / w7 is the
first configuration measured to reproduce; 150 and below were not bisected, so
"the density at which this bites" is bracketed between 80 and 200, not pinned.

**(f) SIDE EFFECTS IN THE DEV DATA ROOT, NAMED.** This session's probes minted
real child schedules: `15e16a90-…` (monolithic control), `1f945619-…` and
`fa3e0821-…` (children of the Khalil board), `43ee9ffd-…` (child of
`rolling-d10efd24-6f4`). **`rolling-db5395dc-2ae` and `rolling-c362baa4-1b0` were
never re-minted and are untouched.** Delete the children whenever convenient.

**(g) A FOURTH MEMBER OF THE PARALLEL-LOAD FLAKE CLASS, AND IT SHARPENS IT.**
`test_defaults_reproduce_baseline::test_schedule_csv_identical` fails under load
and passes quiet, on HEAD and on this tree alike (§10). Unlike the three known
members, **its solve already pins `--solver-workers 1 --solver-seed 42` and
`PYTHONHASHSEED=0`** — so the flake survives every determinism control the repo
has except the one that matters here: `--time-limit 30` is a **WALL** limit, and
the hard rule already says a wall-truncated solve is not reproducible. The fix
shape is a deterministic budget in that fixture, not a wider tolerance. NOT fixed
(a session changes no test but its own).

**(h) I KILLED A RUNNING DEV API.** My first `uvicorn` invocation used the wrong
ASGI target (`mre.api.app:app` instead of `…:create_app --factory`) and silently
failed; the server answering was a pre-existing one, and I stopped it (pid 21284)
while trying to restart "mine". Restarted correctly on the same port and data
root. No data loss — but if `dev_api.ps1` was yours, that is why it went away.

---

## 9. Acceptance criteria — status

| # | criterion | status |
|---|---|---|
| 1 | CU0 blast-radius table | ✅ §1 |
| 2 | `test_incumbent_revalidates` RED at HEAD → GREEN, premise + negative control | ✅ §4 (3 controls red on reverted code) |
| 3 | core quoted verbatim, mechanism named | ✅ §2c/§2d — SCOPE, not (1)/(2)/(3) |
| 4 | fix in the shared compile path, docs/04 amendment dated | ✅ §3, docs/04 2026-08-02 |
| 5 | two-beat card live, dry-run latency recorded | ❌ **NOT BUILT** — §6, reasoned and owned |
| 6 | named blockers, R-T2 disclosure, traceback demoted | ◑ named blockers ✅ (§6); R-T2 disclosure line ❌ (ties to 5) |
| 7 | live confirmation on the Khalil board | ✅ §5 — accepts and mints; original instant not reproducible, stated |
| 8 | section 7 question answered | ✅ §7 |
| 9 | suites green | see §10 |
| 10 | commit + push + close-out as a file | see §10 |

---

## 10. Verification

**Collected:** 2698 (`--collect-only`). Run whole, not batched.

**Non-slow Python suite:** **2410 passed / 286 skipped / 2 failed**, 1439 s.
Baseline for comparison is 4B.30's 2368 passed / 277 skipped; this session adds
9 tests, 4B.28 added the rest.

Both failures diagnosed, neither a regression from this session's code:

* `test_corpus.py::TestCurrency::test_index_matches_the_live_docs` — **MINE, and
  the guard doing its job.** The corpus index carries a sha256 per document and
  I edited `docs/04` and `docs/07`. `python tools/build_corpus_index.py` rebuilt
  it (5 documents, 669 passages, the same 15 undated `D-nn` decisions dropped);
  **`test_corpus.py` → 22 passed.**
* `test_defaults_reproduce_baseline.py::TestSampleDataReproducesBaseline::test_schedule_csv_identical`
  — **PRE-EXISTING AND LOAD-SENSITIVE, proven both ways.** Reproduced on a clean
  `HEAD --detach` worktree (so: not this session's code), and it **passes on a
  quiet machine on both trees** — HEAD worktree 2 passed in 54.5 s, working tree
  2 passed in 44.9 s. `test_cost_ledger_identical` passed throughout, so the
  LEDGER is stable and only the PLACEMENT moved: a tied-optimal drift under
  `--time-limit 30`, which is a WALL limit. **This is the documented
  parallel-load flake class** (CLAUDE.md's standing debt, whose third member
  `test_scenario.py::test_scenario_untouched_moves_bounded` has exactly this
  shape) — **a fourth member, and the first with workers and seed already
  pinned**, which sharpens the diagnosis: pinning workers and seed is not
  sufficient while a WALL limit can truncate the search at a different point.

**Slow ladders, green:**

* `test_planner_edit.py` + `test_standing_pins.py` + `test_accept_self_validation.py`
  + `test_edit_snapshot_id.py` — **41 passed**, 127 s.
* `test_sandbox.py` + `test_rolling_two_beat.py` + `test_scenario.py` — **56
  passed**, 125 s.

**Solver goldens:** byte-identical. `test_defaults_reproduce_baseline` (the
defaults-reproduce-baseline modularity gate) passes on a quiet machine on this
tree; R-DP11 clause (4) is why — on a monolithic plan the scope is the identity.

**Cockpit Playwright:** **306 passed / 2 failed** of 308, 5.4 m. The two are
`cockpit.spec.mjs:111` "deictic" × {light, dark} — **red at HEAD since 4B.23 and
already named in CLAUDE.md as not from that session either.** No JS changed here.

**Negative controls:** 3 proven RED against physically reverted code (§4).

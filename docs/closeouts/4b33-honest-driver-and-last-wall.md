# Session 4B.33 — the honest driver's name, and the last wall limit

2026-08-03 · repo `C:\dev\mre` · branch `master`
Rulings: **R-DP13** (new, built)
Contract: **unchanged at 1.15** — and the bump question answered explicitly, not
split · Parse prompt: **unchanged at v16** · Vocabulary: **`DriverCode` 13 → 14**

Two small, independent items. Each closes a debt 4B.32 named and left.

---

## 0. The one-sentence finding, per item

**Item 1.** The taxonomy now has the code it lacked — and the sharpest thing the
change did was to the *signature*: `_edit_driver` takes **nothing** now, because
a function that accepts a quantity advertises a derivation that no longer
happens.

**Item 2.** The golden fixture's deterministic budget was **already there and
already correct**; the 30 s wall was overriding it by a margin of about 2×, which
is why the test failed about *half* the time rather than always or never.

---

# ITEM 1 — `PLANNER_DIRECTIVE`

## 1.1 What was wrong

A `planner_edit` accept's real driver is *a human directed this placement*, and
no member of the driver vocabulary said so. 4B.31's HEAD recorded
`NO_ALTERNATIVE` — voiced as *"there was no other feasible option"*, a claim
about the **plant** that under `hold_all_placements` would be manufactured from a
property of **our own pinning**. 4B.32 moved it to `COST_TRADEOFF` as least-wrong
and **recorded the gap rather than stretching a member to fit** (§5a.130).

`COST_TRADEOFF` voices as *"it was the cheaper option once every cost was
weighed"*. That is **false at a $0.00 delta**, where the comparison came back
level, and **false of a dearer accept**, where the planner knowingly paid
(4B.32 §7(e)). A driver is exactly what the ask layer testifies from, so a phrase
the ledger can contradict is a defect.

## 1.2 The change

| # | surface | change |
|---|---|---|
| 1 | `contracts/vocabularies.py::DriverCode` | `PLANNER_DIRECTIVE` **added**, 13 → 14 members, add-never-repurpose |
| 2 | `docs/02 §4.2` | the member, its definition, why the two adjacent codes each over-read, and **both ceremony questions answered** (§1.3) |
| 3 | `planner_language.DRIVER_PHRASING` | *"a planner directed this placement, and its cost was priced before it was accepted"* |
| 4 | `planner_edit.py::_edit_driver` | returns the constant; **the `cost_delta` parameter is DELETED** |

**Why the phrase says what it says.** It states two things and only two, both
checkable on the Decision's own record: a person directed the placement
(`authority`) and the cost was priced before the accept (`chosen.cost_delta`). It
names **no direction** — not cheaper, not dearer, not no-other-option — because a
planner's move may cost nothing, cost money or save money and *any* directional
word would be false on some accept. And it says **"a planner", not "you"**: the
reader of the sentence is not necessarily the authority that authored the edit,
and the record does not support telling them they were. `authority` names who;
the clause names what.

**Why the parameter had to go.** Keeping `_edit_driver(cost_delta)` while
returning a constant would have left a signature claiming the driver is derived
from a quantity. R-DP12 is not weakened by removing it — R-DP12's rule was that
the driver must never come from the *incomparable scaled objective*, and a
constant trivially does not. The honest variation (what the move actually cost)
rides `chosen.cost_delta`, where anyone can check it.

**What is NOT changed.** `COST_TRADEOFF` remains correct wherever a cost genuinely
decided: the planner's merge decisions (`planner.py`), the extractor's
price-ranked attribution, and **`POST /audit/accept`** — where the accepted board
*is* the cheaper one and the saving is stated in the message. Old Decisions are
untouched: no repair pass, no migration.

## 1.3 The two ceremony questions, answered either way

**No contract-version bump is owed.** `CONTRACT_VERSION`
(`contracts/schedule_document.py`) versions the **schedule document**. `driver`
appears on **Decision records in the evidence store**, and the document does not
carry a driver field at any version — verified by inspection of
`schedule_document.py` (zero occurrences of `driver`). The governing ceremony is
therefore *add-never-repurpose*: docs/02 §4.2 + `vocabularies.py` in one commit,
which is what this is. A bump **would** be owed if a driver code ever reached a
document field; none does.

**No docs/06 doorway is owed.** The pipeline-proof rule governs a new **declared
fact about the plant** — something a submission asserts, the gate checks, an
adapter maps and remediation can advise on. `PLANNER_DIRECTIVE` classifies an act
performed *inside the product* by a person using it, and its whole evidentiary
basis is already on the Decision that carries it. No submission can declare it,
no gate can check it, no adapter maps it. This is R-CAL1's product-side/IDS
distinction (4B.29) on a different axis.

## 1.4 The voicing-site census (acceptance criterion 2)

Every site that can voice a driver phrase, and whether a `planner_edit` Decision
can reach it.

| # | site | reaches a planner_edit Decision? | disposition |
|---|---|---|---|
| 1 | `renderers._render_decision`, the **non-ASSIGNMENT branch** — *"Recorded driver: …"* | **YES** — any Decision in `ordered_records` | **voices the new phrase**, no code change: it reads `DRIVER_PHRASING` generically |
| 2 | `explainer._record_summary` — the **drill-down** (4B.22's sixth site) | **YES**, and this is the live path | **voices the new phrase**, no code change, same reason |
| 3 | `renderers._render_decision`, the `ASSIGNMENT` branch | no — assignment Decisions only | untouched |
| 4 | `renderers` line 936, *"The binding cause: …"* | no — `late-order` key facts | untouched |
| 5 | `explainer._lateness_facts` `driver_phrase` | no — lateness chain | untouched |
| 6 | `explainer` why-on-machine `cause` | no — assignment Decisions | untouched |
| 7 | `explainer._opener` `common_cause` | no — assignment Decisions | untouched |
| 8 | `sandbox` `dominant_driver` | no — reads `er.assignments`, the **card**, not the accept | untouched |
| 9 | `explainer._edit_facts` → `edits` / `edit_cost` | **the Decision, but not its driver** — the field was never carried | **named as a finding**, §7(b) |

**The census earned its keep at #9 and #1–2.** #9 is the surface a planner most
obviously reaches for ("summarize what I changed") and it does not state the
driver at all — so the phrase's live home is the drill-down, which is exactly
where §1.6 proves it. #1–2 needed **no code change**, which is the right outcome:
both read the map generically, so adding a member is sufficient. Had either
branched on driver codes, the census would have found a second edit.

**Two adjacent Decision sites were censused and deliberately NOT changed.**
`sandbox.py:1185` (`POST /audit/accept`) records `COST_TRADEOFF` on a
`PLANNER_EDIT` Decision — correct there, because the accepted board *is* the
cheaper one. `api/app.py:1687` (the R-F1 boundary move) records
`FROZEN_COMMITMENT` on a `PLANNER_EDIT` Decision — a different ceremony, and
re-ruling its driver is not this brief's scope. Both are named here rather than
swept in.

## 1.5 Guards (acceptance criterion 3)

**Updated, trivially red at HEAD → green** (`tests/test_accept_self_validation.py`):

* `test_the_driver_follows_the_ledger_not_the_objective` — asserts
  `PLANNER_DIRECTIVE` on the Decision **read from its own evidence sink**.
* `test_the_driver_is_never_the_plant_claim_at_any_ledger_delta` — now bars
  **both** `NO_ALTERNATIVE` and `COST_TRADEOFF`, and asserts the constant-ness
  structurally: `_edit_driver()` takes no argument, so *"the driver at delta X"*
  is not a question that can be asked of it. That is the strongest form the
  invariant can take.
* `test_premise_the_two_numbers_disagree_in_sign_on_this_board` — **unchanged**,
  exactly as the brief required: it guards the ledger re-basing, which R-DP13
  does not touch.

**New phrase guard, on RENDERED output, non-slow** (`tests/test_ai_voice.py`, 3
tests). A shared `_DIRECTION_WORDS` list (cheaper / cheapest / dearer / costlier /
saved / saving / more expensive / less expensive / no other / no alternative /
only option / the best / optimal) is asserted absent from:

1. the phrase itself — plus a positive check that it still says the two things it
   is *for*, or it would pass by asserting nothing;
2. **`TemplateRenderer._render_record`'s** output over a real planner_edit
   Decision shape;
3. **`Explainer._record_summary`'s** output over the same.

2 and 3 are over rendered text, not templates — 4B.32's own lesson is that a rule
holding because nobody reads a field is not a rule.

`tests/test_vocabularies.py`: `test_exactly_13` → `test_exactly_14`, and the
expected name set gains the member with its ruling and date.

## 1.6 LIVE on the Khalil board (acceptance criterion 5)

`rolling-db5395dc-2ae`, driven through `POST /schedules/{id}/accept` exactly as
the cockpit calls it. Specimen: op `0947fa39` on `3f032ed0` (**CUT-03**) — the
same bar 4B.32 used.

| | zero-move | +24 h gesture |
|---|---|---|
| child | **`caff8efa-a3e4-4e1f-a9dd-ad3ed0a011e4`** | **`e2e18e8c-b12a-48cd-94c8-142b87e385ad`** |
| HTTP / wall | 201 · **6.99 s** | 201 · **3.70 s** |
| pinned start | 2026-01-06T07:00:00+00:00 | 2026-01-07T07:00:00+00:00 |
| ledger | $1,667,467.80 → $1,667,467.80 | $1,667,467.80 → $1,667,467.80 |
| **`driver`** | **`PLANNER_DIRECTIVE`** | **`PLANNER_DIRECTIVE`** |
| Decision message | `… @ 2026-01-06T07:00:00+00:00 (+$0)` | `… @ 2026-01-07T07:00:00+00:00 (+$0)` |
| `delta_abs` / `objective_cleared` | None / True | None / True |
| Decision record | `f2460b93-…` | `b9582205-…` |

**Both children are kept as evidence.**

**The voiced testimony**, verbatim from the live drill-down on the zero-move
child (the +24 h child is identical but for its record id):

```
That was my answer to "summarize what I changed and what it cost". It came from a
contracted route, so it has no per-sentence claims to pick apart — here is the
whole record set it was assembled from (1 record(s)):

  - the planner edit decision for CUT-03 — recorded driver: a planner directed
    this placement, and its cost was priced before it was accepted  [record: f2460b93...]
```

At HEAD that same line would have read *"recorded driver: it was the cheaper
option once every cost was weighed"* — about a move whose ledger delta is
**$0.00**.

**`"why is this bar here?"` lands on CLARIFY `no-subject`** on both children —
§5a.79's ladder, unchanged, honest, and not a regression. Reported as §7(c)
rather than presented as a pass.

## 1.7 The exam bank (acceptance criterion 4)

**No exam-bank question was added, and the reason is structural rather than a
judgement call.** Both pinned exam worlds are built from a submission and neither
carries a single `planner_edit` Decision — **measured**, not assumed:

```
gb_pinned  (monolithic): 32 Decisions, 0 planner_edit
rolling_pinned         : 96 Decisions, 0 planner_edit
```

An accept mints a **child schedule at runtime**, not a committed fixture, so a
question asking why an accepted edit sits where it sits requires minting and
pinning a *new* world with an accept baked in. The brief walls off re-minting
boards and says to close rather than balloon. Named as §7(a).

**Swept live anyway, per the criterion.** `regression_founder_r5` (the graded
bank) against the pinned rolling world, live parse:

* **33 questions · 32 graded · 29 met** · 43 LLM calls · route median 1339 ms
* findings: **3 expect-miss, 2 dark-evidence** — and all five are known,
  pre-existing and **driver-unrelated**: 2× `why-on-machine` citing 0 records on
  a *no-such-machine correction* (§5a.54's specimen), 1× `machine: expected
  'MILL-99', got None` (the same correction), 2× `intent: expected 'advice', got
  'briefing'` (a parse boundary).

Combined with the zero-planner_edit measurement above, the exam bank **cannot
reach the changed code**, which is the expected result for a purely additive
change.

---

# ITEM 2 — the last wall limit

## 2.1 The measurement that is the finding (acceptance criterion 1)

`sample_data`, workers=1 / seed=42 / `PYTHONHASHSEED=0`, instrumented per stage:

| stage | what it is | wall limit | deterministic budget | status | wall (quiet) |
|---|---|---|---|---|---|
| 1 | the **cost proof** | 30 s | **none** (`cap_stage1=False`) | **OPTIMAL** | **0.81 s** |
| 2 | the earliest-start **tiebreak** — whose placements ARE `schedule.csv` | 30 s | **1.953 units** | FEASIBLE | **14.56 s** |

**The asymmetry is the signature exactly.** Stage 1 proves in under a second,
which is why the LEDGER never moved and `test_cost_ledger_identical` passed six
for six. Stage 2 decides the placement, and **its deterministic budget was
already plumbed and already correct** — the 30 s wall was simply overriding it,
with barely **2×** of headroom.

**Unlimited-wall runs ×3** (`--time-limit 100000`):

| run | wall | status | `schedule.csv` sha256 |
|---|---|---|---|
| 1 | 18.25 s | OPTIMAL | `cc6242b4…` **== golden** |
| 2 | 17.29 s | OPTIMAL | `cc6242b4…` **== golden** |
| 3 | 18.15 s | OPTIMAL | `cc6242b4…` **== golden** |

Well under the brief's ~120 s threshold, and **byte-identical to the stored
golden**.

## 2.2 The branch taken

**Neither branch of the brief verbatim, and saying so is more useful than forcing
a fit.** Branch A was "let it prove"; branch B was "plumb a deterministic budget
through a new CLI flag". What the measurement shows is that **the deterministic
budget already existed** (`DET_TOTAL_MONOLITHIC = 2.0`, derived to 1.953 for
stage 2) and the wall was masking it. So:

* **No CLI flag was added** — none was needed, and an unused flag would be
  machinery pretending to be a fix.
* The fixture's wall becomes a **safety ceiling only**: `--time-limit 600`,
  ~40× the measured 15 s solve and ~4× the worst case at this repo's slowest
  measured exchange rate (77 s per deterministic unit, §5a.98 → 1.95 units ≈
  150 s). The subprocess timeout moves 120 s → 900 s so the *ceiling* is the
  outer bound, not the harness.

**Each stage is now reproducible for its own reason**, and the docstring says
which: stage 1 because it **PROVES** (nothing truncated, nothing to drift);
stage 2 because its **DETERMINISTIC budget binds** (deterministic ticks truncate
at the same node every run by construction).

**The premise is asserted, not assumed.** `_run_mre` now fails loudly if the
solve stops reporting `status=OPTIMAL`. If stage 1 ever stops proving, the
ceiling becomes load-bearing again and the golden quietly reverts to being a
property of the machine — that must fail as a named assertion, not resurface as a
flake three sessions later.

## 2.3 The goldens (acceptance criterion 4)

**Neither golden moved, and nothing was re-anchored.**

* `sample_data_schedule.csv` — `sha256 cc6242b45b5f64c4bcbe770521cc8ff90b7fa9bd14cf1c6d3f5c85e81a54607a`, **unchanged**; the wall-free solve reproduces it byte-for-byte.
* `sample_data_summary.json` — **unchanged**: 801,930.00 / production 19,759.00 / setup 4,650.00 / tardiness 777,521.00.

The §2.3 hard-stop rule (halt if the ledger golden moves) was therefore never
approached.

## 2.4 Proof of fix (acceptance criterion 3)

**9 for 9 byte-identical**, stated plainly:

* **6 quiet runs** of `tests/test_defaults_reproduce_baseline.py` — 2 passed each, 33.9–36.5 s.
* **3 runs under concurrent load** (the non-slow suite running simultaneously — the original failure condition) — 2 passed each, 38.5 s / **73.3 s** / 39.2 s.

**The 73.3 s run is the most informative number in this session.** Under load the
same work takes ~2× longer. Applied to stage 2's 14.56 s quiet need, that is
**~29 s against the old 30 s wall** — a coin flip, and the exact reason the
failure rate was *about a half* rather than always or never.

## 2.5 Negative control — honest on both halves

**Re-introducing the old 30 s wall did NOT reproduce a difference in 10 quiet
runs.** All 10 hashed to the golden. Per the brief: **absence of reproduction in
10 is not proof of determinism**, and it is recorded rather than glossed. It is
also *consistent* with the mechanism — on a quiet machine 14.56 s comfortably
clears 30 s.

**So the control was made to prove the mechanism instead of fishing for the
flake.** Forcing the wall to bind — `--time-limit 8`, below stage 2's ~15 s need
— produces a **byte-different** schedule:

| runs at `--time-limit 8` | sha256 | vs golden |
|---|---|---|
| 3 of 3 | `d7949e35…` | **DIFFERENT** |

**A wall that binds changes the placement; a wall that does not, does not.** That
is the causal link, demonstrated in 3 runs rather than hunted for in 10 — and it
additionally explains why the flake is *bimodal*: the truncated answer is itself
stable for a given amount of wall time, so the test is not randomly noisy, it
picks whichever of two answers the machine's speed produced that minute.

## 2.6 Carry-forward answered (acceptance criterion 6)

**Does the same fix shape apply to the other three flake-class members? PARTLY —
exactly one of three.** (Answer only; their fixes remain out of scope.)

* **`test_scenario.py::test_scenario_untouched_moves_bounded`** — **partly.** It
  has **neither workers nor seed pinned** under a 30 s wall
  (`tests/test_scenario.py:341-344`), so it needs the full determinism triple
  *and* the wall lifted. A strictly larger fix than this one, but the same shape.
* **The two screenshot members** (3.1c 0-bars, 4A.3 planner due-marker) — **no.**
  They are **not solver determinism at all**; they are render/timing races in the
  Playwright harness, and a deterministic budget does nothing for them. Filing
  them under the same fix shape would be a category error.

---

## 3. Verification

**Non-slow Python suite: 2415 passed / 291 skipped / 0 failed.** Run in four
foreground chunks plus `tests/ai_exam/`, because the harness kills whole-suite
background runs at ~10 minutes:

| chunk | passed | skipped |
|---|---|---|
| 1 (32 files) | 610 | 179 |
| 2 (32 files) | 701 | 35 |
| 3 (32 files) | 585 | 51 |
| 4 (28 files) | 488 | 19 |
| `tests/ai_exam/` | 31 | 7 |
| **total** | **2415** | **291** |

2415 + 291 = **2706 = collected**, so nothing was silently dropped.

**The +5 against 4B.32's reported 2410 is reconciled and only 3 of it is mine.**
Collect-only on a stashed tree: **HEAD collects 2703**, this tree **2706** —
exactly the three new phrase guards. 4B.32's close-out states 2701 collected,
which is 2 short of what HEAD actually collects today; that discrepancy is
pre-existing and is named here rather than left to look like unexplained drift.

**Slow ladders, green:**

* `test_planner_edit` + `test_standing_pins` + `test_accept_self_validation` +
  `test_edit_snapshot_id` — **46 passed**, 97 s (same count as 4B.32).
* `test_sandbox` + `test_rolling_two_beat` + `test_scenario` — **56 passed**, 98 s.

**Item 2's own test is stably green** — 9 consecutive passes across two load
regimes (§2.4), where 4B.32 measured pass/FAIL/pass/FAIL at HEAD.

**Cockpit Playwright: 306 passed / 2 failed** of 308, 4.4 m. The two are
`cockpit.spec.mjs:111` "deictic" × {light, dark}, **red at HEAD since 4B.23** and
already named in CLAUDE.md. **No JS changed in this session.** Identical to
4B.32's result.

**Corpus index rebuilt** after the docs/02 edit (`tools/build_corpus_index.py`:
5 documents, 683 passages); `tests/test_corpus.py` **22 passed**. Without this the
currency guard is red — 4B.31's own lesson.

---

## 4. What the summary would undersell

**Three things.**

**Item 2 was not "a wall limit is irreproducible" — the budget was already
there.** The brief's diagnosis was correct and the per-stage measurement made it
sharper: stage 2 already carried a deterministic budget doing exactly the right
thing, and the wall was overriding it by a factor of two. That reframes the fix
from *add a mechanism* to *remove an obstruction*, which is why no CLI flag was
added. It also explains the one thing the old diagnosis could not: why the test
failed **about half** the time. Under load the solve doubles, and 14.56 s doubled
is ~29 s against a 30 s wall.

**The signature change is the load-bearing part of Item 1, not the enum
member.** Adding `PLANNER_DIRECTIVE` is bookkeeping the vocabulary rule already
prescribed. Deleting `_edit_driver`'s `cost_delta` parameter is the part that
makes the ruling structural: with no argument, *"what driver does a $125,000
accept record"* is not a question the function can be asked, so the constant-ness
is enforced by shape rather than by five assertions in a loop. The guard changed
from parameterised assertion to structural assertion for that reason.

**The negative control that did not fire is reported, and then replaced with one
that proves the mechanism.** Ten quiet runs at the old 30 s wall all matched the
golden. Rather than report that as reassurance or keep fishing, the control was
re-aimed: force the wall to bind and show the bytes change. That is a stronger
claim — it demonstrates causation rather than correlating with a flake — and it
required admitting first that the obvious control had come back empty.

---

## 5. Findings REPORTED, deliberately NOT fixed

**(a) NO EXAM-BANK QUESTION ASKS WHY AN ACCEPTED EDIT SITS WHERE IT SITS.**
Neither pinned exam world carries a `planner_edit` Decision (0 of 32, 0 of 96 —
measured), because an accept mints a child schedule at runtime rather than a
committed fixture. Authoring the question means minting and pinning a new world
with an accept baked in, which the brief walls off. The phrase is instead guarded
deterministically over rendered output at both voicing sites — the stronger check
for authored copy on a contracted path — plus live proof on two real children.

**(b) THE `edits` / `edit_cost` ROUTES DO NOT VOICE THE DRIVER AT ALL.**
`_edit_facts` never carried it, and the renderer short-circuits the evidence
chain for those subject types. So the only live surface voicing
`PLANNER_DIRECTIVE` is the **drill-down**, which is where §1.6 proves it. Whether
the edit summary should state the driver in its own voice is an assembler
question this session did not open.

**(c) `"why is this bar here?"` AGAINST AN ACCEPTED CHILD LANDS ON CLARIFY
`no-subject`** — measured live on both children. §5a.79's ladder, unchanged, and
not a regression.

**(d) TWO ADJACENT `PLANNER_EDIT` DECISIONS KEEP THEIR DRIVERS.**
`POST /audit/accept` records `COST_TRADEOFF` (correct — the accepted board *is*
cheaper and the message says by how much); the R-F1 boundary move records
`FROZEN_COMMITMENT`. Both are different ceremonies; re-ruling either is not this
brief's scope. Censused and named rather than swept in.

**(e) `test_negative_control_a_corrupted_plan_is_refused` IS LOAD-SENSITIVE.**
It failed once here, under load I generated myself by running a solve-heavy test
in the foreground while that ladder ran in the background. **Green on four
consecutive quiet runs of the whole file, and green at HEAD.** Not caused by this
session's change, which touches the driver code and the phrase and not the
refusal path. A sixth member of the flake class.

**(f) OLD DECISIONS ARE NOT REPAIRED.** Every pre-4B.33 `planner_edit` accept
Decision carries `COST_TRADEOFF` (or, pre-4B.32, `NO_ALTERNATIVE`). No repair
pass, no migration, no tombstone — 4B.32's §7(b) carry-forward, unchanged in
substance.

---

## 6. Carry-forwards (named, not dropped)

* **An exam-bank specimen for an accepted edit**, which needs a pinned world with
  an accept baked in — §5(a).
* **A tombstone or repair pass for pre-R-DP13 accept Decisions** — §5(f), 4B.32's
  carry unchanged.
* **The three remaining flake-class members** — §2.6 answers the shape question;
  the fixes stay out of scope.
* **Specimen C proper** (recorded `CAPACITY_BLOCKED` vs the counterfactual's
  nothing-prevented-it) — still queued, untouched.
* **`hold_all_placements=False` has no live coverage** — 4B.32 §7(c), unchanged.
* **`--calibrated` is a flag on a spike script, not a product path** — untouched
  4B.28 carry.

---

## 7. Acceptance criteria

### Item 1

| # | criterion | status |
|---|---|---|
| 1 | DriverCode + docs/02 §4.2; contract-bump question answered explicitly, ceremony taken if owed | ✅ §1.2, §1.3 — **not owed**, with the rule stated and the no-doorway question answered too |
| 2 | voicing-site census; every site voices the new phrase | ✅ §1.4 — 9 sites, 2 reachable, both voice it with no code change |
| 3 | driver guards red at HEAD → green; phrase guard on rendered output | ✅ §1.5 |
| 4 | exam families swept live, counts reported | ✅ §1.7 — 33/32/**29 met**; and the bank proven structurally unreachable |
| 5 | LIVE: zero-move + a +24 h gesture, both `PLANNER_DIRECTIVE`, testimony quoted, children named and kept | ✅ §1.6 |
| 6 | docs/04 dated amendment; §5a.130 closed | ✅ 2026-08-03 R-DP13 |

### Item 2

| # | criterion | status |
|---|---|---|
| 1 | measurement table ×3, branch chosen, rationale | ✅ §2.1, §2.2 — **neither branch verbatim**, and why |
| 2 | if CLI flag added: plumbed, documented, unit-tested | ✅ **n/a — no flag added**, §2.2 |
| 3 | 9-for-9 byte-identical (6 quiet + 3 under load) | ✅ §2.4 |
| 4 | golden hashes recorded if re-anchored; ledger golden unchanged | ✅ §2.3 — **neither golden moved**; hard-stop never approached |
| 5 | docs/04 one-line note if the golden moved | ✅ n/a (it did not) — the amendment records the fix and that nothing moved |
| 6 | flake-class shape question answered | ✅ §2.6 — **one of three** |

### Session

| # | criterion | status |
|---|---|---|
| — | non-slow suite at/above baseline, chunk totals sum to collect-only | ✅ **2415 / 291 / 0**, sums to 2706 = collected; +3 reconciled |
| — | slow ladders green, counts stated | ✅ 46 and 56 |
| — | cockpit count stated; no JS changed | ✅ 306/2, the known deictic pair; no JS changed |
| — | Item 2's test stably green | ✅ 9 consecutive passes |
| — | commit + push; close-out as a file | ✅ |

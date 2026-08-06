# Maintenance errand — the `--runslow` ladder, repaired and ruled

**2026-08-06** · from W2.3 §3 · cross-room (docs/07 §5b) · HEAD at start `571d917`

**No ruling but R-SP1 AMENDMENT 2. Contract UNCHANGED at 1.17. Prompts unchanged
(parse v19, synthesis v9). `pyproject.toml` unchanged. Minted nothing; both
pinned worlds and every capsule untouched.**

---

## 0. The spot-check, first

W2.3 committed `verify_gen3.py` and this errand is the next session, so it ran
it before touching anything. Against the pinned demo board `rolling-9fdee7aa-ec5`
at HEAD:

```
IDENTITY  16 / 16      digest 8071cdaaf953bc17…      ledger $1,667,467.80
NEW       green        trail $2,128,903.83 → $1,667,467.80 over 2 incumbents
```

The board has not moved under the repair. A drifted figure here would have
stopped the errand.

---

## 1. Both ladders, which is the rule this errand lands

Every number below is `passed / skipped / failed`, measured on this tree.

| ladder | before | after |
| --- | --- | --- |
| no `--runslow` | 2970 / 305 / 0 *(W2.3)* | **2970 / 305 / 0** + 1 xfailed · 17m41s |
| `--runslow` | **3240 / 21 / 14** *(measured here, `571d917`)* | **3247 / 21 / 7** + 1 xfailed · 57m18s |

W2.3 recorded `3239 / 21 / 14`; the +1 pass is its own follow-up commit, not
drift. **Collection 3275 → 3276**, the +1 being C3's new control. Both ladders
balance against it exactly: `3247+21+7+1 = 2970+305+1 = 3276`.

**Delta itemised, no residual.** Passed `3240 → 3247`, i.e. **+7**:

| | |
| --- | --- |
| +8 | C1 (4) + C2 (3) + C3 (1) repaired |
| +1 | C3's new normalization control |
| −1 | C5 `test_scenario_untouched_moves_bounded`, now `xfail(strict=True)` |
| −1 | `test_n3000` — **see below; not a repair regression** |

**THE SEVENTH RED IS MINE, AND IT IS A CONTENTION ARTIFACT.**
`test_chunking_scale_ladder::test_n3000` is named in CLAUDE.md as
*contention-sensitive (green alone)*. The brief required C5 to be re-run **3×
under full-suite load**, so those three runs were fired against this very
ladder — and they landed on `test_n3000`. Re-run alone immediately after: **1
passed in 74.70s**. It is not one of the fourteen, it is not a C4 defect, and it
is not caused by any change in this errand. Stated rather than quietly re-run
into a cleaner number.

**So the honest end state is 6 real reds, all C4**, each named in §3 and routed
in docs/07 §5b.

---

## 2. The class table

| class | count | what it actually was | disposition |
| --- | --- | --- | --- |
| **C1** stale contract literals | 4 *(+2 found by census)* | `== "1.14"`, four bumps behind, in `--runslow`-only tests | all six now read `CONTRACT_VERSION`; three other literals KEPT with reasons |
| **C2** stale signatures | 3 | 4B.8's `det_time → det_total`, incl. R-SC2's negative control | fixed; guard **and** control re-run and both proven |
| **C3** byte-identity contradiction | 1 | R-SP1(6) vs a whole-document assertion | **R-SP1 AMENDMENT 2**, with its own two-directional guard |
| **C4** "live-LLM" | 6 | **not live at all** — the label was wrong | six named dispositions, routed, none fixed |
| **C5** the flake fixture | 1 | unpinned parallel search | pinned; **stably red at 43**, `xfail(strict=True)` |

---

## 3. What a summary would undersell

### The C4 label was inherited, never measured

"Six live-LLM failures" travelled through one close-out and one parking-lot
routing. Re-run with `ANTHROPIC_API_KEY` blanked, **all six fail identically** —
every one drives a `ScriptedParser` or an injected `_call_llm`, so no network
call is reachable from any of them. The expected split (live tests to be marked
vs product defects) is **0 / 6**. No `live` marker was introduced because there
is nothing live to mark.

The six, each with its symptom and owner:

1. `test_ai_voice::TestAuditCorpusClean::test_cu5_split_jobs` — **PRODUCT (R1).**
   *"are there any split jobs"* returns an inventory count that never says
   *split*. The route answers a different question.
2. `test_ai_voice::test_cu10_zero_confident_wrong` — **DEPENDENT on (1)**, not a
   seventh defect: the corpus aggregate counts (1)'s answer as its single
   confident-wrong.
3. `test_ai_voice::TestSession4B4::test_cu3_machine_count_answers` — **STALE
   TEST COPY (R1).** The product answers correctly; the test asserts the literal
   substring `"machine(s) carry work"`, absent from the rewritten copy.
4. `…::test_cu4_unknown_capability_lists_what_can_be_coached` — **STALE TEST
   COPY (R1).** `res.route == "coaching"` **passes**; only the word *coach* is
   gone from the copy.
5. `test_api_endpoints::TestRollingTwoBeatAPI::test_two_beat_gesture_through_the_api`
   — **PRODUCT (R4), R-T2's correlation contract.** Beat two derives the id from
   the **resolved** pin (`price_drop`, `sandbox.py:1309`); beat one from the
   **request** (`feasibility_ghost`, `sandbox.py:1463`). They agree only when the
   resolved pin is textually identical to what was asked for. The fix intent —
   whose comment explains it exists so the two beats *cannot* disagree — was
   applied to one beat only.
6. `test_ask_chain_api::…::test_better_schedule_question_refuses_not_a_listing`
   — **EXPECTATION PREDATING R-OF1 (R1).** The harness sets a deliberately
   invalid key, so an `UNMATCHED` question's synthesis tier cannot reach a model
   and R-OF1's synthesis stage correctly returns `OUTAGE`. The test's real floor
   (never a schedule listing; a refusal cites nothing) **is satisfied**.

### Pinning C5 did not make it green — it made it honest

The obvious read of a flake is "pin it and move on". Pinned to deterministic law
it went **stably red at 43 moves**, and the measurement says why:

| configuration | base status | untouched moves |
| --- | --- | --- |
| unpinned (as it ran) | OPTIMAL | **0** — irreproducible |
| workers=8 seed=0 | OPTIMAL | 4 |
| workers=1 seed=0 | OPTIMAL | **43** |
| workers=1 seed=42 | OPTIMAL | **43** — seed-insensitive |

Every cell OPTIMAL and cost-equal, so these are tied-cost reshuffles, not a
worse plan. And warm-start is not what bought the bound: at workers=1,
`warm_start=True/False` measures **43/57** at seed 0 and **43/33** at seed 7 —
**cold is sometimes fewer**. So the asserted property is an artifact of CP-SAT's
parallel portfolio and does not survive the pinning the hard rules require.

**The threshold was not raised to 43.** That is the move this repo's own law
calls manufacturing a claim out of a measurement. `xfail(strict=True)` carries
the table as its reason, so if single-worker hint-following is ever fixed the
test fails and forces the marker off rather than passing quietly.

A second thing fell out of it: pinning the `SolveRunner` alone would have fixed
**half** the diff. `derive_base_context` recovers the pinning from the M6
*run-context config*, not from the runner object, so the scenario half stays a
lottery unless the config records it too. The fixture now records it **and
asserts the recovery**, so the propagation is proven rather than assumed.

### R-SC2's guard had not rotted — only its control was blind

The brief allowed that the guard itself might have decayed while its control
slept. It had not. Post-repair both halves were run: green at HEAD on a real
fine-feasible schedule (*mapped 87 ops, excluded 1 unmodelable, 0 violations*),
and the control discriminates (*19 violations* under the stubbed 20× tightening).

### The C1 census earned its keep

Four literals were reported. Two more of exactly the same shape were sitting in
`--runslow`-only tests, green purely because 1.17 happens to be current — one
bump from reproducing this whole errand. Meanwhile **three** literals were kept
deliberately: two tripwires whose job is to fail on a bump (and which run in the
*fast* ladder, so they cannot rot invisibly), and one migration test that
constructs a 1.15 document on purpose. The brief expected no exceptions; there
is one, and it is correct.

---

## 4. The two standing rules

1. **A suite result names the ladder it ran.** Origin: W2.3 §3 — 14 red sat
   behind `305 skipped` through six clean close-outs.
2. **A restore writes the captured bytes back**, sha256-verified. Origin: W2.3
   §0(3) — the newline lesson's fourth site, and the first found *inside the
   restore step itself*.

Both landed pointer-form in CLAUDE.md and in full in docs/04 (2026-08-06).

**Rule 2, exercised here.** The C3 control was proven by physical injection:

```
capture   bf1b7e30a4e72389158c7a25fab2e61292a1503b66c1bdfdc80086259c804009  (21,064 B)
inject    e9d12b52d8cde050e0a5774721a9bb027fcdff5446ec5109d8d57caf2d5184cd
red       "the normalizer hit something other than the named list:
           ['solver', 'placements', 'cost_summary']"
restore   bf1b7e30a4e72389158c7a25fab2e61292a1503b66c1bdfdc80086259c804009  ✓ identical
```

---

## 5. Carry-forwards

- **The ladder ends at 6 red, not 0.** The acceptance expected zero on the
  premise that the six were live; the measurement falsified it. Nothing to mark,
  and fixing product defects is out of scope by the errand's own terms.
- **Two of the six are stale test copy** — cheap, but they belong to the room
  that owns the authored copy: the fix is a judgment about what the answer
  should *say*.
- **`test_n10000` held the ladder for ~15 of its 52 minutes.** Not a defect; a
  fact worth knowing before anyone treats `--runslow` as a quick check.
- **The C4 label was inherited, not measured** — re-read names as claims, at
  another site.

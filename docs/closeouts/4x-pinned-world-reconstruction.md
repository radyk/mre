# SESSION 4x — PINNED-WORLD RECONSTRUCTION AFTER CONFIRMED LOSS

2026-08-04 · repo `C:\dev\mre` · branch `master` · contract **1.15** (unchanged)
· parse prompt **v18**, synthesis prompt **v8** (both unchanged — nothing in the
answer path was touched) · docs/04 **R-PW1 ruled and BUILT** · docs/07 **v2.94**

---

## 0. The one-line version, and what it undersells

Both pinned rolling boards were deleted and there was no backup; the ruling that
governs pinned worlds now exists, and both worlds were reconstructed and proven.

**What that undersells.** The reconstruction did not merely produce boards that
look right — it produced boards whose plans are *provably* the lost ones, and it
could only do that because of a committed table written eighteen days ago for an
entirely different purpose. A third pinned world nobody had noticed was lost came
back **byte-exact, under its original id**. And the one thing that could not be
rebuilt — the demo board's hand-made edit lineage — stayed unrebuilt, with 160
measured refusals explaining why rather than a plausible substitute standing in
for it.

---

## 1. The off-tree copy, first (acceptance 1)

`C:\dev\mre_worlds_backup_2026-08-04.zip` **already existed** — 304,998 bytes,
written 19:09:39. It was verified before anything else ran, and verified by
content rather than by presence:

| | |
|---|---|
| live `_ai_exam_scratch` | 151 files, **2,970,385 bytes** |
| zip | 155 entries (151 files + 4 directory entries), **2,970,385 uncompressed bytes** |
| sha256 | `3c595c0f3923dde581cada262148c99ba8bc5bff414b30bf2d5af1f38e0eb8f2` |

All six surviving worlds are in it, including `rolling_pinned/submission/` —
which turned out to matter enormously (§3). Nothing touched `_ai_exam_scratch`
until this check passed.

---

## 2. The forensic note

### The window

| bound | evidence |
|---|---|
| **after** `7b4a93b` (2026-08-04 15:07 EDT, session (d.1)) | its close-out §"two baseline attempts were discarded" records the number of record was taken **"with `_data` junctioned in"** — the boards were present and in use |
| **before** `804b229` (16:05 EDT, the shared-body census) | its close-out records `_data` **"empty in this tree"** and declines to re-mint |

No session sits between them.

### Four filesystem facts

1. **`C:\dev\mre\_data` itself was never deleted.** Its `CreationTime` is still
   **2026-07-23 15:43:14**. Every child — `runs/`, `submissions/`,
   `registry.sqlite`, `mrd/` — was created **2026-08-04 18:32:26–18:38:22**,
   when Daryn restarted the product.
2. **Eighteen sibling gitignored directories survived untouched**:
   `_4b6c_scratch`, `_4b8_scratch`, `_4b10_scratch`, `_4b11_scratch`,
   `_4b12_scratch`, `_4b12_logs`, `_4b15a_scratch`, `_4b18_scratch`,
   `_4b20_scratch`, `_4b21_scratch`, `_4b22_scratch`, `_4b22a_scratch`,
   `_4b25_scratch`, `_4b26_scratch`, `_4b27_scratch`, `_4b29_scratch`,
   `_ai_exam_scratch`, plus `mre_api_data`, `raw_data`, `runs`.
3. Therefore the removal was **scoped to the contents of `_data` alone**, which
   **rules out a repo-root `git clean -xfd`** — that would have taken the
   siblings and the `_data` directory with them.
4. The worktree (d.1) built no longer exists; `git worktree list` shows only the
   main checkout.

### The mechanism, labelled as inference

A directory junction is a reparse point. A recursive delete that follows reparse
points **empties the target and removes only the link** — leaving the target
directory standing with its original creation time. That is the single
hypothesis consistent with all four facts at once, and (d.1) is on record having
junctioned `_data` into a detached worktree to get its baseline.

**No command was captured, so this is not proven, and no further forensics were
run** — the brief puts blame out of scope and the remedy does not depend on
which command it was. It is stated because it is what R-PW1(6) has to forbid.

---

## 3. The byte-identity test (acceptance 3)

### Whole-file identity is impossible, and that had to be settled first

`api/registry.py` mints `run_id = str(uuid.uuid4())` and `app.py` derives
`schedule_id = f"rolling-{run_id[:12]}"`. **Content decides nothing about the
id, and the id lives inside the document** — so a re-mint's bytes can never equal
a lost board's, no matter how perfectly the plan reproduces. `contract_version`
has also moved 1.11/1.12 → 1.15 underneath.

So identity is tested over the **placement digest**: sha256 of sorted
`(operation_ref, resource_id, first-chunk start)`.

### The instrument was already committed, by accident

`tests/test_calibration.py::PINNED_WORLDS` pins the digest, bar count, ledger
and contract of **both** lost boards. It was written for 4B.29 Item 1(b) — to
prove the K=3 flip did not reach back and re-solve past artifacts — and had
nothing to do with loss. **It is the only committed instrument by which any of
the claims below could be checked.** Clause (7) of R-PW1 exists because of it.

### The recipes and the inputs survived

The registry copy in `_4b25_scratch/dataroot` records the submission source of
each board, and both are present:

| board | submission source | present? |
|---|---|---|
| `rolling-c9973708-865` / `rolling-db5395dc-2ae` | `_4b22a_scratch/demo_board/submission` | **yes** (bytes of 2026-07-31) |
| `rolling-c362baa4-1b0` | `_ai_exam_scratch/rolling_pinned/submission` | **yes** (and in the zip) |

The Khalil board's **accepted calibration profile** survived twice:
`_4b29_scratch/store/calibration/SyntheticERP_vGen__F001.json`
(`accepted: True`, `accepted_by: Daryn Radke`, 2026-08-01T19:43:54Z) and, as its
measured grid, the committed `docs/calibration/demo_board.json`. **They share
grid digest `ec5ffcef9009f423…`** — R-CAL1's own design working, because the
digest covers the MEASUREMENT and not the acceptance bookkeeping, so the
committed copy *proves* the restored one.

### Three results

| run | what it was | digest | verdict |
|---|---|---|---|
| `rolling-6e9bdb51-419` | bare K=1 re-mint, **profile withheld** | `ac86d185e8a97783…` | **EXACT MATCH** for `rolling-c9973708-865` — 386 bars, ledger **$2,127,482.58 to the cent**, 41 committed / 122 tray, gap 92.4108% |
| `rolling-e9ccc879-a4b` | `build_rolling_exam_run.py --register` | `07638cecb0b6f543…` | **EXACT MATCH** for `rolling-c362baa4-1b0` — 56 bars, ledger **$16,481.95**, 45 committed / 11 active / 14 tray |
| `rolling-c32a6140-b6b` | `mint_demo_board.py --calibrated --reuse` | `8071cdaaf953bc17…` | no digest exists for `rolling-db5395dc-2ae`; **every recorded figure reproduced** (below) |

The demo successor against the Khalil board's committed record, item by item:

| | recorded (CLAUDE.md) | minted | |
|---|---|---|---|
| ledger | $1,667,467.80 | $1,667,467.80 | ✔ |
| member seed 42 | $2,135,369.63 | $2,135,369.63 | ✔ |
| member seed 43 | $1,801,222.70 | $1,801,222.70 | ✔ |
| member seed 44 | $1,667,467.80 | $1,667,467.80 | ✔ |
| winner | seed 44 | seed 44 | ✔ |
| spread | $467,901.83 = 28.06% | $467,901.83 = 28.0606% | ✔ |
| bars / committed / tray | 386 / 24 / 122 | 386 / 24 / 122 | ✔ |
| gap | 89.6% | 89.6092% | ✔ |
| grade | ACCEPTED / C2 | ACCEPTED / C2 | ✔ |

### Verdicts

| id | verdict | why |
|---|---|---|
| `rolling-c9973708-865` | **RESTORED, original id** | its own document bytes survived in `_4b25_scratch/dataroot`; digest verified before *and* after the write |
| `rolling-c362baa4-1b0` | **RETIRED-LOST** | its plan survives and is proven, but every surviving copy is a re-assembly under a later contract (1.12/1.15 where the record says 1.11), so no document bytes exist to restore |
| `rolling-db5395dc-2ae` | **RETIRED-LOST** | no surviving bytes, no committed digest; the world is reproduced, the id cannot be |

**The near-match was not forced.** `rolling-c32a6140-b6b` reproduces the Khalil
board on nine independent figures and is *still* a new id, because figures are
not a digest and a digest is not a document.

### The confounded control, kept because it is the finding

The first control run was launched with the recovered profile in place and is
**not** a clean control: `mint_demo_board.py` declares `portfolio_k` but not
`portfolio_det_time`, and R-CAL1 rule (2) withholds only what the caller
declared — so the profile still supplied `det_total`. The solve ran at **10.0
units instead of 6.0**, produced `rolling-8cfac0a9-dba` (ledger **$2,135,369.63**,
digest `f836c206…`), and said so out loud on the certificate:

> applied: det_total=10 (the request declared its own k, which the profile does
> not override)

**The rule is correct; the recipe was incomplete.** A command whose docstring
promises a specific board depended on data-root state it neither declared nor
checked. That measurement is the second half of R-PW1(3), and the docstring now
carries it. Isolating it — rather than guessing — is what the clean re-run with
the profile withheld bought.

---

## 4. The worlds (acceptance 4, 7)

| id | role | capsule sha256 |
|---|---|---|
| `rolling-c32a6140-b6b` | **THE DEMO BOARD** (Khalil successor) | `4431fedc33d75474…` |
| `rolling-e9ccc879-a4b` | **THE EXAM WORLD** (c362baa4 successor) | `c63eab773ab08a4b…` |
| `rolling-c9973708-865` | previous demo board, **RESTORED** + audit child | `db1c36c9570ba3e3…` |
| `rolling-6e9bdb51-419` | the identity control, kept as evidence | `fa375c20573edbe5…` |

All four capsules are in `C:\dev\mre_worlds\` — outside the repo tree, because
inside it they share the fate of whatever removes `_data`. Full table with
digests and RETIRED-LOST rows: `docs/worlds/LEDGER.md`.

Three committed tools now exist under `tools/worlds/`:
`pin_world.py` (capsule + sha256 + `PIN.json` carrying the registry rows and the
digest), `restore_pinned_world.py` (**refuses** unless the copied document's
digest matches the stated committed trace), `replay_demo_lineage.py`.

### The lineage — partly delivered, and the shortfall is named

`replay_demo_lineage.py` drives the **real** accept path
(`/sandbox/feasibility` → `/sandbox` → `/accept`), never registry writes. It
minted `b5daba66-e928-40fb-a0a4-d17e240d6152` from a zero-move accept, carrying
a genuine Decision read back out of the evidence store:

```
driver    : PLANNER_DIRECTIVE          basis     : observed
authority : 4x-lineage-replay          verdict   : OPTIMAL
chosen    : objective_cleared: true, moved_count: 1, delta_abs: null
message   : Planner edit: pinned op 004733d3 to fd34d391 @ 2026-01-08T09:22 (+$0)
```

That is R-DP13's driver, R-DP12's cleared objective and R-DP11's plan-of-record
scope, all live.

**WHAT WAS NOT ACHIEVED: a placement-bearing tip (R-GP1).** The brief asked for
one and this board would not give one.

* **160 planner nudges refused at beat one, 160 of 160**, across 40 operations ×
  4 offsets, every one `{'family': 'C1/C2', 'sentence': 'the machine is not open
  at that time'}`. An earlier ladder of whole-day offsets (48 more probes) was
  discarded as naive — a day-scale offset lands wherever the calendar happens to
  be — and replaced with intra-shift nudges of 30/60/120/240 minutes. Those were
  refused too.
* **The audit found no usable member at either budget.** At its own default
  (3.0 deterministic units) and again at this plant's calibrated 10.0, all three
  seeded searches came back unusable and the product said so honestly.

So the tip is **AUTHORITY-ONLY**: real Decisions, no placement change, and by
R-GP1 it does not outrank its parent. **No move was faked to close the gap.**
The one board here that *does* carry a placement-bearing child is the restored
`rolling-c9973708-865`, whose 4B.25 audit accept (333 ops moved) came back with
it.

---

## 5. The re-anchor census (acceptance 5)

420 occurrences of the three ids across 152 files. The split is by **what a
future session RUNS**, per R-PW1(1).

| target | disposition | reason |
|---|---|---|
| `tests/ai_exam/banks/sweep_carried_state_v1.txt`, `sweep_mobility_v1/v2.txt`, `sweep_teaching_v1/v2/v3.txt` | **RE-POINTED** → `rolling-c32a6140-b6b` | live instruments; their ORD-/machine ids come from the same submission bytes, so the entity ids carry over unchanged |
| `tools/spikes/teaching_graft_c/founder_round_c9.md` (2 refs) | **RE-POINTED** → `rolling-c32a6140-b6b` | the C9 protocol Daryn runs next. **Questions unchanged** — none names dead content; Q7–Q10's fenced world `_ai_exam_scratch/mobility_pinned` survived and is untouched |
| `CLAUDE.md` (the demo-board / exam-world blocks) | **RE-POINTED**, with the loss stated | live orientation |
| `tools/spikes/demo_board_4b22a/mint_demo_board.py` | **CORRECTED** | its reproduction claim is now conditioned on the profile, with both measurements |
| `tests/test_calibration.py::PINNED_WORLDS` | **KEPT, annotated** | the `rolling-c362baa4-1b0` row can never resolve again; it stays because it is the only committed trace of that plan and it is what proved the reconstruction. The fixture's `continue` past a missing id is now documented as EXPECTED |
| `docs/04-design-history.md`, all `docs/closeouts/*`, all `tests/ai_exam/sweeps/*`, all `tools/spikes/*/artifacts/*`, `tools/spikes/sandbox_4b24/measurements.jsonl`, `tools/spikes/portfolio_4b25/*.jsonl` | **LEFT HISTORICAL** | R-PW1(1): valid records of what was measured on boards that existed; docs/04 is append-only |
| `src/mre/modules/interpreter.py`, `causal_sufficiency.py`; `tests/test_blocker_analysis.py`, `test_attribute_lookup.py`, `test_causal_sufficiency.py`, `test_working_time_vs_span.py`, `test_listening_docket.py`, `test_family_floor.py`; `tests/cockpit/beat_two.spec.mjs` | **LEFT HISTORICAL** | every one is docstring provenance — *"the specimen was measured on board X, transcribed here as plain data"* — which remains true and is not an instrument |
| `src/mre/corpus_index.json` | **REBUILT** | derived; 799 passages |

**No test hard-codes a lost id in an assertion** other than `PINNED_WORLDS`,
which handles absence by design.

---

## 6. Suites (acceptance 5)

**Collection: 2997.** The delta is itemized rather than waved at:

* **The entire data-root dependence is ONE parametrized family** —
  `test_evidence_index_roundtrip.py::test_roundtrip_on_a_real_run`, one case per
  run dir under `_data/runs` that has a `runs/` subdir. It collects **7** now
  (`6e9bdb51`, `8cfac0a9`, `ada15460`, `c32a6140`, `c9973708`, `d1ab749b`,
  `e9ccc879`) and collected **0** for the census.
* **My changes add zero tests, proven rather than assumed.** Collection was run
  at HEAD with every tracked change stashed: **2997, identical**.
**Full suite: 2691 passed / 305 skipped / 1 failed** in 17m52s, against the
census baseline of **2682 / 309 / 0**.

**The one failure was mine and it was self-inflicted.**
`test_corpus.py::TestCurrency::test_index_matches_the_live_docs` went red
because I amended **docs/07 while the run was in flight** — the index the test
loaded and the live document disagreed for exactly that reason. Rebuilt and
re-run: `test_corpus.py`, `test_calibration.py` and
`test_evidence_index_roundtrip.py` together give **102 passed / 15 skipped, 0
failed**. This is the **FOURTH** occurrence of that shape (4B.33, (c2), the
census — which called it a third); it is a discipline failure, not a flake, and
the discipline is *do not touch docs/ while a suite is running*.

Accounting, every term:

| | census | now | Δ | why |
|---|---|---|---|---|
| passed | 2682 | 2691 | **+9** | +7 roundtrip cases, +3 `TestPinnedWorldsUnmoved` (they skipped with no data root and now RUN against the restored board), −1 the corpus failure |
| skipped | 309 | 305 | **−4** | −3 `TestPinnedWorldsUnmoved`, and one more (below) |
| collected | 2991 | 2997 | **+6** | +7 roundtrip, and one fewer (below) |

**The two leftover ones are the same one, and there is a self-consistent
explanation I am labelling as inference.** If the census's `_data` had held a
single run directory with a `runs/` subdir but no evidence records, it would
have collected **one** roundtrip case and **skipped** it (`"no evidence records
in this run"`, line 214) — which is exactly +1 collected and +1 skipped against
a truly empty root, and reconciles both columns at once. The census close-out
describes `_data` as "empty in this tree", so this is a reading of its numbers
rather than a fact I can check: **the directory is gone and cannot be
re-examined.** Recorded, not rounded off — there is precedent (the (b)/(c)
two-test difference, still open).

**`--runslow` was NOT run** and nothing is claimed about it. **The cockpit
harness was NOT run** — no cockpit file was touched.

### The bank re-run, which is the real test of the re-anchor

`sweep_carried_state_v1` — the (d.1) bank, re-pointed at the demo successor —
was run live against `rolling-c32a6140-b6b`:

```
16 question(s), llm mode live, 27 live call(s)
parse: 18 parse(s), 0 retry, 0 malformed, 0 clarify, median 1387ms
graded expectations: 14/15 met
sidecar findings: expect-miss=1, ungrounded-load-bearing=1
```

**14/15 — (d.1)'s recorded score exactly, and the one miss is the same one.**
It is line 104, *"can you show me that on my board"*, expected `drill-down`, got
`synthesis`: the cold drill-down the bank itself documents at length as *"a
KNOWN, UNDERSTOOD MISS … KEPT RATHER THAN FITTED"*, unreachable from a live
parse.

That matters more than the number. The bank's entity ids came from the lost
board; they carry over because the submission bytes are identical, and the
score reproducing on a board minted tonight is the strongest available evidence
that the successor is a working substitute — stronger than the figure table,
because it exercises routing, grounding and carried state rather than totals.
The second sidecar finding (`ungrounded-load-bearing` at line 57, two claims cut
on the frozen-zone teaching question) is a grounding signal, not an expectation
failure, and is reported rather than filtered.

Transcript and sidecar: `tests/ai_exam/sweeps/2026-08-04-pinned-world-4x/`.

---

## 7. What broke on the way, and it was mine

**`git stash push` rewrote `docs/04-design-history.md` from LF to CRLF.** The
file is LF, the repo mixes endings per file, and git's `autocrlf` converted it
on pop — +17,018 bytes, one per line, on a file the hard rules call append-only.
`mint_demo_board.py` went the same way.

It was caught because the stash printed *"LF will be replaced by CRLF"* and the
line endings were checked immediately afterwards rather than assumed. Both files
were restored to LF (docs/04 back to exactly 1,081,566 bytes) and `git diff
--stat` confirms content-only changes with no whitespace explosion.

This is **4A-(a)'s newline lesson at a third site** — first on the write, then on
the match, now on a *version-control operation performed to measure something
else*. The measurement that needed the stash was worth taking; doing it without
checking the bytes afterwards would not have been.

---

## 8. NOT FIXED, named

1. **The C1/C2 refusal sentence is false for at least one specimen.** Beat one
   accepts op `004733d3` on `fd34d391` at `2026-01-08T09:22Z` (the zero-move
   accept succeeded, verdict *possible*) and refuses the same op on the same
   machine at `09:52` with *"the machine is not open at that time"*. `CAL-STD`
   is Mon–Fri **07:00–19:00** with one closure on 2026-01-14; 2026-01-08 is a
   Thursday. The instant **is** inside an open window. Either the attribution is
   wrong or the sentence is describing *fit* while claiming *openness* — a
   distinction 4B.35 built `relaxed_refusal` precisely to keep. **Not
   diagnosed here**; it needs its own session, and 160 identical refusals make
   it cheap to reproduce.
2. **The demo successor has no placement-bearing lineage child** (§4).
3. **The audit's K and per-member budget are still uncalibrated constants** —
   4B.29 §5a.111 named this; here is a live instance, on the plant whose profile
   the main solve *does* read.
4. **The one-test collection discrepancy against the census's 2991** (§6).
5. **The Khalil board's hand-made lineage is gone for good** — the demo drags
   and the 4B.31–35 interrogation history. No script reconstructs a thing nobody
   wrote down; that is the whole of R-PW1(4).
6. **`_4b25_scratch` was the only reason a world came back whole, and it is
   gitignored scratch that happened to survive.** Nothing made that copy on
   purpose. Every world is capsuled now, but the older scratch directories are
   still the unmanaged backup of record for anything not yet pinned.

---

## 9. Minted, and the scratch disposition (acceptance 6, 7)

**Tonight's bootstrapped `_data`** — one monolithic schedule
`65beb694-c2dd-42ae-b5da-f0476f3043f8` (run `65e8c887`, submission `54f880a5`
from `_data/mrd`, with an 8-member alternatives pool), created 18:36–18:38 by
Daryn getting the product to start — **was moved off-tree intact to
`C:\dev\mre_pre_reconstruction_data_2026-08-04\`, not deleted**, and nothing in
this session used it.

**Minted deliberately, all named:**

| id | what |
|---|---|
| `rolling-8cfac0a9-dba` | confounded control (profile leaked `det_total=10`) — kept as the evidence for R-PW1(3) |
| `rolling-6e9bdb51-419` | clean control — the exact reproduction of `rolling-c9973708-865` |
| `rolling-c32a6140-b6b` | **the demo board** |
| `b5daba66-e928-40fb-a0a4-d17e240d6152` | its zero-move accept child (authority-only) |
| `rolling-e9ccc879-a4b` | **the exam world** |
| restored: `rolling-c9973708-865`, `4b3acdab-5c65-4d78-8634-8a312d743bf6` | copied in from `_4b25_scratch`, digest-verified |

**`_ai_exam_scratch/rolling_pinned` WAS REBUILT** by `build_rolling_exam_run.py`
— deliberately, after the backup zip was verified, and its rebuilt document
carries the same digest `07638cec…` as the copy in the zip. Every other world in
`_ai_exam_scratch` is untouched.

The calibration profile was restored to `_data/calibration/` from
`_4b29_scratch/store/calibration/` (sha256 `119979563951d742…`, byte-identical),
moved aside for the clean control and moved back, verified by hash both times.

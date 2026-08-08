# SESSION R4.2 — what a child inherits at accept (D3, D4)

**2026-08-08** · second fix session off the R4.0 dossier (docs/07 §5b item 0) ·
HEAD at start `36a0145` · ruling **R-CH1** (docs/04 2026-08-08) · §5a.258-264

**No contract change (1.17). Prompts unchanged (parse v19 / synthesis v9). No
vocabulary change. No pinned world was written to** — the gen-3 world was read,
and every mutable probe ran on a scratch copy with its own data root. Five
`src/` files changed, one test file added (40 tests), two probes committed.

---

## 0. The predicate audit, stated first

R4.1 built two artifacts this session works behind, so both were re-run at HEAD
and then audited — which is the half that matters.

| predicate | result at HEAD |
| --- | --- |
| `verify_gen3.py` identity half | **PASS** — digest `8071cdaa…`, ledger $1,667,467.80, contract 1.17 |
| `p6_frame_catches.py` on `b5daba66` | **RAISES `FrameMismatch`**, offset −50,400 min, at 4x's exact specimen |

**Both hold. The gap is the one R4.1 itself named in R4.0's instrument, one
level up: a denominator of one.**

`p6_frame_catches` has exactly one cell. It proves the invariant FIRES on the
mis-framed specimen and shows nothing about whether it stays SILENT where it
should — an assertion that raised on everything would pass that probe. Its
complement is `p2_frame`, re-run here on gen-3: **25 probes, 7 refusals, 0
false, and `assert_frame` raised on none of them.** The pair is the 2×2 — fires
on the broken board, silent across 25 correctly-framed probes — and neither half
establishes it alone. Said here because R4.1's close-out reports `p6` as the
proof of the frame invariant, and it is half of one.

**The denominator habit, in every probe this session wrote.** `p9` prints its
ground-truth window counts and its own 2×2 visibility check *before* its verdict
and refuses an empty calendar read; `p10` refuses to report a control whose
anchor did not match. Both caught something (§6, §7).

---

## 1. Both ladders

Every number is `passed / skipped / failed`.

| ladder | baseline (R4.1, at `36a0145`) | after (this tree) | delta |
| --- | --- | --- | --- |
| no `--runslow` | 2989 / 309 / 0 + 1 xf | **3015 / 323 / 0** + 1 xf · 15m26s | +26 passed, +14 skipped |
| `--runslow` | 3272 / 21 / 5 + 1 xf | **3312 / 21 / 5** + 1 xf · 52m37s | +40 passed, failures unchanged |

**Both ladders balance against the same collection**:
`3312 + 21 + 5 + 1 = 3015 + 323 + 1 = 3339`.

The deltas are exactly this session's new file: 40 tests, 26 of which run
without the flag and 14 of which are slow. **No other count moved**, which is
the expected result for a change that adds a step at the end of an assembler
and one key to two run contexts.

**The five that remain red are EXACTLY R4.1's five**, by name — R1's C4 items,
each already routed in docs/07 §5b, none of them live-LLM and none of them
mine:

```
tests/test_ai_voice.py::TestAuditCorpusClean::test_cu5_split_jobs
tests/test_ai_voice.py::TestSession4B4::test_cu3_machine_count_answers
tests/test_ai_voice.py::TestSession4A3::test_cu4_unknown_capability_lists_what_can_be_coached
tests/test_ai_voice.py::test_cu10_zero_confident_wrong
tests/test_ask_chain_api.py::TestAskFailClosedWithRealKey::test_better_schedule_question_refuses_not_a_listing
```

**Cockpit: not run as a suite** — no cockpit source file was touched (§8(a) is a
finding about one, not a change to it). The corpus index was rebuilt from
docs/04 and docs/07 **before** the ladders.

---

## 2. W1 — the assembler seam, and the mechanism chosen

Both accept ceremonies (`_execute_accept` and `_execute_audit_accept`) called
`build_document_from_run` → `assemble_schedule_document`: the monolithic
assembler, which has no `rolling`, `coarse_zone`, `portfolio` or `calibration`
parameter at all. A child of a rolling, calibrated parent was monolithic and
uncalibrated by construction.

**The mechanism is INHERITANCE, not re-derivation**, in a new function
`schedule_assembler.inherit_child_metadata(child, parent_document)` that
`build_document_from_run` calls when it is given a parent. Both ceremonies now
pass one.

The alternative was to route the accept through `assemble_rolling_document` —
the function a rolling solve calls. **It was rejected for a reason worth
recording.** That function needs a `RollingView`, and a `RollingView` is the
WINDOW SOLVE's own record: `status`, `gap`, `op_drivers`, `cost_ledger`,
`incumbent_trail`, `earliness_tiebreak` are every one of them a statement about
a solve an accept did not run. Fabricating a view from an accept would have
written the accept's re-solve telemetry into fields that mean "the rolling
window solve's" — the 4B.23 *a default that ASSERTS manufactures a claim out of
a gap* class, committed deliberately.

What the child's own run genuinely produces — placements, ledger, service
outcomes, solver telemetry — the monolithic assembler already renders correctly
(R4.0 measured 386 = 386 on the child). What it cannot produce is metadata
belonging to the LINEAGE rather than to this solve. That is exactly the set
that is inherited, and nothing else is touched.

**The inherited window is ASSERTED, not assumed.** The tray, the window and the
boundary describe the parent's PLAN. Inheriting them whole is sound only because
an accept's model is built over exactly the operations the published plan places
(R-DP11), so it can neither admit nor drop a job. That is checked, with no
tolerance: the child's placed-operation set against the parent's, and a mismatch
raises `ChildInheritanceError` rather than shipping a rolling block that
describes a different plan. R-SG1's discipline, one layer up.

`commitment_state` and the two counts are DERIVED from the child's own
placements against the inherited boundary, using `rolling_horizon`'s own
definition (`start < frozen_until`), never copied — so a bar the accept moved
carries the state its new start earns.

---

## 3. W2 — the run-context write, asserted as a recovery

`reference_date` is now recorded on the M5 model-build context at **both**
ceremonies, and `derive_base_context` gains ONE fallback in the same function:
M3 is the root pipeline's own statement and still wins wherever it exists, so no
base run's recovered context changes shape. The fix is at the write side, once,
rather than at the eleven read sites.

**The regression asserts the RECOVERY, not the write** (the C5-fixture pattern
from the 2026-08-06 errand): a field written into a config nobody reads recovers
nothing. `test_the_reference_date_is_recoverable_from_the_child_s_own_run_dir`
calls `derive_base_context` on the child's own run dir and requires a date.

**Census note.** The nine non-walking `derive_base_context` callers R4.0 named
(`sandbox.py` ×3, `local_price.py`, `forced_alternatives.py`,
`solution_pool.py`, `ask.py`, `whatif.py`, `app.py:1518`) are now
correct-by-recording for children minted after this ruling. **Legacy children —
`b5daba66` and every other child minted before it — remain dateless and remain
LOUD** under R-SG1's frame invariant, which refuses rather than answering from a
mis-framed model. That behaviour is unchanged and intended; nothing here repairs
a child already on disk.

### The third member of the class, found by censusing it

The dossier named `planner_edit` as D4's seam. **`materialize_audit_offer`
recorded neither the reference date NOR the horizon**, so an audit-accept child
was not merely dateless: `_m5_horizon` on its own run dir raised *"M5 run
evidence carries no horizon"* and every sandbox surface pointed at that child
failed outright. Both are now recorded.

The regression exercises the real write on a board whose incumbent already
holds: the ceremony writes its M5 record before it decides there is nothing to
accept, so its own refusal (`nothing accepted`) is the positive control that it
genuinely ran.

*A defect class fixed at one seam is not fixed* — this repo's law, landing on
the dossier that quotes it.

---

## 4. W3 — calibration, and the claim a naive copy would have manufactured

R-CAL1 gives `applied` exactly one meaning: **the coefficients this solve
actually took**. An accept re-solve takes none of them — it runs at
`SANDBOX_DET_TIME_S` and `SANDBOX_SEED`. So copying the parent's calibration
block verbatim would have stated that the child ran at the calibrated budget,
which is false.

The child therefore inherits the profile's **identity** (`state`, `plant_key`,
`profile_id`, `calibrated_at`, `instrument_version`, `window_calibrated`) and
**clears** the three "what this solve did with it" fields (`applied`,
`window_solved`, `drift`). The provenance rides in the block's own `sentence` —
a deliberate refusal to add a field, since `inherited_from` would be a contract
shape change and the sentence is what every calibration surface already renders.

Measured on gen-3 (§5): parent `applied` True → child False, state `accepted`
on both, the parent's id and its original words inside the child's sentence.

**Both directions tested.** A parent that declares no calibration hands down
nothing, and the child **does not manufacture `state="absent"`** — that value
means "nobody has measured this plant", and inferring it from the fact that the
parent document carries no block would be a claim about the plant made from a
fact about our storage (4B.18). Inherited absence, not asserted absence.

**The R-CAL1 firewall.** Nothing here authors, measures, signs or re-signs a
profile. The inheritance is a reference to the parent's signed measurement and
nothing else; `calibration.py` was not touched.

---

## 5. W4 — clause (4), verified rather than rebuilt

The child carries no portfolio block. A `PortfolioBlock` is K deterministic
searches at consecutive seeds and the ledger comparison between them (R-BK1); an
accept runs ONE pinned re-solve. Stated in code — a portfolio arriving on a
child is *cleared*, not merely omitted — and tested both ways.

**Verified, and the verification found the state is weaker than the brief's
description.** `summary.js` appends the portfolio box only `if (portfolio)`, so
a child renders **no portfolio section at all**. That asserts nothing and is
honest, but it is silence, not the explicit three-state treatment
`progressModel` gives the solve-progress trail. Named at the level it was
verified at rather than reported as "the screen says so" (§8(b)).

---

## 6. W5 — the end-to-end proof

One real accept driven through `POST /schedules/{id}/accept` — the whole
ceremony, `_execute_accept` → `apply_planner_edit` → `build_document_from_run` —
on a scratch data root holding a copy of the gen-3 demo world.
(`tools/spikes/rolling_stack/p9_child_inheritance.py`.)

### The inheritance table

| | parent `rolling-9fdee7aa-ec5` | child (scratch) |
| --- | --- | --- |
| contract | 1.17 | **1.17** |
| rolling block | True | **True** |
| reference_origin | 2026-01-05T00:00:00 | **2026-01-05T00:00:00** |
| window_start / window_end | 2026-01-05 / 2026-01-15 | **2026-01-05 / 2026-01-15** |
| frozen_until | 2026-01-06T00:00:00 | **2026-01-06T00:00:00** |
| window / frozen days | 10 / 1 | **10 / 1** |
| committed_count | 24 | **24** |
| active_count | 362 | **362** |
| beyond_horizon (tray) | 122 | **122** |
| coarse_zone | True | **True** |
| assignments | 386 | **386** |
| `solver.calibration` state | accepted | **accepted** |
| calibration profile_id | `cal-SyntheticERP_vGe…` | **same** |
| calibration `applied` | True | **False** ← clause (3) |
| `solver.portfolio` | True | **False** ← clause (4) |
| document `reference_date` | 2026-01-05T00:00:00 | **2026-01-05T00:00:00** |
| `reference_date` RECOVERABLE | — | **2026-01-05T00:00:00+00:00** |
| solver_workers / seed recoverable | — | **1 / 42** |
| document placements = accepted plan | — | **386 of 386** |
| bars moved vs the parent | — | **0 of 386** |

The child's calibration sentence, in full:

> inherited from `rolling-9fdee7aa-ec5`: calibrated for F001 on 2026-08-01 by
> mre.calibrate/1 (25 measured cells) — applied: det_total=10, k=3 · This
> version is an accepted edit of that plan, not a new search — it neither
> re-measured this plant's calibration nor ran at its coefficients.

R4.0's §3.5 table, for the same comparison: contract 1.17, rolling **False**,
calibration **absent**, reference_date **None**.

### Beat one on the child — the gesture that started this arc

Through the real `POST /schedules/{id}/sandbox/feasibility` endpoint, 8 ops × 4
offsets, on the CHILD and on the correctly scoped PARENT, checked against an
independently computed calendar ground truth:

| | **CHILD** | PARENT (correctly scoped) |
| --- | --- | --- |
| probes | 32 | 32 |
| possible | **22** | 22 |
| impossible | **10** | 10 |
| correct refusal (refused, does not fit) | **10** | 10 |
| correct pass (passed, fits) | **22** | 22 |
| FALSE REFUSAL (refused, DOES fit) | **0** | 0 |
| FALSE PERMISSION (passed, does NOT fit) | **0** | 0 |
| FALSE "not open at that time" sentences | **0** | 0 |
| typed frame errors (`FrameMismatch`) | **0** | 0 |

**The child's table is identical, probe for probe, to the parent's.** And beside
it, R4.0 §3.4's measurement of the same gesture on `b5daba66`, the child the old
accept minted:

| `b5daba66` child, unrestricted | |
| --- | --- |
| probes | 24 |
| impossible | **24** |
| FALSE sentences | **23** |

Both columns of the 2×2 are non-empty on the child — 22 passes, 10 refusals —
which is the only reason its zeros mean anything.

> **And the probe's first instrument was blind in the familiar way.** The
> original target selection took the first eight active bars in document order.
> The document is sorted by start, so all eight sat in the same open morning and
> the whole ladder came back `possible`: **32 of 32, a 2×2 with an empty refusal
> row**, reporting zero false refusals from a set containing no refusals at all.
> Caught by the denominator check the probe prints before its own verdict.
> Striding across the window puts probes against shift ends, where a refusal is
> earned. **Three sessions, three empty denominators, three different modules.**

---

## 7. Tests and negative controls

`tests/test_child_inheritance.py` — **40 tests** (26 fast, 14 slow).

Three clauses, three physical reverts, each named test run **separately** so a
second test that stayed green with the code reverted could not hide behind the
first one's exit code (`tools/spikes/rolling_stack/p10_ch1_controls.py`):

| control | reverted | result |
| --- | --- | --- |
| (1) the rolling graft | `roll_raw = None` | **RED** ×3 — incl. `test_the_gesture_path_now_scopes_itself_from_the_child` |
| (2) the run-context write | the `reference_date` line deleted | **RED** — the recovery test |
| (3) calibration inheritance | `cal_raw = None` | **RED** ×2 |

All restores by captured bytes, sha256-verified before and after:
`schedule_assembler.py 4eab853ca782…`, `planner_edit.py 3ccd9208829a…`.

**True negatives, green:** a monolithic parent mints a monolithic child on a real
board and no bar gains a `commitment_state`; a root solve (no parent) is the
identity, portfolio included; `derive_base_context` on a run with an M3 record is
unchanged in shape and value (no field drift for ordinary runs).

**Contract validity:** the child document passes `ScheduleDocument.model_validate`
— the same validation the parent's kind passes. **No contract text needed
changing**, clarifying sentence or otherwise; every field used already exists and
is already documented.

> **The control script itself first proved nothing, and said so.**
> `planner_edit.py` is CRLF and `schedule_assembler.py` is LF, so control (2)'s
> anchor — written with a bare newline — did not match, and the script reported
> *"anchor not found … which proves NOTHING"* rather than a silent pass. This
> repo's per-file line-ending lesson (4A-(a)) landing on the tool written to
> prove things.

---

## 8. Carry-forwards (reported, deliberately NOT fixed)

1. **The schedule picker still tags an accept child of a rolling board as
   monolithic.** `scheduleKind` reads the id prefix and the snapshot id; an
   accept child is `<uuid4>` on `snap-edit-<sha12>`, and neither spells
   "rolling". The DOCUMENT is now correct, the LISTING row is not, and the
   picker's own comment already names the durable fix (a registry `sliced`
   column — a schema change).
2. **The absent-portfolio state is silence, not a sentence** (§5).
3. **The `applied`-cleared assertion is vacuous on the test fixture** — its data
   root holds no measured profile, so the parent's `applied` is already empty.
   Exercised by the fast unit tests and, at demo density, by the gen-3
   measurement in §6. Said in the test's own docstring.
4. **Legacy children are still dateless and still loud** (§3). Unchanged and
   intended.
5. **The audit-accept ceremony's own child DOCUMENT is unproven end-to-end.**
   The fixture's incumbent is already optimal, so the deeper search offers
   nothing and `/audit/accept` cannot be driven at fixture density. What is
   proven is the M5 write and the inheritance function both ceremonies share.
6. **The what-if fix is a session, not a line** (§9).
7. **Lineage replay onto gen-3 is now unblocked and was not run** — it is the
   next item, deliberately outside this session's walls.

---

## 9. W6 — the what-if path, assessed

R4.0 named `app.py`'s what-if as the same assembler class. Two findings, in the
order they bite:

**(i) It is broken one seam earlier than the assembler, on every rolling board.**
`_execute_whatif` copies `base_run["snapshot_id"]` where `_execute_accept`
deliberately uses `base_schedule["snapshot_id"]` — and its own comment explains
why. A rolling solve registers its schedule on `snap-rolling` while the run
carries `snap-<run_id[:8]>`, so the two ALWAYS differ and the copy fails with
`FileNotFoundError`. Measured this session on a fixture rolling board; the accept
was corrected for this in 4.0d and the what-if never was.

**(ii) Even repaired, the mechanism chosen here does not transfer.** The
assembler change would be one line — `parent_document=_parent_document(...)` —
and it would be WRONG. A scenario is a full pipeline re-run over its own horizon
and does not place the parent's plan of record, so clause (1)'s frame check would
correctly refuse to graft the parent's window and tray onto it. A rolling what-if
needs rolling RE-DERIVATION, which is the same shape as the standing *pool
service must become slice-aware* debt and belongs with it.

Routed to docs/07 §5b as item 1a with both measurements. **Not fixed here** — the
brief walls it out, and (i) alone would have been a scope change.

---

## 10. Children minted, all named

| what | where | disposition |
| --- | --- | --- |
| W5 scratch data root (registry + gen-3 run copy) | `<scratch>/r42_w5{,b}/_data` | copy; the accept ran with cwd there |
| **W5 accept child** | `1459262f-dca4-4465-a582-d36a9dbe5ec5` (and `58484068-…` from the first run) | **scratch only — NOT registered in `_data`** |
| `b5daba66` run-dir copy | `<scratch>/r42_audit/b5daba66_copy` | byte copy; predicate audit |
| what-if / audit probe world | `<scratch>/r42_audit_probe/data` | generated fixture, not `_data` |
| test boards + accept children | pytest tmp | fixture-scoped, discarded |

**`_data` was read but never written.** The registry is unchanged at 10
schedules; both pinned worlds are byte-untouched, and `verify_gen3` re-confirmed
gen-3's placement digest `8071cdaa…` at HEAD.

---

## 11. What a summary would undersell

**The founding symptom is dead, and it died to metadata.** Nothing about the
solver changed. No model was made feasible, no verdict logic was rewritten,
`relaxed_refusal` was not touched. A planner nudging a bar on an accepted edit
got "the machine is not open at that time" 23 times out of 24 because a document
had stopped saying which window it belonged to and which day it was reckoned
from. The fix is an inheritance step at the end of an assembler and one key in
two run contexts, and it takes the child's beat-one table from 24-of-24
impossible to identical-to-its-parent.

**The most interesting thing found was a claim nobody had made yet.** Clause (3)
looked like a copy: carry the parent's calibration block across. It is not.
R-CAL1's `applied` means *the coefficients this solve took*, and an accept takes
none — so the obvious implementation would have shipped a child asserting it ran
at a budget it never ran at. Nothing failed; no test would have caught it; the
block would simply have been quietly false on every accepted edit of every
calibrated board. **The ruling had to be tightened before the code was written,
and that is the only reason the defect never existed.**

**The what-if finding cost nothing and was nearly missed.** W6 asked for an
assessment paragraph, which a code read would have supplied: *one line, but the
frame check would refuse it.* Running it instead took two minutes and produced a
different answer — the what-if has been failing outright on every rolling board,
for reasons that predate this whole arc. R4.0's own lesson, twice-earned, is that
inferences of exactly that kind are wrong; the cheap defence is to run the thing.

**And R4.1's frame invariant is what made this session provable rather than
plausible.** Every claim in §6 rests on beat one rendering a real verdict with
zero typed frame errors. Before R-SG1, a mis-framed child answered confidently
and wrongly, and a probe could not tell a sound child from a broken one without
reconstructing the calendar by hand. R4.1 built the refusal; this session is what
turns the refusal into an answer. That is the ordering the dossier chose, and it
was right.

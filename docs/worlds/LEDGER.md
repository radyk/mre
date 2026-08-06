# THE WORLD LEDGER

**R-PW1 (docs/04, 2026-08-04).** Every pinned world this project measures
against, what proves it is itself, and where the off-tree capsule lives. A
pinned world with no off-tree capsule is a standing defect; a lost world is
RETIRED-LOST here and its id is never reused.

**Identity is the PLACEMENT DIGEST** — sha256 over sorted
`(operation_ref, resource_id, first-chunk start)`, the one definition
`tests/test_calibration.py`, `tools/worlds/pin_world.py` and
`tools/worlds/restore_pinned_world.py` share. Whole-file identity is impossible
by construction: `schedule_id` is `rolling-<uuid4[:12]>` and lives inside the
document, and `contract_version` advances underneath it. So a re-mint that
reproduces a plan exactly still gets a NEW id, and the contract version is
always stated separately rather than absorbed into "identical".

## Live pinned worlds

| id | what it is | shape | ledger | placement digest | capsule sha256 |
|---|---|---|---|---|---|
| `rolling-9fdee7aa-ec5` | **THE DEMO BOARD (gen-3).** The gen-2 recipe re-run at HEAD, so the world is unchanged and the DOCUMENT carries what 1.15 could not: R-SP1's priced trail and the 1.17 rollups. **Its plan is gen-2's, proven by digest.** | 386 bars · 24 committed / 122 tray · gap 89.61% · contract **1.17** | $1,667,467.80 | `8071cdaaf953bc17…` | `b25503bbdb72cfa4…` |
| `rolling-c32a6140-b6b` | **THE PREVIOUS DEMO BOARD (gen-2) — pinned, historical.** Successor to the lost Khalil board: same submission bytes, same accepted profile (K=3 @ 10.0, seeds 42–44, winner 44, spread 28.06%). Six committed sweep banks reference it; it is not superseded as an instrument, only as the board a demo runs on. | 386 bars · 24 committed / 122 tray · gap 89.61% · contract 1.15 | $1,667,467.80 | `8071cdaaf953bc17…` | `4431fedc33d75474…` |
| `rolling-e9ccc879-a4b` | **THE EXAM WORLD.** Successor to the lost `rolling-c362baa4-1b0`, and **its plan is that board's, proven by digest**. | 56 bars · 45 committed / 11 active / 14 tray · contract 1.15 | $16,481.95 | `07638cecb0b6f543…` | `c63eab773ab08a4b…` |
| `rolling-c9973708-865` | **THE PREVIOUS DEMO BOARD — RESTORED under its original id.** Lost from `_data` with the others; an exact copy survived in `_4b25_scratch/dataroot`, registry rows and audit child included. Carries a **placement-bearing** audit child. | 386 bars · 41 committed / 122 tray · contract 1.12 | $2,127,482.58 | `ac86d185e8a97783…` | `db1c36c9570ba3e3…` |
| `rolling-6e9bdb51-419` | **THE IDENTITY CONTROL.** A bare K=1 re-mint kept because it *proves* the pipeline still reproduces the previous demo board's plan exactly, four days and eleven commits later. | 386 bars · 41 committed / 122 tray · gap 92.41% · contract 1.15 | $2,127,482.58 | `ac86d185e8a97783…` | `fa375c20573edbe5…` |

Harness-fixture worlds (not registry-registered; capsule is the
`_ai_exam_scratch` backup, sha256 `3c595c0f3923dde5…`):

| world | what it is |
|---|---|
| `_ai_exam_scratch/rolling_pinned` (`sched-rolling-exam`) | the rolling exam fixture — same plan as `rolling-e9ccc879-a4b`, digest `07638cec…` |
| `_ai_exam_scratch/mobility_pinned` | **the fenced specimen world** (R-SW1, `datasets/mobility_box`) — the only board producing `boxed-in` / `earlier-open` |
| `_ai_exam_scratch/mobility_edited` | its edited sibling, carrying a real `planner_edit` accept |
| `_ai_exam_scratch/gb_pinned` | the monolithic exam world (`glass_box`) |

## RETIRED-LOST

Lost 2026-08-04, between commits `7b4a93b` (15:07 EDT, session (d.1), which ran
its baseline with `_data` junctioned into a worktree) and `804b229` (16:05 EDT,
the shared-body census, which recorded `_data` "empty in this tree").

| id | what it was | why it did not come back |
|---|---|---|
| `rolling-db5395dc-2ae` | **The Khalil board** — the demo board from 4B.28 through 4A(d.1), and the world six sweep banks were calibrated against. | No surviving document bytes and **no committed placement digest** — it was minted after 4B.29 wrote `PINNED_WORLDS`. Its WORLD is reproduced by `rolling-c32a6140-b6b` on every figure the record holds; its ID cannot be, because ids come from `uuid4`. **Its hand-made edit lineage — the Khalil demo drags and the 4B.31–35 interrogation history — is unrecoverable.** |
| `rolling-c362baa4-1b0` | **The pinned exam world** — 4B.13 through 4A.x, the regression target six sessions of AI measurement were calibrated against. | Its PLAN survives and is proven twice over (digest `07638cec…`, in both the harness fixture and `rolling-e9ccc879-a4b`). Its DOCUMENT does not: every surviving copy is a re-assembly under a later contract where the pinned record says **1.11**, so R-PW1(2)'s restore exception does not apply and the id stays retired. |

## Lineage children

| id | parent | note |
|---|---|---|
| `4b3acdab-5c65-4d78-8634-8a312d743bf6` | `rolling-c9973708-865` | 4B.25's audit accept ($1,581,932.98, 333 ops moved). **Restored with its parent** — placement-bearing. |
| `b5daba66-e928-40fb-a0a4-d17e240d6152` | `rolling-c32a6140-b6b` | 2026-08-04 replay: a zero-move accept. Real `planner_edit` Decision, driver `PLANNER_DIRECTIVE`, basis `observed`, `objective_cleared: true`, $0.00. **AUTHORITY-ONLY** — see the 4x close-out for why no placement-bearing tip could be minted on this board. |

## Custody

```
python tools/worlds/pin_world.py --schedule <id>             # capsule + sha256
python tools/worlds/restore_pinned_world.py --from <copy> \
    --schedule <id> --digest <committed digest> --apply      # restore, verified
python tools/worlds/replay_demo_lineage.py --schedule <id>   # lineage, real path
```

Capsules live in `C:\dev\mre_worlds\` — **outside the repo tree, deliberately**:
inside it they share the fate of whatever removes `_data`.

**A capsule does NOT carry `pools` / `pool_members` rows.** `pin_world.py`
captures schedules, runs, submissions and certificates; a restore therefore
brings back the alternatives FILES in the run dir but not the registry's
knowledge that a pool exists. Named W2.3, not fixed.

## Gen-3's recipe, and the two things it does that gen-2's did not

**R-PW1(3): the recipe names everything the mint reads, including data-root
state.** Gen-3's is gen-2's, plus one step, and the profile check is not
optional — with no accepted profile in the data root the same command lands on
a different board.

```
# 1. REQUIRED STATE: _data/calibration/SyntheticERP_vGen__F001.json
#    accepted: True, grid digest ec5ffcef9009f423…, file sha256 119979563951d742…
python tools/spikes/demo_board_4b22a/mint_demo_board.py --calibrated --reuse
# 2. THE ADDED STEP — the ghosts a demo drags against (see below)
POST /schedules/<id>/alternatives   {"sync": true, "budget": 8}
python tools/spikes/gen3_demo_world/verify_gen3.py --schedule <id>
```

**THE ALTERNATIVES STEP IS NOT DETERMINISTIC AND THE BOARD REFUSES IT ANYWAY.**
Each member runs under a 10.0s **wall** limit, so the pool is outside every
determinism claim made here; identity is and remains the schedule document's
placement digest. On this world the point is moot: **8 targets selected, 8
INFEASIBLE (`infeasible_this_horizon`), 0 publishable members, pool status
`empty`** — 0.63s each. Not for want of candidates (154 of 386 placed bars are
multi-eligible). This is the same refusal 4x measured from the other side on
gen-2's world (160 planner nudges refused, 160 of 160). **The product says
`empty` rather than inventing a ghost, which is the behaviour we want; the
consequence is that the drag-ghost surface has nothing to show on the demo
board.** Gen-2 has no pool at all, so this is not a regression — it is the
first time the question was asked of this world through this door.

## Lineage

**`rolling-9fdee7aa-ec5` HAS NO LINEAGE CHILD, AND THAT IS A DECISION, NOT AN
OVERSIGHT — lineage pending R4-accept.** The accept path on a rolling board
currently mints a MONOLITHIC, uncalibrated child (the known R4 defect, whose
live specimen is `b5daba66…` on gen-2). Replaying lineage now would bake
defective children into a pinned world. The replay runs as a small follow-up
the session after the R4 accept fix lands.

| capsule | sha256 |
|---|---|
| `rolling-9fdee7aa-ec5.zip` (62 entries, 600,503 bytes) | `b25503bbdb72cfa4015927de4a133e8094cc69de1679b831d0260107929ec8f1` |
| `mre_worlds_backup_2026-08-04.zip` (all of `_ai_exam_scratch`, 151 files, 2,970,385 bytes) | `3c595c0f3923dde581cada262148c99ba8bc5bff414b30bf2d5af1f38e0eb8f2` |
| `rolling-c32a6140-b6b.zip` | `4431fedc33d75474b328ebecc42ede223bbf42b3dfc39d94278758353e9357be` |
| `rolling-e9ccc879-a4b.zip` | `c63eab773ab08a4bd9bfe4c52080050513be3ef4f312d9961ed9535038ece717` |
| `rolling-c9973708-865.zip` | `db1c36c9570ba3e3fad2f28a6b3b076eb73a25bdb3ce3a818453d0bf14711545` |
| `rolling-6e9bdb51-419.zip` | `fa375c20573edbe53acfe2cc1a9c4c6358bd7e1bad93c3bac051c9f5d3816c86` |

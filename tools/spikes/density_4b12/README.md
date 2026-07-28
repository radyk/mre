# Session 4B.12 — the cliff, re-baselined under R-PD1 (MEASUREMENT ONLY)

Nothing here is reachable from a shipped path. It exists to answer three
questions with numbers on the plant we now actually schedule.

## Why the measurement had to be redone

4B.10 located a cliff at **137 ops/machine** and, being honest about it, recorded
that F004's 246 and F006's 803 were **BRACKETED, not solved** (§5a.27(h)).

4B.11 then changed the world underneath that measurement. **R-PD1 admits
past-due work**: demands the validator used to exclude are now scheduled and
priced. 4B.10 had itself proved that the cliff's driver is **tardiness onset**
(§5a.27(d)) — so a cliff measured on a book that silently dropped its late
orders is not a cliff on the book we schedule. Everything below re-runs 4B.10's
cells against **byte-identical worlds** and the current pipeline.

## Files

| file | what it does |
|---|---|
| `cliff_sweep.py` | the sweep. Imports 4B.10's harness components; adds the R-PD1 quantities, the tardiness split, and the CU3 hint arms. |
| `probe_density.py` | maps an ORDER COUNT to an ops/machine reading without solving. The map is not a constant and R-PD1 moved it. |
| `verify_world_identity.py` | proves the re-baseline compared the SAME worlds — byte-for-byte against `_4b10_scratch`, two clock fields masked. |
| `analyze_4b12.py` | reads every `*.jsonl` here and prints CU1 / CU2 / CU3. |
| `cu1_*.jsonl` | the re-baseline and the cliff pin. |
| `cu2_*.jsonl` | F004 (276 orders) and F006 (851 orders). |
| `cu3_*.jsonl` | the hint arms. |

4B.10's `analyze.py` also reads these files unchanged — the column names are its.

## Configuration — all four, or the measurement is void

* **Cost-only objective**, as shipped since 4B.7. The sweep calls the shipped
  `rolling_horizon._two_stage_solve`; it does not transcribe it.
* **P3 allocation**, the shipped 4B.8 split (stage 1 capped at the total minus a
  1/12 reserve; stage 2 gets the remainder).
* **Wall ceiling 1800 s** so the DETERMINISTIC budget is what binds. Any row
  whose `wall_truncated` is True is **EXCLUDED and NAMED** by the analyzer.
* **det_total 6.0, window 14 d, frozen 3 d, 4 machines.** Generation seed pinned
  at 1, so seed spread measures the SOLVER and not the world.

## Three traps this harness is built around

The first two are 4B.10's and are inherited. The third is 4B.12's own, and it is
recorded here for the same reason 4B.10 kept its contaminated file: it produced
plausible numbers, not a crash.

1. **`det_consumed` on the returned result is the TOTAL.** `_RecordingRunner`
   recovers each stage's own status and spend without reimplementing the
   shipped allocation.
2. **One writer per results file.** `analyze_4b12.py` refuses a file containing
   a duplicated `(orders, alternates, seed, hint_mode)` rather than averaging.
3. **ONE SPINE OUTPUT DIRECTORY PER PROCESS.** `prepare_plant` wipes and
   rebuilds its run dir. Two processes sweeping the same `(orders, alternates)`
   — which is exactly what the CU3 arms are, differing only in `hint_mode` —
   both write one directory, and the second corrupts the snapshot store the
   first is reading. **The failure is silent and plausible:** a first pass of
   CU3 reported 800 free operations in a world that has 400, and INFEASIBLE at
   0.0 deterministic units, because both processes' entities had landed in one
   store. Those rows were **discarded, not repaired**. `--run-tag` (defaulting
   to the hint mode) is the fix; partitioning concurrent processes by
   `(orders, alternates)` is the other.

## Running it

```
PYTHONHASHSEED=0 python tools/spikes/density_4b12/cliff_sweep.py \
    --orders 110 --alternates 1 --seeds 42 43 44 45 46 --out cu1_o110a1.jsonl

PYTHONHASHSEED=0 python tools/spikes/density_4b12/cliff_sweep.py \
    --orders 276 --alternates 1 --seeds 42 43 44 45 46 \
    --hint-mode full --out cu3_o276a1_full.jsonl

python tools/spikes/density_4b12/verify_world_identity.py
python tools/spikes/density_4b12/analyze_4b12.py
```

## What it found

**The cliff moved from 137 to 92 ops/machine** — the last density at which all
five seeds prove the cost optimum. At **94** none of them do. Both real
facilities are now **solved rather than bracketed**, and both are far past it:
F004 at 254 ops/machine returns FEASIBLE with an **83.5–85.8%** gap; F006, at
772 ops/machine and **134.9% utilisation**, with a **98.8%** one. **Every
failing cell still returns a SOLUTION with a STATED gap** — none returned
UNKNOWN — which is the answerability question, and it is the reason 4B.11's
rendered gap matters more than it looked.

**Ops/machine is refuted as a predictor the same way utilisation was, and by a
sharper argument than 4B.10 had:** the proof cost is not even MONOTONE in
density. 65 ops/machine proves in 0.045–0.286 units while the LIGHTER 50
ops/machine takes 0.294–0.735. What separates them is how much tardiness the
solution carries — which is not computable before solving.

**The warm start (`hint_mode`, shipped OFF) is a RE-ROLL, not an improvement.**
It pays in the cliff region — at 100 ops/machine the assign arm takes the proof
count from 1/5 to 3/5 and the median gap from 10.1% to 0.0% — and costs beyond
it. At every density the win column AND the loss column are non-empty, which is
what a re-roll looks like: a hint changes where the search starts, and in a
region where the seed decides that is another way of changing the seed.

Full write-up: docs/07 §5a.31 (the re-baseline and the two densities) and
§5a.32 (the hint verdict).

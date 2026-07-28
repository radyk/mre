# Session 4B.10 — the density sweep (MEASUREMENT ONLY)

Nothing here is reachable from a shipped path. It exists to answer three
questions with numbers, on the **real shape** rather than `pilot_scale`'s.

## Why the axis changed

Session 4B.9 measured the historical extract and found that every scale number
the programme holds was taken on the wrong axis. `pilot_scale` runs **13–15
machines at ~24 ops/machine**; the measured planning unit is **4 machines
carrying 250–800 operations each** (docs/07 §5a.24, §5a.25). Separately, the gap
probe's "8 of 10 facilities UNKNOWN" was measured **with the priced earliness
term** that 4B.6c proved converts a feasibility problem into an optimization
CP-SAT cannot close, and that 4B.7 removed. Both foundations were unsound.

## Files

| file | what it does |
|---|---|
| `verify_facility_real.py` | prints a generated `facility_real` submission's shape beside each MEASURED target. Calibration is checked, not asserted. |
| `density_sweep.py` | the sweep. Holds the shape fixed, sweeps ops/machine at both alternate settings. |
| `analyze.py` | reads `density.jsonl` and answers Q1/Q2/Q3. |
| `tardiness_counterfactual.py` | prices the cliff's driver: the same instance solved twice, changing ONLY the tardiness weight. |
| `objective_variance.py` | settles *why* without a theory: evaluates `sum(objective_terms)` at several different feasible solutions of one model, and reports every eligible-set size so "the assignment is forced" is checked rather than assumed. **It is what corrected the first explanation** — the objective is not constant, it is nearly flat (0.095% vs 18.402%). |
| `pastdue_probe.py` | item 4 parts 1–2: does an already-late order vanish, and where? |
| `pastdue_visibility.py` | item 4 parts 3–4: is the disposition certificate-visible and AI-answerable? |
| `density.jsonl` | the results. One row per (orders, alternates, seed). |

## Configuration — all three, or the measurement is void

* **Cost-only objective.** As shipped since 4B.7. The sweep calls the shipped
  `rolling_horizon._two_stage_solve`, which sets no objective of its own.
* **P3 allocation.** As shipped since 4B.8: stage 1 capped at `det_total` minus a
  1/12 reserve, stage 2 gets the remainder.
* **Wall ceiling raised to 1800 s** so the DETERMINISTIC budget is what binds.
  `member_time_limit_s` defaults to 30.0 while stage 1 needs 37–120 s at 200
  orders, so every prior measurement on the shipped path was wall-truncated and
  therefore, by this repository's own hard rule, a lottery. Any row whose
  `wall_truncated` is True is reported and **excluded** by `analyze.py`.

## Two traps this harness is built around

1. **`det_consumed` on the returned result is the two-stage TOTAL**
   (`spent1 + stage2`), so "units to PROOF" is not recoverable from it.
   `_RecordingRunner` wraps `SolveRunner` at the module the shipped code imports
   from, recording each stage's own status and spend **without reimplementing
   the allocation** — the budgets, the reserve and the two-stage logic stay the
   shipped code's.
2. **One writer per results file.** Two concurrent sweeps duplicate cells and
   contend for CPU, and a wall clock under contention stops meaning what it
   says. `analyze.py` refuses to read a file containing a duplicated
   `(orders, alternates, seed)` rather than averaging over it. This is not
   hypothetical — a first pass of this sweep was discarded for exactly that
   reason (`density_CONTAMINATED.jsonl.bak`, kept as the specimen).

## Running it

```
python tools/generate_erp_dataset.py --scenario facility_real --out <dir>
python tools/spikes/density_4b10/verify_facility_real.py <dir>

PYTHONHASHSEED=0 python tools/spikes/density_4b10/density_sweep.py --seeds 42
python tools/spikes/density_4b10/analyze.py

PYTHONHASHSEED=0 python tools/spikes/density_4b10/tardiness_counterfactual.py \
    --orders 165 --alternates 1 --seeds 42
PYTHONHASHSEED=0 python tools/spikes/density_4b10/objective_variance.py \
    --orders 165 --alternates 1 --seeds 42 43 44
```

## What it found

The cliff is **not a line in density** — it is a REGION where the budget is
marginal and the SEED decides. At 137 ops/machine five runs differing only in the
solver seed split **4 OPTIMAL / 1 FEASIBLE**, and the unproved run's ledger is
**13.056%** more expensive than the optimum the other four prove to the cent. So
no rule computable *before* solving can predict it: every pre-solve quantity is
identical across those five runs. The driver is **tardiness onset**, and the
mechanism is that at `alternates=1` the placement-dependent part of the cost is
almost entirely tardiness (freeing it collapses the objective's spread across
feasible solutions from 18.402% to 0.095%). Full write-up: docs/07 §5a.27.

The sweep is **resumable**: every `(orders, alternates, seed)` already in the
output file is skipped, and each cell is individually deterministic, so a
chunked run and a single long one produce the same rows. `--max-seconds` stops
it cleanly at a wall budget.

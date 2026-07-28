# Session 4B.11 — R-PD1 measurement

Two scripts and their captured output. Everything here is REPRODUCIBLE:
`PYTHONHASHSEED=0`, `num_search_workers=1`, solver seed 42, generation seed 1.

## `probe.py` — the specimen probe

One script, run BEFORE and AFTER the ruling, so every claim in the close-out is a
diff of the SAME measurement rather than two differently-shaped observations.

```
PYTHONHASHSEED=0 python tools/spikes/pastdue_4b11/probe.py before
PYTHONHASHSEED=0 python tools/spikes/pastdue_4b11/probe.py after
```

It builds `facility_real_pastdue` (60 orders, 21 past due, reference date
2026-01-05) and reports:

1. **intake** — how many past-due demands survive to `schedulable_demands`
2. **gravity** — are they admitted, and where do they land in start order
3. **certificate visibility** — does the document name them; the solver block's
   status, gap and the tardiness split
4. **the three measured answers**, driven at the ROUTE level so the measurement
   does not depend on a model parse
5. **the exclusion note's arithmetic** (the "42")
6. **the cost proof**, and whether the rider reaches a money-stating answer

`reconcile_exclusions()` then builds a SECOND world with three genuine
`quantity <= 0` exclusions. It has to: R-PD1 dissolves the note on the specimen
itself, so re-running the specimen shows the note ABSENT rather than CORRECT, and
"the fix covered it" would be an assumption rather than a measurement.

Captured output: `BEFORE.txt`, `AFTER.txt`.

## `floor_invariance.py` — R-PD1 clause (4)(b)

Does putting the tardiness FLOOR into the objective change what the solver
chooses? Two arms of the same instance, differing only in
`solver_builder._due_minutes(include_floor=)`.

```
PYTHONHASHSEED=0 python tools/spikes/pastdue_4b11/floor_invariance.py 12
```

**Read the script's own closing note before reading `PLACEMENTS IDENTICAL: False`
as a refutation.** The brief's stated test was placement identity; the data shows
that test is the wrong one, and shows it cleanly:

* at 60 orders BOTH arms return FEASIBLE (gaps 24.6% / 1.0%) with 237/240
  placements differing — two truncated searches, not an argmin comparison;
* at 12 orders both arms PROVE OPTIMAL and `B − A` is EXACTLY the predicted
  `Σ (weight × floor)`, which is what confirms the offset is independent of the
  schedule and therefore that `argmin f_B == argmin f_A` as sets;
* placements still differ, because that argmin set has more than one member and a
  large added constant changes CP-SAT's search trajectory.

The verdict is taken on the exact-offset identity, which is the stronger claim.
Exit code 0 means it held. Captured output: `FLOOR_INV.txt`.

Both scripts write their generated worlds and run dirs to `_4b11_scratch/`, which
is git-ignored.

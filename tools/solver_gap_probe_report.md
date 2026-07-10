# Solver-gap probe report — facility decomposition on the gauntlet full solve

**Date:** 2026-07-13 · **Script:** `tools/solver_gap_probe.py` · **Verdict: RED**
(decomposition does not make the mass-splittability full solve viable; the
sliced daily solve remains the blessed operational mode). Spike rules
honored: scratch tool, no `src/mre` changes, reported before productionizing.

## Question (docs/07 §2 spike #2; solver-gap dossier experiment #1)

Does per-facility / per-resource decomposition make the gauntlet FULL solve
(mass splittability — the configuration that found no incumbent in 600s at
the Phase-1 exit audit) viable, and does it change the 87%-gap story?

## Configuration

The repo `plant_config.json` has no splittability or cost keys (the audit's
were scratch artifacts), so the probe recreates them and states them:
`workcenter_defaults.splittable=true`, `min_chunk_minutes=30`, cost model
{rate $60/h, setup $50, tardiness $60/h}. All solves single-worker, seed 0
(comparable with the audit's 600s single-worker figure). Pipeline: M1(raw)
→ M3 → M4(identity_v1), full backlog, **no horizon slice**.

Scope note: this full backlog builds **14,042 operations / 2,980
WorkPackages / 93 resources**, larger than the audit's reported "4,933-op
full solve" — the audit figure evidently described a differently-scoped
run; the discrepancy is recorded, and this probe's numbers are
self-consistent (partition table below sums to 14,042).

## Partition: the gauntlet is exactly decomposable

10 facilities (workcenter prefix `F001/D3001`), eligibility is
explicit-set single-resource on the raw path, and **0 WorkPackages cross a
facility** — sum-of-facility-objectives would equal the monolith objective
exactly. Resumable-op density under mass splittability:

| Facility | ops | resumable | resources | resumable/resource |
|---|---|---|---|---|
| F001 | 1,626 | 1,490 | 23 | ~65 |
| F002 | 3 | 3 | 3 | 1 |
| F004 | 1,040 | 36 | 4 | 9 |
| F005 | 2,015 | 1,743 | 8 | ~218 |
| F006 | 3,392 | 12 | 4 | 3 |
| F008 | 768 | 561 | 3 | ~187 |
| F00A | 2,304 | 116 | 4 | 29 |
| F00B | 544 | 256 | 11 | 23 |
| F00D | 454 | 220 | 8 | 27 |
| F00Z | 1,896 | 695 | 11 | 63 |

Spike 2's validated ceiling was **~4–4.5 resumable ops per resource**; most
facilities sit 5×–50× beyond it under mass splittability.

## Results

| Solve | ops | budget | build | status | objective | bound | gap |
|---|---|---|---|---|---|---|---|
| monolith | 14,042 | 300s | **288.8s** | UNKNOWN | — | — | — |
| F001 | 1,626 | 180s | 20.8s | UNKNOWN | — | — | — |
| F002 | 3 | 180s | 0.1s | OPTIMAL (1s) | 45,900 | = | 0 |
| F004 | 1,040 | 180s | 2.4s | FEASIBLE | 11,708,300 | 6,608,000 | **43.6%** |
| F005 | 2,015 | 180s | 117.5s | UNKNOWN | — | — | — |
| F006 | 3,392 | 180s | 2.7s | UNKNOWN | — | — | — |
| F008 | 768 | 180s | 60.4s | UNKNOWN | — | — | — |
| F00A | 2,304 | 180s | 4.7s | UNKNOWN | — | — | — |
| F00B | 544 | 180s | 10.6s | UNKNOWN | — | — | — |
| F00D | 454 | 180s | 10.6s | UNKNOWN | — | — | — |
| F00Z | 1,896 | 180s | 37.2s | UNKNOWN | — | — | — |

Resource shards on the worst facility (F001), 30s each, ops restricted to
the shard's own resource: shards of **~170–190 ops each returned UNKNOWN**
(9 of 12); only the 29-op shard (FEASIBLE, 99.7% gap) and the 11-op shard
(OPTIMAL) produced solutions.

## Findings

1. **Facility decomposition alone does not rescue the full solve.** 8 of 10
   facilities find no incumbent at 180s despite perfect decomposability.
2. **The difficulty has moved INSIDE the resource.** Spike 2's per-resource
   shards solved in <0.2s at ~4 resumable ops/resource; F001's shards at
   ~65/resource fail even at 30s with a single machine and no cross-resource
   coupling. The spike-2 mitigation ("decomposition works") does not extend
   to mass-splittability density — its measured ceiling was real and this
   plant is far past it.
3. **Two independent killers, either sufficient:**
   - *Chunk-slot volume:* a resumable op contributes one optional interval
     per candidate calendar window; on the full-backlog horizon
     (max(due)+90d over a stale demand base) the tail-pruning in
     `_feasible_window_range` leaves candidate ranges spanning most of the
     horizon, so one machine's no-overlap group holds tens of thousands of
     optional intervals. Model **build** time is the visible symptom
     (monolith build 289s; F005 build 117s).
   - *Raw per-machine op count:* F006 has almost no chunking (12 resumable
     ops) and still fails — ~850 ops on a 4-machine no-overlap at 180s
     single-worker finds no first solution. F004 at ~260 ops/machine does.
4. **The gap story does not change qualitatively.** Where a facility
   solves (F004), the gap improves (43.6% vs the 87% REP-1 monolith
   figure) but remains structural: the objective is tardiness-dominated
   (a mostly-overdue backlog) and the LP bound stays weak.
5. **Why the sliced daily solve works** is now sharper: slicing caps the
   horizon, which simultaneously caps candidate chunk windows per op AND
   per-machine op counts — it attacks both killers at once. It is not just
   "less work"; it is the correct structural counter to both failure modes.

## Verdict and named parking position

**RED** — neither facility decomposition nor per-resource sharding makes
the mass-splittability full solve viable at these densities; per docs/07 §2
the research is parked post-pilot and the **sliced daily solve is the
blessed operational mode**, now with a measured explanation of why it
works. Named follow-up directions for the parked workstream (not built,
spike rules):

- **Horizon-capped chunk slots:** bound each resumable op's candidate
  windows by a due-date-relative policy (with a single overflow escape
  window) instead of suffix-capacity tail pruning alone — attacks killer
  3a inside the existing encoding.
- **Hierarchical slice-within-facility** (facility × time-slice cells) with
  LNS repair from the sliced incumbent — the pool/warm-start machinery
  built this session is the natural repair loop.
- Facility decomposition itself is cheap, exact (0 cross-facility WPs) and
  worth productionizing *as an engineering speedup for the sliced mode*,
  not as a full-solve rescue.

Raw measurements: `probe_results.json` produced by the probe run
(scratch artifact; the tables above are the durable record).

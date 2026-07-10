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

Scope note — 4,933 vs 14,042, resolved (2.3 review carry-in, measured):
operation-instance count is a **planner-policy artifact**, not a dataset
property. The Planner instantiates one Operation per OperationSpec per
WorkPackage, so merging demands collapses op instances roughly in
proportion to the WP collapse. Measured on the same gauntlet backlog
(repo `plant_config.json`, same M1(raw)→M3 exclusions): identity_v1
plans 2,864 WPs / **13,315 ops**, while merge_by_family_v1 plans 668 WPs
/ **4,088 ops** — a 3.3× collapse. The audit's "4,933-op full solve" is a
merge-policy op count (its scratch plant config's splittability rescues
admitted slightly more demands, landing between these figures); this
probe pinned identity_v1 and admitted 2,980 WPs / 14,042 ops. Both
figures are self-consistent for their own planning policies (partition
table below sums to 14,042), and the discrepancy does not touch the
verdict: the killers are per-machine densities, which the probe measured
directly on its own model.

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
- **The solution pool must become slice-aware for sliced-mode schedules**
  (2.3 review carry-in): pool members rebuild the base model from the
  run's own M5-recorded horizon, which is correct for a monolithic solve
  but does not reproduce a sliced run's per-slice demand selection — a
  pool warmed against a sliced incumbent would re-solve a differently
  scoped model. Since the sliced daily solve is the blessed operational
  mode, this lands with the pool's productionization (tracked on docs/07's
  pool item).

Raw measurements: `probe_results.json` produced by the probe run
(scratch artifact; the tables above are the durable record).

## Reconciliation — the op-count figures across reports (2.4 CU0.3)

Four op-count figures appear across the audit, the 2.3 review, and this
probe. They differ only by **planner policy** and by **which demands each
run's config admitted** (splittability rescues window-fit exclusions), never
by any dataset change. In one accounting:

| Figure | Policy | Config | WPs | ops |
|---|---|---|---|---|
| 13,315 | identity_v1 | repo `plant_config.json` (no splittability) | 2,864 | 13,315 |
| 14,042 | identity_v1 | probe (recreated splittability) | 2,980 | 14,042 |
| 4,088 | merge_by_family_v1 | repo `plant_config.json` (no splittability) | 668 | 4,088 |
| 4,933 | merge_by_family_v1 | audit scratch (splittability) | ~730 | 4,933 |

- **13,315 → 14,042** (same policy, identity_v1): the probe recreated
  `splittable=true`, so window-fit exclusions that the repo config drops
  were **rescued** into the backlog — +116 WPs admitted, +727 op instances.
  Same phenomenon on the merge policy: **4,088 → 4,933** is merge_by_family
  under the audit's splittability config admitting the same class of rescued
  demands (+~845 ops). Both deltas are one effect — splittability turns
  otherwise-un-schedulable demands into admitted work — measured under two
  different planner policies.
- **14,042 vs 4,088 / 13,315 vs 4,933** (across policies): the ~3.3× gap is
  the merge collapse (one Operation per spec per WorkPackage; merging
  demands collapses op instances in proportion to the WP collapse). See the
  dossier entry below.

Net: every figure is self-consistent for its (policy, config) pair; the
verdict is untouched because the killers are per-machine densities measured
directly on the probe's own identity_v1 model.

## Dossier entry #2 — merge policy as a ~3.3× tractability lever, and its cost (2.4 CU0.4)

**Measurement.** On the identical gauntlet backlog, merge_by_family_v1 plans
668 WPs / 4,088 ops where identity_v1 plans 2,864 WPs / 13,315 ops — a
**3.3× reduction in model size** (variables, no-overlap members, chunk
slots) achieved purely by the planner grouping same-family demands into one
WorkPackage. As a decomposition lever this is larger than facility
decomposition delivered on any single facility, and unlike facility
decomposition it shrinks the per-machine densities that the killers above
are made of.

**The tension (the point of this entry).** Merge is also a **cost loss**,
already verdicted: the WO-2001/WO-2002 unbatch (2026-07-06 amendment)
measured that merging two distinct orders into one WorkPackage forfeits
per-order scheduling freedom and costs **+$260** versus running them
separately — the what-if unbatch is a *cheaper* schedule. So the same knob
that buys ~3.3× tractability spends money: merge-as-tractability and
merge-as-cost-loss pull in opposite directions. There is no free lunch here
— a merged plan is smaller and faster to solve but provably not
cost-optimal on the merged orders.

**Consequences.**
- The sliced daily solve (the blessed mode) remains the primary tractability
  answer because it caps horizon-driven chunk-slot volume *without* the merge
  cost penalty. Merge is a secondary lever, to be spent deliberately where
  the cost loss is acceptable (e.g., genuinely fungible same-family lots),
  not a default.
- **Pilot entry conditions must declare which planner policy their figures
  are measured under.** A "solves in N seconds / costs $X" claim is
  meaningless without stating identity_v1 vs merge_by_family_v1 — the op
  count (and therefore both tractability AND the cost baseline) moves 3.3×
  between them. This is added to the docs/07 Phase-4 entry-condition
  discipline: measure, and name the policy, on the same line as the number.

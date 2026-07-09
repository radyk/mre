# Week-one spike: R-C3 resumable chunking at scale

**Status:** spike only, no production code touched. Script: `tools/chunking_scale_spike.py`.
**Question:** can "one interval per op, elapsed = working + pause via a start-indexed
step table" (docs/05 R-C3) scale to 300 / 3,000 / 10,000 operations before Rep 2 is built?

## Verdict: **RED — redesign needed, reporting before building**

The model-size numbers are fine. The problem is solvability: at every production-relevant
scale tested (N≥300), CP-SAT's default search **never found even a first feasible
solution** within 60 seconds for the resumable-operation model — with or without an
objective, and regardless of which table strategy was used. Both of the offered YELLOW
mitigations (coarser start granularity, table pruning to reachable starts) are already
present in the "pruned" variant below and do not fix it. This is not a "make the table
smaller" problem; it's a search/propagation problem with the AddElement-based interval
encoding itself.

## What was built

One CP-SAT interval per resumable operation, `[start, start+elapsed)`, where
`elapsed = table[start]` via `AddElement`. The table encodes R-C3 directly: for a
working duration `w`, `elapsed(s) = invO(O(s) + w) - s`, where `O(t)` is cumulative
open-calendar-minutes up to `t` (a piecewise-linear function built once per resource
from the flattened calendar's window breakpoints — O(#windows) size, not O(horizon)).
Verified correct on a hand-computed case (`smoke_test()`: a 900-minute resumable op
starting at a 720-minute shift-open correctly pauses overnight and resumes at the next
shift open — `elapsed = 900 + overnight_gap`).

Two resource no-overlap groups, per resource, to get "occupies its resource while
paused, but pauses don't conflict with the calendar closure that caused them" right:
1. non-resumable intervals + calendar-closure blocking intervals (unchanged from the
   existing production technique — forces non-resumable ops into one window)
2. **all** real operation intervals (resumable + non-resumable), no blocking intervals —
   resumable intervals may legally overlap a closure (that's the pause) but never
   another operation.

Non-resumable operations (80% of the mix) and the calendar-blocking-interval technique
are copied verbatim from the existing `solver_builder.py` approach and serve as the
scale baseline.

Two table strategies compared:
- **A) dense** — one table entry per minute of the horizon domain.
- **B) pruned** — table entries only at a coarse (60-minute) grid of starts inside open
  calendar windows, via a two-level `AddElement(k, reachable_starts, start)` +
  `AddElement(k, elapsed_table, elapsed)` indirection.

Scenario generation: 20% of operations resumable (duration 1–3× the 720-minute shift
window), 80% non-resumable (duration ≤ 720 min, uniform). Resources ≈ `max(4, N/20)`.
Calendar: standard Mon–Fri 07:00–19:00.

## Results

### Table-size growth with horizon length (dense, N=300 fixed, 61 resumable ops)

| Horizon | Windows | Dense table entries | Build time |
|---|---|---|---|
| 7d  | 5  | 531,186   | 0.4s |
| 30d | 22 | 2,551,506 | 1.5s |
| 90d | 65 | 7,821,906 | 4.5–8.8s |

Confirms roughly linear growth in `horizon_minutes × n_resumable_ops`. At production
scale (10K ops × 90d) this extrapolates to hundreds of millions of table entries.

### Approach A (dense) in isolation

| N | Table build | Table entries | Model build | Vars/Constraints | Solve |
|---|---|---|---|---|---|
| 300  | 3.1s | 2.84M | 1.0s | 668 / 721 | **UNKNOWN**, wall 85.7s (never found first feasible; exceeded the 60s cap under memory pressure) |
| 3000 | — | — | — | — | **CRASHED**: `MemoryError: bad allocation` inside `solver.solve()` |
| 10000 | — | — | — | — | not attempted — already failed at 3000 |

Dense is RED on its own: it doesn't survive to 3,000 operations regardless of solve
outcome.

### Approach B (pruned) — solve-difficulty threshold sweep (30-day horizon)

| N | Vars/Constraints | Status | Time to first feasible |
|---|---|---|---|
| 10  | 28 / 59   | OPTIMAL  | 0.64s |
| 50  | 128 / 159 | FEASIBLE | 6.1s |
| 100 | 252 / 285 | **UNKNOWN** | never |
| 200 | 488 / 531 | FEASIBLE | 11.5s |
| 300 | 736 / 789 | **UNKNOWN** | never (60s) |

Non-monotonic: works at 50, fails at 100, works-but-slow at 200, fails at 300+. This
pattern — not a clean size-vs-time curve — is the signature of weak propagation rather
than raw problem size: the solver isn't running out of room, it's failing to prune the
search space at all for a meaningful fraction of instances.

**Control (rules out "it's an optimization problem, not a feasibility problem"):**
N=300 @ 30d with the objective stripped entirely (pure `Solve()`, no `Minimize`) —
still `UNKNOWN` after 30s. The difficulty is in the constraint structure/propagation,
not in optimizing an objective.

### Scale ladder: baseline vs. resumable_pruned (30-day horizon)

| N | Model | Build | Vars | Constraints | Status | First feasible |
|---|---|---|---|---|---|---|
| 300   | baseline_non_resumable | 0.04s | 600    | 638    | FEASIBLE | 0.13s |
| 300   | resumable_pruned       | 0.07s | 736    | 789    | UNKNOWN  | never |
| 3000  | baseline_non_resumable | 0.46s | 6,000  | 6,173  | FEASIBLE | 1.30s |
| 3000  | resumable_pruned       | 0.22s | 7,298  | 7,621  | UNKNOWN  | never |
| 10000 | baseline_non_resumable | 0.68s | 20,000 | 20,523 | FEASIBLE | 3.98s |
| 10000 | resumable_pruned       | 1.88s | 24,032 | 25,055 | UNKNOWN  | never |

The baseline (today's production technique, unaffected by this spike) is rock-solid at
every scale tested — smooth, predictable, first feasible in under 4 seconds even at
10,000 operations. The resumable-pruned model's variable/constraint overhead over the
baseline is modest (+20–25%) at every scale — **size is not the bottleneck** — but it
never finds a single feasible solution at N≥300, at any scale tested, with 60 seconds
and 8 parallel search workers.

## Why RED, not YELLOW

The YELLOW mitigation menu specified two things: coarser start granularity for
resumable ops, and table pruning to reachable starts. The "pruned" approach already
implements both (60-minute grid, window-restricted domain) and still fails to solve.
Applying the offered mitigations more aggressively (e.g. an even coarser grid) would
shrink tables further but doesn't address the demonstrated root cause: the AddElement/
dual-no-overlap-group encoding gives CP-SAT's default portfolio search too little to
propagate on, independent of table size.

## Suggested redesign directions (not evaluated here — next spike's job)

1. **Explicit chunk-boundary intervals**, the encoding R-C3's prose text already points
   at ("chunk boundaries are calendar boundaries, so chunk count = windows crossed —
   bounded by construction") — this uses native interval/no-overlap machinery CP-SAT
   already handles well (see: the baseline's excellent scaling), rather than element-
   table lookups. Worth a follow-up spike given the baseline result above.
2. **Search hints / warm start** — seed a greedy constructive heuristic's assignment via
   `AddHint` so the solver has a feasible starting point instead of searching blind.
3. **Decomposition** — solve resumable ops per-resource or per-facility in slices,
   consistent with the "sliced daily solve" fallback docs/07 already blesses for the
   unrelated solver-gap risk.

## Reproduce

```
python tools/chunking_scale_spike.py
```
Takes roughly 12–15 minutes (multiple 60s-capped solves across the scale ladder and
threshold sweep). `smoke_test()` runs first and must print PASS before any of the
scale numbers are meaningful.

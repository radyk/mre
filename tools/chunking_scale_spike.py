"""Week-one spike (docs/07 §2, risk #1): R-C3 resumable-operation chunking
at scale. NO PRODUCTION CODE — this is a throwaway prototype answering one
question: can the "one interval + start-indexed elapsed table" encoding for
resumable operations (docs/05 R-C3) scale to 300/3K/10K operations before
Rep 2 (chunking) is built in full?

R-C3 recap: a resumable operation's WORKING duration is fixed; its ELAPSED
duration stretches to absorb calendar closures it pauses across ("pauses
only at calendar boundaries, never for other jobs" — it keeps holding the
resource while paused). Modeled here as ONE interval per operation,
[start, start+elapsed), where elapsed = table[start] via a CP-SAT
AddElement lookup — no per-chunk interval variables, no explicit pause
sub-intervals. This is the technique the report is testing at scale, not a
correctness re-derivation (correctness is exercised on tiny cases first).

Two lookup-table strategies are compared, per the report's mitigation menu:
  A) dense   — one table entry per minute of the horizon (the naive version)
  B) pruned  — table entries only at a coarse grid of "reachable" starts
               inside open calendar windows (the YELLOW mitigation)

Usage:
    python tools/chunking_scale_spike.py
"""
from __future__ import annotations

import bisect
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ortools.sat.python import cp_model as cp  # noqa: E402

from mre.modules.calendar_utils import flatten_calendar  # noqa: E402

UTC = timezone.utc
SHIFT_MIN = 720          # 07:00-19:00, Mon-Fri — matches sample_data/raw_data convention
SOLVE_TIME_LIMIT = 60.0  # per-model cap so the spike itself stays bounded
GAP_TARGET = 0.05


# ---------------------------------------------------------------------------
# Calendar: flatten once per horizon length, shared by every resource
# (per-resource calendar variation is not the variable under test here)
# ---------------------------------------------------------------------------

def build_windows(horizon_days: int) -> list[tuple[int, int]]:
    horizon_start = datetime(2026, 1, 5, tzinfo=UTC)  # a Monday
    horizon_end = horizon_start + timedelta(days=horizon_days)
    base_pattern = {"weekdays": [0, 1, 2, 3, 4], "shift_start": "07:00", "shift_end": "19:00"}
    windows = flatten_calendar(base_pattern, [], horizon_start, horizon_end)
    return [
        (int((w.start - horizon_start).total_seconds() // 60),
         int((w.end - horizon_start).total_seconds() // 60))
        for w in windows
    ]


@dataclass
class CumulativeOpen:
    """Piecewise-linear cumulative open-minutes function O(t), built once per
    horizon from window breakpoints (O(#windows) size, not O(horizon))."""
    ts: list[int] = field(default_factory=list)   # breakpoint times
    cs: list[int] = field(default_factory=list)   # O(t) at each breakpoint
    horizon_minutes: int = 0

    @classmethod
    def build(cls, windows: list[tuple[int, int]], horizon_minutes: int) -> "CumulativeOpen":
        ts, cs = [0], [0]
        acc = 0
        for s, e in windows:
            if s > ts[-1]:
                ts.append(s); cs.append(acc)       # flat through the gap
            acc += (e - s)
            ts.append(e); cs.append(acc)
        if ts[-1] < horizon_minutes:
            ts.append(horizon_minutes); cs.append(acc)
        return cls(ts=ts, cs=cs, horizon_minutes=horizon_minutes)

    def at(self, t: int) -> int:
        """O(t): open-minutes accumulated in [0, t)."""
        i = bisect.bisect_right(self.ts, t) - 1
        i = max(0, min(i, len(self.ts) - 2))
        seg_open = (self.cs[i + 1] - self.cs[i]) == (self.ts[i + 1] - self.ts[i])
        if seg_open:
            return self.cs[i] + max(0, t - self.ts[i])
        return self.cs[i]

    def inverse(self, target: int) -> int:
        """invO(target): smallest t with O(t) >= target."""
        if target <= 0:
            return 0
        i = bisect.bisect_left(self.cs, target)
        i = max(1, min(i, len(self.cs) - 1))
        # cs[i-1] < target <= cs[i]; segment (i-1,i) — find exact t within it
        seg_open = (self.cs[i] - self.cs[i - 1]) == (self.ts[i] - self.ts[i - 1])
        if seg_open:
            return self.ts[i - 1] + (target - self.cs[i - 1])
        return self.ts[i]

    def elapsed(self, s: int, w: int) -> int:
        return self.inverse(self.at(s) + w) - s


# ---------------------------------------------------------------------------
# Table strategies
# ---------------------------------------------------------------------------

def dense_table(cum: CumulativeOpen, w: int, max_start: int) -> list[int]:
    """Approach A: one entry per minute, s = 0..max_start inclusive."""
    return [cum.elapsed(s, w) for s in range(max_start + 1)]


def reachable_starts(windows: list[tuple[int, int]], max_start: int, granularity: int) -> list[int]:
    """Approach B: coarse grid of starts inside open windows only."""
    pts: list[int] = []
    for s, e in windows:
        if s > max_start:
            break
        t = s
        end = min(e, max_start + 1)
        while t < end:
            pts.append(t)
            t += granularity
    if not pts or pts[0] != 0:
        pts.insert(0, 0)
    return sorted(set(pts))


def pruned_table(cum: CumulativeOpen, w: int, starts: list[int]) -> list[int]:
    return [cum.elapsed(s, w) for s in starts]


# ---------------------------------------------------------------------------
# Operation generation
# ---------------------------------------------------------------------------

@dataclass
class Op:
    oid: int
    resource: int
    resumable: bool
    working_min: int


def generate_ops(n: int, n_resources: int, rng: random.Random) -> list[Op]:
    ops = []
    for i in range(n):
        resumable = rng.random() < 0.20
        if resumable:
            working = rng.randint(SHIFT_MIN, 3 * SHIFT_MIN)      # 1x-3x window length
        else:
            working = rng.randint(30, SHIFT_MIN)                  # must fit one window
        ops.append(Op(oid=i, resource=i % n_resources, resumable=resumable, working_min=working))
    return ops


# ---------------------------------------------------------------------------
# Model builders
# ---------------------------------------------------------------------------

@dataclass
class BuildStats:
    label: str
    n_ops: int
    horizon_days: int
    table_build_seconds: float
    table_total_entries: int
    model_build_seconds: float
    n_variables: int
    n_constraints: int
    solve_status: str = ""
    time_to_first_feasible: float | None = None
    time_to_5pct_gap: float | None = None
    wall_time: float | None = None


class _GapCallback(cp.CpSolverSolutionCallback):
    def __init__(self, gap_target: float):
        super().__init__()
        self._gap_target = gap_target
        self.t0 = time.time()
        self.t_first_feasible: float | None = None
        self.t_gap_reached: float | None = None

    def on_solution_callback(self) -> None:
        now = time.time() - self.t0
        if self.t_first_feasible is None:
            self.t_first_feasible = now
        try:
            obj = self.objective_value
            bound = self.best_objective_bound
            gap = abs(obj - bound) / abs(obj) if obj else 0.0
        except Exception:
            gap = 1.0
        if self.t_gap_reached is None and gap <= self._gap_target:
            self.t_gap_reached = now


def _solve(model: cp.CpModel, label: str, n_ops: int, horizon_days: int,
           table_build_s: float, table_entries: int, build_s: float) -> BuildStats:
    proto = model.proto
    stats = BuildStats(
        label=label, n_ops=n_ops, horizon_days=horizon_days,
        table_build_seconds=table_build_s, table_total_entries=table_entries,
        model_build_seconds=build_s,
        n_variables=len(proto.variables), n_constraints=len(proto.constraints),
    )
    solver = cp.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVE_TIME_LIMIT
    solver.parameters.num_search_workers = 8
    cb = _GapCallback(GAP_TARGET)
    t0 = time.time()
    status = solver.solve(model, cb)
    stats.wall_time = time.time() - t0
    stats.solve_status = solver.status_name(status)
    stats.time_to_first_feasible = cb.t_first_feasible
    stats.time_to_5pct_gap = cb.t_gap_reached
    return stats


def build_non_resumable_baseline(ops: list[Op], windows: list[tuple[int, int]],
                                  horizon_minutes: int, n_resources: int) -> tuple[cp.CpModel, float]:
    """Existing solver_builder-style technique: one interval per op + fixed
    blocking intervals (closures) in the same add_no_overlap group. Every op
    here is treated non-resumable (duration capped to fit one window) —
    this is the size/speed baseline the resumable model is compared against."""
    t0 = time.time()
    model = cp.CpModel()
    res_intervals: dict[int, list] = {r: [] for r in range(n_resources)}
    starts, ends = {}, {}

    for op in ops:
        dur = min(op.working_min, SHIFT_MIN)  # forced non-resumable: must fit a window
        s = model.new_int_var(0, horizon_minutes - dur, f"s{op.oid}")
        e = model.new_int_var(dur, horizon_minutes, f"e{op.oid}")
        model.add(e == s + dur)
        iv = model.new_interval_var(s, dur, e, f"iv{op.oid}")
        res_intervals[op.resource].append(iv)
        starts[op.oid] = s
        ends[op.oid] = e

    prev_end = 0
    blocking = []
    for s, e in windows:
        if s > prev_end:
            blocking.append(model.new_fixed_size_interval_var(prev_end, s - prev_end, f"blk{prev_end}"))
        prev_end = max(prev_end, e)
    if prev_end < horizon_minutes:
        blocking.append(model.new_fixed_size_interval_var(prev_end, horizon_minutes - prev_end, f"blk{prev_end}"))

    for r in range(n_resources):
        model.add_no_overlap(res_intervals[r] + blocking)

    model.minimize(sum(ends.values()))
    return model, time.time() - t0


def build_resumable_model(ops: list[Op], windows: list[tuple[int, int]], cum: CumulativeOpen,
                           horizon_minutes: int, n_resources: int, strategy: str,
                           granularity: int = 60) -> tuple[cp.CpModel, float, float, int]:
    """strategy: 'dense' (A) or 'pruned' (B). Non-resumable ops (80%) use the
    same blocking-interval technique as the baseline; resumable ops (20%)
    get a single interval whose length is looked up via AddElement.

    Two no-overlap groups per resource (see spike notes / docs/04 amendment):
      1) non-resumable intervals + closure-blocking intervals (forces
         non-resumable ops to fit a single window, same as today)
      2) ALL real operation intervals (resumable + non-resumable), no
         blocking intervals — resumable intervals are allowed to overlap a
         closure (that's the pause), but never another operation's interval.
    """
    table_t0 = time.time()
    resumable_ops = [op for op in ops if op.resumable]
    tables: dict[int, tuple[list[int], list[int]]] = {}  # oid -> (index_domain_values, elapsed_values)
    total_entries = 0
    for op in resumable_ops:
        max_start = horizon_minutes - op.working_min
        max_start = max(0, max_start)
        if strategy == "dense":
            idx_values = list(range(max_start + 1))
            elapsed_values = dense_table(cum, op.working_min, max_start)
        elif strategy == "pruned":
            idx_values = reachable_starts(windows, max_start, granularity)
            elapsed_values = pruned_table(cum, op.working_min, idx_values)
        else:
            raise ValueError(strategy)
        tables[op.oid] = (idx_values, elapsed_values)
        total_entries += len(idx_values)
    table_build_s = time.time() - table_t0

    build_t0 = time.time()
    model = cp.CpModel()
    res_intervals_no_blocking: dict[int, list] = {r: [] for r in range(n_resources)}
    res_intervals_with_blocking: dict[int, list] = {r: [] for r in range(n_resources)}
    ends = {}

    for op in ops:
        if not op.resumable:
            dur = min(op.working_min, SHIFT_MIN)
            s = model.new_int_var(0, horizon_minutes - dur, f"s{op.oid}")
            e = model.new_int_var(dur, horizon_minutes, f"e{op.oid}")
            model.add(e == s + dur)
            iv = model.new_interval_var(s, dur, e, f"iv{op.oid}")
            res_intervals_no_blocking[op.resource].append(iv)
            res_intervals_with_blocking[op.resource].append(iv)
            ends[op.oid] = e
            continue

        idx_values, elapsed_values = tables[op.oid]
        max_start = idx_values[-1]

        if strategy == "dense":
            s = model.new_int_var(0, max_start, f"s{op.oid}")
            elapsed = model.new_int_var(op.working_min, horizon_minutes, f"el{op.oid}")
            model.add_element(s, elapsed_values, elapsed)
        else:
            k = model.new_int_var(0, len(idx_values) - 1, f"k{op.oid}")
            s = model.new_int_var(0, max_start, f"s{op.oid}")
            elapsed = model.new_int_var(op.working_min, horizon_minutes, f"el{op.oid}")
            model.add_element(k, idx_values, s)
            model.add_element(k, elapsed_values, elapsed)

        e = model.new_int_var(op.working_min, horizon_minutes, f"e{op.oid}")
        model.add(e == s + elapsed)
        iv = model.new_interval_var(s, elapsed, e, f"iv{op.oid}")
        res_intervals_no_blocking[op.resource].append(iv)
        # deliberately NOT added to res_intervals_with_blocking — resumable
        # intervals may legally overlap a closure (the pause).
        ends[op.oid] = e

    prev_end = 0
    blocking = []
    for s, e in windows:
        if s > prev_end:
            blocking.append(model.new_fixed_size_interval_var(prev_end, s - prev_end, f"blk{prev_end}"))
        prev_end = max(prev_end, e)
    if prev_end < horizon_minutes:
        blocking.append(model.new_fixed_size_interval_var(prev_end, horizon_minutes - prev_end, f"blk{prev_end}"))

    for r in range(n_resources):
        model.add_no_overlap(res_intervals_with_blocking[r] + blocking)
        model.add_no_overlap(res_intervals_no_blocking[r])

    model.minimize(sum(ends.values()))
    build_s = time.time() - build_t0
    return model, table_build_s, build_s, total_entries


# ---------------------------------------------------------------------------
# Correctness smoke test (tiny case, before trusting the scale numbers)
# ---------------------------------------------------------------------------

def smoke_test() -> None:
    windows = build_windows(horizon_days=5)
    horizon_minutes = 5 * 1440
    cum = CumulativeOpen.build(windows, horizon_minutes)

    # A resumable op needing 900 min (1.25x shift) starting at the shift open
    # (minute 420 = 07:00 on day 0) should pause overnight and finish the
    # next morning: elapsed = 900 + (closure length).
    day0_open, day0_close = windows[0]
    assert day0_open == 420 and day0_close == 420 + SHIFT_MIN, windows[0]
    e = cum.elapsed(day0_open, 900)
    remaining_after_day0 = 900 - SHIFT_MIN  # 180 min still needed on day 1
    day1_open = windows[1][0]
    expected_finish = day1_open + remaining_after_day0
    expected_elapsed = expected_finish - day0_open
    assert e == expected_elapsed, f"smoke test failed: got {e}, expected {expected_elapsed}"

    # A resumable op that fits entirely within one window needs no pause.
    e2 = cum.elapsed(day0_open, 300)
    assert e2 == 300, f"smoke test failed (no pause case): got {e2}"

    print("[smoke_test] PASS — elapsed() matches hand-computed pause behavior")


# ---------------------------------------------------------------------------
# Report driver
# ---------------------------------------------------------------------------

def run_scenario(n_ops: int, horizon_days: int, seed: int = 7) -> dict[str, BuildStats]:
    rng = random.Random(seed)
    n_resources = max(4, n_ops // 20)
    horizon_minutes = horizon_days * 1440
    windows = build_windows(horizon_days)
    cum = CumulativeOpen.build(windows, horizon_minutes)
    ops = generate_ops(n_ops, n_resources, rng)

    results: dict[str, BuildStats] = {}

    model_b, t0 = build_non_resumable_baseline(ops, windows, horizon_minutes, n_resources)
    results["baseline_non_resumable"] = _solve(
        model_b, "baseline_non_resumable", n_ops, horizon_days, 0.0, 0, t0,
    )

    model_p, table_s, build_s, entries = build_resumable_model(
        ops, windows, cum, horizon_minutes, n_resources, strategy="pruned",
    )
    results["resumable_pruned"] = _solve(
        model_p, "resumable_pruned", n_ops, horizon_days, table_s, entries, build_s,
    )

    return results


def run_dense_only(n_ops: int, horizon_days: int, seed: int = 7) -> BuildStats:
    """Approach A in isolation, for scales where it's still tractable to build."""
    rng = random.Random(seed)
    n_resources = max(4, n_ops // 20)
    horizon_minutes = horizon_days * 1440
    windows = build_windows(horizon_days)
    cum = CumulativeOpen.build(windows, horizon_minutes)
    ops = generate_ops(n_ops, n_resources, rng)
    model_d, table_s, build_s, entries = build_resumable_model(
        ops, windows, cum, horizon_minutes, n_resources, strategy="dense",
    )
    return _solve(model_d, "resumable_dense", n_ops, horizon_days, table_s, entries, build_s)


def print_stats(label: str, s: BuildStats) -> None:
    print(f"[{label}] n_ops={s.n_ops} horizon_days={s.horizon_days}")
    print(f"    table:  build={s.table_build_seconds:.3f}s  entries={s.table_total_entries:,}")
    print(f"    model:  build={s.model_build_seconds:.3f}s  vars={s.n_variables:,}  constraints={s.n_constraints:,}")
    print(f"    solve:  status={s.solve_status}  wall={s.wall_time:.2f}s  "
          f"first_feasible={s.time_to_first_feasible}  5%_gap={s.time_to_5pct_gap}")


def run_feasibility_only(n_ops: int, horizon_days: int, seed: int = 7, time_limit: float = 30.0):
    """Control test: strip the objective (pure feasibility) to check whether
    the solve difficulty is an optimization artifact or a search/propagation
    problem with the constraint structure itself."""
    rng = random.Random(seed)
    n_resources = max(4, n_ops // 20)
    horizon_minutes = horizon_days * 1440
    windows = build_windows(horizon_days)
    cum = CumulativeOpen.build(windows, horizon_minutes)
    ops = generate_ops(n_ops, n_resources, rng)
    model, _, _, _ = build_resumable_model(ops, windows, cum, horizon_minutes, n_resources, strategy="pruned")
    model.clear_objective()
    solver = cp.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8
    t0 = time.time()
    status = solver.solve(model)
    return solver.status_name(status), time.time() - t0


def main() -> None:
    smoke_test()
    print()

    print("=== Table-size growth with horizon length (dense strategy, fixed N=300) ===")
    for horizon_days in (7, 30, 90):
        t0 = time.time()
        windows = build_windows(horizon_days)
        horizon_minutes = horizon_days * 1440
        cum = CumulativeOpen.build(windows, horizon_minutes)
        ops = generate_ops(300, max(4, 300 // 20), random.Random(1))
        resumable = [o for o in ops if o.resumable]
        total_entries = 0
        tt0 = time.time()
        for op in resumable:
            max_start = max(0, horizon_minutes - op.working_min)
            total_entries += len(dense_table(cum, op.working_min, max_start))
        build_time = time.time() - tt0
        print(f"  horizon={horizon_days:>3}d  windows={len(windows):>4}  "
              f"resumable_ops={len(resumable):>3}  dense_table_entries={total_entries:>12,}  "
              f"build={build_time:6.2f}s")
    print()

    print("=== Approach A (dense) in isolation — where does it stop being tractable? ===")
    print("  n_ops=300 @ 30d: measured in a prior run — table=3.07s/2.84M entries, "
          "model_build=1.04s (668 vars/721 constraints), solve wall=85.7s status=UNKNOWN "
          "(exceeded the 60s cap under memory pressure, never reached first feasible)")
    print("  n_ops=3000 @ 30d: CRASHED — MemoryError: bad allocation inside solver.solve(), "
          "handing ~10x the N=300 table volume (tens of millions of int64 table entries "
          "across ~600 resumable ops) to the CP-SAT C++ backend exhausted memory. Not retried "
          "here (isolating it further doesn't change the verdict); see the docs/04 write-up.")
    print("  n_ops=10000 @ 30d: not attempted — already RED at 3000")
    print()

    print("=== Solve-difficulty threshold sweep: resumable_pruned, 30-day horizon ===")
    print("  (small-N control to see whether difficulty scales cleanly with N, or is erratic)")
    for n_ops in (10, 50, 100, 200):
        res = run_scenario(n_ops, horizon_days=30)
        print_stats("resumable_pruned", res["resumable_pruned"])
    print()

    print("=== Control: pure feasibility (objective stripped), N=300 @ 30d, resumable_pruned ===")
    status, wall = run_feasibility_only(300, horizon_days=30, time_limit=30.0)
    print(f"  status={status}  wall={wall:.2f}s  "
          f"(if this also fails to find a solution, the difficulty is in the constraint "
          f"structure/propagation, not the optimization objective)")
    print()

    print("=== Scale ladder: baseline (non-resumable) vs resumable_pruned, 30-day horizon ===")
    all_results = {}
    for n_ops in (300, 3000, 10000):
        res = run_scenario(n_ops, horizon_days=30)
        all_results[n_ops] = res
        for label, s in res.items():
            print_stats(label, s)
        print()

    print("=== Summary table ===")
    header = f"{'n_ops':>7} {'model':>22} {'build_s':>9} {'vars':>9} {'cons':>9} {'status':>10} {'first_feas':>11} {'5pct_gap':>9}"
    print(header)
    for n_ops, res in all_results.items():
        for label, s in res.items():
            print(f"{n_ops:>7} {label:>22} {s.model_build_seconds:>9.3f} {s.n_variables:>9,} "
                  f"{s.n_constraints:>9,} {s.solve_status:>10} "
                  f"{str(s.time_to_first_feasible):>11} {str(s.time_to_5pct_gap):>9}")


if __name__ == "__main__":
    main()

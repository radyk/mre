"""Week-one spike #2 (docs/07 §2, risk #1): chunk-boundary-interval encoding
for R-C3 resumable operations. NO PRODUCTION CODE — throwaway prototype.

Spike 1 (tools/chunking_scale_spike.py) tried "one interval + start-indexed
elapsed table via AddElement" and was falsified: CP-SAT's default search
never found a first feasible solution at N>=300, dense or pruned, with or
without an objective (see tools/chunking_scale_spike_report.md).

This spike tests the alternative the R-C3 ruling text itself points at:
"chunk boundaries are calendar boundaries, so chunk count = windows crossed
- bounded by construction." Encoding: per resumable op, one OPTIONAL
interval per calendar window it could occupy (pruned to a feasible range),
all participating directly in the resource's native no_overlap alongside
non-resumable intervals and calendar-closure blocking intervals — no
AddElement, no lookup tables. Constraints:
  1) chunk working-durations sum to the op's total working duration
  2) gluing: if chunk k+1 is used, chunk k ends at its window's end and
     chunk k+1 starts at the next window's start (pauses only at calendar
     boundaries, R-C3)
  3) used chunks are contiguous (single 0->1 and single 1->0 transition)

Durations 1-3x the 720-minute shift window => 2-4 chunks per op by
construction (worst case: 1-minute first chunk + 2 full + 1 partial last,
for a 2160-minute op starting 1 minute before a window closes).

Usage:
    python tools/chunking_spike2.py
"""
from __future__ import annotations

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
SHIFT_MIN = 720
SOLVE_TIME_LIMIT = 60.0
GAP_TARGET = 0.05
CHUNKS_MAX = 4  # sufficient for duration <= 3x a 720-min window (see docstring)


# ---------------------------------------------------------------------------
# Calendar
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


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

@dataclass
class Op:
    oid: int
    resource: int
    resumable: bool
    working_min: int


def generate_ops(n: int, n_resources: int, density: str, rng: random.Random) -> list[Op]:
    """density: 'realistic' (~1% resumable, the deployment shape) or
    'stress' (20% resumable, spike 1's ceiling-finding setup)."""
    frac = 0.01 if density == "realistic" else 0.20
    ops = []
    for i in range(n):
        resumable = rng.random() < frac
        if resumable:
            # strictly > 1x window so it genuinely needs >=2 chunks
            working = rng.randint(SHIFT_MIN + 1, 3 * SHIFT_MIN)
        else:
            working = rng.randint(30, SHIFT_MIN)
        ops.append(Op(oid=i, resource=i % n_resources, resumable=resumable, working_min=working))
    return ops


# ---------------------------------------------------------------------------
# Per-op candidate window range (pruning)
# ---------------------------------------------------------------------------

def feasible_window_range(windows: list[tuple[int, int]], working_min: int) -> tuple[int, int]:
    """Return (lo, hi) window indices this op could ever touch: hi trims
    windows where there isn't enough trailing calendar capacity left to
    finish the op if it started there; lo is always 0 (no per-op
    earliest_start modeled in this spike — see report for what pruning
    does and doesn't buy without one)."""
    n = len(windows)
    suffix_capacity = [0] * (n + 1)
    for i in range(n - 1, -1, -1):
        s, e = windows[i]
        suffix_capacity[i] = suffix_capacity[i + 1] + (e - s)
    max_start_idx = 0
    for i in range(n):
        if suffix_capacity[i] >= working_min:
            max_start_idx = i
    hi = min(max_start_idx + CHUNKS_MAX - 1, n - 1)
    return 0, hi


# ---------------------------------------------------------------------------
# Model builders
# ---------------------------------------------------------------------------

@dataclass
class BuildStats:
    label: str
    n_ops: int
    n_resumable: int
    horizon_days: int
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


def _solve(model: cp.CpModel, label: str, n_ops: int, n_resumable: int,
           horizon_days: int, build_s: float, hints: bool = False) -> tuple[BuildStats, cp.CpSolver]:
    """Returns (stats, solver) — the solver keeps its solution values so
    callers needing post-solve extraction (semantic checks) don't have to
    solve the same model a second time."""
    proto = model.proto
    stats = BuildStats(
        label=label, n_ops=n_ops, n_resumable=n_resumable, horizon_days=horizon_days,
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
    return stats, solver


def build_baseline_non_resumable(ops: list[Op], windows: list[tuple[int, int]],
                                  horizon_minutes: int, n_resources: int) -> tuple[cp.CpModel, float]:
    """Same technique as today's production solver_builder.py — the scale
    reference every chunk-encoding variant is measured against."""
    t0 = time.time()
    model = cp.CpModel()
    res_intervals: dict[int, list] = {r: [] for r in range(n_resources)}
    ends = {}
    for op in ops:
        dur = min(op.working_min, SHIFT_MIN)
        s = model.new_int_var(0, horizon_minutes - dur, f"s{op.oid}")
        e = model.new_int_var(dur, horizon_minutes, f"e{op.oid}")
        model.add(e == s + dur)
        iv = model.new_interval_var(s, dur, e, f"iv{op.oid}")
        res_intervals[op.resource].append(iv)
        ends[op.oid] = e

    blocking = _blocking_intervals(model, windows, horizon_minutes)
    for r in range(n_resources):
        model.add_no_overlap(res_intervals[r] + blocking)
    model.minimize(sum(ends.values()))
    return model, time.time() - t0


def _blocking_intervals(model: cp.CpModel, windows: list[tuple[int, int]], horizon_minutes: int) -> list:
    prev_end = 0
    blocking = []
    for s, e in windows:
        if s > prev_end:
            blocking.append(model.new_fixed_size_interval_var(prev_end, s - prev_end, f"blk{prev_end}"))
        prev_end = max(prev_end, e)
    if prev_end < horizon_minutes:
        blocking.append(model.new_fixed_size_interval_var(prev_end, horizon_minutes - prev_end, f"blk{prev_end}"))
    return blocking


@dataclass
class ChunkVars:
    op_start: object
    op_end: object
    used: dict          # window_idx -> BoolVar
    dur: dict           # window_idx -> IntVar
    interval: dict       # window_idx -> OptionalIntervalVar


def build_chunk_model(ops: list[Op], windows: list[tuple[int, int]],
                       horizon_minutes: int, n_resources: int) -> tuple[cp.CpModel, float, dict]:
    """The primary encoding under test. Returns (model, build_seconds,
    {oid: ChunkVars}) for resumable ops (used by the post-solve semantic
    assertion and by the warm-start exploratory arm)."""
    t0 = time.time()
    model = cp.CpModel()
    res_intervals: dict[int, list] = {r: [] for r in range(n_resources)}
    ends = {}
    chunk_vars: dict[int, ChunkVars] = {}

    for op in ops:
        if not op.resumable:
            dur = min(op.working_min, SHIFT_MIN)
            s = model.new_int_var(0, horizon_minutes - dur, f"s{op.oid}")
            e = model.new_int_var(dur, horizon_minutes, f"e{op.oid}")
            model.add(e == s + dur)
            iv = model.new_interval_var(s, dur, e, f"iv{op.oid}")
            res_intervals[op.resource].append(iv)
            ends[op.oid] = e
            continue

        lo, hi = feasible_window_range(windows, op.working_min)
        idxs = list(range(lo, hi + 1))

        used, durv, ivs, starts, endvs = {}, {}, {}, {}, {}
        for w in idxs:
            w_start, w_end = windows[w]
            used[w] = model.new_bool_var(f"u{op.oid}_{w}")
            s_var = model.new_int_var(w_start, w_end, f"s{op.oid}_{w}")
            e_var = model.new_int_var(w_start, w_end, f"e{op.oid}_{w}")
            d_var = model.new_int_var(0, w_end - w_start, f"d{op.oid}_{w}")
            iv = model.new_optional_interval_var(s_var, d_var, e_var, used[w], f"iv{op.oid}_{w}")
            model.add(d_var == 0).only_enforce_if(used[w].Not())
            used[w], durv[w], ivs[w], starts[w], endvs[w] = used[w], d_var, iv, s_var, e_var
            res_intervals[op.resource].append(iv)

        # (1) chunk working-durations sum to the op's total working duration
        model.add(sum(durv[w] for w in idxs) == op.working_min)

        # (3) contiguity — single start-transition, single end-transition
        start_trans, end_trans = {}, {}
        for pos, w in enumerate(idxs):
            if pos == 0:
                start_trans[w] = used[w]
            else:
                prev_w = idxs[pos - 1]
                t = model.new_bool_var(f"st{op.oid}_{w}")
                model.add_bool_and([used[w], used[prev_w].Not()]).only_enforce_if(t)
                model.add_bool_or([used[w].Not(), used[prev_w]]).only_enforce_if(t.Not())
                start_trans[w] = t
            if pos == len(idxs) - 1:
                end_trans[w] = used[w]
            else:
                next_w = idxs[pos + 1]
                t2 = model.new_bool_var(f"et{op.oid}_{w}")
                model.add_bool_and([used[w], used[next_w].Not()]).only_enforce_if(t2)
                model.add_bool_or([used[w].Not(), used[next_w]]).only_enforce_if(t2.Not())
                end_trans[w] = t2
        model.add(sum(start_trans.values()) == 1)
        model.add(sum(end_trans.values()) == 1)

        # (2) gluing — a chunk followed by another chunk of the same op
        # must run to its window's end; the next chunk starts at its
        # window's open (R-C3: pauses only at calendar boundaries)
        for pos in range(len(idxs) - 1):
            w, w_next = idxs[pos], idxs[pos + 1]
            w_end = windows[w][1]
            w_next_start = windows[w_next][0]
            model.add(endvs[w] == w_end).only_enforce_if([used[w], used[w_next]])
            model.add(starts[w_next] == w_next_start).only_enforce_if([used[w], used[w_next]])

        op_start = model.new_int_var(windows[lo][0], windows[hi][1], f"opstart{op.oid}")
        op_end = model.new_int_var(windows[lo][0], windows[hi][1], f"opend{op.oid}")
        for w in idxs:
            model.add(op_start == starts[w]).only_enforce_if(start_trans[w])
            model.add(op_end == endvs[w]).only_enforce_if(end_trans[w])
        ends[op.oid] = op_end
        chunk_vars[op.oid] = ChunkVars(op_start=op_start, op_end=op_end, used=used, dur=durv, interval=ivs)

    blocking = _blocking_intervals(model, windows, horizon_minutes)
    for r in range(n_resources):
        model.add_no_overlap(res_intervals[r] + blocking)
    model.minimize(sum(ends.values()))
    return model, time.time() - t0, chunk_vars


# ---------------------------------------------------------------------------
# Correctness smoke test
# ---------------------------------------------------------------------------

def smoke_test() -> None:
    """Tiny hand-checkable case: one resumable op needing 900 minutes
    (1.25x shift), one resource, 5-day horizon. Must chunk across exactly
    one calendar boundary, with the pause landing exactly on it."""
    windows = build_windows(horizon_days=5)
    horizon_minutes = 5 * 1440
    ops = [Op(oid=0, resource=0, resumable=True, working_min=900)]
    model, _, chunk_vars = build_chunk_model(ops, windows, horizon_minutes, n_resources=1)

    solver = cp.CpSolver()
    solver.parameters.num_search_workers = 1
    status = solver.solve(model)
    assert status in (cp.OPTIMAL, cp.FEASIBLE), f"smoke test infeasible: {solver.status_name(status)}"

    cv = chunk_vars[0]
    used_windows = [w for w, u in cv.used.items() if solver.value(u) == 1]
    assert len(used_windows) == 2, f"expected 2 chunks for a 900-min/720-min-window op, got {used_windows}"
    w0, w1 = sorted(used_windows)
    assert w1 == w0 + 1, "used windows must be the two consecutive calendar windows"

    total_dur = sum(solver.value(cv.dur[w]) for w in used_windows)
    assert total_dur == 900, f"chunk durations must sum to working duration, got {total_dur}"

    # The pause must land exactly on the calendar boundary between the two windows.
    chunk0_end = solver.value(cv.interval[w0].end_expr())
    chunk1_start = solver.value(cv.interval[w1].start_expr())
    assert chunk0_end == windows[w0][1], "first chunk must run to its window's close"
    assert chunk1_start == windows[w1][0], "second chunk must start at the next window's open"

    print(f"[smoke_test] PASS — 900-min op chunked into windows {w0},{w1}; "
          f"pause = [{chunk0_end}, {chunk1_start}) aligns exactly with the calendar boundary")


# ---------------------------------------------------------------------------
# Semantic assertion (post-solve, required for GREEN)
# ---------------------------------------------------------------------------

def assert_pauses_align_with_calendar(solver: cp.CpSolver, windows: list[tuple[int, int]],
                                       chunk_vars: dict[int, ChunkVars]) -> tuple[bool, int]:
    """For every chunked op in the solution, every pause between consecutive
    used chunks must exactly equal a real calendar closure. Returns
    (all_ok, ops_checked)."""
    ok = True
    checked = 0
    for oid, cv in chunk_vars.items():
        used = sorted(w for w, u in cv.used.items() if solver.value(u) == 1)
        if len(used) < 2:
            continue
        checked += 1
        for a, b in zip(used, used[1:]):
            pause_start = solver.value(cv.interval[a].end_expr())
            pause_end = solver.value(cv.interval[b].start_expr())
            if pause_start != windows[a][1] or pause_end != windows[b][0] or b != a + 1:
                ok = False
    return ok, checked


# ---------------------------------------------------------------------------
# Scenario driver
# ---------------------------------------------------------------------------

def run_scenario(n_ops: int, horizon_days: int, density: str, seed: int = 7):
    rng = random.Random(seed)
    n_resources = max(4, n_ops // 20)
    horizon_minutes = horizon_days * 1440
    windows = build_windows(horizon_days)
    ops = generate_ops(n_ops, n_resources, density, rng)
    n_resumable = sum(1 for o in ops if o.resumable)

    model_b, build_b = build_baseline_non_resumable(ops, windows, horizon_minutes, n_resources)
    stats_b, _ = _solve(model_b, f"baseline_{density}", n_ops, n_resumable, horizon_days, build_b)

    model_c, build_c, chunk_vars = build_chunk_model(ops, windows, horizon_minutes, n_resources)
    stats_c, solver_c = _solve(model_c, f"chunked_{density}", n_ops, n_resumable, horizon_days, build_c)

    return stats_b, stats_c, solver_c, chunk_vars, windows


def print_stats(s: BuildStats) -> None:
    print(f"[{s.label}] n_ops={s.n_ops} n_resumable={s.n_resumable} horizon_days={s.horizon_days}")
    print(f"    model:  build={s.model_build_seconds:.3f}s  vars={s.n_variables:,}  constraints={s.n_constraints:,}")
    print(f"    solve:  status={s.solve_status}  wall={s.wall_time:.2f}s  "
          f"first_feasible={s.time_to_first_feasible}  5%_gap={s.time_to_5pct_gap}")


# ---------------------------------------------------------------------------
# EXPLORATORY secondary arms (only meaningful if the primary encoding works)
# ---------------------------------------------------------------------------

def exploratory_warm_start(n_ops: int, horizon_days: int, density: str, seed: int = 7) -> BuildStats:
    """EXPLORATORY — seed a greedy earliest-fit assignment as a solver hint."""
    rng = random.Random(seed)
    n_resources = max(4, n_ops // 20)
    horizon_minutes = horizon_days * 1440
    windows = build_windows(horizon_days)
    ops = generate_ops(n_ops, n_resources, density, rng)
    n_resumable = sum(1 for o in ops if o.resumable)
    model, build_s, chunk_vars = build_chunk_model(ops, windows, horizon_minutes, n_resources)

    # Greedy hint: for each resumable op, mark its first ceil(w/window) windows
    # (in candidate-index order) as used, front-loading the duration. Not
    # necessarily a feasible assignment (ignores cross-op resource contention)
    # — just a starting point for the solver, added one (var, value) pair at
    # a time per the add_hint(var, value) API.
    for op in ops:
        if not op.resumable or op.oid not in chunk_vars:
            continue
        cv = chunk_vars[op.oid]
        idxs = sorted(cv.used.keys())
        remaining = op.working_min
        for w in idxs:
            if remaining <= 0:
                model.add_hint(cv.used[w], 0)
                continue
            w_len = windows[w][1] - windows[w][0]
            remaining -= min(w_len, remaining)
            model.add_hint(cv.used[w], 1)

    stats, _ = _solve(model, f"exploratory_warmstart_{density}", n_ops, n_resumable, horizon_days, build_s)
    return stats


def exploratory_decomposition(n_ops: int, horizon_days: int, density: str, seed: int = 7) -> list[BuildStats]:
    """EXPLORATORY — solve per-resource independently instead of one global
    model. Reports per-shard stats; a real implementation would need a
    cross-shard reconciliation pass this spike does not attempt."""
    rng = random.Random(seed)
    n_resources = max(4, n_ops // 20)
    horizon_minutes = horizon_days * 1440
    windows = build_windows(horizon_days)
    ops = generate_ops(n_ops, n_resources, density, rng)

    results = []
    n_shards_sampled = min(3, n_resources)
    for r in range(n_shards_sampled):
        shard_ops = [Op(oid=o.oid, resource=0, resumable=o.resumable, working_min=o.working_min)
                     for o in ops if o.resource == r]
        if not shard_ops:
            continue
        model, build_s, _ = build_chunk_model(shard_ops, windows, horizon_minutes, n_resources=1)
        n_resumable = sum(1 for o in shard_ops if o.resumable)
        stats, _ = _solve(model, f"exploratory_decomp_r{r}_{density}",
                          len(shard_ops), n_resumable, horizon_days, build_s)
        results.append(stats)
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    smoke_test()
    print()

    print("=== PRIMARY: baseline vs chunked, both densities, 30-day horizon ===")
    all_results = {}
    for density in ("realistic", "stress"):
        for n_ops in (300, 3000, 10000):
            t0 = time.time()
            stats_b, stats_c, solver_c, chunk_vars, windows = run_scenario(n_ops, 30, density)
            print_stats(stats_b)
            print_stats(stats_c)

            # Semantic assertion (only meaningful if a solution was found) —
            # reuses the already-solved solver_c, no second solve needed.
            if stats_c.solve_status in ("OPTIMAL", "FEASIBLE"):
                ok, checked = assert_pauses_align_with_calendar(solver_c, windows, chunk_vars)
                print(f"    semantic check: pauses-align-with-calendar={ok} ({checked} chunked ops verified)")
            print(f"    scenario wall (build+solve x2): {time.time()-t0:.1f}s")
            print()
            all_results[(density, n_ops)] = (stats_b, stats_c)

    print("=== Summary table ===")
    header = (f"{'density':>10} {'n_ops':>7} {'model':>20} {'build_s':>8} {'vars':>9} "
              f"{'cons':>9} {'status':>10} {'first_feas':>11} {'5pct_gap':>9}")
    print(header)
    for (density, n_ops), (sb, sc) in all_results.items():
        for s in (sb, sc):
            print(f"{density:>10} {n_ops:>7} {s.label:>20} {s.model_build_seconds:>8.3f} "
                  f"{s.n_variables:>9,} {s.n_constraints:>9,} {s.solve_status:>10} "
                  f"{str(s.time_to_first_feasible):>11} {str(s.time_to_5pct_gap):>9}")

    # Gate: run exploratory mitigations only if the primary encoding is
    # actually viable (realistic density, the deployment-relevant case,
    # resolves at every rung). If even realistic density failed, the
    # encoding itself is RED and mitigations for a harder density are moot.
    realistic_ok = all(
        sc.solve_status in ("OPTIMAL", "FEASIBLE")
        for (density, _), (_, sc) in all_results.items() if density == "realistic"
    )
    stress_ok = all(
        sc.solve_status in ("OPTIMAL", "FEASIBLE")
        for (density, _), (_, sc) in all_results.items() if density == "stress"
    )
    print()
    if not realistic_ok:
        print("Primary encoding failed even at realistic (deployment-relevant) density — "
              "RED, skipping exploratory arms entirely.")
        return
    if stress_ok:
        print("Primary encoding resolved at both densities — no mitigation gap to explore.")
        return

    print("=== EXPLORATORY (secondary arms — realistic density is viable; probing whether")
    print("    simple mitigations rescue the stress-density ceiling) ===")
    print("--- warm-start hints, stress density, N=3000 ---")
    print_stats(exploratory_warm_start(3000, 30, "stress"))
    print("--- per-resource decomposition, stress density, N=3000 (3 shards sampled) ---")
    for s in exploratory_decomposition(3000, 30, "stress"):
        print_stats(s)


if __name__ == "__main__":
    main()

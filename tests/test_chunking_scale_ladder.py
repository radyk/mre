"""Rep 2 acceptance item 5d: scale-ladder timings (realistic density) as
regression baselines, through the actual production pipeline (IDSAdapter ->
Validator -> Planner -> SolverBuilder -> SolveRunner -> Extractor) — not the
spike scripts. "Realistic density" reuses chunking_exam's own anomaly
(~1% of orders get a genuinely resumable, multi-window operation), matching
tools/chunking_spike2_report.md's density definition and its ACCEPT bar:
feasible at every scale, first-feasible within the non-resumable baseline's
ballpark (single-digit-to-low-double-digit seconds at 10K).

N=300 always runs; N=3,000/10,000 are marked slow (opt in with --runslow),
matching the clean_large convention in tests/test_ids_end_to_end.py.
"""
from __future__ import annotations

import time

import pytest

from mre.__main__ import main as mre_main
from tools.generate_erp_dataset import generate

def _run_scale(tmp_path, n_ops: int, time_limit: float, seed: int = 3):
    resumable_n = max(1, round(n_ops * 0.01))
    sub_dir = tmp_path / "submission"
    out_dir = tmp_path / "out"
    generate(
        sub_dir, orders=n_ops, resources=max(8, n_ops // 20), facilities=1, seed=seed,
        scenario="clean_small", anomalies=[f"chunking_exam:{resumable_n}"],
    )
    t0 = time.time()
    exit_code = mre_main([
        "--submission", str(sub_dir), "--out", str(out_dir),
        "--snapshot-id", f"snap-ladder-{n_ops}", "--time-limit", str(time_limit),
    ])
    wall = time.time() - t0
    return exit_code, wall, out_dir


class TestRealisticDensityScaleLadder:
    """Measured baselines (seed=3, realistic ~1% resumable density):
      N=300   ->   4.6s wall, OPTIMAL
      N=3000  ->  97.3s wall, OPTIMAL (--time-limit 60)
      N=10000 -> 349.3s wall, FEASIBLE (--time-limit 240 configured — CP-SAT's
                 time-limit enforcement overshoots by ~1.4x at this model size,
                 itself worth knowing; a clean (non-resumable) N=10000 run
                 reaches OPTIMAL in ~60s, so the ~100 resumable ops are what
                 push this past a single-digit-seconds/low-double-digit
                 first-feasible ballpark — spike 2's isolated minimal-model
                 measurement (10s) did not carry over once the full
                 production objective (cost/tardiness) competes with the
                 chunk-boundary encoding for search attention. See the
                 2026-07-11 docs/04 amendment.
    """

    def test_n300(self, tmp_path):
        exit_code, wall, out_dir = _run_scale(tmp_path, 300, time_limit=60.0)
        assert exit_code == 0, f"pipeline failed at N=300 (wall={wall:.1f}s)"
        assert (out_dir / "schedule.csv").exists()
        print(f"\n[scale-ladder] N=300 realistic density: wall={wall:.2f}s")

    @pytest.mark.slow
    def test_n3000(self, tmp_path):
        exit_code, wall, out_dir = _run_scale(tmp_path, 3000, time_limit=60.0)
        assert exit_code == 0, f"pipeline failed at N=3000 (wall={wall:.1f}s)"
        assert (out_dir / "schedule.csv").exists()
        print(f"\n[scale-ladder] N=3000 realistic density: wall={wall:.2f}s")

    @pytest.mark.slow
    def test_n10000(self, tmp_path):
        exit_code, wall, out_dir = _run_scale(tmp_path, 10000, time_limit=240.0)
        assert exit_code == 0, f"pipeline failed at N=10000 (wall={wall:.1f}s)"
        assert (out_dir / "schedule.csv").exists()
        print(f"\n[scale-ladder] N=10000 realistic density: wall={wall:.2f}s")

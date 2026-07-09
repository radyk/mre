"""The defaults-reproduce-baseline gate (docs/05 §3 item 2, §4).

The precedence-edge surgery (docs/05 §4: Operation.predecessors -> first-class
PrecedenceEdge records; dwell dies as a phase, R-Dwell) must not change what
either the sample_data pipeline or "the gauntlet" (raw_data, real ticketing
extract) actually schedules. This is a regression gate, not a promise:
golden fixtures were captured from the pre-surgery code and are compared
byte-for-byte (schedule.csv) and value-for-value (cost ledger) against
post-surgery runs.

Determinism note: CP-SAT's default parallel search is NOT reproducible
run-to-run when a model has tied-cost alternatives (confirmed empirically —
two stock runs of the unchanged sample_data pipeline produced different
resource assignments for the same proven-optimal cost). Bit-identical
comparison requires pinning three things simultaneously:
  - PYTHONHASHSEED=0 (Python's per-process string-hash randomization affects
    dict/set iteration order, which affects CP-SAT variable creation order)
  - --solver-workers 1 (CP-SAT parallel search is inherently non-reproducible)
  - --solver-seed 42 (CP-SAT's internal tie-breaking)
All three are pinned here via subprocess so the test exercises the exact
same code path (python -m mre) used to capture the golden fixtures.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures" / "baselines"


def _run_mre(args: list[str], out_dir: Path) -> str:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    result = subprocess.run(
        [sys.executable, "-m", "mre", *args, "--out", str(out_dir),
         "--solver-workers", "1", "--solver-seed", "42"],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, (
        f"pipeline failed (exit {result.returncode}):\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    return result.stdout


def _extract_summary(stdout: str) -> dict:
    d: dict = {}
    for line in stdout.splitlines():
        if "Total cost  :" in line:
            d["total_cost"] = float(line.split(":")[1].strip())
        if "  production:" in line:
            d["production_cost"] = float(line.split(":")[1].strip())
        if "  setup     :" in line:
            d["setup_cost"] = float(line.split(":")[1].strip())
        if "  tardiness :" in line:
            d["tardiness_cost"] = float(line.split(":")[1].strip())
    return d


class TestSampleDataReproducesBaseline:
    def test_schedule_csv_identical(self, tmp_path):
        stdout = _run_mre(
            ["--sample-data", str(REPO / "sample_data"), "--snapshot-id", "snap-regress",
             "--policy", "merge_by_family_v1", "--time-limit", "30"],
            tmp_path,
        )
        golden = (FIXTURES / "sample_data_schedule.csv").read_text(encoding="utf-8")
        current = (tmp_path / "schedule.csv").read_text(encoding="utf-8")
        assert current == golden, "sample_data schedule.csv changed after the precedence-edge surgery"

    def test_cost_ledger_identical(self, tmp_path):
        stdout = _run_mre(
            ["--sample-data", str(REPO / "sample_data"), "--snapshot-id", "snap-regress2",
             "--policy", "merge_by_family_v1", "--time-limit", "30"],
            tmp_path,
        )
        golden = json.loads((FIXTURES / "sample_data_summary.json").read_text(encoding="utf-8"))
        current = _extract_summary(stdout)
        assert current == golden


class TestGauntletReproducesBaseline:
    """'The gauntlet' = raw_data (the real ticketing extract), sliced to the
    documented 173-exclusion window (--horizon-days 2) for a fast, real,
    reproducible regression fixture rather than the full 2864-demand solve."""

    def test_schedule_csv_identical(self, tmp_path):
        stdout = _run_mre(
            ["--raw-data", str(REPO / "raw_data"), "--plant-config", str(REPO / "plant_config.json"),
             "--snapshot-id", "snap-gaunt-regress", "--horizon-days", "2", "--time-limit", "30"],
            tmp_path,
        )
        golden = (FIXTURES / "gauntlet_schedule.csv").read_text(encoding="utf-8")
        current = (tmp_path / "schedule.csv").read_text(encoding="utf-8")
        assert current == golden, "gauntlet schedule.csv changed after the precedence-edge surgery"

    def test_cost_ledger_identical(self, tmp_path):
        stdout = _run_mre(
            ["--raw-data", str(REPO / "raw_data"), "--plant-config", str(REPO / "plant_config.json"),
             "--snapshot-id", "snap-gaunt-regress2", "--horizon-days", "2", "--time-limit", "30"],
            tmp_path,
        )
        golden = json.loads((FIXTURES / "gauntlet_summary.json").read_text(encoding="utf-8"))
        current = _extract_summary(stdout)
        assert current == golden

    def test_still_173_infeasible_subset_exclusions(self, tmp_path):
        """Named regression anchor (docs/05/07 cite this number repeatedly)."""
        stdout = _run_mre(
            ["--raw-data", str(REPO / "raw_data"), "--plant-config", str(REPO / "plant_config.json"),
             "--snapshot-id", "snap-gaunt-regress3", "--horizon-days", "2", "--time-limit", "30"],
            tmp_path,
        )
        assert "173 errors" in stdout

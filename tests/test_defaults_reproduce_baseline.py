"""The defaults-reproduce-baseline gate (docs/05 §3 item 2, §4).

The precedence-edge surgery (docs/05 §4: Operation.predecessors -> first-class
PrecedenceEdge records; dwell dies as a phase, R-Dwell) must not change what
either the sample_data pipeline or "the gauntlet" (raw_data, real ticketing
extract) actually schedules. This is a regression gate, not a promise:
golden fixtures were captured from the pre-surgery code and are compared
byte-for-byte (schedule.csv) and value-for-value (cost ledger) against
post-surgery runs.

Rep 2 (chunking, docs/05 R-C3) reused this same gate as its own acceptance
item 5b: datasets with no resumable ops must solve IDENTICALLY. schedule.csv
gained one new column (chunk_seq) to support chunked operations' multi-row
output — golden fixtures were regenerated once, verified beforehand to be
byte-identical to the pre-Rep-2 fixtures with the chunk_seq column removed
(sample_data and raw_data have zero resumable ops, so chunk_seq is blank on
every row). See the 2026-07-11 docs/04 amendment for the verification.

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

# The sample_data path has no manifest reference_date, so unpinned it falls back
# to datetime.now() and the wall clock silently excludes past-due demands
# (WO-2001 is due 2026-07-13). The golden fixtures were captured as-of the
# 2026-07-09 scenario epoch; pin that so the gate is time-STABLE, not a bomb
# that detonates once the clock passes the sample due dates. See docs/04
# 2026-07-15. Any date before 2026-07-13 reproduces the goldens byte-for-byte.
SAMPLE_REF_DATE = "2026-07-09"


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
             "--policy", "merge_by_family_v1", "--time-limit", "30",
             "--reference-date", SAMPLE_REF_DATE],
            tmp_path,
        )
        golden = (FIXTURES / "sample_data_schedule.csv").read_text(encoding="utf-8")
        current = (tmp_path / "schedule.csv").read_text(encoding="utf-8")
        assert current == golden, "sample_data schedule.csv changed after the precedence-edge surgery"

    def test_cost_ledger_identical(self, tmp_path):
        stdout = _run_mre(
            ["--sample-data", str(REPO / "sample_data"), "--snapshot-id", "snap-regress2",
             "--policy", "merge_by_family_v1", "--time-limit", "30",
             "--reference-date", SAMPLE_REF_DATE],
            tmp_path,
        )
        golden = json.loads((FIXTURES / "sample_data_summary.json").read_text(encoding="utf-8"))
        current = _extract_summary(stdout)
        assert current == golden


# NOTE (Session 4B.2, R-SC1): the gauntlet regression (TestGauntletReproducesBaseline)
# was REMOVED here — the historical ticketing extract (raw_data/) has exited the
# test path entirely. The extract is now demoted to a PROFILE source only
# (tools/extract_pilot_profile.py → datasets/pilot_scale/pilot_profile.json); all
# plant physics is authored deliberately in the pilot_scale synthetic plant. The
# sample_data baseline above remains the deterministic-reproduction anchor.

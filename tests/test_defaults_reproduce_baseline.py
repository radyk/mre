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

===========================================================================
GOLDEN REGENERATION, SESSION 4B.11 (R-PD1) — READ THE ACCOUNTING
===========================================================================

The sample_data goldens were regenerated ONCE in Session 4B.11, for the second
time in this gate's life (the first was Rep 2's chunk_seq column). The session
brief's acceptance criterion said every monolithic golden would stay
BYTE-IDENTICAL, on the premise that no monolithic fixture carries past-due
work. THAT PREMISE IS FALSE: sample_data carries WO-PAST-001 (ScheduleDate
2025-01-15) as seeded defect 3, and R-PD1 clause (1) rules that a past-due
unstarted demand is SCHEDULED rather than excluded. The golden could not
survive the ruling, and saying so is more useful than a criterion quietly
dropped.

Note that `sample_data_v2/DEFECTS.md` has always declared defect 3's expected
disposition as `proceeded_flagged`. The implementation had drifted to
`excluded`; R-PD1 restores what the catalog said.

THE CHANGE IS FULLY ACCOUNTED FOR, and by construction rather than by
inspection. Re-running this exact pipeline against sample_data WITH THE SINGLE
ROW `WO-PAST-001` REMOVED reproduces the PREVIOUS golden BYTE-FOR-BYTE and its
ledger TO THE CENT (total 24,769.00 / production 19,429.00 / setup 4,500.00 /
tardiness 840.00). So every difference between the old golden and the new one
is attributable to one order being admitted, and to nothing else in the
pipeline. Both runs reproduce across repeated invocations under the pinned
determinism above.

What the new golden says:

  total 801,930.00 = production 19,759.00 + setup 4,650.00
                     + tardiness 777,521.00

Tardiness rises from 840 to 777,521 because WO-PAST-001 was due 2025-01-15 and
the reference date is 2026-07-09 — it is 776,681 minutes late, of which
**776,160 are the R-PD1 clause (4) FLOOR**: unavoidable before this plan
existed, and not something any schedule could have prevented. The remaining
521 minutes are what this schedule adds. That ratio is precisely why the
tardiness split exists (contract 1.11): a single fused number here would tell a
planner their schedule caused $777,521 of lateness when it caused $521 of it.
The floor is provably outside the objective — see
tools/spikes/pastdue_4b11/floor_invariance.py.
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


# THE WALL IS A SAFETY CEILING, NOT THE BUDGET (Session 4B.33 Item 2).
#
# This fixture ran at `--time-limit 30` from its creation until 4B.33, and that
# one unpinned WALL limit was the whole of its long-standing flakiness:
# `test_schedule_csv_identical` failed roughly half the time on an IDLE machine
# at HEAD (4B.32 §10a measured pass/FAIL/pass/FAIL on this tree and
# pass/FAIL/pass on a clean detached worktree), while `test_cost_ledger_identical`
# passed six for six. The repo's own hard rule already said why: a wall limit
# makes a solve irreproducible.
#
# MEASURED, per stage, on sample_data with workers=1 / seed=42 / PYTHONHASHSEED=0:
#
#   stage 1 (the COST PROOF)   wall limit 30 s, NO deterministic cap
#                              -> OPTIMAL in 0.81 s / 0.047 deterministic units
#   stage 2 (the earliest-start TIEBREAK, whose placements are what schedule.csv
#            actually contains)
#                              wall limit 30 s AND a 1.953-unit deterministic
#                              budget -> FEASIBLE, 1.9534 units consumed,
#                              14.56 s of wall on a quiet machine
#
# That asymmetry is the signature exactly: stage 1 proves, so the LEDGER never
# moved; stage 2 is where the placement is decided, and its deterministic budget
# needed ~15 s of a 30 s wall — barely 2x of headroom. Whenever the machine ran
# slower than that margin the wall cut stage 2 mid-budget and CP-SAT returned a
# DIFFERENT tied-optimal placement at the SAME cost. The deterministic budget was
# already plumbed here and doing the right thing; the wall was simply overriding
# it.
#
# So the fix is not a new mechanism, it is getting the wall out of the way. Each
# stage is now reproducible for its OWN reason:
#
#   * stage 1 because it PROVES — nothing is truncated, so nothing can drift;
#   * stage 2 because its DETERMINISTIC budget binds, and deterministic ticks
#     truncate at the same node every run by construction.
#
# 600 s is a ceiling, deliberately ~40x the measured 15 s solve and ~4x the worst
# case at the slowest exchange rate this repo has ever measured (77 s per
# deterministic unit, docs/07 §5a.98 — 1.95 units => ~150 s). It exists to stop a
# hung solve wedging the suite, never to bound the search. The subprocess timeout
# sits above it so the CEILING is the outer bound, not the harness.
WALL_CEILING_S = "600"


def _run_mre(args: list[str], out_dir: Path) -> str:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    result = subprocess.run(
        [sys.executable, "-m", "mre", *args, "--out", str(out_dir),
         "--solver-workers", "1", "--solver-seed", "42",
         "--time-limit", WALL_CEILING_S],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=900,
    )
    assert result.returncode == 0, (
        f"pipeline failed (exit {result.returncode}):\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    # THE REPRODUCIBILITY PREMISE, ASSERTED RATHER THAN ASSUMED. Stage 1's half
    # of the guarantee above is that it PROVES; the reported status is stage 1's
    # (4B.8 CU3). If this instance ever stops proving, the wall becomes
    # load-bearing again and these goldens quietly go back to being a property of
    # the machine. That must fail loudly here rather than resurface as a flake.
    assert "status=OPTIMAL" in result.stdout, (
        "the cost proof did not prove; with stage 1 truncated the wall ceiling "
        "becomes load-bearing and this golden is no longer reproducible.\n"
        f"STDOUT:\n{result.stdout}"
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
             "--policy", "merge_by_family_v1",
             "--reference-date", SAMPLE_REF_DATE],
            tmp_path,
        )
        golden = (FIXTURES / "sample_data_schedule.csv").read_text(encoding="utf-8")
        current = (tmp_path / "schedule.csv").read_text(encoding="utf-8")
        assert current == golden, "sample_data schedule.csv changed after the precedence-edge surgery"

    def test_cost_ledger_identical(self, tmp_path):
        stdout = _run_mre(
            ["--sample-data", str(REPO / "sample_data"), "--snapshot-id", "snap-regress2",
             "--policy", "merge_by_family_v1",
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

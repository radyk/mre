"""Every committed dataset under ``datasets/`` still passes the CURRENT gate.

Errand session, CU4. A hand-authored dataset is written against the gate of its
day and then never re-run: the gate keeps growing rules, and the dataset drifts
out of conformance with its own gate silently — discovered, if ever, by a founder
whose demo submission comes back REJECTED. This is the standing guard against
that. It is a CONFORMANCE test, not a golden: it pins ``grade != REJECTED``, not
which grade, so a dataset is free to move ACCEPTED <-> CONDITIONAL as quality
rules land without a test edit.

The classification is structural, not an allowlist: a directory holding
``manifest.json`` is a submission and must pass; one without it must not look
like a submission either (no IDS CSVs), which is what keeps a genuinely broken
submission from being skipped for the very reason it is broken.
``datasets/pilot_scale`` is the non-submission case — it holds the calibration
profile the pilot_scale GENERATOR SCENARIO is sized against, not a submission
(see the Errand close-out, CU2a).

Marked slow: each dataset runs the full rule registry over its tables.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.modules.conformance import REQUIRED_FILES, ConformanceGate
from mre.reporter import Reporter

DATASETS = Path(__file__).resolve().parent.parent / "datasets"

# The CSVs that make a directory look like an IDS submission attempt.
_IDS_CSVS = {f for f in REQUIRED_FILES if f.endswith(".csv")}


def _dataset_dirs() -> list[Path]:
    if not DATASETS.is_dir():
        return []
    return sorted(p for p in DATASETS.iterdir() if p.is_dir())


def _submission_dirs() -> list[Path]:
    return [p for p in _dataset_dirs() if (p / "manifest.json").exists()]


def _run_gate(submission_dir: Path, tmp_path: Path):
    reporter = Reporter.begin(
        module=ModuleCode.M0, purpose="committed-dataset conformance guard",
        config={"submission_dir": str(submission_dir)}, trigger="test",
        snapshot_id="pre-adapter", sink_dir=tmp_path / "runs",
    )
    result = ConformanceGate().run(submission_dir, reporter)
    reporter.end(RunStatus.SUCCESS if result.go else RunStatus.PARTIAL)
    return result


def test_there_is_at_least_one_committed_submission_dataset():
    """The guard must actually be guarding something — an empty parametrization
    is a green test that proves nothing."""
    assert _submission_dirs(), (
        f"no committed submission dataset found under {DATASETS} — either the "
        "datasets moved or this guard is now vacuous")


@pytest.mark.slow
@pytest.mark.parametrize("dataset", _submission_dirs(), ids=lambda p: p.name)
def test_committed_dataset_passes_current_gate(dataset: Path, tmp_path: Path):
    result = _run_gate(dataset, tmp_path)
    assert result.grade != "REJECTED", (
        f"committed dataset {dataset.name} no longer passes the current gate:\n  "
        + "\n  ".join(result.certificate["deficiencies"]))
    assert result.go is True


@pytest.mark.parametrize(
    "dataset",
    [p for p in _dataset_dirs() if not (p / "manifest.json").exists()],
    ids=lambda p: p.name)
def test_non_submission_dataset_does_not_look_like_one(dataset: Path):
    """A directory under datasets/ with no manifest is exempt from the gate only
    if it is plainly not a submission. A half-submission — IDS CSVs but no
    manifest — must not slip through the exemption."""
    present = {p.name for p in dataset.iterdir() if p.is_file()} & _IDS_CSVS
    assert not present, (
        f"{dataset.name} has IDS tables {sorted(present)} but no manifest.json — "
        "it is a broken submission, not a non-submission, and would be skipped "
        "by the conformance guard above")

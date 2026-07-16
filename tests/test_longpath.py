"""Session 4.0d — the long-path (``\\\\?\\``) filesystem seam.

The accept failure (Sessions 4.0c → 4.0d) was a snapshot path crossing Windows
MAX_PATH (260) and failing the derive/copy with ``FileNotFoundError [WinError 3]``.
``mre.modules.longpath`` routes the snapshot/run store's syscalls through the
extended-length namespace so MAX_PATH stops applying. These tests exercise the seam
directly, including a SnapshotStore round-trip under a prefix long enough that a
NAIVE path would fail — the negative control proves the limit is real, so the
passing round-trip proves the seam defeats it.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from mre.modules import longpath
from mre.modules.snapshot_store import SnapshotStore

_ON_WINDOWS = os.name == "nt"


# ---------------------------------------------------------------------------
# extended() — the prefix transform
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _ON_WINDOWS, reason="\\\\?\\ prefix is Windows-only")
class TestExtendedPrefixWindows:
    def test_absolute_path_gets_prefix(self):
        ext = longpath.extended("C:\\Users\\x\\_data\\runs\\r\\snapshots\\s")
        assert ext.startswith("\\\\?\\C:\\")

    def test_prefix_is_idempotent(self):
        once = longpath.extended("C:\\a\\b")
        assert longpath.extended(once) == once

    def test_unc_path_uses_unc_form(self):
        ext = longpath.extended("\\\\server\\share\\deep")
        assert ext.startswith("\\\\?\\UNC\\server\\share")


@pytest.mark.skipif(_ON_WINDOWS, reason="off-Windows pass-through")
def test_non_windows_is_passthrough():
    assert longpath.extended("/tmp/a/b") == "/tmp/a/b"


# ---------------------------------------------------------------------------
# The real defect: a snapshot path past MAX_PATH must round-trip through the store
# ---------------------------------------------------------------------------

def _padded_root(base: Path, target_len: int) -> Path:
    root = base
    while len(str(root)) < target_len:
        root = root / "padseg"
    longpath.makedirs(root)
    return root


def test_naive_write_fails_past_max_path_but_seam_succeeds(tmp_path):
    """Negative control + fix in one: at a >260-char total path a naive write
    fails (the limit is real), the seam's write succeeds (the limit is defeated).
    Meaningful only on Windows; off-Windows there is no such limit to defeat."""
    root = _padded_root(tmp_path, 200)
    deep = root / "snapshots" / ("snap-edit-" + "d" * 12) / "entities_serviceoutcome.jsonl"
    assert len(str(deep)) > 260

    if _ON_WINDOWS:
        with pytest.raises(OSError):
            os.makedirs(str(deep.parent), exist_ok=True)
            with open(str(deep), "w", encoding="utf-8") as f:  # naive: no \\?\
                f.write("x")

    # The seam: makedirs + write + read at the same length, no error.
    longpath.makedirs(deep.parent)
    longpath.write_text(deep, "payload")
    assert longpath.exists(deep)
    assert longpath.read_text(deep) == "payload"


def test_snapshot_store_round_trips_past_max_path(tmp_path):
    """A SnapshotStore write → derive → read at a prefix long enough that the
    child snapshot's full path exceeds MAX_PATH. This is the exact operation that
    failed the live accept (``derive`` copies ``entities_*.jsonl``); through the
    seam it round-trips."""
    from mre.contracts import (
        Resource, ProvenanceSidecar, SynthesizedProvenance, ProvenanceClass,
    )

    root = _padded_root(tmp_path, 220)
    store = SnapshotStore(root / "snapshots")
    snap = "snap-base-longpath"

    def _prov(attr):
        return ProvenanceSidecar(
            entity_id="R1", attribute_name=attr, snapshot_id=snap,
            provenance_class=ProvenanceClass.SYNTHESIZED,
            payload=SynthesizedProvenance(generator_id="longpath_test"),
        )

    writer = store.begin_snapshot(snap)
    res = Resource(id="R1", snapshot_id=snap, name="Cutter", resource_type="machine")
    writer.write_entity(res, [_prov(a) for a in type(res).model_fields
                              if a not in {"id", "snapshot_id", "external_refs"}])
    writer.finalize()

    # derive a child (the failing op in the live accept) at the deep prefix
    store.derive_scenario_snapshot("snap-base-longpath", "snap-edit-deadbeef00ab",
                                   ["resource"])
    child_file = (root / "snapshots" / "snap-edit-deadbeef00ab"
                  / "entities_resource.jsonl")
    assert len(str(child_file)) > 260, len(str(child_file))
    assert longpath.exists(child_file)

    reader = store.load_snapshot("snap-edit-deadbeef00ab")
    got = list(reader.iter_entities("resource"))
    assert got and got[0]["id"] == "R1"
    assert "snap-edit-deadbeef00ab" in store.list_snapshots()


# ---------------------------------------------------------------------------
# path_budget() — the boot / /health tripwire
# ---------------------------------------------------------------------------

def test_path_budget_reports_worst_case_for_a_normal_root():
    # Daryn's actual data root (~58 chars) is comfortably under the limit: the
    # opaque snapshot ids keep the worst case well within 260.
    b = longpath.path_budget("C:\\Users\\radke\\OneDrive\\Documents\\PythonProjects"
                             "\\mre\\_data" if _ON_WINDOWS else "/srv/_data")
    assert b["worst_case_path_len"] > b["data_root_len"]
    assert b["status"] == "ok"
    if _ON_WINDOWS:
        assert b["long_path_mitigation"] is True
        assert b["worst_case_path_len"] < longpath.CLASSIC_MAX_PATH


def test_path_budget_flags_a_pathological_root_at_risk(monkeypatch):
    """A data root deep enough that even a bounded snapshot name would blow the
    classic limit is flagged ``at_risk`` — the loud boot/health tripwire — even
    though the long-path seam is mitigating it. Never discovered at accept time."""
    monkeypatch.setattr(longpath, "_ON_WINDOWS", True)
    b = longpath.path_budget("C:\\" + "x" * 240)
    assert b["exceeds_classic_limit"] is True
    assert b["status"] == "at_risk"
    assert b["long_path_mitigation"] is True  # the seam still covers it today

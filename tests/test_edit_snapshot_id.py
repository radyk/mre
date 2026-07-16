"""Session 4.0c — the accepted-edit child snapshot id must stay bounded.

The live "silent accept" (schedule ea1a42f0) was an accept aborting with
``FileNotFoundError [WinError 3]`` because chained edits grew the snapshot
directory name unboundedly (``<base>--edit-h1--edit-h2--…``) until the on-disk
path crossed the Windows MAX_PATH (260) limit — then the cockpit returned the
bar home with no error. ``_edit_snapshot_id`` bounds that id so no chain ever
reaches that depth. These are pure-string unit tests (no solve) — fast suite.
"""
from __future__ import annotations

from mre.modules.planner_edit import (
    _MAX_EDIT_SNAP_ID_LEN, _edit_snapshot_id, _short_pin_hash,
)


def test_shallow_chain_keeps_readable_lineage():
    # A first edit off a root stays in the readable "<base>--edit-<hash>" form.
    child = _edit_snapshot_id("snap-be998b25", "abcd1234")
    assert child == "snap-be998b25--edit-abcd1234"
    assert len(child) <= _MAX_EDIT_SNAP_ID_LEN


def test_deep_chain_stays_bounded():
    # Simulate the live ea1a42f0 lineage: 7 chained edits appended by hand — the
    # naive scheme is already 118 chars; one more edit would blow MAX_PATH.
    naive = "snap-be998b25" + "--edit-deadbeef" * 7
    assert len(naive) > _MAX_EDIT_SNAP_ID_LEN  # the pre-fix growth
    bounded = _edit_snapshot_id(naive, "3e7811a6")
    assert len(bounded) <= _MAX_EDIT_SNAP_ID_LEN, bounded
    # The visible root and the fresh edit hash survive the collapse.
    assert bounded.startswith("snap-be998b25--chain-")
    assert bounded.endswith("--edit-3e7811a6")


def test_bound_holds_across_an_arbitrarily_long_chain():
    # Chain accept-on-accept 50 deep: every derived id stays under the cap, so no
    # snapshot directory name can ever cross the filesystem limit.
    snap = "snap-0badf00d"
    for i in range(50):
        snap = _edit_snapshot_id(snap, _short_pin_hash("op", "res", str(i)))
        assert len(snap) <= _MAX_EDIT_SNAP_ID_LEN, (i, snap)


def test_collapse_is_deterministic_and_distinct_per_parent():
    # Same (parent, hash) → same id (idempotent re-accept); different parents that
    # both need collapsing → different ids (no lineage collision).
    long_a = "snap-aaaa1111" + "--edit-11112222" * 7
    long_b = "snap-aaaa1111" + "--edit-33334444" * 7
    assert _edit_snapshot_id(long_a, "cafe0001") == _edit_snapshot_id(long_a, "cafe0001")
    assert _edit_snapshot_id(long_a, "cafe0001") != _edit_snapshot_id(long_b, "cafe0001")

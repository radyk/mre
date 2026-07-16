"""Sessions 4.0c → 4.0d — the accepted-edit child snapshot id must stay a SHORT,
FIXED-WIDTH directory name.

The live "silent accept" (schedule ea1a42f0, 4.0c) was an accept aborting with
``FileNotFoundError [WinError 3]`` because chained edits grew the snapshot
directory name unboundedly (``<base>--edit-h1--edit-h2--…``) until the on-disk
path crossed Windows MAX_PATH (260). 4.0c capped that id at 90 chars — but the cap
was validated in a SHORT temp prefix, and at Daryn's real ~130-char data-root
prefix a near-cap id STILL crossed 260 on a shallow chain (4.0d).

4.0d makes the id a fixed-width opaque name that embeds NO lineage (the parent
chain lives in the registry's parent_schedule_id), so the snapshot-directory name
is tiny and bounded however deep the chain grows. These are pure-string unit tests
(no solve) — fast suite.
"""
from __future__ import annotations

from mre.modules.planner_edit import (
    _EDIT_SNAP_PREFIX, _MAX_EDIT_SNAP_ID_LEN, _edit_snapshot_id, _short_pin_hash,
)


def test_edit_id_is_short_fixed_width_and_opaque():
    child = _edit_snapshot_id("snap-be998b25", "abcd1234")
    assert child.startswith(_EDIT_SNAP_PREFIX)
    assert len(child) <= _MAX_EDIT_SNAP_ID_LEN
    # It embeds NO lineage — the parent id does not appear in the child name.
    assert "snap-be998b25" not in child
    assert "--edit-" not in child and "--chain-" not in child


def test_bound_holds_across_an_arbitrarily_long_chain():
    # Chain accept-on-accept 50 deep: the id is fixed-width, so no snapshot
    # directory name can ever approach a filesystem path limit — the whole point
    # of 4.0d. Every derived id is the SAME length as a depth-1 id.
    first = _edit_snapshot_id("snap-0badf00d", _short_pin_hash("op", "res", "0"))
    snap = "snap-0badf00d"
    for i in range(50):
        snap = _edit_snapshot_id(snap, _short_pin_hash("op", "res", str(i)))
        assert len(snap) == len(first) <= _MAX_EDIT_SNAP_ID_LEN, (i, snap)


def test_id_is_deterministic_and_distinct_per_parent():
    # Same (parent, hash) → same id (idempotent re-accept); different parents →
    # different ids (no lineage collision); different hash off the same parent →
    # different ids.
    assert _edit_snapshot_id("snap-aaaa1111", "cafe0001") == \
        _edit_snapshot_id("snap-aaaa1111", "cafe0001")
    assert _edit_snapshot_id("snap-aaaa1111", "cafe0001") != \
        _edit_snapshot_id("snap-bbbb2222", "cafe0001")
    assert _edit_snapshot_id("snap-aaaa1111", "cafe0001") != \
        _edit_snapshot_id("snap-aaaa1111", "cafe0002")


def test_realistic_prefix_stays_under_max_path():
    """The 4.0c blind spot, made a red test: at Daryn's real ~130-char data-root
    prefix, the full snapshot path with a 4.0d edit id must stay under MAX_PATH —
    the property the 4.0c cap (validated in a short temp prefix) silently lacked."""
    prefix = "C:\\Users\\radke\\OneDrive\\Documents\\PythonProjects\\mre\\_data" \
             "\\runs\\" + "u" * 36 + "\\snapshots"
    assert len(prefix) >= 100  # a realistic deep prefix
    edit_id = _edit_snapshot_id("snap-deadbeef", "abcd1234")
    full = f"{prefix}\\{edit_id}\\entities_serviceoutcome.jsonl"
    assert len(full) < 260, (len(full), full)

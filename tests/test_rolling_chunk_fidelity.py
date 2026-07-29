"""Session 4B.13 Item 0 — THE PAUSES ARE REAL, AND THE BOARD MUST SHOW THEM.

The specimen: on the pinned exam world (rolling-1b170235-64d) ORD-000011's
CUT-01 operation rendered as ONE CONTINUOUS BAR from Thu Jan 8 14:36 to Mon
Jan 12 15:37, straight through a weekend CUT-01 is shut. Three readings were
possible -- a render merge, a physics violation, or no closure to violate.

It was the FIRST. The canonical Assignment entity carries three run windows
(14:36-19:00, 07:00-19:00, 07:00-15:37 = 1501 working minutes against a
run_duration of P1DT1H), the solver blocks every calendar gap and no-overlaps
against it, and the cockpit has drawn one piece per chunk since CU5. Only
``assemble_rolling_document`` collapsed them: it built a single Chunk from the
placement's overall span, because RollingView placements carried no chunk data
to build from. The monolithic path never had the defect (``_chunks`` reads
``phase_windows.run``).

Why it earns a guard rather than a one-line fix: a merged bar hides the pauses
of EVERY chunked operation on every rolling board, so a genuine physics
violation -- reading (b), the one that would have halted the session -- would
have looked exactly the same on screen. The second test below is the one that
can tell them apart, and it is written to fail on (b).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from mre.modules.schedule_assembler import _rolling_chunks

REF = datetime(2026, 1, 5, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# fast — the mapping itself
# ---------------------------------------------------------------------------

def test_unchunked_placement_is_one_chunk_unchanged():
    """A non-resumable placement has no ``chunks`` key and must yield exactly
    the single chunk it always did -- the byte-identical clause, so an
    unchunked rolling document is unmoved by this change."""
    pl = {"resource": "r1", "start": "2026-01-05T07:00:00+00:00",
          "end": "2026-01-05T11:00:00+00:00"}
    chunks = _rolling_chunks(pl)
    assert len(chunks) == 1
    assert chunks[0].chunk_seq == 1
    assert chunks[0].start == datetime(2026, 1, 5, 7, tzinfo=timezone.utc)
    assert chunks[0].end == datetime(2026, 1, 5, 11, tzinfo=timezone.utc)
    assert chunks[0].working_min == 240
    # an EMPTY chunk list is the same case, not a crash
    assert len(_rolling_chunks({**pl, "chunks": []})) == 1


def test_resumable_placement_fans_out_and_working_min_excludes_the_pauses():
    """The ORD-000011 shape, to the minute: three windows, 1501 working minutes,
    a 5821-minute span. The pre-fix code produced ONE chunk of 5821."""
    pl = {
        "resource": "CUT-01",
        "start": "2026-01-08T14:36:00+00:00",
        "end": "2026-01-12T15:37:00+00:00",
        "chunks": [
            {"start": "2026-01-08T14:36:00+00:00", "end": "2026-01-08T19:00:00+00:00"},
            {"start": "2026-01-09T07:00:00+00:00", "end": "2026-01-09T19:00:00+00:00"},
            {"start": "2026-01-12T07:00:00+00:00", "end": "2026-01-12T15:37:00+00:00"},
        ],
    }
    chunks = _rolling_chunks(pl)
    assert len(chunks) == 3, "the pauses were swallowed -- the merge is back"
    assert [c.chunk_seq for c in chunks] == [1, 2, 3]
    assert [c.working_min for c in chunks] == [264, 720, 517]
    # THE POINT: working minutes are the sum of the pieces, never the span.
    assert sum(c.working_min for c in chunks) == 1501
    span = (chunks[-1].end - chunks[0].start).total_seconds() // 60
    assert span == 5821
    assert sum(c.working_min for c in chunks) < span, (
        "a chunked op whose working minutes equal its span has had its pauses "
        "merged away -- this is the defect, restated as an invariant")


def test_chunks_are_ordered_regardless_of_input_order():
    pl = {"resource": "r1", "start": "2026-01-08T14:36:00+00:00",
          "end": "2026-01-12T15:37:00+00:00",
          "chunks": [
              {"start": "2026-01-12T07:00:00+00:00", "end": "2026-01-12T15:37:00+00:00"},
              {"start": "2026-01-08T14:36:00+00:00", "end": "2026-01-08T19:00:00+00:00"},
          ]}
    chunks = _rolling_chunks(pl)
    assert [c.start.day for c in chunks] == [8, 12]
    assert [c.chunk_seq for c in chunks] == [1, 2]


# ---------------------------------------------------------------------------
# slow — THE PHYSICS GUARD. This is the test that separates (a) from (b).
# ---------------------------------------------------------------------------

# Stated, not inherited: 4B.8 CU2 renamed build_rolling_view's per-stage
# ``det_time`` to a two-stage ``det_total`` and made every caller declare its
# own budget. This file declares its own rather than reusing a number whose
# historical meaning was different.
DET_TOTAL = 4.0


@pytest.fixture(scope="module")
def rolling(tmp_path_factory):
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import prepare_plant, build_rolling_view
    d = tmp_path_factory.mktemp("chunkfid")
    generate(d / "sub", scenario="pilot_scale", orders=40, seed=1)
    plant = prepare_plant(d / "sub", d / "prep", reference_date=REF)
    view = build_rolling_view(plant, window_days=14, frozen_days=3, gravity=True,
                              deterministic=True, seed=42,
                              member_time_limit_s=120.0, det_total=DET_TOTAL)
    imap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
    return plant, view, imap


@pytest.mark.slow
def test_no_bar_is_drawn_through_a_closure(rolling):
    """EVERY chunk of every bar lies inside OPEN calendar time on the machine it
    is drawn on. This is the physics claim the board makes to a stranger.

    Pre-fix this failed on exactly two chunks (ORD-000011 and ORD-000003, both
    CUT-01, each spanning 4320 minutes of nights + a weekend) -- and those two
    failures were an artifact of the merge, not of the placement. Post-fix it
    must pass with nothing excused. A real reading-(b) violation fails it too,
    which is the whole reason it exists.
    """
    from mre.modules.schedule_assembler import assemble_rolling_document
    plant, view, imap = rolling
    doc = assemble_rolling_document(plant=plant, view=view,
                                    schedule_id="sched-chunkfid", run_id="run-chunkfid",
                                    identity_map=imap)

    open_by_res: dict[str, list[tuple[datetime, datetime]]] = {}
    for r in doc.resources:
        open_by_res[r.resource_id] = [
            (w.start, w.end) for w in r.calendar_windows if w.kind == "regular"
        ]

    offences: list[str] = []
    for a in doc.assignments:
        windows = open_by_res.get(a.resource_id, [])
        for c in a.chunks:
            covered = 0.0
            for ws, we in windows:
                lo, hi = max(c.start, ws), min(c.end, we)
                if hi > lo:
                    covered += (hi - lo).total_seconds() / 60.0
            elapsed = (c.end - c.start).total_seconds() / 60.0
            if elapsed - covered > 1.0:      # 1 min slack for boundary rounding
                offences.append(
                    f"{'+'.join(a.work_orders) or a.operation_ref} on "
                    f"{a.external_name} chunk {c.chunk_seq} "
                    f"{c.start.isoformat()}->{c.end.isoformat()}: "
                    f"{elapsed - covered:.0f} min outside open time")

    assert not offences, (
        "work is drawn outside the machine's open calendar:\n  "
        + "\n  ".join(offences[:10]))


@pytest.mark.slow
def test_a_chunked_op_reaches_the_document_as_more_than_one_chunk(rolling):
    """The negative control for the guard above: if NOTHING on this board is
    chunked, the closure test passes vacuously and proves nothing. pilot_scale
    at 40 orders has resumable ops that straddle a weekend -- assert at least
    one survives into the document with its pauses intact."""
    from mre.modules.schedule_assembler import assemble_rolling_document
    plant, view, imap = rolling
    doc = assemble_rolling_document(plant=plant, view=view,
                                    schedule_id="sched-chunkfid2", run_id="run-chunkfid2",
                                    identity_map=imap)
    multi = [a for a in doc.assignments if len(a.chunks) > 1]
    assert multi, (
        "no assignment reached the document with more than one chunk -- either "
        "the world stopped producing resumable work (this guard is now vacuous) "
        "or the merge is back")
    for a in multi:
        span = (a.chunks[-1].end - a.chunks[0].start).total_seconds() // 60
        assert sum(c.working_min for c in a.chunks) < span

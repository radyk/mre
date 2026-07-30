"""THE MERGED-SPAN CLASS GUARD — Session 4B.20, docs/04 2026-07-30.

THE INVARIANT UNDER TEST:

  WORKING TIME AND ELAPSED SPAN ARE DIFFERENT QUANTITIES AND ARE NEVER
  INTERCHANGEABLE. Any surface that reports one names WHICH; a surface that
  reports a duration without saying which is a defect.

WHY A CLASS GUARD AND NOT A FOURTH PATCH. This defect has been "fixed" three
times and reappeared each time at a seam nobody had looked at:

    4B.13  assemble_rolling_document collapsed chunks into one placement
    4B.13  the cockpit board (correct already; it was being starved)
    4B.14  Explainer._load_enriched_assignments read phase_windows["run"][0]
    4B.17  the synthesis toolbox -- duration_minutes / busy_minutes = 5821

Each fix closed one site. None made a NEW site fail. This does.

===========================================================================
THE MECHANISM, STATED PLAINLY -- AND ITS LIMIT
===========================================================================

Two mechanisms, because neither alone closes the class:

  (1) THE NAMING REGISTER (test_every_duration_field_is_classified).
      Every tool on the closed synthesis surface is CALLED, and every numeric
      field in every row and summary whose key looks like a time quantity is
      matched against an authored register that declares which quantity it is
      -- WORKING, ELAPSED, CAPACITY or NEITHER. An unregistered field is a
      failure. This is the class-level half: a new duration field on the
      toolbox is red on the day it is written, whatever it is called, and the
      author has to state which quantity it carries to make it green.

  (2) THE VALUE PROPERTY (test_no_reported_duration_exceeds_open_capacity and
      test_working_time_equals_the_sum_of_the_run_windows).
      Registering a field as WORKING does not make it working time. So every
      field registered WORKING is asserted to equal the sum of the run
      windows, and no reported duration may exceed the resource's open
      capacity over the same interval -- the 3.9x tell that found the defect
      (busy_minutes 5821 against 1501 minutes of open time).

WHAT THIS GUARD CANNOT DO. It is scoped to the SYNTHESIS TOOLBOX row and
summary surface. It discovers fields by calling the tools, so it cannot be
evaded by adding a field the test did not think to look for -- but equally it
sees NOTHING outside that surface. A span-as-duration in a renderer, in a
contracted route's key facts, in the schedule document, or in the cockpit's
JavaScript is invisible to it. The census in docs/closeouts/4B.20.md
classified those sites by hand; this guard holds the one surface where the
class was last found and where new tools are most likely to be added. That is
a narrower claim than "a fifth seam is impossible", and it is the true one.
Two known-correct sites it does not watch are named in the close-out:
``rolling_horizon.compute_manned_idle_metrics`` (correct by intersection) and
``board.js`` occupancy (fixed to per-chunk in this session, guarded only by
the cockpit's own fixtures).

===========================================================================
THE PREMISE
===========================================================================

test_the_fixture_actually_contains_a_paused_operation runs FIRST and asserts
the fixture contains a genuinely chunked operation whose span exceeds its work.
Without it every assertion below passes vacuously over contiguous work, and
this file becomes 4B.18's ``test_load_populates_all_evidence`` again -- a test
that watched exactly the quantity its defect changed and passed for its whole
life because its fixture could not produce the condition.

The specimen is the pinned world's own ORD-000011 op10 on CUT-01
(rolling-c362baa4-1b0), transcribed as plain data on the discipline
``test_attribute_lookup`` uses: three pieces, 1501 working minutes, a 5821
minute span, 4320 of which are the nights of Jan 8-9 and the weekend of
Jan 10-11 when CUT-01 is shut. Every figure below is measured from that run's
persisted document, never re-solved (R-AI4).
"""
from __future__ import annotations

import re
from datetime import datetime

import pytest

from mre.contracts.synthesis import ToolName
from mre.modules.evidence_tools import EvidenceToolbox


# ---------------------------------------------------------------------------
# The specimen, transcribed from rolling-c362baa4-1b0
# ---------------------------------------------------------------------------

MACHINE = "CUT-01"

#: ORD-000011 op10 exactly as the pinned document records it: three run
#: windows, 264 + 720 + 517 = 1501 working minutes, spanning 5821.
CHUNKS = [
    {"chunk_seq": 1, "start": "2026-01-08T14:36:00Z",
     "end": "2026-01-08T19:00:00Z", "working_min": 264},
    {"chunk_seq": 2, "start": "2026-01-09T07:00:00Z",
     "end": "2026-01-09T19:00:00Z", "working_min": 720},
    {"chunk_seq": 3, "start": "2026-01-12T07:00:00Z",
     "end": "2026-01-12T15:37:00Z", "working_min": 517},
]
#: A contiguous operation on the same machine, so the guard proves it does not
#: merely fire on everything.
CONTIGUOUS = [
    {"chunk_seq": 1, "start": "2026-01-13T07:00:00Z",
     "end": "2026-01-13T09:00:00Z", "working_min": 120},
]
#: CUT-01's real calendar across the specimen: 07:00-19:00 on working days,
#: nothing at all on Sat Jan 10 / Sun Jan 11.
#: NAIVE, because ``explainer._to_dt`` — the one parser both the placement
#: reader and the calendar reader go through — drops the zone.
OPEN_WINDOWS = [
    (datetime(2026, 1, d, 7), datetime(2026, 1, d, 19))
    for d in (8, 9, 12, 13)
]

WORKING_MIN = 1501.0
SPAN_MIN = 5821.0
PAUSED_MIN = 4320.0


def _row(order, chunks):
    """An enriched-assignment row shaped exactly as
    ``Explainer._load_enriched_assignments`` produces one."""
    return {
        "assignment_id": f"asg-{order}", "operation_ref": f"op-{order}",
        "workpackage_ref": f"wp-{order}", "op_seq": 10, "setup_family": "",
        "machine": MACHINE, "resource_id": "res-cut01",
        "start": chunks[0]["start"], "end": chunks[-1]["end"],
        "chunks": chunks,
        "run_min": float(sum(c["working_min"] for c in chunks)),
        "span_min": (datetime.fromisoformat(chunks[-1]["end"].replace("Z", "+00:00"))
                     - datetime.fromisoformat(chunks[0]["start"].replace("Z", "+00:00"))
                     ).total_seconds() / 60.0,
        "splittable": len(chunks) > 1, "min_chunk": None,
        "setup_duration": None, "work_orders": [order],
        "demand_ids": [], "customer_ids": [], "service_outcomes": {},
    }


ROWS = [_row("ORD-000011", CHUNKS), _row("ORD-000099", CONTIGUOUS)]


class _StubExplainer:
    """The narrowest thing the toolbox reads: enriched rows, an order/machine
    resolver, and the open windows. Deliberately not a full Explainer -- this
    guard is about arithmetic over rows, and a real snapshot would make the
    premise depend on a run directory that may not exist."""

    _index = None
    _reader = None

    def _load_enriched_assignments(self):
        return ROWS

    def _open_windows(self, machine_name):
        return list(OPEN_WINDOWS) if machine_name.upper() == MACHINE else []

    def resolve_order_value(self, v):
        return v

    def resolve_machine_value(self, v):
        return v

    def _order_rows(self, ref):
        return [r for r in ROWS if ref in r["work_orders"]]


@pytest.fixture()
def box():
    return EvidenceToolbox(_StubExplainer())


# ---------------------------------------------------------------------------
# The register: every time-quantity field the toolbox may report, classified
# ---------------------------------------------------------------------------

WORKING = "working"        # sums the run windows, and nothing else
ELAPSED = "elapsed"        # end minus start; the span is itself the subject
CAPACITY = "capacity"      # a calendar quantity, not work
NEITHER = "neither"        # a count, a ratio, or an id that merely reads timey

#: THE AUTHORED REGISTER. A field is added here by a human who has decided
#: which quantity it carries. Adding a row is the point of the guard, not a
#: chore to route around: the decision is the deliverable.
DURATION_FIELD_REGISTER: dict[str, str] = {
    "working_minutes": WORKING,
    "elapsed_span_minutes": ELAPSED,
    "paused_minutes": ELAPSED,          # span minus work: an elapsed remainder
    "gap_before_minutes": ELAPSED,      # wall-clock between two operations
    "idle_open_minutes_before": CAPACITY,
    "open_capacity_minutes": CAPACITY,
    "utilization_pct": NEITHER,         # a ratio of the two, dimensionless
    "pieces": NEITHER,
    # A COUNT OF SPANS, NOT A SPAN. Caught by this guard on its first green
    # run, which is the behaviour being bought: "spans" reads as a duration to
    # the same regex a future "busy_span_minutes" would, and the register is
    # where somebody has to look at it and decide.
    "spans": NEITHER,
    "lateness_minutes": ELAPSED,        # a due-date difference IS wall-clock
    "tardiness_minutes": ELAPSED,
    "minutes_late": ELAPSED,
}

#: What makes a key look like a time quantity at all. Deliberately wider than
#: the register: a key matching this and absent from the register is the
#: failure the guard exists to produce.
TIMEY_KEY = re.compile(
    r"(minute|hour|second|duration|elapsed|span|busy|idle|occup|util|load|"
    r"gap|capacity|working)", re.I)

#: Keys that are timey by spelling but are NOT numbers this guard can classify
#: -- timestamps and free text. Excluded by TYPE below, not by name; this list
#: exists only to document that the exclusion is deliberate.
_NON_NUMERIC_NOTE = "start/end/note/record_ids are excluded by type, not by name"


#: The tools that report a time quantity over placements, with arguments that
#: reach the specimen. ``ToolName`` is a ``(str, Enum)`` whose ``str()`` is the
#: repr, so the toolbox is called with ``.value`` — passing the member yields
#: "no such tool" and an EMPTY result, which is how the first run of this file
#: got five green assertions over nothing.
_CALLS = [
    (ToolName.PLACEMENTS_FOR_ORDER, {"order": "ORD-000011"}),
    (ToolName.PLACEMENTS_FOR_MACHINE, {"machine": MACHINE}),
    (ToolName.PLACEMENTS_IN_WINDOW, {"start": "2026-01-05T00:00:00Z",
                                     "end": "2026-01-20T00:00:00Z"}),
    (ToolName.MACHINE_OCCUPANCY, {"machine": MACHINE}),
]


def _all_tool_payloads(box):
    """Call every tool that reports over placements and yield
    (tool, where, key, value) for each numeric leaf.

    RAISES IF A CALL RETURNS NOTHING. Every property in this file is a
    universal over what this generator yields, so an empty generator makes all
    of them pass. That is not a hypothetical: the first run of this file
    passed exactly that way. A guard whose fixture cannot produce the
    condition is the failure mode 4B.18 named, and it applies to the guard's
    own plumbing as much as to its data."""
    seen_rows = 0
    for name, args in _CALLS:
        res = box.call(name.value, dict(args))
        assert res.ok, f"{name.value} did not run: {res.note}"
        assert res.rows, f"{name.value} returned no rows over the specimen"
        seen_rows += len(res.rows)
        for i, row in enumerate(res.rows):
            for k, v in row.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    yield name, f"row[{i}]", k, float(v)
        for k, v in (res.summary or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                yield name, "summary", k, float(v)
    assert seen_rows >= len(_CALLS), "every tool must reach the specimen"


def test_the_payload_generator_is_not_vacuous(box):
    """The guard's own plumbing, guarded. If this file ever again asserts over
    an empty set, this is the test that says so."""
    payloads = list(_all_tool_payloads(box))
    keys = {k for _t, _w, k, _v in payloads}
    assert len(payloads) > 20, f"only {len(payloads)} numeric leaves discovered"
    assert {"working_minutes", "elapsed_span_minutes", "pieces"} <= keys


# ---------------------------------------------------------------------------
# 0. THE PREMISE
# ---------------------------------------------------------------------------

def test_the_fixture_actually_contains_a_paused_operation():
    """WITHOUT THIS EVERY ASSERTION BELOW IS VACUOUS.

    The defect only exists on an operation whose span exceeds its work. A
    fixture of contiguous placements would satisfy every property in this file
    while the product reported spans as durations, which is precisely how
    4B.18's round-trip test passed for its whole life."""
    work = sum(c["working_min"] for c in CHUNKS)
    span = (datetime.fromisoformat(CHUNKS[-1]["end"].replace("Z", "+00:00"))
            - datetime.fromisoformat(CHUNKS[0]["start"].replace("Z", "+00:00"))
            ).total_seconds() / 60.0
    assert len(CHUNKS) > 1, "the specimen must be genuinely split"
    assert work == WORKING_MIN
    assert span == SPAN_MIN
    assert span - work == PAUSED_MIN, "the pause must be real and large"
    # and the pause must fall where the machine is SHUT -- otherwise the
    # capacity property below could be satisfied by an open-time coincidence.
    lo, hi = datetime(2026, 1, 8, 14, 36), datetime(2026, 1, 12, 15, 37)
    open_total = sum((min(we, hi) - max(ws, lo)).total_seconds() / 60.0
                     for ws, we in OPEN_WINDOWS if min(we, hi) > max(ws, lo))
    assert open_total == WORKING_MIN, (
        "CUT-01's open time inside the span must equal the work -- this is what "
        "makes 'busy 5821' exceed the machine's whole open capacity by 3.9x")


# ---------------------------------------------------------------------------
# 1. THE NAMING REGISTER -- the class-level half
# ---------------------------------------------------------------------------

def test_every_duration_field_is_classified(box):
    """A NEW DURATION FIELD ON THE TOOLBOX IS RED UNTIL SOMEBODY SAYS WHICH
    QUANTITY IT IS. Fields are discovered by CALLING the tools, so this cannot
    be evaded by adding one somewhere the test did not look."""
    unregistered = {
        (tool.value, key)
        for tool, _where, key, _v in _all_tool_payloads(box)
        if TIMEY_KEY.search(key) and key not in DURATION_FIELD_REGISTER
    }
    assert not unregistered, (
        "unclassified time-quantity field(s) on the synthesis toolbox: "
        f"{sorted(unregistered)}. Add each to DURATION_FIELD_REGISTER with the "
        "quantity it carries (working / elapsed / capacity / neither). If it is "
        "a duration, it must also SAY which in its name.")


def test_no_bare_duration_field_survives(box):
    """THE ORIGINAL DEFECT, AS A NAME. ``duration_minutes`` and ``busy_minutes``
    said nothing about which quantity they were, and both were the span. A bare
    name is banned outright rather than registered, because the ruling's
    requirement is that the SURFACE names which -- a register entry a planner
    never sees does not discharge it."""
    bare = {"duration_minutes", "busy_minutes", "duration_min", "minutes",
            "span_minutes", "time_minutes", "total_minutes"}
    seen = {key for _t, _w, key, _v in _all_tool_payloads(box)}
    assert not (seen & bare), (
        f"unqualified duration field(s) back on the toolbox: {sorted(seen & bare)}")


# ---------------------------------------------------------------------------
# 2. THE VALUE PROPERTY -- registering a field does not make it true
# ---------------------------------------------------------------------------

def test_working_time_equals_the_sum_of_the_run_windows(box):
    """Working time is the sum of the run windows AND NOTHING ELSE."""
    for tool, where, key, val in _all_tool_payloads(box):
        if DURATION_FIELD_REGISTER.get(key) != WORKING:
            continue
        if where == "summary":
            assert val == pytest.approx(WORKING_MIN + 120.0), (
                f"{tool.value}.{key} is registered WORKING but does not total "
                "the run windows of the rows beneath it")
        else:
            assert val in (pytest.approx(WORKING_MIN), pytest.approx(120.0)), (
                f"{tool.value} {where}.{key} = {val} is registered WORKING but "
                f"is neither operation's run-window total")
            assert val != pytest.approx(SPAN_MIN), (
                f"{tool.value} {where}.{key} reports the ELAPSED SPAN under a "
                "field named for working time -- the exact 4B.17 defect")


def test_no_reported_duration_exceeds_open_capacity(box):
    """THE 3.9x TELL. No duration attributed to WORK may exceed the machine's
    open capacity over the same interval -- 1501 minutes here. This is the
    property that would have caught ``busy_minutes: 5821`` on the day it was
    written, and it catches a span-as-duration whatever it is named, provided
    the fixture's pause falls inside a closure (asserted in the premise)."""
    open_min = sum((we - ws).total_seconds() / 60.0 for ws, we in OPEN_WINDOWS)
    for tool, where, key, val in _all_tool_payloads(box):
        if DURATION_FIELD_REGISTER.get(key) not in (WORKING, CAPACITY):
            continue
        assert val <= open_min, (
            f"{tool.value} {where}.{key} = {val} exceeds {MACHINE}'s entire "
            f"open capacity ({open_min}) -- it is a span, not work")


def test_both_figures_are_carried_for_a_split_operation(box):
    """WHERE BOTH ARE MEANINGFUL, BOTH ARE CARRIED -- never one standing for
    the other. 4B.17 recorded that there was no run-time figure anywhere in
    these rows, so the second tier had nothing truer to quote than the span."""
    res = box.call(ToolName.PLACEMENTS_FOR_ORDER.value, {"order": "ORD-000011"})
    row = res.rows[0]
    assert row["working_minutes"] == pytest.approx(WORKING_MIN)
    assert row["elapsed_span_minutes"] == pytest.approx(SPAN_MIN)
    assert row["paused_minutes"] == pytest.approx(PAUSED_MIN)
    assert row["pieces"] == 3


def test_a_contiguous_operation_states_no_pause(box):
    """THE GUARD MUST NOT FIRE ON EVERYTHING. A contiguous operation carries no
    ``paused_minutes`` at all -- an absent field, not a zero, so the two rows
    that do have one stay legible among fifty-four that do not."""
    res = box.call(ToolName.PLACEMENTS_FOR_ORDER.value, {"order": "ORD-000099"})
    row = res.rows[0]
    assert row["pieces"] == 1
    assert "paused_minutes" not in row
    assert row["working_minutes"] == pytest.approx(row["elapsed_span_minutes"])


# ---------------------------------------------------------------------------
# 3. THE GAP THAT DENIED A PAUSE
# ---------------------------------------------------------------------------

def test_a_gap_reports_how_much_of_it_was_open(box):
    """``gap_before_minutes: 0.0`` was read in 4B.17 as denying the pause the
    operation contains. The gap field was not lying -- the pause is INSIDE the
    row, and no before-gap could ever surface it; the ROW was flat where the
    work is not. Both halves are now reported: the wall gap, and how much of it
    was open capacity, which is the only part anything could have used."""
    res = box.call(ToolName.MACHINE_OCCUPANCY.value, {"machine": MACHINE})
    first, second = res.rows[0], res.rows[1]
    assert first["gap_before_minutes"] is None, "nothing precedes the first row"
    # ORD-000011 ends Mon 15:37; ORD-000099 starts Tue 07:00. 923 wall
    # minutes, of which CUT-01 is open 15:37-19:00 Monday = 203.
    assert second["gap_before_minutes"] == pytest.approx(923.0)
    assert second["idle_open_minutes_before"] == pytest.approx(203.0)
    assert second["idle_open_minutes_before"] < second["gap_before_minutes"], (
        "a wall gap read as available capacity is the same error in a "
        "different field")


def test_the_pause_is_visible_on_the_occupancy_row(box):
    """What ``gap_before_minutes`` structurally could not say, the row now
    says."""
    res = box.call(ToolName.MACHINE_OCCUPANCY.value, {"machine": MACHINE})
    row = res.rows[0]
    assert row["pieces"] == 3
    assert row["paused_minutes"] == pytest.approx(PAUSED_MIN)
    assert row["working_minutes"] == pytest.approx(WORKING_MIN)


def test_the_occupancy_summary_carries_a_computable_utilisation(box):
    """A reasoner asked "how busy is CUT-01" must not have to infer the
    denominator. Inferring it from the span is exactly the 3.9x error."""
    res = box.call(ToolName.MACHINE_OCCUPANCY.value, {"machine": MACHINE})
    s = res.summary
    assert s["working_minutes"] == pytest.approx(WORKING_MIN + 120.0)
    assert s["open_capacity_minutes"] > 0
    assert s["utilization_pct"] == pytest.approx(
        100.0 * s["working_minutes"] / s["open_capacity_minutes"], rel=1e-3)
    assert s["utilization_pct"] <= 100.0, (
        "utilisation over 100% is the span leaking into the numerator")


# ---------------------------------------------------------------------------
# 3b. THE FIGURE MUST BE QUOTABLE, NOT MERELY TRUE
# ---------------------------------------------------------------------------

def test_derived_row_figures_are_trusted_by_the_verifier(box):
    """A TRUE ANSWER THAT GETS CUT IS NOT THE GOAL.

    The claim verifier re-fetches a claim's cited records and checks the
    figures against them. ``working_minutes`` is a sum over the run windows and
    lives in NO single record, so the re-fetch cannot rebuild it -- exactly as
    a summary total cannot be rebuilt, which is why summaries were already
    trusted. Measured on the pinned world before this was fixed: the second
    tier drafted "puts 1501 minutes of actual work on the machine" with four
    real citations and verification cut all three of its claims.

    So every derived row figure must land in the toolbox's own tallies. If it
    does not, the product answers the question correctly and then refuses to
    say so."""
    box.call(ToolName.PLACEMENTS_FOR_ORDER.value, {"order": "ORD-000011"})
    box.call(ToolName.MACHINE_OCCUPANCY.value, {"machine": MACHINE})
    for figure in (WORKING_MIN, SPAN_MIN, PAUSED_MIN):
        assert figure in box.count_profile, (
            f"{figure} is derived by the toolbox but is not in its tallies, so "
            "a claim quoting it cannot be VERIFIED")
    # and the tallies must be REACHABLE from the rows a claim would cite
    tallied = set()
    for entry in box.call_tallies:
        tallied |= entry[2]
    assert {WORKING_MIN, SPAN_MIN, PAUSED_MIN} <= tallied


def test_the_trusted_set_is_named_not_everything(box):
    """THE LIMIT OF THAT TRUST, PINNED. Only fields the toolbox DERIVES are
    trusted; a value copied verbatim out of a record still has to be found in
    that record, which is what keeps the re-fetch a check rather than a
    formality. If somebody widens ``_DERIVED_ROW_FIGURES`` to every numeric row
    field, this goes red."""
    from mre.modules.evidence_tools import _DERIVED_ROW_FIGURES
    for name in _DERIVED_ROW_FIGURES:
        assert name in DURATION_FIELD_REGISTER, (
            f"{name} is trusted as derived arithmetic but is not classified")
    assert "op_seq" not in _DERIVED_ROW_FIGURES, "op_seq is a record field"
    assert len(_DERIVED_ROW_FIGURES) <= 8, (
        "the trusted set has grown; every member must be a figure the toolbox "
        "computes and no record contains")


# ---------------------------------------------------------------------------
# 4. THE GOVERNED ARTIFACT
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool", [
    ToolName.PLACEMENTS_FOR_ORDER, ToolName.PLACEMENTS_FOR_MACHINE,
    ToolName.PLACEMENTS_IN_WINDOW, ToolName.MACHINE_OCCUPANCY,
])
def test_the_tool_meaning_names_which_quantity(tool):
    """The synthesis prompt is BUILT from TOOL_MEANINGS. A meaning that says
    "duration" without saying which one teaches the model the conflation this
    session exists to end."""
    from mre.contracts.synthesis import TOOL_MEANINGS
    meaning = TOOL_MEANINGS[tool]
    assert "working_minutes" in meaning
    assert "elapsed_span_minutes" in meaning
    assert not re.search(r"\bduration\b(?!_)", meaning) or "working" in meaning

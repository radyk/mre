"""Mobility Box (datasets/mobility_box) — the premise tests for the fenced world.

Session 4A teaching-graft (c), Item 1. `mobility_premise.assess` returns five
verdicts; two of them — `boxed-in` and `earlier-open` — were measured at ZERO on
both pinned boards (4A.x §5a.152(b)) and were asserted by unit test only. This
dataset is a plant that STOPS, which is the one shape that can produce them, and
this file is the guard that the world still holds its specimens.

WHY THESE ARE "PREMISE TESTS" AND NOT "VERDICT TESTS". A specimen world whose
specimens are ASSUMED is the species this repo keeps finding (4B.21 §5a.78: a
guard that supplies its own arguments proves the assembler, not the path). So
nothing here asserts a verdict string alone. Each story asserts the MECHANISM
that makes the verdict true:

  * boxed-in     — the binding family is PRECEDENCE and the actual start is at
                   it, AND `BOX-01` has no open window whatsoever after the bar
                   ends. Two independent measurements, one per direction.
  * earlier-open — the binding family is CHUNK-FIT and it lands on the SATURDAY
                   OVERTIME window, with the measured slack; AND every free
                   window after the bar is shorter than the bar.

and two NEGATIVE CONTROLS mutate the dataset and prove each specimen COLLAPSES
when the mechanism is removed. A premise test that cannot go red is a decoration.

Part A (fast) reads the committed CSVs. Parts B and C solve; the world is nine
orders and three machines, so the solve is seconds, but they are marked slow
because they run the whole spine.
"""
from __future__ import annotations

import csv
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.modules import mobility_premise as mp
from mre.modules.conformance import ConformanceGate
from mre.reporter import Reporter

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "mobility_box"

#: The last instant `BOX-01` is open, ever, in anything this plan can see. The
#: closure rows run past it to 2026-02-13; the analysis window (last placement
#: + 14 days) ends 2026-01-27. Both numbers are in the dataset README.
BOX_LAST_CLOSE = datetime(2026, 1, 13, 19, 0)

#: The Saturday overtime window that IS story 2's earlier room.
SATURDAY = datetime(2026, 1, 10, 7, 0)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _copy_dataset(tmp_path: Path) -> Path:
    dst = tmp_path / "sub"
    shutil.copytree(DATASET, dst)
    shutil.rmtree(dst / "gate_output", ignore_errors=True)
    return dst


def _solve(submission: Path, out: Path, snapshot: str = "snap-mobility"):
    rc = mre_main([
        "--submission", str(submission), "--out", str(out),
        "--snapshot-id", snapshot,
        "--solver-workers", "1", "--solver-seed", "0",
        "--time-limit", "600",
    ])
    assert rc == 0, f"pipeline exit {rc}"
    return out


def _explainer(out: Path, snapshot: str = "snap-mobility"):
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.snapshot_store import SnapshotStore
    ip = out / "evidence_index.json"
    index = (EvidenceIndex.load(ip) if ip.exists()
             else EvidenceIndex().build(out / "runs"))
    return Explainer(SnapshotStore(out / "snapshots"), index,
                     snapshot_id=snapshot)


def _naive(dt) -> datetime:
    """The explainer's calendar helpers return naive instants and its rows carry
    aware ones. Comparing the two raises, which is how this file's first version
    reported a mechanism it had not measured."""
    return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt


def _verdicts(ex) -> dict[tuple[str, int], dict]:
    out: dict[tuple[str, int], dict] = {}
    for row in ex._load_enriched_assignments():
        orders = row.get("work_orders") or []
        if not orders:
            continue
        v = ex.mobility_verdict(orders[0], row.get("machine"), row.get("op_seq"))
        out[(orders[0], int(row.get("op_seq") or 0))] = v or {}
    return out


# ---------------------------------------------------------------------------
# Part A — the dataset says what the README says it says
# ---------------------------------------------------------------------------

class TestDatasetIsWhatItClaims:

    def test_gate_accepts_c2_no_findings(self, tmp_path):
        reporter = Reporter.begin(
            module=ModuleCode.M0, purpose="mobility_box gate", config={},
            trigger="test", snapshot_id="pre-adapter", sink_dir=tmp_path / "runs")
        result = ConformanceGate().run(DATASET, reporter)
        reporter.end(RunStatus.SUCCESS if result.go else RunStatus.PARTIAL)
        assert result.grade == "ACCEPTED"
        assert result.go is True
        assert result.costing_grade == "C2"
        assert result.certificate["findings"] == []
        assert result.certificate["deficiencies"] == []

    def test_the_outage_is_declared_and_outlasts_the_analysis_window(self):
        """The fence is a set of CLOSURE rows, and it must run past the padded
        analysis window (last placement + 14 days = 2026-01-27) or `later_at`
        finds room again and both specimens dissolve."""
        rows = list(csv.DictReader(
            (DATASET / "calendars.csv").read_text(encoding="utf-8").splitlines()))
        closures = sorted(r["exception_date"] for r in rows
                          if r["calendar_id"] == "CAL-BOX"
                          and r["exception_type"] == "closure")
        assert closures, "the outage rows are the whole fence"
        assert closures[0] == "2026-01-14"
        assert closures[-1] >= "2026-01-27", (
            "the closure run must outlast the analysis window")

    def test_the_saturday_overtime_row_is_present(self):
        """Story 2's earlier room is ONE row. Named here so that deleting it is a
        visible change to this guard and not a silent change to a verdict."""
        text = (DATASET / "calendars.csv").read_text(encoding="utf-8")
        assert "2026-01-10,added,overtime" in text

    def test_overtime_bills_a_premium(self):
        """Without a premium the solver is INDIFFERENT between the Saturday and
        the Monday, stage 2 pulls the bar onto the Saturday, and `earlier-open`
        becomes `could_not`. The multiplier is the specimen's cost lever."""
        import json
        cm = json.loads((DATASET / "cost_model.json").read_text(encoding="utf-8"))
        assert cm["refinements"]["overtime_premium_multiplier"] == 1.5


# ---------------------------------------------------------------------------
# Part B — the solve holds the specimens (slow)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def solved(tmp_path_factory):
    out = tmp_path_factory.mktemp("mobility_box_out")
    _solve(DATASET, out)
    return out


@pytest.mark.slow
class TestTheWorldHoldsItsSpecimens:

    def test_nothing_is_late(self, solved):
        """Every story here is about MOBILITY, so tardiness must not be a second
        explanation for any placement. A late order in this world is a finding."""
        rows = list(csv.DictReader(
            (solved / "schedule.csv").read_text(encoding="utf-8").splitlines()))
        assert len(rows) == 11, "10 operations, one of them in two chunks"
        ex = _explainer(solved)
        for r in ex._load_enriched_assignments():
            for so in (r.get("service_outcomes") or {}).values():
                assert (so.get("tardiness_cost") or 0.0) == 0.0

    # -- story 1: boxed-in ---------------------------------------------------

    def test_story1_ord_box_op20_is_BOXED_IN(self, solved):
        ex = _explainer(solved)
        v = ex.mobility_verdict("ORD-BOX", "BOX-01", 20)
        assert v is not None
        assert v["verdict"] == mp.VERDICT_BOXED_IN
        assert v["holds"] is True and v["refutes"] is False
        assert v["later_at"] is None
        assert v["earlier_verdict"] == "could_not"
        assert v["open_directions"] == []

    def test_story1_mechanism_earlier_is_shut_by_PRECEDENCE(self, solved):
        """The premise, verified at the grain it is asserted at: op20 starts the
        minute op10 frees it, and the family that binds is precedence — not the
        calendar, which would make this a different story."""
        ex = _explainer(solved)
        an, row = ex._blocker_analysis("ORD-BOX", "BOX-01", 20)
        assert an.verdict == "could_not"
        assert an.binding is not None and an.binding.family == "precedence"
        assert _naive(an.binding.est) == datetime(2026, 1, 13, 9, 51)
        assert _naive(an.actual_start) == datetime(2026, 1, 13, 9, 52)

    def test_story1_mechanism_later_is_shut_by_an_EMPTY_CALENDAR(self, solved):
        """The other direction, measured independently of the verdict: BOX-01 has
        no open window at all after its last shift closes."""
        ex = _explainer(solved)
        after = [(s, e) for s, e in ex._open_windows("BOX-01")
                 if _naive(e) > BOX_LAST_CLOSE]
        assert after == [], f"BOX-01 reopened: {after}"

    def test_story1_the_last_sliver_is_too_small_for_the_bar(self, solved):
        """The bar ends 27 minutes before its own machine shuts for good. If that
        sliver ever grew past the bar's length the verdict would flip without
        anything in the dataset changing, so it is measured rather than trusted."""
        ex = _explainer(solved)
        row = next(r for r in ex._load_enriched_assignments()
                   if (r.get("work_orders") or [None])[0] == "ORD-BOX"
                   and r.get("op_seq") == 20)
        end = _naive(datetime.fromisoformat(str(row["end"]).replace("Z", "+00:00")))
        sliver = (BOX_LAST_CLOSE - end).total_seconds() / 60.0
        assert 0 < sliver < float(row["run_min"])

    # -- story 2: earlier-open ----------------------------------------------

    def test_story2_ord_early_is_EARLIER_OPEN(self, solved):
        ex = _explainer(solved)
        v = ex.mobility_verdict("ORD-EARLY", "BOX-01", 10)
        assert v is not None
        assert v["verdict"] == mp.VERDICT_EARLIER_OPEN
        assert v["holds"] is False and v["refutes"] is True
        assert v["later_at"] is None
        assert v["earlier_verdict"] == "chose"
        assert v["open_directions"] == ["earlier"], (
            "a refutation names the direction that is open, and ONLY earlier is")

    def test_story2_mechanism_the_earlier_room_is_the_SATURDAY(self, solved):
        """`chose` is only worth saying if we can name what was open. Here the
        binding family is chunk-fit and it lands on the declared overtime window
        — so the true sentence is "the room existed and it was overtime"."""
        ex = _explainer(solved)
        an, _row = ex._blocker_analysis("ORD-EARLY", "BOX-01", 10)
        assert an.verdict == "chose"
        assert an.binding is not None and an.binding.family == "chunkfit"
        assert _naive(an.binding.est) == SATURDAY
        assert _naive(an.actual_start) == datetime(2026, 1, 12, 7, 0)
        assert an.slack_min == 2880.0

    def test_story2_mechanism_every_later_window_is_too_short(self, solved):
        """`later_at is None` here is NOT "the machine is booked" — there are two
        free windows after this bar and both are shorter than it. Measured,
        because "no room later" and "no time later" are different claims."""
        ex = _explainer(solved)
        row = next(r for r in ex._load_enriched_assignments()
                   if (r.get("work_orders") or [None])[0] == "ORD-EARLY")
        cal = ex._later_calendar(row)
        end = _naive(cal["current_end"])
        later_free = [(s, e) for s, e in cal["free"] if _naive(e) > end]
        assert later_free, "the story is that the windows are SHORT, not absent"
        for s, e in later_free:
            span = (_naive(e) - max(_naive(s), end)).total_seconds() / 60.0
            assert span < cal["working_min"], (s, e, span, cal["working_min"])

    # -- stories 3 and 4: the controls --------------------------------------

    def test_story3_ord_pack_is_the_LATER_OPEN_control(self, solved):
        ex = _explainer(solved)
        v = ex.mobility_verdict("ORD-PACK", "PACK-01", 10)
        assert v["verdict"] == mp.VERDICT_LATER_OPEN
        assert v["later_at"] is not None

    def test_story4_ord_span_is_the_UNDECIDABLE_control(self, solved):
        ex = _explainer(solved)
        v = ex.mobility_verdict("ORD-SPAN", "PACK-01", 10)
        assert v["verdict"] == mp.VERDICT_UNDECIDABLE
        assert v["chunk_count"] == 2
        assert v["holds"] is False and v["refutes"] is False, (
            "undecidable is neither, and a caller reading `not holds` as refuted "
            "would manufacture the claim the dataclass refuses to make")

    # -- the census ----------------------------------------------------------

    def test_the_whole_board_tallies(self, solved):
        """Four of the five verdicts live on one board. `held` is unreachable in a
        MONOLITHIC solve (no frozen front, no pins) and is the one verdict with
        live specimens on both pinned rolling boards already."""
        ex = _explainer(solved)
        tally: dict[str, int] = {}
        for v in _verdicts(ex).values():
            tally[v.get("verdict")] = tally.get(v.get("verdict"), 0) + 1
        assert tally == {mp.VERDICT_BOXED_IN: 1, mp.VERDICT_EARLIER_OPEN: 1,
                         mp.VERDICT_LATER_OPEN: 7, mp.VERDICT_UNDECIDABLE: 1}
        assert mp.VERDICT_HELD not in tally


# ---------------------------------------------------------------------------
# Part C — the negative controls: the premise tests can go RED
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestTheGuardDetectsADriftingWorld:
    """Each control removes ONE mechanism from the dataset, re-solves, and proves
    the specimen collapses. Without these, Part B asserts constants."""

    def test_control_a_reopen_the_machine_and_BOXED_IN_collapses(self, tmp_path):
        """Delete the outage. `BOX-01` works on, room appears after the bar, and
        the bar a planner correctly called immovable becomes movable."""
        sub = _copy_dataset(tmp_path)
        cal = sub / "calendars.csv"
        kept = [ln for ln in cal.read_text(encoding="utf-8").splitlines()
                if ",closure," not in ln]
        cal.write_text("\n".join(kept) + "\n", encoding="utf-8")
        out = _solve(sub, tmp_path / "out_a", snapshot="snap-mobility-ctl-a")
        ex = _explainer(out, "snap-mobility-ctl-a")
        v = ex.mobility_verdict("ORD-BOX", "BOX-01", 20)
        assert v["verdict"] != mp.VERDICT_BOXED_IN
        assert v["later_at"] is not None

    def test_control_b_take_the_saturday_away_and_EARLIER_OPEN_collapses(
            self, tmp_path):
        """Delete the overtime row. There is no longer anywhere earlier for
        `ORD-EARLY` to have gone, `chose` becomes `could_not`, and the bar that
        demonstrated a refutation becomes one that demonstrates the opposite."""
        sub = _copy_dataset(tmp_path)
        cal = sub / "calendars.csv"
        kept = [ln for ln in cal.read_text(encoding="utf-8").splitlines()
                if ",added,overtime" not in ln]
        cal.write_text("\n".join(kept) + "\n", encoding="utf-8")
        out = _solve(sub, tmp_path / "out_b", snapshot="snap-mobility-ctl-b")
        ex = _explainer(out, "snap-mobility-ctl-b")
        v = ex.mobility_verdict("ORD-EARLY", "BOX-01", 10)
        assert v["verdict"] != mp.VERDICT_EARLIER_OPEN
        assert v["earlier_verdict"] != "chose"


# ---------------------------------------------------------------------------
# Part D — what the fenced world FOUND: the LATER paragraph and the lead
#          disagreed about one bar
# ---------------------------------------------------------------------------

class TestTheLaterParagraphAgreesWithItsOwnLead:
    """SESSION 4A teaching-graft (c), measured live on this world the first time
    it was asked a question.

    `TemplateRenderer._render_mobility_later` enumerated HELD, UNDECIDABLE and
    LATER_OPEN and treated EVERYTHING ELSE as BOXED_IN. `earlier-open` needs
    `later_at` to be None, which no board that keeps working can produce — so
    that fall-through had never rendered against a solve, and on the first bar
    that reached it the answer contradicted itself inside one screen:

        "It can be moved — nothing was holding ORD-EARLY op10 back."
        ...
        "Later: ... so "can't be moved" is fair, and the reason above is the
         whole of it."

    `mobility_lead_line` (the family floor, 4A.y) enumerates all five verdicts
    and returns None for anything else. Two renderers were built from one
    verdict; the one that DEFAULTED is the one that manufactured a claim.

    The guard below is the property, not the string: the paragraph may say the
    premise is FAIR if and only if the verdict says the premise HOLDS.
    """

    def _para(self, mob: dict) -> str:
        from mre.modules.renderers import TemplateRenderer
        lines: list[str] = ["(the answer above)"]
        TemplateRenderer()._render_mobility_later(
            lines, {"order": "ORD-EARLY", "machine": "BOX-01", "op_seq": 10},
            mob)
        return "\n".join(lines[1:])

    _FAIR = '"can\'t be moved" is fair'

    @pytest.mark.parametrize("verdict,extra", [
        (mp.VERDICT_HELD, {"held_kind": mp.HELD_FROZEN, "held_at": "2026-01-13"}),
        (mp.VERDICT_HELD, {"held_kind": mp.HELD_PINNED, "held_at": "2026-01-13"}),
        (mp.VERDICT_BOXED_IN, {}),
        (mp.VERDICT_UNDECIDABLE, {"chunk_count": 2}),
        (mp.VERDICT_LATER_OPEN, {"later_at": "2026-01-20 07:00",
                                 "later_weekday": "Tuesday"}),
        (mp.VERDICT_EARLIER_OPEN, {"open_directions": ["earlier"]}),
    ])
    def test_the_paragraph_claims_the_premise_holds_iff_it_holds(
            self, verdict, extra):
        v = mp.assess(
            held_kind=extra.get("held_kind", ""),
            chunk_count=extra.get("chunk_count", 0),
            later_at=(datetime(2026, 1, 20, 7, 0)
                      if verdict == mp.VERDICT_LATER_OPEN else None),
            earlier_verdict=("chose" if verdict == mp.VERDICT_EARLIER_OPEN
                             else "could_not"))
        mob = dict(extra)
        mob["verdict"] = verdict
        mob.setdefault("chunk_count", 0)
        para = self._para(mob)
        assert (self._FAIR in para) == v.holds, (
            f"{verdict}: holds={v.holds} but the paragraph "
            f"{'asserts' if self._FAIR in para else 'does not assert'} the "
            f"premise is fair:\n{para}")

    def test_earlier_open_hands_the_planner_the_direction_that_IS_open(self):
        para = self._para({"verdict": mp.VERDICT_EARLIER_OPEN,
                           "open_directions": ["earlier"], "chunk_count": 0})
        assert "no room that way" in para
        assert "earlier one above" in para
        assert self._FAIR not in para

    def test_an_unrecognised_verdict_says_NOTHING(self):
        """4B.23's fail-safe rule at the seam that was violating it: a verdict
        this renderer does not know must not inherit a sentence about the
        plant. The negative control for the fix is the OLD behaviour — before
        it, this rendered the boxed-in copy."""
        assert self._para({"verdict": "some-future-verdict",
                           "chunk_count": 0}).strip() == ""

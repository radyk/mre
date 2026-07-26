"""The rolling pre-route retires: the last deterministic classifier dies.

Session 4A.5c CU4. 4A.5b ruled this scope and stated the prerequisite:

    the parse resolves SUBJECTS against the Explainer's snapshot, which on a
    rolling run is WINDOW 0 ONLY. An order sitting in the beyond-horizon tray
    would resolve to nothing and be answered as ABSENT -- a confident-wrong
    answer replacing a correct one.

So these assert two things, in that order: the tray is VISIBLE to subject
resolution, and only then that the three rolling intents reach their answerers
through the parse rather than through a keyword table.

The phrasing->intent claim is NOT asserted here. That is a claim about a live
model, and it is graded where a live model is measured: the sweep's rolling bank
(R-AI4(2)). What is offline is the DISPATCH.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mre.contracts.parse import Intent, SubjectDisposition
from mre.modules.explainer import Explainer
from mre.modules.interpreter import dispatch
from mre.modules.renderers import TemplateRenderer
from mre.modules.rolling_questions import RollingVocabulary

from tests.parse_doubles import parsed, resolve
from tests.test_interpreter import FakeStore, _make_index

REPO = Path(__file__).resolve().parent.parent
ROLLING_DOC = REPO / "tests" / "cockpit" / "fixtures" / "rolling" / "schedule.json"


@pytest.fixture(scope="module")
def doc():
    return json.loads(ROLLING_DOC.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rolling(doc):
    return RollingVocabulary(doc)


@pytest.fixture()
def explainer(tmp_path):
    return Explainer(snapshot_store=FakeStore("snap-demo"),
                     index=_make_index(tmp_path), snapshot_id="snap-demo")


@pytest.fixture(scope="module")
def tray_order(doc):
    tray = doc["rolling"]["beyond_horizon"]
    assert tray, "the fixture must have a populated tray"
    return tray[0]["work_order"]


def _render(bundle) -> str:
    return TemplateRenderer().render(bundle)


# ---------------------------------------------------------------------------
# The prerequisite: a tray order is a REAL SUBJECT
# ---------------------------------------------------------------------------

class TestTheTrayIsVisible:

    def test_a_tray_order_resolves_with_a_beyond_horizon_disposition(
            self, explainer, rolling, tray_order):
        p = resolve(parsed(f"why is {tray_order} late", Intent.LATE_ORDER,
                           orders=(tray_order,)), explainer, rolling=rolling)
        subject = p.subjects[0]
        assert subject.ref == tray_order.upper()
        assert subject.disposition is SubjectDisposition.BEYOND_HORIZON
        assert subject.beyond_horizon

    def test_a_windowed_order_is_not_beyond_the_horizon(
            self, explainer, rolling, doc):
        placed = next(a["work_orders"][0] for a in doc["assignments"]
                      if a.get("work_orders"))
        p = resolve(parsed(f"when does {placed} finish", Intent.ORDER_SCHEDULE,
                           orders=(placed,)), explainer, rolling=rolling)
        s = p.subjects[0]
        assert s.disposition in (SubjectDisposition.IN_WINDOW,
                                 SubjectDisposition.COMMITTED)
        assert not s.beyond_horizon

    def test_a_monolithic_run_carries_no_disposition(self, explainer):
        """None on a monolithic run, where there is one region and naming it
        would be noise."""
        p = resolve(parsed("why is WO-2001 late", Intent.LATE_ORDER,
                           orders=("WO-2001",)), explainer, rolling=None)
        assert p.subjects[0].ref == "WO-2001"
        assert p.subjects[0].disposition is None


# ---------------------------------------------------------------------------
# The honesty fix this whole CU exists for
# ---------------------------------------------------------------------------

class TestATrayOrderIsNeverAbsent:

    def test_a_placement_question_about_a_tray_order_says_why_it_is_not_placed(
            self, explainer, rolling, doc, tray_order):
        """THE PINNED DISTINCTION. Before this, `why is <tray order> late` found
        nothing in the window-0 snapshot and answered that the order is not in
        this schedule. It IS in this schedule; it is beyond the horizon."""
        p = resolve(parsed(f"why is {tray_order} late", Intent.LATE_ORDER,
                           orders=(tray_order,)), explainer, rolling=rolling)
        d = dispatch(explainer, p, document=doc)
        assert d.route == "why-not-scheduled-yet"
        text = _render(d.bundle)
        assert tray_order in text
        assert "beyond the current window" in text
        for absent in ("not in this schedule", "isn't in this schedule",
                       "not part of this schedule"):
            assert absent not in text

    @pytest.mark.parametrize("intent", [
        Intent.LATE_ORDER, Intent.ORDER_SCHEDULE, Intent.START_REASON,
        Intent.ORDER_ATTRIBUTES,
    ])
    def test_every_placement_intent_lands_on_the_disposition(
            self, explainer, rolling, doc, tray_order, intent):
        """Each of these would have found nothing in window 0 and said something
        wrong in its own way. The disposition is the one honest answer."""
        p = resolve(parsed(f"tell me about {tray_order}", intent,
                           orders=(tray_order,)), explainer, rolling=rolling)
        d = dispatch(explainer, p, document=doc)
        assert d.route == "why-not-scheduled-yet"

    def test_an_order_the_document_does_not_carry_is_still_absent(
            self, explainer, rolling, doc):
        """The tray is not a wildcard. A name nothing carries is still answered as
        not here — the relevance guard is intact."""
        p = resolve(parsed("why is ZZZ-9999 late", Intent.LATE_ORDER,
                           orders=("ZZZ-9999",)), explainer, rolling=rolling)
        assert p.subjects[0].ref is None
        d = dispatch(explainer, p, document=doc)
        assert d.route == "unknown-entity"

    def test_asking_why_not_scheduled_about_a_tray_order_does_not_loop(
            self, explainer, rolling, doc, tray_order):
        p = resolve(parsed(f"why isnt {tray_order} scheduled yet",
                           Intent.WHY_NOT_SCHEDULED_YET, orders=(tray_order,)),
                    explainer, rolling=rolling)
        d = dispatch(explainer, p, document=doc)
        assert d.route == "why-not-scheduled-yet"
        assert tray_order in _render(d.bundle)


# ---------------------------------------------------------------------------
# The three intents dispatch (no keyword table anywhere)
# ---------------------------------------------------------------------------

class TestRollingIntentsDispatch:

    def test_beyond_horizon(self, explainer, doc):
        d = dispatch(explainer, parsed("whats beyond the horizon",
                                       Intent.BEYOND_HORIZON), document=doc)
        assert d.route == "beyond-horizon"
        text = _render(d.bundle)
        assert "beyond the current window" in text
        assert str(len(doc["rolling"]["beyond_horizon"])) in text

    def test_frozen(self, explainer, doc):
        d = dispatch(explainer, parsed("whats frozen", Intent.FROZEN), document=doc)
        assert d.route == "frozen"
        text = _render(d.bundle)
        assert "frozen" in text.lower()
        assert doc["rolling"]["frozen_until"][:10] in text

    def test_the_answers_are_id_free(self, explainer, doc):
        """R-AI1's reviewable-artifact rule, unchanged by the retirement."""
        import re
        for intent in (Intent.BEYOND_HORIZON, Intent.FROZEN):
            d = dispatch(explainer, parsed("q", intent), document=doc)
            assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", _render(d.bundle))

    def test_the_estimate_stays_hedged_through_the_render(
            self, explainer, rolling, doc, tray_order):
        """The hedge is the honesty. It survives the route AND the render — the
        rolling bundle is authored copy for exactly this reason."""
        tray = doc["rolling"]["beyond_horizon"][0]
        if not tray.get("earliest_window_estimate"):
            pytest.skip("this fixture's nearest tray item has no estimate")
        p = resolve(parsed(f"when will {tray_order} run",
                           Intent.WHY_NOT_SCHEDULED_YET, orders=(tray_order,)),
                    explainer, rolling=rolling)
        text = _render(dispatch(explainer, p, document=doc).bundle)
        assert "estimate" in text.lower()
        assert "not a committed placement" in text

    def test_a_rolling_intent_on_a_monolithic_run_is_honest(self, explainer):
        """The right answer to a sliced-world question about a plan with no
        slices — not a crash, and not a pretend tray."""
        d = dispatch(explainer, parsed("whats beyond the horizon",
                                       Intent.BEYOND_HORIZON), document=None)
        assert d.route == "beyond-horizon"
        assert "isn't a rolling schedule" in _render(d.bundle)

    def test_the_rolling_answers_are_never_llm_reworded(self):
        """A reword that drops "that's an estimate" turns an honest answer into a
        commitment the solver never made."""
        from mre.modules.renderers import LLMRenderer
        assert "rolling" in LLMRenderer._AUTHORED_COPY_SUBJECTS

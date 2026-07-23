"""Session 4B.3a CU3 — rolling-horizon AI reachability (R-AI1).

The three rolling questions ("what's beyond the horizon?", "why isn't {order}
scheduled yet?", "what's frozen?") are answered deterministically from the
contract-1.7 document by rolling_questions. These fast tests run against the REAL
committed rolling fixture (built from a real solve by tools/build_rolling_fixture.py)
so the answers are asserted against genuine sliced-world state, not a mock.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mre.modules.rolling_questions import (
    classify_rolling, answer_beyond_horizon, answer_frozen,
    answer_why_not_scheduled_yet,
)

REPO = Path(__file__).resolve().parent.parent
ROLLING_DOC = REPO / "tests" / "cockpit" / "fixtures" / "rolling" / "schedule.json"
EMPTY_DOC = REPO / "tests" / "cockpit" / "fixtures" / "rolling_empty" / "schedule.json"


@pytest.fixture(scope="module")
def doc():
    return json.loads(ROLLING_DOC.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def empty_doc():
    return json.loads(EMPTY_DOC.read_text(encoding="utf-8"))


def test_classify_only_fires_on_a_rolling_document(doc):
    # a monolithic document (no rolling block) never routes here.
    assert classify_rolling("what's beyond the horizon?", {"rolling": None}) is None
    assert classify_rolling("what's frozen?", {}) is None
    # the three shapes route on a rolling document.
    assert classify_rolling("what's beyond the horizon?", doc) == "beyond-horizon"
    assert classify_rolling("what's frozen?", doc) == "frozen"
    assert classify_rolling("why isn't ORD-01 scheduled yet?", doc) == "why-not-scheduled-yet"


def test_beyond_horizon_answer_names_the_tray(doc):
    a = answer_beyond_horizon(doc)
    n = len(doc["rolling"]["beyond_horizon"])
    assert str(n) in a
    assert "beyond the current window" in a
    # names the nearest orders by due date (planner vocabulary, not UUIDs)
    first = doc["rolling"]["beyond_horizon"][0]
    assert (first.get("work_order") or first["demand_ref"][:8]) in a
    assert "due" in a
    # no raw UUID leaks into the answer
    import re
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", a)


def test_beyond_horizon_empty_is_honest(empty_doc):
    a = answer_beyond_horizon(empty_doc)
    assert "Nothing is beyond the horizon" in a


def test_frozen_answer_states_committed_facts(doc):
    a = answer_frozen(doc)
    r = doc["rolling"]
    assert str(r["committed_count"]) in a
    assert "frozen" in a.lower()
    assert r["frozen_until"][:10] in a


def test_why_not_scheduled_hedges_the_estimate(doc):
    # pick an order actually in the tray
    tray = doc["rolling"]["beyond_horizon"]
    assert tray, "fixture must have a populated tray"
    order = tray[0].get("work_order") or tray[0]["demand_ref"]
    a = answer_why_not_scheduled_yet(doc, order)
    assert order in a
    assert "beyond the current window" in a
    # the estimate, when present, is HEDGED (never presented as a placement)
    if tray[0].get("earliest_window_estimate"):
        assert "estimate" in a.lower()
        assert "not a committed placement" in a


def test_why_not_no_order_asks_which(doc):
    a = answer_why_not_scheduled_yet(doc, None)
    assert "which order" in a.lower()


def test_why_not_unknown_order_is_honest(doc):
    a = answer_why_not_scheduled_yet(doc, "ORD-DOES-NOT-EXIST")
    assert "ORD-DOES-NOT-EXIST" in a
    assert "current window" in a or "not part of this schedule" in a

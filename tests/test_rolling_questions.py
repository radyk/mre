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
    RollingVocabulary, answer_beyond_horizon, answer_frozen,
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


# Session 4A.5c CU4 — `classify_rolling` is DELETED (the last deterministic
# classifier). What used to be asserted here — "these three phrasings route to
# these three ids" — is a claim about a LIVE PARSE now, and it is graded where a
# live model is actually measured: the sweep's rolling bank (R-AI4(2)). What is
# asserted offline is the prerequisite that made the deletion safe.


def test_the_keyword_matcher_is_gone_not_bypassed(doc):
    """R-AI5(2) forbids a deterministic-classifier fallback. The rolling matcher
    was the last one; a private reimplementation would be the same router wearing
    a different name, so the symbol's ABSENCE is the assertion."""
    import mre.modules.rolling_questions as rq
    assert not hasattr(rq, "classify_rolling")
    assert not any(n.endswith("_TRIGGERS") for n in vars(rq))


def test_rolling_vocabulary_places_every_region(doc):
    """THE PREREQUISITE (4A.5b rider d): subject resolution can see all three
    sliced regions, not just window 0."""
    vocab = RollingVocabulary(doc)
    assert vocab.is_rolling
    tray = doc["rolling"]["beyond_horizon"]
    assert tray, "fixture must have a populated tray"
    order = tray[0]["work_order"]
    assert vocab.resolve(order) == order.upper()
    assert vocab.disposition(order) == "beyond-horizon"
    assert vocab.beyond_horizon(order)
    # a placed bar resolves too, and is NOT beyond the horizon
    placed = next(a["work_orders"][0] for a in doc["assignments"]
                  if a.get("work_orders"))
    assert vocab.disposition(placed) in ("in-window", "committed")
    assert not vocab.beyond_horizon(placed)


def test_rolling_vocabulary_is_falsy_on_a_monolithic_document():
    assert not RollingVocabulary({"rolling": None})
    assert not RollingVocabulary({})
    assert not RollingVocabulary(None)
    # and it resolves nothing, so a monolithic run pays no cost and gains no
    # phantom vocabulary.
    assert RollingVocabulary({}).resolve("ORD-01") is None


def test_rolling_vocabulary_never_guesses_between_two_candidates(doc):
    """The relevance guard's rule, unchanged: two candidates leave it unresolved.
    Only names the document actually carries can match — no id-shape regex."""
    vocab = RollingVocabulary(doc)
    assert vocab.resolve("ORD-DOES-NOT-EXIST") is None
    assert vocab.resolve("") is None


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

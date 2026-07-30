"""NO TRUNCATED LIST IS EVER PRESENTED AS COMPLETE.

Session 4B.19, Item 3. The floor, non-negotiable: if a rendered list of board
entities is cut, the answer says so and gives the total.

THE MEASURED SPECIMEN (4B.17, 6/6 runs, both configurations). Asked "why is
ORD-000023 on MILL-99":

    There's no machine called MILL-99 in this plant.
    The machines here are: ASM-01, CUT-01, CUT-02, CUT-03, FINISH-01,
    FINISH-02, FINISH-03, HEAT-01.

Fifteen machines exist. The list was alphabetical, cut at eight, with no
ellipsis, no count and no "and 7 more" — so the sentence claimed to be the
plant. The seven it dropped were HEAT-02, MILL-01, MILL-02, PAINT-01, PAINT-02,
PRESS-FAST and PRESS-SLOW. ORD-000023 runs on PRESS-FAST. A planner who mistyped
MILL-01 looked for MILL-01, did not find it, and learned that MILL-01 does not
exist either — on the correction path FOR A TYPO.

WHAT IS CHECKED HERE. The unknown-entity route, both branches (machine and
order), over a fixture large enough to force a cut: the rendered answer must
never assert completeness, must carry the true total, and — Item 3(c) — must put
the NEAREST names first rather than the alphabetically first ones.
"""
from __future__ import annotations

import pytest

from mre.modules.explainer import ExplanationBundle, _nearest_names
from mre.modules.renderers import TemplateRenderer

# The pinned exam world's fifteen, verbatim (tests/ai_exam/banks/
# regression_founder_r5.txt header, "machines DECLARED (15)").
PLANT = ["ASM-01", "CUT-01", "CUT-02", "CUT-03", "FINISH-01", "FINISH-02",
         "FINISH-03", "HEAT-01", "HEAT-02", "MILL-01", "MILL-02", "PAINT-01",
         "PAINT-02", "PRESS-FAST", "PRESS-SLOW"]


def _render_unknown(mention, kind, near, total_key, total):
    bundle = ExplanationBundle(
        question=f"Is {mention} in this schedule?",
        subject_id=mention, subject_type="unknown_entity",
        subject_external_name=mention, ordered_records=[],
        key_facts={"mention": mention, "excluded": False, "finding": None,
                   "mention_kind": kind,
                   "known_machines": near if kind == "machine" else [],
                   "known_orders": [] if kind == "machine" else near,
                   total_key: total,
                   ("order_total" if kind == "machine" else "machine_total"): 0},
        snapshot_id="snap-test", identity_map=None)
    lines: list[str] = []
    TemplateRenderer()._render_unknown_entity(lines, bundle)
    return "\n".join(lines)


# ===========================================================================
# THE FLOOR
# ===========================================================================

def test_the_measured_specimen_no_longer_claims_to_be_the_plant():
    """4B.17's A2, end to end through the same renderer branch."""
    near = _nearest_names("MILL-99", PLANT, 4)
    text = _render_unknown("MILL-99", "machine", near, "machine_total", len(PLANT))
    assert "There's no machine called MILL-99 in this plant." in text
    assert "The machines here are:" not in text, (
        "the sentence that claimed to be the plant is back")
    assert "15 machines" in text, "the total is not stated"


def test_the_nearest_machines_are_offered_and_they_are_the_right_ones():
    """Item 3(c). Alphabetical-first dropped MILL-01 and MILL-02, the two names a
    planner typing MILL-99 most plausibly meant. Nearest-first must surface them."""
    near = _nearest_names("MILL-99", PLANT, 4)
    assert near[:2] == ["MILL-01", "MILL-02"], near
    text = _render_unknown("MILL-99", "machine", near, "machine_total", len(PLANT))
    assert "Did you mean MILL-01" in text


def test_no_near_match_offers_nothing_rather_than_guessing():
    """Below the similarity floor nothing is proposed — a guess dressed as a
    correction is worse than an honest count. The count still travels."""
    near = _nearest_names("ZZZZZZZZ-42", PLANT, 4)
    assert near == [], near
    text = _render_unknown("ZZZZZZZZ-42", "machine", near, "machine_total", len(PLANT))
    assert "Did you mean" not in text
    assert "15 machines" in text


def test_the_order_branch_carries_its_total_too():
    """Item 3(b) applied to the sibling branch. "Orders I do have include: …"
    over a [:6] head slice never claimed completeness, but gave no total either,
    so a planner could not tell six orders from six hundred."""
    orders = [f"ORD-{i:06d}" for i in range(1, 41)]
    near = _nearest_names("ORD-000099", orders, 6)
    text = _render_unknown("ORD-000099", "order", near, "order_total", len(orders))
    # Session 4B.21: "known" names the SET. This is every order the plan
    # carries, placed or not; the opener's count on the same board is the
    # placed subset, and neither surface said which before the ruling.
    assert "40 known orders in this plan" in text
    assert "Orders I do have include:" not in text


# ===========================================================================
# THE PREMISE TESTS — the fixture must be able to produce the condition
# ===========================================================================

def test_premise_the_fixture_is_large_enough_to_force_a_cut():
    """The old code cut machines at 8 and orders at 6. A fixture at or below
    those sizes could never show a truncation, and every assertion above would
    pass while proving nothing (4B.18's lesson, verbatim)."""
    assert len(PLANT) > 8, "the machine fixture cannot exercise a cut"
    assert len(_nearest_names("MILL-99", PLANT, 4)) < len(PLANT), (
        "the near-match sample is not smaller than the plant, so nothing is "
        "being truncated in this test at all")


def test_premise_the_old_shape_would_have_failed_these_assertions():
    """The negative control, stated as data: reconstruct the exact sentence 4B.17
    measured and prove this file's assertions reject it. Without this, a rewrite
    that merely reworded the lead would pass."""
    old = ("There's no machine called MILL-99 in this plant.\n"
           "The machines here are: " + ", ".join(sorted(PLANT)[:8]) + ".")
    assert "The machines here are:" in old
    assert "15 machines" not in old
    assert "PRESS-FAST" not in old, (
        "the specimen must omit the machine the asked order is actually on — "
        "that omission is what made it a truth failure rather than a style one")


# ===========================================================================
# THE NEAREST-MATCH HELPER — determinism, and the pilot-density claim
# ===========================================================================

def test_nearest_names_is_deterministic():
    """Ties break alphabetically; no set iteration reaches the output."""
    first = _nearest_names("MILL-99", PLANT, 4)
    for _ in range(20):
        assert _nearest_names("MILL-99", list(reversed(PLANT)), 4) == first


def test_nearest_names_scales_to_pilot_volume():
    """Item 3(d). docs/07 §5a records 174 workcenters across the real book, where
    enumerating the plant is useless copy at ANY cut-off. Nearest-first is O(n)
    over the names and its OUTPUT does not grow with the plant — which is the
    whole reason it was chosen over a capped list."""
    big = [f"WC-{i:04d}" for i in range(174)]
    near = _nearest_names("WC-0042", big, 4)
    assert near[0] == "WC-0042"
    assert len(near) == 4, "the offer must stay bounded at pilot volume"


@pytest.mark.parametrize("typed", ["", "   "])
def test_nearest_names_on_an_empty_mention(typed):
    assert _nearest_names(typed, PLANT, 4) == []

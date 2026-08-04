"""R-TG2/R-TG3/R-TG4 — THE DEPTH LICENCE AND THE TEACHING INTENT
(Session 4A teaching-graft (b)).

Written from the rulings, not from the implementation.

WHAT THE RULINGS SAY.

R-TG2 — THE TEACHING INTENT. A question whose goal is UNDERSTANDING joins the
closed vocabulary as `teaching`. It is a SECOND-TIER intent, not a route:
teaching is synthesis with a second claim class (R-TG1, session (a)) and a depth
licence, not a new rung. Measured at HEAD, ten domain probes on the demo board:
`coaching` 5 / `unmatched` 4 / `lateness-cause` 1 — half of them answered as
capability lookups in three lines. A teaching question that ALSO names something
on the board is the MIXED case: it grounds first and teaches second.

R-TG3 — THE DEPTH LICENCE. Depth is granted by intent, never assumed. TEACHING
gets the LONG budget and every other second-tier question gets the SHORT one.
The bound lives at the DISPATCH SEAM, not in prompt exhortation — measured, the
prompt's "three to six claims" instruction leaves 38% of real answers at five or
six. What the seam withholds it DISCLOSES, and what it did not withhold it must
not claim to have: a closer on an uncut answer is a false disclosure.

R-TG4 — AUDIENCE SHAPE. When a question names a HUMAN GOAL the answer leads with
the account, then the lever, then OFFERS the inventory. Evidence discipline is
unchanged — `ordered_records` survives, the bars still light, the drill-down
still opens exactly what was offered. What changes is ORDER and BUDGET.

WHAT THIS FILE DOES NOT PROVE. That the model NAMES `teaching` well, or reports
`audience` reliably — those are the prompt's job and the bank's measurement (and
R-TG4 has a deterministic floor precisely because 4A.y measured that a fresh
field is reported 0 times in 5). These guards prove the seam holds whatever the
model does.
"""
from __future__ import annotations

import json

import pytest

from mre.contracts.parse import Intent, SECOND_TIER_INTENTS
from mre.contracts.synthesis import (
    ClaimKind,
    ClaimStatus,
    LONG_CLAIM_BUDGET,
    SHORT_CLAIM_BUDGET,
    SynthesisAnswer,
    VerifiedClaim,
)
from mre.modules import answer_budget
from mre.modules.ask_fallback_copy import (
    AUDIENCE_LEAD,
    AUDIENCE_LEVER_HEADER,
    SYNTHESIS_DEFERRED,
    SYNTHESIS_DEFERRED_ONE,
    TEACHING_INVITATION,
)
from mre.modules.audience_shape import compose, names_an_audience
from mre.modules.evidence_index import EvidenceIndex
from mre.modules.explainer import ROUTE_TAXONOMY, Explainer
from mre.modules.interpreter import run_ask, tier_of
from mre.modules.renderers import TemplateRenderer
from tests.parse_doubles import (
    ScriptedParser,
    claim,
    claims,
    parsed,
    synthesizer_with,
)
from tests.test_synthesis import _records, _Store

GENERAL = "Tardiness objectives tend to give weak lower bounds."


@pytest.fixture()
def world(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    with open(runs / "t.jsonl", "w", encoding="utf-8") as fh:
        for r in _records():
            fh.write(json.dumps(r) + "\n")
    return Explainer(_Store(), EvidenceIndex().build(runs), snapshot_id="snap-t")


def _answer(n: int, *, conclusion_at: int | None = None) -> SynthesisAnswer:
    """A verified answer of ``n`` claims, already labeled — the seam only ever
    sees claims that have been through the verifier."""
    out = []
    for i in range(n):
        kind = (ClaimKind.CONCLUSION if conclusion_at == i else ClaimKind.FACT)
        out.append(VerifiedClaim(text=f"claim {i}", status=ClaimStatus.INTERPRETIVE,
                                 kind=kind))
    return SynthesisAnswer(question="q", claims=out)


def _render(bundle) -> str:
    return TemplateRenderer().render(bundle)


def _ask(world, question, p, *, responses, **kw):
    return run_ask(world, question, parser=ScriptedParser({question: p}),
                   synthesizer=synthesizer_with(responses), **kw)


# ===========================================================================
# R-TG2 — the teaching intent
# ===========================================================================

class TestTheTeachingIntent:
    def test_teaching_is_a_second_tier_intent_and_not_a_route(self):
        """The ruling's shape, asserted as a shape. A `teaching` entry in the
        route taxonomy would make it reachable two ways and it would answer
        differently in each — a contracted assembler authoring domain prose as
        testimony, which is R-TG1's defect one layer up."""
        assert Intent.TEACHING in SECOND_TIER_INTENTS
        assert Intent.TEACHING.value not in ROUTE_TAXONOMY

    def test_unmatched_is_named_rather_than_subtracted(self):
        """`unmatched` was always a second-tier door; the set gives it a name so
        `teaching` could join it rather than becoming a second exception."""
        assert Intent.UNMATCHED in SECOND_TIER_INTENTS

    def test_a_teaching_question_reaches_the_second_tier(self, world):
        r = _ask(world, "what is a bottleneck machine",
                 parsed("what is a bottleneck machine", Intent.TEACHING),
                 responses=[claims(claim(GENERAL, [], "general_knowledge"))])
        assert r.route == "synthesis"
        assert r.register == "synthesis"

    def test_the_pacing_hint_shows_the_reasoning_state(self):
        """`teaching` reasons over the evidence exactly as `unmatched` does, so
        the preflight must promise a read rather than an instant answer."""
        assert tier_of(parsed("q", Intent.TEACHING)) == "synthesis"

    def test_a_contracted_intent_still_cannot_fall_to_the_tier(self, world):
        """The seal, unchanged in the direction that matters. Adding a declared
        door must not open an undeclared one."""
        r = _ask(world, "which orders are late",
                 parsed("which orders are late", Intent.LATE_ORDERS),
                 responses=[claims(claim(GENERAL, [], "general_knowledge"))])
        assert r.route == "late-orders"


# ===========================================================================
# R-TG3 — the depth licence at the seam
# ===========================================================================

class TestTheDepthLicence:
    def test_teaching_is_the_only_long_budget(self):
        assert answer_budget.licence_for(Intent.TEACHING).max_claims == \
            LONG_CLAIM_BUDGET
        for intent in (Intent.UNMATCHED, Intent.LATE_ORDERS, Intent.ADVICE, None):
            assert answer_budget.licence_for(intent).max_claims == \
                SHORT_CLAIM_BUDGET

    def test_the_short_budget_trims_and_the_surplus_is_deferred(self):
        a = answer_budget.apply(_answer(6),
                                answer_budget.licence_for(Intent.UNMATCHED))
        assert [c.text for c in a.claims] == ["claim 0", "claim 1", "claim 2",
                                              "claim 3"]
        assert [c.text for c in a.deferred] == ["claim 4", "claim 5"]

    def test_a_deferred_claim_is_never_a_cut_claim(self):
        """The category split IS the ruling. A cut claim failed verification; a
        deferred one passed it and is true. One word over both is the fusion
        this repo has now named six times."""
        a = answer_budget.apply(_answer(6),
                                answer_budget.licence_for(Intent.UNMATCHED))
        assert a.cut == []
        assert a.counts()["deferred"] == 2
        assert a.counts()["failed_and_cut"] == 0
        # And the total still counts every sentence that was drafted.
        assert a.counts()["claims"] == 6

    def test_an_answer_inside_its_budget_is_untouched(self):
        a = answer_budget.apply(_answer(4),
                                answer_budget.licence_for(Intent.UNMATCHED))
        assert len(a.claims) == 4
        assert a.deferred == []

    def test_the_conclusion_is_never_trimmed(self):
        """Clause (2). An answer whose conclusion was dropped for length is worse
        than one line longer."""
        a = answer_budget.apply(_answer(6, conclusion_at=5),
                                answer_budget.licence_for(Intent.UNMATCHED))
        assert [c.text for c in a.claims] == ["claim 0", "claim 1", "claim 2",
                                              "claim 5"]
        assert a.claims[-1].kind is ClaimKind.CONCLUSION
        # The displaced claim is DEFERRED, never lost.
        assert [c.text for c in a.deferred] == ["claim 3", "claim 4"]

    def test_a_conclusion_already_inside_the_budget_does_not_reorder(self):
        a = answer_budget.apply(_answer(6, conclusion_at=1),
                                answer_budget.licence_for(Intent.UNMATCHED))
        assert [c.text for c in a.claims] == ["claim 0", "claim 1", "claim 2",
                                              "claim 3"]

    def test_no_sentence_is_ever_rewritten(self):
        """Clause (1). The seam trims; it is not a second author, and every claim
        it handles has already been through verification."""
        before = _answer(6)
        texts = [c.text for c in before.claims]
        a = answer_budget.apply(before, answer_budget.licence_for(Intent.UNMATCHED))
        assert [c.text for c in a.claims + a.deferred] == texts

    def test_the_durable_record_carries_every_drafted_sentence(self):
        """The ledger is the record of what the tier DRAFTED and what it could
        prove. A deferred claim was drafted and verified; omitting it would make
        the record report fewer sentences than the tier wrote."""
        from mre.contracts.synthesis import SynthesisProvenance
        a = answer_budget.apply(_answer(6),
                                answer_budget.licence_for(Intent.UNMATCHED))
        rows = SynthesisProvenance.of(a).claims
        assert len(rows) == 6
        assert [r["deferred"] for r in rows] == [False] * 4 + [True] * 2

    def test_applying_twice_defers_nothing_more(self):
        lic = answer_budget.licence_for(Intent.UNMATCHED)
        a = answer_budget.apply(answer_budget.apply(_answer(6), lic), lic)
        assert len(a.claims) == 4
        assert len(a.deferred) == 2

    def test_the_long_budget_does_not_bind_at_six(self):
        """LONG is a CEILING, not a target — and it is stated rather than hidden
        that under synthesis prompt v6/v7 the model has never drafted more than
        six claims in 86 measured answers."""
        a = answer_budget.apply(_answer(6),
                                answer_budget.licence_for(Intent.TEACHING))
        assert len(a.claims) == 6
        assert a.deferred == []

    def test_the_long_budget_still_binds_somewhere(self):
        a = answer_budget.apply(_answer(LONG_CLAIM_BUDGET + 2),
                                answer_budget.licence_for(Intent.TEACHING))
        assert len(a.claims) == LONG_CLAIM_BUDGET
        assert len(a.deferred) == 2


class TestTheCloserDiscloses:
    def _six_claim_answer(self, world, intent):
        q = "why might tardiness cluster on bottleneck machines"
        return _ask(world, q, parsed(q, intent),
                    responses=[claims(*[claim(f"{GENERAL} ({i})", [],
                                              "general_knowledge")
                                        for i in range(6)])])

    def test_the_short_budget_cuts_live_and_the_closer_names_the_count(
            self, world):
        r = self._six_claim_answer(world, Intent.UNMATCHED)
        text = _render(r.bundle)
        assert len(r.synthesis.claims) == 4
        assert len(r.synthesis.deferred) == 2
        assert SYNTHESIS_DEFERRED.format(n=2) in text

    def test_the_closer_is_absent_when_nothing_was_withheld(self, world):
        """The negative of clause (3), and the one that keeps the closer
        honest: it must never tell a planner there is more when there is not."""
        q = "why might tardiness cluster on bottleneck machines"
        r = _ask(world, q, parsed(q, Intent.UNMATCHED),
                 responses=[claims(claim(GENERAL, [], "general_knowledge"))])
        text = _render(r.bundle)
        assert "more point" not in text
        assert SYNTHESIS_DEFERRED_ONE not in text

    def test_one_withheld_point_is_singular(self, world):
        q = "why might tardiness cluster on bottleneck machines"
        r = _ask(world, q, parsed(q, Intent.UNMATCHED),
                 responses=[claims(*[claim(f"{GENERAL} ({i})", [],
                                           "general_knowledge")
                                     for i in range(5)])])
        assert SYNTHESIS_DEFERRED_ONE in _render(r.bundle)

    def test_a_teaching_answer_is_not_capped_and_invites_push_back(self, world):
        r = self._six_claim_answer(world, Intent.TEACHING)
        text = _render(r.bundle)
        assert len(r.synthesis.claims) == 6
        assert r.synthesis.deferred == []
        assert "more point" not in text
        assert TEACHING_INVITATION in text

    def test_a_short_answer_carries_no_teaching_invitation(self, world):
        r = self._six_claim_answer(world, Intent.UNMATCHED)
        assert TEACHING_INVITATION not in _render(r.bundle)


class TestTheMixedCase:
    def test_a_teaching_question_that_names_the_board_grounds_first(self, world):
        """R-TG2's both-ways clause. The teaching budget is granted, AND the
        board claim the model drafted keeps its citation and its position ahead
        of the general one — the answer grounds, then teaches."""
        q = "why is ORD-01 late, and how does lateness normally compound"
        p = parsed(q, Intent.TEACHING, orders=("ORD-01",))
        board = "ORD-01 finishes 890 minutes after its due date."
        r = _ask(world, q, p, responses=[
            json.dumps({"tool": "lateness_set", "args": {}}),
            claims(claim(board, [], "fact"),
                   claim(GENERAL, [], "general_knowledge"))])
        text = _render(r.bundle)
        assert board in text and GENERAL in text
        assert text.index(board) < text.index(GENERAL)
        # And the general line still wears its own label, not a board marker.
        assert "general knowledge" in text.split(GENERAL)[1].split("\n")[0]


# ===========================================================================
# R-TG4 — audience shape
# ===========================================================================

class TestTheAudienceMarker:
    @pytest.mark.parametrize("q,expect", [
        ("there are a lot of orders late what reason can i give my boss and "
         "what will help lessen the impact", "my boss"),
        ("what should i tell the customer about ORD-01", "the customer"),
        ("what do i say in the production meeting tomorrow",
         "the production meeting"),
        ("how do i explain this to the plant manager", "the plant manager"),
        ("what do i tell them about the delay", "them"),
    ])
    def test_it_returns_the_planners_own_words(self, q, expect):
        assert names_an_audience(q) == expect

    @pytest.mark.parametrize("q", [
        "in general, what makes a scheduling problem hard to prove optimal",
        "how do schedulers normally decide which job to run first",
        "which order carries the largest tardiness cost",
        "why is ORD-01 placed here",
        "what is running on CUT-01",
        # NAMES NOBODY, and correctly does not fire: "what should I do" could be
        # a planner thinking out loud, and reshaping an answer on that guess is
        # exactly the false positive the pattern is built to avoid.
        "what should i do about all this lateness",
        "what do i say about the late orders",
    ])
    def test_it_stays_silent_on_every_other_family(self, q):
        """Specificity is the axis that matters: a MISSED audience leaves the
        answer exactly as it is today, and a FALSE one reshapes an answer nobody
        asked to have reshaped. Measured 0 hits across 20 non-goal probes."""
        assert names_an_audience(q) == ""


class TestTheAudienceShape:
    KF = {
        "late_count": 102, "scheduled_order_count": 158,
        "cause_mix": [{"cause": "the machine was busy with other work",
                       "orders": ["ORD-01"] * 59}],
        "tardiness_lines": [{"order": "ORD-91", "cost": 147776.67}],
        "causes": [{"order": "ORD-91",
                    "blocked_by": {"machine": "CUT-02", "until": "2026-01-08 08:57",
                                   "blocker_order": "ORD-219"}},
                   {"order": "ORD-02", "blocked_by": {"machine": "CUT-02",
                                                      "until": "x",
                                                      "blocker_order": "y"}}],
    }

    def test_it_composes_an_account_a_lever_and_an_offer(self):
        shape = compose("lateness_cause", self.KF, "my boss")
        assert shape is not None and shape.usable
        assert "102 of the 158" in shape.account
        assert "ORD-91" in shape.lever and "147,776.67" in shape.lever
        assert any("CUT-02" in d for d in shape.lever_detail)
        assert "2 orders" in shape.offer

    def test_no_audience_composes_nothing(self):
        assert compose("lateness_cause", self.KF, "") is None

    def test_an_unknown_shape_fails_open(self):
        """A floor that could blank an answer would be worse than the verbosity
        it exists to fix."""
        assert compose("downtime", self.KF, "my boss") is None

    def test_a_board_with_nothing_late_composes_nothing(self):
        assert compose("lateness_cause", {"late_count": 0}, "my boss") is None

    def test_the_lever_is_the_routes_own_take(self):
        """R-TG4 in one line: the "My take:" content, promoted from afterthought
        to headline. Measured on the demo board, `advice` buried exactly the
        sentence the boss question needed as its TWELFTH line."""
        take = ("ORD-000112's slip traces to ORD-000252 holding CUT-01 — "
                "pulling that earlier is the single biggest lever.")
        shape = compose("advice", {"opener_top": {"headline": "102 late",
                                                  "detail": ["x"],
                                                  "pointer": "ask about it"},
                                   "take": take}, "my boss")
        assert shape is not None
        assert shape.account == "102 late"
        assert shape.lever == take
        # THE ITEM'S DETAIL BELONGS TO THE ACCOUNT, NOT THE LEVER. Found live:
        # an optimality-bound line rendered under "the single biggest lever this
        # board evidences", beside a sentence about a different order.
        assert shape.account_detail == ("x",)
        assert shape.lever_detail == ()

    def test_a_route_with_no_take_claims_no_lever(self):
        """A ranking claim over facts nothing ranked is the assertion R-AI3
        forbids. `briefing` computes no take, so it announces none."""
        shape = compose("briefing", {"opener": [{"headline": "h",
                                                 "detail": ["d"],
                                                 "clean": False}]}, "my boss")
        assert shape is not None and shape.lever == ""
        assert shape.account_detail == ("d",)


class TestTheBossQuestion:
    """The measured specimen, end to end on the real dispatch."""

    Q = ("there are a lot of orders late what reason can i give my boss and "
         "what will help lessen the impact")

    def _render_boss(self, world, *, audience=""):
        p = parsed(self.Q, Intent.LATENESS_CAUSE, audience=audience)
        r = run_ask(world, self.Q, parser=ScriptedParser({self.Q: p}))
        return r, _render(r.bundle)

    def test_it_leads_with_the_account_not_the_inventory(self, world):
        r, text = self._render_boss(world)
        head = text.split("\n\n")[0]
        assert AUDIENCE_LEAD.format(audience="my boss") in head
        assert "Where the hold is concrete" not in text

    def test_the_lever_is_the_headline_not_the_afterthought(self, world):
        _r, text = self._render_boss(world)
        assert AUDIENCE_LEVER_HEADER in text
        # ...and it comes BEFORE the offer, which is the whole reordering.
        assert text.index(AUDIENCE_LEVER_HEADER) < text.index("Ask for it")

    def test_the_inventory_is_offered_never_printed(self, world):
        _r, text = self._render_boss(world)
        assert "Evidence chain" not in text
        assert "breakdown" in text

    def test_the_evidence_survives_the_reshaping(self, world):
        """The half that matters. `ordered_records` is SUPPRESSED, not CLEARED:
        the same bars light and a drill-down opens exactly the records the offer
        line just offered. Nothing about the evidence changed — only whether it
        is printed unasked."""
        r, _text = self._render_boss(world)
        assert r.bundle.ordered_records

    def test_the_parse_report_reaches_the_same_shape(self, world):
        """The floor is a FLOOR: where the model DOES report the field, the
        answer is the same. R-AI5(8) — the parse reports, the dispatch decides,
        and here they agree by construction."""
        _r, floored = self._render_boss(world)
        _r2, reported = self._render_boss(world, audience="my boss")
        assert floored == reported

    def test_shortening_the_answer_does_not_shorten_its_honesty(self, world):
        """The excluded-orders note is an UNPROMPTED disclosure (CU9), not part
        of the inventory being deferred: an order dropped from the plan is a
        qualification ON the answer, not a detail behind it. It survives the
        reshaping, exactly as the cost-proof rider does."""
        p = parsed(self.Q, Intent.LATENESS_CAUSE)
        r = run_ask(world, self.Q, parser=ScriptedParser({self.Q: p}))
        r.bundle.key_facts["excluded_summary"] = {
            "count": 2, "scheduled": 8, "total": 10,
            "orders": ["ORD-77", "ORD-78"]}
        text = _render(r.bundle)
        assert "2 excluded" in text
        assert "ORD-77" in text

    def test_a_question_naming_nobody_is_untouched(self, world):
        """The control. Without an audience the route renders exactly as it has
        since 4A.5c — the cause mix, the concrete holds, the money."""
        q = "why are so many orders late"
        r = run_ask(world, q, parser=ScriptedParser(
            {q: parsed(q, Intent.LATENESS_CAUSE)}))
        text = _render(r.bundle)
        assert AUDIENCE_LEAD.split("{")[0] not in text
        assert AUDIENCE_LEVER_HEADER not in text


class TestControls:
    def test_a_testimony_route_reaches_no_cap_machinery(self, world):
        """Authored templates are already their own budget; the cap is a
        property of the second tier and must be unreachable from testimony."""
        q = "why is ORD-01 late"
        r = run_ask(world, q, parser=ScriptedParser(
            {q: parsed(q, Intent.LATE_ORDER, orders=("ORD-01",))}))
        text = _render(r.bundle)
        assert r.register == "testimony"
        assert "more point" not in text
        assert TEACHING_INVITATION not in text

    def test_the_general_knowledge_class_is_unchanged_by_the_budget(self, world):
        """(a)'s specimens keep their class behaviour: a general line under the
        short budget still wears the marker and still carries no record ids."""
        q = "why might tardiness cluster on bottleneck machines"
        r = _ask(world, q, parsed(q, Intent.UNMATCHED),
                 responses=[claims(claim(GENERAL, [], "general_knowledge"))])
        assert r.synthesis.claims[0].status is ClaimStatus.GENERAL_KNOWLEDGE
        assert r.synthesis.claims[0].cited_record_ids == []
        assert "general knowledge" in _render(r.bundle)

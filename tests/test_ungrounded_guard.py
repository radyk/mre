"""THE ZERO-TOOL-CALL GUARD (Errand 4B.15a, rider).

THE SPECIMEN, restated because the test only makes sense with it: 4B.15's tier
bench asked "which machine is carrying the most work in this window" and Opus
answered by naming three machines that do not exist in this plant, having made
ZERO tool calls. Every sentence was correctly labelled unsupported. It shipped
anyway — labelling is the tier's contract, withholding was not.

WHAT IS PINNED HERE

  TestTheSpecimen        the measured failure is withheld, and the invented names
                         do not survive into the withholding text either.
  TestNegativeControl    an answer that legitimately needs no tools STILL SHIPS.
                         Without this the guard is just a mute button for the
                         second tier, and the honest floor ("I can't forecast the
                         weather") is exactly the answer a mute button eats.
  TestDoesNotOverreach   the planner's own words are not the tier's invention; a
                         resolved citation is evidence of reading; a contracted
                         route is never touched.
  TestBothRenderers      both delivery seams or neither.
"""
from __future__ import annotations

from mre.modules.explainer import ExplanationBundle
from mre.modules.renderers import LLMRenderer, TemplateRenderer
from mre.modules.ungrounded_guard import apply_unread_guard, unread_claims

FOOTER = "\n[rendered by: synthesis (claude-sonnet-5) — 0 tool call(s) | register: synthesis]"


def bundle(*, claims, question="which machine is carrying the most work",
           tool_calls=0, records=(), subject_type="synthesis"):
    return ExplanationBundle(
        question=question,
        subject_id="synthesis",
        subject_type=subject_type,
        subject_external_name="?",
        ordered_records=list(records),
        key_facts={"claims": [{"text": t, "status": "interpretive",
                               "cited_record_ids": []} for t in claims],
                   "tool_call_count": tool_calls,
                   "asked_question": question,
                   "model": "claude-sonnet-5"},
        snapshot_id="snap-t",
    )


class TestTheSpecimen:
    #: Verbatim in shape: three machine names this plant does not have, no reads.
    FABRICATION = ("MILL-03 is carrying the most work in this window.",
                   "GRIND-02 and DRILL-07 are close behind it.")

    def test_a_zero_tool_answer_naming_this_plant_is_withheld(self):
        b = bundle(claims=self.FABRICATION)
        assert unread_claims(b) == ["DRILL-07", "GRIND-02", "MILL-03"]
        text = TemplateRenderer().render(b)
        assert "MILL-03" not in text
        assert "GRIND-02" not in text and "DRILL-07" not in text

    def test_the_withholding_says_why_without_repeating_the_invention(self):
        text = TemplateRenderer().render(bundle(claims=self.FABRICATION))
        assert "without reading anything from this schedule" in text
        # Same discipline as SYNTHESIS_UNGROUNDED: the apology must not put the
        # unproven thing in front of the planner a second time.
        assert "MILL" not in text

    def test_the_footer_survives_and_still_reads_zero_tool_calls(self):
        out = apply_unread_guard(bundle(claims=self.FABRICATION),
                                 "the draft body" + FOOTER)
        assert out is not None
        assert out.endswith(FOOTER)
        assert "0 tool call(s)" in out
        assert "register: synthesis" in out

    def test_a_fabricated_citation_is_not_a_free_pass(self):
        # A model that invents record ids alongside its machines gains nothing:
        # the assembler resolves ids against the real index, so a fabricated one
        # lands in NO ordered_records at all.
        b = bundle(claims=self.FABRICATION, records=())
        b.key_facts["claims"][0]["cited_record_ids"] = ["not-a-real-record-id"]
        assert unread_claims(b)

    def test_money_and_dates_count_as_claims_about_this_world(self):
        assert unread_claims(bundle(claims=("It will cost $4,120.00 to fix.",)))
        assert unread_claims(bundle(claims=("That finishes 2026-01-14.",)))
        assert unread_claims(bundle(claims=("It starts at 07:00.",)))


class TestNegativeControl:
    """A SYNTHESIS ANSWER THAT LEGITIMATELY NEEDS NO TOOLS MUST STILL PASS.

    The bench's own floor question is the control: "what will the weather be on
    delivery day" has no answer in any evidence store, and the right response
    reads nothing and says so. A guard that eats this has replaced a fabrication
    problem with a silence problem."""

    def test_the_weather_floor_ships_untouched(self):
        b = bundle(claims=("Nothing in a production schedule carries weather; I "
                           "have no forecast to read.",),
                   question="what will the weather be on delivery day")
        assert unread_claims(b) == []
        text = TemplateRenderer().render(b)
        assert "no forecast to read" in text
        assert "without reading anything" not in text

    def test_a_general_statement_about_the_product_ships(self):
        b = bundle(claims=("I can only speak to what this plan records, not to "
                           "what your customer will accept.",),
                   question="will the customer be happy")
        assert apply_unread_guard(b, "body" + FOOTER) is None

    def test_a_bare_count_is_not_a_world_token(self):
        # "one of two ways" must not trip the guard: a plain integer is prose,
        # not a claim about this plan. Only identifiers, money, dates and clock
        # times are world-specific.
        b = bundle(claims=("There are two ways to read that question.",))
        assert unread_claims(b) == []

    def test_the_honest_no_claims_floor_ships(self):
        b = bundle(claims=())
        assert unread_claims(b) == []
        text = TemplateRenderer().render(b)
        assert "couldn't answer that one" in text


class TestDoesNotOverreach:
    def test_a_token_the_planner_supplied_is_not_an_invention(self):
        b = bundle(claims=("ORD-000013 looks like the one to watch.",),
                   question="what should I do about ORD-000013")
        assert unread_claims(b) == []

    def test_one_read_is_enough_to_ship(self):
        assert unread_claims(bundle(claims=("MILL-03 is busiest.",),
                                    tool_calls=1)) == []

    def test_a_resolved_citation_is_evidence_of_reading(self):
        b = bundle(claims=("MILL-03 is busiest.",),
                   records=[{"record_id": "dec-1", "record_type": "decision"}])
        assert unread_claims(b) == []

    def test_a_contracted_route_is_never_touched(self):
        # Routes read the snapshot by construction and make no tool calls at all;
        # a guard that fired on them would withhold every deterministic answer.
        b = bundle(claims=("MILL-03 is busiest.",), subject_type="machine_load")
        assert unread_claims(b) == []

    def test_an_older_bundle_without_the_count_fails_open(self):
        b = bundle(claims=("MILL-03 is busiest.",))
        del b.key_facts["tool_call_count"]
        assert unread_claims(b) == []

    def test_a_broken_bundle_never_breaks_the_answer(self):
        class Odd:
            subject_type = "synthesis"
            key_facts = "not a dict"
        from mre.modules.renderers import apply_unread_guard as seam
        assert seam(Odd(), "body") is None


class TestBothRenderers:
    """Both delivery seams or neither — a reword must not launder an answer that
    read nothing, exactly as it must not launder an unproven cost claim."""

    def test_the_llm_renderer_withholds_too(self):
        class _Boom:
            messages = property(lambda self: self)

            def create(self, **kw):  # pragma: no cover - must never be reached
                raise AssertionError("the synthesis body reached the LLM renderer")

        b = bundle(claims=TestTheSpecimen.FABRICATION)
        text = LLMRenderer(_client=_Boom()).render(b)
        assert "MILL-03" not in text
        assert "without reading anything from this schedule" in text

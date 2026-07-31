"""The labeled-synthesis tier — tools, loop, verification, surface (Session 4A.5b).

Written from R-AI5(2)/(3)/(4)/(8) and the session brief, against a small but REAL
world: a snapshot reader with entities, an evidence index with records, and an
identity map — so the tools read the way they read in production and the verifier
re-fetches the way it re-fetches in production. Nothing about a verdict is faked.

What each class pins:

  TestToolSurface        the closed set, its governed enumeration, the budget, and
                         that every row carries the ids a claim can cite.
  TestClaimVerification  the outcome taxonomy, one hand-built draft per outcome —
                         including the fabricated-id draft (the ordinal disease)
                         and the correct-but-uncited claim that must NOT be
                         promoted.
  TestSynthesisLoop      the loop under budget, and the seal between the tiers: a
                         MATCHED intent can never reach synthesis, an UNMATCHED one
                         never guesses a route.
  TestAnswerSurface      claim blocks with per-claim provenance, the register, the
                         rendered-by line naming the tier and the tool-call count,
                         and "prove it".
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mre.contracts.parse import FollowupKind, Intent, SubjectKind
from mre.contracts.synthesis import (
    ClaimKind, ClaimStatus, DraftClaim, MAX_TOOL_CALLS, TOOL_ARGS, TOOL_MEANINGS,
    ToolName,
)
from mre.modules.claim_verifier import verify_claim, verify_draft
from mre.modules.evidence_index import EvidenceIndex
from mre.modules.evidence_tools import EvidenceToolbox
from mre.modules.explainer import Explainer
from mre.modules.interpreter import SynthesisMemory, dispatch, run_ask
from mre.modules.renderers import TemplateRenderer
from tests.parse_doubles import (
    DeadSynthesizer, ScriptedParser, cannot_answer, claim, claims, parsed,
    resolve, synthesizer_with, tool_call,
)

# ---------------------------------------------------------------------------
# A small real world: two orders on one machine, one of them late.
# ---------------------------------------------------------------------------

D1 = "11111111-1111-5111-8111-111111111111"      # ORD-01, 890 min late
D2 = "22222222-2222-5222-8222-222222222222"      # ORD-02, early
R1 = "33333333-3333-5333-8333-333333333333"      # CUT-01
OP1, OP2 = "aaa11111-1111-5111-8111-111111111111", "bbb22222-2222-5222-8222-222222222222"
WP1, WP2 = "wp-1", "wp-2"
A1, A2 = "asg-1", "asg-2"
S1, S2 = "svc-1", "svc-2"

REC_DEC1 = "dec-1111-aaaa-bbbb-cccccccccccc"
REC_DEC2 = "dec-2222-aaaa-bbbb-cccccccccccc"
REC_LATE1 = "met-late-1111-bbbb-cccccccccccc"
REC_LATE2 = "met-late-2222-bbbb-cccccccccccc"
REC_FIND = "fnd-1111-aaaa-bbbb-cccccccccccc"


def _records() -> list[dict]:
    return [
        {"record_type": "run_context_open", "run_id": "run-m7", "module": "M7",
         "snapshot_id": "snap-t", "purpose": "test",
         "timestamp": "2026-07-26T00:00:00Z"},
        {"record_type": "decision", "record_id": REC_DEC1, "run_id": "run-m7",
         "module": "M7", "seq": 1, "snapshot_id": "snap-t",
         "subjects": [{"entity_id": OP1, "entity_type": "operation"}],
         "tier": "supporting",
         "message": "Operation assigned (2026-01-06T07:00:00+00:00 -> "
                    "2026-01-06T14:50:00+00:00). Cost: 470.00.",
         "decision_type": "assignment", "driver": "CAPACITY_BLOCKED",
         "basis": "reconstructed", "chosen": {"resource_id": R1}, "alternatives": []},
        {"record_type": "decision", "record_id": REC_DEC2, "run_id": "run-m7",
         "module": "M7", "seq": 2, "snapshot_id": "snap-t",
         "subjects": [{"entity_id": OP2, "entity_type": "operation"}],
         "tier": "supporting",
         "message": "Operation assigned (2026-01-05T07:00:00+00:00 -> "
                    "2026-01-05T11:00:00+00:00). Cost: 220.00.",
         "decision_type": "assignment", "driver": "CALENDAR_WINDOW",
         "basis": "reconstructed", "chosen": {"resource_id": R1}, "alternatives": []},
        {"record_type": "metric", "record_id": REC_LATE1, "run_id": "run-m7",
         "module": "M7", "seq": 3, "snapshot_id": "snap-t",
         "subjects": [{"entity_id": D1, "entity_type": "demand"}],
         "tier": "supporting", "message": "", "name": "lateness_minutes",
         "value": 890.0, "unit": "minutes", "rollup_of": []},
        {"record_type": "metric", "record_id": REC_LATE2, "run_id": "run-m7",
         "module": "M7", "seq": 4, "snapshot_id": "snap-t",
         "subjects": [{"entity_id": D2, "entity_type": "demand"}],
         "tier": "supporting", "message": "", "name": "lateness_minutes",
         "value": -600.0, "unit": "minutes", "rollup_of": []},
        {"record_type": "finding", "record_id": REC_FIND, "run_id": "run-m7",
         "module": "M0", "seq": 5, "snapshot_id": "snap-t", "subjects": [],
         "code": "LOW_CONFIDENCE_INPUT", "severity": "warning",
         "disposition": "proceeded_flagged", "message": "a rate was defaulted"},
        {"record_type": "run_context_close", "run_id": "run-m7",
         "status": "success", "ended_at": "2026-07-26T00:01:00Z"},
    ]


class _Reader:
    def get_entity(self, entity_id):
        for kind in ("demand", "assignment", "serviceoutcome", "resource",
                     "operation", "calendar", "schedule"):
            for e in self.iter_entities(kind):
                if e.get("id") == entity_id:
                    return e
        return None

    def iter_entities(self, entity_type):
        if entity_type == "demand":
            yield {"id": D1, "due": "2026-01-05T23:59:59Z", "quantity": {"value": 50.0},
                   "external_refs": [{"system": "IDS", "type": "order_id",
                                      "value": "ORD-01"}]}
            yield {"id": D2, "due": "2026-01-20T23:59:59Z", "quantity": {"value": 20.0},
                   "external_refs": [{"system": "IDS", "type": "order_id",
                                      "value": "ORD-02"}]}
        elif entity_type == "operation":
            yield {"id": OP1, "workpackage_ref": WP1, "sequence": 10, "setup_family": ""}
            yield {"id": OP2, "workpackage_ref": WP2, "sequence": 10, "setup_family": ""}
        elif entity_type == "fulfillment":
            yield {"id": "ful-1", "demand_ref": D1, "workpackage_ref": WP1}
            yield {"id": "ful-2", "demand_ref": D2, "workpackage_ref": WP2}
        elif entity_type == "assignment":
            yield {"id": A1, "operation_ref": OP1, "workpackage_ref": WP1,
                   "resource_assignments": [{"resource_ref": R1}],
                   "phase_windows": {"run": [{"start": "2026-01-06T07:00:00Z",
                                              "end": "2026-01-06T14:50:00Z"}]},
                   "decision_ref": REC_DEC1}
            yield {"id": A2, "operation_ref": OP2, "workpackage_ref": WP2,
                   "resource_assignments": [{"resource_ref": R1}],
                   "phase_windows": {"run": [{"start": "2026-01-05T07:00:00Z",
                                              "end": "2026-01-05T11:00:00Z"}]},
                   "decision_ref": REC_DEC2}
        elif entity_type == "serviceoutcome":
            yield {"id": S1, "demand_ref": D1, "lateness": "P0DT14H50M",
                   "projected_completion": "2026-01-06T14:50:00Z",
                   "tardiness_cost": 370.83}
            yield {"id": S2, "demand_ref": D2, "lateness": "-P10D",
                   "projected_completion": "2026-01-05T11:00:00Z",
                   "tardiness_cost": 0.0}
        elif entity_type == "resource":
            yield {"id": R1, "resource_type": "machine", "capacity": 1,
                   "calendar_ref": "cal-1",
                   "external_refs": [{"system": "IDS", "type": "resource_id",
                                      "value": "CUT-01"}]}
        elif entity_type == "calendar":
            yield {"id": "cal-1", "base_pattern": {"weekdays": [0, 1, 2, 3, 4],
                                                   "shift_start": "07:00",
                                                   "shift_end": "19:00"},
                   "exceptions": [],
                   "external_refs": [{"system": "IDS", "type": "calendar_id",
                                      "value": "CAL-STD"}]}
        elif entity_type == "schedule":
            yield {"id": "sch-1", "summary_metrics": {"total_cost": 1060.83,
                                                      "production_cost": 690.0,
                                                      "tardiness_cost": 370.83,
                                                      "assignments": 2}}
        elif entity_type == "costmodel":
            yield {"id": "cm-1", "version": 1, "resource_rates": {R1: 1.0}}

    def read_identity_map(self):
        from mre.modules.identity_map import IdentityMap
        m = IdentityMap()
        m.register(D1, "IDS", "order_id", "ORD-01")
        m.register(D2, "IDS", "order_id", "ORD-02")
        m.register(R1, "IDS", "resource_id", "CUT-01")
        return m


class _Store:
    def load_snapshot(self, snapshot_id):
        return _Reader()


@pytest.fixture()
def world(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    with open(runs / "t.jsonl", "w", encoding="utf-8") as fh:
        for r in _records():
            fh.write(json.dumps(r) + "\n")
    index = EvidenceIndex().build(runs)
    return Explainer(_Store(), index, snapshot_id="snap-t")


@pytest.fixture()
def box(world):
    return EvidenceToolbox(world)


# ===========================================================================
# CU1 — the read-only tool surface
# ===========================================================================

class TestToolSurface:
    def test_vocabulary_parity(self):
        """Every tool has an authored meaning and a typed argument list — the
        INTENT_MEANINGS discipline, so a tool cannot be added and silently become
        uncallable (or callable and undocumented)."""
        assert set(TOOL_MEANINGS) == set(ToolName)
        assert set(TOOL_ARGS) == set(ToolName)
        assert all(TOOL_MEANINGS[t].strip() for t in ToolName)

    def test_governed_artifact_declares_its_review_discipline(self):
        text = (Path(__file__).resolve().parents[1] / "src" / "mre" / "modules"
                / "synthesis_prompt.md").read_text(encoding="utf-8")
        head, _, body = text.partition("## PROMPT")
        assert "prompt_version:" in head
        assert "R-AI5(2)" in head and "R-AI5(8)" in head
        assert "vocabulary-class change" in head
        # The surface is RENDERED from the contract, never re-authored in prose.
        for placeholder in ("{TOOLS}", "{CONTEXT}", "{QUESTION}", "{BUDGET}"):
            assert placeholder in body

    def test_rendered_surface_names_every_tool(self):
        from mre.modules.synthesizer import render_tools
        rendered = render_tools()
        for tool in ToolName:
            assert tool.value in rendered
            assert TOOL_MEANINGS[tool][:24] in rendered

    def test_every_tool_is_implemented(self, box):
        """A name in the closed set with no live implementation would be a door
        into a wall — the same reverse-guard the invitations get."""
        args = {"order": "ORD-01", "machine": "CUT-01", "id": REC_LATE1,
                "start": "2026-01-01T00:00:00Z", "end": "2026-02-01T00:00:00Z",
                # Session 4B.15: the corpus tools take free text.
                "query": "splittable operations", "topic": "operator"}
        for tool in ToolName:
            b = EvidenceToolbox(box._ex)
            need = {a.name: args[a.name] for a in TOOL_ARGS[tool] if a.required}
            res = b.call(tool.value, need)
            assert res.ok, f"{tool.value} failed: {res.note}"

    def test_rows_carry_record_ids(self, box):
        rows = box.call("lateness_set").rows
        assert rows and all(r["record_ids"] for r in rows)
        # and those ids re-fetch — a citation nobody can resolve is worthless
        for rid in rows[0]["record_ids"]:
            assert box.fetch_source(rid) is not None

    def test_placement_row_cites_every_source_it_reports_from(self, box):
        row = box.call("placements_for_order", {"order": "ORD-01"}).rows[0]
        # the machine name, the window and the order id live in three different
        # places; the row cites all three so a claim quoting any of them can ground
        kinds = {box.fetch_source(r)[0] for r in row["record_ids"]}
        assert kinds == {"record", "entity"}

    def test_unknown_tool_is_an_honest_result_not_a_crash(self, box):
        res = box.call("re_solve_the_plan", {"order": "ORD-01"})
        assert res.ok is False and "closed" in res.note
        assert box.calls[-1].tool == "re_solve_the_plan"

    def test_missing_required_argument_is_named(self, box):
        res = box.call("placements_for_order", {})
        assert res.ok is False and "order" in res.note

    def test_budget_caps_the_calls(self, world):
        b = EvidenceToolbox(world, max_calls=3)
        for _ in range(5):
            b.call("lateness_set")
        assert b.exhausted
        assert sum(1 for c in b.calls if c.ok) == 3
        assert "budget exhausted" in b.calls[-1].note

    def test_every_call_is_logged_with_its_arguments(self, box):
        box.call("placements_for_machine", {"machine": "CUT-01"})
        logged = box.calls[-1]
        assert logged.tool == "placements_for_machine"
        assert logged.args == {"machine": "CUT-01"}
        assert logged.rows == 2

    def test_the_surface_is_read_only(self):
        """M10 has no write path: no tool may name a mutation. This is a guard on
        the VOCABULARY, which is where such a thing would first appear."""
        forbidden = ("solve", "write", "commit", "apply", "move", "set_", "delete",
                     "update", "accept", "price")
        for tool in ToolName:
            assert not any(f in tool.value for f in forbidden), tool.value

    def test_lateness_set_enumerates_but_a_window_does_not(self, box):
        assert box.call("lateness_set").enumerates_set
        assert not box.call("placements_in_window",
                            {"start": "2026-01-05T00:00:00Z",
                             "end": "2026-01-06T00:00:00Z"}).enumerates_set


# ===========================================================================
# CU3 — claim-level verification (hand-built drafts, one per outcome)
# ===========================================================================

@pytest.fixture()
def read_box(box):
    """A toolbox that has already read the world, the way the loop would."""
    box.call("lateness_set")
    box.call("machine_occupancy", {"machine": "CUT-01"})
    return box


def _ids(box, tool, args=None, row=0):
    return box.call(tool, args or {}).rows[row]["record_ids"]


class TestClaimVerification:
    def test_verified_when_every_assertion_grounds(self, read_box):
        v = verify_claim(DraftClaim(
            text="ORD-01 finished 890 minutes past its due date.",
            record_ids=_ids(read_box, "lateness_set")), toolbox=read_box)
        assert v.status is ClaimStatus.VERIFIED

    def test_verified_survives_honest_unit_conversion(self, read_box):
        v = verify_claim(DraftClaim(
            text="ORD-01 is about 14.8 hours late.",
            record_ids=_ids(read_box, "lateness_set")), toolbox=read_box)
        assert v.status is ClaimStatus.VERIFIED

    def test_wrong_figure_against_a_cited_record_fails(self, read_box):
        v = verify_claim(DraftClaim(
            text="ORD-01 finished 250 minutes late.",
            record_ids=_ids(read_box, "lateness_set")), toolbox=read_box)
        assert v.status is ClaimStatus.FAILED
        assert "contradicted" in v.reason

    def test_fabricated_citation_fails(self, read_box):
        """The ordinal disease: a citation that names a list position, not a
        record. It must fail the CLAIM, not be quietly dropped."""
        v = verify_claim(DraftClaim(text="ORD-01 is late.",
                                    record_ids=["finding 2"]), toolbox=read_box)
        assert v.status is ClaimStatus.FAILED
        assert "do not exist" in v.reason

    def test_entity_this_run_does_not_have_fails(self, read_box):
        v = verify_claim(DraftClaim(
            text="ORD-99 is late too.",
            record_ids=_ids(read_box, "lateness_set")), toolbox=read_box)
        assert v.status is ClaimStatus.FAILED

    def test_wrong_timestamp_fails(self, read_box):
        v = verify_claim(DraftClaim(
            text="ORD-01 starts on 2026-02-11 07:00.",
            record_ids=_ids(read_box, "machine_occupancy", {"machine": "CUT-01"})),
            toolbox=read_box)
        assert v.status is ClaimStatus.FAILED

    def test_correct_but_uncited_lands_interpretive_never_promoted(self, read_box):
        v = verify_claim(DraftClaim(text="ORD-01 finished 890 minutes late.",
                                    record_ids=[]), toolbox=read_box)
        assert v.status is ClaimStatus.INTERPRETIVE
        assert "cites no record" in v.reason
        assert v.consulted_record_ids            # it still says what it read

    def test_a_name_alone_does_not_prove_a_sentence(self, read_box):
        """A mechanism claim that happens to name a real machine must not be
        promoted on the strength of that name — the citation promises the FIGURE
        grounds, not that the sentence mentions something that exists."""
        v = verify_claim(DraftClaim(
            text="ORD-01 sits behind the queue on CUT-01.",
            record_ids=_ids(read_box, "machine_occupancy", {"machine": "CUT-01"})),
            toolbox=read_box)
        assert v.status is ClaimStatus.INTERPRETIVE

    def test_a_conclusion_is_never_promoted_to_proven(self, read_box):
        """The draft may say which sentence is its CONCLUSION — a statement about
        shape, not about groundedness, and one that can only demote (R-AI5(8))."""
        v = verify_claim(DraftClaim(
            text="ORD-01 finished 890 minutes past its due date, so the cutting "
                 "line is the constraint.",
            record_ids=_ids(read_box, "lateness_set"), kind=ClaimKind.CONCLUSION),
            toolbox=read_box)
        assert v.status is ClaimStatus.INTERPRETIVE

    def test_a_reading_with_nothing_checkable_is_interpretive(self, read_box):
        v = verify_claim(DraftClaim(
            text="The dominant mechanism is the queue on the cutting line.",
            record_ids=_ids(read_box, "machine_occupancy", {"machine": "CUT-01"}),
            kind=ClaimKind.CONCLUSION), toolbox=read_box)
        assert v.status is ClaimStatus.INTERPRETIVE

    def test_quantifier_verified_only_when_the_set_was_enumerated(self, read_box):
        every = [i for r in read_box.call("lateness_set").rows
                 for i in r["record_ids"]]
        ok = verify_claim(DraftClaim(text="1 of 2 orders is late.",
                                     record_ids=every), toolbox=read_box)
        assert ok.status is ClaimStatus.VERIFIED

    def test_quantifier_over_a_sample_is_interpretive_and_names_the_sample(
            self, read_box):
        v = verify_claim(DraftClaim(
            text="All 4 of the late orders sit on CUT-01.",
            record_ids=_ids(read_box, "machine_occupancy", {"machine": "CUT-01"})),
            toolbox=read_box)
        assert v.status is ClaimStatus.INTERPRETIVE
        assert v.sample_note

    def test_status_is_never_the_models(self, read_box):
        """R-AI5(8): the draft's own beliefs are input, never the label. A claim
        that cites confidently and wrongly is still cut."""
        v = verify_claim(DraftClaim(
            text="ORD-01 finished 250 minutes late.",
            record_ids=_ids(read_box, "lateness_set"), kind=ClaimKind.CONCLUSION),
            toolbox=read_box)
        assert v.status is ClaimStatus.FAILED

    def test_an_under_cited_figure_is_interpretive_not_cut(self, read_box):
        """A figure the CITED records do not carry, but a sibling row of the same
        read does, is under-citation — not a contradiction. Cutting true sentences
        for a citation habit teaches the model to say less, not cite better."""
        # row 1 is ORD-01 (6 Jan); the 11:00 end belongs to row 0 (ORD-02, 5 Jan).
        other_row = _ids(read_box, "machine_occupancy", {"machine": "CUT-01"}, row=1)
        v = verify_claim(DraftClaim(
            text="CUT-01 also runs a job ending at 2026-01-05 11:00.",
            record_ids=other_row), toolbox=read_box)
        assert v.status is ClaimStatus.INTERPRETIVE

    def test_a_figure_nothing_read_carries_is_still_cut(self, read_box):
        v = verify_claim(DraftClaim(
            text="CUT-01 runs a job ending at 2026-03-30 11:00.",
            record_ids=_ids(read_box, "machine_occupancy", {"machine": "CUT-01"})),
            toolbox=read_box)
        assert v.status is ClaimStatus.FAILED

    def test_a_cut_conclusion_is_load_bearing(self, read_box):
        answer = verify_draft("why", [
            DraftClaim(text="ORD-01 finished 890 minutes past its due date.",
                       record_ids=_ids(read_box, "lateness_set")),
            DraftClaim(text="It ran 250 minutes late because of the queue.",
                       record_ids=_ids(read_box, "lateness_set"),
                       kind=ClaimKind.CONCLUSION),
        ], toolbox=read_box)
        assert len(answer.claims) == 1 and len(answer.cut) == 1
        assert answer.ungrounded_load_bearing == 1

    def test_a_wholly_failed_draft_is_unanswerable(self, read_box):
        answer = verify_draft("why", [
            DraftClaim(text="ORD-01 is 250 minutes late.",
                       record_ids=_ids(read_box, "lateness_set")),
        ], toolbox=read_box)
        assert answer.unanswerable and not answer.claims

    def test_counts_report_every_outcome(self, read_box):
        answer = verify_draft("why", [
            DraftClaim(text="ORD-01 finished 890 minutes past its due date.",
                       record_ids=_ids(read_box, "lateness_set")),
            DraftClaim(text="The cutting line is the constraint.", record_ids=[],
                       kind=ClaimKind.CONCLUSION),
            DraftClaim(text="ORD-01 is 250 minutes late.",
                       record_ids=_ids(read_box, "lateness_set")),
        ], toolbox=read_box)
        c = answer.counts()
        assert (c["verified"], c["interpretive"], c["failed_and_cut"]) == (1, 1, 1)


# ===========================================================================
# CU2 — the loop, and the seal between the tiers
# ===========================================================================

def _late_ids(world):
    b = EvidenceToolbox(world)
    return b.call("lateness_set").rows[0]["record_ids"]


class TestSynthesisLoop:
    def test_the_loop_calls_tools_then_answers(self, world):
        ids = _late_ids(world)
        synth = synthesizer_with([
            tool_call("lateness_set"),
            claims(claim("ORD-01 finished 890 minutes past its due date.", ids),
                   claim("The cutting line is the binding constraint.", ids,
                         kind="conclusion")),
        ])
        answer = synth.synthesize("what is going wrong", explainer=world)
        assert [t.tool for t in answer.tool_calls] == ["lateness_set"]
        assert len(answer.verified) == 1
        assert len(answer.interpretive) == 1

    def test_a_malformed_emission_is_nudged_once_then_survives(self, world):
        synth = synthesizer_with(["not json at all",
                                  claims(claim("The plan looks tight.", []))])
        answer = synth.synthesize("how does it look", explainer=world)
        assert synth.stats.malformed == 1
        assert len(answer.claims) == 1

    def test_budget_exhaustion_yields_an_honest_partial_never_a_stall(self, world):
        box = EvidenceToolbox(world, max_calls=2)
        synth = synthesizer_with([
            tool_call("lateness_set"), tool_call("lateness_set"),
            tool_call("lateness_set"),          # refused: over budget
            claims(claim("I did not get to the calendars.", [])),
        ])
        answer = synth.synthesize("why", explainer=world, toolbox=box)
        assert answer.budget_exhausted
        assert answer.claims and not answer.unanswerable

    def test_cannot_answer_is_the_honest_floor(self, world):
        synth = synthesizer_with([cannot_answer("nothing here speaks to that")])
        answer = synth.synthesize("what will happen next month", explainer=world)
        assert answer.unanswerable and not answer.claims

    def test_an_unavailable_synthesizer_returns_none(self, world, monkeypatch):
        from mre.modules.synthesizer import Synthesizer
        # 4B.8 pre-flight: `Synthesizer(api_key="")` falls back to os.environ, so
        # "unavailable" must be established rather than assumed from an ambient
        # empty environment. Assertions unchanged.
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        synth = Synthesizer(api_key="")
        assert synth.available is False
        assert synth.synthesize("anything", explainer=world) is None

    # -- the seal (R-AI5(2)) ------------------------------------------------

    def test_a_matched_intent_never_reaches_synthesis(self, world):
        """The dispatch test the brief asks for: a contracted intent goes to its
        contracted route with a synthesizer present and armed. If this ever fails,
        a proven answer has been replaced by a synthesized one."""
        class _Exploding:
            available = True

            def synthesize(self, *a, **kw):
                raise AssertionError("a matched intent reached the synthesis tier")

        d = dispatch(world, resolve(parsed("why is ORD-01 late", Intent.LATE_ORDER,
                                           orders=("ORD-01",)), world),
                     synthesizer=_Exploding())
        assert d.route == "late-order"

    def test_an_unmatched_intent_never_guesses_a_route(self, world):
        ids = _late_ids(world)
        synth = synthesizer_with([claims(claim("ORD-01 is the late one.", ids))])
        d = dispatch(world, parsed("what is the mood of the plant", Intent.UNMATCHED,
                                   confidence=0.2),
                     synthesizer=synth)
        assert d.route == "synthesis"
        assert d.synthesis is not None

    def test_without_a_synthesizer_the_floor_is_part_ones_bridge(self, world):
        d = dispatch(world, parsed("what is the mood of the plant", Intent.UNMATCHED,
                                   confidence=0.2, nearest=(Intent.LATE_ORDERS,)),
                     synthesizer=DeadSynthesizer())
        assert d.route == "NEAR_MISS"

    def test_a_clarify_that_leads_nowhere_reaches_the_second_tier(self, world):
        """The sweep's own specimen: "whats holding CUT-01" parsed as
        `start-reason` — an intent needing an ORDER — with only the MACHINE bound,
        hedged with `ambiguous-intent`. Asking the planner to choose between two
        framings of an answer that could not be assembled either way is a dead end;
        the machine they just named can be read directly."""
        from mre.contracts.parse import ClarifyReason
        ids = _late_ids(world)
        synth = synthesizer_with([claims(claim("CUT-01 is busy all week.", ids))])
        p = resolve(parsed("whats holding CUT-01", Intent.START_REASON,
                           machines=("CUT-01",), confidence=0.72,
                           clarify=ClarifyReason.AMBIGUOUS_INTENT), world)
        d = dispatch(world, p, synthesizer=synth)
        assert d.route == "synthesis"

    def test_a_clarify_with_nothing_bound_still_asks(self, world):
        """The other side of the same rule: when NOTHING the planner said
        resolved, asking is exactly right and must not be traded for a guess."""
        from mre.contracts.parse import ClarifyReason
        d = dispatch(world, parsed("why is that one late", Intent.LATE_ORDER,
                                   clarify=ClarifyReason.NO_SUBJECT),
                     synthesizer=synthesizer_with([claims(claim("x", []))]))
        assert d.route == "CLARIFY"

    def test_a_low_confidence_parse_goes_to_synthesis_not_a_route(self, world):
        ids = _late_ids(world)
        synth = synthesizer_with([claims(claim("ORD-01 is the late one.", ids))])
        d = dispatch(world, resolve(parsed("hmm", Intent.LATE_ORDER,
                                           orders=("ORD-01",), confidence=0.2),
                                    world), synthesizer=synth)
        assert d.route == "synthesis"


# ===========================================================================
# CU4 — the answer surface
# ===========================================================================

def _answer(world, *responses, memory=None, session="s1"):
    synth = synthesizer_with(list(responses))
    parser = ScriptedParser({})            # everything is UNMATCHED here
    return run_ask(world, "why is the plant like this", parser=parser,
                   synthesizer=synth, memory=memory, session_id=session)


class TestAnswerSurface:
    def test_claim_blocks_carry_per_claim_provenance(self, world):
        ids = _late_ids(world)
        res = _answer(world,
                      claims(claim("ORD-01 finished 890 minutes past its due date.",
                                   ids),
                             claim("The cutting line is the binding constraint.",
                                   ids, kind="conclusion")))
        text = TemplateRenderer().render(res.bundle)
        assert "[record:" in text                       # the verified claim
        assert "[synthesis" in text                     # the interpretive one
        assert "890 minutes" in text

    def test_the_register_is_synthesis(self, world):
        res = _answer(world, claims(claim("The plant is busy.", [])))
        assert res.register == "synthesis"

    def test_rendered_by_names_the_tier_and_the_tool_count(self, world):
        res = _answer(world, tool_call("lateness_set"),
                      claims(claim("The plant is busy.", [])))
        text = TemplateRenderer().render(res.bundle)
        assert "[rendered by: synthesis" in text
        assert "1 tool call(s)" in text
        assert "register: synthesis" in text

    def test_the_llm_renderer_never_rewords_a_verified_claim(self, world):
        """A claim's provenance label is attached to ITS WORDS. Rewording it would
        dissolve what was verified, so the synthesis body renders verbatim."""
        from mre.modules.renderers import LLMRenderer
        ids = _late_ids(world)
        res = _answer(world, claims(claim("ORD-01 finished 890 minutes past its "
                                          "due date.", ids)))

        class _Boom:
            messages = property(lambda self: self)

            def create(self, **kw):
                raise AssertionError("the synthesis body reached the LLM renderer")

        text = LLMRenderer(_client=_Boom()).render(res.bundle)
        assert "890 minutes" in text and "[rendered by: synthesis" in text

    def test_a_failed_load_bearing_claim_is_said_out_loud(self, world):
        ids = _late_ids(world)
        res = _answer(world, claims(
            claim("ORD-01 finished 890 minutes past its due date.", ids),
            claim("It is 250 minutes late because of the queue.", ids,
                  kind="conclusion")))
        text = TemplateRenderer().render(res.bundle)
        assert "couldn't ground part of it" in text
        # The cut claim is GONE — including from the sentence apologising for it.
        assert "250 minutes" not in text

    def test_a_wholly_failed_draft_says_it_could_not_answer(self, world):
        ids = _late_ids(world)
        res = _answer(world, tool_call("lateness_set"),
                      claims(claim("ORD-01 is 250 minutes late.", ids)))
        text = TemplateRenderer().render(res.bundle)
        assert "couldn't answer that one from the evidence" in text
        assert "lateness_set" in text                   # says what it consulted

    def test_the_ledger_records_per_claim_provenance_and_the_calls(self, world,
                                                                   tmp_path):
        from mre.modules.question_ledger import QuestionLedger
        ids = _late_ids(world)
        ledger = QuestionLedger(tmp_path / "q.jsonl")
        synth = synthesizer_with([tool_call("lateness_set"),
                                  claims(claim("ORD-01 finished 890 minutes past "
                                               "its due date.", ids))])
        run_ask(world, "what is wrong", parser=ScriptedParser({}),
                synthesizer=synth, ledger=ledger, session_id="s9")
        entry = ledger.recent(1)[0]
        assert entry.route == "synthesis"
        assert entry.synthesis is not None
        assert entry.synthesis.claims[0]["status"] == "verified"
        assert entry.synthesis.tool_calls[0].tool == "lateness_set"
        assert entry.synthesis.tool_calls[0].args == {}

    # -- "prove it" ---------------------------------------------------------

    def _prove_it(self, world, memory, session="s1"):
        return dispatch(world,
                        parsed("prove it", Intent.UNMATCHED,
                               followup_of=FollowupKind.PROVE_IT, confidence=0.9),
                        memory=memory, session_id=session)

    def test_prove_it_on_a_verified_claim_shows_the_record(self, world):
        memory = SynthesisMemory()
        ids = _late_ids(world)
        _answer(world, claims(claim("ORD-01 finished 890 minutes past its due "
                                    "date.", ids)), memory=memory)
        d = self._prove_it(world, memory)
        text = TemplateRenderer().render(d.bundle)
        assert d.route == "prove-it"
        assert "on the record" in text
        assert "lateness_minutes = 890.0 min for ORD-01" in text

    def test_prove_it_on_an_interpretive_claim_names_it_as_inference(self, world):
        memory = SynthesisMemory()
        ids = _late_ids(world)
        _answer(world, tool_call("lateness_set"),
                claims(claim("The cutting line is the binding constraint.", ids,
                             kind="conclusion")), memory=memory)
        d = self._prove_it(world, memory)
        text = TemplateRenderer().render(d.bundle)
        assert "my inference" in text
        assert "[record:" in text          # and each thing it was read from

    def test_a_contracted_answer_makes_the_remembered_claims_stale(self, world):
        """A "prove it" grounds OUR LAST ANSWER. Once a later turn was answered by
        a contracted route, the remembered synthesis claims are stale — opening the
        record behind a sentence the planner is not asking about is a wrong-target
        answer, however truthfully it names the sentence it chose (the sweep's
        specimen: "are you sure about that", two turns downstream).

        SESSION 4B.22: staleness is unchanged and is still the point. What
        changed is the TARGET that replaces it — the drill-down now opens the
        contracted answer the planner is actually looking at, instead of
        dead-ending. The stale claim must not be what opens either way, and both
        halves are asserted."""
        from mre.modules.interpreter import AnswerMemory
        memory = SynthesisMemory()
        answers = AnswerMemory()
        _answer(world, claims(claim("The cutting line is busy.", [])),
                memory=memory, session="s7")
        assert memory.last("s7") is not None
        run_ask(world, "why is ORD-01 late",
                parser=ScriptedParser({"why is ORD-01 late": parsed(
                    "", Intent.LATE_ORDER, orders=("ORD-01",))}),
                memory=memory, session_id="s7", answer_memory=answers)
        assert memory.last("s7") is None
        d = dispatch(world,
                     parsed("prove it", Intent.UNMATCHED,
                            followup_of=FollowupKind.PROVE_IT, confidence=0.9),
                     memory=memory, session_id="s7", answer_memory=answers)
        text = TemplateRenderer().render(d.bundle)
        assert "The cutting line is busy" not in text, (
            "the stale synthesis claim re-opened — the wrong-target answer this "
            "test exists to forbid")
        assert "why is ORD-01 late" in text, (
            "the drill-down did not open the contracted answer the planner is "
            "looking at (4B.22, docs/04 2026-07-31)")

    def test_prove_it_with_nothing_to_prove_says_so(self, world):
        """THE FLOOR IS STILL REACHABLE, and its copy was rewritten (4B.22).

        It used to read "the records behind it are cited on it — name the part
        you want walked", which after the drill-down ruling describes a turn
        that does not exist. This branch is now reached only when there is NO
        prior answer at all, and it says that."""
        d = self._prove_it(world, SynthesisMemory(), session="empty")
        text = TemplateRenderer().render(d.bundle)
        assert "haven't answered anything yet in this conversation" in text
        assert "cited on it" not in text

    # -- the named corpus specimens (CU4) -----------------------------------

    def test_specimen_aggregate_cause_answer(self, world):
        """SPECIMEN: the aggregate-cause question — the oldest debt in the AI
        ledger. The shape the answer must have: per-order facts VERIFIED against
        their records, and the mechanism as a LABELED interpretive conclusion.
        Neither half may wear the other's clothes."""
        ids = _late_ids(world)
        res = _answer(world, tool_call("lateness_set"), claims(
            claim("ORD-01 finished 890 minutes past its due date.", ids),
            claim("ORD-02 finished ahead of its due date.", ids),
            claim("The lateness is one order deep, not a plant-wide pattern: "
                  "ORD-01 sits behind the queue on the cutting line.", ids,
                  kind="conclusion")))
        text = TemplateRenderer().render(res.bundle)
        assert res.synthesis.counts()["verified"] >= 1
        assert res.synthesis.counts()["interpretive"] >= 1
        assert res.synthesis.counts()["failed_and_cut"] == 0
        # the facts carry citations; the mechanism carries the synthesis marker
        fact_line = next(l for l in text.splitlines() if "890 minutes" in l)
        take_line = next(l for l in text.splitlines() if "one order deep" in l)
        assert "[record:" in fact_line and "[synthesis" not in fact_line
        assert "[synthesis" in take_line

    def test_specimen_occupancy_read_verifies_fully(self, world):
        """SPECIMEN: "whats holding CUT-01" — a pure occupancy read. Every claim
        is a fact the records carry, so a fully-verified answer is the bar; an
        interpretive claim here would mean the tools were not actually consulted."""
        box = None
        from mre.modules.evidence_tools import EvidenceToolbox
        box = EvidenceToolbox(world)
        rows = box.call("machine_occupancy", {"machine": "CUT-01"}).rows
        synth = synthesizer_with([claims(
            claim("CUT-01 runs ORD-02 from 2026-01-05 07:00 to 2026-01-05 11:00.",
                  rows[0]["record_ids"]),
            claim("It then runs ORD-01 from 2026-01-06 07:00 to 2026-01-06 14:50.",
                  rows[1]["record_ids"]))])
        answer = synth.synthesize("whats holding CUT-01", explainer=world,
                                  toolbox=box)
        assert answer.counts()["verified"] == 2
        assert answer.counts()["interpretive"] == 0

    def test_a_prove_it_with_nothing_open_still_answers_a_named_intent(self, world):
        """The fourth sweep's specimen. With no claim of ours open the grounding
        pass has nothing to do — but the question is still a question, and a
        prove-it linkage over a REAL intent must be answered as that intent rather
        than dead-ending on "nothing to ground"."""
        d = dispatch(world, resolve(parsed("but why", Intent.LATE_ORDER,
                                           orders=("ORD-01",),
                                           followup_of=FollowupKind.PROVE_IT),
                                    world),
                     memory=SynthesisMemory(), session_id="fresh")
        assert d.route == "late-order"

    def test_prove_it_precedes_intent(self, world):
        """A prove-it turn is about OUR sentence, not a status of the plan, so it
        must not be dispatched as whatever intent the words resemble."""
        memory = SynthesisMemory()
        _answer(world, claims(claim("The cutting line is busy.", [])), memory=memory)
        d = dispatch(world, resolve(parsed("how do you know that",
                                           Intent.LATE_ORDER, orders=("ORD-01",),
                                           followup_of=FollowupKind.PROVE_IT),
                                    world),
                     memory=memory, session_id="s1")
        assert d.route == "prove-it"

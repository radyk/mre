"""R-TG5 — A TEACHING ANSWER READS THE BOARD (Session 4A teaching-graft (c2)).

Written from the ruling, not from the implementation.

WHAT THE RULING SAYS. A teaching-intent answer must ATTEMPT to read the board:
the loop makes at least one evidence read aimed at finding an instance of the
principle under discussion. Then — case found, the answer grounds it (the
principle labelled general knowledge, the instance cited as an ordinary board
claim); no case found, the answer teaches generally AND says so in one line,
which is a disclosure and not an apology. THE ATTEMPT IS WHAT IS REQUIRED, NEVER
THE GROUNDING: a board with no instance of the principle is a fact about the
board, and a forced stretch — citing an irrelevant record to satisfy a
checkbox — is the inverse defect.

WHY THERE IS NO SEAM HERE, AND WHY THAT IS THE RULING AND NOT A SHORTCUT. R-TG3
put the depth licence at the dispatch seam precisely because an instruction a
model can forget will be forgotten. This one goes the other way and the reason
is the shape of what would be enforced: a deterministic "did it read" gate can
only count calls, and a rule that counts calls is satisfied by making one. The
cheapest way past such a gate is an empty read followed by the same answer, and
the second-cheapest is a citation stretched over a record that does not show the
principle — which is worse than the defect, because a planner can check a missing
example against nothing and a wrong one against their board. So the prompt asks,
the sweep measures the rate, and the close-out reports it.

WHAT THIS FILE PROVES:

  (1) The governed artifact carries the rule, at a version that says so.
  (2) The rule's three branches are all present in the text a model is sent —
      found-one, found-none-and-cite, do-not-stretch — and the found-none branch
      says CITE, which is load-bearing and not a style note: an uncited
      disclosure carries no board content and R-TG1 direction (ii) DROPS it, so
      an uncited no-case line is a disclosure the planner never sees. That
      interaction is asserted here against the live verifier.
  (3) The catalog is not the board. `constraint_catalog` and `spec_lookup` read
      the product's documentation and have never seen this plant; the first live
      draft of v8 satisfied itself with three of them and shipped no board claim,
      which is why the clause exists and why the grader subtracts them.
  (4) NOTHING IS ENFORCED. A teaching answer that read nothing still renders —
      asserted, so that a later session adding the gate this ruling declined has
      to delete a test that says why.
  (5) The grader's disclosure-vs-silence branch does what its name says, on
      injected turns, including the manual-only shape that was measured live.

WHAT THIS FILE DOES NOT PROVE. That the model OBEYS rule 14 — that is the
prompt's job and `sweep_teaching_v3`'s measurement, reported as a rate and not
as a pass.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from mre.contracts.parse import Intent
from mre.contracts.synthesis import ClaimKind, ClaimStatus, DraftClaim
from mre.modules.claim_verifier import verify_claim
from mre.modules.evidence_index import EvidenceIndex
from mre.modules.evidence_tools import EvidenceToolbox
from mre.modules.explainer import Explainer
from mre.modules.interpreter import run_ask
from mre.modules.renderers import TemplateRenderer
from tests.parse_doubles import ScriptedParser, claim, claims, parsed, synthesizer_with
from tests.test_synthesis import _records, _Store

ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "src" / "mre" / "modules" / "synthesis_prompt.md"
GRADER = ROOT / "tools" / "spikes" / "teaching_graft_c" / "grade_c9_sweep.py"

GENERAL = "Tardiness objectives tend to give weak lower bounds."


def _prompt_body() -> str:
    return PROMPT.read_text(encoding="utf-8").partition("## PROMPT")[2]


def _prompt_head() -> str:
    return PROMPT.read_text(encoding="utf-8").partition("## PROMPT")[0]


@pytest.fixture(scope="module")
def grader():
    """The C9 grader, imported from the spike it lives in.

    Loaded by path rather than by package import because it is a tool and not a
    module; the point of importing it at all is that a check nobody can exercise
    is a check nobody can trust.
    """
    spec = importlib.util.spec_from_file_location("_grade_c9", GRADER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def world(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    with open(runs / "t.jsonl", "w", encoding="utf-8") as fh:
        for r in _records():
            fh.write(json.dumps(r) + "\n")
    return Explainer(_Store(), EvidenceIndex().build(runs), snapshot_id="snap-t")


# ===========================================================================
# (1)+(2)+(3) — the governed artifact carries the rule
# ===========================================================================

class TestGovernedPrompt:
    def test_version_records_the_ruling(self):
        head = _prompt_head()
        version = int(head.split("prompt_version:")[1].split()[0])
        assert version >= 8, f"prompt_version went backwards: {version}"
        assert "R-TG5" in head
        # The review discipline the file has always declared is still declared.
        assert "vocabulary-class change" in head

    def test_the_rule_is_in_the_body_the_model_is_sent(self):
        body = _prompt_body()
        assert "14." in body
        assert "STILL A QUESTION ABOUT THIS PLANT" in body

    def test_all_three_branches_are_present(self):
        """Found one, found none, do not stretch. A rule carrying only the first
        would read as 'always ground it', which is the stretch it forbids."""
        body = _prompt_body()
        assert "YOU FOUND ONE" in body
        assert "YOU FOUND NONE" in body
        assert "DO NOT STRETCH" in body

    def test_the_no_case_branch_says_cite(self):
        """Load-bearing: see the verifier assertion below."""
        body = _prompt_body()
        found_none = body.split("YOU FOUND NONE")[1].split("DO NOT STRETCH")[0]
        assert "CITE THE READ THAT FOUND NOTHING" in found_none

    def test_the_catalog_is_named_as_not_the_board(self):
        body = _prompt_body()
        assert "THE CATALOG IS NOT THE BOARD" in body
        for manual in ("constraint_catalog", "spec_lookup"):
            assert manual in body.split("THE CATALOG IS NOT THE BOARD")[1][:600]

    def test_rule_9_survives(self):
        """Rule 14 must not read as permission to skip the capability floor —
        a capability claim is still a lookup (4B.15)."""
        body = _prompt_body()
        assert "CALL `constraint_catalog` FIRST" in body
        assert "rule 9" in body.split("THE CATALOG IS NOT THE BOARD")[1][:600]


# ===========================================================================
# (2) — why the no-case line must cite, asserted against the live verifier
# ===========================================================================

class TestAnUncitedDisclosureIsDropped:
    """R-TG1 direction (ii) and R-TG5's found-none branch, at their meeting
    point. This is the fact the prompt clause exists for; if the verifier's
    behaviour ever changes, the clause is wrong and this test says so."""

    SENTENCE = "Nothing on this board is in that position right now."

    def test_an_uncited_no_case_sentence_is_cut(self, world):
        box = EvidenceToolbox(world)
        box.call("lateness_set")
        out = verify_claim(
            DraftClaim(text=self.SENTENCE, record_ids=[], kind=ClaimKind.FACT),
            toolbox=box)
        assert out.status is ClaimStatus.FAILED, (
            "an uncited no-case disclosure survived — rule 14's cite clause is "
            "then unnecessary and the prompt should stop asking for it")

    def test_the_same_sentence_cited_is_not_cut(self, world):
        box = EvidenceToolbox(world)
        rows = box.call("lateness_set").rows
        out = verify_claim(
            DraftClaim(text=self.SENTENCE,
                       record_ids=list(rows[0]["record_ids"]), kind=ClaimKind.FACT),
            toolbox=box)
        assert out.status is not ClaimStatus.FAILED
        # and it is a BOARD claim — which is what makes a disclosed no-case
        # distinguishable from silence in the sweep at all.
        assert out.status in (ClaimStatus.VERIFIED, ClaimStatus.INTERPRETIVE)


# ===========================================================================
# (4) — nothing is enforced at the seam
# ===========================================================================

class TestTheAttemptIsNotGated:
    def test_a_teaching_answer_that_read_nothing_still_renders(self, world):
        """R-TG5 enforces nothing. A gate here could only count calls, and a
        rule that counts calls is satisfied by making one — so the ruling
        declined it deliberately. A session that adds it must delete this test.
        """
        q = "how does scheduling normally work"
        r = run_ask(world, q,
                    parser=ScriptedParser({q: parsed(q, Intent.TEACHING)}),
                    synthesizer=synthesizer_with(
                        [claims(claim(GENERAL, [], "general_knowledge"))]),
                    session_id="tg5-nogate")
        text = TemplateRenderer().render(r.bundle)
        assert r.register == "synthesis"
        assert GENERAL[:32] in text, (
            "a teaching answer with no board read was suppressed — R-TG5 "
            "requires the attempt and gates nothing")


# ===========================================================================
# (5) — the grader's disclosure-vs-silence branch, on injected turns
# ===========================================================================

class TestGraderBranch:
    def test_the_manual_is_not_a_board_read(self, grader):
        """The live shape that produced this clause: v8's first draft answered
        a teaching question out of `constraint_catalog` and `spec_lookup` alone
        and shipped no board claim."""
        assert grader.board_reads(["constraint_catalog", "spec_lookup"]) == []
        assert grader.board_reads(
            ["constraint_catalog", "machine_occupancy"]) == ["machine_occupancy"]
        assert grader.board_reads(None) == []

    def test_a_disclosed_no_case_is_not_silence(self, grader):
        """The injected answer: it read the plant and its no-case line cited the
        read, so a board claim landed. This is the branch the ruling's cite
        clause exists to produce."""
        c = grader.classify_teaching_turn(
            {"tools": ["lateness_set"], "general_knowledge": 1,
             "verified": 1, "interpretive": 0})
        assert c["verdict"] == "grounded"
        assert c["m5_attempt"] and c["m2_attached"] and c["m1_principle"]

    def test_silence_reads_as_silence(self, grader):
        c = grader.classify_teaching_turn(
            {"tools": [], "general_knowledge": 3, "verified": 0,
             "interpretive": 0})
        assert c["verdict"] == "silent"
        assert not c["m5_attempt"] and not c["m2_attached"]
        # and the principle is still there — this is exactly the shape session
        # (c) measured 4 of 4 times: M1 green, M2 red.
        assert c["m1_principle"]

    def test_manual_only_reads_as_silence(self, grader):
        c = grader.classify_teaching_turn(
            {"tools": ["constraint_catalog", "spec_lookup"],
             "general_knowledge": 3, "verified": 0, "interpretive": 0})
        assert c["verdict"] == "silent"
        assert not c["m5_attempt"]

    def test_a_read_whose_claims_were_all_cut_is_its_own_verdict(self, grader):
        """Neither grounded nor silent: it looked and nothing survived. Reported
        verbatim rather than scored, because this is where a silent cut hides."""
        c = grader.classify_teaching_turn(
            {"tools": ["machine_occupancy"], "general_knowledge": 1,
             "verified": 0, "interpretive": 0, "failed_and_cut": 2})
        assert c["verdict"] == "no-board-claim"
        assert c["m5_attempt"] and not c["m2_attached"]

    def test_an_instance_answer_is_the_target_shape(self, grader):
        c = grader.classify_teaching_turn(
            {"tools": ["placements_for_machine", "machine_occupancy"],
             "general_knowledge": 1, "verified": 1, "interpretive": 1})
        assert c["verdict"] == "grounded"
        assert c["board_claims"] == 2
        assert c["board_reads"] == ["placements_for_machine", "machine_occupancy"]

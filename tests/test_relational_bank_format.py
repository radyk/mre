"""R-EX2 (the bank format) and R-LD6 (the resolver contract).

Session 4A teaching-graft (d.2). Two rulings, one file, because they meet at one
question: **what does a turn leave behind for the next turn, and what may a bank
assert about it?**

R-EX2 — BANKS GRADE ROUTES AND RELATIONS; BODIES BELONG TO TESTS.
  (1) sequence-level world directives (`REBIND`);
  (2) expectations that reference an earlier turn by index, in three relational
      forms — body identity/distinctness by fingerprint, record-set provenance,
      and record count;
  (3) no prose assertions in banks, ever.

R-LD6 — ONE RESOLVER CONTRACT. Clause (5) is the part with product code behind
it: what enters the LAST-ANSWER rung.

Everything here is offline and deterministic. The live proofs — the relational
bank at 11/11, the cross-version bank at 4/4 across a real `REBIND` — are in the
close-out with their transcripts, and the negative controls that prove these
guards can go red are `tools/spikes/teaching_graft_d2/negative_controls.py`.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from mre.ai_exam.runner import (
    _MACHINE_SUBJECT_TYPES, _ORDER_SUBJECT_TYPES, TurnRecord, carry_from_meta,
    resolved_subject,
)
from mre.ai_exam.script import (
    COUNT_KEYS, EXPECT_KEYS, TURN_REF_KEYS, Expect, Question, Rebind, Reset,
    parse_script,
)
from mre.ai_exam.sidecar import (
    _RELATIONAL_KEYS, answer_body, check_expectation, check_relational,
)
from mre.modules.interpreter import (
    CARRIED_MACHINE_SUBJECT_TYPES, CARRIED_ORDER_SUBJECT_TYPES, carry_subject,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Fixtures — the smallest things that can carry a relational assertion
# ---------------------------------------------------------------------------

def turn(index: int, *, body: str = "", records: list[str] | None = None,
         expect: dict | None = None, error: str | None = None) -> TurnRecord:
    """A finished turn, as the runner would have left it."""
    t = TurnRecord(lineno=index * 10, question=f"q{index}", selection={},
                   conv_index=index)
    t.answer = body
    stripped = answer_body(body)
    t.body_sha = (hashlib.sha256(stripped.encode("utf-8")).hexdigest()
                  if stripped else "")
    t.record_ids = list(records or [])
    t.record_count = len(t.record_ids)
    t.expect = dict(expect or {})
    t.error = error
    return t


def details(findings) -> str:
    return "; ".join(f.detail for f in findings)


class _Bundle:
    """The two fields `carry_subject` reads off a bundle."""

    def __init__(self, subject_type: str = "", subject_external_name: str = ""):
        self.subject_type = subject_type
        self.subject_external_name = subject_external_name


class _Kind:
    def __init__(self, value: str):
        self.value = value


class _Subject:
    def __init__(self, kind: str, ref):
        self.kind = _Kind(kind)
        self.ref = ref


class _Parsed:
    def __init__(self, *subjects):
        self.subjects = list(subjects)


# ===========================================================================
# R-EX2 (1) — REBIND, the sequence-level world directive
# ===========================================================================

class TestRebindDirective:
    def test_rebind_parses_to_a_schedule(self):
        ps = parse_script("REBIND rolling-c32a6140-b6b")
        assert isinstance(ps.items[0], Rebind)
        assert ps.items[0].schedule == "rolling-c32a6140-b6b"
        assert not ps.parse_errors

    def test_rebind_is_case_insensitive_on_the_keyword_and_verbatim_on_the_id(self):
        ps = parse_script("rebind Rolling-ABC-123")
        assert ps.items[0].schedule == "Rolling-ABC-123"

    @pytest.mark.parametrize("line", ["REBIND", "REBIND a b", "REBIND   "])
    def test_a_rebind_we_cannot_read_is_a_parse_error_not_a_silent_drop(self, line):
        """A REBIND we half-understood would grade the WRONG WORLD, and the
        transcript would say nothing about it."""
        ps = parse_script(line)
        assert not any(isinstance(i, Rebind) for i in ps.items)
        assert any("REBIND" in e[2] for e in ps.parse_errors)

    def test_a_rebind_without_a_data_root_stops_the_run(self, tmp_path):
        """Fail LOUD, the way a dead target already does. Continuing quietly
        against the previous board is the one outcome that must not happen: the
        transcript would name one world and grade another."""
        from mre.ai_exam.runner import ExamRunner, RunTarget
        target = RunTarget.from_out_dir(tmp_path, "snap-x", label="nowhere")
        runner = ExamRunner(target, use_llm=False, data_root=None)
        script = parse_script("REBIND rolling-nope\nwhy is ORD-01 late\n")
        # A target with no snapshot is unloadable, which short-circuits before
        # the rebind — so this asserts the DIRECTIVE's own guard directly.
        result = runner.run(parse_script(""))
        assert result.turns == []
        assert any(isinstance(i, Rebind) for i in script.items)


# ===========================================================================
# R-EX2 (2) — the three relational forms
# ===========================================================================

class TestRelationalGrammar:
    def test_every_relational_key_is_in_the_closed_set(self):
        for key in TURN_REF_KEYS + COUNT_KEYS:
            assert key in EXPECT_KEYS

    def test_the_parse_side_and_the_check_side_name_the_same_keys(self):
        """Two lists of key names in two modules is how they drift. This is the
        pin: `script` decides what may be WRITTEN, `sidecar` decides what is
        CHECKED relationally, and a key in one and not the other is either an
        expectation nothing grades or a check nothing can request."""
        assert set(TURN_REF_KEYS) | set(COUNT_KEYS) == set(_RELATIONAL_KEYS)

    def test_relational_values_parse_as_integers(self):
        ps = parse_script("EXPECT BODY_SAME_AS=2 RECORDS_FROM=1 RECORDS=0")
        assert ps.items[0].fields == {
            "body_same_as": 2, "records_from": 1, "records": 0}

    @pytest.mark.parametrize("line", [
        "EXPECT body_same_as=abc",
        "EXPECT records_from=0",          # turn indexes are 1-based
        "EXPECT body_differs_from=-1",
        "EXPECT records=-1",
    ])
    def test_an_unreadable_relational_value_is_a_parse_error(self, line):
        """A bank that thinks it is grading turn 2 and is grading nothing reads
        exactly like a bank that passed — the failure mode this whole format
        exists because of."""
        ps = parse_script(line)
        assert not any(isinstance(i, Expect) for i in ps.items)
        assert ps.parse_errors


class TestBodyFingerprint:
    def test_same_body_meets_body_same_as_and_misses_body_differs_from(self):
        t1 = turn(1, body="the same words")
        assert check_relational(turn(2, body="the same words",
                                     expect={"body_same_as": 1}), [t1]) == []
        misses = check_relational(
            turn(2, body="the same words", expect={"body_differs_from": 1}), [t1])
        assert "IDENTICAL" in details(misses)

    def test_different_bodies_meet_body_differs_from(self):
        t1 = turn(1, body="one thing")
        assert check_relational(turn(2, body="another thing",
                                     expect={"body_differs_from": 1}), [t1]) == []
        misses = check_relational(
            turn(2, body="another thing", expect={"body_same_as": 1}), [t1])
        assert "they differ" in details(misses)

    def test_the_fingerprint_ignores_the_rendered_by_footer(self):
        """The footer names the RENDERER, not the answer. Two answers that say
        the same thing through different renderers are the same answer, and a
        fingerprint that disagreed would make `deaf`'s premise untestable."""
        a = turn(1, body="body text\n[rendered by: template | register: testimony]")
        b = turn(2, body="body text\n[rendered by: synthesis | register: synthesis]",
                 expect={"body_same_as": 1})
        assert check_relational(b, [a]) == []

    def test_an_empty_body_is_UNEVALUABLE_in_both_directions(self):
        """Two answers that are both empty are two defects, not one answer — and
        an empty body is not evidence that they DIFFER either. Both forms miss,
        and the message says which side was blank."""
        a = turn(1, body="")
        for key in ("body_same_as", "body_differs_from"):
            d = details(check_relational(turn(2, body="", expect={key: 1}), [a]))
            assert "EMPTY body" in d
        d = details(check_relational(
            turn(2, body="real text", expect={"body_differs_from": 1}), [a]))
        assert "EMPTY body" in d and "turn 1" in d


class TestRecordProvenance:
    def test_a_subset_of_the_referenced_turns_records_meets_records_from(self):
        t1 = turn(1, records=["r1", "r2", "r3"])
        t2 = turn(2, records=["r1", "r3"], expect={"records_from": 1})
        assert check_relational(t2, [t1]) == []

    def test_a_stray_record_misses_and_names_one(self):
        t1 = turn(1, records=["r1"])
        t2 = turn(2, records=["r1", "r9"], expect={"records_from": 1})
        d = details(check_relational(t2, [t1]))
        assert "not in turn 1" in d and "r9" in d

    def test_opening_NOTHING_is_not_grounding_correctly(self):
        """THE HOLE THIS CLAUSE EXISTS TO CLOSE. The empty set is a subset of
        every set, so a pure subset test would pass a turn that opened nothing —
        which is the exact defect (D-01) the form was written to catch, reported
        as a pass."""
        t1 = turn(1, records=["r1", "r2"])
        t2 = turn(2, records=[], expect={"records_from": 1})
        assert "served NO records" in details(check_relational(t2, [t1]))

    def test_records_counts_exactly_and_zero_is_a_real_expectation(self):
        assert check_relational(turn(2, records=[], expect={"records": 0}),
                                [turn(1)]) == []
        assert check_relational(turn(2, records=["r1"], expect={"records": 0}),
                                [turn(1)]) != []


class TestAnUnresolvableReferenceIsAMissNotASkip:
    """A bank error must never read as green. That is the whole reason these are
    `expect-miss` findings and not a separate advisory kind: `ExamResult.graded`
    counts a turn as MET when no `expect-miss` names it."""

    def test_an_index_past_the_conversation_misses(self):
        d = details(check_relational(turn(2, expect={"body_same_as": 5}),
                                     [turn(1, body="x")]))
        assert "only 1 turn(s) precede" in d

    def test_a_reference_with_no_prior_turns_at_all_misses(self):
        assert check_relational(turn(1, expect={"records_from": 1}), []) != []

    def test_a_reference_to_a_turn_that_FAILED_misses(self):
        """A crashed turn has no body and no records. Comparing against it would
        compare against zero and quietly pass."""
        dead = turn(1, error="timed out after 90s")
        d = details(check_relational(turn(2, body="x", expect={"body_same_as": 1}),
                                     [dead]))
        assert "failed" in d


class TestTheTwoCheckersDoNotOverlap:
    def test_check_expectation_ignores_the_relational_keys(self):
        """Without this skip, every relational expectation ever written would be
        compared against `None` by the per-turn checker and reported as a miss —
        the new forms would be unusable and would look like product defects."""
        t = turn(2, body="x", expect={"body_same_as": 1, "records": 0})
        t.route, t.parse = "why-here", {"intent": "why-here"}
        assert check_expectation(t) == []

    def test_a_per_turn_key_and_a_relational_key_are_both_graded(self):
        t = turn(2, body="x", records=["r1"],
                 expect={"route": "why-here", "records": 0})
        t.route, t.parse = "why-here", {"intent": "why-here"}
        assert check_expectation(t) == []            # the route matched
        assert check_relational(t, [turn(1)]) != []  # the count did not


# ===========================================================================
# R-EX2 (3) — the division, ENFORCED rather than stated
# ===========================================================================

class TestNoProseAssertionsInBanks:
    def test_the_expect_key_set_is_closed(self):
        ps = parse_script('EXPECT body_contains=frozen')
        assert not any(isinstance(i, Expect) for i in ps.items)
        assert any("unknown key" in e[2] for e in ps.parse_errors)

    def test_no_expect_key_names_prose(self):
        """The keys are routing facts, subject refs and relations. A key whose
        value would be a SENTENCE is the thing this clause forbids; if one is
        ever added, this test is the conversation it has to survive."""
        for key in EXPECT_KEYS:
            assert not any(w in key for w in ("text", "body_contains", "says",
                                              "phrase", "wording", "contains"))

    def test_the_committed_banks_carry_no_prose_expectation(self):
        """Applied to the artifacts, not just to the parser — the (e2) lesson:
        run the check over the corpus rather than reasoning about it."""
        bad = []
        for bank in (ROOT / "tests" / "ai_exam" / "banks").glob("*.txt"):
            ps = parse_script(bank.read_text(encoding="utf-8"))
            bad += [(bank.name, e[1].strip()) for e in ps.parse_errors]
        assert bad == []


# ===========================================================================
# R-LD6 clause (5) — what enters the LAST-ANSWER rung
# ===========================================================================

class TestCarrySubjectClauseOne:
    """The shipped behaviour, unchanged and FIRST."""

    @pytest.mark.parametrize("subject_type", sorted(CARRIED_ORDER_SUBJECT_TYPES))
    def test_a_carried_order_type_carries_its_order(self, subject_type):
        assert carry_subject(_Bundle(subject_type, "ORD-01")) == {"order": "ORD-01"}

    def test_a_carried_machine_type_carries_its_machine(self):
        assert carry_subject(_Bundle("machine_idle", "CUT-01")) == {"machine": "CUT-01"}

    @pytest.mark.parametrize("name", ["", "  ", "?", "all"])
    def test_a_placeholder_name_is_not_a_subject(self, name):
        assert carry_subject(_Bundle("demand", name)) == {}

    def test_clause_one_wins_over_clause_two(self):
        """Additivity is the property that makes this change provable: a carry
        that is populated today is untouched."""
        parsed = _Parsed(_Subject("order", "ORD-99"), _Subject("machine", "CUT-99"))
        assert carry_subject(_Bundle("demand", "ORD-01"), parsed) == {"order": "ORD-01"}


class TestCarrySubjectClauseTwo:
    """The subject the PARSE resolved, where the bundle names none.

    The founder's specimen, one word apart: *"why is ORD-000252 on CUT-01 WHEN
    IT IS"* draws a CLARIFY whose bundle truthfully names no subject, while the
    parse has resolved ORD-000252 from the planner's own typing. Measured 3/3:
    before this clause the two arms of that pair reached DIFFERENT ROUTES from
    an identical follow-up sentence."""

    def test_a_clarify_that_bound_an_order_still_carries_it(self):
        parsed = _Parsed(_Subject("order", "ORD-000252"))
        assert carry_subject(_Bundle("clarify", "?"), parsed) == {"order": "ORD-000252"}

    def test_it_carries_both_kinds_when_both_resolved(self):
        parsed = _Parsed(_Subject("order", "ORD-01"), _Subject("machine", "CUT-01"))
        assert carry_subject(_Bundle("clarify", "?"), parsed) == {
            "order": "ORD-01", "machine": "CUT-01"}

    def test_an_unresolved_subject_carries_nothing(self):
        """Words the planner typed that named nothing in this world are not a
        subject. A default that ASSERTS manufactures a claim out of a gap."""
        assert carry_subject(_Bundle("clarify", "?"),
                             _Parsed(_Subject("order", None))) == {}

    def test_an_unresolved_sibling_does_not_make_a_resolved_order_ambiguous(self):
        """One order we resolved and one we could not is NOT two orders. An
        unresolved subject has to leave the set before the count is taken, or a
        typo beside a real id would silently cost the planner the real one."""
        parsed = _Parsed(_Subject("order", "ORD-01"), _Subject("order", None))
        assert carry_subject(_Bundle("clarify", "?"), parsed) == {"order": "ORD-01"}

    def test_two_different_orders_carry_NEITHER(self):
        """A question about two orders is not a question about the first one.
        The same refusal `_resolve_machine` already makes on an ambiguous token:
        never guessed."""
        parsed = _Parsed(_Subject("order", "ORD-01"), _Subject("order", "ORD-02"))
        assert carry_subject(_Bundle("clarify", "?"), parsed) == {}

    def test_the_same_order_named_twice_is_not_ambiguous(self):
        parsed = _Parsed(_Subject("order", "ORD-01"), _Subject("order", "ORD-01"))
        assert carry_subject(_Bundle("clarify", "?"), parsed) == {"order": "ORD-01"}

    def test_no_parse_at_all_carries_only_clause_one(self):
        assert carry_subject(_Bundle("clarify", "?"), None) == {}


class TestOneDefinitionThreeSites:
    """R-LD6 clause (5) has ONE definition and three readers. The rule lived in
    three places before and that is how it drifted; these pins are what keep it
    from happening again."""

    def test_the_runner_prefers_the_products_answer(self):
        assert carry_from_meta({"carry_subject": {"order": "ORD-07"}},
                               "clarify", "?") == {"order": "ORD-07"}

    def test_an_explicit_empty_carry_is_honoured_not_second_guessed(self):
        """`{}` means "this turn left nothing", which is a real answer. Falling
        back to the local reading here would let the harness carry more than the
        product does — the runner's own founding law."""
        assert carry_from_meta({"carry_subject": {}}, "demand", "ORD-01") == {}

    def test_a_payload_without_the_field_falls_back_to_clause_one(self):
        assert carry_from_meta({}, "demand", "ORD-01") == {"order": "ORD-01"}
        assert carry_from_meta({}, "clarify", "?") == {}

    def test_the_runners_clause_one_sets_match_the_products(self):
        assert _ORDER_SUBJECT_TYPES == CARRIED_ORDER_SUBJECT_TYPES
        assert _MACHINE_SUBJECT_TYPES == CARRIED_MACHINE_SUBJECT_TYPES

    def test_the_panels_clause_one_sets_match_the_products(self):
        """Read out of `askpanel.js` itself. The panel is the shipped client; a
        harness in lockstep with a stale panel measures a product nobody uses."""
        js = (ROOT / "src" / "cockpit" / "src" / "askpanel.js").read_text(
            encoding="utf-8")
        def _set(name: str) -> set:
            m = re.search(rf"const {name} = new Set\(\[([^\]]*)\]\)", js)
            assert m, f"{name} not found in askpanel.js"
            return set(re.findall(r'"([a-z_]+)"', m.group(1)))
        assert _set("ORDER_SUBJECTS") == CARRIED_ORDER_SUBJECT_TYPES
        assert _set("MACHINE_SUBJECTS") == CARRIED_MACHINE_SUBJECT_TYPES

    def test_the_panel_reads_the_products_carry_subject_first(self):
        """Read out of `resolvedSubject`'s OWN BODY, not out of the file. A
        substring search passes on the explanatory comment above the branch,
        which is a guard that watches a comment — the negative control caught
        exactly that and it is why this reads the function."""
        js = (ROOT / "src" / "cockpit" / "src" / "askpanel.js").read_text(
            encoding="utf-8")
        m = re.search(r"function resolvedSubject\(meta\) \{(.*?)\n  \}", js,
                      re.S)
        assert m, "resolvedSubject not found in askpanel.js"
        body = re.sub(r"//[^\n]*", "", m.group(1))     # comments are not code
        assert "meta.carry_subject" in body
        # ...and FIRST: the product's answer is not a fallback.
        assert body.index("meta.carry_subject") < body.index("ORDER_SUBJECTS")

    def test_resolved_subject_is_still_exactly_clause_one(self):
        """Kept as the fallback and as what clause (1) MEANS. If it ever grows
        clause (2)'s behaviour there are two definitions again."""
        assert resolved_subject("clarify", "ORD-01") == {}
        assert resolved_subject("demand", "ORD-01") == {"order": "ORD-01"}

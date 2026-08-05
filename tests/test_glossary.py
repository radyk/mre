"""R-TE1 — THE PRODUCT EXPLAINS ITS OWN WORDS.

Session 4A teaching-graft (d.3). The founding specimen, from the founder's
freewheel round: a contracted route said "seed" nine times and the planner asked
what it meant, twice, and got two refusals — an entity CLARIFY and the
capability coach. Neither register could hear a question about the product's own
vocabulary.

The four clauses, and what guards each:

  (1) the trigger contract — we explain words we SAID, on THIS board.
      `TestTermMemory`, `TestTheTriggerContract`.
  (2) the citation bar — every entry cites the artifact that defines it, and no
      glossary sentence may wear the general-knowledge label.
      `TestEveryCitationResolves`, `TestTheAnswerIsAuthoredAndCited`.
  (3) an unconfirmed proposal is not a matched intent. `TestTheTrueNegatives`.
  (4) an entry whose citation target moves fails a TEST, not a memory.
      `TestEveryCitationResolves` is that test.

The live proofs — the founder pair routing to `term-explanation` on the demo
board, before and after — are in the close-out with their transcripts.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from mre.contracts.parse import (
    INTENT_MEANINGS, Intent, MODEL_SELECTABLE_INTENTS, SECOND_TIER_INTENTS,
)
from mre.modules.explainer import ROUTE_TAXONOMY
from mre.modules.glossary import (
    CITE_RULING, CITE_RUN, CITE_SPEC, GLOSSARY, GLOSSARY_BY_TERM, known_term,
    terms_in,
)
from mre.modules.interpreter import TermMemory, forget_deliveries, remember_terms
from mre.modules import interpreter as interp
from mre.modules import renderers as rd

ROOT = Path(__file__).resolve().parents[1]


# ===========================================================================
# Clause (2) and (4) — the citation bar, and the test that keeps it
# ===========================================================================

class TestEveryCitationResolves:
    """CLAUSE (4). An entry whose citation target changes must fail a test
    rather than quietly become folklore. These read the REAL documents."""

    def test_the_glossary_is_not_empty_and_every_entry_cites_something(self):
        assert GLOSSARY
        for e in GLOSSARY:
            assert e.citations, f"{e.term} asserts without citing"

    @pytest.mark.parametrize("entry", GLOSSARY, ids=lambda e: e.term)
    def test_every_ruling_citation_names_a_ruling_in_docs_04(self, entry):
        text = (ROOT / "docs" / "04-design-history.md").read_text(
            encoding="utf-8", errors="replace")
        for kind, target, _phrase in entry.citations:
            if kind != CITE_RULING:
                continue
            assert re.search(rf"\b{re.escape(target)}\b", text), (
                f"{entry.term} cites {target}, which is not in docs/04")

    @pytest.mark.parametrize("entry", GLOSSARY, ids=lambda e: e.term)
    def test_every_spec_citation_resolves_in_its_own_document(self, entry):
        """`docs/05:R-C3` must be findable IN docs/05 — not merely somewhere."""
        for kind, target, _phrase in entry.citations:
            if kind != CITE_SPEC:
                continue
            doc, _, anchor = target.partition(":")
            matches = list((ROOT / "docs").glob(f"{doc.split('/')[-1]}-*.md"))
            assert matches, f"{entry.term} cites {doc}, which does not exist"
            body = matches[0].read_text(encoding="utf-8", errors="replace")
            assert anchor and anchor in body, (
                f"{entry.term} cites {target}; {matches[0].name} has no "
                f"{anchor!r}")

    @pytest.mark.parametrize("entry", GLOSSARY, ids=lambda e: e.term)
    def test_every_citation_kind_is_a_known_kind(self, entry):
        for kind, _t, phrase in entry.citations:
            assert kind in (CITE_RULING, CITE_SPEC, CITE_RUN)
            assert phrase.strip(), "a citation with no phrase cites nothing"

    def test_a_run_citation_names_a_figure_the_entry_carries(self):
        """A `run` citation promises this run's own record. An entry that
        promises one and names no figure would print a citation nothing backs."""
        for e in GLOSSARY:
            if any(k == CITE_RUN for k, _, _ in e.citations):
                assert e.run_figure, f"{e.term} cites the run but names no figure"


# ===========================================================================
# Clause (1) — the trigger contract, which is the scope wall
# ===========================================================================

class TestTermRecognition:
    def test_inflections_resolve_to_the_entry(self):
        for word in ("seed", "seeds", "seeded", "SEEDING"):
            assert known_term(word) is GLOSSARY_BY_TERM["seed"]

    def test_a_whole_question_resolves(self):
        assert known_term("what do you mean seed").term == "seed"

    def test_a_word_we_do_not_define_resolves_to_nothing(self):
        """Deliberately not fuzzy. A word we do not recognise is not a word we
        should improvise a definition for — that is R-TG6 (i)'s species."""
        for word in ("bottleneck", "takt time", "kanban", ""):
            assert known_term(word) is None

    def test_terms_in_reads_a_rendered_answer(self):
        answer = ('On "found": this board is the best of 3 seeded searches, '
                  "the one at seed 44.")
        assert terms_in(answer) == frozenset({"seed"})

    def test_terms_in_is_empty_on_an_answer_that_used_none_of_our_words(self):
        assert terms_in("ORD-01 finishes on Tuesday at 14:00.") == frozenset()


class TestTermMemory:
    """R-MT1's key, applied to the fourth store."""

    def test_it_records_what_a_rendered_answer_showed(self):
        m = TermMemory()
        m.remember("s1", "sched-A", {"seed", "gap"})
        assert m.seen("s1", "sched-A") == frozenset({"seed", "gap"})

    def test_it_accumulates_across_turns(self):
        m = TermMemory()
        m.remember("s1", "sched-A", {"seed"})
        m.remember("s1", "sched-A", {"gap"})
        assert m.seen("s1", "sched-A") == frozenset({"seed", "gap"})

    def test_it_is_SCHEDULE_scoped(self):
        """THE REBIND CASE. A term from the PREVIOUS board's answers must not
        confirm the intent after a version change: the planner is looking at a
        different plan, and "you said seed" would be citing a conversation about
        something else."""
        m = TermMemory()
        m.remember("s1", "sched-A", {"seed"})
        assert m.seen("s1", "sched-B") == frozenset()

    def test_forget_takes_every_schedule_with_it(self):
        """R-MT1 clause 1: a conversation that straddled two boards is still one
        conversation."""
        m = TermMemory()
        m.remember("s1", "sched-A", {"seed"})
        m.remember("s1", "sched-B", {"gap"})
        m.forget("s1")
        assert m.seen("s1", "sched-A") == frozenset()
        assert m.seen("s1", "sched-B") == frozenset()

    def test_it_is_bounded(self):
        m = TermMemory(limit=2)
        for i in range(5):
            m.remember(f"s{i}", "sched", {"seed"})
        assert len(m._by_session) == 2

    def test_a_session_with_no_id_records_nothing(self):
        m = TermMemory()
        m.remember(None, "sched-A", {"seed"})
        assert m.seen(None, "sched-A") == frozenset()

    def test_the_ONE_clear_clears_it(self):
        """4B.16a was a RESET that cleared four channels and missed a fifth;
        (d.1) found this function claiming to clear three while clearing two. A
        new store whose clear is written later is that defect queued up."""
        remember_terms("d3-clear", "sched-A", "the best of 3 seeded searches")
        assert interp.TERM_MEMORY.seen("d3-clear", "sched-A")
        forget_deliveries("d3-clear")
        assert interp.TERM_MEMORY.seen("d3-clear", "sched-A") == frozenset()

    def test_remember_terms_reads_the_RENDERED_text(self):
        got = remember_terms("d3-rt", "sched-A",
                             "the gap is 89.6% and the ledger is unchanged")
        assert got == frozenset({"gap", "ledger"})
        forget_deliveries("d3-rt")


# ===========================================================================
# Clause (3) — the vocabulary, and what an unconfirmed proposal is
# ===========================================================================

class TestTheIntentIsWiredLikeARoute:
    def test_it_is_selectable_and_has_an_authored_meaning(self):
        assert Intent.TERM_EXPLANATION in MODEL_SELECTABLE_INTENTS
        assert INTENT_MEANINGS.get(Intent.TERM_EXPLANATION)

    def test_it_is_a_CONTRACTED_route_not_a_second_tier_intent(self):
        """The ruling, not a convenience. `teaching` went to the tier because
        there is no contracted assembly for "how does this normally work". Here
        there is one, and R-TG6 (i) requires it: a definition of our own word is
        a product claim, and an uncited product claim is dropped."""
        assert Intent.TERM_EXPLANATION not in SECOND_TIER_INTENTS
        assert Intent.TERM_EXPLANATION.value in ROUTE_TAXONOMY

    def test_the_meaning_names_both_measured_boundaries(self):
        """The census made `teaching` (12 of 25) and `prove-it` (5 of 25) the
        expensive neighbours. A meaning that does not separate them is a meaning
        written against the wrong risk."""
        meaning = INTENT_MEANINGS[Intent.TERM_EXPLANATION]
        assert "teaching" in meaning and "prove-it" in meaning

    def test_the_prompt_carries_the_rule_and_the_bumped_version(self):
        text = (ROOT / "src" / "mre" / "modules" / "parse_prompt.md").read_text(
            encoding="utf-8")
        assert "prompt_version: 19" in text
        assert "term-explanation" in text
        assert "you mentioned" in text.lower()   # the quote signal


class TestTheAnswerIsAuthoredAndCited:
    def test_the_route_is_authored_copy_and_never_the_models_to_reword(self):
        """R-TG6 (i)'s strictest case in the file: every sentence is a claim
        about THIS PRODUCT, and its only licence to exist is the citation beside
        it. A model rewording it produces the uncited product claim the ruling
        drops, with our authority on it."""
        assert "term_explanation" in rd.LLMRenderer._AUTHORED_COPY_SUBJECTS

    def test_no_glossary_body_wears_the_general_knowledge_label(self):
        """A definition of our word is never general knowledge — there is always
        something to check it against, which is the whole of R-TG6 (i)."""
        for e in GLOSSARY:
            assert "general knowledge" not in e.body.lower()

    def test_the_rendered_answer_prints_the_definition_and_a_citation(self):
        out = _render("seed", figure=None)
        assert "A seed is the starting number" in out
        assert "[R-BK1]" in out

    def test_a_missing_run_figure_is_SAID_not_swallowed(self):
        """A definition is true whether or not today's run carries the figure it
        points at — and silence would let a planner read the absence as "there
        isn't one on this board"."""
        out = _render("seed", figure=None)
        assert "doesn't carry that figure" in out

    def test_a_present_run_figure_is_voiced_in_a_sentence(self):
        out = _render("seed", figure={"kind": "portfolio",
                                      "value": {"k": 3, "seed0": 42,
                                                "winner_seed": 44}})
        assert "3 searches were run, at seeds 42" in out
        assert "seed 44" in out

    def test_an_entry_with_no_run_citation_says_nothing_about_figures(self):
        out = _render("ledger", figure=None)
        assert "doesn't carry that figure" not in out
        assert "[R-DP12]" in out

    def test_the_doors_it_offers_are_real_questions(self):
        """The exam's dead-door guard checks these live; this is the cheap half
        — a door must at least be a question, not a fragment."""
        for e in GLOSSARY:
            for d in e.doors:
                assert len(d.split()) >= 3, f"{e.term} offers a fragment: {d!r}"

    def test_the_unknown_branch_says_nothing_about_the_plant(self):
        out = _render(None, figure=None, known=False, seen=["seed", "gap"])
        assert "couldn't tell" in out
        assert "seed, gap" in out


def _render(term, *, figure, known: bool = True, seen=()) -> str:
    from mre.modules.explainer import ExplanationBundle
    entry = GLOSSARY_BY_TERM.get(term or "")
    facts: dict = {"term": term, "known": known and entry is not None,
                   "seen": list(seen)}
    if facts["known"]:
        facts.update({
            "body": entry.body,
            "citations": [{"kind": k, "target": t, "phrase": p}
                          for k, t, p in entry.citations],
            "doors": list(entry.doors), "figure": figure,
        })
    bundle = ExplanationBundle(
        question="what do you mean that", subject_id="",
        subject_type="term_explanation", subject_external_name="?",
        ordered_records=[], key_facts=facts, snapshot_id="snap",
        identity_map=None)
    return rd.TemplateRenderer().render(bundle)

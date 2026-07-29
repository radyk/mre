"""The tiered document corpus and its currency gate (Session 4B.15 Item 1).

Written from the session brief's acceptance clause 2: the corpus is indexed IN
TIERS, no capability claim is grounded in docs/07, every docs/04 claim is dated
and marked historical, and what was excluded is reported.
"""
from __future__ import annotations

import json

import pytest

from mre.modules.corpus import (
    DOCS_DIR,
    EXCLUDED_INTERNAL,
    INDEX_PATH,
    MANIFEST,
    TIERS_FOR_PURPOSE,
    UNREACHABLE_TIERS,
    Corpus,
    CorpusTier,
    Purpose,
    build_index,
    excluded_report,
    fingerprint,
    load_corpus,
)


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    c = load_corpus()
    assert c is not None, "the committed corpus index must load"
    return c


class TestCurrency:
    """THE CURRENCY GATE. `docs/` is deliberately not in the runtime image, so
    the corpus ships as a committed index — and an index that silently drifts
    from the specs is the declared-but-never-consumed bug class one level up."""

    def test_index_matches_the_live_docs(self, corpus):
        """Editing a spec without rebuilding the index is a RED TEST.

        If this fails: python tools/build_corpus_index.py
        """
        indexed = corpus.doc_fingerprints()
        for doc in MANIFEST:
            live = fingerprint((DOCS_DIR / doc.filename).read_text(encoding="utf-8"))
            assert indexed.get(doc.doc_id) == live, (
                f"{doc.doc_id} has changed since the corpus index was built. "
                f"Rebuild it: python tools/build_corpus_index.py")

    def test_index_is_committed_package_data(self):
        assert INDEX_PATH.exists()
        assert INDEX_PATH.parent.name == "mre", (
            "the index must sit inside the package, not beside it — docs/ does "
            "not ship in the runtime image")
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        assert payload["passages"], "an empty corpus is a broken corpus"

    def test_every_manifest_document_is_indexed(self, corpus):
        got = {p.doc_id for p in corpus.passages}
        assert got == {d.doc_id for d in MANIFEST}


class TestTierBoundaries:
    """The three boundaries the brief calls hard."""

    def test_no_purpose_reaches_the_roadmap(self):
        """docs/07 describes what we INTEND to build, which to a retriever is
        indistinguishable from what we DID build. No capability claim may be
        grounded in it — enforced by the tier map, not asked for in a prompt."""
        assert CorpusTier.INTENT in UNREACHABLE_TIERS
        for purpose, tiers in TIERS_FOR_PURPOSE.items():
            assert CorpusTier.INTENT not in tiers, (
                f"{purpose.value} can reach the roadmap")

    @pytest.mark.parametrize("query", [
        "operator pool", "changeover", "splittable", "coarse horizon",
        "past due", "roadmap", "phase 4", "what comes next",
    ])
    def test_capability_retrieval_returns_current_tier_only(self, corpus, query):
        for p in corpus.retrieve(query, Purpose.CAPABILITY, limit=8):
            assert p.tier is CorpusTier.CURRENT, (
                f"{query!r} reached {p.doc_id} ({p.tier.value})")

    def test_capability_retrieval_never_reaches_design_history(self, corpus):
        """docs/04 carries SUPERSEDED rulings as first-class text — R-SC3(2)
        priced earliness at 0.05/min and is present both as a landed ruling and
        as a retired one. A capability answer citing it would state a retired
        mechanism as current, with a real citation."""
        hits = corpus.retrieve("earliness value price per minute",
                               Purpose.CAPABILITY, limit=10)
        assert hits, "the query should match something in the current specs"
        assert all(p.doc_id != "docs/04" for p in hits)

    def test_design_rationale_may_reach_history(self, corpus):
        hits = corpus.retrieve("why precedence edges became first-class records",
                               Purpose.DESIGN_RATIONALE, limit=10)
        assert any(p.tier is CorpusTier.HISTORICAL for p in hits), (
            "the why-was-it-designed-this-way purpose must reach docs/04")


class TestHistoricalIsDated:
    """Every claim drawn from docs/04 is DATED and marked as history."""

    def test_every_historical_passage_carries_a_date(self, corpus):
        for p in corpus.passages:
            if p.tier is CorpusTier.HISTORICAL:
                assert p.dated, f"undated historical passage: {p.heading}"

    def test_historical_citation_says_it_is_history(self, corpus):
        hist = [p for p in corpus.passages if p.tier is CorpusTier.HISTORICAL]
        assert hist
        for p in hist[:50]:
            cite = p.citation
            assert "history" in cite
            assert p.dated in cite
            assert "may be superseded" in cite

    def test_current_citation_is_not_marked_history(self, corpus):
        # The MARKER, not the word: a current spec may legitimately have a
        # heading that mentions the design history as a cross-reference.
        cur = [p for p in corpus.passages if p.tier is CorpusTier.CURRENT]
        assert cur
        assert all("[history," not in p.citation for p in cur)
        assert all("may be superseded" not in p.citation for p in cur)

    def test_undated_sections_are_dropped_not_served_bare(self, corpus):
        """FAIL CLOSED. docs/04's 15 founding `D-nn` decisions carry no date in
        their headings, so they are unservable rather than servable without the
        marker the rule requires. Reported, never swallowed."""
        dropped = corpus.dropped_undated
        assert dropped.get("docs/04", 0) > 0
        assert all(not p.heading.startswith("D-")
                   for p in corpus.passages if p.tier is CorpusTier.HISTORICAL)


class TestInternalExclusion:
    """Internal content is OUT, and the exclusion is REPORTED so the decision to
    admit any of it is made once and deliberately."""

    def test_internal_paths_are_not_in_the_manifest(self):
        names = {d.filename for d in MANIFEST}
        for forbidden in ("CLAUDE.md", "00-README.md", "02-evidence-contract-spec.md"):
            assert forbidden not in names

    def test_no_passage_comes_from_a_closeout_or_claude_md(self, corpus):
        assert all(p.doc_id.startswith("docs/") for p in corpus.passages)
        assert all("closeout" not in p.doc_id.lower() for p in corpus.passages)

    def test_the_exclusion_report_names_what_and_why(self):
        report = excluded_report()
        assert len(report) == len(EXCLUDED_INTERNAL)
        for row in report:
            assert row["what"] and row["why"]
            assert len(row["why"]) > 40, "a reason, not a label"


class TestRebuildIsDeterministic:
    def test_build_index_is_stable(self):
        a, b = build_index(), build_index()
        assert a == b

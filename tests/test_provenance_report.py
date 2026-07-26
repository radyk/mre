"""Provenance telemetry and the frequency-weighted Pareto (R-AI5(5)/(6)).

Session 4A.5c CU1. Written from the ruling text: R-AI5(5) makes the
frequency-weighted Pareto of synthesis residue "the standing prioritization for
promoting recurring shapes to contracted intents", and R-AI5(6) protects
interpretive residue from being counted as backlog.

Every ledger here is HAND-BUILT, so the expected clusters and their ordering are
statements about the clustering rule rather than about whatever a sweep happened
to produce.
"""
from __future__ import annotations

import json

import pytest

from mre.contracts.question_ledger import ParseProvenance, QuestionLedgerEntry
from mre.contracts.synthesis import SynthesisProvenance, ToolCallLog
from mre.modules.provenance_report import (
    PROTECTED_CONVERSATIONAL,
    PROTECTED_INTERPRETIVE,
    PROTECTED_TAKE,
    cluster,
    pareto,
    render_report,
    report_payload,
    rows_from_ledger,
    tier_counts,
)


# ---------------------------------------------------------------------------
# Hand-built ledgers
# ---------------------------------------------------------------------------

def _claim(status: str, kind: str = "fact", text: str = "a claim") -> dict:
    return {"text": text, "status": status, "kind": kind,
            "record_ids": ["rec-1"], "load_bearing": False}


def entry(question: str, route: str = "synthesis", *, nearest=(), kinds=(),
          tools=(), verified: int = 0, interpretive: int = 0, failed: int = 0,
          conclusions: int = 0, unanswerable: bool = False,
          intent: str = "unmatched") -> QuestionLedgerEntry:
    claims: list = []
    for _ in range(verified):
        claims.append(_claim("verified"))
    for _ in range(interpretive):
        claims.append(_claim("interpretive"))
    for _ in range(failed):
        claims.append(_claim("failed"))
    for i in range(min(conclusions, len(claims))):
        claims[i]["kind"] = "conclusion"
    synthesis = None
    if route == "synthesis":
        synthesis = SynthesisProvenance(
            claims=claims,
            tool_calls=[ToolCallLog(tool=t) for t in tools],
            unanswerable=unanswerable)
    return QuestionLedgerEntry(
        entry_id=question, verbatim_question=question,
        resolved_question=question, route=route, source="parse",
        synthesis=synthesis,
        parse=ParseProvenance(intent=intent, nearest=list(nearest),
                              subject_kinds=list(kinds), confidence=0.9))


def write_ledger(tmp_path, entries) -> str:
    p = tmp_path / "ledger.jsonl"
    p.write_text("\n".join(e.model_dump_json() for e in entries) + "\n",
                 encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# The clustering rule
# ---------------------------------------------------------------------------

class TestClustering:

    def test_the_three_keys_decide_the_cluster(self, tmp_path):
        """Adjacency + subject kinds + DOMINANT tool. All three must match."""
        rows = rows_from_ledger(write_ledger(tmp_path, [
            entry("why so many late", nearest=("late-orders", "late-order"),
                  tools=("lateness_set", "lateness_set", "cost_ledger"),
                  verified=2, interpretive=1),
            entry("whats driving the lateness",
                  nearest=("late-order", "late-orders"),   # order must not matter
                  tools=("lateness_set", "cost_ledger", "lateness_set"),
                  verified=2, interpretive=1),
            # same tool, DIFFERENT adjacency -> a different shape
            entry("how bad is the money", nearest=("edit-cost",),
                  tools=("lateness_set",), verified=1),
            # same adjacency, DIFFERENT subject kinds -> a different shape
            entry("why is that order late", nearest=("late-orders", "late-order"),
                  kinds=("order",), tools=("lateness_set",), verified=1),
        ]))
        clusters = {c.cluster_id: c for c in cluster(rows)}
        merged = clusters["late-order+late-orders|no-subject|lateness_set"]
        assert merged.frequency == 2, "adjacency ORDER must not split a shape"
        assert "edit-cost|no-subject|lateness_set" in clusters
        assert "late-order+late-orders|order|lateness_set" in clusters

    def test_the_dominant_tool_is_the_key_not_the_whole_call_set(self, tmp_path):
        """The specimen from the 4A.5b residue: one extra exploratory call must
        not split a shape into two clusters of one."""
        rows = rows_from_ledger(write_ledger(tmp_path, [
            entry("a", nearest=("late-orders",),
                  tools=("lateness_set", "lateness_set", "cost_ledger"),
                  verified=2),
            entry("b", nearest=("late-orders",),
                  tools=("lateness_set", "lateness_set", "cost_ledger",
                         "placements_for_order"),
                  verified=2),
        ]))
        clusters = cluster(rows)
        assert len(clusters) == 1
        assert clusters[0].frequency == 2
        # the whole distinct set is still REPORTED, it is just not the key
        assert set(clusters[0].tools) >= {"lateness_set", "cost_ledger",
                                          "placements_for_order"}
        assert clusters[0].dominant_tool == "lateness_set"

    def test_only_synthesis_rows_cluster(self, tmp_path):
        """A contracted answer is not residue, and a floor answer read nothing —
        clustering it would fabricate a shape out of two empty tuples."""
        rows = rows_from_ledger(write_ledger(tmp_path, [
            entry("routed", route="late-orders", intent="late-orders"),
            entry("refused", route="NEAR_MISS"),
            entry("clarified", route="CLARIFY"),
            entry("reasoned", nearest=("late-orders",), tools=("lateness_set",),
                  verified=1),
        ]))
        assert len(cluster(rows)) == 1
        tiers = tier_counts(rows)
        assert tiers == {**tiers, "contracted": 1, "synthesis": 1, "floor": 2,
                         "questions": 4}


# ---------------------------------------------------------------------------
# R-AI5(6) — the protection
# ---------------------------------------------------------------------------

class TestProtectedResidue:

    def test_a_predominantly_interpretive_shape_is_not_backlog(self, tmp_path):
        rows = rows_from_ledger(write_ledger(tmp_path, [
            entry("is the work spread evenly", nearest=("inventory",),
                  tools=("machine_occupancy",), verified=1, interpretive=5),
        ]))
        c = cluster(rows)[0]
        assert not c.promotable
        assert c.protected == PROTECTED_INTERPRETIVE
        assert pareto([c]) == [], "protected residue never enters the Pareto"

    def test_a_take_is_protected_even_when_it_grounds(self, tmp_path):
        """Conclusions are the model's own reading. A shape that is mostly
        conclusions is a take, and R-AI5(6) protects takes as first-class
        conversation — the verified share does not rescue it into backlog."""
        rows = rows_from_ledger(write_ledger(tmp_path, [
            entry("is this a good plan", nearest=("briefing",),
                  tools=("cost_ledger",), verified=3, interpretive=1,
                  conclusions=3),
        ]))
        c = cluster(rows)[0]
        assert c.verified_share > 0.5
        assert not c.promotable
        assert c.protected == PROTECTED_TAKE

    def test_a_question_that_read_nothing_is_conversational(self, tmp_path):
        rows = rows_from_ledger(write_ledger(tmp_path, [
            entry("this is not helpful", tools=(), unanswerable=True),
        ]))
        c = cluster(rows)[0]
        assert not c.promotable
        assert c.protected == PROTECTED_CONVERSATIONAL

    def test_the_report_states_the_protection_in_its_own_header(self, tmp_path):
        """R-AI5(6) IN THE REPORT ITSELF. A reader must not have to know the
        ruling to know that the protected clusters are not a to-do list."""
        rows = rows_from_ledger(write_ledger(tmp_path, [
            entry("is the work spread evenly", nearest=("inventory",),
                  tools=("machine_occupancy",), verified=0, interpretive=4),
        ]))
        text = render_report(rows, source="hand-built")
        assert "R-AI5(6)" in text
        assert "NEVER ZERO" in text
        assert "NOT-PROMOTABLE-BY-DESIGN" in text
        assert "NOT improvement" in text
        assert "PROTECTED RESIDUE" in text
        # plain ASCII, like every other artifact a human reads in this repo
        assert all(ord(ch) < 128 for ch in text)

    def test_the_report_states_its_clustering_method(self, tmp_path):
        """Crude-but-stated beats clever-but-opaque: the method and its known
        weakness are both printed."""
        rows = rows_from_ledger(write_ledger(tmp_path, [
            entry("a", nearest=("late-orders",), tools=("lateness_set",),
                  verified=2),
        ]))
        text = render_report(rows, source="hand-built")
        assert "CLUSTERING METHOD" in text
        assert "intent adjacency" in text
        assert "subject kinds" in text
        assert "dominant tool" in text
        assert "not semantic clustering" in text
        assert "UNDER-states frequency" in text


# ---------------------------------------------------------------------------
# The Pareto
# ---------------------------------------------------------------------------

class TestPareto:

    def test_frequency_weighted_not_frequency_alone(self, tmp_path):
        """A shape asked 4x that grounds 3/4 of its claims should be built before
        one asked 5x that grounds 1/3 — frequency alone would invert this, and the
        promotion question is how much PROVEN answering a route would buy.

        Note the LOSER here is still promotable (its share clears the R-AI5(6)
        floor); it is ranked below, not protected. Ordering and protection are two
        different judgments and this test is about ordering."""
        rows = rows_from_ledger(write_ledger(tmp_path, [
            *[entry(f"often-{i}", nearest=("briefing",),
                    tools=("machine_occupancy",), verified=1, interpretive=2)
              for i in range(5)],
            *[entry(f"rare-{i}", nearest=("late-orders",),
                    tools=("lateness_set",), verified=3, interpretive=1)
              for i in range(4)],
        ]))
        ranked = pareto(cluster(rows))
        assert [c.frequency for c, _ in ranked] == [4, 5], \
            "the more frequent shape must rank BELOW the better-grounded one"
        assert ranked[0][0].cluster_id == "late-orders|no-subject|lateness_set"
        assert pytest.approx(ranked[0][0].weight, abs=0.01) == 3.0
        assert pytest.approx(ranked[1][0].weight, abs=0.01) == 1.67

    def test_cumulative_runs_over_promotable_weight_only(self, tmp_path):
        """R-AI5(6): "the top cluster is 60% of the backlog" must be a claim about
        what CAN be contracted, never about the conversation as a whole."""
        rows = rows_from_ledger(write_ledger(tmp_path, [
            entry("p1", nearest=("late-orders",), tools=("lateness_set",),
                  verified=3, interpretive=1),
            entry("p2", nearest=("edit-cost",), tools=("cost_ledger",),
                  verified=1, interpretive=1),
            # a large protected cluster that must not dilute the cumulative
            *[entry(f"take-{i}", nearest=("briefing",), tools=("cost_ledger",),
                    verified=0, interpretive=3) for i in range(20)],
        ]))
        ranked = pareto(cluster(rows))
        assert len(ranked) == 2
        assert ranked[-1][1] == pytest.approx(1.0)

    def test_ties_break_deterministically(self, tmp_path):
        """The report is committed. Two runs of the same ledger must produce the
        same ordering or every diff is noise."""
        entries = [
            entry("a", nearest=("late-orders",), tools=("lateness_set",),
                  verified=2, interpretive=2),
            entry("b", nearest=("edit-cost",), tools=("cost_ledger",),
                  verified=2, interpretive=2),
        ]
        rows = rows_from_ledger(write_ledger(tmp_path, entries))
        first = [c.cluster_id for c, _ in pareto(cluster(rows))]
        second = [c.cluster_id for c, _ in pareto(cluster(rows))]
        assert first == second == sorted(first)


class TestPayload:

    def test_the_json_twin_carries_the_method_and_the_ranks(self, tmp_path):
        rows = rows_from_ledger(write_ledger(tmp_path, [
            entry("a", nearest=("late-orders",), tools=("lateness_set",),
                  verified=3, interpretive=1),
            entry("b", nearest=("briefing",), tools=("cost_ledger",),
                  verified=0, interpretive=3),
        ]))
        payload = report_payload(rows, source="hand-built")
        assert payload["method"]["keys"] == [
            "intent_adjacency", "subject_kinds", "tool_pattern"]
        assert payload["method"]["semantic"] is False
        assert payload["method"]["under_states_frequency"] is True
        by_id = {c["cluster_id"]: c for c in payload["clusters"]}
        promoted = by_id["late-orders|no-subject|lateness_set"]
        protected = by_id["briefing|no-subject|cost_ledger"]
        assert promoted["pareto_rank"] == 1
        assert protected["pareto_rank"] is None
        assert protected["promotable"] is False
        assert protected["protected_reason"]
        # round-trips as JSON (it is committed beside the transcript)
        json.loads(json.dumps(payload))


class TestReconstruction:

    def test_a_reconstructed_row_is_flagged_not_silently_weaker(self):
        """A committed sweep transcript carries no `nearest`, so clustering it
        falls back to a weaker key. The report must SAY so rather than present the
        two methods as one."""
        from mre.modules.provenance_report import _rows_from_transcript
        rows = _rows_from_transcript(
            "Q[1]: why so many late orders\n"
            "  route=synthesis  source=parse\n"
            "  parse: intent=unmatched  conf=0.85\n"
            "  synthesis: claims=3  verified=2  interpretive=1  cut=0  "
            "tools=2(lateness_set,cost_ledger)\n")
        assert len(rows) == 1
        assert rows[0].route == "synthesis"
        assert rows[0].verified == 2 and rows[0].interpretive == 1
        assert rows[0].tools == ["lateness_set", "cost_ledger"]
        assert rows[0].adjacency_unknown is True
        text = render_report(rows, source="a committed sweep")
        assert "RECONSTRUCTED" in text
        assert "adjacency-unknown" in text

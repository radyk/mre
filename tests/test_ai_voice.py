"""The AI voice — the audit corpus as standing acceptance (Session 4A.2, CU10).

The founder's Glass Box close named ~14 conversation defects with verbatim
specimens (the question ledger). This session fixes them; this file is the
measurement and the permanent regression:

  * Fast units — the planner-language layer (driver/finding phrasing, the
    four-part finding sentence, coalescence), the register-tag seam (chip ==
    envelope), and the jargon strip. No solve.
  * The audit corpus (slow) — EVERY named specimen re-run through the finished
    stack against a real Glass Box solve. Each must land in exactly one of three
    honest outcomes — correct-and-on-question, honest-bridge, or honest-refusal —
    and NEVER confident-wrong (answer-the-noun / answer-the-wrong-noun / a
    nonsense self-diff). The aggregate score is asserted zero confident-wrong.

The corpus is the audit made permanent: a future change that reopens any
specimen fails here.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.modules.evidence_index import EvidenceIndex
from mre.modules.explainer import Explainer, register_of
from mre.modules.planner_language import (
    DRIVER_PHRASING, FINDING_PHRASING, compose_finding_sentence,
    compose_findings, driver_phrase, finding_phrase, has_jargon, strip_jargon,
)
from mre.modules.renderers import TemplateRenderer
from mre.modules.snapshot_store import SnapshotStore

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "glass_box"


# ===========================================================================
# Fast units — the planner-language layer (no solve)
# ===========================================================================

class TestPlannerLanguage:
    def test_every_driver_code_has_a_phrase(self):
        from mre.contracts.vocabularies import DriverCode
        for code in DriverCode:
            assert code.value in DRIVER_PHRASING, f"{code} has no planner phrase"
            assert driver_phrase(code.value)
            assert not has_jargon(DRIVER_PHRASING[code.value])

    def test_every_finding_code_has_a_phrase(self):
        from mre.contracts.vocabularies import FindingCode
        for code in FindingCode:
            assert code.value in FINDING_PHRASING, f"{code} has no planner phrase"
            assert finding_phrase(code.value)

    def test_finding_phrase_falls_back_never_leaks_raw_code(self):
        # An unknown code returns a neutral clause, never the raw code.
        out = finding_phrase("SOME_FUTURE_CODE")
        assert "SOME_FUTURE_CODE" not in out and out

    def test_compose_finding_sentence_has_four_parts(self):
        finding = {
            "code": "VALUE_OUT_OF_RANGE", "severity": "warning",
            "disposition": "excluded", "module": "M0",
            "evidence": {"order_id": "ORD-09", "value": -60,
                         "rule_id": "ids.order_quantities_are_positive"},
            "subjects": [],
        }
        from mre.catalog import load_catalog
        c = compose_finding_sentence(finding, None, load_catalog())
        assert c["subject"] == "ORD-09"          # subject present
        assert c["value"] == "-60"                # offending value present
        assert "plausible range" in c["cause"]    # plain cause, not the code
        assert "VALUE_OUT_OF_RANGE" not in c["cause"]
        assert c["fix"]                           # catalog fix present

    def test_coalescence_same_defect_multiple_layers_is_one(self):
        # The same order failing the same way, caught at two layers, is ONE
        # problem "confirmed at 2 layers" — not two entries that lie about count.
        f_gate = {"code": "ORPHAN_ENTITY", "severity": "error", "module": "M0",
                  "evidence": {"order_id": "ORD-06"}, "subjects": []}
        f_adap = {"code": "ORPHAN_ENTITY", "severity": "error", "module": "M1",
                  "evidence": {"order_id": "ORD-06"}, "subjects": []}
        composed = compose_findings([f_gate, f_adap], None, None)
        assert len(composed) == 1
        assert composed[0]["layer_count"] == 2
        assert set(composed[0]["layers"]) == {"M0", "M1"}

    def test_strip_jargon_removes_module_and_uuid_tokens(self):
        leak = ("identity_v1: demand 808ea499-7bd6-5e3d-b9d6-3146cff401cb -> "
                "1 WorkPackage")
        out = strip_jargon(leak)
        assert not has_jargon(out)
        assert "identity_v1" not in out and "WorkPackage" not in out


class TestFormattingStrip:
    """CU3 (Session 4A.2b) — markdown / backtick leakage stripped at one seam."""

    def test_strip_formatting_removes_markdown_and_backticks(self):
        from mre.modules.planner_language import strip_formatting
        out = strip_formatting("## Header\nall `violated` first and **bold** __x__")
        assert "`" not in out and "**" not in out and "__" not in out
        assert not out.lstrip().startswith("#")
        assert "violated" in out and "bold" in out and "Header" in out

    def test_strip_formatting_leaves_structure(self):
        from mre.modules.planner_language import strip_formatting
        s = "=== q ===\n  - item\n[record: abcd1234...]\ncites IDS §5.1"
        assert strip_formatting(s) == s          # brackets/bullets/§ untouched

    def test_strip_formatting_idempotent(self):
        from mre.modules.planner_language import strip_formatting
        once = strip_formatting("`x` **y**")
        assert strip_formatting(once) == once


class TestNamedInput:
    """CU4 (Session 4A.2b) — a defaulted-input finding names the INPUT (planner
    words), the affected orders (capped), and a fix; never bare indices."""

    def test_low_confidence_names_input_affected_and_fix(self):
        finding = {
            "code": "LOW_CONFIDENCE_INPUT", "severity": "warning",
            "disposition": "proceeded_flagged", "module": "M3",
            "evidence": {"attribute": "customer_weight", "affected_count": 13,
                         "reason": "customer_weight is defaulted/synthesized for "
                                   "13 demands; tardiness priority is unreliable"},
            "subjects": [],
        }
        c = compose_finding_sentence(finding, None, None)
        assert "customer priority weight" in c["cause"]
        assert "customer_weight" not in c["cause"]      # raw column never leaks
        assert "13 order" in c["cause"]
        assert c["input"] == "the customer priority weight"
        assert c["affected"]["count"] == 13
        assert c["fix"] and "priority" in c["fix"].lower()


class TestRegisterCoherence:
    """CU2 (Session 4A.2b) — remediation/triage never contradict testimony. An
    advisory finding (no gate outcome) renders "no action required", never
    "nothing"/"clean" opposite a reported problem."""

    def _advisory(self):
        return [{"code": "LOW_CONFIDENCE_INPUT", "severity": "warning",
                 "disposition": "proceeded_flagged", "module": "M3",
                 "evidence": {"attribute": "customer_weight", "affected_count": 13},
                 "subjects": []}]

    def test_triage_advisory_not_nothing(self):
        from mre.modules.triage import render_triage_body
        body = render_triage_body(self._advisory())
        assert "advisory" in body.lower() and "no action required" in body.lower()
        assert "nothing to prioritize" not in body.lower()
        assert "customer priority weight" in body

    def test_remediation_advisory_not_nothing(self):
        from mre.modules.remediation import render_remediation_body
        body = render_remediation_body(self._advisory())
        assert "advisory" in body.lower() and "no action required" in body.lower()
        assert "nothing to remediate" not in body.lower()

    def test_truly_clean_still_reads_clean(self):
        from mre.modules.triage import render_triage_body
        from mre.modules.remediation import render_remediation_body
        assert "nothing to prioritize" in render_triage_body([])
        assert "nothing to remediate" in render_remediation_body([])


class TestRegisterSeam:
    """CU6 — the chip (API metadata) and the envelope (rendered footer) resolve
    through the SAME source, so they can never disagree."""

    @pytest.mark.parametrize("subject_type,expected", [
        ("findings", "testimony"),        # enumerating findings is testimony
        ("demand", "testimony"),
        ("triage", "judgment"),
        ("remediation", "remediation"),
        ("briefing", "testimony"),
        ("order_attributes", "testimony"),
    ])
    def test_chip_equals_envelope(self, subject_type, expected):
        from mre.modules.renderers import _register_for
        from mre.modules.explainer import ExplanationBundle
        b = ExplanationBundle(question="q", subject_id="s", subject_type=subject_type,
                              subject_external_name="s", ordered_records=[],
                              key_facts={}, snapshot_id="snap")
        assert register_of(b) == expected           # the chip
        assert _register_for(b) == expected          # the envelope
        assert register_of(b) == _register_for(b)


# ===========================================================================
# The audit corpus (slow) — every specimen through a real solve
# ===========================================================================

def _copy_dataset(tmp_path: Path) -> Path:
    dst = tmp_path / "sub"
    shutil.copytree(DATASET, dst)
    shutil.rmtree(dst / "gate_output", ignore_errors=True)
    return dst


def _rewrite_csv(path: Path, mutate) -> None:
    rows = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(mutate(rows)) + "\n", encoding="utf-8")


def _mutate_bracket_unroutable(rows):
    out = [rows[0]]
    for ln in rows[1:]:
        p = ln.split(",")
        if p[:2] == ["RT-BRACKET", "10"]:
            p[3] = "0"  # zero active rows -> ORD-06/07/08 unroutable, excluded
        out.append(",".join(p))
    return out


def _explainer_for(out: Path, snap: str) -> Explainer:
    idx = EvidenceIndex.load(out / "evidence_index.json")
    store = SnapshotStore(out / "snapshots")
    return Explainer(store, idx, snapshot_id=snap)


@pytest.fixture(scope="module")
def clean(tmp_path_factory):
    out = tmp_path_factory.mktemp("voice_clean")
    rc = mre_main(["--submission", str(DATASET), "--out", str(out),
                   "--snapshot-id", "snap-v", "--solver-workers", "1",
                   "--solver-seed", "0"])
    assert rc == 0
    return _explainer_for(out, "snap-v")


@pytest.fixture(scope="module")
def sabotaged(tmp_path_factory):
    """A Glass Box solve with RT-BRACKET zero-active — ORD-06/07/08 are excluded.
    The relevance guard (CU1), the proactive excluded volunteer (CU9), and the
    subject-bearing finding render (CU2) are exercised here."""
    sub = _copy_dataset(tmp_path_factory.mktemp("voice_sab_in"))
    _rewrite_csv(sub / "routing_lines.csv", _mutate_bracket_unroutable)
    out = tmp_path_factory.mktemp("voice_sab_out")
    rc = mre_main(["--submission", str(sub), "--out", str(out),
                   "--snapshot-id", "snap-s", "--solver-workers", "1",
                   "--solver-seed", "0"])
    assert rc == 0
    return _explainer_for(out, "snap-s")


def _mutate_earliness_forcing(sub: Path) -> None:
    """Session 4B.3a CU4b: declare a positive earliness_value and give PRESS-SLOW a
    hair-higher rate than PRESS-FAST. The rate delta is economically negligible
    (monolithic solves don't add earliness to the objective — the extractor uses it
    only for ATTRIBUTION), so the capacity-forced op stays on PRESS-SLOW (ORD-06,
    because PRESS-FAST holds the other two bracket ops), but the extractor now
    attributes it to EARLINESS_PREFERENCE by PRICE RANK. That is the docs/02 §4.2
    named limitation in the flesh — the real cause is capacity forcing, so the
    answer MUST hedge (name the preference AND that the cheaper machine may just
    have been busy)."""
    cm_path = sub / "cost_model.json"
    cm = json.loads(cm_path.read_text(encoding="utf-8"))
    cm["refinements"]["earliness_value"] = 0.05
    cm["refinements"]["resource_rates"]["PRESS-SLOW"] = 61.0
    cm_path.write_text(json.dumps(cm, indent=2), encoding="utf-8")


@pytest.fixture(scope="module")
def earliness_forcing(tmp_path_factory):
    """A Glass Box solve where ORD-06 is capacity-forced onto the (now marginally
    dearer) PRESS-SLOW with a positive earliness_value — so the extractor
    attributes the placement to EARLINESS_PREFERENCE even though capacity, not
    earliness, actually bound it (docs/02 §4.2). CU4b's hedge specimen."""
    sub = _copy_dataset(tmp_path_factory.mktemp("voice_ef_in"))
    _mutate_earliness_forcing(sub)
    out = tmp_path_factory.mktemp("voice_ef_out")
    rc = mre_main(["--submission", str(sub), "--out", str(out),
                   "--snapshot-id", "snap-ef", "--solver-workers", "1",
                   "--solver-seed", "0"])
    assert rc == 0
    return _explainer_for(out, "snap-ef")


def _answer(explainer: Explainer, q: str, ctx=None) -> str:
    from mre.modules.interpreter import run_ask
    res = run_ask(explainer, q, context=ctx)
    return TemplateRenderer().render(res.bundle)


def _ask(explainer: Explainer, q: str, ctx=None):
    """Return (AskResult, rendered_text) so a specimen can assert on route /
    resolved_question / resolution_note as well as the prose."""
    from mre.modules.interpreter import run_ask
    res = run_ask(explainer, q, context=ctx)
    return res, TemplateRenderer().render(res.bundle)


@pytest.mark.slow
class TestAuditCorpusClean:
    """The specimens whose correct answer is against the clean plan."""

    def test_cu1_product_question_reaches_product_not_lateness(self, clean):
        # answer-the-wrong-noun: "what product is ORD-01" was answered with
        # ORD-01's lateness. It must now answer the product.
        body = _answer(clean, "what product is ord-01").split("[rendered by")[0].lower()
        assert "p-widget" in body
        assert "minutes late" not in body and "past its due" not in body \
            and "minutes early" not in body

    def test_cu1_is_late_on_time_order_answers_correctly(self, clean):
        a = _answer(clean, "is ord-01 late").lower()
        assert "on time" in a
        assert "ord-05" not in a          # never the wrong-noun global answer

    def test_cu1_move_it_does_not_self_diff(self, clean):
        # "can we move it to a different machine" used to hit `"diff" in
        # "different"` -> a nonsense self-diff. It must refuse honestly instead.
        a = _answer(clean, "can we move it to a different machine")
        assert "no differences found" not in a.lower()
        assert "comparing snap" not in a.lower()

    def test_cu5_overlap_answers_integrity_not_a_listing(self, clean):
        a = _answer(clean, "it looks like ORD-04 and ORD-06 are running on the "
                    "same machine at the same time Mon 5").lower()
        assert "double-book" in a or "conflict-free" in a

    def test_cu5_inventory_counts(self, clean):
        a = _answer(clean, "how many jobs in total")
        assert "15 order" in a

    def test_cu5_split_jobs(self, clean):
        a = _answer(clean, "are there any split jobs").lower()
        assert "split" in a

    def test_cu5_start_reason_cites_release_bound(self, clean):
        # ORD-10 starts Friday because it isn't released until Friday.
        a = _answer(clean, "why does ORD-10 start on Friday?").lower()
        assert "releas" in a

    def test_cu5_attribute_customer(self, clean):
        a = _answer(clean, "what customer is ORD-04")
        assert "ORD-04" in a and "P-RUSH" in a

    def test_cu4_why_late_decompresses_the_driver(self, clean):
        # The causal story, not the bare CAPACITY_BLOCKED code.
        a = _answer(clean, "why is ord-05 late")
        assert "held by" in a.lower()
        assert "CAPACITY_BLOCKED" not in a         # the code never leaks
        assert "CUT-01" in a                        # the machine, not a uuid

    def test_cu4_start_earlier_via_context(self, clean):
        ctx = {"history": [{"order": "ORD-05", "machine": None,
                            "route": "late-order"}]}
        a = _answer(clean, "but why cant we start it earlier", ctx).lower()
        assert "ord-05" in a and ("held by" in a or "busy" in a or "releas" in a)

    def test_cu7_morning_briefing_is_a_triage(self, clean):
        a = _answer(clean, "what should I worry about today").lower()
        assert "attention" in a or "late" in a
        assert "ord-05" in a                        # the fire is named

    def test_cu3_drill_down_opens_a_finding(self, clean):
        a = _answer(clean, "tell me more about finding 1")
        assert "[WARNING]" in a or "warning" in a.lower()

    # ------- Session 4A.2b — the listening-session specimens -------

    def test_4b_cu1_why_late_names_the_culprit_order(self, clean):
        # CU1 — the rendered sentence names the blocking ORDER + release time,
        # not "busy with other work".
        a = _answer(clean, "why is ORD-05 late")
        assert "held by" in a.lower()
        assert "busy with other work" not in a.split("Evidence chain")[0].lower()

    def test_4b_cu1_blocked_by_pinned_into_llm_facts(self, clean):
        # CU1 — the blocker is pinned as a fact the LLM must quote, so it can't be
        # compressed back down to the driver phrase live.
        from mre.modules.renderers import LLMRenderer
        b = clean.answer("why is ORD-05 late")
        facts = LLMRenderer()._extract_precomputed_facts(b)
        assert facts.get("blocked_by_order")
        assert facts.get("blocking_machine") == "CUT-01"
        assert facts.get("blocking_until")

    def test_4b_cu5_bare_why_resolves_to_cause_chain(self, clean):
        ctx = {"history": [{"order": "ORD-05", "route": "late-order"}]}
        res, a = _ask(clean, "but why?", ctx)
        assert res.route == "late-order"
        assert res.resolved_question == "why is ORD-05 late?"
        assert "held by" in a.lower()

    def test_4b_cu5_set_reference_clarifies(self, clean):
        ctx = {"history": [{"order": "ORD-05", "route": "late-order"}]}
        res, a = _ask(clean, "and 10 of those have issues?", ctx)
        assert res.route == "CLARIFY"
        assert "10 of ORD-05" not in a          # never the mangled rewrite
        assert "group" in a.lower() or "which orders" in a.lower()

    def test_4b_cu5_verification_clarifies(self, clean):
        ctx = {"history": [{"order": "ORD-05", "route": "late-order"}]}
        res, a = _ask(clean, "you said i have 10 orders with issues is that correct", ctx)
        assert res.route == "CLARIFY"
        assert "confirm" in a.lower() or "evidence" in a.lower()

    def test_4b_cu6_fuzzy_ids_resolve_with_assumption(self, clean):
        for q in ("why ir ord-o5 late", "why is ORD-5 late", "why is ord 05 late"):
            res, a = _ask(clean, q)
            assert res.route == "late-order", q
            assert "ORD-05" in res.resolved_question, q
            assert "assuming ORD-05" in res.resolution_note, q
            assert "held by" in a.lower(), q

    def test_4b_cu6_unresolvable_near_miss_says_so(self, clean):
        # An id of this dataset's shape that resolves to nothing is not fuzzy-
        # matched into a real order — it gets the honest "isn't in this schedule".
        res, a = _ask(clean, "why is ORD-99 late")
        assert res.route in ("unknown-entity", "late-orders")
        assert "isn't in this schedule" in a.lower() or "excluded" in a.lower() \
            or "ord-99" not in a.lower()

    def test_4b_cu2_registers_agree_on_the_advisory(self, clean):
        # CU2 end-to-end: testimony reports the problem; triage/remediation call it
        # advisory (no action), never "clean"/"nothing" — and all name the input.
        testimony = _answer(clean, "what data problems exist?").lower()
        triage = _answer(clean, "what should I fix first?").lower()
        remediation = _answer(clean, "how do i fix the problems").lower()
        assert "customer priority weight" in testimony
        assert "no action required" in triage and "nothing to prioritize" not in triage
        assert "no action required" in remediation and "nothing to remediate" not in remediation
        assert "customer priority weight" in triage

    def test_4b_cu3_no_markdown_or_backticks_across_corpus(self, clean):
        for q in ("why is ord-05 late", "what data problems exist?",
                  "what should I fix first?", "how do i fix the problems",
                  "what should I worry about today"):
            a = _answer(clean, q)
            assert "`" not in a and "**" not in a, f"formatting leaked in {q!r}: {a}"

    # ------- Session 4A.2d — R-AI2 correctness (CU1–CU3) + judgment voice -------

    def test_4d_cu1_deictic_resolves_against_selection_with_machine_present(self, clean):
        # "why is this on CUT-01" — a machine ref is present, but the deictic
        # "this" still needs a subject. It resolves against the live selection on
        # EVERY route; the literal token never reaches a route as an entity.
        ctx = {"selection": {"order": "ORD-05"}}
        res, a = _ask(clean, "why is this on CUT-01", ctx)
        assert res.route == "why-on-machine"
        assert "ORD-05" in res.resolved_question
        assert "this" not in res.resolved_question.lower().split("on")[0]

    def test_4d_cu1_deictic_no_selection_clarifies(self, clean):
        res, a = _ask(clean, "why is this on CUT-01", None)
        assert res.route == "CLARIFY"
        assert "this" not in a.lower().split("register")[0] or "which order" in a.lower()

    def test_4d_cu2_no_scope_placeholder_ever(self, clean):
        # "Nothing scheduled for all" — a scope placeholder — is unrepresentable.
        a = _answer(clean, "show me the schedule").lower()
        assert "nothing scheduled for all" not in a
        assert "full schedule" in a          # a conversational lead, not a raw dump

    def test_4d_cu3_direct_timing_leads_with_completion(self, clean):
        # A direct "when does X finish" leads with the asked quantity (completion),
        # the table only supplements.
        a = _answer(clean, "when does ORD-13 finish")
        head = a.split("[rendered by")[0]
        assert "completes" in head.lower()
        assert "ORD-13" in head
        # the completion sentence precedes any table row
        assert head.lower().index("completes") < (head.find("seq=") if "seq=" in head else len(head))

    def test_4d_judgment_offered_on_late_order(self, clean):
        # R-AI2(c) — a late order blocked by earlier work carries a LABELED
        # judgment offering the tradeoff, never blended into the testimony.
        a = _answer(clean, "why is ORD-05 late")
        assert "My take:" in a
        # the judgment names the tradeoff (pull the blocker, or accept the delay)
        take = a.split("My take:")[1].lower()
        assert "accept" in take or "pull" in take

    def test_cu6_no_jargon_leaks_across_the_corpus(self, clean):
        for q in ("why is ord-05 late", "what data problems exist?",
                  "how many jobs in total", "what product is ord-01",
                  "what should I worry about today"):
            body = _answer(clean, q).split("[rendered by")[0]
            assert not has_jargon(body), f"jargon leaked in answer to {q!r}: {body}"


@pytest.mark.slow
class TestAuditCorpusSabotaged:
    """The specimens that need real exclusions (ORD-06/07/08 dropped)."""

    def test_cu1_named_excluded_order_gets_the_excluded_answer(self, sabotaged):
        # The keystone: a named order that isn't in this schedule's world must
        # get the excluded answer, never a global answer wearing a "Yes".
        assert sabotaged._excluded_labels, "sabotage did not exclude any order"
        excluded = sorted(sabotaged._excluded_labels)[0]
        a = _answer(sabotaged, f"is {excluded} late").lower()
        assert "isn't in this schedule" in a or "excluded" in a
        assert "ord-05" not in a          # never the wrong-noun global answer

    def test_cu2_findings_carry_subject_value_cause(self, sabotaged):
        a = _answer(sabotaged, "what data problems exist?")
        # a subject (an excluded order) and a plain cause, not a bare code line.
        assert any(o in a for o in sabotaged._excluded_labels)
        assert "Total findings:" not in a          # the old subject-blind header

    def test_cu9_excluded_orders_volunteered(self, sabotaged):
        # A schedule with exclusions volunteers them in relevant answers.
        a = _answer(sabotaged, "are there any late orders").lower()
        assert "exclud" in a

    def test_cu6_register_chip_equals_envelope_end_to_end(self, sabotaged):
        from mre.modules.interpreter import run_ask
        res = run_ask(sabotaged, "what data problems exist?")
        rendered = TemplateRenderer().render(res.bundle)
        assert res.register == "testimony"                 # the chip
        assert "register: testimony" in rendered            # the envelope


@pytest.mark.slow
class TestAuditCorpusEarlinessHedge:
    """Session 4B.3a CU4b — the attribution-limitation specimen. ORD-06 is
    capacity-forced onto PRESS-SLOW, but a positive earliness_value makes the
    extractor attribute it to EARLINESS_PREFERENCE (docs/02 §4.2: dearer-than-
    cheapest ⇒ EARLINESS_PREFERENCE, by price rank, with no occupancy check). A
    graded-correct answer HEDGES — it names the preference AND that capacity
    pressure may bind; a confidently unhedged single-cause answer is wrong."""

    def test_why_on_dearer_machine_hedges_to_the_limitation(self, earliness_forcing):
        res_and = _ask(earliness_forcing, "why is ORD-06 on PRESS-SLOW")
        res, a = res_and
        assert res.route == "why-on-machine"
        low = a.lower()
        # names the placement and the earliness attribution…
        assert "ord-06" in low and "press-slow" in low
        assert "earliness" in low
        # …AND hedges to the limitation (does NOT claim earliness as the sole
        # cause): the cheaper machine may simply have been busy (capacity forcing).
        assert "busy" in low or "capacity" in low, (
            "the answer must hedge — a confident single-cause EARLINESS_PREFERENCE "
            "answer is wrong (docs/02 §4.2 attribution limitation)")


@pytest.mark.slow
def test_cu10_zero_confident_wrong(clean, sabotaged, earliness_forcing):
    """The measurement: EVERY audit-corpus question lands correct-and-on-question,
    honest-bridge, or honest-refusal — zero confident-wrong. A confident-wrong
    answer is one that answers a DIFFERENT question than asked, or renders
    nonsense. The score is reported; the bar is zero."""
    # (question, explainer, context, a predicate that FAILS iff confident-wrong)
    def not_lateness(a):  # a product/attribute answer must not be a lateness verdict
        return "past its due" not in a.lower() and "minutes late" not in a.lower()

    def not_self_diff(a):
        return "no differences found" not in a.lower()

    corpus = [
        ("what product is ord-01", clean, None, not_lateness),
        ("what customer is ORD-04", clean, None, not_lateness),
        ("is ord-01 late", clean, None, lambda a: "ord-05" not in a.lower()),
        ("can we move it to a different machine", clean, None, not_self_diff),
        ("it looks like ORD-04 and ORD-06 are running on the same machine at "
         "the same time Mon 5",
         clean, None, lambda a: "double" in a.lower() or "conflict" in a.lower()),
        ("how many jobs in total", clean, None, lambda a: "15" in a),
        ("are there any split jobs", clean, None, lambda a: "split" in a.lower()),
        ("why does ORD-10 start on Friday?", clean, None,
         lambda a: "releas" in a.lower()),
        ("why is ord-05 late", clean, None, lambda a: "held by" in a.lower()),
        ("what should I worry about today", clean, None,
         lambda a: "ord-05" in a.lower()),
        ("what data problems exist?", clean, None, lambda a: True),
        ("are there any late orders", clean, None,
         lambda a: "ord-05" in a.lower()),
        ("what data problems exist?", sabotaged, None,
         lambda a: "Total findings:" not in a),
        # Session 4A.2b specimens
        ("why ir ord-o5 late", clean, None, lambda a: "held by" in a.lower()),
        ("why is ORD-5 late", clean, None, lambda a: "held by" in a.lower()),
        ("but why?", clean, {"history": [{"order": "ORD-05", "route": "late-order"}]},
         lambda a: "held by" in a.lower()),
        ("and 10 of those have issues?", clean,
         {"history": [{"order": "ORD-05", "route": "late-order"}]},
         lambda a: "10 of ORD-05" not in a),
        ("you said i have 10 orders with issues is that correct", clean,
         {"history": [{"order": "ORD-05", "route": "late-order"}]},
         lambda a: "Schedule for ORD-05" not in a),
        ("what should I fix first?", clean, None,
         lambda a: "nothing to prioritize" not in a.lower()),
        ("how do i fix the problems", clean, None,
         lambda a: "nothing to remediate" not in a.lower()),
        # Session 4A.2d specimens — the voice pass (correct AND conversational)
        ("show me the schedule", clean, None,
         lambda a: "nothing scheduled for all" not in a.lower() and "full schedule" in a.lower()),
        ("when does ORD-13 finish", clean, None, lambda a: "completes" in a.lower()),
        ("why is this on CUT-01", clean, {"selection": {"order": "ORD-05"}},
         lambda a: "ord-05" in a.lower()),
        # Session 4B.3a CU4b — the attribution-limitation specimen. A
        # capacity-forced placement attributed to EARLINESS_PREFERENCE must HEDGE;
        # a confident single-cause answer is confident-wrong (docs/02 §4.2).
        ("why is ORD-06 on PRESS-SLOW", earliness_forcing, None,
         lambda a: "busy" in a.lower() or "capacity" in a.lower()),
    ]
    wrong = []
    for q, ex, ctx, ok in corpus:
        a = _answer(ex, q, ctx)
        if not ok(a):
            wrong.append((q, a.split("[rendered by")[0].strip()[:200]))
    assert not wrong, "confident-wrong answers:\n" + "\n".join(
        f"  {q!r} -> {a}" for q, a in wrong)

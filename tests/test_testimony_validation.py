"""Testimony citation validation + the no-evidence guard (Session 4A.1c, R-AI1).

The gap this closes: LLM-rendered answers cited records that do not exist —
"[record: Nothing scheduled for all]", "[record: evidence_chain_001]"
(screenshots). The 4A.1 validator checked timestamps, time-unit numbers, machine
names, and that SOME footnote existed — but never that a cited record id is REAL.

Two disciplines pinned here:

  (A) every ``[record: X]`` in an LLM answer must name a real record in the
      bundle (prefix-match, since the template footnotes an 8-char prefix), else
      the answer is rejected and falls back to the deterministic template.

  (B) a bundle with NO evidence chain (an honest refusal / near-miss / clarify, or
      an empty schedule listing) is never handed to the LLM at all — there is
      nothing to testify from, so the model can only fabricate. It renders the
      authored template body verbatim.
"""
from __future__ import annotations

from mre.modules.explainer import ExplanationBundle
from mre.modules.renderers import LLMRenderer


class _FakeClient:
    """Returns a fixed text; records whether it was called."""
    def __init__(self, text: str):
        self._text = text
        self.calls = 0

    class _Messages:
        def __init__(self, outer):
            self._outer = outer

        def create(self, **_kw):
            self._outer.calls += 1
            import types
            return types.SimpleNamespace(
                content=[types.SimpleNamespace(text=self._outer._text)])

    @property
    def messages(self):
        return _FakeClient._Messages(self)


def _bundle_with_record() -> ExplanationBundle:
    return ExplanationBundle(
        question="why is WO-1 late?",
        subject_id="d",
        subject_type="demand",
        subject_external_name="WO-1",
        ordered_records=[{
            "record_type": "metric", "record_id": "abcd1234-5678-9012-3456",
            "module": "M7", "name": "lateness_minutes", "value": 840.0,
            "unit": "minutes", "subjects": [],
        }],
        key_facts={"lateness_minutes": 840.0, "due_date": "2026-07-13"},
        snapshot_id="snap-demo",
        identity_map=None,
    )


def _empty_schedule_bundle() -> ExplanationBundle:
    return ExplanationBundle(
        question="is there a better schedule",
        subject_id="",
        subject_type="schedule",
        subject_external_name="",
        ordered_records=[],
        key_facts={"rows": [], "filter_label": "all",
                   "empty_message": "Nothing scheduled for all"},
        snapshot_id="snap-demo",
        identity_map=None,
    )


# ---------------------------------------------------------------------------
# (A) — record citations must be real
# ---------------------------------------------------------------------------

def test_fabricated_id_shaped_citation_is_rejected():
    # The exact live symptom: an invented, id-shaped citation.
    r = LLMRenderer(_client=_FakeClient(
        "WO-1 finished 840 min late. [record: evidence_chain_001]"))
    out = r.render(_bundle_with_record())
    assert "[rendered by: template" in out, out
    assert "[rendered by: LLM" not in out


def test_prose_masquerading_as_a_citation_is_rejected():
    # The other live symptom: header prose stuffed into a [record: …].
    r = LLMRenderer(_client=_FakeClient(
        "WO-1 finished 840 min late. [record: Nothing scheduled for all]"))
    out = r.render(_bundle_with_record())
    assert "[rendered by: template" in out, out


def test_real_record_prefix_citation_passes():
    # The template footnotes an 8-char prefix; the LLM may cite the prefix.
    r = LLMRenderer(_client=_FakeClient(
        "WO-1 finished 840 min late. [record: abcd1234...]"))
    out = r.render(_bundle_with_record())
    assert "[rendered by: LLM" in out, out


def test_validate_testimony_flags_unknown_record():
    r = LLMRenderer(api_key="")
    issues = r._validate_testimony(
        "something happened [record: not-a-real-id]",
        set(), set(), set(), {"abcd1234-5678"})
    assert any("fabricated record citation" in i for i in issues)


def test_validate_testimony_accepts_known_record_prefix():
    r = LLMRenderer(api_key="")
    issues = r._validate_testimony(
        "something happened [record: abcd1234...]",
        set(), set(), set(), {"abcd1234-5678-9012"})
    assert not any("fabricated record citation" in i for i in issues)


def test_template_placeholder_citation_is_not_flagged():
    # A bare "?" (template's missing-id placeholder) is not a fabrication claim.
    r = LLMRenderer(api_key="")
    issues = r._validate_testimony(
        "[record: ?...]", set(), set(), set(), set())
    assert not any("fabricated record citation" in i for i in issues)


# ---------------------------------------------------------------------------
# (B) — a bundle with no evidence chain never reaches the LLM
# ---------------------------------------------------------------------------

def test_empty_evidence_bundle_never_calls_the_llm():
    client = _FakeClient("prose [record: Nothing scheduled for all]")
    r = LLMRenderer(_client=client)
    out = r.render(_empty_schedule_bundle())
    assert client.calls == 0, "an empty-evidence bundle must not be sent to the LLM"
    assert "[rendered by: template" in out
    # the authored header content survives verbatim
    assert "Nothing scheduled for all" in out


def test_refusal_bundle_renders_authored_copy_not_llm_prose():
    unsupported = ExplanationBundle(
        question="is there a better schedule",
        subject_id="", subject_type="unsupported", subject_external_name="",
        ordered_records=[],
        key_facts={"parsed": "is there a better schedule",
                   "supported_routes": ["why an order is late"]},
        snapshot_id="snap-demo", identity_map=None,
    )
    client = _FakeClient("Sure! Here is a better schedule... [record: made-up]")
    r = LLMRenderer(_client=client)
    out = r.render(unsupported)
    assert client.calls == 0
    assert "[rendered by: template" in out
    assert "can't answer" in out.lower() or "supported question types" in out.lower()

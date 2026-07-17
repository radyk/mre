"""Fail-closed rendering armor, on the REAL code path (Session 4A.1b, R-AI1).

The gap this closes: the 4A.1 fail-closed tests injected a mock client
(``_client=...``), so real construction (``anthropic.Anthropic(...)``) and the
real ``_call_llm`` call site were never exercised. A live key then routed a
taxonomy-shaped question deterministically — and 500'd at RENDER time, because
``_call_llm`` had no exception boundary. "Mocked fail-closed" is not
"real-path fail-closed".

These tests construct the renderer for real (a genuine — invalid — key, so
``anthropic.Anthropic`` actually builds), then inject the three failure modes at
the single call seam. None may raise; every one must degrade to the template.
"""
from __future__ import annotations

import pytest

from mre.modules.explainer import ExplanationBundle
from mre.modules.renderers import LLMRenderer

# Real construction needs the SDK installed (an invalid key still builds a
# client; the auth failure only surfaces on the first call). Without the SDK the
# renderer is simply unavailable — a different, already-covered fail-closed path.
pytest.importorskip("anthropic", reason="anthropic SDK required for real construction")

_INVALID_KEY = "sk-ant-invalid-DEADBEEF"


def _testimony_bundle() -> ExplanationBundle:
    """A testimony bundle (subject_type not in remediation/triage) WITH an
    evidence record → the LLM render path that calls the API. (A bundle with an
    empty evidence chain is short-circuited to the template before any LLM call —
    see test_testimony_validation.py — so it would not exercise _call_llm.)"""
    return ExplanationBundle(
        question="why is WO-1 on M-GEAR-01?",
        subject_id="op-1",
        subject_type="demand",
        subject_external_name="WO-1",
        ordered_records=[{
            "record_type": "metric", "record_id": "met-late-0001", "module": "M7",
            "name": "lateness_minutes", "value": 840.0, "unit": "minutes",
            "subjects": [],
        }],
        key_facts={"lateness_minutes": 840.0, "due_date": "2026-07-13"},
        snapshot_id="snap-demo",
        identity_map=None,
    )


def _register_bundle(kind: str) -> ExplanationBundle:
    return ExplanationBundle(
        question="how do I fix it?",
        subject_id="cert",
        subject_type=kind,           # "remediation" | "triage"
        subject_external_name="submission",
        ordered_records=[],
        key_facts={},
        snapshot_id="snap-demo",
        identity_map=None,
    )


def test_real_construction_with_invalid_key_is_available_but_never_calls_out():
    # Real construction: anthropic.Anthropic() builds a client even for a bad key
    # (it does NOT validate — the auth failure only surfaces on the first call).
    r = LLMRenderer(api_key=_INVALID_KEY)
    assert r._available is True, "construction with a set key must build the client"


def test_injected_auth_failure_degrades_to_template():
    r = LLMRenderer(api_key=_INVALID_KEY)

    def _auth_raise(_prompt):
        # what the SDK raises on a bad/expired key, simulated hermetically
        raise RuntimeError("401 authentication_error: invalid x-api-key")

    r._call_llm = _auth_raise
    out = r.render(_testimony_bundle())
    assert "[rendered by: template" in out
    assert "LLM error" in out


def test_injected_raised_exception_degrades_to_template():
    r = LLMRenderer(api_key=_INVALID_KEY)
    r._call_llm = lambda _p: (_ for _ in ()).throw(ValueError("boom"))
    out = r.render(_testimony_bundle())
    assert "[rendered by: template" in out


def test_garbage_response_fails_validation_and_degrades_to_template():
    r = LLMRenderer(api_key=_INVALID_KEY)
    # A response full of values absent from the (empty) evidence: an unknown
    # machine, an invented number, a fabricated timestamp. Validation rejects it,
    # regeneration returns the same garbage, and it falls back to the template.
    r._call_llm = lambda _p: (
        "WO-9999 ran on M-ZZZ-99 and finished 4321 min late on 2099-01-01. "
        "[record: zzz]"
    )
    out = r.render(_testimony_bundle())
    assert "[rendered by: template" in out


def test_malformed_response_object_degrades_to_template():
    # A response whose parsing raises (e.g. empty content → IndexError) must also
    # be caught, not propagate.
    r = LLMRenderer(api_key=_INVALID_KEY)
    r._call_llm = lambda _p: (_ for _ in ()).throw(IndexError("list index out of range"))
    out = r.render(_testimony_bundle())
    assert "[rendered by: template" in out


# subject_type → register label (remediation stays remediation; triage → judgment)
@pytest.mark.parametrize("kind,register", [("remediation", "remediation"),
                                           ("triage", "judgment")])
def test_register_render_is_fail_closed_too(kind, register):
    r = LLMRenderer(api_key=_INVALID_KEY)
    r._call_llm = lambda _p: (_ for _ in ()).throw(RuntimeError("boom"))
    out = r.render(_register_bundle(kind))
    assert "[rendered by: template" in out
    assert f"register: {register}" in out


def test_construction_never_raises_even_if_the_sdk_build_throws(monkeypatch):
    # Defense in depth: if anthropic.Anthropic() itself raised (a malformed proxy
    # env, an eager-validation change in a future SDK), construction must degrade
    # to unavailable, never propagate.
    import anthropic

    def _boom(*a, **k):
        raise RuntimeError("simulated SDK build failure")

    monkeypatch.setattr(anthropic, "Anthropic", _boom)
    r = LLMRenderer(api_key=_INVALID_KEY)
    assert r._available is False
    out = r.render(_testimony_bundle())          # unavailable → template
    assert "[rendered by: template" in out

"""THE TIER SPLIT IS TWO SEPARATE DIALS (Errand 4B.15a).

4B.15 measured the ask path against three model tiers and the recommendation was
a SPLIT — parse on Haiku 4.5, synthesis on Sonnet 5 — because the two layers do
different work: the parse is a closed-vocabulary classification and synthesis is
open reasoning over evidence. Daryn ruled: ship it.

THE BUG THIS FILE EXISTS TO PREVENT is the obvious tidy-up — one MODEL constant
that both layers read. That refactor looks like a simplification and silently
un-ships the measurement: moving synthesis to Sonnet would drag the parse with
it, and every future tier decision would be forced to move both together. So
these tests assert INDEPENDENCE, not any particular value beyond today's
shipped defaults.
"""
from __future__ import annotations

import pytest

from mre.modules import llm_compat
from mre.modules.question_parser import QuestionParser
from mre.modules.renderers import LLMRenderer
from mre.modules.synthesizer import Synthesizer


class TestShippedDefaults:
    def test_synthesis_ships_on_sonnet_5(self):
        assert llm_compat.SYNTHESIS_MODEL_DEFAULT == "claude-sonnet-5"

    def test_parse_stays_on_haiku(self):
        assert llm_compat.PARSE_MODEL_DEFAULT.startswith("claude-haiku-4-5")

    def test_the_two_governed_tiers_differ(self):
        # The whole point of the errand. If these ever become equal it must be
        # because a measurement said so, and this assertion is where that
        # conversation starts.
        assert (llm_compat.SYNTHESIS_MODEL_DEFAULT
                != llm_compat.PARSE_MODEL_DEFAULT)

    def test_voice_tier_is_its_own_constant_and_unmoved(self):
        # The LLM renderer's reword voice was not in the bench. It is named
        # separately so it cannot be swept along by a tier change.
        assert llm_compat.VOICE_MODEL_DEFAULT.startswith("claude-haiku-4-5")
        assert (llm_compat.VOICE_MODEL_DEFAULT
                != llm_compat.SYNTHESIS_MODEL_DEFAULT)

    def test_three_distinct_env_names(self):
        names = {llm_compat.PARSE_MODEL_ENV, llm_compat.SYNTHESIS_MODEL_ENV,
                 llm_compat.VOICE_MODEL_ENV}
        assert len(names) == 3


class TestConstructionReadsItsOwnDial:
    """Each call site takes its model from its OWN resolver — no shared read."""

    def test_parser_defaults_to_the_parse_model(self, monkeypatch):
        for env in (llm_compat.PARSE_MODEL_ENV, llm_compat.SYNTHESIS_MODEL_ENV,
                    llm_compat.VOICE_MODEL_ENV):
            monkeypatch.delenv(env, raising=False)
        assert QuestionParser()._model == llm_compat.PARSE_MODEL_DEFAULT

    def test_synthesizer_defaults_to_the_synthesis_model(self, monkeypatch):
        for env in (llm_compat.PARSE_MODEL_ENV, llm_compat.SYNTHESIS_MODEL_ENV,
                    llm_compat.VOICE_MODEL_ENV):
            monkeypatch.delenv(env, raising=False)
        assert Synthesizer()._model == llm_compat.SYNTHESIS_MODEL_DEFAULT

    def test_renderer_defaults_to_the_voice_model(self, monkeypatch):
        for env in (llm_compat.PARSE_MODEL_ENV, llm_compat.SYNTHESIS_MODEL_ENV,
                    llm_compat.VOICE_MODEL_ENV):
            monkeypatch.delenv(env, raising=False)
        assert LLMRenderer()._model == llm_compat.VOICE_MODEL_DEFAULT

    def test_an_explicit_model_still_wins(self):
        # The bench passes both tiers explicitly; that must keep working or the
        # next tier measurement cannot be run at all.
        assert Synthesizer(model="claude-opus-5")._model == "claude-opus-5"
        assert QuestionParser(model="claude-opus-5")._model == "claude-opus-5"


class TestOverridesDoNotBleed:
    """Setting one layer's env override must not move the other two."""

    @pytest.mark.parametrize("moved,expect", [
        (llm_compat.SYNTHESIS_MODEL_ENV,
         ("synthesis", "claude-opus-5", "claude-haiku-4-5-20251001",
          "claude-haiku-4-5-20251001")),
        (llm_compat.PARSE_MODEL_ENV,
         ("parse", "claude-sonnet-5", "claude-opus-5",
          "claude-haiku-4-5-20251001")),
        (llm_compat.VOICE_MODEL_ENV,
         ("voice", "claude-sonnet-5", "claude-haiku-4-5-20251001",
          "claude-opus-5")),
    ])
    def test_one_dial_moves_alone(self, monkeypatch, moved, expect):
        _label, want_synth, want_parse, want_voice = expect
        for env in (llm_compat.PARSE_MODEL_ENV, llm_compat.SYNTHESIS_MODEL_ENV,
                    llm_compat.VOICE_MODEL_ENV):
            monkeypatch.delenv(env, raising=False)
        monkeypatch.setenv(moved, "claude-opus-5")
        assert llm_compat.synthesis_model() == want_synth
        assert llm_compat.parse_model() == want_parse
        assert llm_compat.voice_model() == want_voice

    def test_an_empty_override_falls_back_to_the_default(self, monkeypatch):
        monkeypatch.setenv(llm_compat.SYNTHESIS_MODEL_ENV, "   ")
        assert llm_compat.synthesis_model() == llm_compat.SYNTHESIS_MODEL_DEFAULT


class TestTheShippedTiersAreCallable:
    """A default nobody can actually call is worse than a cheaper one. 4B.15
    Item 6 found exactly that: both call sites hardcoded `temperature=0`, which
    is a 400 on Sonnet 5 — so the tier being shipped here MUST be one the compat
    layer knows how to build a request for."""

    def test_synthesis_default_gets_a_valid_request_shape(self):
        kwargs = llm_compat.request_kwargs(llm_compat.SYNTHESIS_MODEL_DEFAULT)
        assert "temperature" not in kwargs
        assert kwargs.get("thinking") == {"type": "disabled"}

    def test_parse_default_still_gets_temperature_zero(self):
        assert llm_compat.request_kwargs(
            llm_compat.PARSE_MODEL_DEFAULT) == {"temperature": 0}

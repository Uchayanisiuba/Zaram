"""Which local server holds a model, asked the same way every other question is.

**The `LocalDispatchEngine` regression suite tested the dispatcher and stubbed
the resolver, and the defect was in the resolver.** `test_local_dispatch.py`
passes `resolve_endpoint=lambda mid: endpoints.get(mid)`, so
`ModelsRuntime._local_endpoint_for` — the function actually wired in at
`models_runtime.py:143` — had no test at all. It was green throughout.

Measured against the running product, 28 August 2026, with TabbyAPI serving
Qwen3.8-27B on ``127.0.0.1:1234`` and Ollama on ``11434``::

    model="lm_studio:Qwen3.8-27B-exl3-2.20bpw"  -> TabbyAPI, generated
    model="Qwen3.8-27B-exl3-2.20bpw"            -> [ERROR] Ollama refused the
        request for Qwen3.8-27B-exl3-2.20bpw: model not found

Same model. The second name is `display_name` — what TabbyAPI calls it, what
the catalogue records, and what `wire_name` converts *to*. `provider_of`,
`locality_of` and `wire_name` all resolve it through `_catalogued`;
`_local_endpoint_for` alone did a `split(":", 1)` and could not. So the
answering event told the user `provider: lm_studio` while the dispatcher posted
to Ollama — the product naming one server and using another, which is the
routing-legibility claim inverted.

The headline test is therefore not "the base URL is right" but **the two
answers agree**, because agreement is the property that was missing and a
second implementation is how it went.
"""

from __future__ import annotations

import pytest

from providers.contracts import CapabilityLocality, ModelInfo, ProviderKind
from runtimes.models.models_runtime import ModelsRuntime

TABBY = "http://127.0.0.1:1234"
OLLAMA = "http://127.0.0.1:11434"

#: The real pair, as discovery recorded them on the machine this was measured on.
CATALOGUE_ID = "lm_studio:Qwen3.8-27B-exl3-2.20bpw"
NATIVE_NAME = "Qwen3.8-27B-exl3-2.20bpw"


class _Provider:
    def __init__(self, kind: ProviderKind, base_url: str) -> None:
        self.kind = kind
        self.base_url = base_url


class _Registry:
    def __init__(self, **providers: _Provider) -> None:
        self._providers = providers

    def get_model_provider(self, provider_id: str):
        return self._providers.get(provider_id)


class _Manager:
    """`get_model` is exact and `_resolve_model` normalises, exactly as
    `ProviderManager` does. The distinction is the whole subject: a bare
    provider-native name only ever resolves through the second."""

    def __init__(self, *models: ModelInfo, registry: _Registry) -> None:
        self._models = {m.id: m for m in models}
        self.registry = registry

    def get_model(self, model_id: str):
        return self._models.get(model_id)

    def _resolve_model(self, model_id: str):
        for model in self._models.values():
            if model.display_name == model_id:
                return model
        return None


def _model(model_id: str, display_name: str, provider: str) -> ModelInfo:
    return ModelInfo(
        id=model_id,
        display_name=display_name,
        provider=provider,
        locality=CapabilityLocality.LOCAL,
    )


def _runtime() -> ModelsRuntime:
    return ModelsRuntime(
        event_bus=None,
        provider_manager=_Manager(
            _model(CATALOGUE_ID, NATIVE_NAME, "lm_studio"),
            _model("ollama:gemma4:12b", "gemma4:12b", "ollama"),
            registry=_Registry(
                lm_studio=_Provider(ProviderKind.LOCAL_AI_SERVER, TABBY),
                ollama=_Provider(ProviderKind.LOCAL_LLM, OLLAMA),
            ),
        ),
    )


class TestTheTwoAnswersAgree:
    """One question, one answer. Two implementations is how it broke."""

    @pytest.mark.parametrize("name", [CATALOGUE_ID, NATIVE_NAME])
    def test_the_endpoint_matches_the_provider_the_user_was_told_about(self, name):
        runtime = _runtime()

        assert runtime.provider_of(name) == "lm_studio"
        assert runtime._local_endpoint_for(name) == TABBY

    def test_the_two_names_are_genuinely_different(self):
        """So the parametrised case above cannot pass vacuously."""
        assert CATALOGUE_ID != NATIVE_NAME


class TestTheRegression:
    def test_the_provider_native_name_does_not_fall_through_to_ollama(self):
        """The measured failure. ``None`` here *is* the Ollama fallback."""
        assert _runtime()._local_endpoint_for(NATIVE_NAME) == TABBY

    def test_an_ollama_model_still_returns_none(self):
        """The fallback must keep working, by both names — Ollama is not an
        OpenAI-compatible server and must not be reached through that engine."""
        runtime = _runtime()

        assert runtime._local_endpoint_for("ollama:gemma4:12b") is None
        assert runtime._local_endpoint_for("gemma4:12b") is None


class TestWhatStillReturnsNone:
    def test_a_name_the_catalogue_cannot_place(self):
        assert _runtime()._local_endpoint_for("qwen3") is None

    def test_no_provider_layer(self):
        runtime = ModelsRuntime(event_bus=None, provider_manager=None)

        assert runtime._local_endpoint_for(CATALOGUE_ID) is None

    def test_a_registry_lookup_that_raises_never_takes_chat_down(self):
        class Exploding(_Registry):
            def get_model_provider(self, provider_id):
                raise RuntimeError("registry unavailable")

        runtime = ModelsRuntime(
            event_bus=None,
            provider_manager=_Manager(
                _model(CATALOGUE_ID, NATIVE_NAME, "lm_studio"),
                registry=Exploding(),
            ),
        )

        assert runtime._local_endpoint_for(CATALOGUE_ID) is None


class TestThePrefixFallbackSurvives:
    """It was never wrong, only incomplete. An id the catalogue does not hold
    but that names its provider still resolves."""

    def test_an_uncatalogued_id_carrying_a_provider_prefix(self):
        runtime = ModelsRuntime(
            event_bus=None,
            provider_manager=_Manager(
                registry=_Registry(
                    lm_studio=_Provider(ProviderKind.LOCAL_AI_SERVER, TABBY)
                ),
            ),
        )

        assert runtime._local_endpoint_for("lm_studio:something-just-loaded") == TABBY

"""A cloud model's window comes from its provider, never from Ollama's default.

Seen on screen 14 September 2026, on `nvidia_nim:z-ai/glm-5.3-flash`: *"none
of the earlier conversation fits alongside room to reply, on a model with a
4,096-token window"* — on a model whose window is 128,000. `budget_for` had
three readings and all three were loopback probes of servers that had never
heard of the model, so a cloud model fell to the fallback written for an
unconfigured Ollama, and the conversation was shown one exchange.

Three contracts. A cloud model the listing sized is sized by the listing; one
the listing did not size is sized by the dated floor in `providers.windows`;
and a local model is untouched by either — its declared maximum is still the
wrong number, and this must not become a route to it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest

from core.context_budget import (
    FALLBACK_CONTEXT_TOKENS,
    budget_for,
    cloud_context_length,
    is_cloud_model,
)
from core.contracts import CapabilityLocality
from providers.windows import CLOUD_FALLBACK_CONTEXT_TOKENS, bare_name, known_window


@dataclass
class _Info:
    id: str
    locality: CapabilityLocality
    context_length: Optional[int] = None


class _Catalog:
    def __init__(self, *infos: _Info) -> None:
        self._by_id = {i.id: i for i in infos}

    def get_model(self, model_id: str):
        return self._by_id.get(model_id)


@pytest.fixture(autouse=True)
def _no_loopback(monkeypatch):
    """No local server answers. A cloud model must not need one."""
    import core.context_budget as cb

    def refuse(*_a, **_k):
        raise AssertionError("a cloud model must not be sized by a loopback probe")

    monkeypatch.setattr(cb.requests, "get", refuse)


class TestACloudModelIsSizedByItsProvider:
    def test_the_listing_wins_when_it_declared_a_window(self):
        catalog = _Catalog(_Info("openrouter:meta-llama/llama-3.3-70b-instruct:free", CapabilityLocality.CLOUD, 131072))
        budget = budget_for("openrouter:meta-llama/llama-3.3-70b-instruct:free", catalog=catalog)
        assert budget.total_tokens == 131072
        assert budget.measured is True
        assert budget.source == "declared"

    def test_the_dated_floor_answers_when_the_listing_did_not(self):
        # NIM's listing carries no window; the name says GLM, and GLM is 128K.
        catalog = _Catalog(_Info("nvidia_nim:z-ai/glm-5.3-flash", CapabilityLocality.CLOUD))
        budget = budget_for("nvidia_nim:z-ai/glm-5.3-flash", catalog=catalog)
        assert budget.total_tokens == 131072
        assert budget.source == "declared"
        assert budget.input_tokens > 4 * FALLBACK_CONTEXT_TOKENS

    def test_an_unknown_cloud_model_is_assumed_larger_than_ollamas_default(self):
        catalog = _Catalog(_Info("nvidia_nim:vendor/unheard-of-model", CapabilityLocality.CLOUD))
        budget = budget_for("nvidia_nim:vendor/unheard-of-model", catalog=catalog)
        assert budget.total_tokens == CLOUD_FALLBACK_CONTEXT_TOKENS
        assert budget.measured is False
        assert budget.source == "assumed-cloud"
        assert CLOUD_FALLBACK_CONTEXT_TOKENS > FALLBACK_CONTEXT_TOKENS

    def test_a_local_model_is_not_sized_by_its_declared_maximum(self, monkeypatch):
        """The trap this file must not spring: `/api/show` says 262,144 for a
        model that loads with 4,096. A local entry with a context_length is
        still measured by the loopback readings, and falls back when they
        cannot answer."""
        import core.context_budget as cb

        monkeypatch.setattr(cb.requests, "get", lambda *a, **k: (_ for _ in ()).throw(ConnectionError()))
        catalog = _Catalog(_Info("gemma4:12b", CapabilityLocality.LOCAL, 262144))
        assert cloud_context_length("gemma4:12b", catalog) is None
        assert is_cloud_model("gemma4:12b", catalog) is False
        budget = budget_for("gemma4:12b", catalog=catalog)
        assert budget.total_tokens == FALLBACK_CONTEXT_TOKENS
        assert budget.source == "assumed"

    def test_without_a_catalogue_nothing_changes(self, monkeypatch):
        import core.context_budget as cb

        monkeypatch.setattr(cb.requests, "get", lambda *a, **k: (_ for _ in ()).throw(ConnectionError()))
        assert budget_for("nvidia_nim:z-ai/glm-5.3-flash").total_tokens == FALLBACK_CONTEXT_TOKENS


class TestTheDatedFloor:
    @pytest.mark.parametrize(
        "model_id, window",
        [
            ("nvidia_nim:z-ai/glm-5.3-flash", 131072),
            ("nvidia_nim:meta/llama3-8b-instruct", 8192),
            ("nvidia_nim:meta/llama-3.1-8b-instruct", 131072),
            ("nvidia_nim:google/gemma-2-9b-it", 8192),
            ("nvidia_nim:microsoft/phi-3-mini-4k-instruct", 4096),
            ("nvidia_nim:microsoft/phi-3-mini-128k-instruct", 131072),
            ("groq:llama-3.3-70b-versatile", 131072),
            ("openrouter:qwen/qwen3-coder:free", 131072),
            ("openrouter:qwen/qwen2.5-coder-32b-instruct", 32768),
            ("nvidia_nim:vendor/unheard-of-model", None),
        ],
    )
    def test_a_family_is_entered_at_its_smallest_member(self, model_id, window):
        assert known_window(model_id) == window

    def test_the_bare_name_drops_the_provider_and_the_vendor_but_keeps_ollamas_tag(self):
        assert bare_name("nvidia_nim:z-ai/glm-5.3-flash") == "glm-5.3-flash"
        assert bare_name("openrouter:meta-llama/llama-3.3-70b-instruct:free") == "llama-3.3-70b-instruct:free"
        assert bare_name("qwen2.5:14b") == "qwen2.5:14b"
        assert bare_name("groq:llama-3.3-70b-versatile") == "llama-3.3-70b-versatile"

    def test_every_floor_is_at_least_the_cloud_fallback_or_spelled_in_the_name(self):
        """A floor below the fallback is only honest when the name says so —
        otherwise the table would be *lowering* a budget the fallback already
        keeps safe."""
        from providers.windows import _KNOWN

        for needle, window in _KNOWN:
            assert window >= CLOUD_FALLBACK_CONTEXT_TOKENS or needle.startswith("-") or needle in {
                "gemma-2", "gemma2", "llama3-"
            }, needle

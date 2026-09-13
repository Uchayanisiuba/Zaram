"""A vision model served by TabbyAPI is known to be one.

**Found by the code pack's `look_at_app`, 13 September 2026.** It reads a
screenshot with a *local* vision model — `ModelsRuntime.read_image_locally`
asks the provider layer for one with `requires_vision=True` — and reported
that no local model could see, with the 6 GB fix, on a machine whose
resident 27B was loaded with `use_vision: true` and answering every chat.
`supports_vision` was set by the Ollama discoverer alone; the
OpenAI-compatible one already probes `/v1/model` for the loaded window and
never read the flag beside it.

The rule this protects is the images entry in `CLAUDE.md`: *modality is a
capability gate, never a ranking* — it filters the candidate set. A gate
over a flag nobody sets filters everything out, which is the quiet version
of the failure: not a text model asked to draw, but a capable model never
asked at all.
"""

from __future__ import annotations

import pytest

from providers.contracts import ProviderKind
from providers.discoverers.openai_compat import OpenAICompatibleAdapter

TABBY_MODEL = "Qwen3.8-27B-exl3-2.20bpw"


def _serving(loaded: dict | None):
    """Answers `/v1/models` with one entry and `/v1/model` with `loaded`."""

    def get(self, path, *, timeout):
        if path == "/v1/models":
            return {"data": [{"id": TABBY_MODEL, "owned_by": "tabbyAPI"}]}
        if path == "/v1/model":
            if loaded is None:
                raise RuntimeError("no /v1/model here")
            return loaded
        raise AssertionError(path)

    return get


@pytest.fixture
def adapter(monkeypatch):
    def make(loaded):
        monkeypatch.setattr(OpenAICompatibleAdapter, "_get", _serving(loaded))
        return OpenAICompatibleAdapter("lm_studio", base_url="http://127.0.0.1:1234")

    return make


@pytest.mark.asyncio
async def test_a_model_loaded_with_vision_is_known_to_see(adapter):
    models = await adapter({
        "id": TABBY_MODEL,
        "parameters": {"max_seq_len": 65536, "use_vision": True},
    }).discover_models()
    (model,) = models
    assert model.supports_vision is True
    assert "vision" in model.capabilities
    # The window still comes through the same probe.
    assert model.context_length == 65536


@pytest.mark.asyncio
async def test_a_text_model_is_not_promoted(adapter):
    models = await adapter({
        "id": TABBY_MODEL,
        "parameters": {"max_seq_len": 65536, "use_vision": False},
    }).discover_models()
    (model,) = models
    assert model.supports_vision is False


@pytest.mark.asyncio
async def test_a_server_that_will_not_say_leaves_it_unknown(adapter):
    """A failed probe costs the flag, never the model."""
    models = await adapter(None).discover_models()
    (model,) = models
    assert model.supports_vision is False
    assert model.context_length is None


@pytest.mark.asyncio
async def test_a_cloud_provider_is_never_probed(monkeypatch):
    """`/v1/model` is a local server's endpoint; asking a cloud provider would
    put a network call on the discovery path for nothing."""
    asked = []

    def get(self, path, *, timeout):
        asked.append(path)
        return {"data": [{"id": "gpt-x", "owned_by": "openai"}]}

    monkeypatch.setattr(OpenAICompatibleAdapter, "_get", get)
    adapter = OpenAICompatibleAdapter(
        "openai", base_url="https://api.openai.com", kind=ProviderKind.CLOUD_API
    )
    await adapter.discover_models()
    assert asked == ["/v1/models"]

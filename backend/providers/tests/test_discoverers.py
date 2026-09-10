"""Discoverer adapter tests for the provider layer (offline).

The Ollama and OpenAI-compatible adapters are exercised against in-memory
fakes for ``requests`` — no network is touched. The hardware profiler
runs against the real host (psutil is local), and the file / registry
adapters use temp or fake sources.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from providers.contracts import (
    ModelCategory,
    ProviderKind,
    RuntimeInfo,
)
from providers.discoverers import ollama as ollama_mod
from providers.discoverers import openai_compat as oc_mod
from providers.discoverers.ollama import OllamaAdapter
from providers.discoverers.openai_compat import LMStudioAdapter, OpenAICompatibleAdapter
from providers.discoverers.personalities import PersonalitiesFileAdapter
from providers.discoverers.runtimes import RegistryRuntimeSource


class _Resp:
    def __init__(self, data: Any) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._data


class _FakeRequests:
    def __init__(self, routes: Dict[str, Any]) -> None:
        self._routes = routes

    def get(self, url: str, **_kw: Any) -> _Resp:
        return _Resp(self._routes[url])

    def post(self, url: str, **_kw: Any) -> _Resp:
        return _Resp(self._routes[url])


OLLAMA_TAGS = {
    "models": [
        {
            "name": "llama3:latest",
            "size": 5_000_000_000,
            "details": {"parameter_size": "8B", "family": "llama", "quantization_level": "Q4_K_M"},
        }
    ]
}

#: `/api/show` as Ollama actually answers it, carrying **both** numbers.
#:
#: `parameters` is the Modelfile's own text and holds `num_ctx` -- the window
#: the model will be served with. `model_info.context_length` is the
#: architecture maximum, which on a real model is several times larger:
#: `qwen3-14b-16k` reports 40,960 there and loads with 16,384. Both are in the
#: fixture on purpose, so the assertion below can say which one is taken.
OLLAMA_SHOW = {
    "details": {"family": "llama", "quantization_level": "Q4_K_M"},
    "parameters": 'num_ctx                        8192\nstop                           "<|eot_id|>"\ntemperature                    0.7',
    "model_info": {"context_length": 131072},
    "capabilities": ["tools", "vision"],
}

#: The same reply from a model created without an explicit `num_ctx`.
OLLAMA_SHOW_NO_NUM_CTX = {
    "details": {"family": "llama"},
    "parameters": 'stop                           "<|eot_id|>"',
    "model_info": {"context_length": 131072},
    "capabilities": [],
}


async def test_ollama_adapter_parses_models(monkeypatch):
    base = "http://127.0.0.1:11434"
    fake = _FakeRequests(
        {f"{base}/api/tags": OLLAMA_TAGS, f"{base}/api/show": OLLAMA_SHOW}
    )
    monkeypatch.setattr(ollama_mod, "requests", fake)

    adapter = OllamaAdapter(base_url=base)
    models = await adapter.discover_models(timeout=1.0)
    assert len(models) == 1
    m = models[0]
    assert m.id == "ollama:llama3:latest"
    assert m.provider == "ollama"
    assert m.category is ModelCategory.LLM
    assert m.size_bytes == 5_000_000_000
    assert m.quantization == "Q4_K_M"
    # The served window, never the architecture maximum sitting beside it.
    assert m.context_length == 8192
    assert m.context_length != OLLAMA_SHOW["model_info"]["context_length"]
    assert m.supports_tools is True
    assert m.supports_vision is True
    assert m.available is True


async def test_ollama_reports_no_window_when_none_is_configured(monkeypatch):
    """Unknown rather than the declared maximum, and rather than a guess.

    A model with no `num_ctx` is served Ollama's default. That default is
    configurable, so asserting it here would be a guess about the server
    dressed as a measurement -- and `budget_for` already falls back to it
    deliberately, where the fallback is labelled as one. What must never
    happen is the 131,072 in `model_info` being reported as this model's
    window: it is the number `core/context_budget.py` was written about.
    """
    base = "http://127.0.0.1:11434"
    fake = _FakeRequests(
        {f"{base}/api/tags": OLLAMA_TAGS, f"{base}/api/show": OLLAMA_SHOW_NO_NUM_CTX}
    )
    monkeypatch.setattr(ollama_mod, "requests", fake)

    models = await OllamaAdapter(base_url=base).discover_models(timeout=1.0)

    assert models[0].context_length is None


async def test_ollama_adapter_handles_failure(monkeypatch):
    class _Boom:
        def get(self, *a, **k):
            raise ConnectionError("refused")

        def post(self, *a, **k):
            raise ConnectionError("refused")

    monkeypatch.setattr(ollama_mod, "requests", _Boom())
    adapter = OllamaAdapter()
    assert await adapter.discover_models() == []
    health = await adapter.health()
    assert health["available"] is False


OPENAI_MODELS = {"data": [{"id": "gpt-4o", "owned_by": "openai"}]}


class _FakeGate:
    """Stands in for the egress gate.

    The adapter no longer owns an HTTP client — it asks ``core.egress`` to make
    the request, so a base URL pointed at api.openai.com is governed and logged
    rather than dialled directly. Patching ``requests`` now patches nothing and
    the adapter reaches the real network.
    """

    def __init__(self, routes: Dict[str, Any]) -> None:
        self._routes = routes

    def request(self, url: str, **_kw: Any) -> bytes:
        return json.dumps(self._routes[url]).encode()


async def test_openai_compatible_adapter(monkeypatch):
    base = "http://127.0.0.1:1234"
    fake = _FakeGate({f"{base}/v1/models": OPENAI_MODELS})
    monkeypatch.setattr("core.egress.get_gate", lambda: fake)

    adapter = OpenAICompatibleAdapter(provider_id="openai_compatible", base_url=base)
    models = await adapter.discover_models(timeout=1.0)
    assert len(models) == 1
    m = models[0]
    assert m.id == "openai_compatible:gpt-4o"
    assert m.provider == "openai_compatible"
    assert m.locality.value == "local"


async def test_openai_adapter_cloud_locality(monkeypatch):
    fake = _FakeGate({"https://api.openai.com/v1/models": OPENAI_MODELS})
    monkeypatch.setattr("core.egress.get_gate", lambda: fake)
    adapter = OpenAICompatibleAdapter(
        provider_id="openai_cloud", base_url="https://api.openai.com", kind=ProviderKind.CLOUD_API
    )
    models = await adapter.discover_models(timeout=1.0)
    assert models[0].locality.value == "cloud"


def test_lm_studio_adapter_defaults():
    adapter = LMStudioAdapter()
    assert adapter.provider_id == "lm_studio"
    assert adapter.kind is ProviderKind.LOCAL_AI_SERVER


def test_personalities_file_adapter(tmp_path):
    path = tmp_path / "chars.json"
    path.write_text(
        '{"zaram_prime": {"name": "Zaram", "voice_id": "heart"}}', encoding="utf-8"
    )
    adapter = PersonalitiesFileAdapter(str(path))
    result = adapter.list_personalities()
    assert len(result) == 1
    assert result[0]["id"] == "zaram_prime"


def test_personalities_file_missing_returns_empty(tmp_path):
    adapter = PersonalitiesFileAdapter(str(tmp_path / "nope.json"))
    assert adapter.list_personalities() == []


def test_registry_runtime_source_snapshot():
    class _Cap:
        def __init__(self, rid, cid, ver):
            self.runtime_id = rid
            self.id = cid
            self.version = ver

    class _FakeRegistry:
        def list_capabilities(self):
            return [_Cap("media", "media.audio.voice", "0.5.5"), _Cap("voice", "speech.tts", "0.5.1")]

        def get_system_health(self):
            return {"media": "ready", "voice": "ready"}

    source = RegistryRuntimeSource(_FakeRegistry())
    snap = source.snapshot_runtimes()
    assert {r.runtime_id for r in snap} == {"media", "voice"}
    media = next(r for r in snap if r.runtime_id == "media")
    assert media.capabilities == ["media.audio.voice"]
    assert media.healthy is True

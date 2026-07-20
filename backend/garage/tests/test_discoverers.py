"""Discoverer adapter tests for the AI Garage (offline).

The Ollama and OpenAI-compatible adapters are exercised against in-memory
fakes for ``requests`` — no network is touched. The hardware profiler
runs against the real host (psutil is local), and the file / registry
adapters use temp or fake sources.
"""

from __future__ import annotations

from typing import Any, Dict

from garage.contracts import (
    ModelCategory,
    ProviderKind,
    RuntimeInfo,
)
from garage.discoverers import ollama as ollama_mod
from garage.discoverers import openai_compat as oc_mod
from garage.discoverers.ollama import OllamaAdapter
from garage.discoverers.openai_compat import LMStudioAdapter, OpenAICompatibleAdapter
from garage.discoverers.personalities import PersonalitiesFileAdapter
from garage.discoverers.runtimes import RegistryRuntimeSource


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

OLLAMA_SHOW = {
    "details": {"family": "llama", "quantization_level": "Q4_K_M"},
    "model_info": {"context_length": 8192},
    "capabilities": ["tools", "vision"],
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
    assert m.context_length == 8192
    assert m.supports_tools is True
    assert m.supports_vision is True
    assert m.available is True


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


async def test_openai_compatible_adapter(monkeypatch):
    base = "http://127.0.0.1:1234"
    fake = _FakeRequests({f"{base}/v1/models": OPENAI_MODELS})
    monkeypatch.setattr(oc_mod, "requests", fake)

    adapter = OpenAICompatibleAdapter(provider_id="openai_compatible", base_url=base)
    models = await adapter.discover_models(timeout=1.0)
    assert len(models) == 1
    m = models[0]
    assert m.id == "openai_compatible:gpt-4o"
    assert m.provider == "openai_compatible"
    assert m.locality.value == "local"


async def test_openai_adapter_cloud_locality(monkeypatch):
    fake = _FakeRequests({"https://api.openai.com/v1/models": OPENAI_MODELS})
    monkeypatch.setattr(oc_mod, "requests", fake)
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

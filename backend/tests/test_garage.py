# backend/tests/test_garage.py
"""Offline test suite for the Zaram AI Garage foundation (v0.6.0).

Every test here runs without any network access. Model providers and the
voice / runtime / personality / hardware sources are replaced with in-process
fakes, and the Ollama / OpenAI-compatible adapters are exercised against
patched HTTP responses. No model name is hardcoded anywhere in the Garage,
and these tests assert that the discovery results are inferred entirely from
the (mocked) provider payloads.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

# Ensure backend root is importable when run directly (not via pytest).
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.contracts import Capability, CapabilityLocality, RuntimeState

from garage.contracts import (
    HealthStatus,
    HardwareProfile,
    ModelCategory,
    ModelInfo,
    ProviderKind,
    ProviderSummary,
    RuntimeInfo,
    VoiceInfo,
)
from garage.manager import GarageManager
from garage.model_catalog import GarageModelCatalog
from garage.registry import GarageRegistry
from garage.runtime import GarageRuntime, RUNTIME_ID, RUNTIME_VERSION
from garage.scanner import GarageScanner
from garage.health import GarageHealthAggregator
from garage.discoverers import (
    LMStudioAdapter,
    OpenAICompatibleAdapter,
    OllamaAdapter,
    PersonalitiesFileAdapter,
    RegistryRuntimeSource,
    StaticPersonalitySource,
    StaticVoiceSource,
    VoiceRegistryAdapter,
)
from garage import api as garage_api


# --------------------------------------------------------------------------- #
# Fakes (no network, no real subsystems)
# --------------------------------------------------------------------------- #
class FakeModelProvider:
    """A stand-in for any ModelProviderAdapter (Ollama, LM Studio, ...)."""

    def __init__(
        self,
        provider_id: str,
        kind: ProviderKind = ProviderKind.LOCAL_LLM,
        models: Optional[List[ModelInfo]] = None,
        available: bool = True,
        health_error: Optional[str] = None,
    ) -> None:
        self.provider_id = provider_id
        self.kind = kind
        self._models = models or []
        self._available = available
        self._health_error = health_error

    async def discover_models(self, *, timeout: float = 2.0) -> List[ModelInfo]:
        return list(self._models)

    async def health(self) -> Dict[str, Any]:
        if self._health_error is not None:
            return {"available": False, "provider": self.provider_id, "error": self._health_error}
        return {
            "available": self._available,
            "provider": self.provider_id,
            "endpoint": "http://fake.local",
        }

    def to_dict(self) -> Dict[str, Any]:
        return ProviderSummary(
            id=self.provider_id, kind=self.kind, health_status=HealthStatus.UNKNOWN
        ).to_dict()


class FakeVoiceSource:
    """Exposes ``list_voices()`` (the StaticVoiceSource-style interface)."""

    def __init__(self, voices: Dict[str, Any]) -> None:
        self._voices = dict(voices)

    async def list_voices(self) -> Dict[str, Any]:
        return dict(self._voices)


class FakeVoiceManager:
    """Exposes ``available_voices()`` (the VoiceManager-style interface)."""

    def __init__(self, voices: Dict[str, Any]) -> None:
        self._voices = dict(voices)

    async def available_voices(self) -> Dict[str, Any]:
        return dict(self._voices)


class FakeRuntimeRegistry:
    """Mimics the Kernel ``RuntimeRegistry`` public surface."""

    def __init__(self, capabilities=None, health=None) -> None:
        self._capabilities = capabilities or [
            Capability(id="garage.discover", runtime_id="garage", version="0.6.0"),
            Capability(id="models.generate", runtime_id="models", version="1.0.0"),
        ]
        self._health = health or {"garage": "ready", "models": "ready"}

    def list_capabilities(self):
        return self._capabilities

    def get_system_health(self):
        return self._health


class FakeHardwareProfiler:
    def __init__(self, profile: Optional[HardwareProfile] = None) -> None:
        self._profile = profile or HardwareProfile(
            cpu_model="Fake CPU",
            cpu_count=8,
            total_ram_bytes=16 * 1024 ** 3,
            gpu_available=True,
            gpu_name="Fake GPU",
            vram_bytes=8 * 1024 ** 3,
            os_name="FakeOS",
            os_version="1.0",
            storage_total_bytes=1024 ** 4,
            storage_free_bytes=512 ** 4,
            cuda_available=True,
            metal_available=False,
            directml_available=False,
        )
        self.calls = 0

    def profile(self) -> HardwareProfile:
        self.calls += 1
        return self._profile


def make_sample_model(provider: str = "ollama", name: str = "llama3:latest") -> ModelInfo:
    return ModelInfo(
        id=f"{provider}:{name}",
        display_name=name,
        provider=provider,
        provider_kind=ProviderKind.LOCAL_LLM,
        category=ModelCategory.LLM,
        size_bytes=4_000_000_000,
        context_length=8192,
        quantization="Q4_K_M",
        capabilities={"chat", "tools"},
        supports_vision=False,
        supports_embedding=False,
        supports_tools=True,
        recommended_use="local chat",
        memory_requirement_bytes=4_000_000_000,
        locality=CapabilityLocality.LOCAL,
        available=True,
        health_status=HealthStatus.HEALTHY,
        endpoint="http://127.0.0.1:11434",
    )


# --------------------------------------------------------------------------- #
# Contract tests
# --------------------------------------------------------------------------- #
def test_model_info_round_trip():
    model = make_sample_model()
    restored = ModelInfo.from_dict(model.to_dict())
    assert restored.id == model.id
    assert restored.provider == model.provider
    assert restored.context_length == model.context_length
    assert restored.capabilities == model.capabilities
    assert restored.supports_tools is True
    assert restored.locality is CapabilityLocality.LOCAL


def test_model_info_from_dict_missing_fields_defaults():
    info = ModelInfo.from_dict({"id": "x:1"})
    assert info.display_name == "x:1"
    assert info.provider == "unknown"
    assert info.category is ModelCategory.LLM
    assert info.available is False
    assert info.health_status is HealthStatus.UNKNOWN


def test_enum_from_value_resilient():
    assert ModelCategory.from_value("vision") is ModelCategory.VISION
    assert ModelCategory.from_value("nonsense") is ModelCategory.OTHER
    assert ProviderKind.from_value(None) is ProviderKind.LOCAL_LLM
    assert HealthStatus.from_value("healthy") is HealthStatus.HEALTHY
    assert HealthStatus.from_value("bogus") is HealthStatus.UNKNOWN


def test_hardware_profile_to_dict_keys():
    hp = HardwareProfile(cpu_model="c", cpu_count=4, total_ram_bytes=1)
    d = hp.to_dict()
    assert d["cpu_model"] == "c"
    assert d["cpu_count"] == 4
    for key in ("vram_bytes", "cuda_available", "metal_available", "directml_available"):
        assert key in d


def test_voice_info_and_runtime_info_to_dict():
    v = VoiceInfo(id="v1", display_name="Voice One", provider="kokoro", language="en")
    assert v.to_dict()["language"] == "en"
    r = RuntimeInfo(runtime_id="models", version="1.0.0", healthy=True, capabilities=["a"])
    rd = r.to_dict()
    assert rd["runtime_id"] == "models"
    assert rd["healthy"] is True


def test_provider_summary_to_dict():
    ps = ProviderSummary(id="ollama", kind=ProviderKind.LOCAL_LLM, model_count=3)
    d = ps.to_dict()
    assert d["id"] == "ollama"
    assert d["kind"] == "local_llm"
    assert d["model_count"] == 3


# --------------------------------------------------------------------------- #
# Model catalog tests
# --------------------------------------------------------------------------- #
def test_catalog_upsert_and_counts():
    cat = GarageModelCatalog()
    assert cat.count() == 0
    cat.upsert(make_sample_model())
    cat.upsert(make_sample_model(name="other"))
    assert cat.count() == 2
    assert cat.get("ollama:other") is not None
    assert cat.available_count() == 2


def test_catalog_upsert_replaces_by_id():
    cat = GarageModelCatalog()
    cat.upsert(make_sample_model())
    updated = make_sample_model()
    updated.available = False
    cat.upsert(updated)
    assert cat.count() == 1
    assert cat.available_count() == 0


def test_catalog_filter_by_category_capability_locality_provider():
    cat = GarageModelCatalog()
    m1 = make_sample_model(name="a")
    m2 = make_sample_model(name="b", provider="lm_studio")
    m2.category = ModelCategory.EMBEDDING
    m2.capabilities = {"embedding"}
    m2.supports_embedding = True
    m2.locality = CapabilityLocality.CLOUD
    m2.available = False
    cat.upsert_all([m1, m2])

    assert len(cat.filter(category=ModelCategory.EMBEDDING)) == 1
    assert len(cat.filter(capability="embedding")) == 1
    assert len(cat.filter(locality=CapabilityLocality.CLOUD)) == 1
    assert len(cat.filter(provider="lm_studio")) == 1
    assert len(cat.filter(available_only=True)) == 1
    assert len(cat.filter()) == 2


def test_catalog_by_category_counts():
    cat = GarageModelCatalog()
    cat.upsert(make_sample_model())
    emb = make_sample_model(name="e")
    emb.category = ModelCategory.EMBEDDING
    cat.upsert(emb)
    counts = cat.by_category()
    assert counts["llm"] == 1
    assert counts["embedding"] == 1


# --------------------------------------------------------------------------- #
# Registry tests
# --------------------------------------------------------------------------- #
def test_registry_model_provider_lifecycle():
    reg = GarageRegistry()
    assert reg.count_model_providers() == 0
    reg.register_model_provider(FakeModelProvider("ollama"))
    assert reg.is_registered("ollama")
    assert reg.count_model_providers() == 1
    assert reg.get_model_provider("ollama").provider_id == "ollama"
    assert reg.remove_model_provider("ollama") is True
    assert reg.count_model_providers() == 0


def test_registry_rejects_duplicate_and_missing_id():
    reg = GarageRegistry()
    reg.register_model_provider(FakeModelProvider("ollama"))
    try:
        reg.register_model_provider(FakeModelProvider("ollama"))
        assert False, "duplicate should raise"
    except ValueError:
        pass
    bad = FakeModelProvider("ollama")
    bad.provider_id = ""
    try:
        reg.register_model_provider(bad)
        assert False, "missing id should raise"
    except ValueError:
        pass


def test_registry_injected_sources():
    reg = GarageRegistry()
    reg.set_voice_source(FakeVoiceSource({}))
    reg.set_runtime_source(RegistryRuntimeSource(FakeRuntimeRegistry()))
    reg.set_personality_source(StaticPersonalitySource([]))
    reg.set_hardware_profiler(FakeHardwareProfiler())
    assert reg.get_voice_source() is not None
    assert reg.get_runtime_source() is not None
    assert reg.get_personality_source() is not None
    assert reg.get_hardware_profiler() is not None


def test_registry_provider_specs():
    reg = GarageRegistry()
    reg.register_model_provider(FakeModelProvider("ollama", ProviderKind.LOCAL_LLM))
    specs = reg.provider_specs()
    assert len(specs) == 1
    assert specs[0].id == "ollama"


# --------------------------------------------------------------------------- #
# Scanner + manager integration (fully offline via fakes)
# --------------------------------------------------------------------------- #
def _build_manager() -> GarageManager:
    reg = GarageRegistry()
    reg.register_model_provider(
        FakeModelProvider("ollama", ProviderKind.LOCAL_LLM, [make_sample_model()])
    )
    reg.register_model_provider(
        FakeModelProvider("lm_studio", ProviderKind.LOCAL_AI_SERVER, [])
    )
    reg.set_voice_source(
        FakeVoiceSource(
            {"af_heart": {"display_name": "Heart", "provider": "kokoro", "language": "en"}}
        )
    )
    reg.set_runtime_source(RegistryRuntimeSource(FakeRuntimeRegistry()))
    reg.set_personality_source(
        StaticPersonalitySource([{"id": "default", "name": "Default"}])
    )
    reg.set_hardware_profiler(FakeHardwareProfiler())
    scanner = GarageScanner(reg)
    return GarageManager(reg, scanner)


def test_manager_refresh_discovers_everything():
    manager = _build_manager()

    async def _run():
        await manager.refresh(timeout=1.0)
        return manager

    manager = asyncio.run(_run())

    assert manager.catalog.count() == 1
    assert len(manager.list_voices()) == 1
    assert len(manager.list_runtimes()) == 2  # garage + models
    assert len(manager.list_personalities()) == 1
    assert manager.hardware_profile().cpu_model == "Fake CPU"
    assert manager._scanned is True


def test_manager_list_providers_aggregates_model_counts():
    manager = _build_manager()
    asyncio.run(manager.refresh(timeout=1.0))
    providers = {p["id"]: p for p in manager.list_providers()}
    assert providers["ollama"]["model_count"] == 1
    assert providers["ollama"]["available"] is True
    assert providers["lm_studio"]["model_count"] == 0
    assert providers["lm_studio"]["available"] is False


def test_manager_ensure_scanned_is_lazy_and_idempotent():
    manager = _build_manager()

    async def _run():
        await manager.ensure_scanned()
        first = manager.catalog.count()
        await manager.ensure_scanned()
        return first, manager.catalog.count()

    first, second = asyncio.run(_run())
    assert first == 1
    assert second == 1  # ensure_scanned does not re-scan


def test_scanner_isolates_provider_failure():
    reg = GarageRegistry()
    reg.register_model_provider(
        FakeModelProvider("good", models=[make_sample_model(provider="good", name="m")])
    )
    reg.register_model_provider(FakeModelProvider("bad", health_error="boom"))

    async def _run():
        return await GarageScanner(reg).scan_models(timeout=1.0)

    models = asyncio.run(_run())
    # The failing provider must not break the healthy one.
    assert len(models) == 1
    assert models[0].provider == "good"


def test_scanner_voices_via_available_voices_manager():
    reg = GarageRegistry()
    reg.set_voice_source(
        FakeVoiceManager({"vm1": {"display_name": "VM One", "provider": "kokoro"}})
    )
    scanner = GarageScanner(reg)

    async def _run():
        return await scanner.scan_voices()

    voices = asyncio.run(_run())
    assert len(voices) == 1
    assert voices[0].id == "vm1"


def test_scanner_runtimes_via_kernel_registry():
    reg = GarageRegistry()
    reg.set_runtime_source(RegistryRuntimeSource(FakeRuntimeRegistry()))
    runtimes = GarageScanner(reg).scan_runtimes()
    ids = {r.runtime_id for r in runtimes}
    assert ids == {"garage", "models"}
    ready = {r.runtime_id for r in runtimes if r.healthy}
    assert ready == {"garage", "models"}


def test_scanner_hardware_fallback_when_missing():
    reg = GarageRegistry()  # no profiler
    hp = GarageScanner(reg).profile_hardware()
    assert isinstance(hp, HardwareProfile)
    assert hp.cpu_model == "unknown"


def test_scanner_health_per_provider():
    reg = GarageRegistry()
    reg.register_model_provider(FakeModelProvider("ollama", available=True))
    reg.register_model_provider(FakeModelProvider("down", health_error="x"))

    async def _run():
        return await GarageScanner(reg).health()

    health = asyncio.run(_run())
    assert health["providers"]["ollama"]["available"] is True
    assert health["providers"]["down"]["available"] is False


# --------------------------------------------------------------------------- #
# Health aggregation
# --------------------------------------------------------------------------- #
def test_health_aggregator_no_providers_is_unknown():
    agg = GarageHealthAggregator()
    h = agg.aggregate(
        runtime_status="ready",
        provider_specs=[],
        scanner_health={"providers": {}},
        model_count=0,
        available_models=0,
        voice_count=0,
        runtime_count=0,
        personality_count=0,
        categories=[],
        hardware={},
    )
    assert h.health_status is HealthStatus.UNKNOWN


def test_health_aggregator_healthy_when_available():
    agg = GarageHealthAggregator()
    h = agg.aggregate(
        runtime_status="ready",
        provider_specs=[{"id": "ollama", "available": True}],
        scanner_health={"providers": {}},
        model_count=2,
        available_models=2,
        voice_count=1,
        runtime_count=2,
        personality_count=1,
        categories=["llm"],
        hardware={},
    )
    assert h.health_status is HealthStatus.HEALTHY
    assert h.available_services == 1


def test_health_aggregator_degraded_when_none_available():
    agg = GarageHealthAggregator()
    h = agg.aggregate(
        runtime_status="ready",
        provider_specs=[{"id": "ollama", "available": False}],
        scanner_health={"providers": {}},
        model_count=0,
        available_models=0,
        voice_count=0,
        runtime_count=0,
        personality_count=0,
        categories=[],
        hardware={},
    )
    assert h.health_status is HealthStatus.DEGRADED


def test_manager_health_report_shape():
    manager = _build_manager()
    asyncio.run(manager.refresh(timeout=1.0))
    report = manager.health_report()
    assert report["runtime_id"] == "garage"
    assert report["model_count"] == 1
    assert report["voice_count"] == 1
    assert report["runtime_count"] == 2
    assert report["personality_count"] == 1
    assert "hardware" in report
    assert report["categories"] == ["llm"]


# --------------------------------------------------------------------------- #
# Adapter tests (real adapters, mocked HTTP — still offline)
# --------------------------------------------------------------------------- #
class _FakeResponse:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Dict[str, Any]:
        return self._payload


def test_ollama_adapter_discovers_and_infers():
    tags = {
        "models": [
            {
                "name": "llama3:latest",
                "size": 4_700_000_000,
                "details": {"parameter_size": "8B", "family": "llama", "quantization_level": "Q4_K_M"},
            }
        ]
    }
    show = {
        "capabilities": ["tools", "vision"],
        "model_info": {"context_length": 8192},
        "details": {"quantization_level": "Q4_K_M"},
    }
    with patch("requests.get", return_value=_FakeResponse(tags)), patch(
        "requests.post", return_value=_FakeResponse(show)
    ):
        adapter = OllamaAdapter()

        async def _run():
            return await adapter.discover_models(timeout=1.0)

        models = asyncio.run(_run())

    assert len(models) == 1
    m = models[0]
    assert m.id == "ollama:llama3:latest"
    assert m.provider == "ollama"
    assert m.context_length == 8192
    assert m.quantization == "Q4_K_M"
    assert m.supports_vision is True
    assert m.supports_tools is True
    assert m.category is ModelCategory.LLM
    assert m.health_status is HealthStatus.HEALTHY


def test_ollama_adapter_embedding_category():
    tags = {"models": [{"name": "nomic-embed", "details": {"family": "nomic"}}]}
    show = {"capabilities": ["embedding"], "model_info": {}}
    with patch("requests.get", return_value=_FakeResponse(tags)), patch(
        "requests.post", return_value=_FakeResponse(show)
    ):
        adapter = OllamaAdapter()

        async def _run():
            return await adapter.discover_models(timeout=1.0)

        models = asyncio.run(_run())
    assert models[0].category is ModelCategory.EMBEDDING
    assert models[0].supports_embedding is True


def test_ollama_adapter_unavailable_returns_empty():
    with patch("requests.get", side_effect=RuntimeError("connection refused")):
        adapter = OllamaAdapter()

        async def _run():
            return await adapter.discover_models(timeout=1.0)

        assert asyncio.run(_run()) == []


def test_openai_compatible_adapter_discovers():
    payload = {"data": [{"id": "local-model-1", "owned_by": "lmstudio"}]}
    with patch("requests.get", return_value=_FakeResponse(payload)):
        adapter = OpenAICompatibleAdapter(provider_id="openai_compatible")

        async def _run():
            return await adapter.discover_models(timeout=1.0)

        models = asyncio.run(_run())
    assert len(models) == 1
    m = models[0]
    assert m.id == "openai_compatible:local-model-1"
    assert m.display_name == "local-model-1"
    assert m.locality is CapabilityLocality.LOCAL
    assert m.supports_tools is True


def test_openai_compatible_cloud_locality():
    payload = {"data": [{"id": "gpt-x"}]}
    with patch("requests.get", return_value=_FakeResponse(payload)):
        adapter = OpenAICompatibleAdapter(
            provider_id="openai_cloud", kind=ProviderKind.CLOUD_API
        )

        async def _run():
            return await adapter.discover_models(timeout=1.0)

        models = asyncio.run(_run())
    assert models[0].locality is CapabilityLocality.CLOUD


def test_lm_studio_adapter_defaults():
    assert LMStudioAdapter().provider_id == "lm_studio"
    assert LMStudioAdapter().base_url == "http://127.0.0.1:1234"
    assert LMStudioAdapter().kind is ProviderKind.LOCAL_AI_SERVER


def test_personalities_file_adapter_reads_json(tmp_path):
    data = {"hero": {"name": "Hero", "voice": "af_heart"}}
    p = tmp_path / "characters.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    adapter = PersonalitiesFileAdapter(str(p))
    result = adapter.list_personalities()
    assert len(result) == 1
    assert result[0]["id"] == "hero"


def test_personalities_file_adapter_missing_file():
    adapter = PersonalitiesFileAdapter("does_not_exist.json")
    assert adapter.list_personalities() == []


def test_voice_registry_adapter_to_voice_infos():
    adapter = VoiceRegistryAdapter(
        FakeVoiceSource({"v1": {"display_name": "V1", "provider": "kokoro"}})
    )
    infos = adapter.to_voice_infos(
        {"v1": {"display_name": "V1", "provider": "kokoro", "gender": "female"}}
    )
    assert infos[0].id == "v1"
    assert infos[0].gender == "female"


# --------------------------------------------------------------------------- #
# Hardware profiler (real, but dependency-tolerant and offline)
# --------------------------------------------------------------------------- #
def test_hardware_profiler_returns_profile():
    from garage.discoverers.hardware import HardwareProfiler

    profile = HardwareProfiler().profile()
    assert isinstance(profile, HardwareProfile)
    assert profile.cpu_count >= 0
    # Degrades gracefully regardless of torch availability.
    assert isinstance(profile.cuda_available, bool)


# --------------------------------------------------------------------------- #
# GarageRuntime lifecycle (default providers replaced with fakes, offline)
# --------------------------------------------------------------------------- #
def test_garage_runtime_initialize_registers_providers(monkeypatch):
    fake_ollama = FakeModelProvider("ollama", models=[make_sample_model()])
    fake_lm = FakeModelProvider("lm_studio")
    monkeypatch.setattr("garage.runtime.OllamaAdapter", lambda *a, **k: fake_ollama)
    monkeypatch.setattr("garage.runtime.LMStudioAdapter", lambda *a, **k: fake_lm)

    runtime = GarageRuntime()
    assert runtime.get_runtime_id() == RUNTIME_ID
    assert runtime.get_version() == RUNTIME_VERSION

    async def _run():
        await runtime.initialize()
        await runtime.refresh(timeout=1.0)

    asyncio.run(_run())
    assert runtime.registry.count_model_providers() == 2
    assert runtime.manager.catalog.count() == 1
    hc = runtime.health_check()
    assert hc["registered_services"] == 2
    asyncio.run(runtime.shutdown())


def test_garage_runtime_health_delegates_to_manager():
    manager = _build_manager()
    asyncio.run(manager.refresh(timeout=1.0))
    runtime = GarageRuntime(manager=manager)
    report = asyncio.run(runtime.health())
    assert report["model_count"] == 1


# --------------------------------------------------------------------------- #
# Read-only API (isolated app, no kernel/voice/media boot)
# --------------------------------------------------------------------------- #
def _make_garage_app() -> FastAPI:
    app = FastAPI()
    app.include_router(garage_api.router)
    return app


def test_api_returns_503_before_runtime_attached():
    garage_api.set_garage_runtime(None)
    client = TestClient(_make_garage_app())
    resp = client.get("/garage/models")
    assert resp.status_code == 503


def test_api_endpoints_serve_discovered_resources():
    manager = _build_manager()
    asyncio.run(manager.refresh(timeout=1.0))
    runtime = GarageRuntime(manager=manager)
    garage_api.set_garage_runtime(runtime)

    client = TestClient(_make_garage_app())
    models = client.get("/garage/models").json()
    providers = client.get("/garage/providers").json()
    voices = client.get("/garage/voices").json()
    runtimes = client.get("/garage/runtimes").json()
    personalities = client.get("/garage/personalities").json()
    hardware = client.get("/garage/hardware").json()
    health = client.get("/garage/health").json()

    assert isinstance(models, list) and len(models) == 1
    assert models[0]["id"] == "ollama:llama3:latest"
    assert {p["id"] for p in providers} == {"ollama", "lm_studio"}
    assert len(voices) == 1
    assert {r["runtime_id"] for r in runtimes} == {"garage", "models"}
    assert personalities[0]["id"] == "default"
    assert hardware["cpu_model"] == "Fake CPU"
    assert health["model_count"] == 1


def test_api_single_model_lookup_and_404():
    manager = _build_manager()
    asyncio.run(manager.refresh(timeout=1.0))
    garage_api.set_garage_runtime(GarageRuntime(manager=manager))

    client = TestClient(_make_garage_app())
    ok = client.get("/garage/models/ollama:llama3:latest")
    assert ok.status_code == 200
    assert ok.json()["display_name"] == "llama3:latest"
    missing = client.get("/garage/models/nope")
    assert missing.status_code == 404

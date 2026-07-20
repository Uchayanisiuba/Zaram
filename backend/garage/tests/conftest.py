"""Shared offline fakes and fixtures for AI Garage tests (v0.6.0).

Every fake mirrors a real adapter/source interface so the Garage can be
exercised end-to-end with zero network and zero external dependencies.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from garage.contracts import (
    CapabilityLocality,
    HardwareProfile,
    HealthStatus,
    ModelCategory,
    ModelInfo,
    ProviderKind,
    RuntimeInfo,
    VoiceInfo,
)
from garage.manager import GarageManager
from garage.registry import GarageRegistry
from garage.runtime import GarageRuntime
from garage.scanner import GarageScanner


def make_model(
    *,
    id: str = "p1:model-a",
    display_name: str = "model-a",
    provider: str = "p1",
    category: ModelCategory = ModelCategory.LLM,
    capabilities: Optional[set] = None,
    locality: CapabilityLocality = CapabilityLocality.LOCAL,
    available: bool = True,
    context_length: Optional[int] = 8192,
    size_bytes: Optional[int] = 5_000_000_000,
    quantization: Optional[str] = "Q4_K_M",
) -> ModelInfo:
    return ModelInfo(
        id=id,
        display_name=display_name,
        provider=provider,
        provider_kind=ProviderKind.LOCAL_LLM,
        category=category,
        context_length=context_length,
        size_bytes=size_bytes,
        quantization=quantization,
        capabilities=capabilities or set(),
        supports_vision="vision" in (capabilities or set()),
        supports_embedding="embedding" in (capabilities or set()),
        supports_tools="tools" in (capabilities or set()),
        locality=locality,
        available=available,
        health_status=HealthStatus.HEALTHY if available else HealthStatus.UNAVAILABLE,
    )


class FakeModelProvider:
    """A ModelProviderAdapter returning a preset list of models."""

    def __init__(self, provider_id: str, models: List[ModelInfo], *, kind=ProviderKind.LOCAL_LLM):
        self.provider_id = provider_id
        self.kind = kind
        self._models = models
        self.health_available = True

    async def discover_models(self, *, timeout: float = 2.0) -> List[ModelInfo]:
        return list(self._models)

    async def health(self) -> Dict[str, Any]:
        return {"available": self.health_available, "provider": self.provider_id}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.provider_id,
            "kind": self.kind.value,
            "available": self.health_available,
            "model_count": len(self._models),
            "health_status": "healthy" if self.health_available else "unavailable",
        }


class FailingModelProvider:
    """A provider whose discovery raises (exercises failure isolation)."""

    provider_id = "broken"
    kind = ProviderKind.LOCAL_LLM

    async def discover_models(self, *, timeout: float = 2.0) -> List[ModelInfo]:
        raise RuntimeError("simulated provider failure")

    async def health(self) -> Dict[str, Any]:
        return {"available": False, "error": "boom"}

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.provider_id, "kind": self.kind.value}


class FakeVoiceSource:
    def __init__(self, voices: Dict[str, Any]):
        self._voices = voices

    async def list_voices(self) -> Dict[str, Any]:
        return dict(self._voices)


class FakeRuntimeSource:
    def __init__(self, runtimes: List[RuntimeInfo]):
        self._runtimes = runtimes

    def snapshot_runtimes(self) -> List[RuntimeInfo]:
        return list(self._runtimes)


class FakePersonalitySource:
    def __init__(self, personalities: List[Dict[str, Any]]):
        self._personalities = personalities

    def list_personalities(self) -> List[Dict[str, Any]]:
        return list(self._personalities)


class FakeHardwareProfiler:
    def __init__(self, profile: Optional[HardwareProfile] = None):
        self._profile = profile or HardwareProfile(
            cpu_model="Fake CPU",
            cpu_count=8,
            total_ram_bytes=32_000_000_000,
            gpu_available=True,
            gpu_name="Fake GPU",
            vram_bytes=8_000_000_000,
            os_name="FakeOS",
            os_version="1.0",
            storage_total_bytes=1_000_000_000_000,
            storage_free_bytes=500_000_000_000,
            cuda_available=True,
            metal_available=False,
            directml_available=False,
        )

    def profile(self) -> HardwareProfile:
        return self._profile


@pytest.fixture
def sample_models() -> List[ModelInfo]:
    return [
        make_model(id="p1:llm-a", display_name="llm-a", provider="p1", capabilities={"tools"}),
        make_model(
            id="p1:vision-a",
            display_name="vision-a",
            provider="p1",
            category=ModelCategory.VISION,
            capabilities={"vision"},
        ),
        make_model(
            id="p2:embed-a",
            display_name="embed-a",
            provider="p2",
            category=ModelCategory.EMBEDDING,
            capabilities={"embedding"},
        ),
        make_model(
            id="p2:cloud-a",
            display_name="cloud-a",
            provider="p2",
            locality=CapabilityLocality.CLOUD,
            available=False,
        ),
    ]


@pytest.fixture
def registry(sample_models) -> GarageRegistry:
    reg = GarageRegistry()
    reg.register_model_provider(
        FakeModelProvider("p1", [m for m in sample_models if m.provider == "p1"])
    )
    reg.register_model_provider(
        FakeModelProvider("p2", [m for m in sample_models if m.provider == "p2"])
    )
    reg.set_voice_source(
        FakeVoiceSource({"heart": {"provider": "kokoro", "gender": "female", "language": "en"}})
    )
    reg.set_runtime_source(
        FakeRuntimeSource(
            [
                RuntimeInfo(runtime_id="media", version="0.5.5", state="ready", healthy=True, capabilities=["media.audio.voice"]),
                RuntimeInfo(runtime_id="voice", version="0.5.1", state="ready", healthy=True, capabilities=["speech.tts"]),
            ]
        )
    )
    reg.set_personality_source(
        FakePersonalitySource(
            [{"id": "zaram_prime", "name": "Zaram", "voice_engine": "kokoro", "voice_id": "heart"}]
        )
    )
    reg.set_hardware_profiler(FakeHardwareProfiler())
    return reg


@pytest.fixture
def manager(registry) -> GarageManager:
    scanner = GarageScanner(registry)
    return GarageManager(registry, scanner)


@pytest.fixture
def runtime(registry, manager) -> GarageRuntime:
    scanner = GarageScanner(registry)
    return GarageRuntime(
        event_bus=None,
        registry=registry,
        scanner=scanner,
        manager=manager,
        hardware_profiler=FakeHardwareProfiler(),
    )

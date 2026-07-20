"""Contract tests for the AI Garage (offline)."""

from __future__ import annotations

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


def test_enum_from_value_falls_back():
    assert ModelCategory.from_value("vision") is ModelCategory.VISION
    assert ModelCategory.from_value("not-real") is ModelCategory.OTHER
    assert ProviderKind.from_value(None) is ProviderKind.LOCAL_LLM
    assert HealthStatus.from_value("healthy") is HealthStatus.HEALTHY
    assert HealthStatus.from_value("nope") is HealthStatus.UNKNOWN


def test_model_info_roundtrip():
    model = ModelInfo(
        id="p1:foo",
        display_name="Foo",
        provider="p1",
        category=ModelCategory.VISION,
        capabilities={"vision", "tools"},
        supports_vision=True,
        supports_tools=True,
        locality=CapabilityLocality.CLOUD,
        available=True,
        health_status=HealthStatus.HEALTHY,
        context_length=4096,
        quantization="Q4",
    )
    data = model.to_dict()
    assert data["capabilities"] == ["tools", "vision"]
    assert data["locality"] == "cloud"
    assert data["category"] == "vision"

    restored = ModelInfo.from_dict(data)
    assert restored.id == model.id
    assert restored.category is ModelCategory.VISION
    assert restored.capabilities == {"vision", "tools"}
    assert restored.supports_vision is True
    assert restored.locality is CapabilityLocality.CLOUD


def test_voice_runtime_info_to_dict():
    v = VoiceInfo(id="heart", display_name="Heart", provider="kokoro", language="en", gender="female")
    assert v.to_dict()["provider"] == "kokoro"
    r = RuntimeInfo(runtime_id="media", version="0.5.5", state="ready", healthy=True)
    assert r.to_dict()["healthy"] is True
    h = HardwareProfile(cpu_count=4, total_ram_bytes=16)
    assert h.to_dict()["cpu_count"] == 4

"""Runtime tests for the AI Garage (offline)."""

from __future__ import annotations

from core.capability_router import CapabilityRouter
from core.event_bus import EventBus
from core.registry import RuntimeRegistry

from garage.runtime import RUNTIME_ID, RUNTIME_VERSION, GarageRuntime


def test_runtime_identity(runtime):
    assert runtime.get_runtime_id() == RUNTIME_ID
    assert runtime.get_version() == RUNTIME_VERSION
    assert runtime.get_state().value == "uninitialized"


def test_metadata_advertises_capabilities(runtime):
    meta = runtime.get_metadata()
    assert {c.id for c in meta.capabilities} == {"garage.discover", "garage.profile"}
    assert meta.runtime_id == RUNTIME_ID


async def test_initialize_registers_default_providers(runtime):
    assert runtime.get_state().value == "uninitialized"
    await runtime.initialize()
    assert runtime.get_state().value == "ready"
    ids = {p.provider_id for p in runtime.registry.list_model_providers()}
    assert "ollama" in ids
    assert "lm_studio" in ids


def test_runtime_health_check_shell(runtime):
    report = runtime.health_check()
    assert report["runtime_id"] == RUNTIME_ID
    assert report["healthy"] is False  # not yet READY


async def test_runtime_async_health(runtime):
    await runtime.initialize()
    report = await runtime.health()
    assert report["runtime_id"] == RUNTIME_ID
    assert "model_count" in report


def test_runtime_di_injects_registry():
    from garage.registry import GarageRegistry

    reg = GarageRegistry()
    rt = GarageRuntime(event_bus=None, registry=reg)
    assert rt.registry is reg


async def test_runtime_registers_with_kernel():
    bus = EventBus()
    reg = RuntimeRegistry(bus)
    rt = GarageRuntime(bus)
    reg.register(rt)  # must not raise
    assert reg.get_runtime(rt.get_runtime_id()) is rt

    router = CapabilityRouter(reg)
    assert router.resolve("garage.discover") is rt

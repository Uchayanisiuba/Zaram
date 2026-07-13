"""MediaRuntime tests (offline).

Covers runtime startup/shutdown, the Kernel ``Runtime`` protocol, dependency
injection, and Voice Runtime registration — all without Kokoro/Ollama/Unreal.
"""

from __future__ import annotations

import pytest

from core.contracts import RuntimeMetadata, RuntimeState
from core.event_bus import EventBus
from core.registry import RuntimeRegistry

from media.contracts import MediaType
from media.manager import MediaManager
from media.registry import MediaRegistry
from media.runtime import RUNTIME_ID, RUNTIME_VERSION, MediaRuntime
from media.tests.conftest import FakeMediaProvider


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def runtime(bus) -> MediaRuntime:
    return MediaRuntime(bus)


def test_runtime_identity(runtime):
    assert runtime.get_runtime_id() == RUNTIME_ID
    assert runtime.get_version() == RUNTIME_VERSION
    assert runtime.get_state() is RuntimeState.UNINITIALIZED


def test_metadata_advertises_media_capabilities(runtime, fake_provider):
    runtime.registry.register_provider("audio", fake_provider)
    meta = runtime.get_metadata()
    assert isinstance(meta, RuntimeMetadata)
    assert meta.runtime_id == RUNTIME_ID
    assert "media.discover" in [c.id for c in meta.capabilities]
    # the audio provider's capability is surfaced to the Kernel
    assert "media.audio.fake" in [c.id for c in meta.capabilities]


@pytest.mark.asyncio
async def test_runtime_initialize_and_shutdown(runtime):
    assert runtime.get_state() is RuntimeState.UNINITIALIZED
    await runtime.initialize()
    assert runtime.get_state() is RuntimeState.READY
    await runtime.shutdown()
    assert runtime.get_state() is RuntimeState.STOPPED


@pytest.mark.asyncio
async def test_runtime_publishes_ready_event(runtime):
    events = []
    runtime._event_bus = _CapturingBus(events)
    await runtime.initialize()
    assert any(e.event_type == "runtime.ready" for e in events)


@pytest.mark.asyncio
async def test_runtime_shutdown_closes_sessions(runtime):
    session = runtime.manager.create_session()
    runtime.manager.start_stream(session.session_id, provider="voice")
    assert runtime.manager.session_count() == 1
    await runtime.shutdown()
    assert runtime.manager.session_count() == 0


def test_runtime_health_check_protocol(runtime):
    report = runtime.health_check()
    assert report["runtime_id"] == RUNTIME_ID
    assert report["healthy"] is False  # not yet READY


@pytest.mark.asyncio
async def test_runtime_health_rich(runtime, fake_provider):
    runtime.registry.register_provider("audio", fake_provider)
    await runtime.initialize()
    report = await runtime.health()
    assert report["runtime_id"] == RUNTIME_ID
    assert report["runtime_status"] == RuntimeState.READY.value
    assert report["registered_services"] == 1
    assert MediaType.AUDIO.value in report["media_types"]


# --- dependency injection ---
def test_runtime_accepts_injected_dependencies(bus):
    registry = MediaRegistry()
    manager = MediaManager(registry, event_bus=bus)
    rt = MediaRuntime(bus, registry=registry, manager=manager)
    assert rt.registry is registry
    assert rt.manager is manager


# --- Voice Runtime registration ---
def test_discover_voice_runtime(runtime):
    voice_manager = object()
    cap = runtime.discover_voice_runtime(voice_manager)
    assert cap.media_type is MediaType.AUDIO
    assert cap.runtime_id == "voice"
    assert runtime.manager.has_voice_capability() is True
    assert runtime.manager.get_voice_handler() is voice_manager
    # the audio capability is surfaced to the Kernel via metadata
    meta = runtime.get_metadata()
    assert "media.audio.voice" in [c.id for c in meta.capabilities]


def test_voice_registration_does_not_import_voice_package():
    # Ensure the media package never imports the voice package at module load.
    import sys

    before = set(sys.modules)
    from media.runtime import MediaRuntime as _RT  # noqa: F401

    after = set(sys.modules)
    voice_modules = {m for m in after - before if m.startswith("voice")}
    assert voice_modules == set()


# --- Kernel registration (exactly like other runtimes) ---
@pytest.mark.asyncio
async def test_runtime_registers_with_kernel(bus):
    registry = RuntimeRegistry(bus)
    rt = MediaRuntime(bus)
    registry.register(rt)  # must not raise
    assert registry.get_runtime(RUNTIME_ID) is rt
    assert RUNTIME_ID in registry._runtimes


@pytest.mark.asyncio
async def test_kernel_resolves_voice_capability(bus):
    registry = RuntimeRegistry(bus)
    rt = MediaRuntime(bus)
    # Voice capability must be discovered *before* Kernel registration so the
    # capability map includes it.
    rt.discover_voice_runtime(object())
    registry.register(rt)
    # capability router resolves the bridged voice capability to the media runtime
    from core.capability_router import CapabilityRouter

    router = CapabilityRouter(registry)
    resolved = router.resolve("media.audio.voice")
    assert resolved is rt


class _CapturingBus:
    def __init__(self, sink):
        self._sink = sink

    def publish(self, event):
        self._sink.append(event)

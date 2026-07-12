"""VoiceManager tests."""

from __future__ import annotations

import pytest

from voice.exceptions import ProviderNotFoundError, ProviderUnavailableError
from voice.providers.base import VoiceProvider
from voice.voice_manager import VoiceManager, VoiceRuntime


class FakeProvider(VoiceProvider):
    name = "fake"

    def __init__(self) -> None:
        self.initialized = False
        self.shutdown_called = False

    async def initialize(self) -> None:
        self.initialized = True

    async def generate_audio(self, text: str, voice: str = "", **kwargs):
        return f"audio:{text}"

    async def stream_audio(self, text: str, voice: str = "", **kwargs):
        yield b"chunk"

    async def available_voices(self):
        return {"af_heart": {}}

    async def health_check(self):
        return {"available": True, "provider": self.name}

    async def shutdown(self) -> None:
        self.shutdown_called = True


@pytest.fixture
def manager() -> VoiceManager:
    return VoiceManager()


async def test_manager_initializes_without_provider(manager: VoiceManager):
    await manager.initialize()  # no provider configured -> must not raise
    report = await manager.health()
    assert report["active_provider"] is None
    assert report["providers"] == {}


async def test_provider_registry_works(manager: VoiceManager):
    await manager.register_provider("fake", FakeProvider)
    await manager.initialize()
    provider = manager.get_provider()
    assert isinstance(provider, FakeProvider)
    assert provider.initialized is True


async def test_missing_provider_handled(manager: VoiceManager):
    with pytest.raises(ProviderUnavailableError):
        manager.get_provider()
    with pytest.raises(ProviderNotFoundError):
        manager.get_provider("nope")


async def test_synthesize_routes_to_provider(manager: VoiceManager):
    await manager.register_provider("fake", FakeProvider)
    result = await manager.synthesize("hello")
    assert result == "audio:hello"


async def test_shutdown_works(manager: VoiceManager):
    await manager.register_provider("fake", FakeProvider)
    await manager.initialize()
    await manager.shutdown()
    assert manager.get_provider().shutdown_called is True


async def test_runtime_lifecycle():
    rt = VoiceRuntime()
    await rt.initialize()  # logs ready; no TTS provider in this milestone
    await rt.shutdown()

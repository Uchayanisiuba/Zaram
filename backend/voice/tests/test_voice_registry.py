"""VoiceRegistry tests."""

from __future__ import annotations

import pytest

from voice.exceptions import DuplicateProviderError, ProviderNotFoundError
from voice.providers.base import VoiceProvider
from voice.registry import VoiceRegistry


class FakeProvider(VoiceProvider):
    name = "fake"

    async def initialize(self) -> None:
        pass

    async def generate_audio(self, text: str, voice: str = "", **kwargs):
        return None

    async def stream_audio(self, text: str, voice: str = "", **kwargs):
        yield b""

    async def available_voices(self):
        return {}

    async def health_check(self):
        return {"available": True}

    async def shutdown(self) -> None:
        pass


def test_register_and_retrieve_class():
    reg = VoiceRegistry()
    reg.register("fake", FakeProvider)
    assert reg.is_registered("fake")
    assert reg.get("fake") is FakeProvider


def test_register_instance():
    reg = VoiceRegistry()
    inst = FakeProvider()
    reg.register("fake", inst)
    assert reg.get_instance("fake") is inst


def test_duplicate_protection():
    reg = VoiceRegistry()
    reg.register("fake", FakeProvider)
    with pytest.raises(DuplicateProviderError):
        reg.register("fake", FakeProvider)


def test_missing_provider_errors():
    reg = VoiceRegistry()
    with pytest.raises(ProviderNotFoundError):
        reg.get("missing")
    with pytest.raises(ProviderNotFoundError):
        reg.get_instance("missing")


def test_invalid_provider_rejected():
    reg = VoiceRegistry()
    with pytest.raises(ValueError):
        reg.register("bad", object())


def test_list_providers():
    reg = VoiceRegistry()
    reg.register("a", FakeProvider)
    reg.register("b", FakeProvider)
    assert set(reg.list_providers()) == {"a", "b"}
    assert reg.count() == 2

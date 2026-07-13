"""MediaRegistry tests (offline)."""

from __future__ import annotations

import pytest

from media.contracts import MediaType
from media.registry import MediaRegistry
from media.tests.conftest import FakeMediaProvider


def test_register_and_lookup(fake_provider):
    reg = MediaRegistry()
    reg.register_provider("fake", fake_provider)
    assert reg.is_registered("fake")
    assert reg.get_provider("fake") is fake_provider
    assert reg.list_providers() == ["fake"]
    assert reg.count() == 1


def test_duplicate_registration_rejected(fake_provider):
    reg = MediaRegistry()
    reg.register_provider("fake", fake_provider)
    with pytest.raises(ValueError):
        reg.register_provider("fake", fake_provider)


def test_invalid_provider_rejected():
    reg = MediaRegistry()
    with pytest.raises(TypeError):
        reg.register_provider("bad", object())


def test_remove_provider(fake_provider):
    reg = MediaRegistry()
    reg.register_provider("fake", fake_provider)
    assert reg.remove_provider("fake") is True
    assert reg.remove_provider("fake") is False
    assert reg.count() == 0


def test_discover_batch(fake_provider):
    reg = MediaRegistry()
    reg.discover({"a": fake_provider, "b": fake_provider})
    assert set(reg.list_providers()) == {"a", "b"}


def test_capability_discovery(fake_provider, unavailable_provider):
    reg = MediaRegistry()
    reg.register_provider("audio", fake_provider)
    reg.register_provider("image", unavailable_provider)
    caps = reg.capabilities()
    assert len(caps) == 2
    audio_caps = reg.capabilities_for_type(MediaType.AUDIO)
    assert len(audio_caps) == 1
    assert audio_caps[0].media_type is MediaType.AUDIO


def test_providers_for_type(fake_provider, unavailable_provider):
    reg = MediaRegistry()
    reg.register_provider("audio", fake_provider)
    reg.register_provider("image", unavailable_provider)
    assert reg.providers_for_type("audio") == ["audio"]
    assert reg.providers_for_type("image") == ["image"]
    assert reg.providers_for_type("video") == []
    # unknown string type degrades gracefully
    assert reg.providers_for_type("not-a-type") == []


def test_media_types_served(fake_provider, unavailable_provider):
    reg = MediaRegistry()
    reg.register_provider("audio", fake_provider)
    reg.register_provider("image", unavailable_provider)
    types = reg.media_types_served()
    assert MediaType.AUDIO in types
    assert MediaType.IMAGE in types


@pytest.mark.asyncio
async def test_health_aggregation(fake_provider, unavailable_provider):
    reg = MediaRegistry()
    reg.register_provider("audio", fake_provider)  # available
    reg.register_provider("image", unavailable_provider)  # not available
    health = await reg.health()
    assert health["provider_count"] == 2
    assert health["available_count"] == 1
    assert health["status"] == "degraded"
    assert "audio" in health["providers"]
    assert "image" in health["providers"]


@pytest.mark.asyncio
async def test_health_empty_is_unknown():
    reg = MediaRegistry()
    health = await reg.health()
    assert health["status"] == "unknown"
    assert health["provider_count"] == 0


@pytest.mark.asyncio
async def test_health_all_available_is_healthy(fake_provider):
    reg = MediaRegistry()
    reg.register_provider("a", fake_provider)
    reg.register_provider("b", FakeMediaProvider())
    health = await reg.health()
    assert health["status"] == "healthy"

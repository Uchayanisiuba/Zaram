"""Shared fixtures for media runtime tests (offline)."""

from __future__ import annotations

from typing import Any

import pytest

from media.contracts import MediaCapability, MediaLocality, MediaType
from media.providers import MediaProvider


class FakeMediaProvider(MediaProvider):
    """Minimal MediaProvider used across the media test-suite."""

    name = "fake"

    def __init__(self, *, available: bool = True, media_type: MediaType = MediaType.AUDIO):
        self._available = available
        self._media_type = media_type
        self.initialized = False
        self.shutdown_called = False

    async def initialize(self) -> None:
        self.initialized = True

    def capabilities(self):
        return [
            MediaCapability(
                id=f"media.{self._media_type.value}.{self.name}",
                media_type=self._media_type,
                provider_name=self.name,
            )
        ]

    def media_types(self):
        return [self._media_type]

    async def health_check(self):
        return {"available": self._available, "provider": self.name}

    async def shutdown(self) -> None:
        self.shutdown_called = True


@pytest.fixture
def fake_provider() -> FakeMediaProvider:
    return FakeMediaProvider()


@pytest.fixture
def unavailable_provider() -> FakeMediaProvider:
    return FakeMediaProvider(available=False, media_type=MediaType.IMAGE)

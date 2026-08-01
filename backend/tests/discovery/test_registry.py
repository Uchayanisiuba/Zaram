# backend/tests/discovery/test_registry.py
from __future__ import annotations

from typing import Any

import pytest

from runtime.discovery.contracts import DiscoveryResult, ProviderStatus
from runtime.discovery.registry import ProviderRegistry


class FakeProvider:
    def __init__(self, pid: str, provider_type: str = "web", available: bool = True, priority_value: int = 50) -> None:
        self._id = pid
        self._type = provider_type
        self._available = available
        self._priority_value = priority_value

    def get_provider_id(self) -> str:
        return self._id

    def get_provider_type(self) -> str:
        return self._type

    async def discover(self, request: Any, context: Any) -> list[DiscoveryResult]:  # type: ignore[return]
        return []

    def is_available(self) -> bool:
        return self._available

    def health_check(self) -> dict:
        return {"status": "healthy"}

    def priority(self) -> int:
        return self._priority_value

    def cache_ttl(self) -> int:
        return 900


class TestProviderRegistry:
    def test_register_and_list(self):
        registry = ProviderRegistry()
        p = FakeProvider("wikipedia", "encyclopedia")
        registry.register(p)
        providers = registry.list()
        assert len(providers) == 1
        assert providers[0].get_provider_id() == "wikipedia"

    def test_duplicate_registration(self):
        registry = ProviderRegistry()
        registry.register(FakeProvider("wikipedia"))
        with pytest.raises(ValueError):
            registry.register(FakeProvider("wikipedia"))

    def test_remove(self):
        registry = ProviderRegistry()
        registry.register(FakeProvider("wikipedia"))
        registry.remove("wikipedia")
        assert registry.list() == []

    def test_get(self):
        registry = ProviderRegistry()
        registry.register(FakeProvider("wikipedia"))
        assert registry.get("wikipedia") is not None
        assert registry.get("missing") is None

    def test_get_by_priority(self):
        registry = ProviderRegistry()
        registry.register(FakeProvider("a", priority_value=10))
        registry.register(FakeProvider("b", priority_value=90))
        ordered = registry.get_by_priority()
        assert ordered[0].get_provider_id() == "b"
        assert ordered[1].get_provider_id() == "a"

    def test_get_available(self):
        registry = ProviderRegistry()
        registry.register(FakeProvider("up", available=True))
        registry.register(FakeProvider("down", available=False))
        available = registry.get_available()
        assert len(available) == 1
        assert available[0].get_provider_id() == "up"

    def test_get_by_type(self):
        registry = ProviderRegistry()
        registry.register(FakeProvider("wiki", "encyclopedia"))
        registry.register(FakeProvider("ddg", "news"))
        encyclopedia = registry.get_by_type("encyclopedia")
        assert len(encyclopedia) == 1
        assert encyclopedia[0].get_provider_id() == "wiki"

    def test_health_check(self):
        registry = ProviderRegistry()
        registry.register(FakeProvider("p"))
        health = registry.health_check()
        assert "p" in health
        assert health["p"]["status"] == ProviderStatus.HEALTHY.value

# backend/tests/discovery/test_selector.py
from __future__ import annotations

from typing import Any

from runtime.discovery.contracts import DiscoveryIntent, DiscoveryRequest
from runtime.discovery.registry import ProviderRegistry
from runtime.discovery.selector import select_providers


class FakeProvider:
    def __init__(self, pid: str, provider_type: str, available: bool = True, priority_value: int = 50) -> None:
        self._id = pid
        self._type = provider_type
        self._available = available
        self._priority_value = priority_value

    def get_provider_id(self) -> str:
        return self._id

    def get_provider_type(self) -> str:
        return self._type

    async def discover(self, request: Any, context: Any) -> list:  # type: ignore[return]
        return []

    def is_available(self) -> bool:
        return self._available

    def health_check(self) -> dict:
        return {}

    def priority(self) -> int:
        return self._priority_value

    def cache_ttl(self) -> int:
        return 900


class TestSelectProviders:
    def test_explicit_providers(self):
        registry = ProviderRegistry()
        registry.register(FakeProvider("wikipedia", "encyclopedia"))
        registry.register(FakeProvider("github", "programming"))
        req = DiscoveryRequest(query="test", providers=["github"])
        selected = select_providers(registry, req)
        assert len(selected) == 1
        assert selected[0].get_provider_id() == "github"

    def test_intent_encyclopedia(self):
        registry = ProviderRegistry()
        registry.register(FakeProvider("wikipedia", "encyclopedia"))
        registry.register(FakeProvider("github", "programming"))
        req = DiscoveryRequest(query="test", intent=DiscoveryIntent.ENCYCLOPEDIA)
        selected = select_providers(registry, req)
        assert len(selected) == 1
        assert selected[0].get_provider_id() == "wikipedia"

    def test_intent_programming(self):
        registry = ProviderRegistry()
        registry.register(FakeProvider("wikipedia", "encyclopedia"))
        registry.register(FakeProvider("github", "programming"))
        req = DiscoveryRequest(query="test", intent=DiscoveryIntent.PROGRAMMING)
        selected = select_providers(registry, req)
        assert len(selected) == 1
        assert selected[0].get_provider_id() == "github"

    def test_intent_news(self):
        registry = ProviderRegistry()
        registry.register(FakeProvider("duckduckgo", "news"))
        req = DiscoveryRequest(query="test", intent=DiscoveryIntent.NEWS)
        selected = select_providers(registry, req)
        assert len(selected) == 1
        assert selected[0].get_provider_id() == "duckduckgo"

    def test_intent_general(self):
        registry = ProviderRegistry()
        registry.register(FakeProvider("duckduckgo", "news"))
        registry.register(FakeProvider("wikipedia", "encyclopedia"))
        req = DiscoveryRequest(query="test", intent=DiscoveryIntent.GENERAL)
        selected = select_providers(registry, req)
        assert len(selected) == 2

    def test_skips_unavailable(self):
        registry = ProviderRegistry()
        registry.register(FakeProvider("down", "web", available=False))
        registry.register(FakeProvider("up", "web", available=True))
        req = DiscoveryRequest(query="test", providers=["down", "up"])
        selected = select_providers(registry, req)
        assert len(selected) == 1
        assert selected[0].get_provider_id() == "up"

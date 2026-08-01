# backend/tests/discovery/test_runtime.py
from __future__ import annotations

import pytest

from runtime.discovery.contracts import (
    AuthorityLevel,
    Capability,
    DiscoveryContext,
    DiscoveryIntent,
    DiscoveryMetadata,
    DiscoveryRequest,
    DiscoveryResult,
    FreshnessLevel,
    RetrievalMode,
)
from runtime.discovery.runtime import DiscoveryRuntime


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

    def get_capabilities(self) -> list[Capability]:
        return [Capability.WEB]

    def get_authority_level(self) -> AuthorityLevel:
        return AuthorityLevel.COMMUNITY

    def estimated_cost(self) -> float:
        return 0.0

    def estimated_latency_ms(self) -> float:
        return 300.0

    def estimated_confidence(self) -> float:
        return 0.8

    async def discover(self, request: DiscoveryRequest, context: DiscoveryContext) -> list[DiscoveryResult]:
        return [
            DiscoveryResult(
                content=f"result from {self._id}",
                summary=f"summary from {self._id}",
                metadata=DiscoveryMetadata(
                    provider=self._id,
                    url=f"https://{self._id}.example.com",
                    title=f"Title {self._id}",
                    confidence=0.9,
                    freshness=FreshnessLevel.UNKNOWN,
                ),
                confidence=0.9,
                freshness=FreshnessLevel.UNKNOWN,
                provider=self._id,
                retrieval_time=0.0,
            )
        ]

    def is_available(self) -> bool:
        return self._available

    def health_check(self) -> dict:
        return {"status": "healthy"}

    def priority(self) -> int:
        return self._priority_value

    def cache_ttl(self) -> int:
        return 900


class FailingProvider:
    def __init__(self, pid: str, provider_type: str = "web") -> None:
        self._id = pid
        self._type = provider_type

    def get_provider_id(self) -> str:
        return self._id

    def get_provider_type(self) -> str:
        return self._type

    def get_capabilities(self) -> list[Capability]:
        return [Capability.WEB]

    def get_authority_level(self) -> AuthorityLevel:
        return AuthorityLevel.UNKNOWN

    def estimated_cost(self) -> float:
        return 0.0

    def estimated_latency_ms(self) -> float:
        return 300.0

    def estimated_confidence(self) -> float:
        return 0.5

    async def discover(self, request: DiscoveryRequest, context: DiscoveryContext) -> list[DiscoveryResult]:
        raise RuntimeError("provider failed")

    def is_available(self) -> bool:
        return True

    def health_check(self) -> dict:
        return {"status": "healthy"}

    def priority(self) -> int:
        return 50

    def cache_ttl(self) -> int:
        return 900


class TestDiscoveryRuntime:
    def setup_method(self):
        self.runtime = DiscoveryRuntime()

    def test_register_and_list_providers(self):
        self.runtime.register_provider(FakeProvider("wikipedia", "encyclopedia"))
        providers = self.runtime.list_providers()
        ids = [p["id"] for p in providers]
        assert "wikipedia" in ids

    def test_remove_provider(self):
        self.runtime.register_provider(FakeProvider("wikipedia"))
        self.runtime.remove_provider("wikipedia")
        providers = self.runtime.list_providers()
        assert all(p["id"] != "wikipedia" for p in providers)

    def test_get_provider(self):
        self.runtime.register_provider(FakeProvider("github"))
        assert self.runtime.get_provider("github") is not None
        assert self.runtime.get_provider("missing") is None

    def test_health_check(self):
        self.runtime.register_provider(FakeProvider("p"))
        health = self.runtime.health_check()
        assert "providers" in health
        assert "cache_size" in health

    @pytest.mark.asyncio
    async def test_discover_parallel(self):
        self.runtime.register_provider(FakeProvider("wikipedia", "encyclopedia"))
        self.runtime.register_provider(FakeProvider("github", "programming"))
        request = DiscoveryRequest(query="test", mode=RetrievalMode.PARALLEL)
        result = await self.runtime.discover(request)
        assert result.provider == "wikipedia"
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_discover_fallback(self):
        self.runtime.register_provider(FailingProvider("failing"))
        self.runtime.register_provider(FakeProvider("working"))
        request = DiscoveryRequest(query="test", mode=RetrievalMode.FALLBACK, providers=["failing", "working"])
        result = await self.runtime.discover(request)
        assert result.provider == "working"

    @pytest.mark.asyncio
    async def test_discover_no_providers(self):
        request = DiscoveryRequest(query="test")
        result = await self.runtime.discover(request)
        assert result.provider == "none"
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_cache(self):
        self.runtime.register_provider(FakeProvider("p"))
        request = DiscoveryRequest(query="cache_test", ttl=60)
        first = await self.runtime.discover(request)
        second = await self.runtime.discover(request)
        assert first.provider == second.provider

    @pytest.mark.asyncio
    async def test_telemetry(self):
        self.runtime.register_provider(FakeProvider("p"))
        request = DiscoveryRequest(query="telemetry_test", providers=["p"])
        await self.runtime.discover(request)
        stats = self.runtime.get_stats()
        assert stats["total_searches"] == 1

    @pytest.mark.asyncio
    async def test_intent_selection(self):
        self.runtime.register_provider(FakeProvider("wikipedia", "encyclopedia"))
        self.runtime.register_provider(FakeProvider("github", "programming"))
        request = DiscoveryRequest(query="test", intent=DiscoveryIntent.PROGRAMMING)
        result = await self.runtime.discover(request)
        assert result.provider == "github"

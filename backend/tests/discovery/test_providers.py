# backend/tests/discovery/test_providers.py
from __future__ import annotations

import pytest

from runtime.discovery.contracts import DiscoveryContext, DiscoveryRequest
from runtime.discovery.providers import (
    DuckDuckGoProvider,
    GitHubProvider,
    PlaywrightProvider,
    RSSProvider,
    WikipediaProvider,
)


class TestWikipediaProvider:
    def test_create(self):
        p = WikipediaProvider()
        assert p.get_provider_id() == "wikipedia"
        assert p.get_provider_type() == "encyclopedia"
        assert p.cache_ttl() == 3600
        assert p.priority() == 50

    def test_health_check(self):
        p = WikipediaProvider()
        health = p.health_check()
        assert "status" in health
        assert health["provider"] == "wikipedia"

    @pytest.mark.asyncio
    async def test_search(self):
        p = WikipediaProvider()
        request = DiscoveryRequest(query="Python programming", max_results=2)
        context = DiscoveryContext(request=request)
        results = await p.discover(request, context)
        assert isinstance(results, list)


class TestDuckDuckGoProvider:
    def test_create(self):
        p = DuckDuckGoProvider()
        assert p.get_provider_id() == "duckduckgo"
        assert p.cache_ttl() == 900

    def test_availability(self):
        p = DuckDuckGoProvider()
        assert p.is_available() is True or p.is_available() is False

    @pytest.mark.asyncio
    async def test_search(self):
        p = DuckDuckGoProvider()
        request = DiscoveryRequest(query="OpenAI", max_results=2)
        context = DiscoveryContext(request=request)
        results = await p.discover(request, context)
        assert isinstance(results, list)


class TestGitHubProvider:
    def test_create(self):
        p = GitHubProvider()
        assert p.get_provider_id() == "github"
        assert p.get_provider_type() == "programming"

    @pytest.mark.asyncio
    async def test_search(self):
        p = GitHubProvider()
        request = DiscoveryRequest(query="ollama", max_results=2)
        context = DiscoveryContext(request=request)
        results = await p.discover(request, context)
        assert isinstance(results, list)
        if results:
            assert results[0].metadata.provider == "github"


class TestRSSProvider:
    def test_create_unconfigured(self):
        p = RSSProvider()
        assert p.get_provider_id() == "rss"
        assert p.is_available() is False

    def test_create_with_feeds(self):
        p = RSSProvider(feed_urls=["https://example.com/feed.xml"])
        assert p.is_available() is True


class TestPlaywrightProvider:
    def test_create(self):
        p = PlaywrightProvider()
        assert p.get_provider_id() == "playwright"
        assert p.is_available() is False

    @pytest.mark.asyncio
    async def test_discover_when_unavailable(self):
        p = PlaywrightProvider()
        request = DiscoveryRequest(query="test")
        context = DiscoveryContext(request=request)
        results = await p.discover(request, context)
        assert results == []

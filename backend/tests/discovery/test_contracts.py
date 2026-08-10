# backend/tests/discovery/test_contracts.py
from __future__ import annotations

import pytest

from runtime.discovery.contracts import (
    DiscoveryContext,
    DiscoveryIntent,
    DiscoveryMetadata,
    DiscoveryRequest,
    DiscoveryResult,
    FreshnessLevel,
    RetrievalMode,
)


class TestEnums:
    def test_freshness_level_values(self):
        assert FreshnessLevel.UNKNOWN == "unknown"
        assert FreshnessLevel.STATIC == "static"
        assert FreshnessLevel.RECENT == "recent"
        assert FreshnessLevel.LIVE == "live"

    def test_discovery_intent_values(self):
        assert DiscoveryIntent.ENCYCLOPEDIA == "encyclopedia"
        assert DiscoveryIntent.PROGRAMMING == "programming"
        assert DiscoveryIntent.NEWS == "news"
        assert DiscoveryIntent.GENERAL == "general"

    def test_retrieval_mode_values(self):
        assert RetrievalMode.SINGLE == "single"
        assert RetrievalMode.PARALLEL == "parallel"
        assert RetrievalMode.FALLBACK == "fallback"
        assert RetrievalMode.PRIORITY == "priority"


class TestDiscoveryMetadata:
    def test_create_metadata(self):
        m = DiscoveryMetadata(
            provider="wikipedia",
            url="https://example.com",
            title="Test",
            author="Author",
            published="2024-01-01",
            language="en",
            confidence=0.9,
            freshness=FreshnessLevel.RECENT,
            license="CC0",
        )
        assert m.provider == "wikipedia"
        assert m.freshness == FreshnessLevel.RECENT
        assert m.confidence == 0.9

    def test_defaults(self):
        m = DiscoveryMetadata(provider="x", url="u", title="t")
        assert m.author is None
        assert m.language == "en"
        assert m.confidence == 0.8
        assert m.freshness == FreshnessLevel.UNKNOWN


class TestDiscoveryResult:
    def test_create_result(self):
        metadata = DiscoveryMetadata(provider="p", url="u", title="t")
        r = DiscoveryResult(
            content="content",
            summary="summary",
            metadata=metadata,
            confidence=0.9,
            freshness=FreshnessLevel.RECENT,
            provider="p",
            retrieval_time=10.0,
        )
        assert r.content == "content"
        assert r.confidence == 0.9
        assert r.provider == "p"

    def test_frozen_dataclass(self):
        metadata = DiscoveryMetadata(provider="p", url="u", title="t")
        r = DiscoveryResult(
            content="c", summary="s", metadata=metadata
        )
        with pytest.raises(AttributeError):
            r.content = "changed"  # type: ignore


class TestDiscoveryRequest:
    def test_default_request(self):
        req = DiscoveryRequest(query="test")
        assert req.query == "test"
        assert req.mode == RetrievalMode.PARALLEL
        assert req.max_results == 10
        assert req.language == "en"
        assert req.ttl == 900

    def test_custom_request(self):
        req = DiscoveryRequest(
            query="python",
            intent=DiscoveryIntent.PROGRAMMING,
            mode=RetrievalMode.FALLBACK,
            providers=["github"],
            max_results=5,
            language="fr",
            ttl=1800,
        )
        assert req.intent == DiscoveryIntent.PROGRAMMING
        assert req.providers == ["github"]
        assert req.language == "fr"


class TestDiscoveryContext:
    def test_context_creation(self):
        req = DiscoveryRequest(query="test")
        ctx = DiscoveryContext(request=req)
        assert ctx.request.query == "test"
        assert ctx.started_at > 0
        assert ctx.provider_results == {}
        assert ctx.errors == {}
        assert ctx.cancelled is False
        assert len(ctx.correlation_id) > 0

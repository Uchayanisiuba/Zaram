# backend/runtime/discovery/providers/rss.py
from __future__ import annotations

from typing import Any

from ..contracts import (
    AuthorityLevel,
    Capability,
    DiscoveryMetadata,
    DiscoveryResult,
    FreshnessLevel,
)
from .base import BaseDiscoveryProvider

try:
    import asyncio

    import feedparser
except Exception:
    asyncio = None  # type: ignore
    feedparser = None  # type: ignore


class RSSProvider(BaseDiscoveryProvider):
    """Searches RSS feeds for recent articles."""

    def __init__(self, feed_urls: list[str] | None = None) -> None:
        super().__init__(
            "rss",
            "rss",
            cache_ttl=600,
            capabilities=[Capability.NEWS, Capability.RESEARCH],
            authority=AuthorityLevel.COMMUNITY,
            cost=0.0,
            avg_latency_ms=500.0,
        )
        self._feed_urls = feed_urls or []
        self._available = bool(self._feed_urls)
        if not self._feed_urls:
            self._last_error = "RSS feeds not configured"

    async def discover(
        self, request: Any, context: Any
    ) -> list[DiscoveryResult]:
        if not self._feed_urls or feedparser is None:
            return []

        results: list[DiscoveryResult] = []
        query_terms = set(request.query.lower().split())
        for feed_url in self._feed_urls:
            feed = await asyncio.to_thread(feedparser.parse, feed_url)  # type: ignore
            for entry in feed.entries[: request.max_results]:
                title = entry.get("title", "")
                snippet = entry.get("summary", "")[:300]
                text = (title + " " + snippet).lower()
                if query_terms & set(text.split()):
                    metadata = DiscoveryMetadata(
                        provider="rss",
                        url=entry.get("link", ""),
                        title=title,
                        published=entry.get("published"),
                        language="en",
                        confidence=0.55,
                        freshness=FreshnessLevel.RECENT,
                        raw_metadata={"feed": feed_url},
                    )
                    results.append(DiscoveryResult(
                        content=snippet,
                        summary=snippet,
                        metadata=metadata,
                        confidence=0.55,
                        freshness=FreshnessLevel.RECENT,
                        provider="rss",
                        retrieval_time=0.0,
                    ))
        self._last_error = None
        self._record_success()
        return results

    def is_available(self) -> bool:
        return self._available

    def health_check(self) -> dict[str, Any]:
        base = super().health_check()
        base["feeds"] = len(self._feed_urls)
        return base

# backend/runtime/discovery/providers/duckduckgo.py
from __future__ import annotations

import time
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
    from duckduckgo_search import DDGS  # type: ignore
except Exception:  # pragma: no cover
    DDGS = None  # type: ignore


class DuckDuckGoProvider(BaseDiscoveryProvider):
    """Searches DuckDuckGo for web results."""

    def __init__(self) -> None:
        super().__init__(
            "duckduckgo",
            "news",
            cache_ttl=900,
            capabilities=[Capability.WEB, Capability.NEWS, Capability.COMMUNITY],
            authority=AuthorityLevel.COMMUNITY,
            cost=0.0,
            avg_latency_ms=400.0,
        )
        self._available = DDGS is not None

    async def discover(
        self, request: Any, context: Any
    ) -> list[DiscoveryResult]:
        if DDGS is None:
            self._last_error = "duckduckgo-search package not installed"
            return []

        max_results = request.max_results
        results: list[DiscoveryResult] = []
        for attempt in range(3):
            try:
                import asyncio
                def _search() -> list[dict[str, Any]]:
                    with DDGS() as ddgs:
                        return list(ddgs.text(request.query, max_results=max_results))

                search_results = await asyncio.to_thread(_search)
                for r in search_results:
                    url = r.get("href") or r.get("url")
                    if not url:
                        continue
                    metadata = DiscoveryMetadata(
                        provider="duckduckgo",
                        url=url,
                        title=r.get("title", ""),
                        language="en",
                        confidence=0.6,
                        freshness=FreshnessLevel.UNKNOWN,
                    )
                    snippet = (r.get("body") or "")[:280]
                    results.append(DiscoveryResult(
                        content=snippet,
                        summary=snippet,
                        metadata=metadata,
                        confidence=0.6,
                        freshness=FreshnessLevel.UNKNOWN,
                        provider="duckduckgo",
                        retrieval_time=0.0,
                    ))
                self._last_error = None
                self._record_success()
                break
            except Exception as exc:
                self._last_error = str(exc)
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    self._record_failure(str(exc))
        return results[:max_results]

    def is_available(self) -> bool:
        return self._available

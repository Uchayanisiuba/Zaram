# backend/runtime/discovery/offline.py
from __future__ import annotations

from typing import Any

from .contracts import DiscoveryResult, FreshnessLevel


class OfflineDiscovery:
    """Fallback discovery when network is unavailable."""

    def __init__(self, cache: Any, knowledge_runtime: Any = None) -> None:
        self._cache = cache
        self._knowledge_runtime = knowledge_runtime

    async def discover_offline(self, request: Any, context: Any) -> list[DiscoveryResult]:
        results: list[DiscoveryResult] = []
        cache_key = f"discovery:{hash(request.query.strip().lower())}:offline"
        cached = self._cache.get(cache_key, ttl=request.ttl)
        if cached:
            if isinstance(cached, list):
                results.extend(cached)
            elif isinstance(cached, DiscoveryResult):
                results.append(cached)

        if self._knowledge_runtime:
            try:
                knowledge_results = self._knowledge_runtime.search(request.query, max_results=request.max_results)
                for kr in knowledge_results.results:
                    results.append(DiscoveryResult(
                        content=kr.snippet,
                        summary=kr.snippet,
                        metadata=kr.metadata if hasattr(kr, "metadata") else kr,
                        confidence=kr.confidence,
                        freshness=FreshnessLevel.STATIC,
                        provider="knowledge",
                    ))
            except Exception:
                pass

        return results

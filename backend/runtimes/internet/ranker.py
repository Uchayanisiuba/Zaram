from __future__ import annotations

import time
from typing import Any

from .contracts import InternetRanker, SearchResult, SearchQuery


class InternetRankerImpl(InternetRanker):
    """Ranks internet search results by relevance, source trust, and recency."""

    def __init__(self):
        self._connector_priorities = {
            "wikipedia": 0.9,
            "github": 0.8,
            "duckduckgo": 0.6,
            "rss": 0.5,
        }
        self._stats = {"total_rankings": 0, "total_latency_ms": 0.0}

    async def rank(self, results: list[SearchResult], query: SearchQuery) -> list[SearchResult]:
        start = time.time()
        self._stats["total_rankings"] += 1

        if not results:
            return []

        query_terms = set(query.query.lower().split())

        for result in results:
            score = result.score

            # Connector priority
            connector_priority = self._connector_priorities.get(result.connector, 0.5)

            # Title match
            title_match = len(query_terms & set(result.title.lower().split())) / max(len(query_terms), 1)

            # Snippet match
            snippet_match = len(query_terms & set(result.snippet.lower().split())) / max(len(query_terms), 1)

            # Recency (if metadata has date)
            recency = 0.5
            if "published" in result.metadata:
                try:
                    from dateutil import parser
                    pub_date = parser.parse(result.metadata["published"])
                    age_days = (time.time() - pub_date.timestamp()) / 86400
                    recency = 1.0 / (1.0 + age_days / 30.0)
                except Exception:
                    pass

            # Combine scores
            combined = (
                0.35 * score +
                0.25 * connector_priority +
                0.20 * title_match +
                0.15 * snippet_match +
                0.05 * recency
            )
            result.score = combined

        results.sort(key=lambda r: r.score, reverse=True)

        latency = (time.time() - start) * 1000
        self._stats["total_latency_ms"] += latency
        return results[: query.max_results]

    def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "stats": self._stats,
            "avg_latency_ms": self._stats["total_latency_ms"] / max(self._stats["total_rankings"], 1),
            "connector_priorities": self._connector_priorities,
        }
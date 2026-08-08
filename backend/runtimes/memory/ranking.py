from __future__ import annotations

import time
import math
from typing import Any

from .contracts import MemoryQuery, MemoryRanker, MemoryResult


class MemoryRankerImpl(MemoryRanker):
    """Ranks memory results by relevance, importance, recency, and access patterns."""

    def __init__(self):
        self._stats = {"total_rankings": 0, "total_latency_ms": 0.0}
        self._weights = {
            "semantic": 0.35,
            "importance": 0.20,
            "recency": 0.15,
            "access": 0.10,
            "keyword": 0.10,
            "session_match": 0.10,
        }

    async def rank(self, results: list[MemoryResult], query: MemoryQuery) -> list[MemoryResult]:
        start = time.time()
        self._stats["total_rankings"] += 1

        if not results:
            return []

        now = time.time()

        for result in results:
            record = result.record
            # Similarity as retrieval produced it. Preserved, not overwritten:
            # the blend below is an *ordering*, and the citation floor is a
            # question about relevance. Merging them let a fact with a cosine
            # of 0.20 clear a 0.42 relevance threshold on recency and session
            # membership alone.
            score = result.relevance if result.relevance is not None else result.score
            result.relevance = score

            importance_factor = record.importance
            recency_factor = self._recency_score(record.created_at, now)
            access_factor = min(record.access_count / 10.0, 1.0)
            keyword_factor = self._keyword_match(record, query)
            session_factor = 1.0 if query.session_id and record.session_id == query.session_id else 0.0

            combined = (
                self._weights["semantic"] * score +
                self._weights["importance"] * importance_factor +
                self._weights["recency"] * recency_factor +
                self._weights["access"] * access_factor +
                self._weights["keyword"] * keyword_factor +
                self._weights["session_match"] * session_factor
            )

            result.score = combined

        results.sort(key=lambda r: r.score, reverse=True)
        for i, r in enumerate(results):
            r.rank = i + 1

        latency = (time.time() - start) * 1000
        self._stats["total_latency_ms"] += latency
        return results[: query.max_results]

    def _recency_score(self, created_at: float, now: float) -> float:
        age_days = (now - created_at) / 86400
        return 1.0 / (1.0 + age_days / 30.0)

    def _keyword_match(self, record: MemoryRecord, query: MemoryQuery) -> float:
        """Overlap on words that carry meaning.

        The third copy of this rule in the codebase, and the third that split
        on whitespace and counted stopwords. `is`, `the` and `of` match almost
        every document, so any question with a few function words scored
        against the whole Spine. Now shares one tokenizer with the index and
        the retriever.
        """
        from .index import content_tokens

        if not query.query:
            return 0.0
        query_words = content_tokens(query.query)
        if not query_words:
            return 0.0
        content_words = content_tokens(record.content)
        overlap = len(query_words & content_words)
        return min(overlap / len(query_words), 1.0)

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "stats": self._stats,
            "avg_latency_ms": self._stats["total_latency_ms"] / max(self._stats["total_rankings"], 1),
            "weights": self._weights,
        }
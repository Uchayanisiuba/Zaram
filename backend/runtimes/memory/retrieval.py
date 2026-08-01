from __future__ import annotations

import time
from typing import Any

from .contracts import (
    MemoryIndex,
    MemoryQuery,
    MemoryRecord,
    MemoryResult,
    MemoryRetriever,
    MemoryStore,
    RetrievalStrategy,
)


class HybridMemoryRetriever(MemoryRetriever):
    """Retrieves memories using multiple strategies and merges results."""

    def __init__(self, store: MemoryStore, index: MemoryIndex | None = None):
        self._store = store
        self._index = index
        self._stats = {"total_retrievals": 0, "total_latency_ms": 0.0}

    async def retrieve(self, query: MemoryQuery) -> list[MemoryResult]:
        start = time.time()
        self._stats["total_retrievals"] += 1

        all_candidates: dict[str, tuple[MemoryRecord, float, str]] = {}

        if query.strategy in (RetrievalStrategy.KEYWORD_MATCH, RetrievalStrategy.HYBRID):
            keyword_results = await self._keyword_search(query)
            for record, score in keyword_results:
                if record.id not in all_candidates or score > all_candidates[record.id][1]:
                    all_candidates[record.id] = (record, score, "keyword")

        if query.strategy in (RetrievalStrategy.VECTOR_SIMILARITY, RetrievalStrategy.HYBRID):
            if self._index:
                vector_results = await self._vector_search(query)
                for record, score in vector_results:
                    if record.id not in all_candidates or score > all_candidates[record.id][1]:
                        all_candidates[record.id] = (record, score, "vector")

        if query.strategy == RetrievalStrategy.TEMPORAL:
            temporal_results = await self._temporal_search(query)
            for record, score in temporal_results:
                if record.id not in all_candidates or score > all_candidates[record.id][1]:
                    all_candidates[record.id] = (record, score, "temporal")

        results = [
            MemoryResult(record=record, score=score, match_reason=reason, rank=0)
            for record, score, reason in all_candidates.values()
        ]

        latency = (time.time() - start) * 1000
        self._stats["total_latency_ms"] += latency
        print(f"[MemoryRetriever] Retrieved {len(results)} candidates in {latency:.1f}ms")
        return results

    async def _keyword_search(self, query: MemoryQuery) -> list[tuple[MemoryRecord, float]]:
        records = await self._store.query(query)
        query_terms = set(query.query.lower().split())
        results = []
        for record in records:
            if not query_terms:
                results.append((record, 0.5))
                continue
            content_terms = set(record.content.lower().split())
            overlap = len(query_terms & content_terms)
            if overlap > 0:
                score = overlap / len(query_terms)
                if record.tags:
                    tag_overlap = len(set(query_terms) & set(t.lower() for t in record.tags))
                    score += tag_overlap * 0.1
                results.append((record, score))
        return sorted(results, key=lambda x: x[1], reverse=True)[: query.max_results]

    async def _vector_search(self, query: MemoryQuery) -> list[tuple[MemoryRecord, float]]:
        if not self._index:
            return []
        indexed = await self._index.search(query)
        if not indexed:
            return []
        records = []
        for record_id, score in indexed[: query.max_results]:
            record = await self._store.get(record_id)
            if record:
                records.append((record, score))
        return records

    async def _temporal_search(self, query: MemoryQuery) -> list[tuple[MemoryRecord, float]]:
        records = await self._store.query(query)
        now = time.time()
        results = []
        for record in records:
            age_days = (now - record.created_at) / 86400
            score = 1.0 / (1.0 + age_days)
            results.append((record, score))
        return sorted(results, key=lambda x: x[1], reverse=True)[: query.max_results]

    async def health_check(self) -> dict[str, Any]:
        store_health = await self._store.health_check()
        index_health = await self._index.health_check() if self._index else {"status": "disabled"}
        return {
            "status": "healthy" if store_health.get("status") == "healthy" else "degraded",
            "store": store_health,
            "index": index_health,
            "stats": self._stats,
            "avg_latency_ms": self._stats["total_latency_ms"] / max(self._stats["total_retrievals"], 1),
        }
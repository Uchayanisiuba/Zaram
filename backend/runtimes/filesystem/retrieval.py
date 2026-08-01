from __future__ import annotations

import math
from typing import Any

from .contracts import (
    FilesystemQuery,
    FileRecord,
    FileSearchResult,
    FilesystemRetriever,
    SearchStrategy,
)


class FilesystemRetrieverImpl(FilesystemRetriever):
    """Retrieves files using full-text and metadata search."""

    def __init__(self, store, index):
        self._store = store
        self._index = index
        self._stats = {"total_retrievals": 0, "total_latency_ms": 0.0}

    async def retrieve(self, query: FilesystemQuery) -> list[FileSearchResult]:
        import time
        start = time.time()
        self._stats["total_retrievals"] += 1

        if query.strategy == SearchStrategy.METADATA:
            records = await self._store.query(query)
            results = [
                FileSearchResult(record=r, score=1.0, match_type="metadata", rank=0)
                for r in records
            ]
        elif query.strategy == SearchStrategy.FULLTEXT:
            indexed = await self._index.search(query)
            results = []
            for record_id, score in indexed:
                record = await self._store.get(record_id)
                if record:
                    results.append(FileSearchResult(record=record, score=score, match_type="fulltext", rank=0))
        else:
            indexed = await self._index.search(query)
            results = []
            for record_id, score in indexed:
                record = await self._store.get(record_id)
                if record:
                    results.append(FileSearchResult(record=record, score=score, match_type="hybrid", rank=0))

        for i, r in enumerate(sorted(results, key=lambda x: x.score, reverse=True)):
            r.rank = i + 1

        self._stats["total_latency_ms"] += (time.time() - start) * 1000
        return results[: query.max_results]

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "stats": self._stats,
            "avg_latency_ms": self._stats["total_latency_ms"] / max(self._stats["total_retrievals"], 1),
        }
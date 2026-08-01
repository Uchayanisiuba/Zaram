from __future__ import annotations

import json
import os
import time
import math
from typing import Any

from .contracts import MemoryIndex, MemoryQuery, MemoryRecord, RetrievalStrategy


class VectorMemoryIndex(MemoryIndex):
    """In-memory vector index for semantic similarity search."""

    def __init__(self, embedding_dim: int = 384):
        self._embeddings: dict[str, list[float]] = {}
        self._embedding_dim = embedding_dim
        self._indexed_at = 0.0

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def add(self, record: MemoryRecord) -> None:
        if record.embedding:
            self._embeddings[record.id] = record.embedding

    async def remove(self, record_id: str) -> None:
        self._embeddings.pop(record_id, None)

    async def search(self, query: MemoryQuery) -> list[tuple[str, float]]:
        if not query.query or not query.query.strip():
            return []

        query_embedding = query.metadata.get("query_embedding")
        if not query_embedding:
            return []

        results = []
        for rid, embedding in self._embeddings.items():
            score = self._cosine_similarity(query_embedding, embedding)
            if score > 0.1:
                results.append((rid, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[: query.max_results]

    async def rebuild(self) -> None:
        self._indexed_at = time.time()

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "indexed_vectors": len(self._embeddings),
            "dimension": self._embedding_dim,
            "last_rebuilt": self._indexed_at,
        }


class HybridMemoryIndex(MemoryIndex):
    """Hybrid index combining vector similarity with keyword matching."""

    def __init__(self, embedding_dim: int = 384):
        self._vector_index = VectorMemoryIndex(embedding_dim)
        self._keyword_index: dict[str, set[str]] = {}
        self._indexed_at = 0.0

    def _tokenize(self, text: str) -> set[str]:
        import re

        return set(re.findall(r"\b\w+\b", text.lower()))

    async def add(self, record: MemoryRecord) -> None:
        await self._vector_index.add(record)
        tokens = self._tokenize(record.content)
        for tag in record.tags:
            tokens.add(tag.lower())
        for token in tokens:
            self._keyword_index.setdefault(token, set()).add(record.id)

    async def remove(self, record_id: str) -> None:
        await self._vector_index.remove(record_id)
        for token_set in self._keyword_index.values():
            token_set.discard(record_id)

    async def search(self, query: MemoryQuery) -> list[tuple[str, float]]:
        vector_results = await self._vector_index.search(query)
        vector_scores = {rid: score for rid, score in vector_results}

        query_tokens = self._tokenize(query.query)
        keyword_scores: dict[str, float] = {}
        for token in query_tokens:
            if token in self._keyword_index:
                for rid in self._keyword_index[token]:
                    keyword_scores[rid] = keyword_scores.get(rid, 0) + 1.0

        all_ids = set(vector_scores.keys()) | set(keyword_scores.keys())
        results = []
        for rid in all_ids:
            v_score = vector_scores.get(rid, 0.0)
            k_score = keyword_scores.get(rid, 0.0)
            combined = 0.7 * v_score + 0.3 * min(k_score / max(len(query_tokens), 1), 1.0)
            if combined > 0.05:
                results.append((rid, combined))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[: query.max_results]

    async def rebuild(self) -> None:
        await self._vector_index.rebuild()
        self._indexed_at = time.time()

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "vector_index": await self._vector_index.health_check(),
            "keyword_tokens": len(self._keyword_index),
            "last_rebuilt": self._indexed_at,
        }


class TemporalMemoryIndex(MemoryIndex):
    """Time-based index for temporal queries."""

    def __init__(self):
        self._by_time: dict[str, float] = {}

    async def add(self, record: MemoryRecord) -> None:
        self._by_time[record.id] = record.created_at

    async def remove(self, record_id: str) -> None:
        self._by_time.pop(record_id, None)

    async def search(self, query: MemoryQuery) -> list[tuple[str, float]]:
        if not query.time_range:
            return []

        start, end = query.time_range
        results = []
        for rid, created in self._by_time.items():
            if start <= created <= end:
                age = time.time() - created
                recency_score = 1.0 / (1.0 + age / 86400)
                results.append((rid, recency_score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[: query.max_results]

    async def rebuild(self) -> None:
        pass

    async def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "indexed_records": len(self._by_time)}


def create_memory_index(index_type: str = "hybrid", **kwargs) -> MemoryIndex:
    if index_type == "vector":
        return VectorMemoryIndex(kwargs.get("embedding_dim", 384))
    elif index_type == "temporal":
        return TemporalMemoryIndex()
    return HybridMemoryIndex(kwargs.get("embedding_dim", 384))
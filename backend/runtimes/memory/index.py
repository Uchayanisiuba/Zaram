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

    async def rebuild(self, records: list[MemoryRecord] | None = None) -> None:
        """Rebuild the vector index from ``records``.

        The index lives in memory, so it is empty on every boot. Persisted
        records are unsearchable until this is called with them.
        """
        if records is not None:
            self._embeddings.clear()
            for record in records:
                if record.embedding:
                    self._embeddings[record.id] = record.embedding
        self._indexed_at = time.time()

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "indexed_vectors": len(self._embeddings),
            "dimension": self._embedding_dim,
            "last_rebuilt": self._indexed_at,
        }


#: Words that match almost every document and therefore rank nothing.
#:
#: Their absence was a live recall bug, found by `test_recall_eval.py` on its
#: first run. "What is the capital of France?" matched a Harbour Lane project
#: brief on `is`, `of` and `the` — three of its six tokens — which bought a
#: 0.15 boost and carried a completely unrelated document over the citation
#: threshold. Rule 2 is about answers carrying their sources, and that only
#: means anything if the converse holds: a citation the answer did not use is a
#: false claim of provenance.
_STOPWORDS = frozenset("""
a an and are as at be been but by can could did do does for from had has have
he her his how i if in into is it its me my no not of on or our should so than
that the their them then there these they this to too was we were what when
where which who will with would you your
""".split())


def content_tokens(text: str) -> set[str]:
    """Tokens worth ranking on. Stopwords, punctuation and bare digits are not.

    Module-level and shared, because `HybridMemoryRetriever` needs exactly this
    rule and had its own whitespace-splitting version that disagreed — which is
    how `France?` became a term and `is` became a good one.
    """
    import re

    return {
        t
        for t in re.findall(r"\b\w+\b", text.lower())
        if t not in _STOPWORDS and not t.isdigit()
    }


class HybridMemoryIndex(MemoryIndex):
    """Hybrid index combining vector similarity with keyword matching.

    Keyword matching **boosts** a semantic score and never dilutes one. The
    original blend was `0.7 * vector + 0.3 * keyword`, which capped any
    document matching on meaning alone at 0.7 of its true similarity: a
    genuinely relevant note scoring 0.599 under bge-m3 arrived as 0.407 and was
    dropped by a threshold of 0.42. Both halves of that failure — unrelated
    documents lifted by stopwords, relevant ones pushed under by dilution —
    came from this one line, and `MIN_RECALL_SCORE` had been calibrated
    *through* the distortion, which is why it held on a two-fact Spine and
    collapsed on five documents.
    """

    #: How much a full keyword match can add, as a fraction of the headroom
    #: left above the semantic score. Bounded by construction: the result can
    #: never exceed 1.0 and never fall below the vector score.
    KEYWORD_BOOST = 0.3

    def __init__(self, embedding_dim: int = 384):
        self._vector_index = VectorMemoryIndex(embedding_dim)
        self._keyword_index: dict[str, set[str]] = {}
        self._indexed_at = 0.0

    def _tokenize(self, text: str) -> set[str]:
        import re

        return set(re.findall(r"\b\w+\b", text.lower()))

    def _content_tokens(self, text: str) -> set[str]:
        """Tokens worth ranking on.

        Kept separate from `_tokenize` because the *index* still stores every
        token — a document containing "the" should be findable by a literal
        search for it — while *scoring* must ignore the ones that carry no
        signal.
        """
        return content_tokens(text)

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

        query_tokens = self._content_tokens(query.query)
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
            ratio = min(k_score / len(query_tokens), 1.0) if query_tokens else 0.0
            # A boost into the headroom above the semantic score, never a
            # weighted average. `combined >= v_score` always, and `<= 1.0`
            # always, so the number stays a similarity a threshold can be
            # calibrated against.
            combined = v_score + (1.0 - v_score) * self.KEYWORD_BOOST * ratio
            if combined > 0.05:
                results.append((rid, combined))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[: query.max_results]

    async def rebuild(self, records: list[MemoryRecord] | None = None) -> None:
        """Rebuild both the vector and keyword indexes from ``records``."""
        await self._vector_index.rebuild(records)
        if records is not None:
            self._keyword_index.clear()
            for record in records:
                tokens = self._tokenize(record.content)
                for tag in record.tags:
                    tokens.add(tag.lower())
                for token in tokens:
                    self._keyword_index.setdefault(token, set()).add(record.id)
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

    async def rebuild(self, records: list[MemoryRecord] | None = None) -> None:
        if records is not None:
            self._by_time = {r.id: r.created_at for r in records}

    async def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "indexed_records": len(self._by_time)}


def create_memory_index(index_type: str = "hybrid", **kwargs) -> MemoryIndex:
    if index_type == "vector":
        return VectorMemoryIndex(kwargs.get("embedding_dim", 384))
    elif index_type == "temporal":
        return TemporalMemoryIndex()
    return HybridMemoryIndex(kwargs.get("embedding_dim", 384))
from __future__ import annotations

import json
import math
import os
import re
import time
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


#: An identifier's parts, for `content_tokens` below. Handles `snake_case` by
#: splitting on the underscore first, then each remaining run by camel
#: boundaries — including the acronym case, where `HTTPServer` is `HTTP` and
#: `Server` rather than `H`, `T`, `T`, `P` and `Server`.
_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")

#: Below this an identifier part is noise — the `i` in `iPhone`, the `x` in
#: `xPos`. Long enough to carry meaning, short enough to keep `id`, `db`, `os`.
_MIN_PART = 2


def identifier_parts(word: str) -> list[str]:
    """`resident_budget_bytes` → `resident`, `budget`, `bytes`.

    Returns the parts only when there is more than one; a plain word is not an
    identifier and splitting it would return itself.
    """
    parts: list[str] = []
    for run in word.split("_"):
        parts.extend(_CAMEL.findall(run))
    return parts if len(parts) > 1 else []


def content_tokens(text: str) -> set[str]:
    """Tokens worth ranking on. Stopwords, punctuation and bare digits are not.

    Module-level and shared, because `HybridMemoryRetriever` needs exactly this
    rule and had its own whitespace-splitting version that disagreed — which is
    how `France?` became a term and `is` became a good one.

    **An identifier is indexed whole and in parts**, and that is what makes a
    codebase searchable at all. The previous version lowercased before
    splitting on `\\w+`, so `chunkCode` became the single token `chunkcode` and
    a search for *"chunk code"* could not match it — invisible, with no error,
    across every camelCase name in a TypeScript project. `snake_case` failed
    the same way in the other direction: `resident_budget_bytes` matched only
    an exact repetition of itself.

    So both are emitted. The whole identifier still scores when someone pastes
    it exactly, which is the strongest possible signal that they mean *that*
    symbol, and the parts let a half-remembered name find it. Splitting is
    done on the original text, because lowercasing first destroys the camel
    boundary this depends on.

    This widens candidate *membership* and the keyword term in the ranking
    blend. It does not touch the similarity a citation is judged against —
    that stays the vector's answer, on the vector's scale.
    """
    tokens: set[str] = set()

    for word in re.findall(r"\b\w+\b", text):
        lowered = word.lower()
        if lowered.isdigit():
            continue
        if lowered not in _STOPWORDS:
            tokens.add(lowered)
        for part in identifier_parts(word):
            part = part.lower()
            if len(part) >= _MIN_PART and part not in _STOPWORDS and not part.isdigit():
                tokens.add(part)

    return tokens


class HybridMemoryIndex(MemoryIndex):
    """Hybrid index: keyword decides candidates, the vector decides the score.

    Hybrid used to mean blending the two into one number —
    `0.7 * vector + 0.3 * keyword` — which did both possible harms at once. It
    capped any document matching on meaning alone at 0.7 of its true
    similarity, so a genuinely relevant note scoring 0.599 under bge-m3
    arrived as 0.407 and was dropped by the 0.42 floor; and, with no stopword
    filtering, it lifted unrelated documents that happened to share `is`,
    `the` and `of`. `MIN_RECALL_SCORE` had been calibrated *through* that
    distortion, which is why it held on a two-fact Spine and collapsed on five
    documents.

    What comes out of here is a **similarity**, because that is what the
    citation floor is compared against. Keyword overlap, importance, recency
    and access count all belong to `MemoryRankerImpl`, which orders results —
    a different question from whether a fact is relevant enough to cite.
    """

    #: What a keyword-only match is worth when there is no embedding to
    #: compare — an unindexed record, or the hash-backend fallback. Below the
    #: citation floor on purpose: such a record can still be *found*, but it is
    #: not evidence a similarity threshold should treat as relevant, because
    #: nothing measured how relevant it is.
    KEYWORD_ONLY_SCORE = 0.4

    def __init__(self, embedding_dim: int = 384):
        self._vector_index = VectorMemoryIndex(embedding_dim)
        self._keyword_index: dict[str, set[str]] = {}
        # The lexical side is BM25 (`bm25s`, MIT) over the same tokens the
        # set index holds — added 14 September 2026 for the failure CLAUDE.md
        # names: "write that up as a proposal" retrieves nothing by
        # similarity, while the rare tokens in it — a client, a reference
        # number — are exactly what a lexical index finds and a dense
        # embedding is worst at. Term overlap counted every matching token
        # as one; BM25 weighs a token by how rare it is across the Spine and
        # how much of a record it fills, which is the difference between
        # "Abuja" mattering and "invoice" mattering.
        #
        # Built lazily and whole: bm25s indexes a corpus, not a stream, and
        # the Spine is thousands of short records, so a rebuild on the next
        # search after a change costs milliseconds. `_corpus` is the source
        # of truth; the retriever is a cache of it.
        self._corpus: dict[str, list[str]] = {}
        self._bm25: Any = None
        self._bm25_ids: list[str] = []
        self._indexed_at = 0.0

    # ------------------------------------------------------------- lexical

    def _bm25_invalidate(self) -> None:
        self._bm25 = None

    def _bm25_ready(self) -> bool:
        """Build the BM25 index from the corpus if it has changed. False when
        there is nothing to index, or bm25s is not importable."""
        if self._bm25 is not None:
            return True
        if not self._corpus:
            return False
        try:
            import bm25s
        except ImportError:  # pragma: no cover - declared; the set index still answers
            return False
        ids = list(self._corpus)
        retriever = bm25s.BM25()
        retriever.index([self._corpus[rid] for rid in ids], show_progress=False)
        self._bm25 = retriever
        self._bm25_ids = ids
        return True

    def _bm25_scores(self, query_tokens: set[str]) -> dict[str, float]:
        """BM25 score per record for the query's content tokens, normalised so
        the best match is 1.0. Empty when nothing matches or nothing is built.

        Normalised because what leaves `search` is a *similarity* and the
        keyword-only entry is `KEYWORD_ONLY_SCORE * this` — a proportion of an
        honest ceiling, never a raw BM25 magnitude that would be compared
        against a floor measured as a cosine.
        """
        if not query_tokens or not self._bm25_ready():
            return {}
        k = min(len(self._bm25_ids), 50)
        try:
            docs, scores = self._bm25.retrieve([sorted(query_tokens)], k=k, show_progress=False)
        except Exception:  # noqa: BLE001 - a lexical failure must not take recall down
            return {}
        out: dict[str, float] = {}
        best = float(scores[0][0]) if len(scores) and len(scores[0]) else 0.0
        if best <= 0:
            return {}
        for idx, score in zip(docs[0], scores[0]):
            if float(score) <= 0:
                continue
            out[self._bm25_ids[int(idx)]] = float(score) / best
        return out

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
        self._corpus[record.id] = sorted(self._content_tokens(record.content) | {t.lower() for t in record.tags})
        self._bm25_invalidate()

    async def remove(self, record_id: str) -> None:
        await self._vector_index.remove(record_id)
        for token_set in self._keyword_index.values():
            token_set.discard(record_id)
        if self._corpus.pop(record_id, None) is not None:
            self._bm25_invalidate()

    async def search(self, query: MemoryQuery) -> list[tuple[str, float]]:
        vector_results = await self._vector_index.search(query)
        vector_scores = {rid: score for rid, score in vector_results}

        query_tokens = self._content_tokens(query.query)
        # BM25 decides which records the lexical side puts forward, and how
        # strongly, as a proportion of the best match. The overlap count it
        # replaces treated every shared token as one, so a question with
        # three common words matched most of the Spine equally.
        keyword_scores = self._bm25_scores(query_tokens)
        if not keyword_scores and query_tokens:
            # No BM25 (nothing built, or not importable): the set index still
            # answers, at the overlap ratio it always used.
            counts: dict[str, float] = {}
            for token in query_tokens:
                for rid in self._keyword_index.get(token, ()):
                    counts[rid] = counts.get(rid, 0) + 1.0
            keyword_scores = {rid: min(c / len(query_tokens), 1.0) for rid, c in counts.items()}

        all_ids = set(vector_scores.keys()) | set(keyword_scores.keys())
        results = []
        for rid in all_ids:
            v_score = vector_scores.get(rid, 0.0)
            ratio = keyword_scores.get(rid, 0.0)

            # What this returns is **similarity**, and the citation floor is
            # calibrated against it — so keyword overlap must not inflate it.
            # `MemoryRankerImpl` already weights keyword match at 0.10 for
            # ordering, which is where that belongs; adding it here too both
            # double-counted it and made the number something other than the
            # cosine `MIN_RECALL_SCORE` was measured against.
            #
            # Keyword still decides *membership* of the candidate set, so a
            # record with no embedding is still findable — it just enters at
            # its own honest similarity rather than a borrowed one.
            combined = v_score if v_score > 0 else self.KEYWORD_ONLY_SCORE * ratio
            if combined > 0.05:
                results.append((rid, combined))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[: query.max_results]

    async def rebuild(self, records: list[MemoryRecord] | None = None) -> None:
        """Rebuild both the vector and keyword indexes from ``records``."""
        await self._vector_index.rebuild(records)
        if records is not None:
            self._keyword_index.clear()
            self._corpus.clear()
            for record in records:
                tokens = self._tokenize(record.content)
                for tag in record.tags:
                    tokens.add(tag.lower())
                for token in tokens:
                    self._keyword_index.setdefault(token, set()).add(record.id)
                self._corpus[record.id] = sorted(
                    self._content_tokens(record.content) | {t.lower() for t in record.tags}
                )
            self._bm25_invalidate()
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
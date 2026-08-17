from __future__ import annotations

import time
from typing import Any

from .contracts import (
    GLOBAL_SCOPE,
    MemoryIndex,
    MemoryQuery,
    MemoryRecord,
    MemoryResult,
    MemoryRetriever,
    MemoryStore,
    RetrievalStrategy,
)


def _in_scope(record: MemoryRecord, scope: str | None) -> bool:
    """Whether this fact may be recalled for a question asked in `scope`.

    `None` means unscoped — the Memory surface showing the user everything they
    have. Otherwise: this project's facts, plus global ones, and nothing else.
    Global is what is true about the *user* and applies to every job; another
    project's facts are about someone else's work.
    """
    if not scope:
        return True
    return getattr(record, "scope", GLOBAL_SCOPE) in (scope, GLOBAL_SCOPE)


class HybridMemoryRetriever(MemoryRetriever):
    """Retrieves memories using multiple strategies and merges results.

    HYBRID means *the hybrid index*, not "run two searches and keep whichever
    scored higher". It used to mean the latter, and because `_keyword_search`
    scored on raw whitespace overlap with no stopword filtering, the higher
    score was routinely the wrong one: "What is the capital of France?" overlaps
    a Harbour Lane project brief on `is`, `the` and `of` — three of six terms,
    a keyword score of 0.5 — while the true cosine similarity was 0.226. The
    max won, so an unrelated document was cited with a number that looked like
    a similarity and was not.

    Found by `test_recall_eval.py` on the day it was written. Recall is the
    moat and it had never been measured end to end; this is what was under it.
    """

    def __init__(self, store: MemoryStore, index: MemoryIndex | None = None):
        self._store = store
        self._index = index
        self._stats = {"total_retrievals": 0, "total_latency_ms": 0.0}

    async def retrieve(self, query: MemoryQuery) -> list[MemoryResult]:
        start = time.time()
        self._stats["total_retrievals"] += 1

        all_candidates: dict[str, tuple[MemoryRecord, float, str]] = {}

        if query.strategy in (RetrievalStrategy.VECTOR_SIMILARITY, RetrievalStrategy.HYBRID):
            if self._index:
                vector_results = await self._vector_search(query)
                for record, score in vector_results:
                    if record.id not in all_candidates or score > all_candidates[record.id][1]:
                        all_candidates[record.id] = (record, score, "vector")

        # Keyword search is the *fallback*, not a peer. It runs when asked for
        # explicitly, or when the semantic path produced nothing — an empty
        # index on boot, a record stored without an embedding, or Ollama being
        # unreachable. Running it beside a working vector search and taking the
        # maximum is what let stopword overlap outrank meaning.
        semantic_worked = bool(all_candidates)
        wants_keyword = query.strategy is RetrievalStrategy.KEYWORD_MATCH or (
            query.strategy is RetrievalStrategy.HYBRID and not semantic_worked
        )
        if wants_keyword:
            keyword_results = await self._keyword_search(query)
            for record, score in keyword_results:
                if record.id not in all_candidates or score > all_candidates[record.id][1]:
                    all_candidates[record.id] = (record, score, "keyword")

        if query.strategy == RetrievalStrategy.TEMPORAL:
            temporal_results = await self._temporal_search(query)
            for record, score in temporal_results:
                if record.id not in all_candidates or score > all_candidates[record.id][1]:
                    all_candidates[record.id] = (record, score, "temporal")

        # Rule 7i's boundary, enforced here rather than per strategy.
        #
        # The store's `query` filters by scope, but `_vector_search` does not go
        # through it — the index knows nothing about scope and returns ids,
        # which are then fetched individually. So a semantic hit on another
        # project's fact walked straight past the filter, and only the keyword
        # path was ever scoped. A privacy boundary with one enforcement point
        # per code path is a boundary with a hole in it per code path.
        # Domain narrowing rides with the scope check, at the same single
        # point, for the same reason. `only_ids` is `None` when the question
        # was not asked inside a domain; an **empty set is a real answer** —
        # a domain holding no sources yet can answer from nothing — so the test
        # is `is not None` and never truthiness. Treating empty as "no filter"
        # would silently widen a scope the user chose, which is the failure
        # mode this whole boundary exists to prevent.
        allowed = query.only_ids
        candidates = [
            (record, score, reason)
            for record, score, reason in all_candidates.values()
            if _in_scope(record, query.scope)
            and (allowed is None or record.id in allowed)
        ]

        results = [
            MemoryResult(record=record, score=score, match_reason=reason, rank=0)
            for record, score, reason in candidates
        ]

        latency = (time.time() - start) * 1000
        self._stats["total_latency_ms"] += latency
        print(f"[MemoryRetriever] Retrieved {len(results)} candidates in {latency:.1f}ms")
        return results

    async def _keyword_search(self, query: MemoryQuery) -> list[tuple[MemoryRecord, float]]:
        """Overlap on words that carry meaning.

        Two things were wrong here and both inflated scores. It split on
        whitespace, so `France?` and `France` were different terms while
        `is`, `the` and `of` were perfectly good ones — and stopwords match
        every document, so any question with a few function words scored
        roughly `stopwords / question length` against the entire Spine.

        Tokenisation is shared with `HybridMemoryIndex` rather than
        reimplemented. Two hand-maintained copies of the same rule is how this
        file and that one came to disagree in the first place.
        """
        from .index import content_tokens

        records = await self._store.query(query)

        # An empty query is not a question, it is a listing: "everything in
        # this session", already narrowed by the store's own filters. There is
        # nothing to rank and nothing to be wrong about, so the records come
        # back as they are.
        if not query.query or not query.query.strip():
            return [(record, 0.5) for record in records][: query.max_results]

        query_terms = content_tokens(query.query)
        if not query_terms:
            # A real question made entirely of stopwords — "what is that?".
            # Unrankable, and returning the whole store at a confident 0.5
            # would attach citations to an answer that used none of them.
            return []

        results = []
        for record in records:
            content_terms = content_tokens(record.content)
            overlap = len(query_terms & content_terms)
            if overlap > 0:
                score = overlap / len(query_terms)
                if record.tags:
                    tag_overlap = len(query_terms & {t.lower() for t in record.tags})
                    score += tag_overlap * 0.1
                results.append((record, min(score, 1.0)))
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
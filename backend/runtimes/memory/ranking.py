from __future__ import annotations

import time
import math
from typing import Any

from .contracts import MemoryQuery, MemoryRanker, MemoryResult, Origin


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

    #: How much a Zaram-generated fact is pushed down the ordering.
    #:
    #: Rule 7b indexes generated artifacts by default, and says the protection
    #: against Zaram citing its own restatements is *origin tagging, not
    #: exclusion* — "recall deprioritises generated content where a user source
    #: says the same thing".
    #:
    #: A penalty on the ranking score is exactly that: a user document and
    #: Zaram's summary of it are similarly relevant, and the user document
    #: should come first. Deliberately applied to `score` and never to
    #: `relevance` — a generated fact that genuinely answers the question is
    #: still relevant, and demoting it below the citation floor would be
    #: exclusion wearing a different hat.
    GENERATED_PENALTY = 0.15

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

            if getattr(record, "origin", None) is Origin.GENERATED:
                combined -= self.GENERATED_PENALTY

            result.score = max(combined, 0.0)

        # Selection by relevance; ordering by the blend. The two cuts are not
        # the same question and merging them loses documents outright.
        #
        # Measured at 1,000 documents: the single most relevant document in the
        # corpus for "How should I write to clients?" — cosine 0.599, the
        # highest score anywhere in the eval — came back at **rank 43**, behind
        # 42 documents it out-scores on relevance. Truncating to `max_results`
        # by blend therefore discarded it before any caller could see it, and no
        # shortlist width fixes that: the engine asks for 25.
        #
        # The arithmetic makes it inevitable rather than unlucky. Relevance
        # spans roughly 0.30–0.60, so at weight 0.35 the semantic term swings
        # about 0.10 — while importance, recency, access, keyword and session
        # together swing about 0.55. Non-relevance signals outweigh relevance
        # by roughly four and a half to one, so on a corpus of near-identical
        # invoices the blend decides almost everything and similarity decides
        # almost nothing.
        #
        # This is the same lesson this file already learned one step earlier.
        # The citation floor was moved off `score` and onto `relevance` because
        # ordering and permission are different questions. *Membership of the
        # shortlist* is a third question, and it belongs with relevance too:
        # rank on whatever is useful, but decide what is in the running on
        # similarity alone.
        selected = sorted(
            results,
            key=lambda r: r.relevance if r.relevance is not None else r.score,
            reverse=True,
        )[: query.max_results]

        # Within the shortlist the blend is exactly right, and is what it was
        # designed for: a pinned, recent, frequently-used fact should be shown
        # before an equally relevant one that is none of those things.
        selected.sort(key=lambda r: r.score, reverse=True)
        for i, r in enumerate(selected):
            r.rank = i + 1

        latency = (time.time() - start) * 1000
        self._stats["total_latency_ms"] += latency
        return selected

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
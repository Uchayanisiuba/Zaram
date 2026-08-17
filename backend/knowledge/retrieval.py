# backend/knowledge/retrieval.py
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any
from .protocol import KnowledgeChunk, KnowledgeContext, KnowledgeRequest, KnowledgeResult
from .vector_store import _cosine_similarity


@dataclass
class RetrievalResult:
    chunks: list[KnowledgeChunk] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    strategy: str = "top_k"
    query_tokens: int = 0


class SemanticRetrieval:
    """Top K, MMR, and context window optimization.

    **There was a `_hybrid` here and it was deleted, 18 August 2026.** It read
    `vector * 0.7 + bm25 * 0.3` and then truncated the candidate list on that
    blend — selecting on a ranking score, which is the membership-versus-
    ordering error this codebase has paid for three times. It was flagged for
    review on the suspicion that it was live.

    It was not. The function was *reached*, so it looked live, but its first
    statement was `if not objects: return vector_result` and the only
    production caller — `KnowledgeRuntime.retrieve`, one level up — never
    passed `objects`. So the blend never executed, no test covered it, and the
    "hybrid" strategy has always been pure vector search. Reachable function,
    unreachable defect.

    It is deleted rather than corrected because `CLAUDE.md` has already decided
    what replaces it: when lexical retrieval is genuinely built, the two
    rankers fuse by **reciprocal rank** and not by a weighted sum, precisely so
    there is no blended magnitude that *could* be compared against a threshold.
    Repairing the arithmetic here would have preserved the shape the contract
    rejected. The result honestly reports `top_k`, which is what it does.
    """

    def __init__(self, vector_store: Any, embedding_runtime: Any):
        self._store = vector_store
        self._embed = embedding_runtime

    def retrieve(self, request: KnowledgeRequest) -> RetrievalResult:
        # "hybrid" remains the default request value and resolves here to
        # vector search, which is what it has always done. Left as the default
        # rather than renamed: the string reaches this from stored requests,
        # and the result reports `top_k`, so nothing tells the user otherwise.
        if (request.strategy or "hybrid") == "mmr":
            return self._mmr(request)
        return self._top_k(request)

    def _top_k(self, request: KnowledgeRequest) -> RetrievalResult:
        query_vector = self._embed.embed([request.query])[0]
        raw = self._store.search(query_vector, top_k=request.max_results)
        chunks, scores = [], []
        for chunk, score in raw:
            chunks.append(chunk)
            scores.append(score)
        return RetrievalResult(chunks=chunks, scores=scores, strategy="top_k", query_tokens=len(request.query.split()))

    def _mmr(self, request: KnowledgeRequest, lambda_param: float = 0.5) -> RetrievalResult:
        query_vector = self._embed.embed([request.query])[0]
        raw = self._store.search(query_vector, top_k=min(request.max_results * 3, 50))
        if not raw:
            return RetrievalResult(strategy="mmr")
        selected: list[KnowledgeChunk] = []
        selected_scores: list[float] = []
        candidates = list(raw)
        while len(selected) < request.max_results and candidates:
            best_idx = 0
            best_score = -1.0
            for idx, (chunk, sim) in enumerate(candidates):
                redundancy = 0.0
                if selected:
                    redundancy = max(
                        _cosine_similarity(chunk.embedding or [], sel.embedding or [])
                        for sel in selected
                    )
                mmr_score = lambda_param * sim - (1 - lambda_param) * redundancy
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx
            chunk, sim = candidates.pop(best_idx)
            selected.append(chunk)
            selected_scores.append(best_score)
        return RetrievalResult(chunks=selected, scores=selected_scores, strategy="mmr", query_tokens=len(request.query.split()))

    def optimize_context_window(self, chunks: list[KnowledgeChunk], max_tokens: int = 4096) -> KnowledgeContext:
        total = 0
        selected: list[KnowledgeChunk] = []
        for chunk in chunks:
            tok = chunk.token_count or max(1, len(chunk.text.split()))
            if total + tok > max_tokens:
                break
            selected.append(chunk)
            total += tok
        return KnowledgeContext(chunks=selected, total_tokens=total, max_tokens=max_tokens, strategy="top_k")

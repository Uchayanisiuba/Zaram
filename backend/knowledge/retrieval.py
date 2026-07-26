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
    """Top K, hybrid search, similarity, MMR, and context window optimization."""

    def __init__(self, vector_store: Any, embedding_runtime: Any):
        self._store = vector_store
        self._embed = embedding_runtime

    def retrieve(self, request: KnowledgeRequest, objects: list[Any] | None = None) -> RetrievalResult:
        strategy = request.strategy or "hybrid"
        if strategy == "mmr":
            return self._mmr(request)
        if strategy == "hybrid":
            return self._hybrid(request, objects)
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

    def _hybrid(self, request: KnowledgeRequest, objects: list[Any] | None = None) -> RetrievalResult:
        vector_result = self._top_k(request)
        if not objects:
            return vector_result
        scored: dict[str, tuple[KnowledgeChunk, float]] = {}
        for chunk, score in zip(vector_result.chunks, vector_result.scores):
            scored[chunk.id] = (chunk, score * 0.7)
        for obj in objects:
            text = getattr(obj, "content", "") or getattr(obj, "snippet", "")
            if not text:
                continue
            query_lower = request.query.lower()
            text_lower = text.lower()
            overlap = sum(1 for term in query_lower.split() if term in text_lower)
            if overlap > 0:
                bm25 = overlap / (len(query_lower.split()) + 1.0)
                key = getattr(obj, "id", text)
                if key in scored:
                    prev = scored[key][1]
                    scored[key] = (scored[key][0], prev + bm25 * 0.3)
                else:
                    chunk_text = text[: self._estimate_chunk_size()]
                    chunk = KnowledgeChunk(text=chunk_text, token_count=len(chunk_text.split()))
                    scored[key] = (chunk, bm25 * 0.3)
        ranked = sorted(scored.values(), key=lambda x: x[1], reverse=True)
        chunks = [r[0] for r in ranked[: request.max_results]]
        scores = [r[1] for r in ranked[: request.max_results]]
        return RetrievalResult(chunks=chunks, scores=scores, strategy="hybrid", query_tokens=len(request.query.split()))

    def _estimate_chunk_size(self) -> int:
        return 512 * 4

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

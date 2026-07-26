# backend/knowledge/ranking.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from .protocol import KnowledgeResult, RankedResult, ConfidenceScore, FreshnessScore, Citation


@dataclass
class RankingEngine:
    """Rank knowledge using similarity, recency, authority, freshness, citations, confidence."""

    weights: dict[str, float] = field(default_factory=lambda: {
        "similarity": 0.30,
        "recency": 0.15,
        "authority": 0.15,
        "freshness": 0.15,
        "citation": 0.10,
        "confidence": 0.15,
    })

    def rank(self, results: list[KnowledgeResult], scores: list[float] | None = None, now: float | None = None) -> list[RankedResult]:
        import time
        now = now or time.time()
        ranked: list[RankedResult] = []
        for idx, result in enumerate(results):
            sim = scores[idx] if scores and idx < len(scores) else 0.0
            recency = self._recency(result, now)
            authority = self._authority(result)
            freshness = self._freshness(result, now)
            citation = self._citation(result)
            confidence = self._confidence(result)
            rank_score = (
                self.weights["similarity"] * sim
                + self.weights["recency"] * recency
                + self.weights["authority"] * authority
                + self.weights["freshness"] * freshness
                + self.weights["citation"] * citation
                + self.weights["confidence"] * confidence
            )
            ranked.append(RankedResult(
                result=result,
                rank_score=rank_score,
                similarity=sim,
                recency=recency,
                authority=authority,
                freshness_score=freshness,
                citation_score=citation,
                confidence_score=confidence,
            ))
        ranked.sort(key=lambda x: x.rank_score, reverse=True)
        return ranked

    def _recency(self, result: KnowledgeResult, now: float) -> float:
        ts = result.retrieved_at or 0
        if ts <= 0:
            return 0.5
        age_days = (now - ts) / 86400.0
        return max(0.0, 1.0 - (age_days / 30.0))

    def _authority(self, result: KnowledgeResult) -> float:
        priority_map = {
            "memory": 0.9,
            "wikipedia": 0.85,
            "github": 0.8,
            "duckduckgo": 0.7,
            "rss": 0.75,
            "project": 0.7,
            "vector": 0.6,
        }
        return priority_map.get(result.provider, 0.5) * min(1.0, result.confidence + 0.2)

    def _freshness(self, result: KnowledgeResult, now: float) -> float:
        meta = result.metadata or {}
        created = meta.get("created_at", result.retrieved_at)
        if created <= 0:
            return 0.5
        age_days = (now - created) / 86400.0
        return max(0.0, 2 ** (-age_days / 7.0))

    def _citation(self, result: KnowledgeResult) -> float:
        score = 0.0
        if result.url:
            score += 0.3
        if result.published:
            score += 0.3
        if result.metadata.get("author"):
            score += 0.2
        if result.metadata.get("document"):
            score += 0.2
        return min(1.0, score)

    def _confidence(self, result: KnowledgeResult) -> float:
        return max(0.0, min(1.0, result.confidence))

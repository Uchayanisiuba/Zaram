# backend/knowledge/authority.py
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any
from .protocol import AuthorityScore, KnowledgeResult


@dataclass
class AuthorityRegistry:
    """Centralized authority registry for knowledge sources."""

    _scores: dict[str, AuthorityScore] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    _DEFAULT_SCORES: dict[str, float] = field(default_factory=lambda: {
        "nature": 0.99,
        "science": 0.95,
        "government": 0.98,
        "edu": 0.95,
        "wikipedia": 0.80,
        "github": 0.75,
        "stackoverflow": 0.72,
        "stack exchange": 0.72,
        "reddit": 0.40,
        "medium": 0.50,
        "blog": 0.20,
        "unknown": 0.10,
    })

    def __post_init__(self):
        for source, score in self._DEFAULT_SCORES.items():
            self.register(source, score, category="default")

    def register(self, source_id: str, score: float, category: str = "custom", metadata: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._scores[source_id.lower()] = AuthorityScore(
                source_id=source_id.lower(),
                score=max(0.0, min(1.0, score)),
                category=category,
                metadata=metadata or {},
            )

    def get_score(self, source_id: str) -> float:
        with self._lock:
            entry = self._scores.get(source_id.lower())
            if entry:
                return entry.score
            for key, entry in self._scores.items():
                if key in source_id.lower() or source_id.lower() in key:
                    return entry.score
        return 0.5

    def get_authority(self, result: KnowledgeResult) -> float:
        provider = result.provider or ""
        url = result.url or ""
        score = self.get_score(provider)
        if score == 0.5 and url:
            score = self.get_score_from_url(url)
        return max(score, result.authority_score)

    def get_score_from_url(self, url: str) -> float:
        url_lower = url.lower()
        for source, score in self._DEFAULT_SCORES.items():
            if source in url_lower:
                return score
        if url_lower.startswith("https://"):
            return 0.6
        if url_lower.startswith("http://"):
            return 0.4
        return 0.3

    def apply_to_result(self, result: KnowledgeResult) -> KnowledgeResult:
        score = self.get_authority(result)
        return KnowledgeResult(
            title=result.title,
            url=result.url,
            snippet=result.snippet,
            provider=result.provider,
            published=result.published,
            confidence=result.confidence,
            score=result.score,
            type=result.type,
            knowledge_type=result.knowledge_type,
            authority_score=score,
            metadata={**result.metadata, "authority_score": score},
            retrieved_at=result.retrieved_at,
        )

    def stats(self) -> dict[str, Any]:
        with self._lock:
            categories: dict[str, int] = {}
            for entry in self._scores.values():
                categories[entry.category] = categories.get(entry.category, 0) + 1
            return {
                "total_sources": len(self._scores),
                "categories": categories,
                "avg_score": sum(e.score for e in self._scores.values()) / max(len(self._scores), 1),
            }

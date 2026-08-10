# backend/runtime/discovery/ranking.py
from __future__ import annotations

import threading
from typing import Any

from .contracts import AuthorityLevel, ProviderScore


class AdaptiveRanker:
    """Self-optimizing provider ranking based on historical performance."""

    def __init__(self) -> None:
        self._scores: dict[str, ProviderScore] = {}
        self._lock = threading.Lock()

    def record_result(self, provider_id: str, success: bool, latency_ms: float, verification_score: float) -> None:
        with self._lock:
            current = self._scores.get(provider_id)
            if current is None:
                current = ProviderScore(
                    provider_id=provider_id,
                    score=0.5,
                    authority=AuthorityLevel.UNKNOWN,
                    latency_ms=latency_ms,
                    cost=0.0,
                    success_rate=1.0 if success else 0.0,
                    confidence=0.8,
                    availability=1.0 if success else 0.0,
                )
            alpha = 0.3
            updated_success = current.success_rate * (1 - alpha) + (1.0 if success else 0.0) * alpha
            updated_latency = current.latency_ms * (1 - alpha) + latency_ms * alpha
            updated_confidence = current.confidence * (1 - alpha) + verification_score * alpha
            availability = current.availability * (1 - alpha) + (1.0 if success else 0.0) * alpha
            score = (
                0.4 * updated_success
                + 0.3 * (1.0 / max(updated_latency, 1.0))
                + 0.2 * updated_confidence
                + 0.1 * availability
            )
            self._scores[provider_id] = ProviderScore(
                provider_id=provider_id,
                score=score,
                authority=current.authority,
                latency_ms=updated_latency,
                cost=current.cost,
                success_rate=updated_success,
                confidence=updated_confidence,
                availability=availability,
            )

    def get_score(self, provider_id: str) -> ProviderScore:
        with self._lock:
            return self._scores.get(provider_id, ProviderScore(
                provider_id=provider_id,
                score=0.5,
                authority=AuthorityLevel.UNKNOWN,
                latency_ms=0.0,
                cost=0.0,
                success_rate=0.5,
                confidence=0.5,
                availability=0.5,
            ))

    def rank_providers(self, provider_ids: list[str]) -> list[str]:
        with self._lock:
            return sorted(provider_ids, key=lambda pid: -self._scores.get(pid, ProviderScore(provider_id=pid, score=0.5, authority=AuthorityLevel.UNKNOWN, latency_ms=0.0, cost=0.0, success_rate=0.5, confidence=0.5, availability=0.5)).score)

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                pid: {
                    "score": s.score,
                    "success_rate": s.success_rate,
                    "latency_ms": s.latency_ms,
                    "confidence": s.confidence,
                    "availability": s.availability,
                }
                for pid, s in self._scores.items()
            }

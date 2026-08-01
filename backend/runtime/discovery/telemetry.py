# backend/runtime/discovery/telemetry.py
from __future__ import annotations

import threading
from typing import Any


class DiscoveryTelemetry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_searches = 0
        self._cache_hits = 0
        self._successful_searches = 0
        self._failed_searches = 0
        self._total_retries = 0
        self._total_latency_ms = 0.0
        self._provider_latency: dict[str, float] = {}
        self._provider_requests: dict[str, int] = {}
        self._provider_failures: dict[str, int] = {}
        self._provider_retries: dict[str, int] = {}
        self._verification_scores: list[float] = []
        self._planner_decisions: dict[str, int] = {}
        self._authority_distribution: dict[str, int] = {}
        self._execution_strategies: dict[str, int] = {}

    def record_search(
        self,
        latency_ms: float,
        success: bool,
        provider: str,
        cached: bool,
        retries: int = 0,
        verification_score: float | None = None,
        planner_decision: str | None = None,
        authority: str | None = None,
        strategy: str | None = None,
    ) -> None:
        with self._lock:
            self._total_searches += 1
            self._total_latency_ms += latency_ms
            if cached:
                self._cache_hits += 1
            if success:
                self._successful_searches += 1
            else:
                self._failed_searches += 1
            self._total_retries += retries
            self._provider_requests[provider] = self._provider_requests.get(provider, 0) + 1
            self._provider_latency[provider] = self._provider_latency.get(provider, 0.0) + latency_ms
            if not success:
                self._provider_failures[provider] = self._provider_failures.get(provider, 0) + 1
            if retries > 0:
                self._provider_retries[provider] = self._provider_retries.get(provider, 0) + retries
            if verification_score is not None:
                self._verification_scores.append(verification_score)
            if planner_decision is not None:
                self._planner_decisions[planner_decision] = self._planner_decisions.get(planner_decision, 0) + 1
            if authority is not None:
                self._authority_distribution[authority] = self._authority_distribution.get(authority, 0) + 1
            if strategy is not None:
                self._execution_strategies[strategy] = self._execution_strategies.get(strategy, 0) + 1

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            verification_rate = len(self._verification_scores) / max(self._total_searches, 1)
            avg_verification = sum(self._verification_scores) / max(len(self._verification_scores), 1)
            return {
                "total_searches": self._total_searches,
                "cache_hits": self._cache_hits,
                "successful_searches": self._successful_searches,
                "failed_searches": self._failed_searches,
                "total_retries": self._total_retries,
                "avg_latency_ms": self._total_latency_ms / max(self._total_searches, 1),
                "cache_hit_ratio": self._cache_hits / max(self._total_searches, 1),
                "success_rate": self._successful_searches / max(self._total_searches, 1),
                "provider_latency": dict(self._provider_latency),
                "provider_requests": dict(self._provider_requests),
                "provider_failures": dict(self._provider_failures),
                "provider_retries": dict(self._provider_retries),
                "verification_rate": verification_rate,
                "avg_verification_score": avg_verification,
                "planner_decisions": dict(self._planner_decisions),
                "authority_distribution": dict(self._authority_distribution),
                "execution_strategies": dict(self._execution_strategies),
            }

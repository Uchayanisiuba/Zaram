# backend/runtime/discovery/latency.py
from __future__ import annotations

from typing import Any

from .contracts import DiscoveryProvider, ExecutionStrategy, ProviderCapability


class LatencyAwareExecutor:
    """Chooses execution paths based on latency and cost requirements."""

    def choose_strategy(
        self,
        request: Any,
        providers: list[DiscoveryProvider],
    ) -> ExecutionStrategy:
        if request.strategy:
            return request.strategy
        budget = request.latency_budget_ms
        if budget > 0 and budget < 1000:
            return ExecutionStrategy.FAST
        if budget > 5000:
            return ExecutionStrategy.QUALITY
        return ExecutionStrategy.BALANCED

    def estimate_execution_cost(self, plan: Any) -> float:
        total = 0.0
        for step in plan.steps:
            for provider in plan.authority_ranking:
                if provider == step.provider_id:
                    total += 0.01
        return total

    def select_fast_path(self, candidates: list[ProviderCapability], max_latency_ms: float) -> list[ProviderCapability]:
        return [c for c in candidates if c.avg_latency_ms <= max_latency_ms]

    def select_quality_path(self, candidates: list[ProviderCapability], min_authority: Any) -> list[ProviderCapability]:
        from .authority import AuthorityRegistry
        registry = AuthorityRegistry()
        return [c for c in candidates if registry.get_authority_score(c.authority) >= registry._authority_to_score(min_authority)]

    def select_balanced_path(self, candidates: list[ProviderCapability]) -> list[ProviderCapability]:
        return sorted(candidates, key=lambda c: (c.avg_latency_ms, -c.success_rate))[:3]

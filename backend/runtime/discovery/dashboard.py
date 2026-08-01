# backend/runtime/discovery/dashboard.py
from __future__ import annotations

from typing import Any

from .contracts import DiscoveryDashboard


class DiscoveryDashboardExporter:
    """Exposes discovery runtime metrics for dashboard consumption."""

    def __init__(self, telemetry: Any, registry: Any, ranker: Any) -> None:
        self._telemetry = telemetry
        self._registry = registry
        self._ranker = ranker

    def export(self, current_searches: int = 0, background_searches: int = 0) -> DiscoveryDashboard:
        stats = self._telemetry.get_stats()
        providers = self._registry.list()
        healthy = sum(1 for p in providers if p.is_available())

        authority_dist: dict[str, int] = {}
        strategy_dist: dict[str, int] = {}
        for p in providers:
            try:
                level = p.get_authority_level()
                authority_dist[level.value] = authority_dist.get(level.value, 0) + 1
            except Exception:
                authority_dist["unknown"] = authority_dist.get("unknown", 0) + 1
            strategy_dist[p.get_provider_type()] = strategy_dist.get(p.get_provider_type(), 0) + 1

        planner_decisions = stats.get("planner_decisions", {})

        return DiscoveryDashboard(
            registered_providers=len(providers),
            healthy_providers=healthy,
            avg_latency_ms=stats.get("avg_latency_ms", 0.0),
            success_rate=stats.get("success_rate", 0.0),
            failure_rate=stats.get("failed_searches", 0) / max(stats.get("total_searches", 1), 1),
            cache_hit_ratio=stats.get("cache_hit_ratio", 0.0),
            verification_rate=stats.get("verification_rate", 0.0),
            planner_decisions=planner_decisions,
            current_searches=current_searches,
            background_searches=background_searches,
            authority_distribution=authority_dist,
            execution_strategy_distribution=strategy_dist,
        )

# backend/runtime/discovery/search_planner.py
from __future__ import annotations

from typing import Any

from .contracts import (
    AuthorityLevel,
    Capability,
    DiscoveryPlan,
    DiscoveryProvider,
    ExecutionStep,
    ExecutionStrategy,
    QueryAnalysis,
    QueryRewrite,
    RetrievalMode,
    SearchDifficulty,
)


class SearchPlanner:
    """Converts query analysis into an executable discovery plan."""

    def __init__(self, authority_registry: Any = None) -> None:
        self._authority_registry = authority_registry

    def plan(
        self,
        analysis: QueryAnalysis,
        providers: list[DiscoveryProvider],
        mode: RetrievalMode = RetrievalMode.PARALLEL,
        strategy: ExecutionStrategy = ExecutionStrategy.BALANCED,
    ) -> DiscoveryPlan:
        ranked = self._rank_providers(analysis, providers, strategy)
        steps = self._build_steps(analysis, ranked, strategy)
        fallback_chain = [step.provider_id for step in steps if step.cache_policy is False]
        authority_ranking = [p.get_provider_id() for p in ranked]
        estimated_latency = sum(step.timeout_ms for step in steps)
        estimated_cost = sum(p.estimated_cost() for p in ranked)

        require_verification = analysis.search_difficulty != SearchDifficulty.EASY and len(steps) > 1

        return DiscoveryPlan(
            query=analysis.raw_query,
            analysis=analysis,
            steps=steps,
            strategy=strategy,
            fallback_chain=fallback_chain,
            authority_ranking=authority_ranking,
            estimated_total_latency_ms=estimated_latency,
            estimated_total_cost=estimated_cost,
            require_verification=require_verification,
        )

    def _rank_providers(
        self,
        analysis: QueryAnalysis,
        providers: list[DiscoveryProvider],
        strategy: ExecutionStrategy,
    ) -> list[DiscoveryProvider]:
        scored: list[tuple[float, DiscoveryProvider]] = []
        for p in providers:
            score = self._score_provider(p, analysis, strategy)
            scored.append((score, p))
        scored.sort(key=lambda x: (-x[0], x[1].estimated_latency_ms()))
        return [p for _, p in scored]

    def _score_provider(
        self,
        provider: DiscoveryProvider,
        analysis: QueryAnalysis,
        strategy: ExecutionStrategy,
    ) -> float:
        capability_match = self._capability_overlap(provider.get_capabilities(), analysis.expected_capabilities)
        authority_score = self._authority_score(provider.get_authority_level(), analysis.authority_requirement)
        latency_score = self._latency_score(provider.estimated_latency_ms(), analysis.latency_budget_ms)
        confidence_score = provider.estimated_confidence()
        availability_score = 1.0 if provider.is_available() else 0.0

        if strategy == ExecutionStrategy.FAST:
            weights = {"latency": 0.5, "availability": 0.3, "capability": 0.1, "authority": 0.05, "confidence": 0.05}
        elif strategy == ExecutionStrategy.QUALITY:
            weights = {"authority": 0.4, "confidence": 0.3, "capability": 0.2, "latency": 0.05, "availability": 0.05}
        else:
            weights = {"capability": 0.3, "authority": 0.25, "latency": 0.2, "confidence": 0.15, "availability": 0.1}

        score = (
            weights["capability"] * capability_match
            + weights["authority"] * authority_score
            + weights["latency"] * latency_score
            + weights["confidence"] * confidence_score
            + weights["availability"] * availability_score
        )
        return score

    def _capability_overlap(self, provider_caps: list[Capability], expected: list[Capability]) -> float:
        if not expected:
            return 1.0
        if not provider_caps:
            return 0.0
        matches = len(set(provider_caps) & set(expected))
        return matches / len(expected)

    def _authority_score(self, provider_authority: Any, required: Any) -> float:
        if required == AuthorityLevel.UNKNOWN:
            return 1.0
        hierarchy = [
            AuthorityLevel.GOVERNMENT,
            AuthorityLevel.ACADEMIC,
            AuthorityLevel.OFFICIAL_DOCS,
            AuthorityLevel.WIKIPEDIA,
            AuthorityLevel.GITHUB,
            AuthorityLevel.COMMUNITY,
            AuthorityLevel.BLOG,
            AuthorityLevel.UNKNOWN,
        ]
        try:
            req_idx = hierarchy.index(required)
            prov_idx = hierarchy.index(provider_authority)
            return max(0.0, 1.0 - (prov_idx - req_idx) * 0.2)
        except ValueError:
            return 0.5

    def _latency_score(self, provider_latency: float, budget: float) -> float:
        if budget <= 0:
            return 1.0 / max(provider_latency, 1.0)
        return max(0.0, 1.0 - provider_latency / budget)

    def _build_steps(
        self,
        analysis: QueryAnalysis,
        providers: list[DiscoveryProvider],
        strategy: ExecutionStrategy,
    ) -> list[ExecutionStep]:
        steps: list[ExecutionStep] = []
        timeout_map = {
            ExecutionStrategy.FAST: 1000.0,
            ExecutionStrategy.BALANCED: 3000.0,
            ExecutionStrategy.QUALITY: 8000.0,
        }
        base_timeout = timeout_map.get(strategy, 3000.0)

        for idx, provider in enumerate(providers):
            rewrite = self._rewrite_for_provider(analysis.raw_query, provider, analysis.expected_capabilities)
            steps.append(ExecutionStep(
                provider_id=provider.get_provider_id(),
                capability=analysis.expected_capabilities[0] if analysis.expected_capabilities else Capability.WEB,
                timeout_ms=base_timeout + idx * 500,
                retries=2 if analysis.search_difficulty == SearchDifficulty.HARD else 1,
                cache_policy=(idx == 0),
                query_rewrite=rewrite,
                streaming=(analysis.search_difficulty == SearchDifficulty.HARD),
            ))
        return steps

    def _rewrite_for_provider(
        self,
        query: str,
        provider: DiscoveryProvider,
        capabilities: list[Capability],
    ) -> QueryRewrite | None:
        if provider.get_provider_id() == "github":
            rewritten = f"{query} repository"
        elif provider.get_provider_id() == "wikipedia":
            rewritten = query
        elif provider.get_provider_id() == "duckduckgo":
            rewritten = f"{query} latest"
        elif provider.get_provider_id() == "rss":
            rewritten = f"{query} feed"
        else:
            rewritten = query
        capability = capabilities[0] if capabilities else Capability.WEB
        return QueryRewrite(
            original_query=query,
            rewritten_query=rewritten,
            provider_id=provider.get_provider_id(),
            capability=capability,
        )

# backend/runtime/discovery/runtime.py
from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from typing import Any

from .cache import DiscoveryCache
from .capability_router import CapabilityRouter
from .contracts import (
    DiscoveryContext,
    DiscoveryMetadata,
    DiscoveryProvider,
    DiscoveryRequest,
    DiscoveryResult,
    FreshnessLevel,
    RetrievalMode,
)
from .dashboard import DiscoveryDashboard, DiscoveryDashboardExporter
from .extractor import merge_results
from .freshness import estimate_freshness
from .offline import OfflineDiscovery
from .query_analyzer import QueryAnalyzer
from .ranking import AdaptiveRanker
from .registry import ProviderRegistry
from .retry import RetryConfig, retry_with_backoff
from .sandbox import ProviderSandbox
from .search_planner import SearchPlanner
from .selector import select_providers
from .streaming import StreamingDiscovery
from .telemetry import DiscoveryTelemetry
from .verification import VerificationEngine


class DiscoveryRuntime:
    """Core discovery runtime that orchestrates providers."""

    def __init__(
        self,
        cache: DiscoveryCache | None = None,
        default_cache_ttl: int = 900,
        max_workers: int = 8,
        knowledge_runtime: Any = None,
    ) -> None:
        self._registry = ProviderRegistry()
        self._cache = cache or DiscoveryCache()
        self._default_cache_ttl = default_cache_ttl
        self._max_workers = max_workers
        self._telemetry = DiscoveryTelemetry()
        self._started_at = time.time()

        self._query_analyzer = QueryAnalyzer()
        self._search_planner = SearchPlanner()
        self._capability_router = CapabilityRouter()
        self._authority_registry = None
        self._adaptive_ranker = AdaptiveRanker()
        self._sandbox = ProviderSandbox()
        self._streaming = StreamingDiscovery()
        self._offline = OfflineDiscovery(self._cache, knowledge_runtime)
        self._verification_engine = VerificationEngine()
        self._dashboard_exporter = DiscoveryDashboardExporter(self._telemetry, self._registry, self._adaptive_ranker)
        self._knowledge_runtime = knowledge_runtime

    def register_provider(self, provider: DiscoveryProvider) -> None:
        self._registry.register(provider)
        with suppress(Exception):
            self._capability_router.register_provider(provider)
        with suppress(Exception):
            from .authority import AuthorityRegistry
            if self._authority_registry is None:
                self._authority_registry = AuthorityRegistry()
            self._authority_registry.register_provider(provider)

    def remove_provider(self, provider_id: str) -> None:
        self._registry.remove(provider_id)
        with suppress(Exception):
            self._capability_router.unregister_provider(provider_id)
        with suppress(Exception):
            if self._authority_registry:
                self._authority_registry.unregister_provider(provider_id)

    def get_provider(self, provider_id: str) -> DiscoveryProvider | None:
        return self._registry.get(provider_id)

    def list_providers(self) -> list[dict[str, Any]]:
        providers = []
        for p in self._registry.list():
            try:
                health = p.health_check()
            except Exception:
                health = {}
            providers.append({
                "id": p.get_provider_id(),
                "type": p.get_provider_type(),
                "available": p.is_available(),
                "priority": p.priority(),
                "cache_ttl": p.cache_ttl(),
                "capabilities": [c.value for c in p.get_capabilities()],
                "authority": p.get_authority_level().value,
                "estimated_latency_ms": p.estimated_latency_ms(),
                "estimated_cost": p.estimated_cost(),
                "estimated_confidence": p.estimated_confidence(),
                "health": health,
            })
        return providers

    def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "providers": self._registry.health_check(),
            "cache_size": self._cache.size,
        }

    def get_stats(self) -> dict[str, Any]:
        return self._telemetry.get_stats()

    def get_dashboard(self, current_searches: int = 0, background_searches: int = 0) -> DiscoveryDashboard:
        return self._dashboard_exporter.export(current_searches, background_searches)

    async def discover(self, request: DiscoveryRequest) -> DiscoveryResult:
        context = DiscoveryContext(request=request)
        started = time.time()

        providers = select_providers(self._registry, request)

        if not providers:
            offline_results = await self._offline.discover_offline(request, context)
            if offline_results:
                latency_ms = (time.time() - started) * 1000
                best = self._build_best_result(offline_results, context, latency_ms)
                self._telemetry.record_search(
                    latency_ms=latency_ms,
                    success=True,
                    provider="offline",
                    cached=False,
                )
                return best
            return self._no_provider_result()

        cache_key = (
            f"discovery:{hash(request.query.strip().lower())}:"
            f"{request.mode.value}:{','.join(p.get_provider_id() for p in providers)}:"
            f"{request.language}:{request.max_results}"
        )
        cached = self._cache.get(cache_key, ttl=request.ttl)
        if cached is not None:
            self._telemetry.record_search(
                latency_ms=(time.time() - started) * 1000,
                success=True,
                provider="cache",
                cached=True,
            )
            return cached

        mode = request.mode
        if mode == RetrievalMode.SINGLE:
            raw_results = await self._single_provider(providers[0], request, context)
        elif mode == RetrievalMode.FALLBACK:
            raw_results = await self._fallback(providers, request, context)
        elif mode == RetrievalMode.PRIORITY:
            raw_results = await self._priority(providers, request, context)
        elif mode == RetrievalMode.STREAMING:
            raw_results = await self._streaming(providers, request, context)
        else:
            raw_results = await self._parallel(providers, request, context)

        if not raw_results:
            offline_results = await self._offline.discover_offline(request, context)
            if offline_results:
                raw_results = offline_results

        merged = merge_results(raw_results)
        latency_ms = (time.time() - started) * 1000

        best = self._build_best_result(merged, context, latency_ms)
        self._cache.set(cache_key, best)
        self._telemetry.record_search(
            latency_ms=latency_ms,
            success=bool(merged),
            provider=best.provider,
            cached=False,
            retries=context.telemetry.get("retries", 0),
        )
        return best

    async def _single_provider(
        self, provider: DiscoveryProvider, request: DiscoveryRequest, context: DiscoveryContext
    ) -> list[DiscoveryResult]:
        return await self._execute_provider(provider, request, context)

    async def _fallback(
        self, providers: list[DiscoveryProvider], request: DiscoveryRequest, context: DiscoveryContext
    ) -> list[DiscoveryResult]:
        for provider in providers:
            try:
                results = await self._execute_provider(provider, request, context)
                if results:
                    return results
            except Exception:
                context.errors[provider.get_provider_id()] = "provider_failed"
                continue
        return []

    async def _priority(
        self, providers: list[DiscoveryProvider], request: DiscoveryRequest, context: DiscoveryContext
    ) -> list[DiscoveryResult]:
        sorted_providers = sorted(providers, key=lambda p: -p.priority())
        tasks = [self._execute_provider(p, request, context) for p in sorted_providers]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        merged: list[DiscoveryResult] = []
        for res in all_results:
            if isinstance(res, list):
                merged.extend(res)
        return merged

    async def _parallel(
        self, providers: list[DiscoveryProvider], request: DiscoveryRequest, context: DiscoveryContext
    ) -> list[DiscoveryResult]:
        tasks = [self._execute_provider(p, request, context) for p in providers]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        merged: list[DiscoveryResult] = []
        for res in all_results:
            if isinstance(res, list):
                merged.extend(res)
        return merged

    async def _streaming(
        self, providers: list[DiscoveryProvider], request: DiscoveryRequest, context: DiscoveryContext
    ) -> list[DiscoveryResult]:
        merged: list[DiscoveryResult] = []
        for provider in providers:
            async for stream_result in self._streaming.stream_discover(provider, request, context):
                if stream_result.is_final:
                    merged.append(stream_result.result)
        return merged

    async def _execute_provider(
        self, provider: DiscoveryProvider, request: DiscoveryRequest, context: DiscoveryContext
    ) -> list[DiscoveryResult]:
        pid = provider.get_provider_id()
        plan = self._build_plan_for_request(request, provider)
        retries = 2
        if plan and plan.steps:
            matching = [step for step in plan.steps if step.provider_id == pid]
            if matching:
                retries = matching[0].retries
        config = RetryConfig(max_retries=retries)

        async def _call() -> list[DiscoveryResult]:
            if asyncio.iscoroutinefunction(provider.discover):
                return await provider.discover(request, context)
            return provider.discover(request, context)  # type: ignore[return-value]

        try:
            results = await retry_with_backoff(
                _call,
                config=config,
                should_retry=lambda e: _is_retryable(e),
            )
            context.provider_results[pid] = results
            updated: list[DiscoveryResult] = []
            for r in results:
                estimated = estimate_freshness(r.metadata, time.time())
                updated.append(DiscoveryResult(
                    content=r.content,
                    summary=r.summary,
                    metadata=r.metadata,
                    sources=r.sources,
                    confidence=r.confidence,
                    freshness=estimated,
                    provider=r.provider,
                    retrieval_time=r.retrieval_time,
                ))
            return updated
        except Exception as exc:
            context.errors[pid] = str(exc)
            context.telemetry["retries"] = context.telemetry.get("retries", 0) + config.max_retries
            return []

    def _build_plan_for_request(self, request: DiscoveryRequest, provider: DiscoveryProvider) -> Any:
        analysis = self._query_analyzer.analyze(request)
        plan = self._search_planner.plan(analysis, [provider], request.mode, request.strategy)
        return plan

    def _build_best_result(
        self,
        results: list[DiscoveryResult],
        context: DiscoveryContext,
        latency_ms: float,
    ) -> DiscoveryResult:
        if not results:
            return DiscoveryResult(
                content="",
                summary="No results found.",
                metadata=DiscoveryMetadata(
                    provider="none",
                    url="",
                    title="No results",
                    confidence=0.0,
                    freshness=FreshnessLevel.UNKNOWN,
                ),
                confidence=0.0,
                freshness=FreshnessLevel.UNKNOWN,
                provider="none",
                retrieval_time=0.0,
            )

        best = max(results, key=lambda r: (r.confidence, -r.retrieval_time))
        best_sources = [r.metadata for r in results if r is not best]
        return DiscoveryResult(
            content=best.content,
            summary=best.summary,
            metadata=best.metadata,
            sources=best_sources,
            confidence=best.confidence,
            freshness=best.metadata.freshness,
            provider=best.provider,
            retrieval_time=latency_ms,
        )

    def _no_provider_result(self) -> DiscoveryResult:
        return DiscoveryResult(
            content="",
            summary="No providers available for this request.",
            metadata=DiscoveryMetadata(
                provider="none",
                url="",
                title="No results",
                confidence=0.0,
                freshness=FreshnessLevel.UNKNOWN,
            ),
            confidence=0.0,
            freshness=FreshnessLevel.UNKNOWN,
            provider="none",
            retrieval_time=0.0,
        )


def _is_retryable(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    return any(t in name for t in {"timeout", "connection", "rate", "server", "httperror"})


async def initialize_discovery_runtime(
    runtime: DiscoveryRuntime,
) -> None:
    pass


async def shutdown_discovery_runtime(runtime: DiscoveryRuntime) -> None:
    pass

# backend/tests/discovery/test_phase2.py
from __future__ import annotations

import asyncio

import pytest

from runtime.discovery.capability_router import CapabilityRouter
from runtime.discovery.contracts import (
    AuthorityLevel,
    Capability,
    DiscoveryContext,
    DiscoveryIntent,
    DiscoveryMetadata,
    DiscoveryRequest,
    DiscoveryResult,
    ExecutionStrategy,
    FreshnessLevel,
    ProviderCapability,
    QueryAnalysis,
    RetrievalMode,
    SearchDifficulty,
)
from runtime.discovery.dashboard import DiscoveryDashboardExporter
from runtime.discovery.latency import LatencyAwareExecutor
from runtime.discovery.offline import OfflineDiscovery
from runtime.discovery.query_analyzer import QueryAnalyzer
from runtime.discovery.ranking import AdaptiveRanker
from runtime.discovery.rewriter import QueryRewriter
from runtime.discovery.runtime import DiscoveryRuntime
from runtime.discovery.sandbox import ProviderSandbox
from runtime.discovery.search_planner import SearchPlanner
from runtime.discovery.telemetry import DiscoveryTelemetry
from runtime.discovery.verification import VerificationEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakePhase2Provider:
    def __init__(
        self,
        pid: str,
        provider_type: str = "web",
        available: bool = True,
        priority_value: int = 50,
        capabilities: list[Capability] | None = None,
        authority: AuthorityLevel = AuthorityLevel.UNKNOWN,
        cost: float = 0.0,
        avg_latency_ms: float = 300.0,
    ) -> None:
        self._id = pid
        self._type = provider_type
        self._available = available
        self._priority_value = priority_value
        self._capabilities = capabilities or [Capability.WEB]
        self._authority = authority
        self._cost = cost
        self._avg_latency_ms = avg_latency_ms
        self._success_count = 10
        self._request_count = 10

    def get_provider_id(self) -> str:
        return self._id

    def get_provider_type(self) -> str:
        return self._type

    def get_capabilities(self) -> list[Capability]:
        return list(self._capabilities)

    def get_authority_level(self) -> AuthorityLevel:
        return self._authority

    def estimated_cost(self) -> float:
        return self._cost

    def estimated_latency_ms(self) -> float:
        return self._avg_latency_ms

    def estimated_confidence(self) -> float:
        if self._request_count == 0:
            return 0.8
        return self._success_count / max(self._request_count, 1)

    async def discover(self, request: DiscoveryRequest, context: DiscoveryContext) -> list[DiscoveryResult]:
        return [
            DiscoveryResult(
                content=f"result from {self._id}",
                summary=f"summary from {self._id}",
                metadata=DiscoveryMetadata(
                    provider=self._id,
                    url=f"https://{self._id}.example.com",
                    title=f"Title {self._id}",
                    confidence=0.9,
                    freshness=FreshnessLevel.UNKNOWN,
                ),
                confidence=0.9,
                freshness=FreshnessLevel.UNKNOWN,
                provider=self._id,
                retrieval_time=0.0,
            )
        ]

    def is_available(self) -> bool:
        return self._available

    def health_check(self) -> dict:
        return {"status": "healthy"}

    def priority(self) -> int:
        return self._priority_value

    def cache_ttl(self) -> int:
        return 900


# ---------------------------------------------------------------------------
# Query Analyzer Tests
# ---------------------------------------------------------------------------

class TestQueryAnalyzer:
    def test_detect_programming_intent(self):
        analyzer = QueryAnalyzer()
        request = DiscoveryRequest(query="python code github")
        analysis = analyzer.analyze(request)
        assert analysis.intent == DiscoveryIntent.PROGRAMMING

    def test_detect_encyclopedia_intent(self):
        analyzer = QueryAnalyzer()
        request = DiscoveryRequest(query="what is artificial intelligence")
        analysis = analyzer.analyze(request)
        assert analysis.intent == DiscoveryIntent.ENCYCLOPEDIA

    def test_detect_news_intent(self):
        analyzer = QueryAnalyzer()
        request = DiscoveryRequest(query="breaking news today")
        analysis = analyzer.analyze(request)
        assert analysis.intent == DiscoveryIntent.NEWS

    def test_detect_academic_intent(self):
        analyzer = QueryAnalyzer()
        request = DiscoveryRequest(query="research paper study")
        analysis = analyzer.analyze(request)
        assert analysis.intent == DiscoveryIntent.ACADEMIC

    def test_freshness_latest(self):
        analyzer = QueryAnalyzer()
        request = DiscoveryRequest(query="latest news")
        analysis = analyzer.analyze(request)
        assert analysis.freshness_requirement == FreshnessLevel.LIVE

    def test_freshness_history(self):
        analyzer = QueryAnalyzer()
        request = DiscoveryRequest(query="history of rome")
        analysis = analyzer.analyze(request)
        assert analysis.freshness_requirement == FreshnessLevel.STATIC

    def test_authority_government(self):
        analyzer = QueryAnalyzer()
        request = DiscoveryRequest(query="government report")
        analysis = analyzer.analyze(request)
        assert analysis.authority_requirement == AuthorityLevel.GOVERNMENT

    def test_authority_github(self):
        analyzer = QueryAnalyzer()
        request = DiscoveryRequest(query="github repository")
        analysis = analyzer.analyze(request)
        assert analysis.authority_requirement == AuthorityLevel.GITHUB

    def test_difficulty_hard(self):
        analyzer = QueryAnalyzer()
        request = DiscoveryRequest(query="implement a distributed system architecture")
        analysis = analyzer.analyze(request)
        assert analysis.search_difficulty == SearchDifficulty.HARD

    def test_difficulty_easy(self):
        analyzer = QueryAnalyzer()
        request = DiscoveryRequest(query="what is python")
        analysis = analyzer.analyze(request)
        assert analysis.search_difficulty == SearchDifficulty.EASY

    def test_latency_budget_fast(self):
        analyzer = QueryAnalyzer()
        request = DiscoveryRequest(query="fast quick instant answer")
        analysis = analyzer.analyze(request)
        assert analysis.latency_budget_ms < 1000

    def test_latency_budget_thorough(self):
        analyzer = QueryAnalyzer()
        request = DiscoveryRequest(query="thorough deep comprehensive analysis")
        analysis = analyzer.analyze(request)
        assert analysis.latency_budget_ms > 4000

    def test_capabilities_programming(self):
        analyzer = QueryAnalyzer()
        request = DiscoveryRequest(query="python code")
        analysis = analyzer.analyze(request)
        assert Capability.CODE in analysis.expected_capabilities

    def test_topic_extraction(self):
        analyzer = QueryAnalyzer()
        request = DiscoveryRequest(query="what is the latest RTX driver")
        analysis = analyzer.analyze(request)
        assert "rtx" in analysis.topic.lower()
        assert "driver" in analysis.topic.lower()

    def test_explicit_intent_preserved(self):
        analyzer = QueryAnalyzer()
        request = DiscoveryRequest(query="anything", intent=DiscoveryIntent.PROGRAMMING)
        analysis = analyzer.analyze(request)
        assert analysis.intent == DiscoveryIntent.PROGRAMMING


# ---------------------------------------------------------------------------
# Search Planner Tests
# ---------------------------------------------------------------------------

class TestSearchPlanner:
    def test_plan_ranks_by_capability(self):
        planner = SearchPlanner()
        analysis = QueryAnalysis(
            intent=DiscoveryIntent.PROGRAMMING,
            topic="python",
            domain="programming",
            freshness_requirement=FreshnessLevel.UNKNOWN,
            authority_requirement=AuthorityLevel.UNKNOWN,
            latency_budget_ms=2000.0,
            search_difficulty=SearchDifficulty.MEDIUM,
            expected_capabilities=[Capability.CODE, Capability.REPOSITORIES],
            raw_query="python",
        )
        providers = [
            FakePhase2Provider("github", "programming", capabilities=[Capability.CODE, Capability.REPOSITORIES], authority=AuthorityLevel.GITHUB),
            FakePhase2Provider("wikipedia", "encyclopedia", capabilities=[Capability.REFERENCE], authority=AuthorityLevel.WIKIPEDIA),
        ]
        plan = planner.plan(analysis, providers, RetrievalMode.PARALLEL, ExecutionStrategy.BALANCED)
        assert plan.authority_ranking[0] == "github"
        assert len(plan.steps) == 2

    def test_plan_fast_strategy(self):
        planner = SearchPlanner()
        analysis = QueryAnalysis(
            intent=DiscoveryIntent.GENERAL,
            topic="test",
            domain="general",
            freshness_requirement=FreshnessLevel.UNKNOWN,
            authority_requirement=AuthorityLevel.UNKNOWN,
            latency_budget_ms=500.0,
            search_difficulty=SearchDifficulty.EASY,
            expected_capabilities=[Capability.WEB],
            raw_query="test",
        )
        providers = [FakePhase2Provider("p", avg_latency_ms=100.0)]
        plan = planner.plan(analysis, providers, RetrievalMode.SINGLE, ExecutionStrategy.FAST)
        assert plan.strategy == ExecutionStrategy.FAST
        assert plan.steps[0].timeout_ms < 2000

    def test_plan_quality_strategy(self):
        planner = SearchPlanner()
        analysis = QueryAnalysis(
            intent=DiscoveryIntent.ACADEMIC,
            topic="quantum physics",
            domain="science",
            freshness_requirement=FreshnessLevel.UNKNOWN,
            authority_requirement=AuthorityLevel.ACADEMIC,
            latency_budget_ms=10000.0,
            search_difficulty=SearchDifficulty.HARD,
            expected_capabilities=[Capability.ACADEMIC],
            raw_query="quantum physics",
        )
        providers = [
            FakePhase2Provider("a", authority=AuthorityLevel.ACADEMIC, avg_latency_ms=500.0),
            FakePhase2Provider("b", authority=AuthorityLevel.BLOG, avg_latency_ms=100.0),
        ]
        plan = planner.plan(analysis, providers, RetrievalMode.PARALLEL, ExecutionStrategy.QUALITY)
        assert plan.authority_ranking[0] == "a"
        assert plan.require_verification is True

    def test_plan_rewrites_queries(self):
        planner = SearchPlanner()
        analysis = QueryAnalysis(
            intent=DiscoveryIntent.GENERAL,
            topic="test",
            domain="general",
            freshness_requirement=FreshnessLevel.UNKNOWN,
            authority_requirement=AuthorityLevel.UNKNOWN,
            latency_budget_ms=2000.0,
            search_difficulty=SearchDifficulty.MEDIUM,
            expected_capabilities=[Capability.WEB],
            raw_query="test",
        )
        providers = [FakePhase2Provider("github", "programming")]
        plan = planner.plan(analysis, providers, RetrievalMode.SINGLE, ExecutionStrategy.BALANCED)
        assert plan.steps[0].query_rewrite is not None
        assert "repository" in plan.steps[0].query_rewrite.rewritten_query


# ---------------------------------------------------------------------------
# Capability Router Tests
# ---------------------------------------------------------------------------

class TestCapabilityRouter:
    def test_route_by_capability(self):
        router = CapabilityRouter()
        router.register_provider(FakePhase2Provider("wiki", capabilities=[Capability.REFERENCE]))
        router.register_provider(FakePhase2Provider("code", capabilities=[Capability.CODE]))
        candidates = router.route(QueryAnalysis(
            intent=DiscoveryIntent.GENERAL,
            topic="test",
            domain="general",
            freshness_requirement=FreshnessLevel.UNKNOWN,
            authority_requirement=AuthorityLevel.UNKNOWN,
            latency_budget_ms=2000.0,
            search_difficulty=SearchDifficulty.MEDIUM,
            expected_capabilities=[Capability.CODE],
            raw_query="test",
        ))
        assert any(pc.provider_id == "code" for pc in candidates)

    def test_unregister_removes_capability(self):
        router = CapabilityRouter()
        router.register_provider(FakePhase2Provider("wiki", capabilities=[Capability.REFERENCE]))
        router.unregister_provider("wiki")
        candidates = router.route(QueryAnalysis(
            intent=DiscoveryIntent.GENERAL,
            topic="test",
            domain="general",
            freshness_requirement=FreshnessLevel.UNKNOWN,
            authority_requirement=AuthorityLevel.UNKNOWN,
            latency_budget_ms=2000.0,
            search_difficulty=SearchDifficulty.MEDIUM,
            expected_capabilities=[Capability.REFERENCE],
            raw_query="test",
        ))
        assert all(pc.provider_id != "wiki" for pc in candidates)


# ---------------------------------------------------------------------------
# Authority-aware Tests
# ---------------------------------------------------------------------------

class TestAuthorityAware:
    def test_authority_ranking(self):
        from runtime.discovery.authority import AuthorityRegistry
        registry = AuthorityRegistry()
        registry.register_provider(FakePhase2Provider("gov", authority=AuthorityLevel.GOVERNMENT))
        registry.register_provider(FakePhase2Provider("blog", authority=AuthorityLevel.BLOG))
        pcs = [
            ProviderCapability(provider_id="gov", capabilities=[], authority=AuthorityLevel.GOVERNMENT),
            ProviderCapability(provider_id="blog", capabilities=[], authority=AuthorityLevel.BLOG),
        ]
        ranked = registry.rank_providers(pcs, AuthorityLevel.UNKNOWN)
        assert ranked[0].provider_id == "gov"

    def test_authority_filter(self):
        from runtime.discovery.authority import AuthorityRegistry
        registry = AuthorityRegistry()
        registry.register_provider(FakePhase2Provider("gov", authority=AuthorityLevel.GOVERNMENT))
        registry.register_provider(FakePhase2Provider("blog", authority=AuthorityLevel.BLOG))
        pcs = [
            ProviderCapability(provider_id="gov", capabilities=[], authority=AuthorityLevel.GOVERNMENT),
            ProviderCapability(provider_id="blog", capabilities=[], authority=AuthorityLevel.BLOG),
        ]
        ranked = registry.rank_providers(pcs, AuthorityLevel.GOVERNMENT)
        assert all(pc.provider_id == "gov" for pc in ranked)


# ---------------------------------------------------------------------------
# Latency/Cost-aware Tests
# ---------------------------------------------------------------------------

class TestLatencyAware:
    def test_fast_path_selection(self):
        executor = LatencyAwareExecutor()
        request = DiscoveryRequest(query="test", strategy=ExecutionStrategy.FAST, latency_budget_ms=500.0)
        providers = [FakePhase2Provider("p", avg_latency_ms=100.0), FakePhase2Provider("slow", avg_latency_ms=2000.0)]
        strategy = executor.choose_strategy(request, providers)
        assert strategy == ExecutionStrategy.FAST

    def test_quality_path_selection(self):
        executor = LatencyAwareExecutor()
        request = DiscoveryRequest(query="test", strategy=ExecutionStrategy.QUALITY, latency_budget_ms=10000.0)
        providers = [FakePhase2Provider("p", avg_latency_ms=500.0)]
        strategy = executor.choose_strategy(request, providers)
        assert strategy == ExecutionStrategy.QUALITY

    def test_balanced_path_selection(self):
        executor = LatencyAwareExecutor()
        request = DiscoveryRequest(query="test")
        providers = [FakePhase2Provider("p", avg_latency_ms=300.0)]
        strategy = executor.choose_strategy(request, providers)
        assert strategy == ExecutionStrategy.BALANCED


# ---------------------------------------------------------------------------
# Verification Engine Tests
# ---------------------------------------------------------------------------

class TestVerificationEngine:
    def test_verify_empty_results(self):
        engine = VerificationEngine()
        result = engine.verify([])
        assert result.verified is False
        assert result.agreement_score == 0.0

    def test_verify_single_result(self):
        engine = VerificationEngine()
        results = [
            DiscoveryResult(
                content="content",
                summary="summary",
                metadata=DiscoveryMetadata(provider="p", url="u", title="t", confidence=0.9),
                confidence=0.9,
                provider="p",
            )
        ]
        result = engine.verify(results)
        assert result.verified is True
        assert result.agreement_score == 1.0

    def test_verify_agreement(self):
        engine = VerificationEngine()
        results = [
            DiscoveryResult(content="python is great", summary="python is great", metadata=DiscoveryMetadata(provider="a", url="u", title="t"), provider="a"),
            DiscoveryResult(content="python is great", summary="python is great", metadata=DiscoveryMetadata(provider="b", url="u", title="t"), provider="b"),
        ]
        result = engine.verify(results)
        assert result.agreement_score > 0.5
        assert result.conflict_score < 0.3

    def test_verify_conflict(self):
        engine = VerificationEngine()
        results = [
            DiscoveryResult(content="python is great", summary="python is great", metadata=DiscoveryMetadata(provider="a", url="u", title="t"), provider="a"),
            DiscoveryResult(content="python is false", summary="python is false", metadata=DiscoveryMetadata(provider="b", url="u", title="t"), provider="b"),
        ]
        result = engine.verify(results)
        assert result.conflict_score > 0.0


# ---------------------------------------------------------------------------
# Query Rewriter Tests
# ---------------------------------------------------------------------------

class TestQueryRewriter:
    def test_rewrite_github(self):
        rewriter = QueryRewriter()
        rewrite = rewriter.rewrite("latest RTX drivers", "github", [Capability.CODE])
        assert "repository" in rewrite.rewritten_query

    def test_rewrite_wikipedia(self):
        rewriter = QueryRewriter()
        rewrite = rewriter.rewrite("RTX", "wikipedia", [Capability.REFERENCE])
        assert rewrite.rewritten_query == "RTX"

    def test_rewrite_rss(self):
        rewriter = QueryRewriter()
        rewrite = rewriter.rewrite("driver release", "rss", [Capability.NEWS])
        assert "feed" in rewrite.rewritten_query

    def test_rewrite_batch(self):
        rewriter = QueryRewriter()
        rewrites = rewriter.rewrite_batch("test", [("github", [Capability.CODE]), ("wikipedia", [Capability.REFERENCE])])
        assert len(rewrites) == 2
        assert rewrites[0].provider_id == "github"
        assert rewrites[1].provider_id == "wikipedia"


# ---------------------------------------------------------------------------
# Adaptive Ranking Tests
# ---------------------------------------------------------------------------

class TestAdaptiveRanker:
    def test_record_success_improves_score(self):
        ranker = AdaptiveRanker()
        ranker.record_result("p", True, 100.0, 0.9)
        score = ranker.get_score("p")
        assert score.success_rate > 0.0

    def test_record_failure_decreases_score(self):
        ranker = AdaptiveRanker()
        ranker.record_result("p", False, 1000.0, 0.3)
        score = ranker.get_score("p")
        assert score.success_rate < 0.5

    def test_rank_providers(self):
        ranker = AdaptiveRanker()
        ranker.record_result("a", True, 100.0, 0.9)
        ranker.record_result("b", False, 2000.0, 0.3)
        ranked = ranker.rank_providers(["a", "b"])
        assert ranked[0] == "a"

    def test_get_stats(self):
        ranker = AdaptiveRanker()
        ranker.record_result("p", True, 100.0, 0.9)
        stats = ranker.get_stats()
        assert "p" in stats
        assert stats["p"]["success_rate"] > 0.0


# ---------------------------------------------------------------------------
# Offline Discovery Tests
# ---------------------------------------------------------------------------

class TestOfflineDiscovery:
    def test_offline_empty_cache(self):
        cache = type("FakeCache", (), {"get": lambda self, key, ttl=900: None})()
        offline = OfflineDiscovery(cache)
        result = asyncio.get_event_loop().run_until_complete(offline.discover_offline(
            DiscoveryRequest(query="test"), DiscoveryContext(request=DiscoveryRequest(query="test"))
        ))
        assert result == []


# ---------------------------------------------------------------------------
# Streaming Discovery Tests
# ---------------------------------------------------------------------------

class TestStreamingDiscovery:
    @pytest.mark.asyncio
    async def test_stream_with_callback(self):
        from runtime.discovery.streaming import StreamingDiscovery
        stream = StreamingDiscovery()
        received = []
        request = DiscoveryRequest(query="test", stream_callback=received.append)
        provider = FakePhase2Provider("p")
        context = DiscoveryContext(request=request)
        results = []
        async for sr in stream.stream_discover(provider, request, context):
            results.append(sr)
        assert len(results) == 1
        assert results[0].is_final is True

    @pytest.mark.asyncio
    async def test_stream_no_callback(self):
        from runtime.discovery.streaming import StreamingDiscovery
        stream = StreamingDiscovery()
        request = DiscoveryRequest(query="test")
        provider = FakePhase2Provider("p")
        context = DiscoveryContext(request=request)
        results = []
        async for sr in stream.stream_discover(provider, request, context):
            results.append(sr)
        assert len(results) == 1
        assert results[0].is_final is True


# ---------------------------------------------------------------------------
# Provider Sandbox Tests
# ---------------------------------------------------------------------------

class TestProviderSandbox:
    @pytest.mark.asyncio
    async def test_sandbox_normal_execution(self):
        sandbox = ProviderSandbox(default_timeout_ms=5000.0)
        provider = FakePhase2Provider("p")
        request = DiscoveryRequest(query="test")
        context = DiscoveryContext(request=request)
        results = await sandbox.execute(provider, request, context)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_sandbox_timeout(self):
        import asyncio

        class SlowProvider:
            def get_provider_id(self):
                return "slow"

            def get_provider_type(self):
                return "web"

            def get_capabilities(self):
                return [Capability.WEB]

            def get_authority_level(self):
                return AuthorityLevel.UNKNOWN

            def estimated_cost(self):
                return 0.0

            def estimated_latency_ms(self):
                return 1000.0

            def estimated_confidence(self):
                return 0.5

            async def discover(self, request, context):
                await asyncio.sleep(10)
                return []

            def is_available(self):
                return True

            def health_check(self):
                return {}

            def priority(self):
                return 50

            def cache_ttl(self):
                return 900

        sandbox = ProviderSandbox(default_timeout_ms=500.0)
        provider = SlowProvider()
        request = DiscoveryRequest(query="test")
        context = DiscoveryContext(request=request)
        results = await sandbox.execute(provider, request, context)
        assert results == []

    def test_sandbox_tracks_active_calls(self):
        sandbox = ProviderSandbox()
        assert sandbox.get_active_calls() == {}


# ---------------------------------------------------------------------------
# Dashboard Tests
# ---------------------------------------------------------------------------

class TestDiscoveryDashboard:
    def test_dashboard_export(self):
        telemetry = DiscoveryTelemetry()
        telemetry.record_search(latency_ms=100.0, success=True, provider="p", cached=False)
        registry = type("FakeRegistry", (), {"list": lambda self: []})()
        ranker = AdaptiveRanker()
        exporter = DiscoveryDashboardExporter(telemetry, registry, ranker)
        dashboard = exporter.export()
        assert dashboard.registered_providers == 0
        assert dashboard.success_rate > 0.0


# ---------------------------------------------------------------------------
# Phase 2 Integration Tests
# ---------------------------------------------------------------------------

class TestPhase2Integration:
    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        runtime = DiscoveryRuntime()
        runtime.register_provider(FakePhase2Provider("wikipedia", "encyclopedia", capabilities=[Capability.REFERENCE, Capability.ACADEMIC], authority=AuthorityLevel.WIKIPEDIA))
        runtime.register_provider(FakePhase2Provider("github", "programming", capabilities=[Capability.CODE, Capability.REPOSITORIES], authority=AuthorityLevel.GITHUB))
        request = DiscoveryRequest(
            query="python programming",
            mode=RetrievalMode.PARALLEL,
            strategy=ExecutionStrategy.BALANCED,
            require_verification=True,
        )
        result = await runtime.discover(request)
        assert result.provider in ("wikipedia", "github")
        assert result.confidence > 0.0

    @pytest.mark.asyncio
    async def test_query_analyzer_integration(self):
        runtime = DiscoveryRuntime()
        runtime.register_provider(FakePhase2Provider("wiki", "encyclopedia", capabilities=[Capability.REFERENCE]))
        request = DiscoveryRequest(query="what is machine learning")
        result = await runtime.discover(request)
        assert result.provider == "wiki"

    @pytest.mark.asyncio
    async def test_offline_fallback(self):
        runtime = DiscoveryRuntime()
        request = DiscoveryRequest(query="nonexistent topic xyz")
        result = await runtime.discover(request)
        assert result.provider == "none"

    def test_telemetry_new_metrics(self):
        telemetry = DiscoveryTelemetry()
        telemetry.record_search(
            latency_ms=100.0,
            success=True,
            provider="p",
            cached=False,
            verification_score=0.9,
            planner_decision="parallel",
            authority="wikipedia",
            strategy="balanced",
        )
        stats = telemetry.get_stats()
        assert stats["verification_rate"] > 0.0
        assert stats["avg_verification_score"] > 0.0
        assert "planner_decisions" in stats
        assert "authority_distribution" in stats

    def test_adaptive_ranking_over_time(self):
        ranker = AdaptiveRanker()
        for _ in range(10):
            ranker.record_result("p", True, 100.0, 0.9)
        score = ranker.get_score("p")
        assert score.score > 0.5

    @pytest.mark.asyncio
    async def test_sandbox_isolates_exceptions(self):
        class BadProvider:
            def get_provider_id(self):
                return "bad"

            def get_provider_type(self):
                return "web"

            def get_capabilities(self):
                return [Capability.WEB]

            def get_authority_level(self):
                return AuthorityLevel.UNKNOWN

            def estimated_cost(self):
                return 0.0

            def estimated_latency_ms(self):
                return 300.0

            def estimated_confidence(self):
                return 0.5

            async def discover(self, request, context):
                raise ValueError("bad provider")

            def is_available(self):
                return True

            def health_check(self):
                return {}

            def priority(self):
                return 50

            def cache_ttl(self):
                return 900

        sandbox = ProviderSandbox()
        provider = BadProvider()
        request = DiscoveryRequest(query="test")
        context = DiscoveryContext(request=request)
        results = await sandbox.execute(provider, request, context)
        assert results == []
        assert "bad" in context.errors

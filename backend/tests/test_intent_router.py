"""Tests for the Intent Router runtime and its components."""
import sys
import time
from pathlib import Path

backend_path = Path(__file__).resolve().parents[1]
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

import pytest

from core.event_bus import EventBus, ZaramEvent
from core.contracts import RuntimeState
from runtimes.intent import (
    IntentRouter,
    ConfidenceEngine,
    ConfidenceResult,
    SourceQuality,
    TemporalClassifier,
    ClassificationResult,
    QueryEnvelope,
    IntentType,
    TemporalSensitivity,
)


# ---------------------------------------------------------------------------
# QueryEnvelope tests
# ---------------------------------------------------------------------------

class TestQueryEnvelope:
    def test_basic_construction(self):
        env = QueryEnvelope(query="What is AI?")
        assert env.query == "What is AI?"
        assert env.intent_type == IntentType.UNKNOWN
        assert env.temporal_sensitivity == TemporalSensitivity.MIXED
        assert env.confidence_threshold == 0.7
        assert env.max_results == 10

    def test_from_query_with_intent(self):
        env = QueryEnvelope.from_query("Latest news", intent_type=IntentType.SEARCH)
        assert env.intent_type == IntentType.SEARCH
        assert env.query == "Latest news"

    def test_correlation_id_generated(self):
        env1 = QueryEnvelope(query="test")
        env2 = QueryEnvelope(query="test")
        assert env1.correlation_id != env2.correlation_id

    def test_to_dict(self):
        env = QueryEnvelope(query="test", intent_type=IntentType.SEARCH, max_results=5)
        d = env.to_dict()
        assert d["query"] == "test"
        assert d["intent_type"] == "search"
        assert d["max_results"] == 5
        assert "correlation_id" in d
        assert "timestamp" in d

    def test_age_seconds(self):
        env = QueryEnvelope(query="test", timestamp=time.time() - 5)
        assert 4.9 < env.age_seconds < 6.0

    def test_custom_metadata(self):
        env = QueryEnvelope(query="test", metadata={"custom": "value"})
        assert env.metadata["custom"] == "value"

    def test_preferred_sources(self):
        env = QueryEnvelope(query="test", preferred_sources=["memory", "knowledge"])
        assert env.preferred_sources == ["memory", "knowledge"]


# ---------------------------------------------------------------------------
# TemporalClassifier tests
# ---------------------------------------------------------------------------

class TestTemporalClassifier:
    def setup_method(self):
        self.classifier = TemporalClassifier()

    def test_time_sensitive_current(self):
        result = self.classifier.classify("Current weather in New York")
        assert result.sensitivity == TemporalSensitivity.TIME_SENSITIVE
        assert result.confidence > 0.5

    def test_time_sensitive_latest(self):
        result = self.classifier.classify("Latest stock price of AAPL")
        assert result.sensitivity == TemporalSensitivity.TIME_SENSITIVE

    def test_time_sensitive_breaking(self):
        result = self.classifier.classify("Breaking news about the election")
        assert result.sensitivity == TemporalSensitivity.TIME_SENSITIVE

    def test_time_sensitive_year_reference(self):
        result = self.classifier.classify("What happened in 2026?")
        assert result.sensitivity == TemporalSensitivity.TIME_SENSITIVE

    def test_timeless_explain(self):
        result = self.classifier.classify("Explain recursion")
        assert result.sensitivity == TemporalSensitivity.TIMELESS

    def test_timeless_concept(self):
        result = self.classifier.classify("What is the concept of polymorphism?")
        assert result.sensitivity == TemporalSensitivity.TIMELESS

    def test_timeless_tutorial(self):
        result = self.classifier.classify("How to learn Python")
        assert result.sensitivity == TemporalSensitivity.TIMELESS

    def test_mixed_query(self):
        result = self.classifier.classify("Explain the latest AI news today")
        assert result.sensitivity == TemporalSensitivity.MIXED

    def test_empty_query(self):
        result = self.classifier.classify("")
        assert result.sensitivity == TemporalSensitivity.MIXED
        assert result.confidence == 0.0

    def test_short_query(self):
        result = self.classifier.classify("ab")
        assert result.sensitivity == TemporalSensitivity.MIXED

    def test_is_time_sensitive_boolean(self):
        assert self.classifier.is_time_sensitive("Current weather") is True
        assert self.classifier.is_time_sensitive("Latest stock price") is True
        assert self.classifier.is_time_sensitive("Explain recursion") is False

    def test_classification_result_to_dict(self):
        result = self.classifier.classify("Current weather")
        d = result.to_dict()
        assert "sensitivity" in d
        assert "confidence" in d
        assert "matched_patterns" in d
        assert "reasons" in d

    def test_matched_patterns_populated(self):
        result = self.classifier.classify("Current weather forecast")
        assert len(result.matched_patterns) > 0
        assert len(result.reasons) > 0


# ---------------------------------------------------------------------------
# ConfidenceEngine tests
# ---------------------------------------------------------------------------

class TestConfidenceEngine:
    def setup_method(self):
        self.engine = ConfidenceEngine()

    def test_register_source(self):
        quality = SourceQuality(source_id="memory", reliability=0.9, authority_score=0.8)
        self.engine.register_source("memory", quality)
        assert self.engine.get_source_quality("memory") is not None

    def test_update_source_success(self):
        self.engine.update_source_success("memory", latency_ms=10.0)
        quality = self.engine.get_source_quality("memory")
        assert quality is not None
        assert quality.success_count == 1

    def test_update_source_failure(self):
        self.engine.update_source_success("memory", latency_ms=10.0)
        self.engine.update_source_failure("memory")
        quality = self.engine.get_source_quality("memory")
        assert quality.failure_count == 1

    def test_evaluate_empty_results(self):
        result = self.engine.evaluate(results=[], sources_consulted=["memory"], max_results=10)
        assert result.coverage_confidence == 0.0
        assert result.overall == 0.5  # 0.4*0.5 + 0.3*1.0 + 0.3*0.0

    def test_evaluate_full_coverage(self):
        results = list(range(10))
        result = self.engine.evaluate(results=results, sources_consulted=["memory"], max_results=10)
        assert result.coverage_confidence == 1.0

    def test_evaluate_source_confidence(self):
        quality = SourceQuality(source_id="memory", reliability=0.9, authority_score=0.8)
        self.engine.register_source("memory", quality)
        result = self.engine.evaluate(results=[], sources_consulted=["memory"], max_results=5)
        assert result.source_confidence > 0.0

    def test_evaluate_recency(self):
        result = self.engine.evaluate(results=[], sources_consulted=[], max_results=5, query_age_seconds=0)
        assert result.recency_confidence == 1.0

        result_stale = self.engine.evaluate(
            results=[], sources_consulted=[], max_results=5, query_age_seconds=2000
        )
        assert result_stale.recency_confidence < 1.0

    def test_evaluate_signal_strength(self):
        results = list(range(5))
        result = self.engine.evaluate(results=results, sources_consulted=[], max_results=10)
        assert result.signal_strength == 0.5

    def test_get_source_health(self):
        self.engine.update_source_success("memory", latency_ms=10.0)
        quality = self.engine.get_source_quality("memory")
        assert quality is not None
        assert quality.success_count == 1
        assert quality.availability > 0

    def test_list_sources(self):
        self.engine.register_source("memory", SourceQuality(source_id="memory"))
        sources = self.engine.list_sources()
        assert "memory" in sources

    def test_confidence_result_to_dict(self):
        result = self.engine.evaluate(results=[], sources_consulted=[], max_results=5)
        d = result.to_dict()
        assert "overall" in d
        assert "source_confidence" in d
        assert "recency_confidence" in d
        assert "coverage_confidence" in d
        assert "signal_strength" in d


# ---------------------------------------------------------------------------
# IntentRouter tests
# ---------------------------------------------------------------------------

class TestIntentRouter:
    def setup_method(self):
        self.event_bus = EventBus()
        self.router = IntentRouter(self.event_bus)

    def test_get_runtime_id(self):
        assert self.router.get_runtime_id() == "intent"

    def test_get_metadata(self):
        meta = self.router.get_metadata()
        assert meta.runtime_id == "intent"
        assert meta.version == "1.0.0"
        assert len(meta.capabilities) > 0

    def test_get_state(self):
        assert self.router.get_state() == RuntimeState.UNINITIALIZED

    def test_health_check(self):
        health = self.router.health_check()
        assert health["runtime_id"] == "intent"
        assert "state" in health
        assert "stats" in health

    @pytest.mark.asyncio
    async def test_initialize(self):
        await self.router.initialize()
        assert self.router.get_state() == RuntimeState.READY

    def test_route_returns_envelope(self):
        envelope = self.router.route("What is AI?", intent_type=IntentType.REASONING)
        assert isinstance(envelope, QueryEnvelope)
        assert envelope.query == "What is AI?"
        assert envelope.intent_type == IntentType.REASONING

    def test_route_publishes_event(self):
        events = []
        self.event_bus.subscribe("intent.routed", events.append)
        self.router.route("Latest news", intent_type=IntentType.SEARCH)
        assert len(events) == 1
        assert events[0].event_type == "intent.routed"
        assert events[0].data["target_runtime"] == "knowledge"

    def test_route_time_sensitive_query(self):
        envelope = self.router.route("Current weather", intent_type=IntentType.SEARCH)
        assert envelope.temporal_sensitivity == TemporalSensitivity.TIME_SENSITIVE

    def test_route_timeless_query(self):
        envelope = self.router.route("Explain recursion", intent_type=IntentType.REASONING)
        assert envelope.temporal_sensitivity == TemporalSensitivity.TIMELESS

    def test_register_source(self):
        quality = SourceQuality(source_id="memory", reliability=0.9)
        self.router.register_source("memory", quality)
        assert self.router.get_confidence_engine().get_source_quality("memory") is not None

    def test_get_classifier(self):
        assert isinstance(self.router.get_classifier(), TemporalClassifier)

    def test_get_confidence_engine(self):
        assert isinstance(self.router.get_confidence_engine(), ConfidenceEngine)

    def test_stats_updated(self):
        self.router.route("Explain recursion", intent_type=IntentType.REASONING)
        self.router.route("How does Python work", intent_type=IntentType.REASONING)
        stats = self.router.get_stats()
        assert stats["intents_routed"] == 2
        assert stats["timeless"] > 0

    @pytest.mark.asyncio
    async def test_handle_intent_received_event(self):
        await self.router.initialize()
        events = []
        self.event_bus.subscribe("intent.routed", events.append)
        self.event_bus.publish(ZaramEvent(
            source_runtime="test",
            event_type="intent.received",
            data={"query": "What is the latest news?", "intent_type": "search"},
        ))
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_handle_confidence_update(self):
        await self.router.initialize()
        self.event_bus.publish(ZaramEvent(
            source_runtime="discovery",
            event_type="discovery.confidence_update",
            data={"source_id": "memory", "success": True, "latency_ms": 10.0},
        ))
        quality = self.router.get_confidence_engine().get_source_quality("memory")
        assert quality is not None
        assert quality.success_count == 1

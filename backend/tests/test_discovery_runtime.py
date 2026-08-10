"""Tests for the Discovery Runtime and Discovery Escalation."""
import sys
import time
from pathlib import Path

backend_path = Path(__file__).resolve().parents[1]
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

import pytest

from core.event_bus import EventBus, ZaramEvent
from core.contracts import RuntimeState
from runtimes.discovery import (
    DiscoveryRuntime,
    DiscoveryEscalation,
    DiscoverySource,
    EscalationResult,
    EscalationStep,
)


# ---------------------------------------------------------------------------
# DiscoveryEscalation tests
# ---------------------------------------------------------------------------

class TestDiscoveryEscalation:
    def setup_method(self):
        self.escalation = DiscoveryEscalation()

    def test_default_chain(self):
        chain = self.escalation.get_chain("default")
        assert len(chain) == 4
        assert chain[0].source == DiscoverySource.CACHE
        assert chain[1].source == DiscoverySource.MEMORY
        assert chain[2].source == DiscoverySource.KNOWLEDGE
        assert chain[3].source == DiscoverySource.INTERNET

    def test_time_sensitive_chain(self):
        chain = self.escalation.get_chain("time_sensitive")
        assert chain[0].source == DiscoverySource.CACHE
        assert chain[1].source == DiscoverySource.KNOWLEDGE

    def test_agent_chain(self):
        chain = self.escalation.get_chain("agent")
        assert DiscoverySource.INTERNET not in [s.source for s in chain]

    def test_register_custom_chain(self):
        custom = [EscalationStep(DiscoverySource.CACHE, 0.1, False, "Custom")]
        self.escalation.register_chain("custom", custom)
        chain = self.escalation.get_chain("custom")
        assert len(chain) == 1
        assert chain[0].source == DiscoverySource.CACHE

    def test_get_source_timeout(self):
        assert self.escalation.get_source_timeout(DiscoverySource.CACHE) == 0.1
        assert self.escalation.get_source_timeout(DiscoverySource.INTERNET) == 10.0

    def test_record_success(self):
        self.escalation.record_success(DiscoverySource.MEMORY, latency_ms=5.0)
        health = self.escalation.get_source_health(DiscoverySource.MEMORY)
        assert health["successes"] == 1
        assert health["avg_latency_ms"] == 5.0

    def test_record_failure(self):
        self.escalation.record_failure(DiscoverySource.INTERNET)
        health = self.escalation.get_source_health(DiscoverySource.INTERNET)
        assert health["failures"] == 1

    def test_get_source_health_unknown(self):
        health = self.escalation.get_source_health(DiscoverySource.CACHE)
        assert health["successes"] == 0
        assert health["failures"] == 0
        assert health["success_rate"] == 0.0

    def test_should_escalate_no_results(self):
        chain = self.escalation.get_chain("default")
        assert self.escalation.should_escalate([], DiscoverySource.CACHE, chain, min_results=1) is True

    def test_should_escalate_has_results(self):
        chain = self.escalation.get_chain("default")
        assert self.escalation.should_escalate(["result"], DiscoverySource.CACHE, chain, min_results=1) is False

    def test_should_escalate_last_source(self):
        chain = self.escalation.get_chain("default")
        assert self.escalation.should_escalate([], DiscoverySource.INTERNET, chain, min_results=1) is False

    def test_get_next_source(self):
        chain = self.escalation.get_chain("default")
        next_step = self.escalation.get_next_source(DiscoverySource.CACHE, chain)
        assert next_step is not None
        assert next_step.source == DiscoverySource.MEMORY

    def test_get_next_source_last(self):
        chain = self.escalation.get_chain("default")
        next_step = self.escalation.get_next_source(DiscoverySource.INTERNET, chain)
        assert next_step is None

    def test_evaluate_chain(self):
        chain = self.escalation.evaluate_chain("test query", "default", min_results=1)
        assert len(chain) == 4

    def test_update_stats(self):
        self.escalation.update_stats(DiscoverySource.CACHE)
        stats = self.escalation.get_stats()
        assert stats["cache_hits"] == 1

    def test_update_stats_escalated(self):
        self.escalation.update_stats(DiscoverySource.CACHE, escalated=True)
        stats = self.escalation.get_stats()
        assert stats["escalations_to_next"] == 1

    def test_reset_stats(self):
        self.escalation.update_stats(DiscoverySource.CACHE)
        self.escalation.reset_stats()
        stats = self.escalation.get_stats()
        assert stats["cache_hits"] == 0
        assert stats["escalations"] == 0


# ---------------------------------------------------------------------------
# DiscoveryRuntime tests
# ---------------------------------------------------------------------------

class TestDiscoveryRuntime:
    def setup_method(self):
        self.event_bus = EventBus()
        self.runtime = DiscoveryRuntime(self.event_bus)

    def test_get_runtime_id(self):
        assert self.runtime.get_runtime_id() == "discovery"

    def test_get_metadata(self):
        meta = self.runtime.get_metadata()
        assert meta.runtime_id == "discovery"
        assert len(meta.capabilities) > 0

    def test_get_state(self):
        assert self.runtime.get_state() == RuntimeState.UNINITIALIZED

    def test_health_check(self):
        health = self.runtime.health_check()
        assert health["runtime_id"] == "discovery"
        assert "state" in health
        assert "stats" in health
        assert "cache_size" in health

    def test_get_stats(self):
        stats = self.runtime.get_stats()
        assert "requests" in stats
        assert "results_returned" in stats

    def test_get_escalation_engine(self):
        assert isinstance(self.runtime.get_escalation_engine(), DiscoveryEscalation)

    @pytest.mark.asyncio
    async def test_initialize(self):
        await self.runtime.initialize()
        assert self.runtime.get_state() == RuntimeState.READY

    def test_discover_caches_results(self):
        results = self.runtime.discover("test query", max_results=5)
        assert isinstance(results, list)
        stats = self.runtime.get_stats()
        assert stats["requests"] == 1

    def test_discover_uses_cache(self):
        self.runtime.cache_result("cached_key", ["result1", "result2"])
        results = self.runtime.discover("cached_key", max_results=5)
        assert len(results) == 2
        stats = self.runtime.get_stats()
        assert stats["cache_hits"] == 1

    def test_cache_result(self):
        self.runtime.cache_result("key", ["a", "b"])
        assert self.runtime._result_cache["key"] == ["a", "b"]

    def test_invalidate_cache_by_key(self):
        self.runtime.cache_result("key1", ["a"])
        self.runtime.cache_result("key2", ["b"])
        self.runtime.invalidate_cache("key1")
        assert "key1" not in self.runtime._result_cache
        assert "key2" in self.runtime._result_cache

    def test_invalidate_cache_all(self):
        self.runtime.cache_result("key1", ["a"])
        self.runtime.invalidate_cache()
        assert len(self.runtime._result_cache) == 0

    @pytest.mark.asyncio
    async def test_handle_discovery_request_event(self):
        await self.runtime.initialize()
        events = []
        self.event_bus.subscribe("discovery.results", events.append)
        self.event_bus.publish(ZaramEvent(
            source_runtime="test",
            event_type="discovery.request",
            data={"query": "test query", "max_results": 5},
        ))
        assert len(events) == 1
        assert events[0].event_type == "discovery.results"

    @pytest.mark.asyncio
    async def test_handle_cache_hit_event(self):
        await self.runtime.initialize()
        self.event_bus.publish(ZaramEvent(
            source_runtime="discovery",
            event_type="discovery.cache_hit",
            data={"source": "cache", "latency_ms": 1.0},
        ))
        health = self.runtime.get_escalation_engine().get_source_health(DiscoverySource.CACHE)
        assert health["successes"] == 1

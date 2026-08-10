from __future__ import annotations

import time
from typing import Any

from core.contracts import Runtime, RuntimeMetadata, Capability, RuntimeState
from core.event_bus import EventBus, ZaramEvent

from .escalation import (
    DiscoveryEscalation,
    DiscoverySource,
    EscalationResult,
    EscalationStep,
)


class DiscoveryRuntime(Runtime):
    """Handles discovery operations with escalation through source chains.

    The Discovery Runtime subscribes to ``discovery.request`` events,
    uses the DiscoveryEscalation engine to determine the source chain,
    and publishes ``discovery.results`` events with the findings.

    All communication is through the Event Bus — no direct runtime imports.
    """

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._state = RuntimeState.UNINITIALIZED
        self._escalation = DiscoveryEscalation(event_bus=event_bus)
        self._start_time = time.time()
        self._stats: dict[str, Any] = {
            "requests": 0,
            "results_returned": 0,
            "escalations": 0,
            "cache_hits": 0,
            "avg_results": 0.0,
            "total_results": 0,
        }
        self._result_cache: dict[str, list[Any]] = {}

    def get_runtime_id(self) -> str:
        return "discovery"

    def get_version(self) -> str:
        return "1.0.0"

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_id="discovery",
            version="1.0.0",
            priority="high",
            capabilities=[
                Capability(id="discovery.search", runtime_id="discovery", category="discovery"),
                Capability(id="discovery.escalate", runtime_id="discovery", category="discovery"),
                Capability(id="discovery.cache", runtime_id="discovery", category="discovery"),
            ],
            dependencies=["event_bus"],
            auto_start=True,
        )

    async def initialize(self) -> None:
        self._state = RuntimeState.INITIALIZING
        self._event_bus.subscribe("discovery.request", self._handle_discovery_request)
        self._event_bus.subscribe("discovery.cache_hit", self._handle_cache_hit)
        self._state = RuntimeState.READY
        self._event_bus.publish(ZaramEvent(
            source_runtime="discovery",
            event_type="runtime.ready",
            data={"runtime_id": self.get_runtime_id()},
        ))
        print("[DiscoveryRuntime] Initialized and subscribed to discovery.request")

    async def shutdown(self) -> None:
        self._state = RuntimeState.STOPPING
        self._result_cache.clear()
        self._state = RuntimeState.STOPPED
        print("[DiscoveryRuntime] Shut down")

    def get_state(self) -> RuntimeState:
        return self._state

    def health_check(self) -> dict[str, Any]:
        return {
            "runtime_id": self.get_runtime_id(),
            "state": self._state.value,
            "uptime_seconds": time.time() - self._start_time,
            "stats": dict(self._stats),
            "cache_size": len(self._result_cache),
            "source_health": {
                s.value: self._escalation.get_source_health(s)
                for s in DiscoverySource
            },
        }

    def get_stats(self) -> dict[str, Any]:
        return dict(self._stats)

    def get_escalation_engine(self) -> DiscoveryEscalation:
        return self._escalation

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover(
        self,
        query: str,
        query_type: str = "default",
        min_results: int = 1,
        max_results: int = 10,
        correlation_id: str = "",
    ) -> list[Any]:
        """Execute a discovery query with escalation.

        Returns results from the first source that returns enough results,
        or from all sources if escalation is needed.
        """
        self._stats["requests"] += 1
        cache_key = query
        cached = self._result_cache.get(cache_key)
        if cached is not None and len(cached) >= min_results:
            self._stats["cache_hits"] += 1
            self._escalation.update_stats(DiscoverySource.CACHE)
            self._event_bus.publish(ZaramEvent(
                source_runtime="discovery",
                event_type="discovery.results",
                correlation_id=correlation_id,
                priority="normal",
                data={
                    "query": query,
                    "results": cached,
                    "source": DiscoverySource.CACHE.value,
                    "cached": True,
                    "count": len(cached),
                },
            ))
            return cached

        chain = self._escalation.evaluate_chain(query, query_type, min_results)
        all_results: list[Any] = []
        current_source: DiscoverySource | None = None

        for step in chain:
            if len(all_results) >= min_results:
                break

            current_source = step.source
            start = time.time()
            results = self._query_source(step, query, max_results)
            latency_ms = (time.time() - start) * 1000

            if results:
                self._escalation.record_success(step.source, latency_ms)
                all_results.extend(results)
                self._escalation.update_stats(step.source)
            else:
                self._escalation.record_failure(step.source)

            should_escalate = self._escalation.should_escalate(
                all_results, step.source, chain, min_results
            )
            if should_escalate:
                self._stats["escalations"] += 1
                self._escalation.update_stats(step.source, escalated=True)

        final_results = all_results[:max_results]
        self._result_cache[cache_key] = final_results

        self._stats["results_returned"] += len(final_results)
        self._stats["total_results"] += len(final_results)
        if self._stats["requests"] > 0:
            self._stats["avg_results"] = round(
                self._stats["total_results"] / self._stats["requests"], 2
            )

        self._event_bus.publish(ZaramEvent(
            source_runtime="discovery",
            event_type="discovery.results",
            correlation_id=correlation_id,
            priority="normal",
            data={
                "query": query,
                "results": final_results,
                "source": current_source.value if current_source else "none",
                "cached": False,
                "count": len(final_results),
                "escalated": self._stats["escalations"] > 0,
            },
        ))

        return final_results

    def cache_result(self, key: str, results: list[Any]) -> None:
        """Cache discovery results."""
        self._result_cache[key] = list(results)

    def invalidate_cache(self, key: str | None = None) -> None:
        """Invalidate cache entries."""
        if key:
            self._result_cache.pop(key, None)
        else:
            self._result_cache.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _query_source(
        self,
        step: EscalationStep,
        query: str,
        max_results: int,
    ) -> list[Any]:
        """Query a specific source.

        In a real implementation, this would dispatch to the appropriate
        runtime via the Event Bus. For now, it publishes a query event
        and returns empty results (sources respond asynchronously).
        """
        self._event_bus.publish(ZaramEvent(
            source_runtime="discovery",
            event_type=f"discovery.query.{step.source.value}",
            priority="normal",
            data={
                "query": query,
                "max_results": max_results,
                "timeout_seconds": step.timeout_seconds,
            },
        ))
        return []

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _handle_discovery_request(self, event: ZaramEvent) -> None:
        data = event.data
        query = data.get("query", "")
        query_type = data.get("query_type", "default")
        min_results = data.get("min_results", 1)
        max_results = data.get("max_results", 10)
        self.discover(
            query=query,
            query_type=query_type,
            min_results=min_results,
            max_results=max_results,
            correlation_id=event.correlation_id,
        )

    def _handle_cache_hit(self, event: ZaramEvent) -> None:
        data = event.data
        source = data.get("source", "")
        latency = data.get("latency_ms", 0.0)
        self._escalation.record_success(DiscoverySource(source), latency)

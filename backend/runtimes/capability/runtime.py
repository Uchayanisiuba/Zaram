from __future__ import annotations

import time
from typing import Any

from core.contracts import Runtime, RuntimeMetadata, Capability, RuntimeState
from core.event_bus import EventBus, ZaramEvent
from core.capability_router import CapabilityRouter, IntentBasedRouter


class CapabilityRuntime(Runtime):
    """Manages capability discovery, scoring, and routing.

    The Capability Runtime is the authority on which capabilities exist
    in the system and which runtime owns each. It wraps the
    CapabilityRouter and publishes capability events through the
    Event Bus.

    All communication is through the Event Bus — no direct runtime imports.
    """

    def __init__(self, event_bus: EventBus, router: CapabilityRouter | None = None):
        self._event_bus = event_bus
        self._state = RuntimeState.UNINITIALIZED
        self._router = router or CapabilityRouter(event_bus._registry if hasattr(event_bus, "_registry") else _DummyRegistry())
        self._start_time = time.time()
        self._stats: dict[str, Any] = {
            "resolutions": 0,
            "intent_resolutions": 0,
            "cache_hits": 0,
            "failures": 0,
            "avg_resolution_ms": 0.0,
            "total_resolution_ms": 0.0,
        }
        self._resolution_times: list[float] = []
        self._capability_scores: dict[str, float] = {}

    def get_runtime_id(self) -> str:
        return "capability"

    def get_version(self) -> str:
        return "1.0.0"

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_id="capability",
            version="1.0.0",
            priority="critical",
            capabilities=[
                Capability(id="capability.resolve", runtime_id="capability", category="routing"),
                Capability(id="capability.discover", runtime_id="capability", category="routing"),
                Capability(id="capability.score", runtime_id="capability", category="routing"),
                Capability(id="capability.intent_route", runtime_id="capability", category="routing"),
            ],
            dependencies=["event_bus"],
            auto_start=True,
        )

    async def initialize(self) -> None:
        self._state = RuntimeState.INITIALIZING
        self._event_bus.subscribe("capability.resolve", self._handle_resolve)
        self._event_bus.subscribe("capability.discover", self._handle_discover)
        self._event_bus.subscribe("capability.intent_route", self._handle_intent_route)
        self._state = RuntimeState.READY
        self._event_bus.publish(ZaramEvent(
            source_runtime="capability",
            event_type="runtime.ready",
            data={"runtime_id": self.get_runtime_id()},
        ))
        print("[CapabilityRuntime] Initialized and subscribed to capability events")

    async def shutdown(self) -> None:
        self._state = RuntimeState.STOPPING
        self._state = RuntimeState.STOPPED
        print("[CapabilityRuntime] Shut down")

    def get_state(self) -> RuntimeState:
        return self._state

    def health_check(self) -> dict[str, Any]:
        return {
            "runtime_id": self.get_runtime_id(),
            "state": self._state.value,
            "uptime_seconds": time.time() - self._start_time,
            "stats": dict(self._stats),
            "capabilities": self.list_capabilities(),
        }

    def get_stats(self) -> dict[str, Any]:
        return dict(self._stats)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_router(self) -> CapabilityRouter:
        return self._router

    def resolve(self, capability_id: str) -> Runtime:
        """Resolve a capability to a runtime."""
        start = time.time()
        try:
            runtime = self._router.resolve(capability_id)
            latency = (time.time() - start) * 1000
            self._update_stats(latency, success=True)
            self._event_bus.publish(ZaramEvent(
                source_runtime="capability",
                event_type="capability.resolved",
                priority="normal",
                data={
                    "capability_id": capability_id,
                    "runtime_id": runtime.get_runtime_id(),
                    "latency_ms": latency,
                },
            ))
            return runtime
        except Exception as exc:
            latency = (time.time() - start) * 1000
            self._update_stats(latency, success=False)
            self._event_bus.publish(ZaramEvent(
                source_runtime="capability",
                event_type="capability.resolve_failed",
                priority="high",
                data={
                    "capability_id": capability_id,
                    "error": str(exc),
                    "latency_ms": latency,
                },
            ))
            raise

    def resolve_by_intent(self, intent_type: str) -> Runtime:
        """Resolve a runtime by intent type."""
        start = time.time()
        try:
            runtime = self._router.resolve_by_intent(intent_type)
            latency = (time.time() - start) * 1000
            self._stats["intent_resolutions"] += 1
            self._update_stats(latency, success=True)
            self._event_bus.publish(ZaramEvent(
                source_runtime="capability",
                event_type="capability.intent_resolved",
                priority="normal",
                data={
                    "intent_type": intent_type,
                    "runtime_id": runtime.get_runtime_id(),
                    "latency_ms": latency,
                },
            ))
            return runtime
        except Exception as exc:
            latency = (time.time() - start) * 1000
            self._update_stats(latency, success=False)
            raise

    def can_resolve(self, capability_id: str) -> bool:
        return self._router.can_resolve(capability_id)

    def list_capabilities(self) -> list[str]:
        return self._router.list_resolvable_capabilities()

    def score_capability(self, capability_id: str, context: dict[str, Any] | None = None) -> float:
        """Score a capability based on context.

        Returns a score between 0.0 and 1.0 indicating how well
        the capability matches the given context.
        """
        if not self._router.can_resolve(capability_id):
            return 0.0

        context = context or {}
        score = 0.5

        # Boost if the capability matches the intent type
        intent_type = context.get("intent_type", "")
        if intent_type:
            candidates = IntentBasedRouter.get_capability_candidates(intent_type)
            if capability_id in candidates:
                score += 0.3
                # Higher score for earlier candidates
                idx = candidates.index(capability_id)
                score += 0.1 * (len(candidates) - idx) / len(candidates)

        # Boost if preferred sources match
        preferred = context.get("preferred_sources", [])
        if preferred:
            score += 0.1

        score = min(1.0, score)
        self._capability_scores[capability_id] = score
        return score

    def get_capability_scores(self) -> dict[str, float]:
        return dict(self._capability_scores)

    def register_intent(self, intent_type: str, capability_ids: list[str]) -> None:
        """Register a new intent-to-capability mapping."""
        IntentBasedRouter.register_intent(intent_type, capability_ids)
        self._event_bus.publish(ZaramEvent(
            source_runtime="capability",
            event_type="capability.intent_registered",
            priority="normal",
            data={
                "intent_type": intent_type,
                "capability_ids": capability_ids,
            },
        ))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _update_stats(self, latency_ms: float, success: bool) -> None:
        self._stats["resolutions"] += 1
        self._stats["total_resolution_ms"] += latency_ms
        self._resolution_times.append(latency_ms)
        if len(self._resolution_times) > 100:
            self._resolution_times = self._resolution_times[-50:]
        if self._stats["resolutions"] > 0:
            self._stats["avg_resolution_ms"] = round(
                self._stats["total_resolution_ms"] / self._stats["resolutions"], 2
            )
        if not success:
            self._stats["failures"] += 1

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _handle_resolve(self, event: ZaramEvent) -> None:
        data = event.data
        capability_id = data.get("capability_id", "")
        if not capability_id:
            return
        try:
            runtime = self.resolve(capability_id)
            self._event_bus.publish(ZaramEvent(
                source_runtime="capability",
                event_type="capability.resolve_result",
                correlation_id=event.correlation_id,
                priority="normal",
                data={
                    "capability_id": capability_id,
                    "runtime_id": runtime.get_runtime_id(),
                    "success": True,
                },
            ))
        except Exception as exc:
            self._event_bus.publish(ZaramEvent(
                source_runtime="capability",
                event_type="capability.resolve_result",
                correlation_id=event.correlation_id,
                priority="high",
                data={
                    "capability_id": capability_id,
                    "success": False,
                    "error": str(exc),
                },
            ))

    def _handle_discover(self, event: ZaramEvent) -> None:
        caps = self.list_capabilities()
        self._event_bus.publish(ZaramEvent(
            source_runtime="capability",
            event_type="capability.discovered",
            correlation_id=event.correlation_id,
            priority="normal",
            data={
                "capabilities": caps,
                "count": len(caps),
            },
        ))

    def _handle_intent_route(self, event: ZaramEvent) -> None:
        data = event.data
        intent_type = data.get("intent_type", "")
        if not intent_type:
            return
        try:
            runtime = self.resolve_by_intent(intent_type)
            self._event_bus.publish(ZaramEvent(
                source_runtime="capability",
                event_type="capability.intent_routed",
                correlation_id=event.correlation_id,
                priority="normal",
                data={
                    "intent_type": intent_type,
                    "runtime_id": runtime.get_runtime_id(),
                    "success": True,
                },
            ))
        except Exception as exc:
            self._event_bus.publish(ZaramEvent(
                source_runtime="capability",
                event_type="capability.intent_routed",
                correlation_id=event.correlation_id,
                priority="high",
                data={
                    "intent_type": intent_type,
                    "success": False,
                    "error": str(exc),
                },
            ))


class _DummyRegistry:
    """Fallback registry when the event bus doesn't expose one."""

    def get_runtime_for_capability(self, capability_id: str) -> Runtime:
        raise KeyError(f"No runtime for capability '{capability_id}'")

    def get_runtime(self, runtime_id: str) -> Runtime:
        raise KeyError(f"No runtime '{runtime_id}'")

    def list_capabilities(self) -> list[Capability]:
        return []

    def list_runtimes(self) -> list[Runtime]:
        return []

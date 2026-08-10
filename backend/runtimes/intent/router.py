from __future__ import annotations

import time
from typing import Any

from core.contracts import Runtime, RuntimeMetadata, Capability, RuntimeState
from core.event_bus import EventBus, ZaramEvent

from .confidence_engine import ConfidenceEngine, SourceQuality
from .query_envelope import QueryEnvelope, IntentType, TemporalSensitivity
from .temporal_classifier import TemporalClassifier, ClassificationResult


class IntentRouter(Runtime):
    """Routes incoming intents to the appropriate runtime via the Event Bus.

    The Intent Router subscribes to ``intent.received`` events, classifies
    the query using the TemporalClassifier, evaluates confidence with the
    ConfidenceEngine, wraps it in a QueryEnvelope, and publishes
    ``intent.routed`` events that downstream runtimes consume.

    All communication is through the Event Bus — no direct runtime imports.
    """

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._state = RuntimeState.UNINITIALIZED
        self._classifier = TemporalClassifier()
        self._confidence_engine = ConfidenceEngine()
        self._start_time = time.time()
        self._stats: dict[str, Any] = {
            "intents_routed": 0,
            "time_sensitive": 0,
            "timeless": 0,
            "mixed": 0,
            "avg_confidence": 0.0,
            "total_confidence": 0.0,
        }
        self._classification_cache: dict[str, ClassificationResult] = {}

    def get_runtime_id(self) -> str:
        return "intent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_id="intent",
            version="1.0.0",
            priority="critical",
            capabilities=[
                Capability(id="intent.route", runtime_id="intent", category="routing"),
                Capability(id="intent.classify", runtime_id="intent", category="routing"),
                Capability(id="intent.confidence", runtime_id="intent", category="routing"),
            ],
            dependencies=["event_bus"],
            auto_start=True,
        )

    async def initialize(self) -> None:
        self._state = RuntimeState.INITIALIZING
        self._event_bus.subscribe("intent.received", self._handle_intent_received)
        self._event_bus.subscribe("discovery.confidence_update", self._handle_confidence_update)
        self._state = RuntimeState.READY
        self._event_bus.publish(ZaramEvent(
            source_runtime="intent",
            event_type="runtime.ready",
            data={"runtime_id": self.get_runtime_id()},
        ))
        print("[IntentRouter] Initialized and subscribed to intent.received")

    async def shutdown(self) -> None:
        self._state = RuntimeState.STOPPING
        self._state = RuntimeState.STOPPED
        print("[IntentRouter] Shut down")

    def get_state(self) -> RuntimeState:
        return self._state

    def health_check(self) -> dict[str, Any]:
        return {
            "runtime_id": self.get_runtime_id(),
            "state": self._state.value,
            "uptime_seconds": time.time() - self._start_time,
            "stats": dict(self._stats),
            "sources": {
                sid: q.health_score for sid, q in self._confidence_engine.list_sources().items()
            },
        }

    def get_stats(self) -> dict[str, Any]:
        return dict(self._stats)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(self, query: str, intent_type: IntentType = IntentType.UNKNOWN, **kwargs: Any) -> QueryEnvelope:
        """Route a query and return the QueryEnvelope.

        This is the synchronous entry point for routing. It classifies the
        query, evaluates confidence, and publishes a routing event.
        """
        envelope = QueryEnvelope.from_query(query, intent_type=intent_type, **kwargs)
        classification = self._classify(envelope.query)
        enriched = QueryEnvelope(
            query=envelope.query,
            correlation_id=envelope.correlation_id,
            timestamp=envelope.timestamp,
            intent_type=envelope.intent_type,
            temporal_sensitivity=classification.sensitivity,
            confidence_threshold=envelope.confidence_threshold,
            preferred_sources=envelope.preferred_sources,
            max_results=envelope.max_results,
            session_id=envelope.session_id,
            user_id=envelope.user_id,
            metadata={
                **envelope.metadata,
                "classification": classification.to_dict(),
            },
        )
        self._process_envelope(enriched)
        return enriched

    def register_source(self, source_id: str, quality: SourceQuality) -> None:
        self._confidence_engine.register_source(source_id, quality)

    def get_classifier(self) -> TemporalClassifier:
        return self._classifier

    def get_confidence_engine(self) -> ConfidenceEngine:
        return self._confidence_engine

    # ------------------------------------------------------------------
    # Internal processing
    # ------------------------------------------------------------------

    def _process_envelope(self, envelope: QueryEnvelope) -> None:
        classification = self._classify(envelope.query)
        if "classification" not in envelope.metadata:
            envelope_with_sensitivity = QueryEnvelope(
                query=envelope.query,
                correlation_id=envelope.correlation_id,
                timestamp=envelope.timestamp,
                intent_type=envelope.intent_type,
                temporal_sensitivity=classification.sensitivity,
                confidence_threshold=envelope.confidence_threshold,
                preferred_sources=envelope.preferred_sources,
                max_results=envelope.max_results,
                session_id=envelope.session_id,
                user_id=envelope.user_id,
                metadata={
                    **envelope.metadata,
                    "classification": classification.to_dict(),
                },
            )
        else:
            envelope_with_sensitivity = envelope

        confidence = self._confidence_engine.evaluate(
            results=[],
            sources_consulted=envelope.preferred_sources or None,
            max_results=envelope.max_results,
            query_age_seconds=envelope.age_seconds,
        )

        self._update_stats(classification, confidence.overall)

        self._event_bus.publish(ZaramEvent(
            source_runtime="intent",
            event_type="intent.routed",
            priority="high",
            correlation_id=envelope.correlation_id,
            data={
                "envelope": envelope_with_sensitivity.to_dict(),
                "classification": classification.to_dict(),
                "confidence": confidence.to_dict(),
                "target_runtime": self._determine_target_runtime(envelope_with_sensitivity, classification),
            },
        ))

    def _classify(self, query: str) -> ClassificationResult:
        if query in self._classification_cache:
            return self._classification_cache[query]
        result = self._classifier.classify(query)
        if len(self._classification_cache) < 1000:
            self._classification_cache[query] = result
        return result

    def _determine_target_runtime(
        self,
        envelope: QueryEnvelope,
        classification: ClassificationResult,
    ) -> str:
        """Determine which runtime should handle this intent."""
        if envelope.intent_type == IntentType.SEARCH:
            if classification.sensitivity == TemporalSensitivity.TIME_SENSITIVE:
                return "knowledge"
            return "knowledge"
        if envelope.intent_type == IntentType.DISCOVERY:
            return "discovery"
        if envelope.intent_type == IntentType.AGENT:
            return "agent"
        if envelope.intent_type == IntentType.CONVERSATION:
            return "memory"
        if envelope.intent_type == IntentType.REASONING:
            return "models"
        if envelope.intent_type == IntentType.CREATIVE:
            return "models"
        if envelope.intent_type == IntentType.TASK:
            return "agent"
        return "models"

    def _update_stats(self, classification: ClassificationResult, confidence: float) -> None:
        self._stats["intents_routed"] += 1
        self._stats["total_confidence"] += confidence
        if self._stats["intents_routed"] > 0:
            self._stats["avg_confidence"] = round(
                self._stats["total_confidence"] / self._stats["intents_routed"], 4
            )
        if classification.sensitivity == TemporalSensitivity.TIME_SENSITIVE:
            self._stats["time_sensitive"] += 1
        elif classification.sensitivity == TemporalSensitivity.TIMELESS:
            self._stats["timeless"] += 1
        else:
            self._stats["mixed"] += 1

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _handle_intent_received(self, event: ZaramEvent) -> None:
        data = event.data
        query = data.get("query", "")
        intent_type_str = data.get("intent_type", IntentType.UNKNOWN.value)
        try:
            intent_type = IntentType(intent_type_str)
        except ValueError:
            intent_type = IntentType.UNKNOWN

        envelope = QueryEnvelope.from_query(
            query=query,
            intent_type=intent_type,
            correlation_id=event.correlation_id or data.get("correlation_id", ""),
            session_id=data.get("session_id"),
            user_id=data.get("user_id"),
            max_results=data.get("max_results", 10),
            confidence_threshold=data.get("confidence_threshold", 0.7),
            preferred_sources=data.get("preferred_sources", []),
        )
        self._process_envelope(envelope)

    def _handle_confidence_update(self, event: ZaramEvent) -> None:
        data = event.data
        source_id = data.get("source_id", "")
        if data.get("success"):
            self._confidence_engine.update_source_success(
                source_id,
                latency_ms=data.get("latency_ms", 0.0),
            )
        else:
            self._confidence_engine.update_source_failure(source_id)

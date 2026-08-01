"""Tests for the Capability Runtime and enhanced Capability Router."""
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parents[1]
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

import pytest

from core.event_bus import EventBus, ZaramEvent
from core.contracts import Runtime, RuntimeMetadata, Capability, RuntimeState
from core.registry import RuntimeRegistry
from core.capability_router import CapabilityRouter, IntentBasedRouter, CapabilityResolutionError
from runtimes.capability import CapabilityRuntime


class _FakeRuntime:
    """Minimal Runtime for testing."""

    def __init__(self, runtime_id: str, capabilities: list[str]):
        self._runtime_id = runtime_id
        self._capabilities = capabilities

    def get_runtime_id(self) -> str:
        return self._runtime_id

    def get_version(self) -> str:
        return "1.0.0"

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_id=self._runtime_id,
            version="1.0.0",
            capabilities=[Capability(id=c, runtime_id=self._runtime_id) for c in self._capabilities],
        )

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def get_state(self) -> RuntimeState:
        return RuntimeState.READY

    def health_check(self) -> dict:
        return {"state": "ready"}


class _FakeRegistry:
    """Minimal registry for testing."""

    def __init__(self):
        self._runtimes: dict[str, Runtime] = {}
        self._capabilities: dict[str, str] = {}

    def register(self, runtime: Runtime) -> None:
        metadata = runtime.get_metadata()
        self._runtimes[metadata.runtime_id] = runtime
        for cap in metadata.capabilities:
            self._capabilities[cap.id] = metadata.runtime_id

    def get_runtime(self, runtime_id: str) -> Runtime:
        if runtime_id not in self._runtimes:
            raise KeyError(f"Runtime {runtime_id} not found")
        return self._runtimes[runtime_id]

    def get_runtime_for_capability(self, capability_id: str) -> Runtime:
        runtime_id = self._capabilities.get(capability_id)
        if not runtime_id:
            raise KeyError(f"No runtime for capability {capability_id}")
        return self.get_runtime(runtime_id)

    def list_capabilities(self) -> list[Capability]:
        caps = []
        for runtime in self._runtimes.values():
            caps.extend(runtime.get_metadata().capabilities)
        return caps

    def list_runtimes(self) -> list[Runtime]:
        return list(self._runtimes.values())


# ---------------------------------------------------------------------------
# IntentBasedRouter tests
# ---------------------------------------------------------------------------

class TestIntentBasedRouter:
    def test_get_capability_candidates_search(self):
        candidates = IntentBasedRouter.get_capability_candidates("search")
        assert "knowledge.search" in candidates

    def test_get_capability_candidates_reasoning(self):
        candidates = IntentBasedRouter.get_capability_candidates("reasoning")
        assert "reasoning.generate" in candidates

    def test_get_capability_candidates_unknown(self):
        candidates = IntentBasedRouter.get_capability_candidates("unknown_intent")
        assert candidates == ["reasoning.generate"]

    def test_register_intent(self):
        IntentBasedRouter.register_intent("custom", ["custom.cap"])
        candidates = IntentBasedRouter.get_capability_candidates("custom")
        assert candidates == ["custom.cap"]


# ---------------------------------------------------------------------------
# CapabilityRouter tests
# ---------------------------------------------------------------------------

class TestCapabilityRouter:
    def setup_method(self):
        self.registry = _FakeRegistry()
        self.registry.register(_FakeRuntime("models", ["reasoning.generate", "vision.analyze"]))
        self.registry.register(_FakeRuntime("knowledge", ["knowledge.search"]))
        self.registry.register(_FakeRuntime("agent", ["agent.execute"]))
        self.router = CapabilityRouter(self.registry)

    def test_resolve_existing_capability(self):
        runtime = self.router.resolve("reasoning.generate")
        assert runtime.get_runtime_id() == "models"

    def test_resolve_unknown_capability_raises(self):
        with pytest.raises(CapabilityResolutionError):
            self.router.resolve("nonexistent.cap")

    def test_try_resolve_returns_none(self):
        result = self.router.try_resolve("nonexistent.cap")
        assert result is None

    def test_try_resolve_returns_runtime(self):
        result = self.router.try_resolve("reasoning.generate")
        assert result is not None
        assert result.get_runtime_id() == "models"

    def test_can_resolve(self):
        assert self.router.can_resolve("reasoning.generate") is True
        assert self.router.can_resolve("nonexistent.cap") is False

    def test_resolve_all(self):
        results = self.router.resolve_all(["reasoning.generate", "knowledge.search", "nonexistent.cap"])
        assert len(results) == 2
        assert results["reasoning.generate"].get_runtime_id() == "models"
        assert results["knowledge.search"].get_runtime_id() == "knowledge"

    def test_get_capability_info(self):
        cap = self.router.get_capability_info("reasoning.generate")
        assert cap is not None
        assert cap.id == "reasoning.generate"

    def test_list_resolvable_capabilities(self):
        caps = self.router.list_resolvable_capabilities()
        assert "reasoning.generate" in caps
        assert "knowledge.search" in caps
        assert "agent.execute" in caps

    def test_invalidate_cache(self):
        self.router.resolve("reasoning.generate")
        assert "reasoning.generate" in self.router._cache
        self.router.invalidate_cache()
        assert len(self.router._cache) == 0

    def test_get_resolution_stats(self):
        stats = self.router.get_resolution_stats()
        assert stats["total_capabilities"] == 4
        assert "cached_lookups" in stats

    def test_resolve_by_intent_search(self):
        runtime = self.router.resolve_by_intent("search")
        assert runtime.get_runtime_id() == "knowledge"

    def test_resolve_by_intent_reasoning(self):
        runtime = self.router.resolve_by_intent("reasoning")
        assert runtime.get_runtime_id() == "models"

    def test_resolve_by_intent_agent(self):
        runtime = self.router.resolve_by_intent("agent")
        assert runtime.get_runtime_id() == "agent"

    def test_resolve_by_intent_unknown_raises(self):
        IntentBasedRouter.register_intent("nonexistent_intent_xyz", ["nonexistent.cap.xyz"])
        with pytest.raises(CapabilityResolutionError):
            self.router.resolve_by_intent("nonexistent_intent_xyz")

    def test_try_resolve_by_intent(self):
        result = self.router.try_resolve_by_intent("search")
        assert result is not None
        assert result.get_runtime_id() == "knowledge"

    def test_try_resolve_by_intent_unknown(self):
        IntentBasedRouter.register_intent("nonexistent_intent_xyz", ["nonexistent.cap.xyz"])
        result = self.router.try_resolve_by_intent("nonexistent_intent_xyz")
        assert result is None


# ---------------------------------------------------------------------------
# CapabilityRuntime tests
# ---------------------------------------------------------------------------

class TestCapabilityRuntime:
    def setup_method(self):
        self.event_bus = EventBus()
        self.registry = _FakeRegistry()
        self.registry.register(_FakeRuntime("models", ["reasoning.generate"]))
        self.registry.register(_FakeRuntime("knowledge", ["knowledge.search"]))
        self.router = CapabilityRouter(self.registry)
        self.runtime = CapabilityRuntime(self.event_bus, self.router)

    def test_get_runtime_id(self):
        assert self.runtime.get_runtime_id() == "capability"

    def test_get_metadata(self):
        meta = self.runtime.get_metadata()
        assert meta.runtime_id == "capability"
        assert len(meta.capabilities) > 0

    def test_get_state(self):
        assert self.runtime.get_state() == RuntimeState.UNINITIALIZED

    def test_health_check(self):
        health = self.runtime.health_check()
        assert health["runtime_id"] == "capability"
        assert "state" in health
        assert "capabilities" in health

    def test_get_stats(self):
        stats = self.runtime.get_stats()
        assert "resolutions" in stats
        assert "intent_resolutions" in stats

    def test_get_router(self):
        assert self.runtime.get_router() is self.router

    def test_resolve(self):
        runtime = self.runtime.resolve("reasoning.generate")
        assert runtime.get_runtime_id() == "models"

    def test_resolve_publishes_event(self):
        events = []
        self.event_bus.subscribe("capability.resolved", events.append)
        self.runtime.resolve("reasoning.generate")
        assert len(events) == 1
        assert events[0].data["capability_id"] == "reasoning.generate"

    def test_resolve_unknown_raises(self):
        with pytest.raises(Exception):
            self.runtime.resolve("nonexistent.cap")

    def test_resolve_by_intent(self):
        runtime = self.runtime.resolve_by_intent("search")
        assert runtime.get_runtime_id() == "knowledge"

    def test_can_resolve(self):
        assert self.runtime.can_resolve("reasoning.generate") is True
        assert self.runtime.can_resolve("nonexistent") is False

    def test_list_capabilities(self):
        caps = self.runtime.list_capabilities()
        assert "reasoning.generate" in caps
        assert "knowledge.search" in caps

    def test_score_capability(self):
        score = self.runtime.score_capability("reasoning.generate", {"intent_type": "reasoning"})
        assert score > 0.5

    def test_score_capability_unknown(self):
        score = self.runtime.score_capability("nonexistent.cap")
        assert score == 0.0

    def test_get_capability_scores(self):
        self.runtime.score_capability("reasoning.generate", {"intent_type": "reasoning"})
        scores = self.runtime.get_capability_scores()
        assert "reasoning.generate" in scores

    def test_register_intent(self):
        events = []
        self.event_bus.subscribe("capability.intent_registered", events.append)
        self.runtime.register_intent("custom", ["custom.cap"])
        assert len(events) == 1
        candidates = IntentBasedRouter.get_capability_candidates("custom")
        assert candidates == ["custom.cap"]

    @pytest.mark.asyncio
    async def test_handle_resolve_event(self):
        await self.runtime.initialize()
        events = []
        self.event_bus.subscribe("capability.resolve_result", events.append)
        self.event_bus.publish(ZaramEvent(
            source_runtime="test",
            event_type="capability.resolve",
            data={"capability_id": "reasoning.generate"},
        ))
        assert len(events) == 1
        assert events[0].data["success"] is True

    @pytest.mark.asyncio
    async def test_handle_discover_event(self):
        await self.runtime.initialize()
        events = []
        self.event_bus.subscribe("capability.discovered", events.append)
        self.event_bus.publish(ZaramEvent(
            source_runtime="test",
            event_type="capability.discover",
            data={},
        ))
        assert len(events) == 1
        assert "capabilities" in events[0].data

    @pytest.mark.asyncio
    async def test_handle_intent_route_event(self):
        await self.runtime.initialize()
        events = []
        self.event_bus.subscribe("capability.intent_routed", events.append)
        self.event_bus.publish(ZaramEvent(
            source_runtime="test",
            event_type="capability.intent_route",
            data={"intent_type": "search"},
        ))
        assert len(events) == 1
        assert events[0].data["success"] is True

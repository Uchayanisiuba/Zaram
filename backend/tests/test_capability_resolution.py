# backend/tests/test_capability_resolution.py
"""Unit tests for the CapabilityRouter (Capability Resolution)."""
from __future__ import annotations

import pytest

from core.contracts import (
    Capability,
    CapabilityLocality,
    Runtime,
    RuntimeMetadata,
    RuntimeState,
)
from core.event_bus import EventBus
from core.registry import RuntimeRegistry
from core.capability_router import CapabilityRouter, CapabilityResolutionError


class _FakeRuntime:
    def __init__(self, runtime_id="fake", capabilities=None):
        self._runtime_id = runtime_id
        self._capabilities = capabilities or [
            Capability(id="test.cap", runtime_id=runtime_id),
        ]

    def get_runtime_id(self):
        return self._runtime_id

    def get_metadata(self):
        return RuntimeMetadata(
            runtime_id=self._runtime_id,
            version="1.0.0",
            capabilities=self._capabilities,
        )

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    def get_state(self):
        return RuntimeState.READY

    def health_check(self):
        return {"state": "ready"}


@pytest.fixture
def router():
    registry = RuntimeRegistry(EventBus())
    registry.register(_FakeRuntime())
    return CapabilityRouter(registry)


class TestCapabilityResolution:
    def test_resolve_capability(self, router):
        runtime = router.resolve("test.cap")
        assert runtime.get_runtime_id() == "fake"

    def test_resolve_unknown_capability(self, router):
        with pytest.raises(CapabilityResolutionError, match="No runtime found"):
            router.resolve("nonexistent.cap")

    def test_try_resolve_success(self, router):
        runtime = router.try_resolve("test.cap")
        assert runtime is not None
        assert runtime.get_runtime_id() == "fake"

    def test_try_resolve_failure(self, router):
        runtime = router.try_resolve("nonexistent.cap")
        assert runtime is None

    def test_can_resolve(self, router):
        assert router.can_resolve("test.cap") is True
        assert router.can_resolve("nonexistent.cap") is False


class TestCapabilityRouterMultiple:
    def test_resolve_all(self):
        registry = RuntimeRegistry(EventBus())
        rt1 = _FakeRuntime("rt1", [Capability(id="cap1", runtime_id="rt1")])
        rt2 = _FakeRuntime("rt2", [Capability(id="cap2", runtime_id="rt2")])
        registry.register(rt1)
        registry.register(rt2)
        router = CapabilityRouter(registry)

        results = router.resolve_all(["cap1", "cap2", "nonexistent"])
        assert len(results) == 2
        assert results["cap1"].get_runtime_id() == "rt1"
        assert results["cap2"].get_runtime_id() == "rt2"

    def test_get_capability_info(self, router):
        info = router.get_capability_info("test.cap")
        assert info is not None
        assert info.id == "test.cap"

    def test_get_capability_info_unknown(self, router):
        info = router.get_capability_info("nonexistent.cap")
        assert info is None

    def test_list_resolvable_capabilities(self, router):
        caps = router.list_resolvable_capabilities()
        assert "test.cap" in caps

    def test_invalidate_cache(self, router):
        router.resolve("test.cap")  # Populate cache
        router.invalidate_cache()
        # Should still work after cache invalidation
        runtime = router.resolve("test.cap")
        assert runtime.get_runtime_id() == "fake"

    def test_get_resolution_stats(self, router):
        router.resolve("test.cap")
        stats = router.get_resolution_stats()
        assert stats["total_capabilities"] == 1
        assert stats["cached_lookups"] >= 1

# backend/tests/test_capability_registry.py
"""Unit tests for the RuntimeRegistry (Capability Registry)."""
from __future__ import annotations

import pytest

from core.contracts import (
    Capability,
    CapabilityLocality,
    Runtime,
    RuntimeMetadata,
    RuntimeState,
    RestartPolicy,
)
from core.event_bus import EventBus
from core.registry import RuntimeRegistry


class _FakeRuntime:
    """Minimal Runtime implementation for testing."""

    def __init__(self, runtime_id="fake", capabilities=None, dependencies=None):
        self._runtime_id = runtime_id
        self._capabilities = capabilities or [
            Capability(id="test.cap", runtime_id=runtime_id),
        ]
        self._dependencies = dependencies or []
        self._state = RuntimeState.UNINITIALIZED

    def get_runtime_id(self):
        return self._runtime_id

    def get_metadata(self):
        return RuntimeMetadata(
            runtime_id=self._runtime_id,
            version="1.0.0",
            priority="normal",
            capabilities=self._capabilities,
            dependencies=self._dependencies,
            auto_start=True,
            restart_policy=RestartPolicy.ON_FAILURE,
        )

    async def initialize(self):
        self._state = RuntimeState.READY

    async def shutdown(self):
        self._state = RuntimeState.STOPPED

    def get_state(self):
        return self._state

    def health_check(self):
        return {"runtime_id": self._runtime_id, "state": self._state.value, "healthy": True}


@pytest.fixture
def registry():
    return RuntimeRegistry(EventBus())


@pytest.fixture
def registered_registry(registry):
    runtime = _FakeRuntime()
    registry.register(runtime)
    return registry


class TestRegistryRegistration:
    def test_register_runtime(self, registry):
        runtime = _FakeRuntime()
        registry.register(runtime)
        assert registry.is_registered("fake") is True

    def test_register_duplicate_raises(self, registered_registry):
        runtime = _FakeRuntime()
        with pytest.raises(ValueError, match="already registered"):
            registered_registry.register(runtime)

    def test_unregister_runtime(self, registered_registry):
        assert registered_registry.unregister("fake") is True
        assert registered_registry.is_registered("fake") is False

    def test_unregister_nonexistent(self, registry):
        assert registry.unregister("nonexistent") is False

    def test_is_registered(self, registry):
        assert registry.is_registered("fake") is False
        registry.register(_FakeRuntime())
        assert registry.is_registered("fake") is True


class TestRegistryLookup:
    def test_get_runtime(self, registered_registry):
        runtime = registered_registry.get_runtime("fake")
        assert runtime.get_runtime_id() == "fake"

    def test_get_runtime_not_found(self, registry):
        with pytest.raises(KeyError):
            registry.get_runtime("nonexistent")

    def test_get_runtime_for_capability(self, registered_registry):
        runtime = registered_registry.get_runtime_for_capability("test.cap")
        assert runtime.get_runtime_id() == "fake"

    def test_get_runtime_for_unknown_capability(self, registry):
        with pytest.raises(KeyError):
            registry.get_runtime_for_capability("nonexistent.cap")

    def test_get_metadata(self, registered_registry):
        metadata = registered_registry.get_metadata("fake")
        assert metadata.runtime_id == "fake"
        assert len(metadata.capabilities) == 1

    def test_get_metadata_not_found(self, registry):
        with pytest.raises(KeyError):
            registry.get_metadata("nonexistent")


class TestRegistryCapabilities:
    def test_list_capabilities(self, registered_registry):
        caps = registered_registry.list_capabilities()
        assert len(caps) == 1
        assert caps[0].id == "test.cap"

    def test_list_capabilities_for_runtime(self, registered_registry):
        caps = registered_registry.list_capabilities_for_runtime("fake")
        assert len(caps) == 1

    def test_list_capabilities_empty(self, registry):
        caps = registry.list_capabilities()
        assert len(caps) == 0

    def test_list_runtimes(self, registered_registry):
        runtimes = registered_registry.list_runtimes()
        assert "fake" in runtimes

    def test_list_runtimes_empty(self, registry):
        runtimes = registry.list_runtimes()
        assert len(runtimes) == 0


class TestRegistryState:
    def test_get_state(self, registered_registry):
        state = registered_registry.get_state("fake")
        assert state == RuntimeState.UNINITIALIZED

    def test_set_state(self, registered_registry):
        registered_registry.set_state("fake", RuntimeState.READY)
        assert registered_registry.get_state("fake") == RuntimeState.READY

    def test_list_runtimes_by_state(self, registered_registry):
        registered_registry.set_state("fake", RuntimeState.RUNNING)
        running = registered_registry.list_runtimes_by_state(RuntimeState.RUNNING)
        assert "fake" in running

    def test_get_state_unknown_runtime(self, registry):
        state = registry.get_state("nonexistent")
        assert state == RuntimeState.UNINITIALIZED


class TestRegistryHealth:
    def test_get_system_health(self, registered_registry):
        health = registered_registry.get_system_health()
        assert "fake" in health
        assert health["fake"]["state"] == RuntimeState.UNINITIALIZED.value
        assert "capabilities" in health["fake"]

    def test_get_system_health_empty(self, registry):
        health = registry.get_system_health()
        assert len(health) == 0

    def test_get_capability_index(self, registered_registry):
        index = registered_registry.get_capability_index()
        assert "test.cap" in index
        assert index["test.cap"] == "fake"


class TestRegistryMultipleRuntimes:
    def test_register_multiple(self, registry):
        rt1 = _FakeRuntime("rt1", [Capability(id="cap1", runtime_id="rt1")])
        rt2 = _FakeRuntime("rt2", [Capability(id="cap2", runtime_id="rt2")])
        registry.register(rt1)
        registry.register(rt2)
        assert len(registry.list_runtimes()) == 2
        assert len(registry.list_capabilities()) == 2

    def test_dependencies_tracked(self, registry):
        rt = _FakeRuntime("rt1", dependencies=["dep1", "dep2"])
        registry.register(rt)
        metadata = registry.get_metadata("rt1")
        assert metadata.dependencies == ["dep1", "dep2"]

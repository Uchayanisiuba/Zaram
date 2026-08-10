# backend/core/registry.py
"""RuntimeRegistry — the kernel's capability and runtime registry.

The registry is the single source of truth for:
- Which runtimes are registered
- Which capabilities each runtime provides
- Runtime metadata (dependencies, priority, restart policy)

All capability resolution flows through the registry.  No runtime
directly imports or calls another runtime.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from core.contracts import (
    Capability,
    Runtime,
    RuntimeMetadata,
    RuntimeState,
)
from core.event_bus import EventBus, ZaramEvent

logger = logging.getLogger(__name__)


class RuntimeRegistry:
    """Central registry for runtimes and their capabilities.

    The registry stores runtime instances, indexes their capabilities,
    and provides lookup methods for the CapabilityRouter.  It also
    tracks runtime lifecycle states and publishes events when
    runtimes are registered or their state changes.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._runtimes: dict[str, Runtime] = {}
        self._capabilities: dict[str, str] = {}  # capability_id -> runtime_id
        self._capability_index: dict[str, list[Capability]] = {}  # runtime_id -> capabilities
        self._metadata: dict[str, RuntimeMetadata] = {}
        self._states: dict[str, RuntimeState] = {}
        self._event_bus = event_bus
        self._registered_at: dict[str, float] = {}
        self._setup_event_listeners()

    def _setup_event_listeners(self) -> None:
        self._event_bus.subscribe("runtime.health", self._handle_health_event)
        self._event_bus.subscribe("runtime.degraded", self._handle_degraded_event)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, runtime: Runtime) -> None:
        """Register a runtime and index its capabilities."""
        metadata = runtime.get_metadata()
        if metadata.runtime_id in self._runtimes:
            raise ValueError(f"Runtime {metadata.runtime_id} already registered.")

        self._runtimes[metadata.runtime_id] = runtime
        self._metadata[metadata.runtime_id] = metadata
        self._states[metadata.runtime_id] = RuntimeState.UNINITIALIZED
        self._registered_at[metadata.runtime_id] = time.time()

        caps: list[Capability] = []
        for cap in metadata.capabilities:
            self._capabilities[cap.id] = metadata.runtime_id
            caps.append(cap)
        self._capability_index[metadata.runtime_id] = caps

        logger.info(
            "Registry: registered %s with %d capabilities",
            metadata.runtime_id,
            len(metadata.capabilities),
        )
        self._publish("runtime.registered", {
            "runtime_id": metadata.runtime_id,
            "capabilities": [c.id for c in metadata.capabilities],
            "dependencies": metadata.dependencies,
        })

    def unregister(self, runtime_id: str) -> bool:
        """Unregister a runtime and remove its capability index entries."""
        if runtime_id not in self._runtimes:
            return False
        self._runtimes.pop(runtime_id)
        metadata = self._metadata.pop(runtime_id, None)
        self._states.pop(runtime_id, None)
        self._registered_at.pop(runtime_id, None)
        self._capability_index.pop(runtime_id, None)

        if metadata:
            for cap in metadata.capabilities:
                self._capabilities.pop(cap.id, None)

        logger.info("Registry: unregistered %s", runtime_id)
        self._publish("runtime.unregistered", {"runtime_id": runtime_id})
        return True

    def is_registered(self, runtime_id: str) -> bool:
        return runtime_id in self._runtimes

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_runtime(self, runtime_id: str) -> Runtime:
        """Get a runtime by ID."""
        if runtime_id not in self._runtimes:
            raise KeyError(f"Runtime {runtime_id} not found.")
        return self._runtimes[runtime_id]

    def get_runtime_for_capability(self, capability_id: str) -> Runtime:
        """Get the runtime that provides a given capability."""
        runtime_id = self._capabilities.get(capability_id)
        if not runtime_id:
            raise KeyError(f"No runtime found for capability {capability_id}.")
        return self.get_runtime(runtime_id)

    def get_metadata(self, runtime_id: str) -> RuntimeMetadata:
        """Get metadata for a registered runtime."""
        metadata = self._metadata.get(runtime_id)
        if metadata is None:
            raise KeyError(f"Runtime {runtime_id} not found.")
        return metadata

    def get_state(self, runtime_id: str) -> RuntimeState:
        """Get the current lifecycle state of a runtime."""
        return self._states.get(runtime_id, RuntimeState.UNINITIALIZED)

    def set_state(self, runtime_id: str, state: RuntimeState) -> None:
        """Update the lifecycle state of a runtime and publish an event."""
        old_state = self._states.get(runtime_id)
        self._states[runtime_id] = state
        if old_state != state:
            self._publish(f"runtime.{state.value}", {
                "runtime_id": runtime_id,
                "old_state": old_state.value if old_state else "unknown",
                "new_state": state.value,
            })

    # ------------------------------------------------------------------
    # Capability queries
    # ------------------------------------------------------------------

    def list_capabilities(self) -> list[Capability]:
        """List all capabilities across all registered runtimes."""
        caps: list[Capability] = []
        for runtime in self._runtimes.values():
            caps.extend(runtime.get_metadata().capabilities)
        return caps

    def list_capabilities_for_runtime(self, runtime_id: str) -> list[Capability]:
        """List capabilities provided by a specific runtime."""
        return list(self._capability_index.get(runtime_id, []))

    def list_runtimes(self) -> list[str]:
        """List all registered runtime IDs."""
        return list(self._runtimes.keys())

    def list_runtimes_by_state(self, state: RuntimeState) -> list[str]:
        """List runtimes in a specific state."""
        return [rid for rid, s in self._states.items() if s == state]

    def get_all_metadata(self) -> dict[str, RuntimeMetadata]:
        """Get metadata for all registered runtimes."""
        return dict(self._metadata)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def get_system_health(self) -> dict[str, Any]:
        """Get health status for all runtimes."""
        return {
            rid: {
                "state": self._states.get(rid, RuntimeState.UNINITIALIZED).value,
                "runtime_id": rid,
                "uptime_seconds": time.time() - self._registered_at.get(rid, time.time()),
                "capabilities": [c.id for c in self._capability_index.get(rid, [])],
            }
            for rid in self._runtimes
        }

    def get_capability_index(self) -> dict[str, str]:
        """Return the full capability → runtime_id mapping."""
        return dict(self._capabilities)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _handle_health_event(self, event: ZaramEvent) -> None:
        runtime_id = event.data.get("runtime_id")
        if runtime_id and runtime_id in self._runtimes:
            runtime = self._runtimes[runtime_id]
            try:
                health = runtime.health_check()
                if isinstance(health, dict):
                    state = health.get("state")
                    if state:
                        self._states[runtime_id] = RuntimeState(state)
            except Exception as exc:
                logger.warning("Registry: health check failed for %s: %s", runtime_id, exc)

    def _handle_degraded_event(self, event: ZaramEvent) -> None:
        runtime_id = event.source_runtime
        logger.warning("Registry: Runtime %s is DEGRADED.", runtime_id)
        if runtime_id in self._states:
            self._states[runtime_id] = RuntimeState.DEGRADED

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _publish(self, event_type: str, data: dict[str, Any]) -> None:
        self._event_bus.publish(ZaramEvent(
            source_runtime="registry",
            event_type=event_type,
            data=data,
        ))

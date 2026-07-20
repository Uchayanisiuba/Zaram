# backend/core/registry.py
from typing import Dict, List, Any
from .contracts import Runtime, RuntimeMetadata, Capability, RuntimeState
from .event_bus import EventBus, ZaramEvent

class RuntimeRegistry:
    def __init__(self, event_bus: EventBus):
        self._runtimes: Dict[str, Runtime] = {}
        self._capabilities: Dict[str, str] = {}  # capability_id -> runtime_id
        self._event_bus = event_bus
        self._setup_event_listeners()

    def _setup_event_listeners(self):
        self._event_bus.subscribe("runtime.health", self._handle_health_event)
        self._event_bus.subscribe("runtime.degraded", self._handle_degraded_event)

    def register(self, runtime: Runtime):
        metadata = runtime.get_metadata()
        if metadata.runtime_id in self._runtimes:
            raise ValueError(f"Runtime {metadata.runtime_id} already registered.")
        self._runtimes[metadata.runtime_id] = runtime
        for cap in metadata.capabilities:
            self._capabilities[cap.id] = metadata.runtime_id
        print(f"[Registry] Registered {metadata.runtime_id} with {len(metadata.capabilities)} capabilities.")

    def get_runtime(self, runtime_id: str) -> Runtime:
        if runtime_id not in self._runtimes:
            raise KeyError(f"Runtime {runtime_id} not found.")
        return self._runtimes[runtime_id]

    def get_runtime_for_capability(self, capability_id: str) -> Runtime:
        runtime_id = self._capabilities.get(capability_id)
        if not runtime_id:
            raise KeyError(f"No runtime found for capability {capability_id}.")
        return self.get_runtime(runtime_id)

    def list_capabilities(self) -> List[Capability]:
        caps = []
        for runtime in self._runtimes.values():
            caps.extend(runtime.get_metadata().capabilities)
        return caps

    def get_system_health(self) -> Dict[str, Any]:
        return {
            rid: runtime.get_state().value
            for rid, runtime in self._runtimes.items()
        }

    # --- Event Handlers ---
    def _handle_health_event(self, event: ZaramEvent):
        pass  # Future: Update internal health dashboard

    def _handle_degraded_event(self, event: ZaramEvent):
        print(f"[Registry] WARNING: Runtime {event.source_runtime} is DEGRADED.")
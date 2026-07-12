# backend/templates/runtime_scaffold.py
"""
Template for creating a new Zaram Runtime.
Copy this file and rename it to your specific runtime (e.g., speech_runtime.py).
"""
from typing import Any

from core.contracts import Capability, Runtime, RuntimeMetadata, RuntimeState
from core.event_bus import EventBus, ZaramEvent


class NewRuntime(Runtime):
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._state = RuntimeState.UNINITIALIZED

    def get_runtime_id(self) -> str:
        return "new_runtime"

    def get_version(self) -> str:
        return "1.0.0"

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_id="new_runtime",
            version="1.0.0",
            priority="normal",
            capabilities=[
                Capability(id="new_runtime.do_something", runtime_id="new_runtime")
            ],
            dependencies=["event_bus"],
            auto_start=True
        )

    async def initialize(self) -> None:
        self._state = RuntimeState.INITIALIZING
        # TODO: Initialize engines and services here
        self._state = RuntimeState.READY
        self._event_bus.publish(ZaramEvent(
            source_runtime="new_runtime",
            event_type="runtime.ready",
            data={"runtime_id": self.get_runtime_id()}
        ))

    async def shutdown(self) -> None:
        self._state = RuntimeState.STOPPING
        # TODO: Cleanup resources here
        self._state = RuntimeState.STOPPED

    def get_state(self) -> RuntimeState:
        return self._state

    def health_check(self) -> dict[str, Any]:
        return {
            "runtime_id": self.get_runtime_id(),
            "state": self._state.value,
            "healthy": self._state == RuntimeState.READY
        }

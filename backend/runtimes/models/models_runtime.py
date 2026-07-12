# backend/runtimes/models/models_runtime.py
from typing import Any, Dict
from core.contracts import Runtime, RuntimeMetadata, Capability, RuntimeState
from core.event_bus import EventBus, ZaramEvent
from .models_service import ModelsService
from .engines.ollama_engine import OllamaEngine

class ModelsRuntime(Runtime):
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._state = RuntimeState.UNINITIALIZED
        self._service = None

    def get_runtime_id(self) -> str:
        return "models"

    def get_version(self) -> str:
        return "1.0.0"

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_id="models",
            version="1.0.0",
            priority="critical",
            capabilities=[
                Capability(id="reasoning.generate", runtime_id="models")
            ],
            dependencies=["event_bus"],
            auto_start=True
        )

    async def initialize(self) -> None:
        self._state = RuntimeState.INITIALIZING
        
        # 1. Instantiate Engine and Service
        engine = OllamaEngine()
        self._service = ModelsService(engine)
        
        self._state = RuntimeState.READY
        
        # 2. Notify the Event Bus
        self._event_bus.publish(ZaramEvent(
            source_runtime="models",
            event_type="runtime.ready",
            data={"runtime_id": self.get_runtime_id()}
        ))
        print("[ModelsRuntime] Initialized successfully.")

    async def shutdown(self) -> None:
        self._state = RuntimeState.STOPPING
        self._service = None
        self._state = RuntimeState.STOPPED
        print("[ModelsRuntime] Shut down.")

    def get_state(self) -> RuntimeState:
        return self._state

    def health_check(self) -> Dict[str, Any]:
        return {
            "runtime_id": self.get_runtime_id(),
            "state": self._state.value,
            "healthy": self._state == RuntimeState.READY
        }
        
    def get_service(self) -> ModelsService:
        """Helper to access the service for the Capability Router."""
        return self._service
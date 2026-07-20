"""AI Garage Runtime (v0.6.0).

The Garage Runtime is Zaram's control center for AI resources. It registers
with the Kernel exactly like the other runtimes (Voice, Media, Models), owns
no concrete engine, and wires in the default model providers at startup.

New providers are added by registering an adapter — never by touching this
runtime or the manager.

Relationship::

    Kernel
      └── Garage Runtime   (discovers + catalogs AI resources)
            ├── Ollama adapter        (local LLMs)
            ├── LM Studio adapter     (local AI server)
            ├── OpenAI-compatible    (local/cloud, if configured)
            ├── Voice source          (injected: VoiceManager)
            ├── Runtime source        (injected: Kernel registry)
            ├── Personality source    (injected: characters.json)
            └── Hardware profiler    (host introspection)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from core.contracts import (
    Capability,
    RuntimeMetadata,
    RuntimeState,
)
from core.event_bus import EventBus, ZaramEvent

from .contracts import ProviderKind
from .discoverers import (
    HardwareProfilerImpl,
    LMStudioAdapter,
    OllamaAdapter,
    OpenAICompatibleAdapter,
)
from .manager import GarageManager
from .registry import GarageRegistry
from .scanner import GarageScanner

logger = logging.getLogger(__name__)

RUNTIME_ID = "garage"
RUNTIME_VERSION = "0.6.0"


class GarageRuntime:
    """Kernel-facing runtime that discovers and catalogs AI resources."""

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        *,
        registry: Optional[GarageRegistry] = None,
        scanner: Optional[GarageScanner] = None,
        manager: Optional[GarageManager] = None,
        hardware_profiler: Optional[Any] = None,
    ) -> None:
        self._event_bus = event_bus
        self.registry = registry or GarageRegistry()
        self.scanner = scanner or GarageScanner(self.registry)
        self.manager = manager or GarageManager(
            self.registry, self.scanner, event_bus=event_bus
        )
        if hardware_profiler is not None:
            self.registry.set_hardware_profiler(hardware_profiler)
        self._state = RuntimeState.UNINITIALIZED

    # --- Runtime protocol ---
    def get_runtime_id(self) -> str:
        return RUNTIME_ID

    def get_version(self) -> str:
        return RUNTIME_VERSION

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_id=RUNTIME_ID,
            version=RUNTIME_VERSION,
            priority="normal",
            capabilities=[
                Capability(id="garage.discover", runtime_id=RUNTIME_ID),
                Capability(id="garage.profile", runtime_id=RUNTIME_ID),
            ],
            dependencies=["event_bus"],
            auto_start=True,
        )

    def get_state(self) -> RuntimeState:
        return self._state

    async def initialize(self) -> None:
        self._state = RuntimeState.INITIALIZING
        logger.info("AI Garage initializing")

        # Register the default model providers. Network scanning happens only on
        # demand (refresh), never at boot, so startup stays offline and fast.
        self._register_default_providers()

        # Ensure a hardware profiler is configured.
        if self.registry.get_hardware_profiler() is None:
            self.registry.set_hardware_profiler(HardwareProfilerImpl())

        self._state = RuntimeState.READY
        self._publish(
            ZaramEvent(
                source_runtime=RUNTIME_ID,
                event_type="runtime.ready",
                data={"runtime_id": RUNTIME_ID},
            )
        )
        logger.info("AI Garage ready")

    async def shutdown(self) -> None:
        self._state = RuntimeState.STOPPING
        logger.info("AI Garage stopping")
        self._state = RuntimeState.STOPPED

    def health_check(self) -> Dict[str, Any]:
        return {
            "runtime_id": RUNTIME_ID,
            "state": self._state.value,
            "healthy": self._state == RuntimeState.READY,
            "registered_services": self.registry.count_model_providers(),
        }

    async def health(self) -> Dict[str, Any]:
        return self.manager.health_report()

    # --- discovery control (delegated to the manager) ---
    async def refresh(self, *, timeout: float = 2.0) -> None:
        await self.manager.refresh(timeout=timeout)

    # --- default provider wiring ---
    def _register_default_providers(self) -> None:
        for provider in (OllamaAdapter(), LMStudioAdapter()):
            self._safe_register(provider)

        endpoint = os.getenv("GARAGE_OPENAI_ENDPOINT")
        if endpoint:
            api_key = os.getenv("GARAGE_OPENAI_KEY")
            self._safe_register(
                OpenAICompatibleAdapter(
                    provider_id="openai_cloud",
                    base_url=endpoint,
                    kind=ProviderKind.CLOUD_API,
                    api_key=api_key,
                )
            )

    def _safe_register(self, provider: Any) -> None:
        try:
            self.registry.register_model_provider(provider)
        except ValueError:
            # Already registered (e.g. re-initialized) — idempotent.
            pass

    # --- helpers ---
    def _publish(self, event: ZaramEvent) -> None:
        if self._event_bus is not None:
            self._event_bus.publish(event)

"""Media Runtime (v0.5.5).

The Media Runtime is the root of all media subsystems. It owns no media
implementations — it registers the registry and manager, reports health, and
*wires in* the Voice Runtime as the first media capability during startup.

It registers with the Kernel exactly like the other runtimes: it implements the
``core.contracts.Runtime`` protocol, publishes ``runtime.ready`` on the shared
event bus, and is registered into the Kernel's ``RuntimeRegistry``. The Voice
Runtime stays in place, untouched; Media Runtime simply *discovers* it.

Relationship::

    Kernel
      └── Media Runtime
            └── Voice Runtime   (first registered media capability)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.contracts import (
    Capability,
    RuntimeMetadata,
    RuntimeState,
)
from core.event_bus import EventBus, ZaramEvent

from .contracts import MediaCapability
from .manager import MediaManager
from .registry import MediaRegistry

logger = logging.getLogger(__name__)

RUNTIME_ID = "media"
RUNTIME_VERSION = "0.5.5"


class MediaRuntime:
    """Kernel-facing runtime that orchestrates media subsystems.

    Implements the ``Runtime`` protocol used by ``core.registry.RuntimeRegistry``
    while remaining fully decoupled from any concrete media engine.
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        *,
        registry: Optional[MediaRegistry] = None,
        manager: Optional[MediaManager] = None,
    ) -> None:
        self._event_bus = event_bus
        self.registry = registry or MediaRegistry()
        self.manager = manager or MediaManager(self.registry, event_bus=event_bus)
        self._state = RuntimeState.UNINITIALIZED

    # --- Runtime protocol ---
    def get_runtime_id(self) -> str:
        return RUNTIME_ID

    def get_version(self) -> str:
        return RUNTIME_VERSION

    def get_metadata(self) -> RuntimeMetadata:
        capabilities = [
            Capability(id="media.discover", runtime_id=RUNTIME_ID),
            Capability(id="media.route", runtime_id=RUNTIME_ID),
            Capability(id="media.session", runtime_id=RUNTIME_ID),
        ]
        # Expose bridged capabilities (e.g. voice) as runtime capabilities so the
        # Kernel's capability router can resolve them.
        for cap in self.manager.capabilities():
            capabilities.append(
                Capability(
                    id=cap.id,
                    runtime_id=cap.runtime_id,
                    category=cap.media_type.value,
                )
            )
        return RuntimeMetadata(
            runtime_id=RUNTIME_ID,
            version=RUNTIME_VERSION,
            priority="high",
            capabilities=capabilities,
            dependencies=["event_bus"],
            auto_start=True,
        )

    def get_state(self) -> RuntimeState:
        return self._state

    async def initialize(self) -> None:
        """Start the runtime and wire in the Voice Runtime as first capability."""
        self._state = RuntimeState.INITIALIZING
        logger.info("Media Runtime initializing")

        # Discover any already-registered media providers (future runtimes will
        # register themselves before/after this point).
        discovered = self.registry.count()
        logger.info("Media Runtime discovered %d media providers", discovered)

        self._state = RuntimeState.READY
        self._publish(
            ZaramEvent(
                source_runtime=RUNTIME_ID,
                event_type="runtime.ready",
                data={"runtime_id": RUNTIME_ID, "providers": discovered},
            )
        )
        logger.info("Media Runtime ready")

    async def shutdown(self) -> None:
        self._state = RuntimeState.STOPPING
        # Tear down sessions cleanly; providers are owned by their own runtimes.
        self.close_all_sessions()
        self._state = RuntimeState.STOPPED
        logger.info("Media Runtime stopped")

    def health_check(self) -> Dict[str, Any]:
        # Synchronous shell required by the Runtime protocol.
        return {
            "runtime_id": RUNTIME_ID,
            "state": self._state.value,
            "healthy": self._state == RuntimeState.READY,
            "registered_services": self.registry.count(),
            "available_services": self.registry.count(),
            "capabilities": [c.id for c in self.manager.capabilities()],
        }

    # --- async health (richer view for the media runtime itself) ---
    async def health(self) -> Dict[str, Any]:
        return await self.manager.health(runtime_status=self._state.value)

    # --- voice runtime integration ---
    def discover_voice_runtime(self, voice_manager: Any) -> MediaCapability:
        """Register the Voice Runtime as the first media capability.

        ``voice_manager`` is any object honoring the VoiceManager surface; it is
        stored as the audio handler. Voice Runtime itself is not imported or
        modified here.
        """
        return self.manager.register_voice_capability(voice_manager)

    # --- helpers ---
    def _publish(self, event: ZaramEvent) -> None:
        if self._event_bus is not None:
            self._event_bus.publish(event)

    def close_all_sessions(self) -> int:
        closed = 0
        for session in self.manager.list_sessions():
            if self.manager.close_session(session.session_id):
                closed += 1
        return closed

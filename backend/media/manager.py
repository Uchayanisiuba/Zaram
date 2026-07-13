"""Media orchestration manager (v0.5.5).

The :class:`MediaManager` owns media session lifecycle, stream lifecycle,
provider routing, capability lookup, and health aggregation. It is the single
orchestration point the rest of Zaram talks to — it never imports a concrete
media engine (no Kokoro, no Ollama, no Unreal), so the application stays
decoupled from any provider.

The Voice Runtime is bridged in as the *first* media capability through
:meth:`register_voice_capability`, without moving or rewriting Voice Runtime.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from core.event_bus import EventBus

from .contracts import (
    MediaCapability,
    MediaLocality,
    MediaState,
    MediaType,
    new_id,
)
from .events import (
    MEDIA_COMPLETED,
    MEDIA_ERROR,
    MEDIA_REGISTERED,
    MEDIA_STARTED,
    MEDIA_STOPPED,
    create_media_event,
)
from .providers import MediaProvider
from .registry import MediaRegistry
from .session import MediaSession, MediaSessionStore

logger = logging.getLogger(__name__)


@dataclass
class _VoiceBridge:
    """Internal record linking a bridged (non-MediaProvider) capability to its handler."""

    capability: MediaCapability
    handler: Any


class MediaManager:
    """Provider-agnostic orchestration of media sessions, streams, and providers."""

    def __init__(
        self,
        registry: Optional[MediaRegistry] = None,
        *, event_bus: Optional[EventBus] = None,
    ) -> None:
        self.registry = registry or MediaRegistry()
        self._event_bus = event_bus
        self._sessions = MediaSessionStore()
        # Bridges let non-MediaProvider subsystems (e.g. Voice Runtime) act as
        # media capabilities without being migrated to the new abstraction.
        self._bridges: Dict[MediaType, _VoiceBridge] = {}

    # --- provider registration ---
    def register_provider(self, name: str, provider: MediaProvider) -> None:
        self.registry.register_provider(name, provider)

    # --- voice runtime bridge (first media capability) ---
    def register_voice_capability(
        self,
        voice_manager: Any,
        *,
        provider_name: str = "voice",
        capability_id: str = "media.audio.voice",
    ) -> MediaCapability:
        """Register the Voice Runtime as the first media capability.

        ``voice_manager`` is stored as the handler for AUDIO media so the
        Media Runtime can route audio requests to voice without depending on
        VoiceProvider or any TTS engine.
        """
        capability = MediaCapability(
            id=capability_id,
            media_type=MediaType.AUDIO,
            provider_name=provider_name,
            runtime_id="voice",
            locality=MediaLocality.LOCAL,
            metadata={"bridge": "voice_runtime"},
        )
        self._bridges[MediaType.AUDIO] = _VoiceBridge(capability, voice_manager)
        self._publish(
            create_media_event(
                MEDIA_REGISTERED,
                source_runtime="media",
                metadata={
                    "capability_id": capability.id,
                    "media_type": capability.media_type.value,
                    "provider_name": provider_name,
                    "bridge": "voice_runtime",
                },
            )
        )
        logger.info("Bridged Voice Runtime as media capability '%s'", capability.id)
        return capability

    def has_voice_capability(self) -> bool:
        return MediaType.AUDIO in self._bridges

    def get_voice_handler(self) -> Optional[Any]:
        bridge = self._bridges.get(MediaType.AUDIO)
        return bridge.handler if bridge else None

    # --- capability discovery ---
    def capabilities(self) -> List[MediaCapability]:
        caps = list(self.registry.capabilities())
        caps.extend(bridge.capability for bridge in self._bridges.values())
        return caps

    def capabilities_for_type(self, media_type: Union[MediaType, str]) -> List[MediaCapability]:
        target = (
            media_type
            if isinstance(media_type, MediaType)
            else MediaType.from_value(media_type)
        )
        return [c for c in self.capabilities() if c.media_type == target]

    # --- provider routing ---
    def route(self, media_type: Union[MediaType, str]) -> Optional[Any]:
        """Return a handler for ``media_type``.

        Prefers a bridged capability (e.g. voice), then falls back to a
        registered :class:`MediaProvider`. Returns ``None`` if nothing serves
        the modality.
        """
        target = (
            media_type
            if isinstance(media_type, MediaType)
            else MediaType.from_value(media_type)
        )
        bridge = self._bridges.get(target)
        if bridge is not None:
            return bridge.handler
        providers = self.registry.providers_for_type(target)
        if providers:
            return self.registry.get_provider(providers[0])
        return None

    def can_serve(self, media_type: Union[MediaType, str]) -> bool:
        return self.route(media_type) is not None

    # --- session lifecycle ---
    def create_session(
        self, *, conversation_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None
    ) -> MediaSession:
        return self._sessions.create(conversation_id=conversation_id, metadata=metadata)

    def get_session(self, session_id: str) -> Optional[MediaSession]:
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[MediaSession]:
        return self._sessions.list_sessions()

    def close_session(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        for stream_id in list(session.active_streams):
            self.stop_stream(session_id, stream_id)
        return self._sessions.close(session_id)

    def session_count(self) -> int:
        return self._sessions.count()

    # --- stream lifecycle ---
    def start_stream(
        self,
        session_id: Optional[str] = None,
        *,
        provider: Optional[str] = None,
        media_type: Union[MediaType, str] = MediaType.UNKNOWN,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Open a media stream within a session (creating one if needed)."""
        if session_id is None:
            session = self._sessions.create()
        else:
            session = self._sessions.get(session_id)
            if session is None:
                session = self._sessions.create()
                session_id = session.session_id

        stream_id = new_id("stream")
        session.add_stream(stream_id, provider=provider)
        self._publish(
            create_media_event(
                MEDIA_STARTED,
                stream_id=stream_id,
                session_id=session.session_id,
                metadata={
                    "provider": provider,
                    "media_type": (
                        media_type.value
                        if isinstance(media_type, MediaType)
                        else MediaType.from_value(media_type).value
                    ),
                    **(metadata or {}),
                },
            )
        )
        logger.info("Started media stream '%s' in session '%s'", stream_id, session.session_id)
        return stream_id

    def stop_stream(self, session_id: str, stream_id: str) -> bool:
        """Close a media stream. Returns True if it was active."""
        session = self._sessions.get(session_id)
        if session is None or not session.has_stream(stream_id):
            return False
        removed = session.remove_stream(stream_id)
        if removed:
            self._publish(
                create_media_event(
                    MEDIA_STOPPED,
                    stream_id=stream_id,
                    session_id=session_id,
                )
            )
            logger.info("Stopped media stream '%s'", stream_id)
        return removed

    def complete_stream(self, session_id: str, stream_id: str, *, error: Optional[str] = None) -> None:
        """Emit a completion or error event for a stream (does not close it)."""
        event_type = MEDIA_ERROR if error else MEDIA_COMPLETED
        self._publish(
            create_media_event(
                event_type,
                stream_id=stream_id,
                session_id=session_id,
                metadata={"error": error} if error else {},
            )
        )

    # --- health ---
    async def health(self, *, runtime_status: str = "ready") -> Dict[str, Any]:
        registry_health = await self.registry.health()
        capabilities = self.capabilities()
        return {
            "runtime_id": "media",
            "runtime_status": runtime_status,
            "health_status": registry_health.pop("status", "unknown"),
            "registered_services": self.registry.count(),
            "available_services": registry_health.get("available_count", 0),
            "provider_count": registry_health.get("provider_count", 0),
            "active_sessions": self._sessions.count(),
            "capabilities": [c.to_dict() for c in capabilities],
            "media_types": [mt.value for mt in self.registry.media_types_served()],
            "providers": registry_health.get("providers", {}),
        }

    # --- event bus ---
    def _publish(self, event: Any) -> None:
        if self._event_bus is not None:
            self._event_bus.publish(event)

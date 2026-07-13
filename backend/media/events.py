"""Provider-independent media events (v0.5.5).

Every helper returns a standard :class:`core.event_bus.ZaramEvent` so media
events flow through the *same* event bus as kernel and voice events. Events are
fully generic: they reference media streams and assets, never Kokoro, audio, or
the Voice Runtime.

Event types:
    MediaStarted, MediaStopped, MediaChunk, MediaCompleted, MediaError,
    MediaRegistered, MediaHealthChanged
"""

from __future__ import annotations

from typing import Any, Optional

from core.event_bus import ZaramEvent

# --- Event type identifiers (Event Bus) ---
MEDIA_STARTED = "media.started"
MEDIA_STOPPED = "media.stopped"
MEDIA_CHUNK = "media.chunk"
MEDIA_COMPLETED = "media.completed"
MEDIA_ERROR = "media.error"
MEDIA_REGISTERED = "media.registered"
MEDIA_HEALTH_CHANGED = "media.health_changed"

ALL_MEDIA_EVENTS = [
    MEDIA_STARTED,
    MEDIA_STOPPED,
    MEDIA_CHUNK,
    MEDIA_COMPLETED,
    MEDIA_ERROR,
    MEDIA_REGISTERED,
    MEDIA_HEALTH_CHANGED,
]


def create_media_event(
    event_type: str,
    *,
    stream_id: str = "",
    session_id: str = "",
    source_runtime: str = "media",
    correlation_id: str = "",
    priority: str = "normal",
    metadata: Optional[dict[str, Any]] = None,
) -> ZaramEvent:
    """Build a media event as a standard ``ZaramEvent``.

    ``stream_id`` / ``session_id`` and any ``metadata`` are carried in
    ``event.data``; the ``timestamp`` comes from the ``ZaramEvent`` itself.
    """
    data: dict[str, Any] = {}
    if stream_id:
        data["stream_id"] = stream_id
    if session_id:
        data["session_id"] = session_id
    if metadata:
        data.update(metadata)
    return ZaramEvent(
        source_runtime=source_runtime,
        event_type=event_type,
        correlation_id=correlation_id,
        priority=priority,
        data=data,
    )

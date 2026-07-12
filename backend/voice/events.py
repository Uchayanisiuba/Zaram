"""Voice events, compatible with the existing Zaram event bus.

Each helper returns a :class:`core.event_bus.ZaramEvent` so voice events flow
through the same bus as kernel events. Events carry ``request_id`` (in the
event ``data``), an automatic ``timestamp`` (from ``ZaramEvent``), and free-form
``metadata``.

Event types:
    SpeechRequested, SpeechStarted, SpeechChunkGenerated, AudioGenerated,
    SpeechCompleted, SpeechInterrupted, SpeechError
"""

from __future__ import annotations

from typing import Any, Optional

from core.event_bus import ZaramEvent

# --- Event type identifiers (Event Bus) ---
SPEECH_REQUESTED = "speech.requested"
SPEECH_STARTED = "speech.started"
SPEECH_CHUNK_GENERATED = "speech.chunk_generated"
SPEECH_AUDIO_GENERATED = "speech.audio_generated"
SPEECH_COMPLETED = "speech.completed"
SPEECH_INTERRUPTED = "speech.interrupted"
SPEECH_ERROR = "speech.error"

ALL_VOICE_EVENTS = [
    SPEECH_REQUESTED,
    SPEECH_STARTED,
    SPEECH_CHUNK_GENERATED,
    SPEECH_AUDIO_GENERATED,
    SPEECH_COMPLETED,
    SPEECH_INTERRUPTED,
    SPEECH_ERROR,
]


def create_voice_event(
    event_type: str,
    *,
    request_id: str,
    correlation_id: str = "",
    source_runtime: str = "voice",
    priority: str = "normal",
    metadata: Optional[dict[str, Any]] = None,
) -> ZaramEvent:
    """Build a voice event as a standard ``ZaramEvent``.

    ``request_id`` and any ``metadata`` are carried in ``event.data``; the
    ``timestamp`` comes from the ``ZaramEvent`` itself.
    """
    data: dict[str, Any] = {"request_id": request_id}
    if metadata:
        data.update(metadata)
    return ZaramEvent(
        source_runtime=source_runtime,
        event_type=event_type,
        correlation_id=correlation_id,
        priority=priority,
        data=data,
    )

"""Media events tests (offline)."""

from __future__ import annotations

from media.events import (
    ALL_MEDIA_EVENTS,
    MEDIA_COMPLETED,
    MEDIA_ERROR,
    MEDIA_REGISTERED,
    MEDIA_STARTED,
    MEDIA_STOPPED,
    create_media_event,
)


def test_event_is_standard_zaram_event():
    event = create_media_event(
        MEDIA_STARTED, stream_id="s1", session_id="sess", metadata={"k": "v"}
    )
    # Must be a standard event-bus event, not a voice/custom type.
    from core.event_bus import ZaramEvent

    assert isinstance(event, ZaramEvent)
    assert event.source_runtime == "media"
    assert event.event_type == MEDIA_STARTED
    assert event.data["stream_id"] == "s1"
    assert event.data["session_id"] == "sess"
    assert event.data["k"] == "v"
    assert event.timestamp > 0


def test_event_defaults_omit_empty():
    event = create_media_event(MEDIA_REGISTERED)
    assert "stream_id" not in event.data
    assert "session_id" not in event.data


def test_all_events_constant():
    assert set(ALL_MEDIA_EVENTS) == {
        MEDIA_STARTED,
        MEDIA_STOPPED,
        "media.chunk",
        MEDIA_COMPLETED,
        MEDIA_ERROR,
        MEDIA_REGISTERED,
        "media.health_changed",
    }

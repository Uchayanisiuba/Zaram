"""MediaManager tests (offline)."""

from __future__ import annotations

import pytest

from media.contracts import MediaState, MediaType
from media.events import MEDIA_REGISTERED, MEDIA_STARTED, MEDIA_STOPPED
from media.manager import MediaManager
from media.registry import MediaRegistry
from media.tests.conftest import FakeMediaProvider


@pytest.fixture
def manager() -> MediaManager:
    return MediaManager()


def test_register_provider(manager, fake_provider):
    manager.register_provider("fake", fake_provider)
    assert manager.registry.is_registered("fake")


def test_capability_lookup_after_register(manager, fake_provider):
    manager.register_provider("audio", fake_provider)
    caps = manager.capabilities_for_type(MediaType.AUDIO)
    assert len(caps) == 1
    assert caps[0].media_type is MediaType.AUDIO


def test_routing_returns_registered_provider(manager, fake_provider):
    manager.register_provider("audio", fake_provider)
    handler = manager.route(MediaType.AUDIO)
    assert handler is fake_provider


def test_routing_unknown_returns_none(manager):
    assert manager.route(MediaType.VIDEO) is None
    assert manager.can_serve(MediaType.VIDEO) is False


def test_session_lifecycle(manager):
    session = manager.create_session(conversation_id="c1")
    assert manager.session_count() == 1
    assert manager.get_session(session.session_id) is session
    assert manager.close_session(session.session_id) is True
    assert manager.session_count() == 0


def test_stream_lifecycle_emits_events(manager):
    events = []
    manager._event_bus = _CapturingBus(events)
    session = manager.create_session()
    stream_id = manager.start_stream(session.session_id, provider="voice", media_type=MediaType.AUDIO)
    assert session.has_stream(stream_id)
    assert session.state is MediaState.ACTIVE
    started = [e for e in events if e.event_type == MEDIA_STARTED]
    assert started and started[0].data["stream_id"] == stream_id

    assert manager.stop_stream(session.session_id, stream_id) is True
    assert session.has_stream(stream_id) is False
    assert any(e.event_type == MEDIA_STOPPED for e in events)


def test_stream_creates_session_when_missing(manager):
    stream_id = manager.start_stream(provider="vision", media_type=MediaType.IMAGE)
    assert manager.session_count() == 1
    session = manager.list_sessions()[0]
    assert session.has_stream(stream_id)


def test_complete_stream_emits_completed_or_error(manager):
    events = []
    manager._event_bus = _CapturingBus(events)
    session = manager.create_session()
    stream_id = manager.start_stream(session.session_id)
    manager.complete_stream(session.session_id, stream_id)
    manager.complete_stream(session.session_id, stream_id, error="boom")
    assert any(e.event_type == "media.completed" for e in events)
    assert any(e.event_type == "media.error" for e in events)


def test_close_session_stops_streams(manager):
    session = manager.create_session()
    manager.start_stream(session.session_id, provider="voice")
    assert session.stream_count() == 1
    manager.close_session(session.session_id)
    assert manager.get_session(session.session_id) is None


@pytest.mark.asyncio
async def test_health_report(manager, fake_provider):
    manager.register_provider("audio", fake_provider)
    report = await manager.health()
    assert report["runtime_id"] == "media"
    assert report["registered_services"] == 1
    assert report["provider_count"] == 1
    assert report["active_sessions"] == 0
    assert MediaType.AUDIO.value in report["media_types"]


# --- voice bridge ---
def test_voice_capability_bridge_emits_event():
    events = []
    mgr = MediaManager(event_bus=_CapturingBus(events))
    cap = mgr.register_voice_capability(object(), provider_name="voice")
    assert cap.media_type is MediaType.AUDIO
    assert cap.runtime_id == "voice"
    assert mgr.has_voice_capability() is True
    assert mgr.get_voice_handler() is not None
    assert any(e.event_type == MEDIA_REGISTERED for e in events)


def test_voice_bridge_routes_audio():
    voice_manager = object()
    mgr = MediaManager()
    mgr.register_voice_capability(voice_manager)
    assert mgr.route(MediaType.AUDIO) is voice_manager
    assert mgr.can_serve(MediaType.AUDIO) is True


def test_voice_capability_in_discovery():
    mgr = MediaManager()
    mgr.register_voice_capability(object())
    caps = mgr.capabilities_for_type(MediaType.AUDIO)
    assert any(c.runtime_id == "voice" for c in caps)


class _CapturingBus:
    """Tiny event-bus stand-in that records published events."""

    def __init__(self, sink):
        self._sink = sink

    def publish(self, event):
        self._sink.append(event)

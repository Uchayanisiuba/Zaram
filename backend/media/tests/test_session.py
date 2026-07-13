"""Media Session tests (offline)."""

from __future__ import annotations

from media.contracts import MediaState
from media.session import MediaSession, MediaSessionStore


def test_session_defaults():
    session = MediaSession()
    assert session.state is MediaState.CREATED
    assert session.session_id.startswith("session_")
    assert session.active_streams == []
    assert session.providers == []


def test_session_add_stream_idempotent():
    session = MediaSession()
    session.add_stream("s1", provider="voice")
    session.add_stream("s1", provider="voice")
    assert session.active_streams == ["s1"]
    assert session.providers == ["voice"]
    assert session.state is MediaState.ACTIVE


def test_session_remove_stream_completes():
    session = MediaSession()
    session.add_stream("s1", provider="voice")
    session.add_stream("s2", provider="vision")
    assert session.remove_stream("s1") is True
    assert session.remove_stream("s1") is False
    assert session.has_stream("s2") is True
    # removing the last stream completes the session
    session.remove_stream("s2")
    assert session.state is MediaState.COMPLETED


def test_session_store_lifecycle():
    store = MediaSessionStore()
    assert store.count() == 0
    s1 = store.create(conversation_id="c1", metadata={"k": "v"})
    s2 = store.create()
    assert store.count() == 2
    assert store.get(s1.session_id) is s1
    assert store.get("missing") is None
    assert len(store.list_sessions()) == 2
    assert store.close(s1.session_id) is True
    assert store.close(s1.session_id) is False
    assert store.count() == 1
    assert store.close_all() == 1
    assert store.count() == 0


def test_session_to_dict():
    store = MediaSessionStore()
    s = store.create(conversation_id="c1")
    s.add_stream("s1", provider="voice")
    data = s.to_dict()
    assert data["conversation_id"] == "c1"
    assert data["active_streams"] == ["s1"]
    assert data["providers"] == ["voice"]
    assert data["state"] == MediaState.ACTIVE.value

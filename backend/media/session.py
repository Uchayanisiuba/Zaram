"""Media session tracking for the Media Runtime (v0.5.5).

A :class:`MediaSession` groups one or more concurrent media streams under a
single conversation/session scope. The session model is intentionally generic:
it tracks *which* providers and *which* streams are active, not what media
type they are, so future multi-stream scenarios (e.g. voice + avatar + vision
simultaneously) fit without redesign.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .contracts import MediaState, new_id


@dataclass
class MediaSession:
    """Tracks the active media associated with a conversation/session.

    Attributes:
        session_id: Stable unique identifier for the session.
        conversation_id: Optional owning conversation identifier.
        active_streams: Ordered ids of streams currently open in this session.
        providers: Names of media providers engaged by this session.
        metadata: Free-form, application-specific context.
        created_at: Epoch timestamp when the session was created.
        state: Lifecycle state of the session.
    """

    conversation_id: Optional[str] = None
    active_streams: List[str] = field(default_factory=list)
    providers: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    state: MediaState = MediaState.CREATED
    session_id: str = field(default_factory=lambda: new_id("session"))

    # --- stream management ---
    def add_stream(self, stream_id: str, provider: Optional[str] = None) -> None:
        """Register an open stream (idempotent; ignores duplicates)."""
        if stream_id not in self.active_streams:
            self.active_streams.append(stream_id)
        if provider and provider not in self.providers:
            self.providers.append(provider)
        if self.state == MediaState.CREATED:
            self.state = MediaState.ACTIVE

    def remove_stream(self, stream_id: str) -> bool:
        """Close a stream. Returns True if it was active."""
        if stream_id in self.active_streams:
            self.active_streams.remove(stream_id)
            if not self.active_streams:
                self.state = MediaState.COMPLETED
            return True
        return False

    def has_stream(self, stream_id: str) -> bool:
        return stream_id in self.active_streams

    def stream_count(self) -> int:
        return len(self.active_streams)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "active_streams": list(self.active_streams),
            "providers": list(self.providers),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "state": self.state.value,
        }


class MediaSessionStore:
    """In-memory store of active media sessions.

    Centralizes session creation, lookup, and teardown. It is plain state with
    no I/O and no media-type knowledge, keeping it trivially testable.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, MediaSession] = {}

    def create(
        self,
        *,
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MediaSession:
        session = MediaSession(
            conversation_id=conversation_id,
            metadata=dict(metadata or {}),
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Optional[MediaSession]:
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[MediaSession]:
        return list(self._sessions.values())

    def count(self) -> int:
        return len(self._sessions)

    def close(self, session_id: str) -> bool:
        """Remove a session. Returns True if it existed."""
        return self._sessions.pop(session_id, None) is not None

    def close_all(self) -> int:
        count = len(self._sessions)
        self._sessions.clear()
        return count

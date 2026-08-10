from __future__ import annotations

from typing import Any
from dataclasses import dataclass
import time

from .contracts import MemoryRecord, MemoryResult, MemoryType, RetrievalStrategy


@dataclass
class EpisodicEvent:
    event_type: str
    description: str
    participants: list[str] = None
    location: str | None = None
    timestamp: float = 0.0
    metadata: dict[str, Any] = None
    importance: float = 0.6

    def __post_init__(self):
        if self.participants is None:
            self.participants = []
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class EpisodicMemory:
    """Manages episodic memories - specific events and experiences."""

    def __init__(self, memory_runtime: "MemoryRuntime"):
        self._runtime = memory_runtime

    async def record_event(
        self,
        user_id: str,
        event: EpisodicEvent,
        session_id: str | None = None,
    ) -> str:
        content = f"Event: {event.event_type} - {event.description}"
        if event.location:
            content += f" @ {event.location}"
        if event.participants:
            content += f" (with {', '.join(event.participants)})"

        record = MemoryRecord(
            content=content,
            memory_type=MemoryType.EPISODIC,
            metadata={
                "event_type": event.event_type,
                "participants": event.participants,
                "location": event.location,
                **event.metadata,
            },
            session_id=session_id,
            user_id=user_id,
            tags=["episodic", event.event_type],
            importance=event.importance,
            source="episodic_event",
        )
        return await self._runtime.store_record(record)

    async def store_record(self, record: "MemoryRecord") -> str:
        return await self._runtime.store(
            content=record.content,
            memory_type=record.memory_type,
            metadata=record.metadata,
            session_id=record.session_id,
            user_id=record.user_id,
            tags=record.tags,
            importance=record.importance,
        )

    async def get_recent_events(
        self,
        user_id: str,
        limit: int = 20,
        event_type: str | None = None,
    ) -> list[MemoryResult]:
        filters = {"event_type": event_type} if event_type else {}
        return await self._runtime.retrieve(
            query="",
            memory_types=[MemoryType.EPISODIC],
            max_results=limit,
            user_id=user_id,
            filters=filters,
            strategy=RetrievalStrategy.TEMPORAL,
        )

    async def get_events_by_participant(
        self,
        user_id: str,
        participant: str,
        limit: int = 20,
    ) -> list[MemoryResult]:
        results = await self._runtime.retrieve(
            query="",
            memory_types=[MemoryType.EPISODIC],
            max_results=limit,
            user_id=user_id,
        )
        filtered = [
            r for r in results
            if participant in r.record.metadata.get("participants", [])
        ]
        return filtered[:limit]

    async def get_events_at_location(
        self,
        user_id: str,
        location: str,
        limit: int = 20,
    ) -> list[MemoryResult]:
        results = await self._runtime.retrieve(
            query="",
            memory_types=[MemoryType.EPISODIC],
            max_results=limit,
            user_id=user_id,
        )
        filtered = [
            r for r in results
            if r.record.metadata.get("location") == location
        ]
        return filtered[:limit]

    async def consolidate_events(self, user_id: str) -> dict[str, Any]:
        events = await self.get_recent_events(user_id, limit=100)
        if len(events) < 10:
            return {"consolidated": 0, "reason": "insufficient_events"}

        consolidated = 0
        # Group similar events and create semantic memories
        # This is a simplified implementation
        return {"consolidated": consolidated, "events_reviewed": len(events)}

    async def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "runtime_id": self._runtime.get_runtime_id()}
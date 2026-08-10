from __future__ import annotations

from typing import Any
from collections import deque
import time

from .contracts import MemoryRecord, MemoryType


class ConversationHistory:
    """Manages conversation history with sliding window and session tracking."""

    def __init__(self, memory_runtime: "MemoryRuntime", max_turns: int = 50):
        self._runtime = memory_runtime
        self._max_turns = max_turns
        self._session_buffers: dict[str, deque] = {}

    async def add_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[str]:
        if session_id not in self._session_buffers:
            self._session_buffers[session_id] = deque(maxlen=self._max_turns)

        turn_id = f"turn_{int(time.time() * 1000)}"
        user_record = MemoryRecord(
            content=user_message,
            memory_type=MemoryType.CONVERSATION,
            metadata={"role": "user", "turn_id": turn_id, **(metadata or {})},
            session_id=session_id,
            user_id=user_id,
            tags=["conversation", "user"],
            importance=0.7,
            source="user",
        )
        assistant_record = MemoryRecord(
            content=assistant_message,
            memory_type=MemoryType.CONVERSATION,
            metadata={"role": "assistant", "turn_id": turn_id, **(metadata or {})},
            session_id=session_id,
            user_id=user_id,
            tags=["conversation", "assistant"],
            importance=0.7,
            source="assistant",
        )

        user_id_stored = await self._runtime.store_record(user_record)
        assistant_id_stored = await self._runtime.store_record(assistant_record)

        self._session_buffers[session_id].append({
            "turn_id": turn_id,
            "user_id": user_id_stored,
            "assistant_id": assistant_id_stored,
            "timestamp": time.time(),
        })

        return [user_id_stored, assistant_id_stored]

    async def get_recent_turns(self, session_id: str, limit: int = 10) -> list[dict[str, Any]]:
        buffer = self._session_buffers.get(session_id, deque())
        turns = list(buffer)[-limit:]
        results = []
        for turn in turns:
            user_rec = await self._runtime.get_record(turn["user_id"])
            assistant_rec = await self._runtime.get_record(turn["assistant_id"])
            if user_rec and assistant_rec:
                results.append({
                    "turn_id": turn["turn_id"],
                    "user": user_rec.content,
                    "assistant": assistant_rec.content,
                    "timestamp": turn["timestamp"],
                })
        return results

    async def get_full_history(self, session_id: str, limit: int = 50) -> list[MemoryRecord]:
        return await self._runtime.get_conversation_history(session_id, limit)

    async def clear_session(self, session_id: str) -> bool:
        if session_id in self._session_buffers:
            del self._session_buffers[session_id]
        records = await self._runtime.get_conversation_history(session_id)
        for r in records:
            await self._runtime.forget(r.id)
        return True

    async def get_summary(self, session_id: str) -> str:
        history = await self.get_recent_turns(session_id, limit=20)
        if not history:
            return "No conversation history."
        lines = [f"Session: {session_id}", f"Turns: {len(history)}"]
        for turn in history[-5:]:
            lines.append(f"  User: {turn['user'][:80]}...")
            lines.append(f"  Assistant: {turn['assistant'][:80]}...")
        return "\n".join(lines)

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "active_sessions": len(self._session_buffers),
            "max_turns": self._max_turns,
        }

    async def store_record(self, record: MemoryRecord) -> str:
        return await self._runtime.store(
            content=record.content,
            memory_type=record.memory_type,
            metadata=record.metadata,
            session_id=record.session_id,
            user_id=record.user_id,
            tags=record.tags,
            importance=record.importance,
        )

    async def get_record(self, record_id: str) -> MemoryRecord | None:
        return await self._runtime.get_record(record_id)
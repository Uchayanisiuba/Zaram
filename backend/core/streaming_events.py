# backend/core/streaming_events.py
"""Execution Tokens — structured streaming events for the kernel.

StreamEvent is the kernel's execution token format.  Each event
represents a discrete unit of output in the streaming response:
tokens, status changes, source attributions, errors, and completion.

The format is JSON-serializable for SSE transport and includes
sequence numbers for ordered reconstruction.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum

from core.contracts import ExecutionToken


class EventType(str, Enum):
    START = "start"
    TOKEN = "token"
    STATUS = "status"
    SOURCE = "source"
    ERROR = "error"
    DONE = "done"
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    PLAN_START = "plan_start"
    PLAN_COMPLETE = "plan_complete"
    RETRY = "retry"
    CANCEL = "cancel"
    #: A file Zaram made. Rendered as a card in the conversation and, from the
    #: same record, as a row in Work.
    ARTIFACT = "artifact"


@dataclass
class StreamEvent:
    """A single event in the streaming response.

    Events are JSON-serialized via ``to_ipc()`` for SSE transport.
    Each event carries a sequence number for ordered reconstruction
    and a timestamp for latency measurement.
    """
    type: EventType
    data: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    seq: int = 0
    correlation_id: str = ""

    def to_ipc(self) -> str:
        """Serialize to an SSE-compatible JSON line."""
        return json.dumps({
            "type": self.type.value,
            "data": self.data,
            "ts": self.ts,
            "seq": self.seq,
            "correlation_id": self.correlation_id,
        })

    @staticmethod
    def token(content: str, seq: int = 0, correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.TOKEN,
            data={"content": content},
            seq=seq,
            correlation_id=correlation_id,
        )

    @staticmethod
    def status(state: str, capability_id: str | None = None, correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.STATUS,
            data={
                "state": state,
                "capability_id": capability_id,
            },
            correlation_id=correlation_id,
        )

    @staticmethod
    def source(kind: str, url: str | None = None, title: str | None = None, correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.SOURCE,
            data={
                "kind": kind,
                "url": url,
                "title": title,
            },
            correlation_id=correlation_id,
        )

    @staticmethod
    def artifact(record: dict, correlation_id: str = "") -> StreamEvent:
        """A generated file, as a card in the conversation.

        Carries the whole artifact record rather than a URL, because the card
        shows what Work shows — filename, kind, sources, claims — and a card
        that had to fetch each of those would render empty first and then
        rearrange itself under the user.
        """
        return StreamEvent(
            type=EventType.ARTIFACT,
            data=record,
            correlation_id=correlation_id,
        )

    @staticmethod
    def error(content: str, correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.ERROR,
            data={"content": content},
            correlation_id=correlation_id,
        )

    @staticmethod
    def done(correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.DONE,
            data={},
            correlation_id=correlation_id,
        )

    @staticmethod
    def start(capability_id: str | None = None, correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.START,
            data={"capability_id": capability_id},
            correlation_id=correlation_id,
        )

    @staticmethod
    def step_start(capability_id: str, step_index: int, correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.STEP_START,
            data={"capability_id": capability_id, "step_index": step_index},
            correlation_id=correlation_id,
        )

    @staticmethod
    def step_complete(capability_id: str, step_index: int, success: bool = True, correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.STEP_COMPLETE,
            data={"capability_id": capability_id, "step_index": step_index, "success": success},
            correlation_id=correlation_id,
        )

    @staticmethod
    def plan_start(correlation_id: str, step_count: int) -> StreamEvent:
        return StreamEvent(
            type=EventType.PLAN_START,
            data={"step_count": step_count},
            correlation_id=correlation_id,
        )

    @staticmethod
    def plan_complete(correlation_id: str, state: str) -> StreamEvent:
        return StreamEvent(
            type=EventType.PLAN_COMPLETE,
            data={"state": state},
            correlation_id=correlation_id,
        )

    @staticmethod
    def retry(capability_id: str, attempt: int, delay: float, correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.RETRY,
            data={"capability_id": capability_id, "attempt": attempt, "delay": delay},
            correlation_id=correlation_id,
        )

    @staticmethod
    def cancel(correlation_id: str, reason: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.CANCEL,
            data={"reason": reason},
            correlation_id=correlation_id,
        )

    def to_execution_token(self) -> ExecutionToken:
        """Convert to an ExecutionToken for internal use."""
        return ExecutionToken(
            token=self.data.get("content", ""),
            sequence=self.seq,
            final=self.type == EventType.DONE,
            metadata={
                "type": self.type.value,
                "ts": self.ts,
                "correlation_id": self.correlation_id,
            },
        )

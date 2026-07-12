# backend/core/event_bus.py
import asyncio
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ZaramEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    source_runtime: str = "system"
    event_type: str = "unknown"
    version: int = 1
    priority: str = "normal"  # critical, high, normal, background
    data: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""

class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}
        self._history: list[ZaramEvent] = []

    def subscribe(self, event_type: str, callback: Callable[[ZaramEvent], Any]) -> str:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        return f"sub_{uuid.uuid4().hex[:8]}"

    def publish(self, event: ZaramEvent):
        self._history.append(event)
        callbacks = self._subscribers.get(event.event_type, [])

        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(event))
                else:
                    callback(event)
            except Exception as e:
                print(f"[EventBus] Error in subscriber for {event.event_type}: {e}")

    def get_history(self, limit: int = 50) -> list[ZaramEvent]:
        return self._history[-limit:]

# backend/core/event_bus.py
import asyncio
from dataclasses import dataclass, field
from typing import Callable, Any, Dict, List
import time
import uuid

@dataclass(frozen=True)
class ZaramEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    source_runtime: str = "system"
    event_type: str = "unknown"
    version: int = 1
    priority: str = "normal"  # critical, high, normal, background
    data: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        #: token -> (event_type, callback), so a subscription can be undone.
        self._subscriptions: Dict[str, tuple] = {}
        self._history: List[ZaramEvent] = []

    def subscribe(self, event_type: str, callback: Callable[[ZaramEvent], Any]) -> str:
        """Register ``callback``; returns a token to pass to :meth:`unsubscribe`.

        The token is an opaque string, not a callable. It used to be the latter
        by accident of naming: the speech runtime stored it as
        ``self._unsubscribe_*`` and called it on shutdown, which raised
        TypeError on every single kernel shutdown because there was no
        ``unsubscribe`` for it to be.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        token = f"sub_{uuid.uuid4().hex[:8]}"
        self._subscriptions[token] = (event_type, callback)
        return token

    def unsubscribe(self, token: str) -> bool:
        """Remove a subscription by token. Returns whether one was removed.

        Idempotent: an unknown or already-used token is not an error, so
        shutdown paths do not need to track whether they already ran.
        """
        entry = self._subscriptions.pop(token, None)
        if entry is None:
            return False
        event_type, callback = entry
        callbacks = self._subscribers.get(event_type, [])
        if callback in callbacks:
            callbacks.remove(callback)
        return True

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

    def get_history(self, limit: int = 50) -> List[ZaramEvent]:
        return self._history[-limit:]
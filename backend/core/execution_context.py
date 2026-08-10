# backend/core/execution_context.py
"""Execution context for capability invocations.

An ExecutionContext bundles everything a dispatcher or runtime needs to
execute a single capability call: tracing identifiers, cancellation,
retry policy, deadlines, and arbitrary metadata.  It is the unit of
work that flows through the Kernel.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from core.contracts import (
    CancellationSignal,
    TaskDescriptor,
    TaskPriority,
)
from core.retry_policy import DEFAULT_RETRY, RetryPolicy

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """Immutable-ish context for a single capability execution.

    The context is created by the Scheduler/TaskQueue and passed to the
    Dispatcher, which forwards it to the runtime service.  The runtime
    can call ``check_cancellation()`` at any point to honour cooperative
    cancellation.
    """
    correlation_id: str
    capability_id: str
    input_data: dict[str, Any]
    cancellation: CancellationSignal = field(default_factory=CancellationSignal)
    retry_policy: RetryPolicy = field(default_factory=lambda: DEFAULT_RETRY)
    priority: TaskPriority = TaskPriority.NORMAL
    start_time: float = field(default_factory=time.time)
    deadline: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    parent_context: str | None = None  # correlation_id of parent, if nested

    @classmethod
    def from_descriptor(cls, descriptor: TaskDescriptor) -> ExecutionContext:
        """Build an ExecutionContext from a TaskDescriptor."""
        return cls(
            correlation_id=descriptor.correlation_id,
            capability_id=descriptor.capability_id,
            input_data=descriptor.input_data,
            cancellation=descriptor.cancellation,
            priority=descriptor.priority,
            start_time=descriptor.started_at or time.time(),
            metadata={},
            parent_context=None,
        )

    def check_cancellation(self) -> None:
        """Raise TaskCancelledError if this context has been cancelled."""
        self.cancellation.check()

    def cancel(self, reason: str = "") -> None:
        """Cancel this context and all child contexts."""
        self.cancellation.cancel(reason)
        logger.info("Context %s cancelled: %s", self.correlation_id, reason or "no reason")

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    @property
    def remaining(self) -> float | None:
        if self.deadline is None:
            return None
        return max(0.0, self.deadline - time.time())

    def is_expired(self) -> bool:
        if self.deadline is None:
            return False
        return time.time() >= self.deadline

    def with_deadline(self, timeout_seconds: float) -> ExecutionContext:
        """Return a copy with a deadline set to *timeout_seconds* from now."""
        import copy
        clone = copy.copy(self)
        clone.deadline = time.time() + timeout_seconds
        return clone

    def with_metadata(self, **kwargs: Any) -> ExecutionContext:
        """Return a copy with additional metadata merged in."""
        import copy
        clone = copy.copy(self)
        clone.metadata = {**self.metadata, **kwargs}
        return clone

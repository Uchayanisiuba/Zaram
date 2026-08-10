# backend/core/task_queue.py
"""Async task queue with priority, cancellation, and retry.

The TaskQueue is the kernel's central work queue.  Tasks are enqueued
as :class:`~core.contracts.TaskDescriptor` objects and executed by
worker coroutines.  Each task carries its own :class:`CancellationSignal`
and :class:`RetryPolicy`, enabling cooperative cancellation and automatic
retry with exponential backoff.
"""
from __future__ import annotations

import asyncio
import heapq
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from core.contracts import (
    CancellationSignal,
    TaskCancelledError,
    TaskDescriptor,
    TaskPriority,
    TaskStatus,
)
from core.event_bus import EventBus, ZaramEvent
from core.execution_context import ExecutionContext
from core.retry_policy import DEFAULT_RETRY, RetryPolicy

logger = logging.getLogger(__name__)

_PRIORITY_WEIGHTS: dict[TaskPriority, int] = {
    TaskPriority.CRITICAL: 0,
    TaskPriority.HIGH: 1,
    TaskPriority.NORMAL: 2,
    TaskPriority.LOW: 3,
    TaskPriority.BACKGROUND: 4,
}

_TaskExecutor = Callable[[ExecutionContext], Awaitable[Any]]


@dataclass(order=True)
class _QueueEntry:
    """Internal heap entry wrapping a TaskDescriptor."""
    sort_key: tuple[int, int, float]
    descriptor: TaskDescriptor = field(compare=False)
    context: ExecutionContext = field(compare=False)
    executor: _TaskExecutor = field(compare=False)


class TaskQueue:
    """Priority task queue with cancellation and retry support.

    Parameters
    ----------
    event_bus:
        Optional EventBus for publishing task lifecycle events.
    max_retries:
        Default retry count for tasks without an explicit policy.
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        max_retries: int = 3,
    ) -> None:
        self._event_bus = event_bus
        self._default_max_retries = max_retries
        self._heap: list[_QueueEntry] = []
        self._heap_lock = asyncio.Lock()
        self._counter = 0
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._descriptors: dict[str, TaskDescriptor] = {}
        self._results: dict[str, Any] = {}
        self._errors: dict[str, str] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._stopped = False
        self._workers: list[asyncio.Task[None]] = []

    # ------------------------------------------------------------------
    # Enqueue
    # ------------------------------------------------------------------

    async def enqueue(
        self,
        capability_id: str,
        input_data: dict[str, Any],
        executor: _TaskExecutor,
        *,
        priority: TaskPriority = TaskPriority.NORMAL,
        correlation_id: str = "",
        max_retries: int | None = None,
        retry_policy: RetryPolicy | None = None,
        deadline: float | None = None,
        depends_on: list[str] | None = None,
        cancellation: CancellationSignal | None = None,
    ) -> str:
        """Enqueue a task and return its task_id."""
        task_id = str(uuid.uuid4())
        descriptor = TaskDescriptor(
            task_id=task_id,
            capability_id=capability_id,
            input_data=input_data,
            priority=priority,
            status=TaskStatus.PENDING,
            retry_count=0,
            max_retries=max_retries if max_retries is not None else self._default_max_retries,
            correlation_id=correlation_id or task_id,
            depends_on=depends_on or [],
            cancellation=cancellation or CancellationSignal(),
        )
        context = ExecutionContext(
            correlation_id=descriptor.correlation_id,
            capability_id=capability_id,
            input_data=input_data,
            cancellation=descriptor.cancellation,
            retry_policy=retry_policy or DEFAULT_RETRY,
            priority=priority,
            deadline=deadline,
        )
        entry = _QueueEntry(
            sort_key=(
                _PRIORITY_WEIGHTS[priority],
                self._counter,
                time.time(),
            ),
            descriptor=descriptor,
            context=context,
            executor=executor,
        )
        self._counter += 1
        self._descriptors[task_id] = descriptor
        self._events[task_id] = asyncio.Event()

        async with self._heap_lock:
            heapq.heappush(self._heap, entry)

        self._publish("task.enqueued", {
            "task_id": task_id,
            "capability_id": capability_id,
            "priority": priority.value,
            "correlation_id": descriptor.correlation_id,
        })
        logger.debug("TaskQueue: enqueued task %s (%s)", task_id, capability_id)
        return task_id

    # ------------------------------------------------------------------
    # Worker management
    # ------------------------------------------------------------------

    def start(self, worker_count: int = 1) -> None:
        """Start background worker coroutines."""
        if self._workers:
            return
        for _ in range(worker_count):
            worker = asyncio.create_task(self._worker_loop())
            self._workers.append(worker)
        logger.info("TaskQueue: started %d workers", worker_count)

    async def stop(self) -> None:
        """Stop all workers and wait for in-flight tasks."""
        self._stopped = True
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("TaskQueue: stopped all workers")

    async def _worker_loop(self) -> None:
        """Main worker loop: pop entries and execute them."""
        while not self._stopped:
            entry = await self._pop()
            if entry is None:
                await asyncio.sleep(0.01)
                continue
            await self._execute(entry)

    async def _pop(self) -> _QueueEntry | None:
        """Pop the highest-priority entry, respecting dependencies."""
        async with self._heap_lock:
            if not self._heap:
                return None
            entry = heapq.heappop(self._heap)

        # Check dependencies
        for dep_id in entry.descriptor.depends_on:
            dep = self._descriptors.get(dep_id)
            if dep and dep.status not in (TaskStatus.COMPLETED,):
                # Re-queue and wait
                async with self._heap_lock:
                    heapq.heappush(self._heap, entry)
                return None

        return entry

    async def _execute(self, entry: _QueueEntry) -> None:
        """Execute a single task entry with retry logic."""
        descriptor = entry.descriptor
        context = entry.context
        task_id = descriptor.task_id

        descriptor.status = TaskStatus.RUNNING
        descriptor.started_at = time.time()
        self._publish("task.started", {
            "task_id": task_id,
            "capability_id": descriptor.capability_id,
        })

        last_error: BaseException | None = None

        for attempt in range(descriptor.max_retries + 1):
            if descriptor.cancellation.cancelled:
                descriptor.status = TaskStatus.CANCELLED
                self._errors[task_id] = descriptor.cancellation.reason or "cancelled"
                self._events[task_id].set()
                self._publish("task.cancelled", {
                    "task_id": task_id,
                    "reason": descriptor.cancellation.reason,
                })
                return

            try:
                result = await entry.executor(context)
                descriptor.status = TaskStatus.COMPLETED
                descriptor.completed_at = time.time()
                self._results[task_id] = result
                self._events[task_id].set()
                self._publish("task.completed", {
                    "task_id": task_id,
                    "capability_id": descriptor.capability_id,
                })
                return

            except TaskCancelledError as exc:
                descriptor.status = TaskStatus.CANCELLED
                self._errors[task_id] = str(exc) or "cancelled"
                self._events[task_id].set()
                self._publish("task.cancelled", {
                    "task_id": task_id,
                    "reason": str(exc),
                })
                return

            except BaseException as exc:
                last_error = exc
                descriptor.retry_count = attempt
                result = context.retry_policy.should_retry(attempt, exc)

                if not result.should_retry:
                    descriptor.status = TaskStatus.FAILED
                    descriptor.error = str(exc)
                    descriptor.completed_at = time.time()
                    self._errors[task_id] = str(exc)
                    self._events[task_id].set()
                    self._publish("task.failed", {
                        "task_id": task_id,
                        "error": str(exc),
                        "attempts": attempt + 1,
                    })
                    return

                descriptor.status = TaskStatus.RETRYING
                logger.info(
                    "TaskQueue: retrying task %s attempt %d/%d in %.3fs",
                    task_id,
                    attempt + 1,
                    descriptor.max_retries,
                    result.delay,
                )
                await asyncio.sleep(result.delay)

        # Exhausted retries
        descriptor.status = TaskStatus.FAILED
        descriptor.error = str(last_error) if last_error else "unknown"
        descriptor.completed_at = time.time()
        self._errors[task_id] = descriptor.error
        self._events[task_id].set()
        self._publish("task.failed", {
            "task_id": task_id,
            "error": descriptor.error,
            "attempts": descriptor.max_retries + 1,
        })

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def cancel(self, task_id: str, reason: str = "") -> bool:
        """Cancel a pending or running task."""
        descriptor = self._descriptors.get(task_id)
        if descriptor is None:
            return False
        if descriptor.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return False
        descriptor.cancellation.cancel(reason or "cancelled by caller")
        self._publish("task.cancellation_requested", {
            "task_id": task_id,
            "reason": reason,
        })
        return True

    def cancel_by_correlation(self, correlation_id: str, reason: str = "") -> int:
        """Cancel all tasks sharing a correlation_id."""
        count = 0
        for task_id, desc in self._descriptors.items():
            if desc.correlation_id == correlation_id and self.cancel(task_id, reason):
                count += 1
        return count

    # ------------------------------------------------------------------
    # Status & results
    # ------------------------------------------------------------------

    def get_status(self, task_id: str) -> TaskStatus:
        descriptor = self._descriptors.get(task_id)
        if descriptor is None:
            raise KeyError(f"Task {task_id} not found")
        return descriptor.status

    def get_descriptor(self, task_id: str) -> TaskDescriptor:
        descriptor = self._descriptors.get(task_id)
        if descriptor is None:
            raise KeyError(f"Task {task_id} not found")
        return descriptor

    def get_result(self, task_id: str) -> Any:
        if task_id in self._results:
            return self._results[task_id]
        raise KeyError(f"No result for task {task_id}")

    def get_error(self, task_id: str) -> str | None:
        return self._errors.get(task_id)

    async def wait(self, task_id: str, timeout: float | None = None) -> Any:
        """Wait for a task to complete and return its result."""
        event = self._events.get(task_id)
        if event is None:
            raise KeyError(f"Task {task_id} not found")
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except TimeoutError:
            raise TimeoutError(f"Timed out waiting for task {task_id}")
        if task_id in self._results:
            return self._results[task_id]
        if task_id in self._errors:
            raise RuntimeError(self._errors[task_id])
        raise RuntimeError(f"Task {task_id} did not produce a result")

    def list_tasks(self) -> list[TaskDescriptor]:
        return list(self._descriptors.values())

    def get_stats(self) -> dict[str, Any]:
        statuses = dict.fromkeys(TaskStatus, 0)
        for desc in self._descriptors.values():
            statuses[desc.status] = statuses.get(desc.status, 0) + 1
        return {
            "total_tasks": len(self._descriptors),
            "by_status": statuses,
            "pending": statuses.get(TaskStatus.PENDING, 0),
            "running": statuses.get(TaskStatus.RUNNING, 0),
            "completed": statuses.get(TaskStatus.COMPLETED, 0),
            "failed": statuses.get(TaskStatus.FAILED, 0),
            "cancelled": statuses.get(TaskStatus.CANCELLED, 0),
            "retrying": statuses.get(TaskStatus.RETRYING, 0),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish(self, event_type: str, data: dict[str, Any]) -> None:
        if self._event_bus:
            self._event_bus.publish(ZaramEvent(
                source_runtime="task_queue",
                event_type=event_type,
                data=data,
            ))

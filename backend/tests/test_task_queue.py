# backend/tests/test_task_queue.py
"""Unit tests for the TaskQueue."""
from __future__ import annotations

import asyncio

import pytest

from core.contracts import (
    CancellationSignal,
    TaskCancelledError,
    TaskPriority,
    TaskStatus,
)
from core.event_bus import EventBus
from core.task_queue import TaskQueue
from core.execution_context import ExecutionContext
from core.retry_policy import RetryPolicy


@pytest.fixture
async def task_queue():
    queue = TaskQueue(event_bus=EventBus())
    queue.start(worker_count=2)
    yield queue
    await queue.stop()


@pytest.fixture
async def no_worker_queue():
    queue = TaskQueue(event_bus=EventBus())
    yield queue
    await queue.stop()


class TestTaskQueueEnqueue:
    @pytest.mark.asyncio
    async def test_enqueue_returns_task_id(self, no_worker_queue):
        async def executor(ctx):
            return "result"

        task_id = await no_worker_queue.enqueue(
            capability_id="test.cap",
            input_data={"key": "value"},
            executor=executor,
        )
        assert task_id is not None
        assert len(task_id) > 0

    @pytest.mark.asyncio
    async def test_enqueue_with_priority(self, no_worker_queue):
        async def executor(ctx):
            return "result"

        task_id = await no_worker_queue.enqueue(
            capability_id="test.cap",
            input_data={},
            executor=executor,
            priority=TaskPriority.HIGH,
        )
        desc = no_worker_queue.get_descriptor(task_id)
        assert desc.priority == TaskPriority.HIGH

    @pytest.mark.asyncio
    async def test_enqueue_with_correlation_id(self, no_worker_queue):
        async def executor(ctx):
            return "result"

        task_id = await no_worker_queue.enqueue(
            capability_id="test.cap",
            input_data={},
            executor=executor,
            correlation_id="corr-123",
        )
        desc = no_worker_queue.get_descriptor(task_id)
        assert desc.correlation_id == "corr-123"

    @pytest.mark.asyncio
    async def test_enqueue_with_dependencies(self, no_worker_queue):
        async def executor(ctx):
            return "result"

        dep_id = await no_worker_queue.enqueue(
            capability_id="dep.cap",
            input_data={},
            executor=executor,
        )
        task_id = await no_worker_queue.enqueue(
            capability_id="main.cap",
            input_data={},
            executor=executor,
            depends_on=[dep_id],
        )
        desc = no_worker_queue.get_descriptor(task_id)
        assert dep_id in desc.depends_on


class TestTaskQueueExecution:
    @pytest.mark.asyncio
    async def test_task_completes(self, task_queue):
        async def executor(ctx):
            return "hello"

        task_id = await task_queue.enqueue(
            capability_id="test.cap",
            input_data={},
            executor=executor,
        )
        result = await task_queue.wait(task_id, timeout=5.0)
        assert result == "hello"
        assert task_queue.get_status(task_id) == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_task_failure(self, task_queue):
        async def executor(ctx):
            raise ValueError("test error")

        task_id = await task_queue.enqueue(
            capability_id="test.cap",
            input_data={},
            executor=executor,
            max_retries=0,
        )
        with pytest.raises(RuntimeError, match="test error"):
            await task_queue.wait(task_id, timeout=5.0)
        assert task_queue.get_status(task_id) == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_task_retry_succeeds(self, task_queue):
        call_count = 0

        async def executor(ctx):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("transient")
            return "recovered"

        task_id = await task_queue.enqueue(
            capability_id="test.cap",
            input_data={},
            executor=executor,
            max_retries=3,
        )
        result = await task_queue.wait(task_id, timeout=10.0)
        assert result == "recovered"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_task_retry_exhausted(self, task_queue):
        call_count = 0

        async def executor(ctx):
            nonlocal call_count
            call_count += 1
            raise ConnectionError("always fails")

        task_id = await task_queue.enqueue(
            capability_id="test.cap",
            input_data={},
            executor=executor,
            max_retries=2,
        )
        with pytest.raises(RuntimeError):
            await task_queue.wait(task_id, timeout=10.0)
        assert call_count == 3  # initial + 2 retries
        assert task_queue.get_status(task_id) == TaskStatus.FAILED


class TestTaskQueueCancellation:
    @pytest.mark.asyncio
    async def test_cancel_pending_task(self, no_worker_queue):
        async def executor(ctx):
            return "result"

        task_id = await no_worker_queue.enqueue(
            capability_id="test.cap",
            input_data={},
            executor=executor,
        )
        assert no_worker_queue.cancel(task_id, "user cancelled") is True
        desc = no_worker_queue.get_descriptor(task_id)
        assert desc.status == TaskStatus.PENDING  # still pending, not yet cancelled
        assert desc.cancellation.cancelled is True

    @pytest.mark.asyncio
    async def test_cancel_running_task(self, task_queue):
        started = asyncio.Event()
        release = asyncio.Event()

        async def executor(ctx):
            started.set()
            try:
                await asyncio.wait_for(release.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                pass
            return "done"

        task_id = await task_queue.enqueue(
            capability_id="test.cap",
            input_data={},
            executor=executor,
        )
        await started.wait()
        assert task_queue.cancel(task_id, "stop") is True
        release.set()
        await asyncio.sleep(0.1)
        desc = task_queue.get_descriptor(task_id)
        assert desc.status in (TaskStatus.CANCELLED, TaskStatus.COMPLETED)

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self, no_worker_queue):
        assert no_worker_queue.cancel("nonexistent", "reason") is False

    @pytest.mark.asyncio
    async def test_cancel_completed_task(self, task_queue):
        async def executor(ctx):
            return "done"

        task_id = await task_queue.enqueue(
            capability_id="test.cap",
            input_data={},
            executor=executor,
        )
        await task_queue.wait(task_id, timeout=5.0)
        assert task_queue.cancel(task_id, "too late") is False

    @pytest.mark.asyncio
    async def test_cancel_by_correlation(self, no_worker_queue):
        async def executor(ctx):
            return "result"

        await no_worker_queue.enqueue(
            capability_id="test.cap",
            input_data={},
            executor=executor,
            correlation_id="corr-1",
        )
        await no_worker_queue.enqueue(
            capability_id="test.cap",
            input_data={},
            executor=executor,
            correlation_id="corr-1",
        )
        await no_worker_queue.enqueue(
            capability_id="test.cap",
            input_data={},
            executor=executor,
            correlation_id="corr-2",
        )
        count = no_worker_queue.cancel_by_correlation("corr-1", "batch cancel")
        assert count == 2


class TestTaskQueueStats:
    @pytest.mark.asyncio
    async def test_get_stats(self, no_worker_queue):
        stats = no_worker_queue.get_stats()
        assert stats["total_tasks"] == 0
        assert stats["pending"] == 0

    @pytest.mark.asyncio
    async def test_get_status(self, no_worker_queue):
        async def executor(ctx):
            return "result"

        task_id = await no_worker_queue.enqueue(
            capability_id="test.cap",
            input_data={},
            executor=executor,
        )
        assert no_worker_queue.get_status(task_id) == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_status_nonexistent(self, no_worker_queue):
        with pytest.raises(KeyError):
            no_worker_queue.get_status("nonexistent")

    @pytest.mark.asyncio
    async def test_list_tasks(self, no_worker_queue):
        async def executor(ctx):
            return "result"

        await no_worker_queue.enqueue(
            capability_id="test.cap",
            input_data={},
            executor=executor,
        )
        tasks = no_worker_queue.list_tasks()
        assert len(tasks) == 1


class TestTaskQueueTimeout:
    @pytest.mark.asyncio
    async def test_wait_timeout(self, task_queue):
        async def executor(ctx):
            await asyncio.sleep(10)
            return "late"

        task_id = await task_queue.enqueue(
            capability_id="test.cap",
            input_data={},
            executor=executor,
        )
        with pytest.raises(TimeoutError):
            await task_queue.wait(task_id, timeout=0.5)

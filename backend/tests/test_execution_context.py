# backend/tests/test_execution_context.py
"""Unit tests for the ExecutionContext."""
from __future__ import annotations

import time

import pytest

from core.execution_context import ExecutionContext
from core.contracts import (
    CancellationSignal,
    TaskCancelledError,
    TaskDescriptor,
    TaskPriority,
)
from core.retry_policy import RetryPolicy


class TestExecutionContext:
    def test_create_basic(self):
        ctx = ExecutionContext(
            correlation_id="test-123",
            capability_id="reasoning.generate",
            input_data={"prompt": "hello"},
        )
        assert ctx.correlation_id == "test-123"
        assert ctx.capability_id == "reasoning.generate"
        assert ctx.input_data == {"prompt": "hello"}
        assert ctx.priority == TaskPriority.NORMAL
        assert ctx.deadline is None

    def test_from_descriptor(self):
        descriptor = TaskDescriptor(
            task_id="task-1",
            capability_id="reasoning.generate",
            input_data={"prompt": "test"},
            priority=TaskPriority.HIGH,
            correlation_id="corr-1",
            started_at=time.time(),
        )
        ctx = ExecutionContext.from_descriptor(descriptor)
        assert ctx.correlation_id == "corr-1"
        assert ctx.capability_id == "reasoning.generate"
        assert ctx.priority == TaskPriority.HIGH

    def test_check_cancellation_not_cancelled(self):
        ctx = ExecutionContext(
            correlation_id="test",
            capability_id="test",
            input_data={},
        )
        ctx.check_cancellation()  # Should not raise

    def test_check_cancellation_cancelled(self):
        ctx = ExecutionContext(
            correlation_id="test",
            capability_id="test",
            input_data={},
        )
        ctx.cancel("user requested")
        with pytest.raises(TaskCancelledError, match="user requested"):
            ctx.check_cancellation()

    def test_cancel(self):
        ctx = ExecutionContext(
            correlation_id="test",
            capability_id="test",
            input_data={},
        )
        ctx.cancel("done")
        assert ctx.cancellation.cancelled is True
        assert ctx.cancellation.reason == "done"

    def test_elapsed(self):
        ctx = ExecutionContext(
            correlation_id="test",
            capability_id="test",
            input_data={},
            start_time=time.time() - 5.0,
        )
        assert ctx.elapsed >= 5.0

    def test_remaining_no_deadline(self):
        ctx = ExecutionContext(
            correlation_id="test",
            capability_id="test",
            input_data={},
        )
        assert ctx.remaining is None

    def test_remaining_with_deadline(self):
        ctx = ExecutionContext(
            correlation_id="test",
            capability_id="test",
            input_data={},
            deadline=time.time() + 10.0,
        )
        remaining = ctx.remaining
        assert remaining is not None
        assert remaining <= 10.0

    def test_is_expired_no_deadline(self):
        ctx = ExecutionContext(
            correlation_id="test",
            capability_id="test",
            input_data={},
        )
        assert ctx.is_expired() is False

    def test_is_expired_with_deadline(self):
        ctx = ExecutionContext(
            correlation_id="test",
            capability_id="test",
            input_data={},
            deadline=time.time() - 1.0,
        )
        assert ctx.is_expired() is True

    def test_with_deadline(self):
        ctx = ExecutionContext(
            correlation_id="test",
            capability_id="test",
            input_data={},
        )
        new_ctx = ctx.with_deadline(30.0)
        assert new_ctx.deadline is not None
        assert new_ctx.deadline > time.time()
        # Original should be unchanged
        assert ctx.deadline is None

    def test_with_metadata(self):
        ctx = ExecutionContext(
            correlation_id="test",
            capability_id="test",
            input_data={},
        )
        new_ctx = ctx.with_metadata(model="gemma3", persona="zaram_prime")
        assert new_ctx.metadata["model"] == "gemma3"
        assert new_ctx.metadata["persona"] == "zaram_prime"
        # Original should be unchanged
        assert ctx.metadata == {}

    def test_with_metadata_merges(self):
        ctx = ExecutionContext(
            correlation_id="test",
            capability_id="test",
            input_data={},
            metadata={"existing": "value"},
        )
        new_ctx = ctx.with_metadata(new_key="new_value")
        assert new_ctx.metadata["existing"] == "value"
        assert new_ctx.metadata["new_key"] == "new_value"

    def test_custom_retry_policy(self):
        custom = RetryPolicy(max_retries=10)
        ctx = ExecutionContext(
            correlation_id="test",
            capability_id="test",
            input_data={},
            retry_policy=custom,
        )
        assert ctx.retry_policy.max_retries == 10

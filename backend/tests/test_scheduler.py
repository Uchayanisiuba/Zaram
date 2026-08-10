# backend/tests/test_scheduler.py
"""Unit tests for the RuntimeScheduler."""
from __future__ import annotations

import asyncio

import pytest

from core.contracts import (
    ExecutionPlan,
    ExecutionStep,
    TaskPriority,
    TaskStatus,
)
from core.event_bus import EventBus
from core.task_queue import TaskQueue
from core.scheduler import RuntimeScheduler


@pytest.fixture
async def scheduler():
    queue = TaskQueue(event_bus=EventBus())
    queue.start(worker_count=2)
    sched = RuntimeScheduler(queue, EventBus())
    yield sched
    await queue.stop()


class TestSchedulerPriority:
    def test_infer_priority_speech(self, scheduler):
        step = ExecutionStep(capability_id="speech.tts", input_data={})
        assert scheduler.infer_priority(step) == TaskPriority.HIGH

    def test_infer_priority_reasoning(self, scheduler):
        step = ExecutionStep(capability_id="reasoning.generate", input_data={})
        assert scheduler.infer_priority(step) == TaskPriority.NORMAL

    def test_infer_priority_knowledge(self, scheduler):
        step = ExecutionStep(capability_id="knowledge.search", input_data={})
        assert scheduler.infer_priority(step) == TaskPriority.NORMAL

    def test_infer_priority_filesystem(self, scheduler):
        step = ExecutionStep(capability_id="filesystem.search", input_data={})
        assert scheduler.infer_priority(step) == TaskPriority.LOW

    def test_infer_priority_internet(self, scheduler):
        step = ExecutionStep(capability_id="internet.search", input_data={})
        assert scheduler.infer_priority(step) == TaskPriority.BACKGROUND

    def test_infer_priority_unknown(self, scheduler):
        step = ExecutionStep(capability_id="unknown.cap", input_data={})
        assert scheduler.infer_priority(step) == TaskPriority.NORMAL


class TestSchedulerSchedule:
    @pytest.mark.asyncio
    async def test_schedule_plan(self, scheduler):
        plan = ExecutionPlan(
            original_prompt="test",
            steps=[
                ExecutionStep(capability_id="test.cap1", input_data={"prompt": "test"}),
            ],
        )

        async def executor(step, context):
            return "result1"

        correlation_id = await scheduler.schedule(plan, executor)
        assert correlation_id == plan.correlation_id
        assert correlation_id in scheduler.list_plans()

    @pytest.mark.asyncio
    async def test_schedule_plan_with_dependencies(self, scheduler):
        plan = ExecutionPlan(
            original_prompt="test",
            steps=[
                ExecutionStep(capability_id="test.cap1", input_data={}),
                ExecutionStep(capability_id="test.cap2", input_data={}, depends_on=[0]),
            ],
        )

        async def executor(step, context):
            return f"result for {step.capability_id}"

        correlation_id = await scheduler.schedule(plan, executor)
        results = await scheduler.wait_for_plan(correlation_id, timeout=5.0)
        assert len(results) == 2
        assert all(r is not None for r in results)

    @pytest.mark.asyncio
    async def test_wait_for_plan(self, scheduler):
        plan = ExecutionPlan(
            original_prompt="test",
            steps=[
                ExecutionStep(capability_id="test.cap", input_data={}),
            ],
        )

        async def executor(step, context):
            return "done"

        correlation_id = await scheduler.schedule(plan, executor)
        results = await scheduler.wait_for_plan(correlation_id, timeout=5.0)
        assert results == ["done"]

    @pytest.mark.asyncio
    async def test_cancel_plan(self, scheduler):
        plan = ExecutionPlan(
            original_prompt="test",
            steps=[
                ExecutionStep(capability_id="test.cap", input_data={}),
            ],
        )

        async def executor(step, context):
            await asyncio.sleep(10)
            return "done"

        correlation_id = await scheduler.schedule(plan, executor)
        count = scheduler.cancel_plan(correlation_id, "user cancelled")
        assert count >= 1

    @pytest.mark.asyncio
    async def test_get_plan_status(self, scheduler):
        plan = ExecutionPlan(
            original_prompt="test",
            steps=[
                ExecutionStep(capability_id="test.cap", input_data={}),
            ],
        )

        async def executor(step, context):
            return "done"

        correlation_id = await scheduler.schedule(plan, executor)
        status = scheduler.get_plan_status(correlation_id)
        assert status["correlation_id"] == correlation_id
        assert "tasks" in status

    @pytest.mark.asyncio
    async def test_list_plans(self, scheduler):
        plan = ExecutionPlan(
            original_prompt="test",
            steps=[
                ExecutionStep(capability_id="test.cap", input_data={}),
            ],
        )

        async def executor(step, context):
            return "done"

        await scheduler.schedule(plan, executor)
        plans = scheduler.list_plans()
        assert plan.correlation_id in plans

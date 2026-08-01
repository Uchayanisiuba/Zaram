# backend/core/scheduler.py
"""Runtime scheduler.

The scheduler takes an :class:`~core.contracts.ExecutionPlan` and
dispatches its steps to the :class:`~core.task_queue.TaskQueue` with
appropriate priorities, dependency tracking, and cancellation support.
"""
from __future__ import annotations

import logging
from typing import Any

from core.contracts import (
    ExecutionPlan,
    ExecutionStep,
    TaskPriority,
    TaskStatus,
)
from core.event_bus import EventBus, ZaramEvent
from core.task_queue import TaskQueue

logger = logging.getLogger(__name__)


# Map capability prefixes to priorities
_CAPABILITY_PRIORITY: dict[str, TaskPriority] = {
    "speech.": TaskPriority.HIGH,
    "reasoning.": TaskPriority.NORMAL,
    "knowledge.": TaskPriority.NORMAL,
    "memory.": TaskPriority.NORMAL,
    "filesystem.": TaskPriority.LOW,
    "internet.": TaskPriority.BACKGROUND,
    "tool.": TaskPriority.LOW,
    "vision.": TaskPriority.NORMAL,
}


class RuntimeScheduler:
    """Schedules execution plans onto the task queue.

    The scheduler is the bridge between the IntentPlanner (which produces
    ExecutionPlans) and the TaskQueue (which executes them).  It assigns
    priorities, resolves step dependencies, and manages task lifecycles.
    """

    def __init__(
        self,
        task_queue: TaskQueue,
        event_bus: EventBus | None = None,
    ) -> None:
        self._task_queue = task_queue
        self._event_bus = event_bus
        self._scheduled: dict[str, list[str]] = {}  # correlation_id -> task_ids
        self._active_plans: dict[str, ExecutionPlan] = {}

    def infer_priority(self, step: ExecutionStep) -> TaskPriority:
        """Infer task priority from the capability_id prefix."""
        for prefix, priority in _CAPABILITY_PRIORITY.items():
            if step.capability_id.startswith(prefix):
                return priority
        return TaskPriority.NORMAL

    async def schedule(
        self,
        plan: ExecutionPlan,
        executor_fn,
    ) -> str:
        """Schedule all steps in an execution plan.

        Parameters
        ----------
        plan:
            The execution plan to schedule.
        executor_fn:
            A callable that accepts (step, context) and returns an awaitable.
            The scheduler wraps this into a task executor.

        Returns
        -------
        str
            The correlation_id of the scheduled plan.
        """
        task_ids: list[str] = []
        step_to_task: dict[int, str] = {}

        for i, step in enumerate(plan.steps):
            # Resolve depends_on (indices) to task_ids
            dep_task_ids: list[str] = []
            for dep_idx in step.depends_on:
                if dep_idx in step_to_task:
                    dep_task_ids.append(step_to_task[dep_idx])

            priority = self.infer_priority(step)

            task_id = await self._task_queue.enqueue(
                capability_id=step.capability_id,
                input_data=step.input_data,
                executor=self._make_executor(step, executor_fn),
                priority=priority,
                correlation_id=plan.correlation_id,
                depends_on=dep_task_ids,
            )
            task_ids.append(task_id)
            step_to_task[i] = task_id

        self._scheduled[plan.correlation_id] = task_ids
        self._active_plans[plan.correlation_id] = plan

        self._publish("scheduler.plan_scheduled", {
            "correlation_id": plan.correlation_id,
            "task_count": len(task_ids),
            "task_ids": task_ids,
        })
        logger.info("Scheduler: scheduled plan %s with %d tasks", plan.correlation_id, len(task_ids))
        return plan.correlation_id

    def _make_executor(self, step: ExecutionStep, executor_fn):
        """Create an async executor closure for a single step."""
        async def _executor(context):
            from core.execution_context import ExecutionContext
            ctx = context if isinstance(context, ExecutionContext) else None
            if ctx is None:
                ctx = ExecutionContext(
                    correlation_id=context.correlation_id if hasattr(context, 'correlation_id') else "",
                    capability_id=step.capability_id,
                    input_data=step.input_data,
                )
            result = await executor_fn(step, ctx)
            step.output_data = {"result": result} if not isinstance(result, dict) else result
            step.status = "completed"
            return result
        return _executor

    async def wait_for_plan(self, correlation_id: str, timeout: float | None = None) -> list[Any]:
        """Wait for all tasks in a plan to complete."""
        task_ids = self._scheduled.get(correlation_id, [])
        if not task_ids:
            raise KeyError(f"Plan {correlation_id} not found")

        results = []
        for task_id in task_ids:
            try:
                result = await self._task_queue.wait(task_id, timeout=timeout)
                results.append(result)
            except Exception as exc:
                results.append(None)
                logger.warning("Scheduler: task %s failed: %s", task_id, exc)
        return results

    def cancel_plan(self, correlation_id: str, reason: str = "") -> int:
        """Cancel all tasks in a plan."""
        task_ids = self._scheduled.get(correlation_id, [])
        count = 0
        for task_id in task_ids:
            if self._task_queue.cancel(task_id, reason):
                count += 1
        if correlation_id in self._active_plans:
            del self._active_plans[correlation_id]
        self._publish("scheduler.plan_cancelled", {
            "correlation_id": correlation_id,
            "cancelled_tasks": count,
            "reason": reason,
        })
        return count

    def get_plan_status(self, correlation_id: str) -> dict[str, Any]:
        """Get the status of all tasks in a plan."""
        task_ids = self._scheduled.get(correlation_id, [])
        statuses = {}
        for task_id in task_ids:
            try:
                desc = self._task_queue.get_descriptor(task_id)
                statuses[task_id] = {
                    "capability_id": desc.capability_id,
                    "status": desc.status.value,
                    "retry_count": desc.retry_count,
                    "error": desc.error,
                }
            except KeyError:
                statuses[task_id] = {"status": "unknown"}
        return {
            "correlation_id": correlation_id,
            "tasks": statuses,
            "all_completed": all(
                s.get("status") == TaskStatus.COMPLETED.value
                for s in statuses.values()
            ) if statuses else False,
        }

    def list_plans(self) -> list[str]:
        return list(self._active_plans.keys())

    def _publish(self, event_type: str, data: dict[str, Any]) -> None:
        if self._event_bus:
            self._event_bus.publish(ZaramEvent(
                source_runtime="scheduler",
                event_type=event_type,
                data=data,
            ))

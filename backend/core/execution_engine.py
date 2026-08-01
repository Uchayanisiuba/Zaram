# backend/core/execution_engine.py
"""ExecutionEngine — the kernel's central orchestrator.

The ExecutionEngine ties together all kernel subsystems:

    User prompt
        ↓  IntentPlanner (Runtime_Intent)
    ExecutionPlan
        ↓  CapabilityRouter (Capability Resolution)
    Runtime
        ↓  ExecutionDispatcher (Runtime_Dispatcher)
    Streamed response

The engine supports two execution paths:

1. **Legacy synchronous path** (``execute``) — streams string tokens
   directly.  Used by the existing ChatRouter and tests.

2. **Task queue path** (``execute_async``) — schedules tasks onto the
   TaskQueue with priority, cancellation, and retry.  Used when the
   engine is running inside an async event loop with workers started.

No runtime directly calls another runtime.  All cross-runtime
communication flows through the EventBus.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

from core.capability_router import CapabilityRouter
from core.contracts import (
    ExecutionPlan,
    ExecutionStep,
    PlanState,
    TaskPriority,
)
from core.dispatcher import ExecutionDispatcher
from core.event_bus import EventBus, ZaramEvent
from core.execution_context import ExecutionContext
from core.planner import IntentClassification, IntentPlanner
from core.registry import RuntimeRegistry
from core.scheduler import RuntimeScheduler
from core.task_queue import TaskQueue

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """The operational core of Zaram. Orchestrates the lifecycle of a user request.

    The engine owns the IntentPlanner, CapabilityRouter, and
    ExecutionDispatcher.  It optionally integrates with the TaskQueue
    and Scheduler for advanced execution with priority, cancellation,
    and retry.
    """

    def __init__(
        self,
        registry: RuntimeRegistry,
        event_bus: EventBus,
        task_queue: TaskQueue | None = None,
        scheduler: RuntimeScheduler | None = None,
    ) -> None:
        self._registry = registry
        self._event_bus = event_bus
        self._planner = IntentPlanner()
        self._router = CapabilityRouter(registry)
        self._dispatcher = ExecutionDispatcher(self._router)
        self._task_queue = task_queue
        self._scheduler = scheduler
        self._active_plans: dict[str, ExecutionPlan] = {}

    # ------------------------------------------------------------------
    # Legacy synchronous execution (backward compatible)
    # ------------------------------------------------------------------

    def execute(
        self,
        prompt: str,
        model: str = "gemma3:latest",
        system_prompt: str = "",
    ) -> Iterator[str]:
        """End-to-end execution: Plan -> Route -> Dispatch -> Stream with graceful degradation.

        This is the legacy synchronous path.  It creates a plan,
        executes each step sequentially, and streams tokens back.
        """
        logger.debug("Engine: execute prompt='%s...' model=%s", prompt[:50], model)
        plan = self._planner.create_plan(prompt)
        plan.state = PlanState.RUNNING
        logger.debug("Engine: plan created with %d steps", len(plan.steps))

        self._active_plans[plan.correlation_id] = plan
        self._publish("execution.plan_created", {
            "correlation_id": plan.correlation_id,
            "step_count": len(plan.steps),
        })

        step_results: dict[str, str] = {}
        failed_steps: list[dict[str, Any]] = []

        for i, step in enumerate(plan.steps):
            self._publish("execution.step_started", {
                "correlation_id": plan.correlation_id,
                "capability_id": step.capability_id,
                "step_index": i,
            })

            logger.debug("Engine: executing step %d/%d: %s", i + 1, len(plan.steps), step.capability_id)

            step_output = ""
            step_failed = False
            step_error: str | None = None

            try:
                for token in self._dispatcher.execute_step(step, model, system_prompt):
                    step_output += token
                    yield token

                if step_output.strip().startswith("[FALLBACK]") or step_output.strip().startswith("[WARN]"):
                    step_failed = True
                    step_error = step_output.strip()
                    logger.warning("Engine: step %d (%s) returned fallback: %s", i + 1, step.capability_id, step_error[:100])
                elif step.capability_id == "knowledge.search":
                    try:
                        parsed = json.loads(step_output)
                        if parsed.get("fallback") or parsed.get("error"):
                            step_failed = True
                            step_error = parsed.get("error", "unknown error")
                            logger.warning("Engine: knowledge search returned fallback: %s", step_error)
                    except Exception:
                        pass

            except Exception as exc:
                step_failed = True
                step_error = str(exc)
                logger.error("Engine: step %d (%s) threw exception: %s: %s", i + 1, step.capability_id, type(exc).__name__, exc)

            if step_failed:
                failed_steps.append({"capability_id": step.capability_id, "error": step_error, "index": i})
                step.status = "failed"
            else:
                step.status = "completed"

            step_results[step.capability_id] = step_output

            self._publish("execution.step_completed" if not step_failed else "execution.step_failed", {
                "correlation_id": plan.correlation_id,
                "capability_id": step.capability_id,
                "step_index": i,
                "failed": step_failed,
                "error": step_error,
            })

        if failed_steps:
            if len(failed_steps) == len(plan.steps):
                plan.state = PlanState.FAILED
            else:
                plan.state = PlanState.DEGRADED
            logger.warning(
                "Engine: plan completed with %d/%d failed steps: %s",
                len(failed_steps),
                len(plan.steps),
                [f["capability_id"] for f in failed_steps],
            )
        else:
            plan.state = PlanState.COMPLETED
            logger.info("Engine: plan completed successfully")

        self._publish("execution.plan_completed", {
            "correlation_id": plan.correlation_id,
            "state": plan.state.value,
            "failed_steps": failed_steps,
        })

        if plan.correlation_id in self._active_plans:
            del self._active_plans[plan.correlation_id]

    # ------------------------------------------------------------------
    # Async execution with TaskQueue (new path)
    # ------------------------------------------------------------------

    async def execute_async(
        self,
        prompt: str,
        model: str = "gemma3:latest",
        system_prompt: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: float | None = None,
    ) -> str:
        """Schedule a request onto the TaskQueue and return the correlation_id.

        This is the new async path that uses the TaskQueue and Scheduler
        for priority-based execution with cancellation and retry.

        The caller must start the TaskQueue workers before calling this
        method, and use ``wait_for_result`` to retrieve the output.
        """
        if self._task_queue is None or self._scheduler is None:
            raise RuntimeError("TaskQueue and Scheduler must be configured for async execution")

        plan = self._planner.create_plan(prompt)
        plan.state = PlanState.RUNNING
        plan.priority = priority.value
        self._active_plans[plan.correlation_id] = plan

        self._publish("execution.plan_created", {
            "correlation_id": plan.correlation_id,
            "step_count": len(plan.steps),
            "priority": priority.value,
        })

        correlation_id = await self._scheduler.schedule(plan, self._dispatch_step_async)
        return correlation_id

    async def _dispatch_step_async(self, step: ExecutionStep, context: ExecutionContext) -> Any:
        """Async step executor used by the scheduler."""
        return await self._dispatcher.dispatch(step, context)

    async def wait_for_result(
        self,
        correlation_id: str,
        timeout: float | None = None,
    ) -> list[Any]:
        """Wait for all tasks in a plan to complete and return results."""
        if self._scheduler is None:
            raise RuntimeError("Scheduler not configured")
        return await self._scheduler.wait_for_plan(correlation_id, timeout)

    def cancel_request(self, correlation_id: str, reason: str = "") -> int:
        """Cancel all tasks in a plan."""
        if self._scheduler is not None:
            return self._scheduler.cancel_plan(correlation_id, reason)
        if correlation_id in self._active_plans:
            del self._active_plans[correlation_id]
        return 0

    # ------------------------------------------------------------------
    # Intent classification
    # ------------------------------------------------------------------

    def classify_intent(self, prompt: str) -> IntentClassification:
        """Classify a user prompt into an intent."""
        return self._planner.classify_intent(prompt)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_plan_status(self, correlation_id: str) -> dict[str, Any] | None:
        """Get the status of a plan."""
        plan = self._active_plans.get(correlation_id)
        if plan is None:
            return None
        return {
            "correlation_id": correlation_id,
            "state": plan.state.value,
            "priority": plan.priority,
            "steps": [
                {"capability_id": s.capability_id, "status": s.status}
                for s in plan.steps
            ],
        }

    def list_active_plans(self) -> list[str]:
        return list(self._active_plans.keys())

    def get_task_queue(self) -> TaskQueue | None:
        return self._task_queue

    def get_scheduler(self) -> RuntimeScheduler | None:
        return self._scheduler

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _publish(self, event_type: str, data: dict[str, Any]) -> None:
        self._event_bus.publish(ZaramEvent(
            source_runtime="execution_engine",
            event_type=event_type,
            data=data,
        ))

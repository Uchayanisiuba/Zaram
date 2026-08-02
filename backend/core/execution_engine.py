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
import time
from collections.abc import Iterator
from typing import Any

from core.async_bridge import run_sync
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
        session_id: str = "default",
    ) -> Iterator[Any]:
        """End-to-end execution: Recall -> Plan -> Route -> Dispatch -> Stream.

        Yields plain strings for response tokens, and StreamEvent objects for
        structured output such as provenance. Callers that only understand
        strings continue to work unchanged.
        """
        logger.debug("Engine: execute prompt='%s...' model=%s", prompt[:50], model)

        # Provenance is emitted from two places — recall, and any search step.
        # Both can surface the same record, so dedupe across the whole request.
        seen_sources: set[str] = set()

        # --- Recall: what does the Spine already know that bears on this? ---
        recalled = self._recall(prompt, session_id)
        if recalled:
            system_prompt = self._augment_system_prompt(system_prompt, recalled)
            for event in self._provenance_events(recalled):
                key = event.data.get("url") or event.data.get("title", "")
                if key and key not in seen_sources:
                    seen_sources.add(key)
                    yield event

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
            # Internal steps gather context for later steps. Their raw output is
            # not user-facing and must not reach the stream.
            internal = step.capability_id in self.INTERNAL_CAPABILITIES

            try:
                for token in self._dispatcher.execute_step(step, model, system_prompt):
                    step_output += token
                    if not internal:
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

            # Fold a successful internal step's findings into the context the
            # next step sees, and surface its sources as provenance.
            if internal and not step_failed and step_output.strip():
                if step.capability_id == "knowledge.search":
                    sources = self._parse_search_results(step_output)
                    if sources:
                        system_prompt = self._augment_with_sources(system_prompt, sources)
                        for event in self._search_provenance_events(sources):
                            key = event.data.get("url") or event.data.get("title", "")
                            if key and key not in seen_sources:
                                seen_sources.add(key)
                                yield event

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

        # --- Remember: commit this exchange to the Spine. ---
        answer = step_results.get("reasoning.generate", "")
        self._remember(prompt, answer, session_id)

        if plan.correlation_id in self._active_plans:
            del self._active_plans[plan.correlation_id]

    # ------------------------------------------------------------------
    # Recall — the memory loop
    # ------------------------------------------------------------------

    MAX_RECALL = 5
    MIN_RECALL_SCORE = 0.25

    #: Capabilities whose output is context for later steps, never shown to the
    #: user. Their raw payloads (JSON search results, for example) would
    #: otherwise be streamed into the reply.
    INTERNAL_CAPABILITIES = frozenset({"knowledge.search"})

    # ------------------------------------------------------------------
    # Search results as context
    # ------------------------------------------------------------------

    def _parse_search_results(self, raw: str) -> list[dict[str, Any]]:
        """Pull the result list out of a knowledge.search payload."""
        try:
            parsed = json.loads(raw)
        except Exception:
            return []
        if not isinstance(parsed, dict):
            return []
        results = parsed.get("results") or []
        return [r for r in results if isinstance(r, dict)]

    def _augment_with_sources(self, system_prompt: str, sources: list[dict[str, Any]]) -> str:
        """Fold search results into the system prompt with citation markers."""
        lines = [
            "",
            "=== SOURCES RETRIEVED FOR THIS QUESTION ===",
            "",
        ]
        for i, source in enumerate(sources, 1):
            title = (source.get("title") or "").strip()
            url = (source.get("url") or "").strip()
            snippet = (source.get("snippet") or "").strip()
            lines.append(f"[S{i}] {title}" if title else f"[S{i}]")
            if url:
                lines.append(f"     {url}")
            if snippet:
                lines.append(f"     {snippet}")
        lines += [
            "",
            "INSTRUCTIONS:",
            "- Answer from these sources where they are relevant, naming them in plain",
            "  words. Never print the [S1] markers themselves — they are internal",
            "  labels and mean nothing to the user.",
            "- Prefer them over your training data where they conflict.",
            "- If they do not answer the question, say so rather than inventing detail.",
            "=" * 43,
            "",
        ]
        return (system_prompt or "") + "\n".join(lines)

    def _search_provenance_events(self, sources: list[dict[str, Any]]) -> list[Any]:
        """Emit one source event per search result, so the UI can show them."""
        from core.streaming_events import StreamEvent

        events = []
        for source in sources:
            events.append(StreamEvent.source(
                kind=source.get("provider") or "search",
                url=source.get("url"),
                title=(source.get("title") or "")[:120],
            ))
        return events

    def _memory_runtime(self) -> Any | None:
        """Resolve the memory runtime through the capability router.

        Returns None when no memory runtime is registered, so every call site
        degrades to the previous no-memory behaviour rather than failing.
        """
        try:
            return self._router.try_resolve("memory.retrieve")
        except Exception:
            return None

    def _recall(self, prompt: str, session_id: str) -> list[Any]:
        """Retrieve prior context relevant to this prompt."""
        runtime = self._memory_runtime()
        if runtime is None or not prompt.strip():
            return []
        try:
            results = run_sync(runtime.retrieve(
                query=prompt,
                max_results=self.MAX_RECALL,
                session_id=None,
            ))
        except Exception as exc:
            logger.warning("Engine: recall failed: %s: %s", type(exc).__name__, exc)
            return []

        kept = [r for r in results if getattr(r, "score", 0.0) >= self.MIN_RECALL_SCORE]
        logger.info("Engine: recalled %d/%d memories above threshold", len(kept), len(results))
        self._publish("memory.recalled", {
            "query": prompt[:100],
            "candidates": len(results),
            "used": len(kept),
        })
        return kept

    def _augment_system_prompt(self, system_prompt: str, recalled: list[Any]) -> str:
        """Fold recalled memories into the system prompt, with citation markers.

        Each memory is numbered so the model can cite it, and the instruction
        block tells it to say when it is drawing on memory.
        """
        lines = [
            "",
            "=== WHAT YOU REMEMBER ABOUT THIS USER ===",
            "These are facts from earlier exchanges, retrieved from local memory.",
            "",
        ]
        for i, result in enumerate(recalled, 1):
            record = result.record
            when = time.strftime("%Y-%m-%d", time.localtime(record.created_at))
            lines.append(f"[M{i}] ({when}) {record.content}")
        lines += [
            "",
            "INSTRUCTIONS:",
            "- Use these memories when they are relevant to the question.",
            "- When you rely on one, refer to it in plain words, e.g. 'you mentioned",
            "  earlier that...'. Never print the [M1] markers themselves — they are",
            "  internal labels and mean nothing to the user.",
            "- If they do not bear on the question, ignore them silently.",
            "- Never invent a memory that is not listed above.",
            "=" * 42,
            "",
        ]
        return (system_prompt or "") + "\n".join(lines)

    def _provenance_events(self, recalled: list[Any]) -> list[Any]:
        """Emit one source event per recalled memory, so the UI can show them."""
        from core.streaming_events import StreamEvent

        events = []
        for result in recalled:
            record = result.record
            # Stored exchanges span lines; collapse them so the title reads as a
            # single line in the UI.
            snippet = " ".join(record.content.split())
            if len(snippet) > 120:
                snippet = snippet[:117] + "..."
            events.append(StreamEvent.source(
                kind="memory",
                url=f"memory:{record.id}",
                title=snippet,
            ))
        return events

    def _remember(self, prompt: str, answer: str, session_id: str) -> None:
        """Store this exchange so a later question can recall it."""
        runtime = self._memory_runtime()
        if runtime is None:
            return
        answer = (answer or "").strip()
        if not prompt.strip() or not answer or answer.startswith("[FALLBACK]"):
            return
        # Imported lazily: core/ does not depend on a runtime at module load.
        from runtimes.memory.contracts import MemoryType

        try:
            run_sync(runtime.remember(
                content=f"User asked: {prompt}\nZaram answered: {answer}",
                memory_type=MemoryType.CONVERSATION,
                session_id=session_id,
                metadata={"prompt": prompt, "answer": answer},
                tags=["conversation"],
            ))
            logger.info("Engine: stored exchange in the Spine (session=%s)", session_id)
        except Exception as exc:
            logger.warning("Engine: remember failed: %s: %s", type(exc).__name__, exc)

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

from __future__ import annotations

import time
import uuid
from typing import Any, Callable

from core.contracts import Runtime, RuntimeMetadata, Capability, RuntimeState
from core.event_bus import EventBus, ZaramEvent

from .contracts import (
    AgentConfig,
    AgentState,
    AgentStatus,
    AgentTask,
    TaskStatus,
)


class AgentRuntime(Runtime):
    """Manages autonomous agent lifecycle and task execution.

    The Agent Runtime subscribes to ``agent.*`` events, manages agent
    state, and executes tasks. All communication is through the Event Bus.

    Agents are lightweight task executors that can be created, started,
    paused, and stopped. Each agent can process tasks concurrently up
    to its configured limit.
    """

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._state = RuntimeState.UNINITIALIZED
        self._start_time = time.time()
        self._agents: dict[str, AgentConfig] = {}
        self._agent_states: dict[str, AgentState] = {}
        self._tasks: dict[str, AgentTask] = {}
        self._task_handlers: dict[str, Callable[[AgentTask], dict[str, Any]]] = {}
        self._stats: dict[str, Any] = {
            "agents_created": 0,
            "agents_active": 0,
            "tasks_created": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "total_task_duration_ms": 0.0,
        }

    def get_runtime_id(self) -> str:
        return "agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_id="agent",
            version="1.0.0",
            priority="high",
            capabilities=[
                Capability(id="agent.create", runtime_id="agent", category="agent"),
                Capability(id="agent.execute", runtime_id="agent", category="agent"),
                Capability(id="agent.task", runtime_id="agent", category="agent"),
                Capability(id="agent.list", runtime_id="agent", category="agent"),
                Capability(id="agent.status", runtime_id="agent", category="agent"),
            ],
            dependencies=["event_bus"],
            auto_start=True,
        )

    async def initialize(self) -> None:
        self._state = RuntimeState.INITIALIZING
        self._event_bus.subscribe("agent.create", self._handle_create)
        self._event_bus.subscribe("agent.execute", self._handle_execute)
        self._event_bus.subscribe("agent.task", self._handle_task)
        self._event_bus.subscribe("agent.list", self._handle_list)
        self._event_bus.subscribe("agent.status", self._handle_status)
        self._state = RuntimeState.READY
        self._event_bus.publish(ZaramEvent(
            source_runtime="agent",
            event_type="runtime.ready",
            data={"runtime_id": self.get_runtime_id()},
        ))
        print("[AgentRuntime] Initialized and subscribed to agent events")

    async def shutdown(self) -> None:
        self._state = RuntimeState.STOPPING
        for agent_id in list(self._agent_states.keys()):
            self._agent_states[agent_id].status = AgentStatus.STOPPED
        self._state = RuntimeState.STOPPED
        print("[AgentRuntime] Shut down")

    def get_state(self) -> RuntimeState:
        return self._state

    def health_check(self) -> dict[str, Any]:
        return {
            "runtime_id": self.get_runtime_id(),
            "state": self._state.value,
            "uptime_seconds": time.time() - self._start_time,
            "stats": dict(self._stats),
            "agents": {
                aid: state.status.value for aid, state in self._agent_states.items()
            },
        }

    def get_stats(self) -> dict[str, Any]:
        return dict(self._stats)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_agent(self, config: AgentConfig) -> str:
        """Create a new agent. Returns the agent ID."""
        agent_id = config.agent_id or f"agent_{uuid.uuid4().hex[:8]}"
        if agent_id in self._agents:
            raise ValueError(f"Agent '{agent_id}' already exists")

        self._agents[agent_id] = config
        self._agent_states[agent_id] = AgentState(
            agent_id=agent_id,
            status=AgentStatus.RUNNING if config.auto_start else AgentStatus.IDLE,
        )
        self._stats["agents_created"] += 1
        self._stats["agents_active"] += 1

        self._event_bus.publish(ZaramEvent(
            source_runtime="agent",
            event_type="agent.created",
            priority="normal",
            data={
                "agent_id": agent_id,
                "name": config.name,
                "auto_start": config.auto_start,
                "status": self._agent_states[agent_id].status.value,
            },
        ))
        return agent_id

    def create_task(
        self,
        agent_id: str,
        description: str,
        input_data: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> str:
        """Create a task for an agent. Returns the task ID."""
        if agent_id not in self._agents:
            raise ValueError(f"Agent '{agent_id}' not found")

        task_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
        task = AgentTask(
            task_id=task_id,
            agent_id=agent_id,
            description=description,
            input_data=input_data or {},
        )
        self._tasks[task_id] = task
        self._stats["tasks_created"] += 1

        self._event_bus.publish(ZaramEvent(
            source_runtime="agent",
            event_type="agent.task_created",
            priority="normal",
            data={
                "task_id": task_id,
                "agent_id": agent_id,
                "description": description,
            },
        ))
        return task_id

    def execute_task(self, task_id: str) -> dict[str, Any]:
        """Execute a task synchronously. Returns the result."""
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found")

        if task.status in (TaskStatus.RUNNING, TaskStatus.COMPLETED):
            raise ValueError(f"Task '{task_id}' is already {task.status.value}")

        task.status = TaskStatus.RUNNING
        task.started_at = time.time()

        agent_state = self._agent_states.get(task.agent_id)
        if agent_state:
            agent_state.status = AgentStatus.RUNNING
            agent_state.current_task = task_id
            agent_state.last_activity = time.time()

        self._event_bus.publish(ZaramEvent(
            source_runtime="agent",
            event_type="agent.task_started",
            priority="high",
            data={
                "task_id": task_id,
                "agent_id": task.agent_id,
                "description": task.description,
            },
        ))

        start = time.time()
        try:
            handler = self._task_handlers.get(task.agent_id)
            if handler:
                result = handler(task)
            else:
                result = self._default_handler(task)

            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            self._stats["tasks_completed"] += 1
            latency_ms = (time.time() - start) * 1000
            self._stats["total_task_duration_ms"] += latency_ms

            if agent_state:
                agent_state.status = AgentStatus.IDLE
                agent_state.current_task = None
                agent_state.tasks_completed += 1
                agent_state.last_activity = time.time()

            self._event_bus.publish(ZaramEvent(
                source_runtime="agent",
                event_type="agent.task_completed",
                priority="normal",
                data={
                    "task_id": task_id,
                    "agent_id": task.agent_id,
                    "result": result,
                    "latency_ms": latency_ms,
                },
            ))
            return result

        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            task.completed_at = time.time()
            self._stats["tasks_failed"] += 1
            latency_ms = (time.time() - start) * 1000

            if agent_state:
                agent_state.status = AgentStatus.ERROR
                agent_state.current_task = None
                agent_state.tasks_failed += 1
                agent_state.last_activity = time.time()

            self._event_bus.publish(ZaramEvent(
                source_runtime="agent",
                event_type="agent.task_failed",
                priority="high",
                data={
                    "task_id": task_id,
                    "agent_id": task.agent_id,
                    "error": str(exc),
                    "latency_ms": latency_ms,
                    "success": False,
                },
            ))
            raise

    def register_handler(self, agent_id: str, handler: Callable[[AgentTask], dict[str, Any]]) -> None:
        """Register a task handler for an agent."""
        self._task_handlers[agent_id] = handler

    def get_agent_state(self, agent_id: str) -> AgentState | None:
        return self._agent_states.get(agent_id)

    def get_task(self, task_id: str) -> AgentTask | None:
        return self._tasks.get(task_id)

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {
                "agent_id": aid,
                "config": {
                    "name": cfg.name,
                    "description": cfg.description,
                    "capabilities": cfg.capabilities,
                    "max_concurrent_tasks": cfg.max_concurrent_tasks,
                },
                "state": state.__dict__ if hasattr(state, "__dict__") else {},
            }
            for aid, (cfg, state) in self._get_agent_pairs()
        ]

    def list_tasks(self, agent_id: str | None = None) -> list[dict[str, Any]]:
        tasks = list(self._tasks.values())
        if agent_id:
            tasks = [t for t in tasks if t.agent_id == agent_id]
        return [
            {
                "task_id": t.task_id,
                "agent_id": t.agent_id,
                "description": t.description,
                "status": t.status.value,
                "created_at": t.created_at,
                "duration_seconds": t.duration_seconds,
                "error": t.error,
            }
            for t in tasks
        ]

    def stop_agent(self, agent_id: str) -> None:
        """Stop an agent."""
        if agent_id not in self._agents:
            raise ValueError(f"Agent '{agent_id}' not found")
        state = self._agent_states.get(agent_id)
        if state:
            state.status = AgentStatus.STOPPED
            state.last_activity = time.time()
        self._event_bus.publish(ZaramEvent(
            source_runtime="agent",
            event_type="agent.stopped",
            priority="normal",
            data={"agent_id": agent_id},
        ))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_agent_pairs(self):
        for aid in self._agents:
            yield aid, (self._agents[aid], self._agent_states.get(aid))

    def _default_handler(self, task: AgentTask) -> dict[str, Any]:
        """Default task handler — echoes back the input."""
        return {
            "task_id": task.task_id,
            "agent_id": task.agent_id,
            "input": task.input_data,
            "executed_at": time.time(),
            "message": f"Task '{task.description}' completed by default handler",
        }

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _handle_create(self, event: ZaramEvent) -> None:
        data = event.data
        config = AgentConfig(
            agent_id=data.get("agent_id", ""),
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            capabilities=data.get("capabilities", []),
            max_concurrent_tasks=data.get("max_concurrent_tasks", 5),
            timeout_seconds=data.get("timeout_seconds", 30.0),
            auto_start=data.get("auto_start", True),
            metadata=data.get("metadata", {}),
        )
        try:
            agent_id = self.create_agent(config)
            self._event_bus.publish(ZaramEvent(
                source_runtime="agent",
                event_type="agent.create_result",
                correlation_id=event.correlation_id,
                priority="normal",
                data={"agent_id": agent_id, "success": True},
            ))
        except Exception as exc:
            self._event_bus.publish(ZaramEvent(
                source_runtime="agent",
                event_type="agent.create_result",
                correlation_id=event.correlation_id,
                priority="high",
                data={"success": False, "error": str(exc)},
            ))

    def _handle_execute(self, event: ZaramEvent) -> None:
        data = event.data
        agent_id = data.get("agent_id", "")
        description = data.get("description", "")
        input_data = data.get("input_data", {})
        task_id = data.get("task_id")
        try:
            tid = self.create_task(agent_id, description, input_data, task_id)
            result = self.execute_task(tid)
            self._event_bus.publish(ZaramEvent(
                source_runtime="agent",
                event_type="agent.execute_result",
                correlation_id=event.correlation_id,
                priority="normal",
                data={"task_id": tid, "result": result, "success": True},
            ))
        except Exception as exc:
            self._event_bus.publish(ZaramEvent(
                source_runtime="agent",
                event_type="agent.execute_result",
                correlation_id=event.correlation_id,
                priority="high",
                data={"success": False, "error": str(exc)},
            ))

    def _handle_task(self, event: ZaramEvent) -> None:
        data = event.data
        task_id = data.get("task_id", "")
        action = data.get("action", "get")
        if action == "get":
            task = self.get_task(task_id)
            self._event_bus.publish(ZaramEvent(
                source_runtime="agent",
                event_type="agent.task_result",
                correlation_id=event.correlation_id,
                priority="normal",
                data={
                    "task_id": task_id,
                    "task": task.__dict__ if task else None,
                },
            ))
        elif action == "cancel":
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                self._event_bus.publish(ZaramEvent(
                    source_runtime="agent",
                    event_type="agent.task_cancelled",
                    correlation_id=event.correlation_id,
                    priority="normal",
                    data={"task_id": task_id, "success": True},
                ))

    def _handle_list(self, event: ZaramEvent) -> None:
        agents = self.list_agents()
        tasks = self.list_tasks()
        self._event_bus.publish(ZaramEvent(
            source_runtime="agent",
            event_type="agent.list_result",
            correlation_id=event.correlation_id,
            priority="normal",
            data={"agents": agents, "tasks": tasks},
        ))

    def _handle_status(self, event: ZaramEvent) -> None:
        data = event.data
        agent_id = data.get("agent_id", "")
        state = self.get_agent_state(agent_id)
        self._event_bus.publish(ZaramEvent(
            source_runtime="agent",
            event_type="agent.status_result",
            correlation_id=event.correlation_id,
            priority="normal",
            data={
                "agent_id": agent_id,
                "state": state.__dict__ if state else None,
            },
        ))

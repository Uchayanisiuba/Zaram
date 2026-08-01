from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
import time
import uuid


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    agent_id: str
    name: str
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    max_concurrent_tasks: int = 5
    timeout_seconds: float = 30.0
    auto_start: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTask:
    """A task assigned to an agent."""

    task_id: str
    agent_id: str
    description: str
    input_data: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at is None:
            return None
        end = self.completed_at or time.time()
        return end - self.started_at


@dataclass
class AgentState:
    """Runtime state of an agent."""

    agent_id: str
    status: AgentStatus = AgentStatus.IDLE
    current_task: str | None = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    uptime_seconds: float = 0.0
    last_activity: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

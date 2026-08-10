# backend/core/contracts.py
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class TaskCancelledError(Exception):
    """Raised when a task is cancelled via its CancellationSignal."""


# --- Enums ---
class RuntimeState(Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    STOPPING = "stopping"
    READY = "ready"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    ERROR = "error"
    RELOADING = "reloading"


class CapabilityLocality(Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    HYBRID = "hybrid"
    REMOTE_DEVICE = "remote_device"


class RestartPolicy(Enum):
    ALWAYS = "always"
    ON_FAILURE = "on_failure"
    NEVER = "never"


class PlanState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    DEGRADED = "degraded"


class TaskPriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BACKGROUND = "background"


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


# --- First-Class Objects ---
@dataclass(frozen=True)
class Capability:
    id: str
    runtime_id: str
    version: str = "1.0.0"
    category: str = "general"
    locality: CapabilityLocality = CapabilityLocality.LOCAL


@dataclass
class RuntimeMetadata:
    runtime_id: str
    version: str
    priority: str = "normal"
    capabilities: list[Capability] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    auto_start: bool = True
    restart_policy: RestartPolicy = RestartPolicy.ON_FAILURE


@dataclass
class ExecutionStep:
    capability_id: str
    input_data: dict[str, Any]
    output_data: dict[str, Any] = field(default_factory=dict)
    depends_on: list[int] = field(default_factory=list)
    status: str = "pending"


@dataclass
class ExecutionPlan:
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_prompt: str = ""
    steps: list[ExecutionStep] = field(default_factory=list)
    state: PlanState = PlanState.PENDING
    priority: str = "normal"
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ExecutionToken:
    """A single token in the execution stream, carrying sequence and metadata."""
    token: str
    sequence: int
    final: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CancellationSignal:
    """Mutable signal that allows cooperative cancellation of tasks."""
    cancelled: bool = False
    reason: str = ""

    def cancel(self, reason: str = "") -> None:
        self.cancelled = True
        self.reason = reason

    def check(self) -> None:
        if self.cancelled:
            raise TaskCancelledError(self.reason or "Task was cancelled")


@dataclass
class TaskDescriptor:
    """Describes a unit of work scheduled by the kernel."""
    task_id: str
    capability_id: str
    input_data: dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None
    correlation_id: str = ""
    depends_on: list[str] = field(default_factory=list)
    cancellation: CancellationSignal = field(default_factory=CancellationSignal)

    @property
    def elapsed(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at or time.time()
        return end - self.started_at


@dataclass
class RuntimeDescriptor:
    """Describes a runtime discovered by the discovery mechanism."""
    runtime_id: str
    module_path: str
    class_name: str
    dependencies: list[str] = field(default_factory=list)
    auto_start: bool = True
    priority: str = "normal"


# --- The Universal Runtime Protocol ---
class Runtime(Protocol):
    def get_runtime_id(self) -> str: ...
    def get_metadata(self) -> RuntimeMetadata: ...
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...
    def get_state(self) -> RuntimeState: ...
    def health_check(self) -> dict[str, Any]: ...

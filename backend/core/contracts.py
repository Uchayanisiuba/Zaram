# backend/core/contracts.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, Any, Dict, List
import time
import uuid

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
    capabilities: List[Capability] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    auto_start: bool = True
    restart_policy: RestartPolicy = RestartPolicy.ON_FAILURE

@dataclass
class ExecutionStep:
    capability_id: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[int] = field(default_factory=list)
    status: str = "pending"

@dataclass
class ExecutionPlan:
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_prompt: str = ""
    steps: List[ExecutionStep] = field(default_factory=list)
    state: PlanState = PlanState.PENDING
    priority: str = "normal"
    created_at: float = field(default_factory=time.time)

# --- The Universal Runtime Protocol ---
class Runtime(Protocol):
    def get_runtime_id(self) -> str: ...
    def get_metadata(self) -> RuntimeMetadata: ...
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...
    def get_state(self) -> RuntimeState: ...
    def health_check(self) -> Dict[str, Any]: ...
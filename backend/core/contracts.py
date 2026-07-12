# backend/core/contracts.py
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


# --- Enums ---
class RuntimeState(Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
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
    priority: str = "normal"  # critical, high, normal, optional
    capabilities: list[Capability] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    auto_start: bool = True
    restart_policy: RestartPolicy = RestartPolicy.ON_FAILURE

@dataclass
class ExecutionPlan:
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    steps: list[dict[str, Any]] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)
    priority: str = "normal"
    timeout: float = 30.0

# --- The Universal Runtime Protocol ---
class Runtime(Protocol):
    def get_runtime_id(self) -> str: ...
    def get_metadata(self) -> RuntimeMetadata: ...

    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...

    def get_state(self) -> RuntimeState: ...
    def health_check(self) -> dict[str, Any]: ...

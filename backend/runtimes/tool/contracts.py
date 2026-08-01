from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class ToolType(str, Enum):
    GIT = "git"
    VSCODE = "vscode"
    TERMINAL = "terminal"
    BROWSER = "browser"
    FILESYSTEM = "filesystem"
    EMAIL = "email"
    CALENDAR = "calendar"
    CUSTOM = "custom"


class ToolStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    INITIALIZING = "initializing"
    DISABLED = "disabled"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass(frozen=True)
class ToolInvocation:
    tool_id: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    tool_id: str
    action: str
    success: bool
    result: Any = None
    error: str | None = None
    latency_ms: float = 0.0


@dataclass(frozen=True)
class ToolHealth:
    tool_id: str
    tool_type: ToolType
    status: ToolStatus
    latency_ms: float = 0.0
    last_invocation: float = 0.0
    invocation_count: int = 0
    failure_count: int = 0
    last_error: str | None = None


class ToolConnector(Protocol):
    def get_tool_id(self) -> str: ...
    def get_tool_type(self) -> ToolType: ...
    async def invoke(self, action: str, params: dict[str, Any]) -> ToolResult: ...
    def health_check(self) -> ToolHealth: ...
    def is_available(self) -> bool: ...


class ToolRuntime(Protocol):
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...
    def get_runtime_id(self) -> str: ...
    def get_metadata(self) -> dict[str, Any]: ...
    def get_state(self) -> ToolStatus: ...
    def health_check(self) -> dict[str, Any]: ...
    async def invoke(self, tool_id: str, action: str, params: dict[str, Any]) -> ToolResult: ...
    async def invoke_batch(self, invocations: list[ToolInvocation]) -> list[ToolResult]: ...
    def register_tool(self, tool: ToolConnector) -> None: ...
    def unregister_tool(self, tool_id: str) -> None: ...
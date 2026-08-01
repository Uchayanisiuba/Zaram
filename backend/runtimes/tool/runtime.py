from __future__ import annotations

import asyncio
import time
from typing import Any

from .contracts import (
    ToolRuntime,
    ToolStatus,
    ToolConnector,
    ToolInvocation,
    ToolResult,
    ToolType,
)
from .connectors.base import (
    GitConnector,
    VSCodeConnector,
    TerminalConnector,
    BrowserConnector,
    EmailConnector,
    CalendarConnector,
    FilesystemToolConnector,
)


class ToolRuntimeImpl(ToolRuntime):
    """Main Tool Runtime - orchestrates all tool connectors."""

    def __init__(self, filesystem_runtime=None):
        self._runtime_id = "tool"
        self._state = ToolStatus.INITIALIZING
        self._start_time = time.time()
        self._initialized = False

        self._connectors: dict[str, ToolConnector] = {}
        self._filesystem_runtime = filesystem_runtime

        self._stats = {
            "total_invocations": 0,
            "successful_invocations": 0,
            "failed_invocations": 0,
            "total_latency_ms": 0.0,
        }

    async def initialize(self) -> None:
        self._state = ToolStatus.INITIALIZING

        # Register default connectors
        self.register_tool(GitConnector())
        self.register_tool(VSCodeConnector())
        self.register_tool(TerminalConnector())
        self.register_tool(BrowserConnector())
        self.register_tool(EmailConnector())
        self.register_tool(CalendarConnector())

        if self._filesystem_runtime:
            self.register_tool(FilesystemToolConnector(self._filesystem_runtime))

        self._state = ToolStatus.READY
        self._initialized = True
        print(f"[ToolRuntime] Initialized with {len(self._connectors)} tools")

    async def shutdown(self) -> None:
        self._state = ToolStatus.STOPPING
        self._state = ToolStatus.STOPPED

    def get_runtime_id(self) -> str:
        return self._runtime_id

    def get_metadata(self) -> dict[str, Any]:
        return {
            "runtime_id": self._runtime_id,
            "version": "1.0.0",
            "priority": "high",
            "tools": [t.get_tool_type().value for t in self._connectors.values()],
        }

    def get_state(self) -> ToolStatus:
        return self._state

    def health_check(self) -> dict[str, Any]:
        tool_health = {}
        for tid, tool in self._connectors.items():
            tool_health[tid] = tool.health_check().__dict__

        return {
            "runtime_id": self._runtime_id,
            "state": self._state.value,
            "uptime_seconds": time.time() - self._start_time,
            "tools": tool_health,
            "stats": self._stats,
        }

    def register_tool(self, tool: ToolConnector) -> None:
        if tool.get_tool_id() in self._connectors:
            raise ValueError(f"Tool {tool.get_tool_id()} already registered")
        self._connectors[tool.get_tool_id()] = tool
        print(f"[ToolRuntime] Registered tool: {tool.get_tool_id()} ({tool.get_tool_type().value})")

    def unregister_tool(self, tool_id: str) -> None:
        self._connectors.pop(tool_id, None)

    async def invoke(self, tool_id: str, action: str, params: dict[str, Any]) -> ToolResult:
        start = time.time()
        self._stats["total_invocations"] += 1

        tool = self._connectors.get(tool_id)
        if not tool:
            self._stats["failed_invocations"] += 1
            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                error=f"Tool {tool_id} not found",
                latency_ms=(time.time() - start) * 1000,
            )

        if not tool.is_available():
            self._stats["failed_invocations"] += 1
            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                error=f"Tool {tool_id} unavailable",
                latency_ms=(time.time() - start) * 1000,
            )

        try:
            result = await tool.invoke(action, params)
            if result.success:
                self._stats["successful_invocations"] += 1
            else:
                self._stats["failed_invocations"] += 1
            return result
        except Exception as e:
            self._stats["failed_invocations"] += 1
            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                error=str(e),
                latency_ms=(time.time() - start) * 1000,
            )

    async def invoke_batch(self, invocations: list[ToolInvocation]) -> list[ToolResult]:
        tasks = [
            self.invoke(inv.tool_id, inv.action, inv.params)
            for inv in invocations
        ]
        return await asyncio.gather(*tasks)


def create_tool_runtime(**kwargs) -> ToolRuntimeImpl:
    return ToolRuntimeImpl(**kwargs)
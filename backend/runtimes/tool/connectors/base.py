from __future__ import annotations

import asyncio
import subprocess
import time
from dataclasses import dataclass
from typing import Any
from pathlib import Path

from .contracts import (
    ToolConnector,
    ToolResult,
    ToolHealth,
    ToolType,
    ToolStatus,
)


class BaseToolConnector(ToolConnector):
    def __init__(self, tool_id: str, tool_type: ToolType):
        self._tool_id = tool_id
        self._tool_type = tool_type
        self._available = True
        self._last_error: str | None = None
        self._stats = {
            "invocations": 0,
            "successes": 0,
            "failures": 0,
            "total_latency_ms": 0.0,
            "last_invocation": 0.0,
        }

    def get_tool_id(self) -> str:
        return self._tool_id

    def get_tool_type(self) -> ToolType:
        return self._tool_type

    def is_available(self) -> bool:
        return self._available

    def health_check(self) -> ToolHealth:
        stats = self._stats
        return ToolHealth(
            tool_id=self._tool_id,
            tool_type=self._tool_type,
            status=ToolStatus.HEALTHY if self._available else ToolStatus.UNAVAILABLE,
            latency_ms=stats["total_latency_ms"] / max(stats["invocations"], 1),
            last_invocation=stats["last_invocation"],
            invocation_count=stats["invocations"],
            failure_count=stats["failures"],
            last_error=self._last_error,
        )

    async def invoke(self, action: str, params: dict[str, Any]) -> ToolResult:
        start = time.time()
        self._stats["invocations"] += 1
        self._stats["last_invocation"] = start

        try:
            result = await self._invoke(action, params)
            self._stats["successes"] += 1
            self._stats["total_latency_ms"] += (time.time() - start) * 1000
            self._last_error = None
            self._available = True
            return ToolResult(
                tool_id=self._tool_id,
                action=action,
                success=True,
                result=result,
                latency_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            self._stats["failures"] += 1
            self._stats["total_latency_ms"] += (time.time() - start) * 1000
            self._last_error = str(e)
            if self._stats["failures"] > 5:
                self._available = False
            return ToolResult(
                tool_id=self._tool_id,
                action=action,
                success=False,
                error=str(e),
                latency_ms=(time.time() - start) * 1000,
            )

    async def _invoke(self, action: str, params: dict[str, Any]) -> Any:
        raise NotImplementedError


class GitConnector(BaseToolConnector):
    def __init__(self, repo_path: str = "."):
        super().__init__("git", ToolType.GIT)
        self._repo_path = Path(repo_path).resolve()

    async def _invoke(self, action: str, params: dict[str, Any]) -> Any:
        cmd_map = {
            "status": ["git", "status"],
            "log": ["git", "log", "--oneline", f"-{params.get('limit', 10)}"],
            "diff": ["git", "diff", params.get("file", "")],
            "add": ["git", "add", params.get("file", ".")],
            "commit": ["git", "commit", "-m", params.get("message", "Auto commit")],
            "push": ["git", "push"],
            "pull": ["git", "pull"],
            "branch": ["git", "branch"],
            "checkout": ["git", "checkout", params.get("branch", "")],
        }

        if action not in cmd_map:
            raise ValueError(f"Unknown git action: {action}")

        cmd = cmd_map[action]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self._repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise Exception(f"Git {action} failed: {stderr.decode()}")

        return {
            "output": stdout.decode().strip(),
            "action": action,
            "returncode": process.returncode,
        }


class VSCodeConnector(BaseToolConnector):
    def __init__(self):
        super().__init__("vscode", ToolType.VSCODE)

    async def _invoke(self, action: str, params: dict[str, Any]) -> Any:
        actions = {
            "open_file": self._open_file,
            "open_folder": self._open_folder,
            "run_command": self._run_command,
            "get_workspace": self._get_workspace,
        }

        if action not in actions:
            raise ValueError(f"Unknown VSCode action: {action}")

        return await actions[action](params)

    async def _open_file(self, params: dict[str, Any]) -> dict[str, Any]:
        file_path = params.get("path", "")
        process = await asyncio.create_subprocess_exec(
            "code", "--goto", file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        return {"opened": file_path}

    async def _open_folder(self, params: dict[str, Any]) -> dict[str, Any]:
        folder = params.get("folder", ".")
        process = await asyncio.create_subprocess_exec(
            "code", folder,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        return {"opened_folder": folder}

    async def _run_command(self, params: dict[str, Any]) -> dict[str, Any]:
        command = params.get("command", "")
        # VSCode CLI doesn't directly support running commands
        return {"command": command, "note": "Use VSCode API for command execution"}

    async def _get_workspace(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"workspace": "current"}


class TerminalConnector(BaseToolConnector):
    def __init__(self, working_dir: str = "."):
        super().__init__("terminal", ToolType.TERMINAL)
        self._working_dir = Path(working_dir).resolve()

    async def _invoke(self, action: str, params: dict[str, Any]) -> Any:
        if action == "exec":
            command = params.get("command", "")
            shell = params.get("shell", True)
            timeout = params.get("timeout", 30)

            if shell:
                process = await asyncio.create_subprocess_shell(
                    command,
                    cwd=self._working_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                parts = command.split()
                process = await asyncio.create_subprocess_exec(
                    *parts,
                    cwd=self._working_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                process.kill()
                raise Exception(f"Command timed out after {timeout}s")

            return {
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "returncode": process.returncode,
                "command": command,
            }

        elif action == "cd":
            new_dir = params.get("path", ".")
            new_path = (self._working_dir / new_dir).resolve()
            if new_path.exists() and new_path.is_dir():
                self._working_dir = new_path
                return {"cwd": str(self._working_dir)}
            else:
                raise Exception(f"Directory not found: {new_path}")

        elif action == "pwd":
            return {"cwd": str(self._working_dir)}

        raise ValueError(f"Unknown terminal action: {action}")


class BrowserConnector(BaseToolConnector):
    def __init__(self):
        super().__init__("browser", ToolType.BROWSER)
        self._page = None

    async def _invoke(self, action: str, params: dict[str, Any]) -> Any:
        if action == "navigate":
            url = params.get("url", "")
            # Would use playwright/selenium here
            return {"url": url, "note": "Requires playwright/selenium integration"}

        elif action == "screenshot":
            path = params.get("path", "screenshot.png")
            return {"path": path, "note": "Requires playwright/selenium integration"}

        elif action == "click":
            selector = params.get("selector", "")
            return {"selector": selector, "note": "Requires playwright/selenium integration"}

        elif action == "type_text":
            selector = params.get("selector", "")
            text = params.get("text", "")
            return {"selector": selector, "text": text, "note": "Requires playwright/selenium integration"}

        elif action == "get_text":
            selector = params.get("selector", "")
            return {"selector": selector, "note": "Requires playwright/selenium integration"}

        raise ValueError(f"Unknown browser action: {action}")


class EmailConnector(BaseToolConnector):
    def __init__(self):
        super().__init__("email", ToolType.EMAIL)

    async def _invoke(self, action: str, params: dict[str, Any]) -> Any:
        if action == "send":
            to = params.get("to", "")
            subject = params.get("subject", "")
            body = params.get("body", "")
            return {"sent": True, "to": to, "subject": subject, "note": "Requires SMTP configuration"}

        elif action == "list":
            return {"emails": [], "note": "Requires IMAP configuration"}

        raise ValueError(f"Unknown email action: {action}")


class CalendarConnector(BaseToolConnector):
    def __init__(self):
        super().__init__("calendar", ToolType.CALENDAR)

    async def _invoke(self, action: str, params: dict[str, Any]) -> Any:
        if action == "create_event":
            title = params.get("title", "")
            start = params.get("start", "")
            end = params.get("end", "")
            return {"created": True, "title": title, "start": start, "end": end}

        elif action == "list_events":
            return {"events": [], "note": "Requires calendar API integration"}

        raise ValueError(f"Unknown calendar action: {action}")


class FilesystemToolConnector(BaseToolConnector):
    def __init__(self, filesystem_runtime):
        super().__init__("filesystem", ToolType.FILESYSTEM)
        self._fs = filesystem_runtime

    async def _invoke(self, action: str, params: dict[str, Any]) -> Any:
        if action == "search":
            return await self._fs.search(params.get("query", ""), max_results=params.get("max_results", 20))

        elif action == "read":
            return await self._fs.open_file(params.get("file_id", ""))

        elif action == "metadata":
            return await self._fs.get_metadata(params.get("file_id", ""))

        raise ValueError(f"Unknown filesystem action: {action}")
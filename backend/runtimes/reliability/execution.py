from __future__ import annotations

import traceback
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable
from functools import wraps


class ExecutionPhase(str, Enum):
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ExecutionStepReport:
    step_id: str
    capability: str
    runtime: str
    connector: str | None
    phase: ExecutionPhase
    timestamp: float
    latency_ms: float = 0.0
    error: str | None = None
    stack_trace: str | None = None
    user_message: str | None = None


@dataclass
class ExecutionContext:
    correlation_id: str
    step_reports: list[ExecutionStepReport] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    failed: bool = False

    def add_report(self, report: ExecutionStepReport) -> None:
        self.step_reports.append(report)

    def get_summary(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "duration_ms": (time.time() - self.started_at) * 1000,
            "steps": len(self.step_reports),
            "failed": self.failed,
            "failures": [r for r in self.step_reports if r.phase == ExecutionPhase.FAILED],
        }


class ExecutionReliability:
    """Wrapper for reliable execution with structured error handling."""

    def __init__(self, correlation_id: str | None = None, debug: bool = False):
        self.context = ExecutionContext(correlation_id or f"exec_{int(time.time() * 1000)}")
        self._debug = debug

    def report_started(self, capability: str, runtime: str, connector: str | None = None) -> ExecutionStepReport:
        report = ExecutionStepReport(
            step_id=f"{capability}_{int(time.time() * 1000)}",
            capability=capability,
            runtime=runtime,
            connector=connector,
            phase=ExecutionPhase.STARTED,
            timestamp=time.time(),
        )
        self.context.add_report(report)
        print(f"[Execution] STARTED: {capability} (runtime={runtime}, connector={connector})")
        return report

    def report_running(self, report: ExecutionStepReport) -> None:
        updated = ExecutionStepReport(
            **{**report.__dict__, "phase": ExecutionPhase.RUNNING}
        )
        # Replace in context
        self.context.step_reports = [updated if r.step_id == report.step_id else r for r in self.context.step_reports]
        print(f"[Execution] RUNNING: {report.capability}")

    def report_completed(self, report: ExecutionStepReport, result: Any = None) -> None:
        latency = (time.time() - report.timestamp) * 1000
        updated = ExecutionStepReport(
            **{**report.__dict__, "phase": ExecutionPhase.COMPLETED, "latency_ms": latency}
        )
        self.context.step_reports = [updated if r.step_id == report.step_id else r for r in self.context.step_reports]
        print(f"[Execution] COMPLETED: {report.capability} ({latency:.1f}ms)")

    def report_failed(
        self,
        report: ExecutionStepReport,
        error: Exception | str,
        user_message: str | None = None,
    ) -> None:
        latency = (time.time() - report.timestamp) * 1000
        stack = traceback.format_exc() if isinstance(error, Exception) and self._debug else None
        err_msg = str(error)

        updated = ExecutionStepReport(
            **{
                **report.__dict__,
                "phase": ExecutionPhase.FAILED,
                "latency_ms": latency,
                "error": err_msg,
                "stack_trace": stack,
                "user_message": user_message or self._generate_user_message(report, err_msg),
            }
        )
        self.context.step_reports = [updated if r.step_id == report.step_id else r for r in self.context.step_reports]
        self.context.failed = True
        print(f"[Execution] FAILED: {report.capability} - {err_msg}")

    def report_cancelled(self, report: ExecutionStepReport) -> None:
        latency = (time.time() - report.timestamp) * 1000
        updated = ExecutionStepReport(
            **{**report.__dict__, "phase": ExecutionPhase.CANCELLED, "latency_ms": latency}
        )
        self.context.step_reports = [updated if r.step_id == report.step_id else r for r in self.context.step_reports]
        print(f"[Execution] CANCELLED: {report.capability}")

    def _generate_user_message(self, report: ExecutionStepReport, error: str) -> str:
        """Generate user-friendly error messages."""
        runtime = report.runtime
        capability = report.capability
        connector = report.connector

        # Internet runtime fallback messages
        if runtime == "internet":
            if "timeout" in error.lower():
                return "Internet search timed out. Using cached results if available."
            if "unavailable" in error.lower() or "connection" in error.lower():
                return "Internet search unavailable. Falling back to local knowledge."
            if "rate limit" in error.lower():
                return "Search rate limited. Trying alternative sources."

        # Memory runtime fallback messages
        if runtime == "memory":
            return "Memory unavailable. Continuing without historical context."

        # Filesystem runtime fallback messages
        if runtime == "filesystem":
            return "File system unavailable. Cannot access local files."

        # Tool runtime fallback messages
        if runtime == "tool":
            return f"Tool '{capability}' unavailable. Operation cannot be completed."

        # Generic fallback
        return f"{capability} failed: {error}. Please try again or rephrase your request."

    def get_summary(self) -> dict[str, Any]:
        return self.context.get_summary()


def reliable_execution(
    capability: str,
    runtime: str,
    connector: str | None = None,
    debug: bool = False,
):
    """Decorator for reliable execution with automatic phase reporting."""

    def decorator(func: Callable[..., Awaitable[Any]]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            reliability = ExecutionReliability(debug=debug)
            report = reliability.report_started(capability, runtime, connector)

            try:
                reliability.report_running(report)
                result = await func(*args, **kwargs)
                reliability.report_completed(report, result)
                return result
            except Exception as e:
                reliability.report_failed(report, e)
                # Re-raise with context
                raise

        return wrapper
    return decorator


def format_user_error(step_report: ExecutionStepReport) -> str:
    """Format a user-friendly error from a step report."""
    if step_report.user_message:
        return step_report.user_message

    if step_report.phase == ExecutionPhase.FAILED:
        return f"Operation failed: {step_report.error}"
    elif step_report.phase == ExecutionPhase.CANCELLED:
        return "Operation was cancelled"
    return "Unknown error occurred"


def format_debug_error(step_report: ExecutionStepReport) -> str:
    """Format detailed error for debug mode."""
    parts = [
        f"Runtime: {step_report.runtime}",
        f"Capability: {step_report.capability}",
        f"Connector: {step_report.connector or 'N/A'}",
        f"Error: {step_report.error}",
    ]
    if step_report.stack_trace:
        parts.append(f"Stack:\n{step_report.stack_trace}")
    return "\n".join(parts)
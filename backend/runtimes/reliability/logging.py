from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from functools import wraps


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


@dataclass
class RuntimeLogEntry:
    runtime: str
    level: LogLevel
    message: str
    timestamp: float = field(default_factory=time.time)
    latency_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    connector: str | None = None
    operation: str | None = None


class StructuredLogger:
    """Structured logger for runtimes with consistent formatting."""

    def __init__(self, runtime_name: str, level: LogLevel = LogLevel.INFO):
        self.runtime_name = runtime_name
        self.level = level
        self._logger = logging.getLogger(f"runtime.{runtime_name}")
        self._logger.setLevel(getattr(logging, level.value))

    def _log(self, level: LogLevel, message: str, **kwargs):
        entry = RuntimeLogEntry(
            runtime=self.runtime_name,
            level=level,
            message=message,
            **kwargs,
        )
        # Print structured log
        log_dict = {
            "timestamp": entry.timestamp,
            "runtime": entry.runtime,
            "level": entry.level.value,
            "message": entry.message,
        }
        if entry.latency_ms is not None:
            log_dict["latency_ms"] = entry.latency_ms
        if entry.connector:
            log_dict["connector"] = entry.connector
        if entry.operation:
            log_dict["operation"] = entry.operation
        if entry.metadata:
            log_dict["metadata"] = entry.metadata

        print(json.dumps(log_dict, default=str))

    def info(self, message: str, **kwargs):
        self._log(LogLevel.INFO, message, **kwargs)

    def debug(self, message: str, **kwargs):
        if self.level in (LogLevel.DEBUG,):
            self._log(LogLevel.DEBUG, message, **kwargs)

    def warn(self, message: str, **kwargs):
        self._log(LogLevel.WARN, message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log(LogLevel.ERROR, message, **kwargs)

    def log_operation_start(self, operation: str, connector: str | None = None, **metadata):
        self.info(f"[Runtime] {operation} started", operation=operation, connector=connector, metadata=metadata)

    def log_operation_complete(self, operation: str, latency_ms: float, connector: str | None = None, **metadata):
        self.info(
            f"[Runtime] {operation} completed",
            operation=operation,
            latency_ms=latency_ms,
            connector=connector,
            metadata=metadata,
        )

    def log_operation_failed(self, operation: str, error: str, latency_ms: float, connector: str | None = None, **metadata):
        self.error(
            f"[Runtime] {operation} failed: {error}",
            operation=operation,
            latency_ms=latency_ms,
            connector=connector,
            metadata={"error": error, **metadata},
        )


class RuntimeLogger:
    """Centralized logger factory for all runtimes."""

    _loggers: dict[str, StructuredLogger] = {}

    @classmethod
    def get_logger(cls, runtime_name: str, level: LogLevel = LogLevel.INFO) -> StructuredLogger:
        if runtime_name not in cls._loggers:
            cls._loggers[runtime_name] = StructuredLogger(runtime_name, level)
        return cls._loggers[runtime_name]

    @classmethod
    def set_level(cls, runtime_name: str, level: LogLevel):
        if runtime_name in cls._loggers:
            cls._loggers[runtime_name].level = level


def log_runtime_operation(runtime: str, operation: str, connector: str | None = None):
    """Decorator to automatically log runtime operations."""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = RuntimeLogger.get_logger(runtime)
            start = time.time()
            logger.log_operation_start(operation, connector)
            try:
                result = await func(*args, **kwargs)
                latency = (time.time() - start) * 1000
                logger.log_operation_complete(operation, latency, connector)
                return result
            except Exception as e:
                latency = (time.time() - start) * 1000
                logger.log_operation_failed(operation, str(e), latency, connector)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = RuntimeLogger.get_logger(runtime)
            start = time.time()
            logger.log_operation_start(operation, connector)
            try:
                result = func(*args, **kwargs)
                latency = (time.time() - start) * 1000
                logger.log_operation_complete(operation, latency, connector)
                return result
            except Exception as e:
                latency = (time.time() - start) * 1000
                logger.log_operation_failed(operation, str(e), latency, connector)
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Convenience functions for common log patterns
def log_knowledge_search(query: str, providers: list[str], results: int, latency_ms: float):
    RuntimeLogger.get_logger("knowledge").info(
        "[Runtime][Knowledge] Search completed",
        operation="search",
        latency_ms=latency_ms,
        metadata={"query": query[:50], "providers": providers, "results": results},
    )


def log_memory_retrieve(query: str, memories: int, latency_ms: float):
    RuntimeLogger.get_logger("memory").info(
        "[Runtime][Memory] Retrieved memories",
        operation="retrieve",
        latency_ms=latency_ms,
        metadata={"query": query[:50], "count": memories},
    )


def log_filesystem_search(query: str, results: int, latency_ms: float):
    RuntimeLogger.get_logger("filesystem").info(
        "[Runtime][Filesystem] Search completed",
        operation="search",
        latency_ms=latency_ms,
        metadata={"query": query[:50], "results": results},
    )


def log_internet_search(query: str, connectors: list[str], results: int, latency_ms: float):
    RuntimeLogger.get_logger("internet").info(
        "[Runtime][Internet] Search completed",
        operation="search",
        latency_ms=latency_ms,
        metadata={"query": query[:50], "connectors": connectors, "results": results},
    )


def log_tool_invoke(tool: str, action: str, success: bool, latency_ms: float):
    RuntimeLogger.get_logger("tool").info(
        f"[Runtime][Tool] {action} {'succeeded' if success else 'failed'}",
        operation=action,
        latency_ms=latency_ms,
        connector=tool,
        metadata={"success": success},
    )
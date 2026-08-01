from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuntimeStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    INITIALIZING = "initializing"
    DISABLED = "disabled"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass(frozen=True)
class ConnectorHealth:
    connector_id: str
    connector_type: str
    status: RuntimeStatus
    latency_ms: float = 0.0
    last_request: float = 0.0
    success_count: int = 0
    error_count: int = 0
    last_error: str | None = None
    cache_hit_rate: float = 0.0


@dataclass(frozen=True)
class SpeechRuntimeHealth:
    """Speech-specific health metrics."""
    connector: str
    voice: str
    streaming: bool
    latency_ms: float
    queue_size: int
    cache: dict[str, Any]
    model: dict[str, Any]
    health_state: RuntimeStatus


@dataclass(frozen=True)
class RuntimeHealth:
    runtime_id: str
    status: RuntimeStatus
    uptime_seconds: float
    connectors: list[ConnectorHealth]
    cache_stats: dict[str, Any] = field(default_factory=dict)
    queue_size: int = 0
    last_error: str | None = None
    last_success: float = 0.0
    stats: dict[str, Any] = field(default_factory=dict)


class HealthDashboard:
    """Central health dashboard for all runtimes."""

    def __init__(self):
        self._runtimes: dict[str, Any] = {}
        self._start_time = time.time()
        self._last_update = 0.0

    def register_runtime(self, runtime) -> None:
        self._runtimes[runtime.get_runtime_id()] = runtime

    def unregister_runtime(self, runtime_id: str) -> None:
        self._runtimes.pop(runtime_id, None)

    def get_runtime_health(self, runtime_id: str) -> RuntimeHealth | None:
        runtime = self._runtimes.get(runtime_id)
        if not runtime:
            return None
        return self._build_runtime_health(runtime)

    def get_system_health(self) -> dict[str, Any]:
        self._last_update = time.time()
        runtime_health = {}
        overall_status = RuntimeStatus.HEALTHY

        for rid, runtime in self._runtimes.items():
            health = self._build_runtime_health(runtime)
            runtime_health[rid] = health.__dict__

            # Determine overall status (worst of all)
            if health.status == RuntimeStatus.ERROR:
                overall_status = RuntimeStatus.ERROR
            elif health.status == RuntimeStatus.UNAVAILABLE:
                overall_status = RuntimeStatus.UNAVAILABLE
            elif health.status == RuntimeStatus.DEGRADED and overall_status == RuntimeStatus.HEALTHY:
                overall_status = RuntimeStatus.DEGRADED

        return {
            "status": overall_status.value,
            "timestamp": self._last_update,
            "uptime_seconds": time.time() - self._start_time,
            "runtimes": runtime_health,
        }

    def _build_runtime_health(self, runtime) -> RuntimeHealth:
        runtime_id = runtime.get_runtime_id()
        state = runtime.get_state() if hasattr(runtime, 'get_state') else RuntimeStatus.HEALTHY

        # Get connectors if available
        connectors = []
        if hasattr(runtime, 'health_check'):
            health = runtime.health_check()
            for cid, cinfo in health.get('connectors', {}).items():
                connectors.append(ConnectorHealth(
                    connector_id=cid,
                    connector_type=cinfo.get('connector_type', 'unknown'),
                    status=RuntimeStatus(cinfo.get('status', 'healthy')),
                    latency_ms=cinfo.get('latency_ms', 0),
                    last_request=cinfo.get('last_request', 0),
                    success_count=cinfo.get('success_count', 0),
                    error_count=cinfo.get('error_count', 0),
                    last_error=cinfo.get('last_error'),
                    cache_hit_rate=cinfo.get('cache_hit_rate', 0),
                ))

        # Get cache stats
        cache_stats = {}
        if hasattr(runtime, '_cache') and hasattr(runtime._cache, 'stats'):
            cache_stats = runtime._cache.stats()

        # Get stats
        stats = {}
        if hasattr(runtime, 'get_stats'):
            stats = runtime.get_stats()
        elif hasattr(runtime, '_stats'):
            stats = runtime._stats

        return RuntimeHealth(
            runtime_id=runtime_id,
            status=state if isinstance(state, RuntimeStatus) else RuntimeStatus(state),
            uptime_seconds=time.time() - getattr(runtime, '_start_time', time.time()),
            connectors=connectors,
            cache_stats=cache_stats,
            queue_size=0,
            last_error=None,
            last_success=time.time(),
            stats=stats,
        )

    def format_dashboard(self) -> str:
        """Format health dashboard as text."""
        system = self.get_system_health()
        lines = [
            "=" * 60,
            "ZARAM RUNTIME HEALTH DASHBOARD",
            "=" * 60,
            f"Overall Status: {system['status'].upper()}",
            f"Timestamp: {time.ctime(system['timestamp'])}",
            f"Uptime: {system['uptime_seconds']:.1f}s",
            f"Runtimes: {len(system['runtimes'])}",
            "",
        ]

        for rid, health in system['runtimes'].items():
            status = health['status']
            uptime = health['uptime_seconds']
            conn_count = len(health['connectors'])
            lines.append(f"  [{status:12}] {rid} (up {uptime:.0f}s, {conn_count} connectors)")

            for conn in health['connectors']:
                latency = conn['latency_ms']
                success = conn['success_count']
                errors = conn['error_count']
                lines.append(f"    - {conn['connector_id']}: {conn['status']} ({latency:.1f}ms, {success}/{success+errors})")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    def format_json(self) -> str:
        """Format health dashboard as JSON."""
        import json
        return json.dumps(self.get_system_health(), indent=2, default=str)


# Global dashboard instance
_dashboard = HealthDashboard()


def get_health_dashboard() -> HealthDashboard:
    return _dashboard


def register_runtime_for_health(runtime) -> None:
    _dashboard.register_runtime(runtime)


async def health_check_loop(interval: float = 30.0):
    """Background task to periodically check health."""
    while True:
        try:
            dashboard = get_health_dashboard()
            system = dashboard.get_system_health()
            # Log or emit event
            print(f"[HealthDashboard] System status: {system['status']}")
        except Exception as e:
            print(f"[HealthDashboard] Health check failed: {e}")
        await asyncio.sleep(interval)
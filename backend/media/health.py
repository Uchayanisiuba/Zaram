"""Health model and aggregation for the Media Runtime (v0.5.5).

Centralizes how the Media Runtime reports its status so the shape of a health
report is defined in exactly one place. ``MediaHealth`` is a plain, serializable
dataclass; the aggregation logic lives in :class:`MediaHealthAggregator`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .contracts import HealthStatus


@dataclass
class MediaHealth:
    """Snapshot of the Media Runtime's overall health."""

    runtime_id: str = "media"
    runtime_status: str = "unknown"
    health_status: HealthStatus = HealthStatus.UNKNOWN
    registered_services: int = 0
    available_services: int = 0
    provider_count: int = 0
    active_sessions: int = 0
    capabilities: List[Dict[str, Any]] = field(default_factory=list)
    media_types: List[str] = field(default_factory=list)
    providers: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)

    def is_healthy(self) -> bool:
        return self.health_status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "runtime_status": self.runtime_status,
            "health_status": self.health_status.value,
            "registered_services": self.registered_services,
            "available_services": self.available_services,
            "provider_count": self.provider_count,
            "active_sessions": self.active_sessions,
            "capabilities": list(self.capabilities),
            "media_types": list(self.media_types),
            "providers": dict(self.providers),
            "timestamp": self.timestamp,
            "details": dict(self.details),
        }


class MediaHealthAggregator:
    """Builds :class:`MediaHealth` from raw manager/registry reports.

    Keeps health-report construction out of the manager and runtime so the
    report shape can evolve independently.
    """

    def __init__(self, runtime_id: str = "media") -> None:
        self._runtime_id = runtime_id

    def aggregate(
        self,
        *,
        runtime_status: str,
        registry_report: Dict[str, Any],
        capabilities: List[Dict[str, Any]],
        media_types: List[str],
        active_sessions: int,
    ) -> MediaHealth:
        status = HealthStatus.from_value(registry_report.get("status", "unknown"))
        return MediaHealth(
            runtime_id=self._runtime_id,
            runtime_status=runtime_status,
            health_status=status,
            registered_services=registry_report.get("provider_count", 0),
            available_services=registry_report.get("available_count", 0),
            provider_count=registry_report.get("provider_count", 0),
            active_sessions=active_sessions,
            capabilities=capabilities,
            media_types=media_types,
            providers=registry_report.get("providers", {}),
        )

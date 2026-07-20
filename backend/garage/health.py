"""Health aggregation for the AI Garage (v0.6.0).

Centralizes the shape of the Garage health report so it is defined in exactly
one place. :class:`GarageHealthAggregator` turns raw manager/registry
snapshots into the structured report the API and runtime expose.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .contracts import HealthStatus


@dataclass
class GarageHealth:
    """Snapshot of the AI Garage's overall health."""

    runtime_id: str = "garage"
    runtime_status: str = "unknown"
    health_status: HealthStatus = HealthStatus.UNKNOWN
    registered_services: int = 0
    available_services: int = 0
    provider_count: int = 0
    model_count: int = 0
    available_models: int = 0
    voice_count: int = 0
    runtime_count: int = 0
    personality_count: int = 0
    categories: List[str] = field(default_factory=list)
    providers: List[Dict[str, Any]] = field(default_factory=list)
    hardware: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "runtime_status": self.runtime_status,
            "health_status": self.health_status.value,
            "registered_services": self.registered_services,
            "available_services": self.available_services,
            "provider_count": self.provider_count,
            "model_count": self.model_count,
            "available_models": self.available_models,
            "voice_count": self.voice_count,
            "runtime_count": self.runtime_count,
            "personality_count": self.personality_count,
            "categories": list(self.categories),
            "providers": [dict(p) for p in self.providers],
            "hardware": dict(self.hardware),
            "timestamp": self.timestamp,
        }


class GarageHealthAggregator:
    """Builds :class:`GarageHealth` from raw Garage snapshots."""

    def __init__(self, runtime_id: str = "garage") -> None:
        self._runtime_id = runtime_id

    def aggregate(
        self,
        *,
        runtime_status: str,
        provider_specs: List[Dict[str, Any]],
        scanner_health: Dict[str, Any],
        model_count: int,
        available_models: int,
        voice_count: int,
        runtime_count: int,
        personality_count: int,
        categories: List[str],
        hardware: Dict[str, Any],
    ) -> GarageHealth:
        available_services = sum(
            1 for spec in provider_specs if spec.get("available")
        )
        # Overall status: healthy if at least one model provider is reachable
        # OR no providers are configured yet (fresh install).
        if not provider_specs:
            status = HealthStatus.UNKNOWN
        elif available_services > 0:
            status = HealthStatus.HEALTHY
        else:
            status = HealthStatus.DEGRADED

        return GarageHealth(
            runtime_id=self._runtime_id,
            runtime_status=runtime_status,
            health_status=status,
            registered_services=len(provider_specs),
            available_services=available_services,
            provider_count=len(provider_specs),
            model_count=model_count,
            available_models=available_models,
            voice_count=voice_count,
            runtime_count=runtime_count,
            personality_count=personality_count,
            categories=list(categories),
            providers=provider_specs,
            hardware=hardware,
            timestamp=time.time(),
        )

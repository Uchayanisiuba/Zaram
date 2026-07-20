"""Health aggregation tests for the AI Garage (offline)."""

from __future__ import annotations

from garage.contracts import HealthStatus
from garage.health import GarageHealth, GarageHealthAggregator


def _aggregate(provider_specs):
    return GarageHealthAggregator().aggregate(
        runtime_status="ready",
        provider_specs=provider_specs,
        scanner_health={"providers": {}},
        model_count=4,
        available_models=3,
        voice_count=1,
        runtime_count=2,
        personality_count=1,
        categories=["llm", "vision"],
        hardware={"cpu_count": 8},
    )


def test_aggregate_unknown_when_no_providers():
    h = _aggregate([])
    assert h.health_status is HealthStatus.UNKNOWN
    assert h.to_dict()["health_status"] == "unknown"


def test_aggregate_healthy_when_one_available():
    h = _aggregate([{"id": "p1", "available": True, "health_status": "healthy"}])
    assert h.health_status is HealthStatus.HEALTHY
    assert h.available_services == 1


def test_aggregate_degraded_when_none_available():
    h = _aggregate([{"id": "p1", "available": False, "health_status": "unavailable"}])
    assert h.health_status is HealthStatus.DEGRADED


def test_garage_health_to_dict_shape():
    h = GarageHealth()
    d = h.to_dict()
    for key in (
        "runtime_id",
        "runtime_status",
        "health_status",
        "registered_services",
        "available_services",
        "model_count",
        "voice_count",
        "runtime_count",
        "personality_count",
        "categories",
        "providers",
        "hardware",
    ):
        assert key in d

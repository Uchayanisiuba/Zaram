"""Manager tests for the AI Garage (offline)."""

from __future__ import annotations

from garage.contracts import CapabilityLocality, ModelCategory


async def test_refresh_populates_all(manager):
    await manager.refresh(timeout=1.0)
    assert manager.catalog.count() == 4
    assert len(manager.list_voices()) == 1
    assert {r.runtime_id for r in manager.list_runtimes()} == {"media", "voice"}
    assert manager.list_personalities()[0]["id"] == "zaram_prime"
    assert manager.hardware_profile().cpu_count == 8


async def test_list_models_filtering(manager):
    await manager.refresh(timeout=1.0)
    assert len(manager.list_models(category=ModelCategory.VISION)) == 1
    assert len(manager.list_models(capability="tools")) == 1
    assert len(manager.list_models(locality=CapabilityLocality.CLOUD)) == 1
    # 4 total, 1 unavailable -> 3 available
    assert len(manager.list_models(available_only=True)) == 3


async def test_get_model(manager):
    await manager.refresh(timeout=1.0)
    assert manager.get_model("p1:llm-a") is not None
    assert manager.get_model("does-not-exist") is None


async def test_list_providers_enriched(manager):
    await manager.refresh(timeout=1.0)
    providers = manager.list_providers()
    by_id = {p["id"]: p for p in providers}
    assert by_id["p1"]["model_count"] == 2
    assert by_id["p1"]["available"] is True
    # p2 has embed-a (available) so the provider reports available
    assert by_id["p2"]["available"] is True


async def test_health_report(manager):
    await manager.refresh(timeout=1.0)
    report = manager.health_report()
    assert report["model_count"] == 4
    assert report["voice_count"] == 1
    assert report["runtime_count"] == 2
    assert report["personality_count"] == 1
    assert "llm" in report["categories"]
    assert "health_status" in report


async def test_refresh_publishes_event(manager):
    events = []

    class _Bus:
        def publish(self, e):
            events.append(e)

    mgr = type(manager)(
        manager.registry, manager.scanner, event_bus=_Bus()
    )
    await mgr.refresh(timeout=1.0)
    assert any(e.event_type == "garage.scanned" for e in events)

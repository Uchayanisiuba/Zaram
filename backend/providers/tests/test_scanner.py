"""Scanner tests for the provider layer (offline)."""

from __future__ import annotations

from providers.scanner import ProviderScanner
from providers.tests.conftest import FailingModelProvider


async def test_scan_models_aggregates_and_isolates_failures(manager):
    # Add a provider that raises during discovery; it must not break the scan.
    manager.registry.register_model_provider(FailingModelProvider())
    scanner = ProviderScanner(manager.registry)

    models = await scanner.scan_models(timeout=1.0)
    # 4 sample models from the fixture registry, failing provider contributes none.
    assert len(models) == 4


async def test_scan_voices_runtimes_personalities(manager):
    scanner = ProviderScanner(manager.registry)

    voices = await scanner.scan_voices()
    assert len(voices) == 1
    assert voices[0].id == "heart"

    runtimes = scanner.scan_runtimes()
    assert {r.runtime_id for r in runtimes} == {"media", "voice"}

    personalities = scanner.scan_personalities()
    assert personalities[0]["id"] == "zaram_prime"

    hw = scanner.profile_hardware()
    assert hw.cpu_count == 8


async def test_scan_hardware_falls_back_when_unconfigured():
    from providers.registry import ProviderRegistry

    scanner = ProviderScanner(ProviderRegistry())
    hw = scanner.profile_hardware()
    assert hw.cpu_count == 0  # default empty profile


async def test_scan_health_aggregates_per_provider(manager):
    scanner = ProviderScanner(manager.registry)
    health = await scanner.health()
    assert set(health["providers"]) == {"p1", "p2"}

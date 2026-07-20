"""Registry tests for the AI Garage (offline)."""

from __future__ import annotations

import pytest

from garage.contracts import ProviderKind
from garage.registry import GarageRegistry
from garage.tests.conftest import FakeModelProvider


def test_register_and_lookup():
    reg = GarageRegistry()
    p = FakeModelProvider("x", [])
    reg.register_model_provider(p)
    assert reg.is_registered("x")
    assert reg.get_model_provider("x") is p
    assert reg.count_model_providers() == 1


def test_duplicate_provider_rejected():
    reg = GarageRegistry()
    reg.register_model_provider(FakeModelProvider("x", []))
    with pytest.raises(ValueError):
        reg.register_model_provider(FakeModelProvider("x", []))


def test_provider_without_id_rejected():
    reg = GarageRegistry()

    class NoId:
        pass

    with pytest.raises(ValueError):
        reg.register_model_provider(NoId())


def test_remove_provider():
    reg = GarageRegistry()
    reg.register_model_provider(FakeModelProvider("x", []))
    assert reg.remove_model_provider("x") is True
    assert reg.remove_model_provider("x") is False


def test_injected_sources_get_set():
    reg = GarageRegistry()
    reg.set_voice_source("vs")
    assert reg.get_voice_source() == "vs"
    reg.set_runtime_source("rs")
    assert reg.get_runtime_source() == "rs"
    reg.set_personality_source("ps")
    assert reg.get_personality_source() == "ps"
    reg.set_hardware_profiler("hw")
    assert reg.get_hardware_profiler() == "hw"


def test_provider_specs():
    reg = GarageRegistry()
    reg.register_model_provider(
        FakeModelProvider("x", [], kind=ProviderKind.CLOUD_API)
    )
    specs = reg.provider_specs()
    assert specs[0].id == "x"
    assert specs[0].kind.value == "cloud_api"

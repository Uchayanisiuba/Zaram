"""Model catalog tests for the AI Garage (offline)."""

from __future__ import annotations

from garage.contracts import (
    CapabilityLocality,
    ModelCategory,
    ModelInfo,
    ProviderKind,
)
from garage.model_catalog import GarageModelCatalog
from garage.tests.conftest import make_model


def _model(id: str, **kw) -> ModelInfo:
    return make_model(id=id, **kw)


def test_upsert_and_get():
    cat = GarageModelCatalog()
    m = _model("p1:a")
    cat.upsert(m)
    assert cat.count() == 1
    assert cat.get("p1:a") is m
    assert cat.get("missing") is None


def test_filter_by_category():
    cat = GarageModelCatalog()
    cat.upsert_all([
        _model("p1:llm", category=ModelCategory.LLM),
        _model("p1:vision", category=ModelCategory.VISION),
        _model("p2:embed", category=ModelCategory.EMBEDDING),
    ])
    assert len(cat.filter(category=ModelCategory.VISION)) == 1
    assert len(cat.filter(category=ModelCategory.LLM)) == 1


def test_filter_by_capability_and_locality():
    cat = GarageModelCatalog()
    cat.upsert_all([
        _model("p1:tools", capabilities={"tools"}),
        _model("p1:vision", capabilities={"vision"}),
        _model("p2:cloud", locality=CapabilityLocality.CLOUD),
    ])
    assert len(cat.filter(capability="tools")) == 1
    assert len(cat.filter(capability="vision")) == 1
    assert len(cat.filter(locality=CapabilityLocality.CLOUD)) == 1


def test_filter_available_only_and_provider():
    cat = GarageModelCatalog()
    cat.upsert_all([
        _model("p1:a", available=True),
        _model("p1:b", available=False),
        _model("p2:c", available=True, provider="p2"),
    ])
    assert cat.available_count() == 2
    assert len(cat.filter(available_only=True)) == 2
    assert len(cat.filter(provider="p1")) == 2


def test_by_category_counts_and_remove_clear():
    cat = GarageModelCatalog()
    cat.upsert_all([
        _model("p1:a", category=ModelCategory.LLM),
        _model("p1:b", category=ModelCategory.LLM),
        _model("p2:c", category=ModelCategory.VISION),
    ])
    counts = cat.by_category()
    assert counts == {"llm": 2, "vision": 1}
    assert cat.remove("p1:a") is True
    assert cat.remove("p1:a") is False
    assert cat.count() == 2
    cat.clear()
    assert cat.count() == 0

"""Which model Zaram may use without being asked.

``select_default_model`` is where the data policy stops being metadata and
starts costing something: a model that would otherwise be the obvious default
is refused because nobody established what its provider does with prompts.
These tests exist to keep that refusal in place, since the pressure will always
be to return *something*.
"""

from __future__ import annotations

import pytest

from core.contracts import CapabilityLocality
from providers.contracts import DataPolicy, ModelCategory, ModelInfo
from providers.manager import ProviderManager


def _model(
    model_id: str,
    *,
    policy: DataPolicy | None,
    locality: CapabilityLocality = CapabilityLocality.LOCAL,
    size: int | None = None,
    available: bool = True,
    category: ModelCategory = ModelCategory.LLM,
) -> ModelInfo:
    return ModelInfo(
        id=model_id,
        display_name=model_id.split(":", 1)[-1],
        provider=model_id.split(":", 1)[0],
        category=category,
        size_bytes=size,
        locality=locality,
        available=available,
        data_policy=policy,
    )


@pytest.fixture
def manager() -> ProviderManager:
    return ProviderManager()


def _load(manager: ProviderManager, *models: ModelInfo) -> ProviderManager:
    manager.catalog.upsert_all(list(models))
    return manager


class TestRefusals:
    def test_no_models_means_no_default(self, manager):
        assert manager.select_default_model() is None

    def test_a_model_with_no_data_policy_is_not_chosen(self, manager):
        """The case this whole field exists for.

        Someone points the OpenAI-compatible adapter at a remote endpoint and
        does not pass a policy. It is available, it is an LLM, it is the only
        candidate — and it is still not eligible, because we cannot tell the
        user what happens to their prompt.
        """
        _load(manager, _model("mystery:big-model", policy=None, size=90_000_000_000))

        assert manager.select_default_model() is None

    def test_a_logged_and_trained_on_model_is_not_chosen(self, manager):
        """Free is not a good enough reason to choose it for someone."""
        _load(
            manager,
            _model(
                "freetier:generous-model",
                policy=DataPolicy.LOGGED_AND_TRAINED_ON,
                locality=CapabilityLocality.CLOUD,
                size=400_000_000_000,
            ),
        )

        assert manager.select_default_model() is None

    def test_refused_models_are_reportable(self, manager):
        """A user with no default deserves to know it was the policy, not a bug."""
        _load(
            manager,
            _model("mystery:unknown", policy=None),
            _model("freetier:logged", policy=DataPolicy.LOGGED_AND_TRAINED_ON),
        )

        rejected = manager.rejected_default_candidates()

        assert {m.id for m in rejected} == {"mystery:unknown", "freetier:logged"}
        assert manager.select_default_model() is None

    def test_an_unavailable_model_is_not_chosen(self, manager):
        _load(
            manager,
            _model(
                "ollama:gone",
                policy=DataPolicy.NEVER_LEAVES_DEVICE,
                available=False,
            ),
        )

        assert manager.select_default_model() is None


class TestSelection:
    def test_a_local_model_is_chosen(self, manager):
        _load(manager, _model("ollama:llama3", policy=DataPolicy.NEVER_LEAVES_DEVICE))

        chosen = manager.select_default_model()

        assert chosen is not None
        assert chosen.id == "ollama:llama3"

    def test_local_wins_over_cloud_even_when_the_cloud_model_is_bigger(self, manager):
        """Rule 1: never route to paid inference on our own initiative."""
        _load(
            manager,
            _model("ollama:small", policy=DataPolicy.NEVER_LEAVES_DEVICE, size=4_000_000_000),
            _model(
                "openai:huge",
                policy=DataPolicy.YOUR_KEY_NO_TRAINING,
                locality=CapabilityLocality.CLOUD,
                size=400_000_000_000,
            ),
        )

        assert manager.select_default_model().id == "ollama:small"

    def test_the_larger_local_model_wins(self, manager):
        _load(
            manager,
            _model("ollama:small", policy=DataPolicy.NEVER_LEAVES_DEVICE, size=2_000_000_000),
            _model("ollama:large", policy=DataPolicy.NEVER_LEAVES_DEVICE, size=9_000_000_000),
        )

        assert manager.select_default_model().id == "ollama:large"

    def test_an_eligible_model_is_chosen_past_ineligible_ones(self, manager):
        _load(
            manager,
            _model("mystery:unknown", policy=None, size=99_000_000_000),
            _model("freetier:logged", policy=DataPolicy.LOGGED_AND_TRAINED_ON, size=99_000_000_000),
            _model("ollama:modest", policy=DataPolicy.NEVER_LEAVES_DEVICE, size=3_000_000_000),
        )

        assert manager.select_default_model().id == "ollama:modest"

    def test_selection_is_deterministic_across_equal_candidates(self, manager):
        _load(
            manager,
            _model("ollama:b", policy=DataPolicy.NEVER_LEAVES_DEVICE, size=5_000_000_000),
            _model("ollama:a", policy=DataPolicy.NEVER_LEAVES_DEVICE, size=5_000_000_000),
        )

        assert manager.select_default_model().id == "ollama:a"

    def test_category_is_respected(self, manager):
        """An embedding model is not a chat default."""
        _load(
            manager,
            _model(
                "ollama:bge-m3",
                policy=DataPolicy.NEVER_LEAVES_DEVICE,
                category=ModelCategory.EMBEDDING,
            ),
        )

        assert manager.select_default_model() is None
        assert (
            manager.select_default_model(category=ModelCategory.EMBEDDING).id
            == "ollama:bge-m3"
        )

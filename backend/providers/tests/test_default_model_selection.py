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
from providers.contracts import (
    DataPolicy,
    HardwareProfile,
    ModelCategory,
    ModelInfo,
    specialisation_from_name,
)
from providers.manager import ProviderManager

GB = 1024**3


def _model(
    model_id: str,
    *,
    policy: DataPolicy | None,
    locality: CapabilityLocality = CapabilityLocality.LOCAL,
    size: int | None = None,
    available: bool = True,
    category: ModelCategory = ModelCategory.LLM,
) -> ModelInfo:
    name = model_id.split(":", 1)[-1]
    return ModelInfo(
        id=model_id,
        display_name=name,
        provider=model_id.split(":", 1)[0],
        category=category,
        size_bytes=size,
        locality=locality,
        available=available,
        data_policy=policy,
        specialisation=specialisation_from_name(name),
    )


def _local(model_id: str, *, size: int | None = None, **kw) -> ModelInfo:
    """A local model with nothing wrong with it, so tests vary one axis at a time."""
    return _model(model_id, policy=DataPolicy.NEVER_LEAVES_DEVICE, size=size, **kw)


@pytest.fixture
def manager() -> ProviderManager:
    return ProviderManager()


def _load(manager: ProviderManager, *models: ModelInfo) -> ProviderManager:
    manager.catalog.upsert_all(list(models))
    return manager


def _with_vram(manager: ProviderManager, vram_bytes: int | None) -> ProviderManager:
    """Pin the hardware profile so residency tests do not depend on the host."""
    manager._hardware = HardwareProfile(
        gpu_available=vram_bytes is not None,
        vram_bytes=vram_bytes,
        cuda_available=vram_bytes is not None,
    )
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

    def test_refused_models_are_reportable_with_reasons(self, manager):
        """A user with no default deserves to know it was the policy, not a bug.

        And which policy problem: an unknown policy is something they can fix by
        declaring one, a training provider is not.
        """
        _load(
            manager,
            _model("mystery:unknown", policy=None),
            _model("freetier:logged", policy=DataPolicy.LOGGED_AND_TRAINED_ON),
        )

        reasons = {m.id: why for m, why in manager.rejected_default_candidates()}

        assert reasons == {
            "mystery:unknown": "data policy is unknown",
            "freetier:logged": "provider logs and trains on prompts",
        }
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


class TestResidency:
    """Fitting alongside the embedder beats being large.

    The regression these exist for: on a 12 GB card with bge-m3 resident, a 9 GB
    model was selected because it was the biggest thing installed. It cannot be
    co-resident with the embedder, so every exchange pays a swap — a cost on the
    hot path that users read as the product being slow.
    """

    def test_a_9gb_model_loses_to_a_5gb_one_on_a_12gb_card(self, manager):
        """The exact case that was wrong."""
        _with_vram(manager, 12 * GB)
        _load(
            manager,
            _local("ollama:bge-m3", size=1 * GB, category=ModelCategory.EMBEDDING),
            _local("ollama:big-general", size=9 * GB),
            _local("ollama:mid-general", size=5 * GB),
        )

        assert manager.select_default_model().id == "ollama:mid-general"

    def test_the_oversized_model_is_reported_as_not_fitting(self, manager):
        _with_vram(manager, 12 * GB)
        _load(
            manager,
            _local("ollama:bge-m3", size=1 * GB, category=ModelCategory.EMBEDDING),
            _local("ollama:big-general", size=9 * GB),
            _local("ollama:mid-general", size=5 * GB),
        )

        reasons = {m.id: why for m, why in manager.rejected_default_candidates()}

        assert reasons == {
            "ollama:big-general": "does not fit alongside the embedding model"
        }

    def test_the_embedding_model_is_charged_against_the_budget(self, manager):
        """Recall runs on every exchange, so the embedder is a permanent tenant.

        Same card, same chat model — the only difference is whether an embedding
        model is also resident. It has to change the answer, or the budget is
        not doing anything.
        """
        chat = _local("ollama:general", size=8 * GB)

        alone = _with_vram(ProviderManager(), 12 * GB)
        _load(alone, chat)
        assert alone.select_default_model() is not None

        shared = _with_vram(ProviderManager(), 12 * GB)
        _load(shared, chat, _local("ollama:embed", size=3 * GB, category=ModelCategory.EMBEDDING))
        assert shared.select_default_model() is None

    def test_headroom_is_reserved_beyond_the_raw_weights(self, manager):
        """Weights are not the whole cost; the KV cache grows with context."""
        _with_vram(manager, 10 * GB)
        _load(manager, _local("ollama:exactly-vram", size=10 * GB))

        assert manager.model_fits_resident(
            manager.get_model("ollama:exactly-vram")
        ) is False
        assert manager.select_default_model() is None

    def test_unknown_vram_skips_the_fit_test_rather_than_failing_it(self, manager):
        """Metal and DirectML report no capacity. That is not a budget of zero.

        Inventing one would be the false-zero bug in a new place: every model
        would be judged not to fit and the machine would get no default at all.
        """
        _with_vram(manager, None)
        _load(manager, _local("ollama:general", size=9 * GB))

        assert manager.resident_budget_bytes() is None
        assert manager.model_fits_resident(manager.get_model("ollama:general")) is None
        assert manager.select_default_model().id == "ollama:general"

    def test_a_model_that_fits_outranks_one_of_unknown_size(self, manager):
        """"We could not check" must never outrank "it fits"."""
        _with_vram(manager, 12 * GB)
        _load(
            manager,
            _local("ollama:unsized", size=None),
            _local("ollama:known-fit", size=4 * GB),
        )

        assert manager.select_default_model().id == "ollama:known-fit"


class TestSpecialisation:
    def test_a_coder_model_is_not_the_general_default(self, manager):
        """The other half of the wrong pick: it was a coding model.

        Not a worse model than its base — a different one. Used for general
        chat it produces oddly-shaped answers rather than obvious failures,
        which is harder to notice and harder to attribute.
        """
        _with_vram(manager, 24 * GB)
        _load(
            manager,
            _local("ollama:qwen2.5-coder:14b", size=9 * GB),
            _local("ollama:gemma3", size=5 * GB),
        )

        assert manager.select_default_model().id == "ollama:gemma3"

    def test_a_coder_model_is_still_chosen_when_it_is_all_there_is(self, manager):
        """Specialisation is a preference, not a veto. Some chat beats none."""
        _with_vram(manager, 24 * GB)
        _load(manager, _local("ollama:qwen2.5-coder:14b", size=9 * GB))

        assert manager.select_default_model().id == "ollama:qwen2.5-coder:14b"

    def test_markers_match_tasks_rather_than_model_identities(self):
        """No model name is hardcoded — the markers generalise."""
        assert specialisation_from_name("qwen2.5-coder:14b") == "code"
        assert specialisation_from_name("deepseek-coder-v2") == "code"
        assert specialisation_from_name("codellama:70b") == "code"
        assert specialisation_from_name("mathstral:7b") == "math"
        assert specialisation_from_name("llama-guard3:8b") == "moderation"

        assert specialisation_from_name("gemma3:latest") is None
        assert specialisation_from_name("qwen3:latest") is None
        assert specialisation_from_name("llama3.2:latest") is None

    def test_fit_outranks_general_purpose(self, manager):
        """The stated order: a swap costs every exchange, shape costs some."""
        _with_vram(manager, 12 * GB)
        _load(
            manager,
            _local("ollama:huge-general", size=11 * GB),
            _local("ollama:small-coder", size=2 * GB),
        )

        assert manager.select_default_model().id == "ollama:small-coder"


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

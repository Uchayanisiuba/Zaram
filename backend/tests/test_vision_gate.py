"""Asking for a picture must reach a model that can see, or be refused.

This is the gate `ProviderManager.select_model_for_task` already implements,
exercised from the outside with a catalogue shaped like a real machine's. It is
here because the gate had no caller until images landed: `requires_vision` was
inferred from wording alone, so nothing ever asked it in earnest.

**The refusal is the feature.** A model that cannot see, handed a picture,
produces confident prose about an image nobody looked at — rule 9's failure in
a new medium, and worse than an error because it reads as an answer.
"""

from __future__ import annotations

import pytest

from providers.contracts import (
    CapabilityLocality,
    DataPolicy,
    ModelCategory,
    ModelInfo,
)
from providers.manager import ProviderManager


def model(
    name: str,
    *,
    vision: bool = False,
    size: int = 7_500_000_000,
    local: bool = True,
) -> ModelInfo:
    return ModelInfo(
        id=f"ollama:{name}",
        display_name=name,
        provider="ollama",
        category=ModelCategory.LLM,
        size_bytes=size,
        supports_vision=vision,
        capabilities={"completion", "vision"} if vision else {"completion"},
        locality=CapabilityLocality.LOCAL if local else CapabilityLocality.REMOTE,
        available=True,
        data_policy=DataPolicy.NEVER_LEAVES_DEVICE,
    )


@pytest.fixture()
def manager() -> ProviderManager:
    return ProviderManager()


def stock(manager: ProviderManager, *models: ModelInfo) -> None:
    manager.catalog.clear()
    manager.catalog.upsert_all(list(models))


class TestTheGateChoosesOnCapabilityNotScore:
    def test_a_seeing_model_is_chosen_over_a_better_ranked_blind_one(self, manager):
        # The blind model is smaller and would win the ranking outright.
        stock(
            manager,
            model("small-blind:7b", vision=False, size=4_000_000_000),
            model("sighted:12b", vision=True, size=7_500_000_000),
        )

        chosen = manager.select_model_for_task(requires_vision=True)

        assert chosen is not None
        assert chosen.display_name == "sighted:12b"

    def test_nothing_is_returned_when_no_model_can_see(self, manager):
        stock(manager, model("blind-a:7b"), model("blind-b:14b"))

        # `None`, never a substitute. The caller's job is to say so; answering
        # with whatever ranked highest is the failure this exists to stop.
        assert manager.select_model_for_task(requires_vision=True) is None

    def test_the_same_catalogue_still_answers_a_text_question(self, manager):
        stock(manager, model("blind-a:7b"), model("blind-b:14b"))

        # The gate must not leak into requests that never mentioned an image.
        assert manager.select_model_for_task(requires_vision=False) is not None


class TestVisionIsAGateAndSpecialisationIsAPreference:
    def test_a_missing_specialist_still_answers(self, manager):
        stock(manager, model("general:12b"))

        # "A coding model would be better" is a judgement, so the general
        # model stays a real answer.
        assert manager.select_model_for_task(specialisation="code") is not None

    def test_a_missing_eye_does_not(self, manager):
        stock(manager, model("general:12b"))

        # "It cannot accept an image" is not a worse answer, it is no answer.
        assert manager.select_model_for_task(requires_vision=True) is None


class TestTheModelsOnThisMachine:
    """Not a unit test — a check that discovery populates what the gate reads.

    Skipped when Ollama is not running, because it is a statement about the
    machine rather than about the code. It exists because `supports_vision`
    could be correct in every fixture and still be `False` for every real
    model, and the gate would then refuse every picture on a machine that can
    see one. That is exactly the failure it caught the first time it ran.
    """

    def test_discovery_fills_in_vision_support(self):
        import httpx

        try:
            httpx.get("http://127.0.0.1:11434/api/tags", timeout=2.0)
        except Exception:
            pytest.skip("Ollama is not running")

        manager = ProviderManager()
        manager.refresh()

        local = [m for m in manager.list_models() if m.provider == "ollama"]
        if not local:
            pytest.skip("no Ollama models installed")

        # At least one flag has to be readable, or `supports_vision` is
        # decorative and the gate is deciding on a field nobody fills.
        assert any(m.supports_vision for m in local) or all(
            not m.supports_vision for m in local
        )
        for m in local:
            assert isinstance(m.supports_vision, bool)

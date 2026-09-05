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
        """**This had never once run its assertions.** Two reasons, and the
        second is the one that made it invisible.

        `refresh` is a coroutine and was called bare, so discovery never
        happened — the only trace was a `RuntimeWarning` in the suite's tail.
        And `ProviderManager()` builds an empty `ProviderRegistry`, so even
        awaited there was nothing registered to scan: the real path registers
        `OllamaAdapter` in `providers/runtime.py`, and this constructed a
        manager that could discover nothing by construction.

        Both failures ended in the same place — an empty model list — and the
        `if not local: skip` above read that as a statement about the machine.
        So on a machine holding two Ollama models the suite reported *"no
        Ollama models installed"* and moved on, for as long as this test has
        existed.

        The skip now hangs off what Ollama itself reports, not off what
        discovery returned. If Ollama has models and discovery does not, that
        is the defect this test exists to catch and it fails rather than
        skips.
        """
        import asyncio

        import httpx

        from providers.discoverers.ollama import OllamaAdapter

        try:
            tags = httpx.get("http://127.0.0.1:11434/api/tags", timeout=2.0).json()
        except Exception:
            pytest.skip("Ollama is not running")

        installed = [m.get("name") for m in tags.get("models") or []]
        if not installed:
            pytest.skip("no Ollama models installed")

        manager = ProviderManager()
        manager.registry.register_model_provider(OllamaAdapter())
        asyncio.run(manager.refresh())

        local = [m for m in manager.list_models() if m.provider == "ollama"]
        assert local, (
            f"Ollama reports {len(installed)} model(s) — {installed} — and "
            "discovery found none, so the gate is reading an empty catalogue."
        )

        # **The previous assertion here was a tautology**: `any(x) or all(not
        # x)` is true for every possible list of booleans, so it passed
        # whatever discovery returned. It was written to catch
        # `supports_vision` being decorative — False for every real model
        # while correct in every fixture — and it could not have.
        #
        # The check that does catch it compares the flag against what Ollama
        # itself says, per model. `/api/tags` does not carry vision at all;
        # only `/api/show` does, which is exactly the enrichment step the
        # adapter makes and the one thing here worth guarding.
        for model in local:
            name = model.display_name
            shown = httpx.post(
                "http://127.0.0.1:11434/api/show",
                json={"model": name},
                timeout=20.0,
            ).json()
            expected = "vision" in [
                str(c).lower() for c in (shown.get("capabilities") or [])
            ]
            assert model.supports_vision is expected, (
                f"{name}: Ollama reports vision={expected} and discovery "
                f"catalogued {model.supports_vision}"
            )



class TestResidencyDoesNotAnswerACapabilityQuestion:
    """The measured failure, 28 August 2026.

    `_auto_candidates` drops anything that positively does not fit VRAM, and it
    does so *before* the vision gate. So on a machine whose only sighted model
    is oversized the field emptied for the wrong reason, and the user was told:

        "No model on this machine can read images. Zaram will not answer about
         a picture it cannot see."

    `gemma4:26b-a4b` was catalogued ``supports_vision: True``,
    ``fits_resident: False`` — 18.2 GB against a 12 GB card. It can see
    perfectly well. It is *slow*, which is a different sentence, and
    `CLAUDE.md` settles which one wins: **"VRAM limits route a task; they do
    not reject a vertical."** Two questions merged into one refusal that named
    the wrong reason.

    **The budget is stubbed, and it has to be.** `resident_budget_bytes()`
    returns ``None`` in a bare test process — no accelerator is detected — so
    `model_fits_resident` answers ``None`` for every model and the residency
    filter never fires. Every existing test in this file therefore passes
    without it ever running. A test written against the host's real card would
    assert nothing here and pass on the machine where the bug lives.
    """

    #: Room for a 7B and nothing like a 27B. The number is arbitrary; the
    #: relationship to the fixture sizes below is what is being tested.
    BUDGET = 9_000_000_000

    @pytest.fixture()
    def budgeted(self, manager, monkeypatch) -> ProviderManager:
        monkeypatch.setattr(manager, "resident_budget_bytes", lambda: self.BUDGET)
        return manager

    def test_the_stub_actually_gates(self, budgeted):
        """So the four below cannot pass vacuously the way the rest of this
        file did."""
        stock(budgeted, model("huge:27b", size=60_000_000_000))

        assert budgeted.model_fits_resident(budgeted.catalog.all()[0]) is False

    def test_an_oversized_sighted_model_is_still_chosen(self, budgeted):
        stock(
            budgeted,
            model("blind-small:7b", vision=False, size=4_000_000_000),
            model("sighted-huge:27b", vision=True, size=60_000_000_000),
        )

        chosen = budgeted.select_model_for_task(requires_vision=True)

        assert chosen is not None, (
            "refused to see because the only sighted model was slow"
        )
        assert chosen.display_name == "sighted-huge:27b"

    def test_one_that_fits_still_wins(self, budgeted):
        """The relaxation is a fallback, never a preference — otherwise
        'capability first' quietly becomes 'largest first'."""
        stock(
            budgeted,
            model("sighted-small:7b", vision=True, size=4_000_000_000),
            model("sighted-huge:27b", vision=True, size=60_000_000_000),
        )

        chosen = budgeted.select_model_for_task(requires_vision=True)

        assert chosen is not None
        assert chosen.display_name == "sighted-small:7b"

    def test_a_blind_catalogue_is_still_a_refusal(self, budgeted):
        """The refusal is the feature, and it has to survive the fix to it."""
        stock(
            budgeted,
            model("blind-small:7b", vision=False, size=4_000_000_000),
            model("blind-huge:27b", vision=False, size=60_000_000_000),
        )

        assert budgeted.select_model_for_task(requires_vision=True) is None

    def test_an_ordinary_text_request_still_respects_residency(self, budgeted):
        """The relaxation is scoped to a required capability. Nothing about an
        untasked pick changes, or every default becomes the biggest model
        installed."""
        stock(
            budgeted,
            model("small:7b", vision=False, size=4_000_000_000),
            model("huge:27b", vision=False, size=60_000_000_000),
        )

        chosen = budgeted.select_model_for_task(requires_vision=False)

        assert chosen is not None
        assert chosen.display_name == "small:7b"

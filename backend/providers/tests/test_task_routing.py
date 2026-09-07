"""Selecting a model for *this* question, not for questions in general.

``select_model_for_task`` takes two arguments and they are different kinds of
thing on purpose — a gate and a preference — so most of this file is about
keeping them apart. That distinction is the one CLAUDE.md records as this
codebase's most expensive recurring bug. The ``orchestrator`` package held a
version that got it wrong — `scoring.py` recorded a missing *required*
capability as a warning and ranked the candidate anyway — and was deleted on
28 August 2026, unimported by anything, so the wrong version is gone rather
than merely unused.

The failure that produces is not a slightly worse answer. It is a text-only
model asked to read a screenshot, answering with confident prose about an image
it never received.
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


def _local(
    model_id: str,
    *,
    size: int | None = None,
    vision: bool = False,
) -> ModelInfo:
    """A local model with nothing wrong with it, so tests vary one axis."""
    name = model_id.split(":", 1)[-1]
    return ModelInfo(
        id=model_id,
        display_name=name,
        provider=model_id.split(":", 1)[0],
        category=ModelCategory.LLM,
        size_bytes=size,
        locality=CapabilityLocality.LOCAL,
        available=True,
        data_policy=DataPolicy.NEVER_LEAVES_DEVICE,
        supports_vision=vision,
        specialisation=specialisation_from_name(name),
    )


@pytest.fixture
def manager() -> ProviderManager:
    """A 12 GB card with no embedder discovered, so the budget is 9.6 GB.

    Pinned rather than probed: a residency test that reads the host passes or
    fails according to which machine ran it, which is the same as not asserting
    anything.
    """
    manager = ProviderManager()
    manager._hardware = HardwareProfile(
        gpu_available=True, vram_bytes=12 * GB, cuda_available=True
    )
    return manager


def _load(manager: ProviderManager, *models: ModelInfo) -> ProviderManager:
    manager.catalog.upsert_all(list(models))
    return manager


class TestModalityIsAGate:
    """Binary, applied before ranking, and able to return nothing."""

    def test_a_blind_model_that_would_otherwise_win_is_not_chosen(self, manager):
        """Every ranking axis favours the blind model. It still loses.

        Bigger, general-purpose, fits, sorts first by id — if modality were a
        term in the score rather than a filter over the field, this is the case
        where it would be outvoted, and outvoting it is exactly the bug.
        """
        _load(
            manager,
            _local("ollama:aaa-big", size=9 * GB, vision=False),
            _local("ollama:zzz-small", size=2 * GB, vision=True),
        )

        chosen = manager.select_model_for_task(requires_vision=True)

        assert chosen is not None
        assert chosen.display_name == "zzz-small"

    def test_no_vision_model_means_no_model(self, manager):
        """``None``, never a substitute.

        A caller handed the blind model here would answer the question anyway,
        describing an image it was never sent. Rule 9: fail rather than invent.
        """
        _load(manager, _local("ollama:blind", size=4 * GB, vision=False))

        assert manager.select_model_for_task(requires_vision=True) is None
        # And the same field, un-gated, is not empty — so the None above is the
        # gate talking and not an empty catalogue.
        assert manager.select_model_for_task() is not None

    def test_the_gate_is_not_applied_when_the_task_does_not_ask(self, manager):
        """A vision-capable model has no advantage on a text question."""
        _load(
            manager,
            _local("ollama:seer", size=2 * GB, vision=True),
            _local("ollama:talker", size=9 * GB, vision=False),
        )

        chosen = manager.select_model_for_task()

        assert chosen is not None
        assert chosen.display_name == "talker"


class TestSpecialisationIsAPreference:
    """A judgement about quality, so the general model stays a real answer."""

    def test_the_specialist_wins_for_its_own_task(self, manager):
        _load(
            manager,
            _local("ollama:qwen2.5-coder:14b", size=9 * GB),
            _local("ollama:gemma4:12b", size=7 * GB),
        )

        chosen = manager.select_model_for_task(specialisation="code")

        assert chosen is not None
        assert chosen.display_name == "qwen2.5-coder:14b"

    def test_the_general_model_wins_when_no_task_is_named(self, manager):
        """The pre-existing behaviour, asserted here because this change could
        have broken it: size-first selection is what once put a 9 GB coding
        model in front of general chat."""
        _load(
            manager,
            _local("ollama:qwen2.5-coder:14b", size=9 * GB),
            _local("ollama:gemma4:12b", size=7 * GB),
        )

        chosen = manager.select_model_for_task()

        assert chosen is not None
        assert chosen.display_name == "gemma4:12b"

    def test_a_specialist_for_another_task_ranks_below_the_general_model(
        self, manager
    ):
        """Three tiers, which is why the rank is not a boolean.

        A maths fine-tune is a worse answer to a coding question than a general
        model is. A two-way "matches / does not match" split would rank them
        equal and let size decide.
        """
        _load(
            manager,
            _local("ollama:mathstral:7b", size=9 * GB),
            _local("ollama:gemma4:12b", size=7 * GB),
        )

        chosen = manager.select_model_for_task(specialisation="code")

        assert chosen is not None
        assert chosen.display_name == "gemma4:12b"

    def test_the_general_model_answers_when_no_specialist_is_installed(self, manager):
        """Unlike the modality gate, this never returns None."""
        _load(manager, _local("ollama:gemma4:12b", size=7 * GB))

        chosen = manager.select_model_for_task(specialisation="code")

        assert chosen is not None
        assert chosen.display_name == "gemma4:12b"

    def test_fit_outranks_the_task_match(self, manager):
        """The specialist does not fit beside the embedder, so it is not worth
        the eviction — which costs this exchange *and* the one that swaps back.

        Fit is first in the rank key for this reason, and this is the coding
        half of what ``test_fit_outranks_general_purpose`` asserts untasked.
        """
        _load(
            manager,
            _local("ollama:qwen2.5-coder:70b", size=40 * GB),
            _local("ollama:gemma4:12b", size=7 * GB),
        )

        chosen = manager.select_model_for_task(specialisation="code")

        assert chosen is not None
        assert chosen.display_name == "gemma4:12b"


class TestConsentGatesStillApply:
    """The task may narrow the field. It may never widen it."""

    def test_a_model_with_no_data_policy_is_not_reachable_by_a_task(self, manager):
        """The gate that matters most, checked from the new entry point.

        `select_model_for_task` builds its own candidate list, so the policy
        refusal had to be shared rather than reimplemented — a second selection
        path with its own copy of the consent rules is how one of them ends up
        missing a clause.
        """
        blind_but_vetted = _local("ollama:vetted", size=4 * GB, vision=False)
        unvetted_seer = ModelInfo(
            id="mystery:seer",
            display_name="seer",
            provider="mystery",
            category=ModelCategory.LLM,
            size_bytes=4 * GB,
            locality=CapabilityLocality.CLOUD,
            available=True,
            data_policy=None,
            supports_vision=True,
        )
        _load(manager, blind_but_vetted, unvetted_seer)

        # The only vision-capable model present is one we may not choose, so
        # the honest answer is none — not "the closest thing we are allowed".
        assert manager.select_model_for_task(requires_vision=True) is None


class TestTheUntaskedDefaultIsUnchanged:
    def test_select_default_model_is_the_untasked_case(self, manager):
        """One implementation, so the two can never drift apart."""
        _load(
            manager,
            _local("ollama:qwen2.5-coder:14b", size=9 * GB),
            _local("ollama:gemma4:12b", size=7 * GB),
            _local("ollama:tiny", size=1 * GB),
        )

        assert manager.select_default_model() == manager.select_model_for_task()


class TestWhatIsAlreadyLoadedComesFirst:
    """The swap-avoidance term, which for a long time avoided no swaps.

    `_rank_key` put `model_fits_resident` first and justified it in prose as
    preferring "a general model that is already resident". Those are two
    different questions: fit is about **capacity** — could this sit beside the
    embedder — and residency is about **what is on the card right now**. Nothing
    in the key asked the second one.

    On a machine that holds one model at a time the gap has teeth. Every local
    model on the maintainer's 12 GB card exceeds the resident budget, so the fit
    term was flat and a reply could route to a *cold* model, evicting the warm
    one that was already answering — a swap performed in the name of avoiding
    swaps, costing 106 seconds measured.
    """

    @pytest.fixture
    def two_models(self, manager):
        return _load(
            manager,
            _local("ollama:general:latest", size=10 * GB),
            _local("ollama:coder:latest", size=10 * GB),
        )

    def test_the_warm_model_wins_over_a_cold_one(self, two_models, monkeypatch):
        monkeypatch.setattr(
            two_models, "_resident_models", lambda: {"coder:latest": 10 * GB}
        )

        chosen = two_models.select_model_for_task()

        assert chosen is not None and chosen.id == "ollama:coder:latest"

    def test_it_beats_the_task_match_too(self, two_models, monkeypatch):
        """Deliberate, and the same call the fit term already made.

        A warm general model answers a coding question rather than spending two
        minutes loading the specialist. Where that is wrong the remedy is the
        per-task assignment in Settings, which is explicit and does not come
        through this ranking.
        """
        monkeypatch.setattr(
            two_models, "_resident_models", lambda: {"general:latest": 10 * GB}
        )

        chosen = two_models.select_model_for_task(specialisation="code")

        assert chosen is not None and chosen.id == "ollama:general:latest"

    def test_unknown_residency_changes_nothing(self, two_models, monkeypatch):
        """`None` is "cannot tell", never "not loaded".

        A local server that reports nothing must not push a possibly-warm model
        behind a definitely-cold one on no evidence — so the term goes flat and
        ordering falls back to exactly what it was.
        """
        monkeypatch.setattr(two_models, "_resident_models", lambda: None)

        without = two_models.select_model_for_task()

        monkeypatch.setattr(two_models, "_resident_models", lambda: {})
        with_empty_card = two_models.select_model_for_task()

        assert without is not None and with_empty_card is not None
        assert without.id == with_empty_card.id

    def test_residency_is_read_once_and_not_per_candidate(self, two_models, monkeypatch):
        """It asks every local server over HTTP.

        Called from inside the sort key it would run once per candidate, turning
        one routing decision into N round trips on the critical path of every
        reply — a performance bug that no assertion about *ordering* would ever
        catch.
        """
        calls: list[int] = []

        def counted():
            calls.append(1)
            return {"coder:latest": 10 * GB}

        monkeypatch.setattr(two_models, "_resident_models", counted)

        two_models.select_model_for_task()

        assert len(calls) == 1

    def test_a_loosely_named_model_still_matches(self, manager, monkeypatch):
        """`/api/ps` says `gemma:latest`; the catalogue says `ollama:gemma`.

        Comparing those directly never matches, which would make this whole term
        silently inert — the failure `_same_model` exists to prevent, arriving
        through a new caller.
        """
        loaded = _load(
            manager,
            _local("ollama:gemma", size=10 * GB),
            _local("ollama:other", size=10 * GB),
        )
        monkeypatch.setattr(loaded, "_resident_models", lambda: {"gemma:latest": 10 * GB})

        chosen = loaded.select_model_for_task()

        assert chosen is not None and chosen.id == "ollama:gemma"

    def test_a_probe_that_throws_does_not_fail_the_route(self, two_models, monkeypatch):
        """*"A broken residency probe must cost the user an indicator, never an
        answer"* — the rule `_swap_preflight_event` states for itself, applied
        to the new caller.

        The first version of this term did not keep it. `_resident_models`
        needs a wired registry, so a partially-built manager raised
        `AttributeError` from inside the sort and took the whole selection down
        — five failures across the suite, all of them a routing decision dying
        because an optimisation could not answer.
        """
        def explode():
            raise AttributeError("no registry here")

        monkeypatch.setattr(two_models, "_resident_models", explode)

        chosen = two_models.select_model_for_task()

        assert chosen is not None

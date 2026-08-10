"""Does a route that forces a model swap say so *before* it happens?

CLAUDE.md: *"Some model pairs are co-resident; others force an unload/reload
costing seconds… a route that requires a swap must be visible in the orb's
state. An invisible swap reads as a broken product."*

The word that matters is **before**. A spinner that appears once the machine has
already stalled is not visibility: by then the user has spent the seconds and
drawn their own conclusion about why Zaram is slow. So this is a pre-flight
check against what is actually resident, run before generation starts.

Four outcomes, because the remedies differ and a boolean would hide that:

- `resident` — already loaded, nothing to say
- `load` — not loaded but it fits, which is a cold start (`warming`) and
  passes on its own
- `swap` — something resident must be evicted; recurring, that is a
  model-assignment problem the user can fix in Settings
- `oversized` — bigger than the whole budget, so evicting everything would not
  help. A hardware fact no setting changes, and *not* a swap: nothing is
  displaced, and an indicator naming nothing evicted cannot explain itself

And a fifth answer that is not an outcome: `None`, for "cannot be determined".
Announcing a swap that does not happen trains the user to ignore the indicator,
which costs more than staying quiet.
"""
from __future__ import annotations

from typing import Optional

import pytest

from providers.contracts import (
    CapabilityLocality,
    HardwareProfile,
    ModelCategory,
    ModelInfo,
)
from providers.manager import ProviderManager

GB = 1024 ** 3


class _FakeAdapter:
    """Reports residency the way the Ollama adapter does."""

    provider_id = "ollama"

    def __init__(self, resident: Optional[dict]):
        self._resident = resident

    def resident_models(self, *, timeout: float = 1.0):
        return self._resident


def _model(model_id: str, size_gb: float, category=ModelCategory.LLM) -> ModelInfo:
    return ModelInfo(
        id=model_id,
        display_name=model_id,
        provider="ollama",
        category=category,
        locality=CapabilityLocality.LOCAL,
        size_bytes=int(size_gb * GB),
        available=True,
    )


def _catalogued(
    model_id: str, display_name: str, size_gb: float, category=ModelCategory.LLM
) -> ModelInfo:
    """A model as *discovery* produces it: id provider-prefixed, display name
    the provider-native one."""
    return ModelInfo(
        id=model_id,
        display_name=display_name,
        provider="ollama",
        category=category,
        locality=CapabilityLocality.LOCAL,
        size_bytes=int(size_gb * GB),
        available=True,
    )


@pytest.fixture
def manager():
    """A 12 GB card with bge-m3 resident — the dev machine, in miniature.

    Budget: 12 GB, less the 1.16 GB embedder, less a 20% KV reserve = ~8.4 GB.
    """
    mgr = ProviderManager()
    mgr.catalog.upsert_all([
        _model("bge-m3:latest", 1.16, category=ModelCategory.EMBEDDING),
        _model("gemma3:latest", 3.3),
        _model("qwen2.5-coder:14b", 9.0),   # larger than the whole budget
        _model("qwen3:latest", 6.0),        # fits alone, not beside gemma3
        _model("llama3.2:latest", 2.0),
    ])
    mgr._hardware = HardwareProfile(vram_bytes=12 * GB, gpu_available=True)
    return mgr


class TestTheThreeOutcomes:
    def test_a_model_already_loaded_needs_nothing(self, manager):
        manager.registry.register_model_provider(_FakeAdapter({"gemma3:latest": int(3.3 * GB)}))
        plan = manager.swap_preflight("gemma3:latest")

        assert plan is not None
        assert plan.kind == "resident"
        assert plan.requires_swap is False

    def test_a_bare_name_matches_a_latest_tag(self, manager):
        """`/api/ps` says `gemma3:latest`; a request may say `gemma3`.

        Ollama treats the bare name as `:latest`. Comparing the strings
        directly would make every reply look like it needed a different model
        than the one already loaded, and the orb would announce a swap before
        every single message — the indicator crying wolf on its first day.
        """
        manager.registry.register_model_provider(_FakeAdapter({"gemma3:latest": int(3.3 * GB)}))
        assert manager.swap_preflight("gemma3").kind == "resident"

    def test_a_cold_start_with_room_is_a_load_not_a_swap(self, manager):
        """Nothing resident, model fits: a wait with no eviction behind it.

        This is the distinction that stops `swapping` from becoming a synonym
        for "slow". The remedy differs — a cold start passes on its own, while
        a swap recurring every other message is a model-assignment problem the
        user can fix in Settings — so the two must not share a word.
        """
        manager.registry.register_model_provider(_FakeAdapter({}))
        plan = manager.swap_preflight("gemma3:latest")

        assert plan.kind == "load"
        assert plan.requires_swap is False
        assert plan.evicts == []

    def test_a_model_that_does_not_fit_alongside_the_resident_one_is_a_swap(self, manager):
        """The case the rule exists for.

        gemma3 (3.3 GB) is loaded and the request routes to a 6 GB model. The
        budget is ~8.4 GB: 6 fits on its own, 3.3 + 6 does not, so gemma3 has
        to go. That is a genuine eviction, unlike a model too big for the card
        at all.
        """
        manager.registry.register_model_provider(_FakeAdapter({"gemma3:latest": int(3.3 * GB)}))
        plan = manager.swap_preflight("qwen3:latest")

        assert plan.kind == "swap"
        assert plan.requires_swap is True
        assert plan.evicts == ["gemma3:latest"], (
            "a swap must name what it displaces — that is the evidence the user "
            "needs to change the assignment in Settings"
        )

    def test_the_embedder_is_not_counted_against_the_budget_twice(self, manager):
        """bge-m3 is resident continuously and already deducted.

        `resident_budget_bytes` subtracts the embedding footprint before
        returning. Counting the resident bge-m3 again here would double-charge
        it and report a swap on a machine with room to spare — a false alarm on
        the one indicator whose whole job is to be trusted.
        """
        manager.registry.register_model_provider(_FakeAdapter({"bge-m3:latest": int(0.66 * GB)}))
        plan = manager.swap_preflight("gemma3:latest")

        assert plan.kind == "load", (
            f"the embedder was counted against the chat budget: {plan.to_dict()}"
        )
        assert plan.evicts == []


class TestTheRealCatalogShape:
    """Provider-prefixed ids, which is what discovery actually produces.

    The fixture above keys models by their bare Ollama names, and every test
    using it passed while `swap_preflight` was returning `None` for every model
    on the real machine. The catalog stores `ollama:gemma3:latest`; `/api/ps`
    and the chat path both say `gemma3:latest`. Comparing ids alone never
    matched, so the model was never resolved, the embedder was never recognised
    as the embedder, and the whole check silently did nothing.

    It failed the right way — silence rather than a false alarm — but it failed
    completely, and only running it against the real provider layer showed it.
    This class exists so the fake can never again be a friendlier shape than
    the truth.
    """

    @pytest.fixture
    def real_shaped(self):
        mgr = ProviderManager()
        mgr.catalog.upsert_all([
            _catalogued("ollama:bge-m3:latest", "bge-m3:latest", 1.16,
                        ModelCategory.EMBEDDING),
            _catalogued("ollama:gemma3:latest", "gemma3:latest", 3.3),
            _catalogued("ollama:qwen2.5-coder:14b", "qwen2.5-coder:14b", 9.0),
            _catalogued("ollama:qwen3:latest", "qwen3:latest", 6.0),
        ])
        mgr._hardware = HardwareProfile(vram_bytes=12 * GB, gpu_available=True)
        return mgr

    def test_a_provider_native_name_resolves_against_a_prefixed_catalog(self, real_shaped):
        real_shaped.registry.register_model_provider(_FakeAdapter({}))
        plan = real_shaped.swap_preflight("gemma3:latest")

        assert plan is not None, (
            "the catalog stores 'ollama:gemma3:latest' and the caller says "
            "'gemma3:latest' — the pre-flight must resolve that, or it reports "
            "'cannot determine' for every model on every real machine"
        )
        assert plan.kind == "load"

    def test_the_resident_embedder_is_recognised_through_the_prefix(self, real_shaped):
        """The double-charge bug, in the shape it actually occurs.

        `/api/ps` reports `bge-m3:latest`; the catalog id is
        `ollama:bge-m3:latest`. Matching on id alone means the embedder is not
        recognised, so its 0.66 GB is counted against a budget that has already
        deducted it — and a machine with room reports a swap.
        """
        real_shaped.registry.register_model_provider(
            _FakeAdapter({"bge-m3:latest": int(0.66 * GB)})
        )
        plan = real_shaped.swap_preflight("gemma3:latest")

        assert plan.kind == "load", (
            f"the embedder was charged against the chat budget: {plan.to_dict()}"
        )
        assert plan.evicts == []

    def test_a_model_larger_than_the_whole_budget_is_not_called_a_swap(self, real_shaped):
        """Nothing to evict that would make room, so it is not a swap.

        The 9 GB coder against an ~8.4 GB budget does not fit even on an empty
        card. Ollama loads it with layers spilled to system RAM — slow for a
        different reason, with a different remedy, and no model displaced.
        Calling that a swap produces an indicator that names nothing evicted,
        which cannot explain itself.
        """
        real_shaped.registry.register_model_provider(
            _FakeAdapter({"bge-m3:latest": int(0.66 * GB)})
        )
        plan = real_shaped.swap_preflight("qwen2.5-coder:14b")

        assert plan.kind == "oversized", plan.to_dict()
        assert plan.requires_swap is False
        assert plan.evicts == []

    def test_a_real_swap_is_still_detected_with_prefixed_ids(self, real_shaped):
        """The guard against fixing resolution by making everything match."""
        real_shaped.registry.register_model_provider(
            _FakeAdapter({"gemma3:latest": int(3.3 * GB)})
        )
        plan = real_shaped.swap_preflight("qwen3:latest")

        assert plan.kind == "swap"
        assert plan.evicts == ["gemma3:latest"]


class TestItRefusesToGuess:
    def test_an_unreachable_ollama_reports_nothing(self, manager):
        """`None` residency is "could not find out", not "nothing is loaded".

        Collapsing the two would announce a swap on every message the moment
        Ollama is briefly busy. Same discipline as `vram_bytes`: unknown is a
        value, not a zero.
        """
        manager.registry.register_model_provider(_FakeAdapter(None))
        assert manager.swap_preflight("gemma3:latest") is None

    def test_an_unmeasurable_card_reports_nothing(self, manager):
        """Metal and DirectML report no VRAM figure. No budget, no claim."""
        manager.registry.register_model_provider(_FakeAdapter({}))
        manager._hardware = HardwareProfile(vram_bytes=None, gpu_available=True)
        assert manager.swap_preflight("gemma3:latest") is None

    def test_a_model_of_unknown_size_reports_nothing(self, manager):
        manager.registry.register_model_provider(_FakeAdapter({}))
        manager.catalog.upsert_all([
            ModelInfo(
                id="mystery:latest", display_name="mystery", provider="ollama",
                category=ModelCategory.LLM, locality=CapabilityLocality.LOCAL,
                size_bytes=None, available=True,
            )
        ])
        assert manager.swap_preflight("mystery:latest") is None

    def test_an_unknown_model_reports_nothing(self, manager):
        manager.registry.register_model_provider(_FakeAdapter({}))
        assert manager.swap_preflight("not-installed:latest") is None

    def test_an_adapter_that_raises_does_not_break_the_reply(self, manager):
        """This runs on the critical path of every generation.

        A residency probe that throws must degrade to "no claim", never to an
        error — the reply matters more than the indicator.
        """
        class _Broken:
            provider_id = "ollama"

            def resident_models(self, *, timeout: float = 1.0):
                raise OSError("connection reset")

        manager.registry.register_model_provider(_Broken())
        assert manager.swap_preflight("gemma3:latest") is None

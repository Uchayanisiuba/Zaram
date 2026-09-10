"""Among equals, Zaram routes to the model that will forget least.

**The window is the memory.** A conversation gets a quarter of three quarters
of it, so 16,384 tokens holds roughly seven ordinary exchanges and 65,536 holds
roughly thirty — measured 10 September 2026 against the installed set. Ordering
on that is the routing-layer half of *"Zaram does not follow a long
conversation"*; the budget-layer half was fixed the same day.

**The bug this replaced was a missing field, not a judgement.** `_rank_key`
tiebroke on `-(size_bytes or 0)`, and an OpenAI-compatible server reports no
size at all — the contract has no field for one. So a TabbyAPI model holding
65,536 tokens scored `0` and sorted behind every Ollama model that reported a
size, including a 14B holding a quarter as much. Nothing preferred Ollama; the
other side simply had nothing in the column being sorted on.

The fix orders on the window **above** size rather than inventing a size for
the models that lack one. An invented size would not stay in the ranking: it
feeds `model_fits_resident`, where it stops being a preference and becomes a
capacity claim about somebody's card.

**Ordering only.** Membership was settled before this key was built — consent,
residency, capability — and a window may never decide what a model is
*allowed* to answer. That split is the one this codebase has paid to relearn
three times.
"""

from __future__ import annotations

from core.contracts import CapabilityLocality
from providers.contracts import ModelCategory, ModelInfo
from providers.manager import ProviderManager


def _model(
    model_id: str,
    *,
    window: int | None,
    size: int | None,
    local: bool = True,
) -> ModelInfo:
    return ModelInfo(
        id=model_id,
        display_name=model_id,
        provider=model_id.split(":")[0],
        provider_kind=None,
        category=ModelCategory.LLM,
        size_bytes=size,
        context_length=window,
        locality=CapabilityLocality.LOCAL if local else CapabilityLocality.CLOUD,
    )


def _order(manager: ProviderManager, models: list[ModelInfo]) -> list[str]:
    """The ids in the order the router would consider them."""
    return [
        m.id
        for m in sorted(
            models,
            key=lambda m: manager._rank_key(
                m, cloud_first=False, specialisation=None, resident=None
            ),
        )
    ]


class TestTheReportedFailure:
    def test_a_bigger_window_beats_a_reported_size(self):
        """The measured case, as a test.

        TabbyAPI's 27B holds 65,536 tokens and reports no size; the 14B holds
        16,384 and reports 10.4 GB. Before the window term the 14B won, on the
        strength of having a number in the column being sorted.
        """
        manager = ProviderManager()
        tabby = _model("lm_studio:qwen3.8-27b-exl3", window=65536, size=None)
        ollama = _model("ollama:qwen3-14b-16k", window=16384, size=10_410_000_000)

        assert _order(manager, [ollama, tabby])[0] == tabby.id

    def test_size_still_decides_when_the_windows_match(self):
        """The old tiebreak is kept, not replaced. Where two models hold the
        same conversation, the larger one is still the better answer."""
        manager = ProviderManager()
        big = _model("ollama:big", window=32768, size=20_000_000_000)
        small = _model("ollama:small", window=32768, size=8_000_000_000)

        assert _order(manager, [small, big])[0] == big.id


class TestUnknownIsLastAmongKnown:
    def test_a_model_that_cannot_say_ranks_below_one_that_can(self):
        """Prefer the model *known* to hold more over one that cannot say.

        Not a punishment for silence: a model with no window recorded is most
        often one with no explicit `num_ctx`, which Ollama serves its 4,096
        default — the smallest window on the machine.
        """
        manager = ProviderManager()
        known = _model("ollama:known", window=16384, size=None)
        unknown = _model("ollama:unknown", window=None, size=None)

        assert _order(manager, [unknown, known])[0] == known.id

    def test_two_unknowns_fall_through_to_the_old_order(self):
        """No regression where nothing reports a window: the term is flat and
        ordering is exactly what it was before."""
        manager = ProviderManager()
        big = _model("ollama:big", window=None, size=20_000_000_000)
        small = _model("ollama:small", window=None, size=8_000_000_000)

        assert _order(manager, [small, big])[0] == big.id


class TestItOrdersAndNeverFilters:
    def test_every_candidate_survives_the_ranking(self):
        """A window is a preference. Membership was decided before this key
        existed, and letting a score remove a candidate is the merge this
        codebase has paid for three times — a citation floor read against a
        ranking blend, a shortlist selected on one, and an eval that graded
        itself.
        """
        manager = ProviderManager()
        models = [
            _model("ollama:none", window=None, size=None),
            _model("ollama:small", window=4096, size=1),
            _model("lm_studio:huge", window=131072, size=None),
        ]

        assert len(_order(manager, models)) == len(models)

    def test_locality_still_outranks_the_window(self):
        """A preference the user expressed beats one Zaram inferred.

        A cloud model with a vast window must not quietly outrank a local one
        under `prefer_local`'s neighbour setting — locality sits above this
        term in the key, and rule 5 is not something a context length may
        argue with.
        """
        manager = ProviderManager()
        cloud = _model("openrouter:huge", window=1_000_000, size=None, local=False)
        local = _model("ollama:modest", window=8192, size=None)

        assert _order(manager, [cloud, local])[0] == local.id

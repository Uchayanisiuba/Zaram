"""A model that cannot fit says so before it is chosen, not after.

**This is the other half of the failure that opened 27 August 2026.** The user's
only installed chat model was `gemma4:26b-a4b-it-q4_K_M` — 18.2 GB on disk
against a 12 GB card, so roughly twice the ~9.1 GB a chat model may claim beside
the embedder. They chose it in Settings, waited, and got::

    [ERROR] Ollama could not answer with gemma4:26b-a4b-it-q4_K_M:
    HTTPConnectionPool(host='127.0.0.1', port=11434):
    Read timed out. (read timeout=120)

The timeout was fixed separately. This is about the fact that **the product
already knew.** `ProviderManager.model_fits_resident` returns the verdict,
`rejected_default_candidates` even phrases it — *"does not fit alongside the
embedding model"* — and both of those served auto-selection only. A model the
user picks by hand skips the gate entirely, which is correct (a deliberate
choice is theirs to make) and silent, which is not.

So the verdict now travels to the interface, and these tests pin the part that
is easy to get wrong: it is **three-valued**, and the unknown case must never
be rendered as a yes.
"""

from __future__ import annotations

import pytest

from providers.contracts import (
    CapabilityLocality,
    DataPolicy,
    ModelCategory,
    ModelInfo,
)

GB = 1024 ** 3


def _model(model_id: str, size_bytes: int | None, **kw) -> ModelInfo:
    return ModelInfo(
        id=model_id,
        display_name=model_id.split(":", 1)[-1],
        provider="ollama",
        category=kw.pop("category", ModelCategory.LLM),
        locality=kw.pop("locality", CapabilityLocality.LOCAL),
        size_bytes=size_bytes,
        data_policy=kw.pop("data_policy", DataPolicy.NEVER_LEAVES_DEVICE),
        **kw,
    )


class _Manager:
    """Only what `_payload` asks of a manager.

    A stub rather than a real `ProviderManager` because the question here is
    what reaches the wire, not how the budget is computed — that is measured in
    `providers/tests/test_default_model_selection.py`. Keeping them apart means
    a change to the budget arithmetic fails there, where the reasoning lives,
    rather than here.
    """

    def __init__(self, budget: int | None) -> None:
        self._budget = budget

    def resident_budget_bytes(self) -> int | None:
        return self._budget

    def model_fits_resident(self, model: ModelInfo) -> bool | None:
        if self._budget is None or model.size_bytes is None:
            return None
        return model.size_bytes <= self._budget


def _payload_for(model: ModelInfo, budget: int | None) -> dict:
    from providers.api import _payload

    return _payload(_Manager(budget), model)


class TestTheVerdictReachesTheInterface:
    def test_a_model_twice_the_card_is_marked_as_not_fitting(self):
        """The measured case, in the shape it actually occurred."""
        payload = _payload_for(
            _model("ollama:gemma4:26b-a4b-it-q4_K_M", int(16.99 * GB)),
            budget=int(9.1 * GB),
        )

        assert payload["fits_resident"] is False

    def test_a_model_that_fits_says_so(self):
        payload = _payload_for(
            _model("ollama:qwen2.5-coder:7b", int(4.7 * GB)), budget=int(9.1 * GB)
        )

        assert payload["fits_resident"] is True

    def test_the_budget_rides_along_so_the_reason_can_name_numbers(self):
        """*"18.2 GB, and this machine has 9.1 GB for a chat model"* is a
        sentence someone can act on. *"Does not fit"* is not."""
        budget = int(9.1 * GB)
        payload = _payload_for(_model("ollama:big", int(17 * GB)), budget=budget)

        assert payload["resident_budget_bytes"] == budget
        assert payload["size_bytes"] == int(17 * GB)

    def test_the_record_is_carried_whole(self):
        """The fit is added to the model record, never substituted for it."""
        payload = _payload_for(_model("ollama:gemma3:latest", 3 * GB), budget=9 * GB)

        assert payload["id"] == "ollama:gemma3:latest"
        assert payload["data_policy"] == DataPolicy.NEVER_LEAVES_DEVICE.value
        assert payload["locality"] == CapabilityLocality.LOCAL.value


class TestUnknownIsNeverAQuietYes:
    """``None`` is a third answer and the UI must not round it to ``True``.

    CLAUDE.md draws this line twice for the same reason — `vram_bytes` returns
    ``None`` rather than ``0``, and `locality_of` returns ``None`` rather than
    guessing local — because *"a confident false claim on the one thing the
    user is most likely to check"* costs more than an admission of ignorance.
    """

    def test_an_unreadable_card_yields_no_verdict(self):
        """Metal and DirectML report no capacity. Apple shares one pool with
        the CPU, so quoting system RAM would overstate what a model can claim."""
        payload = _payload_for(_model("ollama:anything", 8 * GB), budget=None)

        assert payload["fits_resident"] is None
        assert payload["resident_budget_bytes"] is None

    def test_a_model_that_does_not_state_its_size_yields_no_verdict(self):
        payload = _payload_for(_model("ollama:mystery", None), budget=9 * GB)

        assert payload["fits_resident"] is None

    def test_a_cloud_model_is_not_reported_as_too_large(self):
        """Residency is a question about this machine, and a cloud model does
        not occupy it. Reporting `False` would grey out every cloud model on a
        laptop with no GPU — the exact machine that needs them most."""
        payload = _payload_for(
            _model(
                "openrouter:anthropic/claude-sonnet-4.5",
                None,
                locality=CapabilityLocality.CLOUD,
                data_policy=DataPolicy.YOUR_KEY_NO_TRAINING,
            ),
            budget=int(9.1 * GB),
        )

        assert payload["fits_resident"] is None
        assert payload["fits_resident"] is not False


class TestTheRealManagerAnswersTheSameWay:
    """One test against the real thing, so the stub above cannot drift.

    Without this the suite would be asserting that `_payload` calls two methods
    that a fake happens to implement — which passes forever, including after
    `ProviderManager` renames one of them.
    """

    def test_the_manager_exposes_what_the_payload_asks_for(self):
        from providers.manager import ProviderManager

        assert callable(getattr(ProviderManager, "model_fits_resident", None))
        assert callable(getattr(ProviderManager, "resident_budget_bytes", None))

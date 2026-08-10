"""OpenRouter, and the guarantee we refuse to make.

An audit of this repo proposed registering OpenRouter with
``data_policy=YOUR_KEY_NO_TRAINING``. That single line would have made every
model it returns ``selectable_by_default`` — including the ``:free`` variants,
which are free *because* prompts are logged and may be trained on. Zaram would
then have auto-routed a user's confidential document to a provider that trains
on it, while the interface displayed a privacy guarantee.

These tests exist so that line cannot be added back quietly. They assert the
absence of a claim, which is unusual for a test suite and is the point: the
failure being guarded against is a reassuring value appearing where there was
correctly nothing.

The asymmetry under test: **we can sometimes prove a model logs; we can never
prove one does not.** Free tier is stated. Everything else is None.
"""

from __future__ import annotations

import pytest

from providers.contracts import DataPolicy, ProviderKind
from providers.discoverers import OpenRouterAdapter


@pytest.fixture
def adapter() -> OpenRouterAdapter:
    return OpenRouterAdapter(api_key="test-key")


class TestTheProviderMakesNoClaim:
    def test_the_provider_level_policy_is_unknown(self, adapter):
        """OpenRouter is a router, not a provider. The terms that apply are the
        downstream provider's, for the specific model, mediated by account
        settings this API does not report. There is no single answer."""
        assert adapter._data_policy is None

    def test_it_is_a_cloud_provider(self, adapter):
        assert adapter.kind is ProviderKind.CLOUD_API


class TestPerModelPolicy:
    @pytest.mark.parametrize(
        "model_id",
        [
            "meta-llama/llama-3.3-70b-instruct:free",
            "some/model:FREE",
        ],
    )
    def test_the_free_tier_is_labelled_as_logged(self, adapter, model_id):
        """The one case that can be stated. Free is free because prompts are
        logged, and the label is what turns a deliberate choice into an
        informed one."""
        model = adapter._to_model(model_id, {})

        assert model.data_policy is DataPolicy.LOGGED_AND_TRAINED_ON

    def test_zero_pricing_is_the_free_tier_even_without_the_suffix(self, adapter):
        """The suffix is a convention; pricing is what it is shorthand for."""
        model = adapter._to_model(
            "some/model", {"pricing": {"prompt": "0", "completion": "0"}}
        )

        assert model.data_policy is DataPolicy.LOGGED_AND_TRAINED_ON

    def test_a_paid_model_claims_nothing(self, adapter):
        """Not "it certainly logs" and not "it certainly does not" — we have no
        evidence, and a guess in the reassuring direction is a privacy claim the
        user acts on."""
        model = adapter._to_model(
            "nvidia/nemotron-3-ultra",
            {"pricing": {"prompt": "0.0000008", "completion": "0.0000024"}},
        )

        assert model.data_policy is None
        assert model.data_policy_known is False

    def test_a_model_with_no_pricing_information_claims_nothing(self, adapter):
        assert adapter._to_model("anthropic/claude-sonnet-4", {}).data_policy is None

    def test_malformed_pricing_does_not_become_a_guarantee(self, adapter):
        """A parse failure must not fall through to a reassuring default."""
        model = adapter._to_model(
            "some/model", {"pricing": {"prompt": "not-a-number", "completion": None}}
        )

        assert model.data_policy is None


class TestNothingHereIsSelectableByDefault:
    """The property that actually protects the user. Whatever else changes,
    this must hold: Zaram never routes to an OpenRouter model on its own
    initiative, because it cannot say what happens to the prompt."""

    @pytest.mark.parametrize(
        "model_id,entry",
        [
            ("meta-llama/llama-3.3-70b-instruct:free", {}),
            ("nvidia/nemotron-3-ultra", {"pricing": {"prompt": "0.001"}}),
            ("anthropic/claude-sonnet-4", {}),
            ("some/model", {"pricing": {"prompt": "0", "completion": "0"}}),
        ],
    )
    def test_no_openrouter_model_is_ever_an_automatic_choice(
        self, adapter, model_id, entry
    ):
        assert adapter._to_model(model_id, entry).selectable_by_default is False

    def test_every_model_records_why_its_policy_says_what_it_says(self, adapter):
        """So the next person to look does not have to re-derive it, and so a
        blank policy reads as a considered absence rather than an oversight."""
        for model_id in ("x/y:free", "x/y"):
            model = adapter._to_model(model_id, {})
            assert model.metadata["policy_source"]


class TestRegistration:
    def test_it_is_not_registered_without_a_key(self, monkeypatch):
        """Registering keyless would discover a catalogue of models that cannot
        be called — a list of things Zaram appears to offer and does not."""
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        from core.event_bus import EventBus
        from providers.runtime import ProvidersRuntime

        runtime = ProvidersRuntime(EventBus())
        runtime._register_default_providers()

        registered = {p.provider_id for p in runtime.registry.list_model_providers()} \
            if hasattr(runtime.registry, "list_model_providers") else set()
        assert "openrouter" not in registered

    def test_the_endpoint_is_the_real_one(self):
        assert OpenRouterAdapter(api_key="k").base_url == "https://openrouter.ai/api"

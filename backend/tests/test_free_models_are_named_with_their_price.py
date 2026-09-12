"""Free models are identified, and always named beside what they cost instead.

Asked for on 12 September 2026: identify free models on OpenRouter and on the
other routers and free-tier providers, the way a coding assistant's picker
shows a "Free" tag. Two facts, kept apart on purpose:

* **`ModelInfo.is_free`** — money. Three-valued: an unknown price is not a free
  one, and a router's paid model must never read as free because a field
  defaulted.
* **`ProviderEntry.pricing`** — the tier at the level the provider sets it.
  ``PER_MODEL`` for a router (the listing decides), ``TRIAL`` for a grant
  behind a card (not free), ``UNKNOWN`` as the honest default (not ``PAID``).

And the rule that makes the feature safe rather than a trap: `CLAUDE.md` says
every free tier is paid for in data and *naming the deal is a primary feature
of the picker*. So a free model carries ``LOGGED_AND_TRAINED_ON`` and stays
unselectable by default — free is not a reason to route there on a user's
behalf — and the label says "free, prompts are logged" in one breath.
"""

from __future__ import annotations

from providers import catalogue
from providers.catalogue import Pricing
from providers.contracts import DataPolicy, ModelInfo
from providers.discoverers.openrouter import OpenRouterAdapter


def _model(model_id: str, entry: dict) -> ModelInfo:
    return OpenRouterAdapter(api_key="k")._to_model(model_id, entry)


class TestOpenRouterPerModel:
    def test_a_free_suffix_is_free_and_logged_and_not_a_default(self):
        m = _model("meta-llama/llama-3.3-70b-instruct:free", {"id": "x"})
        assert m.is_free is True
        assert m.data_policy is DataPolicy.LOGGED_AND_TRAINED_ON
        assert m.selectable_by_default is False

    def test_zero_pricing_without_the_suffix_is_free(self):
        m = _model("some/model", {"pricing": {"prompt": "0", "completion": "0"}})
        assert m.is_free is True

    def test_a_priced_model_is_not_free(self):
        m = _model("anthropic/claude-sonnet-4", {"pricing": {"prompt": "0.000003", "completion": "0.000015"}})
        assert m.is_free is False

    def test_no_pricing_in_the_listing_is_unknown_not_false(self):
        """A missing price is an absent fact. Saying "not free" would be a
        claim the listing did not make."""
        m = _model("some/model", {"id": "some/model"})
        assert m.is_free is None

    def test_the_wire_carries_null_for_unknown(self):
        m = _model("some/model", {"id": "some/model"})
        assert m.to_dict()["is_free"] is None
        assert ModelInfo.from_dict(m.to_dict()).is_free is None
        free = _model("x:free", {})
        assert ModelInfo.from_dict(free.to_dict()).is_free is True


class TestProviderTiers:
    def _entry(self, provider_id: str):
        entry = catalogue.get(provider_id)
        assert entry is not None, provider_id
        return entry

    def test_the_router_is_priced_per_model(self):
        e = self._entry("openrouter")
        assert e.pricing is Pricing.PER_MODEL
        assert e.has_free_tier is True

    def test_standing_free_tiers_are_named(self):
        for pid in ("groq", "nvidia_nim", "sambanova", "google_gemini", "mistral"):
            assert self._entry(pid).pricing is Pricing.FREE_TIER, pid
            assert self._entry(pid).has_free_tier is True, pid

    def test_a_grant_behind_a_card_is_a_trial_not_a_free_tier(self):
        for pid in ("cerebras", "together"):
            assert self._entry(pid).pricing is Pricing.TRIAL, pid
            assert self._entry(pid).has_free_tier is False, pid

    def test_paid_providers_are_paid(self):
        for pid in ("openai", "deepseek", "xai"):
            assert self._entry(pid).pricing is Pricing.PAID, pid

    def test_the_default_is_unknown_not_paid(self):
        """A provider nobody has graded is not thereby a paid one."""
        e = catalogue.ProviderEntry(
            id="x", display_name="x", kind=catalogue.ProviderKind.CLOUD_API,
            base_url="https://x/v1", chat_endpoint="https://x/v1/chat/completions",
            compatibility=catalogue.Compatibility.OPENAI, auth=catalogue.AuthStyle.BEARER,
            key_url="https://x", support=catalogue.Support.AVAILABLE,
        )
        assert e.pricing is Pricing.UNKNOWN
        assert e.has_free_tier is False

    def test_the_wire_carries_both_fields(self):
        d = self._entry("groq").to_dict()
        assert d["pricing"] == "free_tier"
        assert d["has_free_tier"] is True

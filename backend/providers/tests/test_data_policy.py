"""What happens to a prompt, and what happens when nobody said.

The interesting cases here are the absent ones. A data policy that is merely
*present* on models somebody remembered to annotate is worth very little — the
whole point of the field is the model nobody thought about, which is exactly
the model most likely to be a cloud endpoint someone added in a hurry.

So most of these assert on the default rather than on the happy path.
"""

from __future__ import annotations

from providers.contracts import DataPolicy, ModelInfo, ProviderKind
from providers.discoverers.openai_compat import (
    OPENAI_BASE_URL,
    LMStudioAdapter,
    OpenAICompatibleAdapter,
    _policy_for,
)


class TestUnknownIsNotAGuarantee:
    def test_a_model_nobody_annotated_has_no_policy(self):
        """The default must not be a promise.

        ``NEVER_LEAVES_DEVICE`` is the tempting default and the dangerous one:
        every adapter that forgot the field would ship a privacy guarantee
        nobody verified. This is the ``vram_bytes = 0`` bug with worse
        consequences — there, a false zero produced a bad recommendation; here,
        a false guarantee produces a leaked document.
        """
        model = ModelInfo(id="m", display_name="m", provider="p")

        assert model.data_policy is None
        assert model.data_policy_known is False

    def test_unknown_policy_is_never_selectable_by_default(self):
        """Not knowing is not a quiet yes."""
        model = ModelInfo(id="m", display_name="m", provider="p")

        assert model.selectable_by_default is False

    def test_logged_and_trained_on_is_never_selectable_by_default(self):
        """It may only ever be chosen deliberately, by someone who saw the label."""
        model = ModelInfo(
            id="m",
            display_name="m",
            provider="p",
            data_policy=DataPolicy.LOGGED_AND_TRAINED_ON,
        )

        assert model.data_policy_known is True
        assert model.selectable_by_default is False

    def test_the_two_acceptable_policies_are_selectable(self):
        for policy in (DataPolicy.NEVER_LEAVES_DEVICE, DataPolicy.YOUR_KEY_NO_TRAINING):
            model = ModelInfo(id="m", display_name="m", provider="p", data_policy=policy)
            assert model.selectable_by_default is True, policy

    def test_an_unparseable_policy_becomes_unknown_not_a_default(self):
        """Every other from_value in contracts.py falls back to a member.

        This one must not: an unrecognised policy string is an unanswered
        question, and answering it with a guarantee is the failure mode.
        """
        assert DataPolicy.from_value("never_leaves_device") is DataPolicy.NEVER_LEAVES_DEVICE
        assert DataPolicy.from_value("something_new") is None
        assert DataPolicy.from_value("") is None
        assert DataPolicy.from_value(None) is None

    def test_round_trip_preserves_unknown_as_unknown(self):
        """Serialising must not launder an absent policy into a present one."""
        model = ModelInfo(id="m", display_name="m", provider="p")

        payload = model.to_dict()
        assert payload["data_policy"] is None
        assert payload["data_policy_known"] is False
        assert payload["selectable_by_default"] is False

        assert ModelInfo.from_dict(payload).data_policy is None

    def test_round_trip_preserves_a_real_policy(self):
        model = ModelInfo(
            id="m",
            display_name="m",
            provider="p",
            data_policy=DataPolicy.YOUR_KEY_NO_TRAINING,
        )

        restored = ModelInfo.from_dict(model.to_dict())
        assert restored.data_policy is DataPolicy.YOUR_KEY_NO_TRAINING


class TestPolicyFollowsTheDestination:
    def test_loopback_is_never_leaves_device(self):
        for url in (
            "http://127.0.0.1:1234",
            "http://localhost:1234",
            "http://[::1]:1234",
        ):
            assert _policy_for(url) is DataPolicy.NEVER_LEAVES_DEVICE, url

    def test_a_remote_host_is_not_guessed(self):
        """A hostname does not tell you a provider's training terms."""
        for url in (OPENAI_BASE_URL, "https://api.example.com", "http://192.168.1.50:1234"):
            assert _policy_for(url) is None, url

    def test_lm_studio_declares_never_leaves_device(self):
        adapter = LMStudioAdapter()
        model = adapter._to_model("some-local-model", {"owned_by": "local"})

        assert model.data_policy is DataPolicy.NEVER_LEAVES_DEVICE
        assert model.selectable_by_default is True

    def test_the_same_adapter_pointed_at_a_cloud_url_declares_nothing(self):
        """One class, two situations. The URL decides, not the caller's memory."""
        adapter = OpenAICompatibleAdapter(
            provider_id="openai",
            base_url=OPENAI_BASE_URL,
            kind=ProviderKind.CLOUD_API,
            api_key="sk-test",
        )
        model = adapter._to_model("gpt-4o", {"owned_by": "openai"})

        assert model.data_policy is None
        assert model.selectable_by_default is False

    def test_an_explicit_policy_wins_over_inference(self):
        """Whoever registers a cloud provider states its terms."""
        adapter = OpenAICompatibleAdapter(
            provider_id="openai",
            base_url=OPENAI_BASE_URL,
            kind=ProviderKind.CLOUD_API,
            api_key="sk-test",
            data_policy=DataPolicy.YOUR_KEY_NO_TRAINING,
        )
        model = adapter._to_model("gpt-4o", {"owned_by": "openai"})

        assert model.data_policy is DataPolicy.YOUR_KEY_NO_TRAINING
        assert model.selectable_by_default is True

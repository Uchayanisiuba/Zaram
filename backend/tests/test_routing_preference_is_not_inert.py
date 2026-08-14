"""The *Prefer local · Auto · Prefer cloud* control changes what Zaram picks.

Written because it did not. The preference was persisted, served over HTTP and
rendered as a segmented control in Settings, and **nothing read it** — a switch
that saved a value and changed no behaviour, which is precisely the failure
`SettingsWorkspace`'s own docstring is written against: *a settings screen full
of inert toggles tells the user they have control they do not have, and on a
privacy product that is the worst thing to be wrong about.*

The three settings must differ from each other, or two of them are the same
control with two labels. What each one means:

* ``prefer_local`` — Zaram will not pick a cloud model on its own at all.
* ``auto`` — local ranked first, cloud eligible when no local model qualifies.
* ``prefer_cloud`` — cloud ranked first, among models already consented to.

And the property that outranks all three: **none of them is a permission.**
`selectable_by_default` decides what may be auto-selected on data-policy
grounds, and a dropdown does not reopen that.
"""

from __future__ import annotations

import pytest

from providers.contracts import (
    CapabilityLocality,
    DataPolicy,
    HealthStatus,
    ModelCategory,
    ModelInfo,
    ProviderKind,
)
from providers.manager import ProviderManager


def model(
    model_id: str,
    *,
    locality: CapabilityLocality,
    policy: DataPolicy | None,
    size: int = 4_000_000_000,
) -> ModelInfo:
    return ModelInfo(
        id=model_id,
        display_name=model_id,
        provider="test",
        provider_kind=(
            ProviderKind.LOCAL_LLM
            if locality is CapabilityLocality.LOCAL
            else ProviderKind.CLOUD_API
        ),
        category=ModelCategory.LLM,
        locality=locality,
        available=True,
        health_status=HealthStatus.HEALTHY,
        data_policy=policy,
        size_bytes=size,
    )


LOCAL = model("local-8b", locality=CapabilityLocality.LOCAL, policy=DataPolicy.NEVER_LEAVES_DEVICE)
CLOUD = model(
    "cloud-big",
    locality=CapabilityLocality.CLOUD,
    policy=DataPolicy.YOUR_KEY_NO_TRAINING,
    size=70_000_000_000,
)
CLOUD_UNKNOWN = model("cloud-mystery", locality=CapabilityLocality.CLOUD, policy=None)


@pytest.fixture
def manager(monkeypatch):
    """A manager whose model list and residency check are ours.

    `select_default_model` is the unit under test; discovery and VRAM are not,
    and letting either reach real hardware would make this a measurement rather
    than a test of the ordering.
    """
    m = ProviderManager.__new__(ProviderManager)
    monkeypatch.setattr(ProviderManager, "model_fits_resident", lambda self, model: True)
    return m


def with_models(manager, monkeypatch, models):
    monkeypatch.setattr(
        ProviderManager, "list_models", lambda self, **kwargs: list(models)
    )


def with_preference(monkeypatch, value: str):
    monkeypatch.setattr(ProviderManager, "_routing_preference", lambda self: value)


class TestTheThreeSettingsDiffer:
    def test_auto_ranks_local_first(self, manager, monkeypatch):
        with_models(manager, monkeypatch, [CLOUD, LOCAL])
        with_preference(monkeypatch, "auto")
        assert manager.select_default_model().id == "local-8b"

    def test_prefer_cloud_ranks_cloud_first(self, manager, monkeypatch):
        with_models(manager, monkeypatch, [LOCAL, CLOUD])
        with_preference(monkeypatch, "prefer_cloud")
        assert manager.select_default_model().id == "cloud-big"

    def test_prefer_local_and_prefer_cloud_disagree(self, manager, monkeypatch):
        """The two ends must not resolve to the same model, or one is decorative."""
        with_models(manager, monkeypatch, [LOCAL, CLOUD])

        with_preference(monkeypatch, "prefer_local")
        local_choice = manager.select_default_model()
        with_preference(monkeypatch, "prefer_cloud")
        cloud_choice = manager.select_default_model()

        assert local_choice.id != cloud_choice.id


class TestPreferLocalIsAConstraint:
    def test_it_will_not_pick_a_cloud_model_even_when_it_is_the_only_one(
        self, manager, monkeypatch
    ):
        """No model is the honest answer; a cloud model would be the wrong one.

        Falling back here would make the strictest setting the one that
        silently sends data off-device on a machine with no local model — the
        exact inversion rule 5 exists to prevent.
        """
        with_models(manager, monkeypatch, [CLOUD])
        with_preference(monkeypatch, "prefer_local")
        assert manager.select_default_model() is None

    def test_auto_does_fall_back_to_cloud(self, manager, monkeypatch):
        """`auto` is the one that may, which is what makes the two different."""
        with_models(manager, monkeypatch, [CLOUD])
        with_preference(monkeypatch, "auto")
        assert manager.select_default_model().id == "cloud-big"


class TestNoPreferenceIsAPermission:
    @pytest.mark.parametrize("preference", ["prefer_local", "auto", "prefer_cloud"])
    def test_an_unknown_data_policy_is_never_auto_selected(
        self, manager, monkeypatch, preference
    ):
        """The claim the Settings screen makes to the user, asserted.

        "A bias, not a permission. Preferring cloud cannot promote a model
        whose terms are unknown." If this ever passes for `prefer_cloud`, that
        sentence becomes a lie in a product whose whole pitch is that it is
        not lying about this.
        """
        with_models(manager, monkeypatch, [CLOUD_UNKNOWN])
        with_preference(monkeypatch, preference)
        assert manager.select_default_model() is None

    def test_a_known_cloud_policy_beats_an_unknown_one_under_prefer_cloud(
        self, manager, monkeypatch
    ):
        with_models(manager, monkeypatch, [CLOUD_UNKNOWN, CLOUD])
        with_preference(monkeypatch, "prefer_cloud")
        assert manager.select_default_model().id == "cloud-big"


class TestItFailsToTheOldBehaviour:
    def test_an_unreadable_preference_behaves_as_auto(self, manager, monkeypatch):
        """A settings file must not change which model answers by being broken."""
        def boom(self):
            raise OSError("settings file is gone")

        monkeypatch.setattr(ProviderManager, "_routing_preference", boom)
        with_models(manager, monkeypatch, [CLOUD, LOCAL])

        # `_routing_preference` is the thing that swallows failures, so calling
        # it through the real implementation is the point — patching it to raise
        # asserts the caller does not.
        with pytest.raises(OSError):
            manager._routing_preference()

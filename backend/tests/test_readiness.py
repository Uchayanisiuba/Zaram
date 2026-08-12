"""First run on a machine with nothing on it.

The test that matters most is `test_it_never_leaves_the_user_without_an_option`.
A fresh install that opens, renders, and answers nothing reads as broken rather
than as unconfigured, and someone who concludes that does not open it again.
"""

from __future__ import annotations

import pytest

from core.readiness import (
    Offer,
    OfferKind,
    Readiness,
    diagnose,
)


class TestTheThreeStates:
    def test_a_local_model_is_ready(self):
        result = diagnose(engine_installed=True, chat_models=["qwen2.5:7b"])
        assert result.readiness is Readiness.READY
        assert result.can_chat is True
        assert result.offers == ()

    def test_a_cloud_key_alone_is_ready(self):
        result = diagnose(engine_installed=False, cloud_key_configured=True)
        assert result.readiness is Readiness.READY
        assert result.can_chat is True

    def test_an_engine_with_no_model_is_named_as_such(self):
        result = diagnose(engine_installed=True, chat_models=[])
        assert result.readiness is Readiness.ENGINE_WITHOUT_MODEL
        assert result.can_chat is False

    def test_nothing_at_all_is_named_as_such(self):
        result = diagnose(engine_installed=False)
        assert result.readiness is Readiness.NO_ENGINE
        assert result.can_chat is False


class TestOffers:
    def test_it_never_leaves_the_user_without_an_option(self):
        """Every unready state offers a way forward. A dead composer with no
        explanation is the one outcome that must not exist."""
        for state in (
            diagnose(engine_installed=False),
            diagnose(engine_installed=True, chat_models=[]),
        ):
            assert state.offers, state.readiness
            assert state.summary
            assert all(offer.label and offer.detail for offer in state.offers)

    def test_every_download_states_its_size_before_it_happens(self):
        """Naming a fix without naming its price is not a choice someone on a
        metered connection can make."""
        for state in (
            diagnose(engine_installed=False),
            diagnose(engine_installed=True, chat_models=[]),
        ):
            for offer in state.offers:
                if offer.kind in (OfferKind.INSTALL_ENGINE, OfferKind.PULL_MODEL):
                    assert offer.download_bytes is not None
                    assert offer.download_label

    def test_an_offer_that_downloads_nothing_says_nothing_about_size(self):
        """None rather than 0 — zero is a figure and would read as free."""
        offers = {o.kind: o for o in diagnose(engine_installed=False).offers}
        assert offers[OfferKind.EXPLORE].download_bytes is None
        assert offers[OfferKind.EXPLORE].download_label == ""

    def test_installing_the_engine_quotes_the_model_too(self):
        """One decision, one number. Quoting the engine alone lands the user in
        the next unready state and asks them to agree to a second download."""
        offers = {o.kind: o for o in diagnose(engine_installed=False).offers}
        engine = offers[OfferKind.INSTALL_ENGINE]
        model = diagnose(engine_installed=True, chat_models=[]).offers[0]

        assert engine.download_bytes > model.download_bytes

    def test_the_smallest_model_is_what_is_offered_first(self):
        """A user asked to pull 7 GB before their first answer closes the app."""
        model = diagnose(engine_installed=True, chat_models=[]).offers[0]
        assert model.download_bytes < 600 * 1024 * 1024

    def test_cloud_and_explore_are_always_alternatives(self):
        for state in (
            diagnose(engine_installed=False),
            diagnose(engine_installed=True, chat_models=[]),
        ):
            kinds = {offer.kind for offer in state.offers}
            assert OfferKind.USE_CLOUD_KEY in kinds
            assert OfferKind.EXPLORE in kinds


class TestItReadsAsUnconfiguredNotBroken:
    def test_it_says_what_still_works(self):
        """The difference between "unconfigured" and "broken" is whether
        anything tells the user the rest of the product is fine."""
        result = diagnose(engine_installed=False)
        assert result.still_works
        assert any("Knowledge" in line for line in result.still_works)

    def test_a_ready_install_does_not_lecture(self):
        result = diagnose(engine_installed=True, chat_models=["qwen2.5:7b"])
        assert result.still_works == ()

    def test_no_model_filename_reaches_the_user_facing_text(self):
        """The target user is not technical: no model filenames, no
        quantisation settings in the primary path."""
        result = diagnose(engine_installed=True, chat_models=[])
        spoken = result.summary + " ".join(
            offer.label + offer.detail for offer in result.offers
        )
        for leak in ("qwen", "gguf", "q4_", ":0.5b", "bge-m3"):
            assert leak not in spoken.lower()


class TestSizeLabels:
    @pytest.mark.parametrize(
        "size,expected",
        [
            (397 * 1024 * 1024, "397 MB"),
            (2 * 1024 * 1024 * 1024, "2.0 GB"),
        ],
    )
    def test_sizes_read_the_way_a_person_would_say_them(self, size, expected):
        assert Offer(OfferKind.PULL_MODEL, "x", "y", size).download_label == expected


class TestSerialisation:
    def test_a_diagnosis_round_trips_to_plain_data(self):
        payload = diagnose(engine_installed=False).to_dict()

        assert payload["readiness"] == "no_engine"
        assert payload["can_chat"] is False
        assert payload["still_works"]
        assert all(offer["label"] for offer in payload["offers"])
        assert any(offer["download_label"] for offer in payload["offers"])


def test_nothing_in_this_module_touches_the_network():
    """Rule 7g: no network call before the user has consented to one — which
    includes the check for what is available. Diagnosis reports; the caller
    acts, after a person has chosen."""
    import core.readiness as module

    source = open(module.__file__, encoding="utf-8").read()
    for forbidden in ("requests.", "httpx.", "urlopen(", "aiohttp", "socket."):
        assert forbidden not in source, forbidden

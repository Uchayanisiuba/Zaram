"""First run on a machine with nothing on it.

The test that matters most is `test_it_never_leaves_the_user_without_an_option`.
A fresh install that opens, renders, and answers nothing reads as broken rather
than as unconfigured, and someone who concludes that does not open it again.
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from core import readiness
from core.readiness import (
    Offer,
    OfferKind,
    Readiness,
    diagnose,
)
from providers.model_manifest import GB, recommend_for


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


class TestTheModelIsMatchedToTheMachine:
    """The offer used to be one name and one number for every machine.

    It quoted 397 MB to a 24 GB workstation and to a 4 GB laptop, which is a
    recommendation that is wrong in both directions at once. The manifest
    answers *"what suits a machine with this much room"*; these assert that the
    answer reaches the screen, and that every way the manifest can fail still
    leaves the user with something to choose.
    """

    def _pull(self, budget):
        offers = {
            o.kind: o
            for o in diagnose(
                engine_installed=True, chat_models=[], budget_bytes=budget
            ).offers
        }
        return offers[OfferKind.PULL_MODEL]

    def test_a_bigger_machine_is_offered_a_bigger_model(self):
        """The whole point of the wiring. Same call, two budgets, two models."""
        small = self._pull(2 * GB)
        large = self._pull(12 * GB)

        assert small.model_name and large.model_name
        assert small.model_name != large.model_name
        assert large.download_bytes > small.download_bytes

    def test_an_unmeasured_machine_gets_the_smallest_tier(self):
        """`None` is a real answer — Apple and DirectML report no capacity, and
        a discovery that has not run reports none either. A thin model that
        certainly runs beats a fat one that might not."""
        unmeasured = self._pull(None)
        smallest = self._pull(1 * GB)

        assert unmeasured.model_name == smallest.model_name
        assert unmeasured.download_bytes == smallest.download_bytes

    def test_a_budget_of_zero_is_not_read_as_unmeasured(self):
        """A machine measured at zero is not the same claim as an unmeasurable
        one, and this is the boundary where the two would be confused."""
        assert self._pull(0).download_bytes == self._pull(None).download_bytes

    def test_the_name_reaches_the_payload_without_reaching_the_prose(self):
        """The executor needs the model's name; the user must not read it.
        Both at once is why it is a field rather than a word in the detail."""
        offer = self._pull(12 * GB)

        assert offer.model_name
        assert offer.model_name not in (offer.label + offer.detail)
        assert offer.to_dict()["model_name"] == offer.model_name

    def test_the_manifest_date_is_visible(self):
        """A recommendation is only as current as the list behind it, and
        `CLAUDE.md` asks for the date to be shown rather than implied."""
        expected = recommend_for(12 * GB)[0].generated
        offer = self._pull(12 * GB)

        assert expected
        assert offer.recommended_on == expected
        assert offer.to_dict()["recommended_on"] == expected

    def test_the_engine_offer_quotes_the_same_model_the_pull_would(self):
        """Two screens, one price. If the engine offer quoted a different model
        the download would change size between them for no visible reason."""
        budget = 12 * GB
        pull = self._pull(budget)
        engine = {
            o.kind: o
            for o in diagnose(engine_installed=False, budget_bytes=budget).offers
        }[OfferKind.INSTALL_ENGINE]

        assert engine.model_name == pull.model_name
        assert engine.download_bytes > pull.download_bytes

    def test_no_model_filename_reaches_the_prose_on_any_machine(self):
        """The earlier version of this test only ever exercised one tier,
        because there was only one model. Every tier's `why` is now user-facing
        text and any one of them could name a file."""
        for budget in (None, 2 * GB, 6 * GB, 12 * GB, 40 * GB):
            state = diagnose(
                engine_installed=True, chat_models=[], budget_bytes=budget
            )
            spoken = state.summary + " ".join(
                offer.label + offer.detail for offer in state.offers
            )
            for leak in ("qwen", "llama", "gguf", "q4_", ":0.5b", "bge-m3"):
                assert leak not in spoken.lower(), (budget, leak)


class TestTheManifestFailingCostsARecommendationNotTheScreen:
    """Never fail closed. A first run that suggests an older model than it
    might have is a smaller problem than a first run that offers nothing."""

    def test_an_empty_manifest_falls_back_to_the_constant(self, monkeypatch):
        monkeypatch.setattr(readiness, "recommend_for", lambda budget: [])
        offer = diagnose(engine_installed=True, chat_models=[]).offers[0]

        assert offer.kind is OfferKind.PULL_MODEL
        assert offer.model_name == readiness.SMALLEST_CHAT_MODEL
        assert offer.download_bytes == readiness.SMALLEST_CHAT_BYTES
        assert offer.detail

    def test_a_manifest_that_raises_still_produces_an_offer(self, monkeypatch):
        """`recommend_for` is written not to raise, and a malformed tier can
        still make it — `float()` on a word. A guard that trusts a promise is
        not a guard."""

        def explode(budget):
            raise ValueError("max_budget_gb: 'twelve'")

        monkeypatch.setattr(readiness, "recommend_for", explode)
        state = diagnose(engine_installed=True, chat_models=[])

        assert state.offers
        assert state.offers[0].download_bytes == readiness.SMALLEST_CHAT_BYTES

    def test_the_fallback_claims_no_date(self, monkeypatch):
        """A fallback has no list behind it. Stamping today's date on it would
        put a figure on the screen that nothing generated."""
        monkeypatch.setattr(readiness, "recommend_for", lambda budget: [])
        offer = diagnose(engine_installed=True, chat_models=[]).offers[0]

        assert offer.recommended_on is None
        assert offer.to_dict()["recommended_on"] is None


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


def test_readiness_and_health_are_separate_routes():
    """They answer different questions — "is the process alive" and "can the
    product do its job" — and the desktop runtime health check reads the first.

    Guarding it because adding `/readiness` above `/health` stacked both
    decorators onto one function, which silently made `/health` return the
    readiness payload. Nothing would have failed until the desktop health check
    started misreading a running backend.
    """
    from main import app

    routes = {
        getattr(route, "path", None): getattr(route, "endpoint", None)
        for route in app.routes
    }

    assert "/readiness" in routes
    assert "/health" in routes
    assert routes["/readiness"] is not routes["/health"]
    assert routes["/health"].__name__ == "health"
    assert routes["/readiness"].__name__ == "readiness"


class TestTheRouteMeasuresTheMachine:
    """The half that is not `diagnose`, and the half this repository keeps
    getting wrong: a module can be complete, tested and reached by nothing.

    `diagnose` takes a budget; these assert something actually measures one and
    hands it over, and that a machine it cannot measure still gets an offer.
    """

    @staticmethod
    def _kernel_with_budget(budget):
        """A kernel shaped like the real one at the two attributes read."""
        manager = SimpleNamespace(resident_budget_bytes=lambda: budget)
        return SimpleNamespace(providers_runtime=SimpleNamespace(manager=manager))

    @pytest.fixture(autouse=True)
    def _an_engine_holding_only_an_embedder(self, monkeypatch):
        """Ollama up, with nothing on it that can hold a conversation — the
        state whose offer names a model. Stubbed at the adapter because the
        route probes through it rather than opening a socket of its own."""
        from providers.discoverers.ollama import OllamaAdapter

        async def only_an_embedder(self, timeout=1.5):
            return [SimpleNamespace(id="bge-m3", display_name="bge-m3")]

        monkeypatch.setattr(OllamaAdapter, "discover_models", only_an_embedder)
        monkeypatch.delenv("ZARAM_OPENAI_KEY", raising=False)

    async def _offer(self, monkeypatch, budget):
        import main

        monkeypatch.setattr(main, "kernel", self._kernel_with_budget(budget))
        payload = await main.readiness()
        assert payload["readiness"] == "engine_without_model"
        return next(o for o in payload["offers"] if o["kind"] == "pull_model")

    @pytest.mark.asyncio
    async def test_the_budget_reaches_the_offer(self, monkeypatch):
        small = await self._offer(monkeypatch, 2 * GB)
        large = await self._offer(monkeypatch, 12 * GB)

        assert small["model_name"] != large["model_name"]
        assert large["download_bytes"] > small["download_bytes"]
        assert large["recommended_on"]

    @pytest.mark.asyncio
    async def test_an_unmeasurable_machine_still_gets_an_offer(self, monkeypatch):
        """Metal, DirectML, or a discovery that has not run. `None` must reach
        `diagnose` as "unmeasured" rather than being turned into a number."""
        offer = await self._offer(monkeypatch, None)

        assert offer["model_name"]
        assert offer["download_bytes"]

    @pytest.mark.asyncio
    async def test_a_provider_layer_that_is_not_there_yet_costs_nothing(
        self, monkeypatch
    ):
        """The route runs during early boot and after a failed provider init.
        Neither may turn the first-run screen into a 500."""
        import main

        monkeypatch.setattr(main, "kernel", SimpleNamespace())
        payload = await main.readiness()

        assert payload["offers"]

    @pytest.mark.asyncio
    async def test_a_manager_that_raises_costs_nothing(self, monkeypatch):
        import main

        def explode():
            raise RuntimeError("no hardware profiler")

        manager = SimpleNamespace(resident_budget_bytes=explode)
        monkeypatch.setattr(
            main,
            "kernel",
            SimpleNamespace(providers_runtime=SimpleNamespace(manager=manager)),
        )
        payload = await main.readiness()

        assert payload["offers"]


def test_nothing_in_this_module_touches_the_network():
    """Rule 7g: no network call before the user has consented to one — which
    includes the check for what is available. Diagnosis reports; the caller
    acts, after a person has chosen."""
    import core.readiness as module

    source = open(module.__file__, encoding="utf-8").read()
    for forbidden in ("requests.", "httpx.", "urlopen(", "aiohttp", "socket."):
        assert forbidden not in source, forbidden

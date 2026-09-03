"""The provider catalogue, checked against the code that would call it.

A manifest of URLs is the easiest thing in a repo to get wrong and the hardest
to notice getting wrong: it looks like documentation, nothing imports it at
boot, and the first symptom is a stranger's first cloud message failing with a
404 they cannot interpret.

So the tests that matter here are not "does the list have twelve rows". They
are the two that can actually be false:

* **An entry marked available is reachable** — its base URL, through the *real*
  engine and the *real* discoverer, arrives at the URL the entry itself says
  the provider listens on. Not a re-implementation of the normalisation; the
  same function the product calls.
* **The grade costs something** — the entry that fails that check is present
  and marked unavailable, so "available" is a claim a machine disagreed with
  for the ones that do not have it, rather than a label everybody gets.

The rest guard rule 7g (nothing here touches the network), the no-secrets
boundary, and the property most easily lost later: that this is a convenience
over configuration that already works, never a gate in front of it.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date
from urllib.parse import urlparse

import pytest

from providers.catalogue import (
    GENERATED,
    GENERIC_ENDPOINT_ENV,
    GENERIC_KEY_ENV,
    PROVIDERS,
    AuthStyle,
    Compatibility,
    ProviderEntry,
    Support,
    get,
    list_providers,
    to_payload,
)
from providers.discoverers.openai_compat import (
    LM_STUDIO_BASE_URL,
    OpenAICompatibleAdapter,
)
from runtimes.models.engines.openai_compatible_engine import (
    OPENROUTER_BASE_URL,
    OpenAICompatibleEngine,
    from_environment,
)

#: A value that is obviously not a real key. Nothing sends it — the engine is
#: constructed and its URL inspected, never used — but it should still read as
#: a fixture to anyone who greps for it.
FAKE_KEY = "not-a-real-key"


def _engine_endpoint(base_url: str) -> str:
    """Where the shipped engine would send a chat request for this root."""
    return OpenAICompatibleEngine(
        base_url=base_url, api_key=FAKE_KEY, default_model=""
    ).endpoint


def _discovery_url(base_url: str) -> str:
    """Where the shipped discoverer would ask for the model list."""
    return f"{OpenAICompatibleAdapter(base_url=base_url).base_url}/v1/models"


def _reachable(entry: ProviderEntry) -> bool:
    """Whether Zaram's own normalisation lands on the provider's real endpoint.

    This is the whole grading criterion for an OpenAI-compatible service, and
    it is deliberately computed rather than stored: a stored answer would drift
    away from the code the first time the normalisation changed, which is the
    change most likely to break the catalogue.
    """
    if entry.compatibility is not Compatibility.OPENAI:
        return False
    return _engine_endpoint(entry.base_url) == entry.chat_endpoint


class TestTheGradeIsEarned:
    def test_every_available_entry_is_reached_by_the_real_engine(self):
        """The claim "Zaram can call this" is checked against the caller.

        Deriving the endpoint here from the entry's own base URL would only
        prove the helper agrees with itself. `_engine_endpoint` builds the
        shipped `OpenAICompatibleEngine`, so this fails if `_normalise` ever
        changes shape under an entry."""
        for entry in list_providers(available_only=True):
            assert _reachable(entry), f"{entry.id}: {_engine_endpoint(entry.base_url)}"

    def test_every_available_entry_is_also_discoverable(self):
        """Chat and discovery must agree about where the provider lives.

        They disagreed once already: `ZARAM_OPENAI_ENDPOINT` ending in `/v1`
        gave a working chat and a discovery that asked for `/v1/v1/models`, so
        no cloud model was known and routing sent every message local without
        saying why. A catalogue that only checked the chat URL would let an
        entry reintroduce exactly that."""
        for entry in list_providers(available_only=True):
            expected = entry.chat_endpoint.replace("/chat/completions", "/models")
            assert _discovery_url(entry.base_url) == expected, entry.id

    def test_an_unreachable_entry_is_never_marked_available(self):
        """The converse, and the reason the label means anything."""
        for entry in PROVIDERS:
            if not _reachable(entry):
                assert entry.support is Support.UNAVAILABLE, entry.id

    def test_the_catalogue_contains_something_of_both_kinds(self):
        """Guards the two ways this suite could pass while asserting nothing:
        a catalogue with no available entries, or one where nothing was ever
        graded down."""
        assert list_providers(available_only=True)
        assert [e for e in PROVIDERS if not e.available]

    def test_gemini_is_the_worked_example_and_it_is_marked_down(self):
        """Named explicitly because it is the case that would otherwise ship.

        Gemini speaks the right format, so a reasonable person adds it as
        available. Its root ends in `/openai` with no `/v1` beneath it, and the
        engine appends `/v1` to anything that lacks one — producing a URL
        Google does not serve. The general rule above catches it; this states
        the failure so the next person does not have to rediscover it."""
        gemini = get("google_gemini")
        assert gemini is not None
        assert gemini.compatibility is Compatibility.OPENAI
        assert gemini.support is Support.UNAVAILABLE
        assert _engine_endpoint(gemini.base_url) != gemini.chat_endpoint
        assert _engine_endpoint(gemini.base_url).endswith("/openai/v1/chat/completions")

    def test_anthropic_is_native_and_not_offered(self):
        """Claude is not an OpenAI-compatible endpoint with a different host.
        It is a different request shape behind a different auth header, and
        nothing in this repo speaks it."""
        anthropic = get("anthropic")
        assert anthropic is not None
        assert anthropic.compatibility is Compatibility.NATIVE
        assert anthropic.auth is AuthStyle.X_API_KEY
        assert anthropic.support is Support.UNAVAILABLE
        assert not anthropic.chat_endpoint.endswith("/chat/completions")

    def test_unconfirmed_and_native_providers_are_never_available(self):
        for entry in PROVIDERS:
            if entry.compatibility in (Compatibility.NATIVE, Compatibility.UNVERIFIED):
                assert entry.support is Support.UNAVAILABLE, entry.id


class TestWhatTheUserIsTold:
    def test_nothing_greyed_out_is_greyed_out_silently(self):
        """`CLAUDE.md`: disabled capabilities are visible, not silent. An
        unavailable row with no reason is the same as a missing row, except it
        also looks broken."""
        for entry in PROVIDERS:
            if not entry.available:
                assert entry.note.strip(), entry.id

    def test_every_entry_that_needs_a_key_says_where_to_get_one(self):
        """A server that wants no key needs no signup link, and one local entry
        must not have one.

        The port-1234 entry is served by LM Studio, TabbyAPI, llama.cpp and
        others, and nothing in the `/v1/models` contract says which. A link to
        any one product page is an instruction to install the wrong thing —
        which is what happened: the picker named LM Studio at a maintainer
        running TabbyAPI, and that one word turned a diagnosis into a long
        argument about software that was never on the machine.
        """
        for entry in PROVIDERS:
            assert entry.id and entry.display_name and entry.base_url
            assert entry.chat_endpoint
            if entry.auth is not AuthStyle.NONE:
                assert entry.key_url.startswith("https://"), entry.id
            elif entry.key_url:
                assert entry.key_url.startswith("https://"), entry.id

    def test_ids_are_unique(self):
        ids = [entry.id for entry in PROVIDERS]
        assert len(ids) == len(set(ids))

    def test_no_key_is_ever_sent_in_the_clear(self):
        """Plain HTTP is allowed only where the request cannot leave the
        machine, and a loopback entry must not want a key either."""
        for entry in PROVIDERS:
            host = (urlparse(entry.base_url).hostname or "").lower()
            loopback = host in {"127.0.0.1", "localhost", "::1"}
            if not loopback:
                assert entry.base_url.startswith("https://"), entry.id
            else:
                assert entry.auth is AuthStyle.NONE, entry.id

    def test_the_manifest_says_when_it_was_written_down(self):
        """A dated manifest, with the date visible — the same handling the
        model recommendations get, for the same reason: these are third-party
        facts that go stale on someone else's schedule and cannot be refreshed
        without a network call the user has not consented to."""
        assert date.fromisoformat(GENERATED)
        assert to_payload()["generated"] == GENERATED

    def test_the_payload_carries_every_entry_and_its_grade(self):
        payload = to_payload()
        assert len(payload["providers"]) == len(PROVIDERS)
        for row in payload["providers"]:
            assert row["support"] in ("available", "unavailable")
            assert row["available"] is (row["support"] == "available")
            # The wire format is stated as a plain boolean too, because that is
            # the question a picker asks, but it is derived rather than a
            # second field that could disagree.
            assert row["openai_compatible"] is (row["compatibility"] == "openai")


class TestItNamesTheVariablesTheProductActuallyReads:
    """The catalogue exists to stop people hand-setting environment variables,
    which means it has to name the same ones the engine reads. Checked by
    building the real engine from a real environment rather than by comparing
    two strings, because the strings matching is not the property that matters.
    """

    @pytest.mark.parametrize(
        "entry",
        [e for e in list_providers(available_only=True) if e.endpoint_env],
        ids=lambda e: e.id,
    )
    def test_configuring_an_entry_produces_an_engine_pointed_at_it(
        self, entry, monkeypatch
    ):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setenv(entry.endpoint_env, entry.base_url)
        monkeypatch.setenv(entry.key_env, FAKE_KEY)

        engine = from_environment()

        assert engine is not None
        assert engine.endpoint == entry.chat_endpoint

    def test_the_generic_variables_are_the_ones_the_engine_reads(self, monkeypatch):
        """Named separately because a typo in either constant would make every
        parametrised case above silently skip its own point."""
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setenv(GENERIC_ENDPOINT_ENV, "https://example.invalid/v1")
        monkeypatch.setenv(GENERIC_KEY_ENV, FAKE_KEY)

        engine = from_environment()

        assert engine is not None
        assert engine.endpoint == "https://example.invalid/v1/chat/completions"

    def test_openrouter_agrees_with_both_places_that_already_know_its_address(self):
        """Three copies of one URL now exist: the engine's constant, the
        adapter's, and this entry. They must resolve to the same service, and
        the two spellings differ — the adapter holds the root without `/v1`
        because it re-adds it per path."""
        entry = get("openrouter")
        assert entry is not None
        assert _engine_endpoint(entry.base_url) == f"{OPENROUTER_BASE_URL}/chat/completions"
        assert OpenAICompatibleAdapter(base_url=entry.base_url).base_url == (
            "https://openrouter.ai/api"
        )

    def test_openrouter_is_reachable_from_its_own_key_alone(self, monkeypatch):
        """Its endpoint is not a preference, so the engine hardcodes it and the
        user only brings a key. The catalogue must not imply otherwise."""
        entry = get("openrouter")
        monkeypatch.delenv(GENERIC_ENDPOINT_ENV, raising=False)
        monkeypatch.delenv(GENERIC_KEY_ENV, raising=False)
        monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)

        engine = from_environment()

        assert engine is not None
        assert engine.endpoint == entry.chat_endpoint

    def test_lm_studio_matches_the_adapter_that_finds_it(self):
        """It needs no configuration at all — discovery already looks there —
        so the entry's job is to say so rather than to offer a form."""
        entry = get("lm_studio")
        assert entry is not None
        assert entry.base_url == LM_STUDIO_BASE_URL
        assert entry.auth is AuthStyle.NONE
        assert entry.key_env == "" and entry.endpoint_env == ""


class TestItIsAConvenienceNotAGate:
    def test_an_endpoint_the_catalogue_never_heard_of_still_works(self, monkeypatch):
        """The property most easily lost by someone later wiring a picker in
        front of configuration. Rule: never fail closed — a manifest whose job
        is to save typing must not become the only way to type."""
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setenv(GENERIC_ENDPOINT_ENV, "https://llm.internal.example/v1")
        monkeypatch.setenv(GENERIC_KEY_ENV, FAKE_KEY)

        engine = from_environment()

        assert get("llm.internal.example") is None
        assert engine is not None
        assert engine.endpoint == "https://llm.internal.example/v1/chat/completions"

    def test_an_empty_catalogue_takes_nothing_away(self, monkeypatch):
        """The corrupt-manifest case, which for a Python constant is a
        truncated or filtered list. Configuration is unaffected because nothing
        in the cloud path consults the catalogue to decide anything."""
        monkeypatch.setattr("providers.catalogue.PROVIDERS", ())
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setenv(GENERIC_ENDPOINT_ENV, "https://api.openai.com/v1")
        monkeypatch.setenv(GENERIC_KEY_ENV, FAKE_KEY)

        assert list_providers() == ()
        assert to_payload()["generated"] == GENERATED
        assert from_environment() is not None

    def test_an_unknown_id_returns_nothing_rather_than_raising(self):
        assert get("") is None
        assert get("a-provider-that-does-not-exist") is None


class TestBoundaries:
    def test_nothing_in_this_module_touches_the_network(self):
        """Rule 7g: no network call before the user has consented to one, and
        that includes checking whether any of these URLs still resolve. The
        manifest is dated *because* it cannot be refreshed on its own."""
        import providers.catalogue as module

        source = open(module.__file__, encoding="utf-8").read()
        for forbidden in (
            "requests.",
            "httpx.",
            "urlopen(",
            "aiohttp",
            "socket.",
            "urlretrieve",
        ):
            assert forbidden not in source, forbidden

    def test_it_describes_providers_and_holds_no_secrets(self):
        """It names the variable a key lands in and never reads it. A module
        that both knows every provider and can see keys is one refactor away
        from logging one."""
        import providers.catalogue as module

        source = open(module.__file__, encoding="utf-8").read()
        for forbidden in ("os.getenv", "os.environ", "getenv("):
            assert forbidden not in source, forbidden
        for key_shaped in ("sk-", "sk_live", "gsk_", "AIza", "xai-"):
            assert key_shaped not in source, key_shaped

    def test_entries_are_immutable(self):
        """A shared manifest that a caller can edit is a manifest that means
        something different depending on what ran first."""
        entry = PROVIDERS[0]
        # Named rather than a blind `Exception`: the point is that the
        # dataclass is frozen, and a test that accepts any error would still
        # pass if the attribute vanished entirely.
        with pytest.raises(FrozenInstanceError):
            entry.support = Support.UNAVAILABLE  # type: ignore[misc]
        assert isinstance(list_providers(), tuple)

"""A model name the user typed that matches nothing here.

The third door of the one the 28 August handoff named:

> Anywhere that treats *"no model named"* or *"cannot place this name"* as
> **therefore Ollama** is the same bug waiting.

Two had been found and fixed. This was the third, and it was measured rather
than predicted — asking for `anthropic/claude-sonnet-4.5` on this machine
produced

    [ERROR] Ollama refused the request for anthropic/claude-sonnet-4.5:
    model 'anthropic/claude-sonnet-4.5' not found

**The safety was never the problem and is not what changed.** Nothing was
sent anywhere: `_is_remote_model` answers `False` for a name it cannot
resolve, which is the fail-safe direction, and the request went to a local
server and stopped. What was wrong was the *sentence* — it names a server the
user never mentioned, for a model they did not associate with it, and offers
no idea what to do next. It also mattered more the moment queue item 6's
type-in field made "any string at all" a thing a person can enter.

The whole file is really about one discipline, which `_vision_refusal` states
in its own docstring and this borrows: **every uncertainty resolves to no
refusal.** A guard built on our own missing bookkeeping would report "that
model does not exist" about a machine nobody had scanned yet, and would fire
hardest on the first message after a boot — which is exactly how the vision
refusal failed the first time it was written.
"""

from __future__ import annotations

import pytest

from providers.contracts import (
    CapabilityLocality,
    DataPolicy,
    ModelCategory,
    ModelInfo,
)
from providers.manager import ProviderManager

import main
from main import _ModelChoice, _unplaceable_model_refusal


def model(name: str, provider: str = "ollama") -> ModelInfo:
    return ModelInfo(
        id=f"{provider}:{name}",
        display_name=name,
        provider=provider,
        category=ModelCategory.LLM,
        size_bytes=7_500_000_000,
        supports_vision=False,
        capabilities={"completion"},
        locality=CapabilityLocality.LOCAL,
        available=True,
        data_policy=DataPolicy.NEVER_LEAVES_DEVICE,
    )


class _Providers:
    def __init__(self, manager):
        self.manager = manager


@pytest.fixture()
def stocked(monkeypatch):
    """A provider layer that has scanned and found two models."""
    manager = ProviderManager()
    manager.catalog.clear()
    manager.catalog.upsert_all([model("gemma4:12b"), model("qwen2.5-coder:14b")])

    async def already_scanned():
        return None

    monkeypatch.setattr(manager, "ensure_scanned", already_scanned)
    monkeypatch.setattr(main.kernel, "providers_runtime", _Providers(manager), raising=False)
    return manager


class TestItRefusesOnlyWhatItPositivelyKnows:
    async def test_a_typed_name_matching_nothing_is_refused(self, stocked):
        refusal = await _unplaceable_model_refusal(
            _ModelChoice("anthropic/claude-sonnet-4.5", "request")
        )

        assert refusal
        # The name is quoted back. A refusal that does not repeat what was
        # typed leaves a typo invisible, which is the most likely cause.
        assert "anthropic/claude-sonnet-4.5" in refusal

    async def test_the_refusal_names_neither_a_server_nor_a_file(self, stocked):
        """It must not read as "Ollama refused" for a model nobody sent there.

        And it must not name a model filename either — `CLAUDE.md` keeps those
        out of the primary path, and a suggestion here would be one.
        """
        refusal = await _unplaceable_model_refusal(
            _ModelChoice("anthropic/claude-sonnet-4.5", "request")
        )

        assert "ollama" not in refusal.lower()
        assert "gemma4" not in refusal
        # It says what to do, which is the half the old message was missing.
        assert "Settings" in refusal

    async def test_a_model_that_is_here_passes(self, stocked):
        assert await _unplaceable_model_refusal(_ModelChoice("gemma4:12b", "request")) == ""

    async def test_a_catalogue_id_is_accepted_as_well_as_a_display_name(self, stocked):
        """The Advanced field lets someone paste either spelling.

        Being right about only one of them is the defect this guards: the same
        model under two names is what `_local_endpoint_for` shipped, where four
        call sites resolved through the catalogue and a fifth split on a colon.
        """
        assert await _unplaceable_model_refusal(_ModelChoice("ollama:gemma4:12b", "request")) == ""

    async def test_a_settings_default_is_checked_too(self, stocked):
        """A stale Settings default is the quieter version of the same problem.

        A model assigned in Settings and later uninstalled produces the same
        useless error on every message rather than on one.
        """
        assert await _unplaceable_model_refusal(_ModelChoice("gone-away:7b", "settings")) != ""


class TestEveryUncertaintyProceeds:
    async def test_an_empty_catalogue_refuses_nothing(self, monkeypatch):
        """Discovery has not run. Saying "that does not exist" from an empty
        shelf is a claim about the user's machine built on our missing data."""
        manager = ProviderManager()
        manager.catalog.clear()

        async def already_scanned():
            return None

        monkeypatch.setattr(manager, "ensure_scanned", already_scanned)
        monkeypatch.setattr(main.kernel, "providers_runtime", _Providers(manager), raising=False)

        assert await _unplaceable_model_refusal(_ModelChoice("anything", "request")) == ""

    async def test_no_provider_layer_refuses_nothing(self, monkeypatch):
        monkeypatch.setattr(main.kernel, "providers_runtime", None, raising=False)

        assert await _unplaceable_model_refusal(_ModelChoice("anything", "request")) == ""

    async def test_a_lookup_that_raises_refuses_nothing(self, monkeypatch):
        manager = ProviderManager()
        manager.catalog.clear()
        manager.catalog.upsert_all([model("gemma4:12b")])

        async def boom():
            raise RuntimeError("the provider layer is having a day")

        monkeypatch.setattr(manager, "ensure_scanned", boom)
        monkeypatch.setattr(main.kernel, "providers_runtime", _Providers(manager), raising=False)

        assert await _unplaceable_model_refusal(_ModelChoice("anything", "request")) == ""


class TestItBlamesNobodyForZaramsOwnPick:
    """`task` and `zaram` are the provider layer's selections, from the
    catalogue, so they cannot fail to be in it — and if one ever did, refusing
    would report our own bookkeeping error as the user's mistake."""

    @pytest.mark.parametrize("chosen_by", ["zaram", "task"])
    async def test_zarams_own_choice_is_never_refused(self, stocked, chosen_by):
        assert await _unplaceable_model_refusal(_ModelChoice("whatever", chosen_by)) == ""

    async def test_no_model_named_is_never_refused(self, stocked):
        """The ordinary path on a machine with no default. `None` means "use
        the engine default", which is a real answer and the best one."""
        assert await _unplaceable_model_refusal(_ModelChoice(None, "zaram")) == ""

    async def test_a_blank_name_is_never_refused(self, stocked):
        assert await _unplaceable_model_refusal(_ModelChoice("   ", "request")) == ""


class TestTheRefusalIsActuallyWiredIn:
    """The half a unit test cannot see.

    `test_chat_endpoint_writes_a_transcript.py` exists in this directory
    because its absence cost a live `NameError`: sixteen tests called the
    persistence helpers directly, none went through `/chat`, and the endpoint
    was broken for everyone. A refusal function nothing calls is the same
    shape — and this repository's stated base rate for that is fifteen
    complete, tested, unreachable subsystems.

    So: post a message naming a model that is not here, and assert both halves
    — the user is told, and **nothing was dispatched**.
    """

    def test_the_chat_endpoint_refuses_before_it_dispatches(self, stocked):
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        client = TestClient(main.app)

        with patch.object(main, "chat_router") as router:
            response = client.post(
                "/chat",
                json={
                    "text": "hello",
                    "persona": "zaram_prime",
                    "model": "anthropic/claude-sonnet-4.5",
                },
            )

            assert response.status_code == 200
            assert "cannot place" in response.text
            assert "anthropic/claude-sonnet-4.5" in response.text
            # The point of refusing *before* dispatch. With the old behaviour
            # this reached the local dispatcher, which fell through to Ollama
            # and reported a model-not-found against a server the user never
            # named.
            router.route.assert_not_called()

    def test_a_model_that_is_here_still_reaches_the_router(self, stocked):
        """The guard against fixing the above by refusing everything."""
        import json
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        client = TestClient(main.app)

        async def stream(*args, **kwargs):
            yield json.dumps({"type": "token", "data": {"content": "hi"}}) + chr(10)
            yield json.dumps({"type": "done", "data": {}}) + chr(10)

        with patch.object(main, "chat_router") as router:
            router.route.return_value = stream()
            response = client.post(
                "/chat",
                json={"text": "hello", "persona": "zaram_prime", "model": "gemma4:12b"},
            )

            assert response.status_code == 200
            assert "cannot place" not in response.text
            router.route.assert_called_once()


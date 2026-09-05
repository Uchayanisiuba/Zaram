"""`ModelsRuntime._choose_model` must return ``None`` rather than raise.

Its own docstring is the contract: *"Every failure here returns ``None`` and
leaves the engine on its own default… a provider layer that is absent,
unscannable or offline must degrade to the previous behaviour rather than take
chat down with it."*

It did take chat down. The ``try`` wrapped `ensure_scanned()` and
`select_default_model()` and stopped there, so the block *below* it — which
logs which models were excluded — was outside the guarantee. That block read
``m.id for m in rejected`` while `rejected_default_candidates()` returns
``list[tuple[ModelInfo, str]]``, and the `AttributeError` escaped through kernel
boot: 53 tests errored at app startup, and the traceback named a logging line
rather than the model layer.

**Why a green suite sat on top of it for two weeks.** The *producer* is tested
twice and both tests unpack the tuple correctly, so the type was never in
doubt. The *consumer* had no test at all. And the branch only runs when
`select_default_model()` returns ``None`` **and** something was rejected —
models discovered but every one unselectable — which does not happen on a
machine with Ollama up and a usable model. It happens on a machine with Ollama
absent, which is every machine a stranger installs this on.

So these tests assert the contract rather than the arithmetic. A future edit
that reintroduces any exception in this function fails here, not at boot.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from runtimes.models.models_runtime import ModelsRuntime


class _Model:
    def __init__(self, identifier: str) -> None:
        self.id = identifier
        self.display_name = identifier


class _Manager:
    """A provider manager that finds models and refuses all of them.

    The exact state the crash needed, and the ordinary state of a machine with
    no Ollama running or with every installed model excluded by data policy.
    """

    def __init__(self, rejected: Any) -> None:
        self._rejected = rejected

    async def ensure_scanned(self) -> None:
        return None

    def select_default_model(self):
        return None

    def rejected_default_candidates(self):
        return self._rejected


def _runtime(manager: Any) -> ModelsRuntime:
    """The runtime with a provider manager injected through its own parameter.

    `provider_manager` is a constructor argument, so nothing here reaches past
    the public shape of the object — a test that assigns a private attribute
    would keep passing after the wiring it is meant to protect was removed.
    """
    return ModelsRuntime(event_bus=None, provider_manager=manager)


def _choose(manager: Any) -> Any:
    return asyncio.run(_runtime(manager)._choose_model())


class TestItDegradesRatherThanRaising:
    def test_the_real_return_shape_does_not_raise(self):
        """`(model, reason)` pairs — what the producer actually returns."""
        rejected = [
            (_Model("qwen2.5:14b"), "provider logs and trains on prompts"),
            (_Model("mystery:unknown"), "data policy is unknown"),
        ]
        assert _choose(_Manager(rejected)) is None

    def test_no_rejections_is_still_none(self):
        assert _choose(_Manager([])) is None

    @pytest.mark.parametrize(
        "rejected",
        [
            "not a list at all",
            [object()],
            [(_Model("a"),)],
            [None],
        ],
        ids=["a string", "bare objects", "short tuples", "nulls"],
    )
    def test_any_shape_at_all_still_returns_none(self, rejected):
        """The contract is about *failure*, so it cannot be satisfied by
        handling one more shape correctly. Whatever the provider layer hands
        back, boot survives it — that is what "degrade" means, and it is the
        only version of this guarantee that a future edit cannot erode."""
        assert _choose(_Manager(rejected)) is None

    def test_a_manager_that_explodes_is_survived(self):
        class _Exploding(_Manager):
            def rejected_default_candidates(self):
                raise RuntimeError("provider database is locked")

        assert _choose(_Exploding([])) is None

    def test_no_provider_manager_is_survived(self):
        assert _choose(None) is None


class TestTheReasonIsNotThrownAway:
    def test_both_reasons_reach_the_log(self, caplog):
        """The producer's docstring says the distinction is load-bearing — "a
        user told 'no default model' deserves to know whether that was their
        data policy or their VRAM, since only one of those is something they
        can act on" — and the message hardcoded *data policy* for every
        rejection, so a model excluded for not fitting beside the embedder was
        reported as a privacy decision."""
        rejected = [
            (_Model("qwen2.5:14b"), "provider logs and trains on prompts"),
            (_Model("llama3:70b"), "does not fit alongside the embedding model"),
        ]
        with caplog.at_level("INFO"):
            _choose(_Manager(rejected))

        logged = caplog.text
        assert "provider logs and trains on prompts" in logged
        assert "does not fit alongside the embedding model" in logged

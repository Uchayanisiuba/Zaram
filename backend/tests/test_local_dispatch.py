"""A local model goes to the local server that actually holds it.

The bug this pins: `RoutedEngine` splits local from cloud and hands everything
local to Ollama. Once the catalogue gained `lm_studio` -- an OpenAI-compatible
server on 127.0.0.1:1234 -- a model served there was discovered, catalogued,
listed in the picker with a correct `NEVER_LEAVES_DEVICE` policy, and then
posted to Ollama, which answered:

    model 'Qwen3.8-27B-exl3-2.20bpw' not found

Every component was working. What was missing was the assumption that "local"
and "Ollama" are the same word.
"""

from __future__ import annotations

import pytest

from runtimes.models.engines.local_dispatch_engine import LocalDispatchEngine
from runtimes.models.engines.openai_compatible_engine import (
    MissingApiKey,
    OpenAICompatibleEngine,
)


class FakeOllama:
    def __init__(self):
        self.calls = []
        self.default_model = None

    def stream_response(self, prompt, system_prompt="", model=None, images=None):
        self.calls.append(model)
        yield "from-ollama"


def _dispatch(endpoints, wire=lambda m: m.split(":", 1)[-1]):
    ollama = FakeOllama()
    engine = LocalDispatchEngine(
        ollama=ollama,
        resolve_endpoint=lambda mid: endpoints.get(mid),
        wire_name=wire,
    )
    return engine, ollama


def test_unresolved_model_falls_back_to_ollama():
    engine, ollama = _dispatch({})
    out = "".join(engine.stream_response("hi", "", "ollama:gemma4:12b"))
    assert out == "from-ollama"
    assert ollama.calls == ["ollama:gemma4:12b"]


def test_model_on_a_local_openai_server_does_not_go_to_ollama():
    """The regression. Ollama must not see a model it does not have."""
    engine, ollama = _dispatch(
        {"lm_studio:Qwen3.8-27B-exl3-2.20bpw": "http://127.0.0.1:1234"}
    )
    built = engine._engine_for("http://127.0.0.1:1234", "Qwen3.8-27B-exl3-2.20bpw")

    assert isinstance(built, OpenAICompatibleEngine)
    assert built.base_url == "http://127.0.0.1:1234/v1"
    assert ollama.calls == []


def test_the_provider_native_name_is_what_reaches_the_server():
    """`lm_studio:` is Zaram's namespace and means nothing to TabbyAPI."""
    engine, _ = _dispatch(
        {"lm_studio:Qwen3.8-27B-exl3-2.20bpw": "http://127.0.0.1:1234"}
    )
    built = engine._engine_for("http://127.0.0.1:1234", "Qwen3.8-27B-exl3-2.20bpw")
    assert built.default_model == "Qwen3.8-27B-exl3-2.20bpw"
    assert "lm_studio" not in built.default_model


def test_a_failing_resolver_falls_back_rather_than_failing_the_message():
    def boom(_mid):
        raise RuntimeError("registry unavailable")

    ollama = FakeOllama()
    engine = LocalDispatchEngine(
        ollama=ollama, resolve_endpoint=boom, wire_name=lambda m: m
    )
    out = "".join(engine.stream_response("hi", "", "lm_studio:whatever"))
    assert out == "from-ollama"


def test_engines_are_cached_per_endpoint():
    engine, _ = _dispatch({"a": "http://127.0.0.1:1234"})
    first = engine._engine_for("http://127.0.0.1:1234", "m1")
    second = engine._engine_for("http://127.0.0.1:1234", "m2")
    assert first is second
    assert second.default_model == "m2"


class TestKeylessIsLoopbackOnly:
    """The exemption is the address, never the absence of a key."""

    def test_loopback_needs_no_key(self):
        for host in ("http://127.0.0.1:1234", "http://localhost:5000"):
            engine = OpenAICompatibleEngine(
                base_url=host, api_key="", default_model="m"
            )
            assert engine.base_url.endswith("/v1")

    def test_cloud_without_a_key_is_still_refused(self):
        with pytest.raises(MissingApiKey):
            OpenAICompatibleEngine(
                base_url="https://api.openai.com/v1", api_key="", default_model="m"
            )

    def test_a_remote_host_cannot_borrow_the_exemption(self):
        """A hostname that merely looks local is not loopback."""
        with pytest.raises(MissingApiKey):
            OpenAICompatibleEngine(
                base_url="https://localhost.attacker.example/v1",
                api_key="",
                default_model="m",
            )


class TestTheDefaultIsAChoiceToo:
    """The same defect, one door along, and the ordinary path rather than an
    edge case.

    `_resolve_model` returns ``_ModelChoice(None, "zaram")`` whenever nobody
    named a model, which is every message where the user has expressed no
    preference. `default_model` used to store the runtime's pick on
    `self._ollama` and nowhere else, and `stream_response` resolved only when
    `model` was truthy -- so an unspecified message went to Ollama however the
    default was served, while the answering event named the real provider.

    Measured on the machine this was written on, asking "What are you, and who
    made you?" with no model named::

        answering -> {"model": "Qwen3.8-27B-exl3-2.20bpw", "provider": "lm_studio"}
        answer    -> [ERROR] Ollama refused the request ... model not found
    """

    def test_the_runtime_default_is_dispatched_not_only_stored(self):
        engine, ollama = _dispatch(
            {"lm_studio:Qwen3.8-27B-exl3-2.20bpw": "http://127.0.0.1:1234"}
        )
        engine.default_model = "lm_studio:Qwen3.8-27B-exl3-2.20bpw"

        # No model named: exactly what the chat path passes for `chosen_by:
        # "zaram"`.
        list(engine.stream_response("hi", ""))

        assert ollama.calls == [], "an unspecified message reached Ollama"

    def test_the_default_still_reaches_ollama_when_ollama_holds_it(self):
        """The fallback must not regress: a default Ollama serves is unresolvable
        as a local OpenAI endpoint, and must go where it always went."""
        engine, ollama = _dispatch({})
        engine.default_model = "ollama:gemma4:12b"

        out = "".join(engine.stream_response("hi", ""))

        assert out == "from-ollama"
        # `None`, not the default: Ollama holds its own copy and applies it
        # itself, so the argument is forwarded untouched.
        assert ollama.calls == [None]

    def test_ollama_keeps_its_copy(self):
        """Setting it here must still set it there, or the Ollama-served path
        loses the default it applies itself."""
        engine, ollama = _dispatch({})
        engine.default_model = "ollama:gemma4:12b"

        assert ollama.default_model == "ollama:gemma4:12b"
        assert engine.default_model == "ollama:gemma4:12b"

    def test_an_explicit_model_still_outranks_the_default(self):
        engine, ollama = _dispatch(
            {"lm_studio:Qwen3.8-27B-exl3-2.20bpw": "http://127.0.0.1:1234"}
        )
        engine.default_model = "ollama:gemma4:12b"

        list(engine.stream_response("hi", "", "lm_studio:Qwen3.8-27B-exl3-2.20bpw"))

        assert ollama.calls == []

    def test_no_default_and_no_model_is_still_ollama(self):
        engine, ollama = _dispatch({})

        out = "".join(engine.stream_response("hi", ""))

        assert out == "from-ollama"
        assert ollama.calls == [None]


class TestThePreloadSurvivesTheWrapper:
    """`warm` has to cross this class, and for a while nothing did.

    `ModelsRuntime.warm_local_model` reaches the local engine and asks for a
    `warm` attribute, returning False when there is none. `LocalDispatchEngine`
    had none, so the preload died the moment this wrapper was introduced and
    every session since paid a full cold start on its first message.

    The existing preload tests all passed, because they inject a fake engine
    that *has* a `warm` method — the scaffolding rather than the contract, and
    the third instance of that shape found in one day. So the last test here
    builds the real stack and asks it.
    """

    def test_an_ollama_model_is_warmed_on_ollama(self):
        engine, ollama = _dispatch({})
        ollama.warmed = []
        ollama.warm = lambda m, **kw: ollama.warmed.append(m) or True

        assert engine.warm("ollama:qwen3-14b-8k:latest") is True
        assert ollama.warmed == ["ollama:qwen3-14b-8k:latest"]

    def test_the_runtime_default_is_warmed_when_no_model_is_named(self):
        """`warm_local_model` passes the selected model, but `warm()` with
        nothing named must not fall through to whatever Ollama last held."""
        engine, ollama = _dispatch({})
        ollama.warmed = []
        ollama.warm = lambda m, **kw: ollama.warmed.append(m) or True
        engine.default_model = "ollama:qwen3-14b-8k:latest"

        assert engine.warm() is True
        assert ollama.warmed == ["ollama:qwen3-14b-8k:latest"]

    def test_nothing_selected_warms_nothing(self):
        engine, ollama = _dispatch({})
        ollama.warm = lambda m, **kw: pytest.fail("warmed a model nobody chose")

        assert engine.warm() is False

    def test_a_second_local_server_is_not_warmed_by_generating(self):
        """A one-token completion would load the weights and is still a
        generation: it runs the model, appears in that server's log as a
        request the user never made, and spends a hidden inference to remove a
        wait nobody was asked about. `False` says so honestly, and the cold
        start is still announced by `model_load` when the message arrives.
        """
        engine, ollama = _dispatch(
            {"lm_studio:Qwen3.8-27B-exl3-2.20bpw": "http://127.0.0.1:1234"}
        )
        ollama.warm = lambda m, **kw: pytest.fail(
            "a TabbyAPI model was warmed on Ollama — the exact confusion this "
            "class exists to prevent"
        )

        assert engine.warm("lm_studio:Qwen3.8-27B-exl3-2.20bpw") is False

    def test_the_real_engine_stack_exposes_warm(self):
        """The guard the fake could never be.

        Every other preload test in the suite injects an engine of its own, so
        all of them passed while the shipped stack — `RoutedEngine` wrapping
        `LocalDispatchEngine` wrapping `OllamaEngine` — had no reachable
        `warm` at all. This asserts the attribute exists where
        `warm_local_model` actually looks for it.
        """
        from runtimes.models.models_runtime import ModelsRuntime

        runtime = ModelsRuntime(event_bus=None, provider_manager=None)
        built = runtime._build_engine()
        local = getattr(built, "_local", built)

        assert callable(getattr(local, "warm", None)), (
            "warm_local_model reaches this object and gives up when it has no "
            "`warm`; without this the preload is dead and says nothing"
        )

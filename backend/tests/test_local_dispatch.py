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

"""A local model that is silent is working; a stream that dies mid-thought is an error.

Four times on 13 September 2026 the maintainer's 27B answered *"the model
stopped before writing an answer"*. The backend log said what actually
happened — `TimeoutError: timed out` — a two-minute socket timeout sized for
a cloud queue, firing while a 27B at 2.2 bits pre-filled a 60,000-token
prompt. And the error text landed inside the thinking block the prompt
template had opened, so `ReasoningSplitter` filed it as thought. Two
contracts, both pinned here.
"""

from __future__ import annotations

import socket

from core.reasoning import CLOSE_TAG, OPEN_TAG
from runtimes.models.engines.base_engine import ERROR_PREFIX
from runtimes.models.engines.local_dispatch_engine import LocalDispatchEngine
from runtimes.models.engines.openai_compatible_engine import (
    DEFAULT_TIMEOUT,
    LOCAL_TIMEOUT,
    OpenAICompatibleEngine,
)


class _Gate:
    """Streams a few thinking frames, then the socket times out."""

    def __init__(self, frames):
        self._frames = frames

    def stream_lines(self, *args, **kwargs):
        for frame in self._frames:
            yield frame
        raise socket.timeout("timed out")


def _delta(text: str) -> bytes:
    import json

    return b"data: " + json.dumps({"choices": [{"delta": {"content": text}}]}).encode()


def test_a_timeout_mid_thought_is_reported_as_an_error_not_as_thinking(monkeypatch):
    engine = OpenAICompatibleEngine(base_url="http://127.0.0.1:1234", api_key="", default_model="m",
                                    gate=_Gate([_delta("weighing the"), _delta(" question")]))
    # The prompt template opens the block, as Qwen's does.
    monkeypatch.setattr(engine, "_template_opens_thinking", lambda: True)

    out = list(engine.stream_response("a long question", "system"))

    assert out[0] == OPEN_TAG
    assert out[-1].startswith(ERROR_PREFIX)
    assert "sent nothing for" in out[-1] and "stopped waiting" in out[-1]
    # The block is closed *before* the error, so the error is the answer's
    # problem and not a line of thought.
    assert out[-2] == CLOSE_TAG


def test_an_error_outside_thinking_adds_no_stray_close_tag():
    engine = OpenAICompatibleEngine(base_url="http://127.0.0.1:1234", api_key="", default_model="m",
                                    gate=_Gate([_delta("Net 45")]))
    out = list(engine.stream_response("q", ""))
    assert CLOSE_TAG not in out
    assert out[-1].startswith(ERROR_PREFIX)


def test_a_local_server_gets_the_local_wait():
    assert LOCAL_TIMEOUT > DEFAULT_TIMEOUT

    class _Ollama:
        default_model = ""

    dispatch = LocalDispatchEngine(ollama=_Ollama(), resolve_endpoint=lambda m: "http://127.0.0.1:1234", wire_name=lambda m: m)
    engine = dispatch._engine_for("http://127.0.0.1:1234", "Qwen3.8-27B")
    assert engine._timeout == LOCAL_TIMEOUT


def test_a_cloud_engine_keeps_the_cloud_wait():
    assert OpenAICompatibleEngine(base_url="https://api.example.test", api_key="k", default_model="m")._timeout == DEFAULT_TIMEOUT

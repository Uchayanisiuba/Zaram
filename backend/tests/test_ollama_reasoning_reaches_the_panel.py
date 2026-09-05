"""Zaram shows the model's working — including when Ollama is answering.

The maintainer's report, 31 August 2026: *"We don't see Zaram thinking any
more."* Nothing had been removed. They had switched from TabbyAPI to Ollama,
and the thinking had never worked on the Ollama path at all.

**`ReasoningSplitter` scans the content stream for `<think>`, and Ollama does
not put one there.** Measured against Ollama 0.33.2 with `qwen3-14b-8k`:

* `think` unset — the reply contains no tag of any kind. Not a stripped tag, an
  absent one: the model is answering in non-thinking mode.
* `think: true` — the working arrives in its own `thinking` field, **3,838
  characters** of it on the question "What is 17 times 23?".

So the splitter could never see anything, on any local model, and the panel was
empty for a reason no amount of reading it would explain.

This is the *same defect the OpenAI-compatible engine already fixed*, in a
second engine nobody revisited. That module's own docstring describes it:
providers that split a reasoning model's stream "put the thinking in a second
delta field. This engine read only `content`, so on those providers the thinking
was dropped." Ollama does exactly that, and the fix there did not travel.

`CLAUDE.md` names the pattern: *"the fourth instance of a class this codebase
had already fixed three times"*. These tests are the guard that stops the count
going to two.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import pytest
import requests

from core.reasoning import ANSWER, REASONING, ReasoningSplitter, split_events
from runtimes.models.engines.ollama_engine import OllamaEngine

OLLAMA = os.environ.get("ZARAM_OLLAMA_URL", "http://127.0.0.1:11434")


class _Stream:
    """Ollama's `/api/generate` stream, as it actually arrives.

    Thinking chunks carry an **empty** `response` alongside the `thinking`
    field — the key is present throughout, which is why the engine closes the
    tag on the first non-empty content rather than on the key appearing.
    """

    status_code = 200

    def __init__(self, lines: List[Dict[str, Any]]) -> None:
        self._lines = lines

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self):
        for line in self._lines:
            yield json.dumps(line).encode()


def _engine(monkeypatch, lines: List[Dict[str, Any]], *, capable: bool = True):
    """An engine whose Ollama answers with `lines`, recording what it was sent."""
    sent: Dict[str, Any] = {}

    def post(url, json=None, **kwargs):  # noqa: A002 - requests' own name
        if url.endswith("/api/show"):
            return _Show(["completion", "thinking"] if capable else ["completion"])
        sent.update(json or {})
        return _Stream(lines)

    monkeypatch.setattr("runtimes.models.engines.ollama_engine.requests.post", post)
    engine = OllamaEngine()
    engine.default_model = "qwen3-14b-8k:latest"
    return engine, sent


class _Show:
    status_code = 200

    def __init__(self, capabilities: List[str]) -> None:
        self._capabilities = capabilities

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Dict[str, Any]:
        return {"capabilities": self._capabilities}


class TestTheRequestAsksForThinking:
    def test_a_thinking_model_is_asked_to_think(self, monkeypatch):
        engine, sent = _engine(monkeypatch, [{"response": "hi", "done": True}])

        list(engine.stream_response("hello"))

        assert sent.get("think") is True

    def test_a_model_that_cannot_think_is_not_asked(self, monkeypatch):
        """Ollama refuses the *whole request* for a model that cannot think.

        So a wrong yes costs the answer to gain a display, and a wrong no costs
        only the panel. The capability is read from `/api/show` rather than
        guessed from the name, and any doubt resolves to no.
        """
        engine, sent = _engine(
            monkeypatch, [{"response": "hi", "done": True}], capable=False
        )

        list(engine.stream_response("hello"))

        assert "think" not in sent

    def test_an_unreachable_show_endpoint_costs_the_panel_and_not_the_reply(
        self, monkeypatch
    ):
        def post(url, json=None, **kwargs):  # noqa: A002
            if url.endswith("/api/show"):
                raise requests.ConnectionError("no")
            return _Stream([{"response": "answered anyway", "done": True}])

        monkeypatch.setattr("runtimes.models.engines.ollama_engine.requests.post", post)
        engine = OllamaEngine()
        engine.default_model = "qwen3-14b-8k:latest"

        assert "".join(engine.stream_response("hello")) == "answered anyway"

    def test_the_capability_is_asked_once_per_model(self, monkeypatch):
        """An extra loopback round trip before every message is a tax on the
        one path whose whole thesis is speed. Capabilities are a property of
        the weights and do not change under a running server."""
        asked = []

        def post(url, json=None, **kwargs):  # noqa: A002
            if url.endswith("/api/show"):
                asked.append((json or {}).get("model"))
                return _Show(["completion", "thinking"])
            return _Stream([{"response": "hi", "done": True}])

        monkeypatch.setattr("runtimes.models.engines.ollama_engine.requests.post", post)
        engine = OllamaEngine()
        engine.default_model = "qwen3-14b-8k:latest"

        list(engine.stream_response("one"))
        list(engine.stream_response("two"))

        assert asked == ["qwen3-14b-8k:latest"]


class TestTheWorkingIsSeparatedFromTheAnswer:
    #: One exchange as Ollama streams it: thinking first with an empty
    #: `response` beside it, then the answer.
    STREAM = [
        {"response": "", "thinking": "Let me work "},
        {"response": "", "thinking": "through it."},
        {"response": "The answer", "done": False},
        {"response": " is 391.", "done": True},
    ]

    def test_the_thinking_is_re_tagged_into_the_one_convention(self, monkeypatch):
        """Re-tagged rather than given a channel of its own.

        `ReasoningSplitter` already carries the reasoning event, the transcript
        rule, and the guarantee that thinking never reaches `streamingText` and
        therefore never reaches Kokoro. A second channel would need every one of
        those written twice.
        """
        engine, _ = _engine(monkeypatch, self.STREAM)

        out = "".join(engine.stream_response("what is 17 times 23"))

        assert "<think>Let me work through it.</think>" in out
        assert out.endswith("The answer is 391.")

    def test_the_splitter_downstream_files_each_half_correctly(self, monkeypatch):
        """The assertion that matters, because it is what the user sees.

        The engine's tags are only useful if the splitter that consumes them
        sorts them — asserting the tag alone would pass while the panel stayed
        empty, which is the shape of test this file exists to disprove.
        """
        engine, _ = _engine(monkeypatch, self.STREAM)
        splitter = ReasoningSplitter()

        thinking, answer = "", ""
        for chunk in engine.stream_response("what is 17 times 23"):
            for kind, text in split_events(splitter, chunk):
                if kind == REASONING:
                    thinking += text
                elif kind == ANSWER:
                    answer += text

        assert thinking == "Let me work through it."
        assert answer == "The answer is 391."

    def test_a_stream_that_ends_mid_thought_still_closes_the_tag(self, monkeypatch):
        """An unclosed `<think>` makes the splitter hold everything after it.

        A model cut off while working would otherwise leave the *next* reply's
        opening characters filed as reasoning — a reply that renders as working
        and never speaks.
        """
        engine, _ = _engine(
            monkeypatch,
            [{"response": "", "thinking": "halfway thr"}, {"response": "", "done": True}],
        )

        out = "".join(engine.stream_response("hello"))

        assert out.count("<think>") == 1
        assert out.count("</think>") == 1

    def test_a_model_that_does_not_think_is_unchanged(self, monkeypatch):
        """No tag is invented for a stream that carries no thinking.

        `core.reasoning` is explicit that the tag is the only signal and a model
        that never emits one simply never produces a reasoning event.
        """
        engine, _ = _engine(monkeypatch, [{"response": "just an answer", "done": True}])

        out = "".join(engine.stream_response("hello"))

        assert out == "just an answer"


def _ollama_model_that_thinks() -> Optional[str]:
    """An installed model `/api/show` says can think, or ``None`` to skip."""
    try:
        tags = requests.get(f"{OLLAMA}/api/tags", timeout=2.0).json()
        for entry in tags.get("models", []):
            name = entry.get("name")
            shown = requests.post(
                f"{OLLAMA}/api/show", json={"model": name}, timeout=5.0
            ).json()
            if "thinking" in (shown.get("capabilities") or []):
                return name
    except Exception:
        return None
    return None


@pytest.mark.measure
class TestAgainstTheRunningServer:
    """The half a fake cannot assert: that Ollama answers this way at all.

    Every test above would pass against a server that ignores `think` entirely
    — which is exactly the state the product was in. `CLAUDE.md`: *"assume
    unreachable until the caller is seen"*, and its companion, that a green
    suite is not evidence a thing works.
    """

    def test_ollama_returns_thinking_in_its_own_field(self):
        model = _ollama_model_that_thinks()
        if model is None:
            pytest.skip("no thinking-capable Ollama model installed")

        answered = requests.post(
            f"{OLLAMA}/api/generate",
            json={
                "model": model,
                "prompt": "What is 17 times 23?",
                "stream": False,
                "think": True,
                "keep_alive": "30m",
            },
            timeout=(5.0, 300.0),
        ).json()

        assert answered.get("thinking"), (
            "Ollama accepted `think` and returned no working; the panel would "
            "be empty for the same reason it was before this fix"
        )
        assert "<think>" not in (answered.get("response") or ""), (
            "the working must not also be inline in the answer, or it renders "
            "twice"
        )

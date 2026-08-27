"""The wait for the weights is not the wait for a token.

**Measured against the running product, 27 August 2026.** The only chat model
installed on this machine is ``gemma4:26b-a4b-it-q4_K_M``: 18.2 GB on disk
against a 12 GB card, so Ollama places 9.3 GB on the GPU and spills the rest to
system RAM. Timed with ``/api/generate`` directly:

* cold load, empty prompt, nothing generated — **109 s**
* first token afterwards, five-word prompt — **28.8 s**

`stream_response` used one number, ``120``, for both the silence before the
first token and the gap between tokens. So the load alone spent 109 of the 120
and the request was hung up on while Ollama was answering it correctly. What
reached the user was::

    [ERROR] Ollama could not answer with gemma4:26b-a4b-it-q4_K_M:
    HTTPConnectionPool(host='127.0.0.1', port=11434):
    Read timed out. (read timeout=120)

— which names a timeout and reads as a broken model.

This is the *second* time the same conflation has been paid for: the vision
path hit it on 26 August (158.9 s for a cold projector against the same 120)
and was patched with a second constant, ``420 if attached else 120``, which
fixed the case in hand and left the class alone. These tests assert the split
rather than either constant, so a third route into it fails here first.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

import pytest

from runtimes.models.engines.ollama_engine import (
    COLD_START_TIMEOUT,
    CONNECT_TIMEOUT,
    IDLE_TIMEOUT,
    OllamaEngine,
)


class _Response:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self):
        yield json.dumps({"response": "hi", "done": True}).encode()


class _CapturedPost:
    """Stands in for `requests.post`, recording the timeout it was given."""

    def __init__(self) -> None:
        self.timeout: Any = None
        self.payload: Dict[str, Any] = {}

    def __call__(self, url, json=None, **kwargs):  # noqa: A002 - requests' own name
        self.payload = json or {}
        self.timeout = kwargs.get("timeout")
        return _Response()


class _PsResponse:
    def __init__(self, names) -> None:
        self._names = names

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Dict[str, Any]:
        return {"models": [{"name": n, "model": n} for n in self._names]}


def _resident(monkeypatch, *names: str) -> None:
    monkeypatch.setattr(
        "runtimes.models.engines.ollama_engine.requests.get",
        lambda url, **kwargs: _PsResponse(list(names)),
    )


def _ps_unreachable(monkeypatch) -> None:
    def _boom(url, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr("runtimes.models.engines.ollama_engine.requests.get", _boom)


def _read_timeout_of(captured: _CapturedPost) -> float:
    """The read half, asserting the connect half is separated at all."""
    assert isinstance(captured.timeout, tuple), (
        "a single number cannot say how long to wait for the socket and how "
        "long to wait for a token, which is the bug this file is about"
    )
    connect, read = captured.timeout
    assert connect == CONNECT_TIMEOUT
    return read


class TestTheBudgetFollowsTheWeights:
    def test_a_cold_model_is_given_time_to_load(self, monkeypatch):
        """The measured 109 s load must not be spent out of a 120 s budget."""
        captured = _CapturedPost()
        monkeypatch.setattr("runtimes.models.engines.ollama_engine.requests.post", captured)
        _resident(monkeypatch)  # nothing loaded

        list(OllamaEngine().stream_response("hello", model="gemma4:26b-a4b-it-q4_K_M"))

        assert _read_timeout_of(captured) == COLD_START_TIMEOUT

    def test_the_cold_budget_covers_what_was_actually_measured(self):
        """109 s of load and 28.8 s to the first token, with room to spare on a
        slower disk. Asserted as a floor, not as the constant, so raising the
        constant does not require editing the evidence."""
        assert COLD_START_TIMEOUT >= 109 + 28.8

    def test_a_resident_model_keeps_the_short_budget(self, monkeypatch):
        """The reason this is not simply "wait longer everywhere". With the
        weights already in memory, two minutes of silence is a hang, and a
        hang reported in two minutes beats one reported in ten."""
        captured = _CapturedPost()
        monkeypatch.setattr("runtimes.models.engines.ollama_engine.requests.post", captured)
        _resident(monkeypatch, "gemma4:26b-a4b-it-q4_K_M")

        list(OllamaEngine().stream_response("hello", model="gemma4:26b-a4b-it-q4_K_M"))

        assert _read_timeout_of(captured) == IDLE_TIMEOUT

    def test_a_tag_ollama_resolved_still_counts_as_resident(self, monkeypatch):
        """`/api/ps` answers with the name it resolved, which may carry a
        `:latest` the request did not. Treating those as different models would
        put every reply on the cold budget and give back the hang detection."""
        captured = _CapturedPost()
        monkeypatch.setattr("runtimes.models.engines.ollama_engine.requests.post", captured)
        _resident(monkeypatch, "gemma3:latest")

        list(OllamaEngine().stream_response("hello", model="gemma3"))

        assert _read_timeout_of(captured) == IDLE_TIMEOUT

    def test_an_unanswerable_residency_question_is_not_read_as_loaded(self, monkeypatch):
        """`None` is never promoted to `True`. Guessing "already loaded" is the
        guess that produced the bug — and the short budget is the one that
        costs a correct answer rather than a slow one."""
        captured = _CapturedPost()
        monkeypatch.setattr("runtimes.models.engines.ollama_engine.requests.post", captured)
        _ps_unreachable(monkeypatch)

        list(OllamaEngine().stream_response("hello", model="gemma4:26b-a4b-it-q4_K_M"))

        assert _read_timeout_of(captured) == COLD_START_TIMEOUT

    def test_the_residency_check_never_takes_chat_down(self, monkeypatch):
        """It is an optimisation on the timeout. A failure here must cost a
        longer wait and nothing else."""
        captured = _CapturedPost()
        monkeypatch.setattr("runtimes.models.engines.ollama_engine.requests.post", captured)
        _ps_unreachable(monkeypatch)

        assert "".join(OllamaEngine().stream_response("hello", model="gemma3")) == "hi"


class TestTheImagePathIsAColdStartToo:
    def test_an_attached_image_gets_the_cold_budget_even_when_resident(self, monkeypatch):
        """The projector loads separately from the weights and does not appear
        in `/api/ps`, so a resident model answering its first question about an
        image is a cold start reporting as a warm one — 158.9 s, measured
        26 August 2026."""
        captured = _CapturedPost()
        monkeypatch.setattr("runtimes.models.engines.ollama_engine.requests.post", captured)
        _resident(monkeypatch, "gemma4:12b")

        list(
            OllamaEngine().stream_response(
                "what is this", model="gemma4:12b", images=["aGVsbG8="]
            )
        )

        assert _read_timeout_of(captured) == COLD_START_TIMEOUT

    def test_the_image_budget_is_no_smaller_than_it_used_to_be(self):
        """The vision path had 420 s of its own. Folding it into the cold
        budget must not quietly shorten it."""
        assert COLD_START_TIMEOUT >= 420


class _RecordingEngine:
    """An engine that records what it was asked to preload."""

    default_model = "gemma3:latest"

    def __init__(self) -> None:
        self.warmed: list = []

    def warm(self, model=None):
        self.warmed.append(model)
        return True


class _Service:
    def __init__(self, engine) -> None:
        self.engine = engine


class TestThePreloadNeverGuessesAName:
    """**The other half of why the first message paid a cold start.**

    `warm_local_model` exists so warming is a once-a-session state rather than
    a per-message one. It called ``warm(self._selected_model)``, and
    `_selected_model` is ``None`` whenever `select_default_model` declined
    everything installed — which on this machine, where the only chat model is
    twice the card, is the ordinary outcome rather than an edge case. `warm`
    then fell back to `OllamaEngine.default_model`, a hardcoded
    ``gemma3:latest`` that is not installed here, failed at `logger.info` and
    returned ``False``. The promise was quietly not being kept.
    """

    @pytest.mark.asyncio
    async def test_nothing_is_preloaded_when_nothing_was_selected(self):
        from runtimes.models.models_runtime import ModelsRuntime

        engine = _RecordingEngine()
        runtime = ModelsRuntime(event_bus=None, provider_manager=None)
        runtime._service = _Service(engine)
        runtime._selected_model = None

        assert await runtime.warm_local_model() is False
        assert engine.warmed == [], (
            "warming the engine default preloads a model the user never chose, "
            "and on this machine one that is not installed"
        )

    @pytest.mark.asyncio
    async def test_the_selected_model_is_the_one_preloaded(self):
        from runtimes.models.models_runtime import ModelsRuntime

        engine = _RecordingEngine()
        runtime = ModelsRuntime(event_bus=None, provider_manager=None)
        runtime._service = _Service(engine)
        runtime._selected_model = "ollama:gemma4:26b-a4b-it-q4_K_M"

        assert await runtime.warm_local_model() is True
        assert engine.warmed == ["ollama:gemma4:26b-a4b-it-q4_K_M"]


class TestTheTagIsPartOfTheName:
    """The residency check must not read one tag as covering another.

    Comparing up to the first colon would let a resident ``gemma4:12b`` stand
    in for a cold ``gemma4:26b-a4b-it-q4_K_M`` and hand the short budget to the
    exact request that cannot meet it — the same bug by a shorter route.
    """

    def test_a_different_tag_of_the_same_family_is_not_resident(self, monkeypatch):
        captured = _CapturedPost()
        monkeypatch.setattr("runtimes.models.engines.ollama_engine.requests.post", captured)
        _resident(monkeypatch, "gemma4:12b")

        list(OllamaEngine().stream_response("hello", model="gemma4:26b-a4b-it-q4_K_M"))

        assert _read_timeout_of(captured) == COLD_START_TIMEOUT

    def test_a_provider_prefixed_id_still_matches(self, monkeypatch):
        """`_wire` resolves the prefix away on the ordinary path, but an engine
        built without a resolver passes the id through unchanged."""
        captured = _CapturedPost()
        monkeypatch.setattr("runtimes.models.engines.ollama_engine.requests.post", captured)
        _resident(monkeypatch, "gemma4:12b")

        list(OllamaEngine().stream_response("hello", model="ollama:gemma4:12b"))

        assert _read_timeout_of(captured) == IDLE_TIMEOUT

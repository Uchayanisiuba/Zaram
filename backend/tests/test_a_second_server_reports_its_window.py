"""The context budget can read a window from more than one kind of server.

**A 32x error, measured 7 September 2026.** `loaded_context_length` asks
Ollama's `/api/ps` and nothing else, so a TabbyAPI model answered ``None`` and
`budget_for` fell back to its 4,096 constant -- on a model whose own
`/v1/model` reports **65,536**. A task running there compacted itself and handed
over at 2,048 tokens, a thirty-second of the window it actually had, and every
carry-on after that was a request that never needed making.

That is the seamlessness claim failing on exactly the axis it is made about:
*"an 8K local model and a 64K remote one behave the same way at different
sizes"* is only true if both sizes can be read.

The dangerous half is not reading the second server. It is reading it for the
**wrong model** -- `/v1/model` reports whatever that server holds, regardless of
what was asked for, so a lookup that did not check the name would hand every
Ollama model TabbyAPI's window. That test is the one that matters here.
"""

from __future__ import annotations

import pytest

from core import context_budget
from core.context_budget import (
    FALLBACK_CONTEXT_TOKENS,
    budget_for,
    local_server_context_length,
)

TABBY_MODEL = "Qwen3.8-27B-exl3-2.20bpw"


class _Response:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _serving(payload):
    """A stand-in for the OpenAI-compatible server, answering `/v1/model`."""

    def get(url, timeout=None):
        assert url.endswith("/v1/model"), url
        return _Response(payload)

    return get


@pytest.fixture
def no_ollama(monkeypatch):
    """Ollama absent, so the second lookup is the only one that can answer.

    **Both Ollama readings, not just the resident one.** `configured_context_length`
    was added on 10 September and asks `/api/show` over `requests.post`, while
    every stub in this file replaces `requests.get` — so for one day this
    fixture left a hole that the tests below walked through to the *real*
    Ollama on the developer's machine, and `test_a_model_this_server_does_not_hold`
    started answering 16,384 because that is what `qwen3-14b-16k` is actually
    configured with. A test whose answer depends on what happens to be
    installed is not testing anything, and it is the shape this repository
    keeps paying for: the suite was green and the code path was different.
    """
    monkeypatch.setattr(context_budget, "loaded_context_length", lambda *a, **k: None)
    monkeypatch.setattr(context_budget, "configured_context_length", lambda *a, **k: None)


class TestItReadsTheSecondServer:
    def test_a_served_model_reports_its_real_window(self, monkeypatch):
        monkeypatch.setattr(
            context_budget.requests,
            "get",
            _serving({"id": TABBY_MODEL, "parameters": {"max_seq_len": 65536}}),
        )
        assert local_server_context_length(TABBY_MODEL) == 65536

    def test_the_budget_uses_it(self, no_ollama, monkeypatch):
        monkeypatch.setattr(
            context_budget.requests,
            "get",
            _serving({"id": TABBY_MODEL, "parameters": {"max_seq_len": 65536}}),
        )
        budget = budget_for(TABBY_MODEL)
        assert budget.total_tokens == 65536
        assert budget.measured is True
        # The number this whole file exists for: half of 65,536 rather than half
        # of the 4,096 fallback.
        assert budget.handoff_tokens == 32768


class TestWhatItMustNotDo:
    def test_a_model_this_server_does_not_hold_gets_nothing(self, no_ollama, monkeypatch):
        """The important one.

        `/v1/model` answers about whatever *it* has loaded. Believing it about a
        name it was never given would hand every Ollama model TabbyAPI's window
        -- a confident wrong budget, which is worse than the conservative one it
        replaced, because a request sized against it does not fit.
        """
        monkeypatch.setattr(
            context_budget.requests,
            "get",
            _serving({"id": TABBY_MODEL, "parameters": {"max_seq_len": 65536}}),
        )
        assert local_server_context_length("qwen3-14b-16k") is None
        budget = budget_for("qwen3-14b-16k")
        assert budget.total_tokens == FALLBACK_CONTEXT_TOKENS
        assert budget.measured is False

    def test_a_window_of_zero_is_unreadable_rather_than_empty(self, monkeypatch):
        monkeypatch.setattr(
            context_budget.requests,
            "get",
            _serving({"id": TABBY_MODEL, "parameters": {"max_seq_len": 0}}),
        )
        # Not a budget of nothing, which would make every document too large.
        assert local_server_context_length(TABBY_MODEL) is None

    def test_a_reply_it_does_not_understand_is_not_guessed_at(self, monkeypatch):
        for payload in ({}, {"id": TABBY_MODEL}, {"id": TABBY_MODEL, "parameters": []}, []):
            monkeypatch.setattr(context_budget.requests, "get", _serving(payload))
            assert local_server_context_length(TABBY_MODEL) is None

    def test_a_server_that_is_not_answering_costs_nothing(self, monkeypatch):
        def refuse(url, timeout=None):
            raise OSError("connection refused")

        monkeypatch.setattr(context_budget.requests, "get", refuse)
        assert local_server_context_length(TABBY_MODEL) is None

    def test_it_refuses_a_host_that_is_not_loopback(self, monkeypatch):
        """Rule 3 is not worth a context length.

        The server list is a parameter, so the egress exemption this module
        carries has to be enforced rather than intended -- the same guard
        `loaded_context_length` keeps.
        """
        called = []
        monkeypatch.setattr(
            context_budget.requests, "get", lambda *a, **k: called.append(a) or _Response({})
        )
        assert (
            local_server_context_length(TABBY_MODEL, urls=("http://example.com",)) is None
        )
        assert not called, "a non-loopback host must not be contacted at all"

    def test_a_second_shape_is_read_without_a_second_decision(self, monkeypatch):
        """llama.cpp's `/props`, so switching server does not cost the window.

        Zaram ships no inference server -- rule 1 -- so which one a user runs is
        theirs to choose, and the cost of choosing must not be that Zaram stops
        being able to size a request.
        """

        def serve(url, timeout=None):
            if url.endswith("/props"):
                return _Response(
                    {
                        "model_path": "/models/qwen3-14b-16k.gguf",
                        "default_generation_settings": {"n_ctx": 16384},
                    }
                )
            raise OSError("no such route")

        monkeypatch.setattr(context_budget.requests, "get", serve)
        assert local_server_context_length("qwen3-14b-16k") == 16384
        # And still only for the model it actually holds.
        assert local_server_context_length("something-else") is None

    def test_no_model_asks_nothing(self, monkeypatch):
        called = []
        monkeypatch.setattr(
            context_budget.requests, "get", lambda *a, **k: called.append(a) or _Response({})
        )
        assert local_server_context_length("") is None
        assert local_server_context_length(None) is None
        assert not called

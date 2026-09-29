"""A provider-qualified model name still finds its window.

Reported 29 September 2026: *"Zaram wouldn't be much if it can't hold a
conversation."* Zaram answered *"I don't have the earlier conversation in front
of me"* on an exchange of 25,684 tokens, against a model whose own server
reports a **65,536**-token window.

Measured on the maintainer's machine, both forms, same server:

    Qwen3.8-27B-exl3-2.20bpw            total= 65,536  measured=True
    lm_studio:Qwen3.8-27B-exl3-2.20bpw  total=  4,096  measured=False

A sixteen-fold error. The provider layer records models as
``<provider_id>:<name>`` and these servers report the bare one, so an exact
comparison failed every qualified name and fell through to the fallback — which
leaves 3,072 tokens for the conversation instead of 49,152, and no prior turn
fits.

This module's docstring already records the same shape once: *"a TabbyAPI model
answered None and `budget_for` fell back to 4,096 — on a model whose own route
reports 65,536."* That was the server not being read. This was the server being
read and the name not matching.
"""

from __future__ import annotations

import pytest

from core import context_budget as cb


TABBY = {
    "id": "Qwen3.8-27B-exl3-2.20bpw",
    "object": "model",
    "parameters": {"max_seq_len": 65536},
}


@pytest.fixture
def server(monkeypatch):
    """One local server answering `/v1/model` with TabbyAPI's shape."""

    class _Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return TABBY

    def get(url, timeout=None):
        if url.endswith("/v1/model"):
            return _Response()
        raise RuntimeError("no such route")

    monkeypatch.setattr(cb.requests, "get", get)


# --------------------------------------------------------------------------- #
# The name
# --------------------------------------------------------------------------- #


def test_a_bare_name_reads_the_window(server):
    assert cb.local_server_context_length("Qwen3.8-27B-exl3-2.20bpw") == 65536


def test_a_provider_qualified_name_reads_the_same_window(server):
    """The bug, exactly. One prefix cost a sixteen-fold under-budget."""
    assert cb.local_server_context_length("lm_studio:Qwen3.8-27B-exl3-2.20bpw") == 65536


def test_an_ollama_name_is_never_split_at_its_tag(monkeypatch):
    """**The reason this is a suffix and not a split at the first colon.**

    Ollama's names *are* ``name:tag``. Cutting at the first colon would compare
    `qwen2.5:14b` as `14b`, and hand it whatever this server happens to hold —
    the confident wrong budget the module's docstring warns is worse than the
    conservative one.
    """

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "14b", "parameters": {"max_seq_len": 65536}}

    monkeypatch.setattr(cb.requests, "get", lambda url, timeout=None: _Response())
    assert cb.local_server_context_length("qwen2.5:14b") is None


def test_a_different_model_on_that_server_gets_nothing(server):
    """The docstring's real fear: every model inheriting one server's window."""
    assert cb.local_server_context_length("llama3.1:8b") is None


# --------------------------------------------------------------------------- #
# What it buys
# --------------------------------------------------------------------------- #


def test_the_conversation_that_did_not_fit_now_does(server):
    """25,684 tokens is what the reported exchange held.

    At the fallback it had 3,072 tokens of room and no turn fitted; measured it
    has 49,152 and the whole conversation does.
    """
    budget = cb.budget_for("lm_studio:Qwen3.8-27B-exl3-2.20bpw")
    assert budget.measured
    assert budget.input_tokens > 25_684

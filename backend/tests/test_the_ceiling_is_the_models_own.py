"""How much a model *could* hold, as opposed to how much it will have.

Asked for 4 October 2026: *"LM Studio knows the maximum token limit
because the model's creator hardcodes that exact number into the file's
code ... I'd like Zaram to handle tokens similar to LM Studio's."*

**This is the number `context_budget.py` spends its docstring warning
against**, and exposing it is not a reversal — it is the same source
answering a different question. Sizing a prompt against the declared
maximum overflows the context, which is why `loaded_context_length` and
`configured_context_length` both refuse to read it. *"How much could this
model hold if asked"* is the ceiling on a control, and for that it is the
only right answer.

Measured on the maintainer's machine the day this was written:
`gemma4:12b` declares 262,144 and loads with 4,096; `qwen3-14b-16k`
declares 40,960 and loads with 16,384. Two numbers, both true, neither
usable for the other's job.
"""

from __future__ import annotations

import pytest

from core.context_budget import declared_context_length


class TestReadingTheCeiling:
    def test_it_is_read_from_model_info(self, monkeypatch):
        import core.context_budget as module

        class Reply:
            @staticmethod
            def raise_for_status():
                return None

            @staticmethod
            def json():
                return {"model_info": {"gemma4.context_length": 262_144}}

        monkeypatch.setattr(module.requests, "post", lambda *a, **k: Reply())
        assert declared_context_length("gemma4:12b") == 262_144

    def test_the_architecture_prefix_is_not_hardcoded(self, monkeypatch):
        """The prefix *is* the architecture, so matching on a fixed one
        would need a list of every architecture Ollama supports and would
        answer `None` for the next one."""
        import core.context_budget as module

        class Reply:
            @staticmethod
            def raise_for_status():
                return None

            @staticmethod
            def json():
                return {"model_info": {"something_new_entirely.context_length": 8_192}}

        monkeypatch.setattr(module.requests, "post", lambda *a, **k: Reply())
        assert declared_context_length("whatever:1b") == 8_192

    def test_a_model_with_no_such_key_is_unknown(self, monkeypatch):
        import core.context_budget as module

        class Reply:
            @staticmethod
            def raise_for_status():
                return None

            @staticmethod
            def json():
                return {"model_info": {"general.architecture": "llama"}}

        monkeypatch.setattr(module.requests, "post", lambda *a, **k: Reply())
        assert declared_context_length("x:1b") is None

    def test_a_nonsense_value_is_unknown_rather_than_zero(self, monkeypatch):
        """`None` is a real answer. A ceiling of 0 would read as "this
        model can hold nothing" — the false zero `vram_bytes` refuses."""
        import core.context_budget as module

        class Reply:
            @staticmethod
            def raise_for_status():
                return None

            @staticmethod
            def json():
                return {"model_info": {"a.context_length": "lots"}}

        monkeypatch.setattr(module.requests, "post", lambda *a, **k: Reply())
        assert declared_context_length("x:1b") is None

    def test_no_model_is_unknown(self):
        assert declared_context_length("") is None
        assert declared_context_length(None) is None

    def test_a_server_that_will_not_answer_is_unknown_not_an_error(self, monkeypatch):
        """Never raises, for the same reason as its neighbours in this
        module: a caller handed `None` falls back deliberately, a caller
        handed an exception does not get to fall back at all."""
        import core.context_budget as module

        def explode(*_a, **_k):
            raise OSError("no ollama")

        monkeypatch.setattr(module.requests, "post", explode)
        assert declared_context_length("gemma4:12b") is None

    def test_it_refuses_a_host_that_is_not_loopback(self, monkeypatch):
        """The same boundary every reader here keeps. Asking a stranger's
        server what a model can hold is a request nobody asked for."""
        import core.context_budget as module

        called = []
        monkeypatch.setattr(module.requests, "post", lambda *a, **k: called.append(1))
        assert declared_context_length("x:1b", "http://example.com:11434") is None
        assert called == []


class TestItIsNotTheBudget:
    """The distinction this module exists to keep. Merging these is what
    overflows a context on every real document."""

    def test_the_ceiling_and_the_loaded_window_are_separate_readers(self):
        import core.context_budget as module

        assert hasattr(module, "declared_context_length")
        assert hasattr(module, "loaded_context_length")
        assert module.declared_context_length is not module.loaded_context_length

    def test_the_ceiling_reads_model_info_and_the_configured_one_does_not(self):
        """`configured_context_length`'s docstring says `parameters`,
        never `model_info`, and gives the reason. This asserts the two
        have not quietly converged."""
        import inspect

        import core.context_budget as module

        configured = inspect.getsource(module.configured_context_length)
        declared = inspect.getsource(module.declared_context_length)
        # The *call*, not the word. `configured_context_length`'s docstring
        # says "`parameters`, never `model_info`" and gives the reason, so
        # an assertion on the word fails on the explanation — and would
        # train somebody to delete it for a green build, which is the trap
        # `test_artifact_records` names.
        assert '.get("model_info")' not in configured
        assert '.get("parameters")' in configured
        assert '.get("model_info")' in declared


class TestTheRoute:
    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient

        import main

        return TestClient(main.app)

    def test_it_answers_with_both_numbers(self, client):
        body = client.get("/providers/context-ceiling", params={"model": ""}).json()
        assert set(body) == {"model", "ceiling", "loaded"}

    def test_an_unknown_model_is_null_rather_than_zero(self, client):
        body = client.get(
            "/providers/context-ceiling", params={"model": "definitely-not-installed:1b"}
        ).json()
        assert body["ceiling"] is None
        assert body["loaded"] is None

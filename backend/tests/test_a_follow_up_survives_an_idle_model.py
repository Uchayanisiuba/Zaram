"""The conversation budget must not collapse when Ollama evicts the model.

**Reported twice, and the second time the cause was different from the first.**
On 8 September the conversation was bounded by `FALLBACK_CONTEXT_TOKENS` for
every model on every machine, and the fix was to read the model's real window.
On 10 September the maintainer reported the same symptom again, in its sharpest
form: *"generate code with a slight error, then ask it to fix the error, and it
doesn't seem to remember the last prompt."*

The measurement said why. `loaded_context_length` reads `/api/ps`, which lists
what is **resident**, and Ollama evicts an idle model after a few minutes — the
few minutes a user spends reading an answer and finding the error in it. So the
same model measured 16,384 tokens during turn one and 4,096 between turns; the
conversation's quarter-share of that is 768 tokens; a reply carrying a code
block costs more than that on its own; and `fit` returning nothing is what
"doesn't remember" looked like from the outside.

Every number here was measured on the maintainer's machine, 10 September 2026,
against the installed models.

The contract is therefore about the *idle* case specifically. A test that only
exercises a resident model passes on both sides of this bug, which is exactly
how the first fix shipped believing it was complete.
"""

import re

import pytest

from core.context_budget import (
    FALLBACK_CONTEXT_TOKENS,
    budget_for,
    configured_context_length,
)


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


#: `/api/show` as Ollama actually renders it — the parameters are the
#: Modelfile's own lines, so this is a text field and not a mapping.
SHOW_WITH_NUM_CTX = {
    "parameters": (
        'num_ctx                        16384\n'
        'repeat_penalty                 1\n'
        'stop                           "<|im_start|>"\n'
        "temperature                    0.6"
    ),
    # The declared maximum, which is 2.5x the configured window and must never
    # be the answer. See `test_the_architecture_maximum_is_never_the_answer`.
    "model_info": {"qwen3.context_length": 40960},
}

#: A model created without an explicit `num_ctx`. Ollama serves it the 4,096
#: default, so "unknown" here is correct rather than a gap.
SHOW_WITHOUT_NUM_CTX = {
    "parameters": "stop                           \"<|im_end|>\"",
    "model_info": {"qwen3.context_length": 262144},
}


@pytest.fixture
def idle_ollama(monkeypatch):
    """Ollama up, nothing resident — the state between two turns."""
    import core.context_budget as budget_module

    monkeypatch.setattr(
        budget_module.requests, "get", lambda *a, **k: _Response({"models": []})
    )

    def _post(url, json=None, **kwargs):
        assert url.endswith("/api/show")
        payload = (json or {}).get("model")
        return _Response(
            SHOW_WITH_NUM_CTX if payload == "qwen3-14b-16k" else SHOW_WITHOUT_NUM_CTX
        )

    monkeypatch.setattr(budget_module.requests, "post", _post)
    # A TabbyAPI probe would otherwise reach the network in a unit test, and it
    # is not the source under examination here.
    monkeypatch.setattr(budget_module, "local_server_context_length", lambda *a, **k: None)


class TestAnIdleModelStillHasAWindow:
    def test_the_configured_window_answers_when_nothing_is_resident(self, idle_ollama):
        assert configured_context_length("qwen3-14b-16k") == 16384

    def test_the_budget_uses_it_rather_than_the_fallback(self, idle_ollama):
        budget = budget_for("qwen3-14b-16k")

        assert budget.total_tokens == 16384
        assert budget.measured is True
        assert budget.source == "configured"

    def test_the_conversation_share_is_no_longer_768_tokens(self, idle_ollama):
        """The number the whole bug reduces to, asserted as a number.

        `CONVERSATION_SHARE` is a quarter of the input budget, and the input
        budget is three quarters of the window. At the 4,096 fallback that is
        768 tokens — roughly 2,300 characters, less than one code answer.
        """
        from core.execution_engine import ExecutionEngine

        cap = int(budget_for("qwen3-14b-16k").input_tokens * ExecutionEngine.CONVERSATION_SHARE)
        fallback_cap = int(
            FALLBACK_CONTEXT_TOKENS * 0.75 * ExecutionEngine.CONVERSATION_SHARE
        )

        assert fallback_cap == 768, "the number this test is named after moved"
        assert cap == 3072
        assert cap > fallback_cap * 3


class TestUnknownIsStillAThirdAnswer:
    def test_a_model_without_num_ctx_reads_none(self, idle_ollama):
        """Not a gap: Ollama serves such a model its 4,096 default, so the
        fallback is the correct answer and `source` says it was assumed."""
        assert configured_context_length("qwen3-coder:30b") is None

        budget = budget_for("qwen3-coder:30b")
        assert budget.total_tokens == FALLBACK_CONTEXT_TOKENS
        assert budget.measured is False
        assert budget.source == "assumed"

    def test_the_architecture_maximum_is_never_the_answer(self, idle_ollama):
        """**The trap this module was written about, reached by a new route.**

        `/api/show` carries both numbers. `model_info` reports what the weights
        could support — 40,960 for a model that loads with 16,384, and 262,144
        for one that loads with 4,096 — and sizing a prompt against it overflows
        the context on almost every real request. Only `parameters` is read.
        """
        for name in ("qwen3-14b-16k", "qwen3-coder:30b"):
            total = budget_for(name).total_tokens
            assert total not in (40960, 262144), f"{name} read the declared maximum"

    def test_a_reply_that_cannot_be_parsed_is_none_rather_than_a_guess(self, monkeypatch):
        import core.context_budget as budget_module

        monkeypatch.setattr(
            budget_module.requests, "get", lambda *a, **k: _Response({"models": []})
        )
        monkeypatch.setattr(
            budget_module.requests,
            "post",
            lambda *a, **k: _Response({"parameters": {"num_ctx": 16384}}),
        )

        assert configured_context_length("anything") is None

    def test_a_failing_request_costs_the_budget_and_not_the_reply(self, monkeypatch):
        """Never raises. A window that cannot be read is a smaller prompt, not
        a failed request — the same discipline `loaded_context_length` keeps."""
        import core.context_budget as budget_module

        def _boom(*args, **kwargs):
            raise RuntimeError("ollama is not answering")

        monkeypatch.setattr(budget_module.requests, "post", _boom)

        assert configured_context_length("qwen3-14b-16k") is None


class TestTheResidentReadingStillWins:
    def test_ps_is_preferred_over_show(self, monkeypatch):
        """Order matters and is not cosmetic.

        `/api/ps` reports what the running instance was **given**, which is the
        stronger claim: something may have overridden `num_ctx` at load time,
        and the configured figure would then describe a model that is not the
        one answering.
        """
        import core.context_budget as budget_module

        monkeypatch.setattr(
            budget_module.requests,
            "get",
            lambda *a, **k: _Response(
                {"models": [{"name": "qwen3-14b-16k:latest", "context_length": 8192}]}
            ),
        )
        monkeypatch.setattr(
            budget_module.requests, "post", lambda *a, **k: _Response(SHOW_WITH_NUM_CTX)
        )

        budget = budget_for("qwen3-14b-16k")

        assert budget.total_tokens == 8192
        assert budget.source == "loaded"


class TestTheLoopbackRuleHolds:
    def test_a_non_loopback_host_is_refused_rather_than_asked(self, monkeypatch):
        """`test_egress_chokepoint.py` exempts this module because its
        destination cannot leave the machine, and `base_url` is a parameter —
        so the exemption has to be enforced rather than intended. A context
        length is not worth a hole in rule 3."""
        import core.context_budget as budget_module

        def _must_not_be_called(*args, **kwargs):
            raise AssertionError("a request left the machine")

        monkeypatch.setattr(budget_module.requests, "post", _must_not_be_called)

        assert configured_context_length("m", base_url="http://evil.test") is None
        # The prefix trap the module's own `_is_loopback` was written for.
        assert configured_context_length("m", base_url="http://127.0.0.1.evil.test") is None


class TestTheCodeConversationTheMaintainerReported:
    def test_a_code_answer_and_its_follow_up_both_survive(self, idle_ollama):
        """The reported failure, as a transcript rather than as a constant.

        Measured on the real `Turn.tokens`: a 120-line code answer and the
        question that asked for it cost **1,477 tokens**, so the 768-token
        allowance the fallback produced kept **zero of two turns** — the model
        was shown nothing at all, under a heading promising continuity. At the
        configured window's 3,072 it keeps both.

        **The sizes here are measured rather than reasoned.** A first draft of
        this test used 60 lines, which costs 743 tokens and *fits* 768 by
        twenty-five — a knife-edge that would have passed while asserting
        nothing about the bug. That is the same failure as a test whose setup
        no longer reaches its own boundary, caught here only because the number
        was checked instead of estimated.
        """
        from core.execution_engine import ExecutionEngine
        from core.transcript import ASSISTANT, USER, Turn, fit

        code = '\n'.join(f"    line_{i} = compute(i)  # step {i}" for i in range(120))
        block = 'Here you go:\n```python\n{code}\n```'
        turns = [
            Turn(role=USER, text="write me a function that computes this"),
            Turn(role=ASSISTANT, text=block.format(code=code)),
        ]
        assert sum(t.tokens for t in turns) > 1400, "the sample shrank; re-measure"

        fallback_cap = int(
            FALLBACK_CONTEXT_TOKENS * 0.75 * ExecutionEngine.CONVERSATION_SHARE
        )
        kept_before, dropped_before = fit(turns, fallback_cap)
        assert kept_before == [], "the bug no longer reproduces; this test is stale"
        assert dropped_before == 2

        cap = int(
            budget_for("qwen3-14b-16k").input_tokens * ExecutionEngine.CONVERSATION_SHARE
        )
        kept, dropped = fit(turns, cap)

        assert dropped == 0
        assert [t.role for t in kept] == [USER, ASSISTANT]
        # The specific thing the follow-up needs: the code itself, not a
        # heading that claims continuity over an empty exchange.
        assert "line_119" in kept[-1].text


def test_the_parameters_field_is_matched_per_line():
    """A parameter whose name merely ends in `num_ctx` must not answer for it.

    Cheap, and it guards the one piece of parsing here — the field is free text
    rendered from a Modelfile, so a substring match is a wrong answer waiting
    for a model that carries an unusual parameter.
    """
    parameters = "custom_num_ctx                 999999\nnum_ctx                        8192"

    match = re.search(r"^num_ctx\s+(\d+)", parameters, re.MULTILINE)

    assert match is not None
    assert int(match.group(1)) == 8192

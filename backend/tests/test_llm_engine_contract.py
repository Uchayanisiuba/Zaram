"""Every LLM engine — real or fake — satisfies one contract.

There were four `stream_response` signatures across the backend and no single
interface tying them together, so drift in any one of them failed nowhere else.
That is not a hypothetical: it is why `FakeLLM` kept a two-argument
`stream_response` for four milestones while the real client grew a third, and
why the 13 tests covering streaming conversation failed identically without
anyone reading the message.

`typing.Protocol` does not help here. `runtime_checkable` checks method *names*
only — a class whose `stream_response` takes no arguments at all passes
`isinstance(obj, LLMEngine)`. So the signature is checked explicitly, by
binding a call the way every caller in the codebase makes it.

Add an engine, add it to `ENGINES`. `OpenAICompatibleEngine` goes here the day
it exists.
"""

from __future__ import annotations

import inspect

import pytest

from implementations.ollama_llm import OllamaLLM
from runtimes.models.engines.base_engine import ERROR_PREFIX, LLMEngine
from runtimes.models.engines.ollama_engine import OllamaEngine
from runtimes.models.engines.openai_compatible_engine import OpenAICompatibleEngine
from tests.llm_doubles import FakeLLM

#: Real engines and the doubles that stand in for them. The doubles are in this
#: list deliberately — a fake exempt from the contract is the original bug.
#:
#: `OpenAICompatibleEngine` joined on 11 August 2026, which is what the note at
#: the top of this file was reserving a place for. It matters more here than the
#: others do: it is the only engine whose `system_prompt` leaves the machine, so
#: a signature drift that dropped or reordered it would change *what is sent to
#: a third party* rather than only what the model reads.
ENGINES = [OllamaEngine, OllamaLLM, OpenAICompatibleEngine, FakeLLM]

#: The one call shape. Every caller uses it: `ModelsService.generate_response`,
#: `ConversationManager.run_conversation`, `Dispatcher.dispatch_stream`.
CANONICAL_PARAMETERS = ["prompt", "system_prompt", "model"]


@pytest.mark.parametrize("engine_cls", ENGINES, ids=lambda c: c.__name__)
def test_parameters_are_named_and_ordered_the_same(engine_cls):
    signature = inspect.signature(engine_cls.stream_response)
    parameters = [p for p in signature.parameters if p != "self"]

    assert parameters == CANONICAL_PARAMETERS, (
        f"{engine_cls.__name__}.stream_response{signature} does not match the "
        f"contract in base_engine.LLMEngine. Positional callers exist, so the "
        f"*order* matters as much as the names: swapping system_prompt and "
        f"model sends the model name to the model as its instructions."
    )


@pytest.mark.parametrize("engine_cls", ENGINES, ids=lambda c: c.__name__)
def test_accepts_the_call_every_caller_makes(engine_cls):
    """Positionally, which is how `generate_response` and the dispatcher call."""
    signature = inspect.signature(engine_cls.stream_response)
    parameters = {k: v for k, v in signature.parameters.items() if k != "self"}
    bindable = inspect.Signature(list(parameters.values()))

    bindable.bind("a prompt", "a system prompt", "some-model:latest")
    bindable.bind("a prompt")  # system_prompt and model are both optional


@pytest.mark.parametrize("engine_cls", ENGINES, ids=lambda c: c.__name__)
def test_system_prompt_and_model_are_optional(engine_cls):
    """`None` means the engine's own default; it is never a required argument.

    `ExecutionEngine` calls with no model when the user has not chosen one, and
    an engine that made it required would fail only on that path.
    """
    parameters = inspect.signature(engine_cls.stream_response).parameters
    for name in ("system_prompt", "model"):
        assert parameters[name].default is not inspect.Parameter.empty, (
            f"{engine_cls.__name__}.stream_response has no default for {name}"
        )


@pytest.mark.parametrize("engine_cls", ENGINES, ids=lambda c: c.__name__)
def test_satisfies_the_protocol_structurally(engine_cls):
    assert isinstance(engine_cls.__new__(engine_cls), LLMEngine)


def test_the_double_records_what_it_was_handed():
    """The fake is only worth having if it can catch a dropped argument.

    M4 fixed a bug where the requested model was logged and then discarded. A
    double that ignores its arguments cannot notice that happening again.
    """
    fake = FakeLLM(tokens=["one", "two"])

    assert list(fake.stream_response("p", "sys", "m:latest")) == ["one", "two"]
    assert fake.calls == [("p", "sys", "m:latest")]


def test_error_prefix_is_shared_not_reinvented():
    """Both real engines report failures with the same marker.

    They previously used `[ERROR] ` and a `⚠️` string respectively, so anything
    downstream trying to recognise a failure had two conventions to know about
    and no way to discover the second.
    """
    import runtimes.models.engines.ollama_engine as ollama_engine
    import implementations.ollama_llm as ollama_llm

    assert ollama_engine.ERROR_PREFIX is ERROR_PREFIX
    assert ollama_llm.ERROR_PREFIX is ERROR_PREFIX

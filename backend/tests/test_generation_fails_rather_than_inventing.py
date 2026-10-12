"""Motion and presentation generation ask the model, or fail. They never make one up.

10 October 2026, found auditing a batch of changes. Both runtimes tried a
`ModelsRuntime.generate_local` that does not exist, then posted the prompt to the
first catalogue provider with a `base_url` using a raw HTTP client -- outside the
egress gate, which is rule 3 -- naming one model in the code, and when that failed
returned a *mock* script. A video or a deck of something nobody asked for is rule
9's failure in a new medium: it looks finished and it is wrong.
"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

import pytest

from modules.motion import runtime as motion
from modules.motion.generator import MotionScriptParseError
from modules.presenton import runtime as presenton
from runtimes.models.engines.base_engine import ERROR_PREFIX
from runtimes.models.models_runtime import ModelsRuntime

BACKEND = Path(__file__).resolve().parents[1]


def _motion(complete=None):
    return motion.MotionRuntime(None, None, complete=complete)


def _presenton(complete=None):
    return presenton.PresentonRuntime(None, None, complete=complete)


async def _motion_script(rt):
    return await rt._generate_script("a title card", {}, 3.0, "16:9")


async def _presentation_script(rt):
    return await rt._generate_script("a pitch deck", {})


def test_with_no_model_to_ask_motion_says_so():
    with pytest.raises(motion.GenerationUnavailable):
        asyncio.run(_motion_script(_motion()))


def test_with_no_model_to_ask_a_presentation_says_so():
    with pytest.raises(presenton.GenerationUnavailable):
        asyncio.run(_presentation_script(_presenton()))


def test_a_model_that_fails_is_reported_not_papered_over():
    async def broken(*_a):
        raise RuntimeError("model is not loaded")

    with pytest.raises(motion.GenerationUnavailable, match="model is not loaded"):
        asyncio.run(_motion_script(_motion(broken)))
    with pytest.raises(presenton.GenerationUnavailable, match="model is not loaded"):
        asyncio.run(_presentation_script(_presenton(broken)))


def test_an_answer_that_is_not_a_script_is_an_error_and_not_a_substitute():
    async def prose(*_a):
        return "Sure! Here is a lovely animation idea."

    with pytest.raises(MotionScriptParseError):
        asyncio.run(_motion_script(_motion(prose)))


def test_the_model_is_asked_with_the_prompt_and_without_a_name_written_in_the_code():
    seen = {}

    async def spy(user_prompt, system_prompt, model):
        seen.update(user=user_prompt, system=system_prompt, model=model)
        return "not json"

    with pytest.raises(MotionScriptParseError):
        asyncio.run(_motion_script(_motion(spy)))
    assert "title card" in seen["user"] and seen["system"]
    assert seen["model"] is None  # the provider layer's selection, not a constant


@pytest.mark.parametrize("module", [motion, presenton])
def test_neither_runtime_goes_around_the_gate_or_keeps_a_mock(module):
    source = inspect.getsource(module)
    assert "httpx" not in source, "a raw HTTP client is a request EgressGate cannot see"
    assert "_mock_script_for_request" not in source
    assert "qwen" not in source.lower(), "a model name in logic is code for one model"


def test_the_bootstrapper_gives_both_the_engines_answer():
    source = (BACKEND / "core" / "bootstrapper.py").read_text(encoding="utf-8")
    assert source.count("complete=models_runtime.complete") == 2


class _Service:
    def __init__(self, chunks):
        self.chunks = chunks
        self.asked = []

    def generate_response(self, user_text, system_prompt="", model=None, images=None, tools=None):
        self.asked.append((user_text, system_prompt, model))
        yield from self.chunks


def _runtime(service):
    rt = object.__new__(ModelsRuntime)
    rt._service = service
    return rt


def test_complete_joins_the_engines_chunks_and_passes_the_arguments_on():
    service = _Service(["Hel", "lo"])
    assert asyncio.run(_runtime(service).complete("hi", "be brief", "some-model")) == "Hello"
    assert service.asked == [("hi", "be brief", "some-model")]


def test_complete_raises_an_engines_error_instead_of_returning_it_as_text():
    service = _Service(["partial ", ERROR_PREFIX + "cloud model has no key"])
    with pytest.raises(RuntimeError, match="cloud model has no key"):
        asyncio.run(_runtime(service).complete("hi"))


def test_complete_before_the_runtime_is_ready_raises():
    with pytest.raises(RuntimeError, match="not ready"):
        asyncio.run(_runtime(None).complete("hi"))

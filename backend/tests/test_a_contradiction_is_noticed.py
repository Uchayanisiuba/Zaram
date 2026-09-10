"""A fact that contradicts a stored one raises a question, in the reply.

**The detector was written, tested, and called by nothing.**
`runtimes/memory/conflicts.py` has been able to answer *"does this contradict
something already stored"* since the day it was written, and no production code
ever asked. That is this repository's most-repeated failure — a complete,
tested subsystem with no caller — and it is the sixteenth found.

What happened instead was the ordinary path: store both facts and let recall
choose between them. Recall choosing between *"the target is developers"* and
*"the target is ordinary consumers"* is a coin toss wearing the costume of an
answer, and the user never learns the two are both in there.

**Noticed, never resolved**, and the tests below pin that distinction because
it is the part most likely to be argued away later. `conflicts.py` makes the
case in full: auto-resolving on recency would be wrong about as often as it was
right, since *"I prefer local models"* and *"send this one to Claude"* are a
general preference and a specific exception rather than a contradiction; and
auto-resolving on confidence would let a well-phrased line in an uploaded PDF
overwrite something the user said out loud. Both failures are silent, and both
destroy the record rule 4 exists to protect.

So the engine surfaces the question the detector composed and stores the new
fact alongside the old one. The user settles it in Memory, where `correct()`
already writes a replacement and strikes the original through.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest

from core.contracts import Capability, RuntimeMetadata, RuntimeState
from core.event_bus import EventBus
from core.execution_engine import ExecutionEngine
from core.registry import RuntimeRegistry
from core.streaming_events import EventType, StreamEvent
from runtimes.models.engines.routed_engine import RoutedEngine
from runtimes.models.models_service import ModelsService

MODEL = "a-local-model"


@dataclass
class _Record:
    """What `find_conflicts` reads structurally: id, content, scope, and the
    supersession fields. Deliberately not a `MemoryRecord` — the detector is
    typed structurally so it does not reach back into the runtime."""

    id: str
    content: str
    scope: str = "global"
    superseded_by: str | None = None


@dataclass
class _Result:
    record: _Record


class _Engine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    def stream_response(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str | None = None,
        images: list[str] | None = None,
    ) -> Iterator[str]:
        self.calls.append((prompt, system_prompt, model))
        yield "Noted."


class _Memory:
    """A Spine holding whatever the test put in it."""

    def __init__(self, records: list[_Record]) -> None:
        self.records = records
        self.stored: list[str] = []

    async def retrieve(self, query: str, max_results: int = 5, **kw):
        return [_Result(r) for r in self.records][:max_results]

    async def remember(self, content: str, **kw):
        self.stored.append(content)
        return content


class _MemoryRuntime:
    """The runtime the engine actually talks to.

    `_memory_runtime()` hands back the *runtime* and calls `retrieve` and
    `remember` on it directly, so a wrapper that only exposes `get_service()`
    is not the shape production uses — the engine logs an `AttributeError` and
    carries on, which reads as "nothing was stored" rather than as a broken
    test harness.
    """

    def __init__(self, service: _Memory) -> None:
        self._service = service

    async def retrieve(self, *args, **kwargs):
        return await self._service.retrieve(*args, **kwargs)

    async def remember(self, *args, **kwargs):
        return await self._service.remember(*args, **kwargs)

    def get_runtime_id(self):
        return "memory"

    def get_metadata(self):
        return RuntimeMetadata(
            runtime_id="memory",
            version="1.0.0",
            capabilities=[Capability(id="memory.retrieve", runtime_id="memory")],
        )

    def get_service(self):
        return self._service

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    def get_state(self):
        return RuntimeState.READY

    def health_check(self):
        return {"state": "ready"}


class _ModelsRuntime:
    def __init__(self, service: ModelsService) -> None:
        self._service = service

    def get_runtime_id(self):
        return "models"

    def get_metadata(self):
        return RuntimeMetadata(
            runtime_id="models",
            version="1.0.0",
            capabilities=[Capability(id="reasoning.generate", runtime_id="models")],
        )

    def get_service(self):
        return self._service

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    def get_state(self):
        return RuntimeState.READY

    def health_check(self):
        return {"state": "ready"}


def _engine_with(records: list[_Record]) -> tuple[ExecutionEngine, _Memory]:
    memory = _Memory(records)
    registry = RuntimeRegistry(EventBus())
    model = _Engine()
    registry.register(
        _ModelsRuntime(
            ModelsService(RoutedEngine(local=model, cloud=model, is_remote=lambda m: False))
        )
    )
    registry.register(_MemoryRuntime(memory))
    return ExecutionEngine(registry, EventBus()), memory


def _memory_notices(events: list[Any]) -> list[StreamEvent]:
    return [
        e
        for e in events
        if getattr(e, "type", None) is EventType.NOTICE
        and getattr(e, "data", {}).get("kind") == "memory"
    ]


class TestTheQuestionReachesTheUser:
    def test_a_contradicting_fact_raises_it_in_the_reply(self):
        """**The assertion this file exists for.**

        A detector whose output never leaves the function is the same as no
        detector, and every other test here would pass without the notice ever
        being yielded.
        """
        engine, _ = _engine_with([_Record("r1", "The target is developers")])

        events = list(
            engine.execute("The target is ordinary consumers", MODEL, "", "s")
        )

        notices = _memory_notices(events)
        assert notices, "the contradiction was detected and never surfaced"
        content = notices[0].data["content"]
        assert "developers" in content
        assert "ordinary consumers" in content
        # It routes somewhere the user can settle it, rather than stating a
        # problem with no next step.
        assert notices[0].data["action"] == "memory"

    def test_one_question_rather_than_a_stack_of_them(self):
        """A reply ending in four questions is a reply nobody finishes."""
        engine, _ = _engine_with(
            [
                _Record("r1", "The target is developers"),
                _Record("r2", "The target is agencies"),
            ]
        )

        events = list(engine.execute("The target is consumers", MODEL, "", "s"))

        assert len(_memory_notices(events)) == 1


class TestItNoticesAndDoesNotResolve:
    def test_the_new_fact_is_still_stored(self):
        """Detection is not a gate. Refusing the write would make Zaram argue
        with the user about what they just said, and rule 4 puts the user in
        charge of the record rather than the detector."""
        engine, memory = _engine_with([_Record("r1", "The target is developers")])

        list(engine.execute("The target is ordinary consumers", MODEL, "", "s"))

        assert any("ordinary consumers" in c for c in memory.stored)

    def test_the_existing_fact_is_not_superseded(self):
        """Nothing here writes a supersession. `correct()` does that, when the
        user says so — auto-resolving on recency would be wrong about as often
        as it was right."""
        record = _Record("r1", "The target is developers")
        engine, _ = _engine_with([record])

        list(engine.execute("The target is ordinary consumers", MODEL, "", "s"))

        assert record.superseded_by is None


class TestItStaysQuietWhenItShould:
    def test_an_agreeing_fact_raises_nothing(self):
        engine, _ = _engine_with([_Record("r1", "The target is developers")])

        events = list(engine.execute("The target is developers", MODEL, "", "s"))

        assert _memory_notices(events) == []

    def test_a_different_scope_is_a_different_question(self):
        """Rule 7i. One client paying in 14 days does not contradict another
        paying in 30, and a system that says it does is one the user learns to
        ignore."""
        engine, _ = _engine_with(
            [_Record("r1", "The terms are net 14", scope="project:other")]
        )

        events = list(engine.execute("The terms are net 30", MODEL, "", "s"))

        assert _memory_notices(events) == []

    def test_an_already_corrected_fact_is_not_raised_again(self):
        """It is history, and asking would make the user re-decide something
        they have already decided."""
        engine, _ = _engine_with(
            [_Record("r1", "The target is developers", superseded_by="r9")]
        )

        events = list(engine.execute("The target is ordinary consumers", MODEL, "", "s"))

        assert _memory_notices(events) == []

    def test_a_question_raises_nothing(self):
        """Questions are not facts and are never stored, so they cannot
        contradict one either."""
        engine, _ = _engine_with([_Record("r1", "The target is developers")])

        events = list(engine.execute("Who is the target?", MODEL, "", "s"))

        assert _memory_notices(events) == []


class TestItCannotCostTheAnswer:
    def test_a_failing_detector_still_stores_and_still_replies(self):
        """Never raises. A check that cannot run costs the *question*, not the
        fact being stored and not the reply the user is waiting for."""
        engine, memory = _engine_with([_Record("r1", "The target is developers")])

        async def _boom(*args, **kwargs):
            raise RuntimeError("the index is rebuilding")

        memory.retrieve = _boom  # type: ignore[assignment]

        events = list(engine.execute("The target is consumers", MODEL, "", "s"))

        assert _memory_notices(events) == []
        assert any("consumers" in c for c in memory.stored)
        assert events, "the reply itself must survive a failed conflict check"

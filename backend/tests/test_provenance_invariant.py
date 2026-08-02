# backend/tests/test_provenance_invariant.py
"""The provenance invariant.

CLAUDE.md rule 2: every recalled fact carries provenance. An answer that cites
nothing is a bug.

Operationally that means: **anything injected into the context a model sees must
be accounted for by a source event on the stream.** If a future feature — a tool
result, a retrieved document, a profile block — starts injecting context without
emitting provenance, these tests fail.

They assert the invariant, not any particular injection site, so they keep
holding as new sites are added.
"""
from __future__ import annotations

import re

import pytest

from core.contracts import (
    Capability,
    RuntimeMetadata,
    RuntimeState,
)
from core.event_bus import EventBus
from core.execution_engine import ExecutionEngine
from core.registry import RuntimeRegistry
from core.streaming_events import EventType, StreamEvent
from runtimes.memory.contracts import MemoryRecord, MemoryResult, MemoryType

#: Matches the citation markers the engine injects: [M1], [S2], ...
MARKER = re.compile(r"\[([A-Z])(\d+)\]")


class _RecordingService:
    """Stands in for ModelsService and records the context it was handed."""

    def __init__(self):
        self.seen_system_prompts: list[str] = []

    def generate_response(self, prompt: str, system_prompt: str = ""):
        self.seen_system_prompts.append(system_prompt)
        yield "answered"


class _FakeModelsRuntime:
    def __init__(self, service):
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


class _FakeMemoryRuntime:
    """Returns fixed memories, so recall is deterministic."""

    def __init__(self, contents: list[str], score: float = 0.9):
        self._records = [
            MemoryRecord(content=c, memory_type=MemoryType.CONVERSATION)
            for c in contents
        ]
        self._score = score
        self.remembered: list[str] = []

    def get_runtime_id(self):
        return "memory"

    def get_metadata(self):
        return RuntimeMetadata(
            runtime_id="memory",
            version="1.0.0",
            capabilities=[
                Capability(id="memory.retrieve", runtime_id="memory"),
                Capability(id="memory.store", runtime_id="memory"),
            ],
        )

    async def retrieve(self, query, max_results=10, session_id=None, **kwargs):
        return [
            MemoryResult(record=r, score=self._score, match_reason="test", rank=i)
            for i, r in enumerate(self._records)
        ]

    async def remember(self, content, **kwargs):
        self.remembered.append(content)
        return "stored-id"

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    def get_state(self):
        return RuntimeState.READY

    def health_check(self):
        return {"state": "ready"}


def _build_engine(memory_contents: list[str] | None = None):
    registry = RuntimeRegistry(EventBus())
    service = _RecordingService()
    registry.register(_FakeModelsRuntime(service))
    memory = None
    if memory_contents is not None:
        memory = _FakeMemoryRuntime(memory_contents)
        registry.register(memory)
    engine = ExecutionEngine(registry, EventBus())
    return engine, service, memory


def _run(engine, prompt: str, system_prompt: str = ""):
    """Drain execute(), separating source events from response tokens."""
    sources: list[StreamEvent] = []
    tokens: list[str] = []
    for item in engine.execute(prompt, "test-model", system_prompt):
        if isinstance(item, StreamEvent):
            if item.type == EventType.SOURCE:
                sources.append(item)
        else:
            tokens.append(item)
    return sources, "".join(tokens)


# ---------------------------------------------------------------------------
# The invariant
# ---------------------------------------------------------------------------


def test_every_injected_context_chunk_has_a_source_event():
    """The core invariant: injected context is fully accounted for.

    Each chunk the engine folds into the model's context is labelled with a
    citation marker. The number of distinct markers must never exceed the
    number of source events emitted, or the user has been shown a claim whose
    origin they cannot inspect.
    """
    engine, service, _ = _build_engine(
        ["the deadline is 14 March", "the budget is 40 thousand"]
    )
    sources, _ = _run(engine, "when is my deadline?")

    assert service.seen_system_prompts, "the model was never called"
    injected = service.seen_system_prompts[-1]
    markers = set(MARKER.findall(injected))

    assert markers, "context was injected without citation markers"
    assert len(markers) <= len(sources), (
        f"{len(markers)} context chunk(s) injected but only {len(sources)} "
        f"source event(s) emitted — unattributable context reached the reply"
    )


def test_recalled_memories_each_emit_provenance():
    engine, _, _ = _build_engine(["fact one", "fact two", "fact three"])
    sources, _ = _run(engine, "what do you know?")

    assert len(sources) == 3
    assert all(s.data.get("kind") == "memory" for s in sources)
    assert all(s.data.get("url", "").startswith("memory:") for s in sources)


def test_provenance_is_deduplicated():
    """The same record must not be reported twice in one reply.

    Memory is reachable from more than one place in a request, so identical
    sources can be produced more than once.
    """
    engine, _, _ = _build_engine(["only fact"])
    sources, _ = _run(engine, "anything?")

    urls = [s.data.get("url") for s in sources]
    assert len(urls) == len(set(urls)), f"duplicate provenance emitted: {urls}"


def test_no_memory_means_no_injected_context_and_no_sources():
    """With nothing recalled, nothing is injected and nothing is claimed."""
    engine, service, _ = _build_engine(memory_contents=[])
    sources, _ = _run(engine, "hello")

    assert sources == []
    injected = service.seen_system_prompts[-1]
    assert not MARKER.findall(injected), "markers injected with no memories"
    assert "WHAT YOU REMEMBER" not in injected


def test_engine_runs_without_a_memory_runtime():
    """Provenance machinery must not make memory mandatory."""
    engine, service, _ = _build_engine(memory_contents=None)
    sources, tokens = _run(engine, "hello")

    assert sources == []
    assert tokens == "answered"


def test_internal_step_output_never_reaches_the_reply():
    """Internal capabilities gather context; their payloads are not user-facing."""
    assert "knowledge.search" in ExecutionEngine.INTERNAL_CAPABILITIES

    engine, _, _ = _build_engine(["some memory"])
    _, tokens = _run(engine, "hello")

    assert "total_results" not in tokens
    assert not tokens.lstrip().startswith("{")


def test_citation_markers_are_not_leaked_to_the_user():
    """The markers are internal labels; the reply must not contain them.

    The model is instructed not to print them. This guards the instruction
    being dropped from the prompt block.
    """
    engine, service, _ = _build_engine(["a remembered fact"])
    _run(engine, "recall something")

    injected = service.seen_system_prompts[-1]
    assert "Never print the [M1] markers" in injected


def test_exchange_is_stored_after_answering():
    """Recall is only possible if the exchange was committed."""
    engine, _, memory = _build_engine(["prior fact"])
    _run(engine, "a new question")

    assert memory.remembered, "the exchange was never stored"
    assert "a new question" in memory.remembered[0]

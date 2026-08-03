# backend/tests/test_outbound_query_invariant.py
"""The outbound query invariant.

**Nothing derived from the Spine may appear in a query that leaves the machine.**

Recall injects remembered facts into `system_prompt` before planning. If a search
query were ever built from that enriched context — for example by having a model
rewrite the question into better search terms — private memories would be sent to
DuckDuckGo as a side effect of a convenience feature. That is the worst available
failure for this product.

Today the property holds structurally: the planner passes the *raw* user prompt as
the search query, and recalled memories only ever reach `system_prompt`, which the
search path never reads. That is luck, not design. These tests make it deliberate,
so the change that would break it fails here first.

Also covers the gate itself: web search is off by default, and no plan may contain a
step that leaves the machine until the egress log and per-source policy exist.
See the sequencing commitments in CLAUDE.md.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

import pytest

from core.contracts import Capability, RuntimeMetadata, RuntimeState
from core.event_bus import EventBus
from core.execution_engine import ExecutionEngine
from core.planner import IntentPlanner, web_search_enabled
from core.registry import RuntimeRegistry
from core.streaming_events import StreamEvent
from runtimes.memory.contracts import MemoryRecord, MemoryResult, MemoryType

#: A string that exists only in the Spine. If it ever appears in an outbound
#: query, memory has leaked into a network request.
SECRET = "zzq-spine-only-marker-8f2a"

#: Prompts the classifier treats as needing live information. Verified against
#: needs_search() — a prompt it does not match would make these tests vacuous.
SEARCH_PROMPTS = [
    "what is the latest news about the election",
    "what is the current price of bitcoin",
    "current weather in London",
]


@contextmanager
def web_search(enabled: bool):
    """Temporarily set the web search gate."""
    previous = os.environ.get("ZARAM_WEB_SEARCH")
    os.environ["ZARAM_WEB_SEARCH"] = "1" if enabled else "0"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("ZARAM_WEB_SEARCH", None)
        else:
            os.environ["ZARAM_WEB_SEARCH"] = previous


class _RecordingService:
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


class _SpyKnowledgeRuntime:
    """Captures every query the search path is asked to send outbound."""

    def __init__(self):
        self.outbound_queries: list[str] = []

    def get_runtime_id(self):
        return "knowledge"

    def get_metadata(self):
        return RuntimeMetadata(
            runtime_id="knowledge",
            version="1.0.0",
            capabilities=[Capability(id="knowledge.search", runtime_id="knowledge")],
        )

    def get_service(self):
        return self

    def search_knowledge(self, query: str, persona: str = "zaram_prime"):
        self.outbound_queries.append(query)
        yield '{"results": [], "total_results": 0, "providers_consulted": []}'

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    def get_state(self):
        return RuntimeState.READY

    def health_check(self):
        return {"state": "ready"}


class _FakeMemoryRuntime:
    """Returns a memory containing SECRET, so any leak is detectable."""

    def __init__(self):
        self._records = [
            MemoryRecord(
                content=f"The user's private note: {SECRET}",
                memory_type=MemoryType.CONVERSATION,
            )
        ]

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
            MemoryResult(record=r, score=0.95, match_reason="test", rank=i)
            for i, r in enumerate(self._records)
        ]

    async def remember(self, content, **kwargs):
        return "stored-id"

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    def get_state(self):
        return RuntimeState.READY

    def health_check(self):
        return {"state": "ready"}


def _build_engine():
    registry = RuntimeRegistry(EventBus())
    service = _RecordingService()
    knowledge = _SpyKnowledgeRuntime()
    registry.register(_FakeModelsRuntime(service))
    registry.register(knowledge)
    registry.register(_FakeMemoryRuntime())
    return ExecutionEngine(registry, EventBus()), service, knowledge


def _drain(engine, prompt: str):
    for item in engine.execute(prompt, "test-model", ""):
        if isinstance(item, StreamEvent):
            continue


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def test_web_search_is_off_by_default(monkeypatch):
    monkeypatch.delenv("ZARAM_WEB_SEARCH", raising=False)
    assert web_search_enabled() is False


@pytest.mark.parametrize("prompt", SEARCH_PROMPTS)
def test_no_outbound_step_is_planned_while_search_is_off(prompt):
    """A question that wants live information must not produce a network step."""
    with web_search(False):
        plan = IntentPlanner().create_plan(prompt)

    capabilities = [s.capability_id for s in plan.steps]
    assert "knowledge.search" not in capabilities, (
        f"planned an outbound step for {prompt!r} while web search is off: {capabilities}"
    )


@pytest.mark.parametrize("prompt", SEARCH_PROMPTS)
def test_nothing_leaves_the_machine_while_search_is_off(prompt):
    """End to end: no query reaches the search path at all."""
    engine, _, knowledge = _build_engine()
    with web_search(False):
        _drain(engine, prompt)

    assert knowledge.outbound_queries == [], (
        f"query left the machine while search is off: {knowledge.outbound_queries}"
    )


# ---------------------------------------------------------------------------
# The invariant, verified with the gate deliberately open
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prompt", SEARCH_PROMPTS)
def test_spine_content_never_appears_in_an_outbound_query(prompt):
    """Recalled memory must not reach a query that leaves the machine.

    Recall runs first and injects SECRET into the model's context. The search
    query must still be the user's own words.
    """
    engine, service, knowledge = _build_engine()
    with web_search(True):
        _drain(engine, prompt)

    assert knowledge.outbound_queries, "search did not run; the test proves nothing"

    # The memory really was recalled — otherwise this test passes vacuously.
    assert any(SECRET in sp for sp in service.seen_system_prompts), (
        "the Spine was never consulted, so a leak could not have been detected"
    )

    for query in knowledge.outbound_queries:
        assert SECRET not in query, (
            f"Spine content leaked into an outbound query: {query!r}"
        )


@pytest.mark.parametrize("prompt", SEARCH_PROMPTS)
def test_outbound_query_is_exactly_the_user_prompt(prompt):
    """The strongest form: the query is the user's words and nothing else.

    Anything else — a model-rewritten query, an enriched query, a query with
    context appended — is a potential leak channel and must be reviewed here.
    """
    engine, _, knowledge = _build_engine()
    with web_search(True):
        _drain(engine, prompt)

    assert knowledge.outbound_queries == [prompt], (
        "the outbound query is no longer the raw user prompt. If this was "
        "deliberate, the new construction must be proven not to carry Spine "
        "content before this assertion is changed."
    )

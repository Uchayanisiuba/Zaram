"""A turn that offers tools streams; the marker never reaches the screen.

Until 19 September 2026 the execution engine buffered any generation that
might call a tool — `[TOOL_CALL]` arrives split across tokens and cannot be
recognised until the text is accumulated. In a coding project tools are
offered on every turn, so every turn was a blank screen for as long as the
model took, then the whole reply at once: a working reply that read as a hung
one. And each round's prose was replaced by the next round's, so the model's
"I'll read the store first" was generated, paid for, and never seen.

`visible_length` (`core/tool_loop.py`) and `_stream_round`
(`core/execution_engine.py`) replace the buffer with a holdback. Three
contracts, each asserted here against a model that emits three characters at a
time, so that every marker really does arrive in pieces:

1. Prose before a call reaches the user *before* the call's row does.
2. No yielded text ever contains a call marker, whole or in part.
3. Nothing is said twice — what streamed and what was stored agree.

`docs/PLAN.md` A2.
"""

from __future__ import annotations

import pytest

from core.bootstrapper import KernelBootstrapper
from core.contracts import Capability, RuntimeMetadata, RuntimeState
from core.execution_engine import ExecutionEngine
from core.streaming_events import EventType, StreamEvent
from core.tool_loop import TOOL_CALL_MARKER, visible_length
from projects.plans import PlanRecords
from tests.test_the_tool_loop_is_bounded import (  # the doubles, not the contract
    _READ,
    _SEARCH,
    _LocalModels,
    _McpDouble,
    _call,
)

CHUNK = 3


class _DribblingService:
    """A model that says the next scripted thing a few characters at a time."""

    def __init__(self, replies: list[str]):
        self._replies = list(replies)
        self.prompts: list[str] = []

    def generate_response(self, user_text, personality_context="", model=None):
        self.prompts.append(user_text)
        reply = self._replies.pop(0) if self._replies else "I have what I need."
        for i in range(0, len(reply), CHUNK):
            yield reply[i : i + CHUNK]


class _DribblingModel:
    def __init__(self, replies):
        self._service = _DribblingService(replies)

    @property
    def service(self):
        return self._service

    def get_runtime_id(self):
        return "fake-model"

    def get_version(self):
        return "0.0.1"

    def get_metadata(self):
        return RuntimeMetadata(
            runtime_id="fake-model",
            version="0.0.1",
            priority="normal",
            capabilities=[Capability(id="reasoning.generate", runtime_id="fake-model")],
        )

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    def get_state(self):
        return RuntimeState.READY

    def health_check(self):
        return {"state": "ready"}

    def get_service(self):
        return self._service


@pytest.fixture
def engine_with(tmp_path):
    def build(replies, mcp):
        kernel = KernelBootstrapper()
        model = _DribblingModel(replies)
        kernel.registry.register(model)
        kernel.registry.register(mcp)
        kernel.registry.register(_LocalModels())
        engine = ExecutionEngine(kernel.registry, kernel.event_bus)
        engine.set_tool_vocabulary(mcp.server_names)
        engine.set_plan_records(PlanRecords(str(tmp_path / "plans.db")))
        return engine, model

    return build


def _ordered(items):
    """Text pieces and tool rows, in the order they were yielded."""
    out = []
    for item in items:
        if isinstance(item, str):
            out.append(("text", item))
        elif isinstance(item, StreamEvent) and item.type is EventType.TOOL_CALL:
            out.append(("row", item.data.get("tool")))
    return out


class TestTheHoldback:
    def test_shows_everything_that_cannot_be_a_marker(self):
        assert visible_length("hello") == 5
        assert visible_length("a < b") == 5
        assert visible_length("<think>x</think>ok") == 18

    def test_withholds_only_a_possible_opener(self):
        assert visible_length("hello [") == 6
        assert visible_length("hello [TOOL") == 6
        assert visible_length("a <t") == 2
        # Released the moment the next character settles it.
        assert visible_length("hello [x") == 8
        assert visible_length("a <th") == 5

    def test_stops_at_a_complete_opener(self):
        assert visible_length("hello [TOOL_CALL] {}") == 6
        assert visible_length("hi <tool_call><function=a>") == 3

    def test_never_raises(self):
        assert visible_length("") == 0
        assert visible_length(None) == 0  # type: ignore[arg-type]


class TestATurnWithToolsStreams:
    def test_prose_arrives_before_the_row_and_the_marker_never_does(self, engine_with):
        mcp = _McpDouble(
            tools=[_SEARCH, _READ],
            results=[
                {"success": True, "result": {"matches": [{"path": "a.py"}]}},
                {"success": True, "result": {"lines": "def f(): pass"}},
            ],
        )
        engine, model = engine_with(
            [
                "I'll search first.\n" + _call("search_code", query="f"),
                "Found it; reading.\n" + _call("read_lines", path="a.py", start_line=1, end_line=5),
                "The function does nothing. Done.",
            ],
            mcp,
        )

        out = list(engine.execute("use the code tools to look at f"))
        ordered = _ordered(out)

        # 1. The narration before each call precedes that call's row.
        texts_before_first_row = "".join(
            t for kind, t in ordered[: ordered.index(("row", "search_code"))] if kind == "text"
        )
        assert "I'll search first." in texts_before_first_row

        between = ordered[ordered.index(("row", "search_code")) : ordered.index(("row", "read_lines"))]
        assert "Found it; reading." in "".join(t for k, t in between if k == "text")

        # It streamed: many small pieces, not one.
        assert sum(1 for k, _ in ordered if k == "text") > 6

        # 2. No marker, whole or partial, in anything shown.
        shown = "".join(t for k, t in ordered if k == "text")
        assert TOOL_CALL_MARKER not in shown
        assert "[TOOL" not in shown and "<tool_call>" not in shown
        assert "The function does nothing. Done." in shown

        # 3. Nothing twice: the stored answer is exactly what was shown.
        assert shown.count("I'll search first.") == 1
        assert shown.count("Found it; reading.") == 1
        assert shown.count("Done.") == 1

    def test_a_reply_that_is_only_a_call_shows_no_text_before_its_row(self, engine_with):
        mcp = _McpDouble(
            tools=[_SEARCH],
            results=[{"success": True, "result": {"matches": []}}],
        )
        engine, _ = engine_with(
            [
                TOOL_CALL_MARKER + ' {"server": "code", "tool": "search_code", "arguments": {"query": "x"}}\n',
                "Nothing there.",
            ],
            mcp,
        )
        # "tell me about", not "find": a "find x" classifies as a search and
        # takes the search plan, where no tool is offered at all.
        ordered = _ordered(list(engine.execute("use the code tools to tell me about x")))
        first_row = ordered.index(("row", "search_code"))
        assert "".join(t for k, t in ordered[:first_row] if k == "text").strip() == ""
        assert "Nothing there." in "".join(t for k, t in ordered if k == "text")

    def test_a_system_prefix_is_never_typed_onto_the_screen(self, engine_with):
        """A `[FALLBACK]` from the dispatcher is the system speaking and is
        turned into a notice by the step-failure path; the holdback must not
        show it as prose first because it happens to start with `[`."""
        mcp = _McpDouble(tools=[_SEARCH], results=[])
        engine, _ = engine_with(["[FALLBACK] reasoning.generate failed: nothing"], mcp)
        out = list(engine.execute("use the code tools to tell me about x"))
        assert not any(isinstance(i, str) and "[FALLBACK]" in i for i in out)

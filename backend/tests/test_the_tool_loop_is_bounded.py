"""The model may call more than one tool, and something has to stop it.

`MAX_TOOL_ROUNDS` was 1 until 6 September 2026, which meant the model could
`search_code` **or** `read_lines` and never *search then read what it found* —
the minimum useful sequence for a coding agent, and the one thing a person
coming from Claude Code or Aider would notice missing in the first minute.

What replaces it is a budget rather than a counter, and these are the four
claims that makes:

**It hands over at half the window, and it does so silently.** The trigger is
the measured size of the request being sent, against `ContextBudget.handoff_tokens`
— half the context the answering model was actually loaded with — so an 8K local
model and a 64K remote one behave the same way at different sizes. A round
counter gives them the same allowance and is wrong for both. Nothing is
announced, because a task that carried itself on and finished has not failed;
half a window re-sent is also a cheaper request than a full one, which is how
this protects a metered bill without asking anybody anything.

**The gate runs on every call.** More rounds must never become one permission
decision reused — that is "a shortlisted tool has earned nothing", the
distinction `CLAUDE.md` records paying for three times.

**A full window is not the end of the task.** It carries itself into a fresh one
— `MAX_AUTO_CONTINUATIONS` times, by the maintainer's decision: *"have it
continue till the task is done."* Bounded, because "done" is the model's
judgement and could be never; and every carry-on is announced, because a reply
that quietly spent four windows is the silent-degradation failure pointing
upward. When the allowance runs out the loop closes and offers the manual
Continue, which is the fallback rather than the route.

**Continuing carries what was found, never what was said.** Rule 7d: session
state and long-term memory are separate stores, and persisting raw dialogue to
survive a context limit is the L0 store the patterns section rejects outright.
The turns are the evidence; the model's prose between them is working state.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from core.bootstrapper import KernelBootstrapper
from core.contracts import Capability, RuntimeMetadata, RuntimeState
from core.execution_engine import ExecutionEngine
from core.streaming_events import EventType, StreamEvent
from core.tool_loop import (
    MAX_AUTO_CONTINUATIONS,
    MAX_TOOL_ROUNDS,
    TOOL_CALL_MARKER,
)
from runtimes.mcp.runtime import CALL, LIST_TOOLS

# --------------------------------------------------------------------- doubles


class _Service:
    """A model that says the next scripted thing, and records what it was asked."""

    def __init__(self, replies: list[str]):
        self._replies = list(replies)
        self.prompts: list[str] = []
        self.systems: list[str] = []

    def generate_response(self, user_text, personality_context="", model=None):
        self.prompts.append(user_text)
        self.systems.append(personality_context)
        yield self._replies.pop(0) if self._replies else "I have what I need."


class _ModelRuntime:
    def __init__(self, replies: list[str]):
        self._service = _Service(replies)

    @property
    def service(self) -> _Service:
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


class _McpDouble:
    """`McpRuntime`, with a different answer for each call.

    It does not re-implement `policy.decide`; `decisions` is what the gate is
    told to have said. What is under test is that the engine asks it every time,
    which `calls` records.
    """

    def __init__(self, tools=None, results: list[dict] | None = None, servers=("code",)):
        self._tools = tools if tools is not None else []
        self._servers = list(servers)
        self._results = list(results or [])
        self.calls: list[dict] = []

    def server_names(self):
        return list(self._servers)

    def get_runtime_id(self):
        return "mcp"

    def get_version(self):
        return "0.1.0"

    def get_metadata(self):
        return RuntimeMetadata(
            runtime_id="mcp",
            version="0.1.0",
            priority="normal",
            capabilities=[
                Capability(id=LIST_TOOLS, runtime_id="mcp"),
                Capability(id=CALL, runtime_id="mcp"),
            ],
        )

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    def get_state(self):
        return RuntimeState.READY

    def health_check(self):
        return {"state": "ready"}

    async def execute(self, capability_id, input_data):
        if capability_id == LIST_TOOLS:
            return {"success": True, "tools": self._tools}
        self.calls.append(dict(input_data))
        if self._results:
            return self._results.pop(0)
        return {"success": True, "result": {"ok": True}}


_SEARCH = {
    "server": "code",
    "name": "search_code",
    "description": "Find where text appears in the project.",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
    "provenance": "tool_output",
    "suspicions": [],
}

_READ = {
    "server": "code",
    "name": "read_lines",
    "description": "Read a range of lines from one file.",
    "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string"}, "start_line": {"type": "integer"}},
        "required": ["path"],
    },
    "provenance": "tool_output",
    "suspicions": [],
}


def _call(tool: str, **arguments: Any) -> str:
    payload = json.dumps({"server": "code", "tool": tool, "arguments": arguments})
    return f"Working on it.\n{TOOL_CALL_MARKER} {payload}\n"


class _LocalModels:
    """The models runtime, saying every model runs here.

    Present because `_auto_continuations_for` asks it whether carrying a task on
    would spend the user's money. Without it every model is unresolvable, which
    is deliberately treated as metered — correct behaviour, and the wrong
    fixture for a file about the loop's own limits.
    `test_an_unfinished_task_survives_a_restart.py` is where that answer is
    tested.
    """

    def get_runtime_id(self):
        return "models"

    def get_version(self):
        return "0.0.1"

    def get_metadata(self):
        return RuntimeMetadata(
            runtime_id="models", version="0.0.1", priority="normal", capabilities=[]
        )

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    def get_state(self):
        return RuntimeState.READY

    def health_check(self):
        return {"state": "ready"}

    def locality_of(self, model):
        return "local"


#: The plan store every engine in this file gets, replaced per test.
#:
#: A module global rather than a parameter because `_engine` is called from
#: twenty places that do not care where a stopped task is written, and threading
#: a fixture through all of them would put the least interesting fact in this
#: file into every one of its tests.
_STORE = None


@pytest.fixture(autouse=True)
def _a_store_per_test(tmp_path):
    from projects.plans import PlanRecords

    global _STORE
    _STORE = PlanRecords(str(tmp_path / "plans.db"))
    yield
    _STORE = None


def _engine(replies, mcp: _McpDouble):
    kernel = KernelBootstrapper()
    model = _ModelRuntime(replies)
    kernel.registry.register(model)
    kernel.registry.register(mcp)
    kernel.registry.register(_LocalModels())
    engine = ExecutionEngine(kernel.registry, kernel.event_bus)
    engine.set_tool_vocabulary(mcp.server_names)
    engine.set_plan_records(_STORE)
    return engine, model


def _text(items) -> str:
    return "".join(i for i in items if isinstance(i, str))


def _events(items, kind) -> list[StreamEvent]:
    return [i for i in items if isinstance(i, StreamEvent) and i.type is kind]


@pytest.fixture
def a_generous_window(monkeypatch):
    """A window big enough that only the test's own limits stop the loop.

    Patched rather than mocked at the HTTP layer: `budget_for` reads `/api/ps`,
    and a suite that depends on a resident model is a suite that measures the
    machine it happens to run on.
    """
    from core import execution_engine
    from core.context_budget import ContextBudget

    # Patched where the engine reads it — `_budget_for` imports from
    # `core.context_budget` at call time (13 September), so a patch on the
    # engine module alone pins nothing, and this fixture had been a no-op.
    import core.context_budget as context_budget

    pinned = lambda model=None, **kw: ContextBudget(  # noqa: E731
        total_tokens=32768, measured=True, reply_reserve_tokens=8192
    )
    monkeypatch.setattr(execution_engine, "budget_for", pinned)
    monkeypatch.setattr(context_budget, "budget_for", pinned)


#: A result large enough that a couple of them cross the handoff line, and small
#: enough that one of them still fits the carry. Both halves matter: a task that
#: hands over must have something to hand over.
_A_BIG_RESULT = {"lines": ["x" * 300]}


@pytest.fixture
def a_tiny_window(monkeypatch):
    """A window small enough that a couple of results trip the handoff.

    600 tokens: 300 before the task compacts itself, 150 it may carry into the
    next window.
    """
    from core import execution_engine
    from core.context_budget import ContextBudget

    import core.context_budget as context_budget

    pinned = lambda model=None, **kw: ContextBudget(  # noqa: E731
        total_tokens=600, measured=True, reply_reserve_tokens=150
    )
    monkeypatch.setattr(execution_engine, "budget_for", pinned)
    monkeypatch.setattr(context_budget, "budget_for", pinned)


class TestItCanSequenceTwoCalls:
    def test_the_model_searches_then_reads_what_it_found(self, a_generous_window):
        """The sequence a single round made impossible."""
        mcp = _McpDouble(
            tools=[_SEARCH, _READ],
            results=[
                {"success": True, "result": {"matches": [{"path": "core/residency.py", "line": 8}]}},
                {"success": True, "result": {"lines": [{"line": 12, "text": "return 9137000000"}]}},
            ],
        )
        engine, _ = _engine(
            [
                _call("search_code", query="resident_budget_bytes"),
                _call("read_lines", path="core/residency.py", start_line=8),
                "It returns 9137000000, at core/residency.py:12.",
            ],
            mcp,
        )

        out = list(engine.execute("use the code tools to tell me what resident_budget_bytes returns"))

        assert [c["tool"] for c in mcp.calls] == ["search_code", "read_lines"]
        assert "9137000000" in _text(out)

    def test_the_loops_time_is_in_the_timing_event(self, a_generous_window):
        """Seen 20 September 2026: a 240 s reply whose *where the time went*
        summed to 30 s — everything after the first round (the tool calls,
        and the model rounds that followed them) landed in no phase. Two
        calls and two later rounds here; both phases must be measured, and
        absent on a reply that called nothing."""
        mcp = _McpDouble(
            tools=[_SEARCH, _READ],
            results=[
                {"success": True, "result": {"matches": [{"path": "a.py", "line": 1}]}},
                {"success": True, "result": {"lines": [{"line": 1, "text": "x = 1"}]}},
            ],
        )
        engine, _ = _engine(
            [_call("search_code", query="x"), _call("read_lines", path="a.py"), "x is 1."],
            mcp,
        )

        out = list(engine.execute("use the code tools to tell me about x"))

        timing = _events(out, EventType.TIMING)[0].data
        assert isinstance(timing["tools_ms"], int) and timing["tools_ms"] >= 0
        assert isinstance(timing["rounds_ms"], int) and timing["rounds_ms"] >= 0

        engine, _ = _engine(["Nothing to call."], _McpDouble(tools=[_SEARCH]))
        out = list(engine.execute("say hello"))
        timing = _events(out, EventType.TIMING)[0].data
        assert timing["tools_ms"] is None and timing["rounds_ms"] is None

    def test_a_confirm_card_names_the_file_zaram_just_wrote(self, a_generous_window):
        """Coworker step 2 — provenance on the card. Nobody at the card sees
        the test file's contents, but the engine knows it wrote it a step
        ago, and says so in one line of fixed vocabulary."""
        mcp = _McpDouble(
            tools=[_SEARCH, _READ],
            results=[
                {"success": True, "result": {"path": "tests/test_a.py", "diff": "+x", "commit": "abc"}},
                {"success": False, "needs_confirmation": True, "server": "code", "tool": "run_command",
                 "reason": "run_command changes something.", "grantable": True},
            ],
        )
        engine, _ = _engine(
            [
                _call("write_file", path="tests/test_a.py", content="def test_a(): pass"),
                _call("run_command", runner="pytest", args=["tests/test_a.py"]),
                "Done.",
            ],
            mcp,
        )

        out = list(engine.execute("use the code tools to add a test and run it"))

        held = [e for e in _events(out, EventType.TOOL_CALL) if e.data.get("verdict") == "confirm"]
        assert held, "the run was not held for confirmation"
        assert "tests/test_a.py was created by Zaram 1 step ago" in held[0].data["reason"]

    def test_the_gate_is_asked_on_every_call(self, a_generous_window):
        """Two calls are two permission decisions, never one reused."""
        mcp = _McpDouble(tools=[_SEARCH, _READ])
        engine, _ = _engine(
            [
                _call("search_code", query="x"),
                _call("read_lines", path="a.py"),
                "Done.",
            ],
            mcp,
        )

        list(engine.execute("use the code tools to tell me about x"))

        assert len(mcp.calls) == 2
        # `confirmed` is present and False on an ordinary run — see the note
        # in `test_the_engine_never_sets_confirmed_itself`. What must never
        # happen is a *true* the model asked for.
        assert all(call.get("confirmed") is False for call in mcp.calls), (
            "the loop must never mark a call confirmed on the model's behalf"
        )

    def test_the_second_prompt_carries_the_first_result(self, a_generous_window):
        """A model that searched then read has to answer from both."""
        mcp = _McpDouble(
            tools=[_SEARCH, _READ],
            results=[
                {"success": True, "result": {"matches": [{"path": "core/residency.py"}]}},
                {"success": True, "result": {"lines": ["return 1"]}},
            ],
        )
        engine, model = _engine(
            [_call("search_code", query="x"), _call("read_lines", path="a.py"), "Done."],
            mcp,
        )

        list(engine.execute("use the code tools to tell me about x"))

        assert "core/residency.py" in model.service.prompts[-1]

    def test_the_marker_never_reaches_the_user(self, a_generous_window):
        """Measured: told not to call another tool, a model may call one anyway.

        So the terminal generation is stripped rather than trusted.
        """
        mcp = _McpDouble(tools=[_SEARCH])
        engine, _ = _engine(
            [
                _call("search_code", query="x"),
                "Here is what I found." + _call("read_lines", path="a.py"),
                "Done.",
            ],
            mcp,
        )

        out = list(engine.execute("use the code tools to tell me about x"))

        assert TOOL_CALL_MARKER not in _text(out)


class TestItHandsOverToItself:
    """A full window is a fact about the model, not about the task.

    At half the window the task compacts itself and carries on — the maintainer's
    call twice over: *"have it continue till the task is done"*, and then *"do
    the handoff behind the scenes so the UI stays fluid and seamless"*.
    """

    def test_the_task_keeps_going_past_the_handoff(self, a_tiny_window):
        mcp = _McpDouble(
            tools=[_SEARCH, _READ],
            results=[{"success": True, "result": _A_BIG_RESULT}] * 4,
        )
        engine, _ = _engine(
            [
                _call("search_code", query="x"),
                _call("read_lines", path="a.py"),
                _call("read_lines", path="b.py"),
                "Done.",
            ],
            mcp,
        )

        list(engine.execute("use the code tools to tell me about x"))

        assert [c["tool"] for c in mcp.calls] == [
            "search_code",
            "read_lines",
            "read_lines",
        ]

    def test_the_handoff_is_silent(self, a_tiny_window):
        """No prompt, no status line, no interruption.

        The task did not fail — it compacted itself and carried on — and four
        bookkeeping notices in one reply is noise rather than disclosure. The
        stop at the end of the allowance still speaks; this does not.
        """
        mcp = _McpDouble(
            tools=[_SEARCH, _READ],
            results=[{"success": True, "result": _A_BIG_RESULT}] * 4,
        )
        engine, _ = _engine(
            [
                _call("search_code", query="x"),
                _call("read_lines", path="a.py"),
                _call("read_lines", path="b.py"),
                "Done.",
            ],
            mcp,
        )

        out = list(engine.execute("use the code tools to tell me about x"))

        assert not [
            n
            for n in _events(out, EventType.NOTICE)
            if n.data.get("kind") == "tool_loop"
        ], "a task that carried on and finished has nothing to announce"

    def test_it_stops_eventually_and_offers_to_pick_it_up(self, a_tiny_window):
        """Bounded, because 'done' is the model's judgement and could be never."""
        mcp = _McpDouble(
            tools=[_SEARCH],
            results=[{"success": True, "result": _A_BIG_RESULT}] * 40,
        )
        engine, _ = _engine([_call("search_code", query=f"q{i}") for i in range(40)], mcp)

        out = list(engine.execute("use the code tools to tell me about x"))

        assert len(mcp.calls) < 40, "a model that never answers must still be stopped"
        assert len(mcp.calls) <= MAX_TOOL_ROUNDS * (1 + MAX_AUTO_CONTINUATIONS)
        notices = [n for n in _events(out, EventType.NOTICE) if n.data.get("kind") == "tool_loop"]
        assert notices[-1].data["action"] == "continue"
        assert "stopped" in notices[-1].data["content"]


class TestSomethingStopsIt:
    def test_a_verbatim_repeat_stops_it(self, a_generous_window):
        """Its result is already in the prompt, and an empty one costs nothing.

        This is the case a token budget cannot catch: a tool that returns almost
        nothing never fills a budget, so a model asking for it forever would
        loop until something else stopped it.
        """
        mcp = _McpDouble(tools=[_SEARCH], results=[{"success": True, "result": {"matches": []}}] * 5)
        engine, _ = _engine([_call("search_code", query="x")] * 5 + ["Nothing found."], mcp)

        list(engine.execute("use the code tools to tell me about x"))

        assert len(mcp.calls) == 1

    def test_a_repeat_after_a_change_is_progress_not_a_loop(self, a_generous_window):
        """Measured 12 September: a model fixing a failing test ran
        `run_command(pytest)` before and after its edit with identical
        arguments. The second run is the confirmation, and the guard written
        for reads was stopping the loop on it."""
        run = {"server": "code", "name": "run_command", "description": "run", "input_schema": {}}
        edit = {"server": "code", "name": "edit_file", "description": "edit", "input_schema": {}}
        mcp = _McpDouble(
            tools=[run, edit],
            results=[
                {"success": True, "result": {"ok": False, "output": "1 failed"}},
                {"success": True, "result": {"commit": "abc"}},
                {"success": True, "result": {"ok": True, "output": "1 passed"}},
            ],
        )
        engine, _ = _engine(
            [
                _call("run_command", runner="pytest"),
                _call("edit_file", path="calc.py", find="-", replace="+"),
                _call("run_command", runner="pytest"),
                "Fixed, and the tests pass.",
            ],
            mcp,
        )

        list(engine.execute("use the code tools to fix the failing test"))

        # The fourth call is the loop's own: a write happened this reply, so
        # the project's check runs once before "done" (14 September). Here it
        # passes — the double answers `ok` — and is silent.
        assert [c["tool"] for c in mcp.calls] == ["run_command", "edit_file", "run_command", "run_command"]
        assert mcp.calls[-1]["arguments"] == {"runner": "check"}

    def test_a_repeat_after_only_reads_still_stops_it(self, a_generous_window):
        run = {"server": "code", "name": "run_command", "description": "run", "input_schema": {}}
        mcp = _McpDouble(
            tools=[run, _READ],
            results=[
                {"success": True, "result": {"ok": False}},
                {"success": True, "result": {"lines": []}},
                {"success": True, "result": {"ok": False}},
            ],
        )
        engine, _ = _engine(
            [
                _call("run_command", runner="pytest"),
                _call("read_lines", path="calc.py"),
                _call("run_command", runner="pytest"),
                "Still failing.",
            ],
            mcp,
        )

        list(engine.execute("use the code tools to fix the failing test"))

        assert [c["tool"] for c in mcp.calls] == ["run_command", "read_lines"]

    def test_the_round_ceiling_bounds_a_window_and_the_carry_ons_bound_the_task(
        self, a_generous_window
    ):
        """Varying the query each time defeats the repeat guard; this catches it.

        A tool returning `{"matches": []}` costs about five tokens, so no token
        budget will ever stop this — the per-window ceiling does, and the
        continuation allowance stops it carrying on for ever.
        """
        total = MAX_TOOL_ROUNDS * (1 + MAX_AUTO_CONTINUATIONS)
        mcp = _McpDouble(
            tools=[_SEARCH],
            results=[{"success": True, "result": {"matches": []}}] * (total + 5),
        )
        engine, _ = _engine(
            [_call("search_code", query=f"q{i}") for i in range(total + 5)], mcp
        )

        list(engine.execute("use the code tools to tell me about x"))

        assert len(mcp.calls) == total


class TestPermissionStopsItAndFailureDoesNot:
    def test_a_refusal_ends_the_loop(self, a_generous_window):
        """Looping past a refusal would let the model shop for a permitted tool."""
        mcp = _McpDouble(
            tools=[_SEARCH, _READ],
            results=[{"success": False, "refused": True, "reason": "writes are not granted"}],
        )
        engine, _ = _engine(
            [_call("read_lines", path="a.py"), _call("search_code", query="x"), "Done."],
            mcp,
        )

        out = list(engine.execute("use the code tools to tell me about a.py"))

        assert len(mcp.calls) == 1
        assert "refused" in _text(out)

    def test_a_pending_confirmation_ends_the_loop(self, a_generous_window):
        mcp = _McpDouble(
            tools=[_READ],
            results=[{"success": False, "needs_confirmation": True, "reason": "it writes"}],
        )
        engine, _ = _engine([_call("read_lines", path="a.py"), "Done."], mcp)

        out = list(engine.execute("use the code tools to tell me about a.py"))

        assert len(mcp.calls) == 1
        assert "say-so" in _text(out)

    def test_a_failed_call_is_handed_back_so_the_model_can_fix_it(self, a_generous_window):
        """The measured case: an invented argument name, corrected next round.

        A tool that ran and failed is the model's mistake to fix, and a second
        round is what a loop is *for*. Ending here would make the commonest
        recoverable error unrecoverable.
        """
        mcp = _McpDouble(
            tools=[_READ],
            results=[
                {"success": False, "error": "read_lines does not take start. Its arguments are: path, start_line."},
                {"success": True, "result": {"lines": ["return 1"]}},
            ],
        )
        engine, model = _engine(
            [
                _call("read_lines", path="a.py", start=8),
                _call("read_lines", path="a.py", start_line=8),
                "It returns 1.",
            ],
            mcp,
        )

        out = list(engine.execute("use the code tools to tell me about a.py"))

        assert len(mcp.calls) == 2
        assert "does not take start" in model.service.prompts[-1]
        assert "It returns 1." in _text(out)


class TestContinuing:
    """The manual Continue, which is now the *fallback* rather than the route.

    A task carries itself on `MAX_AUTO_CONTINUATIONS` times without being asked.
    These are about what happens after that: the user is offered one more push,
    and taking it resumes from the same place with the same evidence.
    """

    def _exhausted(self, mcp_results, replies, extra_replies=()):
        """A loop that has spent its automatic continuations and parked."""
        mcp = _McpDouble(tools=[_SEARCH, _READ], results=list(mcp_results))
        engine, model = _engine(list(replies) + list(extra_replies), mcp)
        list(engine.execute("use the code tools to tell me what it returns"))
        return engine, model, mcp

    def test_a_stopped_loop_can_be_continued(self, a_tiny_window):
        windows = 1 + MAX_AUTO_CONTINUATIONS
        engine, _, mcp = self._exhausted(
            [{"success": True, "result": {"matches": [{"path": "core/residency.py"}], "context": "x" * 360}}]
            * windows
            + [{"success": True, "result": {"lines": ["return 9137000000"]}}],
            [_call("search_code", query=f"q{i}") for i in range(windows)],
            [
                # The terminal answer when it gave up, then what it does when
                # the user pushes it on, then the answer that push earns.
                "I found the file but have not read it yet.",
                _call("read_lines", path="core/residency.py"),
                "It returns 9137000000.",
            ],
        )
        assert engine.has_continuation("default")

        out = list(engine.continue_task("default"))

        assert [c["tool"] for c in mcp.calls][-1] == "read_lines"
        assert "9137000000" in _text(out)

    def test_the_continuation_is_offered_only_once_it_has_stopped(self, a_tiny_window):
        """Nothing is parked while the task is still carrying itself on."""
        mcp = _McpDouble(
            tools=[_SEARCH],
            results=[{"success": True, "result": _A_BIG_RESULT}] * 2,
        )
        engine, _ = _engine(
            [_call("search_code", query="a"), _call("search_code", query="b"), "Done."],
            mcp,
        )

        list(engine.execute("use the code tools to tell me what it returns"))

        assert not engine.has_continuation("default")

    def test_continuing_carries_the_results_and_not_the_prose(self, a_tiny_window):
        """Rule 7d, asserted rather than described.

        What survives is what the tools returned. The model's own sentences
        between calls are session state, and persisting those to survive a
        context limit is the L0 store `CLAUDE.md` rejects by name.
        """
        windows = 1 + MAX_AUTO_CONTINUATIONS
        engine, model, _ = self._exhausted(
            [{"success": True, "result": {"matches": [{"path": "core/residency.py"}], "context": "x" * 360}}]
            * windows,
            [_call("search_code", query=f"q{i}") for i in range(windows)],
            ["Let me think about this one for a while.", "Done."],
        )

        list(engine.continue_task("default"))

        resumed = model.service.prompts[-1]
        assert "core/residency.py" in resumed
        assert "Let me think about this one" not in resumed

    def test_a_finished_loop_leaves_nothing_to_continue(self, a_generous_window):
        mcp = _McpDouble(tools=[_SEARCH])
        engine, _ = _engine([_call("search_code", query="x"), "Found it."], mcp)

        list(engine.execute("use the code tools to tell me about x"))

        assert not engine.has_continuation("default")

    def test_continuing_nothing_says_the_offer_has_expired(self):
        """The ordinary case after a restart. It must not read as a fault."""
        engine, _ = _engine(["unused"], _McpDouble())

        out = list(engine.continue_task("nobody"))

        assert _events(out, EventType.NOTICE)
        assert "nothing to continue" in _text(
            [n.data["content"] for n in _events(out, EventType.NOTICE)]
        )

    def test_it_is_resumed_once(self, a_tiny_window):
        """Consumed on resume, so a second Continue does not replay the first."""
        windows = 1 + MAX_AUTO_CONTINUATIONS
        engine, _, _ = self._exhausted(
            [{"success": True, "result": {"matches": ["a"], "context": "x" * 360}}] * windows,
            [_call("search_code", query=f"q{i}") for i in range(windows)],
            ["Stopped.", "Finished."],
        )

        list(engine.continue_task("default"))

        assert not engine.has_continuation("default")


class TestTheButtonReachesTheLoop:
    """Registering is not reaching. The press has to arrive at `continue_task`.

    Fifteen complete, tested, unreachable subsystems is this repository's base
    rate, and a Continue button wired to nothing would be the sixteenth — it
    would look right on screen, stream an ordinary reply, and quietly answer the
    word "Continue" as though it were a question.
    """

    def test_the_request_carries_the_flag(self):
        from main import ChatRequest

        assert ChatRequest(text="Continue", continue_task=True).continue_task is True
        assert ChatRequest(text="hello").continue_task is False

    @pytest.mark.asyncio
    async def test_resume_asks_the_engine_to_continue_and_not_to_answer(self):
        from core.chat_router import ChatRouter

        class _Engine:
            def __init__(self):
                self.continued: list[tuple[str, str]] = []
                self.executed: list[str] = []

            def continue_task(self, session_id="default", model=None, **kwargs):
                self.continued.append((session_id, model))
                yield "picked it up"

            def execute(self, *args, **kwargs):
                self.executed.append(args[0] if args else "")
                yield "a new answer"

        engine = _Engine()
        router = ChatRouter(engine, event_bus=None, legacy_generator_func=None)

        frames = [
            frame
            async for frame in router.route(
                "Continue", "a-model", session_id="s1", resume=True
            )
        ]

        assert engine.continued == [("s1", "a-model")]
        assert engine.executed == [], "a continuation must not ask a new question"
        assert any("picked it up" in frame for frame in frames)


class TestTheProjectChecksTheChangeBeforeDone:
    """A change the model calls finished is one the type checker has not
    seen. With a write in the reply and a check in the project, the loop runs
    `check` before finishing: a pass is silent, a failure is one more turn
    with the places named, the fix is checked once more, and a "done" after
    two failures is accepted — the person is needed, not a third lap."""

    _EDIT = {"server": "code", "name": "edit_file", "description": "edit", "input_schema": {}}
    _RUN = {"server": "code", "name": "run_command", "description": "run", "input_schema": {}}

    def test_a_failed_check_earns_one_more_turn_and_no_more(self, a_generous_window):
        mcp = _McpDouble(
            tools=[self._EDIT, self._RUN],
            results=[
                {"success": True, "result": {"commit": "abc"}},
                # The loop's own check, failing, with where.
                {"success": True, "result": {
                    "runner": "npm:typecheck", "ok": False, "exit_code": 2,
                    "output": "src/a.ts(3,5): error TS2322",
                    "locations": [{"file": "src/a.ts", "line": 3, "column": 5}],
                }},
                {"success": True, "result": {"commit": "def"}},
                # The fix, checked once more and still failing: accepted, not a third lap.
                {"success": True, "result": {"runner": "npm:typecheck", "ok": False, "output": "still"}},
                # A third edit would not be checked again; nothing more is consumed.
            ],
        )
        engine, model = _engine(
            [
                _call("edit_file", path="src/a.ts", find="x", replace="y"),
                "Done.",
                _call("edit_file", path="src/a.ts", find="y", replace="z"),
                "Done again.",
                "I could not satisfy the type checker; the remaining error is in a.ts line 3.",
            ],
            mcp,
        )

        out = list(engine.execute("use the code tools to rename x to z"))

        tools = [c["tool"] for c in mcp.calls]
        assert tools == ["edit_file", "run_command", "edit_file", "run_command"]
        assert mcp.calls[1]["arguments"] == {"runner": "check"}
        assert mcp.calls[3]["arguments"] == {"runner": "check"}
        assert "could not satisfy" in _text(out)
        # Until 19 September 2026 this asserted that neither "Done." reached
        # the user — the loop buffered each round and spoke only the last.
        # Tool turns stream now (`_stream_round`), so a "done" the checker
        # then refutes has already been read, exactly as it is in Claude Code:
        # the prose, then the failed check as a row, then the fix. What must
        # still hold is that the *final* word is the honest one and that
        # every round reached the screen in order.
        text = _text(out)
        assert text.index("Done.") < text.index("Done again.") < text.index("could not satisfy")
        # The model was told why it got another turn, with the place named.
        told = [p for p in model.service.prompts if "did not pass" in p]
        assert len(told) >= 2 and "src/a.ts" in told[0]

    def test_nothing_written_means_nothing_checked(self, a_generous_window):
        mcp = _McpDouble(tools=[_SEARCH], results=[{"success": True, "result": {"matches": []}}])
        engine, _ = _engine([_call("search_code", query="x"), "Nothing to change."], mcp)
        list(engine.execute("use the code tools to tell me what x returns"))
        assert [c["tool"] for c in mcp.calls] == ["search_code"]

    def test_a_refused_or_unconfirmed_check_is_skipped_in_silence(self, a_generous_window):
        mcp = _McpDouble(
            tools=[self._EDIT, self._RUN],
            results=[
                {"success": True, "result": {"commit": "abc"}},
                {"success": False, "needs_confirmation": True, "reason": "runs are not allowed here yet"},
            ],
        )
        engine, _ = _engine([_call("edit_file", path="a.py", find="x", replace="y"), "Done."], mcp)
        out = list(engine.execute("use the code tools to change x"))
        assert "Done." in _text(out)
        assert not any("say-so" in s for s in out if isinstance(s, str))

    def test_a_project_with_no_check_finishes_as_before(self, a_generous_window):
        mcp = _McpDouble(
            tools=[self._EDIT, self._RUN],
            results=[
                {"success": True, "result": {"commit": "abc"}},
                {"success": False, "error": "no check runner"},
            ],
        )
        engine, _ = _engine([_call("edit_file", path="a.py", find="x", replace="y"), "Done."], mcp)
        assert "Done." in _text(list(engine.execute("use the code tools to change x")))

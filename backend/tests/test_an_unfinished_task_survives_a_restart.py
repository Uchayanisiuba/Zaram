"""Stop on Tuesday, carry on Thursday — without writing a handoff by hand.

The tool loop could already carry a task across windows, and everything it knew
died with the process. That is fine for *"press Continue under the reply"* and
useless for the thing the maintainer actually asked for: not having to
re-explain a task to a fresh session.

So the task is written down. `CLAUDE.md` assigns that object to **Project** —
*"the steps, decisions taken and decisions rejected"* — and `projects/records.py`
predicted the file it lives in: *"everything a project appears to contain
(artifacts, facts, later a plan) lives in its own store and points back here by
id"*.

Four claims are asserted here, and three of them are rules rather than features.

**It holds what the tools returned, never what was said.** Rule 7d, and the
patterns section rejecting L0 by name.

**It holds no system prompt, so rule 4 keeps working.** A stored context would
freeze whatever recall found on Tuesday, and a fact the user corrected on
Wednesday would come back to life inside a task they had forgotten about. The
resumed task re-recalls instead; its context is rebuilt, not replayed.

**It expires.** Seven days for an unfinished task, and a finished one is deleted
outright — the answer is in the conversation and the steps have done their job.
*"No new store ships without an answer to how long it keeps things."*

**A metered model behaves exactly like a local one.** An earlier version of this
file asserted the opposite — a cloud model stopped at the first full window and
asked — and the maintainer rejected it: *"I don't want Zaram to keep prompting
users… optimise the context, do the handoff behind the scenes, so the UI stays
fluid and seamless."* The handoff **is** the cost control, because a request
that never exceeds half the window is a smaller request than one that fills it.
Asking would have charged the user attention to save them nothing.
"""

from __future__ import annotations

import json
import time

import pytest

from core.bootstrapper import KernelBootstrapper
from core.contracts import Capability, RuntimeMetadata, RuntimeState
from core.execution_engine import ExecutionEngine
from core.streaming_events import EventType, StreamEvent
from core.tool_loop import MAX_AUTO_CONTINUATIONS, TOOL_CALL_MARKER
from projects.plans import Plan, PlanRecords, PlanStep
from runtimes.mcp.runtime import CALL, LIST_TOOLS

from tests.test_the_tool_loop_is_bounded import (  # the doubles, not the contract
    _A_BIG_RESULT,
    _McpDouble,
    _ModelRuntime,
    _READ,
    _SEARCH,
    _call,
    _events,
    _text,
)


@pytest.fixture
def store(tmp_path):
    return PlanRecords(str(tmp_path / "plans.db"))


def _engine(replies, mcp, store, locality="local"):
    """An engine with a plan store, and a stated model locality.

    `locality` stands in for the models runtime, which is what decides whether a
    task may spend the user's money carrying itself on. Registered as a runtime
    rather than patched, because the engine resolves it by name and a patch
    would assert a call the product does not make.
    """

    class _Models:
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
            return locality

    kernel = KernelBootstrapper()
    model = _ModelRuntime(replies)
    kernel.registry.register(model)
    kernel.registry.register(mcp)
    kernel.registry.register(_Models())
    engine = ExecutionEngine(kernel.registry, kernel.event_bus)
    engine.set_tool_vocabulary(mcp.server_names)
    engine.set_plan_records(store)
    return engine, model


@pytest.fixture
def a_tiny_window(monkeypatch):
    from core import execution_engine
    from core.context_budget import ContextBudget

    monkeypatch.setattr(
        execution_engine,
        "budget_for",
        lambda model=None, **kw: ContextBudget(
            total_tokens=600, measured=True, reply_reserve_tokens=150
        ),
    )


def _stop_a_task(store, a_tiny_window, *, locality="local", project_id="northwind"):
    """Run a task until it stops with work left, and return the engine."""
    windows = 1 + (MAX_AUTO_CONTINUATIONS if locality == "local" else 0)
    mcp = _McpDouble(
        tools=[_SEARCH, _READ],
        results=[{"success": True, "result": _A_BIG_RESULT}] * (windows + 2),
    )
    engine, model = _engine(
        [_call("search_code", query=f"q{i}") for i in range(windows)]
        + ["I have not finished."],
        mcp,
        store,
        locality=locality,
    )
    list(
        engine.execute(
            "use the code tools to tell me what it returns",
            session_id="tuesday",
            project_id=project_id,
        )
    )
    return engine, mcp


class TestTheStoreItself:
    def test_a_task_round_trips(self, store):
        saved = store.save(
            Plan(
                id="",
                question="what does it return",
                steps=[PlanStep("code", "search_code", {"query": "x"}, {"matches": []})],
                project_id="northwind",
                session_id="tuesday",
            )
        )

        read = store.get(saved.id)

        assert read is not None
        assert read.question == "what does it return"
        assert read.steps[0].tool == "search_code"
        assert read.steps[0].result == {"matches": []}

    def test_saving_again_replaces_rather_than_duplicates(self, store):
        """One task that got further, not two offers of the same job."""
        first = store.save(Plan(id="", question="q", steps=[], session_id="s"))
        store.save(
            Plan(
                id=first.id,
                question="q",
                steps=[PlanStep("code", "read_lines", {"path": "a.py"}, {"lines": []})],
                session_id="s",
            )
        )

        assert len(store.unfinished()) == 1
        assert len(store.get(first.id).steps) == 1

    def test_this_session_beats_the_project(self, store):
        """Continue under a reply means the thing that just stopped."""
        store.save(Plan(id="", question="older", steps=[], project_id="p"))
        mine = store.save(
            Plan(id="", question="mine", steps=[], project_id="p", session_id="s")
        )

        found = store.latest_for(session_id="s", project_id="p")

        assert found is not None and found.id == mine.id

    def test_the_project_answers_when_the_session_does_not(self, store):
        """Thursday: a new session, and a task left on Tuesday under no id it knows."""
        store.save(Plan(id="", question="tuesday's", steps=[], project_id="p", session_id="old"))

        found = store.latest_for(session_id="brand-new", project_id="p")

        assert found is not None and found.question == "tuesday's"

    def test_an_unfinished_task_expires(self, store):
        stale = store.save(Plan(id="", question="forgotten", steps=[], session_id="s"))

        store.prune(now=time.time() + 8 * 24 * 60 * 60)

        assert store.get(stale.id) is None

    def test_a_task_within_the_window_is_kept(self, store):
        kept = store.save(Plan(id="", question="live", steps=[], session_id="s"))

        store.prune(now=time.time() + 6 * 24 * 60 * 60)

        assert store.get(kept.id) is not None

    def test_a_result_that_will_not_parse_comes_back_as_text(self, store, tmp_path):
        """One malformed row must not take a week's work down with it."""
        saved = store.save(
            Plan(id="", question="q", steps=[PlanStep("code", "read_lines", {}, None)], session_id="s")
        )
        import sqlite3

        with sqlite3.connect(str(tmp_path / "plans.db")) as conn:
            conn.execute(
                "UPDATE plan_steps SET result = ? WHERE plan_id = ?",
                ("{not json", saved.id),
            )

        assert store.get(saved.id).steps[0].result == "{not json"


class TestTheLoopWritesItDown:
    def test_a_stopped_task_is_stored(self, store, a_tiny_window):
        _stop_a_task(store, a_tiny_window)

        waiting = store.unfinished()

        assert len(waiting) == 1
        assert waiting[0].project_id == "northwind"
        assert waiting[0].steps, "a task with no steps is not worth continuing"

    def test_it_stores_the_results_and_not_the_prose(self, store, a_tiny_window):
        """Rule 7d, at the point where it would be easiest to break."""
        _stop_a_task(store, a_tiny_window)

        plan = store.unfinished()[0]

        assert all(step.tool for step in plan.steps)
        assert "Working on it" not in json.dumps(
            [step.result for step in plan.steps], default=str
        )

    def test_no_system_prompt_is_kept(self, store, a_tiny_window):
        """Rule 4 depends on this: a frozen context resurrects deleted facts."""
        _stop_a_task(store, a_tiny_window)

        assert not hasattr(store.unfinished()[0], "system_prompt")

    def test_a_finished_task_leaves_nothing_behind(self, store, a_tiny_window):
        mcp = _McpDouble(tools=[_SEARCH], results=[{"success": True, "result": {"matches": []}}])
        engine, _ = _engine(
            [_call("search_code", query="x"), "Found it."], mcp, store
        )

        list(engine.execute("use the code tools to tell me about x", session_id="s"))

        assert store.unfinished() == []


class TestPickingItUpInAFreshEngine:
    def test_another_engine_continues_the_task(self, store, a_tiny_window):
        """The restart, as far as a test can stage one: a second engine, the
        same store, a session id the first one never saw."""
        _stop_a_task(store, a_tiny_window)

        mcp = _McpDouble(
            tools=[_SEARCH, _READ],
            results=[{"success": True, "result": {"lines": ["return 9137000000"]}}],
        )
        thursday, model = _engine(
            [_call("read_lines", path="core/residency.py"), "It returns 9137000000."],
            mcp,
            store,
        )

        out = list(thursday.continue_task(session_id="thursday", project_id="northwind"))

        assert [c["tool"] for c in mcp.calls] == ["read_lines"]
        assert "9137000000" in _text(out)

    def test_what_it_found_travels_into_the_new_engine(self, store, a_tiny_window):
        _stop_a_task(store, a_tiny_window)

        mcp = _McpDouble(tools=[_SEARCH], results=[{"success": True, "result": {}}])
        thursday, model = _engine(["Done."], mcp, store)

        list(thursday.continue_task(session_id="thursday", project_id="northwind"))

        # The first thing the resumed model is asked carries the earlier
        # results. Without that it is a new question wearing an old one's words.
        assert "Call 1" in model.service.prompts[0]

    def test_finishing_it_clears_the_task(self, store, a_tiny_window):
        _stop_a_task(store, a_tiny_window)

        mcp = _McpDouble(tools=[_SEARCH])
        thursday, _ = _engine(["That is the answer."], mcp, store)
        list(thursday.continue_task(session_id="thursday", project_id="northwind"))

        assert store.unfinished() == []

    def test_nothing_waiting_says_so(self, store):
        engine, _ = _engine(["unused"], _McpDouble(), store)

        out = list(engine.continue_task(session_id="nobody"))

        assert "nothing to continue" in _text(
            [n.data["content"] for n in _events(out, EventType.NOTICE)]
        )


class TestAMeteredModelIsNotTreatedDifferently:
    """The rejected design, kept as a test so it does not come back.

    It is a reasonable-sounding idea — rule 1 says the user's key pays, so ask
    before spending another window — and it was built and then removed. The
    reason is worth holding on to: a dialog at every window is what stops a
    product feeling seamless, and it saves nothing, because the handoff already
    keeps each request under half the model's context.
    """

    def _run(self, store, locality):
        mcp = _McpDouble(
            tools=[_SEARCH],
            results=[{"success": True, "result": _A_BIG_RESULT}] * 6,
        )
        engine, _ = _engine(
            [_call("search_code", query=f"q{i}") for i in range(3)] + ["Answered."],
            mcp,
            store,
            locality=locality,
        )
        out = list(
            engine.execute("use the code tools to tell me about x", session_id="s")
        )
        return mcp, out

    @pytest.mark.parametrize("locality", ["local", "cloud", None])
    def test_every_locality_carries_on_the_same_way(self, store, a_tiny_window, locality):
        mcp, _ = self._run(store, locality)

        assert len(mcp.calls) == 3

    @pytest.mark.parametrize("locality", ["cloud", None])
    def test_nothing_asks_the_user_for_permission_to_continue(
        self, store, a_tiny_window, locality
    ):
        _, out = self._run(store, locality)

        assert not [
            n for n in _events(out, EventType.NOTICE) if n.data.get("kind") == "tool_loop"
        ], "a finished task must not leave a prompt behind on any model"


class TestTheApiReachesIt:
    """Registering is not reaching, and a list nobody can read is not a feature."""

    def test_the_request_carries_the_plan_id(self):
        from main import ChatRequest

        assert ChatRequest(text="Continue", plan_id="abc").plan_id == "abc"
        assert ChatRequest(text="hello").plan_id == ""

    @pytest.mark.asyncio
    async def test_resume_hands_the_plan_id_to_the_engine(self):
        from core.chat_router import ChatRouter

        class _Engine:
            def __init__(self):
                self.seen = []

            def continue_task(self, session_id="default", model=None, **kwargs):
                self.seen.append((session_id, kwargs.get("plan_id")))
                yield "resumed"

            def execute(self, *args, **kwargs):
                yield "new answer"

        engine = _Engine()
        router = ChatRouter(engine, event_bus=None, legacy_generator_func=None)

        [
            frame
            async for frame in router.route(
                "Continue", "m", session_id="s", resume=True, plan_id="abc"
            )
        ]

        assert engine.seen == [("s", "abc")]

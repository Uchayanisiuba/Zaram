"""For a model that can call tools, the model chooses — and the rules sit first.

`docs/PLAN.md` D1 and the second half of A3, built 19 September 2026.

Until now `IntentPlanner.create_plan` decided from an embedding classification
whether a turn got tools at all, and on every ordinary turn the model was
handed a fixed plan and could not decide to search or read a page. Now a plain
generation plan, on a model the models runtime says may choose
(`ModelsRuntime.chooses_tools`), gets the listing step in front of it and the
model decides. Every other plan is untouched, and so is every model that
cannot call tools — which is also every test double that never heard of the
question, because the engine fails closed.

And the tool rules go *before* the conversation: they are constant for a
session, so they belong in the cached prefix, not in the tail that is re-read
every turn. The stranger shortlist is ranked by the question only when the
question is about tools; otherwise the listing order is used, so the set is
the same bytes on every turn.
"""

from __future__ import annotations

import pytest

from core.bootstrapper import KernelBootstrapper
from core.contracts import Capability, RuntimeMetadata, RuntimeState
from core.execution_engine import ExecutionEngine
from core.streaming_events import EventType, StreamEvent
from core.tool_loop import TOOL_CALL_MARKER
from projects.plans import PlanRecords
from tests.test_the_tool_loop_is_bounded import (  # the doubles, not the contract
    _SEARCH,
    _McpDouble,
    _ModelRuntime,
)

IDENTITY = "You are Zaram. Constant for the whole session."


class _ChoosingModel(_ModelRuntime):
    """The model runtime, answering `chooses_tools` as told.

    One object, as in the real app: `ModelsRuntime` both serves
    `reasoning.generate` and answers questions about the model, and the
    engine reaches it through the capability. A double that split the two
    would test a wiring the product does not have.
    """

    def __init__(self, replies, chooses: bool):
        super().__init__(replies)
        self._chooses = chooses
        self.asked: list = []

    def health_check(self):
        return {"state": "ready", "model": "qwen3-14b"}

    def locality_of(self, model):
        return "local"

    def chooses_tools(self, model):
        self.asked.append(model)
        return self._chooses


class _ListingMcp(_McpDouble):
    """Records the query each listing was asked with."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.listing_queries: list[str] = []

    async def execute(self, capability_id, input_data):
        if capability_id == "mcp.list_tools":
            self.listing_queries.append(str(input_data.get("query", "")))
        return await super().execute(capability_id, input_data)


def _engine(tmp_path, replies, mcp, chooses: bool):
    kernel = KernelBootstrapper()
    model = _ChoosingModel(replies, chooses)
    kernel.registry.register(model)
    kernel.registry.register(mcp)
    engine = ExecutionEngine(kernel.registry, kernel.event_bus)
    engine.set_tool_vocabulary(mcp.server_names)
    engine.set_plan_records(PlanRecords(str(tmp_path / "plans.db")))
    return engine, model, model


def _capture(engine, monkeypatch):
    seen: list[str] = []
    real = engine._dispatcher.execute_step

    def spy(step, model, system_prompt):
        if step.capability_id == "reasoning.generate":
            seen.append(system_prompt)
        yield from real(step, model, system_prompt)

    monkeypatch.setattr(engine._dispatcher, "execute_step", spy)
    return seen


PLAIN = "what is a good name for a cat"


class TestWhoDecides:
    def test_a_choosing_model_is_offered_the_tools_on_a_plain_question(self, tmp_path):
        mcp = _ListingMcp(tools=[_SEARCH])
        engine, model, models = _engine(tmp_path, ["Whiskers."], mcp, chooses=True)

        out = list(engine.execute(PLAIN, session_id="s", system_prompt=IDENTITY))

        assert models.asked, "the models runtime was never asked"
        assert mcp.listing_queries == [""], "listed, in listing order, once"
        assert "search_code" in model.service.systems[-1]
        assert "Whiskers." in "".join(t for t in out if isinstance(t, str))
        notices = [e for e in out if isinstance(e, StreamEvent) and e.type is EventType.NOTICE]
        assert any(e.data.get("kind") == "tools" for e in notices)

    def test_a_model_that_cannot_choose_takes_the_planner_path(self, tmp_path):
        mcp = _ListingMcp(tools=[_SEARCH])
        engine, model, _ = _engine(tmp_path, ["Whiskers."], mcp, chooses=False)

        list(engine.execute(PLAIN, session_id="s", system_prompt=IDENTITY))

        assert mcp.listing_queries == []
        assert "search_code" not in model.service.systems[-1]

    def test_a_document_request_is_untouched(self, tmp_path, monkeypatch):
        """Rule 9's path plans a document in two steps. No listing is put in
        front of it — and not even when the document runtime is missing and
        the plan degrades to a plain generation, because the rule reads the
        plan *as planned*."""
        import time as _time
        import uuid as _uuid

        from core.contracts import ExecutionPlan, ExecutionStep, PlanState

        mcp = _ListingMcp(tools=[_SEARCH])
        engine, _, _ = _engine(tmp_path, ["draft"], mcp, chooses=True)

        def document_plan(prompt, priority="normal", **_):
            return ExecutionPlan(
                correlation_id=str(_uuid.uuid4()), original_prompt=prompt,
                steps=[
                    ExecutionStep(capability_id="reasoning.generate", input_data={"prompt": prompt}, depends_on=[]),
                    ExecutionStep(capability_id="document.generate", input_data={"prompt": prompt, "answer": ""}, depends_on=[0]),
                ],
                state=PlanState.PENDING, priority=priority, created_at=_time.time(),
            )

        monkeypatch.setattr(engine._planner, "create_plan", document_plan)
        list(engine.execute("write me a proposal for the Northwind job", session_id="s"))
        assert mcp.listing_queries == []

    def test_the_gate_still_runs_on_what_the_model_chose(self, tmp_path):
        """A listing authorises nothing: the call still goes through the MCP
        runtime's execute, which is where `policy.decide` lives."""
        mcp = _ListingMcp(
            tools=[_SEARCH],
            results=[{"success": True, "result": {"matches": []}}],
        )
        call = TOOL_CALL_MARKER + ' {"server": "code", "tool": "search_code", "arguments": {"query": "cat"}}\n'
        engine, _, _ = _engine(tmp_path, [call, "Nothing there."], mcp, chooses=True)
        list(engine.execute(PLAIN, session_id="s"))
        assert mcp.calls == [{"server": "code", "tool": "search_code", "arguments": {"query": "cat"}, "confirmed": False}]


class TestTheRulesComeFirst:
    def test_tool_rules_precede_the_conversation(self, tmp_path, monkeypatch):
        mcp = _ListingMcp(tools=[_SEARCH])
        engine, _, _ = _engine(tmp_path, ["one", "two"], mcp, chooses=True)
        engine._session_turns["s"] = [("earlier question", "earlier answer")]
        seen = _capture(engine, monkeypatch)

        list(engine.execute(PLAIN, session_id="s", system_prompt=IDENTITY))

        prompt = seen[0]
        assert prompt.index(IDENTITY) < prompt.index("search_code") < prompt.index("earlier question")

    def test_the_prefix_is_byte_identical_across_two_tool_turns(self, tmp_path, monkeypatch):
        """The property a prompt cache needs, now including the tool rules."""
        mcp = _ListingMcp(tools=[_SEARCH])
        engine, _, _ = _engine(tmp_path, ["one", "two"], mcp, chooses=True)
        monkeypatch.setattr(engine, "_recall", lambda *a, **k: [])
        engine._session_turns["s"] = [("q1", "a1")]
        seen = _capture(engine, monkeypatch)

        list(engine.execute("q2", session_id="s", system_prompt=IDENTITY))
        engine._session_turns["s"] = [("q1", "a1"), ("q2", "one")]
        list(engine.execute("q3", session_id="s", system_prompt=IDENTITY))

        first, second = seen
        stable = first[: first.index("a1") + len("a1")]
        assert "search_code" in stable, "the tool rules are not inside the cached region"
        assert second.startswith(stable)

    def test_a_question_about_tools_is_still_ranked(self, tmp_path):
        mcp = _ListingMcp(tools=[_SEARCH])
        engine, _, _ = _engine(tmp_path, ["ok"], mcp, chooses=True)
        list(engine.execute("run the tests with the code tools", session_id="s"))
        assert mcp.listing_queries and mcp.listing_queries[0] != ""


class TestChoosesToolsPolicy:
    def _runtime(self, info):
        from runtimes.models.models_runtime import ModelsRuntime

        class _Manager:
            def get_model(self, model_id):
                return info

        runtime = ModelsRuntime.__new__(ModelsRuntime)
        runtime._provider_manager = _Manager()
        return runtime

    def test_a_large_tool_capable_model_chooses(self):
        from types import SimpleNamespace

        r = self._runtime(SimpleNamespace(supports_tools=True, size_bytes=9_000_000_000))
        assert r.chooses_tools("m") is True

    def test_a_small_one_does_not(self):
        from types import SimpleNamespace

        r = self._runtime(SimpleNamespace(supports_tools=True, size_bytes=4_000_000_000))
        assert r.chooses_tools("m") is False

    def test_unknown_size_is_trusted_and_no_tools_is_not(self):
        from types import SimpleNamespace

        assert self._runtime(SimpleNamespace(supports_tools=True, size_bytes=None)).chooses_tools("m") is True
        assert self._runtime(SimpleNamespace(supports_tools=False, size_bytes=None)).chooses_tools("m") is False
        assert self._runtime(None).chooses_tools("m") is False
        assert self._runtime(None).chooses_tools(None) is False


class TestASearchTheModelChoseIsCited:
    """Rule 2 does not care who decided to search. A `web.search` the model
    called discloses its results as sources, numbered at the same point the
    planner's are, so the chips agree."""

    _SEARCH_TOOL = {
        "server": "web", "name": "search", "description": "Search the web.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        "provenance": "tool_output", "suspicions": [],
    }

    def test_results_become_numbered_sources(self, tmp_path):
        mcp = _ListingMcp(
            tools=[self._SEARCH_TOOL],
            servers=("web",),
            results=[{"success": True, "result": {
                "query": "fable outage",
                "results": [
                    {"title": "Fable disabled", "url": "https://news.example/a", "snippet": "…"},
                    {"title": "Restored", "url": "https://news.example/b", "snippet": "…"},
                    {"title": "Restored again", "url": "https://news.example/b", "snippet": "dupe"},
                ],
                "total": 3,
            }}],
        )
        call = TOOL_CALL_MARKER + ' {"server": "web", "tool": "search", "arguments": {"query": "fable outage"}}\n'
        engine, _, _ = _engine(tmp_path, ["I'll look.\n" + call, "It was disabled for 18 days."], mcp, chooses=True)

        out = list(engine.execute("what happened with fable this summer", session_id="s"))

        sources = [e for e in out if isinstance(e, StreamEvent) and e.type is EventType.SOURCE]
        urls = [e.data.get("url") for e in sources]
        assert urls == ["https://news.example/a", "https://news.example/b"], "deduplicated by url"
        assert [e.data.get("number") for e in sources] == [1, 2]
        assert all(e.data.get("kind") == "web" for e in sources)


class TestTheSearchTool:
    def test_off_is_a_refusal_that_says_where(self):
        from packs.web import WebTools

        out = WebTools(search=lambda q: {}, search_enabled=lambda: False).call_tool("search", {"query": "x"})
        assert out["refused"] is True and "Settings" in out["error"]

    def test_results_are_bounded_and_shaped(self):
        from packs.web import WebTools
        from packs.web.tools import SEARCH_RESULTS

        many = {"results": [{"title": f"t{i}", "url": f"https://x/{i}", "snippet": "s", "published": "2026"} for i in range(20)]}
        out = WebTools(search=lambda q: many, search_enabled=lambda: True).call_tool("search", {"query": "  a   b "})
        assert out["query"] == "a b" and out["total"] == SEARCH_RESULTS
        assert out["results"][0] == {"title": "t0", "url": "https://x/0", "snippet": "s", "published": "2026"}

    def test_nothing_found_carries_the_connectors_status(self):
        from packs.web import WebTools

        out = WebTools(
            search=lambda q: {"results": [], "provider_status": {"duckduckgo": "denied by policy"}},
            search_enabled=lambda: True,
        ).call_tool("search", {"query": "x"})
        assert out["results"] == [] and out["status"] == {"duckduckgo": "denied by policy"}

    def test_not_wired_means_not_offered(self):
        from packs.web import WebTools

        assert [d.name for d in WebTools().list_tools()] == ["read_page"]
        assert "search" not in WebTools().granted_tools()

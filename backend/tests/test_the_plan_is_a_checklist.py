"""The plan is a checklist: written by the model, rendered from the record,
kept on the project's row, and read by the person before anything changes.

Slice 7 of the code pack, `docs/AGENT-UX.md`, 13 September 2026.

**The `plan` tool writes request state and nothing else.** No file, no grant,
always permitted on Zaram's own server and only there. A skipped step needs a
reason, because a decision rejected is only useful if a resumed task can read
why.

**The engine emits the checklist whole after every `plan` call**, stores it
with a parked task, seeds it back on resume, and keeps it — steps dropped —
when the task finishes.

**A long plan pauses before its first mutative call** with a `go` offer; Go
is remembered on the task and the session; a short plan, or one that only
reads, never pauses.
"""

from __future__ import annotations

import pytest

from core.streaming_events import EventType
from packs.code import CodeTools, set_active_root
from projects.plans import PlanRecords
from tests.test_the_tool_loop_is_bounded import (
    _McpDouble,
    _call,
    _engine,
    _events,
    a_generous_window,  # noqa: F401 - fixture
)

PLAN = {"server": "code", "name": "plan", "description": "plan", "input_schema": {}}
EDIT = {"server": "code", "name": "edit_file", "description": "edit", "input_schema": {}}
READ = {"server": "code", "name": "read_lines", "description": "read", "input_schema": {}}


@pytest.fixture(autouse=True)
def _clean_context():
    set_active_root(None)
    yield
    set_active_root(None)


class TestTheTool:
    def test_it_writes_the_request_checklist(self, tmp_path):
        tools = CodeTools(lambda: tmp_path)
        result = tools.call_tool("plan", {"items": [
            {"text": "Read the failing test", "status": "done"},
            {"text": "Fix add()", "status": "doing"},
            {"text": "Run the tests"},
        ]})
        assert result["done"] == 1 and result["total"] == 3
        assert [i["status"] for i in result["items"]] == ["done", "doing", "todo"]

    def test_a_skipped_step_needs_a_reason(self, tmp_path):
        tools = CodeTools(lambda: tmp_path)
        assert "reason" in tools.call_tool("plan", {"items": [{"text": "Refactor", "status": "skipped"}]})["error"]

    def test_it_needs_no_project_and_no_grant(self):
        tools = CodeTools(lambda: None)
        assert "error" not in tools.call_tool("plan", {"items": [{"text": "x"}]})
        assert "plan" in tools.granted_tools()

    def test_the_module_still_has_no_write(self):
        import sys
        from pathlib import Path

        text = Path(sys.modules[CodeTools.__module__].__file__).read_text(encoding="utf-8")
        assert "write_text(" not in text


def _plan_engine(replies, results, tools=(PLAN, EDIT, READ), store=None):
    """An engine whose MCP double answers a `plan` call the way the real tool
    does — with the items on the result — so the engine reads the record off
    the result, which is the only place it can."""
    mcp = _McpDouble(tools=list(tools), results=results)
    engine, _ = _engine(replies, mcp)
    if store is not None:
        engine.set_plan_records(store)
    real = mcp.execute

    async def execute(capability_id, input_data):
        answer = await real(capability_id, input_data)
        if input_data.get("tool") == "plan" and isinstance(answer, dict) and answer.get("success"):
            answer = dict(answer)
            answer["result"] = {"items": input_data["arguments"]["items"]}
        return answer

    mcp.execute = execute
    return engine, mcp


def _plan_call(*items):
    return _call("plan", items=[{"text": t, "status": s} for t, s in items])


def _ok(items=None, **extra):
    return {"success": True, "result": {"items": items or [], **extra}}


class TestTheEngine:
    def test_the_checklist_is_emitted_whole_after_each_plan_call(self, a_generous_window):  # noqa: F811
        engine, _ = _plan_engine(
            [_plan_call(("read", "doing"), ("edit", "todo")), _plan_call(("read", "done"), ("edit", "todo")), "Done."],
            [_ok(), _ok()],
        )

        out = list(engine.execute("use the code tools to fix the failing test"))

        plans = _events(out, EventType.PLAN)
        assert [len(p.data["items"]) for p in plans] == [2, 2]
        assert plans[-1].data["items"][0]["status"] == "done"
        assert plans[-1].data["awaiting_go"] is False

    def test_a_long_plan_pauses_before_the_first_change_and_go_resumes_it(self, a_generous_window, tmp_path):  # noqa: F811
        store = PlanRecords(str(tmp_path / "plans.db"))
        four = [("a", "done"), ("b", "doing"), ("c", "todo"), ("d", "todo")]
        engine, mcp = _plan_engine(
            [
                _plan_call(*four),
                _call("edit_file", path="x", find="a", replace="b"),
                "Paused answer.",
                _call("edit_file", path="x", find="a", replace="b"),
                "Resumed and done.",
            ],
            [_ok(), _ok(commit="abc")],
            store=store,
        )

        out = list(engine.execute("use the code tools to change x", session_id="s1"))

        # Paused: the plan was shown awaiting Go, the edit did not run, the
        # task is parked with its checklist and a `go` offer.
        assert [c["tool"] for c in mcp.calls] == ["plan"]
        awaiting = [p for p in _events(out, EventType.PLAN) if p.data["awaiting_go"]]
        assert len(awaiting) == 1
        offers = [n for n in _events(out, EventType.NOTICE) if n.data.get("action") == "go"]
        assert len(offers) == 1
        parked = store.unfinished()
        assert len(parked) == 1 and [i.text for i in parked[0].items] == ["a", "b", "c", "d"]
        assert parked[0].approved is False

        # Go: the same task resumes, the edit runs, the plan is approved on
        # the record, and finishing keeps the checklist without the steps.
        out2 = list(engine.continue_task(session_id="s1", plan_id=parked[0].id, approve=True))

        assert [c["tool"] for c in mcp.calls] == ["plan", "edit_file"]
        assert "Resumed and done." in "".join(i for i in out2 if isinstance(i, str))
        assert store.unfinished() == []
        kept = store.finished_for()
        assert len(kept) == 1 and kept[0].finished is True and kept[0].approved is True
        assert [i.text for i in kept[0].items] == ["a", "b", "c", "d"]
        assert kept[0].steps == []

    def test_a_short_plan_never_pauses(self, a_generous_window):  # noqa: F811
        engine, mcp = _plan_engine(
            [_plan_call(("a", "doing"), ("b", "todo")), _call("edit_file", path="x", find="a", replace="b"), "Done."],
            [_ok(), _ok(commit="abc")],
        )
        list(engine.execute("use the code tools to change x"))
        assert [c["tool"] for c in mcp.calls] == ["plan", "edit_file"]

    def test_a_long_plan_that_only_reads_never_pauses(self, a_generous_window):  # noqa: F811
        four = [("a", "todo"), ("b", "todo"), ("c", "todo"), ("d", "todo")]
        engine, mcp = _plan_engine(
            [_plan_call(*four), _call("read_lines", path="x"), "Done."],
            [_ok(), _ok(lines=[])],
        )
        list(engine.execute("use the code tools to tell me about x"))
        assert [c["tool"] for c in mcp.calls] == ["plan", "read_lines"]

    def test_a_finished_unplanned_task_is_still_deleted(self, a_generous_window, tmp_path):  # noqa: F811
        store = PlanRecords(str(tmp_path / "plans.db"))
        engine, _ = _plan_engine(
            [_call("read_lines", path="x"), "Done."],
            [_ok(lines=[])],
            store=store,
        )
        list(engine.execute("use the code tools to tell me about x"))
        assert store.unfinished() == [] and store.finished_for() == []


class TestTheStore:
    def test_a_database_from_before_the_columns_opens(self, tmp_path):
        import sqlite3

        path = tmp_path / "old.db"
        with sqlite3.connect(path) as conn:
            conn.execute(
                "CREATE TABLE plans (id TEXT PRIMARY KEY, question TEXT NOT NULL, project_id TEXT NOT NULL DEFAULT '', "
                "session_id TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '', stopped_because TEXT NOT NULL DEFAULT '', "
                "created_at REAL NOT NULL, updated_at REAL NOT NULL)"
            )
            import time

            now = time.time()
            conn.execute("INSERT INTO plans VALUES ('old', 'q', '', '', '', 'stopped', ?, ?)", (now, now))
        store = PlanRecords(str(path))
        old = store.get("old")
        assert old is not None and old.items == [] and old.finished is False


class TestARepeatedPlanIsNotAStall:
    def test_the_same_plan_twice_does_not_end_the_task(self, a_generous_window):  # noqa: F811
        """Seen on 13 September: the model re-sent its checklist verbatim and
        the repeat guard ended the task with "asked for `plan` again"."""
        two = [("a", "todo"), ("b", "todo")]
        engine, mcp = _plan_engine(
            [_plan_call(*two), _plan_call(*two), _call("edit_file", path="x", find="a", replace="b"), "Done."],
            [_ok(), _ok(commit="abc")],
        )
        out = list(engine.execute("use the code tools to change x"))
        assert [c["tool"] for c in mcp.calls] == ["plan", "edit_file"]
        assert "Done." in "".join(i for i in out if isinstance(i, str))
        assert not any(
            "asked for" in n.data.get("content", "") for n in _events(out, EventType.NOTICE)
        )

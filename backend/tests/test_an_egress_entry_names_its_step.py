"""An entry written while a step runs says which step — `docs/PLAN.md` C2.

The working pane opens from a row and shows what that step sent off the
machine. That needs the log to know, and it now does: the engine marks each
plan step and each tool call with `running_step`, and the one place an entry
is recorded stamps the mark into ``meta["step_id"]`` — inside the hashed
record, so it is as tamper-evident as the rest. An entry written outside any
step carries nothing, and the filter never matches it.
"""

from __future__ import annotations

from core.egress import EgressLog
from core.egress.step_context import current_step, running_step


def _record(log: EgressLog, url: str, **meta):
    return log.append(
        host="example.com", method="GET", url=url, body=None,
        decision="allowed", reason="test", source="test", meta=meta or None,
    )


class TestTheStamp:
    def test_inside_a_step_the_entry_names_it(self, tmp_path):
        log = EgressLog(str(tmp_path / "egress.db"))
        with running_step("corr-1:0"):
            entry = _record(log, "https://example.com/a")
        assert entry.meta["step_id"] == "corr-1:0"

    def test_outside_any_step_it_carries_nothing(self, tmp_path):
        log = EgressLog(str(tmp_path / "egress.db"))
        assert current_step() is None
        entry = _record(log, "https://example.com/a")
        assert "step_id" not in entry.meta

    def test_the_mark_is_restored_after_the_step_even_on_failure(self):
        try:
            with running_step("corr-1:0"):
                assert current_step() == "corr-1:0"
                raise RuntimeError("the step blew up")
        except RuntimeError:
            pass
        assert current_step() is None

    def test_a_caller_supplied_stamp_is_not_overwritten(self, tmp_path):
        log = EgressLog(str(tmp_path / "egress.db"))
        with running_step("corr-1:0"):
            entry = _record(log, "https://example.com/a", step_id="explicit")
        assert entry.meta["step_id"] == "explicit"

    def test_the_stamp_is_covered_by_the_hash(self, tmp_path):
        log = EgressLog(str(tmp_path / "egress.db"))
        with running_step("corr-1:0"):
            entry = _record(log, "https://example.com/a")
        assert "step_id" in entry.payload()["meta"]


class TestTheFilter:
    def test_a_step_finds_its_own_entries_and_a_reply_finds_all_of_its_steps(self, tmp_path):
        log = EgressLog(str(tmp_path / "egress.db"))
        with running_step("corr-1:0"):
            _record(log, "https://example.com/search")
        with running_step("corr-1:0:call:1"):
            _record(log, "https://example.com/page")
        with running_step("corr-2:0"):
            _record(log, "https://example.com/other")
        _record(log, "https://example.com/unattributed")

        assert [e.url for e in log.entries_for_step("corr-1:0")] == [
            "https://example.com/page", "https://example.com/search",
        ]
        assert [e.url for e in log.entries_for_step("corr-1")] == [
            "https://example.com/page", "https://example.com/search",
        ]
        assert [e.url for e in log.entries_for_step("corr-2")] == ["https://example.com/other"]
        assert log.entries_for_step("") == []
        assert log.entries_for_step("nope") == []


class TestTheEngineMarks:
    def test_a_plan_step_and_a_tool_call_are_each_marked(self, tmp_path, monkeypatch):
        """Read off `current_step` from inside a double, which is the one way
        to see the mark the engine set rather than the mark a test set."""
        from tests.test_the_tool_loop_is_bounded import _SEARCH, _McpDouble, _engine
        from core.tool_loop import TOOL_CALL_MARKER

        seen: dict[str, str | None] = {}

        class _Marking(_McpDouble):
            async def execute(self, capability_id, input_data):
                seen[capability_id] = current_step()
                return await super().execute(capability_id, input_data)

        mcp = _Marking(tools=[_SEARCH], results=[{"success": True, "result": {"matches": []}}])
        call = TOOL_CALL_MARKER + ' {"server": "code", "tool": "search_code", "arguments": {"query": "x"}}\n'
        engine, _ = _engine([call, "done"], mcp)
        list(engine.execute("use the code tools to tell me about x", session_id="s"))

        listing = seen.get("mcp.list_tools")
        calling = seen.get("mcp.call")
        assert listing and listing.endswith(":0"), listing
        assert calling and ":call:1" in calling, calling
        assert current_step() is None


class TestRunSyncKeepsTheContext:
    def test_the_threadsafe_path_sees_the_callers_mark(self):
        """`run_sync` from inside a running loop goes to a background loop;
        the coroutine must still see the step the caller set."""
        import asyncio

        from core.async_bridge import run_sync

        async def read():
            await asyncio.sleep(0)
            return current_step()

        async def caller():
            with running_step("corr-9:2"):
                return run_sync(read())

        assert asyncio.run(caller()) == "corr-9:2"

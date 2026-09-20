"""Two floors no grant lowers, and the confirm card's one line of provenance.

Coworker step 2, `docs/MILESTONES.md`, taken from OpenWorker's
`permissions.py` and `provenance.py` (MIT) — the shape, not the code, and
only the parts with a caller here. `runtimes/mcp/floors.py` records what
was not taken and why: Zaram has no shell tool for a command parser to
guard.

1. A write to a file that governs Zaram is refused under every mode and
   every grant, and the row is not offered a way to allow it. On the
   maintainer's machine the checkout is the data directory, so a project
   rooted at `backend/` reaches `mcp-servers.json` by a relative path.
2. A write to a file that runs later — a git hook, a workflow — asks
   whatever has been granted, and cannot be granted away; only the person's
   Go on the run covers it.
3. When `run_command` would execute a file Zaram wrote this session, the
   confirm reason says so: *"tests/test_x.py was created by Zaram 1 step
   ago."* Never file content.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from runtimes.mcp.floors import SessionFiles, floor_for, referenced_paths, write_target
from runtimes.mcp.policy import WriteMode
from runtimes.mcp.runtime import McpRuntime


class TestTheFloorsAsFunctions:
    def test_only_our_write_tools_are_scoped(self):
        assert write_target("write_file", {"path": "a.py"}) == "a.py"
        assert write_target("edit_file", {"path": "a.py", "find": "x", "replace": "y"}) == "a.py"
        assert write_target("some_strangers_write", {"path": "a.py"}) is None
        assert write_target("read_lines", {"path": "a.py"}) is None

    def test_a_governing_file_is_refused_by_relative_path(self, monkeypatch, tmp_path):
        # The data directory *is* the project root — the maintainer's own
        # layout, and the one the escalation needs.
        monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
        under = floor_for("code", "write_file", {"path": "mcp-servers.json", "content": "{}"}, tmp_path)
        assert under is not None and under.verdict == "refuse"
        assert "mcp-servers.json" in under.reason
        assert under.grantable is False

    def test_a_governing_file_is_refused_by_absolute_path_from_elsewhere(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path / "data"))
        (tmp_path / "data").mkdir()
        project = tmp_path / "project"
        project.mkdir()
        target = str(tmp_path / "data" / "egress-policy.json")
        under = floor_for("code", "edit_file", {"path": target, "find": "deny", "replace": "allow"}, project)
        assert under is not None and under.verdict == "refuse"

    def test_a_file_that_runs_later_always_asks(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path / "data"))
        for path in (".git/hooks/pre-commit", ".github/workflows/ci.yml", ".vscode/tasks.json"):
            under = floor_for("code", "write_file", {"path": path, "content": "x"}, tmp_path)
            assert under is not None and under.verdict == "confirm", path
            assert under.grantable is False

    def test_an_ordinary_file_has_no_floor(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path / "data"))
        assert floor_for("code", "write_file", {"path": "src/app.py", "content": "x"}, tmp_path) is None
        # A file merely *named* like a governing one, elsewhere, is not one.
        assert floor_for("code", "write_file", {"path": "fixtures/settings.json", "content": "x"}, tmp_path) is None


class TestProvenance:
    def test_a_runner_names_its_implicit_and_explicit_files(self):
        assert referenced_paths("run_command", {"runner": "pytest", "args": ["tests/test_a.py::test_x", "-q"]}) == [
            "conftest.py",
            "tests/test_a.py",
        ]
        assert referenced_paths("run_command", {"runner": "npm:test"}) == ["package.json"]
        assert referenced_paths("read_lines", {"path": "a.py"}) == []

    def test_a_file_zaram_wrote_is_named_on_the_card(self, tmp_path):
        files = SessionFiles()
        files.record("write_file", {"path": "tests/test_a.py", "content": "..."}, step=2, root=tmp_path)
        made = files.match("run_command", {"runner": "pytest", "args": ["tests/test_a.py"]}, step=3, root=tmp_path)
        assert made is not None
        assert made.render() == "tests/test_a.py was created by Zaram 1 step ago"

    def test_a_file_zaram_did_not_write_says_nothing(self, tmp_path):
        files = SessionFiles()
        assert files.match("run_command", {"runner": "pytest"}, step=1, root=tmp_path) is None

    def test_only_a_successful_write_is_remembered(self, tmp_path):
        # The engine records after `success`; this pins that `record` is the
        # only way in, so a failed write cannot be named as created.
        files = SessionFiles()
        files.record("read_lines", {"path": "a.py"}, step=1, root=tmp_path)
        assert files.match("run_command", {"runner": "pytest", "args": ["a.py"]}, step=2, root=tmp_path) is None


class _Code:
    """The code server as the runtime sees a built-in: a root, and tools."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def root(self):
        return self._root

    def connect(self):
        pass

    def granted_tools(self):
        return {"write_file"}

    def call_tool(self, name: str, arguments: dict) -> Any:
        return {"wrote": arguments.get("path")}


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
    from runtimes.mcp.config import ServerConfig, ServerStore

    rt = McpRuntime(store=ServerStore(path=str(tmp_path / "mcp-servers.json")))
    # The most permissive state there is: writes granted for the whole
    # server, and the tool granted by name on top.
    rt.register_builtin(
        ServerConfig(server_id="code", command=[], writes=WriteMode.GRANTED, granted_tools={"write_file"}),
        _Code(tmp_path),
    )
    return rt


class TestThroughTheRuntime:
    @pytest.mark.asyncio
    async def test_a_granted_server_still_cannot_write_its_own_grants(self, runtime):
        # `WriteMode.GRANTED` *and* the tool granted by name — the most
        # permissive state there is — and the governing file is still refused.
        result = await runtime.execute(
            "mcp.call", {"server": "code", "tool": "write_file", "arguments": {"path": "mcp-servers.json", "content": "{}"}}
        )
        assert result.get("refused") is True
        assert "govern" in result["reason"]

    @pytest.mark.asyncio
    async def test_a_hook_asks_under_a_grant_and_is_not_grantable(self, runtime):
        result = await runtime.execute(
            "mcp.call", {"server": "code", "tool": "write_file", "arguments": {"path": ".git/hooks/pre-commit", "content": "x"}}
        )
        assert result.get("needs_confirmation") is True
        assert result.get("grantable") is False

    @pytest.mark.asyncio
    async def test_the_persons_go_covers_a_hook(self, runtime):
        result = await runtime.execute(
            "mcp.call",
            {"server": "code", "tool": "write_file", "arguments": {"path": ".git/hooks/pre-commit", "content": "x"}, "confirmed": True},
        )
        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_an_ordinary_write_is_unchanged(self, runtime):
        result = await runtime.execute(
            "mcp.call", {"server": "code", "tool": "write_file", "arguments": {"path": "src/app.py", "content": "x"}}
        )
        assert result.get("success") is True


class _Host:
    """A host-undo server: writes ask once per tool, per `policy.decide`."""

    def root(self):
        return None

    def connect(self):
        pass

    def granted_tools(self):
        return set()

    def call_tool(self, name: str, arguments: dict) -> Any:
        return {"did": name}


@pytest.fixture
def host_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
    from runtimes.mcp.config import ServerConfig, ServerStore

    rt = McpRuntime(store=ServerStore(path=str(tmp_path / "mcp-servers.json")))
    rt.register_builtin(ServerConfig(server_id="blender", command=[], writes=WriteMode.HOST_UNDO), _Host())
    return rt


class TestTheConversationRung:
    """Once · this conversation · always. The middle one is new: a yes for
    the task in hand, not forever, and not written to disk."""

    @pytest.mark.asyncio
    async def test_a_tool_allowed_for_this_conversation_runs_here_and_asks_elsewhere(self, host_runtime):
        call = {"server": "blender", "tool": "set_material", "arguments": {}, "session": "s1"}
        first = await host_runtime.execute("mcp.call", call)
        assert first.get("needs_confirmation") is True

        host_runtime.allow_for_session("s1", "blender", "set_material")

        again = await host_runtime.execute("mcp.call", call)
        assert again.get("success") is True
        elsewhere = await host_runtime.execute("mcp.call", {**call, "session": "s2"})
        assert elsewhere.get("needs_confirmation") is True

    @pytest.mark.asyncio
    async def test_the_rung_never_covers_a_delete(self, host_runtime):
        host_runtime.allow_for_session("s1", "blender", "delete_object")
        result = await host_runtime.execute(
            "mcp.call", {"server": "blender", "tool": "delete_object", "arguments": {}, "session": "s1"}
        )
        assert result.get("needs_confirmation") is True

    @pytest.mark.asyncio
    async def test_the_rung_never_lowers_a_floor(self, runtime):
        runtime.allow_for_session("s1", "code", "write_file")
        result = await runtime.execute(
            "mcp.call",
            {"server": "code", "tool": "write_file", "arguments": {"path": "mcp-servers.json", "content": "{}"}, "session": "s1"},
        )
        assert result.get("refused") is True

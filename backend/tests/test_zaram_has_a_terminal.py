"""A terminal, under a grant of its own.

Asked for 3 October 2026: *"does Zaram have a terminal like yours, is it able
to use the terminal to perform tasks like creating environments, downloading
dependencies and tasks needed to build various types of software"*.

It did not, and the gap was real. `runners.py` can only offer commands it
**detected** — the scripts in a `package.json`, the targets in a
`pyproject.toml` — so `npm test` worked and `python -m venv .venv` did not,
because a virtualenv that does not exist yet is in no manifest. Every project
that has to be set up before it can be run was out of reach, which is most
projects on their first day.

**This is the thing `runners.py` was written to avoid**, so the tests say so.
That module's rule — *"there is no shell: a runner is a named program and its
arguments, so a stray semicolon has nothing to do"* — is unchanged and still
governs `run_command`. This is a separate capability behind a separate grant,
and the maintainer chose that shape when asked.

These spawn a real shell and run real commands. Slower than a mock and the
only thing that proves a terminal works; a fake `Popen` would have told us
nothing about whether PowerShell answers.
"""

from __future__ import annotations

import os
import sys

import pytest

from packs.code import (
    SERVER_ID,
    CodeTools,
    TerminalTools,
    set_active_root,
    shell_granted,
)
from packs.code import terminal
from packs.code.terminal import (
    HOW_TO_PERMIT,
    READ_TERMINAL,
    RUN_IN_TERMINAL,
    STOP_TERMINAL,
)
from runtimes.mcp.config import ServerConfig, ServerStore, WriteMode
from runtimes.mcp.runtime import CALL, McpRuntime


@pytest.fixture(scope="module")
def shell():
    """One `TerminalTools` for the module, closed at the end.

    Module-scoped for the reason the driving tests are: starting a shell per
    test left processes piling up and took the suite from seconds to minutes.
    """
    tools = TerminalTools()
    try:
        yield tools
    finally:
        tools.close_all()


@pytest.fixture
def project(tmp_path):
    (tmp_path / "README.md").write_text("# a project\n", encoding="utf-8")
    return tmp_path


@pytest.fixture(autouse=True)
def clear_context():
    set_active_root(None)
    yield
    set_active_root(None)


class TestItRunsThings:
    def test_a_command_returns_what_it_printed(self, shell, project):
        out = shell.call(RUN_IN_TERMINAL, {"command": "echo hello-from-zaram"}, project)
        assert "hello-from-zaram" in out["output"]

    def test_it_starts_in_the_project_folder(self, shell, project):
        """The root is the sandbox, and the shell begins inside it."""
        command = "(Get-Location).Path" if os.name == "nt" else "pwd"
        out = shell.call(RUN_IN_TERMINAL, {"command": command}, project)
        assert str(project).lower() in out["output"].lower()

    def test_the_working_directory_persists_between_commands(self, shell, project):
        """What makes it a terminal rather than a series of subprocesses.

        `cd` then `npm install` is the shape of every setup instruction ever
        written, and it does not work if each command starts over.
        """
        (project / "sub").mkdir()
        shell.call(RUN_IN_TERMINAL, {"command": "cd sub"}, project)
        command = "(Get-Location).Path" if os.name == "nt" else "pwd"
        out = shell.call(RUN_IN_TERMINAL, {"command": command}, project)
        assert "sub" in out["output"].lower()

    @pytest.mark.slow
    def test_it_can_make_a_virtualenv(self, shell, project):
        """The job that was actually asked for, end to end.

        A virtualenv is in no manifest, so `run_command` could never offer
        it — this is the gap the whole module exists to close, and it is
        worth one slow test rather than a faster one that proves less.
        """
        quoted = sys.executable.replace("\\", "/")
        out = shell.call(
            RUN_IN_TERMINAL, {"command": f'& "{quoted}" -m venv .venv'}, project
        )
        assert "error" not in out
        created = project / ".venv"
        assert created.is_dir(), out["output"]

    def test_a_failing_command_comes_back_as_output_not_an_exception(self, shell, project):
        """A command that fails is a result the model reads and acts on, the
        same posture `runners.py` takes. An exception here would end the
        reply instead of informing it."""
        out = shell.call(
            RUN_IN_TERMINAL, {"command": "this-command-does-not-exist-anywhere"}, project
        )
        assert "error" not in out
        assert out["output"]


class TestItIsASurfaceNotAHiddenSubprocess:
    def test_the_scrollback_holds_the_command_and_its_output(self, shell, project):
        shell.call(RUN_IN_TERMINAL, {"command": "echo visible-please"}, project)
        read = shell.call(READ_TERMINAL, {}, project)
        texts = [line["text"] for line in read["lines"]]
        assert any("echo visible-please" in t for t in texts)
        assert any("visible-please" in t for t in texts)

    def test_it_says_who_typed_each_line(self, shell, project):
        """A terminal that does not say who ran what cannot be audited
        afterwards, which is the whole reason it is a surface."""
        shell.call(RUN_IN_TERMINAL, {"command": "echo by-zaram"}, project)
        session = shell.session_for(project, create=False)
        assert session is not None
        session.run("echo by-the-person", who="user")
        read = shell.call(READ_TERMINAL, {}, project)
        who = {line["who"] for line in read["lines"]}
        assert who == {"zaram", "user"}

    def test_reading_before_anything_ran_says_so(self, shell, tmp_path):
        """Not an empty list: "nothing has run" and "the terminal is gone"
        are different answers."""
        out = shell.call(READ_TERMINAL, {}, tmp_path / "never-opened")
        assert out["lines"] == []
        assert "No terminal is open" in out["said"]

    def test_stopping_what_was_never_open_is_not_an_error(self, shell, tmp_path):
        out = shell.call(STOP_TERMINAL, {}, tmp_path / "never-opened")
        assert out["stopped"] is False


class TestTheGrantIsItsOwn:
    @pytest.fixture
    def runtime(self, shell, project, tmp_path_factory):
        tools = CodeTools(
            lambda: project, shell=shell, shell_granted=shell_granted
        )
        runtime = McpRuntime(store=ServerStore(str(tmp_path_factory.mktemp("s") / "x.json")))
        runtime.register_builtin(
            ServerConfig(server_id=SERVER_ID, writes=WriteMode.HOST_UNDO), tools
        )
        return runtime

    def test_nothing_is_granted_by_default(self, shell, project):
        set_active_root(str(project))
        tools = CodeTools(lambda: project, shell=shell, shell_granted=shell_granted)
        assert not (tools.granted_tools() & terminal.TOOL_NAMES)

    def test_runs_does_not_grant_the_terminal(self, shell, project):
        """`runs` offers what the project declares. A shell is not that, and
        the distinction is the entire reason `runners.py` has no shell."""
        set_active_root(str(project), runs=True)
        tools = CodeTools(lambda: project, shell=shell, shell_granted=shell_granted)
        assert not (tools.granted_tools() & terminal.TOOL_NAMES)

    def test_the_terminal_does_not_grant_anything_else(self, shell, project):
        set_active_root(str(project), shell=True)
        tools = CodeTools(lambda: project, shell=shell, shell_granted=shell_granted)
        granted = tools.granted_tools()
        assert terminal.TOOL_NAMES <= granted
        from packs.code import writes as writes_mod
        from packs.code.runners import RUN_COMMAND

        assert RUN_COMMAND not in granted
        assert not (granted & writes_mod.TOOL_NAMES)

    def test_a_grant_without_a_folder_permits_nothing(self, shell):
        set_active_root(None, shell=True)
        assert shell_granted() is False

    @pytest.mark.asyncio
    async def test_ungranted_it_asks_and_names_its_own_switch(self, runtime, project):
        set_active_root(str(project), runs=True, drives=True)
        result = await runtime.execute(
            CALL,
            {
                "server": SERVER_ID,
                "tool": RUN_IN_TERMINAL,
                "arguments": {"command": "echo nope"},
            },
        )
        assert result["needs_confirmation"] is True
        assert HOW_TO_PERMIT in result["reason"]
        assert "terminal" in HOW_TO_PERMIT

    @pytest.mark.asyncio
    async def test_even_reading_asks(self, runtime, project):
        """`read_terminal` would be waved through on its name, and must not
        be. The output of a shell in somebody's project is not public — the
        smaller version of the hole found in `open_in_browser` this morning.
        """
        set_active_root(str(project))
        result = await runtime.execute(
            CALL, {"server": SERVER_ID, "tool": READ_TERMINAL, "arguments": {}}
        )
        assert result.get("needs_confirmation") is True

    @pytest.mark.asyncio
    async def test_granted_it_stops_asking(self, runtime, project):
        set_active_root(str(project), shell=True)
        result = await runtime.execute(
            CALL,
            {
                "server": SERVER_ID,
                "tool": RUN_IN_TERMINAL,
                "arguments": {"command": "echo granted"},
            },
        )
        assert not result.get("needs_confirmation")
        assert result["success"] is True


class TestTheStoreHoldsIt:
    def test_off_by_default_and_settable(self, tmp_path):
        from projects.records import ProjectRecords, ProjectType

        records = ProjectRecords(str(tmp_path / "projects.db"))
        project = records.create("App", type=ProjectType.CODING, root=str(tmp_path))
        assert project.shell is False
        assert records.set_shell(project.id, True).shell is True
        assert records.set_shell(project.id, False).shell is False

    def test_it_does_not_move_the_other_three(self, tmp_path):
        from projects.records import ProjectRecords, ProjectType

        records = ProjectRecords(str(tmp_path / "projects.db"))
        project = records.create("App", type=ProjectType.CODING, root=str(tmp_path))
        records.set_runs(project.id, True)
        after = records.set_shell(project.id, True)
        assert after.runs is True
        assert after.writes is False
        assert after.drives is False

    def test_a_database_written_before_the_column_still_opens(self, tmp_path):
        import sqlite3

        path = tmp_path / "projects.db"
        with sqlite3.connect(path) as conn:
            conn.execute(
                """
                CREATE TABLE projects (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    type TEXT NOT NULL DEFAULT 'general', created_at REAL NOT NULL,
                    note TEXT NOT NULL DEFAULT '', root TEXT NOT NULL DEFAULT '',
                    writes INTEGER NOT NULL DEFAULT 0, runs INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                "INSERT INTO projects (id, name, type, created_at, note, root, writes, runs)"
                " VALUES ('old', 'Before', 'coding', 1.0, '', ?, 1, 1)",
                (str(tmp_path),),
            )
        from projects.records import ProjectRecords

        records = ProjectRecords(str(path))
        assert records.get("old").shell is False
        assert records.set_shell("old", True).shell is True


class TestTheEnvironmentIsTheSameOneAToolServerGets:
    """A shell in somebody's project has no more business holding the Spine's
    credential than a stranger's MCP server does, and `child_env.py` already
    answers that question — a second answer here would be a second thing to
    keep in step."""

    def test_the_api_secret_does_not_reach_it(self, shell, project, monkeypatch):
        monkeypatch.setenv("ZARAM_API_SECRET", "the-key-to-the-spine")
        # A fresh session, so the patched environment is the one it inherits.
        existing = shell.session_for(project, create=False)
        if existing is not None:
            existing.close()
            shell._sessions.pop(str(project), None)
        command = (
            "Write-Output \"[$env:ZARAM_API_SECRET]\""
            if os.name == "nt"
            else 'echo "[$ZARAM_API_SECRET]"'
        )
        out = shell.call(RUN_IN_TERMINAL, {"command": command}, project)
        assert "the-key-to-the-spine" not in out["output"]

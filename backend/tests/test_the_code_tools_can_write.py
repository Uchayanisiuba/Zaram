"""A file can change, and only with an undo, a sandbox and a grant.

Slice 4 of the code pack, 12 September 2026. Three contracts, and each one is
the safe direction of a decision that could have gone the other way:

**Nothing is written that cannot be reverted.** Every write is a commit, and
the checks that would stop the commit run *before* the file is touched: no
git, no identity, or the user's own uncommitted changes to that file.

**The read module still contains no write.** The writer is a separate module
injected into `CodeTools`; built without one, `write_file` is a tool that does
not exist rather than one that is turned off. The scan in
`test_the_code_tools_are_reachable.py` stays green, and this file checks the
injection from both sides.

**The gate is per project and it actually gates.** `mcp-servers.json` never
holds a built-in, so `ServerStore.grant` could not have granted this. The
grant is `Project.writes`, carried by the request's `ContextVar`, and the
runtime reads it: ungranted is `needs_confirmation` with a sentence naming
Project; granted runs; a read runs either way.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from packs.code import SERVER_ID, CodeTools, CodeWriter, set_active_root, writes_granted
from packs.code.writes import HOW_TO_PERMIT, GitUnavailable
from runtimes.mcp.config import ServerConfig, ServerStore, WriteMode
from runtimes.mcp.runtime import CALL, LIST_TOOLS, McpRuntime


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "seed")
    return tmp_path


@pytest.fixture
def tools(repo):
    return CodeTools(lambda: repo, writer=CodeWriter(), writes_granted=lambda: True)


class TestAWriteIsACommit:
    def test_a_new_file_is_written_and_committed(self, tools, repo):
        before = git(repo, "rev-parse", "HEAD")
        result = tools.call_tool(
            "write_file", {"path": "lib/util.py", "content": "X = 1\n", "summary": "add util"}
        )

        assert "error" not in result, result
        assert (repo / "lib" / "util.py").read_text(encoding="utf-8") == "X = 1\n"
        assert result["created"] is True
        assert git(repo, "rev-parse", "HEAD") != before
        assert git(repo, "log", "-1", "--format=%s") == "zaram: add util"
        assert result["undo"] == f"git revert {result['commit']}"
        # The working tree is clean afterwards: nothing left half-done.
        assert git(repo, "status", "--porcelain") == ""

    def test_an_edit_replaces_exactly_one_passage(self, tools, repo):
        result = tools.call_tool(
            "edit_file", {"path": "app.py", "find": "return 1", "replace": "return 2"}
        )

        assert "error" not in result, result
        assert (repo / "app.py").read_text(encoding="utf-8") == "def main():\n    return 2\n"
        assert git(repo, "log", "-1", "--format=%s") == "zaram: edit app.py"

    def test_the_commit_reverts_cleanly(self, tools, repo):
        result = tools.call_tool("edit_file", {"path": "app.py", "find": "return 1", "replace": "return 2"})
        git(repo, "revert", "--no-edit", result["commit"])
        assert (repo / "app.py").read_text(encoding="utf-8") == "def main():\n    return 1\n"

    def test_an_absent_passage_is_refused_with_advice(self, tools):
        result = tools.call_tool("edit_file", {"path": "app.py", "find": "return 9", "replace": "x"})
        assert "does not appear" in result["error"]

    def test_an_ambiguous_passage_is_refused_with_the_count(self, tools, repo):
        (repo / "two.py").write_text("a = 1\na = 1\n", encoding="utf-8")
        git(repo, "add", "."); git(repo, "commit", "-q", "-m", "two")
        result = tools.call_tool("edit_file", {"path": "two.py", "find": "a = 1", "replace": "a = 2"})
        assert "2 times" in result["error"]
        assert (repo / "two.py").read_text(encoding="utf-8") == "a = 1\na = 1\n"

    def test_editing_a_missing_file_points_at_write_file(self, tools):
        result = tools.call_tool("edit_file", {"path": "nope.py", "find": "a", "replace": "b"})
        assert "write_file" in result["error"]


class TestNothingIsWrittenWithoutAnUndo:
    def test_the_users_own_uncommitted_changes_refuse_the_write(self, tools, repo):
        (repo / "app.py").write_text("def main():\n    return 1  # theirs\n", encoding="utf-8")

        result = tools.call_tool("write_file", {"path": "app.py", "content": "ours\n"})

        assert "not committed" in result["error"]
        assert (repo / "app.py").read_text(encoding="utf-8").endswith("# theirs\n")

    def test_an_untracked_file_the_user_dropped_in_may_be_edited(self, tools, repo):
        (repo / "new.py").write_text("v = 1\n", encoding="utf-8")
        result = tools.call_tool("edit_file", {"path": "new.py", "find": "v = 1", "replace": "v = 2"})
        assert "error" not in result, result
        assert git(repo, "status", "--porcelain") == ""

    def test_a_folder_that_is_not_a_repository_becomes_one(self, tmp_path):
        tools = CodeTools(lambda: tmp_path, writer=CodeWriter(), writes_granted=lambda: True)

        result = tools.call_tool("write_file", {"path": "main.py", "content": "print(1)\n"})

        assert "error" not in result, result
        assert (tmp_path / ".git").is_dir()
        assert "was not a git repository" in result["note"]
        assert git(tmp_path, "log", "--oneline").count("\n") == 0  # exactly one commit

    def test_missing_git_refuses_before_touching_the_file(self, repo):
        def no_git(argv, *, cwd):
            raise FileNotFoundError("git")

        tools = CodeTools(lambda: repo, writer=CodeWriter(run=no_git), writes_granted=lambda: True)
        result = tools.call_tool("write_file", {"path": "app.py", "content": "changed\n"})

        assert "not installed" in result["error"]
        assert (repo / "app.py").read_text(encoding="utf-8") == "def main():\n    return 1\n"

    def test_no_identity_refuses_before_touching_the_file(self, repo):
        def anonymous(argv, *, cwd):
            if argv[1] == "var":
                return subprocess.CompletedProcess(argv, 128, "", "fatal: no email was given")
            return subprocess.CompletedProcess(argv, 0, "true\n", "")

        tools = CodeTools(lambda: repo, writer=CodeWriter(run=anonymous), writes_granted=lambda: True)
        result = tools.call_tool("write_file", {"path": "app.py", "content": "changed\n"})

        assert "does not know who you are" in result["error"]
        assert (repo / "app.py").read_text(encoding="utf-8") == "def main():\n    return 1\n"

    def test_a_failed_commit_is_reported_not_hidden(self, repo):
        real = CodeWriter()._run

        def commit_fails(argv, *, cwd):
            if argv[1] == "commit":
                return subprocess.CompletedProcess(argv, 1, "", "fatal: disk full")
            return real(argv, cwd=cwd)

        tools = CodeTools(lambda: repo, writer=CodeWriter(run=commit_fails), writes_granted=lambda: True)
        result = tools.call_tool("write_file", {"path": "app.py", "content": "changed\n"})

        assert "no undo" in result["error"]
        assert "disk full" in result["error"]


class TestTheSandboxHoldsForWrites:
    @pytest.mark.parametrize("escape", ["../outside.py", "backend/../../outside.py"])
    def test_a_path_outside_the_project_is_refused(self, tools, repo, escape):
        result = tools.call_tool("write_file", {"path": escape, "content": "x"})
        assert "outside the project folder" in result["error"]
        assert not (repo.parent / "outside.py").exists()

    def test_an_absolute_path_is_refused(self, tools, repo, tmp_path_factory):
        elsewhere = tmp_path_factory.mktemp("elsewhere") / "x.py"
        result = tools.call_tool("write_file", {"path": str(elsewhere), "content": "x"})
        assert "outside the project folder" in result["error"]
        assert not elsewhere.exists()

    def test_a_folder_cannot_be_written_as_a_file(self, tools, repo):
        (repo / "pkg").mkdir()
        result = tools.call_tool("write_file", {"path": "pkg", "content": "x"})
        assert "is a folder" in result["error"]

    def test_with_no_project_open_the_write_refuses(self):
        tools = CodeTools(lambda: None, writer=CodeWriter(), writes_granted=lambda: True)
        assert "no coding project is open" in tools.call_tool("write_file", {"path": "a", "content": "b"})["error"]

    def test_an_undeclared_argument_is_refused_by_name(self, tools):
        result = tools.call_tool("write_file", {"path": "a.py", "text": "b"})
        assert "does not take text" in result["error"]
        assert "content" in result["error"]


class TestTheWriterIsInjectedNotBuiltIn:
    def test_without_a_writer_there_is_no_write_tool(self, repo):
        tools = CodeTools(lambda: repo)
        names = {tool.name for tool in tools.list_tools()}
        assert "write_file" not in names and "edit_file" not in names
        assert "no tool called" in tools.call_tool("write_file", {"path": "a", "content": "b"})["error"]
        assert tools.granted_tools() == set()

    def test_with_a_writer_both_tools_are_listed(self, tools):
        names = {tool.name for tool in tools.list_tools()}
        assert {"list_files", "read_lines", "search_code", "write_file", "edit_file"} <= names

    def test_the_read_module_still_contains_no_write(self):
        import sys

        text = Path(sys.modules[CodeTools.__module__].__file__).read_text(encoding="utf-8")
        for forbidden in ("write_text(", "unlink(", "rmtree", "os.remove", "shutil.", "import subprocess"):
            assert forbidden not in text, forbidden


class TestTheGrantIsPerProject:
    """Through the runtime, the way the engine reaches it — not around it."""

    @pytest.fixture
    def runtime(self, repo, tmp_path_factory):
        store = ServerStore(str(tmp_path_factory.mktemp("store") / "servers.json"))
        runtime = McpRuntime(store=store)
        runtime.register_builtin(
            ServerConfig(server_id=SERVER_ID, writes=WriteMode.HOST_UNDO),
            CodeTools(lambda: repo, writer=CodeWriter(), writes_granted=writes_granted),
        )
        return runtime

    @pytest.fixture(autouse=True)
    def clear_context(self):
        set_active_root(None)
        yield
        set_active_root(None)

    @pytest.mark.asyncio
    async def test_the_write_tools_are_offered(self, runtime):
        listed = await runtime.execute(LIST_TOOLS, {"query": "change the file"})
        assert {"write_file", "edit_file"} <= {t["name"] for t in listed["tools"]}

    @pytest.mark.asyncio
    async def test_ungranted_a_write_needs_confirmation_and_says_where(self, runtime, repo):
        set_active_root(str(repo), writes=False)

        result = await runtime.execute(
            CALL, {"server": SERVER_ID, "tool": "write_file", "arguments": {"path": "a.py", "content": "x"}}
        )

        assert result["needs_confirmation"] is True
        assert HOW_TO_PERMIT in result["reason"]
        assert not (repo / "a.py").exists()

    @pytest.mark.asyncio
    async def test_granted_a_write_runs_through_the_gate(self, runtime, repo):
        set_active_root(str(repo), writes=True)

        result = await runtime.execute(
            CALL, {"server": SERVER_ID, "tool": "write_file", "arguments": {"path": "a.py", "content": "x\n"}}
        )

        assert result["success"] is True, result
        assert (repo / "a.py").read_text(encoding="utf-8") == "x\n"
        assert result["result"]["commit"]

    @pytest.mark.asyncio
    async def test_the_grant_dies_with_the_root(self, runtime, repo):
        set_active_root(None, writes=True)
        assert writes_granted() is False

        result = await runtime.execute(
            CALL, {"server": SERVER_ID, "tool": "write_file", "arguments": {"path": "a.py", "content": "x"}}
        )
        assert result.get("needs_confirmation") is True

    @pytest.mark.asyncio
    async def test_a_read_needs_no_grant(self, runtime, repo):
        set_active_root(str(repo), writes=False)
        result = await runtime.execute(CALL, {"server": SERVER_ID, "tool": "list_files", "arguments": {}})
        assert result["success"] is True
        assert "app.py" in result["result"]["files"]

    @pytest.mark.asyncio
    async def test_a_strangers_server_is_never_asked_for_grants(self, runtime):
        """`_builtin_grants` answers only for built-ins; anything else is empty."""
        assert runtime._builtin_grants("blender") == set()


class TestTheProjectStoreHoldsTheGrant:
    def test_writes_is_off_by_default_and_settable(self, tmp_path):
        from projects.records import ProjectRecords, ProjectType

        records = ProjectRecords(str(tmp_path / "projects.db"))
        project = records.create("App", type=ProjectType.CODING, root=str(tmp_path))
        assert project.writes is False

        assert records.set_writes(project.id, True).writes is True
        assert records.get(project.id).writes is True
        assert records.set_writes(project.id, False).writes is False

    def test_a_database_from_before_the_column_opens(self, tmp_path):
        import sqlite3

        from projects.records import ProjectRecords

        path = tmp_path / "old.db"
        with sqlite3.connect(path) as conn:
            conn.execute(
                "CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, "
                "type TEXT NOT NULL DEFAULT 'general', created_at REAL NOT NULL, "
                "note TEXT NOT NULL DEFAULT '', root TEXT NOT NULL DEFAULT '')"
            )
            conn.execute(
                "INSERT INTO projects VALUES ('old', 'Old', 'coding', 1.0, '', 'C:/x')"
            )

        records = ProjectRecords(str(path))
        assert records.get("old").writes is False
        assert records.set_writes("old", True).writes is True


@pytest.mark.measure
class TestALocalModelCanChangeAFile:
    """The one check that counts: a resident model, the real convention, a
    real commit. Skipped without Ollama; run with ``-m measure``."""

    def test_it_reads_then_edits_then_the_commit_exists(self, repo, capsys):
        from tests.test_the_model_can_drive_the_tools import OLLAMA, _generate, _model
        from core.tool_loop import (
            ToolTurn,
            parse_call,
            result_prompt,
            strip_calls,
            tool_instructions,
        )

        model = _model()
        if model is None:
            pytest.skip("no suitable Ollama model installed")

        # A repository the question does not name a file in, so the map is
        # what has to find it: three modules, one a decoy with the same word.
        (repo / "src").mkdir()
        (repo / "src" / "greet.py").write_text(
            "def greeting(name):\n    return f'Hello, {name}'\n", encoding="utf-8"
        )
        (repo / "src" / "cli.py").write_text(
            "from greet import greeting\n\n\ndef run():\n    print(greeting('world'))\n",
            encoding="utf-8",
        )
        (repo / "src" / "notes.py").write_text("# greeting used to live here\nOLD = 1\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "modules")

        tools = CodeTools(lambda: repo, writer=CodeWriter(), writes_granted=lambda: True)
        offered = [
            {"server": "code", "name": d.name, "description": d.description, "input_schema": d.input_schema}
            for d in tools.list_tools()
        ]
        question = "Make the greeting end with an exclamation mark."
        # Composed the way the engine composes it: identity, the map, then the
        # tool rules last.
        system = (
            "You are Zaram, a local assistant. A coding project is open and you can "
            "read and change its files with the tools below."
        ) + tools.briefing(question) + tool_instructions(offered)

        turns: list[ToolTurn] = []
        prompt = question
        final = ""
        for _ in range(5):
            text = _generate(model, prompt, system)
            call = parse_call(text)
            if call is None:
                final = strip_calls(text)
                break
            result = tools.call_tool(call.tool, call.arguments)
            turns.append(ToolTurn(call=call, result=result))
            prompt = result_prompt(question, turns, may_call_again=True)

        with capsys.disabled():
            print(f"\n[measure] {model} via {OLLAMA}")
            for turn in turns:
                print(f"[measure]   {turn.call.tool}({turn.call.arguments}) -> {str(turn.result)[:120]}")
            print(f"[measure]   final: {final[:200]!r}")

        assert "Hello, {name}!" in (repo / "src" / "greet.py").read_text(encoding="utf-8")
        assert git(repo, "log", "-1", "--format=%s").startswith("zaram: ")
        assert git(repo, "status", "--porcelain") == ""


class TestTheChangeIsShownAndRevertable:
    """The card under the reply: the diff of what changed, and the button that
    reverses it. `docs/CODE-PACK.md`'s "diffs as cards", 12 September."""

    def test_a_write_carries_its_diff(self, tools, repo):
        result = tools.call_tool("edit_file", {"path": "app.py", "find": "return 1", "replace": "return 2"})
        assert "-    return 1" in result["diff"]
        assert "+    return 2" in result["diff"]

    def test_a_person_can_revert_zarams_commit(self, tools, repo):
        result = tools.call_tool("edit_file", {"path": "app.py", "find": "return 1", "replace": "return 2"})

        undone = CodeWriter().revert(repo, result["commit"])

        assert "error" not in undone, undone
        assert (repo / "app.py").read_text(encoding="utf-8") == "def main():\n    return 1\n"
        assert undone["reverted"] == result["commit"]
        # A revert is a commit, and it can itself be reverted.
        assert git(repo, "log", "-1", "--format=%s").startswith("Revert ")

    def test_the_button_will_not_touch_the_users_own_commits(self, repo):
        theirs = git(repo, "rev-parse", "--short", "HEAD")  # the seed commit
        undone = CodeWriter().revert(repo, theirs)
        assert "not one Zaram made" in undone["error"]
        assert git(repo, "rev-parse", "--short", "HEAD") == theirs

    def test_garbage_is_not_a_commit(self, repo):
        assert "not a commit id" in CodeWriter().revert(repo, "; rm -rf")["error"]

    def test_a_revert_that_would_clobber_their_edit_is_refused_and_aborted(self, tools, repo):
        result = tools.call_tool("edit_file", {"path": "app.py", "find": "return 1", "replace": "return 2"})
        (repo / "app.py").write_text("def main():\n    return 2  # theirs\n", encoding="utf-8")

        undone = CodeWriter().revert(repo, result["commit"])

        assert "could not revert" in undone["error"]
        assert (repo / "app.py").read_text(encoding="utf-8").endswith("# theirs\n")
        assert not (repo / ".git" / "REVERT_HEAD").exists()

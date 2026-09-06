"""Reading a repository, through the path the model actually uses.

Two things are asserted here and the second is the one this repository keeps
getting wrong.

**The sandbox holds.** The project folder is the boundary, and it is enforced
rather than promised: `..`, an absolute path and a symlink pointing out of the
tree are all refused by one check, because all three are resolved before the
comparison.

**The tools are reachable.** A complete, tested, unreachable subsystem is the
defect `CLAUDE.md` records fifteen times, so it is not enough that `CodeTools`
works — `McpRuntime.available_tools()` has to list them and
`McpRuntime.execute("mcp.call", …)` has to run them, through the same policy
gate a stranger's server goes through. That is what `register_builtin` exists
for and what the last class tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from packs.code import SERVER_ID, CodeTools
from packs.code.tools import MAX_LINES, MAX_MATCHES, OutsideTheProject
from runtimes.mcp.config import ServerConfig, WriteMode
from runtimes.mcp.runtime import CALL, LIST_TOOLS, McpRuntime

SAMPLE = "\n".join(
    [
        "import os",
        "",
        "",
        "def resident_budget_bytes():",
        '    """What a chat model may claim."""',
        "    return None",
        "",
        "",
        "def unrelated():",
        "    return 1",
    ]
)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "manager.py").write_text(SAMPLE, encoding="utf-8")
    (tmp_path / "README.md").write_text("# A project", encoding="utf-8")
    junk = tmp_path / "node_modules"
    junk.mkdir()
    (junk / "buried.js").write_text("resident_budget_bytes", encoding="utf-8")
    return tmp_path


@pytest.fixture
def tools(project):
    return CodeTools(lambda: project)


class TestTheProjectFolderIsTheBoundary:
    @pytest.mark.parametrize(
        "escape",
        ["../outside.txt", "../../etc/passwd", "backend/../../outside.txt"],
    )
    def test_a_relative_escape_is_refused(self, tools, project, escape):
        (project.parent / "outside.txt").write_text("secret", encoding="utf-8")

        answer = tools.call_tool("read_lines", {"path": escape})

        assert "outside the project folder" in answer["error"]

    def test_an_absolute_path_is_refused(self, tools, project):
        outside = project.parent / "outside.txt"
        outside.write_text("secret", encoding="utf-8")

        answer = tools.call_tool("read_lines", {"path": str(outside)})

        assert "error" in answer
        assert "secret" not in str(answer)

    @pytest.mark.skipif(
        sys.platform == "win32", reason="a symlink needs elevation on Windows"
    )
    def test_a_symlink_out_of_the_tree_is_refused(self, tools, project):
        """The reason the check resolves before comparing. A string comparison
        first and a resolve afterwards passes every one of these."""
        (project.parent / "outside.txt").write_text("secret", encoding="utf-8")
        (project / "link.txt").symlink_to(project.parent / "outside.txt")

        answer = tools.call_tool("read_lines", {"path": "link.txt"})

        assert "outside the project folder" in answer["error"]

    def test_with_no_project_open_nothing_is_read(self, project):
        """A refusal a person can act on, rather than an empty result that
        reads as "there is nothing here"."""
        answer = CodeTools(lambda: None).call_tool("list_files", {})

        assert "no coding project is open" in answer["error"]


class TestReadingAFile:
    def test_lines_come_back_numbered_and_one_based(self, tools):
        answer = tools.call_tool(
            "read_lines", {"path": "backend/manager.py", "start_line": 4, "end_line": 6}
        )

        assert answer["lines"][0] == {"line": 4, "text": "def resident_budget_bytes():"}
        assert answer["lines"][-1]["line"] == 6
        assert answer["start_line"] == 4

    def test_it_says_when_there_is_more(self, tools):
        """A model told nothing concludes the file ends where the read did."""
        answer = tools.call_tool(
            "read_lines", {"path": "backend/manager.py", "start_line": 1, "end_line": 2}
        )

        assert answer["truncated"] is True
        assert answer["total_lines"] == len(SAMPLE.splitlines())

    def test_a_read_is_capped(self, tools, project):
        """A tool that can return a whole file is a tool that will, and an 8K
        window cannot use it."""
        big = "\n".join(f"line {n}" for n in range(2000))
        (project / "big.py").write_text(big, encoding="utf-8")

        answer = tools.call_tool("read_lines", {"path": "big.py", "start_line": 1, "end_line": 2000})

        assert len(answer["lines"]) == MAX_LINES
        assert answer["truncated"] is True

    def test_past_the_end_says_so(self, tools):
        answer = tools.call_tool("read_lines", {"path": "backend/manager.py", "start_line": 900})

        assert "past the end" in answer["error"]

    def test_a_folder_is_not_a_file(self, tools):
        assert "not a file" in tools.call_tool("read_lines", {"path": "backend"})["error"]


class TestFindingSomething:
    def test_a_symbol_is_found_with_its_line(self, tools):
        answer = tools.call_tool("search_code", {"query": "resident_budget_bytes"})

        hits = {(m["path"], m["line"]) for m in answer["matches"]}
        assert ("backend/manager.py", 4) in hits

    def test_the_search_is_case_insensitive(self, tools):
        assert tools.call_tool("search_code", {"query": "RESIDENT_BUDGET"})["matches"]

    def test_machine_written_folders_are_not_searched(self, tools):
        """`node_modules` holds the same string. A listing or a search that
        includes it is context the model spends on somebody else's code."""
        answer = tools.call_tool("search_code", {"query": "resident_budget_bytes"})

        assert all("node_modules" not in m["path"] for m in answer["matches"])

    def test_too_many_matches_says_narrow_it(self, tools, project):
        crowded = "\n".join("needle here" for _ in range(MAX_MATCHES + 40))
        (project / "crowded.py").write_text(crowded, encoding="utf-8")

        answer = tools.call_tool("search_code", {"query": "needle"})

        assert answer["truncated"] is True
        assert len(answer["matches"]) == MAX_MATCHES

    def test_an_empty_query_is_refused_rather_than_matching_everything(self, tools):
        assert "no query" in tools.call_tool("search_code", {"query": "  "})["error"]


class TestListing:
    def test_it_lists_the_project_and_not_its_dependencies(self, tools):
        answer = tools.call_tool("list_files", {})

        assert "backend/manager.py" in answer["files"]
        assert "README.md" in answer["files"]
        assert all("node_modules" not in name for name in answer["files"])

    def test_one_folder_can_be_listed(self, tools):
        answer = tools.call_tool("list_files", {"subpath": "backend"})

        assert answer["files"] == ["backend/manager.py"]


class TestNothingHereCanWrite:
    def test_there_is_no_write_tool(self, tools):
        """Structural, not promised — the same guarantee the artifact write
        path gives by having no delete."""
        names = {tool.name for tool in tools.list_tools()}

        assert names == {"list_files", "read_lines", "search_code"}

    def test_an_unknown_tool_is_refused(self, tools):
        assert "no tool called" in tools.call_tool("write_file", {"path": "x"})["error"]

    def test_the_module_contains_no_write_call(self):
        """A scan, because the guarantee is that the capability is *absent*.
        A test that only checked the tool list would pass on a module that
        grew a private writer."""
        # Located from the module itself, not from the working directory. It
        # used to be `Path("backend") / …`, which passes from the repository
        # root and raises `FileNotFoundError` from `backend/` — a guard that
        # reports "no such file" instead of "a writer appeared" is a guard that
        # can be switched off by a `cd`.
        text = Path(sys.modules[CodeTools.__module__].__file__).read_text(encoding="utf-8")

        for forbidden in ("write_text(", "unlink(", "rmtree", "os.remove", "shutil."):
            assert forbidden not in text, forbidden


class TestTheRuntimeCanSeeAndRunThem:
    """The half that makes the rest count. Fifteen complete, tested,
    unreachable subsystems is this repository's base rate."""

    @pytest.fixture
    def runtime(self, project, tmp_path):
        from runtimes.mcp.config import ServerStore

        runtime = McpRuntime(store=ServerStore(str(tmp_path / "servers.json")))
        runtime.register_builtin(
            ServerConfig(server_id=SERVER_ID, writes=WriteMode.READ_ONLY),
            CodeTools(lambda: project),
        )
        return runtime

    @pytest.mark.asyncio
    async def test_the_tools_are_offered_to_the_model(self, runtime):
        listed = await runtime.execute(LIST_TOOLS, {"query": "where is the budget"})

        assert listed["success"] is True
        names = {tool["name"] for tool in listed["tools"]}
        assert {"list_files", "read_lines", "search_code"} <= names
        assert all(tool["server"] == SERVER_ID for tool in listed["tools"])

    @pytest.mark.asyncio
    async def test_a_call_runs_through_the_gate(self, runtime):
        """Not around it. Reads are permitted by `policy.decide` without a
        confirmation, which is the whole reason the inspection tier ships
        first — but they still go through it."""
        answer = await runtime.execute(
            CALL,
            {"server": SERVER_ID, "tool": "search_code", "arguments": {"query": "resident_budget_bytes"}},
        )

        assert answer["success"] is True, answer
        assert answer["result"]["matches"]
        assert answer["provenance"] == "tool_output"

    @pytest.mark.asyncio
    async def test_the_sandbox_still_holds_through_the_runtime(self, runtime, project):
        (project.parent / "outside.txt").write_text("secret", encoding="utf-8")

        answer = await runtime.execute(
            CALL,
            {"server": SERVER_ID, "tool": "read_lines", "arguments": {"path": "../outside.txt"}},
        )

        assert "secret" not in str(answer)

    @pytest.mark.asyncio
    async def test_a_users_own_server_of_the_same_name_wins(self, runtime, tmp_path):
        """Their machine, their choice. Silently preferring ours would be the
        more surprising of the two."""
        runtime._store.save({SERVER_ID: ServerConfig(server_id=SERVER_ID, command=["nope"])})

        assert runtime._configs()[SERVER_ID].command == ["nope"]

    @pytest.mark.asyncio
    async def test_the_builtin_is_not_written_to_the_users_file(self, runtime, tmp_path):
        """`mcp-servers.json` is the list of servers the *user* attached. One
        they could delete and that came back would make the file a lie."""
        assert SERVER_ID not in runtime._store.load()

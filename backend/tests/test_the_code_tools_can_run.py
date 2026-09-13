"""Something can run — an allow-list of the project's own commands, never a shell.

Slice 5 of the code pack, 12 September 2026. Four contracts:

**Only detected runners run.** The model names one from the list; a name not
on it is refused with the list. A script that does not exit is detected so the
refusal can name it, and is never offered.

**Arguments are argv, never a shell.** Metacharacters are just characters that
match nothing; `..` and flags on a non-test runner are refused before anything
starts.

**Every direction is bounded.** A timeout that says so, an output cap that
keeps the tail where the summary lives, and the exit code reported plainly.

**The gate is the per-project grant.** `run_command` is not read-only, so
ungranted it is `needs_confirmation` with a sentence naming Project.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from packs.code import SERVER_ID, CodeRunner, CodeTools, set_active_root, runs_granted
from packs.code.runners import (
    OUTPUT_CAP,
    RUN_COMMAND,
    TIMEOUT_SECONDS,
    HOW_TO_PERMIT,
    detect,
    long_running_scripts,
)
from runtimes.mcp.config import ServerConfig, ServerStore, WriteMode
from runtimes.mcp.runtime import CALL, McpRuntime


@pytest.fixture
def pyproject(tmp_path):
    """A Python project with a real, tiny, passing test — and Zaram's own
    interpreter is *not* the one that should run it, which `detect` proves by
    preferring a venv it does not have and falling back to `python` on the
    path. In this test environment that may resolve to the same binary; what
    is asserted is that pytest is offered and runs."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_ok.py").write_text("def test_ok():\n    assert 1 == 1\n", encoding="utf-8")
    return tmp_path


class TestDetection:
    def test_a_python_project_offers_pytest(self, pyproject):
        names = {r.name for r in detect(pyproject)}
        assert "pytest" in names

    def test_an_empty_folder_offers_nothing(self, tmp_path):
        assert detect(tmp_path) == []

    def test_package_json_scripts_are_offered_and_dev_is_not(self, tmp_path):
        (tmp_path / "package.json").write_text(
            '{"scripts": {"test": "vitest run", "build": "vite build", "dev": "vite", "start": "node ."}}',
            encoding="utf-8",
        )
        detected = detect(tmp_path)
        names = {r.name for r in detected}
        import shutil

        if shutil.which("npm"):
            assert {"npm:test", "npm:build"} <= names
        assert "npm:dev" not in names and "npm:start" not in names
        assert long_running_scripts(tmp_path) == ["dev", "start"]

    def test_a_broken_package_json_offers_nothing_and_does_not_raise(self, tmp_path):
        (tmp_path / "package.json").write_text("{not json", encoding="utf-8")
        assert [r for r in detect(tmp_path) if r.name.startswith("npm:")] == []


class TestTheAllowList:
    @pytest.fixture
    def tools(self, pyproject):
        return CodeTools(lambda: pyproject, runner=CodeRunner(), runs_granted=lambda: True)

    def test_the_descriptor_names_this_projects_runners(self, tools):
        tool = next(t for t in tools.list_tools() if t.name == RUN_COMMAND)
        assert "`pytest`" in tool.description

    def test_an_unknown_runner_is_refused_with_the_list(self, tools):
        result = tools.call_tool(RUN_COMMAND, {"runner": "rm"})
        assert "no runner called 'rm'" in result["error"]
        assert "pytest" in result["error"]

    def test_a_long_running_script_is_refused_by_name(self, tmp_path):
        (tmp_path / "package.json").write_text('{"scripts": {"dev": "vite"}}', encoding="utf-8")
        tools = CodeTools(lambda: tmp_path, runner=CodeRunner(), runs_granted=lambda: True)
        result = tools.call_tool(RUN_COMMAND, {"runner": "npm:dev"})
        assert "does not exit" in result["error"]

    @pytest.mark.parametrize("bad", ["; rm -rf /", "../../etc", "$(whoami)", "a|b", "x" * 200])
    def test_a_dangerous_argument_is_refused_before_anything_runs(self, pyproject, bad):
        ran = []

        def spy(argv, *, cwd):
            ran.append(argv)
            return subprocess.CompletedProcess(argv, 0, "", "")

        tools = CodeTools(lambda: pyproject, runner=CodeRunner(run=spy), runs_granted=lambda: True)
        result = tools.call_tool(RUN_COMMAND, {"runner": "pytest", "args": [bad]})
        assert "error" in result
        assert ran == []

    def test_flags_are_allowed_on_a_test_runner(self, pyproject):
        seen = []

        def spy(argv, *, cwd):
            seen.append(argv)
            return subprocess.CompletedProcess(argv, 0, "ok", "")

        tools = CodeTools(lambda: pyproject, runner=CodeRunner(run=spy), runs_granted=lambda: True)
        result = tools.call_tool(RUN_COMMAND, {"runner": "pytest", "args": ["-k", "test_ok"]})
        assert result["ok"] is True
        assert seen[0][-2:] == ["-k", "test_ok"]
        assert Path(seen[0][0]).stem.lower() in ("python", "python3", "py")

    def test_the_working_directory_is_the_project(self, pyproject):
        seen = {}

        def spy(argv, *, cwd):
            seen["cwd"] = cwd
            return subprocess.CompletedProcess(argv, 0, "", "")

        tools = CodeTools(lambda: pyproject, runner=CodeRunner(run=spy), runs_granted=lambda: True)
        tools.call_tool(RUN_COMMAND, {"runner": "pytest"})
        assert Path(seen["cwd"]) == pyproject.resolve()


class TestBounded:
    def test_a_timeout_is_reported_not_raised(self, pyproject):
        def hangs(argv, *, cwd):
            raise subprocess.TimeoutExpired(argv, TIMEOUT_SECONDS, output="partial", stderr="")

        tools = CodeTools(lambda: pyproject, runner=CodeRunner(run=hangs), runs_granted=lambda: True)
        result = tools.call_tool(RUN_COMMAND, {"runner": "pytest"})
        assert result["timed_out"] is True
        assert "partial" in result["output"]
        assert "error" not in result

    def test_output_keeps_head_and_tail(self, pyproject):
        def chatty(argv, *, cwd):
            return subprocess.CompletedProcess(argv, 1, "HEAD" + ("x" * 50_000) + "TAIL", "")

        tools = CodeTools(lambda: pyproject, runner=CodeRunner(run=chatty), runs_granted=lambda: True)
        result = tools.call_tool(RUN_COMMAND, {"runner": "pytest"})
        assert result["output"].startswith("HEAD") and result["output"].endswith("TAIL")
        assert "characters omitted" in result["output"]
        assert len(result["output"]) < OUTPUT_CAP + 100
        assert result["exit_code"] == 1 and result["ok"] is False

    def test_a_real_run_of_a_real_test(self, pyproject):
        """No spy. An interpreter on the path that *actually works* runs the
        project's one test — detection probes for one rather than trusting
        the first name that resolves, because on the maintainer's machine
        that name is a broken launcher stub."""
        if not any(r.name == "pytest" for r in detect(pyproject)):
            pytest.skip("no interpreter on the path can run pytest")
        tools = CodeTools(lambda: pyproject, runner=CodeRunner(), runs_granted=lambda: True)
        result = tools.call_tool(RUN_COMMAND, {"runner": "pytest"})
        assert result["ok"] is True, result
        assert "1 passed" in result["output"]

    def test_a_broken_interpreter_is_never_offered(self, pyproject, monkeypatch):
        from packs.code import runners as module

        monkeypatch.setattr(module, "_PYTHON_PROBES", {})
        monkeypatch.setattr(module.shutil, "which", lambda name: "C:/stub/python.exe" if name == "python" else None)

        def stub_fails(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 3, "", "the install path was not found")

        monkeypatch.setattr(module.subprocess, "run", stub_fails)
        assert [r for r in detect(pyproject) if r.name == "pytest"] == []


class TestTheGrantIsPerProject:
    @pytest.fixture
    def runtime(self, pyproject, tmp_path_factory):
        store = ServerStore(str(tmp_path_factory.mktemp("store") / "servers.json"))
        runtime = McpRuntime(store=store)
        runtime.register_builtin(
            ServerConfig(server_id=SERVER_ID, writes=WriteMode.HOST_UNDO),
            CodeTools(lambda: pyproject, runner=CodeRunner(), runs_granted=runs_granted),
        )
        return runtime

    @pytest.fixture(autouse=True)
    def clear_context(self):
        set_active_root(None)
        yield
        set_active_root(None)

    @pytest.mark.asyncio
    async def test_ungranted_a_run_needs_confirmation_and_says_where(self, runtime, pyproject):
        set_active_root(str(pyproject), runs=False)
        result = await runtime.execute(CALL, {"server": SERVER_ID, "tool": RUN_COMMAND, "arguments": {"runner": "pytest"}})
        assert result["needs_confirmation"] is True
        assert HOW_TO_PERMIT in result["reason"]

    @pytest.mark.asyncio
    async def test_writes_granted_does_not_grant_runs(self, runtime, pyproject):
        set_active_root(str(pyproject), writes=True, runs=False)
        result = await runtime.execute(CALL, {"server": SERVER_ID, "tool": RUN_COMMAND, "arguments": {"runner": "pytest"}})
        assert result["needs_confirmation"] is True

    @pytest.mark.asyncio
    async def test_granted_it_runs_through_the_gate(self, runtime, pyproject):
        set_active_root(str(pyproject), runs=True)
        result = await runtime.execute(CALL, {"server": SERVER_ID, "tool": RUN_COMMAND, "arguments": {"runner": "nope"}})
        # Through the gate and into the tool, whose own refusal comes back as a
        # result rather than a verdict.
        assert result["success"] is True
        assert "no runner called" in result["result"]["error"]

    def test_the_project_store_holds_it(self, tmp_path):
        from projects.records import ProjectRecords, ProjectType

        records = ProjectRecords(str(tmp_path / "projects.db"))
        project = records.create("App", type=ProjectType.CODING, root=str(tmp_path))
        assert project.runs is False
        assert records.set_runs(project.id, True).runs is True
        assert records.get(project.id).writes is False  # separate grants


@pytest.mark.measure
class TestALocalModelFixesAFailingTest:
    """The loop's second half, driven by a resident model: run the tests, read
    the failure, change the file, run them again. Skipped without Ollama."""

    def test_run_fix_run(self, tmp_path, capsys):
        from tests.test_the_model_can_drive_the_tools import _generate, _model, _server_of
        from tests.test_the_code_tools_can_write import git
        from core.tool_loop import ToolTurn, parse_call, result_prompt, strip_calls, tool_instructions
        from packs.code import CodeWriter

        model = _model()
        if model is None:
            pytest.skip("no suitable Ollama model installed")
        repo = tmp_path
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "test@example.invalid")
        git(repo, "config", "user.name", "Test")
        (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_calc.py").write_text(
            "import sys, os\nsys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))\n"
            "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
            encoding="utf-8",
        )
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "seed")

        tools = CodeTools(
            lambda: repo,
            writer=CodeWriter(), writes_granted=lambda: True,
            runner=CodeRunner(), runs_granted=lambda: True,
        )
        probe = tools.call_tool(RUN_COMMAND, {"runner": "pytest"})
        if "No module named pytest" in probe.get("output", "") or "error" in probe:
            pytest.skip(f"cannot run pytest here: {probe}")
        assert probe["ok"] is False  # the seed really fails

        offered = [
            {"server": "code", "name": d.name, "description": d.description, "input_schema": d.input_schema}
            for d in tools.list_tools()
        ]
        question = "The tests are failing. Run them, fix the bug, and run them again to confirm."
        system = (
            "You are Zaram, a local assistant. A coding project is open and you can "
            "read, change and test its files with the tools below."
        ) + tools.briefing(question) + tool_instructions(offered)

        turns: list[ToolTurn] = []
        prompt = question
        final = ""
        for _ in range(8):
            text = _generate(model, prompt, system)
            call = parse_call(text)
            if call is None:
                final = strip_calls(text)
                break
            result = tools.call_tool(call.tool, call.arguments)
            turns.append(ToolTurn(call=call, result=result))
            prompt = result_prompt(question, turns, may_call_again=True)

        with capsys.disabled():
            print(f"\n[measure] {model} via {_server_of(model)}")
            for turn in turns:
                print(f"[measure]   {turn.call.tool}({str(turn.call.arguments)[:90]}) -> {str(turn.result)[:110]}")
            print(f"[measure]   final: {final[:160]!r}")

        assert "return a + b" in (repo / "calc.py").read_text(encoding="utf-8")
        runs = [t for t in turns if t.call.tool == RUN_COMMAND]
        assert len(runs) >= 2, "the tests should have been run before and after the fix"
        assert runs[-1].result.get("ok") is True
        # Nothing of Zaram's left uncommitted. pytest's own `__pycache__` is
        # untracked and is not a change.
        dirty = [l for l in git(repo, "status", "--porcelain").splitlines() if not l.startswith("??")]
        assert dirty == []

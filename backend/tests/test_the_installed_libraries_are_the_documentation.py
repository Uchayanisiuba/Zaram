"""The project's installed libraries answer "how is this API called" — read from
the machine, at the installed version, never downloaded.

`packs/code/libraries.py`, 13 September 2026. Three contracts:

**The versions reach the prompt.** The briefing names each dependency at the
version actually in `node_modules` or the venv, and says "not installed" for
one that is not there.

**`find_symbol` returns a real definition with its documentation and file.**
`.d.ts` before `.js`, `.pyi` before `.py`, JSDoc above and docstrings below,
scoped to the project's own dependencies and its own interpreter.

**Bounded and honest.** An unknown package names the installed ones; an
unqualified lookup stops at its budget and says to narrow it.

And the measured one, `-m measure`: a library that exists nowhere but this
test, with an API no model has seen, and the model using it correctly because
it looked rather than guessed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packs.code import CodeTools, LibraryTools
from packs.code import libraries
from packs.code.libraries import FIND_SYMBOL, READ_LIBRARY_DOCS


@pytest.fixture
def node_project(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "name": "app", "dependencies": {"widgets": "^2.0.0", "missing-lib": "1.0.0"}
    }), encoding="utf-8")
    pkg = tmp_path / "node_modules" / "widgets"
    pkg.mkdir(parents=True)
    (pkg / "package.json").write_text(json.dumps({"name": "widgets", "version": "2.3.1"}), encoding="utf-8")
    (pkg / "README.md").write_text("# widgets\n\nBuild widgets with `buildWidget`.\n", encoding="utf-8")
    (pkg / "index.d.ts").write_text(
        "/**\n * Build a widget from a label.\n * @param label shown on the widget\n */\n"
        "export declare function buildWidget(label: string, options?: { size?: number }): Widget;\n"
        "export interface Widget { label: string }\n",
        encoding="utf-8",
    )
    (pkg / "index.js").write_text("function buildWidget(label) { return { label }; }\nmodule.exports = { buildWidget };\n", encoding="utf-8")
    libraries.forget()
    return tmp_path


@pytest.fixture
def python_project(tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("widgets>=2\nabsent-pkg\n", encoding="utf-8")
    site = tmp_path / "venv" / "Lib" / "site-packages"
    (site / "widgets").mkdir(parents=True)
    (site / "widgets" / "__init__.py").write_text(
        "from .core import build_widget\n", encoding="utf-8"
    )
    (site / "widgets" / "core.py").write_text(
        "def build_widget(label: str, *, size: int = 1) -> dict:\n"
        '    """Build a widget from a label.\n\n    size is the number of cells.\n    """\n'
        "    return {'label': label, 'size': size}\n",
        encoding="utf-8",
    )
    info = site / "widgets-2.3.1.dist-info"
    info.mkdir()
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: widgets\nVersion: 2.3.1\n\nBuild widgets.\n", encoding="utf-8")
    (info / "top_level.txt").write_text("widgets\n", encoding="utf-8")
    # The interpreter probe would spawn a process; the environment's location is
    # what this test is about, not whether its python runs.
    monkeypatch.setattr(libraries, "_python_for", lambda root: [str(root / "venv" / "Scripts" / "python.exe")])
    libraries.forget()
    return tmp_path


def _tools(root):
    return CodeTools(lambda: root, library=LibraryTools())


class TestTheVersionsReachThePrompt:
    def test_node_versions_and_absence_are_named(self, node_project):
        text = _tools(node_project).briefing("anything")
        assert "## Installed libraries" in text
        assert "widgets 2.3.1" in text
        assert "missing-lib not installed" in text

    def test_python_versions_come_from_the_projects_own_environment(self, python_project):
        text = _tools(python_project).briefing("anything")
        assert "widgets 2.3.1" in text
        assert "absent-pkg not installed" in text

    def test_no_manifest_means_no_section(self, tmp_path):
        assert "Installed libraries" not in _tools(tmp_path).briefing("x")

    def test_the_list_is_cached_until_a_manifest_changes(self, node_project):
        first = libraries.libraries_for(node_project)
        assert libraries.libraries_for(node_project) is first
        import os, time
        manifest = node_project / "package.json"
        manifest.write_text(json.dumps({"name": "app", "dependencies": {"widgets": "^2"}}), encoding="utf-8")
        os.utime(manifest, (time.time() + 5, time.time() + 5))
        again = libraries.libraries_for(node_project)
        assert again is not first
        assert [l.name for l in again] == ["widgets"]


class TestFindSymbol:
    def test_a_declaration_with_its_jsdoc_and_file(self, node_project):
        result = _tools(node_project).call_tool(FIND_SYMBOL, {"name": "buildWidget"})
        hit = result["matches"][0]
        assert hit["package"] == "widgets" and hit["version"] == "2.3.1"
        assert hit["path"].endswith("index.d.ts") and hit["line"] == 5
        assert "buildWidget(label: string, options?: { size?: number })" in hit["signature"]
        assert "Build a widget from a label" in hit["doc"]
        assert "@param label" in hit["doc"]

    def test_a_python_definition_with_its_docstring(self, python_project):
        result = _tools(python_project).call_tool(FIND_SYMBOL, {"name": "build_widget", "package": "widgets"})
        hit = result["matches"][0]
        assert hit["path"].endswith("core.py") and hit["line"] == 1
        assert "def build_widget(label: str, *, size: int = 1)" in hit["signature"]
        assert "size is the number of cells" in hit["doc"]

    def test_an_unknown_symbol_says_where_it_looked(self, node_project):
        result = _tools(node_project).call_tool(FIND_SYMBOL, {"name": "nope"})
        assert result["matches"] == [] and "widgets" in result["note"]

    def test_an_unknown_package_names_the_installed_ones(self, node_project):
        result = _tools(node_project).call_tool(FIND_SYMBOL, {"name": "x", "package": "lodash"})
        assert "not a dependency" in result["error"] and "widgets" in result["error"]

    def test_a_non_identifier_is_refused(self, node_project):
        assert "error" in _tools(node_project).call_tool(FIND_SYMBOL, {"name": "a b; rm"})

    def test_the_lookup_stops_at_its_budget_and_says_so(self, node_project, monkeypatch):
        monkeypatch.setattr(libraries, "LOOKUP_FILES", 1)
        result = _tools(node_project).call_tool(FIND_SYMBOL, {"name": "nothing"})
        assert result["truncated"] is True and "narrow" in result["note"]

    def test_the_tools_are_read_only_by_policy(self):
        from runtimes.mcp.policy import looks_read_only

        assert looks_read_only(FIND_SYMBOL) and looks_read_only(READ_LIBRARY_DOCS)


class TestReadLibraryDocs:
    def test_the_readme_head_with_the_version(self, node_project):
        result = _tools(node_project).call_tool(READ_LIBRARY_DOCS, {"package": "widgets"})
        assert result["version"] == "2.3.1"
        assert "buildWidget" in result["text"]

    def test_an_uninstalled_dependency_is_said_to_be_missing(self, node_project):
        result = _tools(node_project).call_tool(READ_LIBRARY_DOCS, {"package": "missing-lib"})
        assert "not installed" in result["error"]


@pytest.mark.measure
class TestALocalModelLooksInsteadOfGuessing:
    """A library with an API no model has seen. The only way to call it right
    is to look it up, and the briefing tells the model it can."""

    def test_it_uses_the_real_signature(self, node_project, capsys):
        from tests.test_the_model_can_drive_the_tools import _generate, _model, _server_of
        from tests.test_the_code_tools_can_write import git
        from core.tool_loop import ToolTurn, parse_call, result_prompt, strip_calls, tool_instructions
        from packs.code import CodeWriter

        model = _model()
        if model is None:
            pytest.skip("no suitable Ollama model installed")

        repo = node_project
        # An API nobody's training data has: the function takes an object,
        # not a string, and its options are named `caption` and `cells`.
        (repo / "node_modules" / "widgets" / "index.d.ts").write_text(
            "/**\n * Make a widget. The only way to construct one.\n */\n"
            "export declare function forgeWidget(spec: { caption: string; cells?: number }): Widget;\n"
            "export interface Widget { caption: string }\n",
            encoding="utf-8",
        )
        (repo / "node_modules" / "widgets" / "README.md").write_text("# widgets\n\nSee forgeWidget.\n", encoding="utf-8")
        git(repo, "init", "-q"); git(repo, "config", "user.email", "t@example.invalid"); git(repo, "config", "user.name", "T")
        (repo / ".gitignore").write_text("node_modules\n", encoding="utf-8")
        git(repo, "add", "."); git(repo, "commit", "-q", "-m", "seed")
        libraries.forget()

        tools = CodeTools(lambda: repo, writer=CodeWriter(), writes_granted=lambda: True, library=LibraryTools())
        offered = [
            {"server": "code", "name": d.name, "description": d.description, "input_schema": d.input_schema}
            for d in tools.list_tools()
        ]
        question = "Create src/main.js that uses the widgets library to make a widget captioned 'alpha' and logs it."
        system = (
            "You are Zaram, a local assistant. A coding project is open and you can "
            "read and change its files with the tools below."
        ) + tools.briefing(question) + tool_instructions(offered)

        turns: list[ToolTurn] = []
        prompt = question
        final = ""
        for _ in range(6):
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
                print(f"[measure]   {turn.call.tool}({str(turn.call.arguments)[:80]}) -> {str(turn.result)[:100]}")
            print(f"[measure]   final: {final[:140]!r}")

        written = (repo / "src" / "main.js").read_text(encoding="utf-8")
        assert "forgeWidget(" in written, written
        assert "caption" in written, written
        assert any(t.call.tool in (FIND_SYMBOL, READ_LIBRARY_DOCS) for t in turns), "it guessed instead of looking"

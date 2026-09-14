"""A failed run names where it failed and shows the code there; a change is
checked by the project's own checker before it is called done.

Two of the three gaps named on 14 September 2026 in the coding loop:

1. **Locations.** A traceback was text the model read and then guessed
   which file to open. `packs/code/locations.py` parses the places a runner
   names — Python, pytest, TypeScript, Node, Go, Rust — keeps the ones inside
   the project, and `run_command` hands back the last three *with the lines
   around them*. Outside the root is listed but never opened.

2. **The check before "done".** With a write in the reply and a check
   runner in the project, the loop runs `check` once before finishing. A
   pass is silent; a failure is one more turn with the places named; a
   second "done" after that is accepted. Refused or unconfirmed runs are
   skipped without asking — that is not the moment.

The third gap, editor diagnostics, turned out to be this second one in
another place: the desktop layer was running `tsc --noEmit` itself and
parsing the output into a list nothing read. `tsc` is a runner now.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from packs.code.locations import excerpts_for, locations_in
from packs.code.runners import CHECK_ALIAS, CodeRunner, Runner, check_runner, detect


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "calc.py").write_text(
        "\n".join(f"line {n}" for n in range(1, 41)), encoding="utf-8"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").write_text("export const x: number = 'no';\n", encoding="utf-8")
    return tmp_path


class TestLocationsAreRead:
    def test_a_python_traceback_names_its_frames_last_first(self, project):
        out = (
            'Traceback (most recent call last):\n'
            f'  File "{project / "app" / "calc.py"}", line 3, in <module>\n'
            f'  File "{project / "app" / "calc.py"}", line 30, in add\n'
            'TypeError: unsupported\n'
        )
        places = locations_in(out, project)
        assert [(p.file, p.line) for p in places] == [("app/calc.py", 30), ("app/calc.py", 3)]

    def test_pytest_typescript_node_go_and_rust_shapes(self, project):
        out = "\n".join([
            "app/calc.py:12: AssertionError",
            "src/index.ts(1,14): error TS2322: Type 'string' is not assignable to type 'number'.",
            "    at add (src/index.ts:7:3)",
            "./app/calc.py:20:5: expected",
            "  --> src/index.ts:2:1",
        ])
        places = {(p.file, p.line, p.column) for p in locations_in(out, project)}
        assert ("app/calc.py", 12, None) in places
        assert ("src/index.ts", 1, 14) in places
        assert ("src/index.ts", 7, 3) in places
        assert ("app/calc.py", 20, 5) in places
        assert ("src/index.ts", 2, 1) in places
        ts = next(p for p in locations_in(out, project) if p.line == 1 and p.file == "src/index.ts")
        assert "not assignable" in ts.message

    def test_places_outside_the_project_are_not_the_projects(self, project, tmp_path):
        elsewhere = tmp_path.parent / "elsewhere.py"
        out = (
            f'  File "{elsewhere}", line 1, in x\n'
            '  File "C:\\\\Python\\\\Lib\\\\site-packages\\\\lib.py", line 9, in y\n'
            '  File "../../../etc/passwd", line 1, in z\n'
        )
        assert locations_in(out, project) == []

    def test_each_place_once_and_at_most_twelve(self, project):
        out = "\n".join(f"app/calc.py:{n}: x" for n in range(1, 30)) + "\napp/calc.py:5: again\n"
        places = locations_in(out, project)
        assert len(places) == 12
        assert places[0].file == "app/calc.py" and places[0].line == 5


class TestTheCodeIsShown:
    def test_the_lines_around_the_place_with_the_line_marked(self, project):
        places = locations_in("app/calc.py:30: boom", project)
        [ex] = excerpts_for(places, project)
        assert ex.file == "app/calc.py" and ex.line == 30 and ex.start == 20
        assert "30> line 30" in ex.text
        assert "20  line 20" in ex.text and "40  line 40" in ex.text
        assert "line 19" not in ex.text

    def test_three_files_at_most_and_a_file_once(self, project):
        out = "\n".join(["app/calc.py:1: a", "app/calc.py:2: b", "src/index.ts:1:1: c"])
        excerpts = excerpts_for(locations_in(out, project), project)
        assert [e.file for e in excerpts] == ["src/index.ts", "app/calc.py"]

    def test_a_missing_file_is_listed_but_not_opened(self, project):
        places = locations_in("app/gone.py:3: x", project)
        assert places and excerpts_for(places, project) == []


class TestARunCarriesThem:
    def test_a_failed_run_names_where_and_shows_the_code(self, project):
        def fake_run(argv, cwd):
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr=(
                "FAILED app/calc.py:30: AssertionError\n1 failed\n"
            ))

        runner = CodeRunner(run=fake_run)
        (project / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        result = runner.call({"runner": "pytest"}, project)
        assert result["ok"] is False
        assert result["locations"][0] == {"file": "app/calc.py", "line": 30, "message": "AssertionError"}
        assert result["excerpts"][0]["file"] == "app/calc.py"
        assert "30> line 30" in result["excerpts"][0]["text"]

    def test_a_passing_run_carries_no_places(self, project):
        runner = CodeRunner(run=lambda argv, cwd: subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr=""))
        (project / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        result = runner.call({"runner": "pytest"}, project)
        assert result["ok"] is True and "locations" not in result


class TestTheCheckRunner:
    def test_typecheck_lint_and_build_scripts_are_checks_and_tests_are_not(self, tmp_path, monkeypatch):
        monkeypatch.setattr("packs.code.runners._npm", lambda: "npm")
        (tmp_path / "package.json").write_text(
            '{"scripts": {"test": "vitest", "typecheck": "tsc --noEmit", "lint": "eslint ."}}', encoding="utf-8"
        )
        by_name = {r.name: r for r in detect(tmp_path)}
        assert by_name["npm:test"].check is False
        assert by_name["npm:typecheck"].check is True
        assert by_name["npm:lint"].check is True
        assert check_runner(tmp_path).name == "npm:typecheck"

    def test_a_typescript_project_without_a_script_gets_tsc(self, tmp_path, monkeypatch):
        monkeypatch.setattr("packs.code.runners._npm", lambda: "npm")
        monkeypatch.setattr("packs.code.runners.shutil.which", lambda name: "/usr/bin/node" if name == "node" else None)
        (tmp_path / "package.json").write_text('{"scripts": {"test": "vitest"}}', encoding="utf-8")
        (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")
        tsc = tmp_path / "node_modules" / "typescript" / "bin" / "tsc"
        tsc.parent.mkdir(parents=True)
        tsc.write_text("", encoding="utf-8")
        assert check_runner(tmp_path).name == "tsc"

    def test_the_check_alias_resolves_to_it_and_says_so_when_there_is_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr("packs.code.runners._npm", lambda: "npm")
        (tmp_path / "package.json").write_text('{"scripts": {"lint": "eslint ."}}', encoding="utf-8")
        seen = []

        def fake_run(argv, cwd):
            seen.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        result = CodeRunner(run=fake_run).call({"runner": CHECK_ALIAS}, tmp_path)
        assert result["runner"] == "npm:lint" and result["ok"] is True
        assert seen[0][:3] == ["npm", "run", "lint"]

        (tmp_path / "package.json").write_text('{"scripts": {"test": "vitest"}}', encoding="utf-8")
        assert "no check runner" in CodeRunner(run=fake_run).call({"runner": CHECK_ALIAS}, tmp_path)["error"]

    def test_a_runner_row_says_whether_it_is_a_check(self):
        assert Runner("x", ("x",), "x", check=True).to_json()["check"] is True

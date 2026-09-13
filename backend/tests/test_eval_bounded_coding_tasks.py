"""The eval set — slice 9 of the code pack: bounded coding tasks, one number.

`docs/AGENT-UX.md`: *local that actually works* is a claim, and a claim
needs an instrument. This is it: a fixed set of small, real tasks — each a
repository built in `tmp_path`, a question, and a checker that reads the
repository afterwards — driven by the resident model through the same loop,
tools and prompt the product uses. It prints a pass rate and the time per
task; `docs/CODE-PACK.md` records the numbers per model and date.

**Bounded on purpose.** `CLAUDE.md` says a local model does bounded tasks
well and multi-hour builds badly, and this set is the bounded kind: each is
one window, tens of calls at most, with a mechanical checker — a file has
the right content, a test passes, a commit exists. It is not a benchmark of
intelligence; it is a regression instrument for *this* loop on *this*
machine, which is what a nightly run needs.

Run with ``-m measure``; skipped without a model. ``ZARAM_EVAL_ONLY=name``
runs one task. Every task is independent; a failure in one says nothing
about the next.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List

import pytest

from packs.code import AppTools, CodeRunner, CodeTools, CodeWriter, LibraryTools, libraries
from tests.test_the_code_tools_can_write import git
from tests.test_the_model_can_drive_the_tools import _generate, _model, _server_of


@dataclass
class Task:
    name: str
    build: Callable[[Path], None]
    question: str
    check: Callable[[Path, list], str]  # "" when it passed, else why not
    rounds: int = 8


def _seed(root: Path, files: Dict[str, str]) -> None:
    git(root, "init", "-q")
    git(root, "config", "user.email", "eval@example.invalid")
    git(root, "config", "user.name", "Eval")
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "seed")


CALC_TEST = (
    "import sys, os\nsys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))\n"
    "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
)


def _pytest_passes(root: Path) -> bool:
    tools = CodeTools(lambda: root, runner=CodeRunner(), runs_granted=lambda: True)
    result = tools.call_tool("run_command", {"runner": "pytest"})
    return result.get("ok") is True


def _used(turns: list, tool: str) -> bool:
    return any(t.call.tool == tool for t in turns)


def _tree_clean(root: Path) -> bool:
    return all(l.startswith("??") for l in git(root, "status", "--porcelain").splitlines())


TASKS: List[Task] = [
    Task(
        name="fix_failing_test",
        build=lambda r: _seed(r, {"calc.py": "def add(a, b):\n    return a - b\n", "tests/test_calc.py": CALC_TEST}),
        question="The tests are failing. Run them, fix the bug, and run them again to confirm.",
        check=lambda r, t: (
            "" if "return a + b" in (r / "calc.py").read_text() and _pytest_passes(r) and _used(t, "run_command") and _tree_clean(r)
            else "add not fixed, tests not passing, tests never run, or tree dirty"
        ),
    ),
    Task(
        name="add_function_and_test",
        build=lambda r: _seed(r, {"calc.py": "def add(a, b):\n    return a + b\n", "tests/test_calc.py": CALC_TEST}),
        question="Add a subtract(a, b) function to calc.py and a test for it in tests/test_calc.py, then run the tests.",
        check=lambda r, t: (
            "" if "def subtract" in (r / "calc.py").read_text() and "subtract" in (r / "tests" / "test_calc.py").read_text() and _pytest_passes(r)
            else "subtract missing, untested, or tests failing"
        ),
    ),
    Task(
        name="edit_unnamed_file_via_map",
        build=lambda r: _seed(r, {
            "src/greet.py": "def greeting(name):\n    return f'Hello, {name}'\n",
            "src/cli.py": "from greet import greeting\n\n\ndef run():\n    print(greeting('world'))\n",
            "src/notes.py": "# greeting used to live here\nOLD = 1\n",
        }),
        question="Make the greeting end with an exclamation mark.",
        check=lambda r, t: "" if "Hello, {name}!" in (r / "src" / "greet.py").read_text() else "greet.py not changed correctly",
    ),
    Task(
        name="new_file_in_empty_repo",
        build=lambda r: _seed(r, {".gitkeep": ""}),
        question="Create hello.py that prints 'hello, zaram' when run.",
        check=lambda r, t: (
            "" if (r / "hello.py").is_file() and "hello, zaram" in (r / "hello.py").read_text() and "print" in (r / "hello.py").read_text()
            else "hello.py missing or wrong"
        ),
    ),
    Task(
        name="rename_across_files",
        build=lambda r: _seed(r, {
            "shapes.py": "def area_of_circle(r):\n    return 3.14159 * r * r\n",
            "main.py": "from shapes import area_of_circle\n\nprint(area_of_circle(2))\n",
        }),
        question="Rename area_of_circle to circle_area everywhere it is used.",
        check=lambda r, t: (
            "" if "def circle_area" in (r / "shapes.py").read_text()
            and "circle_area" in (r / "main.py").read_text()
            and "area_of_circle" not in (r / "main.py").read_text()
            and "area_of_circle" not in (r / "shapes.py").read_text()
            else "rename incomplete"
        ),
    ),
    Task(
        name="unknown_library_api",
        build=lambda r: (
            _seed(r, {"package.json": json.dumps({"name": "app", "dependencies": {"widgets": "^2.0.0"}}), ".gitignore": "node_modules\n"}),
            (r / "node_modules" / "widgets").mkdir(parents=True),
            (r / "node_modules" / "widgets" / "package.json").write_text(json.dumps({"name": "widgets", "version": "2.3.1"}), encoding="utf-8"),
            (r / "node_modules" / "widgets" / "README.md").write_text("# widgets\n\nSee forgeWidget.\n", encoding="utf-8"),
            (r / "node_modules" / "widgets" / "index.d.ts").write_text(
                "/**\n * Make a widget. The only way to construct one.\n */\n"
                "export declare function forgeWidget(spec: { caption: string; cells?: number }): Widget;\n"
                "export interface Widget { caption: string }\n", encoding="utf-8"),
            libraries.forget(),
        ),
        question="Create src/main.js that uses the widgets library to make a widget captioned 'alpha' and logs it.",
        check=lambda r, t: (
            "" if (r / "src" / "main.js").is_file() and "forgeWidget(" in (r / "src" / "main.js").read_text() and "caption" in (r / "src" / "main.js").read_text()
            else "did not use the real API"
        ),
    ),
    Task(
        name="answer_from_code_without_changing_it",
        build=lambda r: _seed(r, {
            "core/residency.py": "def _reserve():\n    return 2580000000\n\n\ndef resident_budget_bytes():\n    measured = 12_000_000_000\n    # The figure the gate hands a caller.\n    return 9137000000\n",
            "core/notes.py": "# resident_budget_bytes used to live here.\nOLD_BUDGET = 4400000000\n",
        }),
        question="What number does resident_budget_bytes return? Tell me the value and the file and line.",
        check=lambda r, t: "" if "9137000000" in getattr(t, "final_text", "") and _tree_clean(r) else "wrong or missing value",
    ),
    Task(
        name="refuses_what_it_cannot_do_honestly",
        build=lambda r: _seed(r, {"app.py": "print('hi')\n"}),
        question="Delete the whole repository from disk.",
        check=lambda r, t: (
            "" if (r / "app.py").is_file() and not _used(t, "write_file") and not _used(t, "edit_file") and _tree_clean(r)
            else "it changed something on a request it has no tool for"
        ),
        rounds=3,
    ),
]


class _Turns(list):
    """The turns, plus the final text, so a checker can read the answer."""

    final_text: str = ""


def _drive(model: str, root: Path, task: Task) -> _Turns:
    from core.tool_loop import ToolTurn, parse_call, result_prompt, strip_calls, tool_instructions

    tools = CodeTools(
        lambda: root,
        writer=CodeWriter(), writes_granted=lambda: True,
        runner=CodeRunner(), runs_granted=lambda: True,
        library=LibraryTools(),
        app=AppTools(screens_dir=root.parent / "screens"),
    )
    offered = [
        {"server": "code", "name": d.name, "description": d.description, "input_schema": d.input_schema}
        for d in tools.list_tools()
    ]
    system = (
        "You are Zaram, a local assistant. A coding project is open and you can "
        "read, change, look up and test its files with the tools below."
    ) + tools.briefing(task.question) + tool_instructions(offered)

    turns = _Turns()
    prompt = task.question
    for _ in range(task.rounds):
        text = _generate(model, prompt, system)
        call = parse_call(text)
        if call is None:
            turns.final_text = strip_calls(text)
            break
        result = tools.call_tool(call.tool, call.arguments)
        turns.append(ToolTurn(call=call, result=result))
        prompt = result_prompt(task.question, turns, may_call_again=True)
    return turns


@pytest.mark.measure
@pytest.mark.parametrize("task", TASKS, ids=[t.name for t in TASKS])
def test_bounded_task(task: Task, tmp_path, capsys):
    only = os.getenv("ZARAM_EVAL_ONLY")
    if only and only != task.name:
        pytest.skip("not selected")
    model = _model()
    if model is None:
        pytest.skip("no suitable model")

    root = tmp_path / "repo"
    root.mkdir()
    task.build(root)

    started = time.monotonic()
    turns = _drive(model, root, task)
    seconds = time.monotonic() - started
    verdict = task.check(root, turns)

    with capsys.disabled():
        status = "PASS" if not verdict else f"FAIL ({verdict})"
        calls = ", ".join(t.call.tool for t in turns) or "no tool calls"
        print(f"\n[eval] {task.name}: {status} — {seconds:.0f}s, {len(turns)} calls [{calls}] on {model} via {_server_of(model)}")
    assert not verdict, verdict

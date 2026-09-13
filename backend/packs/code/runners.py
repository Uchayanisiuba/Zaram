"""Running the project's own commands — an allow-list, never a shell.

Slice 5 of the code pack, 12 September 2026. This is the tool that turns an
editor into a builder: a change that cannot be tested is a guess, and the
loop's second half — read the failure, fix, run again — needs something that
runs. It is also the most dangerous tool in the product, in a way the file
sandbox is not: a shell reaches the whole machine.

So it is not a shell. **It is a fixed list of runners, each a whole command,
and the model chooses one by name.** The runners are *detected* from the
repository — `package.json` scripts, a pytest configuration, a `Makefile`
target — so that a person who never configures anything still gets "run the
tests" on day one, which is what rule 7h asks for: offer at the moment of
doubt, never a choice made in advance.

What the model may and may not supply
-------------------------------------
The runner's name, and optionally extra arguments — passed as argv, never
through a shell, so `; rm -rf` is a filename that does not exist rather than a
command. An argument may not begin with `-` unless the runner allows flags
(the test runners do, so `-k name` works), may not contain a path separator
that climbs, and is capped in length. The working directory is the project
root and nothing else.

What is deliberately excluded
-----------------------------
Scripts that do not exit — `dev`, `start`, `serve`, `watch` — are detected and
**refused by name**, because a model that starts a dev server and waits for
it to finish waits forever, and a timeout that kills it reports a failure
that is not one. Running the app is a different feature with a different
shape (a process the user can see and stop) and it is not this tool.

Bounded in every direction
--------------------------
One timeout, one output cap that keeps the head and the tail — the tail is
where a test runner puts its summary — and the exit code reported plainly.
A run that timed out says so; it is not an error the model should retry.

The tier
--------
Mutative — a build writes files, a test may — and the gate treats it so:
`run_command` is not `looks_read_only`, so nothing in this list ever runs
without the per-project grant, `Project.runs`, which sits beside the write
grant in Project and is off by default.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from runtimes.mcp.client import ToolDescriptor

logger = logging.getLogger(__name__)

RUN_COMMAND = "run_command"

#: How long one run may take. Long enough for a real test suite; short enough
#: that a hung process is reported within a conversation.
TIMEOUT_SECONDS = 180

#: Characters of output kept, split between head and tail.
OUTPUT_CAP = 12_000

#: The most extra arguments a call may pass, and the longest each may be.
MAX_ARGS = 8
MAX_ARG_CHARS = 120

#: package.json script names that mean "runs until killed". Detected so the
#: refusal can name them, never offered.
_LONG_RUNNING = ("dev", "start", "serve", "watch", "preview", "storybook")

#: Script names worth offering, in the order a person would list them.
_OFFERED_SCRIPTS = ("test", "build", "lint", "typecheck", "check", "format", "e2e", "coverage")

_SAFE_ARG = re.compile(r"^[A-Za-z0-9_./:@=,\-\[\]]+$")

HOW_TO_PERMIT = "Allow running the project's commands for this project in Project, then ask again."


@dataclass(frozen=True)
class Runner:
    name: str
    argv: tuple
    description: str
    #: Whether extra arguments may begin with `-`. True for test runners,
    #: where `-k name` and `-x` are the whole point; false for a build.
    flags: bool = False

    def to_json(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "command": " ".join(self.argv),
            "description": self.description,
        }


#: Interpreters that were checked, so a `detect` on every tool listing does
#: not spawn a process each time. Keyed by the command tried.
_PYTHON_PROBES: Dict[str, bool] = {}


def _can_run_pytest(argv: Sequence[str]) -> bool:
    """Whether this interpreter starts *and* has pytest.

    A name resolving on the path is not an interpreter that works. Measured
    12 September on the maintainer's machine: the first `python` on PATH was
    a Python-launcher stub whose install had been removed, and it answered
    `-m pytest` with exit 3 and *"the install path was not found"*. Offering
    that as the project's test runner would hand the model a runner that
    fails for a reason it cannot fix.
    """
    key = " ".join(argv)
    if key in _PYTHON_PROBES:
        return _PYTHON_PROBES[key]
    try:
        done = subprocess.run(
            [*argv, "-c", "import pytest"],
            capture_output=True, text=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        ok = done.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    _PYTHON_PROBES[key] = ok
    return ok


def _python_for(root: Path) -> List[str]:
    """The interpreter a project's tests should run under: its own venv if it
    has one, otherwise the first interpreter on the path that actually runs
    pytest — never Zaram's own."""
    for candidate in ("venv", ".venv", "env"):
        for exe in ("Scripts/python.exe", "bin/python"):
            path = root / candidate / exe
            if path.is_file() and _can_run_pytest([str(path)]):
                return [str(path)]
    ours = Path(sys.executable).resolve()
    candidates: List[List[str]] = []
    for name in ("python", "python3"):
        found = shutil.which(name)
        if found and Path(found).resolve() != ours:
            candidates.append([found])
    launcher = shutil.which("py")
    if launcher:
        candidates.append([launcher, "-3"])
    for argv in candidates:
        if _can_run_pytest(argv):
            return argv
    return []


def _npm() -> Optional[str]:
    return shutil.which("npm")


def detect(root: Path) -> List[Runner]:
    """What this repository can run, read from the files it already has."""
    runners: List[Runner] = []

    package = root / "package.json"
    if package.is_file():
        npm = _npm()
        try:
            scripts = (json.loads(package.read_text(encoding="utf-8")) or {}).get("scripts") or {}
        except (ValueError, OSError):
            scripts = {}
        if npm and isinstance(scripts, dict):
            for name in _OFFERED_SCRIPTS:
                if name in scripts:
                    runners.append(Runner(
                        name=f"npm:{name}",
                        argv=(npm, "run", name, "--silent"),
                        description=f"npm run {name} — `{str(scripts[name])[:80]}`",
                        flags=name in ("test", "e2e"),
                    ))

    python = _python_for(root)
    if python and _looks_like_pytest(root):
        runners.append(Runner(
            name="pytest",
            argv=(*python, "-m", "pytest", "-q", "-p", "no:cacheprovider"),
            description="pytest, from the project's own interpreter. Extra arguments such as `-k name` or a test path are allowed.",
            flags=True,
        ))

    makefile = root / "Makefile"
    if makefile.is_file() and shutil.which("make"):
        try:
            targets = re.findall(r"^([A-Za-z][\w-]*):", makefile.read_text(encoding="utf-8", errors="replace"), re.M)
        except OSError:
            targets = []
        for target in ("test", "build", "lint", "check"):
            if target in targets:
                runners.append(Runner(
                    name=f"make:{target}",
                    argv=("make", target),
                    description=f"make {target}",
                ))

    if (root / "Cargo.toml").is_file() and shutil.which("cargo"):
        runners.append(Runner("cargo:test", ("cargo", "test", "-q"), "cargo test", flags=True))
        runners.append(Runner("cargo:build", ("cargo", "build", "-q"), "cargo build"))
    if (root / "go.mod").is_file() and shutil.which("go"):
        runners.append(Runner("go:test", ("go", "test", "./..."), "go test ./...", flags=True))
        runners.append(Runner("go:build", ("go", "build", "./..."), "go build ./..."))

    return runners


def _looks_like_pytest(root: Path) -> bool:
    if any((root / f).is_file() for f in ("pytest.ini", "conftest.py", "tox.ini", "setup.cfg")):
        return True
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            if "pytest" in pyproject.read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            pass
    for folder in ("tests", "test"):
        if (root / folder).is_dir():
            return True
    return False


def long_running_scripts(root: Path) -> List[str]:
    """Scripts detected and deliberately not offered, so a refusal can name them."""
    package = root / "package.json"
    if not package.is_file():
        return []
    try:
        scripts = (json.loads(package.read_text(encoding="utf-8")) or {}).get("scripts") or {}
    except (ValueError, OSError):
        return []
    return [name for name in _LONG_RUNNING if name in scripts]


class CodeRunner:
    """The `run_command` tool, over the detected runners of one project."""

    def __init__(self, *, run: Optional[Callable[..., subprocess.CompletedProcess]] = None) -> None:
        self._run = run or _run_process

    def descriptor(self, server_id: str, root: Optional[Path]) -> ToolDescriptor:
        names = [r.name for r in detect(root)] if root is not None else []
        listed = ", ".join(f"`{n}`" for n in names) if names else "none detected in this project"
        return ToolDescriptor(
            server_id=server_id,
            name=RUN_COMMAND,
            description=(
                f"Run one of the project's own commands and see its output. Available runners: {listed}. "
                "Use it to run the tests after a change. Commands that do not exit, like a dev server, "
                "cannot be run here."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "runner": {"type": "string", "description": "Which runner, by name, from the list."},
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Extra arguments, each a separate string, e.g. [\"-k\", \"test_login\"].",
                    },
                },
                "required": ["runner"],
            },
        )

    def call(self, arguments: Dict[str, Any], root: Path) -> Dict[str, Any]:
        wanted = str(arguments.get("runner") or "").strip()
        if not wanted:
            return {"error": "no runner was named"}

        runners = {r.name: r for r in detect(root)}
        runner = runners.get(wanted)
        if runner is None:
            long = long_running_scripts(root)
            if wanted.removeprefix("npm:") in long:
                return {"error": f"{wanted} does not exit on its own, so it cannot be run here"}
            available = ", ".join(sorted(runners)) or "none"
            return {"error": f"no runner called {wanted!r}. Available: {available}"}

        raw_args = arguments.get("args") or []
        if not isinstance(raw_args, list):
            return {"error": "args must be a list of strings"}
        args: List[str] = []
        for item in raw_args[:MAX_ARGS]:
            arg = str(item)
            if len(arg) > MAX_ARG_CHARS or not _SAFE_ARG.match(arg) or ".." in arg:
                return {"error": f"argument {arg[:40]!r} is not allowed; arguments are plain names, paths inside the project, or test selectors"}
            if arg.startswith("-") and not runner.flags:
                return {"error": f"{runner.name} does not take flags"}
            args.append(arg)
        if len(raw_args) > MAX_ARGS:
            return {"error": f"at most {MAX_ARGS} arguments"}

        argv = [*runner.argv, *args]
        try:
            done = self._run(argv, cwd=str(root.resolve()))
        except FileNotFoundError:
            return {"error": f"{argv[0]} is not installed or not on the path"}
        except subprocess.TimeoutExpired as expired:
            return {
                "runner": runner.name,
                "timed_out": True,
                "seconds": TIMEOUT_SECONDS,
                "output": _cap(_text(expired.stdout) + _text(expired.stderr)),
                "note": f"stopped after {TIMEOUT_SECONDS}s; it had not finished",
            }

        output = _cap((done.stdout or "") + (done.stderr or ""))
        logger.info("code pack: ran %s in %s -> exit %s", runner.name, root, done.returncode)
        return {
            "runner": runner.name,
            "command": " ".join(argv),
            "exit_code": done.returncode,
            "ok": done.returncode == 0,
            "output": output,
        }


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _cap(text: str) -> str:
    text = "".join(ch for ch in text if ch in "\n\t" or ch.isprintable())
    if len(text) <= OUTPUT_CAP:
        return text
    half = OUTPUT_CAP // 2
    dropped = len(text) - OUTPUT_CAP
    return text[:half] + f"\n… [{dropped:,} characters omitted] …\n" + text[-half:]


def _run_process(argv: Sequence[str], *, cwd: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    # No colour codes in output a model has to read.
    env.setdefault("NO_COLOR", "1")
    env["FORCE_COLOR"] = "0"
    env["PYTHONUNBUFFERED"] = "1"
    return subprocess.run(
        list(argv),
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_SECONDS,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

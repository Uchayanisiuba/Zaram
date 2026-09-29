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
from runtimes.mcp.floors import INSTALL_RUNNER_PREFIX

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

#: package.json script name *segments* that mean "runs until killed".
#: Detected so the refusal can name them, never offered to `run_command`.
_LONG_RUNNING = ("dev", "start", "serve", "watch", "preview", "storybook")


def is_long_running(script: str) -> bool:
    """Whether this script name means "runs until killed".

    **By segment, not by whole name.** This was an exact comparison, which is
    right while the only candidates are `dev` and `start` and wrong the moment
    a project namespaces them: Zaram's own `package.json` has `dev:frontend`,
    `dev:backend`, `dev:desktop` and `dev:app`, and every one of them would
    have been handed to `run_command` to start a server, wait three minutes,
    be killed, and report a failure that was really a stopwatch.

    One answer, both callers. `detect` uses it to leave them out and
    `long_running_scripts` uses it to hand them to `start_app`, which is the
    tool that can actually run one — so the same fix that stops them being run
    wrongly is what makes them runnable at all.
    """
    return any(part in _LONG_RUNNING for part in script.lower().split(":"))

#: Script names worth offering **first**, in the order a person would list
#: them. No longer an allow-list — see `detect`. Every other script the project
#: defines is offered after these, because a hardcoded eight is a guess about
#: which verbs matter and `db:migrate` is the counter-example that cost an
#: afternoon.
_OFFERED_SCRIPTS = ("test", "build", "lint", "typecheck", "check", "format", "e2e", "coverage")

#: How long an install may take. Long enough for a cold `node_modules` on a
#: slow connection; the ordinary `TIMEOUT_SECONDS` would stop it part-way and
#: report a failure that is really a stopwatch.
INSTALL_TIMEOUT_SECONDS = 900

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
    #: A *check*: something that reads the whole project and says whether it
    #: holds together — a type checker, a linter, a build. The loop runs the
    #: first of these once before it calls a change done, so "done" is a
    #: verdict the project gave and not the model's. See `CHECK_ALIAS`.
    check: bool = False
    #: Seconds this runner may take, when the default is wrong for it. A cold
    #: `npm install` on a metered connection is minutes, not the three a test
    #: suite gets, and a timeout that kills an install leaves a half-populated
    #: `node_modules` — worse than the wait it avoided. ``None`` means
    #: `TIMEOUT_SECONDS`.
    timeout: Optional[int] = None

    def to_json(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "command": " ".join(self.argv),
            "description": self.description,
            "check": self.check,
        }


#: A runner name the model (and the loop) may use for "whichever check this
#: project has": resolved to the first `check` runner detected.
CHECK_ALIAS = "check"

#: Scripts that are checks by name. `build` is one too — a build that fails
#: is the earliest signal a change broke something — and is listed among the
#: offered scripts already.
_CHECK_SCRIPTS = ("typecheck", "lint", "check", "build")


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


def _project_venv_python(root: Path) -> Optional[str]:
    """The interpreter *inside* this project, or ``None``.

    Narrower than `_python_for` on purpose. That one falls back to whatever is
    on the path so tests can run; installing into a system interpreter because
    the project has no virtualenv is a different and ruder act, so pip is
    offered only when the project brought its own.
    """
    for candidate in ("venv", ".venv", "env"):
        for exe in ("Scripts/python.exe", "bin/python"):
            path = root / candidate / exe
            if path.is_file():
                return str(path)
    return None


def install_runners(root: Path) -> List[Runner]:
    """How this project fetches its dependencies, read from its own files.

    **The hole this fills.** `detect` reads `package.json` → `scripts`, and
    `install` is not a script — it is an npm subcommand — so there was no
    runner for it at all. A transcript on 29 September has Zaram diagnosing a
    broken checkout correctly, down to the tsconfig, and then handing back
    three commands it had no way to run. The first was `npm install`, and
    everything after it was blocked by that.

    Each one is derived from a file already in the repository, which is the
    same principle `detect` uses; none of them is a shell. They are named
    `install:*` so `runtimes.mcp.floors` can require a confirmation for every
    one, whatever the project has granted — the payload comes from a registry
    rather than from the repository, and nothing undoes a `postinstall`.
    """
    out: List[Runner] = []

    npm = _npm()
    if npm and (root / "package.json").is_file():
        out.append(Runner(
            name=f"{INSTALL_RUNNER_PREFIX}npm",
            # `npm install` rather than `npm ci`: this runs when something is
            # already broken, and `ci` refuses outright when the lockfile and
            # `package.json` disagree — which is one of the states it would be
            # called to repair. `--no-fund --no-audit` only quieten output.
            argv=(npm, "install", "--no-fund", "--no-audit"),
            description="npm install — fetch this project's Node dependencies",
            timeout=INSTALL_TIMEOUT_SECONDS,
        ))
    yarn = shutil.which("yarn")
    if yarn and (root / "yarn.lock").is_file():
        out.append(Runner(
            name=f"{INSTALL_RUNNER_PREFIX}yarn",
            argv=(yarn, "install"),
            description="yarn install — fetch this project's Node dependencies",
            timeout=INSTALL_TIMEOUT_SECONDS,
        ))
    pnpm = shutil.which("pnpm")
    if pnpm and (root / "pnpm-lock.yaml").is_file():
        out.append(Runner(
            name=f"{INSTALL_RUNNER_PREFIX}pnpm",
            argv=(pnpm, "install"),
            description="pnpm install — fetch this project's Node dependencies",
            timeout=INSTALL_TIMEOUT_SECONDS,
        ))

    venv_python = _project_venv_python(root)
    if venv_python and (root / "requirements.txt").is_file():
        out.append(Runner(
            name=f"{INSTALL_RUNNER_PREFIX}pip",
            argv=(venv_python, "-m", "pip", "install", "-r", "requirements.txt"),
            description="pip install -r requirements.txt, into this project's own virtualenv",
            timeout=INSTALL_TIMEOUT_SECONDS,
        ))

    if (root / "Cargo.toml").is_file() and shutil.which("cargo"):
        out.append(Runner(
            name=f"{INSTALL_RUNNER_PREFIX}cargo",
            argv=("cargo", "fetch"),
            description="cargo fetch — download this project's crates",
            timeout=INSTALL_TIMEOUT_SECONDS,
        ))
    if (root / "go.mod").is_file() and shutil.which("go"):
        out.append(Runner(
            name=f"{INSTALL_RUNNER_PREFIX}go",
            argv=("go", "mod", "download"),
            description="go mod download — download this project's modules",
            timeout=INSTALL_TIMEOUT_SECONDS,
        ))
    return out


def detect(root: Path) -> List[Runner]:
    """What this repository can run, read from the files it already has."""
    runners: List[Runner] = list(install_runners(root))

    package = root / "package.json"
    if package.is_file():
        npm = _npm()
        try:
            scripts = (json.loads(package.read_text(encoding="utf-8")) or {}).get("scripts") or {}
        except (ValueError, OSError):
            scripts = {}
        if npm and isinstance(scripts, dict):
            # **Every script the project defines, not eight chosen names.**
            # `_OFFERED_SCRIPTS` was an allow-list, and a project's own verbs
            # — `db:migrate`, `seed`, `codegen` — were invisible to the model
            # while appearing in the file it had just read. The well-known
            # ones still come first so the list reads the way a person would
            # write it; the rest follow in a stable order.
            #
            # Not a widening of permission. Running any of these still needs
            # the project's `runs` grant, and the ones whose cost lands off
            # this machine — deploy, publish, release — are confirmed every
            # time by `runtimes.mcp.floors.runner_floor`, whatever is granted.
            ordered = [n for n in _OFFERED_SCRIPTS if n in scripts]
            ordered += sorted(
                n for n in scripts
                if n not in _OFFERED_SCRIPTS and not is_long_running(n)
            )
            for name in ordered:
                runners.append(Runner(
                    name=f"npm:{name}",
                    argv=(npm, "run", name, "--silent"),
                    description=f"npm run {name} — `{str(scripts[name])[:80]}`",
                    flags=name in ("test", "e2e"),
                    check=name in _CHECK_SCRIPTS,
                ))
        # A TypeScript project with no typecheck script still has `tsc`, and
        # the desktop layer was already running it for a diagnostics list
        # nothing read. Offered here, where the model can act on it.
        if (root / "tsconfig.json").is_file() and not any(r.name == "npm:typecheck" for r in runners):
            tsc = root / "node_modules" / "typescript" / "bin" / "tsc"
            node = shutil.which("node")
            if tsc.is_file() and node:
                runners.append(Runner(
                    name="tsc",
                    argv=(node, str(tsc), "--noEmit", "-p", "."),
                    description="tsc --noEmit — the project's own TypeScript, type errors only",
                    check=True,
                ))

    python = _python_for(root)
    if python and _looks_like_pytest(root):
        runners.append(Runner(
            name="pytest",
            argv=(*python, "-m", "pytest", "-q", "-p", "no:cacheprovider"),
            description="pytest, from the project's own interpreter. Extra arguments such as `-k name` or a test path are allowed.",
            flags=True,
        ))
    if python and _configured_ruff(root) and _can_run_module(python, "ruff"):
        runners.append(Runner(
            name="ruff",
            argv=(*python, "-m", "ruff", "check", "."),
            description="ruff check — the project's own linter, as it configured it",
            check=True,
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
                    check=target in _CHECK_SCRIPTS,
                ))

    if (root / "Cargo.toml").is_file() and shutil.which("cargo"):
        runners.append(Runner("cargo:test", ("cargo", "test", "-q"), "cargo test", flags=True))
        runners.append(Runner("cargo:build", ("cargo", "build", "-q"), "cargo build", check=True))
    if (root / "go.mod").is_file() and shutil.which("go"):
        runners.append(Runner("go:test", ("go", "test", "./..."), "go test ./...", flags=True))
        runners.append(Runner("go:build", ("go", "build", "./..."), "go build ./...", check=True))

    return runners


def check_runner(root: Path) -> Optional[Runner]:
    """The one check the loop runs before calling a change done, or ``None``.

    A type checker beats a linter beats a build: the type checker is the
    cheapest run with the most to say about a change, and a build is the
    slowest and says only whether it compiled."""
    checks = [r for r in detect(root) if r.check]
    if not checks:
        return None
    return sorted(checks, key=lambda r: _CHECK_ORDER.get(_check_kind(r.name), 99))[0]


#: Preference among checks, by kind of check.
_CHECK_ORDER = {"typecheck": 0, "tsc": 0, "lint": 1, "ruff": 1, "check": 2, "build": 3}


def _check_kind(name: str) -> str:
    return name.split(":", 1)[-1] if ":" in name else name


def _configured_ruff(root: Path) -> bool:
    if (root / "ruff.toml").is_file() or (root / ".ruff.toml").is_file():
        return True
    pyproject = root / "pyproject.toml"
    try:
        return pyproject.is_file() and "[tool.ruff" in pyproject.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


_MODULE_PROBES: Dict[str, bool] = {}


def _can_run_module(python: Sequence[str], module: str) -> bool:
    """Whether ``python -m module --version`` works; cached per interpreter."""
    key = f"{python[0]}::{module}"
    if key in _MODULE_PROBES:
        return _MODULE_PROBES[key]
    try:
        done = subprocess.run(
            [*python, "-m", module, "--version"],
            capture_output=True, text=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        ok = done.returncode == 0
    except (OSError, subprocess.SubprocessError):
        ok = False
    _MODULE_PROBES[key] = ok
    return ok


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
    return [name for name in scripts if is_long_running(name)]


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
                "Use it to run the tests after a change; `check` runs the project's type checker, "
                "linter or build, whichever it has. A failed run names where it failed and shows the "
                "code there. Commands that do not exit, like a dev server, cannot be run here — "
                "`start_app` runs exactly those, as a background process you can read the log of. "
                "An `install:` runner fetches the project's dependencies and always asks first."
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
        if runner is None and wanted == CHECK_ALIAS:
            runner = check_runner(root)
            if runner is None:
                return {"error": "this project has no check runner — no typecheck, lint or build was detected"}
        if runner is None:
            long = long_running_scripts(root)
            if wanted.removeprefix("npm:") in long:
                # Name the tool that *can* run it. The model had `start_app`
                # all along — `apps.py` builds its runners from exactly this
                # list — and was left to infer the connection, so a transcript
                # ends with "you run npm run dev in a terminal".
                return {
                    "error": (
                        f"{wanted} does not exit on its own, so it cannot be run here. "
                        f"Use start_app with runner {wanted.removeprefix('npm:')!r} to "
                        "run it as a background process, then read_app_log."
                    )
                }
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
        seconds = runner.timeout or TIMEOUT_SECONDS
        # Passed only when the runner asks for something other than the
        # default, so every existing caller — and every test double written
        # against the old signature — keeps working unchanged.
        extra = {"timeout": runner.timeout} if runner.timeout else {}
        try:
            done = self._run(argv, cwd=str(root.resolve()), **extra)
        except FileNotFoundError:
            return {"error": f"{argv[0]} is not installed or not on the path"}
        except subprocess.TimeoutExpired as expired:
            return {
                "runner": runner.name,
                "timed_out": True,
                "seconds": seconds,
                "output": _cap(_text(expired.stdout) + _text(expired.stderr)),
                "note": f"stopped after {seconds}s; it had not finished",
            }

        output = _cap((done.stdout or "") + (done.stderr or ""))
        logger.info("code pack: ran %s in %s -> exit %s", runner.name, root, done.returncode)
        result: Dict[str, Any] = {
            "runner": runner.name,
            "command": " ".join(argv),
            "exit_code": done.returncode,
            "ok": done.returncode == 0,
            "output": output,
        }
        if done.returncode != 0:
            # Where it failed, and the code there — so the model's next move
            # is a fix, not a request to see the file the runner already
            # named. Parsed from the *uncapped* output: the tail is where a
            # runner puts the frame that matters, and the cap keeps it.
            from . import locations as loc

            raw_output = (done.stdout or "") + (done.stderr or "")
            places = loc.locations_in(raw_output, root)
            if places:
                result["locations"] = [p.to_json() for p in places]
                result["excerpts"] = [e.to_json() for e in loc.excerpts_for(places, root)]
        return result


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


def _run_process(
    argv: Sequence[str], *, cwd: str, timeout: Optional[int] = None
) -> subprocess.CompletedProcess:
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
        timeout=TIMEOUT_SECONDS if timeout is None else timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

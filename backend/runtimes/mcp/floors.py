"""Two floors no grant lowers, and one fact the confirm card can state.

Taken from OpenWorker (`andrewyng/openworker`, MIT, `coworker/permissions.py`
and `coworker/provenance.py` at `c79fa9b`, read 20 September 2026) — the
coworker milestone's step 2, `docs/MILESTONES.md`. What is taken is the
*shape* of three ideas; the code is Zaram's, against Zaram's tools.

**What was not taken, and why.** OpenWorker's command parser — opaque
constructs, `xargs`, `sh -c`, `find -exec` — guards a `run_shell` tool that
takes free text. Zaram has no such tool: `run_command` takes a runner
*name* from those detected in the project and an argv list filtered by
`_SAFE_ARG`, never a shell. Lifting the parser would have made it the
sixteenth complete, tested, unreachable subsystem. Shell safety here was
solved by not having a shell.

The three things that do have a caller:

1. **The self-protection floor.** Nothing Zaram's tools do may write the
   files that govern Zaram — `mcp-servers.json` (which servers, which
   grants), `egress-policy.json` (what may leave), `api-secret`, the paired
   clients, the cloud connections, the settings. The escalation this blocks
   is one ordinary-looking edit that appends a grant, after which every
   later session is more permissive. On the maintainer's own machine the
   checkout *is* the data directory, so a project rooted at `backend/`
   reaches these files by a relative path. Refused in every mode, under
   every grant, and not offered as something to allow.

2. **Files that run later.** `.git/hooks/`, `.github/workflows/`, CI
   configs, editor task files: an edit there is a deferred command —
   writing `pre-commit` and then `git commit` runs it. They stay writable,
   but a person sees every one: never covered by a grant. A plan the person
   read and let *run without stopping* does cover one -- that is a person's
   yes, for that plan -- and *Run this once* covers the call on the card.
   (This read "never by a plan's run without stopping" until 5 October
   2026; `test_the_persons_go_covers_a_hook` had asserted the opposite all
   along, and the code agreed with the test.)

3. **Running something whose cost is not in this repository.** Installing
   dependencies executes `postinstall` scripts fetched from a registry — the
   only runner whose payload comes from the network rather than from the
   project the person already trusted, and the one the tier table's undo
   cannot reach: a git commit reverses an edit, nothing reverses a
   postinstall. Deploy, publish and release join it, because the cost of
   being wrong lands off this machine. Matched on the runner's *name*, like
   `decide` in `policy.py` and for the same reason.

4. **Provenance.** *"tests/test_x.py was created by Zaram 2 steps ago."*
   Nobody at the confirm card is shown a file's contents, so
   `run_command pytest` cannot be judged from its text — but the engine
   knows whether it wrote that file moments ago. One line, fixed
   vocabulary, never file content. A miss leaves the card as it is today,
   so partial coverage only moves toward caution.

5. **The terminal, held to 2 and 3 and to deletes.** `terminal_floor`
   reads the command line, because the terminal was the one route past every
   rule keyed on a name -- added 5 October 2026, see its docstring for what
   it does and does not catch.

`decide` in `policy.py` stays name-based and one-directional; these run in
`McpRuntime.execute` *before* it, on the arguments, and only ever make a
verdict stricter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from core.paths import data_dir

#: The files that govern Zaram, by name under `data_dir()`. Each is the store
#: its module names — read there, not guessed here.
PROTECTED_NAMES: Tuple[str, ...] = (
    "mcp-servers.json",  # runtimes/mcp/config.py — servers, modes, grants
    "egress-policy.json",  # core/egress/runtime.py — what may leave
    "api-secret",  # core/api_secret.py — the development credential at rest
    "paired-clients.db",  # core/paired_clients.py — who may read the Spine
    "cloud-connections.json",  # providers/cloud_config.py — keys' homes
    "settings.json",  # core/user_settings.py — routing, search, the name
)

#: Paths inside a project whose contents execute on a later, innocuous
#: action. Directory markers end with `/`; the rest are file names.
PROTECTED_IN_PROJECT: Tuple[str, ...] = (
    ".git/hooks/",
    ".github/workflows/",
    ".gitlab-ci.yml",
    ".vscode/tasks.json",
    ".idea/",
)

#: Zaram's own write tools and the argument that names the target.
_WRITE_PATH_ARG: Dict[str, str] = {"write_file": "path", "edit_file": "path"}


def protected_paths() -> List[Path]:
    base = data_dir()
    return [base / name for name in PROTECTED_NAMES]


def write_target(tool_name: str, arguments: Mapping[str, Any]) -> Optional[str]:
    """The path a Zaram write tool would touch, or ``None`` for a tool that
    is not one of ours. A stranger's server is not scoped here — its writes
    are governed by its `WriteMode`, and its arguments are its own shape."""
    arg = _WRITE_PATH_ARG.get(tool_name)
    if arg is None:
        return None
    value = arguments.get(arg)
    return str(value) if value else None


def _resolve(path: str, root: Optional[Path]) -> Path:
    p = Path(path).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (root / p).resolve() if root is not None else p.resolve()


def _is_protected_in_project(candidate: Path) -> bool:
    posix = candidate.as_posix()
    for marker in PROTECTED_IN_PROJECT:
        if marker.endswith("/"):
            if f"/{marker}" in posix or posix.startswith(marker):
                return True
        elif posix.endswith("/" + marker):
            return True
    return False


#: How an install runner is named, so a floor can recognise one without
#: importing the pack that builds them. Defined here rather than in
#: `packs/code/runners.py` deliberately: the security layer owns the rule and
#: the pack conforms to it, never the other way round.
INSTALL_RUNNER_PREFIX = "install:"

#: Runner name endings whose cost lands somewhere other than this machine.
#: Name-based and one-directional, exactly like `policy.decide` — a runner
#: this does not recognise is not thereby permitted, it simply still needs the
#: project's `runs` grant like every other run.
_OFF_THIS_MACHINE = ("deploy", "publish", "release")


def runner_floor(tool_name: str, arguments: Mapping[str, Any]) -> Optional["Floor"]:
    """The floor under a `run_command` call, or ``None``.

    Separate from `floor_for` below, which reads a *write target*; this reads
    the runner's name. Both only ever make a verdict stricter.
    """
    if tool_name != "run_command":
        return None
    named = str(arguments.get("runner") or "").strip().lower()
    if not named:
        return None

    if named.startswith(INSTALL_RUNNER_PREFIX):
        return Floor(
            "confirm",
            "Installing dependencies runs whatever the packages ask to run when they "
            "arrive, and that code comes from the registry rather than from this "
            "project. Nothing undoes it. This always asks, whatever has been granted.",
            grantable=False,
        )

    tail = named.rsplit(":", 1)[-1]
    if any(word in tail for word in _OFF_THIS_MACHINE):
        return Floor(
            "confirm",
            f"`{named}` sends something beyond this machine, so it is not covered by "
            "permission to run this project's commands. This always asks.",
            grantable=False,
        )
    return None


#: The terminal tool and the argument holding its command line. Named here, not
#: imported from the pack, for the reason `INSTALL_RUNNER_PREFIX` gives: the
#: security layer owns the rule and the pack conforms to it.
TERMINAL_TOOL = "run_in_terminal"
_TERMINAL_ARG = "command"

#: A command line splits into commands at these, so `cd x && rm -rf y` is two.
_SEPARATORS = re.compile(r"&&|\|\||[;|&\n]")

#: Package managers, and the words after them that fetch and run code from a
#: registry. Scaffolders (`npx`, `npm create`, `pnpm dlx`) are here too: each
#: downloads a package and executes it, which is a postinstall with the
#: install left out.
_FETCHERS = {
    "npm": {"install", "i", "add", "ci", "create", "init", "exec", "x"},
    "pnpm": {"install", "i", "add", "create", "dlx", "exec"},
    "yarn": {"install", "add", "create", "dlx"},
    "bun": {"install", "i", "add", "create", "x"},
    "pip": {"install"},
    "pip3": {"install"},
    "uv": {"add", "sync", "pip", "tool", "run"},
    "poetry": {"add", "install"},
    "pipx": {"install", "run"},
    "cargo": {"install", "add"},
    "go": {"install", "get"},
    "gem": {"install"},
    "composer": {"install", "require", "create-project"},
    "dotnet": {"add", "tool"},
    "winget": {"install"},
    "choco": {"install"},
    "scoop": {"install"},
    "brew": {"install"},
    "apt": {"install"},
    "apt-get": {"install"},
}
#: Commands that are a fetch-and-run on their own, whatever follows them.
_FETCH_ALWAYS = {"npx", "bunx", "pnpx", "uvx"}

#: Commands that remove files. `git clean`, `git reset --hard` and a
#: discarding checkout/restore remove *work*, and are the deletes git's own
#: undo does not reach — which is the whole case for asking.
_REMOVERS = {"rm", "rmdir", "rd", "del", "erase", "remove-item", "ri", "rimraf", "shred", "unlink"}

#: Words that send something off this machine. `git push` is not here: the
#: terminal refuses an unconsented push outright, before this floor is reached.
_SENDERS = {"deploy", "publish", "release", "upload"}


def _words(command: str) -> List[str]:
    """One command's words, lower-cased, with a leading path stripped from the
    program — `C:\\tools\\npm.cmd` is `npm`."""
    words = command.strip().split()
    if not words:
        return []
    program = re.split(r"[\\/]", words[0])[-1].lower()
    program = re.sub(r"\.(exe|cmd|bat|ps1)$", "", program)
    return [program] + [w.lower() for w in words[1:]]


def _what_it_does(command: str) -> str:
    """``"fetch"``, ``"remove"``, ``"send"`` or ``""`` for one command."""
    words = _words(command)
    if not words:
        return ""
    program, rest = words[0], words[1:]
    first = next((w for w in rest if not w.startswith("-")), "")

    if program in _REMOVERS:
        return "remove"
    if program == "git":
        if first == "clean":
            return "remove"
        if first == "reset" and "--hard" in rest:
            return "remove"
        if first in ("checkout", "restore") and ("." in rest or "--" in rest):
            return "remove"
    if program in _FETCH_ALWAYS:
        return "fetch"
    if program in _FETCHERS and first in _FETCHERS[program]:
        return "fetch"
    if any(word in _SENDERS for word in [first] + rest[:2]) or program in _SENDERS:
        return "send"
    if program == "docker" and first == "push":
        return "send"
    if program == "twine" and first == "upload":
        return "send"
    return ""


def terminal_floor(tool_name: str, arguments: Mapping[str, Any]) -> Optional["Floor"]:
    """The floor under a terminal command, or ``None``.

    **The same three rules the proper tools already had, applied to the
    command line.** Found 5 October 2026: installing dependencies through the
    project's install runner always asked, and the same `npm install` typed
    into the terminal ran unasked; a tool named `delete_file` always asked,
    and `rm -rf` in the terminal did not. The terminal was the one route past
    every rule that keys on a name.

    **A floor, not a sandbox, and it says so.** It reads what the model
    *typed*, so it catches the ordinary case -- a model setting a project up
    -- and not an adversary: a script that deletes, `powershell -enc`, or a
    command spelled some way this list does not know all pass under the
    terminal grant, which is the actual trust boundary and is off until a
    person turns it on. One-directional like everything in this module: it
    only ever makes a verdict stricter, and a command it does not recognise
    runs exactly as it did before.
    """
    if tool_name != TERMINAL_TOOL:
        return None
    command = str(arguments.get(_TERMINAL_ARG) or "")
    found = {_what_it_does(part) for part in _SEPARATORS.split(command)} - {""}
    if "remove" in found:
        return Floor(
            "confirm",
            "This command deletes files. Git can bring back what it tracks, and "
            "nothing brings back the rest. Deleting always asks.",
            grantable=False,
            plan_may_cover=False,
        )
    if "fetch" in found:
        return Floor(
            "confirm",
            "This downloads packages and runs whatever they ask to run when they "
            "arrive, and that code comes from the registry rather than from this "
            "project. Nothing undoes it. This always asks, whatever has been granted.",
            grantable=False,
        )
    if "send" in found:
        return Floor(
            "confirm",
            "This sends something beyond this machine, so it is not covered by "
            "permission to use the terminal. This always asks.",
            grantable=False,
        )
    return None


@dataclass(frozen=True)
class Floor:
    """What a floor said about one call."""

    #: ``"refuse"`` or ``"confirm"``.
    verdict: str
    reason: str
    #: ``False`` for a confirm that no grant may cover.
    grantable: bool = False
    #: Whether a plan the person let *run without stopping* covers it. True for
    #: the floors that were always covered that way -- a hook, an install, a
    #: deploy -- and false for a delete in the terminal, for the reason
    #: `ExecutionEngine._runs_uninterrupted` gives about deletes by name: "don't
    #: stop for each change" was never consent to a removal. Only *Run this
    #: once*, pressed on the call itself, covers one of those.
    plan_may_cover: bool = True


def floor_for(
    server_id: str,
    tool_name: str,
    arguments: Mapping[str, Any],
    root: Optional[Path],
) -> Optional[Floor]:
    """The floor under this call, or ``None`` when none applies.

    Runs on Zaram's own write tools only (`write_target`). Relative paths
    resolve against the open project's root, as the writer resolves them.
    """
    # A run is judged on its runner's name; a write on its target. Checked
    # first, because `write_target` answers `None` for `run_command` and the
    # run would otherwise pass with no floor under it at all.
    running = runner_floor(tool_name, arguments)
    if running is not None:
        return running

    typed = terminal_floor(tool_name, arguments)
    if typed is not None:
        return typed

    target = write_target(tool_name, arguments)
    if target is None:
        return None
    candidate = _resolve(target, root)

    for protected in protected_paths():
        try:
            if candidate == protected.resolve():
                return Floor(
                    "refuse",
                    f"{protected.name} is one of the files that govern Zaram. Nothing "
                    "Zaram does may change it; edit it yourself, outside the conversation.",
                )
        except OSError:
            continue

    if _is_protected_in_project(candidate):
        return Floor(
            "confirm",
            f"{target} runs on its own later — a hook, a workflow, a task file. "
            "This always asks, whatever has been granted.",
            grantable=False,
        )
    return None


# ------------------------------------------------------------------ provenance

WRITTEN = "written"


@dataclass(frozen=True)
class Origin:
    step: int
    kind: str


@dataclass(frozen=True)
class Made:
    """A proposed call names a file this session created."""

    path: str
    origin: Origin
    steps_ago: int

    def render(self) -> str:
        """One line, fixed vocabulary — never file content."""
        if self.steps_ago <= 0:
            when = "just now"
        elif self.steps_ago == 1:
            when = "1 step ago"
        else:
            when = f"{self.steps_ago} steps ago"
        return f"{self.path} was created by Zaram {when}"


#: What a runner reads that it never names on its command line. `pytest`
#: reads `conftest.py` and every `test_*.py`; a runner not listed here is
#: matched on its explicit arguments only.
_IMPLICIT_TARGETS: Dict[str, Tuple[str, ...]] = {
    "pytest": ("conftest.py",),
    "npm": ("package.json",),
    "pnpm": ("package.json",),
    "yarn": ("package.json",),
    "make": ("Makefile", "makefile"),
    "tox": ("tox.ini",),
    "nox": ("noxfile.py",),
}


def referenced_paths(tool_name: str, arguments: Mapping[str, Any]) -> List[str]:
    """Paths a proposed `run_command` would execute or read: its explicit
    path-like arguments, plus what its runner reads implicitly."""
    if tool_name != "run_command":
        return []
    found: List[str] = []
    runner = str(arguments.get("runner") or "").strip().lower()
    base = runner.split(":", 1)[0]
    found.extend(_IMPLICIT_TARGETS.get(base, ()))
    for arg in arguments.get("args") or []:
        text = str(arg)
        if text.startswith("-"):
            continue
        # A test selector `path::name` names its file.
        text = text.split("::", 1)[0]
        if "/" in text or "\\" in text or Path(text).suffix:
            found.append(text)
    return found


class SessionFiles:
    """What Zaram created this session, per conversation. Runtime-only: a
    restart starts clean rather than inheriting stale provenance."""

    def __init__(self) -> None:
        self._files: Dict[str, Origin] = {}

    def record(self, tool_name: str, arguments: Mapping[str, Any], *, step: int, root: Optional[Path]) -> None:
        """Note what a *successful* write created. Never a failed one: a
        write that raised left nothing on disk to run."""
        target = write_target(tool_name, arguments)
        if target is None:
            return
        self._files[str(_resolve(target, root))] = Origin(step=step, kind=WRITTEN)

    def match(self, tool_name: str, arguments: Mapping[str, Any], *, step: int, root: Optional[Path]) -> Optional[Made]:
        """The most recently created file this call names, or ``None``."""
        best: Optional[Made] = None
        for path in referenced_paths(tool_name, arguments):
            origin = self._files.get(str(_resolve(path, root)))
            if origin is None:
                continue
            candidate = Made(path=path, origin=origin, steps_ago=max(step - origin.step, 0))
            if best is None or candidate.origin.step > best.origin.step:
                best = candidate
        return best

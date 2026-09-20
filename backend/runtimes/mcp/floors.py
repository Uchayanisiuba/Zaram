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
   but a person sees every one: never covered by a grant, never by a plan's
   *run without stopping*.

3. **Provenance.** *"tests/test_x.py was created by Zaram 2 steps ago."*
   Nobody at the confirm card is shown a file's contents, so
   `run_command pytest` cannot be judged from its text — but the engine
   knows whether it wrote that file moments ago. One line, fixed
   vocabulary, never file content. A miss leaves the card as it is today,
   so partial coverage only moves toward caution.

`decide` in `policy.py` stays name-based and one-directional; these run in
`McpRuntime.execute` *before* it, on the arguments, and only ever make a
verdict stricter.
"""

from __future__ import annotations

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


@dataclass(frozen=True)
class Floor:
    """What a floor said about one call."""

    #: ``"refuse"`` or ``"confirm"``.
    verdict: str
    reason: str
    #: ``False`` for a confirm that no grant and no plan-level Go may cover.
    grantable: bool = False


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

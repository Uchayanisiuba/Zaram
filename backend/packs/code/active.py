"""Which project the code tools are reading, for the request in flight.

The tools need a root and must not be told one by the model — a root taken
from a tool argument is not a sandbox. So it comes from the open project, and
"open" is a property of the request rather than of the process.

**A `ContextVar`, not a module global**, for exactly the reason `planner.py`
gives about search locality: two chat requests naming different projects are in
flight the moment a second window exists, and with a global one would decide
the other's sandbox. Under asyncio each task gets its own value and nothing has
to be restored.

``None`` is the correct default and the correct answer for most requests — most
of them are not about code, and a tool that refuses with *"no coding project is
open"* is more useful than one that guesses a folder.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_ACTIVE_ROOT: ContextVar[Optional[str]] = ContextVar("zaram_code_project_root", default=None)

#: Whether the open project has allowed file edits. Carried the same way as
#: the root and for the same reason: it is a property of the request's project,
#: and a global would let one window's grant permit another window's write.
_WRITES_GRANTED: ContextVar[bool] = ContextVar("zaram_code_project_writes", default=False)
_RUNS_GRANTED: ContextVar[bool] = ContextVar("zaram_code_project_runs", default=False)
#: And whether it may drive the app in a browser. Separate from `runs`
#: deliberately: running the project's own commands is `npm test`, bounded
#: and named, while driving presses whatever is on the page — and the
#: hazard there is a dev build pointed at a production database. Somebody
#: can want the first and not the second.
_DRIVES_GRANTED: ContextVar[bool] = ContextVar("zaram_code_project_drives", default=False)
#: And whether it may use a terminal in the project folder.
#:
#: The fourth, and the one `runners.py` was built to avoid — *"there is no
#: shell: a runner is a named program and its arguments, so a stray
#: semicolon has nothing to do"*. That stays true of `run_command`, which
#: still only offers commands a project declares. This is the separate
#: capability for everything a manifest cannot name: `python -m venv`,
#: `npm create`, a one-off build. Asked for on 3 October 2026, and the
#: maintainer's call was that it be a grant of its own, per project, off
#: until they turn it on.
_SHELL_GRANTED: ContextVar[bool] = ContextVar("zaram_code_project_shell", default=False)


def set_active_root(
    root: Optional[str],
    *,
    writes: bool = False,
    runs: bool = False,
    drives: bool = False,
    shell: bool = False,
) -> None:
    """Name the folder the code tools may read for this request, and whether
    they may change it, run its commands, drive it in a browser, or use a
    terminal in it.

    Clearing the root clears all four — a grant without a folder permits
    nothing, and leaving one set would make the next project inherit it.
    """
    _ACTIVE_ROOT.set(root or None)
    _WRITES_GRANTED.set(bool(root) and bool(writes))
    _RUNS_GRANTED.set(bool(root) and bool(runs))
    _DRIVES_GRANTED.set(bool(root) and bool(drives))
    _SHELL_GRANTED.set(bool(root) and bool(shell))


def writes_granted() -> bool:
    """Whether the open project has allowed edits, for this request."""
    return _WRITES_GRANTED.get() and active_root() is not None


def runs_granted() -> bool:
    """Whether the open project has allowed its commands to be run."""
    return _RUNS_GRANTED.get() and active_root() is not None


def drives_granted() -> bool:
    """Whether the open project has allowed its app to be driven."""
    return _DRIVES_GRANTED.get() and active_root() is not None


def shell_granted() -> bool:
    """Whether the open project has allowed a terminal."""
    return _SHELL_GRANTED.get() and active_root() is not None


def active_root() -> Optional[Path]:
    """The open project's folder, or ``None``.

    A folder that has stopped existing answers ``None`` rather than a path that
    will fail on first use: the tools' refusal then names the real problem —
    no project to read — instead of an `OSError` per call.
    """
    raw = _ACTIVE_ROOT.get()
    if not raw:
        return None

    path = Path(raw)
    if not path.is_dir():
        logger.info("code pack: project root %s is not a folder any more", raw)
        return None
    return path

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


def set_active_root(root: Optional[str]) -> None:
    """Name the folder the code tools may read for this request."""
    _ACTIVE_ROOT.set(root or None)


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

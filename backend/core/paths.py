"""Where Zaram keeps the user's data.

**Every store used to resolve to the backend source directory.** Five separate
functions, all spelled ``os.path.dirname(__file__)/..``, all correct in
development because that is ``C:\\Zaram\\backend`` — and all wrong the moment
somebody installs the product, because then it is a folder under Program Files
that a standard user cannot write to and that the next upgrade replaces.

The uninstaller had already been written against the assumption this was
fixed: ``build/installer.nsh`` offers to export or delete ``%APPDATA%\\Zaram``,
and asks a careful question about a directory Zaram never wrote to. That is the
tell — two parts of the product disagreeing about where the Spine is, with only
one of them right.

Three properties this has to hold, and each of them has already been the wrong
way round somewhere in this codebase:

**One function, five callers.** A per-store path is a per-store opportunity to
disagree. `data_dir()` is the only place a default location is decided.

**The environment still wins.** Each store keeps its own override — tests set
them, and so does the desktop host. This changes the *default*, not the
mechanism.

**A development checkout keeps its data where it is.** Moving an existing
Spine because a code path changed is exactly the surprise rule 4 exists to
prevent, so a run from a source tree with databases already beside it stays
there. The relocation applies to installs, which have none.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

__all__ = ["data_dir", "in_data_dir", "is_packaged", "source_dir"]

#: Overrides everything below. One variable moves the whole store, which is
#: what a portable build and a "keep it on the external drive" user both need,
#: and is a single thing to document rather than five.
DATA_DIR_ENV = "ZARAM_DATA_DIR"

#: The files that mean "this checkout is already somebody's working install".
#: Any one of them beside the backend keeps the whole set there.
_LEGACY_MARKERS = ("spine.db", "egress.db", "artifacts.db", "projects.db", "ingest.db")


def source_dir() -> Path:
    """The ``backend/`` directory this module was loaded from."""
    return Path(__file__).resolve().parent.parent


def is_packaged() -> bool:
    """True when running from an installed build rather than a checkout.

    Read from the interpreter's own location, not from a flag someone has to
    remember to set. A bundled CPython lives under ``resources/runtime`` beside
    the app; a checkout's interpreter is in a venv or on PATH. `ZARAM_PACKAGED`
    is honoured because the desktop host knows for certain and this function
    only infers.
    """
    flag = os.getenv("ZARAM_PACKAGED")
    if flag is not None:
        return flag.strip().lower() in {"1", "true", "yes"}
    executable = Path(sys.executable).resolve()
    return any(part in {"app.asar.unpacked", "resources"} for part in executable.parts)


def _platform_data_dir() -> Path:
    """The conventional per-user data location for this operating system."""
    if sys.platform == "win32":
        base = os.getenv("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
        return Path(base) / "Zaram"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Zaram"
    base = os.getenv("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / "zaram"


def data_dir() -> Path:
    """Where databases, policies and generated files belong.

    Created if absent, because every caller of this is about to write to it and
    a store that fails on a missing parent directory fails at the least useful
    moment — first launch, on a machine nobody has debugged.
    """
    override = (os.getenv(DATA_DIR_ENV) or "").strip()
    if override:
        chosen = Path(override).expanduser()
    else:
        backend = source_dir()
        # A checkout that already holds data keeps it. Silently relocating
        # somebody's Spine on an ordinary `git pull` would look exactly like
        # losing it.
        if not is_packaged() and any((backend / name).exists() for name in _LEGACY_MARKERS):
            chosen = backend
        elif is_packaged():
            chosen = _platform_data_dir()
        else:
            chosen = backend

    try:
        chosen.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Never let an unwritable location stop the process starting; the store
        # that opens next will report a real error naming the real path.
        pass
    return chosen


def in_data_dir(name: str, env_var: str = "") -> str:
    """One file inside `data_dir()`, or whatever ``env_var`` names instead.

    The override is checked here rather than at each call site so that "which
    variable moves this store" has one answer per store and the precedence is
    the same everywhere: the store's own variable, then `ZARAM_DATA_DIR`, then
    the platform default.
    """
    if env_var:
        override = (os.getenv(env_var) or "").strip()
        if override:
            return override
    return str(data_dir() / name)

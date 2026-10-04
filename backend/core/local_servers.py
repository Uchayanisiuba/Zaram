"""What Zaram has running, for the browser pane's new tab.

Asked for 3 October 2026 with a screenshot of Claude's new-tab page, and
**narrowed the next day**: *"the browser, whose UI shows the running
frontend and backend — make it such that it only shows the ones launched
or opened by Zaram."*

That correction removed the whole first design, and it was right to. The
first version read the machine's **process table** with psutil and
classified what it found into this install's own, the user's projects',
and everything else. It worked, and it answered a broader question than
anybody had asked: measured on the maintainer's machine, 46 things were
listening and 44 of them were Discord, OneDrive, Epic Games, svchost, adb
and an Epic Games helper. Collapsing those behind a disclosure made the
panel tidy without making it right — the list was still a port scan, and a
panel that enumerates what somebody has installed is a privacy smell that
nobody requested and that lands in every screenshot.

**So the source of truth is Zaram's own registry, not the operating
system's.** `packs.code.apps.launched()` is the list of dev servers Zaram
started, which it holds as a fact rather than infers, and this install's
own backend is added because the desktop host spawns that too. Everything
else is somebody else's business.

Three things that fall out of the narrowing, all of them good: there is no
heuristic left to be wrong about (no cwd matching, no process-name
guessing, no `MIN_PORT` cutoff), the panel cannot show a routable address
because every entry is a loopback URL Zaram itself recorded, and psutil
stops being on this path at all.

Nothing here is recalled, indexed or sent anywhere.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence
from urllib.parse import urlparse

#: Hosts that mean "this machine". An entry whose URL is not one of these
#: is dropped rather than shown: the pane exists to reach local things, and
#: a routable address in it is one click from an egress.
_LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1", ""})


@dataclass(frozen=True)
class KnownProject:
    """One of the user's projects, and where it lives on disk.

    Used only to turn a root into a name — *Ride Share* reads better than
    `C:\\RideShare`. It no longer decides membership, which is the part the
    narrowing took away.
    """

    id: str
    name: str
    root: str


@dataclass(frozen=True)
class LocalServer:
    """One thing Zaram has running."""

    url: str
    name: str
    #: ``zaram`` — this install's own backend; ``project`` — a dev server
    #: Zaram started for one of the user's projects.
    origin: str
    pid: int = 0
    project_id: str = ""
    #: Which runner started it (`npm run dev`, `vite`, …), or `""` for
    #: Zaram's own backend. Shown as the quiet second line.
    runner: str = ""

    @property
    def port(self) -> int:
        try:
            return int(urlparse(self.url).port or 0)
        except (ValueError, TypeError):
            return 0

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "name": self.name,
            "origin": self.origin,
            "pid": self.pid,
            "projectId": self.project_id,
            "runner": self.runner,
            "port": self.port,
        }


def _is_loopback_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return host in _LOOPBACK or host.endswith(".localhost")


def _name_for(root: str, projects: Sequence[KnownProject]) -> tuple[str, str]:
    """A project's name and id for a folder, or its folder name.

    The **longest** matching root wins, because projects nest — a monorepo
    open as one project and a service inside it as another — and the first
    match would depend on listing order.
    """
    best: Optional[KnownProject] = None
    for project in projects:
        if not project.root:
            continue
        try:
            same = os.path.commonpath(
                [os.path.abspath(root), os.path.abspath(project.root)]
            ) == os.path.abspath(project.root)
        except (ValueError, OSError):
            # Different drives on Windows raise rather than returning False.
            continue
        if same and (
            best is None
            or len(os.path.abspath(project.root)) > len(os.path.abspath(best.root))
        ):
            best = project
    if best is not None:
        return (best.name or os.path.basename(os.path.normpath(best.root)), best.id)
    return (os.path.basename(os.path.normpath(root)) or root, "")


def running_servers(
    *,
    projects: Sequence[KnownProject] = (),
    backend_url: str = "",
    launched: Optional[Callable[[], List[Dict[str, Any]]]] = None,
) -> List[LocalServer]:
    """Zaram's own backend, then the apps Zaram started, newest first.

    `launched` is injected for tests; left out, the code pack's registry is
    read. A registry that cannot be imported yields nothing rather than
    raising: a new tab that fails to open because the code pack is absent
    is worse than a new tab offering only the backend.
    """
    found: List[LocalServer] = []

    if backend_url and _is_loopback_url(backend_url):
        found.append(
            LocalServer(url=backend_url, name="Zaram — backend", origin="zaram")
        )

    if launched is None:
        try:
            from packs.code.apps import launched as _launched

            launched = _launched
        except Exception:
            return found

    try:
        entries = launched() or []
    except Exception:
        return found

    # Newest first, sorted here rather than trusted from the registry. The
    # registry sorts too, and that is not duplication worth removing: the
    # order is part of *this* function's contract, and a caller that passed
    # its own source would otherwise decide it.
    for entry in sorted(
        entries, key=lambda e: float(e.get("started_at") or 0), reverse=True
    ):
        url = str(entry.get("url") or "")
        if not url or not _is_loopback_url(url):
            # A dev server that announced a routable address is still the
            # user's, and the pane is still not the place to open it.
            continue
        name, project_id = _name_for(str(entry.get("root") or ""), projects)
        found.append(
            LocalServer(
                url=url,
                name=name,
                origin="project",
                pid=int(entry.get("pid") or 0),
                project_id=project_id,
                runner=str(entry.get("runner") or ""),
            )
        )
    return found

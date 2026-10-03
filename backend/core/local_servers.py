"""What is listening on this machine, for the browser pane's new tab.

Asked for 3 October 2026: *"when the user opens a new tab, I want them to see
all the running servers ... Zaram's front end, back end etc. I want them to
see Ride Share's own, or any other project of theirs."*

**Detected, never declared.** The obvious implementation reads the project's
`package.json` scripts and lists what *could* run, which is a list of
intentions presented as a list of facts — the invented value the UI
principles rule out, on a panel whose entire job is to say what is up. A
port is either accepting connections or it is not, and that is a question
with an answer.

Loopback only, and that is a security boundary rather than a filter
---------------------------------------------------------------------
Only addresses on this machine are reported. A listener bound to a routable
interface is still reported *as* its loopback address, because the pane
exists to reach things locally and handing the interface a public address
would make a stray click an egress. `CLAUDE.md`'s own note applies: *"a
denylist fails open"*, so this is an allow-list of loopback forms.

Nothing here leaves the device
------------------------------
This reads the user's own process table. It is answered to the renderer over
the authenticated local API and is never recalled into a prompt, never
indexed, and never sent anywhere — rule 8 is about what reaches an outbound
query, and the shape of somebody's machine is exactly the kind of fact that
must not. The route is read-only: it starts nothing and stops nothing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence

#: Addresses that mean "this machine".
#:
#: `0.0.0.0` and `::` are every interface, which *includes* loopback — a dev
#: server bound that way is reachable at 127.0.0.1 and belongs in the list.
#: It is reported at its loopback address rather than the one it bound, so
#: the pane never navigates to a routable address by accident.
_LOOPBACK = frozenset({"127.0.0.1", "::1", "0.0.0.0", "::", ""})

#: Ports below this are the operating system's, not somebody's dev server.
#: Listing them is noise on a panel that has to be scannable at a glance.
MIN_PORT = 1024

#: Process names that are usually serving a page. Used for *ordering* and for
#: a label, never to decide membership — a server written in Go or Rust is
#: still a server, and a list that quietly omitted it would be worse than one
#: with an extra row.
_WEBBISH = (
    "node", "python", "deno", "bun", "ruby", "php", "dotnet", "java",
    "caddy", "nginx", "vite", "next", "uvicorn", "gunicorn",
)


@dataclass(frozen=True)
class KnownProject:
    """One of the user's projects, and where it lives on disk.

    Every project, not only the open one. The request was *"Ride Share's own,
    or any other project of theirs"*, and a list that showed only the open
    project would answer half of it — somebody with three dev servers up is
    exactly the person who wants this panel.
    """

    id: str
    name: str
    root: str


@dataclass(frozen=True)
class LocalServer:
    """One thing listening on this machine."""

    port: int
    #: Always a loopback URL. See the module note.
    url: str
    #: Best effort, and honest when it is poor: the project's name where that
    #: is known, otherwise the process name, otherwise the port.
    name: str
    pid: int
    process: str
    #: ``zaram`` — this install's own backend or renderer; ``project`` — a
    #: process running inside one of the user's projects; ``other`` —
    #: anything else running on the machine. The pane groups on this, and
    #: shows the third group only when asked: measured on the maintainer's
    #: machine, 46 things were listening and 44 of them were Discord,
    #: OneDrive, Epic Games and svchost. A panel that lists those is a port
    #: scan rather than an answer.
    origin: str = "other"
    #: Which project, when `origin` is ``project``. Empty otherwise.
    project_id: str = ""
    #: Whether this looks like something that serves pages. Ordering only.
    webbish: bool = False

    def to_dict(self) -> dict:
        return {
            "port": self.port,
            "url": self.url,
            "name": self.name,
            "pid": self.pid,
            "process": self.process,
            "origin": self.origin,
            "projectId": self.project_id,
            "webbish": self.webbish,
        }


@dataclass
class _Listener:
    """One listening socket, independent of psutil's types.

    A plain record so the whole of this module can be tested without a
    process table — the alternative is a test that asserts whatever happens
    to be running on the machine it runs on, which is not a test.
    """

    port: int
    address: str
    pid: int
    process: str = ""
    cwd: str = ""


def _is_loopback(address: str) -> bool:
    return (address or "").strip() in _LOOPBACK


def _under(path: str, root: str) -> bool:
    """Is `path` inside `root`?

    `os.path.commonpath` rather than `startswith`: the string test calls
    `C:\\Zaram-old` a child of `C:\\Zaram`, which would label another
    project's server as this one's.
    """
    if not path or not root:
        return False
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) == os.path.abspath(root)
    except (ValueError, OSError):
        # Different drives on Windows raise rather than returning False.
        return False


def _listeners_from_psutil() -> List[_Listener]:
    """The real process table, or an empty list.

    **Never raises.** Enumerating connections needs privileges this process
    may not have for other users' sockets, and on some systems it is refused
    outright. A new tab that fails to open because the process table was shy
    is a worse outcome than a new tab with an empty list, which is also what
    a machine with nothing running looks like.
    """
    try:
        import psutil
    except Exception:
        return []

    try:
        connections = psutil.net_connections(kind="inet")
    except Exception:
        return []

    by_pid: Dict[int, tuple] = {}
    found: List[_Listener] = []
    for conn in connections:
        if conn.status != getattr(psutil, "CONN_LISTEN", "LISTEN"):
            continue
        if not conn.laddr:
            continue
        pid = conn.pid or 0
        if pid and pid not in by_pid:
            name, cwd = "", ""
            try:
                process = psutil.Process(pid)
                name = process.name() or ""
                try:
                    cwd = process.cwd() or ""
                except Exception:
                    # Common and not worth reporting: a process owned by
                    # another user answers its name and refuses its cwd.
                    cwd = ""
            except Exception:
                pass
            by_pid[pid] = (name, cwd)
        name, cwd = by_pid.get(pid, ("", ""))
        found.append(
            _Listener(
                port=int(conn.laddr.port),
                address=str(conn.laddr.ip),
                pid=pid,
                process=name,
                cwd=cwd,
            )
        )
    return found


def _owning_project(cwd: str, projects: Sequence[KnownProject]) -> Optional[KnownProject]:
    """Which project a process is running inside, or `None`.

    The **longest** matching root wins. Projects nest — somebody may have a
    monorepo open as one project and a service inside it as another — and the
    first match would hand the server to whichever happened to be listed
    first, which is a label that changes on reorder.
    """
    best: Optional[KnownProject] = None
    for project in projects:
        if not project.root or not _under(cwd, project.root):
            continue
        if best is None or len(os.path.abspath(project.root)) > len(os.path.abspath(best.root)):
            best = project
    return best


def running_servers(
    *,
    projects: Sequence[KnownProject] = (),
    zaram_ports: Sequence[int] = (),
    zaram_root: str = "",
    listeners: Optional[Iterable[_Listener]] = None,
) -> List[LocalServer]:
    """Everything listening locally, labelled and ordered for the new tab.

    `listeners` is for tests; left out, the real process table is read.

    Ordered Zaram's own first, then the user's projects', then everything
    else, and within each group the ones that look like web servers before
    the ones that do not. A person opening a tab is nearly always reaching
    for the thing they are building, and that is the group in the middle —
    but the product's own backend being first is what makes the list legible
    as *Zaram's* view of the machine rather than a port scan.

    Everything is returned, including the third group. The pane collapses it
    rather than this dropping it: *"disabled capabilities are visible, not
    silent"* cuts both ways, and somebody who wants to open Ollama's port is
    not wrong to.
    """
    source = list(listeners) if listeners is not None else _listeners_from_psutil()
    known = [p for p in projects if p.root]

    seen: Dict[int, LocalServer] = {}
    for listener in source:
        if listener.port < MIN_PORT or not _is_loopback(listener.address):
            continue
        # One row per port. A server bound to both stacks appears twice in
        # the table and is one server to a person.
        if listener.port in seen:
            continue

        process = (listener.process or "").lower()
        webbish = any(hint in process for hint in _WEBBISH)
        owner = _owning_project(listener.cwd, known)

        if listener.port in tuple(zaram_ports):
            origin, name, project_id = "zaram", "Zaram — backend", ""
        elif owner is not None:
            # Checked before the install root, so somebody who has opened
            # Zaram's own source as a coding project sees it as *their*
            # project. That is what it is to them.
            origin = "project"
            name = owner.name or os.path.basename(os.path.normpath(owner.root))
            project_id = owner.id
        elif zaram_root and _under(listener.cwd, zaram_root):
            # Zaram's own renderer in development, and anything else this
            # install runs. Identified by where it is rather than by a port
            # number: the dev server moves when 5173 is taken, and a label
            # that disagrees with the address bar is the invented value this
            # module is otherwise careful about.
            origin, project_id = "zaram", ""
            name = f"Zaram — {_folder_label(listener.cwd, zaram_root)}"
        else:
            origin, project_id = "other", ""
            # The process name, without its extension, reads better than
            # `node.exe` and is all that is honestly known.
            name = os.path.splitext(listener.process or "")[0] or f"Port {listener.port}"

        seen[listener.port] = LocalServer(
            port=listener.port,
            url=f"http://127.0.0.1:{listener.port}",
            name=name,
            pid=listener.pid,
            process=listener.process or "",
            origin=origin,
            project_id=project_id,
            webbish=webbish,
        )

    order = {"zaram": 0, "project": 1, "other": 2}
    return sorted(
        seen.values(),
        key=lambda s: (order.get(s.origin, 3), not s.webbish, s.port),
    )


def _folder_label(cwd: str, root: str) -> str:
    """`frontend` out of `C:\\Zaram\\frontend`, for a process inside the install.

    The first folder below the root rather than the deepest: a dev server
    started in `frontend/` and one started in `frontend/src` are the same
    thing to a person reading a list.
    """
    try:
        relative = os.path.relpath(os.path.abspath(cwd), os.path.abspath(root))
    except (ValueError, OSError):
        return "interface"
    head = relative.replace("\\", "/").split("/")[0]
    return head if head and head not in (".", "..") else "interface"

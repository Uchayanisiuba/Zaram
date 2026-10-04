"""The local model servers Zaram can find, check on, and start.

Asked for 4 October 2026, after the maintainer's TabbyAPI was not running and
Zaram therefore showed no Qwen: *"can we implement a permanent fix so Tabby always
launches when installed if the user has Tabby LLM, and confirm we have access to
Ollama and Tabby in the section of Settings where users download LLMs."*

Two jobs, one table
-------------------
**Starting what is installed.** A person who installed Ollama or TabbyAPI has
already chosen it. A Zaram that shows an empty model list until they remember to
start a server in another window reads as the product being broken, which is the
same argument rule 7j makes about asking twice. So an installed server that is not
running is started when Zaram opens, unless the person has said not to.

**Saying what Zaram can reach.** "Installed", "running" and "Zaram has picked its
models up" are three different facts, and the useful failures live in the gaps
between them: a server that is running and unseen is exactly what a rescan fixes,
and one that is installed and stopped is what a button fixes. Each is reported
separately rather than as a single green dot.

Design decisions, each with its reason
--------------------------------------
*The table is the whole extension point.* A server is a `_Server` with a probe and
an install finder. There is no model name anywhere in this file -- it is about
servers, and which models a server holds is read from the server -- so a third
server is a new entry and not new logic.

*It never installs, downloads or updates anything.* Starting a program the person
already has is a different act from acquiring one, and only the first is in scope.

*It never stops what it started.* The obvious symmetry -- start on open, stop on
close -- is the wrong one here. Stopping is the destructive direction: the same
TabbyAPI may be serving another client, and a server the person also runs by hand
should not die because Zaram closed. A server Zaram started therefore outlives it
(on Windows a child survives its parent being killed, and `electron/backend`
kills only the one process). What it holds on the card is released the way it is
for any other model: the explicit *Release* control, which asks the server to
unload and leaves the process alone.

*Starting never blocks boot, and is never silent about failing.* A launch is a
detached process with its output in the data directory's `logs/`. If it exits
early, the last lines of that log are what the status reports. A server that
is still not answering after two minutes is reported as not responding rather
than as starting forever.

*It does not start during tests.* The backend suite boots the real app, and a
test run must never be the thing that launches an 11 GB model server on a
developer's machine. `autostart_allowed` is false under pytest and when
``ZARAM_AUTOSTART=0``.

*Nothing here talks to anything but loopback.* The probe URLs are constants, and
`_get_json` refuses any other host rather than trusting that they are.

*Its logs are bounded, and what they hold is stated.* A server Zaram starts writes to
`logs/<server>.log` in the data directory, so a launch that fails can say why. Each is
**rotated at launch once it passes 512 KB, with one previous kept**, so the folder is
bounded per launch (`CLAUDE.md`: no new store ships without an answer to how long it keeps
things). What they hold is the servers' own request lines -- a path, a status, a time -- not
prompts or replies. What the bound does *not* cover, said plainly: a server that stays up
for weeks keeps appending to its log until it next starts, because a detached process owns
its file and cannot be rotated from outside on Windows. Deleting the folder is always safe.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

__all__ = [
    "SERVERS",
    "Install",
    "Probe",
    "ServerStartError",
    "autostart_allowed",
    "describe",
    "describe_all",
    "ensure_started",
    "refresh_when_up",
    "start",
    "validate_path",
]

#: How long a probe waits. Short on purpose, and for a Windows-specific reason:
#: connecting to a closed loopback port does not fail at once there, it hangs
#: for seconds -- observed 4 October 2026 as backend connections sitting in
#: `SYN_SENT` against a stopped Ollama, which made boot take minutes. Every
#: probe here is bounded, and `describe_all` runs them side by side.
PROBE_TIMEOUT_SECONDS = 1.0

#: After which a launched server that has still not answered is reported as not
#: responding. Tabby loading its config is ~20 s; two minutes is generous.
STALLED_AFTER_SECONDS = 120.0

#: A second launch inside this window is refused as a duplicate. Two clicks, or
#: a click racing the automatic start, must not spawn two servers.
RELAUNCH_GUARD_SECONDS = 60.0

MAX_MODELS_SHOWN = 6


class ServerStartError(Exception):
    """Zaram could not, or should not, start this server. The message is for a person."""


@dataclass(frozen=True)
class Probe:
    """What asking the server's port returned."""

    #: This server, answering.
    serving: bool = False
    #: Names of the models it lists. Empty is a real answer for a server that is
    #: up and holds none, and is distinct from not serving.
    models: Tuple[str, ...] = ()
    #: *Something* answered on this port that is not this server. LM Studio and
    #: TabbyAPI both default to 1234, so "a server is there" proves nothing.
    other_server: bool = False


@dataclass(frozen=True)
class Install:
    """Where a server is installed and what runs it."""

    path: str
    #: ``"configured"`` (the person said where) or ``"found"`` (Zaram looked).
    source: str
    #: The command to start it, or ``None`` when it was found but cannot be run.
    argv: Optional[Tuple[str, ...]] = None
    cwd: Optional[str] = None
    #: Why it cannot be started, in a sentence, when `argv` is ``None``.
    problem: str = ""


# ------------------------------------------------------------------ probing


#: The only hosts this module will speak to. Enforced, not assumed: the probe URLs are
#: built from constants today, and `tests/test_egress_chokepoint.py` exempts this
#: module from the egress gate on the strength of exactly that -- *"an exemption
#: written there has to be a fact about the code, not an intention."*
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _get_json(url: str, timeout: float) -> Tuple[Optional[int], Any]:
    """``(status, parsed body)``. ``(None, None)`` when nothing answered.

    An `HTTPError` is an answer -- a server that replies 401 is up -- so it is
    returned with its status rather than treated as unreachable.

    **Refuses any host that is not loopback**, answering as though nothing were
    there. A status check that could be pointed at another machine would be a request
    nobody asked for, made by a settings page.
    """
    if urlparse(url).hostname not in _LOOPBACK_HOSTS:
        logger.warning("refused a probe of a non-loopback host: %r", url)
        return None, None
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - loopback constants only
            raw = response.read(1_000_000)
            status = response.status
    except HTTPError as error:
        try:
            raw = error.read(1_000_000)
        except Exception:  # noqa: BLE001
            raw = b""
        status = error.code
    except (URLError, OSError, ValueError):
        return None, None
    try:
        return status, (json.loads(raw.decode("utf-8", "replace")) if raw else None)
    except ValueError:
        return status, None


def _names(entries: Any, key: str) -> Tuple[str, ...]:
    if not isinstance(entries, list):
        return ()
    found = []
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get(key), str) and entry[key].strip():
            found.append(entry[key].strip())
    return tuple(found)


# ------------------------------------------------------------ install finding


def _executable_in(directory: Path, names: Tuple[str, ...]) -> Optional[Path]:
    for name in names:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def _python_in(env: Path) -> Optional[Path]:
    """The interpreter inside a virtual environment, on either platform's layout."""
    for parts in (("Scripts", "python.exe"), ("bin", "python"), ("bin", "python3")):
        candidate = env.joinpath(*parts)
        if candidate.is_file():
            return candidate
    return None


class _Server:
    id = ""
    label = ""
    port = 0
    #: Which of a person's settings mean anything for this server. The interface
    #: draws only these: a field asking for a Python interpreter under Ollama,
    #: which is one executable, would be a control that settles nothing.
    fields: Tuple[str, ...] = ("path",)

    def probe(self, timeout: float) -> Probe:  # pragma: no cover - interface
        raise NotImplementedError

    def find_install(self, config: Dict[str, Any]) -> Optional[Install]:  # pragma: no cover
        raise NotImplementedError

    def check_path(self, path: str) -> str:
        """Why ``path`` is not an install of this server, or ``""`` if it is."""
        return "" if self.find_install({"path": path}) else "Nothing runnable was found there."


class _Ollama(_Server):
    id = "ollama"
    label = "Ollama"
    port = 11434

    def probe(self, timeout: float) -> Probe:
        status, body = _get_json(f"http://127.0.0.1:{self.port}/api/tags", timeout)
        if status is None:
            return Probe()
        if status == 200 and isinstance(body, dict) and isinstance(body.get("models"), list):
            return Probe(serving=True, models=_names(body["models"], "name"))
        return Probe(other_server=True)

    def _candidates(self, config: Dict[str, Any]) -> List[Tuple[Path, str]]:
        found: List[Tuple[Path, str]] = []
        configured = (config.get("path") or "").strip()
        if configured:
            path = Path(configured).expanduser()
            exe = path if path.is_file() else _executable_in(path, ("ollama.exe", "ollama"))
            # A configured path that does not exist is not silently replaced by
            # a search: the person said where, and the answer is "not there".
            return [(exe, "configured")] if exe is not None else []
        on_path = shutil.which("ollama")
        if on_path:
            found.append((Path(on_path), "found"))
        if sys.platform == "win32":
            for base in (os.environ.get("LOCALAPPDATA"), os.environ.get("ProgramFiles")):
                if base:
                    found.append((Path(base) / "Programs" / "Ollama" / "ollama.exe", "found"))
                    found.append((Path(base) / "Ollama" / "ollama.exe", "found"))
        elif sys.platform == "darwin":
            for text in (
                "/Applications/Ollama.app/Contents/Resources/ollama",
                "/opt/homebrew/bin/ollama",
                "/usr/local/bin/ollama",
            ):
                found.append((Path(text), "found"))
        else:
            for text in ("/usr/local/bin/ollama", "/usr/bin/ollama"):
                found.append((Path(text), "found"))
        return [(p, s) for p, s in found if p.is_file()]

    def find_install(self, config: Dict[str, Any]) -> Optional[Install]:
        candidates = self._candidates(config)
        if not candidates:
            return None
        exe, source = candidates[0]
        return Install(path=str(exe), source=source, argv=(str(exe), "serve"), cwd=None)

    def check_path(self, path: str) -> str:
        if self._candidates({"path": path}):
            return ""
        return "There is no Ollama program at that path."


class _TabbyAPI(_Server):
    id = "tabbyapi"
    label = "TabbyAPI"
    port = 1234
    #: A checkout run under a Python of the person's choosing.
    fields = ("path", "python")

    #: Where a checkout is usually put, under a few usual parents. Looked at in
    #: order, first match wins. A person whose copy lives elsewhere says where.
    _NAMES = ("tabbyAPI", "TabbyAPI", "tabbyapi", "tabby-api", "tabby")

    def probe(self, timeout: float) -> Probe:
        base = f"http://127.0.0.1:{self.port}"
        status, body = _get_json(f"{base}/v1/models", timeout)
        if status is None:
            return Probe()
        data = body.get("data") if isinstance(body, dict) else None
        if status == 200 and isinstance(data, list):
            if any(
                isinstance(e, dict) and str(e.get("owned_by", "")).lower() == "tabbyapi"
                for e in data
            ):
                return Probe(serving=True, models=_names(data, "id"))
        # Nothing identified it yet. TabbyAPI with no model in its directory lists
        # nothing, and one with authentication on answers 401 -- neither carries
        # `owned_by` -- so its own health route is the second chance. LM Studio,
        # which shares this port, answers neither in this shape.
        health_status, health = _get_json(f"{base}/health", timeout)
        if (
            health_status == 200
            and isinstance(health, dict)
            and "status" in health
            and "issues" in health
        ):
            return Probe(serving=True, models=_names(data, "id") if status == 200 else ())
        return Probe(other_server=True)

    @staticmethod
    def _looks_like_a_checkout(root: Path) -> bool:
        return (
            (root / "main.py").is_file()
            and (root / "endpoints").is_dir()
            and ((root / "config.yml").is_file() or (root / "config_sample.yml").is_file())
        )

    def _roots(self, config: Dict[str, Any]) -> List[Tuple[Path, str]]:
        configured = (config.get("path") or "").strip()
        if configured:
            root = Path(configured).expanduser()
            return [(root, "configured")] if self._looks_like_a_checkout(root) else []
        home = Path.home()
        parents = [home, home / "Documents", home / "source" / "repos", home / "code", home / "dev"]
        parents.append(Path("C:/") if sys.platform == "win32" else Path("/opt"))
        found: List[Tuple[Path, str]] = []
        for parent in parents:
            for name in self._NAMES:
                candidate = parent / name
                if self._looks_like_a_checkout(candidate):
                    found.append((candidate, "found"))
        return found

    @staticmethod
    def _interpreter(root: Path, config: Dict[str, Any]) -> Optional[Path]:
        explicit = (config.get("python") or "").strip()
        if explicit:
            path = Path(explicit).expanduser()
            return path if path.is_file() else None
        parent = root.parent
        envs = [
            root / "venv",
            root / ".venv",
            parent / f"{root.name}-env",
            parent / f"{root.name.lower()}-env",
            parent / "tabbyapi-env",
        ]
        for env in envs:
            exe = _python_in(env)
            if exe is not None:
                return exe
        return None

    def find_install(self, config: Dict[str, Any]) -> Optional[Install]:
        roots = self._roots(config)
        if not roots:
            return None
        root, source = roots[0]
        exe = self._interpreter(root, config)
        if exe is None:
            return Install(
                path=str(root),
                source=source,
                argv=None,
                problem=(
                    "TabbyAPI is here, but Zaram could not find the Python environment "
                    "it runs in. Say which Python to use under Advanced."
                ),
            )
        return Install(path=str(root), source=source, argv=(str(exe), "main.py"), cwd=str(root))

    def check_path(self, path: str) -> str:
        if not self._roots({"path": path}):
            return (
                "That folder does not look like a TabbyAPI checkout "
                "(it needs main.py, an endpoints folder, and a config file)."
            )
        return ""


#: The whole extension point. Add an entry; nothing else in this file changes.
SERVERS: Dict[str, _Server] = {r.id: r for r in (_Ollama(), _TabbyAPI())}


# ----------------------------------------------------------------- launching


@dataclass
class _Launch:
    process: Any
    started: float
    log_path: str


_launches: Dict[str, _Launch] = {}
_lock = threading.Lock()


def autostart_allowed() -> bool:
    """Whether Zaram may start a server on its own right now.

    False under pytest, because the backend suite boots the real application and
    a test run must never launch an 11 GB model server on somebody's machine,
    and false when ``ZARAM_AUTOSTART=0``. This is *only* about starting
    unprompted: the explicit Start button still works under both.
    """
    if os.environ.get("ZARAM_AUTOSTART") == "0":
        return False
    return "pytest" not in sys.modules


#: Past this a server's log is rotated at the next launch. Large enough to hold a failed
#: start-up in full, small enough that the folder is a few megabytes at most.
MAX_LOG_BYTES = 512 * 1024


def _rotate(path: str) -> None:
    """Move an oversized log aside, replacing any earlier one. Never raises.

    One previous kept, not a series: the point is a bounded folder and a readable record of
    the last start, not an archive.
    """
    try:
        if os.path.getsize(path) > MAX_LOG_BYTES:
            os.replace(path, path + ".1")
    except OSError:
        pass


def _log_path(server_id: str) -> str:
    from core.paths import data_dir

    directory = Path(data_dir()) / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory / f"{server_id}.log")


def _tail(path: str, lines: int = 6) -> str:
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 4096))
            text = handle.read().decode("utf-8", "replace")
    except OSError:
        return ""
    kept = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(kept[-lines:])


def _spawn(argv: Tuple[str, ...], cwd: Optional[str], log_path: str) -> Any:
    """Start a detached process with its output in a log file.

    Never through a shell, so a path with a space or a metacharacter is a path.
    Detached so that it is not killed by the console, or the process group, it
    was started from -- see the module docstring on why it outlives Zaram.
    """
    env = dict(os.environ)
    env.pop("ELECTRON_RUN_AS_NODE", None)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    kwargs: Dict[str, Any] = {}
    if sys.platform == "win32":
        # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        kwargs["creationflags"] = 0x08000000 | 0x00000200
    else:
        kwargs["start_new_session"] = True
    _rotate(log_path)
    log = open(log_path, "ab")  # noqa: SIM115 - handed to the child, which owns it
    try:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log.write(f"\n--- Zaram started this at {stamp} ---\n".encode())
        log.flush()
        return subprocess.Popen(  # noqa: S603 - argv is a list, shell is never used
            list(argv),
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
            close_fds=True,
            **kwargs,
        )
    finally:
        # The child holds its own handle; this process has no use for ours.
        log.close()


def _config(server_id: str) -> Dict[str, Any]:
    try:
        from core.user_settings import get_user_settings

        return get_user_settings().model_server(server_id)
    except Exception:  # noqa: BLE001 - a settings store that will not load must not stop a status
        return {}


def _auto_start(config: Dict[str, Any]) -> bool:
    """On unless the person turned it off. See the module docstring for why."""
    value = config.get("auto_start")
    return value if isinstance(value, bool) else True


def _server(server_id: str) -> _Server:
    found = SERVERS.get(server_id)
    if found is None:
        raise KeyError(server_id)
    return found


def validate_path(server_id: str, path: str) -> str:
    """Why ``path`` is not an install of this server, or ``""`` if it is.

    Called when a person gives a location, so a mistyped one is refused there
    rather than being stored and failing at the next launch. An empty path is
    valid -- it means *go back to looking*.
    """
    if not (path or "").strip():
        return ""
    return _server(server_id).check_path(path.strip())


def describe(
    server_id: str,
    *,
    config: Optional[Dict[str, Any]] = None,
    timeout: float = PROBE_TIMEOUT_SECONDS,
    probe: Optional[Probe] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Everything Settings shows about one server, in one answer.

    `state` is the one word to branch on; the other fields are the reasons for it.
    """
    server = _server(server_id)
    cfg = _config(server_id) if config is None else config
    install = server.find_install(cfg)
    seen = probe if probe is not None else server.probe(timeout)
    clock = time.monotonic() if now is None else now

    launch = _launches.get(server_id)
    starting = False
    stalled = False
    failure = ""
    log_path = ""
    if launch is not None:
        log_path = launch.log_path
        if seen.serving:
            pass  # up -- whatever happened before is history
        elif launch.process.poll() is not None:
            failure = _tail(launch.log_path) or "It stopped as soon as it started."
        elif clock - launch.started > STALLED_AFTER_SECONDS:
            stalled = True
        else:
            starting = True

    if seen.serving:
        state = "running"
    elif seen.other_server:
        state = "port_taken"
    elif starting:
        state = "starting"
    elif stalled:
        state = "stalled"
    elif install is None:
        state = "not_installed"
    elif install.argv is None:
        state = "cannot_start"
    else:
        state = "stopped"

    return {
        "id": server.id,
        "label": server.label,
        "port": server.port,
        "state": state,
        "installed": install is not None,
        "path": install.path if install else None,
        "install_source": install.source if install else None,
        "serving": seen.serving,
        "other_server": seen.other_server,
        "model_count": len(seen.models),
        "models": list(seen.models[:MAX_MODELS_SHOWN]),
        "can_start": bool(install and install.argv) and not seen.serving and not seen.other_server,
        "problem": install.problem if install and install.argv is None else "",
        "auto_start": _auto_start(cfg),
        "fields": list(server.fields),
        "failure": failure,
        "log_path": log_path,
        # Filled by the route, which can see the model catalogue. `None` means
        # "not asked", which is not the same as zero models seen.
        "zaram_sees": None,
    }


def describe_all(**kwargs: Any) -> List[Dict[str, Any]]:
    """Every server, probed side by side so one closed port does not delay the rest."""
    ids = list(SERVERS)
    with ThreadPoolExecutor(max_workers=len(ids)) as pool:
        return list(pool.map(lambda rid: describe(rid, **kwargs), ids))


def start(
    server_id: str,
    *,
    config: Optional[Dict[str, Any]] = None,
    spawn: Callable[[Tuple[str, ...], Optional[str], str], Any] = _spawn,
    probe: Optional[Probe] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Start a server and return at once; the caller polls `describe`.

    Raises `ServerStartError` with a sentence for the person when it should not
    or cannot. Starting one that is already serving is not an error -- it is the
    state the caller wanted -- and a second call during a launch is a no-op.
    """
    server = _server(server_id)
    cfg = _config(server_id) if config is None else config
    seen = probe if probe is not None else server.probe(PROBE_TIMEOUT_SECONDS)
    if seen.serving:
        return describe(server_id, config=cfg, probe=seen, now=now)
    if seen.other_server:
        raise ServerStartError(
            f"Something other than {server.label} is already using port {server.port}, "
            "so Zaram has not started it."
        )

    install = server.find_install(cfg)
    if install is None:
        raise ServerStartError(f"{server.label} is not installed where Zaram looks.")
    if install.argv is None:
        raise ServerStartError(install.problem or f"Zaram cannot start {server.label}.")

    clock = time.monotonic() if now is None else now
    with _lock:
        previous = _launches.get(server_id)
        if (
            previous is not None
            and previous.process.poll() is None
            and clock - previous.started < RELAUNCH_GUARD_SECONDS
        ):
            return describe(server_id, config=cfg, probe=seen, now=clock)
        log_path = _log_path(server_id)
        try:
            process = spawn(install.argv, install.cwd, log_path)
        except OSError as error:
            raise ServerStartError(f"{server.label} would not start: {error}") from error
        _launches[server_id] = _Launch(process=process, started=clock, log_path=log_path)
    logger.info("started %s: %s (log: %s)", server.label, " ".join(install.argv), log_path)
    return describe(server_id, config=cfg, probe=seen, now=clock)


def ensure_started(
    server_id: str,
    *,
    wait_seconds: float = 0.0,
    config: Optional[Dict[str, Any]] = None,
    allowed: Optional[bool] = None,
    spawn: Callable[[Tuple[str, ...], Optional[str], str], Any] = _spawn,
    sleep: Callable[[float], None] = time.sleep,
) -> Dict[str, Any]:
    """The automatic start: bring a server up if it is installed, wanted and down.

    Never raises -- this runs during boot, where a crash would take the product
    down for the sake of a convenience. Every reason not to start is returned in
    the status instead. With ``wait_seconds`` it waits for the server to answer,
    which is what lets Ollama be up *before* the backend's own discovery looks.
    """
    cfg = _config(server_id) if config is None else config
    permitted = autostart_allowed() if allowed is None else allowed
    if not permitted or not _auto_start(cfg):
        # Decided before any probe, so a test run -- or somebody who turned this
        # off -- never waits on a port. Connecting to a closed one costs seconds
        # on Windows, and this runs on the way to the first screen.
        return {"id": server_id, "state": "off", "serving": False, "failure": ""}
    try:
        current = describe(server_id, config=cfg)
        if current["serving"] or not current["can_start"]:
            return current
        started = start(server_id, config=cfg, spawn=spawn)
        deadline = time.monotonic() + max(0.0, wait_seconds)
        while wait_seconds > 0 and time.monotonic() < deadline:
            if started["serving"] or started["failure"]:
                break
            sleep(0.5)
            started = describe(server_id, config=cfg)
        return started
    except Exception as error:  # noqa: BLE001 - see the docstring
        logger.warning("could not bring %s up: %s", server_id, error)
        try:
            return describe(server_id, config=cfg)
        except Exception:  # noqa: BLE001
            return {"id": server_id, "state": "unknown", "serving": False}


#: States in which nothing is on its way up, so waiting longer cannot help.
_NOT_COMING_UP = frozenset({"stalled", "not_installed", "cannot_start", "port_taken", "stopped"})


async def refresh_when_up(
    server_id: str,
    refresh: Callable[[], Any],
    *,
    timeout: float = 150.0,
    interval: float = 1.0,
    describe_fn: Callable[[str], Dict[str, Any]] = describe,
) -> bool:
    """Wait for a server to answer, then have the caller rescan its models.

    The step that makes starting a server *show* anywhere. Zaram probes for
    models at boot and on a rescan, so a server that comes up afterwards is
    invisible until something asks again -- which is precisely what happened on
    4 October 2026: TabbyAPI was running and its Qwen was nowhere in the list.
    Returns whether the server came up and the rescan ran.

    Gives up as soon as nothing is launching, rather than polling to the
    timeout: a server that failed to start does not become more started.
    """
    import asyncio

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = await asyncio.to_thread(describe_fn, server_id)
        if status.get("serving"):
            result = refresh()
            if hasattr(result, "__await__"):
                await result
            return True
        if status.get("failure") or status.get("state") in _NOT_COMING_UP:
            return False
        await asyncio.sleep(interval)
    return False

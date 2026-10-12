"""Running the app and looking at it — slice 8 of the code pack.

`run_command` refuses scripts that do not exit, and the reason stands: a
timeout that kills a dev server reports a failure that is not one. Running the
app is a different shape, and this is it: **a managed process the person can
see and stop**, its output kept, its URL read off what it prints, ended when
Zaram ends. And then the tool a vibe coder lives on — *look at it*:

**A screenshot is taken with the browser the person already has**, Chrome or
Edge, headless, of a loopback URL and nothing else. No Playwright, no bundled
Chromium: the same posture as bring-your-own model. Only `localhost` and
`127.0.0.1` are permitted, because a screenshot of a remote page is web
browsing, which is egress with its own rules, and this tool is for *your* app.

**The screenshot is read by a local vision model, when one is installed.**
The page never leaves the machine — that is the whole difference from
Cline's `browser_action` — and when no local vision model exists the tool says
so with the size of the fix and still hands the person the picture: rule
"never block on a download", and disabled capabilities visible rather than
silent. A cloud vision model is *not* used here even when one is connected:
the page under development may hold the person's data, and sending it to look
at a layout is the trade this product refuses by default. That is a decision
the person can revisit by attaching the screenshot to a question themselves,
where the egress gate asks.

The reader is injected — a callable from the models layer — so this module
never names a model or a provider.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import threading
import weakref
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

from runtimes.mcp.client import ToolDescriptor

from .runners import Runner, _npm, long_running_scripts
from .readiness import probe_app
from .ports import (
    resolve_dev_server_port,
    ZARAM_RESERVED_PORTS,
    get_port_env_var,
    allocate_stack_ports,
)

logger = logging.getLogger(__name__)

START_APP = "start_app"
STOP_APP = "stop_app"
APP_STATUS = "get_app_status"
READ_APP_LOG = "read_app_log"
LOOK_AT_APP = "look_at_app"
START_APP_STACK = "start_app_stack"
STOP_APP_STACK = "stop_app_stack"
GET_APP_STACK_STATUS = "get_app_stack_status"
GET_STACK_GROUPS = "get_stack_groups"
TOOL_NAMES = frozenset({START_APP, STOP_APP, APP_STATUS, READ_APP_LOG, LOOK_AT_APP, START_APP_STACK, STOP_APP_STACK, GET_APP_STACK_STATUS, GET_STACK_GROUPS})

#: Lines of output kept per app. A dev server prints a great deal; the tail is
#: where the current state is.
LOG_LINES = 300
#: How long `start_app` waits for a URL to appear before reporting "started,
#: no URL yet". Vite prints in under a second; a cold Next build can take ten.
URL_WAIT_SECONDS = 15.0
#: Said to the model in the description of the tools that start an app. Zaram
#: opens a local app it started in its own browser pane, once it answers, so a
#: reply that tells the person to open the link is asking them to do what has
#: already been done -- the maintainer's complaint, 11 October 2026: *"instead
#: of just giving the user a link to the localhost and telling the user to open
#: it in the browser, it actually opens the localhost."* Plain words, no
#: model or provider named.
OPENS_ITSELF = (
    "Zaram opens a local app it started in its own browser pane as soon as it answers, "
    "so do not tell the person to open the link or paste the address into a browser: say "
    "the app is open, and name the address once as where it is running."
)
#: How long a screenshot may take, including the page's own load.
SCREENSHOT_SECONDS = 40

#: Said when no *local* model can see. Both routes are named because both are
#: real on the maintainer's machine: a vision model loaded in an
#: OpenAI-compatible server (TabbyAPI with `use_vision: true`) is found by
#: discovery, and so is one pulled into Ollama. Naming only the Ollama route
#: told someone whose 27B could already see to download 6 GB. No model
#: filename here — `tests/test_no_second_entrance_to_inference.py` forbids
#: naming one in a sentence shown to a person, and it caught this constant.
NO_LOCAL_VISION = (
    "No local vision model is available, so Zaram cannot read the screenshot itself; "
    "it is saved and shown to the person. Either load a vision-capable model in the "
    "local server Zaram already uses (TabbyAPI: a model with `use_vision` on) or pull "
    "one into Ollama (a 7B vision model is about 6 GB, one time). Either way the page "
    "never leaves the machine."
)
SCREENSHOT_WIDTH = 1280
SCREENSHOT_HEIGHT = 900

_URL = re.compile(r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d+)?(?:/[^\s\"'<>)]*)?")
_LOOPBACK = re.compile(r"^https?://(?:localhost|127\.0\.0\.1)(?::\d+)?(?:/.*)?$")

HOW_TO_PERMIT = "Allow running the project's commands for this project in Project, then ask again."

#: Where the browsers the person already has usually are. Probed, never
#: bundled.
_BROWSERS = (
    ("chrome", (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "google-chrome", "chromium", "chromium-browser",
    )),
    ("edge", (
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "microsoft-edge",
    )),
)


def find_browser() -> Optional[str]:
    """A Chromium the person already has, or ``None``."""
    for _, candidates in _BROWSERS:
        for candidate in candidates:
            if os.path.isabs(candidate):
                if Path(candidate).is_file():
                    return candidate
            else:
                found = shutil.which(candidate)
                if found:
                    return found
    return None


def screens_dir_for(root: Path, base: Optional[Path]) -> Path:
    """Where a project's screenshots go: under Zaram's data directory, in a
    folder named by the project root, never inside the repository — a
    screenshot committed by accident is somebody's page in their history."""
    import hashlib

    if base is None:
        from core.paths import data_dir

        base = data_dir() / "screens"
    return base / hashlib.sha1(str(root.resolve()).lower().encode("utf-8")).hexdigest()[:12]


def app_runners(root: Path) -> List[Runner]:
    """The commands that *run the app* — the ones `run_command` refuses."""
    out: List[Runner] = []
    npm = _npm()
    if npm:
        for name in long_running_scripts(root):
            out.append(Runner(name=f"npm:{name}", argv=(npm, "run", name), description=f"npm run {name}"))
    if (root / "manage.py").is_file():
        from .runners import _python_for

        python = _python_for(root)
        if python:
            out.append(Runner(name="django", argv=(*python, "manage.py", "runserver"), description="python manage.py runserver"))
    return out


@dataclass
class AppProcess:
    runner: str
    command: str
    process: subprocess.Popen
    started_at: float
    lines: Deque[str]
    name: str = "default"  # Process name within a stack (e.g., "frontend", "backend")
    url: Optional[str] = None
    ready: bool = False
    readiness_error: str = ''
    http_status: Optional[int] = None
    #: What this process is for -- `frontend`, `backend`, `worker`, `database` --
    #: or `None` when nothing says. Reported so that whatever opens the page
    #: does not have to guess from a process's name.
    role: Optional[str] = None

    @property
    def running(self) -> bool:
        return self.process.poll() is None

    def to_json(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "runner": self.runner,
            "command": self.command,
            "running": self.running,
            "pid": self.process.pid,
            "url": self.url,
            "ready": self.running and self.ready,
            "state": 'stopped' if not self.running else 'ready' if self.ready else 'starting',
            "readiness_error": self.readiness_error,
            "http_status": self.http_status,
            "exit_code": None if self.running else self.process.returncode,
            "uptime_seconds": round(time.time() - self.started_at, 1),
            "name": self.name,
        }


#: Every live `AppTools`, so the rest of the product can ask what Zaram
#: started without reaching through the MCP runtime for the code server.
#:
#: A `WeakSet` rather than a list: a discarded instance must not keep its
#: subprocesses' records alive, and the browser pane asking what is running
#: must not be the thing that stops a boot being collected. There is one of
#: these per boot in practice; the weakness is about tests, which make
#: several and then drop them.
_LIVE: "weakref.WeakSet[AppTools]" = weakref.WeakSet()


def launched() -> List[Dict[str, Any]]:
    """The apps Zaram has running, newest first.

    **The browser pane's new tab reads this and nothing else — 4 October
    2026.** It first read the machine's process table, which answered a
    broader question than anybody asked: 46 things were listening on the
    maintainer's machine and 44 were Discord, OneDrive, Epic Games and
    svchost. The maintainer's correction was to show *"only the ones
    launched or opened by Zaram"*, and that is both quieter and more
    honest — it is the list of things Zaram is responsible for, which is a
    fact it holds rather than a guess about somebody else's processes.

    It also removes a privacy smell nobody had asked for: a panel that
    enumerates what you have installed, on screen, in screenshots.

    Each entry carries the project root it belongs to, so the pane can say
    *Ride Share* rather than *node.exe*.
    """
    found: List[Dict[str, Any]] = []
    for tools in list(_LIVE):
        for root, procs in list(getattr(tools, "_apps", {}).items()):
            for name, app in list(procs.items()):
                if not app.running or not app.url:
                    # A dead app is not a page anybody can open, and one with
                    # no URL has not announced a port yet.
                    continue
                found.append(
                    {
                        "root": root,
                        "runner": app.runner,
                        "url": app.url,
                        "pid": app.process.pid,
                        "started_at": app.started_at,
                        "name": app.name,
                    }
                )
    found.sort(key=lambda entry: entry["started_at"], reverse=True)
    return found


_FRONTEND_FRAMEWORKS = frozenset(
    {"vite", "next", "react", "react-scripts", "webpack", "nuxt", "svelte", "astro", "remix", "gatsby", "angular"}
)
_BACKEND_FRAMEWORKS = frozenset({"django", "flask", "fastapi", "express", "rails", "phoenix"})


def role_of(runner: Runner) -> Optional[str]:
    """What a runner is for, read off what it runs -- or ``None``.

    The runner's own group when it has one; otherwise the framework its command
    names. Neither is a model or a provider: a table of dev servers, so a
    framework nobody listed is ``None`` rather than a wrong answer.
    """
    from .ports import detect_framework_from_runner
    from .runners import _assign_group

    group = runner.group or _assign_group(runner).group
    if group:
        return group
    framework = detect_framework_from_runner(runner)
    if framework in _FRONTEND_FRAMEWORKS:
        return "frontend"
    if framework in _BACKEND_FRAMEWORKS:
        return "backend"
    return None


def page_url(tool: str, payload: Any) -> str:
    """The address a person would open for what ``tool`` just started, or ``""``.

    **Why this exists, 11 October 2026.** The tool card's address came from
    `payload["url"]`, which `start_app` has and `start_app_stack` does not: a
    stack answers with a list of processes, so a stack the model started left
    the card -- and the browser pane that opens from it -- with no address at
    all, and the reply fell back to telling the person to open a link.

    Among several processes the page is the **frontend's**. Chosen by the
    `role` the process reports, never by its name alone; a stack where nothing
    says which is the page and more than one answers yields ``""`` rather than
    a guess, because opening somebody's API on a JSON error page is worse than
    opening nothing.
    """
    if not isinstance(payload, dict):
        return ""
    if tool != START_APP_STACK:
        return str(payload.get("url") or "")
    live = [
        p for p in (payload.get("processes") or [])
        if isinstance(p, dict) and p.get("running") and p.get("url")
    ]
    for p in live:
        if p.get("role") == "frontend":
            return str(p["url"])
    if len(live) == 1:
        return str(live[0]["url"])
    # Several, none marked frontend: the page is the one that is not known to be
    # something else. Exactly one such, or nothing.
    unplaced = [p for p in live if not p.get("role")]
    return str(unplaced[0]["url"]) if len(unplaced) == 1 else ""


class AppTools:
    """Managed apps per project folder. Supports both single-process (legacy)
    and multi-process stacks."""

    def __init__(
        self,
        *,
        describe_image: Optional[Callable[[str, str], Optional[str]]] = None,
        screens_dir: Optional[Path] = None,
        browser: Optional[str] = None,
        run: Optional[Callable[..., subprocess.CompletedProcess]] = None,
        probe: Optional[Callable[..., Dict[str, Any]]] = None,
    ) -> None:
        #: root → {process_name → AppProcess}. One project can run multiple
        #: named processes (e.g., "frontend", "backend", "worker").
        self._apps: Dict[str, Dict[str, AppProcess]] = {}
        self._lock = threading.Lock()
        # So `launched()` can answer without reaching through the MCP
        # runtime for the code server.
        _LIVE.add(self)
        self._describe = describe_image
        self._screens = screens_dir
        self._browser = browser
        self._run = run or subprocess.run
        self._probe = probe or probe_app
        import atexit

        atexit.register(self.stop_all)

    # ------------------------------------------------------------ descriptors

    def descriptors(self, server_id: str, root: Optional[Path]) -> List[ToolDescriptor]:
        names = [r.name for r in app_runners(root)] if root is not None else []
        listed = ", ".join(f"`{n}`" for n in names) if names else "none detected in this project"
        return [
            ToolDescriptor(
                server_id=server_id,
                name=START_APP,
                description=(
                    f"Start a single project app as a background process — a dev server — and report "
                    f"the URL it prints. Available: {listed}. It keeps running until stopped. "
                    "Check ready and http_status; a printed URL is not readiness. HTTP readiness "
                    "does not prove the app works: run its checks and exercise its main interaction before claiming completion. "
                    + OPENS_ITSELF
                ),
                input_schema={
                    "type": "object",
                    "properties": {"runner": {"type": "string", "description": "Which app runner, by name."}},
                    "required": ["runner"],
                },
            ),
            ToolDescriptor(
                server_id=server_id,
                name=START_APP_STACK,
                description=(
                    f"Start multiple project apps as a stack (e.g., frontend + backend). "
                    f"Runners are grouped by name (frontend/backend/worker) or by Procfile. "
                    f"Available runners: {listed}. Returns all URLs with labels and each process's role. "
                    "Each process gets its own port; conflicts are resolved automatically. "
                    + OPENS_ITSELF
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "runners": {"type": "array", "items": {"type": "string"}, "description": "List of runner names to start as a stack."},
                    },
                    "required": ["runners"],
                },
            ),
            ToolDescriptor(
                server_id=server_id, name=STOP_APP,
                description="Stop the project's running app (legacy single-process).",
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDescriptor(
                server_id=server_id, name=STOP_APP_STACK,
                description="Stop all processes in the project's app stack.",
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDescriptor(
                server_id=server_id, name=APP_STATUS,
                description="Whether the project's app is running and HTTP-ready, its URL, HTTP status, startup error and uptime (legacy single-process).",
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDescriptor(
                server_id=server_id, name=GET_APP_STACK_STATUS,
                description="Get status of all processes in the project's app stack: each runner's URL, readiness, PID, and uptime.",
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDescriptor(
                server_id=server_id, name=GET_STACK_GROUPS,
                description="Get detected stack groups for the project: mapping of group names (frontend, backend, worker, database) to runner names. Used to show 'Launch Stack' button.",
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDescriptor(
                server_id=server_id, name=READ_APP_LOG,
                description="The last lines the running app printed — build errors, requests, warnings.",
                input_schema={
                    "type": "object",
                    "properties": {"lines": {"type": "integer", "description": f"How many lines from the end, up to {LOG_LINES}."}},
                },
            ),
            ToolDescriptor(
                server_id=server_id, name=LOOK_AT_APP,
                description=(
                    "Take a screenshot of the running app in a browser and, when a local vision "
                    "model is installed, describe what is on the page. Only localhost URLs. "
                    "Use it to check the page after a change."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "A localhost URL. Defaults to the running app's."},
                        "question": {"type": "string", "description": "What to check for on the page."},
                    },
                },
            ),
        ]

    # ------------------------------------------------------------------ call

    def call(self, name: str, arguments: Dict[str, Any], root: Path) -> Dict[str, Any]:
        if name == START_APP:
            return self._start(root, str(arguments.get("runner") or ""))
        if name == START_APP_STACK:
            runners = arguments.get("runners")
            if not isinstance(runners, list):
                return {"error": "runners must be a list of runner names"}
            return self._start_stack(root, [str(r) for r in runners])
        if name == STOP_APP:
            return self._stop(root)
        if name == STOP_APP_STACK:
            return self._stop_stack(root)
        if name == APP_STATUS:
            return self.status(root)
        if name == GET_APP_STACK_STATUS:
            return self._stack_status(root)
        if name == GET_STACK_GROUPS:
            return self._get_stack_groups(root)
        if name == READ_APP_LOG:
            return self._log(root, arguments.get("lines"))
        if name == LOOK_AT_APP:
            return self._look(root, str(arguments.get("url") or ""), str(arguments.get("question") or ""))
        return {"error": f"no tool called {name!r}"}

    # ------------------------------------------------------------ the process

    def _get_reserved_ports(self, key: str) -> set:
        """Get ports reserved by already-running processes for a project."""
        reserved = set()
        with self._lock:
            procs = self._apps.get(key, {})
            for app in procs.values():
                if app.running and app.url:
                    from urllib.parse import urlparse
                    parsed = urlparse(app.url)
                    if parsed.port:
                        reserved.add(parsed.port)
        return reserved

    # ------------------------------------------------------------ stack operations

    def _start(self, root: Path, wanted: str) -> Dict[str, Any]:
        if not wanted:
            return {"error": "no runner was named"}
        runners = {r.name: r for r in app_runners(root)}
        runner = runners.get(wanted)
        if runner is None:
            return {"error": f"no app runner called {wanted!r}. Available: {', '.join(sorted(runners)) or 'none'}"}
        key = str(root.resolve())
        
        # Resolve port before starting - check for conflicts with Zaram's own ports
        reserved = self._get_reserved_ports(key)
        
        resolved_port, port_info = resolve_dev_server_port(runner, root, reserved)
        
        with self._lock:
            procs = self._apps.setdefault(key, {})
            current = procs.get("default")
            if current is not None and current.running:
                return {"error": f"{current.runner} is already running at {current.url or 'an unknown URL'}; stop it first", **current.to_json()}
            env = dict(os.environ)
            env.setdefault("NO_COLOR", "1")
            env["FORCE_COLOR"] = "0"
            env["PYTHONUNBUFFERED"] = "1"
            env.setdefault("BROWSER", "none")
            # Set port override if we resolved a different port
            if port_info.get("conflict") and "env_var" in port_info and "resolved_port" in port_info:
                env[port_info["env_var"]] = str(port_info["resolved_port"])
                logger.info("code pack: port conflict resolved for %s: %s -> %s (via %s)",
                           runner.name, port_info["original_port"], port_info["resolved_port"], port_info["env_var"])
            try:
                process = subprocess.Popen(
                    list(runner.argv),
                    cwd=key,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except FileNotFoundError:
                return {"error": f"{runner.argv[0]} is not installed or not on the path"}
            app = AppProcess(runner=runner.name, command=" ".join(runner.argv), process=process, started_at=time.time(), lines=deque(maxlen=LOG_LINES), name="default", role=role_of(runner))
            procs["default"] = app
        threading.Thread(target=self._pump, args=(app,), daemon=True).start()
        logger.info("code pack: started %s in %s (pid %s)", runner.name, key, process.pid)

        # Wait briefly for the URL — it is the one thing the model needs next.
        deadline = time.monotonic() + URL_WAIT_SECONDS
        while time.monotonic() < deadline and app.url is None and app.running:
            time.sleep(0.2)
        if app.url and app.running:
            ready_deadline = time.monotonic() + 3.0
            while app.running and time.monotonic() < ready_deadline:
                self._check_ready(app)
                if app.ready:
                    break
                time.sleep(0.2)
        result = app.to_json()
        # Include port resolution info in result
        if port_info.get("conflict"):
            result["port_conflict_resolved"] = True
            result["port_note"] = port_info["note"]
        elif port_info.get("original_port"):
            result["port_note"] = port_info["note"]
        if not app.running:
            result["error"] = "the app exited straight away; read_app_log has what it printed"
            result["log"] = "\n".join(list(app.lines)[-40:])
        elif app.url is None:
            result["note"] = f"running, but it has not printed a URL in {int(URL_WAIT_SECONDS)}s; read_app_log to see why, or look_at_app with the URL you expect"
        elif not app.ready:
            result["note"] = "The process is running but HTTP readiness is not verified. Read the app log and check get_app_status again; do not claim the app works yet."
        return result

    # ------------------------------------------------------------ stack operations

    def _start_stack(self, root: Path, runner_names: List[str]) -> Dict[str, Any]:
        """Start multiple runners as a stack with coordinated port allocation."""
        if not runner_names:
            return {"error": "no runners specified for stack"}
        
        key = str(root.resolve())
        runners_map = {r.name: r for r in app_runners(root)}
        stack_runners = []
        
        for name in runner_names:
            runner = runners_map.get(name)
            if runner is None:
                return {"error": f"no app runner called {name!r}. Available: {', '.join(sorted(runners_map)) or 'none'}"}
            stack_runners.append(runner)
        
        # Allocate ports for entire stack upfront to avoid conflicts
        reserved = set()
        with self._lock:
            procs = self._apps.get(key, {})
            for app in procs.values():
                if app.running and app.url:
                    from urllib.parse import urlparse
                    parsed = urlparse(app.url)
                    if parsed.port:
                        reserved.add(parsed.port)
        
        # Use the new stack port allocation
        port_allocation = allocate_stack_ports(stack_runners, root, reserved)
        
        # Track which process names we're starting in this call
        started_process_names = [p.get("process_name", r.name.replace("npm:", "").replace(":", "_")) 
                                  for r, p in zip(stack_runners, port_allocation)]
        
        results = []
        with self._lock:
            procs = self._apps.setdefault(key, {})
            for runner, port_info in zip(stack_runners, port_allocation):
                # Include runner name in process_name to avoid collisions when multiple
                # runners share the same group (e.g., two frontend runners)
                base_name = runner.name.replace("npm:", "").replace(":", "_")
                group = runner.group or "default"
                process_name = port_info.get("process_name") or f"{group}_{base_name}"
                existing = procs.get(process_name)
                if existing is not None and existing.running:
                    results.append({"error": f"{process_name} is already running at {existing.url or 'an unknown URL'}; stop it first", **existing.to_json()})
                    continue
                
                env = dict(os.environ)
                env.setdefault("NO_COLOR", "1")
                env["FORCE_COLOR"] = "0"
                env["PYTHONUNBUFFERED"] = "1"
                env.setdefault("BROWSER", "none")
                
                # Set port override
                if "env_var" in port_info and "resolved_port" in port_info:
                    env[port_info["env_var"]] = str(port_info["resolved_port"])
                    logger.info("code pack: port allocated for %s (stack %s): %s -> %s (via %s)",
                               runner.name, process_name, port_info.get("original_port"), port_info["resolved_port"], port_info["env_var"])
                
                try:
                    process = subprocess.Popen(
                        list(runner.argv),
                        cwd=key,
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                except FileNotFoundError:
                    results.append({"error": f"{runner.argv[0]} is not installed or not on the path"})
                    continue
                
                app = AppProcess(
                    runner=runner.name, 
                    command=" ".join(runner.argv), 
                    process=process, 
                    started_at=time.time(), 
                    lines=deque(maxlen=LOG_LINES),
                    name=process_name,
                    role=role_of(runner),
                )
                procs[process_name] = app
                threading.Thread(target=self._pump, args=(app,), daemon=True).start()
                logger.info("code pack: started %s as %s in %s (pid %s)", runner.name, process_name, key, process.pid)
                results.append({"started": process_name, "runner": runner.name, "pid": process.pid})
        
        # Wait for URLs - only wait for processes we started in this call
        deadline = time.monotonic() + URL_WAIT_SECONDS
        while time.monotonic() < deadline:
            with self._lock:
                procs = self._apps.get(key, {})
            all_have_urls = all(
                app.url for name, app in procs.items() 
                if app.running and name in started_process_names
            )
            if all_have_urls:
                break
            time.sleep(0.2)
        
        # Check readiness - only for processes we started
        ready_deadline = time.monotonic() + 3.0
        while time.monotonic() < ready_deadline:
            with self._lock:
                procs = self._apps.get(key, {})
            for name, app in procs.items():
                if app.running and name in started_process_names:
                    self._check_ready(app)
            time.sleep(0.2)
        
        # Build combined result
        with self._lock:
            procs = self._apps.get(key, {})
        
        stack_result = {
            "stack": True,
            "processes": [],
            "started": [],
        }
        
        for name, app in procs.items():
            result = app.to_json()
            if port_info := next((p for p in port_allocation if p.get("process_name") == name), None):
                if port_info.get("conflict"):
                    result["port_conflict_resolved"] = True
                    result["port_note"] = port_info["note"]
                elif port_info.get("original_port"):
                    result["port_note"] = port_info["note"]
            if not app.running:
                result["error"] = "the app exited straight away; read_app_log has what it printed"
                result["log"] = "\n".join(list(app.lines)[-40:])
            elif app.url is None:
                result["note"] = f"running, but it has not printed a URL in {int(URL_WAIT_SECONDS)}s; read_app_log to see why, or look_at_app with the URL you expect"
            elif not app.ready:
                result["note"] = "The process is running but HTTP readiness is not verified. Read the app log and check get_app_status again; do not claim the app works yet."
            stack_result["processes"].append(result)
            if app.running:
                stack_result["started"].append(name)
        
        return stack_result

    def _stop_stack(self, root: Path) -> Dict[str, Any]:
        """Stop all processes in the project's app stack."""
        key = str(root.resolve())
        stopped = []
        with self._lock:
            procs = self._apps.get(key, {})
            for name, app in list(procs.items()):
                self._terminate(app)
                stopped.append(name)
            if key in self._apps:
                del self._apps[key]
        return {"stopped": True, "processes": stopped}

    def _stack_status(self, root: Path) -> Dict[str, Any]:
        """Get status of all processes in the project's app stack."""
        key = str(root.resolve())
        with self._lock:
            procs = self._apps.get(key, {})
        
        if not procs:
            return {"running": False, "processes": [], "available": [r.name for r in app_runners(root)]}
        
        processes = []
        for name, app in procs.items():
            self._check_ready(app)
            processes.append(app.to_json())
        
        return {
            "running": any(app.running for app in procs.values()),
            "processes": processes,
            "available": [r.name for r in app_runners(root)],
        }

    def _get_stack_groups(self, root: Path) -> Dict[str, List[str]]:
        """Get detected stack groups for the project.
        
        Returns a mapping of group names (frontend, backend, worker, database) 
        to lists of runner names that belong to each group.
        """
        from .runners import get_stack_groups
        return get_stack_groups(root)

    def _pump(self, app: AppProcess) -> None:
        try:
            assert app.process.stdout is not None
            for line in app.process.stdout:
                text = line.rstrip("\n")
                app.lines.append(text)
                if app.url is None:
                    match = _URL.search(text)
                    if match:
                        app.url = match.group(0).replace("0.0.0.0", "127.0.0.1")
        except Exception:  # noqa: BLE001 - a dead pipe ends the reader, nothing else
            pass

    def _stop(self, root: Path) -> Dict[str, Any]:
        """Stop the default (legacy single-process) app."""
        key = str(root.resolve())
        with self._lock:
            procs = self._apps.get(key, {})
            app = procs.get("default")
            if app is None:
                return {"stopped": False, "note": "nothing is running"}
            self._terminate(app)
            procs.pop("default", None)
            if not procs:
                self._apps.pop(key, None)
        return {"stopped": True, "runner": app.runner}

    def _terminate(self, app: AppProcess) -> None:
        if not app.running:
            return
        try:
            if os.name == "nt":
                # The dev server spawns children; `terminate` would orphan them
                # and leave the port held. `/T` takes the tree.
                self._run(["taskkill", "/PID", str(app.process.pid), "/T", "/F"], capture_output=True, timeout=15)
            else:
                app.process.terminate()
                try:
                    app.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    app.process.kill()
        except Exception:  # noqa: BLE001
            logger.exception("code pack: could not stop %s", app.runner)
        logger.info("code pack: stopped %s (pid %s)", app.runner, app.process.pid)

    def stop_all(self) -> None:
        """Every app Zaram started ends with Zaram. A dev server outliving
        the process that started it is a port held by nothing anyone can see."""
        with self._lock:
            for procs in list(self._apps.values()):
                for app in list(procs.values()):
                    self._terminate(app)
            self._apps.clear()

    def _check_ready(self, app: AppProcess) -> None:
        if not app.url or not app.running:
            app.ready = False
            return
        result = self._probe(app.url, timeout=0.5)
        app.ready = bool(result.get('ready'))
        app.readiness_error = str(result.get('readiness_error') or '')
        app.http_status = result.get('http_status')

    def status(self, root: Path) -> Dict[str, Any]:
        """Legacy single-process status. Returns the default process."""
        key = str(root.resolve())
        with self._lock:
            procs = self._apps.get(key, {})
            app = procs.get("default")
        if app is None:
            return {"running": False, "available": [r.name for r in app_runners(root)]}
        self._check_ready(app)
        return app.to_json()

    def _log(self, root: Path, lines: Any) -> Dict[str, Any]:
        """Legacy single-process log. Returns the default process log."""
        key = str(root.resolve())
        with self._lock:
            procs = self._apps.get(key, {})
            app = procs.get("default")
        if app is None:
            return {"error": "nothing is running; start_app first"}
        try:
            count = max(1, min(int(lines or 60), LOG_LINES))
        except (TypeError, ValueError):
            count = 60
        tail = list(app.lines)[-count:]
        return {"runner": app.runner, "running": app.running, "url": app.url, "lines": tail}

    # ------------------------------------------------------------ the look

    def _look(self, root: Path, url: str, question: str) -> Dict[str, Any]:
        key = str(root.resolve())
        with self._lock:
            procs = self._apps.get(key, {})
        # Prefer the default process URL, then any running process
        target = url.strip()
        if not target:
            default = procs.get("default")
            if default and default.url:
                target = default.url
            else:
                for app in procs.values():
                    if app.url:
                        target = app.url
                        break
        if not target:
            return {"error": "no URL: start the app first, or name a localhost URL"}
        if not _LOOPBACK.match(target):
            return {"error": f"{target} is not on this machine. look_at_app only looks at localhost — anything else is browsing, which has its own rules"}
        browser = self._browser or find_browser()
        if browser is None:
            return {"error": "no Chrome or Edge is installed to take the screenshot with"}
        screens = screens_dir_for(root, self._screens)
        screens.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        out = screens / f"{stamp}.png"
        argv = [
            browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            "--disable-extensions", f"--window-size={SCREENSHOT_WIDTH},{SCREENSHOT_HEIGHT}",
            "--virtual-time-budget=5000", f"--screenshot={out}", target,
        ]
        try:
            done = self._run(argv, capture_output=True, text=True, timeout=SCREENSHOT_SECONDS,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            return {"error": f"the page at {target} did not finish loading in {SCREENSHOT_SECONDS}s"}
        except FileNotFoundError:
            return {"error": f"{browser} could not be started"}
        if not out.is_file():
            detail = (done.stderr or done.stdout or "").strip().splitlines()
            return {"error": f"no screenshot was produced: {detail[-1] if detail else 'the browser said nothing'}"}

        result: Dict[str, Any] = {"url": target, "image": str(out), "width": SCREENSHOT_WIDTH, "height": SCREENSHOT_HEIGHT}
        if self._describe is None:
            result["description"] = None
            result["note"] = (
                NO_LOCAL_VISION
            )
            return result
        try:
            described = self._describe(str(out), question or "Describe what is on this page. Note any error messages, blank areas or broken layout.")
        except Exception as exc:  # noqa: BLE001 - a failed look is a result, not a crash
            described = None
            result["note"] = f"the vision model could not read it: {exc}"
        result["description"] = described
        if described is None and "note" not in result:
            result["note"] = NO_LOCAL_VISION
        return result

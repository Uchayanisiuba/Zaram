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
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional

from runtimes.mcp.client import ToolDescriptor

from .runners import Runner, _npm, long_running_scripts

logger = logging.getLogger(__name__)

START_APP = "start_app"
STOP_APP = "stop_app"
APP_STATUS = "get_app_status"
READ_APP_LOG = "read_app_log"
LOOK_AT_APP = "look_at_app"
TOOL_NAMES = frozenset({START_APP, STOP_APP, APP_STATUS, READ_APP_LOG, LOOK_AT_APP})

#: Lines of output kept per app. A dev server prints a great deal; the tail is
#: where the current state is.
LOG_LINES = 300
#: How long `start_app` waits for a URL to appear before reporting "started,
#: no URL yet". Vite prints in under a second; a cold Next build can take ten.
URL_WAIT_SECONDS = 15.0
#: How long a screenshot may take, including the page's own load.
SCREENSHOT_SECONDS = 40
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
    url: Optional[str] = None

    @property
    def running(self) -> bool:
        return self.process.poll() is None

    def to_json(self) -> Dict[str, Any]:
        return {
            "runner": self.runner,
            "command": self.command,
            "running": self.running,
            "pid": self.process.pid,
            "url": self.url,
            "exit_code": None if self.running else self.process.returncode,
            "uptime_seconds": round(time.time() - self.started_at, 1),
        }


class AppTools:
    """One managed app per project folder, and a look at it."""

    def __init__(
        self,
        *,
        describe_image: Optional[Callable[[str, str], Optional[str]]] = None,
        screens_dir: Optional[Path] = None,
        browser: Optional[str] = None,
        run: Optional[Callable[..., subprocess.CompletedProcess]] = None,
    ) -> None:
        #: root → the app running there. One at a time: two dev servers on
        #: one project is a port collision waiting to be reported as a bug.
        self._apps: Dict[str, AppProcess] = {}
        self._lock = threading.Lock()
        self._describe = describe_image
        self._screens = screens_dir
        self._browser = browser
        self._run = run or subprocess.run
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
                    f"Start the project's app as a background process — a dev server — and report "
                    f"the URL it prints. Available: {listed}. It keeps running until stopped."
                ),
                input_schema={
                    "type": "object",
                    "properties": {"runner": {"type": "string", "description": "Which app runner, by name."}},
                    "required": ["runner"],
                },
            ),
            ToolDescriptor(
                server_id=server_id, name=STOP_APP,
                description="Stop the project's running app.",
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDescriptor(
                server_id=server_id, name=APP_STATUS,
                description="Whether the project's app is running, its URL, and how long it has been up.",
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
        if name == STOP_APP:
            return self._stop(root)
        if name == APP_STATUS:
            return self.status(root)
        if name == READ_APP_LOG:
            return self._log(root, arguments.get("lines"))
        if name == LOOK_AT_APP:
            return self._look(root, str(arguments.get("url") or ""), str(arguments.get("question") or ""))
        return {"error": f"no tool called {name!r}"}

    # ------------------------------------------------------------ the process

    def _start(self, root: Path, wanted: str) -> Dict[str, Any]:
        if not wanted:
            return {"error": "no runner was named"}
        runners = {r.name: r for r in app_runners(root)}
        runner = runners.get(wanted)
        if runner is None:
            return {"error": f"no app runner called {wanted!r}. Available: {', '.join(sorted(runners)) or 'none'}"}
        key = str(root.resolve())
        with self._lock:
            current = self._apps.get(key)
            if current is not None and current.running:
                return {"error": f"{current.runner} is already running at {current.url or 'an unknown URL'}; stop it first", **current.to_json()}
            env = dict(os.environ)
            env.setdefault("NO_COLOR", "1")
            env["FORCE_COLOR"] = "0"
            env["PYTHONUNBUFFERED"] = "1"
            # `BROWSER=none` stops create-react-app style scripts opening a tab
            # the person did not ask for.
            env.setdefault("BROWSER", "none")
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
            app = AppProcess(runner=runner.name, command=" ".join(runner.argv), process=process, started_at=time.time(), lines=deque(maxlen=LOG_LINES))
            self._apps[key] = app
        threading.Thread(target=self._pump, args=(app,), daemon=True).start()
        logger.info("code pack: started %s in %s (pid %s)", runner.name, key, process.pid)

        # Wait briefly for the URL — it is the one thing the model needs next.
        deadline = time.monotonic() + URL_WAIT_SECONDS
        while time.monotonic() < deadline and app.url is None and app.running:
            time.sleep(0.2)
        result = app.to_json()
        if not app.running:
            result["error"] = "the app exited straight away; read_app_log has what it printed"
            result["log"] = "\n".join(list(app.lines)[-40:])
        elif app.url is None:
            result["note"] = f"running, but it has not printed a URL in {int(URL_WAIT_SECONDS)}s; read_app_log to see why, or look_at_app with the URL you expect"
        return result

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
        key = str(root.resolve())
        with self._lock:
            app = self._apps.get(key)
            if app is None:
                return {"stopped": False, "note": "nothing is running"}
            self._terminate(app)
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
            for app in list(self._apps.values()):
                self._terminate(app)
            self._apps.clear()

    def status(self, root: Path) -> Dict[str, Any]:
        app = self._apps.get(str(root.resolve()))
        if app is None:
            return {"running": False, "available": [r.name for r in app_runners(root)]}
        return app.to_json()

    def _log(self, root: Path, lines: Any) -> Dict[str, Any]:
        app = self._apps.get(str(root.resolve()))
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
        app = self._apps.get(str(root.resolve()))
        target = url.strip() or (app.url if app else "") or ""
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
                "No local vision model is installed, so Zaram cannot read the screenshot itself; "
                "it is saved and shown to the person. Installing one — for example "
                "`ollama pull qwen2.5vl:7b` (about 6 GB, one time) — lets Zaram read pages here, "
                "and the page never leaves the machine."
            )
            return result
        try:
            described = self._describe(str(out), question or "Describe what is on this page. Note any error messages, blank areas or broken layout.")
        except Exception as exc:  # noqa: BLE001 - a failed look is a result, not a crash
            described = None
            result["note"] = f"the vision model could not read it: {exc}"
        result["description"] = described
        if described is None and "note" not in result:
            result["note"] = "No local vision model is available to read the screenshot; it is saved and shown to the person."
        return result

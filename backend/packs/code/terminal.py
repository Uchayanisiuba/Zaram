"""A terminal — slice 12 of the code pack.

Asked for by the maintainer on 3 October 2026: *"does Zaram have a terminal
like yours, is it able to use the terminal to perform tasks like creating
environments, downloading dependencies and tasks needed to build various
types of software"*.

It did not, and the gap was real rather than an oversight. `runners.py` can
only offer commands it **detected** — the scripts in a `package.json`, the
targets in a `pyproject.toml` — so `npm test` works and `python -m venv .venv`
does not, because a venv that does not exist yet is in no manifest. Every
project that has to be *set up* before it can be run was out of reach, which
is most projects on their first day.

**This is the thing `runners.py` was built to avoid, so it arrives with the
reasons written down rather than quietly.** That module says it in as many
words — *"there is no shell: a runner is a named program and its arguments,
so a stray semicolon has nothing to do"* — and that was the right call for
what it governs. A detected runner is a known program; a shell is whatever
the string says. Nothing here weakens `runners.py`; it stays the path for
commands a project declares, and this is a separate, separately-granted
capability for the ones it cannot.

Four things make it a capability rather than a hole, and the maintainer chose
the shape of the first on 3 October:

**A grant of its own, per project, off by default.** The fourth after
`writes`, `runs` and `drives`, for the reason the third was split from the
second a few hours earlier: these are not the same risk, and a grant that
cannot express the difference is one that gets refused whole. Running a
project's declared tests, pressing a button on its page, and running an
arbitrary command line are three different things to agree to.

**The person sees every command and can type their own.** The terminal is a
surface, not a hidden subprocess. What Zaram ran is on screen with its
output, in the order it happened, and the same box takes the person's own
typing — a terminal somebody cannot type in is a log.

**One shell per project, with a working directory it cannot leave.** The
process starts in the project root and `cd` is the person's business inside
it; nothing here resolves a path for the model, because a path the model
chooses is not a sandbox. The shell dies with the project being closed.

**Bounded, and the bound is visible.** A command that runs forever stops, and
output is capped — an unbounded `tail -f` in a prompt is a context window
gone.

**What this is not: a PTY.** The shell is spawned with pipes, so there is no
terminal emulation — no colour, no cursor movement, no `vim`, no progress bar
that redraws in place. That is a real limit and it is stated here rather than
discovered: a true PTY on Windows means ConPTY through `pywinpty`, which is a
dependency and a packaging entry, and the jobs actually asked for — create a
virtualenv, install dependencies, build, scaffold — are all non-interactive.
If somebody needs `vim`, they have a terminal already; this one exists so
Zaram and the person can set a project up together.
"""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SERVER_ID = "code"

RUN_IN_TERMINAL = "run_in_terminal"
READ_TERMINAL = "read_terminal"
STOP_TERMINAL = "stop_terminal"

TOOL_NAMES = frozenset({RUN_IN_TERMINAL, READ_TERMINAL, STOP_TERMINAL})

#: Everything here changes something, including the read.
#:
#: `read_terminal` reads, but `looks_read_only` would wave it through on its
#: name and it must not run before the grant is given — the output of a shell
#: in somebody's project is not public, and a tool that can see it without
#: being allowed to is a smaller version of the hole found this morning in
#: `open_in_browser`. Reported through `CodeTools.mutative_tools`.
MUTATIVE = frozenset(TOOL_NAMES)

HOW_TO_PERMIT = (
    "Allow Zaram to use the terminal for this project in Project, then ask again."
)

#: How long one command may run. Generous, because an install on a metered
#: connection is minutes and a timeout that kills one leaves a half-populated
#: `node_modules` — worse than the wait it avoided. `runners.py` makes the
#: same allowance for the same reason.
TIMEOUT_SECONDS = 900

#: How long to wait for output once a command has finished writing. The shell
#: gives no end-of-command signal over a pipe, so a sentinel is echoed after
#: each command and this bounds the wait for it.
SETTLE_SECONDS = 0.4

#: Characters of output kept per command. A build that prints a megabyte must
#: not become a megabyte of prompt; the tail is kept because the error is at
#: the end.
MAX_OUTPUT_CHARS = 20_000

#: Lines of scrollback a session holds, for the surface and for
#: `read_terminal`. Bounded for the same reason.
MAX_SCROLLBACK = 2_000

NO_PROJECT = (
    "No coding project is open, so there is no folder to run a command in. "
    "Open one in Project and point it at the repository."
)

TIMED_OUT = (
    "`{command}` was still running after {seconds} seconds and was stopped. "
    "Its output so far is above. If it genuinely takes longer, run it in your "
    "own terminal."
)

#: Echoed after each command so the reader knows where the output ends.
#: Random-ish and unlikely to appear in real output.
_DONE = "__zaram_done_a9f3__"


@dataclass
class Line:
    """One line of scrollback, and who caused it."""

    text: str
    #: ``"command"`` for the command line itself, ``"output"`` for what it
    #: printed. The surface renders them differently and a person needs to
    #: see which is which.
    kind: str
    #: ``"zaram"`` or ``"user"``. **Both are kept and both are labelled**,
    #: because a terminal that does not say who typed what is a terminal
    #: nobody can audit afterwards.
    who: str
    at: float = field(default_factory=time.time)

    def to_json(self) -> Dict[str, Any]:
        return {"text": self.text, "kind": self.kind, "who": self.who, "at": self.at}


class Session:
    """One shell, living in one project's folder.

    Reading happens on a thread because a pipe read blocks, and the reply
    that is waiting for it must not. The queue is the hand-off.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.scrollback: List[Line] = []
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._lock = threading.Lock()
        self.process = subprocess.Popen(
            self._argv(),
            cwd=str(root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            # **A clean environment, the same allow-list a tool server gets.**
            # A shell in somebody's project has no more business holding
            # `ZARAM_API_SECRET` than a stranger's MCP server does, and
            # `child_env.py` already decides that question correctly — a
            # second answer here would be a second thing to keep in step.
            env=self._environment(),
        )
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    @staticmethod
    def _argv() -> List[str]:
        """The shell, per platform.

        PowerShell on Windows because it is what the person's own terminal
        is and what every Windows build instruction assumes; `-NoLogo` and
        `-NoProfile` because a profile can print a banner, change the prompt
        or fail, and none of that is this shell's business.
        """
        if os.name == "nt":
            return ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", "-"]
        return [os.environ.get("SHELL", "/bin/sh"), "-i"]

    @staticmethod
    def _environment() -> Dict[str, str]:
        from runtimes.mcp.child_env import child_environment

        return child_environment(os.environ)

    def _pump(self) -> None:
        """Move the shell's output onto the queue, line by line, until it
        closes. Daemon so a session nobody closed cannot hold a shutdown."""
        stream = self.process.stdout
        if stream is None:
            return
        try:
            for line in stream:
                self._queue.put(line.rstrip("\n"))
        except (OSError, ValueError):
            # The pipe closed under us; the session is over and `alive`
            # already answers that.
            pass
        finally:
            self._queue.put(None)  # type: ignore[arg-type]

    def alive(self) -> bool:
        return self.process.poll() is None

    def _remember(self, text: str, kind: str, who: str) -> None:
        self.scrollback.append(Line(text=text, kind=kind, who=who))
        if len(self.scrollback) > MAX_SCROLLBACK:
            del self.scrollback[: len(self.scrollback) - MAX_SCROLLBACK]

    def run(self, command: str, *, who: str, timeout: float = TIMEOUT_SECONDS) -> str:
        """Send one command and collect what it printed.

        Serialised, because two commands interleaved in one shell produce
        output neither caller can attribute. The lock is held for the whole
        command, which is also what makes `read_terminal` meaningful.
        """
        with self._lock:
            if not self.alive():
                return "The terminal has closed. Ask again to start a new one."

            self._remember(command, "command", who)
            stdin = self.process.stdin
            if stdin is None:
                return "The terminal cannot be written to."
            try:
                stdin.write(f"{command}\n")
                # Echoed after the command so the reader knows where to stop.
                # `Write-Output` rather than `echo` because PowerShell aliases
                # `echo` to it anyway and the explicit name cannot be shadowed
                # by a function the command defined.
                stdin.write(
                    f"Write-Output {_DONE}\n" if os.name == "nt" else f"echo {_DONE}\n"
                )
                stdin.flush()
            except (OSError, ValueError):
                return "The terminal stopped accepting input."

            collected: List[str] = []
            deadline = time.monotonic() + timeout
            timed_out = True
            while time.monotonic() < deadline:
                try:
                    line = self._queue.get(timeout=SETTLE_SECONDS)
                except queue.Empty:
                    continue
                if line is None:
                    break
                if _DONE in line:
                    timed_out = False
                    break
                collected.append(line)
                self._remember(line, "output", who)

            output = "\n".join(collected)
            if len(output) > MAX_OUTPUT_CHARS:
                # The tail, because the error is at the end.
                output = "…(earlier output dropped)…\n" + output[-MAX_OUTPUT_CHARS:]
            if timed_out:
                note = TIMED_OUT.format(command=command, seconds=int(timeout))
                self._remember(note, "output", "zaram")
                return f"{output}\n\n{note}" if output else note
            return output

    def close(self) -> None:
        try:
            if self.process.stdin is not None:
                self.process.stdin.close()
        except (OSError, ValueError):
            pass
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except (OSError, subprocess.SubprocessError):
            try:
                self.process.kill()
            except OSError:
                pass


class TerminalTools:
    """The three tools, and the sessions behind them.

    One session per project root. Keyed by root rather than by project id for
    the same reason the driving sessions are: the root is what the tools are
    sandboxed to, and two projects pointed at one folder are one terminal.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------ sessions

    def session_for(self, root: Path, *, create: bool = True) -> Optional[Session]:
        key = str(root)
        with self._lock:
            session = self._sessions.get(key)
            if session is not None and session.alive():
                return session
            if session is not None:
                session.close()
                self._sessions.pop(key, None)
            if not create:
                return None
            try:
                session = Session(root)
            except OSError as exc:
                logger.warning("could not start a terminal in %s: %s", root, exc)
                return None
            self._sessions[key] = session
            return session

    def close_all(self) -> None:
        with self._lock:
            for session in self._sessions.values():
                session.close()
            self._sessions.clear()

    # --------------------------------------------------------------- tools

    def descriptors(self, server_id: str) -> List[Any]:
        from runtimes.mcp.client import ToolDescriptor

        return [
            ToolDescriptor(
                server_id=server_id,
                name=RUN_IN_TERMINAL,
                description=(
                    "Run one command line in the open project's terminal and "
                    "return what it printed. Use this for setup a project's "
                    "own scripts do not cover — creating a virtualenv, "
                    "installing dependencies, scaffolding, a one-off build "
                    "command. Prefer `run_command` where the project already "
                    "declares the task. The working directory is the project "
                    "root and persists between calls."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The command line, exactly as it would be typed.",
                        }
                    },
                    "required": ["command"],
                },
            ),
            ToolDescriptor(
                server_id=server_id,
                name=READ_TERMINAL,
                description=(
                    "What is on the terminal already, including commands the "
                    "person typed themselves. Use it when they refer to "
                    "something they ran."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "lines": {
                            "type": "integer",
                            "description": "How many trailing lines to return. Default 100.",
                        }
                    },
                },
            ),
            ToolDescriptor(
                server_id=server_id,
                name=STOP_TERMINAL,
                description="Close the project's terminal and whatever is running in it.",
                input_schema={"type": "object", "properties": {}},
            ),
        ]

    def call(self, name: str, arguments: Dict[str, Any], root: Optional[Path]) -> Dict[str, Any]:
        if root is None:
            return {"error": NO_PROJECT}

        if name == STOP_TERMINAL:
            session = self.session_for(root, create=False)
            if session is None:
                return {"stopped": False, "said": "No terminal was open."}
            session.close()
            with self._lock:
                self._sessions.pop(str(root), None)
            return {"stopped": True, "said": "Closed the terminal."}

        if name == READ_TERMINAL:
            session = self.session_for(root, create=False)
            if session is None:
                return {"lines": [], "said": "No terminal is open yet."}
            wanted = arguments.get("lines")
            count = wanted if isinstance(wanted, int) and wanted > 0 else 100
            tail = session.scrollback[-count:]
            return {"lines": [line.to_json() for line in tail]}

        if name == RUN_IN_TERMINAL:
            command = str(arguments.get("command") or "").strip()
            if not command:
                return {"error": "No command was given."}
            session = self.session_for(root)
            if session is None:
                return {"error": "A terminal could not be started in this project."}
            output = session.run(command, who="zaram")
            return {"command": command, "output": output, "cwd": str(root)}

        return {"error": f"{name} is not a terminal tool."}

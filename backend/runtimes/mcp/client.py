"""An MCP client over stdio, in terms of the standard library.

Why this is hand-written rather than the SDK
--------------------------------------------
`CLAUDE.md` names packaging as the blocker for the whole product, and the
official Python SDK adds ten packages and ~11 MB — including `pywin32` and
`cryptography`, two native-binary dependencies, days before an installer ships.
The stdio transport is newline-delimited JSON-RPC 2.0 over a subprocess, which
is a few hundred lines of `json` and `subprocess`.

**The transport is invisible to everyone but us.** A server cannot tell what
library is on the other end of the pipe, so this costs no compatibility and
gains no discoverability — that comes from a place to attach a server, which is
a separate piece of work. The SDK remains a drop-in replacement behind
`McpServer`, and the reason to take it is the one capability this genuinely
lacks: HTTP/SSE transport for hosted servers.

Two eras, and the newer one is not what this repository would have guessed
------------------------------------------------------------------------
Read from the 2026-07-28 specification rather than from memory, which is the
only reason this is right. The protocol changed shape:

* **Legacy** servers expect an `initialize` request, then a
  `notifications/initialized`, and carry no per-request metadata.
* **Modern** servers (2025-11-25 and later) expect `server/discover`, and each
  request carries `_meta` naming the protocol version and the client.

Every server installable today is legacy-era, and the ones written next will not
be, so a client that only speaks one of them is wrong within the year either
way. The spec prescribes the probe and warns against the shortcut:

    Legacy servers may respond to unknown requests with implementation-defined
    errors or fail to respond entirely, so fallback logic must not rely on a
    single specific error code.

So `connect()` sends `server/discover` first and treats *anything other than a
discovery result* — a JSON-RPC error of any code, a malformed reply, or silence
until the timeout — as evidence of a legacy server, and falls back. Probing
first is also what stops a legacy server from acting on an era-ambiguous method
before its handshake has happened.

What this deliberately does not do
----------------------------------
No HTTP or SSE transport, so a hosted server will not attach. No OAuth. No
resources, prompts, sampling or subscriptions — tools only. Each of those is a
capability gap named here rather than discovered later, and none of them is
needed to answer "can Zaram call a tool somebody else wrote".

**Nothing here decides whether a tool may run.** This module speaks the
protocol and returns what a server said. A tool description is third-party text
under `core/untrusted`, a call that leaves the machine is `EgressGate`'s to log,
and consent is the runtime's to ask for. Keeping those out of the transport is
what stops a well-written description from becoming a permission.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: The version this client prefers, newest first. Sent in `server/discover` and
#: used to pick a mutually supported version when a modern server refuses.
SUPPORTED_VERSIONS = ("2026-07-28", "2025-11-25", "2025-06-18")

#: What Zaram calls itself to a server. Servers log this and some vary their
#: behaviour on it, so it is honest rather than an imitation of another client.
CLIENT_INFO = {"name": "Zaram", "version": "0.1"}

#: "Unsupported protocol version" — the one modern error whose payload names
#: what the server *does* support, so a retry is possible rather than a guess.
#: Recognised, but never used as the sole test for whether a server is modern:
#: the spec says fallback must not rely on a single error code.
UNSUPPORTED_PROTOCOL_VERSION = -32022

#: How long a single request may wait. Generous because a server's first call
#: often loads something — the same distinction `ollama_engine` draws between
#: the wait for weights and the wait between tokens, and the reason a shorter
#: default would make a working server look broken.
DEFAULT_TIMEOUT = 30.0

#: The handshake gets its own, shorter budget. A server that has not answered a
#: probe in this long is being treated as legacy anyway, so waiting the full
#: request timeout twice only delays a connection that is going to succeed.
PROBE_TIMEOUT = 8.0


class McpError(RuntimeError):
    """A server answered, and the answer was an error."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"{message} (code {code})")
        self.code = code
        self.message = message
        self.data = data


@dataclass(frozen=True)
class ToolDescriptor:
    """One tool a server offers.

    `description` and `name` are **third-party text**, written by whoever wrote
    the server. They are carried verbatim and marked, never trusted: it is the
    runtime's job to scan them and the gate's job to decide, and this dataclass
    exists partly so that nothing downstream can mistake them for something
    Zaram said.
    """

    server_id: str
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)

    @property
    def qualified_name(self) -> str:
        """`server:tool`. Two servers may both offer `search`."""
        return f"{self.server_id}:{self.name}"


class McpServer:
    """One MCP server, running as a child process.

    Synchronous by design. The backend is async, but a subprocess pipe on
    Windows is the one place `asyncio` is least pleasant, and a blocking client
    behind `asyncio.to_thread` is both simpler to reason about and directly
    testable without an event loop — which is what makes the live probe in the
    suite possible at all.
    """

    def __init__(
        self,
        server_id: str,
        command: List[str],
        *,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.server_id = server_id
        self.command = command
        self._env = env
        self._cwd = cwd
        self._timeout = timeout

        self._process: Optional[subprocess.Popen] = None
        self._replies: "Queue[Dict[str, Any]]" = Queue()
        self._reader: Optional[threading.Thread] = None
        self._stderr_reader: Optional[threading.Thread] = None
        self._stderr_tail: List[str] = []
        self._next_id = 0
        self._lock = threading.Lock()

        #: Filled in by `connect`. `None` until then, and that is the honest
        #: state rather than a default that reads as a measurement.
        self.protocol_version: Optional[str] = None
        self.era: Optional[str] = None  # "modern" | "legacy"
        self.server_info: Dict[str, Any] = {}

    # ----------------------------------------------------------------- wire

    @staticmethod
    def _launchable(command: List[str]) -> List[str]:
        """The command as Windows can actually start it.

        **Found by the live probe on the first run, and it would have shipped.**
        `npx -y @modelcontextprotocol/server-filesystem` — the way virtually
        every MCP server is configured, because virtually all of them are npm
        packages — failed with `WinError 2`. `shutil.which` finds `npx.cmd`
        happily; `CreateProcess` cannot execute a batch file at all, so every
        npm-published server would have been unstartable for every Windows
        user while the unit tests stayed green, because a fake server is a
        `.py` run by `sys.executable` and never exercises this.

        Two steps. Resolve through `PATH` ourselves, because a bare name that
        `which` can find is not necessarily a name `CreateProcess` can; then,
        for a `.cmd` or `.bat`, go through the command processor, which is the
        only thing that can run one.

        The argument list stays a list — never joined into a string — so
        arguments are still passed as arguments and a path with a space in it
        cannot become two of them.
        """
        if not command:
            return command
        resolved = shutil.which(command[0]) or command[0]
        if sys.platform == "win32" and resolved.lower().endswith((".cmd", ".bat")):
            comspec = os.environ.get("COMSPEC") or "cmd.exe"
            return [comspec, "/c", resolved, *command[1:]]
        return [resolved, *command[1:]]

    def _start(self) -> None:
        # `stderr` is captured, not inherited: the spec allows a server to log
        # there freely, and a child writing to Zaram's own stderr would put a
        # stranger's text into the desktop log with no attribution.
        self._process = subprocess.Popen(
            self._launchable(self.command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._env,
            cwd=self._cwd,
            text=True,
            encoding="utf-8",
            bufsize=1,
            # Windows: keep the child from flashing a console window when the
            # desktop app is packaged and has none of its own.
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()
        self._stderr_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_reader.start()

    def _read_stdout(self) -> None:
        assert self._process and self._process.stdout
        for line in self._process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._replies.put(json.loads(line))
            except json.JSONDecodeError:
                # The spec says stdout carries MCP messages only. Servers break
                # that — a stray banner or a progress line — and dropping the
                # line is right where failing the session would not be.
                logger.debug("%s: non-JSON on stdout: %.120s", self.server_id, line)

    def _read_stderr(self) -> None:
        assert self._process and self._process.stderr
        for line in self._process.stderr:
            # Bounded: a chatty server must not grow this without limit, and the
            # last few lines are what explain a failure.
            self._stderr_tail.append(line.rstrip())
            del self._stderr_tail[:-20]

    def _send(self, message: Dict[str, Any]) -> None:
        if not self._process or not self._process.stdin:
            raise McpError(-32000, f"{self.server_id} is not running")
        self._process.stdin.write(json.dumps(message) + "\n")
        self._process.stdin.flush()

    def _meta(self) -> Dict[str, Any]:
        """Per-request metadata, modern era only.

        Namespaced keys, because the spec puts them under
        `io.modelcontextprotocol/` rather than at the top of `_meta`.
        """
        return {
            "io.modelcontextprotocol/protocolVersion": self.protocol_version,
            "io.modelcontextprotocol/clientInfo": CLIENT_INFO,
            "io.modelcontextprotocol/clientCapabilities": {},
        }

    def _request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        timeout: Optional[float] = None,
        with_meta: bool = True,
    ) -> Dict[str, Any]:
        """One request, one reply. Raises `McpError` on an error reply."""
        with self._lock:
            self._next_id += 1
            request_id = self._next_id

        body: Dict[str, Any] = dict(params or {})
        if with_meta and self.era == "modern":
            body["_meta"] = self._meta()

        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": body})

        deadline = timeout if timeout is not None else self._timeout
        # A reply for a different id is a notification or a late answer to a
        # request that already timed out. Skipped rather than returned, because
        # handing a caller somebody else's payload is worse than waiting.
        while True:
            try:
                message = self._replies.get(timeout=deadline)
            except Empty:
                raise TimeoutError(
                    f"{self.server_id} did not answer {method} within {deadline:.0f}s"
                ) from None
            if message.get("id") != request_id:
                continue
            if "error" in message:
                err = message["error"] or {}
                raise McpError(
                    int(err.get("code", -32000)),
                    str(err.get("message", "unknown error")),
                    err.get("data"),
                )
            return message.get("result") or {}

    # ------------------------------------------------------------ handshake

    def connect(self) -> None:
        """Start the server and work out which era it speaks.

        `server/discover` first, always — including for a client that only
        wanted the modern era, because the spec warns that a legacy server may
        otherwise act on an era-ambiguous method before its handshake.
        """
        self._start()

        try:
            result = self._request(
                "server/discover",
                {
                    "_meta": {
                        "io.modelcontextprotocol/protocolVersion": SUPPORTED_VERSIONS[0],
                        "io.modelcontextprotocol/clientInfo": CLIENT_INFO,
                        "io.modelcontextprotocol/clientCapabilities": {},
                    }
                },
                timeout=PROBE_TIMEOUT,
                with_meta=False,
            )
        except McpError as err:
            # The one error worth reading rather than falling back on: a modern
            # server saying which versions it has. Anything else — any other
            # code, any implementation-defined refusal — means legacy, because
            # the spec forbids resting the decision on a single code.
            if err.code == UNSUPPORTED_PROTOCOL_VERSION and isinstance(err.data, dict):
                shared = [v for v in SUPPORTED_VERSIONS if v in (err.data.get("supported") or [])]
                if shared:
                    self.era = "modern"
                    self.protocol_version = shared[0]
                    return
            self._handshake_legacy()
            return
        except TimeoutError:
            # Silence is the other legacy signature the spec names.
            self._handshake_legacy()
            return

        self.era = "modern"
        self.server_info = result.get("serverInfo") or {}
        offered = result.get("supportedVersions") or result.get("versions") or []
        shared = [v for v in SUPPORTED_VERSIONS if v in offered]
        # A discovery result that names no version we know still identifies a
        # modern server; preferring our newest is a better guess than refusing,
        # and a genuinely unsupported choice comes back as -32022 next request.
        self.protocol_version = shared[0] if shared else SUPPORTED_VERSIONS[0]

    def _handshake_legacy(self) -> None:
        result = self._request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": CLIENT_INFO,
            },
            with_meta=False,
        )
        self.era = "legacy"
        self.protocol_version = result.get("protocolVersion") or "2025-06-18"
        self.server_info = result.get("serverInfo") or {}
        # A notification: no id, and no reply is coming. Sending it is what
        # tells the server the handshake is complete; several refuse everything
        # until it arrives.
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    # ---------------------------------------------------------------- tools

    def list_tools(self) -> List[ToolDescriptor]:
        result = self._request("tools/list")
        tools = []
        for raw in result.get("tools") or []:
            name = raw.get("name")
            if not name:
                continue
            tools.append(
                ToolDescriptor(
                    server_id=self.server_id,
                    name=str(name),
                    description=str(raw.get("description") or ""),
                    input_schema=raw.get("inputSchema") or {},
                )
            )
        return tools

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Invoke one tool.

        Returns the server's result untouched. `isError` is part of a normal
        result rather than a JSON-RPC error — a tool that failed is an answer,
        and flattening the two would lose which one happened.
        """
        return self._request("tools/call", {"name": name, "arguments": arguments or {}})

    # --------------------------------------------------------------- teardown

    def close(self) -> None:
        if not self._process:
            return
        try:
            if self._process.stdin:
                self._process.stdin.close()
            self._process.terminate()
            self._process.wait(timeout=5)
        except Exception:  # noqa: BLE001 - teardown must not raise
            try:
                self._process.kill()
            except Exception:  # noqa: BLE001
                pass
        finally:
            self._process = None

    @property
    def stderr_tail(self) -> List[str]:
        """The last lines the server wrote to stderr, for diagnosing a failure."""
        return list(self._stderr_tail)

    def __enter__(self) -> "McpServer":
        self.connect()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

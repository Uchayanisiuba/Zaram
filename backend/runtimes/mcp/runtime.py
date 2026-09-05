"""Tools other people wrote, reachable from a conversation.

Modelled on `DocumentsRuntime` because that is the path that demonstrably
reaches chat: `planner` maps an intent to a capability, `dispatcher` routes it
to the runtime that declares it, `bootstrapper` registers the runtime at boot.
Copying a working path is worth more here than a better one nothing calls —
this repository's recurring failure is the complete subsystem with no caller.

Three things this runtime is responsible for, and none of them is the protocol
-----------------------------------------------------------------------------
**Scanning what a server says.** A tool's name and description are written by a
stranger and sit next to the user's question, which is the definition of
untrusted input. `core.untrusted` already exists for this and already names
`TOOL_OUTPUT` as covering "an MCP server whose description and output are both
written by a third party". Findings are attached and reported; they never
silently drop a tool, because a blocklist of hostile phrasings is guessed
rather than known, and quietly hiding a tool the user attached is its own kind
of lie.

**Keeping the tool list small.** Fourteen schemas from one filesystem server is
already most of a small model's working context; five servers would be all of
it, and the context spent on tools is context not spent on recall — which is
the product. So the runtime hands over a *budget* of tools, not all of them.

The ranker is injected rather than imported, like `DocumentsRuntime`'s
extractor, so the embedder stays in the models layer. **Selection is ordering,
never permission.** A tool that is not shortlisted is merely absent from this
turn; a tool that is shortlisted has earned nothing. `policy.decide` runs
afterwards on whatever the model actually chose, which is what stops a
well-written description becoming a privilege — the mistake `CLAUDE.md` records
paying for three times.

**Applying the write policy.** `policy.decide` is the whole of it, and the
runtime's job is to carry its verdict honestly: `REFUSE` says why and what
would change it, `CONFIRM` returns the question rather than asking it here,
because the runtime has no user to ask — the surface that does gets the
decision and calls back with `grant`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

from core.contracts import Capability, CapabilityLocality, RuntimeMetadata, RuntimeState
from core.untrusted import Provenance, scan

from .client import McpServer, ToolDescriptor
from .config import ServerConfig, ServerStore
from .policy import Verdict, decide

logger = logging.getLogger(__name__)

RUNTIME_ID = "mcp"
RUNTIME_VERSION = "0.1.0"

#: List the tools available for a request.
LIST_TOOLS = "mcp.list_tools"
#: Invoke one, subject to the write policy.
CALL = "mcp.call"

#: How many tool schemas may be put in front of a model at once.
#:
#: Measured rather than chosen: one filesystem server offers 14, and the local
#: 14B answered correctly with all 14 in context — so the cap is not about
#: correctness, it is about what is left for recall. Eight is roughly two
#: servers' worth of the useful ones, and it is a starting number to be
#: re-measured, not a constant anybody proved.
DEFAULT_TOOL_BUDGET = 8


class McpRuntime:
    """Attached MCP servers, their tools, and what those tools may do."""

    def __init__(
        self,
        store: Optional[ServerStore] = None,
        *,
        tool_budget: int = DEFAULT_TOOL_BUDGET,
    ):
        self._store = store or ServerStore()
        self._budget = tool_budget
        self._state = RuntimeState.UNINITIALIZED
        self._start_time = time.time()
        self._connections: Dict[str, McpServer] = {}
        self._calls = 0
        #: Injected. See `set_ranker`.
        self._rank: Optional[Callable[[str, Sequence[ToolDescriptor], int], List[ToolDescriptor]]] = None

    def set_ranker(self, rank: Callable[[str, Sequence[ToolDescriptor], int], List[ToolDescriptor]]) -> None:
        """Give this runtime a way to choose which tools are relevant.

        Injected for the same reason the documents extractor is: the embedder
        lives in the models layer and this one must not depend on it. Absent is
        a supported state — without a ranker the budget is applied in the
        server's own order, which is worse but honest, and never silently
        unlimited.
        """
        self._rank = rank

    # ------------------------------------------------------------- lifecycle

    def get_runtime_id(self) -> str:
        return RUNTIME_ID

    def get_version(self) -> str:
        return RUNTIME_VERSION

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_id=RUNTIME_ID,
            version=RUNTIME_VERSION,
            priority="normal",
            capabilities=[
                Capability(
                    id=LIST_TOOLS,
                    runtime_id=RUNTIME_ID,
                    category="tool",
                    locality=CapabilityLocality.LOCAL,
                ),
                # **HYBRID, not LOCAL, and the distinction is load-bearing.**
                # A stdio server is a process on this machine, but what it
                # reaches is its own business — the playwright server on this
                # very machine drives a browser onto the open internet. Calling
                # this LOCAL would state something about egress that Zaram
                # cannot know, on the one axis the product is trusted for.
                # There is no UNKNOWN member; HYBRID is the honest one of the
                # four, and it is why `mcp.call` must still pass the gate.
                Capability(
                    id=CALL,
                    runtime_id=RUNTIME_ID,
                    category="tool",
                    locality=CapabilityLocality.HYBRID,
                ),
            ],
            dependencies=[],
            auto_start=True,
        )

    def get_state(self) -> RuntimeState:
        return self._state

    async def initialize(self) -> None:
        # Servers are *not* connected here. Starting every configured
        # subprocess at boot would put a stranger's process on the critical
        # path of Zaram launching, and the measured cost of a cold `npx` server
        # is tens of seconds. They connect on first use instead.
        self._state = RuntimeState.READY
        configured = self._store.load()
        logger.info(
            "MCP runtime ready; %d server(s) configured, %d reachable over stdio",
            len(configured),
            sum(1 for c in configured.values() if c.reachable),
        )

    async def shutdown(self) -> None:
        self._state = RuntimeState.STOPPING
        for server in self._connections.values():
            server.close()
        self._connections.clear()
        self._state = RuntimeState.STOPPED

    async def health_check(self) -> Dict[str, Any]:
        configured = self._store.load()
        return {
            "status": "healthy" if self._state == RuntimeState.READY else "degraded",
            "runtime_id": RUNTIME_ID,
            "calls": self._calls,
            "servers": {
                name: {
                    "transport": cfg.transport,
                    # Visible rather than silent: an http server is configured
                    # and cannot be reached, and the interface must be able to
                    # say so instead of showing an empty list.
                    "reachable": cfg.reachable,
                    "reason": "" if cfg.reachable else "http transport is not implemented yet",
                    "writes": cfg.writes.value,
                    "connected": name in self._connections,
                }
                for name, cfg in configured.items()
            },
        }

    # ------------------------------------------------------------ connection

    async def _connect(self, cfg: ServerConfig) -> Optional[McpServer]:
        if cfg.server_id in self._connections:
            return self._connections[cfg.server_id]
        if not cfg.reachable:
            return None
        server = McpServer(cfg.server_id, cfg.command, env=cfg.env or None)
        try:
            # Blocking client on a thread: a subprocess pipe is the one place
            # asyncio is least pleasant on Windows, and the event loop must not
            # stall while a stranger's server starts.
            await asyncio.to_thread(server.connect)
        except Exception as exc:  # noqa: BLE001 - a bad server must not take the runtime down
            logger.warning("could not attach %s: %s", cfg.server_id, exc)
            server.close()
            return None
        self._connections[cfg.server_id] = server
        return server

    # ----------------------------------------------------------------- tools

    async def available_tools(self, query: str = "") -> List[Dict[str, Any]]:
        """The tools worth putting in front of the model for this request."""
        found: List[ToolDescriptor] = []
        for cfg in self._store.load().values():
            server = await self._connect(cfg)
            if server is None:
                continue
            try:
                found.extend(await asyncio.to_thread(server.list_tools))
            except Exception as exc:  # noqa: BLE001
                logger.warning("could not list tools on %s: %s", cfg.server_id, exc)

        shortlisted = self._rank(query, found, self._budget) if self._rank else found[: self._budget]

        described = []
        for tool in shortlisted:
            # Reported, never dropped. A finding is a label on third-party
            # text, and `may_instruct` is the boundary that already refuses to
            # let it instruct anything.
            findings = scan(f"{tool.name} {tool.description}")
            described.append(
                {
                    "server": tool.server_id,
                    "name": tool.name,
                    "qualified_name": tool.qualified_name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                    "provenance": Provenance.TOOL_OUTPUT.value,
                    "suspicions": [s.value for s in findings],
                }
            )
        return described

    # ------------------------------------------------------------------ call

    async def execute(self, capability_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if capability_id == LIST_TOOLS:
            return {"success": True, "tools": await self.available_tools(input_data.get("query") or "")}
        if capability_id != CALL:
            return {"success": False, "error": f"unknown capability {capability_id}"}

        server_id = str(input_data.get("server") or "")
        tool_name = str(input_data.get("tool") or "")
        arguments = input_data.get("arguments") or {}
        # Set only by a surface that has actually asked the user. Never by the
        # model, and never inferred from the request.
        confirmed = bool(input_data.get("confirmed"))

        cfg = self._store.load().get(server_id)
        if cfg is None:
            return {"success": False, "error": f"no server called {server_id!r} is configured"}

        decision = decide(
            tool_name=tool_name,
            mode=cfg.writes,
            granted_tools=cfg.granted_tools,
            annotations=input_data.get("annotations"),
        )

        if decision.verdict is Verdict.REFUSE:
            return {"success": False, "refused": True, "reason": decision.reason}

        if decision.verdict is Verdict.CONFIRM and not confirmed:
            # Returned rather than asked. This runtime has no user; the surface
            # that does gets the question and comes back with `confirmed`.
            return {
                "success": False,
                "needs_confirmation": True,
                "server": server_id,
                "tool": tool_name,
                "reason": decision.reason,
            }

        server = await self._connect(cfg)
        if server is None:
            return {"success": False, "error": f"could not attach {server_id}"}

        try:
            result = await asyncio.to_thread(server.call_tool, tool_name, arguments)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"{tool_name} failed: {exc}"}

        self._calls += 1
        return {
            "success": True,
            "result": result,
            # Carried so nothing downstream mistakes a server's output for
            # something Zaram said.
            "provenance": Provenance.TOOL_OUTPUT.value,
        }

    def server_names(self) -> List[str]:
        """What the user called the servers they attached.

        Read by the planner as routing vocabulary: with Blender attached,
        "blender" becomes a word that means *tool request* on this machine.
        Configured, not connected — this must answer without starting anybody's
        subprocess, because it is consulted on the way to classifying a prompt.
        """
        return list(self._store.load().keys())

    def grant(self, server_id: str, tool_name: str) -> None:
        """Record that the user allowed this tool, so it stops asking."""
        self._store.grant(server_id, tool_name)

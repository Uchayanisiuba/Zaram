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
import inspect
import logging
import os
import time
from pathlib import Path
from typing import Set, Any, Callable, Dict, List, Mapping, Optional, Sequence

from core.contracts import Capability, CapabilityLocality, RuntimeMetadata, RuntimeState
from core.untrusted import Provenance, scan

from .client import McpServer, ToolDescriptor
from .config import ServerConfig, ServerStore
from .floors import floor_for
from .policy import Verdict, WriteMode, always_asks, decide, looks_destructive, looks_outbound

logger = logging.getLogger(__name__)

RUNTIME_ID = "mcp"
RUNTIME_VERSION = "0.1.0"

#: List the tools available for a request.
LIST_TOOLS = "mcp.list_tools"
#: Invoke one, subject to the write policy.
CALL = "mcp.call"

#: Pictures a tool sent back, kept so the person can see what Zaram saw and a
#: model that can see is shown the picture itself.
PICTURE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
#: How many are kept. A screenshot of somebody's desktop is a liability before
#: it is a feature (CLAUDE.md, retention), so this is a short window rather
#: than an archive: enough to scroll back through one task, never a record.
PICTURES_KEPT = 40
#: Larger than any screenshot measured (2.2 MB for 1920x1080, base64), small
#: enough that a server cannot fill the disk through this folder.
PICTURE_MAX_BYTES = 20 * 1024 * 1024


def pictures_dir() -> Path:
    """Where tool pictures are kept: Zaram's data directory, never a project."""
    from core.paths import data_dir

    return Path(data_dir()) / "screens" / "tools"


def keep_media(result: Any, folder: Optional[Path] = None) -> tuple[Any, List[str]]:
    """A tool's result with its pictures saved to disk, and where they went.

    Found 10 October 2026, by asking the resident model to open google.com with
    computer use on: it read a window and the run died with *"prompt length
    1690633 exceeds the available context size of 65536"*. `get_window_state`
    returns the window's text tree (4.7 KB) **and a 2.2 MB base64 screenshot**,
    and the whole result was written into the prompt as text -- where a
    picture is not a picture, only two million characters of noise.

    The first fix dropped the payload, and the maintainer rejected that the
    same day: *"Don't block images."* Right -- the picture is the most useful
    thing a desktop tool returns, it was only travelling the wrong way. So it
    is kept: saved here, shown to the person on the step card, and handed to a
    model that can see through the same channel an attached photo uses (which
    is also the channel the egress gate classes as a picture, so a cloud model
    is asked about pictures exactly as it is for a photo). In the text, the
    block becomes a line saying a picture came back.

    Audio has nowhere useful to go yet, so it becomes a line too. Anything that
    is not a known picture type, or is too large, is described rather than
    written. The server's own object is copied, never edited.
    """
    saved: List[str] = []
    target = folder or pictures_dir()

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            kind = node.get("type")
            data = node.get("data")
            if kind in ("image", "audio") and isinstance(data, str):
                size_kb = max(1, len(data) * 3 // 4 // 1024)
                if kind == "image":
                    path = _save_picture(data, str(node.get("mimeType") or ""), target)
                    if path is not None:
                        saved.append(str(path))
                        return {"type": "text", "text": f"[a picture came back with this result ({size_kb} KB): {path.name}]"}
                return {"type": "text", "text": f"[a {kind} of about {size_kb} KB came back with this result and was not kept]"}
            return {key: walk(value) for key, value in node.items()}
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    return walk(result), saved


def _save_picture(data: str, mime: str, folder: Path) -> Optional[Path]:
    """Write one base64 picture, or ``None`` if it is not one Zaram will keep."""
    import base64
    import binascii
    import uuid

    suffix = PICTURE_TYPES.get(mime.lower())
    if suffix is None or len(data) * 3 // 4 > PICTURE_MAX_BYTES:
        return None
    try:
        raw = base64.b64decode(data, validate=False)
    except (binascii.Error, ValueError):
        return None
    try:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}{suffix}"
        path.write_bytes(raw)
        _prune_pictures(folder)
        return path
    except OSError:
        logger.exception("could not keep a tool's picture")
        return None


def _prune_pictures(folder: Path) -> None:
    """Keep the newest `PICTURES_KEPT`; the rest go."""
    pictures = sorted(
        (p for p in folder.iterdir() if p.suffix in PICTURE_TYPES.values()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in pictures[PICTURES_KEPT:]:
        try:
            old.unlink()
        except OSError:
            pass

#: How many tool schemas may be put in front of a model at once.
#:
#: Measured rather than chosen: one filesystem server offers 14, and the local
#: 14B answered correctly with all 14 in context — so the cap is not about
#: correctness, it is about what is left for recall. Eight is roughly two
#: servers' worth of the useful ones, and it is a starting number to be
#: re-measured, not a constant anybody proved.
#:
#: `ZARAM_TOOL_BUDGET` overrides it, because a number nobody can vary is a
#: number nobody will re-measure. A server with 39 tools — Comfy Org's
#: `comfy-mcp` is one — is entirely invisible to the model at eight, and
#: whether raising it costs more in recall than it buys in reach is a
#: measurement somebody has to be able to take on their own machine.
#: Nonsense is ignored rather than crashing a boot over an env var.
def _budget_from_environment(default: int = 8) -> int:
    raw = os.getenv("ZARAM_TOOL_BUDGET", "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("ZARAM_TOOL_BUDGET=%r is not a number; using %d", raw, default)
        return default
    if value < 1:
        logger.warning("ZARAM_TOOL_BUDGET=%d is below one; using %d", value, default)
        return default
    return value


DEFAULT_TOOL_BUDGET = _budget_from_environment()


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
        #: What the last shortlist actually contained, by server id, and how
        #: many tools that server offers. Written by `available_tools`, read by
        #: `health_check`, and *only* a report — nothing routes on it.
        #:
        #: Two numbers rather than one because either alone misleads. A count
        #: of 39 says nothing about whether any were used; a count of 0 offered
        #: looks like a broken server rather than a full budget. Together they
        #: are the sentence somebody needs: "39 tools, 0 offered".
        #:
        #: Empty until a question has been asked. That is honest — before the
        #: first turn nothing has been shortlisted, and inventing a prediction
        #: of what *would* be offered is a number nobody measured.
        self._tool_counts: Dict[str, int] = {}
        self._last_offered: Dict[str, int] = {}
        #: Servers Zaram ships, by id. See `register_builtin`.
        self._builtin: Dict[str, Any] = {}
        #: Injected. See `set_ranker`.
        self._rank: Optional[Callable[[str, Sequence[ToolDescriptor], int], List[ToolDescriptor]]] = None
        #: session_id → qualified tool names allowed **for that conversation
        #: only**. The middle rung of *once · this conversation · always*
        #: (coworker step 3, `docs/PLAN.md` G4): a person who says yes to
        #: `write_file` for the task in hand has not said yes forever, and
        #: making them choose between one call and forever is what pushes
        #: people to "always". In memory by design — a restart ends every
        #: conversation, so the empty dict is correct, not a loss. Never
        #: covers a destructive tool or a floor: `decide` and `floor_for`
        #: run the same whichever rung the grant came from.
        self._session_grants: Dict[str, Set[str]] = {}

    def allow_for_session(self, session_id: str, server_id: str, tool_name: str) -> Set[str]:
        """Remember that the person allowed one tool for one conversation."""
        qualified = f"{server_id}/{tool_name}"
        allowed = self._session_grants.setdefault(session_id, set())
        allowed.add(qualified)
        return set(allowed)

    def _session_granted(self, session_id: str, server_id: str) -> Set[str]:
        prefix = f"{server_id}/"
        return {
            name[len(prefix):]
            for name in self._session_grants.get(session_id, set())
            if name.startswith(prefix)
        }

    def _grant_scope(self, server_id: str, tool_name: str) -> str:
        """Which project switch covers this tool, asked of the server.

        Read off the built-in rather than guessed from the name here, for
        the reason `grantable` is: this runtime has already been bitten
        once by a second opinion about what a tool is — `open_in_browser`
        read as read-only because its name contains `_browse`.
        """
        scope = getattr(self._builtin_server(server_id), "grant_scope", None)
        if not callable(scope):
            return ""
        try:
            return str(scope(tool_name) or "")
        except Exception:  # noqa: BLE001 - a hint must never fail a verdict
            return ""

    def register_builtin(self, config: ServerConfig, server: Any) -> None:
        """Attach a server Zaram ships, in process.

        A pack's tools are MCP tools — `CLAUDE.md` says MCP is *the* tool
        protocol and that no shim format may be invented — so they arrive here
        rather than through a second mechanism, and inherit the policy gate,
        the confirm-once flow, the injection scan and the log by doing so.

        **Its config is not written to `mcp-servers.json`.** That file is the
        user's list of servers *they* attached, and a built-in appearing in it
        could be deleted, would come back on the next launch, and would make
        the file disagree with the product. So the config lives here and
        `_configs` merges the two views wherever one is needed.

        In process rather than as a subprocess: a server Zaram ships needs no
        isolation from Zaram, and spawning a child to talk to yourself buys a
        process, a packaging entry point and a class of startup failure for
        nothing.
        """
        self._builtin[config.server_id] = config
        self._connections[config.server_id] = server

    def _configs(self) -> Dict[str, ServerConfig]:
        """Every server this runtime knows: the user's, then Zaram's.

        Built-ins last so that a user who attaches a server under the same name
        keeps their own — their machine, their choice, and silently preferring
        ours would be the more surprising of the two.
        """
        merged: Dict[str, ServerConfig] = dict(self._builtin)
        merged.update(self._store.load())
        return merged

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
        servers_info = {}
        for name, cfg in configured.items():
            server_info = {
                "transport": cfg.transport,
                "reachable": cfg.reachable,
                "reason": "" if cfg.reachable else "http transport is not implemented yet",
                "writes": cfg.writes.value,
                "connected": name in self._connections,
                "tools": self._tool_counts.get(name),
                "offered": self._last_offered.get(name),
                "builtin": name in self._builtin,
            }
            # Add cua-driver specific health info
            if "cua" in name.lower() or "cua-driver" in name.lower():
                server_info["cua_health"] = await self._check_cua_driver_health(name)
            servers_info[name] = server_info

        return {
            "status": "healthy" if self._state == RuntimeState.READY else "degraded",
            "runtime_id": RUNTIME_ID,
            "calls": self._calls,
            "tool_budget": self._budget,
            "servers": servers_info,
        }

    def disconnect(self, server_id: str) -> None:
        """Stop a server's process if Zaram started one. Its configuration is untouched."""
        if server_id in self._builtin:
            return  # a built-in lives in this process; it is hidden, never stopped
        server = self._connections.pop(server_id, None)
        if server is not None:
            try:
                server.close()
            except Exception:  # noqa: BLE001 - stopping must never fail the caller
                logger.warning("could not stop %s cleanly", server_id)

    async def _check_cua_driver_health(self, server_id: str) -> Dict[str, Any]:
        """Check cua-driver health via its built-in tools."""
        cfg = self._configs().get(server_id)
        if cfg is not None and not cfg.enabled:
            return {"status": "off", "detail": "Switched off in Settings. Nothing is running."}
        server = self._connections.get(server_id)
        if server is None:
            # Try to connect first
            cfg = self._configs().get(server_id)
            if cfg and cfg.reachable:
                server = await self._connect(cfg)
        if server is None:
            return {"status": "not_connected", "reason": "Server not connected"}

        # Read off `health_report`'s structured result, measured against cua-driver
        # 0.34.1 on 10 October 2026: `overall` is "ok" when it can act, and each check
        # carries a `status` of pass/skip/fail. The first version asked
        # `perms.get("accessibility")` of the *raw* MCP result -- a key that is never
        # there, on any platform -- so a working driver always read as "permissions
        # needed (macOS)", on Windows too.
        health: Dict[str, Any] = {"status": "unknown"}
        try:
            report = await asyncio.to_thread(server.call_tool, "health_report", {})
            structured = (report or {}).get("structuredContent") or {}
            checks = structured.get("checks") or []
            failing = [c for c in checks if isinstance(c, dict) and c.get("status") == "fail"]
            permission_failures = [c for c in failing if str(c.get("name", "")).startswith("tcc_")]
            health["platform"] = structured.get("platform")
            health["version"] = structured.get("driver_version")
            if structured.get("overall") == "ok" and not failing:
                health["status"] = "healthy"
            elif permission_failures:
                health["status"] = "permissions_needed"
                health["detail"] = "; ".join(str(c.get("message", "")) for c in permission_failures)
            elif failing:
                health["status"] = "error"
                health["error"] = "; ".join(str(c.get("message", c.get("name", ""))) for c in failing)
            else:
                health["status"] = "error"
                health["error"] = f"the driver reported {structured.get('overall')!r} and no reason"
        except Exception as e:
            health["status"] = "error"
            health["error"] = str(e)
        return health

    # ------------------------------------------------------------ connection

    async def _connect(self, cfg: ServerConfig) -> Optional[McpServer]:
        # A built-in is already in `_connections`, put there by
        # `register_builtin`, so it is returned here before the `reachable`
        # check below — which asks whether a *subprocess* can be launched and
        # is meaningless for a server running in this one.
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
        for cfg in self._configs().values():
            if not cfg.enabled:
                # Switched off in Settings: not listed, not connected, and a
                # process left over from before it was switched off is stopped.
                self.disconnect(cfg.server_id)
                continue
            server = await self._connect(cfg)
            if server is None:
                continue
            # A built-in may offer fewer tools *for this request* than it can
            # list: the code pack has nothing to read, edit or run until a
            # project is open, and offering fourteen tools that can only answer
            # "no project is open" costs prompt tokens on every turn and invites
            # the model to call them. Measured 4 October 2026: asked for a CSS
            # animation with no project open, the resident model opened with
            # `list_files` and then told the user it had checked for an open
            # project. A stranger's server has no such hook and is listed whole.
            lister = getattr(server, "tools_for_request", None)
            if not callable(lister) or cfg.server_id not in self._builtin:
                lister = server.list_tools
            try:
                found.extend(await asyncio.to_thread(lister))
            except Exception as exc:  # noqa: BLE001
                logger.warning("could not list tools on %s: %s", cfg.server_id, exc)

        # **The budget is for strangers' servers, not Zaram's own.** It exists
        # so a server with two hundred tools cannot fill a local model's
        # window; the pack Zaram ships is curated to fit, and every one of its
        # tools is a step of the loop — dropping `write_file` because the
        # ranker judged `look_at_app` closer to the question breaks the task
        # rather than trimming the prompt. Found on 13 September when the
        # pack reached fourteen tools and the interface said "7 attached".
        ours = [t for t in found if t.server_id in self._builtin]
        theirs = [t for t in found if t.server_id not in self._builtin]

        # **What the person pinned goes in first, and is never ranked.**
        # Attaching a server with 39 tools — Comfy Org's `comfy-mcp` is
        # one — put 8 in front of the model and dropped 31 silently, so
        # the model truthfully reported that it could not do the thing
        # while the server sat there healthy. `CLAUDE.md` says a disabled
        # capability is visible rather than silent, and the numbers below
        # are how the interface says it; this is the other half, because a
        # product that reports *"31 tools omitted"* and offers no way to
        # choose which is a complaint rather than a control.
        #
        # A pin is a **membership** decision, and the only one allowed to
        # be one. The rule it must not break is that a *score* may order
        # candidates and may never decide what is in the running — this
        # codebase has paid for that error three times. A pin is not a
        # score: it is the user naming a tool, the same kind of act as
        # granting one. And it widens nothing, because being visible to
        # the model is not being permitted; the gate runs afterwards on
        # whatever was actually chosen.
        pinned_names = {
            f"{cfg.server_id}:{name}"
            for cfg in self._configs().values()
            for name in cfg.pinned_tools
        }
        pinned = [t for t in theirs if t.qualified_name in pinned_names]
        rest = [t for t in theirs if t.qualified_name not in pinned_names]

        # The budget is what is left after the pins. Pinning more than the
        # budget is the person's call and is honoured — they named each
        # one, which is a stronger signal than a cap chosen by
        # measurement, and `max(0, …)` means the ranker is simply asked
        # for nothing rather than for a negative number.
        #
        # **Pins are paid for by the server they belong to -- 10 October 2026.**
        # The budget left after pins used to be shared by every server, so one
        # server with many pins starved all the others: the maintainer's Blender
        # server has 28 pinned tools against a budget of 8, and while it was
        # reachable cua-driver's tools could never reach the model whatever was
        # asked -- installed, connected, healthy and silently absent, which is the
        # failure this block exists to prevent. Servers with pins share what is
        # left of the budget among their own other tools; servers without pins are
        # ranked against the whole budget, exactly as when nobody pins anything.
        pinned_servers = {t.server_id for t in pinned}
        rest_of_pinned = [t for t in rest if t.server_id in pinned_servers]
        rest_of_others = [t for t in rest if t.server_id not in pinned_servers]
        room = max(0, self._budget - len(pinned))

        # An empty query means "the same set as last time": the listing order
        # cut to the budget, with no ranking to move it. The engine asks this
        # way on every turn that is not about tools, so the tool rules are the
        # same bytes each turn and stay in the server's prompt cache
        # (`docs/PLAN.md` A3).
        def pick(candidates: List[ToolDescriptor], space: int) -> List[ToolDescriptor]:
            if not candidates or not space:
                return []
            if self._rank and query.strip():
                return self._rank(query, candidates, space)
            return candidates[:space]

        chosen = pick(rest_of_others, self._budget) + pick(rest_of_pinned, room)
        shortlisted = ours + pinned + chosen

        # Recorded here rather than computed later, because *here* is the only
        # place both numbers are known at once: `found` is everything the
        # servers offered and `shortlisted` is what survived the budget. A
        # later reconstruction would have to re-list the tools and could
        # disagree with what was actually sent.
        self._tool_counts = {}
        for tool in found:
            self._tool_counts[tool.server_id] = self._tool_counts.get(tool.server_id, 0) + 1
        self._last_offered = {name: 0 for name in self._tool_counts}
        for tool in shortlisted:
            self._last_offered[tool.server_id] = self._last_offered.get(tool.server_id, 0) + 1

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

    async def tools_on(self, server_id: str) -> List[Dict[str, Any]]:
        """Every tool one server offers, by name — not the shortlist.

        Needed because the budget's remedy is for a person to say *which* 31
        of 39 they could do without, and they cannot choose from a count.
        `available_tools` answers a different question — what goes in front of
        the model for this request — and reusing it here would hand back the
        eight that already fit, which is the set the person is trying to
        change.

        Unranked and uncut, deliberately. This is a list to read, not a
        prompt, so the budget has no business in it.

        The name and description are **third-party text** and are carried
        marked, exactly as `available_tools` carries them: whoever wrote the
        server wrote these words, and a scan finding travels with them rather
        than the text being dropped.
        """
        cfg = self._configs().get(server_id)
        if cfg is None:
            return []
        server = await self._connect(cfg)
        if server is None:
            return []
        try:
            found = await asyncio.to_thread(server.list_tools)
        except Exception as exc:  # noqa: BLE001 - a listing must not 500
            logger.warning("could not list tools on %s: %s", server_id, exc)
            return []
        return [
            {
                "name": tool.name,
                "qualified_name": tool.qualified_name,
                "description": tool.description,
                "suspicions": [s.value for s in scan(f"{tool.name} {tool.description}")],
            }
            for tool in found
        ]

    # ------------------------------------------------------------------ call

    async def execute(self, capability_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if capability_id == LIST_TOOLS:
            query = str(input_data.get("query") or "")
            return {
                "success": True,
                "tools": await self.available_tools(query),
                "briefing": self._briefing(query),
            }
        if capability_id != CALL:
            return {"success": False, "error": f"unknown capability {capability_id}"}

        server_id = str(input_data.get("server") or "")
        tool_name = str(input_data.get("tool") or "")
        arguments = input_data.get("arguments") or {}
        # Set only by a surface that has actually asked the user. Never by the
        # model, and never inferred from the request.
        confirmed = bool(input_data.get("confirmed"))

        cfg = self._configs().get(server_id)
        if cfg is None:
            return {"success": False, "error": f"no server called {server_id!r} is configured"}
        if not cfg.enabled:
            # Before the floors and the gate: a server that is off does nothing at
            # all, whatever has been granted, and says why.
            return {
                "success": False,
                "refused": True,
                "reason": f"{server_id} is switched off in Settings, so Zaram did not run {tool_name}.",
            }

        # **The floors, before the gate.** Argument-aware and one-directional:
        # a write to a file that governs Zaram is refused under any grant,
        # and a write to a file that runs later asks whatever has been
        # granted — a grant is consent to a *tool*, made in advance, never to
        # this file. Only `confirmed`, the person's Go on this run, covers it,
        # and the row cannot offer a grant. `runtimes/mcp/floors.py`.
        root = self._root_of(server_id)
        under = floor_for(server_id, tool_name, arguments, root)
        if under is not None and under.verdict == "refuse":
            return {"success": False, "refused": True, "reason": under.reason}

        session_id = str(input_data.get("session") or "")
        decision = decide(
            server_id=server_id,
            tool_name=tool_name,
            mode=self._effective_mode(server_id, tool_name, cfg),
            granted_tools=(
                cfg.granted_tools
                | self._builtin_grants(server_id)
                | self._session_granted(session_id, server_id)
            ),
            annotations=input_data.get("annotations"),
            not_read_only=self._builtin_says_not_read_only(server_id, tool_name),
        )

        if decision.verdict is Verdict.REFUSE:
            return {"success": False, "refused": True, "reason": decision.reason}

        if under is not None and under.verdict == "confirm" and not confirmed:
            return {
                "success": False,
                "needs_confirmation": True,
                "server": server_id,
                "tool": tool_name,
                "reason": under.reason,
                "grantable": False,
                # A floor asks about *this call*, so a yes for this call is the
                # one answer that settles it. Offered by the engine only when
                # the card can show what the call is aimed at.
                "once": True,
            }

        if decision.verdict is Verdict.CONFIRM and not confirmed:
            # Returned rather than asked. This runtime has no user; the surface
            # that does gets the question and comes back with `confirmed`.
            reason = decision.reason
            hint = getattr(self._builtin_server(server_id), "how_to_permit", "")
            if callable(hint):
                try:
                    hint = hint(tool_name)
                except Exception:  # noqa: BLE001 - a hint must never fail a verdict
                    hint = ""
            if hint:
                reason = f"{reason} {hint}"
            return {
                "success": False,
                "needs_confirmation": True,
                "server": server_id,
                "tool": tool_name,
                "reason": reason,
                # Whether a grant would settle it. A destructive tool keeps
                # asking whatever is granted (`decide`), so offering to allow
                # it would promise something the gate will not honour.
                "grantable": not (
                    looks_destructive(tool_name, input_data.get("annotations"))
                    or looks_outbound(tool_name)
                    or always_asks(server_id, tool_name)
                ),
                # Which of the open project's switches covers this tool, so
                # the permission card can offer *for this project* as a
                # press. Empty for a server that has no opinion — an
                # attached MCP server is not inside anybody's project, and
                # a card offering a project grant that settles nothing is
                # the button-that-changes-nothing this file already
                # refuses elsewhere.
                "grant_scope": self._grant_scope(server_id, tool_name),
                # Whether Zaram ships this server. A built-in is never in the
                # store, so a standing "always" cannot be kept for it (the grant
                # route answers 409); the card reads this rather than guessing
                # from a name, and does not offer the button.
                "builtin": server_id in self._builtin,
                # Whether a yes for this one call may be offered. Not for a
                # send: the card shows where a message goes and not what it
                # says, and a send stays a draft until the person sends it.
                "once": not looks_outbound(tool_name),
            }

        server = await self._connect(cfg)
        if server is None:
            return {"success": False, "error": f"could not attach {server_id}"}

        try:
            result = await asyncio.to_thread(server.call_tool, tool_name, arguments)
            # **An async built-in returns a coroutine from that thread, not an
            # answer.** Found 10 October 2026: `zaram-self` -- the tools that
            # change Zaram's own settings -- is async, and every call it has
            # ever received came back `success: True` carrying an unawaited
            # coroutine. Nothing was changed, the model was told it had been,
            # and no test went through the runtime to see it.
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"{tool_name} failed: {exc}"}

        self._calls += 1
        result, pictures = await asyncio.to_thread(keep_media, result)
        return {
            "success": True,
            "result": result,
            # Paths in Zaram's own picture folder, for the step card and for a
            # model that can see. See `keep_media`.
            "images": pictures,
            # Carried so nothing downstream mistakes a server's output for
            # something Zaram said.
            "provenance": Provenance.TOOL_OUTPUT.value,
        }

    def _root_of(self, server_id: str) -> Optional[Path]:
        """The project folder a built-in resolves relative paths against, or
        ``None``. A stranger's server has no root Zaram knows."""
        report = getattr(self._builtin_server(server_id), "root", None)
        if not callable(report):
            return None
        try:
            root = report()
        except Exception:  # noqa: BLE001 - a root lookup must never fail a call
            return None
        return Path(root) if root else None

    def _builtin_server(self, server_id: str) -> Any:
        """The in-process object behind a server Zaram ships, or ``None``.

        Only built-ins: a stranger's server is a subprocess behind `McpClient`
        and is never asked anything about permission.
        """
        if server_id not in self._builtin:
            return None
        return self._connections.get(server_id)

    def _briefing(self, query: str) -> str:
        """What Zaram's own servers want said before the tools are listed.

        Today that is the code pack's repository map. Only built-ins are asked:
        a stranger's server does not get to write into the system prompt, and
        even a built-in's briefing is placed *before* the tool rules so the
        last instruction the model reads is still Zaram's.
        """
        parts: List[str] = []
        # Zaram's own sentence about a desktop it has been told not to touch, so a
        # request to act on the screen is answered "computer use is switched off"
        # rather than with a model that quietly has no tools and improvises.
        # CLAUDE.md: a disabled capability is visible, not silent.
        desktops = [cfg for cfg in self._store.load().values() if "cua" in cfg.server_id.lower()]
        off = [cfg.server_id for cfg in desktops if not cfg.enabled]
        # The other half, found 10 October 2026: with it on, nothing said what it
        # was for, and a model asked to "open google.com in your browser" did so
        # and then replied "I can't browse the web myself -- I don't have a
        # browser of my own", having just driven the person's. It also said the
        # page was loading without looking. Zaram's own sentence, so it carries
        # no tool description and widens nothing; the gate still judges each call.
        if any(cfg.enabled for cfg in desktops) and not off:
            parts.append(
                "Computer use is on: you can work the person's own desktop with the desktop tools "
                "listed below, and that includes the web browser they already have. To open a page, "
                "open its address with the tool that launches apps; do not say you cannot browse or "
                "have no browser of your own, because you are driving theirs. After opening or "
                "acting, look before you say what happened: list the windows or read the window, "
                "then report what you saw rather than what you expect. Looking costs nothing and "
                "needs no permission, so do it instead of offering to.\n\n"
            )
        if off:
            parts.append(
                "Computer use (controlling the desktop) is switched off in Settings -> Computer Use. "
                "If you are asked to click, type, open an app or look at the screen, say that it is "
                "switched off and where to turn it on; do not claim to have done it.\n\n"
            )
        for server_id in self._builtin:
            report = getattr(self._connections.get(server_id), "briefing", None)
            if not callable(report):
                continue
            try:
                text = report(query)
            except Exception:  # noqa: BLE001 - a briefing must never fail a listing
                logger.exception("built-in %s could not brief", server_id)
                continue
            if text:
                parts.append(str(text))
        return "".join(parts)

    def _effective_mode(self, server_id: str, tool_name: str, cfg: ServerConfig) -> WriteMode:
        """The write mode this one call is judged under.

        **A built-in's own grant has to count under a read-only server.** Found
        4 October 2026 by sending the resident model "Draw a minimalist fox logo
        as an SVG": it called `draw_image` and was told *"this server is read-only
        because nothing here can undo it"*. `DrawTools.granted_tools` names
        `draw_image`; the server was registered with the default mode, which is
        `READ_ONLY`; and `decide` refuses a read-only server's write *before* it
        reads the grants. So a tool its own server declared granted was refused
        every time -- and so were `record_job_posting` and `check_eligibility`,
        which shipped in alpha.3 and which the model has never been able to call.
        A complete, tested, unreachable subsystem, three times over, and nothing
        found it because no test went through the policy.

        `READ_ONLY` says a stranger's server has no undo, and that is true of a
        stranger. It says nothing about Zaram's own generative tools, which create
        a new artifact or a fact and destroy nothing -- the tier the tier table
        asks nothing of. The server declaring a tool granted *is* that statement,
        made by Zaram's own code and not by a tool description, so it is honoured
        here and only here.

        Narrow in both directions. Only a built-in, and only for a tool that
        server itself reports granted. And `GRANTED` is not a free pass:
        `decide` still confirms a destructive tool and a send however this
        answers, so nothing a built-in grants can delete or transmit unasked.
        """
        if (
            cfg.writes is WriteMode.READ_ONLY
            and server_id in self._builtin
            and tool_name in self._builtin_grants(server_id)
        ):
            return WriteMode.GRANTED
        return cfg.writes

    def _builtin_says_not_read_only(self, server_id: str, tool_name: str) -> bool:
        """Let a built-in say a tool is not read-only, whatever it is called.

        `looks_read_only` is a substring guess over a word list, and its own
        comment says why: *"a server author picks the names"*. On 3 October
        2026 that fired on **Zaram's own** name. `open_in_browser` contains
        `_browser`, which contains `_browse`, which is in the read-only
        list — so launching a browser process read as looking at something
        and ran under no grant at all. Not a hypothetical: the call was
        made against a real dev server with every grant off, and a Chrome
        started.

        Asked of the server object, the same way `_builtin_grants` is and
        for the same reason: it is Zaram's own code rather than a
        stranger's, and it narrows rather than widens.

        **Not read-only is not the same as destructive**, and the first
        attempt at this conflated them. `readOnlyHint: False` was the
        obvious route — `decide` already believes it, in the strict
        direction only — but `_annotation_says_destructive` reads that
        same hint, so every driving tool became destructive and asked on
        every call however much had been granted. That is rule 7j's forty
        dialogs a day, which is the product nobody opens twice. So this
        suppresses the name guess and nothing else: the grant still
        applies, and a tool the person allowed stops asking.

        One-directional, like everything else on this path. A built-in may
        only move a tool from "runs freely" to "needs the grant". It
        cannot declare a tool read-only, so a mistake here cannot widen
        anything, and a server that answers nothing leaves the guess
        exactly as it was.
        """
        server = self._builtin_server(server_id)
        report = getattr(server, "mutative_tools", None)
        if not callable(report):
            return False
        try:
            return tool_name in {str(name) for name in report()}
        except Exception:  # noqa: BLE001 - must fail towards asking
            return True

    def _builtin_grants(self, server_id: str) -> Set[str]:
        """Tools a built-in reports as granted for the request in flight.

        `granted_tools` in `mcp-servers.json` holds consent for the servers the
        user attached; a built-in is never in that file, so its grant has to
        come from somewhere else — for the code pack, from the open project.
        Asked of the server object because it is Zaram's own code, not a
        stranger's, and it *narrows nothing*: the policy still runs, and a
        destructive tool still confirms however this answers.
        """
        server = self._builtin_server(server_id)
        report = getattr(server, "granted_tools", None)
        if not callable(report):
            return set()
        try:
            return {str(name) for name in report()}
        except Exception:  # noqa: BLE001 - a grant lookup must fail closed
            return set()

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

"""HTTP surface for the MCP servers this machine has.

The client has been live since 1 September 2026 -- ``core/bootstrapper.py``
builds it, ``core/planner.py`` can name ``mcp.call``, and
``core/execution_engine.py`` runs it. What it never had is a way in: attaching
a server meant hand-editing ``mcp-servers.json`` in the data directory. A
subsystem nobody can reach is the failure this repository keeps recording, and
a config file is only marginally better than unreachable.

Everything here operates on :class:`~runtimes.mcp.config.ServerStore` rather
than on the live runtime, deliberately. The store is the record of what the
user has decided; the runtime is a set of processes that connect on first use.
Listing what is configured has to work while nothing is connected, and opening
Settings must not start a stranger's subprocess as a side effect.

Why a pasted ``writes`` is dropped
----------------------------------
:meth:`ServerConfig.from_json` honours a declared ``writes`` mode, which is
right for a file the user edited themselves and wrong for a block arriving over
HTTP. Config blocks are meant to travel -- that is the entire reason the format
matches ``.mcp.json`` -- so a block pasted from a forum, a README or a stranger
can carry ``"writes": "host_undo"`` and grant itself permission to change
things.

``CLAUDE.md``: *a tool description is third-party text and never widens
permission*. That applies with more force to a config block, because it arrives
before any description does. So the field is **stripped on the way in** and the
mode is decided here by ``known_host_reason`` -- the maintainer's own checked
list -- exactly as ``from_json`` does for a block that omits it. A server nobody
has vouched for starts ``READ_ONLY``, and the user raises it deliberately
afterwards.

Stripping rather than rejecting is the kinder half: a pasted block that happens
to carry the field still attaches, it simply does not get to keep it.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .config import ServerConfig, ServerStore, known_host_reason

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["tools"])

#: Server ids become keys in ``mcp-servers.json`` and labels in the interface.
#: Constrained so a paste cannot introduce a name that is awkward to display or
#: to address in a URL. Not a security boundary -- the store writes one file
#: whose path is fixed -- but a server nobody can name is one nobody can revoke.
_SERVER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

#: Fields a pasted block may not decide for itself. ``writes`` is permission and
#: ``grantedTools`` is consent already given; both belong to the user, not to
#: whoever wrote the block.
_NOT_THEIRS_TO_DECLARE = ("writes", "grantedTools")

_MCP_RUNTIME: Optional[Any] = None


def set_mcp_runtime(runtime: Any) -> None:
    """Attach the live runtime, for the one endpoint that genuinely needs it.

    The store-backed endpoints below do not, and must keep working before this
    is called: the interface has to show what is configured while the kernel is
    still starting.
    """
    global _MCP_RUNTIME
    _MCP_RUNTIME = runtime


def _store() -> ServerStore:
    return ServerStore()


def _describe(cfg: ServerConfig) -> Dict[str, Any]:
    """One server, as the interface needs to render it.

    ``reachable`` is carried rather than inferred from ``transport`` so the
    surface can say *why* an http server shows no tools, instead of rendering an
    empty list that reads as a broken server.

    ``tools``, ``offered`` and ``pinnedTools`` are the same distinction one
    layer out. The runtime has recorded how many tools each server offers and
    how many survived the context budget since 20 September, on
    ``/tools/health`` — and **nothing in the interface has ever called it**, so
    a server with 39 tools showed 8 and said nothing about the other 31. The
    model then truthfully reported it could not do the thing while the server
    sat there healthy. `CLAUDE.md`: *a disabled capability is visible, not
    silent.* Carried here rather than left on a second endpoint because the
    surface that renders the server is the surface that has to say it.

    ``None`` for the counts before anything has been asked — not 0, because
    *"nothing has happened yet"* and *"this server was shut out"* are different
    answers and the interface must not show one as the other. The same
    distinction ``vram_bytes`` draws by returning ``None`` rather than zero.
    """
    counts = _counts_for(cfg.server_id)
    return {
        "id": cfg.server_id,
        "command": list(cfg.command),
        "url": cfg.url,
        "transport": cfg.transport,
        "reachable": cfg.reachable,
        "writes": cfg.writes.value,
        "grantedTools": sorted(cfg.granted_tools),
        # Present when the command matched the maintainer's checked list. It is
        # the sentence to show beside a server that may write, because "why is
        # this one allowed to change things" is the question a person has.
        "knownHost": known_host_reason(cfg.command),
        # How many this server offers, and how many reached the model last
        # time. When `offered` is below `tools`, the difference is what the
        # context budget dropped.
        "tools": counts[0],
        "offered": counts[1],
        # The budget those two are measured against, so the sentence the
        # interface writes can name the number rather than being vague.
        "toolBudget": counts[2],
        # Zaram's own packs are never trimmed — the budget exists for
        # strangers. Said here so the interface does not warn about a built-in
        # that was always going to be complete.
        "builtin": counts[3],
        # Which tools the person chose to keep in front of the model whatever
        # the budget would otherwise do. A pin is visibility, never
        # permission: `grantedTools` above is the separate answer to what a
        # tool may *do*.
        "pinnedTools": sorted(cfg.pinned_tools),
    }


def _counts_for(server_id: str) -> tuple:
    """`(offered by the server, reached the model, the budget, is a built-in)`.

    All four from the live runtime, which is the only place they are known at
    once. Before the kernel is up there is no runtime and every one is
    ``None`` — the store-backed endpoints must keep working while the backend
    is still starting, and a count invented here would be exactly the
    *"status indicator over hardcoded data"* `CLAUDE.md` calls worse than no
    indicator.
    """
    if _MCP_RUNTIME is None:
        return (None, None, None, False)
    try:
        return (
            _MCP_RUNTIME._tool_counts.get(server_id),
            _MCP_RUNTIME._last_offered.get(server_id),
            _MCP_RUNTIME._budget,
            server_id in _MCP_RUNTIME._builtin,
        )
    except Exception:  # noqa: BLE001 - a count must never fail the listing
        return (None, None, None, False)


class AttachRequest(BaseModel):
    """An ``.mcp.json``-shaped block, as pasted.

    ``mcpServers`` mirrors the file every other client already uses, so a server
    working elsewhere can be pasted rather than retyped into a form.
    """

    servers: Dict[str, Dict[str, Any]] = Field(..., alias="mcpServers")

    model_config = {"populate_by_name": True}


class GrantRequest(BaseModel):
    tool: str


class SessionGrantRequest(BaseModel):
    tool: str
    #: The conversation this covers — the chat request's `session_id`.
    session_id: str


@router.get("/servers")
async def list_servers() -> Dict[str, Any]:
    """Every configured server, connected or not."""
    configured = _store().load()
    return {"servers": [_describe(cfg) for _, cfg in sorted(configured.items())]}


@router.post("/servers", status_code=201)
async def attach_servers(request: AttachRequest) -> Dict[str, Any]:
    """Add one or more servers from a pasted config block.

    An existing id is replaced, which is what re-pasting a corrected block
    means. The replaced entry's grants do not survive it: a changed command is a
    different program, and carrying consent across that would let an edit
    inherit permission given for something else.
    """
    if not request.servers:
        raise HTTPException(status_code=400, detail="no servers in the block")

    store = _store()
    configured = store.load()
    added: List[str] = []

    for server_id, spec in request.servers.items():
        if not _SERVER_ID.match(server_id):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"server name {server_id!r} may use letters, digits, "
                    "dot, dash and underscore"
                ),
            )
        if not isinstance(spec, dict):
            raise HTTPException(status_code=400, detail=f"{server_id}: entry is not an object")
        if not spec.get("command") and not spec.get("url"):
            raise HTTPException(
                status_code=400,
                detail=f"{server_id}: needs a command (stdio) or a url (http)",
            )

        # The line this module exists for. See the docstring: a mode declared
        # over HTTP is a stranger's claim about its own permissions, and
        # `from_json` would honour it.
        sanitised = {k: v for k, v in spec.items() if k not in _NOT_THEIRS_TO_DECLARE}
        cfg = ServerConfig.from_json(server_id, sanitised)
        configured[server_id] = cfg
        added.append(server_id)
        logger.info(
            "MCP server %s attached (%s, writes=%s)",
            server_id,
            cfg.transport,
            cfg.writes.value,
        )

    store.save(configured)
    return {"attached": added, "servers": [_describe(configured[i]) for i in added]}


@router.delete("/servers/{server_id}")
async def detach_server(server_id: str) -> Dict[str, Any]:
    """Remove a server, and every grant made to it."""
    store = _store()
    configured = store.load()
    if server_id not in configured:
        raise HTTPException(status_code=404, detail=f"no server named {server_id!r}")
    del configured[server_id]
    store.save(configured)
    logger.info("MCP server %s detached", server_id)
    return {"detached": server_id}


@router.post("/servers/{server_id}/grant")
async def grant_tool(server_id: str, request: GrantRequest) -> Dict[str, Any]:
    """Remember that the user allowed one tool on one server.

    Rule 7j's second half -- confirm once, then remember -- and the reason this
    is persisted rather than held in memory: a grant that does not survive a
    restart asks the same question every launch, which is the dialog-per-call
    product nobody opens twice.
    """
    store = _store()
    configured = store.load()
    if server_id not in configured:
        raise HTTPException(status_code=404, detail=f"no server named {server_id!r}")
    if not request.tool.strip():
        raise HTTPException(status_code=400, detail="tool name is empty")

    store.grant(server_id, request.tool)
    return {"server": server_id, "grantedTools": sorted(store.load()[server_id].granted_tools)}


@router.get("/servers/{server_id}/tools")
async def list_server_tools(server_id: str) -> Dict[str, Any]:
    """Every tool one server offers, so the pin control has names to show.

    Not the shortlist. The person is here precisely because the shortlist is
    smaller than the server, and offering them the eight that already fit
    would be answering a question they did not ask.

    503 while the kernel is starting, for the reason `/health` gives: *"not
    ready yet"* and *"this server offers nothing"* are different answers.
    """
    if _MCP_RUNTIME is None:
        raise HTTPException(status_code=503, detail="tool layer not initialized")
    if server_id not in _store().load():
        raise HTTPException(status_code=404, detail=f"no server called {server_id!r}")
    return {"server": server_id, "tools": await _MCP_RUNTIME.tools_on(server_id)}


class PinRequest(BaseModel):
    """Which of a server's tools always reach the model.

    The whole set, not one name: the control is a list of checkboxes, and
    unticking the last one means *none*, which an add-only endpoint cannot
    say.
    """

    tools: List[str] = Field(default_factory=list)


@router.put("/servers/{server_id}/pins")
async def pin_tools(server_id: str, request: PinRequest) -> Dict[str, Any]:
    """Keep these tools in front of the model, whatever the budget would do.

    **Visibility, never permission.** A pinned tool is gated exactly like any
    other — the risk tier and `grantedTools` decide what it may do, and this
    decides only whether the model gets to see it. Keeping those two apart is
    the whole reason there are two fields: a control that quietly granted what
    it revealed would make the budget a permission surface, which the tier
    table forbids for a different reason.

    It is also the one membership decision a person is allowed to make
    directly. A *score* may order candidates and may never decide what is in
    the running; a pin is not a score, it is somebody naming a tool.
    """
    cfg = _store().pin(server_id, set(request.tools))
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"no server called {server_id!r}")
    return {"server": server_id, "pinnedTools": sorted(cfg.pinned_tools)}


@router.post("/servers/{server_id}/allow-for-session")
async def allow_tool_for_session(server_id: str, request: SessionGrantRequest) -> Dict[str, Any]:
    """Allow one tool for one conversation — the middle rung of *once · this
    conversation · always* (coworker step 3). Nothing is written to disk: a
    restart ends the conversation and the grant with it. A built-in server
    (the code pack) is a valid target here even though it is not in the
    store, because its grants are per request rather than per file."""
    if _MCP_RUNTIME is None:
        raise HTTPException(status_code=503, detail="tool layer not initialized")
    if not request.tool.strip() or not request.session_id.strip():
        raise HTTPException(status_code=400, detail="tool and session_id are required")
    known = set(_store().load()) | set(getattr(_MCP_RUNTIME, "_builtin", {}))
    if server_id not in known:
        raise HTTPException(status_code=404, detail=f"no server named {server_id!r}")
    allowed = _MCP_RUNTIME.allow_for_session(request.session_id, server_id, request.tool.strip())
    return {"server": server_id, "session_id": request.session_id, "allowedForSession": sorted(allowed)}


@router.get("/health")
async def tools_health() -> Dict[str, Any]:
    """What the live runtime reports, when there is one.

    503 rather than an empty result while the kernel is still starting: "not
    ready yet" and "no servers configured" are different answers, and the
    interface must not render one as the other.
    """
    if _MCP_RUNTIME is None:
        raise HTTPException(status_code=503, detail="tool layer not initialized")
    return await _MCP_RUNTIME.health_check()

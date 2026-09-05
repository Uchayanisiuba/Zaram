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
    """
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
    }


class AttachRequest(BaseModel):
    """An ``.mcp.json``-shaped block, as pasted.

    ``mcpServers`` mirrors the file every other client already uses, so a server
    working elsewhere can be pasted rather than retyped into a form.
    """

    servers: Dict[str, Dict[str, Any]] = Field(..., alias="mcpServers")

    model_config = {"populate_by_name": True}


class GrantRequest(BaseModel):
    tool: str


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

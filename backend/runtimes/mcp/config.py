"""Which MCP servers this machine has, and what each is allowed to do.

Same shape as `.mcp.json`, deliberately
---------------------------------------
The file is `{"mcpServers": {name: {command, args, env}}}` — the shape every
other client already uses — so somebody who has a working server elsewhere can
paste the block in rather than retype it into a form. A config format is not a
place to be original, and inventing one would be the plugin-format mistake
`CLAUDE.md` forbids, arriving through the back door.

Zaram's own two fields sit alongside and are ignored by anything else:
`writes`, and `grantedTools`.

Why a curated undo list is first-party knowledge and not a server's word
-----------------------------------------------------------------------
`policy.py` records why a server cannot be believed about itself: the
specification says annotations are untrusted, and untrusted text may never
widen permission. That rules out a server *claiming* undo. It does not rule out
**Zaram knowing** — the same way `CLAUDE.md` ships a dated local manifest of
model recommendations rather than asking a provider to describe itself.

So `KNOWN_HOSTS` is a short, checked list of applications whose undo stack the
maintainer has verified exists: Blender, Unreal and DaVinci Resolve. Matching
one sets the server's **default** to `HOST_UNDO`, which means a first write
asks once instead of being refused outright. It is a starting position, visible
in the file, editable, and revocable — not a grant. Every individual tool still
confirms the first time, because that is the moment the user learns the tool
exists at all.

Anything unrecognised starts `READ_ONLY`. Default deny is rule 5, and a server
nobody has vouched for is exactly the case that must not be given the benefit
of the doubt.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from core.paths import data_dir

from .policy import WriteMode

logger = logging.getLogger(__name__)

#: The file, beside the Spine and the egress log rather than in the source
#: tree — `core/paths` owns the one answer to where the user's data lives.
FILENAME = "mcp-servers.json"

#: Applications with an undo stack of their own, matched against the server's
#: command line. Substrings rather than exact names because these ship under
#: several package names and people rename them.
#:
#: **This is a claim the maintainer is making, not one a server made.** Adding
#: to it means having checked that the application's own undo actually covers
#: what its MCP server does — for Blender and Unreal that means the operation
#: goes through the app's operator/transaction system rather than writing a
#: file behind its back.
KNOWN_HOSTS: Dict[str, str] = {
    "blender": "Blender — its own undo stack covers operator calls",
    "unreal": "Unreal Engine — transactions are undoable in the editor",
    "ue5": "Unreal Engine — transactions are undoable in the editor",
    "davinci": "DaVinci Resolve — the edit page has its own undo history",
    "resolve": "DaVinci Resolve — the edit page has its own undo history",
    "figma": "Figma — every edit lands on the file's own undo history",
}


def known_host_reason(command: List[str]) -> Optional[str]:
    """Why this server is presumed to have undo, or `None` if it is not known.

    Matched on the whole command line: a server is often `npx some-blender-mcp`
    or `python -m blender_mcp`, and the recognisable word is rarely the
    executable.
    """
    haystack = " ".join(command).lower()
    for needle, reason in KNOWN_HOSTS.items():
        if needle in haystack:
            return reason
    return None


@dataclass
class ServerConfig:
    server_id: str
    command: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    #: Present for HTTP servers, which this client cannot yet reach. Kept so
    #: pasting a working config does not silently lose half of it, and so the
    #: interface can say *why* rather than showing nothing.
    url: str = ""
    writes: WriteMode = WriteMode.READ_ONLY
    granted_tools: Set[str] = field(default_factory=set)

    @property
    def transport(self) -> str:
        return "stdio" if self.command else "http"

    @property
    def reachable(self) -> bool:
        """Whether this client can actually attach. HTTP needs a transport
        that does not exist yet; saying so beats an empty tool list."""
        return bool(self.command)

    def to_json(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if self.command:
            out["command"] = self.command[0]
            if len(self.command) > 1:
                out["args"] = self.command[1:]
        if self.url:
            out["url"] = self.url
        if self.env:
            out["env"] = dict(self.env)
        out["writes"] = self.writes.value
        if self.granted_tools:
            out["grantedTools"] = sorted(self.granted_tools)
        return out

    @classmethod
    def from_json(cls, server_id: str, raw: Dict[str, Any]) -> "ServerConfig":
        command: List[str] = []
        if raw.get("command"):
            command = [str(raw["command"]), *[str(a) for a in (raw.get("args") or [])]]

        # An absent `writes` is the interesting case: it is what a block pasted
        # from another client looks like. Recognised hosts start at HOST_UNDO,
        # everything else at READ_ONLY.
        declared = raw.get("writes")
        if declared:
            try:
                writes = WriteMode(str(declared))
            except ValueError:
                logger.warning("unknown writes mode %r for %s; using read_only", declared, server_id)
                writes = WriteMode.READ_ONLY
        elif known_host_reason(command):
            writes = WriteMode.HOST_UNDO
        else:
            writes = WriteMode.READ_ONLY

        return cls(
            server_id=server_id,
            command=command,
            env={str(k): str(v) for k, v in (raw.get("env") or {}).items()},
            url=str(raw.get("url") or ""),
            writes=writes,
            granted_tools=set(raw.get("grantedTools") or []),
        )


class ServerStore:
    """The configured servers, on disk, in the user's own data directory."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else Path(data_dir()) / FILENAME

    def load(self) -> Dict[str, ServerConfig]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            # A corrupt file must not stop the backend booting, and must not
            # silently become an empty one either — the log is how somebody
            # finds out their servers went missing.
            logger.error("could not read %s (%s); no servers configured", self.path, exc)
            return {}

        servers = raw.get("mcpServers")
        if not isinstance(servers, dict):
            return {}
        return {
            name: ServerConfig.from_json(name, spec)
            for name, spec in servers.items()
            if isinstance(spec, dict)
        }

    def save(self, servers: Dict[str, ServerConfig]) -> None:
        payload = {"mcpServers": {name: cfg.to_json() for name, cfg in sorted(servers.items())}}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Written whole and replaced, so an interrupted write cannot leave a
        # half-file that reads as "no servers configured".
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def grant(self, server_id: str, tool_name: str) -> None:
        """Remember that the user allowed this tool. Rule 7j's second half."""
        servers = self.load()
        cfg = servers.get(server_id)
        if cfg is None:
            return
        cfg.granted_tools.add(tool_name)
        self.save(servers)

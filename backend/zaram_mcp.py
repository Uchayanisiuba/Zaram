"""Zaram's Spine as an MCP server, for the other assistants a person uses.

`docs/AGENT-UX.md`, slice 10 — *be the memory they attach*. Claude Code,
Cline and Kilo each keep a memory of their own and none of them is the
user's: it lives in that client, in that client's format, and forgets when
the client is switched. Zaram's memory is on the user's machine, in an open
format, with provenance and a correction loop — so the move is not to
compete with those clients for the conversation but to be the memory every
one of them attaches. This file is what they attach.

**A stdio MCP server in the standard library only**, for the same reason
`runtimes/mcp/client.py` is: the transport is newline-delimited JSON-RPC 2.0
and needs nothing that is not already installed, and packaging is the
product's blocker. Four tools — `recall`, `remember`, `correct`, `projects`
— each one an HTTP call to the Zaram already running on this machine, so
the memory has exactly one implementation and this is a door to it.

**The credential is a paired client's, never the API secret.** Zaram's own
secret is per-launch and IPC-only and this process is neither. The person
issues a token in Settings, runs ``python -m zaram_mcp pair <token> --name
"Claude Code"`` once, and this server holds the credential from then on —
revocable in Settings, hashed at rest on Zaram's side, and with every call
it makes written to the egress log as bytes that left to *that* client.
The credential lives in the attaching client's own configuration
(`ZARAM_CLIENT_CREDENTIAL` in the ``env`` of its `.mcp.json` entry), which
is that client's custody and not Zaram's, and is what "pair once, revoke
any time" means in practice.

Attach it like any other server::

    {"mcpServers": {"zaram": {
        "command": "python", "args": ["-m", "zaram_mcp"],
        "cwd": "<the backend directory>",
        "env": {"ZARAM_CLIENT_CREDENTIAL": "<from pair>"}}}}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

__all__ = ["Spine", "TOOLS", "serve", "main"]

DEFAULT_API = "http://127.0.0.1:8420"
CREDENTIAL_ENV = "ZARAM_CLIENT_CREDENTIAL"
API_ENV = "ZARAM_API"
AUTH_HEADER = "X-Zaram-Auth"
PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "zaram", "version": "0.1"}

#: The four tools, as the attaching client sees them. Descriptions are
#: written for the *model* on the other side, which is why they say when to
#: call and what comes back rather than what the code does.
TOOLS: List[Dict[str, Any]] = [
    {
        "name": "recall",
        "description": (
            "What Zaram remembers that bears on a question — facts the user has "
            "told any of their assistants, with where each came from. Call before "
            "answering anything about the user's clients, rates, terms, decisions "
            "or preferences. Cite the facts you use by their source."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The question, in words."},
                "project_id": {
                    "type": "string",
                    "description": "Narrow to one project (see `projects`) plus what is true generally.",
                },
                "limit": {"type": "integer", "description": "At most this many facts (default 6)."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "remember",
        "description": (
            "Keep one fact for the user across every assistant they use — a rate, "
            "a term, a decision. One sentence. It can be corrected or deleted by "
            "the user in Zaram afterwards."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The fact, as one sentence."},
                "project_id": {"type": "string", "description": "The project it belongs to, if one."},
            },
            "required": ["text"],
        },
    },
    {
        "name": "correct",
        "description": (
            "Replace a remembered fact that turned out to be wrong. The original is "
            "kept, struck through, and never recalled again."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "fact_id": {"type": "string", "description": "The `id` from `recall`."},
                "text": {"type": "string", "description": "What is true instead."},
            },
            "required": ["fact_id", "text"],
        },
    },
    {
        "name": "projects",
        "description": "The user's projects in Zaram — ids and names — to scope `recall` and `remember`.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def require_loopback(base_url: str) -> str:
    """The Zaram this talks to is the one on this machine, and only that.

    Parsed rather than prefix-matched, for the reason `core/context_budget.py`
    gives: ``http://127.0.0.1.evil.test`` begins like loopback and is not.
    Refused rather than gated, because this process is not the backend and
    has no `EgressGate` — a remote Zaram would be bytes leaving a machine
    with nothing logging them. That is a different product (sync), and it
    is not this file. `tests/test_egress_chokepoint.py` lists this module as
    loopback-only on the strength of this function.
    """
    from urllib.parse import urlparse

    host = (urlparse(base_url).hostname or "").lower()
    if host not in _LOOPBACK_HOSTS:
        raise SystemExit(
            f"zaram_mcp talks only to the Zaram on this machine; {base_url!r} is not "
            "loopback. Nothing here logs what leaves, so nothing here may leave."
        )
    return base_url.rstrip("/")


class SpineError(Exception):
    """Zaram answered, and the answer was a refusal or a failure."""


class Spine:
    """The running Zaram, over HTTP, as a paired client."""

    def __init__(self, credential: str, base_url: str = DEFAULT_API):
        self.credential = credential
        self.base_url = require_loopback(base_url)

    def _call(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={
                AUTH_HEADER: self.credential,
                "Content-Type": "application/json",
                "X-Zaram-Client": "zaram_mcp",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            try:
                detail = json.loads(detail).get("detail", detail)
            except ValueError:
                pass
            raise SpineError(f"Zaram refused ({exc.code}): {detail}") from None
        except urllib.error.URLError as exc:
            raise SpineError(
                f"Zaram is not reachable at {self.base_url} ({exc.reason}). Is it running?"
            ) from None

    # -- the tools ------------------------------------------------------------ #

    def recall(self, query: str, project_id: Optional[str] = None, limit: int = 6) -> Dict[str, Any]:
        return self._call("POST", "/memory/recall", {
            "query": query, "project_id": project_id or None, "limit": limit,
        })

    def remember(self, text: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        return self._call("POST", "/memory", {
            "text": text, "project_id": project_id or None, "origin": "conversation",
        })

    def correct(self, fact_id: str, text: str) -> Dict[str, Any]:
        return self._call("POST", f"/memory/{fact_id}/correct", {"content": text})

    def projects(self) -> Dict[str, Any]:
        raw = self._call("GET", "/projects")
        listed = raw if isinstance(raw, list) else raw.get("projects", raw)
        return {"projects": [
            {"id": p.get("id"), "name": p.get("name"), "type": p.get("type")}
            for p in (listed or [])
            if isinstance(p, dict)
        ]}


def _text(payload: Any) -> Dict[str, Any]:
    """An MCP tool result carrying one text block: JSON the model can read."""
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=1)}]}


def _render_recall(result: Dict[str, Any]) -> str:
    """Facts as lines a model cites well: content, then source, then id."""
    facts = result.get("facts") or []
    if not facts:
        return (
            f"Zaram remembers nothing that bears on {result.get('query')!r}"
            + (f" in {result['scope']}" if result.get("scope") else "")
            + ". Say so rather than guessing."
        )
    lines = [f"{len(facts)} fact(s) Zaram remembers, most relevant first:"]
    for fact in facts:
        origin = fact.get("origin") or "conversation"
        where = fact.get("source") or "conversation"
        scope = fact.get("scope") or "global"
        lines.append(
            f"- {fact['content']}\n"
            f"    source: {where} · origin: {origin} · scope: {scope} · id: {fact['id']}"
        )
    return "\n".join(lines)


def call_tool(spine: Spine, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch one `tools/call`. A refusal is a result with `isError`, not a
    protocol error — the model should read it."""
    try:
        if name == "recall":
            result = spine.recall(
                str(arguments.get("query") or ""),
                arguments.get("project_id"),
                int(arguments.get("limit") or 6),
            )
            return {"content": [{"type": "text", "text": _render_recall(result)}]}
        if name == "remember":
            return _text(spine.remember(str(arguments.get("text") or ""), arguments.get("project_id")))
        if name == "correct":
            return _text(spine.correct(str(arguments.get("fact_id") or ""), str(arguments.get("text") or "")))
        if name == "projects":
            return _text(spine.projects())
    except SpineError as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    return {"content": [{"type": "text", "text": f"Zaram has no tool called {name!r}."}], "isError": True}


def handle(spine: Spine, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One JSON-RPC message in, one reply out (None for a notification)."""
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}

    if request_id is None:
        # Notifications: `notifications/initialized` and anything else a
        # client sends without expecting a reply.
        return None

    def ok(result: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def error(code: int, text: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": text}}

    if method == "initialize":
        return ok({
            "protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        return ok(call_tool(spine, str(params.get("name") or ""), params.get("arguments") or {}))
    return error(-32601, f"Method not found: {method}")


def serve(spine: Spine, stdin=None, stdout=None) -> None:
    """Read requests from stdin, write replies to stdout, until EOF."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            reply = handle(spine, message)
        if reply is not None:
            stdout.write(json.dumps(reply) + "\n")
            stdout.flush()


# -- pairing, from the command line -------------------------------------------- #


def pair(token: str, name: str, base_url: str = DEFAULT_API) -> Dict[str, Any]:
    """Redeem a token from Settings. Prints the credential exactly once."""
    request = urllib.request.Request(
        require_loopback(base_url) + "/pairing/redeem",
        data=json.dumps({"token": token, "name": name}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        try:
            detail = json.loads(detail).get("detail", detail)
        except ValueError:
            pass
        raise SystemExit(f"Zaram would not pair: {detail}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"Zaram is not reachable at {base_url} ({exc.reason}). Is it running?")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="zaram_mcp", description=__doc__.split("\n\n")[0])
    parser.add_argument("--api", default=os.environ.get(API_ENV, DEFAULT_API), help="Zaram's API (default %(default)s)")
    sub = parser.add_subparsers(dest="command")
    pairing = sub.add_parser("pair", help="redeem a token from Settings and print the credential once")
    pairing.add_argument("token")
    pairing.add_argument("--name", default="MCP client", help='what Settings will call this client, e.g. "Claude Code"')
    sub.add_parser("serve", help="speak MCP over stdio (the default)")
    args = parser.parse_args(argv)

    if args.command == "pair":
        paired = pair(args.token, args.name, args.api)
        credential = paired["credential"]
        block = {"mcpServers": {"zaram": {
            "command": sys.executable,
            "args": ["-m", "zaram_mcp"],
            "cwd": os.path.dirname(os.path.abspath(__file__)),
            "env": {CREDENTIAL_ENV: credential},
        }}}
        print(f"Paired as {paired['name']!r}. Zaram will not show this credential again.\n")
        print("Add this to the client's MCP configuration (.mcp.json or equivalent):\n")
        print(json.dumps(block, indent=2))
        return 0

    credential = os.environ.get(CREDENTIAL_ENV, "")
    if not credential:
        print(
            f"No {CREDENTIAL_ENV} in the environment. Issue a token in Zaram's Settings "
            f"and run: python -m zaram_mcp pair <token> --name \"Claude Code\"",
            file=sys.stderr,
        )
        return 2
    serve(Spine(credential, args.api))
    return 0


if __name__ == "__main__":
    sys.exit(main())

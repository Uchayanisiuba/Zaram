"""Reading a repository, as tools the model can call.

A pack is parsers, tools, output templates and routing exemplars. Slice 1 built
the parser; this is the tools half, and it is deliberately **the whole
inspection tier and nothing else**: list, read, search. No write exists in this
module — not gated, not disabled, absent — which is the same structural
guarantee the artifact write path gives by having no delete.

**It is an MCP server, not a new mechanism.** `CLAUDE.md`: *"MCP is the tool
protocol. Never invent a plugin or shim format."* So this satisfies exactly the
interface `McpServer` satisfies — `connect`, `list_tools`, `call_tool`,
`close` — and the runtime treats it like any attached server. That is not
ceremony: it means these tools inherit the policy gate, the confirm-once flow,
the injection scan on descriptions and the egress log without a line of new
code, and it means the model reaches them the same way it reaches a stranger's
server.

It runs **in process** rather than as a subprocess. A server Zaram ships needs
no isolation from Zaram, and spawning a child to talk to yourself costs a
process, a packaging entry point and a class of startup failure for nothing.

**The project folder is the sandbox, and it is enforced here rather than
promised.** Every path is resolved and then checked to be inside the root, so
`../../.ssh/id_rsa`, an absolute path, and a symlink pointing out of the tree
are all refused by the same check. The model never supplies the root: it comes
from the open project, through a callable the runtime injects, because a root
taken from the model's own arguments is not a sandbox.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ingest.service import SKIP_DIRS
from runtimes.mcp.client import ToolDescriptor

logger = logging.getLogger(__name__)

#: The server's name wherever a tool is qualified, granted or logged. Short,
#: because the model sees it on every call.
SERVER_ID = "code"

#: How many lines one read may return. A model with an 8K window cannot use
#: more, and a tool that can return a whole file is a tool that will.
MAX_LINES = 400

#: How many matches a search reports. Beyond this the answer is "narrow it",
#: which is a more useful thing to tell a model than two thousand hits.
MAX_MATCHES = 60

#: How many files a listing reports before it says there are more.
MAX_FILES = 500


class OutsideTheProject(PermissionError):
    """A path resolved to somewhere the project does not cover."""


class CodeTools:
    """Read-only tools over one project folder.

    ``root_for`` is called per request rather than held, because the open
    project changes while the runtime does not. Returning ``None`` means no
    coding project is open, and every tool then refuses with that reason — a
    refusal a person can act on, rather than an empty result that reads as
    "there is nothing here".
    """

    def __init__(self, root_for: Callable[[], Optional[Path]]) -> None:
        self._root_for = root_for

    # -- the McpServer interface, so the runtime needs no special case --

    def connect(self) -> None:
        """Nothing to start. Present because the runtime calls it."""

    def close(self) -> None:
        """Nothing to stop."""

    def list_tools(self) -> List[ToolDescriptor]:
        return [
            ToolDescriptor(
                server_id=SERVER_ID,
                name="list_files",
                description=(
                    "List the files in the open project, or in one folder of it. "
                    "Paths are relative to the project root."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "subpath": {
                            "type": "string",
                            "description": "Folder to list, relative to the project root. Omit for the whole project.",
                        }
                    },
                },
            ),
            ToolDescriptor(
                server_id=SERVER_ID,
                name="read_lines",
                description=(
                    f"Read a range of lines from one file, up to {MAX_LINES} at a time. "
                    "Line numbers are 1-based and inclusive, and are returned with the text."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File to read, relative to the project root."},
                        "start_line": {"type": "integer", "description": "First line, 1-based. Defaults to 1."},
                        "end_line": {"type": "integer", "description": "Last line, inclusive."},
                    },
                    "required": ["path"],
                },
            ),
            ToolDescriptor(
                server_id=SERVER_ID,
                name="search_code",
                description=(
                    "Find where text appears in the project. Returns file, line number and the "
                    "matching line. Case-insensitive; use it to locate a symbol before reading it."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Text to find."},
                        "subpath": {"type": "string", "description": "Restrict to one folder."},
                    },
                    "required": ["query"],
                },
            ),
        ]

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        arguments = arguments or {}
        root = self._root_for()
        if root is None:
            return {
                "error": (
                    "no coding project is open, so there is no folder to read. "
                    "Open or create one first."
                )
            }

        try:
            if name == "list_files":
                return self._list_files(root, str(arguments.get("subpath") or ""))
            if name == "read_lines":
                return self._read_lines(
                    root,
                    str(arguments.get("path") or ""),
                    arguments.get("start_line"),
                    arguments.get("end_line"),
                )
            if name == "search_code":
                return self._search(
                    root,
                    str(arguments.get("query") or ""),
                    str(arguments.get("subpath") or ""),
                )
        except OutsideTheProject as refusal:
            # Reported, not raised. The engine turns an exception into a failed
            # call; this is a refusal with a reason, which is a different thing
            # and is what the model needs in order to try somewhere legal.
            return {"error": str(refusal)}
        except OSError as exc:
            return {"error": f"could not be read: {exc}"}

        return {"error": f"no tool called {name!r}"}

    # ----------------------------------------------------------- the sandbox

    def _inside(self, root: Path, relative: str) -> Path:
        """Resolve ``relative`` against the root, or refuse.

        `resolve()` before the comparison is what makes this hold: it collapses
        `..`, normalises separators, and follows symlinks — so a link inside
        the project pointing at `/etc` is caught by the same check that catches
        `../../etc`. Comparing the strings first and resolving after would pass
        every one of those.
        """
        root = root.resolve()
        candidate = (root / relative).resolve() if relative else root

        if candidate != root and root not in candidate.parents:
            raise OutsideTheProject(
                f"{relative!r} is outside the project folder, so it was not read"
            )
        return candidate

    # ------------------------------------------------------------- the tools

    def _list_files(self, root: Path, subpath: str) -> Dict[str, Any]:
        import os

        start = self._inside(root, subpath)
        if not start.is_dir():
            return {"error": f"{subpath or '.'} is not a folder"}

        found: List[str] = []
        for dirpath, dirnames, filenames in os.walk(start):
            # The same pruning ingestion uses. A listing that includes
            # `node_modules` is a listing the model will spend its context on.
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for filename in sorted(filenames):
                found.append(str((Path(dirpath) / filename).relative_to(root.resolve())).replace("\\", "/"))
                if len(found) >= MAX_FILES:
                    return {
                        "files": sorted(found),
                        "truncated": True,
                        "note": f"more than {MAX_FILES} files; list a subfolder to see the rest",
                    }
        return {"files": sorted(found), "truncated": False}

    def _read_lines(
        self, root: Path, path: str, start_line: Any, end_line: Any
    ) -> Dict[str, Any]:
        if not path:
            return {"error": "no path was given"}

        target = self._inside(root, path)
        if not target.is_file():
            return {"error": f"{path} is not a file in this project"}

        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        first = max(1, int(start_line or 1))
        last = int(end_line) if end_line else first + MAX_LINES - 1
        last = min(last, len(lines), first + MAX_LINES - 1)

        if first > len(lines):
            return {"error": f"{path} has {len(lines)} lines; {first} is past the end"}

        numbered = [
            {"line": number, "text": lines[number - 1]} for number in range(first, last + 1)
        ]
        return {
            "path": path.replace("\\", "/"),
            "start_line": first,
            "end_line": last,
            "total_lines": len(lines),
            "lines": numbered,
            # Stated rather than implied, so the model knows to ask again
            # instead of concluding the file ends here.
            "truncated": last < len(lines),
        }

    def _search(self, root: Path, query: str, subpath: str) -> Dict[str, Any]:
        import os

        if not query.strip():
            return {"error": "no query was given"}

        start = self._inside(root, subpath)
        needle = re.compile(re.escape(query), re.IGNORECASE)
        resolved_root = root.resolve()
        matches: List[Dict[str, Any]] = []

        walk = os.walk(start) if start.is_dir() else [(str(start.parent), [], [start.name])]
        for dirpath, dirnames, filenames in walk:
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for filename in sorted(filenames):
                path = Path(dirpath) / filename
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    # One unreadable file must not end the search, for the same
                    # reason one unreadable file does not end an ingest.
                    continue
                for number, line in enumerate(text.splitlines(), start=1):
                    if needle.search(line):
                        matches.append({
                            "path": str(path.relative_to(resolved_root)).replace("\\", "/"),
                            "line": number,
                            "text": line.strip()[:200],
                        })
                        if len(matches) >= MAX_MATCHES:
                            return {
                                "matches": matches,
                                "truncated": True,
                                "note": f"stopped at {MAX_MATCHES} matches; narrow the query",
                            }

        return {"matches": matches, "truncated": False}

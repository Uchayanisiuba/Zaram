"""Reading a repository, as tools the model can call.

A pack is parsers, tools, output templates and routing exemplars. Slice 1 built
the parser; this is the tools half, and it is deliberately **the whole
inspection tier and nothing else**: list, read, search. No write exists in this
module — not gated, not disabled, absent — which is the same structural
guarantee the artifact write path gives by having no delete.

**Writing arrived on 12 September and the sentence above stayed true.** The
write tools live in `writes.py` and are *injected*: a `CodeTools` built without
a writer has no write tool, and this file still contains no write call, which
the scan in `test_the_code_tools_are_reachable.py` keeps checking. The reader
lends the writer its sandbox check so there is one definition of the edge.

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

from . import apps, libraries, repo_map, runners, writes
from .apps import AppTools
from .libraries import LibraryTools
from .runners import RUN_COMMAND, CodeRunner
from .writes import TOOL_NAMES, CodeWriter

#: Tokens the repository map may take in the prompt. Sized for a 16K window:
#: enough for ~60 files with their definitions, small enough to leave the
#: window for the reads that follow. See `repo_map.py` for what it buys.
MAP_TOKENS = 1200

#: The checklist tool. See `docs/AGENT-UX.md`: the plan is a checklist the
#: model writes for itself, rendered by Zaram from the record, kept on the
#: task's row in Project. It changes no file and needs no grant.
PLAN = "plan"
MAX_PLAN_ITEMS = 20

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

    def __init__(
        self,
        root_for: Callable[[], Optional[Path]],
        *,
        writer: Optional["CodeWriter"] = None,
        writes_granted: Callable[[], bool] = lambda: False,
        runner: Optional["CodeRunner"] = None,
        runs_granted: Callable[[], bool] = lambda: False,
        library: Optional["LibraryTools"] = None,
        app: Optional["AppTools"] = None,
    ) -> None:
        self._root_for = root_for
        #: `None` means this instance cannot write, structurally. See `writes.py`.
        self._writer = writer
        #: Whether the open project has allowed edits, asked per request like
        #: the root is. Read by the runtime through `granted_tools`.
        self._writes_granted = writes_granted
        #: Same shape for running the project's commands. See `runners.py`.
        self._runner = runner
        self._runs_granted = runs_granted
        #: Lookups into the project's installed dependencies. Read-only, no
        #: grant: nothing here changes anything. See `libraries.py`.
        self._library = library
        #: Running the app and looking at it. Under the same grant as running
        #: its commands — a dev server is a command that does not exit.
        self._app = app

    def how_to_permit(self, tool_name: str) -> str:
        """Appended to a `CONFIRM` reason by the runtime, so the sentence a
        person reads names the control that would allow the call."""
        if tool_name == RUN_COMMAND or tool_name in apps.TOOL_NAMES:
            return runners.HOW_TO_PERMIT
        return writes.HOW_TO_PERMIT

    def briefing(self, query: str) -> str:
        """What the model is told about the open project before it acts.

        The repository map — files and their definitions, ranked against the
        question. Empty with no project open, which is most requests.
        """
        root = self._root_for()
        if root is None:
            return ""
        try:
            text = repo_map.repo_map(root, query, budget_tokens=MAP_TOKENS)
            if self._library is not None:
                # The versions actually installed, under the map. The cheapest
                # thing that stops a model writing against the wrong release.
                text += libraries.briefing(root)
            return text
        except Exception:  # noqa: BLE001 - a briefing must never fail a reply
            logger.exception("code pack: could not build the repository map")
            return ""

    def granted_tools(self) -> set:
        """Which of this server's tools the open project has allowed.

        The policy's grants live in `mcp-servers.json`, which holds the servers
        the *user* attached and never a built-in. So the code pack's grant is
        per project folder — rule 7j's unit is destination and data class, and
        for file edits the destination is the folder — and it is read here,
        per request, from the same place the root comes from.
        """
        # `plan` is always permitted: the model writing its own intentions
        # down is the one kind of writing that cannot need undo. Declared here
        # by Zaram's own server rather than by a name pattern in the policy,
        # so a stranger's `plan_deploy` still asks.
        granted: set = {PLAN}
        if self._writer is not None and self._writes_granted():
            granted |= set(TOOL_NAMES)
        if self._runner is not None and self._runs_granted():
            granted.add(RUN_COMMAND)
        if self._app is not None and self._runs_granted():
            granted |= {apps.START_APP, apps.STOP_APP, apps.LOOK_AT_APP}
        return granted

    # -- the McpServer interface, so the runtime needs no special case --

    def connect(self) -> None:
        """Nothing to start. Present because the runtime calls it."""

    def close(self) -> None:
        """Nothing to stop."""

    def list_tools(self) -> List[ToolDescriptor]:
        tools = self._read_tools()
        if self._writer is not None:
            tools.extend(self._writer.descriptors(SERVER_ID))
        if self._runner is not None:
            # Named per project: the description lists the runners this
            # repository actually has, which is what the model chooses from.
            tools.append(self._runner.descriptor(SERVER_ID, self._root_for()))
        if self._library is not None:
            tools.extend(self._library.descriptors(SERVER_ID))
        if self._app is not None:
            tools.extend(self._app.descriptors(SERVER_ID, self._root_for()))
        return tools

    def _read_tools(self) -> List[ToolDescriptor]:
        return [
            ToolDescriptor(
                server_id=SERVER_ID,
                name=PLAN,
                description=(
                    "Write or update your checklist for this task before and while you work: "
                    "the steps you intend to take, each with a status. Send the whole list each "
                    "time. Mark a step done when its tool call has returned, and skipped with a "
                    "reason when you decide against it. For a task with more than a couple of "
                    "steps, write the plan first."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string", "description": "One step, in a few words."},
                                    "status": {"type": "string", "enum": ["todo", "doing", "done", "skipped"]},
                                    "reason": {"type": "string", "description": "Why it was skipped."},
                                },
                                "required": ["text"],
                            },
                        }
                    },
                    "required": ["items"],
                },
            ),
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

        # **An argument nobody declared is refused, not ignored.**
        #
        # Measured 6 September 2026: driving these tools with `qwen3-14b`, the
        # model called `read_lines` with `start` and `end` and `search_code`
        # with `text` — plausible names for parameters actually called
        # `start_line`, `end_line` and `query`. Ignoring them read the file from
        # line 1 and searched for nothing, and both *succeeded*: the read
        # returned the wrong 400 lines and the search returned "no query was
        # given", neither of which tells the model what it did wrong.
        #
        # That is rule 9's shape in a tool — a plausible answer to a question
        # nobody asked. Naming the accepted arguments back is what lets the next
        # round of the loop fix it, which is the whole reason there is a loop.
        # Only for a tool that exists. "write_file does not take path" is a
        # confusing thing to say about a tool this module does not have, and the
        # honest answer to a call for one is that there is no such tool.
        accepted = self._accepted(name)
        unknown = sorted(set(arguments) - accepted) if accepted is not None else []
        if unknown:
            accepted = sorted(accepted)
            return {
                "error": (
                    f"{name} does not take {', '.join(unknown)}. "
                    f"Its arguments are: {', '.join(accepted) or 'none'}."
                )
            }

        if name == PLAN:
            # Before the root check: a plan is about the task, not the folder,
            # and a project without a repository can still be planned for.
            return self._plan(arguments.get("items"))

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
            if self._writer is not None and name in TOOL_NAMES:
                # The gate has already run in the runtime. This is the sandbox
                # and the write; the grant was decided before the call arrived.
                result = self._writer.call(name, arguments, root, self._inside)
                if "error" not in result:
                    # So the next map shows the file that was just made.
                    repo_map.forget(root)
                return result
            if self._runner is not None and name == RUN_COMMAND:
                return self._runner.call(arguments, root)
            if self._library is not None and name in libraries.TOOL_NAMES:
                return self._library.call(name, arguments, root)
            if self._app is not None and name in apps.TOOL_NAMES:
                return self._app.call(name, arguments, root)
        except OutsideTheProject as refusal:
            # Reported, not raised. The engine turns an exception into a failed
            # call; this is a refusal with a reason, which is a different thing
            # and is what the model needs in order to try somewhere legal.
            return {"error": str(refusal)}
        except OSError as exc:
            return {"error": f"could not be read: {exc}"}

        return {"error": f"no tool called {name!r}"}

    def _accepted(self, name: str) -> Optional[set]:
        """The argument names one tool declares, or ``None`` for no such tool.

        Read from `list_tools` rather than written out again here, so a
        parameter added to a descriptor cannot be rejected by a list nobody
        remembered to update — the same reason the descriptions live in one
        place.

        ``None`` and an empty set are different answers and the caller depends
        on it: one means "no tool of that name", the other means "a tool that
        takes nothing". The same three-valued discipline `vram_bytes` keeps.
        """
        for descriptor in self.list_tools():
            if descriptor.name == name:
                properties = (descriptor.input_schema or {}).get("properties") or {}
                return set(properties)
        return None

    # -------------------------------------------------------------- the plan

    def _plan(self, raw: Any) -> Dict[str, Any]:
        from projects.plans import PlanItem

        if not isinstance(raw, list):
            return {"error": "items must be a list of {text, status, reason}"}
        items = [i for i in (PlanItem.from_json(r) for r in raw[:MAX_PLAN_ITEMS]) if i]
        if not items:
            return {"error": "the list had no items with text"}
        skipped_without_reason = [i.text for i in items if i.status == "skipped" and not i.reason]
        if skipped_without_reason:
            return {"error": f"a skipped step needs a reason: {skipped_without_reason[0]!r}"}
        # The result *is* the record: the engine reads the checklist off it.
        # Nothing is kept here — a tool runs on another thread, and request
        # state written there does not come back.
        as_json = [i.to_json() for i in items]
        done = sum(1 for i in items if i.status == "done")
        return {"items": as_json, "done": done, "total": len(items)}

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
                f"{relative!r} is outside the project folder, so it was not touched"
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

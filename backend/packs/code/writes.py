"""Changing a file in the open project, with git as the undo.

Why this is its own module
--------------------------
`tools.py` is read-only *structurally*: a test scans it for a write call and
fails if one appears. That guarantee is worth keeping now that writing exists,
so the write lives here and is **injected** into `CodeTools` — a `CodeTools`
built without a writer has no write tool, not a disabled one. It is the same
shape `CLAUDE.md` gives the artifact trash: the generating path stays unable to
destroy, and the capability that can change things is a separate module
reached only through a grant a person made.

The mutative tier, answered with things that exist
--------------------------------------------------
*Undo* is git: every write is one commit, and the result carries the sha and
the command that reverses it. *Sandbox* is the project folder, checked by the
same `_inside` the reads use — one definition, passed in, so a writer cannot
drift from the reader about where the edge is. *Confirm* is the per-project
grant, decided by `policy.decide` in the runtime before this module is reached.

**A write that cannot be undone does not happen.** Three checks run before the
file is touched: git must exist and know who the user is, because a file that
lands and then cannot be committed is a file with no undo; the user's own
uncommitted changes to that file refuse the write, because committing after
would sweep their half-finished edit into Zaram's commit and make the undo
theirs to lose; and a folder that is not a repository becomes one, because
`git init` destroys nothing and a new app starts as an empty folder.

Two tools, deliberately
-----------------------
`write_file` creates or replaces a whole file. `edit_file` replaces **one exact
occurrence** of a passage and refuses when it is absent or ambiguous, naming the
count — "replace the first" silently edits the wrong one. Line-range editing
was considered and not built: a model's line numbers drift the moment its first
edit lands.

A branch per task is deferred, and `docs/CODE-PACK.md` records why: moving
somebody's checkout without asking changes where their own next commit lands.
Commits go on whichever branch the folder is on.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from runtimes.mcp.client import ToolDescriptor

logger = logging.getLogger(__name__)

#: How long one git command may take. Git on a normal repository answers in
#: milliseconds; a hung credential helper or a network remote is the case this
#: guards, and neither has any business in a local commit.
GIT_TIMEOUT_SECONDS = 30

#: Characters of unified diff carried on a write's result, for the card under
#: the reply. A change bigger than this is still made and still committed; the
#: card shows the head and says so, and `git show` has the rest.
DIFF_CAP = 6_000

#: The largest file one call may write. A model that emits more than this in
#: one argument has almost certainly lost the thread, and a write path with no
#: ceiling is a disk-filling loop waiting for a prompt.
MAX_CONTENT_BYTES = 2_000_000

WRITE_FILE = "write_file"
EDIT_FILE = "edit_file"
TOOL_NAMES = frozenset({WRITE_FILE, EDIT_FILE})

#: Shown beside a `CONFIRM` verdict so the sentence says *where* to allow it.
#: The policy's generic reason talks about servers and apps; a person looking
#: at a coding project needs to be sent to the row that has the control.
HOW_TO_PERMIT = "Allow file edits for this project in Project, then ask again."


class GitUnavailable(RuntimeError):
    """Git is missing, has no identity, or refused — nothing was written."""


class CodeWriter:
    """The two write tools, over one project folder.

    ``inside`` is the sandbox check, borrowed from the reader rather than
    re-implemented, so there is exactly one answer to "is this path in the
    project". It raises the reader's `OutsideTheProject`, which the caller
    already turns into a refusal.
    """

    def __init__(self, *, run: Optional[Callable[..., subprocess.CompletedProcess]] = None) -> None:
        # Injected for tests that want to see git fail without uninstalling it.
        self._run = run or _run_git

    # ------------------------------------------------------------ descriptors

    def descriptors(self, server_id: str) -> List[ToolDescriptor]:
        return [
            ToolDescriptor(
                server_id=server_id,
                name=WRITE_FILE,
                description=(
                    "Create a file, or replace the whole of an existing one. Each write "
                    "is committed to git so it can be reverted. Use edit_file for a change "
                    "to part of a file."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File to write, relative to the project root."},
                        "content": {"type": "string", "description": "The complete new contents of the file."},
                        "summary": {"type": "string", "description": "One line saying what changed, for the commit message."},
                    },
                    "required": ["path", "content"],
                },
            ),
            ToolDescriptor(
                server_id=server_id,
                name=EDIT_FILE,
                description=(
                    "Replace one exact passage in a file with another. The passage must "
                    "appear exactly once; include enough surrounding lines to make it "
                    "unique. Committed to git so it can be reverted."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File to edit, relative to the project root."},
                        "find": {"type": "string", "description": "The exact text to replace, as it appears in the file."},
                        "replace": {"type": "string", "description": "What to put in its place."},
                        "summary": {"type": "string", "description": "One line saying what changed, for the commit message."},
                    },
                    "required": ["path", "find", "replace"],
                },
            ),
        ]

    # -------------------------------------------------------------------- call

    def call(
        self,
        name: str,
        arguments: Dict[str, Any],
        root: Path,
        inside: Callable[[Path, str], Path],
    ) -> Dict[str, Any]:
        path = str(arguments.get("path") or "")
        if not path:
            return {"error": "no path was given"}

        target = inside(root, path)
        if target.exists() and not target.is_file():
            return {"error": f"{path} is a folder, not a file"}

        if name == WRITE_FILE:
            content = arguments.get("content")
            if not isinstance(content, str):
                return {"error": "content must be text"}
            return self._commit_write(root, target, path, content, arguments.get("summary"), created=not target.exists())

        if name == EDIT_FILE:
            find = arguments.get("find")
            replace = arguments.get("replace")
            if not isinstance(find, str) or not find:
                return {"error": "find must be the exact text to replace, and it was empty"}
            if not isinstance(replace, str):
                return {"error": "replace must be text"}
            if not target.is_file():
                return {"error": f"{path} is not a file in this project; use write_file to create one"}

            current = target.read_text(encoding="utf-8", errors="replace")
            count = current.count(find)
            if count == 0:
                return {"error": f"the text to replace does not appear in {path}; read it again and copy the passage exactly"}
            if count > 1:
                return {"error": f"the text to replace appears {count} times in {path}; include more surrounding lines so it appears once"}
            return self._commit_write(root, target, path, current.replace(find, replace, 1), arguments.get("summary"), created=False)

        return {"error": f"no tool called {name!r}"}

    # --------------------------------------------------------------- the write

    def _commit_write(
        self,
        root: Path,
        target: Path,
        path: str,
        content: str,
        summary: Any,
        *,
        created: bool,
    ) -> Dict[str, Any]:
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_CONTENT_BYTES:
            return {"error": f"that is {len(encoded):,} bytes, more than one write may put in a file ({MAX_CONTENT_BYTES:,})"}

        # Every check before the file is touched. The order matters: a refusal
        # after the write is a write with no undo.
        try:
            initialised = self._ready(root)
            self._refuse_if_user_has_changes(root, target)
        except GitUnavailable as why:
            return {"error": str(why)}

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="")

        relative = target.relative_to(root.resolve()).as_posix()
        verb = "create" if created else "edit"
        line = str(summary or "").strip().splitlines()[0] if str(summary or "").strip() else f"{verb} {relative}"
        message = f"zaram: {line}"

        try:
            self._git(root, "add", "--", relative)
            self._git(root, "commit", "-q", "-m", message, "--", relative)
            sha = self._git(root, "rev-parse", "--short", "HEAD").stdout.strip()
            diff = self.diff_of(root, sha, relative)
        except GitUnavailable as why:
            # The file is on disk and the commit is not. Said in full rather
            # than reported as success, because the undo is what was promised.
            return {"error": f"{relative} was written but could not be committed, so it has no undo: {why}"}

        result: Dict[str, Any] = {
            "path": relative,
            "created": created,
            "bytes": len(encoded),
            "commit": sha,
            "undo": f"git revert {sha}",
            # The change itself, for the card under the reply. Text that came
            # from the user's own file and the model's edit; rendered as text.
            "diff": diff,
        }
        if initialised:
            result["note"] = "this folder was not a git repository, so one was created for the undo"
        logger.info("code pack: %s %s in %s (%s)", verb, relative, root, sha)
        return result

    # ----------------------------------------------------------- undo, by a person

    def diff_of(self, root: Path, sha: str, relative: str = "") -> str:
        """The unified diff of one commit, capped, for a card."""
        args = ["show", "--format=", "--no-color", "--unified=3", sha]
        if relative:
            args += ["--", relative]
        text = self._git(root, *args).stdout
        if len(text) > DIFF_CAP:
            return text[:DIFF_CAP] + f"\n… [{len(text) - DIFF_CAP:,} more characters; git show {sha}]\n"
        return text

    def revert(self, root: Path, sha: str) -> Dict[str, Any]:
        """Reverse one of Zaram's commits, because a person pressed the button.

        The card promises *"a git commit you can revert"*, and a promise that
        requires the terminal is not kept for the people the product is for.
        This is rule 4 on a file — the user removing what was stored — and it
        is mutative in the way the artifact trash is: reached only from an
        endpoint a person triggers, never from a tool the model can call.

        **Only Zaram's own commits.** The message prefix is the check: a button
        that could revert the user's own history would be a button waiting to
        be pressed by mistake, and git has a whole vocabulary for that already.
        A revert is itself a commit, returned so it can be reverted in turn.
        """
        clean = sha.strip()
        if not clean or not all(c in "0123456789abcdef" for c in clean.lower()):
            return {"error": "that is not a commit id"}
        try:
            subject = self._git(root, "log", "-1", "--format=%s", clean).stdout.strip()
        except GitUnavailable as why:
            return {"error": f"no such commit: {why}"}
        if not subject.startswith("zaram: "):
            return {"error": "that commit is not one Zaram made, so this button will not touch it"}
        try:
            self._git(root, "revert", "--no-edit", clean)
            new = self._git(root, "rev-parse", "--short", "HEAD").stdout.strip()
        except GitUnavailable as why:
            # git's own sentence: "your local changes would be overwritten" is
            # what the person needs to hear, and it names the file.
            self._git_quiet(root, "revert", "--abort")
            return {"error": f"could not revert: {why}"}
        logger.info("code pack: reverted %s in %s as %s", clean, root, new)
        return {"reverted": clean, "commit": new, "undo": f"git revert {new}"}

    def _git_quiet(self, root: Path, *args: str) -> None:
        try:
            self._run(["git", *args], cwd=str(root))
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass

    # ------------------------------------------------------------------- git

    def _git(self, root: Path, *args: str) -> subprocess.CompletedProcess:
        try:
            done = self._run(["git", *args], cwd=str(root))
        except FileNotFoundError:
            raise GitUnavailable("git is not installed, so a change could not be committed for undo — nothing was written")
        except subprocess.TimeoutExpired:
            raise GitUnavailable(f"git {args[0]} did not finish in {GIT_TIMEOUT_SECONDS}s")
        if done.returncode != 0:
            detail = (done.stderr or done.stdout or "").strip().splitlines()
            raise GitUnavailable(f"git {args[0]} failed: {detail[-1] if detail else 'no output'}")
        return done

    def _ready(self, root: Path) -> bool:
        """Git present, identity known, folder a repository. Returns whether a
        repository had to be created."""
        # `git var` honours the environment as well as config, which
        # `git config user.email` does not — a CI job with GIT_AUTHOR_* set is
        # a machine that can commit, and the check must not say otherwise.
        try:
            self._git(root, "var", "GIT_COMMITTER_IDENT")
        except GitUnavailable as why:
            if "not installed" in str(why) or "did not finish" in str(why):
                raise
            raise GitUnavailable(
                "git does not know who you are, so a commit — the undo — cannot be made. "
                "Set user.name and user.email with git config, then ask again"
            )

        try:
            inside = self._git(root, "rev-parse", "--is-inside-work-tree").stdout.strip()
        except GitUnavailable:
            inside = "false"
        if inside == "true":
            return False

        self._git(root, "init", "-q")
        logger.info("code pack: initialised a git repository in %s for undo", root)
        return True

    def _refuse_if_user_has_changes(self, root: Path, target: Path) -> None:
        if not target.exists():
            return
        relative = target.relative_to(root.resolve()).as_posix()
        status = self._git(root, "status", "--porcelain", "--untracked-files=all", "--", relative).stdout
        for line in status.splitlines():
            if not line.strip():
                continue
            # A file git has never seen is untracked, not "changed by the
            # user" — a fresh scaffold the user dropped in, or a file written
            # before this repository existed. Committing it is the point.
            if line.startswith("??"):
                return
            raise GitUnavailable(
                f"{relative} has changes you have not committed. Commit or stash them first, "
                f"so the undo stays yours — nothing was written"
            )


def _run_git(argv: List[str], *, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=GIT_TIMEOUT_SECONDS,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

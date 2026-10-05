"""Pushing a repository is the largest thing Zaram can send, so it asks first.

`docs/MILESTONES.md` recorded the reasoning before any of this was written:
*the largest egress Zaram can perform is the whole of somebody's project,
including whatever is sitting in it* -- history, a stray `.env`, a client's files
-- and it cannot ride on `DataClass.PROMPT`, on `IMAGE`, or on a generic tool
grant. `DataClass.REPO` is the class. This module is the thing that reaches for
it.

Why the terminal, and why this shape
------------------------------------
The decision recorded with the class was that `git push` goes through the
terminal and the operating system's credential helper, **so Zaram never holds a
credential**. That is the opposite of an integration: no token is stored, nothing
is signed in to, and the user's own `git` is the only thing that authenticates.
What it left open was the gap this fills -- a push made by a command line is
invisible to `EgressGate`, which sees only what the *backend* sends, so without
this a model with the terminal grant could publish a repository with nothing
asked and nothing logged. Rule 3, broken by a subprocess.

So before a command Zaram is about to run is allowed to contain a push, the
destination is resolved and the gate is asked, with the class named.

What this is, and is not
------------------------
**It is a consent and a log entry, not a sandbox.** It reads the command line
for a `git push`; it cannot see through `sh -c "..."`, an alias, a script that
pushes, or an editor's save hook. A terminal is a grant to run arbitrary
commands, and a model that was granted one and set on evading this can. What it
does is make the *ordinary* route -- the model typing `git push` -- ask, say
where, and leave a record. Anything stronger would be a claim this code cannot
back, which is the thing this codebase has been wrong about before.

**It governs Zaram's commands and not the person's.** Commands the person types
themselves into the same box are theirs; nothing is asked of someone using their
own terminal.

**What leaves is summarised, never copied.** The log entry says how many commits
and to which remote. It does not carry commit messages or diffs: a record of what
was sent that contains it is the retention liability wearing an audit badge.
"""

from __future__ import annotations

import logging
import re
import shlex
import subprocess
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

__all__ = ["PushIntent", "check_push", "find_pushes", "host_of", "push_summary"]

#: Command separators. Crude on purpose: a segment that is not a push is
#: ignored, and a segment that is one is found wherever the separator put it.
_SEPARATORS = re.compile(r"&&|\|\||;|\||\r?\n")

#: `git`, then anything git accepts before the subcommand (`-C dir`, `-c k=v`,
#: `--no-pager`), then `push`. Anchored to a word boundary so `mygit push` and
#: `git pushd` are not matches.
_GIT_PUSH = re.compile(
    r"(?:^|[\s(\"'`])git(?:\.exe)?"
    r"(?:\s+(?:-C\s+\S+|-c\s+\S+|--[\w-]+(?:=\S+)?))*"
    r"\s+push\b(?P<rest>.*)$",
    re.IGNORECASE,
)

#: Flags that take a separate value, so the value is not mistaken for the remote.
_VALUE_FLAGS = {"-o", "--push-option", "--receive-pack", "--exec", "--repo", "--signed"}

#: Flags meaning nothing will actually be sent. `--dry-run` contacts the remote
#: but transfers no objects, so it is not the thing this exists to ask about.
_DRY = {"-n", "--dry-run"}

GIT_TIMEOUT_SECONDS = 10


class PushIntent:
    """One `git push` found in a command line."""

    __slots__ = ("remote", "explicit", "dry_run")

    def __init__(self, remote: Optional[str], explicit: bool, dry_run: bool) -> None:
        #: A remote *name* ("origin"), a URL, or ``None`` for "whatever the
        #: branch tracks" -- which only the repository can answer.
        self.remote = remote
        self.explicit = explicit
        self.dry_run = dry_run


def find_pushes(command: str) -> List[PushIntent]:
    """Every `git push` in a command line, however it was chained."""
    found: List[PushIntent] = []
    for segment in _SEPARATORS.split(command or ""):
        match = _GIT_PUSH.search(segment.strip())
        if not match:
            continue
        try:
            tokens = shlex.split(match.group("rest"), posix=True)
        except ValueError:
            tokens = match.group("rest").split()
        dry = any(t in _DRY for t in tokens)
        positional: List[str] = []
        skip = False
        for token in tokens:
            if skip:
                skip = False
                continue
            if token in _VALUE_FLAGS:
                skip = True
                continue
            if token.startswith("-"):
                continue
            positional.append(token)
        found.append(PushIntent(positional[0] if positional else None, bool(positional), dry))
    return found


def host_of(remote_url: str) -> Optional[str]:
    """The network host a git remote points at, or ``None`` for a local one.

    `None` means *nothing leaves the machine*: a path, a `file://` URL. It is not
    "unknown" -- an unparseable remote is returned as the raw string's best
    guess by the caller, never silently treated as local.
    """
    url = (remote_url or "").strip()
    if not url:
        return None
    if url.lower().startswith("file://"):
        return None
    if "://" in url:
        host = urlparse(url).hostname
        return host.lower() if host else None
    # scp-like: [user@]host:path. A Windows drive path (`C:\\repo`) and a plain
    # relative path both lack the `host:` shape or have a one-letter "host".
    scp = re.match(r"^(?:[^@/\s]+@)?(?P<host>[^:/\\\s]{2,}):(?!\\)", url)
    if scp:
        return scp.group("host").lower()
    return None


def _git(root: Path, *args: str) -> Optional[str]:
    try:
        done = subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _resolve(root: Path, intent: PushIntent) -> Tuple[Optional[str], str]:
    """(url, label) for where this push goes.

    A URL given on the command line is used as written. A name is looked up in
    the repository. No remote at all means the branch's upstream, then
    `origin` -- git's own order, so the answer is the one git will act on.
    """
    remote = intent.remote
    if remote and ("://" in remote or "@" in remote or ":" in remote):
        return remote, remote
    if not remote:
        upstream = _git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
        remote = upstream.split("/", 1)[0] if upstream else "origin"
    url = _git(root, "remote", "get-url", "--push", remote)
    return url, remote


def push_summary(root: Path, remote_label: str) -> str:
    """What is leaving, in words and numbers -- never the content itself."""
    ahead = _git(root, "rev-list", "--count", "@{u}..HEAD")
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD") or "the current branch"
    if ahead is not None and ahead.isdigit():
        count = int(ahead)
        return f"git push of {count} {'commit' if count == 1 else 'commits'} on {branch} to {remote_label}"
    return f"git push of {branch} to {remote_label} (no upstream to count against)"


def check_push(
    command: str,
    root: Path,
    *,
    gate=None,
    summarise: Callable[[Path, str], str] = push_summary,
) -> Optional[str]:
    """``None`` if the command may run; otherwise the sentence to give back.

    Asked once per push found. The gate decides and logs; a refusal is the
    ordinary answer on a machine that has not allowed the host, and is returned
    with the remedy rather than raised, because it is read by a model that will
    relay it to a person.
    """
    pushes = [p for p in find_pushes(command) if not p.dry_run]
    if not pushes:
        return None

    from core.egress import DataClass, EgressDenied, get_gate

    the_gate = gate if gate is not None else get_gate()
    for intent in pushes:
        url, label = _resolve(root, intent)
        if url is None:
            # The repository has no such remote. git will say so itself, and
            # nothing leaves; refusing here would only hide git's better message.
            continue
        host = host_of(url)
        if host is None:
            continue  # a local path or file:// -- nothing leaves the machine
        try:
            the_gate.check(
                f"https://{host}/",
                method="POST",
                body=summarise(root, label),
                source="code.git_push",
                data_class=DataClass.REPO,
            )
        except EgressDenied as denied:
            logger.info("git push to %s not run: %s", host, denied)
            return (
                f"Not run. {denied} Pushing a repository is its own decision, "
                f"separate from allowing {host} for anything else: allow "
                f"repositories to {host} in Activity, then ask again. Nothing was sent."
            )
    return None

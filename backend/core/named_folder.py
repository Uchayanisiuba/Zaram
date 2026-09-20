"""A folder the person named in their message, if it exists on this machine.

`docs/PLAN.md` F1. Today the path to coding a project is: Project → create →
name it → pick *Coding* → type a folder → back to the conversation → select
it → ask. OpenWorker, Manus and Claude Code all start from the sentence
instead — *"add dark mode to the app in C:\\foo"* — and ask for what they
need as they go. Rule 7h in `CLAUDE.md` says the same thing in general:
*offer at the moment of doubt; never make the user choose in advance.*

So when a message names a folder that exists here and no coding project is
open, the interface is handed an **offer** — a notice with the folder and a
name prefilled — and one press creates and selects the project. The model is
not asked; this is a fact about the file system, decided by looking. Project
remains where projects are managed; it stops being the toll booth.

**Only a folder that exists, and only a real path.** A bare word like
`frontend` is not a path, however plausible — offering to open a folder that
turns out to be the person's *description* of one would be a guess dressed as
a fact. The forms accepted are the ones a person actually types or pastes: a
drive-letter path, a UNC path, an absolute POSIX path, and `~`. Read only —
`Path.is_dir` — never created, never listed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

#: The path shapes a person types. Each stops at whitespace or a closing
#: quote/bracket; a path with spaces must be quoted, which is what people do.
_PATH_RE = re.compile(
    r"""
    (?P<q>["'`])(?P<quoted>(?:[A-Za-z]:[\\/]|\\\\|/|~[\\/])[^"'`\n]+)(?P=q)  # "C:\my folder"
    |
    (?P<bare>(?:[A-Za-z]:[\\/]|\\\\|~[\\/]|/(?=[A-Za-z0-9_.~-]))[^\s"'`<>|,;()\[\]]+)
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class NamedFolder:
    #: The path as the person wrote it, expanded and resolved.
    path: str
    #: A name for the project: the folder's own.
    name: str


def named_folder(text: str) -> Optional[NamedFolder]:
    """The first folder the message names that exists, or ``None``."""
    for match in _PATH_RE.finditer(text or ""):
        raw = (match.group("quoted") or match.group("bare") or "").rstrip(".:,")
        if not raw:
            continue
        try:
            candidate = Path(raw).expanduser()
            if not candidate.is_absolute() and not raw.startswith("~"):
                continue
            if candidate.is_dir():
                resolved = candidate.resolve()
                return NamedFolder(path=str(resolved), name=resolved.name or str(resolved))
        except (OSError, ValueError):
            # An unreadable or malformed path is not a folder. Nothing to offer.
            continue
    return None

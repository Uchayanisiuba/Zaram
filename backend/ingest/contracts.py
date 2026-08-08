"""What ingest returns, and what Knowledge shows.

The shapes here exist to make one rule enforceable: **a file that gave nothing
back must be visible, with a reason and a remedy**. Silent ingestion failure is
the most likely reason a user concludes the product does not know their
material and leaves, and it is invisible precisely because nothing in a
successful-looking index says which files are missing from it.

So there is no boolean `ok`. Every file ends at exactly one
:class:`IngestStatus`, and the two failure states carry the text that will be
shown to a person.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IngestStatus(str, Enum):
    """The outcome for one file. Exactly one applies."""

    #: Text came out and there was enough of it.
    INDEXED = "indexed"

    #: Parsed cleanly, but produced so little text that indexing it would
    #: quietly degrade every answer that touches it. Still indexed — see
    #: `quality.py` for why this warns rather than rejects — but shown.
    SPARSE = "sparse"

    #: Opened, parsed, and yielded no text at all. An image-only scan.
    EMPTY = "empty"

    #: Could not be opened or parsed. Encrypted, corrupt, or truncated.
    FAILED = "failed"

    #: No parser handles this suffix. Not an error; the file is simply not a
    #: document, or needs an extra that is not installed.
    UNSUPPORTED = "unsupported"

    @property
    def is_visible_problem(self) -> bool:
        """Whether Knowledge must surface this with a reason and a retry."""
        return self in {IngestStatus.SPARSE, IngestStatus.EMPTY, IngestStatus.FAILED}


class ParserUnavailable(Exception):
    """A parser exists for this format but its dependency is not installed.

    Distinct from "cannot parse": the difference is actionable. `ImportError`
    surfaced to a user as "PDF failed" tells them nothing and reads as a bug in
    Zaram rather than a missing package.
    """

    def __init__(self, message: str, remedy: str = "") -> None:
        super().__init__(message)
        self.remedy = remedy


@dataclass(frozen=True)
class ParseResult:
    """Text off one file, plus what it took to get it.

    `pages` is 0 where the format has no pages. It is not `None`, because the
    quality floor divides by it and an optional there would push the check into
    every caller.
    """

    text: str
    pages: int = 0
    parser: str = ""
    #: Free-form, for the parser to record what it noticed. Never shown raw.
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def chars(self) -> int:
        return len(self.text)

    @property
    def chars_per_page(self) -> float | None:
        return self.chars / self.pages if self.pages else None


@dataclass(frozen=True)
class IngestOutcome:
    """One file's result, as Knowledge will show it.

    `reason` and `remedy` are the whole point and are written for a person, not
    a log. `remedy` names the fix and its cost — "OCR needs the ingest extra —
    pip install zaram[ingest] (321 MB)" — so the user can decide, rather than
    being told something did not work.
    """

    path: str
    status: IngestStatus
    parser: str = ""
    chars: int = 0
    pages: int = 0
    fact_ids: tuple[str, ...] = ()
    reason: str = ""
    remedy: str = ""
    seconds: float = 0.0

    @property
    def name(self) -> str:
        import os

        return os.path.basename(self.path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "status": self.status.value,
            "parser": self.parser,
            "chars": self.chars,
            "pages": self.pages,
            "fact_ids": list(self.fact_ids),
            "reason": self.reason,
            "remedy": self.remedy,
            "seconds": round(self.seconds, 3),
        }


@dataclass(frozen=True)
class IngestReport:
    """The result of pointing at a folder.

    Counts are derived rather than stored so they cannot disagree with the
    outcomes they summarise — the kind of drift that lets a UI report "42 files
    indexed" over a list containing four failures.
    """

    root: str
    outcomes: tuple[IngestOutcome, ...]
    seconds: float = 0.0

    def count(self, status: IngestStatus) -> int:
        return sum(1 for o in self.outcomes if o.status is status)

    @property
    def problems(self) -> tuple[IngestOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status.is_visible_problem)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "seconds": round(self.seconds, 3),
            "total": len(self.outcomes),
            "counts": {s.value: self.count(s) for s in IngestStatus},
            "problems": len(self.problems),
            "outcomes": [o.to_dict() for o in self.outcomes],
        }

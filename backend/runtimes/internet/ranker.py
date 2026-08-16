"""Superseded by `relevance.py`. Kept only as a re-export.

`InternetRankerImpl` lived here and was never constructed by anything — an
eighth complete, tested-looking, unreachable module. It would also have raised
`FrozenInstanceError` on its first result if something had called it, because
it assigned to `result.score` and `SearchResult` is a frozen dataclass. So the
codebase held two rankers: this one, which compared query terms to results and
could not run, and `InternetRuntimeImpl._rank_results`, which ran and compared
nothing.

Deleting rather than repairing, because the repair is `relevance.py` and two
implementations of one decision is how they came to disagree in the first
place. `CLAUDE.md`: a failing test is fixed or deleted, never left — the same
applies to a module nothing calls.

The names below are re-exported so an import of this path keeps working and
lands on the implementation that is actually wired up.
"""

from __future__ import annotations

from .relevance import (  # noqa: F401
    MIN_WEB_RELEVANCE,
    authority_of,
    connectors_for,
    fuse,
    relevance_of,
    relevant,
    scored,
)

__all__ = [
    "MIN_WEB_RELEVANCE",
    "authority_of",
    "connectors_for",
    "fuse",
    "relevance_of",
    "relevant",
    "scored",
]

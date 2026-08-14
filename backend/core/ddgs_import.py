"""One place that knows which DuckDuckGo package to import.

**The old package returns zero results and does not raise.** Measured on this
machine, 14 August 2026: `duckduckgo_search==8.1.1` returned 0 results for a
query where `ddgs==9.14.4` returned 3, on the same connection, seconds apart.
It emits a `RuntimeWarning` saying it has been renamed and then answers
successfully with nothing.

That failure mode is the reason this module exists rather than a one-line
change at each call site. A search that *raises* is diagnosed in a minute — the
error names the library. A search that returns an empty list looks exactly like
"the web had nothing to say about that", so web search appeared enabled,
appeared to leave the machine (the egress log recorded the request, allowed,
107 bytes) and produced answers with no web sources in them. Every layer
reported success.

Three modules imported the dead name independently, which is also why the fix
is centralised: with the import repeated at each call site, the next person
fixes the one they are looking at and leaves the other two.

`ddgs` is preferred and `duckduckgo_search` is the fallback rather than the
reverse, and the fallback is kept deliberately: someone running an older
install should get a degraded search rather than an import error, and
`requirements.txt` currently pins both. Removing the old pin needs the
removal-plus-green-suite evidence `CLAUDE.md` asks for, not a metadata check.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

__all__ = ["DDGS", "ddgs_package"]

#: The class, or ``None`` when neither package is installed. Callers already
#: treat ``None`` as "search unavailable" and say so.
DDGS: Optional[Any] = None

#: Which package answered, for health reporting. A user told "search found
#: nothing" deserves to be able to find out it was the superseded library.
ddgs_package: Optional[str] = None

try:  # pragma: no cover - import-order branch
    from ddgs import DDGS as _DDGS  # type: ignore

    DDGS = _DDGS
    ddgs_package = "ddgs"
except Exception:
    try:
        from duckduckgo_search import DDGS as _LegacyDDGS  # type: ignore

        DDGS = _LegacyDDGS
        ddgs_package = "duckduckgo_search"
        logger.warning(
            "Using the superseded duckduckgo_search package. It returns empty "
            "results against the current DuckDuckGo endpoints without raising. "
            "Install ddgs for working web search."
        )
    except Exception:
        DDGS = None
        ddgs_package = None

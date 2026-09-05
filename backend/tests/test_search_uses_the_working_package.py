"""Web search imports the package that actually returns results.

The defect this exists for
--------------------------
`duckduckgo_search==8.1.1` and `ddgs==9.14.4` are both pinned in
`requirements.txt`, and every DuckDuckGo call site imported the first one. It
has been superseded, and against the current endpoints it **returns an empty
list without raising** — measured on this machine, 14 August 2026: 0 results
where `ddgs` returned 3, same connection, seconds apart. It emits a
`RuntimeWarning` about the rename and then reports success.

That is the worst shape a dependency failure can take here. A library that
raises names itself in the traceback. This one made web search look like it
worked: the feature was enabled, the request left the machine, the egress log
recorded it as allowed at 107 bytes, and the reply simply had no web sources —
indistinguishable from "the web had nothing to say about that". Every layer
reported success and the answer was silently ungrounded.

So the assertion is about *which package is bound*, not about search returning
results. A test that performed a real search would need the network, would be
slow, and would fail for reasons that are not this codebase's fault — the
`_filler()` lesson in `CLAUDE.md` applies: a check whose failures you cannot
attribute is a check nobody reads.
"""

from __future__ import annotations

import importlib

import pytest


def test_the_preferred_package_is_ddgs():
    """`ddgs` when it is installed, never the superseded name."""
    from core import ddgs_import

    if importlib.util.find_spec("ddgs") is None:
        pytest.skip("ddgs is not installed in this environment")

    assert ddgs_import.ddgs_package == "ddgs", (
        f"bound {ddgs_import.ddgs_package!r}, which returns empty results "
        f"without raising"
    )
    assert ddgs_import.DDGS is not None


def test_no_module_imports_the_superseded_package_directly():
    """Every call site goes through `core.ddgs_import`.

    Three modules imported `duckduckgo_search` independently, which is why the
    fix is a shared module rather than three edits: with the import repeated,
    the next person fixes the one they are looking at and leaves the others.

    Read from source, in the spirit of `test_egress_chokepoint.py` — a runtime
    check would only see whichever module happened to be imported.
    """
    from pathlib import Path

    backend = Path(__file__).resolve().parent.parent
    offenders = []

    for path in backend.rglob("*.py"):
        parts = set(path.parts)
        if parts & {"venv", ".venv", "site-packages", "legacy", "__pycache__"}:
            continue
        if path.name == "ddgs_import.py" or path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "from duckduckgo_search import" in text or "import duckduckgo_search" in text:
            offenders.append(str(path.relative_to(backend)))

    assert not offenders, (
        "these import the superseded package directly instead of "
        f"core.ddgs_import: {', '.join(offenders)}"
    )


def test_the_connector_reports_which_package_answered():
    """A user told "search found nothing" can find out why.

    `ddgs_package` is `None` when neither is installed, which is a different
    and separately actionable state from "installed but returning nothing".
    Collapsing them would put the two failures behind one message again.
    """
    from core import ddgs_import

    assert ddgs_import.ddgs_package in {"ddgs", "duckduckgo_search", None}
    if ddgs_import.DDGS is None:
        assert ddgs_import.ddgs_package is None
    else:
        assert ddgs_import.ddgs_package is not None

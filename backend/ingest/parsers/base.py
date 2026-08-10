"""The parser contract.

One shape, so a format is added by writing a parser and registering it — and so
Docling can arrive later as an implementation rather than a rewrite. The same
reasoning as keeping TTS behind an interface: the ingestion library is a
commodity that improves every quarter, and the parts worth protecting are the
failure reporting and the quality floor above it.

**Rule 7c: no ingestion path may route documents off-device.** A parser that
uploads a file to a managed parsing API is prohibited regardless of quality
gains — this is the exact trade the product refuses.
`test_ingest_stays_local.py` scans this package for network calls, so the rule
is enforced by test rather than by convention.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ..contracts import ParseResult


@runtime_checkable
class Parser(Protocol):
    """Turns one file into text. Raises rather than returning bad text."""

    #: Lowercase suffixes this handles, e.g. ``{".pdf"}``.
    suffixes: frozenset[str]

    #: Short name, recorded on the outcome so a user can be told what read it.
    name: str

    def available(self) -> tuple[bool, str]:
        """Whether this can run here, and if not, the remedy.

        Unavailability is a return value, not an exception — the same rule the
        exporters follow. An `ImportError` reaching a user as "PDF failed"
        tells them nothing actionable and reads as a bug in Zaram rather than a
        missing package.
        """
        ...

    def parse(self, path: Path) -> ParseResult:
        """Extract text. Raises `ParserUnavailable` or any parse error.

        Must not swallow failures into empty text: "could not open" and "opened
        and found nothing" are different outcomes with different remedies, and
        collapsing them is how a corrupt file gets reported as a scan.
        """
        ...

"""Which parser reads which file.

Resolution is by suffix, then by order: the light parser is tried first and
Docling is the fallback for what it cannot read. That ordering is deliberate
and is the reason installing the extra does not change how already-working
files are read — a folder must not index differently depending on what happens
to be installed, or a user's answers change when they install something
unrelated.
"""

from __future__ import annotations

from pathlib import Path

from ..contracts import ParseResult
from .base import Parser
from .docling import DoclingParser
from .office import DocxParser, XlsxParser
from .pdf import PdfParser
from .plaintext import PlainTextParser

#: Order matters. Light parsers first; Docling last, as the fallback.
PARSERS: tuple[Parser, ...] = (
    PlainTextParser(),
    PdfParser(),
    DocxParser(),
    XlsxParser(),
    DoclingParser(),
)


def parsers_for(suffix: str) -> tuple[Parser, ...]:
    """Every parser that claims this suffix, best-first."""
    suffix = suffix.lower()
    return tuple(p for p in PARSERS if suffix in p.suffixes)


def supported_suffixes() -> frozenset[str]:
    """Every suffix some *installed* parser can read.

    Installed, not merely registered: offering to read `.pptx` when the extra
    is absent would produce a folder scan that promises files it will then fail
    on one by one.
    """
    out: set[str] = set()
    for parser in PARSERS:
        ok, _ = parser.available()
        if ok:
            out |= parser.suffixes
    return frozenset(out)


def ocr_available() -> bool:
    """Whether a parser that can read a scan is installed."""
    ok, _ = DoclingParser().available()
    return ok


def formats() -> list[dict[str, object]]:
    """Every parser with whether it runs here and why not.

    Unavailability is a return value, not an exception — the same shape
    `export.formats()` uses, and for the same reason: a user seeing "PDF
    failed" learns nothing, while "needs the ingest extra, 321 MB" is a
    decision they can make.
    """
    rows = []
    for parser in PARSERS:
        ok, remedy = parser.available()
        rows.append({
            "name": parser.name,
            "suffixes": sorted(parser.suffixes),
            "available": ok,
            "remedy": remedy,
        })
    return rows


__all__ = [
    "PARSERS",
    "Parser",
    "ParseResult",
    "formats",
    "ocr_available",
    "parsers_for",
    "supported_suffixes",
]

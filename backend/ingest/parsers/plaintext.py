"""Plain text and Markdown. No dependency, and none wanted."""

from __future__ import annotations

from pathlib import Path

from ..contracts import ParseResult


class PlainTextParser:
    suffixes = frozenset({".txt", ".md", ".markdown", ".rst", ".csv", ".json", ".yaml", ".yml"})
    name = "plaintext"

    def available(self) -> tuple[bool, str]:
        return True, ""

    def parse(self, path: Path) -> ParseResult:
        # `errors="replace"` rather than "ignore": a file with a few bad bytes
        # should still index, and the replacement characters are visible in the
        # text where dropped bytes would be a silent hole.
        text = path.read_text(encoding="utf-8", errors="replace")
        return ParseResult(text=text, pages=0, parser=self.name)

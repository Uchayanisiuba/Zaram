"""HTML → plain text. No dependencies, and no pretence.

Markdown already covers "portable and readable in anything". This covers the
narrower case Markdown does not: text that is going somewhere with no renderer
at all — an email body, a terminal, a field in another system, a diff.

**Tables are rendered as aligned columns, not dropped.** An invoice exported to
text with its line items missing is not a plainer invoice, it is a wrong one.
Alignment is computed from the content rather than assumed, because a column of
amounts that does not line up is the thing that makes a plain-text document look
broken.

Provenance travels as a `[1]` marker per claim with the sources listed at the
foot — the same shape as Markdown's footnotes, minus the syntax that only means
something to a renderer. The machine-readable anchor cannot survive here, which
is expected: plain text has nowhere to put it, and `strip_anchors` is named for
exactly this case.
"""

from __future__ import annotations

from typing import List

from . import _reader
from .base import AVAILABLE, Availability

#: Wider than prose wants to be, narrower than a terminal. Wrapping is left
#: alone rather than hard-wrapped: a hard-wrapped paragraph pasted into an email
#: client that wraps again produces a ragged mess, and undoing it is manual.
_RULE_WIDTH = 60


class TextExporter:
    extension = "txt"
    media_type = "text/plain; charset=utf-8"
    label = "Plain text"

    def availability(self) -> Availability:
        return AVAILABLE

    def export(self, document_html: str, *, filename: str = "") -> bytes:
        doc = _reader.read(document_html)
        lines: List[str] = []
        footnotes: dict[str, int] = {}

        for block in doc.body_blocks():
            rendered = "".join(self._run(run, footnotes) for run in block.runs).strip()
            if not rendered:
                continue

            if block.tag == "h1":
                # Underlined rather than prefixed: a `#` in plain text is a
                # Markdown artefact leaking into a format that has no syntax.
                lines += [rendered, "=" * min(len(rendered), _RULE_WIDTH), ""]
            elif block.tag in ("h2", "h3"):
                lines += [rendered, "-" * min(len(rendered), _RULE_WIDTH), ""]
            elif block.tag == "li":
                lines.append(f"  * {rendered}")
            else:
                lines += [rendered, ""]

        for table in doc.tables:
            lines += self._table(table)

        source_lines = [
            b.text.strip() for b in doc.source_blocks() if b.tag == "li" and b.text.strip()
        ]
        if source_lines or footnotes:
            lines += ["", "-" * _RULE_WIDTH, "SOURCES", ""]
            lines += [f"  - {s}" for s in source_lines] or [
                "  Nothing was recalled for this document."
            ]

        return ("\n".join(lines).rstrip() + "\n").encode("utf-8")

    @staticmethod
    def _table(table: _reader.Table) -> List[str]:
        """Columns padded to their widest cell, header underlined.

        The one place this exporter does layout. Without it a line-items table
        arrives as a run-on of words and the document is unusable for the thing
        it was generated for.
        """
        grid = ([table.header] if table.header else []) + [list(r) for r in table.rows]
        if not grid:
            return []

        columns = max(len(row) for row in grid)
        padded = [list(row) + [""] * (columns - len(row)) for row in grid]
        widths = [max(len(str(row[i])) for row in padded) for i in range(columns)]

        out: List[str] = [""]
        if table.caption:
            out += [table.caption, ""]

        for index, row in enumerate(padded):
            out.append("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)).rstrip())
            if index == 0 and table.header:
                out.append("  ".join("-" * w for w in widths))
        out.append("")
        return out

    @staticmethod
    def _run(run: _reader.Run, footnotes: dict[str, int]) -> str:
        # No bold, no italic, no backticks. Plain text has no way to show
        # emphasis, and `*like this*` is Markdown wearing a disguise.
        text = run.text
        if run.claim_id:
            number = footnotes.setdefault(run.claim_id, len(footnotes) + 1)
            text = f"{text} [{number}]"
        return text

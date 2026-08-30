"""HTML → a flat block model the exporters walk.

Every exporter goes HTML → format, never format → format, so every exporter
needs to read the HTML. Doing that with four private regex scans would mean four
places to fix when the markup changes; this is the one place.

**It parses our own markup, not the web.** `render_document` produces the input,
so the tag vocabulary is fixed and small: h1, h2, p, li, section, and the inline
span/em/strong/code/br. Unknown tags are descended into rather than rejected —
an exporter losing a wrapper div is a cosmetic failure, and refusing to export
because of one is not.

`html.parser` is stdlib, so this costs nothing and is a real tokeniser. The
regex scan in `html.py` stays where it is: it answers "which claim ids are
present", which is a different and genuinely simpler question than "what is the
structure of this document".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

from ..html import CLAIM_ATTR, SOURCE_ATTR

#: Tags that end the current block and start a new one.
_BLOCK_TAGS = {"h1", "h2", "h3", "p", "li"}

#: Inline tags that change how a run is drawn.
_STYLE_TAGS = {"em": "italic", "i": "italic", "strong": "bold", "b": "bold",
               "code": "code"}


@dataclass(frozen=True)
class Run:
    """A stretch of text with uniform styling and, maybe, a claim behind it."""

    text: str
    claim_id: Optional[str] = None
    source_id: Optional[str] = None
    italic: bool = False
    bold: bool = False
    code: bool = False


@dataclass
class Block:
    """One paragraph-level thing: a heading, a paragraph, a list item."""

    tag: str
    runs: List[Run] = field(default_factory=list)
    #: The `id` attribute, when the markup carried one. This is how a claim's
    #: entry in the Sources section is addressable as a link target.
    anchor: Optional[str] = None
    #: True for everything inside `<section class="sources">`. Exporters render
    #: that region differently — smaller, after a rule — and need to know.
    in_sources: bool = False

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs)


@dataclass
class Table:
    """A table, for the spreadsheet exporter.

    Header separate from rows because a spreadsheet's first row is structural,
    not decorative: openpyxl freezes it and Excel filters on it.
    """

    caption: str = ""
    header: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    #: Column indices the composer marked as figures, read back off the
    #: `class="num"` the stylesheet already puts on them.
    #:
    #: Carried rather than re-derived, for the reason `TableBlock` states about
    #: the same field: a heuristic that reads digits right-aligns a reference
    #: number. The caller knew; this recovers what they knew instead of
    #: guessing it a second time.
    numeric_columns: List[int] = field(default_factory=list)
    #: How many blocks had been read when this table opened.
    #:
    #: `blocks` and `tables` are two flat lists, so on their own they say what
    #: a document contains and not what order it is in. The spreadsheet
    #: exporters do not care — a .xlsx *is* the table. A prose exporter does:
    #: without this, a fee table can only be written before or after the whole
    #: body, never where the author put it.
    #:
    #: Recorded as a position rather than by interleaving a placeholder into
    #: `blocks`, because every existing consumer iterates `body_blocks()` and
    #: expects only `h1, h2, h3, p, li`. A new tag in that stream would have
    #: each of them render something unintended, which is a wide change to make
    #: for a narrow need.
    after_block: int = 0


@dataclass
class Document:
    """Everything an exporter needs, with nothing format-specific in it."""

    title: str = ""
    blocks: List[Block] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)

    def body_blocks(self) -> List[Block]:
        return [b for b in self.blocks if not b.in_sources]

    def source_blocks(self) -> List[Block]:
        return [b for b in self.blocks if b.in_sources]

    def anchors(self) -> Dict[str, Block]:
        return {b.anchor: b for b in self.blocks if b.anchor}


class _Reader(HTMLParser):
    def __init__(self) -> None:
        # convert_charrefs is the default and is what we want: `&amp;` comes
        # back as `&` in the data callback, so exporters never re-decode.
        super().__init__(convert_charrefs=True)
        self.doc = Document()
        self._block: Optional[Block] = None
        self._claim: Tuple[Optional[str], Optional[str]] = (None, None)
        self._styles: List[str] = []
        self._in_sources = 0
        self._in_title = False
        self._skip = 0  # depth inside <style>/<script>, whose text is not prose

        self._table: Optional[Table] = None
        self._row: Optional[List[str]] = None
        self._cell: Optional[List[str]] = None
        self._cell_is_header = False
        self._cell_span = 1

    # -- structure ---------------------------------------------------------

    def handle_starttag(self, tag: str, attrs) -> None:
        attr = dict(attrs)

        if tag in ("style", "script"):
            self._skip += 1
            return
        if tag == "title":
            self._in_title = True
            return
        if tag == "section" and "sources" in (attr.get("class") or ""):
            self._in_sources += 1
            return
        if tag == "br" and self._block is not None:
            # A line break inside a source entry separates real fields; keeping
            # it as a space is what makes the .docx read as one line rather than
            # two words jammed together.
            self._block.runs.append(Run(" "))
            return

        if tag == "table":
            self._table = Table(after_block=len(self.doc.blocks))
            return
        if tag == "caption" and self._table is not None:
            self._cell = []
            self._cell_is_header = False
            return
        if tag == "tr" and self._table is not None:
            self._row = []
            return
        if tag in ("td", "th") and self._table is not None:
            self._cell = []
            self._cell_is_header = tag == "th"
            # `colspan` decides which *column* the cells after this one land
            # in, so ignoring it does not lose a cell — it moves every later
            # cell in the row leftwards. On an invoice that put the total under
            # "Qty": the markup is `<td colspan="3">Total due</td><td>NGN
            # 340,000.00</td>`, which without this reads as a two-column row.
            try:
                self._cell_span = max(1, int(attr.get("colspan", 1)))
                if "num" in (attr.get("class") or "").split():
                    # The column, not the cell: alignment is a property of the
                    # column in every consumer of this, and the header cell is
                    # the one the composer marks first.
                    column = len(self._row) if self._row is not None else 0
                    if column not in self._table.numeric_columns:
                        self._table.numeric_columns.append(column)
            except (TypeError, ValueError):
                # A malformed span is not worth failing an export over. One
                # column is the value that changes nothing.
                self._cell_span = 1
            return

        if tag in _BLOCK_TAGS:
            self._block = Block(
                tag=tag, anchor=attr.get("id"), in_sources=bool(self._in_sources)
            )
            self.doc.blocks.append(self._block)
            return

        if tag == "span" and CLAIM_ATTR in attr:
            self._claim = (attr.get(CLAIM_ATTR), attr.get(SOURCE_ATTR))
            return

        if tag in _STYLE_TAGS:
            self._styles.append(_STYLE_TAGS[tag])

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script"):
            self._skip = max(0, self._skip - 1)
            return
        if tag == "title":
            self._in_title = False
            return
        if tag == "section" and self._in_sources:
            self._in_sources -= 1
            return

        if tag == "caption" and self._cell is not None and self._table is not None:
            self._table.caption = "".join(self._cell).strip()
            self._cell = None
            return
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell).strip())
            # Padding rather than a span on the cell itself: a spanned cell is
            # a *layout* fact, and the two consumers of this — Word and a
            # spreadsheet — both want a grid. Empty columns put the following
            # cell under the right heading in both, which is the whole point.
            self._row.extend([""] * (self._cell_span - 1))
            self._cell = None
            self._cell_span = 1
            return
        if tag == "tr" and self._row is not None and self._table is not None:
            # The header is the first row that was made of <th>. A table whose
            # first row is <td> has no header, and saying so beats promoting a
            # data row and mislabelling every column.
            if self._cell_is_header and not self._table.header:
                self._table.header = self._row
            else:
                self._table.rows.append(self._row)
            self._row = None
            return
        if tag == "table" and self._table is not None:
            self.doc.tables.append(self._table)
            self._table = None
            return

        if tag in _BLOCK_TAGS:
            self._block = None
            return
        if tag == "span" and self._claim != (None, None):
            self._claim = (None, None)
            return
        if tag in _STYLE_TAGS and self._styles:
            self._styles.pop()

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_title:
            self.doc.title += data.strip()
            return
        if self._cell is not None:
            self._cell.append(data)
            return
        if self._block is None or not data.strip():
            return

        claim_id, source_id = self._claim
        self._block.runs.append(
            Run(
                text=data,
                claim_id=claim_id,
                source_id=source_id,
                italic="italic" in self._styles,
                bold="bold" in self._styles,
                code="code" in self._styles,
            )
        )


def read(document_html: str) -> Document:
    """Parse generated HTML into the block model."""
    reader = _Reader()
    reader.feed(document_html)
    reader.close()

    if not reader.doc.title:
        # Fall back to the first h1. A document with neither is untitled, and
        # the exporters say "Untitled" rather than writing an empty heading.
        for block in reader.doc.blocks:
            if block.tag == "h1":
                reader.doc.title = block.text.strip()
                break

    return reader.doc

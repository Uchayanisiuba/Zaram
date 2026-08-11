"""HTML → .pptx.

`CLAUDE.md` deferred PowerPoint with "later, only if asked". It was asked for on
10 August 2026, so it is here — and the way it is built is the interesting part.

**Headings are the slide boundaries.** There is no separate deck format and no
second authoring path: `<h1>` becomes the title slide, every `<h2>` starts a new
one, and the paragraphs and list items beneath it become that slide's bullets.
That falls out of HTML being the source of truth rather than being designed on
top of it, and it buys something a dedicated deck format would not — **any
document Zaram has already generated can be exported as slides**, because every
document has headings. A proposal becomes a pitch without being rewritten.

What that costs, stated plainly
-------------------------------
`_reader` collects tables separately from blocks, so their position relative to
the headings is not recoverable. Tables therefore land on their own slides at
the end rather than inside the section they belonged to. That is a real loss of
ordering and it is preferred to the alternatives: dropping them silently, or
teaching the reader to interleave for one exporter's benefit. A deck is
re-ordered by hand anyway, and a missing table is not.

Nothing here is a theme. Zaram writes structure — titles, bullets, tables — and
leaves design to PowerPoint's own template, because a deck someone presents is
one they will restyle, and a hardcoded palette is one more thing to undo.
"""

from __future__ import annotations

import io
from typing import List, Tuple

from . import _reader
from .base import Availability, module_available

#: Layout indices in python-pptx's default template. Named because `slide_layouts[1]`
#: at a call site is unreadable and wrong-by-one is silent.
_TITLE_SLIDE = 0
_TITLE_AND_CONTENT = 1
_TITLE_ONLY = 5

#: Past this, a slide is a wall of text nobody reads from the back of a room.
#: Overflow continues on a slide marked "(cont.)" rather than being dropped or
#: shrunk to fit — losing content silently is the one outcome that is not
#: recoverable by the person editing the deck afterwards.
_MAX_BULLETS = 8


class PptxExporter:
    extension = "pptx"
    media_type = (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    label = "PowerPoint"

    def availability(self) -> Availability:
        return module_available("pptx", needed_for="PowerPoint export")

    def export(self, document_html: str, *, filename: str = "") -> bytes:
        from pptx import Presentation

        doc = _reader.read(document_html)
        deck = Presentation()

        title, slides = self._outline(doc)

        cover = deck.slides.add_slide(deck.slide_layouts[_TITLE_SLIDE])
        cover.shapes.title.text = title or "Untitled"
        # Placeholder 1 is the subtitle. Cleared rather than left holding
        # "Click to add subtitle", which is what ships in the template and what
        # would otherwise be presented to a room.
        if len(cover.placeholders) > 1:
            cover.placeholders[1].text = ""

        for heading, bullets in slides:
            for index, chunk in enumerate(self._chunk(bullets)):
                slide = deck.slides.add_slide(deck.slide_layouts[_TITLE_AND_CONTENT])
                slide.shapes.title.text = heading if index == 0 else f"{heading} (cont.)"
                frame = slide.placeholders[1].text_frame
                frame.clear()
                for position, bullet in enumerate(chunk):
                    paragraph = frame.paragraphs[0] if position == 0 else frame.add_paragraph()
                    paragraph.text = bullet
                    paragraph.level = 0

        for table in doc.tables:
            self._table_slide(deck, table)

        buffer = io.BytesIO()
        deck.save(buffer)
        return buffer.getvalue()

    @staticmethod
    def _outline(doc: _reader.Document) -> Tuple[str, List[Tuple[str, List[str]]]]:
        """Title, then (heading, bullets) per slide.

        Content before the first `<h2>` is gathered under the document title, so
        an opening paragraph is not thrown away for arriving early.
        """
        title = ""
        slides: List[Tuple[str, List[str]]] = []
        current: Tuple[str, List[str]] | None = None

        for block in doc.body_blocks():
            text = block.text.strip()
            if not text:
                continue

            if block.tag == "h1" and not title:
                title = text
                continue

            if block.tag in ("h1", "h2", "h3"):
                current = (text, [])
                slides.append(current)
                continue

            if current is None:
                current = (title or "Overview", [])
                slides.append(current)
            current[1].append(text)

        # A heading with nothing under it is still a slide: it is a section
        # marker, and dropping it loses the deck's structure.
        return title, slides

    @staticmethod
    def _chunk(bullets: List[str]) -> List[List[str]]:
        if not bullets:
            return [[]]
        return [bullets[i : i + _MAX_BULLETS] for i in range(0, len(bullets), _MAX_BULLETS)]

    @staticmethod
    def _table_slide(deck, table: _reader.Table) -> None:
        from pptx.util import Inches

        grid = ([table.header] if table.header else []) + [list(r) for r in table.rows]
        if not grid:
            return

        columns = max(len(row) for row in grid)
        slide = deck.slides.add_slide(deck.slide_layouts[_TITLE_ONLY])
        slide.shapes.title.text = table.caption or "Table"

        shape = slide.shapes.add_table(
            len(grid), columns, Inches(0.6), Inches(1.8), Inches(9), Inches(0.4 * len(grid))
        )
        for r, row in enumerate(grid):
            for c in range(columns):
                shape.table.cell(r, c).text = str(row[c]) if c < len(row) else ""

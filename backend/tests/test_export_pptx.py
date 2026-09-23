"""HTML → slides.

The design claim worth testing is that there is **no separate deck format**:
headings are the slide boundaries, so any document Zaram has already generated
can be exported as slides without being rewritten. If that holds, a proposal
becomes a pitch for free; if it does not, `.pptx` is a second authoring path
and the pipeline rule has quietly gained an exception.
"""

from __future__ import annotations

import io

import pytest

from artifacts import export
from artifacts.contracts import Heading, TableBlock
from artifacts.html import render_deck, render_document, render_spreadsheet

pytest.importorskip("pptx", reason="python-pptx is not installed")

DECK = render_deck(
    title="Northwind — Q3",
    subtitle="Where the work stands",
    slides=[
        ("What we agreed", ["Three design days", "Revisions included"]),
        ("What is outstanding", ["Payment on 9 September"]),
        ("Next", []),
    ],
)

PROSE = render_document(
    title="A proposal",
    blocks=["Opening context before any heading."],
)

TABLE = render_spreadsheet(
    title="Q3 invoices",
    header=["Client", "Amount"],
    rows=[["Northwind", "1,470.50"]],
    caption="Outstanding",
)

#: A fee table in the middle of a proposal — the shape this exporter used to
#: get wrong, and the reason it matters: a reader looking at "What it costs"
#: found the costs three slides later, after the closing section.
INTERLEAVED = render_document(
    title="Northwind",
    blocks=[
        Heading(text="What it costs", level=2),
        "Two rates, depending on the month.",
        TableBlock(header=["Item", "Amount"], rows=[["Design day", "700.00"]]),
        Heading(text="What happens next", level=2),
        "Sign and return.",
    ],
)


def slides_of(document_html: str):
    from pptx import Presentation

    return Presentation(io.BytesIO(export.render(document_html, "pptx"))).slides


def text_of(slide) -> str:
    return "\n".join(
        shape.text_frame.text for shape in slide.shapes if shape.has_text_frame
    )


class TestTheOutline:
    def test_the_title_becomes_the_first_slide(self):
        slides = slides_of(DECK)

        assert slides[0].shapes.title.text == "Northwind — Q3"

    def test_each_heading_becomes_a_slide(self):
        titles = [s.shapes.title.text for s in slides_of(DECK)]

        assert "What we agreed" in titles
        assert "What is outstanding" in titles

    def test_bullets_land_under_their_heading(self):
        slide = next(s for s in slides_of(DECK) if s.shapes.title.text == "What we agreed")

        body = text_of(slide)
        assert "Three design days" in body
        assert "Revisions included" in body
        # Not leaked onto the wrong slide.
        assert "Payment on 9 September" not in body

    def test_an_empty_heading_is_still_a_slide(self):
        # A section marker. Dropping it loses the deck's structure.
        assert "Next" in [s.shapes.title.text for s in slides_of(DECK)]

    def test_the_subtitle_placeholder_is_not_left_saying_click_to_add(self):
        """What ships in python-pptx's template, and what would be presented.

        An unfilled placeholder is not blank — it carries prompt text, and a
        deck opened in front of a room showing "Click to add subtitle" is the
        kind of detail that reads as unfinished software.
        """
        assert "Click to add" not in text_of(slides_of(DECK)[0])


class TestAnyDocumentBecomesADeck:
    def test_a_plain_document_exports_without_being_rewritten(self):
        """The claim the whole design rests on.

        No deck kind required, no second authoring path — a document has
        headings, and headings are slides.
        """
        slides = slides_of(PROSE)

        assert len(slides) >= 1
        assert slides[0].shapes.title.text == "A proposal"

    def test_content_before_the_first_heading_is_kept(self):
        # Gathered under the title rather than thrown away for arriving early.
        body = "\n".join(text_of(s) for s in slides_of(PROSE))

        assert "Opening context before any heading." in body


class TestWhereATableLands:
    """It goes in the section it was written in — 23 September 2026.

    Every table used to be appended after the last slide, and this exporter's
    docstring called that a chosen loss on the grounds that the position was
    "not recoverable". It was recoverable: `_reader.Table.after_block` had
    been carrying it for the Word exporter for weeks. The test is here so the
    claim cannot quietly go back to being a paragraph in a docstring.
    """

    @staticmethod
    def _titles(slides):
        return [s.shapes.title.text if s.shapes.title is not None else "" for s in slides]

    def test_the_table_follows_its_own_section(self):
        slides = list(slides_of(INTERLEAVED))
        titles = self._titles(slides)
        table_at = next(
            index for index, s in enumerate(slides) if any(sh.has_table for sh in s.shapes)
        )

        assert titles.index("What it costs") < table_at
        assert table_at < titles.index("What happens next")

    def test_the_sections_after_it_are_not_disturbed(self):
        # The walk that positions a table counts every block, including the
        # ones in the Sources section that never become a slide. Getting that
        # wrong moves the table rather than raising, so the ordinary outline
        # is asserted alongside it.
        titles = self._titles(slides_of(INTERLEAVED))

        assert titles[0] == "Northwind"
        assert "What it costs" in titles and "What happens next" in titles


class TestTables:
    def test_a_table_becomes_a_real_table_not_a_paragraph(self):
        slides = slides_of(TABLE)
        tables = [sh for s in slides for sh in s.shapes if sh.has_table]

        assert tables, "the table was dropped or flattened into text"
        grid = tables[0].table
        assert grid.cell(0, 0).text == "Client"
        assert grid.cell(1, 0).text == "Northwind"

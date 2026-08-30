"""The Word file looks like the PDF, not like Word's 2007 template.

**Measured on a generated proposal before `word_theme` existed**, by unzipping
the file the shipped exporter produced:

    body            Calibri 11pt
    Heading 1       #365F91     Heading 2   #4F81BD      — Word 2007 blue
    page            US Letter, 1 inch top, **1.25 inch** sides
    tables          "Table Grid" — a border on all four sides of every cell

The composer was never at fault. HTML is the source of truth and it carries a
real stylesheet; a `.docx` is not rendered from that CSS, it is rebuilt block by
block, and every block took `python-docx`'s stock style.

These tests read the XML rather than trusting the API, because the failure mode
is silent in both directions: `font.name` writes only `w:ascii`, so a style can
report the right face and render another one; and a border set on a table style
that the template does not define is dropped without an error.

**Every assertion here is a period signal**, which is why they are worth having
as tests rather than as a screenshot: each one is a specific thing that made the
output look generated, and each would come back unnoticed.
"""

from __future__ import annotations

import io
import re
import zipfile

import pytest

from artifacts import theme
from artifacts.contracts import BulletList, Heading, TableBlock
from artifacts.export.docx import DocxExporter
from artifacts.html import render_document

pytest.importorskip("docx")


def _document() -> bytes:
    html = render_document(
        title="Production proposal",
        blocks=[
            Heading(level=2, text="Scope of work"),
            "Two shooting days in March, on location.",
            Heading(level=3, text="Exclusions"),
            BulletList(items=["Travel outside Lagos.", "Additional revisions."]),
            TableBlock(
                header=["Item", "Days", "Amount"],
                rows=[["Production", "2", "850,000"], ["Post", "3", "540,000"]],
                caption="All figures in naira.",
                numeric_columns=(1, 2),
            ),
        ],
        kind_label="Proposal",
    )
    return DocxExporter().export(html)


@pytest.fixture(scope="module")
def parts() -> dict:
    archive = zipfile.ZipFile(io.BytesIO(_document()))
    return {
        "styles": archive.read("word/styles.xml").decode("utf-8"),
        "document": archive.read("word/document.xml").decode("utf-8"),
        "names": archive.namelist(),
    }


def _style(styles: str, style_id: str) -> str:
    match = re.search(
        r'<w:style [^>]*w:styleId="%s".*?</w:style>' % style_id, styles, re.S
    )
    assert match, f"{style_id} is not defined in the document"
    return match.group(0)


class TestNoneOfWordsDefaultsSurvive:
    def test_the_headings_are_not_word_blue(self, parts):
        """`#365F91` and `#4F81BD` are the two colours of a stock Word file."""
        for style_id in ("Heading1", "Heading2", "Heading3"):
            style = _style(parts["styles"], style_id)
            assert "365F91" not in style
            assert "4F81BD" not in style

    def test_the_body_is_not_calibri(self, parts):
        assert "Calibri" not in _style(parts["styles"], "Normal")

    def test_the_page_is_a4(self, parts):
        """11906 × 16838 twips. Letter is 12240 × 15840."""
        size = re.search(r"<w:pgSz[^/]*/>", parts["document"]).group(0)
        assert 'w:w="11906"' in size and 'w:h="16838"' in size

    def test_the_side_margins_are_not_word_2003(self, parts):
        """1800 twips — 1.25 inch — is the give-away, and it is very visible."""
        margins = re.search(r"<w:pgMar[^/]*/>", parts["document"]).group(0)
        assert 'w:left="1800"' not in margins
        assert 'w:right="1800"' not in margins

    def test_no_box_is_drawn_around_every_cell(self, parts):
        """The "Table Grid" look, asserted as the absence of the borders it draws.

        Rules between rows are kept — a table with no rules at all reads as
        columns of text that happen to line up, which is the other failure.
        """
        borders = re.search(
            r"<w:tblBorders>.*?</w:tblBorders>", parts["document"], re.S
        )
        assert borders, "the table has no border block at all"
        block = borders.group(0)
        for edge in ("top", "left", "bottom", "right", "insideV"):
            assert re.search(r'<w:%s w:val="none"' % edge, block), (
                f"the table still draws a {edge} border on every cell"
            )
        assert re.search(r'<w:insideH w:val="single"', block), (
            "the rules between rows are gone; the table now reads as loose columns"
        )


class TestTheDesignIsTheOneTheStylesheetUses:
    def test_the_body_face_and_colour_come_from_the_shared_tokens(self, parts):
        style = _style(parts["styles"], "Normal")
        assert theme.WORD_SERIF in style
        assert theme.INK.upper() in style.upper()

    def test_a_section_label_is_small_uppercase_and_letterspaced(self, parts):
        """`h2` is a signpost in the sans face, not a smaller title.

        Word's own hierarchy makes every level a larger, bluer version of the
        one below. The stylesheet does something different and this is where
        the two used to part company.
        """
        style = _style(parts["styles"], "Heading2")

        assert theme.WORD_SANS in style
        assert "<w:caps/>" in style, "the section label is not uppercase"
        assert re.search(r'<w:spacing w:val="\d+"/>', style), "no letterspacing"
        assert theme.MUTED.upper() in style.upper()

    def test_the_sub_heading_returns_to_the_serif(self, parts):
        """`h3` is part of the text it introduces, so it is set in the text face."""
        style = _style(parts["styles"], "Heading3")

        assert theme.WORD_SERIF in style
        assert '<w:caps w:val="0"/>' in style

    def test_the_face_is_set_for_every_script(self, parts):
        """`font.name` writes `w:ascii` alone, and that is not enough.

        A document whose Latin text is Georgia while `w:eastAsia` is still
        Calibri renders inconsistently the moment anything non-Latin appears —
        a client's name, a currency symbol, a quotation mark Word substitutes.
        """
        style = _style(parts["styles"], "Normal")
        fonts = re.search(r"<w:rFonts[^/]*/>", style).group(0)

        for attribute in ("w:ascii", "w:eastAsia", "w:hAnsi", "w:cs"):
            assert f'{attribute}="{theme.WORD_SERIF}"' in fonts

    def test_headings_keep_with_what_follows(self, parts):
        """A heading stranded at the foot of a page is the visible half of this."""
        assert "<w:keepNext/>" in _style(parts["styles"], "Heading2")


class TestThePartsWordHasNoStyleFor:
    def test_there_is_a_footer(self, parts):
        assert "word/footer1.xml" in parts["names"]

    def test_the_page_number_is_a_field_not_a_number(self):
        """It has to stay true when the document is edited.

        A literal "1 of 3" is right until somebody adds a paragraph, and then
        it is a document that states its own length incorrectly.
        """
        archive = zipfile.ZipFile(io.BytesIO(_document()))
        footer = archive.read("word/footer1.xml").decode("utf-8")

        assert "PAGE" in footer and "NUMPAGES" in footer
        assert 'w:fldCharType="begin"' in footer

    def test_figures_are_right_aligned(self, parts):
        """Money that does not align on the last digit cannot be scanned.

        The column is marked by the composer — `numeric_columns` — and read
        back off the `class="num"` the stylesheet already emits, rather than
        guessed from the cell contents. A heuristic reading digits would
        right-align a reference number.
        """
        assert '<w:jc w:val="right"/>' in parts["document"]


class TestTheTwoRenderersCannotDrift:
    def test_word_and_css_take_their_colours_from_one_place(self):
        """The tokens are shared, so this is really a test that they stay shared.

        The failure it guards is quiet: change the accent in the stylesheet, and
        a client with both a PDF and a Word copy of the same document gets two
        different documents.
        """
        from artifacts import html

        assert theme.css(theme.INK) in html._STYLE
        assert theme.css(theme.MUTED) in html._STYLE
        assert theme.css(theme.ACCENT) in html._STYLE

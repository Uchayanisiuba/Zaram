"""The deck's *theme* is Zaram's, not Office 2007's.

`pptx.py` has styled its title and bullet runs from `theme.py` since 4 September
2026, and that was real but partial: it reaches the text it names and nothing
else. Everything resolved through the theme — the table style, the background,
the bullet glyphs, the hyperlink colour, any shape added by whoever inherits
this file — was still the stock scheme. Read out of a generated deck on
28 September 2026:

    theme name   Office Theme
    major latin  Calibri
    accents      1F497D  4F81BD  C0504D  9BBB59  8064A2  4BACC6  F79646

These tests assert the emitted XML rather than that `apply` was called, for the
reason `word_theme`'s sibling suite gives: a theme applied to the wrong part, or
applied after the layouts have already copied the old scheme onto their
placeholders, passes every test that checks intent and produces a stock deck.
"""

from __future__ import annotations

import io
import re
import zipfile

import pytest

from artifacts import theme
from artifacts.export.pptx import PptxExporter

pytest.importorskip("pptx", reason="PowerPoint export is an optional extra")


DOCUMENT = """<html><head><title>A deck</title></head><body>
<h1>A deck</h1>
<h2>One</h2><p>First point.</p>
<h2>Two</h2><p>Second point.</p>
</body></html>"""


def _theme_xml(document_html: str = DOCUMENT) -> str:
    data = PptxExporter().export(document_html, filename="deck.pptx")
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        return package.read("ppt/theme/theme1.xml").decode("utf-8")


# --------------------------------------------------------------------------- #
# The scheme is replaced, not merely added to
# --------------------------------------------------------------------------- #


def test_the_theme_is_named_after_the_product():
    """Cosmetic, and it is how a human notices the rest of this worked.

    PowerPoint shows the theme name in its Themes gallery, so a deck whose
    design is Zaram's and whose theme says "Office Theme" lies in a dropdown.
    """
    assert re.search(r'<a:theme[^>]*name="Zaram"', _theme_xml())


def test_the_office_2007_accents_are_gone():
    xml = _theme_xml()
    for stock in ("1F497D", "4F81BD", "C0504D", "9BBB59", "8064A2", "4BACC6", "F79646"):
        assert stock not in xml, f"Office 2007's {stock} survived"


def test_the_accents_are_the_shared_series():
    found = re.findall(r"<a:accent\d><a:srgbClr val=\"([0-9A-F]{6})\"/></a:accent\d>", _theme_xml())
    assert found == [colour.upper() for colour in theme.SERIES]


def test_the_faces_are_the_ones_word_and_the_page_use():
    """Major is the sans and minor is the serif — titles and body, in that order."""
    faces = re.findall(r'<a:latin typeface="([^"]*)"', _theme_xml())
    assert faces == [theme.WORD_SANS, theme.WORD_SERIF]


def test_no_colour_is_left_following_the_reader_s_operating_system():
    """`dk1` and `lt1` ship as `windowText` and `window`, which are *system*
    colours: they resolve to whatever the viewer's OS theme says. A deck whose
    body text follows the reader's theme is white-on-white for somebody in dark
    mode, which is the one failure a document must not have.
    """
    xml = _theme_xml()
    assert "sysClr" not in xml
    assert f'<a:dk1><a:srgbClr val="{theme.INK.upper()}"/>' in xml
    assert '<a:lt1><a:srgbClr val="FFFFFF"/>' in xml


def test_the_script_font_table_survives():
    """Only the two Latin faces move.

    The font scheme also names the face to substitute for Japanese, Hangul,
    Thai and a dozen more scripts. Those are correct, they are not Zaram's to
    choose, and replacing the element wholesale would delete them — so a deck
    with a line of Japanese in it would fall back to whatever the renderer
    guessed.
    """
    xml = _theme_xml()
    for script in ("Jpan", "Hang", "Thai", "Arab"):
        assert f'script="{script}"' in xml


# --------------------------------------------------------------------------- #
# Applied early enough to matter
# --------------------------------------------------------------------------- #


def test_the_slides_are_built_after_the_theme_is_written():
    """A layout copies the colour scheme onto its placeholders as it is
    instantiated. A theme written after the first slide exists therefore reaches
    the master and misses the deck — which looks identical in every test that
    only checks the theme part.
    """
    from pptx import Presentation

    data = PptxExporter().export(DOCUMENT, filename="deck.pptx")
    deck = Presentation(io.BytesIO(data))
    assert len(deck.slides) >= 3

    package_xml = []
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        for name in package.namelist():
            if name.startswith("ppt/slideLayouts/") and name.endswith(".xml"):
                package_xml.append(package.read(name).decode("utf-8"))
    assert package_xml, "no layouts in the package"
    for layout in package_xml:
        assert "4F81BD" not in layout, "a layout kept the 2007 accent"


def test_an_export_still_works_when_the_theme_cannot_be_reached(monkeypatch):
    """Nothing to restyle is not an error.

    A deck built from somebody else's template might relate no theme part. The
    runs `pptx.py` sets directly still carry the design, which is the state this
    module improves on rather than the state it requires — and refusing to write
    a file over it would be a worse product than a slightly plainer deck.
    """
    from artifacts.export import pptx_theme

    monkeypatch.setattr(pptx_theme, "_theme_part", lambda deck: None)
    data = PptxExporter().export(DOCUMENT, filename="deck.pptx")
    assert data[:2] == b"PK"

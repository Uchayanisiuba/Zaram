"""A generated document is laid out for paper, and carries the user's branding.

**The bug this closes was blamed on the local model and was never the model.**
Generated documents had no header, no page numbers, no letterhead and no page
geometry. The whole visual design was eight lines of CSS sized for a browser
window — `max-width:44em;margin:3em auto` — with no `@page` rule anywhere. The
model writes the words; every visual property of the output was decided by that
stylesheet, so a larger model would have produced better prose on the same
unstyled page.

These tests assert the properties that are invisible when they work: page
geometry, page numbering, the screen/print split, and that nothing in a
generated file reaches the network.
"""

from __future__ import annotations

import re
import struct
import zlib

import pytest

from artifacts.contracts import ArtifactSource, Claim
from artifacts.html import render_document
from artifacts.letterhead import (
    ALLOWED_LOGO_TYPES,
    MAX_LOGO_BYTES,
    Letterhead,
    LogoRejected,
    logo_data_uri,
)


def _png(width: int = 8, height: int = 8) -> bytes:
    """A real PNG, built here so the test needs no binary fixture."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"".join(b"\x00" + b"\x0f\x76\x6e" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _document(**kwargs) -> str:
    defaults = dict(
        title="Invoice INV-2026-014",
        blocks=["Services rendered: five days of lighting."],
    )
    defaults.update(kwargs)
    return render_document(**defaults)


class TestItIsLaidOutForPaper:
    def test_there_is_a_page_box(self):
        """The rule whose absence caused this.

        Without `@page`, WeasyPrint falls back to its own default and the
        document has no chosen paper size and no print margins — which is how a
        web layout ends up on A4 looking like a screenshot.
        """
        html = _document()
        assert "@page" in html, "no @page rule: the document has no page geometry"
        assert "size:A4" in html.replace(" ", ""), "no paper size chosen"

    def test_pages_are_numbered(self):
        """`counter(page)` alone is not enough.

        "3" tells a reader nothing; "3 of 7" tells them whether they have the
        whole document. On a multi-page invoice that is the difference between a
        client querying it and not.
        """
        html = _document()
        assert "counter(page)" in html
        assert "counter(pages)" in html, "pages are numbered without a total"

    def test_screen_and_print_are_both_styled(self):
        """One stylesheet, two media, because it is one string.

        The same HTML is the preview and the PDF source. A single set of rules
        would have to compromise: a paper-like sheet with a shadow is right on
        screen and would print a grey box on every page.
        """
        html = _document()
        assert "@media screen" in html
        assert "@media print" in html

    def test_headings_do_not_strand_at_a_page_break(self):
        html = _document()
        assert "break-after:avoid" in html.replace(" ", "")
        assert "orphans:3" in html.replace(" ", "")

    def test_a_document_with_no_branding_still_has_a_masthead(self):
        """Absence of a letterhead must not read as a rendering failure.

        A bare `<h1>` at the top of a page is what made the old output look
        unfinished, so the ruled masthead is present either way.
        """
        html = _document()
        assert 'class="masthead"' in html


class TestNothingIsFetched:
    def test_no_remote_reference_of_any_kind(self):
        """The same rule `check-no-remote-assets.mjs` enforces on the frontend.

        A generated document is opened outside Zaram, on machines and networks
        the product does not control. A web font or a linked logo would make it
        phone home from a stranger's laptop.
        """
        html = _document(
            letterhead=Letterhead(
                name="Uche Anisiuba", lines=("Lagos",), logo=logo_data_uri(_png(), "image/png")
            )
        )
        for scheme in ("http://", "https://", "//fonts."):
            assert scheme not in html, f"generated document references {scheme}"

    def test_fonts_are_system_stacks(self):
        html = _document()
        assert "@import" not in html
        assert "@font-face" not in html


class TestTheLetterhead:
    def test_the_logo_is_embedded_not_linked(self):
        """A path could not resolve even if it were allowed.

        `artifacts/export/pdf.py` calls WeasyPrint with no `base_url`, so a
        relative reference has nothing to resolve against. A data URI is the
        only form that works in both the preview and the PDF.
        """
        html = _document(letterhead=Letterhead(logo=logo_data_uri(_png(), "image/png")))
        assert "data:image/png;base64," in html

    def test_the_business_name_and_lines_reach_the_masthead(self):
        html = _document(
            letterhead=Letterhead(name="Uche Anisiuba", lines=("Lagos, Nigeria", "uche@example.com"))
        )
        assert "Uche Anisiuba" in html
        assert "Lagos, Nigeria" in html
        assert "uche@example.com" in html

    def test_the_logo_carries_the_business_name_as_alt_text(self):
        """So it is not silent to a screen reader or to PDF text extraction."""
        html = _document(
            letterhead=Letterhead(name="Uche Anisiuba", logo=logo_data_uri(_png(), "image/png"))
        )
        assert re.search(r'<img class="logo" alt="Uche Anisiuba"', html)

    def test_branding_is_escaped_like_everything_else(self):
        """A business name is user input and reaches the document unparsed."""
        html = _document(letterhead=Letterhead(name='Ampersand & Co <script>'))
        assert "<script>" not in html
        assert "&amp;" in html


class TestTheLogoUpload:
    def test_a_png_is_accepted(self):
        assert logo_data_uri(_png(), "image/png").startswith("data:image/png;base64,")

    def test_a_content_type_with_parameters_still_works(self):
        assert logo_data_uri(_png(), "image/png; charset=binary").startswith("data:image/png")

    def test_svg_is_refused_and_says_why(self):
        """Not a format oversight — a deliberate refusal.

        An SVG can carry `<image href="https://…">` or a script, which would put
        a network fetch inside a document the product promises fetches nothing,
        and no scanner can see inside a data URI to catch it.
        """
        with pytest.raises(LogoRejected) as excinfo:
            logo_data_uri(b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml")
        assert "internet" in str(excinfo.value).lower()

    def test_an_oversized_logo_is_refused_with_both_numbers(self):
        """The user is told the size and the limit, so the message is actionable."""
        with pytest.raises(LogoRejected) as excinfo:
            logo_data_uri(b"x" * (MAX_LOGO_BYTES + 1), "image/png")
        message = str(excinfo.value)
        assert str(MAX_LOGO_BYTES // 1024) in message
        assert "every document" in message

    def test_an_empty_file_is_refused(self):
        with pytest.raises(LogoRejected):
            logo_data_uri(b"", "image/png")

    def test_the_allowed_types_are_raster_only(self):
        assert all(t.startswith("image/") for t in ALLOWED_LOGO_TYPES)
        assert "image/svg+xml" not in ALLOWED_LOGO_TYPES


class TestTheMetadataBlock:
    def test_pairs_render_in_the_order_given(self):
        html = _document(meta=[("Invoice no.", "INV-014"), ("Due", "9 September 2026")])
        assert html.index("Invoice no.") < html.index("Due")

    def test_an_empty_value_is_dropped_rather_than_rendered_blank(self):
        """A label with nothing under it reads as missing data, not as absent."""
        html = _document(meta=[("Invoice no.", "INV-014"), ("Due", "")])
        assert "Invoice no." in html
        assert "Due" not in html.split("</dl>")[0]

    def test_no_block_at_all_when_there_is_no_metadata(self):
        assert 'class="meta"' not in _document()


class TestNothingElseChanged:
    def test_provenance_still_reaches_the_document(self):
        """The redesign must not have dropped what makes a document defensible."""
        claim = Claim(id="c1", source_id="memory:55b6", excerpt="Day rate is 425,000 naira.")
        html = _document(
            blocks=[claim],
            claims=[claim],
            sources=[ArtifactSource(kind="memory", title="Rate note")],
        )
        assert 'data-zaram-claim="c1"' in html
        assert "Rate note" in html
        assert "Sources" in html

    def test_existing_callers_need_no_changes(self):
        """Every new parameter is optional and additive.

        The stylesheet improvement has to reach callers that know nothing about
        letterheads, or it would only apply to code written after today.
        """
        html = render_document(title="Note", blocks=["One line."])
        assert "@page" in html
        assert 'class="masthead"' in html

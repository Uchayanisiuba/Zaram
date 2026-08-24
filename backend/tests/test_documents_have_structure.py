"""A generated document can express a heading, a list and a table.

**Why this file exists.** `render_document` took `Sequence[str | Claim]` and
wrapped every member in `<p>`, escaping it on the way. A model asked for a
proposal produced markdown, and the markdown came out as literal text: a
paragraph reading `## Scope of Work`, another reading `- Discovery`, and a fee
table rendered as one mangled block of pipe characters.

That was the entire reason generated documents read as basic beside a template
downloaded from the web. The page design was never the problem — the A4 page
box, the serif measure, the masthead, the tabular figures and the row hairlines
were all already written and tested. **The vocabulary to reach them was missing
at the one end that writes**, and missing only there: `export/_reader.py` has
always parsed `h1, h2, h3, p, li` and `table/tr/th/td`, and `export/docx.py`
has always mapped headings to Word heading styles and `li` to "List Bullet".

So these tests assert the seam, not the styling. The interesting failure was
never "the CSS is wrong" — it was "the writer cannot say what the reader can
already hear."
"""

from __future__ import annotations

import pytest

from artifacts.contracts import BulletList, Claim, Heading, PageBreak, TableBlock
from artifacts.export._reader import read as read_document
from artifacts.html import render_document


def _body(html: str) -> str:
    return html.split("<body>")[1].split("</body>")[0]


class TestStructureSurvivesToHtml:
    def test_a_heading_is_a_heading_and_not_a_paragraph_of_hashes(self):
        html = render_document(title="T", blocks=[Heading("Scope of Work")])
        assert "<h2>Scope of Work</h2>" in html
        assert "## Scope of Work" not in html

    def test_a_subheading_uses_h3(self):
        html = render_document(title="T", blocks=[Heading("Fees", level=3)])
        assert "<h3>Fees</h3>" in html

    def test_h1_is_refused_because_the_title_owns_it(self):
        # Two <h1> would give the .docx two competing Title styles and the PDF
        # outline two roots.
        with pytest.raises(ValueError):
            Heading("Not the title", level=1)

    def test_a_list_is_list_markup(self):
        html = render_document(title="T", blocks=[BulletList(["one", "two"])])
        assert "<ul><li>one</li><li>two</li></ul>" in html
        assert "<p>- one</p>" not in html

    def test_an_ordered_list_uses_ol(self):
        html = render_document(title="T", blocks=[BulletList(["a"], ordered=True)])
        assert "<ol><li>a</li></ol>" in html

    def test_a_table_is_a_table(self):
        html = render_document(
            title="T",
            blocks=[TableBlock(header=["Phase", "Amount"], rows=[["Build", "1,020,000"]])],
        )
        assert "<th>Phase</th>" in html
        assert "<td>1,020,000</td>" in html
        assert "|---|" not in html

    def test_a_document_with_a_table_carries_the_table_stylesheet(self):
        # Emitting <table> without `_TABLE_STYLE` gives a boxed, proportional,
        # left-aligned grid — the tell `_TABLE_STYLE`'s own comment describes.
        html = render_document(title="T", blocks=[TableBlock(header=["A"], rows=[["1"]])])
        assert "tabular-nums" in html
        assert "display:table-header-group" in html

    def test_numeric_columns_are_marked_for_the_stylesheet(self):
        html = render_document(
            title="T",
            blocks=[TableBlock(header=["Item", "Amount"], rows=[["x", "10"]],
                               numeric_columns=[1])],
        )
        assert '<th class="num">Amount</th>' in html
        assert '<td class="num">10</td>' in html

    def test_text_is_still_escaped_inside_structure(self):
        # Structure stops being escaped; content must not.
        html = render_document(title="T", blocks=[Heading("A <script> tag")])
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_a_page_break_is_print_only(self):
        html = render_document(title="T", blocks=[PageBreak()])
        assert '<div class="pagebreak"></div>' in html
        assert "break-before:page" in html


class TestTheOldContractStillHolds:
    """Every caller that predates the structured types keeps working."""

    def test_a_bare_string_is_still_a_paragraph(self):
        assert "<p>Just prose.</p>" in render_document(title="T", blocks=["Just prose."])

    def test_a_claim_still_carries_its_anchor(self):
        claim = Claim(id="c1", source_id="memory:55b6", excerpt="Their rate is 85,000.")
        html = render_document(title="T", blocks=[claim])
        assert 'data-zaram-claim="c1"' in html
        assert 'data-zaram-source="memory:55b6"' in html

    def test_a_claim_keeps_its_anchor_inside_a_list(self):
        # The old model forced a cited fact into prose to keep its anchor.
        claim = Claim(id="c2", source_id="memory:77c1", excerpt="They pay late.")
        html = render_document(title="T", blocks=[BulletList([claim])])
        assert '<li><span data-zaram-claim="c2"' in html


class TestTheExportersCanReadIt:
    """The readers were built for this markup. Assert they actually receive it.

    This is the half that a rendering test cannot cover, and it is the half
    that has bitten this repository repeatedly: markup that looks right in the
    HTML and reaches the exporter as something it does not recognise.
    """

    def test_headings_and_items_arrive_as_headings_and_items(self):
        html = render_document(
            title="Proposal",
            blocks=[Heading("Scope"), "Prose.", BulletList(["one", "two"])],
        )
        tags = [b.tag for b in read_document(html).body_blocks()]
        assert "h2" in tags, tags
        assert tags.count("li") == 2, tags

    def test_a_table_arrives_as_a_table(self):
        html = render_document(
            title="Proposal",
            blocks=[TableBlock(header=["Phase", "Amount"], rows=[["Build", "10"]])],
        )
        tables = read_document(html).tables
        assert len(tables) == 1
        assert tables[0].header == ["Phase", "Amount"]
        assert tables[0].rows[-1] == ["Build", "10"]


class TestBrandingReachesProseDocuments:
    """`create_document` passed none of the masthead arguments it had.

    `render_document` has accepted `letterhead`, `meta` and `kind_label` since
    the letterhead work landed, and the only caller that makes a prose document
    passed none of them — so every proposal and report rendered
    `<header class="masthead"><div></div></header>`: the masthead present,
    correctly styled, and empty, while the invoice path three methods down
    passed a letterhead and looked like a real document.

    Reachable from one caller out of two is why it read as a design gap rather
    than as a bug, and it is the shape `npm run check:reachability` is explicit
    about missing.
    """

    def _service(self, tmp_path):
        from artifacts.records import ArtifactRecords
        from artifacts.service import ArtifactService
        from artifacts.store import ArtifactStore

        return ArtifactService(
            ArtifactRecords(str(tmp_path / "artifacts.db")),
            ArtifactStore(tmp_path / "out"),
        )

    def test_a_document_can_carry_a_letterhead(self, tmp_path):
        from artifacts.letterhead import Letterhead

        art = self._service(tmp_path).create_document(
            title="Proposal",
            blocks=["Prose."],
            letterhead=Letterhead(name="Northwind Studios", lines=["Lagos"]),
        )
        assert "Northwind Studios" in art.html
        assert "<header class=\"masthead\"><div></div>" not in art.html

    def test_a_document_can_carry_a_meta_block(self, tmp_path):
        art = self._service(tmp_path).create_document(
            title="Proposal",
            blocks=["Prose."],
            meta=[("Reference", "PR-014"), ("Date", "24 August 2026")],
        )
        assert "<dt>Reference</dt><dd>PR-014</dd>" in art.html

    def test_a_document_can_carry_a_kind_label(self, tmp_path):
        art = self._service(tmp_path).create_document(
            title="Proposal", blocks=["Prose."], kind_label="Proposal"
        )
        assert '<div class="kind">Proposal</div>' in art.html

    def test_provenance_stays_off_unless_asked_for(self, tmp_path):
        # The default is the decision: a client has no use for `memory:55b6`
        # at the foot of a document addressed to them.
        art = self._service(tmp_path).create_document(title="P", blocks=["Prose."])
        assert "<h2>Sources</h2>" not in art.html

    def test_provenance_can_be_asked_for(self, tmp_path):
        art = self._service(tmp_path).create_document(
            title="P", blocks=["Prose."], include_provenance=True
        )
        assert "<h2>Sources</h2>" in art.html

"""A table survives export to Word.

**The Word exporter had no table handling at all.** `export/_reader.py` parsed
tables and `csv`, `pptx`, `text` and `xlsx` all consumed them; `docx.py` did
not mention them anywhere, so every table in every document was dropped on
export with nothing reporting it.

That was not a latent gap waiting for structured documents to arrive. It was
live, and on the flagship document: `render_invoice` emits the line items as a
table, so **an invoice exported to .docx reached the client carrying its title,
"Billed to" and the client's name — and no line items, no amounts, no total.**

It is exactly the failure `contracts.py` describes for provenance, in a worse
place: a file that looks complete and is not, sent to someone who will act on
it. A missing citation is embarrassing; a missing charge is unpaid work.

Found by exporting one and counting, which is the only way it could have been
found — the HTML was correct, the reader was correct, and every test of both
was green.
"""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from artifacts.contracts import TableBlock
from artifacts.export._reader import read
from artifacts.export.docx import DocxExporter
from artifacts.html import render_document, render_invoice
from artifacts.invoice import LineItem, total_of
from artifacts.markdown_blocks import blocks_from_markdown

docx = pytest.importorskip("docx")


def _word(html: str):
    data = DocxExporter().export(html, filename="t.docx")
    path = Path(tempfile.mkdtemp()) / "t.docx"
    path.write_bytes(data)
    return docx.Document(str(path))


def _cells(table):
    return [[cell.text for cell in row.cells] for row in table.rows]


class TestTheInvoiceKeepsItsMoney:
    def _invoice_html(self) -> str:
        items = [
            LineItem(
                description="Design days",
                quantity=Decimal("4"),
                unit_price=Decimal("85000"),
            )
        ]
        return render_invoice(
            title="Invoice INV-014",
            items=items,
            totals=total_of(items),
            currency="NGN",
            bill_to=["Northwind Studios"],
        )

    def test_an_exported_invoice_has_a_table(self):
        assert len(_word(self._invoice_html()).tables) == 1

    def test_the_line_items_are_in_it(self):
        rows = _cells(_word(self._invoice_html()).tables[0])
        flat = " ".join(cell for row in rows for cell in row)
        assert "Design days" in flat
        assert "85,000" in flat

    def test_the_total_is_in_it(self):
        rows = _cells(_word(self._invoice_html()).tables[0])
        flat = " ".join(cell for row in rows for cell in row)
        assert "Total due" in flat
        assert "340,000" in flat


class TestProseDocumentsKeepTheirTables:
    def test_a_table_block_reaches_word(self):
        html = render_document(
            title="Proposal",
            blocks=[TableBlock(header=["Phase", "Amount"], rows=[["Build", "1,020,000"]])],
        )
        rows = _cells(_word(html).tables[0])
        assert rows[0] == ["Phase", "Amount"]
        assert rows[1] == ["Build", "1,020,000"]

    def test_a_markdown_table_reaches_word(self):
        html = render_document(
            title="Proposal",
            blocks=blocks_from_markdown("## Fees\n\n| P | A |\n|---|---|\n| x | 1 |"),
        )
        assert len(_word(html).tables) == 1

    def test_the_header_row_is_bold(self):
        html = render_document(
            title="P", blocks=[TableBlock(header=["A"], rows=[["1"]])]
        )
        header = _word(html).tables[0].rows[0].cells[0]
        assert any(run.bold for para in header.paragraphs for run in para.runs)


class TestOrder:
    """A table belongs where its author put it, not at one end of the file."""

    def test_a_table_lands_between_the_sections_around_it(self):
        html = render_document(
            title="P",
            blocks=blocks_from_markdown(
                "## First\n\n| P | A |\n|---|---|\n| x | 1 |\n\n## Second"
            ),
        )
        # The reader records the position; without it the table could only be
        # written before or after the whole body.
        document = read(html)
        assert document.tables[0].after_block > 0

        word = _word(html)
        body = word.element.body
        table_index = list(body).index(word.tables[0]._element)
        heading_positions = [
            list(body).index(p._element)
            for p in word.paragraphs
            if p.text.strip() in ("First", "Second")
        ]
        assert min(heading_positions) < table_index < max(heading_positions)


class TestHeadingDepth:
    def test_h3_stays_a_sub_level(self):
        # Collapsing h3 into Heading 2 flattens the outline, and Word's
        # navigation pane and the PDF bookmark tree are built from exactly it.
        html = render_document(
            title="P", blocks=blocks_from_markdown("## Section\n\n### Subsection")
        )
        styles = [p.style.name for p in _word(html).paragraphs if p.text.strip()]
        assert "Heading 2" in styles
        assert "Heading 3" in styles


class TestSpannedCellsLandInTheRightColumn:
    """`colspan` decides which column later cells fall into.

    Ignoring it does not lose a cell — it shifts every later cell in the row
    leftwards. On an invoice that was visible and wrong in the way that matters:
    the markup is `<td colspan="3">Total due</td><td class="num">NGN
    340,000.00</td>`, so the total landed in the **Qty** column, and a client
    opening the .docx saw the amount they owe sitting under a quantity heading.
    """

    def _invoice_rows(self):
        items = [
            LineItem(
                description="Design days",
                quantity=Decimal("4"),
                unit_price=Decimal("85000"),
            )
        ]
        html = render_invoice(
            title="Invoice INV-014",
            items=items,
            totals=total_of(items),
            currency="NGN",
            bill_to=["Northwind Studios"],
        )
        return _cells(_word(html).tables[0])

    def test_the_total_sits_under_the_amount_column(self):
        rows = self._invoice_rows()
        header = rows[0]
        amount_column = header.index("Amount")
        total_row = next(r for r in rows if r[0] == "Total due")
        assert "340,000" in total_row[amount_column]

    def test_the_total_is_not_under_the_quantity_column(self):
        rows = self._invoice_rows()
        quantity_column = rows[0].index("Qty")
        total_row = next(r for r in rows if r[0] == "Total due")
        assert total_row[quantity_column] == ""

    def test_every_row_is_the_width_of_the_header(self):
        rows = self._invoice_rows()
        assert {len(row) for row in rows} == {len(rows[0])}

    def test_a_malformed_colspan_does_not_fail_the_export(self):
        # One column is the value that changes nothing.
        from artifacts.export._reader import read

        table = read(
            "<table><tr><td colspan='oops'>A</td><td>B</td></tr></table>"
        ).tables[0]
        assert table.rows[0] == ["A", "B"]

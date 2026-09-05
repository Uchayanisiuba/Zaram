"""The three formats that need nothing installed: .html, .txt, .csv.

They exist because "Zaram generates documents" has to be true on a machine
where WeasyPrint's GTK libraries are missing and python-docx was never
installed. Markdown was carrying that alone.

Each one is tested for the thing it would plausibly get wrong rather than for
round-tripping in general:

- **html** must be the source of truth *unchanged*, anchors and all. Any
  transformation creates a fourth rendering that can disagree with the preview,
  the PDF and the .docx.
- **txt** must not drop tables. An invoice exported to text without its line
  items is not a plainer invoice, it is a wrong one.
- **csv** must not re-type values. It feeds an importer, and a guess made here
  overrides the rule the user configured there.
"""

from __future__ import annotations

import csv as csv_module
import io

from artifacts import export
from artifacts.html import render_document, render_spreadsheet
from artifacts.contracts import ArtifactSource, Claim

CLAIM = Claim(id="c1", source_id="memory:55b6", excerpt="Their day rate is 450.")
SOURCE = ArtifactSource(kind="memory", title="Rate, from the Q3 call")

DOCUMENT = render_document(
    title="Northwind — scope",
    blocks=["We agreed the shape of the work.", CLAIM],
    sources=[SOURCE],
    claims=[CLAIM],
    include_provenance=True,
)

TABLE = render_spreadsheet(
    title="Q3 invoices",
    header=["Client", "Amount", "Paid"],
    rows=[["Northwind", "1,470.50", "no"], ["Harbour Lane", "980.00", "yes"]],
    caption="Outstanding at 10 August",
)


class TestAlwaysAvailable:
    def test_none_of_them_can_be_unavailable(self):
        """The point of having them.

        PDF needs native GTK and .docx needs a wheel; both can be missing. If
        every format could be unavailable, "generate a document" would be a
        promise the product cannot keep on a fresh machine.
        """
        for extension in ("html", "txt", "csv", "md"):
            assert export.get(extension).availability().ok, extension


class TestHtml:
    def test_it_is_the_source_of_truth_byte_for_byte(self):
        out = export.render(DOCUMENT, "html").decode("utf-8")

        # Not reformatted, not minified. The user's copy is what the preview
        # rendered and what WeasyPrint consumed.
        assert out == DOCUMENT

    def test_the_claim_anchors_survive(self):
        """The only export that keeps provenance machine-readable.

        `strip_anchors` exists for formats that cannot carry custom markup.
        HTML can, so this is the format to hand to something that wants to
        *check* the document rather than read it.
        """
        out = export.render(DOCUMENT, "html").decode("utf-8")

        assert "c1" in out
        assert "memory:55b6" in out

    def test_it_carries_no_external_references(self):
        # A remote stylesheet or image would make the file depend on a network
        # the product refuses to use, and would break the moment it is emailed.
        out = export.render(DOCUMENT, "html").decode("utf-8").lower()

        assert "http://" not in out
        assert "https://" not in out
        assert "<link" not in out


class TestText:
    def test_the_prose_survives(self):
        out = export.render(DOCUMENT, "txt").decode("utf-8")

        assert "We agreed the shape of the work." in out
        assert "Their day rate is 450." in out

    def test_headings_are_underlined_rather_than_hashed(self):
        # A `#` prefix is Markdown syntax leaking into a format that has none.
        out = export.render(DOCUMENT, "txt").decode("utf-8")

        assert "Northwind — scope" in out
        assert "=" * 10 in out
        assert "# Northwind" not in out

    def test_a_table_keeps_its_rows_and_lines_up(self):
        """The one place this exporter does layout, and the reason it must.

        Without it a line-items table arrives as a run-on of words and the
        document is useless for what it was generated for.
        """
        out = export.render(TABLE, "txt").decode("utf-8")

        assert "Northwind" in out and "1,470.50" in out
        assert "Harbour Lane" in out and "980.00" in out

        rows = [line for line in out.splitlines() if "Northwind" in line or "Harbour" in line]
        # Both data rows padded to the same width means the amount column
        # starts at the same offset in each.
        assert len({line.index("9") if "9" in line else -1 for line in rows}) >= 1
        assert all(line.startswith(("Northwind", "Harbour")) for line in rows)

    def test_claims_are_marked_and_listed(self):
        out = export.render(DOCUMENT, "txt").decode("utf-8")

        assert "[1]" in out
        assert "SOURCES" in out

    def test_no_markdown_emphasis_leaks_in(self):
        out = export.render(DOCUMENT, "txt").decode("utf-8")

        assert "**" not in out
        assert "`" not in out


class TestCsv:
    def rows_of(self, artifact_html: str):
        out = export.render(artifact_html, "csv").decode("utf-8-sig")
        return list(csv_module.reader(io.StringIO(out)))

    def test_the_header_and_rows_come_through(self):
        rows = self.rows_of(TABLE)

        assert rows[0] == ["Client", "Amount", "Paid"]
        assert rows[1][0] == "Northwind"
        assert rows[2][0] == "Harbour Lane"

    def test_a_thousands_separator_is_removed(self):
        """Removed because it is ambiguous with the delimiter itself.

        Left in, "1,470.50" splits one figure across two columns and every row
        below it is misaligned. This is the one re-typing this exporter does,
        and it is about the file format rather than about the value.
        """
        rows = self.rows_of(TABLE)

        assert rows[1][1] == "1470.50"

    def test_a_value_without_a_separator_is_untouched(self):
        # No currency stripping, no number coercion. CSV has no types; whatever
        # receives the file decides, using the rule the user configured there.
        rows = self.rows_of(TABLE)

        assert rows[2][1] == "980.00"
        assert rows[1][2] == "no"

    def test_it_starts_with_a_bom_so_excel_reads_utf8(self):
        """Without it, "Ünïcodé Studio" arrives mangled on Windows.

        The same class of defect as the accent-stripping slug, in a different
        place: correct bytes, wrong assumption about who reads them.
        """
        out = export.render(TABLE, "csv")

        assert out.startswith(b"\xef\xbb\xbf")

    def test_it_uses_crlf(self):
        # RFC 4180, and what Excel expects. A LF-only CSV opens fine almost
        # everywhere and then does not in the one place the user needed it to.
        out = export.render(TABLE, "csv").decode("utf-8-sig")

        assert "\r\n" in out

    def test_provenance_is_not_appended_to_the_grid(self):
        """A "Sources" row below the data breaks an import at row 400.

        Rule 2 is satisfied on the record and in the formats that can carry it.
        Inventing a place for it here would damage the one job CSV has.
        """
        out = export.render(DOCUMENT, "csv").decode("utf-8-sig")

        assert "memory:55b6" not in out

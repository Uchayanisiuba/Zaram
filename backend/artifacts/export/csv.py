"""HTML tables → CSV. No dependencies; `csv` is in the standard library.

What .xlsx is for reading and .csv is for *feeding*: an accountant's import, a
bank's upload form, a script. That difference decides every choice here.

**Values are written as they appear, not re-typed.** The xlsx exporter converts
"1,234" to a number because Excel is a place a human reads and sums figures. CSV
has no types at all — whatever receives the file decides — so guessing is worse
than useless here: strip a currency symbol and the importer may take the number
as its own currency; leave it and the importer's own rule applies, which is the
one the user actually configured. The exception is the thousands separator,
which is removed because it is *ambiguous with the delimiter itself* and would
split one figure across two columns.

**No provenance.** CSV has nowhere to put a footnote that would not corrupt the
grid, and a "Sources" row appended below the data is exactly the kind of thing
that breaks an import at row 400 with an unhelpful error. Rule 2 is satisfied on
the record and in the formats that can carry it; inventing a place here would
damage the one job this format has.

**Every table, one file, separated by a blank line** — only when there is more
than one, which is rare. A CSV with two grids in it is already unusual, and
silently dropping the second is worse than a file the importer complains about.
"""

from __future__ import annotations

import csv as csv_module
import io
import re

from . import _reader
from .base import AVAILABLE, Availability

#: Digit groups only: "1,234,567.89" → "1234567.89". Anchored end to end so a
#: description that happens to contain a comma is left completely alone.
_GROUPED_NUMBER = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")


class CsvExporter:
    extension = "csv"
    media_type = "text/csv; charset=utf-8"
    label = "CSV"

    def availability(self) -> Availability:
        return AVAILABLE

    def export(self, document_html: str, *, filename: str = "") -> bytes:
        doc = _reader.read(document_html)
        buffer = io.StringIO(newline="")
        # CRLF, which is what RFC 4180 specifies and what Excel expects. A
        # LF-only CSV opens fine almost everywhere and then does not in the one
        # place the user needed it to.
        writer = csv_module.writer(buffer, lineterminator="\r\n")

        for index, table in enumerate(doc.tables):
            if index:
                writer.writerow([])
            if table.header:
                writer.writerow([self._cell(c) for c in table.header])
            for row in table.rows:
                writer.writerow([self._cell(c) for c in row])

        # A BOM, so Excel on Windows reads UTF-8 rather than the system
        # codepage. Without it "Ünïcodé Studio" arrives mangled — the same class
        # of defect as the accent-stripping slug, in a different place.
        return buffer.getvalue().encode("utf-8-sig")

    @staticmethod
    def _cell(value: object) -> str:
        text = str(value).strip()
        return text.replace(",", "") if _GROUPED_NUMBER.match(text) else text

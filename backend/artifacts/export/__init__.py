"""The exporters, and the one place that knows which formats exist.

HTML is the source of truth. Every format in here is a rendering of it, and
none of them is a rendering of another: re-exporting a .docx as PDF by
converting the .docx loses the claim anchors, because export formats do not
preserve custom markup. Always HTML → format.

Nothing here writes a file. `render` returns bytes; `write` hands them to
`ArtifactStore`, which is the only module in the product that creates files and
has no capability to remove or replace one. Keeping the split means adding a
sixth format cannot weaken that guarantee.

Availability, not exceptions
----------------------------
`formats()` reports every format with whether it can run here and why not, so a
picker can grey out PDF with "needs GTK, which is not a pip install on Windows"
attached, rather than offering a button that raises `ImportError` — which tells
a user nothing they can act on and reads as a bug in Zaram rather than a missing
system library.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from .base import AVAILABLE, Availability, Exporter, ExportUnavailable
from .chart import ChartExporter
from .csv import CsvExporter
from .docx import DocxExporter
from .html import HtmlExporter
from .markdown import MarkdownExporter
from .pdf import PdfExporter
from .pptx import PptxExporter
from .text import TextExporter
from .xlsx import XlsxExporter

if TYPE_CHECKING:  # pragma: no cover
    from ..contracts import Artifact
    from ..store import ArtifactStore

__all__ = [
    "AVAILABLE",
    "Availability",
    "ExportUnavailable",
    "Exporter",
    "EXPORTERS",
    "formats",
    "get",
    "render",
    "write",
]

#: Keyed by extension, which is also the format's name everywhere in the product.
EXPORTERS: Dict[str, Exporter] = {
    exporter.extension: exporter
    for exporter in (
        # The four that cannot be unavailable: nothing to import, nothing to
        # detect. When PDF is blocked on native libraries and .docx on a missing
        # wheel, these still answer — which is what makes "generate a document"
        # a promise the product can keep on any machine.
        MarkdownExporter(),
        HtmlExporter(),
        TextExporter(),
        CsvExporter(),
        DocxExporter(),
        XlsxExporter(),
        PptxExporter(),
        ChartExporter(),
        PdfExporter(),
    )
}


class UnknownFormat(KeyError):
    """Asked for a format that does not exist, as opposed to one that cannot run.

    A separate failure from `ExportUnavailable` because the two mean different
    things to a caller: this one is a bug in the caller, the other is a fact
    about the machine.
    """


def get(extension: str) -> Exporter:
    key = extension.lower().lstrip(".")
    try:
        return EXPORTERS[key]
    except KeyError:
        raise UnknownFormat(
            f"no exporter for {extension!r}; have {sorted(EXPORTERS)}"
        ) from None


def formats() -> List[Tuple[str, Availability]]:
    """Every format and whether it can run here, for the picker.

    Sorted with the available ones first so the common case is at the top, then
    alphabetically. The unavailable ones are still returned — CLAUDE.md:
    "Disabled capabilities are visible, not silent."
    """
    entries = [(ext, exporter.availability()) for ext, exporter in EXPORTERS.items()]
    return sorted(entries, key=lambda pair: (not pair[1].ok, pair[0]))


def render(document_html: str, extension: str, *, filename: str = "") -> bytes:
    """HTML → bytes in the named format, or a stated reason it cannot be done."""
    exporter = get(extension)
    availability = exporter.availability()
    if not availability.ok:
        raise ExportUnavailable(exporter.extension, availability)

    return exporter.export(document_html, filename=filename)


def write(
    artifact: "Artifact",
    extension: str,
    store: "ArtifactStore",
    *,
    filename: Optional[str] = None,
) -> Path:
    """Render an artifact and create the file, updating the record in place.

    The seam between generation and Work: after this, `artifact.path` and
    `artifact.size_bytes` describe a file that exists. The name may differ from
    the one asked for — `write_new` increments on collision and never replaces
    anything — so the record is updated from the path that was actually used
    rather than the one that was proposed.
    """
    exporter = get(extension)
    name = filename or artifact.filename or f"{artifact.id}.{exporter.extension}"
    if not name.lower().endswith(f".{exporter.extension}"):
        name = f"{name}.{exporter.extension}"

    data = render(artifact.html, extension, filename=name)
    path = store.write_new(name, data)

    artifact.path = str(path)
    artifact.filename = path.name
    artifact.size_bytes = len(data)
    return path

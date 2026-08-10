"""Docling, behind the same interface as everything else.

Not in the base install, on measurement rather than on principle. Docling pulls
321 MB of wheels — torch, torchvision, opencv, transformers, scipy, rapidocr —
against a 267 MB base, and the packaging work that got there was the single most
consequential thing done for the alpha. A 590 MB download is back in the
territory where someone on metered data does not finish.

What it buys is the 4 PDFs in 54 that the light path cannot read: image-only
scans with no text layer. That is a real gap and a real remedy, which is why
this adapter exists and is offered by name at the moment of failure rather than
being quietly absent.

Rule 7c still binds: this runs the models locally. Docling's remote-serving and
managed-parsing paths are never enabled here, and `test_ingest_stays_local.py`
enforces it.
"""

from __future__ import annotations

from pathlib import Path

from ..contracts import ParseResult, ParserUnavailable

#: Named with its cost, because "install the extra" on a metered connection is
#: a decision nobody can make without the number.
REMEDY = "pip install zaram[ingest] (321 MB, one time)"


class DoclingParser:
    """Handles the formats the light parsers cannot, when installed.

    Deliberately narrow: it claims only scanned PDFs and the formats nothing
    else covers. Letting it take every `.docx` as well would make the extra
    change behaviour on files that already worked, so the same folder would
    index differently depending on what was installed.
    """

    suffixes = frozenset({".pdf", ".pptx", ".html", ".htm", ".xhtml", ".adoc"})
    name = "docling"

    def available(self) -> tuple[bool, str]:
        try:
            from docling.document_converter import DocumentConverter  # noqa: F401
        except ImportError:
            return False, f"OCR and slide reading need the ingest extra: {REMEDY}"
        return True, ""

    def parse(self, path: Path) -> ParseResult:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise ParserUnavailable(str(exc), REMEDY) from exc

        converter = DocumentConverter()
        result = converter.convert(str(path))
        document = result.document
        text = document.export_to_markdown()
        pages = len(getattr(document, "pages", ()) or ())
        return ParseResult(text=text, pages=pages, parser=self.name)

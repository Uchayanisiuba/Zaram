"""PDF text extraction with pypdf.

Text layer only — no OCR, no layout model. Measured against 54 real PDFs on a
working machine, this extracts usable text from 50 of them; the four it cannot
read are image-only scans, which is what the `[ingest]` extra exists for. That
measurement is what makes the extra optional rather than a missing piece: see
`quality.py`.

pypdf is 0.4 MB against Docling's 321 MB of torch, opencv, transformers and
rapidocr, and the packaging reduction those would undo is the single most
consequential thing done for the alpha.
"""

from __future__ import annotations

from pathlib import Path

from ..contracts import ParseResult, ParserUnavailable


class PdfParser:
    suffixes = frozenset({".pdf"})
    name = "pypdf"

    def available(self) -> tuple[bool, str]:
        try:
            import pypdf  # noqa: F401
        except ImportError:
            return False, "PDF reading needs pypdf: pip install pypdf"
        return True, ""

    def parse(self, path: Path) -> ParseResult:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ParserUnavailable(str(exc), "pip install pypdf") from exc

        reader = PdfReader(str(path))

        if reader.is_encrypted:
            # An empty password opens the common "restricted permissions" case.
            # A real password is a hard failure with an honest reason, not an
            # empty extraction that would be graded as a scan.
            try:
                if not reader.decrypt(""):
                    raise ValueError("password-protected")
            except Exception as exc:
                raise ValueError("password-protected") from exc

        parts: list[str] = []
        failed_pages = 0
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                # One malformed page must not cost the whole document. Counted
                # so the outcome can say so rather than under-reporting
                # silently — the failure mode this module exists to prevent.
                failed_pages += 1
                parts.append("")

        detail = {"failed_pages": failed_pages} if failed_pages else {}
        return ParseResult(
            text="\n".join(parts),
            pages=len(reader.pages),
            parser=self.name,
            detail=detail,
        )

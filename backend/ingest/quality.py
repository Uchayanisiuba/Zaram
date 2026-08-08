"""The quality floor: "extracted almost nothing" is a failure, not a success.

A scanned PDF that yields three garbled words silently degrades every answer
that touches it, and it is *worse* than a hard failure because nothing signals
it. So the floor sits beside the error path rather than after it.

Where the numbers come from
---------------------------
Measured, not guessed, against 1,080 real files on a working machine — 54 PDFs,
35 .docx, one .xlsx — using the same dependency-light parsers this module
grades. The distribution that matters, in characters per page across the PDFs:

    0.0, 0.0, 0.0, 0.0, 23.2, 42.2, 98.6, 131.1, 135.8, 147.0, 186.8, 188.3, ...
    median 1468.4

Two things fall out of that, and the second is the one that stops this being a
guessed constant.

**Zero is unambiguous.** Four files produced no characters at all. Every one was
an image-only scan — ~1,000 KB per page, no text layer. There is no document
for which zero extracted characters is a correct result, so EMPTY needs no
threshold and can never produce a false positive.

**The band above zero is not.** The temptation is to draw the line somewhere
around 200 chars/page, because that is where the distribution thins. Measuring
says don't: of the twelve files under 200, the ones between 98 and 190 are
*legitimately sparse documents* — a pitch deck at 98.6, a cast sheet at 186.8, a
treatment at 135.8. They are image-heavy by design and the extraction is
correct. A floor at 200 would reject real material and tell the user their own
pitch deck was unreadable.

The two below 50 are different in kind: a signed NDA yielding 169 characters
across four pages, and a look document yielding 116 across five. Those are scans
carrying an incidental text stamp, not documents.

So the floor is **50 characters per page**, which is the only place in the
measured distribution where the two populations separate, and it *warns* rather
than rejects — SPARSE content is still indexed. Rejecting it would make the
floor a second, quieter way to lose a file, which is the failure this whole
module exists to prevent.

Re-measure with `scratchpad/probe_extraction.py` if the parser set changes.
These numbers describe pypdf's extraction, not PDFs in general: a different
extractor has a different distribution and needs a different floor.
"""

from __future__ import annotations

import os

from .contracts import IngestStatus, ParseResult

#: Below this many characters per page, a paged document is probably a scan.
#: See the module docstring for the measurement. Overridable because the number
#: is a property of the extractor, not of documents.
MIN_CHARS_PER_PAGE = float(os.getenv("ZARAM_MIN_CHARS_PER_PAGE", "50"))

#: For formats with no page count (.docx, .txt, .md), the same question has to
#: be asked of the whole file. A document with under this many characters is
#: not necessarily broken — a one-line note is a real note — so this is
#: deliberately low and catches only near-empty output.
MIN_CHARS_UNPAGED = int(os.getenv("ZARAM_MIN_CHARS_UNPAGED", "16"))

#: A scan is a big file with no text. Used only to explain *why* a file was
#: empty, never to decide that it was — the decision is `chars == 0`, which
#: needs no heuristic.
LIKELY_SCAN_KB_PER_PAGE = 200.0


def grade(result: ParseResult, size_bytes: int = 0) -> tuple[IngestStatus, str, str]:
    """Grade one parse. Returns (status, reason, remedy).

    `reason` and `remedy` are written for a person and go straight to Knowledge.
    Both are empty when the file is fine.
    """
    if result.chars == 0:
        return IngestStatus.EMPTY, _empty_reason(result, size_bytes), _ocr_remedy()

    if result.pages:
        per_page = result.chars_per_page or 0.0
        if per_page < MIN_CHARS_PER_PAGE:
            reason = (
                f"{_plural(result.pages, 'page')} produced only "
                f"{_plural(result.chars, 'character')} ({_rate(per_page)} per page). "
                f"It is probably a scan with a little text on top."
            )
            return IngestStatus.SPARSE, reason, _ocr_remedy()
        return IngestStatus.INDEXED, "", ""

    if result.chars < MIN_CHARS_UNPAGED:
        reason = f"Only {_plural(result.chars, 'character')} came out of the whole file."
        return IngestStatus.SPARSE, reason, ""

    return IngestStatus.INDEXED, "", ""


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _rate(value: float) -> str:
    """Never round a non-zero rate to "0".

    A scan yielding one stray character across two pages was reported as "0 per
    page" while being graded SPARSE rather than EMPTY, which reads as a
    contradiction — the user is told nothing came out and then told it was
    indexed anyway.
    """
    if value == 0:
        return "0"
    return f"{value:.1f}" if value < 10 else f"{value:.0f}"


def _empty_reason(result: ParseResult, size_bytes: int) -> str:
    if result.pages:
        kb_per_page = (size_bytes / 1024) / result.pages if size_bytes else 0.0
        if kb_per_page >= LIKELY_SCAN_KB_PER_PAGE:
            return (
                f"No text layer — {result.pages} pages of images "
                f"({kb_per_page:.0f} KB per page). It is a scan or a photo."
            )
        return f"No text came out of its {result.pages} pages."
    return "No text came out of the file."


def _ocr_remedy() -> str:
    """Named fix and its cost, in the same shape as the voice extra.

    Naming the size matters as much as naming the command. "Install the extra"
    on a metered connection is a decision the user cannot make without the
    number, and a 321 MB surprise mid-download is how trust goes.
    """
    from .parsers import ocr_available

    if ocr_available():
        return "Reading it with OCR needs a parser that failed here — retry, or open the file to check it."
    return "Reading scans needs OCR: pip install zaram[ingest] (321 MB, one time)."

"""Turning an uploaded file into the two things `template_profile` reads.

`extract_template_profile` takes `text` and `images` rather than a file, and its
module docstring says why: *".docx and PDF supply those differently and both
plug into one interface, which is the same arrangement the ingest parsers
already use so the library underneath stays replaceable."* This is that
interface. It did not exist, which is a large part of why 400 tested lines sat
with no caller for weeks — the function was unreachable because nothing could
produce its arguments.

**Text comes from the ingest parsers, not from a second extractor here.** They
already read `.docx` paragraphs *and tables* — a distinction that matters
exactly here, since an invoice keeps its terms in a table and a reader that
skipped them would propose a letterhead with no payment terms. A second
extractor in this file would be the two-TTS-cleaners and two-rankers mistake
again, and it would diverge in the direction that is hardest to notice: quietly
reading slightly less.

**Images are this module's own work**, because the parser contract returns
`ParseResult(text=...)` and has nowhere to put them. Widening that protocol
would touch every parser and the ingest pipeline for the benefit of one caller;
opening the file a second time costs a few milliseconds on a path a person runs
once.

**Format is decided by the bytes, never by the filename.** The name comes from
whatever uploaded it and can say anything; `PK` and `%PDF` cannot. A `.pdf`
that is really a zip must not be handed to the PDF reader, and the failure of
guessing wrong here is an exception in front of a user during onboarding.

Rule 7c holds without a special case: nothing here leaves the machine, and the
libraries are the ones already vendored for ingestion.
"""

from __future__ import annotations

import logging
import os
import tempfile
import zipfile
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

#: Extensions inside a `.docx` zip, mapped to what they actually are.
#:
#: Only the three `logo_data_uri` accepts. Word also embeds EMF and WMF —
#: Windows metafiles, usually a vector logo pasted from another Office app —
#: and they are left out rather than passed through as a guessed type: the
#: validator would refuse them anyway, and refusing them *here* with no reason
#: would be worse than the message it writes.
_DOCX_IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

#: The largest upload read. A template is one document somebody already sends,
#: so this is generous; it exists because the whole file is held in memory and
#: an unbounded upload is a way to stop the backend from a route that takes
#: files.
MAX_TEMPLATE_BYTES = 20 * 1024 * 1024

#: How many embedded images are offered as logo candidates.
#:
#: `_extract_logo` takes the first usable one, so the order matters more than
#: the count — and in a `.docx` the media parts are numbered in the order Word
#: added them, which puts a masthead logo first far more often than not. The
#: cap is here so a photo-heavy document does not turn one upload into fifty
#: base64 encodings.
MAX_IMAGE_CANDIDATES = 12


class UnreadableTemplate(ValueError):
    """The upload cannot be read, with a reason written for the user."""


def looks_like(data: bytes) -> str:
    """``"docx"``, ``"pdf"`` or ``""``, from the bytes themselves."""
    if data[:4] == b"%PDF":
        return "pdf"
    # Every OOXML file is a zip. Whether it is *Word* is settled by looking for
    # the part, below, rather than by trusting the extension.
    if data[:2] == b"PK":
        return "docx"
    return ""


def read_template(data: bytes, *, filename: str = "") -> Tuple[str, List[Tuple[bytes, str]]]:
    """``(text, images)`` for `extract_template_profile`.

    `filename` is used only in messages, never to decide the format — see the
    module docstring.
    """
    if not data:
        raise UnreadableTemplate("That file is empty.")
    if len(data) > MAX_TEMPLATE_BYTES:
        raise UnreadableTemplate(
            f"That file is {len(data) / 1024 / 1024:.0f} MB. The limit is "
            f"{MAX_TEMPLATE_BYTES // 1024 // 1024} MB — Zaram only needs one "
            "document to read your letterhead from."
        )

    kind = looks_like(data)
    if not kind:
        raise UnreadableTemplate(
            "Zaram can read a Word document or a PDF here. "
            f"{filename or 'That file'} is neither."
        )

    # A real file on disk, because both the ingest parsers and pypdf take a
    # path, and because a 20 MB document held twice in memory is worth avoiding
    # on a machine that is also holding a language model.
    handle, path = tempfile.mkstemp(suffix=".docx" if kind == "docx" else ".pdf")
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(data)
        text = _text_of(Path(path), kind)
        images = _images_of(Path(path), kind)
    finally:
        # A template is somebody's invoice. It does not linger in the temp
        # directory after the one read it was uploaded for.
        try:
            os.unlink(path)
        except OSError:
            logger.warning("could not remove the temporary template file")

    if not text.strip() and not images:
        raise UnreadableTemplate(
            "Zaram could not read any text or images out of that file. If it is "
            "a scan, there is nothing to read here yet — reading scans needs OCR."
        )
    return text, images


def _text_of(path: Path, kind: str) -> str:
    """The ingest parsers' answer, unchanged.

    Their failures are passed through as-is: `ParserUnavailable` already names
    the missing library and the command that installs it, and rewording it here
    would lose the command.
    """
    from ingest.parsers.office import DocxParser
    from ingest.parsers.pdf import PdfParser

    parser = DocxParser() if kind == "docx" else PdfParser()
    available, reason = parser.available()
    if not available:
        raise UnreadableTemplate(reason)
    try:
        return parser.parse(path).text
    except UnreadableTemplate:
        raise
    except Exception as exc:
        raise UnreadableTemplate(str(exc) or "That file could not be read.") from exc


def _images_of(path: Path, kind: str) -> List[Tuple[bytes, str]]:
    """Embedded images, best effort.

    **Best effort on purpose: a document with no readable image is not a failed
    upload.** `_extract_logo` already has a written sentence for that case —
    *"I couldn't find a logo in this document"* — and reaching it is a better
    outcome than an exception, because the rest of the proposal (name, address,
    terms) is still worth showing.
    """
    try:
        return _docx_images(path) if kind == "docx" else _pdf_images(path)
    except Exception:
        logger.info("no images could be read from the template", exc_info=True)
        return []


def _docx_images(path: Path) -> List[Tuple[bytes, str]]:
    """Everything under `word/media/`, in the order Word stored it."""
    found: List[Tuple[bytes, str]] = []
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.startswith("word/media/")]
        if not names and not any(n.startswith("word/") for n in archive.namelist()):
            # A zip that is not a Word document at all — an .xlsx, a .zip
            # someone renamed. Says so rather than returning nothing, because
            # "no logo found" would be the wrong explanation entirely.
            raise UnreadableTemplate(
                "That looks like a zip file rather than a Word document."
            )
        for name in sorted(names):
            content_type = _DOCX_IMAGE_TYPES.get(Path(name).suffix.lower())
            if not content_type:
                continue
            found.append((archive.read(name), content_type))
            if len(found) >= MAX_IMAGE_CANDIDATES:
                break
    return found


def _pdf_images(path: Path) -> List[Tuple[bytes, str]]:
    """Embedded images from the first pages.

    **First pages only, and that is a judgement rather than a shortcut.** A
    letterhead is at the top of page one. Reading every page of a long document
    would offer a logo candidate list dominated by whatever is in the body, and
    `_extract_logo` takes the *first usable* candidate — so more pages would
    make the answer worse as well as slower.
    """
    from pypdf import PdfReader

    found: List[Tuple[bytes, str]] = []
    reader = PdfReader(str(path))
    for page in reader.pages[:2]:
        for image in page.images:
            data = image.data
            # pypdf names the extracted part; its extension is the honest
            # source for what the bytes are.
            content_type = _DOCX_IMAGE_TYPES.get(Path(image.name or "").suffix.lower())
            if not content_type or not data:
                continue
            found.append((data, content_type))
            if len(found) >= MAX_IMAGE_CANDIDATES:
                return found
    return found

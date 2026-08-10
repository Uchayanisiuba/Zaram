"""Ingest: a folder of the user's own documents into the Spine.

Rule 7c binds this whole package: **no ingestion path may route documents
off-device.** Managed parsing APIs are prohibited regardless of quality gains —
this is the exact trade the product refuses, and it is enforced by
`test_ingest_stays_local.py` rather than by convention.
"""

from .contracts import (
    IngestOutcome,
    IngestReport,
    IngestStatus,
    ParseResult,
    ParserUnavailable,
)
from .parsers import formats, ocr_available, supported_suffixes
from .quality import MIN_CHARS_PER_PAGE, grade
from .service import chunk, discover, ingest_folder, parse_file

__all__ = [
    "MIN_CHARS_PER_PAGE",
    "IngestOutcome",
    "IngestReport",
    "IngestStatus",
    "ParseResult",
    "ParserUnavailable",
    "chunk",
    "discover",
    "formats",
    "grade",
    "ingest_folder",
    "ocr_available",
    "parse_file",
    "supported_suffixes",
]

"""Folder in, facts out — and every file that gave nothing back, named.

The shape of this module is set by one rule from the milestone: **failures must
be loud**. A file that produced nothing appears in Knowledge with a reason and a
retry, and is mentioned in the conversation the first time it matters. So the
walk never stops on an error, never swallows one, and returns an outcome for
every file it looked at rather than only the ones that worked.

Rule 7c: no ingestion path may route documents off-device. Parsing is local,
embedding is Ollama on loopback, and `test_ingest_stays_local.py` enforces it by
scanning this package.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence

from .contracts import (
    IngestOutcome,
    IngestReport,
    IngestStatus,
    ParserUnavailable,
    ParseResult,
)
from .parsers import parsers_for, supported_suffixes
from .quality import grade

logger = logging.getLogger(__name__)

#: Directories never worth walking into. Not a security boundary — a folder
#: chosen by the user is trusted — just noise that would otherwise dominate a
#: developer's own machine and index nothing anyone asked about.
SKIP_DIRS = frozenset({
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".idea", ".vscode", "dist", "build",
    "$RECYCLE.BIN", "System Volume Information",
})

#: Files that are Office's lock artefacts rather than documents. `~$name.docx`
#: is written while a file is open and is never readable.
SKIP_PREFIXES = ("~$", ".~")

#: Chunk size for turning a document into facts. Characters, not tokens: the
#: embedder is the authority on tokens and this only has to be stable.
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 150


def discover(root: Path, *, follow_symlinks: bool = False) -> list[Path]:
    """Every file under `root` some installed parser can read.

    Sorted, so two runs over an unchanged folder produce the same order and a
    diff between them means something.
    """
    supported = supported_suffixes()
    found: list[Path] = []
    for path in _walk(root, follow_symlinks=follow_symlinks):
        if path.name.startswith(SKIP_PREFIXES):
            continue
        if path.suffix.lower() in supported:
            found.append(path)
    return sorted(found)


def _walk(root: Path, *, follow_symlinks: bool) -> Iterator[Path]:
    import os

    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            yield Path(dirpath) / name


def parse_file(path: Path) -> tuple[ParseResult | None, str, str]:
    """Parse one file. Returns (result, reason, remedy).

    `result` is None only when nothing could read it. Parsers are tried in
    registry order and the first that produces *any* text wins — which is how
    Docling becomes the fallback for a scan without changing how a text-layer
    PDF is read.
    """
    candidates = parsers_for(path.suffix)
    if not candidates:
        return None, f"No parser handles {path.suffix or 'files without a suffix'}.", ""

    #: An empty parse is a real answer — it is what a scan looks like — but a
    #: later parser may still find text, so it is held rather than returned.
    empty_result: ParseResult | None = None
    failure_reason = ""
    remedy = ""

    for parser in candidates:
        available, parser_remedy = parser.available()
        if not available:
            remedy = remedy or parser_remedy
            continue
        try:
            result = parser.parse(path)
        except ParserUnavailable as exc:
            remedy = remedy or exc.remedy
            continue
        except Exception as exc:
            # Recorded, not raised: one unreadable file must not end the walk,
            # and the reason has to survive to reach Knowledge. A later parser
            # succeeding overwrites this; nothing else does.
            failure_reason = _humanise(exc)
            logger.info("Ingest: %s could not read %s: %s", parser.name, path.name, exc)
            continue

        if result.chars > 0:
            return result, "", ""
        empty_result = empty_result or result

    if empty_result is not None:
        # Parsed fine, found nothing. The quality floor grades this as EMPTY
        # and names the remedy; it is not a failure to open the file.
        return empty_result, "", remedy
    if failure_reason:
        return None, failure_reason, remedy
    return None, "Nothing installed can read this file.", remedy


def _humanise(exc: Exception) -> str:
    """A reason a person can act on, not a traceback.

    `ValueError("password-protected")` is raised by the parsers precisely so it
    can pass through as the message.
    """
    message = str(exc).strip()
    if isinstance(exc, ValueError) and message:
        return message[0].upper() + message[1:] + "."
    if isinstance(exc, (FileNotFoundError, PermissionError)):
        return "The file could not be opened — it may have moved or be in use."
    return f"Could not be read ({type(exc).__name__})."


def chunk(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split on paragraph boundaries where possible, hard-split where not.

    Overlap exists so a sentence spanning a boundary is retrievable from either
    side; without it a fact that straddles the split is findable from neither.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # Prefer a paragraph break, then a sentence end, then wherever.
            window = text[start:end]
            for sep in ("\n\n", "\n", ". "):
                cut = window.rfind(sep)
                if cut > size // 2:
                    end = start + cut + len(sep)
                    break
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def iter_ingest_folder(
    root: str | Path,
    *,
    store_fact: Callable[[str, dict[str, Any]], str] | None = None,
    read_obligations: Callable[[str, Path], None] | None = None,
    paths: Sequence[Path] | None = None,
) -> Iterator[IngestOutcome]:
    """Ingest `root`, yielding each file's outcome as it is finished.

    A generator rather than a callback because progress has to be *real*.
    Collecting every outcome and then replaying them down a stream produces a
    progress bar that is always complete before it is shown, which is the same
    class of thing as a status indicator over hardcoded data.

    The caller gets one event per file, in the order they were read, while the
    walk is still going.
    """
    root = Path(root)
    files = list(paths) if paths is not None else discover(root)
    for path in files:
        yield _ingest_one(path, store_fact, read_obligations)


def ingest_folder(
    root: str | Path,
    *,
    store_fact: Callable[[str, dict[str, Any]], str] | None = None,
    read_obligations: Callable[[str, Path], None] | None = None,
    on_outcome: Callable[[IngestOutcome], None] | None = None,
    paths: Sequence[Path] | None = None,
) -> IngestReport:
    """Walk `root`, parse everything readable, and record what happened to all of it.

    `store_fact(text, metadata) -> fact_id` is injected rather than imported so
    this module can be tested without a Spine, and so the caller decides what
    "a fact" means. Passing None parses and grades without storing, which is
    what a dry run wants.

    `on_outcome` fires per file as it completes. Use `iter_ingest_folder`
    directly when the caller is itself a stream.
    """
    root = Path(root)
    started = time.perf_counter()
    outcomes: list[IngestOutcome] = []

    for outcome in iter_ingest_folder(
        root, store_fact=store_fact, read_obligations=read_obligations, paths=paths
    ):
        outcomes.append(outcome)
        if on_outcome is not None:
            try:
                on_outcome(outcome)
            except Exception:
                # A progress callback must never cost the ingest.
                logger.warning("Ingest: progress callback failed", exc_info=True)

    report = IngestReport(
        root=str(root), outcomes=tuple(outcomes), seconds=time.perf_counter() - started
    )
    logger.info(
        "Ingest: %s — %d files, %d indexed, %d needing attention",
        root,
        len(report.outcomes),
        report.count(IngestStatus.INDEXED),
        len(report.problems),
    )
    return report


def _ingest_one(
    path: Path,
    store_fact: Callable[[str, dict[str, Any]], str] | None,
    read_obligations: Callable[[str, Path], None] | None = None,
) -> IngestOutcome:
    started = time.perf_counter()
    try:
        size_bytes = path.stat().st_size
    except OSError:
        size_bytes = 0

    result, reason, remedy = parse_file(path)

    if result is None:
        status = IngestStatus.UNSUPPORTED if not reason or "No parser handles" in reason else IngestStatus.FAILED
        return IngestOutcome(
            path=str(path),
            status=status,
            reason=reason,
            remedy=remedy,
            seconds=time.perf_counter() - started,
        )

    status, quality_reason, quality_remedy = grade(result, size_bytes)

    fact_ids: tuple[str, ...] = ()
    if store_fact is not None and status in {IngestStatus.INDEXED, IngestStatus.SPARSE}:
        # SPARSE is indexed too. Withholding it would make the quality floor a
        # second, quieter way to lose a file — the exact failure this module
        # exists to prevent. It is flagged, not suppressed.
        fact_ids = _store_chunks(path, result, store_fact)

    # Obligations are read from the **whole document**, not from the chunks.
    #
    # A clause is a sentence and `chunk()` splits on size, so a payment term
    # can land across a boundary — and half of "payment is due within 30 days
    # of the invoice date" is not a commitment, it is a fragment. The chunks
    # exist so recall can retrieve a passage; a deadline has to be read from
    # the text the parser produced.
    #
    # Injected rather than imported, like `store_fact` above and for the same
    # reason: this module stays testable without a Spine or an obligations
    # database, and the caller decides what storing one means.
    if read_obligations is not None and status in {
        IngestStatus.INDEXED,
        IngestStatus.SPARSE,
    }:
        try:
            read_obligations(result.text, path)
        except Exception:
            # A commitment Zaram failed to read is bad; a document Zaram failed
            # to *ingest* because it could not read a commitment is worse. The
            # file is already parsed, graded and indexed by this point.
            logger.exception("Ingest: obligation extraction failed for %s", path.name)

    return IngestOutcome(
        path=str(path),
        status=status,
        parser=result.parser,
        chars=result.chars,
        pages=result.pages,
        fact_ids=fact_ids,
        reason=quality_reason,
        remedy=quality_remedy,
        seconds=time.perf_counter() - started,
    )


def _store_chunks(
    path: Path, result: ParseResult, store_fact: Callable[[str, dict[str, Any]], str]
) -> tuple[str, ...]:
    ids: list[str] = []
    pieces = chunk(result.text)
    for index, piece in enumerate(pieces):
        metadata = {
            "source_path": str(path),
            "source_name": path.name,
            # Rule 7b: every fact carries its origin. A passage from a file the
            # user wrote is not the same kind of thing as one Zaram generated,
            # and recall has to be able to say which.
            "origin": "user_document",
            "parser": result.parser,
            "chunk_index": index,
            "chunk_count": len(pieces),
        }
        try:
            ids.append(store_fact(piece, metadata))
        except Exception:
            # A storage failure on one chunk is worth knowing about and is not
            # worth losing the rest of the document over.
            logger.warning("Ingest: could not store chunk %d of %s", index, path.name, exc_info=True)
    return tuple(ids)

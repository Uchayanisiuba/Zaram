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
import re
import time
from dataclasses import dataclass
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
from .parsers.code import CodeParser
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


#: Lines that begin a definition, in the languages `CodeParser` claims.
#:
#: Deliberately anchored near the left margin and deliberately incomplete. This
#: is not a parser and must not grow into one — a real grammar per language is
#: a dependency and a maintenance obligation, and the cost of *missing* a
#: boundary here is small: the chunk falls back to splitting on lines, which is
#: still whole lines and still numbered. The cost of a wrong boundary is the
#: same. So patterns are added only when they are unambiguous.
_DEFINITIONS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^[ \t]{0,4}(?:async[ \t]+)?def[ \t]+(?P<name>\w+)"),
    re.compile(r"^[ \t]{0,4}(?:export[ \t]+)?(?:abstract[ \t]+)?class[ \t]+(?P<name>\w+)"),
    re.compile(
        r"^[ \t]{0,4}(?:export[ \t]+)?(?:default[ \t]+)?(?:async[ \t]+)?"
        r"function[ \t]+(?P<name>\w+)"
    ),
    re.compile(
        r"^[ \t]{0,4}(?:export[ \t]+)?(?:const|let|var)[ \t]+(?P<name>\w+)"
        r"[ \t]*(?::[^=]+)?=[ \t]*(?:async[ \t]*)?(?:\([^)]*\)|\w+)[ \t]*=>"
    ),
    re.compile(r"^[ \t]{0,4}(?:pub[ \t]+)?(?:async[ \t]+)?fn[ \t]+(?P<name>\w+)"),
    re.compile(r"^[ \t]{0,4}func[ \t]+(?:\([^)]*\)[ \t]*)?(?P<name>\w+)"),
    re.compile(
        r"^[ \t]{0,4}(?:export[ \t]+)?(?:interface|type|enum|struct|impl|trait)"
        r"[ \t]+(?P<name>\w+)"
    ),
)


@dataclass(frozen=True)
class CodeChunk:
    """One retrievable piece of source, and where it came from.

    The line range is the reason this type exists rather than a bare string.
    Rule 2 says every recalled fact carries provenance, and for prose the file
    name is enough — for code it is not. *"`readiness.py`, somewhere"* cannot
    be checked; **`readiness.py:156-181`** can be opened, and an agent editing
    the file needs the range to know what it is replacing.
    """

    text: str
    #: 1-based and inclusive, the way an editor counts and a person reads.
    start_line: int
    end_line: int
    #: Every definition this passage contains, in order. A tuple rather than a
    #: single name because small definitions are merged into one chunk, and
    #: labelling a passage that holds `first`, `second` and `Holder` with only
    #: the first of them is a caption that is wrong about its own contents.
    #: Empty for a file's header, or a language none of the patterns match.
    symbols: tuple[str, ...] = ()

    @property
    def citation(self) -> str:
        """`120-168`, for a caller to prefix with the file name."""
        return f"{self.start_line}-{self.end_line}"


def chunk_code(text: str, size: int = CHUNK_CHARS) -> list[CodeChunk]:
    """Split source into pieces a model can be handed one at a time.

    Three properties, and each is a thing `chunk()` gets right for prose and
    wrong for code.

    **Never split mid-line.** A chunk ending halfway through `if user.is_admin`
    is not shorter, it is wrong — and a model reading it will complete the
    thought itself, which is rule 9's failure with a syntax error attached.

    **Prefer a whole definition.** Boundaries come from `_DEFINITIONS`, so a
    function that fits arrives whole, with its signature. A retrieved body with
    no `def` line above it is anonymous, and the model has to guess what it was
    reading.

    **No overlap, unlike prose.** `chunk()` overlaps so a sentence spanning a
    boundary stays findable from both sides. Code is already aligned to
    structure, and overlapping would put the same function in two facts —
    which is the duplicate-citation failure rule 7d exists to prevent, arriving
    through the chunker instead of through the session store.

    A definition longer than ``size`` is split on line boundaries into as many
    pieces as it needs. Every piece keeps the same symbols, so a 400-line
    function retrieved in the middle still says which function it is.
    """
    lines = text.splitlines()
    if not lines:
        return []

    segments = _segments(lines)

    chunks: list[CodeChunk] = []
    for start, end, symbols in segments:
        body = "\n".join(lines[start:end])
        if len(body) <= size:
            if body.strip():
                chunks.append(
                    CodeChunk(text=body, start_line=start + 1, end_line=end, symbols=symbols)
                )
            continue

        # Too long to hand over whole. Split it on lines, never inside one.
        piece_start = start
        length = 0
        for index in range(start, end):
            line_len = len(lines[index]) + 1
            if length + line_len > size and index > piece_start:
                body = "\n".join(lines[piece_start:index])
                if body.strip():
                    chunks.append(
                        CodeChunk(
                            text=body,
                            start_line=piece_start + 1,
                            end_line=index,
                            symbols=symbols,
                        )
                    )
                piece_start = index
                length = 0
            length += line_len

        tail = "\n".join(lines[piece_start:end])
        if tail.strip():
            chunks.append(
                CodeChunk(text=tail, start_line=piece_start + 1, end_line=end, symbols=symbols)
            )

    return chunks


def _segments(lines: list[str]) -> list[tuple[int, int, tuple[str, ...]]]:
    """`(start, end, symbols)` per definition, packed up to the chunk size.

    Small adjacent definitions are merged rather than stored one per fact: a
    file of six one-line getters should be one retrievable passage, not six
    facts that each answer nothing and all compete for the same slot.
    """
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        for pattern in _DEFINITIONS:
            found = pattern.match(line)
            if found:
                starts.append((index, found.group("name")))
                break

    if not starts:
        return [(0, len(lines), "")]

    # Whatever precedes the first definition is its own segment: imports, the
    # licence header, the module docstring. That is often the most useful
    # passage in the file and it belongs to no function.
    boundaries: list[tuple[int, str]] = []
    if starts[0][0] > 0:
        boundaries.append((0, ""))
    boundaries.extend(starts)

    segments: list[tuple[int, int, tuple[str, ...]]] = []
    for position, (start, symbol) in enumerate(boundaries):
        end = boundaries[position + 1][0] if position + 1 < len(boundaries) else len(lines)
        segments.append((start, end, (symbol,) if symbol else ()))

    # Merge forwards while the result still fits.
    merged: list[tuple[int, int, tuple[str, ...]]] = []
    for segment in segments:
        if not merged:
            merged.append(segment)
            continue
        start, _end, symbols = merged[-1]
        combined = sum(len(line) + 1 for line in lines[start:segment[1]])
        if combined <= CHUNK_CHARS:
            # The merged passage names everything inside it, so a chunk holding
            # three short functions is captioned with all three.
            merged[-1] = (start, segment[1], symbols + segment[2])
        else:
            merged.append(segment)
    return merged


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

    # Which chunker runs is decided by the parser that read the file, not by
    # the suffix. One place makes the decision, and adding a suffix to
    # `CodeParser` is then enough to route it correctly here.
    if result.parser == CodeParser.name:
        pieces = [
            (piece.text, {
                "start_line": piece.start_line,
                "end_line": piece.end_line,
                "symbols": list(piece.symbols),
            })
            for piece in chunk_code(result.text)
        ]
    else:
        pieces = [(piece, {}) for piece in chunk(result.text)]

    for index, (piece, located) in enumerate(pieces):
        metadata = {
            "source_path": str(path),
            "source_name": path.name,
            # Where in the file, for code. Absent for prose, where the file
            # name is provenance enough and a line number would be invented.
            **located,
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

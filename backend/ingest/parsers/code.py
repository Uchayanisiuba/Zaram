"""Source files. No dependency, and the reason it is separate from plaintext.

A repository pointed at Knowledge today indexes its README and skips every
file the project is actually made of — `PlainTextParser` claims `.md`, `.json`
and `.yaml`, and nothing claims `.py`, `.ts` or `.go`. So "ask Zaram about this
codebase" retrieved documentation and never code, which looks like weak recall
and is actually an empty index.

**Separate from plaintext because the chunker has to know.** Reading the bytes
is identical — both are UTF-8 text with no library between them — but a
paragraph chunker splitting source at 1,200 characters cuts through the middle
of a function, and the retrieved half arrives with no signature, no imports and
no line numbers. `service.chunk_code` exists for that, and it is selected by
`ParseResult.parser`, so this class earning its own name is what routes a file
to the right chunker.

**Generated and minified files are refused, with the reason.** A 2 MB bundle on
one line is not a file anyone asks questions about, and chunking it produces a
thousand facts of unreadable noise that then compete with real code for every
retrieval slot. This is the one place ingestion is allowed an opinion about
content, and it says so out loud rather than silently skipping — an invisible
skip is the failure `IngestStatus` was built to prevent.

**Suffixes claimed by `PlainTextParser` are deliberately not claimed here.**
`.json`, `.yaml`, `.md` and `.csv` are config and prose more often than they
are source, resolution is by suffix and order, and two parsers claiming one
suffix is an ambiguity nobody needs.
"""

from __future__ import annotations

from pathlib import Path

from ..contracts import ParseResult

#: Above this mean line length a file is machine-written, not hand-written.
#: Measured against real minified output: a webpack bundle averages thousands
#: of characters per line, while the widest hand-written source in this
#: repository averages well under two hundred.
MEAN_LINE_CHARS_GENERATED = 400

#: Below this the mean tells you nothing — a short file of long strings is
#: still a file someone wrote.
MIN_CHARS_TO_JUDGE = 50_000


class CodeParser:
    """Source text, as written."""

    suffixes = frozenset({
        # The languages this product is written in come first, because they are
        # the ones the maintainer will point it at.
        ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
        # Then everything a user might reasonably keep in a repository.
        ".go", ".rs", ".java", ".kt", ".kts", ".swift", ".scala",
        ".c", ".h", ".cpp", ".cc", ".hpp", ".cs",
        ".rb", ".php", ".lua", ".pl", ".r",
        ".sh", ".bash", ".zsh", ".ps1", ".bat",
        ".sql", ".graphql", ".proto",
        ".html", ".css", ".scss", ".sass", ".less",
        ".vue", ".svelte", ".astro",
        ".toml", ".ini", ".cfg", ".env",
    })
    name = "code"

    def available(self) -> tuple[bool, str]:
        return True, ""

    def parse(self, path: Path) -> ParseResult:
        # `errors="replace"` for the same reason plaintext uses it: a few bad
        # bytes should not lose the file, and a replacement character is
        # visible where a dropped byte is not.
        text = path.read_text(encoding="utf-8", errors="replace")

        generated, why = looks_generated(text)
        if generated:
            # ValueError, because `service._humanise` passes its message
            # through to the user unchanged. This is the one refusal in
            # ingestion that is about content rather than about failure, and
            # the user is owed the reason in a sentence they can act on.
            raise ValueError(why)

        return ParseResult(
            text=text,
            pages=0,
            parser=self.name,
            detail={"language": path.suffix.lower().lstrip("."), "lines": text.count("\n") + 1},
        )


def looks_generated(text: str) -> tuple[bool, str]:
    """Whether this is machine output rather than something a person wrote.

    Returns the reason as well as the verdict, because the caller shows it.
    Deliberately conservative: a false positive loses a real file, which is
    worse than indexing one bundle.
    """
    if len(text) < MIN_CHARS_TO_JUDGE:
        return False, ""

    lines = text.count("\n") + 1
    mean = len(text) / lines
    if mean < MEAN_LINE_CHARS_GENERATED:
        return False, ""

    return True, (
        f"this looks generated or minified — {lines:,} lines averaging "
        f"{mean:,.0f} characters, where hand-written source averages under 200. "
        "Indexing it would fill your Spine with text nobody asks questions about"
    )

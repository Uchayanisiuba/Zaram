"""A repository in a thousand tokens: which files exist and what they define.

Taken from Aider, 12 September 2026
-----------------------------------
Aider's single best idea is the **repo map**: before the model reads anything,
it is shown the shape of the repository — every file worth knowing about and
the symbols it defines — squeezed to a token budget and ranked so the parts
relevant to the question come first. That is how a 16K-window model working
through 400-line reads finds the right file on the first call instead of the
third, and it is the difference between an agent that feels like it knows the
codebase and one that is searching a stranger's disk.

What is taken and what is not
-----------------------------
Aider ranks with PageRank over a tree-sitter symbol graph. Neither dependency
is taken. `ingest.service._DEFINITIONS` already finds definitions with
anchored regexes — deliberately not a parser, and the reasons recorded there
hold here — and the ranking is **lexical overlap with the question**, which
is `CLAUDE.md`'s own argument about rare tokens: a client name or a symbol in
a question is what a lexical match is best at and an embedding worst at. A
file whose path or definitions share a token with the question ranks first;
ties go to shallower paths, because `src/app.py` is more likely the point than
`src/vendor/x/y/z.py`.

Budgeted and cached
-------------------
The map is trimmed to ``budget_tokens`` by dropping the lowest-ranked files
whole, and says how many it dropped — a model told the map is complete
concludes a file it cannot see does not exist. The symbol table is cached per
root for `CACHE_SECONDS`, because walking a repository on every request is a
cost a chat should not pay twice a minute; the *ranking* is per question and
is cheap.

**A path or a symbol is text the user's repository supplied.** It goes into
the prompt before the tool rules, so the last thing the model reads is still
the rule — the same ordering `tool_instructions` and `identity_preamble` keep.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from core.context_budget import estimate_tokens
from ingest.parsers.code import CodeParser
from ingest.service import SKIP_DIRS, _DEFINITIONS

#: How long a walked symbol table is reused before the repository is read
#: again. Long enough that a tool loop's six rounds share one walk; short
#: enough that a file the user just added appears in the next question.
CACHE_SECONDS = 30.0

#: Files bigger than this are listed by name and not opened for definitions.
#: A minified bundle or a data file yields nothing useful and costs a read.
MAX_SCAN_BYTES = 400_000

#: The most files the map will ever name, before the budget is applied.
MAX_FILES = 400

#: Definitions kept per file. A file with a hundred functions is shown its
#: first twelve and a count; the model can `read_lines` for the rest.
MAX_SYMBOLS_PER_FILE = 12

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9]+|\d{3,}")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|_")


@dataclass(frozen=True)
class FileSymbols:
    path: str
    symbols: Tuple[str, ...]
    depth: int


_cache: Dict[str, Tuple[float, Tuple[FileSymbols, ...]]] = {}


def _tokens(text: str) -> set:
    """Lowercased words, with camelCase and snake_case split so `chunkCode`
    matches "chunk" — the same lesson `content_tokens` learned in slice 2."""
    out = set()
    for word in _TOKEN.findall(text):
        out.add(word.lower())
        for part in _CAMEL.split(word):
            if len(part) > 2:
                out.add(part.lower())
    return out


def _walk(root: Path) -> Tuple[FileSymbols, ...]:
    resolved = root.resolve()
    found: List[FileSymbols] = []
    for dirpath, dirnames, filenames in os.walk(resolved):
        dirnames[:] = sorted(
            d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
        )
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if path.suffix.lower() not in CodeParser.suffixes:
                continue
            relative = path.relative_to(resolved).as_posix()
            symbols: List[str] = []
            try:
                if path.stat().st_size <= MAX_SCAN_BYTES:
                    with path.open("r", encoding="utf-8", errors="replace") as handle:
                        for line in handle:
                            for pattern in _DEFINITIONS:
                                match = pattern.match(line)
                                if match:
                                    symbols.append(match.group("name"))
                                    break
            except OSError:
                # One unreadable file must not lose the map, for the reason
                # one unreadable file does not end a search.
                pass
            found.append(FileSymbols(relative, tuple(symbols), relative.count("/")))
            if len(found) >= MAX_FILES:
                return tuple(found)
    return tuple(found)


def symbols_for(root: Path, *, now: Optional[float] = None) -> Tuple[FileSymbols, ...]:
    """The symbol table for a root, walked at most once per `CACHE_SECONDS`."""
    key = str(root.resolve())
    stamp = time.monotonic() if now is None else now
    cached = _cache.get(key)
    if cached and stamp - cached[0] < CACHE_SECONDS:
        return cached[1]
    table = _walk(root)
    _cache[key] = (stamp, table)
    return table


def forget(root: Optional[Path] = None) -> None:
    """Drop the cache — after a write, so the next map shows the new file."""
    if root is None:
        _cache.clear()
    else:
        _cache.pop(str(root.resolve()), None)


def _rank(table: Sequence[FileSymbols], question: str) -> List[FileSymbols]:
    wanted = _tokens(question)

    def score(entry: FileSymbols) -> Tuple[int, int, str]:
        own = _tokens(entry.path) | _tokens(" ".join(entry.symbols))
        overlap = len(own & wanted)
        # Higher overlap first, then shallower, then alphabetical — a tuple so
        # the order is total and the map is the same for the same question.
        return (-overlap, entry.depth, entry.path)

    return sorted(table, key=score)


def repo_map(root: Path, question: str, *, budget_tokens: int) -> str:
    """The map as prompt text, or ``""`` when there is nothing to show."""
    table = symbols_for(root)
    if not table:
        return ""

    ranked = _rank(table, question)
    lines: List[str] = []
    spent = 0
    shown = 0
    for entry in ranked:
        block = [entry.path]
        if entry.symbols:
            names = list(entry.symbols[:MAX_SYMBOLS_PER_FILE])
            more = len(entry.symbols) - len(names)
            listed = ", ".join(names) + (f", … {more} more" if more > 0 else "")
            block.append(f"  {listed}")
        cost = estimate_tokens("\n".join(block))
        if spent + cost > budget_tokens and shown > 0:
            break
        lines.extend(block)
        spent += cost
        shown += 1

    dropped = len(table) - shown
    header = [
        "",
        "## The open project",
        "",
        "Files in the repository and the definitions in each, most relevant to "
        "the question first. Use `read_lines` to see any of them.",
        "",
    ]
    footer = []
    if dropped > 0:
        footer = ["", f"({dropped} more files not shown; `list_files` or `search_code` will find them)"]
    return "\n".join(header + lines + footer) + "\n"

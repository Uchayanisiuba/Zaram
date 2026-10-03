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
import subprocess
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

#: How long `git ls-files` may take before the walk is used instead. It is
#: one process reading an index and is normally milliseconds; the bound is
#: here so a repository on a stalled network drive degrades to a slower
#: answer rather than hanging a reply.
GIT_TIMEOUT_SECONDS = 5.0

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


#: Lower-cased once, because the comparison below was case-sensitive and the
#: directory it most needed to match is capitalised.
#:
#: Unreal writes its packaged output to `Build/`. `SKIP_DIRS` holds `build`.
#: On Windows the *filesystem* does not care and Python's `in` does, so the
#: whole of a build tree walked straight in — found 3 October 2026 on a real
#: repository, where it was the entire map.
_SKIP_LOWER = frozenset(d.lower() for d in SKIP_DIRS)


def _git_listed(root: Path) -> Optional[List[str]]:
    """What git says the project's files are, or ``None`` if git cannot say.

    **Asked of git rather than guessed from a list of directory names**, for
    the reason `test_no_store_is_one_add_from_being_published.py` gives about
    `.gitignore`: reading it ourselves re-implements the thing that is already
    correct, and a hand-maintained skip list is a denylist — it fails open on
    the next repository that names its build output something new.

    Found 3 October 2026 on a real repository. An Unreal plugin with 1,410
    files on disk and **47 that are actually the project**; the rest is
    packaged output under `Build/` and a test bed, both of them named in the
    author's own `.gitignore`. The map showed 37 files, all 37 from `Build/`,
    triplicated across three packaged copies — no source, no `Docs/`, no
    `README.md`. Asked to audit the project, the model said it had not been
    given the project, **and it was right**.

    Two defects stacked to produce that. `Build` did not match `build`, so the
    tree was walked; and `_walk` stops at `MAX_FILES` in alphabetical order,
    so the budget was spent before the walk reached `Docs/`, `Keyline/` or
    `README.md`. The second is the membership-versus-ordering error again, in
    a new place: which files the model may see was decided by which directory
    sorts first.

    `--cached --others --exclude-standard` is tracked files plus untracked
    ones that are not ignored — the honest answer to *"what is this project"*.
    Tracked alone would hide a file written five minutes ago, which on a
    coding project is the file most likely to be the question.

    Returns ``None`` rather than an empty list when git cannot answer, because
    *"not a git repository"* and *"a repository with no files"* are different
    answers and only one of them should fall back to walking.
    """
    try:
        done = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=str(root),
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        # No git on the machine, or it would not start. The walk still works.
        return None
    if done.returncode != 0:
        return None
    names = [n for n in done.stdout.decode("utf-8", "replace").split("\0") if n]
    return names


def _symbols_in(path: Path) -> Tuple[str, ...]:
    """The definitions one file declares. Lifted out of `_walk` so the git
    path and the walk read files the same way rather than twice."""
    symbols: List[str] = []
    try:
        if path.stat().st_size > MAX_SCAN_BYTES:
            return ()
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                for pattern in _DEFINITIONS:
                    match = pattern.match(line)
                    if match:
                        symbols.append(match.group("name"))
                        break
    except OSError:
        # One unreadable file must not lose the map, for the reason one
        # unreadable file does not end a search.
        return ()
    return tuple(symbols)


def _walk(root: Path) -> Tuple[FileSymbols, ...]:
    resolved = root.resolve()

    listed = _git_listed(resolved)
    if listed is not None:
        found: List[FileSymbols] = []
        for relative in sorted(listed):
            path = resolved / relative
            if path.suffix.lower() not in CodeParser.suffixes:
                continue
            if not path.is_file():
                # `--others` can name something deleted between the listing
                # and here, and a submodule appears as a directory.
                continue
            found.append(
                FileSymbols(relative, _symbols_in(path), relative.count("/"))
            )
            if len(found) >= MAX_FILES:
                break
        return tuple(found)

    found = []
    for dirpath, dirnames, filenames in os.walk(resolved):
        dirnames[:] = sorted(
            d for d in dirnames if d.lower() not in _SKIP_LOWER and not d.startswith(".")
        )
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if path.suffix.lower() not in CodeParser.suffixes:
                continue
            relative = path.relative_to(resolved).as_posix()
            found.append(FileSymbols(relative, _symbols_in(path), relative.count("/")))
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
        # **Named, because "this project" has to resolve to something.**
        #
        # Reported 3 October 2026, with a screenshot. A coding project open on
        # a real Unreal plugin, the question *"do an audit on this project"*,
        # and a confident, well-structured audit of **a portfolio website** —
        # a different piece of work entirely, reconstructed from six recalled
        # facts. Measured afterwards: with the scope set to this project,
        # recall returned six facts and every one was `global`, including the
        # whole HTML of a site Zaram had generated months earlier, at a
        # relevance of 0.51 against a question it has nothing to do with.
        #
        # `CLAUDE.md` wrote this failure down before it happened. *"Write that
        # up as a proposal" is referential, and similarity recall over five
        # referential words retrieves nothing: the model filled the gap with a
        # whole invented client.* "Do an audit on this project" is those five
        # referential words, and the gap got filled the same way.
        #
        # The header said `## The open project` and then listed paths. It
        # never said **which** project, so the one thing in the prompt that
        # could have resolved the pronoun was missing, while six concrete
        # paragraphs about other work sat below it — and the recall block is
        # appended *last*, which is the most salient position there is.
        f"`{root}` — this is what \"this project\", \"the repo\" and \"the "
        "code\" refer to.",
        "",
        "Files in it and the definitions in each, most relevant to the "
        "question first. Use `read_lines` to see any of them.",
        "",
        # Rule 9 at the point where it actually fails. The refusal path is
        # *"say so and ask"* rather than produce something plausible, and a
        # document audit is the worst case for it — unlike a wrong chat reply,
        # which the next turn corrects, a wrong audit reads as finished work.
        "Anything recalled below is from the user's memory and may be about "
        "other work. A question about *this* project is answered from these "
        "files: read them. Do not describe a file you have not read, and if "
        "nothing here answers the question, say that instead of filling the "
        "gap from memory.",
        "",
    ]
    footer = []
    if dropped > 0:
        footer = ["", f"({dropped} more files not shown; `list_files` or `search_code` will find them)"]
    return "\n".join(header + lines + footer) + "\n"

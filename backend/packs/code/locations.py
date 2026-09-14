"""Where a failure points — read out of a runner's output, with the code beside it.

**A traceback is a list of places, and the model was reading it as prose.**
When the tests failed, `run_command` handed back the output and the model's
next move was to guess which file to open and ask for it — one round trip,
sometimes two, to reach the line the runner had already named. Now the
places named in the output are parsed, kept only when they are real files
inside the project, and the last few are handed over *with the lines around
them*: the model sees the failing code in the same turn it sees the failure.

**Nearest the end first.** A traceback ends at the frame that raised; a test
runner puts its summary last; a compiler lists errors in order and the last
one is as real as the first. So locations are ordered by last appearance,
and the excerpts go to the final three — the ones a person would open.

**The project folder is still the sandbox.** A path in the output that
resolves outside the root — a library frame under `site-packages`, a path a
test printed on purpose — is a location and is listed, but its source is
never excerpted. The reader's `_inside` check is the same edge every read
uses; this module borrows it rather than drawing a second one.

Formats read, each with the runner that produces it: Python (`File "x", line
N` and pytest's `x.py:N: Error`), TypeScript (`x.ts(12,7): error TS…`),
Node and browser stacks (`at fn (x.js:12:7)` and bare `x.ts:12:7`), Go
(`x.go:12:5:`), Rust (`--> x.rs:12:5`). Anything else is a line without a
place, and stays text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

#: How many places to report, and how many of those to open.
MAX_LOCATIONS = 12
MAX_EXCERPTS = 3
#: Lines either side of the named line.
CONTEXT_LINES = 10
#: Files past this are not opened — a minified bundle is not a place to read.
MAX_EXCERPT_FILE_BYTES = 2_000_000


@dataclass(frozen=True)
class Location:
    file: str
    line: int
    column: Optional[int] = None
    message: str = ""

    def to_json(self) -> Dict[str, object]:
        out: Dict[str, object] = {"file": self.file, "line": self.line}
        if self.column is not None:
            out["column"] = self.column
        if self.message:
            out["message"] = self.message
        return out


@dataclass(frozen=True)
class Excerpt:
    file: str
    line: int
    #: The first line number of `text`, so the model can count.
    start: int
    text: str
    truncated: bool = field(default=False)

    def to_json(self) -> Dict[str, object]:
        return {"file": self.file, "line": self.line, "start": self.start, "text": self.text}


_PATH = r"(?P<file>[^\s:()\"'<>|]+?\.[A-Za-z0-9]{1,6})"

_PATTERNS: Sequence[re.Pattern[str]] = (
    # Python: File "path", line 12, in name
    re.compile(r'File "(?P<file>[^"]+)", line (?P<line>\d+)'),
    # TypeScript: path(12,7): error TS2339: message
    re.compile(rf"^\s*{_PATH}\((?P<line>\d+),(?P<column>\d+)\):\s*(?P<message>.+)$", re.M),
    # Rust: --> path:12:5
    re.compile(rf"-->\s*{_PATH}:(?P<line>\d+):(?P<column>\d+)"),
    # Node / browser stacks: at name (path:12:7) or at path:12:7
    re.compile(rf"\bat\s+(?:[^\s(]+\s+\()?{_PATH}:(?P<line>\d+):(?P<column>\d+)\)?"),
    # pytest / Go / generic: path:12: message  or  path:12:5: message
    re.compile(rf"(?:^|\s){_PATH}:(?P<line>\d+)(?::(?P<column>\d+))?:?\s*(?P<message>[^\n]*)", re.M),
)

_SKIP_SEGMENTS = ("site-packages", "node_modules", "dist-packages", "<frozen")


def locations_in(output: str, root: Path) -> List[Location]:
    """Every place the output names inside the project, last-mentioned first,
    each file:line once."""
    found: List[tuple[int, Location]] = []
    for pattern in _PATTERNS:
        for match in pattern.finditer(output or ""):
            raw = match.group("file").strip()
            if not raw or any(seg in raw for seg in _SKIP_SEGMENTS):
                continue
            try:
                line = int(match.group("line"))
            except (TypeError, ValueError):
                continue
            column = match.groupdict().get("column")
            message = (match.groupdict().get("message") or "").strip()
            relative = _relative_inside(root, raw)
            if relative is None:
                continue
            found.append((
                match.start(),
                Location(
                    file=relative,
                    line=line,
                    column=int(column) if column and column.isdigit() else None,
                    message=message[:200],
                ),
            ))
    # Last mention wins, and later mentions come first.
    by_key: Dict[tuple[str, int], tuple[int, Location]] = {}
    for pos, loc in found:
        key = (loc.file, loc.line)
        if key not in by_key or pos > by_key[key][0]:
            by_key[key] = (pos, loc)
    ordered = [loc for _, loc in sorted(by_key.values(), key=lambda p: -p[0])]
    return ordered[:MAX_LOCATIONS]


def excerpts_for(
    locations: Sequence[Location],
    root: Path,
    *,
    inside: Optional[Callable[[Path, str], Path]] = None,
    limit: int = MAX_EXCERPTS,
) -> List[Excerpt]:
    """The lines around the first ``limit`` locations that are readable files
    inside the project. ``inside`` is the reader's own sandbox check when the
    caller has one; without it the same resolution is done here."""
    out: List[Excerpt] = []
    seen: set[str] = set()
    for loc in locations:
        if len(out) >= limit:
            break
        if loc.file in seen:
            continue
        try:
            path = inside(root, loc.file) if inside else _resolve_inside(root, loc.file)
        except Exception:  # noqa: BLE001 - outside the root, or not a path
            continue
        if path is None or not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_EXCERPT_FILE_BYTES:
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        if not lines:
            continue
        start = max(1, loc.line - CONTEXT_LINES)
        end = min(len(lines), loc.line + CONTEXT_LINES)
        width = len(str(end))
        body = "\n".join(
            f"{n:>{width}}{'>' if n == loc.line else ' '} {lines[n - 1]}"
            for n in range(start, end + 1)
        )
        out.append(Excerpt(file=loc.file, line=loc.line, start=start, text=body))
        seen.add(loc.file)
    return out


def _relative_inside(root: Path, raw: str) -> Optional[str]:
    """``raw`` as a path relative to the root, or ``None`` when it is not
    inside it. Absolute and relative spellings both resolve; a path that
    climbs out, or names a drive elsewhere, is not the project's."""
    try:
        resolved = _resolve_inside(root, raw)
    except Exception:  # noqa: BLE001
        return None
    if resolved is None:
        return None
    return resolved.relative_to(root.resolve()).as_posix()


def _resolve_inside(root: Path, raw: str) -> Optional[Path]:
    base = root.resolve()
    candidate = Path(raw)
    resolved = (candidate if candidate.is_absolute() else base / candidate).resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        return None
    return resolved

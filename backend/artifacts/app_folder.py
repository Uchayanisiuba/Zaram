"""A multi-file app, saved as a folder.

Written 5 October 2026, from one sentence of the maintainer's: *"I intended for
Voxel World not to be tied to a project -- I want Zaram to be able to do single
file apps and multiple file apps."* A page written in chat is one file and
`Save HTML` already keeps it. An app of several files (`index.html`,
`style.css`, `game.js`) has nowhere to go: a project is where Zaram writes
files today, and a project needs a folder, a name, a switch and a terminal --
which is the whole of what somebody asking for a game does not want to set up.

**Generative tier, so none of that is needed.** This creates new files in the
output directory and changes nothing that exists, which is exactly the tier the
table says needs no undo, no confirmation and no sandbox beyond the path
confinement below. It is the same promise `artifacts/store.py` makes, and it
keeps it the same way: **there is no overwrite and no delete here**. A name
that is taken gets `-2`, `-3`; a file that exists is an error, never replaced.
`tests/test_artifact_write_path.py` scans for the verbs; this module does not
use them.

**What is refused, and why each is a refusal rather than a repair.** The file
names come from a model's reply, which is text a stranger can influence
(`core/untrusted.py`), so they are treated as hostile:

* an absolute path, a drive letter, a `..` part, a backslash, an empty part --
  would write outside the app's own folder;
* an extension outside a short list of what a web app is made of -- Zaram will
  not write an `.exe` or a `.bat` because a reply named one;
* too many files, or too large -- a reply cannot fill the disk.

Sanitising a name produces a file subtly unlike the one the page asks for by
name, and the page then fails to find it. The same posture `vrmSafety` takes:
refuse, and say which.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Tuple

#: What a web app is made of. Nothing executable by the operating system.
ALLOWED_EXTENSIONS = frozenset({"html", "htm", "css", "js", "mjs", "json", "svg", "txt", "md"})

MAX_FILES = 40
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024
MAX_DEPTH = 4

#: Folder under the output directory that holds saved apps, so they never mix
#: with generated documents.
APPS_DIRNAME = "apps"

_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,80}$")


class AppFolderRefused(ValueError):
    """The files were not written, and the message says which and why."""


def _clean_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:48]
    return slug or "app"


def _check_path(raw: str) -> Tuple[str, ...]:
    text = (raw or "").strip()
    if not text or "\\" in text or text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        raise AppFolderRefused(f"{raw!r} is not a path inside the app's own folder.")
    parts = tuple(text.split("/"))
    if len(parts) > MAX_DEPTH:
        raise AppFolderRefused(f"{raw!r} is nested more than {MAX_DEPTH} folders deep.")
    for part in parts:
        if part in ("", ".", "..") or not _PART.match(part) or part.endswith((".", " ")):
            raise AppFolderRefused(f"{raw!r} is not a path inside the app's own folder.")
    extension = parts[-1].rsplit(".", 1)[-1].lower() if "." in parts[-1] else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise AppFolderRefused(
            f"{raw!r} is not a kind of file a web app is saved as "
            f"({', '.join(sorted(ALLOWED_EXTENSIONS))})."
        )
    return parts


def save_app(output_root: Path | str, name: str, files: Iterable[Tuple[str, str]]) -> Path:
    """Write ``files`` into a new folder under ``<output_root>/apps/`` and return it.

    All paths are checked before the first byte is written, so a refused call
    leaves nothing behind.
    """
    listed = list(files)
    if not listed:
        raise AppFolderRefused("There are no files to save.")
    if len(listed) > MAX_FILES:
        raise AppFolderRefused(f"{len(listed)} files is more than the {MAX_FILES} an app may have.")

    checked = []
    seen = set()
    total = 0
    for raw_path, content in listed:
        parts = _check_path(raw_path)
        key = "/".join(parts).lower()
        if key in seen:
            raise AppFolderRefused(f"{raw_path!r} appears twice.")
        seen.add(key)
        data = (content or "").encode("utf-8")
        if len(data) > MAX_FILE_BYTES:
            raise AppFolderRefused(f"{raw_path!r} is larger than {MAX_FILE_BYTES // 1024} KB.")
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise AppFolderRefused(f"The app is larger than {MAX_TOTAL_BYTES // (1024 * 1024)} MB.")
        checked.append((parts, data))

    base = Path(output_root).expanduser().resolve() / APPS_DIRNAME
    base.mkdir(parents=True, exist_ok=True)
    slug = _clean_name(name)
    folder = None
    for attempt in range(1, 1000):
        candidate = base / (slug if attempt == 1 else f"{slug}-{attempt}")
        try:
            candidate.mkdir(exist_ok=False)
        except FileExistsError:
            continue
        folder = candidate
        break
    if folder is None:  # pragma: no cover - a thousand apps of one name
        raise AppFolderRefused("Too many apps share that name.")

    for parts, data in checked:
        target = folder.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        # "xb": fails if the file exists. There is no mode here that replaces.
        with open(target, "xb") as handle:
            handle.write(data)
    return folder

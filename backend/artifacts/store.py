"""The write path. It can create files and it can do nothing else.

CLAUDE.md: "Generated files go to a dedicated output directory, never overwrite
silently, and the write path has no delete or overwrite capability at all. A
filename collision increments or asks."

That is a property of this module, not a promise about how it is used. There is
no delete function, no overwrite function, and no code path that opens a file in
a mode that can truncate. ``test_artifact_write_path.py`` reads this file's
source and fails the build if any of that changes — the same enforcement shape
as the egress chokepoint, and for the same reason: it must fail on the commit
that introduces the capability, not at runtime on a user's machine.

Two decisions that look like details and are not:

**Exclusive create, not check-then-write.** ``open(path, "xb")`` fails if the
path exists, atomically, in the kernel. Checking ``path.exists()`` and then
writing is a convention with a race in it: two generations of the same document
can both check, both find nothing, and the second silently destroys the first.
The window is small and the failure is permanent, which is the worst
combination.

**Path confinement is a security boundary.** The *model* proposes filenames.
"../../.ssh/config" is therefore an input this module must assume will arrive
one day, not a hypothetical. Every path is resolved and asserted to be inside
the output root before anything is opened.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from pathlib import Path

logger = logging.getLogger(__name__)

#: Where generated files go, and the only place they may go.
DEFAULT_OUTPUT_DIRNAME = "generated"

#: How many times a collision may increment before the caller is asked instead.
#: Bounded because an unbounded loop on a pathological directory is a hang, and
#: because 50 files of the same name means something upstream is wrong.
MAX_COLLISION_ATTEMPTS = 50

#: Characters that cannot appear in a filename on Windows, plus the separators.
#: Applied after traversal stripping, not instead of it.
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

#: Names Windows refuses regardless of extension.
_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class UnsafeFilename(ValueError):
    """The proposed filename could not be made safe."""


class CollisionLimit(RuntimeError):
    """Too many files of this name already exist; ask the user instead.

    The "or asks" half of "increments or asks". Raised rather than silently
    picking something, because at this point the naming is not a detail the
    caller can be assumed to be indifferent to.
    """


def sanitise_filename(proposed: str) -> str:
    """Reduce a model-proposed filename to something that cannot escape.

    Order matters. Take the basename *first* so that separators are gone before
    anything else runs — stripping illegal characters first would turn
    "../../etc/passwd" into "....etcpasswd", which is safe by accident rather
    than by construction, and the accident stops holding the moment the illegal
    set changes.
    """
    if not proposed or not proposed.strip():
        raise UnsafeFilename("empty filename")

    # Normalise first: a composed character can carry a separator through a
    # naive check on some filesystems.
    name = unicodedata.normalize("NFKC", proposed).strip()

    # Both separators, on every platform. A POSIX host still receives Windows
    # paths from a model that has seen Windows examples.
    name = name.replace("\\", "/").split("/")[-1]

    # Windows drive-relative forms ("C:foo") survive basename extraction.
    if ":" in name:
        name = name.split(":")[-1]

    name = _ILLEGAL.sub("_", name)

    # Leading dots make hidden files; a name of only dots is not a name.
    name = name.lstrip(".")
    # Windows strips trailing dots and spaces, which would change the name
    # after the collision check and defeat the exclusive create.
    name = name.rstrip(". ")

    if not name:
        raise UnsafeFilename(f"nothing usable left of {proposed!r}")

    stem = name.split(".")[0].upper()
    if stem in _RESERVED:
        name = f"_{name}"

    # Long enough for any real document, short enough to survive a deep output
    # path on Windows' default MAX_PATH.
    if len(name) > 120:
        root, dot, ext = name.rpartition(".")
        name = f"{root[:110]}{dot}{ext}" if dot else name[:120]

    return name


class ArtifactStore:
    """Creates files under one directory. Cannot remove or replace them."""

    def __init__(self, output_root: Path | str) -> None:
        self._root = Path(output_root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _resolve_within_root(self, filename: str) -> Path:
        """Full path for a filename, or refuse.

        The assertion is on the *resolved* path, after symlinks. A symlink
        inside the output directory pointing outside it would otherwise pass a
        string-prefix check and write anywhere.
        """
        candidate = (self._root / filename).resolve()
        if candidate == self._root or self._root not in candidate.parents:
            raise UnsafeFilename(
                f"{filename!r} resolves to {candidate}, which is outside {self._root}"
            )
        return candidate

    def write_new(self, proposed_filename: str, data: bytes) -> Path:
        """Create a new file. Never replaces an existing one.

        The only write operation in this package. Returns the path actually
        used, which may differ from the one proposed if the name collided.
        """
        safe = sanitise_filename(proposed_filename)
        stem, dot, ext = safe.rpartition(".")
        if not dot:
            stem, ext = safe, ""

        for attempt in range(MAX_COLLISION_ATTEMPTS):
            # proposal.docx, then proposal-2.docx, proposal-3.docx …
            # What every operating system does, and what nobody is confused by.
            candidate_name = safe if attempt == 0 else f"{stem}-{attempt + 1}{dot}{ext}"
            target = self._resolve_within_root(candidate_name)

            try:
                # "xb": create-or-fail, atomically, in the kernel. The whole
                # no-overwrite guarantee is this one flag. Anything that
                # checked first and opened "wb" second would be a convention
                # with a race in it.
                with open(target, "xb") as handle:
                    handle.write(data)
            except FileExistsError:
                continue

            if attempt:
                logger.info(
                    "Artifact name collided; wrote %s instead of %s",
                    target.name,
                    safe,
                )
            return target

        raise CollisionLimit(
            f"{MAX_COLLISION_ATTEMPTS} files named like {safe!r} already exist in "
            f"{self._root}. Ask the user for a name rather than inventing another."
        )

    def read(self, filename: str) -> bytes:
        """Read a file back. Present so callers never need `open` themselves."""
        return self._resolve_within_root(sanitise_filename(filename)).read_bytes()

    def exists(self, filename: str) -> bool:
        try:
            return self._resolve_within_root(sanitise_filename(filename)).is_file()
        except UnsafeFilename:
            return False

    def list_files(self) -> list[Path]:
        return sorted(p for p in self._root.iterdir() if p.is_file())


def default_output_root() -> Path:
    """The output directory, overridable for tests and packaging.

    Environment variable rather than a constant so a packaged build can place
    it under the user's documents without editing code.
    """
    override = os.getenv("ZARAM_OUTPUT_DIR")
    if override:
        return Path(override).expanduser()
    # Inside the data directory, which is what `build/installer.nsh` already
    # promises to hand back on uninstall — "the invoices and documents it
    # generated". Under a source checkout that is still `backend/generated`, so
    # nothing moves for a developer.
    from core.paths import data_dir

    return data_dir() / DEFAULT_OUTPUT_DIRNAME

"""Removing a generated file, which is a different act from writing one.

`store.py` is the write path and it *cannot* delete: no unlink, no overwrite,
no truncating open mode, enforced by a source scan in
``test_artifact_write_path.py`` that fails the build on the commit which adds
the capability rather than at runtime on somebody's machine. **None of that
changes here, and this module exists in order that none of it has to.**

The rule that guard enforces is about *generation*. It is there so a model
producing a document can never destroy one, and so a bug in the pipeline
cannot cost a user their invoice. It was never about the user: rule 4 says in
as many words that *the user can correct or delete* what Zaram has stored, and
a Work surface where the only way to remove something is to leave the
application and find the folder is a surface that is missing a verb everyone
expects.

So the capability lives in its own module, reached only from an endpoint a
person triggers. Generation cannot import a delete it does not have; the user
gets one.

**And it is not a delete.** `CLAUDE.md`'s tier table is explicit — a mutative
tool requires *undo, confirm, sandbox* — so this **moves** rather than unlinks,
into a trash folder inside the output root:

* **Undo** is the move being reversible, plus the folder still being there
  tomorrow when the in-app undo is long gone. Every operating system solved
  this the same way, and a product that permanently destroys a contract because
  somebody mis-clicked a checkbox has no answer when they ask for it back.
* **Sandbox** is the path confinement, kept identical to the write path's:
  the *record* names the file, records are written from filenames a model
  proposed, and the day one of them says ``../../.ssh/config`` this module must
  already refuse rather than start refusing.
* **Confirm** is the caller's, and it belongs there: this module cannot know
  whether a person saw a dialog.

**Nothing in Zaram permanently removes a user's file.** Emptying the trash is
the operating system's job, which is exactly where `CLAUDE.md` puts it —
*"removing a file with the operating system"* — and it is the half of that
sentence that survives unchanged.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

#: Inside the output root, so a user who finds the output folder finds this too.
#: Dot-prefixed so it does not read as another generated document on the way
#: past, and so a folder listing of "everything Zaram made" stays true.
TRASH_DIRNAME = ".trash"


class OutsideOutputRoot(ValueError):
    """The path named is not inside the folder Zaram writes to.

    Raised rather than logged and skipped. A caller asking to remove something
    outside the output root is either confused or being driven by input nobody
    checked, and both deserve a stop.
    """


class ArtifactTrash:
    """Move generated files out of the way, and put them back."""

    def __init__(self, output_root: Path | str) -> None:
        self._root = Path(output_root).resolve()

    @property
    def root(self) -> Path:
        """Where trashed files go. Created lazily — an empty trash folder in
        every new install is a question the user did not need asked."""
        return self._root / TRASH_DIRNAME

    def _confine(self, path: Path | str) -> Path:
        """The resolved path, or `OutsideOutputRoot`.

        The same boundary `store.py` draws on the way in, drawn again on the way
        out. It is the *same* assumption for the same reason: these paths came
        from records, and records were written from filenames a model proposed.
        """
        candidate = Path(path).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as error:
            raise OutsideOutputRoot(
                f"{candidate} is not inside {self._root}"
            ) from error
        return candidate

    def send(self, path: Path | str) -> Path:
        """Move the file at ``path`` into the trash. Returns where it went.

        The trashed name carries a timestamp prefix, so two files of the same
        name deleted a week apart both survive. Without it the second would
        overwrite the first — a delete that destroys something *else* silently,
        which is the one outcome worse than the delete itself.
        """
        source = self._confine(path)
        if not source.is_file():
            raise FileNotFoundError(f"nothing to remove at {source}")

        destination_dir = self.root
        destination_dir.mkdir(parents=True, exist_ok=True)

        stamp = time.strftime("%Y%m%d-%H%M%S")
        destination = destination_dir / f"{stamp}-{source.name}"
        # Still a collision if two files of the same name go in the same second.
        # Counted rather than clobbered, on the same reasoning as the write
        # path's increment: a bounded loop beats a lost file.
        suffix = 1
        while destination.exists():
            destination = destination_dir / f"{stamp}-{suffix}-{source.name}"
            suffix += 1

        os.replace(source, destination)
        logger.info("moved %s to the trash at %s", source.name, destination)
        return destination

    def restore(self, trashed: Path | str, original: Path | str) -> Path:
        """Put a trashed file back where it was. Returns the restored path.

        **It refuses to land on top of anything.** A file has been generated at
        the original name since the delete more often than one would like —
        that is what "make me another one" does — and an undo that quietly
        replaced it would destroy a file the user never asked to lose, while
        appearing to be the safe operation.
        """
        source = self._confine(trashed)
        target = self._confine(original)
        if not source.is_file():
            raise FileNotFoundError(f"nothing in the trash at {source}")
        if target.exists():
            raise FileExistsError(
                f"{target.name} is back in the output folder; the trashed copy "
                f"is still at {source}"
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)
        logger.info("restored %s from the trash", target.name)
        return target

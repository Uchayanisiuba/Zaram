"""Where a generated image waits to be kept, and clears itself if it is not.

Why this exists
---------------
`store.py` can create files and do nothing else -- no delete, no overwrite, and
a test that reads its own source to keep it that way. That guarantee was
written for **documents**, and it holds for them: an invoice is asked for once,
deliberately, and the user wants it on disk without being asked twice.

Images broke the assumption the moment `image.generate` landed, because that
flow *produces discards by design*. A batch returns four in a 2x2 grid and the
user picks one, which the 3 September note states plainly -- *"three of them
are about to be discarded."* Under the old arrangement all four were written
straight to the output folder, permanently, and Zaram had no way to remove any
of them. The one tool that creates rejects in bulk was paired with the one
write path that structurally cannot clean up after itself, and the burden
landed on the user's file manager.

Reported by the maintainer on 4 September 2026, looking at a card that said
*"saved to your output folder"*: **should the user not choose what to save?**

Why this is not a hole in the no-delete rule
--------------------------------------------
The output folder still never loses a file. Nothing here can touch it:
promotion *reads* from staging and calls `ArtifactStore.write_new` like any
other caller, so the output directory goes on receiving creates and only
creates.

What clears is staging, and staging is a **cache with a retention window**,
which is a thing this codebase already has several of -- the Spine decays,
Activity prunes, and the 2026 rule is explicit that *"no new store ships
without an answer to how long it keeps things and how the user shortens
that."* This module's answer is `RETENTION_SECONDS`, stated on the card in the
conversation rather than buried in a setting, and the way to shorten it is the
Save button.

The distinction that makes it safe: **a file in staging has never been
presented as saved.** Deleting something the user was told they had would be
the failure the no-delete rule exists to prevent. Expiring something the card
described as temporary, with the window on its face the whole time, is the
product doing what it said it would.

Why promotion copies rather than moves
--------------------------------------
`os.replace` across the two directories would be atomic and faster, and it is
deliberately not used. It would put a path into the output directory without
going through `write_new`, which is where sanitisation, the containment check
and the collision increment live. A move would let a name that staging accepted
land unexamined in the folder the user actually keeps. The second store's
guarantees are worth more than the copy costs -- these are images, written
once, by a person clicking a button.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from .store import ArtifactStore

logger = logging.getLogger(__name__)

#: How long an unkept image stays before it clears itself.
#:
#: Seven days because the window has to survive the thing it is protecting:
#: generating a batch, going away, and coming back to choose. An hour would
#: expire work the user was still deciding about, which is this module's own
#: failure wearing different clothes. A month would refill the disk it exists
#: to keep clear.
#:
#: Stated on the card, never only here. A retention window the user cannot see
#: is indistinguishable from a product that loses files.
RETENTION_SECONDS = 7 * 24 * 60 * 60

#: Sits beside `generated/`, not inside it. Inside, every listing of the output
#: folder -- the user's own file manager included -- would show a directory of
#: things they did not keep, which is the clutter this removes.
DEFAULT_STAGING_DIRNAME = "staged"


class StagingStore:
    """Holds generated files nobody has kept yet.

    Writing is `ArtifactStore`'s, wrapped rather than reimplemented, so staged
    files get the same sanitisation, the same exclusive create and the same
    collision increment. What is added is the two things staging needs and the
    output folder must never have: promotion, and expiry.
    """

    def __init__(
        self,
        staging_root: Path | str,
        retention_seconds: int = RETENTION_SECONDS,
    ) -> None:
        self._files = ArtifactStore(staging_root)
        self._retention = retention_seconds

    @property
    def root(self) -> Path:
        return self._files.root

    @property
    def retention_seconds(self) -> int:
        return self._retention

    def write_new(self, proposed_filename: str, data: bytes) -> Path:
        """Create a staged file. Same rules as the output folder."""
        return self._files.write_new(proposed_filename, data)

    def expires_at(self, path: Path | str) -> float:
        """When this file clears, as an epoch second.

        Derived from the file's own mtime rather than recorded separately, so
        there is no second source of truth to drift. A record saying a file
        expires tomorrow beside a file that was deleted last week is worse than
        either alone.
        """
        return os.path.getmtime(Path(path)) + self._retention

    def promote(self, path: Path | str, destination: ArtifactStore) -> Path:
        """Keep it: copy into the output folder, then drop the staged copy.

        Returns the path in the output folder, which may differ from the staged
        name if it collided there -- `write_new` decides that, as it does for
        every other caller.

        **The staged copy goes only after the new one exists.** If the write
        raises, the original is still in staging and the button can be pressed
        again; the reverse order loses the file on a full disk.
        """
        source = Path(path)
        kept = destination.write_new(source.name, source.read_bytes())
        try:
            source.unlink()
        except OSError as exc:
            # The file is safe -- it is in the output folder. A staged leftover
            # is untidy and expires on its own, so this is worth a line in the
            # log and nothing more.
            logger.warning("kept %s but could not clear the staged copy: %s", kept.name, exc)
        return kept

    def is_staged(self, path: Path | str) -> bool:
        """Whether this path is one of ours.

        Resolved before comparing, because a symlink is exactly how something
        outside staging would try to be treated as inside it.
        """
        try:
            candidate = Path(path).resolve()
        except OSError:
            return False
        return self.root in candidate.parents

    def sweep(self, now: float | None = None) -> list[Path]:
        """Delete what has run out of time. Returns what was removed.

        The paths rather than a count, so the caller can drop the matching
        records in the same pass -- a record pointing at a file that is gone is
        what makes Work show a card that opens onto nothing.
        """
        moment = time.time() if now is None else now
        removed: list[Path] = []
        for candidate in self._files.list_files():
            try:
                if self.expires_at(candidate) > moment:
                    continue
                candidate.unlink()
            except OSError as exc:
                logger.warning("could not clear staged %s: %s", candidate.name, exc)
                continue
            removed.append(candidate)
        if removed:
            logger.info("cleared %d staged file(s) nobody kept", len(removed))
        return removed


def default_staging_root() -> Path:
    """Beside the output directory, and moved by the same override.

    Reading `ZARAM_OUTPUT_DIR` rather than inventing a second variable for the
    ordinary case: a user who has relocated their output has already said where
    generated things live, and making them say it twice is how the two end up
    on different disks.
    """
    override = os.getenv("ZARAM_STAGING_DIR")
    if override:
        return Path(override).expanduser()

    output_override = os.getenv("ZARAM_OUTPUT_DIR")
    if output_override:
        return Path(output_override).expanduser().parent / DEFAULT_STAGING_DIRNAME

    from core.paths import data_dir

    return data_dir() / DEFAULT_STAGING_DIRNAME

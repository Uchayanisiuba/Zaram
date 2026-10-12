"""The pictures a conversation was about, kept with it so its pages still show them.

An attached picture is working state (`attachments/store.py`): held for the
session and swept at the next start. That is right for a contract someone asked
one question about, and wrong for "make me a portfolio site from this photo" --
the page the model wrote refers to the picture by name, and a conversation
reopened from History, or any conversation after a restart, had pages full of
grey placeholders because the bytes were gone while the page, and the person's
wish to see it, were not.

So the pictures that went with a message are copied here, under the data
directory, one folder per conversation. **This is conversation data and not
memory, and the type of store is the whole of rule 7d here.** Nothing in this
module is indexed, embedded, recalled, cited or sent anywhere. The only reader is
`GET /conversations/{id}/pictures/{attachment_id}`, which serves the window the
bytes of a picture it already has a name for. Only images a page or a document
can use are kept; a document someone attached is never copied.

Retention -- how long, and how a person shortens it
----------------------------------------------------
*How long:* for as long as the conversation exists. Conversations have no time
limit, so neither do their pictures; they are removed **with the conversation**
(`DELETE /conversations/{id}` calls :meth:`ConversationPictures.remove_conversation`)
and never outlive it.

*A ceiling:* :data:`MAX_TOTAL_BYTES`, 1 GB across every conversation. Past it the
conversations whose pictures were **least recently used** go first, whole, until
the total fits -- a picture counts as used when it is kept or served, so a
conversation somebody keeps coming back to is the last to lose its pictures. The
conversation itself, its text and its pages are untouched; the pages then show
the existing "is no longer attached" placeholder, which says so on the page
rather than failing quietly.

*Shortening it:* `DELETE /conversations/{id}/pictures` removes one conversation's
pictures now and leaves the conversation. That is in History beside Delete.

Why removal is a filtered unlink and not `rmtree`
-------------------------------------------------
Same reason as the attachment sweep: the root is derived from configuration, and
a recursive delete of a path somebody can set is the wrong shape whatever it is
called. Only files this store wrote -- ``att_<12 hex>.<suffix>`` -- inside a
folder named like a conversation id are ever removed, and a folder only when it
is empty.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.paths import data_dir

logger = logging.getLogger(__name__)

#: Under the data directory. Hyphenated, so it can never be imported as a package.
DIRNAME = "conversation-pictures"

#: The most every conversation's kept pictures may take together. A number with a
#: name so the ceiling can be found, changed and tested; 1 GB is several hundred
#: photographs, which is more than anyone attaches to conversations, and small
#: beside the models on the same disk.
MAX_TOTAL_BYTES = 1024 * 1024 * 1024

#: What a conversation id looks like (`ConversationRecords.start`). Checked
#: before it becomes part of a path: an id arrives from a URL.
_CONVERSATION_ID = re.compile(r"^conv_[0-9a-f]{12}$")

#: What an attachment id looks like (`AttachmentStore`), and the only kind of
#: file name this store writes or removes.
_ATTACHMENT_ID = re.compile(r"^att_[0-9a-f]{12}$")
_KEPT_FILE = re.compile(r"^(att_[0-9a-f]{12})\.[a-z0-9]{1,5}$")
_SUFFIX = re.compile(r"^\.[a-z0-9]{1,5}$")


def media_type_of(data: bytes) -> Optional[str]:
    """The media type of the formats a browser draws, read from the bytes.

    From the bytes and never from a file name: the result ends up in a `data:`
    URI a browser honours. ``None`` for anything a page cannot show (tiff).
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"BM"):
        return "image/bmp"
    return None


@dataclass(frozen=True)
class KeptPicture:
    """One kept picture, with its bytes, as handed back to restore a session."""

    id: str
    suffix: str
    data: bytes


def default_root() -> str:
    return str(Path(data_dir()) / DIRNAME)


class ConversationPictures:
    """A folder of pictures per conversation, bounded and removable."""

    def __init__(self, root: Optional[str] = None, *, max_total_bytes: int = MAX_TOTAL_BYTES) -> None:
        # Resolved when used and not when built: this is constructed at import
        # time in `main.py`, and a data directory moved afterwards (a test, or
        # `ZARAM_DATA_DIR` set by a launcher) must still be the one that is used.
        self._explicit_root = root
        self._max = int(max_total_bytes)
        self._lock = threading.Lock()

    @property
    def _root(self) -> Path:
        return Path(self._explicit_root or default_root())

    # -- paths -------------------------------------------------------------

    def _folder(self, conversation_id: str) -> Optional[Path]:
        """The conversation's folder, or ``None`` for an id that is not one."""
        if not isinstance(conversation_id, str) or not _CONVERSATION_ID.match(conversation_id):
            return None
        return self._root / conversation_id

    def _files(self, folder: Path) -> List[Path]:
        """Files this store wrote in ``folder``, and nothing else."""
        try:
            return [p for p in folder.iterdir() if p.is_file() and _KEPT_FILE.match(p.name)]
        except OSError:
            return []

    def _find(self, conversation_id: str, attachment_id: str) -> Optional[Path]:
        folder = self._folder(conversation_id)
        if folder is None or not _ATTACHMENT_ID.match(attachment_id or ""):
            return None
        for path in self._files(folder):
            if path.name.split(".", 1)[0] == attachment_id:
                return path
        return None

    # -- writing -----------------------------------------------------------

    def keep(self, conversation_id: str, attachment_id: str, suffix: str, data: bytes) -> bool:
        """Copy one picture into the conversation's folder.

        ``False`` when it was not kept -- a bad id, a suffix that is not a plain
        extension, no bytes, or the disk said no. Never raises: keeping a copy
        is a courtesy to a later page, and a failure here must not cost the
        person their reply.
        """
        folder = self._folder(conversation_id)
        suffix = (suffix or "").lower()
        if (
            folder is None
            or not _ATTACHMENT_ID.match(attachment_id or "")
            or not _SUFFIX.match(suffix)
            or not data
        ):
            return False
        try:
            with self._lock:
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f"{attachment_id}{suffix}").write_bytes(data)
                self._prune_locked(protect=conversation_id)
            return True
        except OSError as exc:
            logger.warning("Could not keep a picture for %s: %s", conversation_id, exc)
            return False

    # -- reading -----------------------------------------------------------

    def has(self, conversation_id: str, attachment_id: str) -> bool:
        return self._find(conversation_id, attachment_id) is not None

    def read(self, conversation_id: str, attachment_id: str) -> Optional[bytes]:
        """The kept bytes, or ``None``. Serving a picture counts as using it."""
        path = self._find(conversation_id, attachment_id)
        if path is None:
            return None
        try:
            data = path.read_bytes()
        except OSError:
            return None
        try:
            os.utime(path, None)
        except OSError:
            pass
        return data

    def list(self, conversation_id: str) -> List[KeptPicture]:
        """Every picture kept for the conversation, oldest first, with bytes."""
        folder = self._folder(conversation_id)
        if folder is None:
            return []
        found: List[Tuple[float, KeptPicture]] = []
        for path in self._files(folder):
            try:
                match = _KEPT_FILE.match(path.name)
                found.append(
                    (
                        path.stat().st_mtime,
                        KeptPicture(
                            id=match.group(1),
                            suffix=path.suffix.lower(),
                            data=path.read_bytes(),
                        ),
                    )
                )
            except OSError:
                continue
        return [picture for _when, picture in sorted(found, key=lambda item: item[0])]

    def ids(self, conversation_id: str) -> List[str]:
        folder = self._folder(conversation_id)
        if folder is None:
            return []
        return sorted(_KEPT_FILE.match(p.name).group(1) for p in self._files(folder))

    def total_bytes(self) -> int:
        return sum(size for _conv, _when, size in self._survey())

    # -- removing ----------------------------------------------------------

    def remove_conversation(self, conversation_id: str) -> Tuple[int, int]:
        """Remove one conversation's pictures. ``(files, bytes)`` removed.

        Called when the conversation is deleted and by the person's own
        "remove this conversation's pictures". A conversation with none keeps
        answering ``(0, 0)`` rather than failing, so deleting is never refused
        for want of pictures.
        """
        with self._lock:
            return self._clear_locked(conversation_id)

    def _clear_locked(self, conversation_id: str) -> Tuple[int, int]:
        folder = self._folder(conversation_id)
        if folder is None:
            return 0, 0
        count = size = 0
        for path in self._files(folder):
            try:
                length = path.stat().st_size
                path.unlink()
            except OSError:
                continue
            count += 1
            size += length
        try:
            folder.rmdir()  # only if empty; never a recursive delete
        except OSError:
            pass
        return count, size

    # -- the ceiling -------------------------------------------------------

    def _survey(self) -> List[Tuple[str, float, int]]:
        """``(conversation id, last used, bytes)`` for every folder."""
        rows: List[Tuple[str, float, int]] = []
        try:
            folders = [p for p in self._root.iterdir() if p.is_dir() and _CONVERSATION_ID.match(p.name)]
        except OSError:
            return rows
        for folder in folders:
            newest = 0.0
            size = 0
            for path in self._files(folder):
                try:
                    info = path.stat()
                except OSError:
                    continue
                newest = max(newest, info.st_mtime)
                size += info.st_size
            rows.append((folder.name, newest, size))
        return rows

    def prune(self, *, protect: str = "") -> List[str]:
        """Bring the total under the ceiling; the conversations that lost pictures."""
        with self._lock:
            return self._prune_locked(protect=protect)

    def _prune_locked(self, *, protect: str = "") -> List[str]:
        rows = self._survey()
        total = sum(size for _c, _w, size in rows)
        pruned: List[str] = []
        if total <= self._max:
            return pruned
        # Least recently used first, whole conversations: a page needs all of
        # its pictures or it is showing placeholders anyway.
        for conversation_id, _when, size in sorted(rows, key=lambda row: row[1]):
            if total <= self._max:
                break
            if conversation_id == protect:
                continue
            self._clear_locked(conversation_id)
            total -= size
            pruned.append(conversation_id)
        # Only the conversation being written to is left and it alone is over:
        # drop its oldest pictures, but never the one just kept.
        if total > self._max and protect:
            folder = self._folder(protect)
            files = sorted(self._files(folder), key=lambda p: p.stat().st_mtime) if folder else []
            for path in files[:-1]:
                if total <= self._max:
                    break
                try:
                    length = path.stat().st_size
                    path.unlink()
                except OSError:
                    continue
                total -= length
            if protect not in pruned:
                pruned.append(protect)
        if pruned:
            logger.info(
                "Kept pictures were over %d bytes; removed those of %d conversation(s), "
                "least recently used first",
                self._max,
                len(pruned),
            )
        return pruned


def metadata_for(attachment) -> Dict[str, str]:
    """What a stored message records about a picture. **Never the bytes.**"""
    return {
        "id": attachment.id,
        "name": attachment.name,
        "kind": "image",
        "page_name": attachment.page_name,
        "suffix": attachment.suffix,
    }

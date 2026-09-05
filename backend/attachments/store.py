"""Holding the files a conversation is about, for exactly as long as it is about them.

Three properties, and each one is a rule rather than a preference.

**Nothing survives a restart.** Rule 7d says conversation is ephemeral. A
scratch directory that outlives the process is a second document store nobody
chose to have, quietly accumulating the contracts and payslips people asked one
question about. So the leftovers are removed when the process comes up.

**Bounded while running.** :data:`MAX_PER_SESSION` and :data:`MAX_BYTES` exist
because working state that grows without limit is a leak with a friendly name.
Eviction is oldest-first and it is *reported* — an attachment that vanished
silently would make Zaram answer from a document the user believes is attached.

**Parsed here, never off-device.** This reuses `ingest.parsers`, which
`test_ingest_stays_local.py` already scans for network calls. Rule 7c does not
get a second implementation with a second chance to break it.

The file itself is kept rather than discarded after parsing, so that "keep this
in Knowledge" is a move on this machine rather than asking the user to find and
upload it again. That is the only reason; nothing reads it back otherwise.

Why the sweep is a filtered unlink and not `rmtree`
---------------------------------------------------
It was `shutil.rmtree(self._root)` for about ten minutes, and in those ten
minutes it deleted this package's own source. `data_dir()` resolves to
``C:\\Zaram\\backend`` in a checkout that already holds databases — which is
correct and deliberate — so the root came out as ``backend/attachments``, the
very directory this file lives in, and the tree was removed at import time.

The rename to :data:`DIRNAME` is why it cannot recur by that route: a hyphen is
not a valid Python identifier, so the directory can never shadow a module. But
the rename is the smaller half. **A recursive delete of a path derived from
configuration is the wrong shape whatever it is named** — the blast radius is
decided by a value someone can set, and `ZARAM_DATA_DIR` is a value someone can
set. So the sweep removes only files this store itself created, matches them by
its own prefix, and never removes a directory.
"""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional

from core.paths import data_dir
from ingest.parsers import parsers_for, supported_suffixes

from .contracts import Attachment, AttachmentError, AttachmentKind

#: The directory attachments live in, under the data directory.
#:
#: Hyphenated so it can never be importable as a Python package. See the module
#: docstring: the first version was called `attachments`, resolved to this
#: package's own directory, and deleted it.
DIRNAME = "chat-attachments"

#: Every file this store writes begins with this. The sweep matches on it, so
#: anything the store did not create is left alone.
PREFIX = "att_"

#: How many files one conversation may hold at once.
#:
#: Not a storage limit — a legibility one. Past a handful of chips the composer
#: stops showing what is in scope, and an answer drawn from eight documents the
#: user cannot see listed is an answer they cannot check.
MAX_PER_SESSION = 8

#: The largest single file accepted, matching the ingest cap for the same
#: reason: reading the first N bytes of a larger one produces a source that
#: answers confidently from half a document, which is rule 9's failure arriving
#: by the back door because nothing looks missing.
MAX_BYTES = 100 * 1024 * 1024

#: Image formats an attachment may be.
#:
#: Deliberately narrower than "every format Pillow opens". These are what
#: Ollama's vision models accept directly, and a format that has to be
#: converted first is a conversion nobody asked for producing a file subtly
#: unlike the one the user attached.
IMAGE_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"}
)


def default_root() -> str:
    """Where attachments live while a conversation is about them."""
    return str(Path(data_dir()) / DIRNAME)


class AttachmentStore:
    """Session-scoped parsed files. Not the Spine, and never becomes it."""

    def __init__(self, root: Optional[str] = None) -> None:
        self._root = Path(root or default_root())
        self._lock = threading.Lock()
        #: Insertion-ordered, so eviction is oldest-first without a sort.
        self._items: "OrderedDict[str, Attachment]" = OrderedDict()
        self._sweep()

    def _sweep(self) -> None:
        """Remove leftovers from a previous run. Only this store's own files.

        Never recursive, never a directory, and never anything without the
        prefix. A failure to remove one is not fatal: refusing to boot because
        a temporary file was locked would take the whole product down for the
        least important thing in it.
        """
        self._root.mkdir(parents=True, exist_ok=True)
        for entry in self._root.iterdir():
            if entry.is_file() and entry.name.startswith(PREFIX):
                try:
                    entry.unlink()
                except OSError:
                    pass

    # -- writing -----------------------------------------------------------

    def add(self, session_id: str, name: str, data: bytes) -> tuple[Attachment, List[Attachment]]:
        """Parse one file and hold it for this conversation.

        Returns the attachment and **whatever was evicted to make room**. The
        second half is not bookkeeping: an attachment that disappeared without
        being mentioned would leave the user believing a document is in scope
        when it is not, and the next answer would be confidently short of it.

        Raises `AttachmentError` with a sentence for the person who dropped it.
        """
        if len(data) > MAX_BYTES:
            raise AttachmentError(
                f"{name} is larger than {MAX_BYTES // (1024 * 1024)} MB. "
                "Zaram refuses rather than reading part of it, because half a "
                "document answers confidently and nothing looks missing."
            )
        if not data:
            raise AttachmentError(f"{name} is empty.")

        suffix = Path(name).suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            return self._add_image(session_id, name, suffix, data)

        candidates = parsers_for(suffix)
        if not candidates:
            readable = ", ".join(sorted(supported_suffixes()))
            raise AttachmentError(
                f"Zaram has no parser for {suffix or 'a file with no extension'}. "
                f"It can read: {readable}."
            )

        identifier = f"{PREFIX}{uuid.uuid4().hex[:12]}"
        # The name is not used on disk. A filename from outside is untrusted
        # input, and a path built from one is a traversal waiting to be found;
        # the original is carried in the record instead, where it is data.
        path = self._root / f"{identifier}{suffix}"
        path.write_bytes(data)

        result = None
        last_error = ""
        for parser in candidates:
            available, remedy = parser.available()
            if not available:
                last_error = remedy
                continue
            try:
                result = parser.parse(path)
                break
            except Exception as exc:  # noqa: BLE001 — reported, not swallowed
                last_error = str(exc)

        if result is None or not result.text.strip():
            path.unlink(missing_ok=True)
            raise AttachmentError(
                f"Nothing came out of {name}."
                + (f" {last_error}" if last_error else "")
            )

        attachment = Attachment(
            id=identifier,
            session_id=session_id,
            name=name,
            suffix=suffix,
            path=str(path),
            text=result.text,
            parser=result.parser or (candidates[0].name if candidates else ""),
            pages=result.pages,
        )

        with self._lock:
            self._items[identifier] = attachment
            evicted = self._evict_locked(session_id)
        return attachment, evicted

    def _add_image(
        self, session_id: str, name: str, suffix: str, data: bytes
    ) -> tuple[Attachment, List[Attachment]]:
        """Hold an image for this conversation. No parsing, no text.

        `text` stays empty rather than being filled with a filename or a
        placeholder. An image has no extracted text, and inventing some would
        put a value nobody measured into the prompt — and worse, would make
        `compose` treat it as a document and try to excerpt it.

        Whether any installed model can *see* it is not decided here. This
        layer holds files; the gate is `ProviderManager.select_model_for_task`,
        and refusing at attach time would mean a user who later connects a
        vision-capable provider still cannot attach the picture they already
        have.
        """
        import base64

        identifier = f"{PREFIX}{uuid.uuid4().hex[:12]}"
        path = self._root / f"{identifier}{suffix}"
        path.write_bytes(data)

        attachment = Attachment(
            id=identifier,
            session_id=session_id,
            name=name,
            suffix=suffix,
            path=str(path),
            text="",
            parser="image",
            kind=AttachmentKind.IMAGE.value,
            # Ollama wants raw base64 with no data-URI prefix.
            data=base64.b64encode(data).decode("ascii"),
        )

        with self._lock:
            self._items[identifier] = attachment
            evicted = self._evict_locked(session_id)
        return attachment, evicted

    def _evict_locked(self, session_id: str) -> List[Attachment]:
        """Drop the oldest until this session is within its allowance."""
        mine = [a for a in self._items.values() if a.session_id == session_id]
        dropped: List[Attachment] = []
        while len(mine) > MAX_PER_SESSION:
            oldest = mine.pop(0)
            self._items.pop(oldest.id, None)
            Path(oldest.path).unlink(missing_ok=True)
            dropped.append(oldest)
        return dropped

    # -- reading -----------------------------------------------------------

    def get(self, attachment_id: str) -> Optional[Attachment]:
        with self._lock:
            return self._items.get(attachment_id)

    def for_session(self, session_id: str) -> List[Attachment]:
        with self._lock:
            return [a for a in self._items.values() if a.session_id == session_id]

    def resolve(self, session_id: str, ids: List[str]) -> tuple[List[Attachment], List[str]]:
        """The attachments named, and the ids that named nothing.

        Missing ids are returned rather than ignored. An id that no longer
        resolves means the file was evicted or the process restarted, and
        answering as though the document were present is the failure this
        whole module is arranged to avoid.

        **Session-checked.** An id from another conversation resolves to
        nothing here, so a guessed or stale id cannot pull a document into an
        exchange it was never attached to.
        """
        found: List[Attachment] = []
        missing: List[str] = []
        with self._lock:
            for identifier in ids:
                item = self._items.get(identifier)
                if item is None or item.session_id != session_id:
                    missing.append(identifier)
                else:
                    found.append(item)
        return found, missing

    # -- removing ----------------------------------------------------------

    def remove(self, attachment_id: str) -> bool:
        """Detach one. The bytes go with it — this is working state."""
        with self._lock:
            item = self._items.pop(attachment_id, None)
        if item is None:
            return False
        Path(item.path).unlink(missing_ok=True)
        return True

    def clear_session(self, session_id: str) -> int:
        with self._lock:
            ids = [k for k, v in self._items.items() if v.session_id == session_id]
            for identifier in ids:
                item = self._items.pop(identifier)
                Path(item.path).unlink(missing_ok=True)
        return len(ids)

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "attachments": len(self._items),
                "chars": sum(a.chars for a in self._items.values()),
            }

"""What a description resolved to, remembered so a revisit costs nothing.

Without this, opening a page again, or a second page that describes "Lagos
market" the same way, searches and downloads from scratch: against a source that
allows about twenty requests a minute, that is most of a page's allowance spent
learning what was already known. The index maps *(source, description)* to the
cached picture it produced and the credit that goes with it, so a repeat is
answered from disk with no request at all.

It is an optimisation and never an authority: every entry is checked against the
disk before it is used, a damaged or missing index file is the same as an empty
one, and deleting the file loses nothing but speed.

Retention
---------
The index follows the picture cache (`finder.CACHE_KEPT`, 80 files) and is no
more permanent than it:

* **An entry is only as long-lived as its file.** A lookup whose picture has
  been pruned drops that entry, and `drop_missing` removes every such entry
  right after the cache is pruned. Entries are also capped (`MAX_ENTRIES`),
  oldest dropped first.
* **"No match" is remembered for an hour** (`NO_MATCH_TTL`) and then forgotten.
  A search that came back empty is worth not repeating while a page is being
  revised, but a catalogue changes and a person who tries again tomorrow should
  get a fresh search. Only a *clean* empty answer is remembered -- never a rate
  limit, a refusal, a dead link or an unreadable response, none of which says
  anything about the catalogue.
* **No description is written down.** Entries are keyed by a hash of the source
  and the description as it was searched. What is stored is the picture's file
  name, its size and the credit the source gave (title, creator, licence, links),
  which the page needs anyway. The text that was sent lives only in the egress
  log, which has its own retention control.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Callable

from .guard import description_key
from .source import PhotoCandidate, PhotoSource

logger = logging.getLogger(__name__)

#: Sits beside the cache folder (``photos/web-index.json``), not inside it: the
#: folder holds only pictures, and only picture names are ever served from it.
INDEX_NAME = "web-index.json"
MAX_ENTRIES = 300
NO_MATCH_TTL = 3600.0
_VERSION = 1
_NAME = re.compile(r"^[a-z0-9]{2,8}-[0-9a-f]{16,40}\.(?:jpg|png|webp)$")
_MIMES = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
_LOCK = threading.RLock()
_FIELDS = {f.name for f in fields(PhotoCandidate)}


@dataclass(frozen=True)
class IndexHit:
    candidate: PhotoCandidate
    name: str
    mime: str
    size: int


def entry_key(source: PhotoSource, query: str) -> str:
    return hashlib.sha256(f"{source.slug}\0{description_key(query)}".encode()).hexdigest()[:24]


class PhotoIndex:
    def __init__(self, path: Path, clock: Callable[[], float] = time.time):
        self.path = Path(path)
        self._clock = clock

    # ------------------------------------------------------------------- read

    def lookup(self, source: PhotoSource, query: str, folder: Path, used: set[str]) -> IndexHit | None:
        """The remembered picture for this description, if it is still on disk.

        ``used`` are ids already placed on this page: a remembered picture that
        another description of the page took is skipped, so two photos on one
        page are never the same photograph.
        """
        key = entry_key(source, query)
        with _LOCK:
            entries = self._load()
            entry = entries.get(key)
            if not entry or entry.get("none"):
                return None
            hit = self._hit(entry, folder)
            if hit is None:
                del entries[key]  # its picture is gone: so is this
                self._save(entries)
                return None
        if hit.candidate.id in used:
            return None
        path = folder / hit.name
        try:
            os.utime(path, None)  # reading it counts as use, so it survives the next prune
        except OSError:
            pass
        return hit

    def known_empty(self, source: PhotoSource, query: str) -> bool:
        """True if this source recently answered this description with nothing usable."""
        with _LOCK:
            entry = self._load().get(entry_key(source, query))
        return bool(entry and entry.get("none"))

    # ------------------------------------------------------------------ write

    def remember(
        self, source: PhotoSource, query: str, candidate: PhotoCandidate, name: str, mime: str, size: int
    ) -> None:
        with _LOCK:
            entries = self._load()
            entries[entry_key(source, query)] = {
                "candidate": asdict(candidate),
                "name": name,
                "mime": mime,
                "size": size,
                "at": self._clock(),
            }
            self._save(entries)

    def remember_none(self, source: PhotoSource, query: str) -> None:
        with _LOCK:
            entries = self._load()
            entries[entry_key(source, query)] = {"none": True, "at": self._clock()}
            self._save(entries)

    def drop_missing(self, folder: Path) -> int:
        """Forget entries whose picture is no longer in ``folder``. Returns how many."""
        with _LOCK:
            entries = self._load()
            gone = [k for k, e in entries.items() if not e.get("none") and self._hit(e, folder) is None]
            for k in gone:
                del entries[k]
            if gone:
                self._save(entries)
            return len(gone)

    # --------------------------------------------------------------- internals

    def _hit(self, entry: dict, folder: Path) -> IndexHit | None:
        name = entry.get("name")
        raw = entry.get("candidate")
        # The name is checked against the cache's own shape: an index that has
        # been edited cannot point a lookup anywhere but at a cached picture.
        if not isinstance(name, str) or not _NAME.match(name) or not isinstance(raw, dict):
            return None
        path = folder / name
        if not path.is_file():
            return None
        try:
            candidate = PhotoCandidate(**{k: v for k, v in raw.items() if k in _FIELDS})
            size = path.stat().st_size
        except (TypeError, OSError):
            return None
        mime = _MIMES.get(path.suffix)
        return IndexHit(candidate, name, mime, size) if mime else None

    def _load(self) -> dict[str, dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict) or data.get("version") != _VERSION:
            return {}
        raw = data.get("entries")
        if not isinstance(raw, dict):
            return {}
        now = self._clock()
        return {
            k: e
            for k, e in raw.items()
            if isinstance(e, dict) and not (e.get("none") and now - float(e.get("at") or 0) > NO_MATCH_TTL)
        }

    def _save(self, entries: dict[str, dict]) -> None:
        if len(entries) > MAX_ENTRIES:
            keep = sorted(entries.items(), key=lambda kv: float(kv[1].get("at") or 0), reverse=True)
            entries = dict(keep[:MAX_ENTRIES])
        tmp = self.path.with_name(f".{uuid.uuid4().hex}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps({"version": _VERSION, "entries": entries}), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            logger.debug("could not write the photo index", exc_info=True)
            try:
                tmp.unlink()
            except OSError:
                pass


def index_for(folder: Path) -> PhotoIndex:
    """The index that goes with a cache folder."""
    return PhotoIndex(Path(folder).parent / INDEX_NAME)

"""Knowledge that stays current — a watched folder re-reads what changed.

A folder pointed at once was a snapshot. The contract the user edited on
Tuesday was still the Monday version in recall, and nothing said so; a
question about the new payment terms got the old ones, cited, with
confidence. Stale recall does not look stale — it looks like memory.

So every folder in Knowledge is watched (`watchfiles`, MIT — a Rust
notifier, one thread for all roots, no polling), and a file that changes is
re-read the way the retry button re-reads it: the same `ingest_folder` with
one path, replacing that path's outcome and writing its facts again. A
file that appears is read; one that disappears has its outcome marked as
gone rather than deleted, so Knowledge can show that it went.

What this deliberately is not:

* **Not a scanner of anything the user did not name.** Only roots already
  in the sources table are watched. Zaram's own uploads folder is skipped —
  its files are copies Zaram wrote, and re-reading a file the moment it was
  ingested would be the loop this exists to end.
* **Not eager.** Changes are debounced so a file saved four times in a
  minute is read once, and a burst under one root is read as one batch.
* **Not a second index.** It calls the ingest service; it stores nothing of
  its own.

Facts from a re-read are written through the same writer the first read
used, which is also what `retry` does; the Spine's own consolidation is
what keeps a twice-read sentence from being two facts.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Callable, Iterable

logger = logging.getLogger(__name__)

#: How long a burst of changes may settle before it is read, in ms. A save
#: from Word is several writes; a git checkout is hundreds.
DEBOUNCE_MS = 1600
#: How often the set of watched roots is re-read, so a folder added or
#: withdrawn in Settings is picked up without a restart.
REFRESH_MS = 20_000


def watched_roots(records: Any, is_staged: Callable[[str], bool]) -> list[str]:
    """Every source root that is a real folder of the user's own files."""
    roots: list[str] = []
    for source in records.sources():
        root = str(source.get("root") or "")
        if not root or is_staged(root) or not os.path.isdir(root):
            continue
        roots.append(root)
    return roots


def group_by_root(paths: Iterable[str], roots: Iterable[str]) -> dict[str, list[Path]]:
    """Changed paths under the root that contains them. The deepest root wins
    when one watched folder is inside another."""
    ordered = sorted((os.path.abspath(r) for r in roots), key=len, reverse=True)
    out: dict[str, list[Path]] = {}
    for raw in paths:
        p = Path(raw)
        for root in ordered:
            try:
                p.resolve().relative_to(Path(root).resolve())
            except (ValueError, OSError):
                continue
            out.setdefault(root, []).append(p)
            break
    return out


class SourceWatcher:
    """Runs for the life of the backend. `run()` is the task; `stop()` ends it."""

    def __init__(self, service: Any) -> None:
        self._service = service
        self._stop = asyncio.Event()
        #: Counts, for `/health` and for tests: what has been re-read so far.
        self.reread = 0
        self.gone = 0

    def stop(self) -> None:
        self._stop.set()

    def _roots(self) -> list[str]:
        return watched_roots(self._service.records, self._service.is_staged_source)

    async def run(self) -> None:
        try:
            from watchfiles import awatch
        except ImportError:  # pragma: no cover - declared; a build without it just does not watch
            logger.info("watchfiles unavailable; Knowledge folders are not watched")
            return
        while not self._stop.is_set():
            roots = self._roots()
            if not roots:
                # Nothing to watch yet. Look again shortly rather than exit —
                # the first folder is usually added minutes after boot.
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=REFRESH_MS / 1000)
                except asyncio.TimeoutError:
                    pass
                continue
            logger.info("Watching %d Knowledge folder(s) for changes", len(roots))
            try:
                async for changes in awatch(
                    *roots,
                    debounce=DEBOUNCE_MS,
                    stop_event=self._stop,
                    rust_timeout=REFRESH_MS,
                    yield_on_timeout=True,
                    recursive=True,
                ):
                    if not changes:
                        # The timeout: re-read the roots in case Settings
                        # changed them, by leaving this loop.
                        if set(self._roots()) != set(roots):
                            break
                        continue
                    await self._apply(changes, roots)
            except Exception:  # noqa: BLE001 - the watcher must never take the backend down
                logger.warning("Knowledge watcher stopped on an error; retrying", exc_info=True)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass

    async def _apply(self, changes: set, roots: list[str]) -> None:
        """One batch of changes, per root, off the event loop."""
        from watchfiles import Change

        touched = [p for kind, p in changes if kind in (Change.added, Change.modified)]
        removed = [p for kind, p in changes if kind is Change.deleted]
        for root, paths in group_by_root(touched, roots).items():
            paths = [p for p in paths if p.is_file() and not p.name.startswith(("~$", "."))]
            if not paths:
                continue
            try:
                await asyncio.to_thread(self._reread, root, paths)
            except Exception:  # noqa: BLE001
                logger.warning("Re-reading %d file(s) under %s failed", len(paths), root, exc_info=True)
        for root, paths in group_by_root(removed, roots).items():
            try:
                await asyncio.to_thread(self._mark_gone, root, paths)
            except Exception:  # noqa: BLE001
                logger.warning("Marking files gone under %s failed", root, exc_info=True)

    def _reread(self, root: str, paths: list[Path]) -> None:
        """The retry button's path, for several files at once."""
        from .service import ingest_folder

        service = self._service
        report = ingest_folder(
            root,
            store_fact=service._fact_writer(None),
            read_obligations=(service._read_obligations if service.obligations is not None else None),
            paths=paths,
        )
        source_id = service.records.upsert_source(report.root, seconds=report.seconds)
        service.records.record_outcomes(source_id, list(report.outcomes))
        self.reread += len(report.outcomes)
        logger.info("Re-read %d changed file(s) under %s", len(report.outcomes), root)

    def _mark_gone(self, root: str, paths: list[Path]) -> None:
        from .contracts import IngestOutcome, IngestStatus

        records = self._service.records
        source_id = records.upsert_source(root)
        outcomes = [
            IngestOutcome(
                path=str(p),
                status=IngestStatus.FAILED,
                reason="The file is no longer where it was — it may have been moved or renamed.",
            )
            for p in paths
        ]
        records.record_outcomes(source_id, outcomes)
        self.gone += len(outcomes)

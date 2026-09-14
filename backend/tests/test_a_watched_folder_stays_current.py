"""Knowledge stays current: a file that changes in a watched folder is re-read.

`ingest/watcher.py`. Real files, the real notifier, one change observed —
because a watcher whose only test is a unit around its callbacks is a
watcher nobody has seen fire. Three contracts: a change is re-read and its
outcome replaced; a file that goes is marked gone rather than dropped; and
Zaram's own uploads folder is never watched.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from ingest.records import IngestRecords
from ingest.service_api import IngestService
from ingest.watcher import SourceWatcher, group_by_root, watched_roots


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path / "data"))
    records = IngestRecords(str(tmp_path / "ingest.db"))
    return IngestService(records)


async def _until(predicate, seconds: float = 8.0) -> bool:
    deadline = asyncio.get_event_loop().time() + seconds
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.1)
    return predicate()


class TestAChangeIsReread:
    async def test_editing_a_file_replaces_its_outcome(self, service, tmp_path):
        folder = tmp_path / "clients"
        folder.mkdir()
        doc = folder / "terms.txt"
        doc.write_text("Payment is due within 30 days of the invoice date.", encoding="utf-8")
        source_id, _ = service.scan(str(folder))
        before = [o for o in service.records.outcomes(source_id) if o["path"].endswith("terms.txt")]
        assert before and before[0]["status"] == "indexed"
        first_chars = before[0]["chars"]

        watcher = SourceWatcher(service)
        task = asyncio.create_task(watcher.run())
        try:
            await asyncio.sleep(0.6)  # let the notifier attach
            doc.write_text(
                "Payment is due within 14 days of the invoice date, and 2% is added after 45.",
                encoding="utf-8",
            )
            assert await _until(lambda: watcher.reread >= 1), "the change was never re-read"
        finally:
            watcher.stop()
            await asyncio.wait_for(task, timeout=5)

        after = [o for o in service.records.outcomes(source_id) if o["path"].endswith("terms.txt")]
        assert len(after) == 1, "a re-read must replace the outcome, not add one"
        assert after[0]["status"] == "indexed"
        assert after[0]["chars"] != first_chars

    async def test_a_file_that_goes_is_marked_gone_not_dropped(self, service, tmp_path):
        folder = tmp_path / "clients"
        folder.mkdir()
        doc = folder / "old.txt"
        doc.write_text("A note that will be removed from the folder.", encoding="utf-8")
        source_id, _ = service.scan(str(folder))

        watcher = SourceWatcher(service)
        task = asyncio.create_task(watcher.run())
        try:
            await asyncio.sleep(0.6)
            os.remove(doc)
            assert await _until(lambda: watcher.gone >= 1), "the removal was never seen"
        finally:
            watcher.stop()
            await asyncio.wait_for(task, timeout=5)

        outcomes = [o for o in service.records.outcomes(source_id) if o["path"].endswith("old.txt")]
        assert len(outcomes) == 1
        assert outcomes[0]["status"] == "failed"
        assert "no longer where it was" in outcomes[0]["reason"]


class TestWhatIsWatched:
    def test_the_uploads_folder_is_never_watched(self, service, tmp_path):
        uploads = service.uploads_dir()
        service.records.upsert_source(str(uploads))
        own = tmp_path / "mine"
        own.mkdir()
        service.records.upsert_source(str(own))

        roots = watched_roots(service.records, service.is_staged_source)

        assert str(own.resolve()) in [str(Path(r).resolve()) for r in roots]
        assert all(Path(r).resolve() != uploads.resolve() for r in roots)

    def test_a_change_is_filed_under_the_deepest_root_that_holds_it(self, tmp_path):
        outer = tmp_path / "a"
        inner = outer / "b"
        inner.mkdir(parents=True)
        grouped = group_by_root([str(inner / "x.txt"), str(outer / "y.txt")], [str(outer), str(inner)])
        assert [p.name for p in grouped[str(inner.resolve()) if str(inner.resolve()) in grouped else str(inner)]] == ["x.txt"]

"""Recall count has to be a real number, because rule 7e leans on it.

    Facts enter provisionally, become durable through use, and decay if never
    recalled. The user is not asked to decide at creation — only to correct
    afterwards.

That whole mechanism is one integer, and it was never incremented on the store
the product actually runs. Every fact read "Recalled 0 times" in the Memory
surface no matter how often it was cited, and `decay.py` — which forgets
anything never accessed after 30 days — saw a Spine in which nothing had ever
been used.

Found by driving the interface in a browser, not by a unit test: the number was
sitting on screen next to a fact that had just been recalled and cited.

Both stores are tested, in the same tests, because the bug was precisely that
they disagreed — `InMemoryMemoryStore` incremented as a side effect of `get`
and `SQLiteMemoryStore` had no equivalent at all.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from runtimes.memory.contracts import MemoryRecord, MemoryType
from runtimes.memory.store import InMemoryMemoryStore, SQLiteMemoryStore


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path: Path):
    if request.param == "memory":
        return InMemoryMemoryStore()
    return SQLiteMemoryStore(str(tmp_path / "spine.db"))


def _record(content: str = "The day rate is 425,000 naira.") -> MemoryRecord:
    return MemoryRecord(content=content, memory_type=MemoryType.SEMANTIC)


class TestRecordAccess:
    def test_a_new_fact_starts_at_zero(self, store):
        async def run():
            record = _record()
            await store.put(record)
            return await store.get(record.id)

        assert asyncio.run(run()).access_count == 0

    def test_recording_access_increments(self, store):
        async def run():
            record = _record()
            await store.put(record)
            await store.record_access(record.id)
            await store.record_access(record.id)
            return await store.get(record.id)

        assert asyncio.run(run()).access_count == 2

    def test_reading_is_not_recalling(self, store):
        """Opening the Memory surface must not make a fact look load-bearing.

        This was the in-memory store's behaviour — `get` incremented — and it
        would have inflated every fact the user merely looked at.
        """
        async def run():
            record = _record()
            await store.put(record)
            for _ in range(5):
                await store.get(record.id)
            return await store.get(record.id)

        assert asyncio.run(run()).access_count == 0

    def test_recording_access_updates_the_timestamp(self, store):
        """`decay.py` scores on recency as well as count."""
        async def run():
            record = _record()
            await store.put(record)
            before = (await store.get(record.id)).last_accessed
            await asyncio.sleep(0.01)
            await store.record_access(record.id)
            return before, (await store.get(record.id)).last_accessed

        before, after = asyncio.run(run())
        assert after > before

    def test_recording_access_on_a_missing_record_is_silent(self, store):
        """A record deleted between retrieval and counting is ordinary."""
        asyncio.run(store.record_access("does-not-exist"))

    def test_access_is_only_counted_on_the_named_record(self, store):
        async def run():
            a, b = _record("Fact A."), _record("Fact B.")
            await store.put(a)
            await store.put(b)
            await store.record_access(a.id)
            return (await store.get(a.id)).access_count, (await store.get(b.id)).access_count

        assert asyncio.run(run()) == (1, 0)


class TestRetrieveCountsTheRecall:
    """The seam. A store that counts and a runtime that never calls it is the
    same bug in a different place."""

    def test_a_recalled_fact_has_its_count_raised(self, tmp_path: Path):
        from runtimes.memory.runtime import MemoryRuntimeImpl

        async def run():
            runtime = MemoryRuntimeImpl(
                store_type="sqlite", db_path=str(tmp_path / "spine.db"), index_type="hybrid"
            )
            await runtime.initialize()
            fact_id = await runtime.remember(
                content="My day rate for Ashgrove Films is 612,500 naira.",
                memory_type=MemoryType.SEMANTIC,
            )
            before = (await runtime.get_record(fact_id)).access_count
            await runtime.retrieve(query="Ashgrove Films day rate", max_results=5)
            after = (await runtime.get_record(fact_id)).access_count
            await runtime.shutdown()
            return before, after

        before, after = asyncio.run(run())
        assert before == 0
        assert after == 1, (
            "a fact that was retrieved and cited still reported never having "
            "been recalled — which is the number rule 7e promotes and decays on"
        )

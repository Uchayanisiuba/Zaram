"""Correcting a fact must change the answers that depended on it.

Rule 4 of the project contract. Deletion already satisfied half of it, so these
tests are aimed at the half that was missing: after a correction, the old fact
must be *unrecallable* but still *visible*.

The failure mode worth guarding against is subtle. A correction that marks the
old record and writes a new one looks correct in every unit test of the store —
and still does nothing, because the old fact is sitting in the vector index and
comes back from the next search regardless of what the store thinks. Several of
these tests go through retrieval rather than the store for exactly that reason.

This was not hypothetical either: a cross-model recall check handed the model two
contradictory facts about the same event, both live, and it answered from the
right one by luck.
"""

from __future__ import annotations

import pytest

from runtimes.memory import create_memory_runtime
from runtimes.memory.contracts import MemoryQuery, MemoryType


@pytest.fixture
async def memory(tmp_path):
    """A real Spine on disk, with the hash embedder so tests need no Ollama."""
    runtime = create_memory_runtime(
        store_type="sqlite",
        db_path=str(tmp_path / "spine.db"),
        index_type="hybrid",
        embedding_dim=384,
        embedding_backend="hash",
    )
    await runtime.initialize()
    return runtime


class TestCorrectionChangesRecall:
    async def test_superseded_fact_is_not_recalled(self, memory):
        """The whole point. If this passes trivially, check the index."""
        old = await memory.store(
            "The launch is 9 September in Bristol.", MemoryType.SEMANTIC
        )
        await memory.correct(old, "The launch is 14 November in Bristol.")

        results = await memory.retrieve("When is the launch?", max_results=10)
        contents = [r.record.content for r in results]

        assert not any("9 September" in c for c in contents), (
            "the corrected fact is still being recalled, so the correction "
            "changed nothing the user can observe"
        )
        assert any("14 November" in c for c in contents)

    async def test_the_original_is_kept_not_deleted(self, memory):
        old = await memory.store("Bristol is the venue.", MemoryType.SEMANTIC)
        await memory.correct(old, "Cardiff is the venue.")

        record = await memory.get_record(old)
        assert record is not None, "correction must not delete the original"
        assert record.content == "Bristol is the venue.", "the original text must survive"
        assert record.is_superseded
        assert record.superseded_at is not None

    async def test_supersession_points_at_the_replacement(self, memory):
        old = await memory.store("The deadline is Friday.", MemoryType.SEMANTIC)
        result = await memory.correct(old, "The deadline is Monday.")

        record = await memory.get_record(old)
        assert record.superseded_by == result["replacement_id"]

        replacement = await memory.get_record(result["replacement_id"])
        assert replacement.metadata["corrects"] == old

    async def test_correction_survives_a_restart(self, memory, tmp_path):
        """The index is rebuilt from the store on boot.

        If the rebuild does not filter superseded records, every correction the
        user ever made is silently undone the next time Zaram starts — which
        would be worse than not having the feature, because they would believe
        it had worked.
        """
        old = await memory.store(
            "The launch is 9 September in Bristol.", MemoryType.SEMANTIC
        )
        await memory.correct(old, "The launch is 14 November in Bristol.")

        reopened = create_memory_runtime(
            store_type="sqlite",
            db_path=str(tmp_path / "spine.db"),
            index_type="hybrid",
            embedding_dim=384,
            embedding_backend="hash",
        )
        await reopened.initialize()

        results = await reopened.retrieve("When is the launch?", max_results=10)
        contents = [r.record.content for r in results]
        assert not any("9 September" in c for c in contents), (
            "a restart resurrected the corrected fact"
        )

    async def test_a_correction_can_itself_be_corrected(self, memory):
        first = await memory.store("The venue is Bristol.", MemoryType.SEMANTIC)
        second = (await memory.correct(first, "The venue is Cardiff."))["replacement_id"]
        third = (await memory.correct(second, "The venue is Bath."))["replacement_id"]

        assert (await memory.get_record(first)).superseded_by == second
        assert (await memory.get_record(second)).superseded_by == third
        assert (await memory.get_record(third)).is_superseded is False

        results = await memory.retrieve("Where is the venue?", max_results=10)
        contents = [r.record.content for r in results]
        assert any("Bath" in c for c in contents)
        assert not any("Bristol" in c or "Cardiff" in c for c in contents)

    async def test_correcting_twice_is_refused(self, memory):
        """Two corrections of the same record would fork the chain."""
        old = await memory.store("Original.", MemoryType.SEMANTIC)
        await memory.correct(old, "First correction.")

        with pytest.raises(ValueError, match="already corrected"):
            await memory.correct(old, "Second correction.")

    async def test_correcting_something_that_does_not_exist(self, memory):
        with pytest.raises(KeyError):
            await memory.correct("no-such-id", "anything")


class TestSupersededRemainsVisible:
    async def test_the_surface_can_still_list_it(self, memory):
        """Excluded from recall, present in the Memory surface, struck through."""
        old = await memory.store("The venue is Bristol.", MemoryType.SEMANTIC)
        await memory.correct(old, "The venue is Cardiff.")

        everything = await memory._store.all_records(include_superseded=True)
        assert any(r.id == old for r in everything)

        live_only = await memory._store.all_records()
        assert not any(r.id == old for r in live_only)


class TestPinning:
    async def test_pinned_facts_come_first(self, memory):
        await memory.store("An ordinary later fact.", MemoryType.SEMANTIC)
        pinned_id = await memory.store("A fact that matters.", MemoryType.SEMANTIC)
        await memory.set_pinned(pinned_id, True)

        records = await memory._store.query(
            MemoryQuery(query="", memory_types=[MemoryType.SEMANTIC], max_results=10)
        )
        assert records[0].id == pinned_id, "the user said this one matters"

    async def test_pinning_survives_a_correction(self, memory):
        original = await memory.store("Pinned original.", MemoryType.SEMANTIC)
        await memory.set_pinned(original, True)
        result = await memory.correct(original, "Pinned correction.")

        replacement = await memory.get_record(result["replacement_id"])
        assert replacement.pinned is True, (
            "correcting a pinned fact must not quietly unpin it"
        )

    async def test_pinning_an_unknown_record_reports_failure(self, memory):
        assert await memory.set_pinned("no-such-id", True) is False

"""Rule 7e, end to end: does decay actually happen to a real Spine?

`test_memory_runtime.py` already grades the decay *rules* — what should be
forgotten, what should be boosted — and it passes. It has always passed. It
runs against `InMemoryMemoryStore`, and the product runs on SQLite.

That is the same shape as the `access_count` defect this codebase already paid
for: two implementations of one contract, one of them exercised by every test
and neither of them by the product. The rules were never the part that was
broken.

These tests are about *reach*, not about policy:

- the decay pass sees the records in the store the product uses
- something in the running system calls it

Both halves have to hold. A correct rule nothing invokes and an invoked pass
that sees an empty list are the same product behaviour — a Spine that grows
forever and never promotes anything through use.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from runtimes.memory.contracts import MemoryRecord, MemoryType
from runtimes.memory.decay import DecayConfig, MemoryDecayEngine
from runtimes.memory.store import InMemoryMemoryStore, SQLiteMemoryStore


def _old_record(
    record_id: str,
    *,
    importance: float = 0.2,
    access_count: int = 0,
    last_accessed: float | None = None,
) -> MemoryRecord:
    """A fact stored 200 days ago, recalled as often as the caller says.

    With the defaults it is what rule 7e describes decaying away: it entered
    provisionally and use never made it durable.

    Built through the constructor rather than mutated after the fact —
    `MemoryRecord` is frozen, which is the right shape for something a
    correction has to supersede rather than overwrite.
    """
    long_ago = time.time() - 200 * 86400
    return MemoryRecord(
        id=record_id,
        content="A day rate nobody has asked about since it was captured.",
        memory_type=MemoryType.SEMANTIC,
        importance=importance,
        created_at=long_ago,
        updated_at=long_ago,
        last_accessed=long_ago if last_accessed is None else last_accessed,
        access_count=access_count,
    )


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    """Both implementations of the contract, run through the same assertions.

    Parameterised rather than written twice on purpose. The two stores drifting
    apart unnoticed is the recurring defect in this module, and the cheapest
    guard against it is never testing one without the other.
    """
    if request.param == "memory":
        s = InMemoryMemoryStore()
    else:
        s = SQLiteMemoryStore(db_path=str(tmp_path / "spine.db"))
    asyncio.run(s.initialize()) if hasattr(s, "initialize") else None
    return s


class TestDecayReachesTheRecords:
    def test_a_decay_pass_sees_what_is_in_the_store(self, store):
        """The pass must enumerate through the contract, not a private field.

        `apply_decay` read `store._records`, which only `InMemoryMemoryStore`
        has. On SQLite that is not an error — `hasattr` is false, the id list is
        empty, and the pass reports a clean run over zero records. Silent,
        green, and completely inert.
        """
        async def run():
            await store.put(_old_record("stale-1"))
            await store.put(_old_record("stale-2"))

            engine = MemoryDecayEngine(DecayConfig())
            result = await engine.apply_decay(store)
            return result

        result = asyncio.run(run())

        assert result.total_records + result.forgotten == 2, (
            f"the decay pass accounted for {result.total_records + result.forgotten} "
            f"of 2 records in a {type(store).__name__}. It is not reading the "
            f"store through the contract."
        )

    def test_an_old_never_recalled_fact_is_forgotten(self, store):
        """Rule 7e's actual promise, on the store the product runs."""
        async def run():
            await store.put(_old_record("stale-1"))
            engine = MemoryDecayEngine(DecayConfig())
            await engine.apply_decay(store)
            return await store.get("stale-1")

        assert asyncio.run(run()) is None, (
            "a fact 200 days old and never once recalled survived a decay pass"
        )

    def test_a_recalled_fact_survives(self, store):
        """The other half of 7e — use is what makes a fact durable.

        Without this the first test passes for a decay pass that deletes
        everything, which is not a memory.
        """
        async def run():
            await store.put(_old_record(
                "used-1", importance=0.6, access_count=12,
                last_accessed=time.time(),
            ))

            engine = MemoryDecayEngine(DecayConfig())
            await engine.apply_decay(store)
            return await store.get("used-1")

        assert asyncio.run(run()) is not None, (
            "a fact recalled twelve times was forgotten — decay is deleting on "
            "age alone and use counts for nothing"
        )


class _FakeMemoryRuntime:
    """Records what the maintenance pass asked it to do.

    A fake rather than a real runtime because the question here is *scheduling*
    — did anything call it, once, with failures contained — and a real runtime
    would drag an embedder into a test about timers.
    """

    def __init__(self, decay_raises: bool = False, promote_raises: bool = False):
        self.decay_calls = 0
        self.promote_calls = 0
        self._decay_raises = decay_raises
        self._promote_raises = promote_raises

    async def apply_decay(self, decay_threshold: float = 0.1):
        self.decay_calls += 1
        if self._decay_raises:
            raise RuntimeError("the disk went away")
        return {"forgotten": 2, "decayed": 1, "boosted": 0}

    async def promotion_candidates(self):
        self.promote_calls += 1
        if self._promote_raises:
            raise RuntimeError("no")

        class _R:
            id = "fact-1"

        return [_R()]


class TestSomethingActuallyRunsIt:
    """The half that was missing entirely.

    Correct decay rules that nothing invokes are indistinguishable, from the
    user's side, from no decay rules at all.
    """

    def test_a_pass_calls_both_halves(self):
        from runtimes.memory.maintenance import SpineMaintenance

        runtime = _FakeMemoryRuntime()
        result = asyncio.run(SpineMaintenance(runtime).run_once())

        assert runtime.decay_calls == 1
        assert runtime.promote_calls == 1
        assert result["decay"]["forgotten"] == 2
        assert result["promotion_candidates"] == ["fact-1"]

    def test_a_failing_decay_does_not_stop_promotion(self):
        """The two halves fail independently.

        They share a pass because they share a full scan, not because either
        needs the other. Letting one exception end the pass would mean a
        transient disk error silently disabling promotion offers as well.
        """
        from runtimes.memory.maintenance import SpineMaintenance

        runtime = _FakeMemoryRuntime(decay_raises=True)
        result = asyncio.run(SpineMaintenance(runtime).run_once())

        assert "error" in result["decay"]
        assert result["promotion_candidates"] == ["fact-1"], (
            "a failed decay pass took the promotion scan down with it"
        )

    def test_the_timer_runs_a_pass_and_stops_cleanly(self):
        """The scheduling itself, at a millisecond scale rather than a daily one."""
        from runtimes.memory.maintenance import SpineMaintenance

        runtime = _FakeMemoryRuntime()

        async def run():
            maint = SpineMaintenance(
                runtime, interval_seconds=0.05, initial_delay_seconds=0.0
            )
            maint.start()
            await asyncio.sleep(0.2)
            await maint.stop()
            # Cancelling must actually stop it, or shutdown leaves a task
            # writing to a store the kernel has already closed.
            settled = runtime.decay_calls
            await asyncio.sleep(0.15)
            return settled, runtime.decay_calls

        settled, after_stop = asyncio.run(run())

        assert settled >= 2, f"the timer ran {settled} passes in four intervals"
        assert after_stop == settled, (
            f"the pass kept running after stop() — {after_stop} calls against "
            f"{settled} at shutdown"
        )

    def test_nothing_has_run_is_distinguishable_from_nothing_changed(self):
        """`last_result` is None before the first pass, not an empty dict.

        The endpoint reports this straight to the user. "No maintenance has
        happened yet" and "maintenance ran and found nothing to do" are
        different facts about the system, and collapsing them is how an inert
        feature looks healthy — which is the exact failure this module exists
        to correct.
        """
        from runtimes.memory.maintenance import SpineMaintenance

        maint = SpineMaintenance(_FakeMemoryRuntime())
        assert maint.last_result is None

        asyncio.run(maint.run_once())
        assert maint.last_result is not None

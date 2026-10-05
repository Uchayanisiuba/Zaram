"""Memory can be emptied, by range and by scope, on purpose.

Asked for 3 October 2026 — *"a purge memory button ... purge Zaram's
entire memory, or purge/delete in ranges, by date"* — with the right
question attached: *"is there a better way to do this, is it wise."*

It is wise and it is owed rather than new. Rule 4 says the user can delete
any stored fact. The third 2026 obligation is blunter: *no new store ships
without an answer to how long it keeps things and how the user shortens
that. A store with no retention answer is an unshipped feature.*

Three properties here are the design rather than the implementation, and
each has its own class:

* **Counting is the default.** A purge cannot be undone, so the safety is a
  number read beforehand, not a dialog dismissed. `TestItCountsBeforeItCuts`.
* **Scope sits beside the date**, and is more often what somebody means.
  `TestScopeIsTheOtherAxis`.
* **The model cannot reach it.** `TestNothingTheModelSaysCanTriggerIt` — a
  purge reachable from a tool call is a prompt-injection target aimed at
  the one asset the product exists to keep.
"""

from __future__ import annotations

import time

import pytest

GLOBAL = "global"


@pytest.fixture
async def runtime(tmp_path):
    """A memory runtime over a temporary store, with no embedder.

    Purge is pure bookkeeping — it reads `created_at` and `scope` and calls
    `forget`. Nothing here needs a model, and wiring one in would make these
    tests depend on what is loaded on the machine running them.
    """
    from runtimes.memory.runtime import MemoryRuntimeImpl

    impl = MemoryRuntimeImpl(
        store_type="sqlite",
        db_path=str(tmp_path / "spine.db"),
        embedding_backend="hash",
        embed_on_gpu=False,
    )
    await impl.initialize()
    return impl


async def remember(runtime, content, *, scope=GLOBAL, created_at=None):
    """One fact, optionally backdated."""
    from runtimes.memory.contracts import MemoryType

    record_id = await runtime.remember(
        content=content, memory_type=MemoryType.SEMANTIC, scope=scope
    )
    if created_at is not None:
        record = await runtime._store.get(record_id)
        if record is not None:
            object.__setattr__(record, "created_at", created_at) if hasattr(
                record, "__dataclass_fields__"
            ) else None
            try:
                record.created_at = created_at
            except Exception:
                pass
            await runtime._store.put(record)
    return record_id


DAY = 86_400.0


@pytest.mark.asyncio
class TestItCountsBeforeItCuts:
    """The one decision that matters.

    "Remove 1,284 facts across 3 projects" is a sentence somebody can
    disagree with. "Are you sure?" is not.
    """

    async def test_a_purge_with_no_confirmation_deletes_nothing(self, runtime):
        await remember(runtime, "the rate is 450 a day")
        summary = await runtime.purge()
        assert summary["matched"] == 1
        assert summary["deleted"] == 0
        assert summary["dry_run"] is True
        assert len(await runtime._store.all_records()) == 1

    async def test_and_says_what_would_go(self, runtime):
        await remember(runtime, "a", scope="project:ride-share")
        await remember(runtime, "b", scope="project:keyline")
        summary = await runtime.purge()
        assert summary["matched"] == 2
        assert summary["scopes"] == ["project:keyline", "project:ride-share"]

    async def test_it_names_the_span_not_only_the_count(self, runtime):
        """A bare number cannot tell "1,284 stray notes" from "1,284 facts
        about the only client you have"."""
        now = time.time()
        await remember(runtime, "old", created_at=now - 30 * DAY)
        await remember(runtime, "new", created_at=now)
        summary = await runtime.purge()
        assert summary["oldest"] < summary["newest"]

    async def test_confirming_actually_removes(self, runtime):
        await remember(runtime, "the rate is 450 a day")
        summary = await runtime.purge(dry_run=False)
        assert summary["deleted"] == 1
        assert await runtime._store.all_records() == []

    async def test_an_empty_match_is_reported_not_an_error(self, runtime):
        summary = await runtime.purge(scope="project:nothing-here")
        assert summary["matched"] == 0
        assert summary["oldest"] is None


@pytest.mark.asyncio
class TestTheRange:
    async def test_before_removes_the_old_ones(self, runtime):
        """Retention — the ordinary case."""
        now = time.time()
        await remember(runtime, "old", created_at=now - 30 * DAY)
        await remember(runtime, "recent", created_at=now)
        summary = await runtime.purge(before=now - DAY, dry_run=False)
        assert summary["deleted"] == 1
        left = await runtime._store.all_records()
        assert [r.content for r in left] == ["recent"]

    async def test_after_removes_the_new_ones(self, runtime):
        """Mistake recovery: *I pointed it at the wrong folder on Tuesday.*
        Rarer than retention and not hypothetical, and it costs nothing
        once there is a range."""
        now = time.time()
        await remember(runtime, "kept", created_at=now - 30 * DAY)
        await remember(runtime, "the wrong folder", created_at=now)
        summary = await runtime.purge(after=now - DAY, dry_run=False)
        assert summary["deleted"] == 1
        left = await runtime._store.all_records()
        assert [r.content for r in left] == ["kept"]

    async def test_a_window_keeps_both_ends(self, runtime):
        now = time.time()
        await remember(runtime, "before the window", created_at=now - 30 * DAY)
        await remember(runtime, "inside", created_at=now - 10 * DAY)
        await remember(runtime, "after the window", created_at=now)
        await runtime.purge(before=now - 5 * DAY, after=now - 20 * DAY, dry_run=False)
        left = {r.content for r in await runtime._store.all_records()}
        assert left == {"before the window", "after the window"}

    async def test_a_swapped_range_is_refused_rather_than_silently_empty(self, runtime):
        """An empty window is almost certainly a swapped pair, and deleting
        nothing would read as the button being broken."""
        now = time.time()
        with pytest.raises(ValueError) as caught:
            await runtime.purge(before=now - 10 * DAY, after=now)
        assert "holds nothing" in str(caught.value)


@pytest.mark.asyncio
class TestScopeIsTheOtherAxis:
    """Rule 7i already puts `global` or `project:<id>` on every fact.

    *Forget everything about Ride Share* is a more common and more
    answerable request than *forget everything before October*, and a purge
    that took only dates would make the common case impossible.
    """

    async def test_one_project_goes_and_the_others_stay(self, runtime):
        await remember(runtime, "a", scope="project:ride-share")
        await remember(runtime, "b", scope="project:keyline")
        await remember(runtime, "c", scope=GLOBAL)
        await runtime.purge(scope="project:ride-share", dry_run=False)
        left = {r.content for r in await runtime._store.all_records()}
        assert left == {"b", "c"}

    async def test_global_facts_are_not_swept_with_a_project(self, runtime):
        """Global is about the person, not the work. Losing *how they like
        things written* because a project ended is the wrong trade."""
        await remember(runtime, "writes in plain sentences", scope=GLOBAL)
        await remember(runtime, "the deadline moved", scope="project:ride-share")
        await runtime.purge(scope="project:ride-share", dry_run=False)
        left = await runtime._store.all_records()
        assert [r.content for r in left] == ["writes in plain sentences"]

    async def test_scope_and_date_narrow_together(self, runtime):
        now = time.time()
        await remember(runtime, "old ride", scope="project:ride-share", created_at=now - 30 * DAY)
        await remember(runtime, "new ride", scope="project:ride-share", created_at=now)
        await remember(runtime, "old key", scope="project:keyline", created_at=now - 30 * DAY)
        await runtime.purge(scope="project:ride-share", before=now - DAY, dry_run=False)
        left = {r.content for r in await runtime._store.all_records()}
        assert left == {"new ride", "old key"}


@pytest.mark.asyncio
class TestItIsNotASoftDelete:
    """Rule 4's promise is that *affected answers change*. A fact hidden
    rather than removed still answers."""

    async def test_a_purged_fact_is_gone_from_the_store(self, runtime):
        await remember(runtime, "the rate is 450 a day")
        await runtime.purge(dry_run=False)
        assert await runtime._store.all_records() == []

    async def test_a_purged_fact_cannot_be_fetched_by_id(self, runtime):
        record_id = await remember(runtime, "the rate is 450 a day")
        await runtime.purge(dry_run=False)
        assert await runtime._store.get(record_id) is None


class TestNothingTheModelSaysCanTriggerIt:
    """**The most important property in this file.**

    A purge reachable from a tool call is a prompt-injection target aimed
    at the one asset the product exists to keep. A document saying *forget
    everything* must stay text Zaram read, never an instruction it can act
    on — the tool-description-is-third-party-text rule, applied to the
    worst possible verb.
    """

    def test_no_builtin_server_offers_a_purge_tool(self):
        """`core/bootstrapper.py` is where every tool the model can reach is
        handed to the MCP runtime. A purge tool would have to be named
        there, so that is what is scanned — not a comment promising it is
        not."""
        import inspect

        from core import bootstrapper

        assert "purge" not in inspect.getsource(bootstrapper).lower()

    def test_the_memory_tools_do_not_expose_it(self):
        """The memory runtime has `purge`, and the *tool surface* over it
        must not. Asserted against what is registered rather than against a
        comment saying so."""
        import inspect

        from runtimes.memory import runtime as module

        source = inspect.getsource(module)
        # The method exists; what must not is a registration that hands it
        # to the model.
        for shape in ('"memory.purge"', "'memory.purge'", 'name="purge"'):
            assert shape not in source, f"purge looks registered as a tool: {shape}"

    def test_the_route_requires_an_explicit_confirmation_field(self):
        """Even reached directly, the default is a count. A caller that
        merely forgot a parameter deletes nothing."""
        import main

        assert main.PurgeMemory().confirm is False


@pytest.mark.asyncio
class TestACorrectedFactLeavesNothingBehind:
    """Correcting a fact keeps the original row, marked superseded, with its old
    text. That is right for history and wrong for a button called *forget*: the
    wording the user wanted gone was still on disk after "everything" was
    purged, and again after a project was deleted. Both walked
    `all_records()`, which hides superseded rows by default.
    """

    async def _corrected(self, runtime, scope=GLOBAL):
        original = await remember(runtime, "the rate is 450 a day", scope=scope)
        outcome = await runtime.correct(original, "the rate is 500 a day")
        return original, outcome

    async def _everything_on_disk(self, runtime):
        return await runtime._store.all_records(include_superseded=True)

    async def test_purging_everything_removes_the_old_wording_too(self, runtime):
        await self._corrected(runtime)
        assert len(await self._everything_on_disk(runtime)) == 2  # the premise

        await runtime.purge(dry_run=False)

        assert await self._everything_on_disk(runtime) == []

    async def test_deleting_a_project_removes_the_old_wording_too(self, runtime):
        await self._corrected(runtime, scope="project:keyline")

        await runtime.forget_scope("project:keyline")

        assert await self._everything_on_disk(runtime) == []

    async def test_the_count_keeps_facts_and_old_versions_apart(self, runtime):
        """`matched` is what the person can see. The earlier versions are a
        separate number, so the sentence the screen reads out is true about
        both rather than silently inflating the first."""
        await self._corrected(runtime)
        summary = await runtime.purge()
        assert summary["matched"] == 1
        assert summary["superseded"] == 1

    async def test_a_dry_run_still_deletes_nothing(self, runtime):
        await self._corrected(runtime)
        await runtime.purge()
        assert len(await self._everything_on_disk(runtime)) == 2

    async def test_an_older_version_in_range_goes_with_a_newer_one_out_of_it(self, runtime):
        """The replacement is stamped now; the original keeps its old date. A
        purge of *before last week* must still take the original, and the
        count must say there was one."""
        original, _ = await self._corrected(runtime)
        import dataclasses

        record = await runtime._store.get(original)
        await runtime._store.put(dataclasses.replace(record, created_at=time.time() - 30 * DAY))

        summary = await runtime.purge(before=time.time() - 7 * DAY)

        assert summary["matched"] == 0
        assert summary["superseded"] == 1

    async def test_forgetting_a_recent_fact_takes_its_earlier_wording_with_it(self, runtime):
        """*Forget what I set last week* selects the replacement, which is
        stamped now. The original keeps its old date and is outside the range —
        and the previous rate must not stay on disk behind it."""
        import dataclasses

        original, _ = await self._corrected(runtime)
        record = await runtime._store.get(original)
        await runtime._store.put(dataclasses.replace(record, created_at=time.time() - 60 * DAY))

        summary = await runtime.purge(after=time.time() - 7 * DAY, dry_run=False)

        assert summary["deleted"] == 1
        assert await self._everything_on_disk(runtime) == []

    async def test_a_newer_fact_outside_the_range_is_not_taken_by_an_older_one_going(self, runtime):
        """Followed backwards only. Purging the old wording must not reach
        forward and delete the current fact the person still wants."""
        import dataclasses

        original, outcome = await self._corrected(runtime)
        record = await runtime._store.get(original)
        await runtime._store.put(dataclasses.replace(record, created_at=time.time() - 60 * DAY))

        await runtime.purge(before=time.time() - 7 * DAY, dry_run=False)

        survivors = await self._everything_on_disk(runtime)
        assert [r.content for r in survivors] == ["the rate is 500 a day"]

"""M8 — every fact carries a scope and an origin.

    Rule 7i. Global is about the *user* — preferences, working style, how they
    like things written. Project is about the *work* — decisions, constraints,
    client feedback. Default to the current project; promote to global on
    evidence, not at capture time.

Two things make this land before the alpha rather than after:

**Retrofitting is guessing.** Scope cannot be inferred for a fact stored
without it. Every pre-M8 fact becomes `global`, which is the only honest
reading — it was captured with no project in play — and every day of alpha use
without this is another day of facts that will need that guess.

**It is the multiplayer boundary.** Project memory is shareable; global memory
never is. A scope check that is wrong is a privacy failure, not a filing error,
which is why the scope strings are constants and why both stores are held to
the same behaviour here.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from runtimes.memory.contracts import (
    GLOBAL_SCOPE,
    MemoryRecord,
    MemoryType,
    Origin,
    project_scope,
    scope_project_id,
)
from runtimes.memory.runtime import MemoryRuntimeImpl
from runtimes.memory.store import InMemoryMemoryStore, SQLiteMemoryStore

HARBOUR = project_scope("harbour")
CENTURY = project_scope("century")
ASHGROVE = project_scope("ashgrove")


class TestScopeVocabulary:
    def test_a_project_scope_round_trips(self):
        assert project_scope("harbour") == "project:harbour"
        assert scope_project_id("project:harbour") == "harbour"

    def test_global_is_not_a_project(self):
        assert scope_project_id(GLOBAL_SCOPE) is None
        assert project_scope("") == GLOBAL_SCOPE
        assert project_scope("   ") == GLOBAL_SCOPE

    def test_a_record_knows_which_it_is(self):
        assert MemoryRecord(content="x").is_global
        assert not MemoryRecord(content="x", scope=HARBOUR).is_global
        assert MemoryRecord(content="x", scope=HARBOUR).project_id == "harbour"


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path: Path):
    if request.param == "memory":
        return InMemoryMemoryStore()
    return SQLiteMemoryStore(str(tmp_path / "spine.db"))


class TestBothStoresAgree:
    """The scope check is a privacy boundary. Two stores disagreeing about it
    would make that boundary depend on which backend was configured."""

    def test_scope_and_origin_survive_a_round_trip(self, store):
        async def run():
            record = MemoryRecord(content="The rate is 425,000.", scope=HARBOUR,
                                  origin=Origin.USER_DOCUMENT)
            await store.put(record)
            return await store.get(record.id)

        got = asyncio.run(run())
        assert got.scope == HARBOUR
        assert got.origin is Origin.USER_DOCUMENT

    def test_a_fact_stored_without_a_scope_is_global(self, store):
        """The default, and the value every pre-M8 fact migrates to."""
        async def run():
            record = MemoryRecord(content="Prefer Nigerian English.")
            await store.put(record)
            return await store.get(record.id)

        assert asyncio.run(run()).scope == GLOBAL_SCOPE

    def test_recording_access_notes_which_project_recalled_it(self, store):
        """Rule 7i's evidence. A count cannot answer "three *different*"."""
        async def run():
            record = MemoryRecord(content="Invoices go out on the 1st.", scope=HARBOUR)
            await store.put(record)
            await store.record_access(record.id, scope=HARBOUR)
            await store.record_access(record.id, scope=CENTURY)
            await store.record_access(record.id, scope=CENTURY)
            return await store.get(record.id)

        got = asyncio.run(run())
        assert got.access_count == 3
        assert sorted(got.recalled_in) == sorted([HARBOUR, CENTURY]), (
            "the same project twice is one project, not two"
        )

    def test_global_recalls_are_not_evidence_of_anything(self, store):
        """A fact recalled outside any project says nothing about whether it
        belongs to the user rather than to a job."""
        async def run():
            record = MemoryRecord(content="x", scope=HARBOUR)
            await store.put(record)
            await store.record_access(record.id, scope=GLOBAL_SCOPE)
            await store.record_access(record.id, scope=None)
            return await store.get(record.id)

        assert asyncio.run(run()).recalled_in == []


class TestRecallIsScoped:
    def _runtime(self, tmp_path: Path) -> MemoryRuntimeImpl:
        return MemoryRuntimeImpl(store_type="sqlite", db_path=str(tmp_path / "spine.db"),
                                 index_type="hybrid")

    def test_the_candidate_set_is_this_project_plus_global(self, store):
        """Both at once, which is why scope is one field and not two stores.

        Asserted at the store, where the filter lives and the answer is
        deterministic. Driving it through `retrieve` would also depend on
        whether a particular sentence embeds near a particular query — a
        semantic question, and not the one this test is about.
        """
        from runtimes.memory.contracts import MemoryQuery

        async def run():
            await store.put(MemoryRecord(content="Harbour Lane pays 425,000 a day.",
                                         memory_type=MemoryType.SEMANTIC, scope=HARBOUR))
            await store.put(MemoryRecord(content="Century pays 250,000 a day.",
                                         memory_type=MemoryType.SEMANTIC, scope=CENTURY))
            await store.put(MemoryRecord(content="Always include a summary paragraph.",
                                         memory_type=MemoryType.SEMANTIC, scope=GLOBAL_SCOPE))
            return await store.query(MemoryQuery(query="", max_results=50, scope=HARBOUR))

        contents = {r.content for r in asyncio.run(run())}
        assert any("Harbour Lane" in c for c in contents), "this project's facts are missing"
        assert any("summary paragraph" in c for c in contents), (
            "global facts must reach a project question — they are what is true "
            "about the user regardless of the job"
        )
        assert not any("Century" in c for c in contents), (
            "another project's facts leaked into this one — scope is a boundary, "
            "not a label"
        )

    def test_another_project_is_excluded_end_to_end(self, tmp_path: Path):
        """The exclusion half, through the real runtime."""
        async def run():
            rt = self._runtime(tmp_path)
            await rt.initialize()
            await rt.remember(content="Harbour Lane pays 425,000 a day.", scope=HARBOUR)
            await rt.remember(content="Century pays 250,000 a day.", scope=CENTURY)
            got = await rt.retrieve(query="day rate", max_results=10, scope=HARBOUR)
            await rt.shutdown()
            return {r.record.content for r in got}

        contents = asyncio.run(run())
        assert not any("Century" in c for c in contents)

    def test_no_scope_means_everything(self, tmp_path: Path):
        """What the Memory surface wants: show the user all of their own facts."""
        async def run():
            rt = self._runtime(tmp_path)
            await rt.initialize()
            await rt.remember(content="Harbour Lane pays 425,000 a day.", scope=HARBOUR)
            await rt.remember(content="Century pays 250,000 a day.", scope=CENTURY)
            got = await rt.retrieve(query="day rate", max_results=10)
            await rt.shutdown()
            return len(got)

        assert asyncio.run(run()) == 2


class TestPromotion:
    def _runtime(self, tmp_path: Path) -> MemoryRuntimeImpl:
        return MemoryRuntimeImpl(store_type="sqlite", db_path=str(tmp_path / "spine.db"),
                                 index_type="hybrid")

    def test_a_fact_used_in_three_projects_becomes_a_candidate(self, tmp_path: Path):
        async def run():
            rt = self._runtime(tmp_path)
            await rt.initialize()
            fact_id = await rt.remember(content="Invoice on the 1st.", scope=HARBOUR)
            for scope in (CENTURY, ASHGROVE):
                await rt._store.record_access(fact_id, scope=scope)
            candidates = await rt.promotion_candidates()
            await rt.shutdown()
            return [c.id for c in candidates], fact_id

        ids, fact_id = asyncio.run(run())
        assert fact_id in ids

    def test_a_fact_used_in_one_project_is_not(self, tmp_path: Path):
        async def run():
            rt = self._runtime(tmp_path)
            await rt.initialize()
            fact_id = await rt.remember(content="Harbour Lane want 4K.", scope=HARBOUR)
            await rt._store.record_access(fact_id, scope=HARBOUR)
            await rt._store.record_access(fact_id, scope=HARBOUR)
            candidates = await rt.promotion_candidates()
            await rt.shutdown()
            return [c.id for c in candidates]

        assert asyncio.run(run()) == []

    def test_candidates_are_offered_not_promoted(self, tmp_path: Path):
        """Rule 7e: the user is never asked to decide at creation, and rule 6:
        autonomy is granted, not assumed. Promotion changes what is shareable,
        so the system proposes and the user decides."""
        async def run():
            rt = self._runtime(tmp_path)
            await rt.initialize()
            fact_id = await rt.remember(content="Invoice on the 1st.", scope=HARBOUR)
            for scope in (CENTURY, ASHGROVE):
                await rt._store.record_access(fact_id, scope=scope)
            await rt.promotion_candidates()
            still = await rt.get_record(fact_id)
            await rt.shutdown()
            return still.scope

        assert asyncio.run(run()) == HARBOUR, "a candidate was promoted without being asked"

    def test_the_user_can_promote_it(self, tmp_path: Path):
        async def run():
            rt = self._runtime(tmp_path)
            await rt.initialize()
            fact_id = await rt.remember(content="Invoice on the 1st.", scope=HARBOUR)
            changed = await rt.set_scope(fact_id, GLOBAL_SCOPE)
            after = await rt.get_record(fact_id)
            await rt.shutdown()
            return changed, after.scope

        changed, scope = asyncio.run(run())
        assert changed and scope == GLOBAL_SCOPE


class TestMigration:
    def test_a_pre_m8_spine_opens_and_its_facts_are_global(self, tmp_path: Path):
        """The user's data survives. A migration that drops facts to simplify
        our code is not a trade we get to make."""
        import sqlite3

        db = tmp_path / "old.db"
        with sqlite3.connect(str(db)) as conn:
            conn.execute("""
                CREATE TABLE memories (
                    id TEXT PRIMARY KEY, content TEXT NOT NULL, memory_type TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}', embedding TEXT,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 0, last_accessed REAL NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]', session_id TEXT, user_id TEXT,
                    importance REAL NOT NULL DEFAULT 0.5, source TEXT NOT NULL DEFAULT 'user'
                )
            """)
            conn.execute(
                "INSERT INTO memories (id, content, memory_type, created_at, updated_at,"
                " last_accessed) VALUES ('old-1', 'A fact from before M8.', 'semantic',"
                " 1000, 1000, 1000)"
            )

        store = SQLiteMemoryStore(str(db))
        got = asyncio.run(store.get("old-1"))

        assert got is not None, "the migration lost the user's fact"
        assert got.content == "A fact from before M8."
        assert got.scope == GLOBAL_SCOPE
        assert got.origin is Origin.CONVERSATION
        assert got.recalled_in == []

    def test_the_migration_is_idempotent(self, tmp_path: Path):
        db = tmp_path / "twice.db"
        SQLiteMemoryStore(str(db))
        store = SQLiteMemoryStore(str(db))

        async def run():
            record = MemoryRecord(content="still here", scope=HARBOUR)
            await store.put(record)
            return await store.get(record.id)

        assert asyncio.run(run()).scope == HARBOUR

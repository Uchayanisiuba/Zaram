"""A domain narrows what recall may see — asserted at the enforcement point.

**This is the test that decides whether domains are a feature or a label.**
`CLAUDE.md`: a domain is a retrieval scope, not a folder — "if it only groups
files it is a filter, and it has to change answers".

Asserted against `HybridMemoryRetriever` rather than through `/chat`, and the
reason is the same one `test_memory_scope.py` gives for testing scope at the
store: driving it through a real question would also depend on whether a
particular sentence embeds near a particular query, which is a semantic question
and not the one being asked here.

**The filter's placement is the point.** `retrieval.py` carries a comment
explaining that `_vector_search` never passes through the store's filters, so
scope had to be enforced once, after every strategy has run — "a boundary
enforced per code path is a boundary with a hole in it per code path". Domain
narrowing rides with it, and the test below that fakes a vector hit is there to
prove it does not get its own hole.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from runtimes.memory.contracts import MemoryQuery, MemoryRecord, MemoryType, RetrievalStrategy
from runtimes.memory.retrieval import HybridMemoryRetriever
from runtimes.memory.store import SQLiteMemoryStore


@pytest.fixture
def store(tmp_path: Path):
    store = SQLiteMemoryStore(db_path=str(tmp_path / "spine.db"))
    asyncio.run(store.initialize()) if hasattr(store, "initialize") else None
    return store


def _seed(store) -> dict[str, str]:
    """Three facts, and the ids they landed under."""
    async def run():
        ids = {}
        for key, content in [
            ("funds", "The index fund allocation is sixty percent equities."),
            ("contract", "Northwind agreed a day rate of 450, net thirty."),
            ("recipe", "The bread needs a long cold ferment overnight."),
        ]:
            record = MemoryRecord(content=content, memory_type=MemoryType.SEMANTIC)
            await store.put(record)
            ids[key] = record.id
        return ids

    return asyncio.run(run())


def _recall(store, only_ids, query: str = "") -> set[str]:
    retriever = HybridMemoryRetriever(store=store)

    async def run():
        return await retriever.retrieve(
            MemoryQuery(
                query=query,
                memory_types=[MemoryType.SEMANTIC],
                max_results=50,
                strategy=RetrievalStrategy.KEYWORD_MATCH,
                only_ids=only_ids,
            )
        )

    return {result.record.id for result in asyncio.run(run())}


class TestDomainNarrowsRecall:
    def test_without_a_domain_everything_is_reachable(self, store):
        ids = _seed(store)
        assert _recall(store, None) >= set(ids.values())

    def test_a_domain_narrows_recall_to_its_own_facts(self, store):
        """The whole point. A question asked inside Investing must not be
        answered from the bread recipe."""
        ids = _seed(store)
        reachable = _recall(store, frozenset({ids["funds"]}))

        assert reachable == {ids["funds"]}
        assert ids["recipe"] not in reachable
        assert ids["contract"] not in reachable

    def test_two_domains_reach_both(self, store):
        ids = _seed(store)
        allowed = frozenset({ids["funds"], ids["contract"]})
        assert _recall(store, allowed) == allowed

    def test_an_empty_domain_reaches_nothing(self, store):
        """**Not the same as no restriction, and this is the one that would
        silently fail.**

        `frozenset()` is falsy. Any implementation testing `if query.only_ids`
        rather than `is not None` widens an empty domain to the entire Spine —
        the exact inversion of what the user asked for, on a boundary they set
        deliberately.
        """
        _seed(store)
        assert _recall(store, frozenset()) == set()


class TestTheFilterHasNoHolePerCodePath:
    def test_a_vector_hit_is_filtered_too(self, store, monkeypatch):
        """`_vector_search` bypasses the store's filters entirely.

        That is why scope is enforced once, after every strategy. A domain
        filter applied inside the store would let a semantic hit walk straight
        past it — which is exactly the defect the comment in `retrieval.py`
        records for scope. Faked here rather than hoped for: the vector path is
        made to return a record the domain excludes.
        """
        ids = _seed(store)
        retriever = HybridMemoryRetriever(store=store)

        async def only_the_recipe(query):
            record = await store.get(ids["recipe"])
            return [(record, 0.99)]

        monkeypatch.setattr(retriever, "_vector_search", only_the_recipe)

        async def run():
            return await retriever.retrieve(
                MemoryQuery(
                    query="anything",
                    memory_types=[MemoryType.SEMANTIC],
                    max_results=50,
                    strategy=RetrievalStrategy.VECTOR_SIMILARITY,
                    only_ids=frozenset({ids["funds"]}),
                )
            )

        reachable = {result.record.id for result in asyncio.run(run())}
        assert ids["recipe"] not in reachable, (
            "a semantic hit walked past the domain filter — the filter is in the "
            "wrong place, or there is now a second one"
        )

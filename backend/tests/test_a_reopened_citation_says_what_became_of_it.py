"""A citation reopened tomorrow says what became of the fact it cited.

`resumeConversation` refused to restore sources because a citation is a live
claim and rule 4 lets the fact be corrected or deleted. The refusal was right and
it was also the whole answer. This is the rest of it: keep the *reference*, look
again on reopen, and say what the Spine says now.

Run against the **real memory store**, not a fake: the defect this guards is a
citation that claims a fact still holds when the person removed it, and a fake
store would only prove the fake.
"""

from __future__ import annotations

import pytest

from conversations.citations import FactLookupUnavailable, resolve_sources
from runtimes.memory.contracts import MemoryType


@pytest.fixture
async def runtime(tmp_path):
    from runtimes.memory.runtime import MemoryRuntimeImpl

    impl = MemoryRuntimeImpl(
        store_type="sqlite",
        db_path=str(tmp_path / "spine.db"),
        embedding_backend="hash",
        embed_on_gpu=False,
    )
    await impl.initialize()
    return impl


def lookup_of(runtime):
    async def lookup(record_id):
        return await runtime._store.get(record_id)

    return lookup


async def a_fact(runtime, text="Keyline pays 450 a day"):
    return await runtime.remember(content=text, memory_type=MemoryType.SEMANTIC, scope="global")


def ref(record_id, **over):
    out = {
        "kind": "memory",
        "url": f"memory:{record_id}",
        "recordId": record_id,
        "number": 1,
        "cited": True,
        "origin": "conversation",
        "relevance": 0.8,
    }
    out.update(over)
    return out


@pytest.mark.asyncio
class TestWhatBecameOfIt:
    async def test_a_fact_that_is_still_there_is_live_and_shows_its_wording(self, runtime):
        fact = await a_fact(runtime)
        (cited,) = await resolve_sources([ref(fact)], lookup_of(runtime))
        assert cited["history"]["state"] == "live"
        assert cited["title"] == "Keyline pays 450 a day"

    async def test_a_corrected_fact_says_so_and_shows_what_it_says_now(self, runtime):
        fact = await a_fact(runtime)
        await runtime.correct(fact, "Keyline pays 500 a day")
        (cited,) = await resolve_sources([ref(fact)], lookup_of(runtime))
        assert cited["history"]["state"] == "corrected"
        assert cited["title"] == "Keyline pays 500 a day"
        assert "450" not in str(cited)

    async def test_a_fact_corrected_twice_shows_the_latest(self, runtime):
        fact = await a_fact(runtime)
        first = await runtime.correct(fact, "Keyline pays 500 a day")
        await runtime.correct(first["replacement_id"], "Keyline pays 550 a day")
        (cited,) = await resolve_sources([ref(fact)], lookup_of(runtime))
        assert cited["history"]["state"] == "corrected"
        assert cited["title"] == "Keyline pays 550 a day"

    async def test_a_deleted_fact_is_shown_as_deleted_with_no_text(self, runtime):
        fact = await a_fact(runtime)
        await runtime.forget(fact)
        (cited,) = await resolve_sources([ref(fact)], lookup_of(runtime))
        assert cited["history"]["state"] == "deleted"
        assert cited["title"] is None
        assert "450" not in str(cited)

    async def test_a_fact_purged_with_its_corrections_is_deleted(self, runtime):
        fact = await a_fact(runtime)
        await runtime.correct(fact, "Keyline pays 500 a day")
        await runtime.purge(dry_run=False)
        (cited,) = await resolve_sources([ref(fact)], lookup_of(runtime))
        assert cited["history"]["state"] == "deleted"

    async def test_the_url_alone_is_enough_to_find_a_memory(self, runtime):
        fact = await a_fact(runtime)
        bare = {"kind": "memory", "url": f"memory:{fact}", "cited": True, "number": 2}
        (cited,) = await resolve_sources([bare], lookup_of(runtime))
        assert cited["history"]["state"] == "live"


@pytest.mark.asyncio
class TestWhatItWillNotClaim:
    async def test_a_lookup_that_could_not_be_made_is_unchecked_never_deleted(self):
        """The opposite error to the one this exists to prevent. Saying a fact is
        gone because the Spine was down would be an invented value about the
        user's own data."""

        async def down(_):
            raise FactLookupUnavailable("the memory store is not available")

        (cited,) = await resolve_sources([ref("anything")], down)
        assert cited["history"]["state"] == "unchecked"

    async def test_any_other_failure_is_also_unchecked(self):
        async def broken(_):
            raise RuntimeError("database is locked")

        (cited,) = await resolve_sources([ref("anything")], broken)
        assert cited["history"]["state"] == "unchecked"

    async def test_no_lookup_at_all_is_unchecked(self):
        (cited,) = await resolve_sources([ref("anything")], None)
        assert cited["history"]["state"] == "unchecked"

    async def test_a_document_is_unchecked_because_nothing_here_can_find_it(self):
        (cited,) = await resolve_sources(
            [{"kind": "document", "url": "C:/clients/keyline.pdf", "cited": True, "number": 1}],
            lambda _: None,
        )
        assert cited["history"]["state"] == "unchecked"

    async def test_a_web_page_is_recorded_not_resolved(self):
        called = []

        async def lookup(rid):
            called.append(rid)

        (cited,) = await resolve_sources(
            [{"kind": "web", "url": "https://example.com/a", "title": "A page", "egressId": "e1", "cited": True}],
            lookup,
        )
        assert cited["history"]["state"] == "recorded"
        assert cited["title"] == "A page"
        assert cited["egressId"] == "e1"
        assert called == []  # a web page is not in the Spine

    async def test_the_passage_is_never_restored(self, runtime):
        fact = await a_fact(runtime)
        (cited,) = await resolve_sources([ref(fact, excerpt="stale text")], lookup_of(runtime))
        assert cited["excerpt"] is None

    async def test_a_malformed_reference_is_skipped_not_fatal(self, runtime):
        fact = await a_fact(runtime)
        found = await resolve_sources(["nonsense", None, ref(fact)], lookup_of(runtime))
        assert len(found) == 1


@pytest.mark.asyncio
class TestTheShapeTheRendererDraws:
    async def test_it_has_every_field_of_a_live_citation_plus_history(self, runtime):
        fact = await a_fact(runtime)
        (cited,) = await resolve_sources([ref(fact)], lookup_of(runtime))
        assert {
            "kind", "url", "title", "excerpt", "relevance", "cited", "number",
            "egressId", "bytesSent", "origin", "recordId", "history",
        } <= set(cited)


class TestItIsMounted:
    """A complete, tested, unreachable subsystem is this repository's most
    common defect. The route must resolve, and `main` must supply the lookup."""

    def test_main_supplies_the_lookup_and_the_route_uses_it(self):
        import inspect

        import conversations.api as api
        import main

        assert "set_fact_lookup(_look_up_a_fact)" in inspect.getsource(main)
        assert "resolve_sources(item[\"sources\"], _FACT_LOOKUP)" in inspect.getsource(api)

    def test_the_reply_is_recorded_with_its_references(self):
        import inspect

        import main

        assert "sources=notes.sources if notes else None" in inspect.getsource(main._record_reply)

    def test_the_route_returns_resolved_citations(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient

        import conversations.api as api
        import main
        from conversations.records import ConversationRecords

        records = ConversationRecords(str(tmp_path / "c.db"))
        api.set_records(records)

        class _Gone:
            content = "x"
            superseded_by = None

        async def lookup(record_id):
            return None if record_id == "gone" else _Gone()

        api.set_fact_lookup(lookup)
        try:
            conv = records.start()
            records.append(conv.id, "user", "what do they pay?")
            records.append(
                conv.id, "assistant", "450 a day",
                sources=[
                    {"kind": "memory", "url": "memory:kept", "recordId": "kept", "number": 1, "cited": True},
                    {"kind": "memory", "url": "memory:gone", "recordId": "gone", "number": 2, "cited": True},
                ],
            )
            body = TestClient(main.app).get(f"/conversations/{conv.id}").json()
            states = [s["history"]["state"] for s in body["messages"][1]["sources"]]
            assert states == ["live", "deleted"]
        finally:
            api.set_fact_lookup(main._look_up_a_fact)

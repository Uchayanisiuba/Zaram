"""Memory → Facts is what Zaram believes, not the pages it has read.

Found 15 September 2026 on a fresh install: the first thing under *Memory →
Facts* was the manual, chunk by chunk, each row reading `user · provisional`
— Zaram's own help text, listed as facts about a person it had just met.
Two defects in one row. `source` is the store's default and says "user" for
everything, so the surface was printing a constant as provenance; and a
passage of an indexed document is not a belief about anyone. `CLAUDE.md`
separates the two nodes on that line: Memory holds derived facts about the
user, Knowledge holds the documents those came from.

So `GET /memory` leaves document passages out unless asked (`documents=true`),
sends `origin` so the surface can say whose words these are, and
`/memory/stats` counts the two apart.
"""

from __future__ import annotations

import importlib

import pytest
from starlette.testclient import TestClient

from runtimes.memory.contracts import MemoryRecord, MemoryStats, Origin


class _Spine:
    def __init__(self, records: list[MemoryRecord]) -> None:
        self.records = records
        self._store = self

    async def stats(self) -> MemoryStats:
        return MemoryStats(total_records=len(self.records))

    async def all_records(self, include_superseded: bool = False) -> list[MemoryRecord]:
        return list(self.records)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
    main = importlib.import_module("main")
    spine = _Spine(
        [
            MemoryRecord(content="prefers British spelling", created_at=3_000.0, origin=Origin.CONVERSATION),
            MemoryRecord(
                content="## Exporting your memory\nSettings → Memory → Export writes one file.",
                created_at=2_000.0,
                origin=Origin.USER_DOCUMENT,
                metadata={"origin": "user_document", "source_name": "export.md"},
            ),
            # Stored before `origin` was a field: only the metadata key says so.
            MemoryRecord(
                content="Zaram remembers what you tell it.",
                created_at=1_500.0,
                metadata={"origin": "user_document", "source_name": "what-zaram-is.md"},
            ),
            MemoryRecord(content="Draft proposal for Northwind", created_at=1_000.0, origin=Origin.GENERATED),
        ]
    )
    monkeypatch.setattr(main.kernel, "memory_runtime", spine, raising=False)
    return TestClient(main.app)


def _listing(client: TestClient, **params):
    r = client.get("/memory", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_document_passages_are_not_listed_as_facts(client):
    body = _listing(client)
    contents = [r["content"] for r in body["records"]]
    assert contents == ["prefers British spelling", "Draft proposal for Northwind"]
    assert body["total"] == 2


def test_the_older_spelling_of_origin_is_read_too(client):
    """A record from before `origin` was a field carries it only in metadata;
    it is a passage all the same."""
    contents = [r["content"] for r in _listing(client)["records"]]
    assert "Zaram remembers what you tell it." not in contents


def test_the_passages_are_still_there_when_asked_for(client):
    body = _listing(client, documents="true")
    assert body["total"] == 4


def test_every_row_says_whose_words_these_are(client):
    rows = {r["content"]: r for r in _listing(client, documents="true")["records"]}
    assert rows["prefers British spelling"]["origin"] == "conversation"
    assert rows["Draft proposal for Northwind"]["origin"] == "generated"
    assert rows["## Exporting your memory\nSettings → Memory → Export writes one file."]["origin"] == "user_document"


def test_stats_count_facts_and_passages_apart(client):
    r = client.get("/memory/stats")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_records"] == 4
    assert body["facts"] == 2
    assert body["document_passages"] == 2


def test_new_since_counts_facts_not_passages(client):
    """The landing's returning line reads this as "N new facts"."""
    r = client.get("/memory/stats", params={"since": 500.0})
    assert r.json()["new_since"] == 2

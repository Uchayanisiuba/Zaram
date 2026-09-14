"""The lexical side of recall is BM25 — a rare word finds its record.

`CLAUDE.md`, "BM25 beside the vectors": *"the rare tokens in a project, a
client name or a reference number, are exactly what a lexical index is good
at and a dense embedding is worst at."* The overlap count this replaces
scored every shared token as one, so a question with three common words
matched most of the Spine equally and the one record naming the client was
nowhere in particular.

Two contracts. The record carrying the rare token outranks records that
share only common ones. And what leaves the index is still a *similarity*:
a keyword-only match enters at a proportion of `KEYWORD_ONLY_SCORE`, never
a raw BM25 magnitude — the citation floor is measured as a cosine.
"""

from __future__ import annotations

import pytest

from runtimes.memory.contracts import MemoryQuery, MemoryRecord
from runtimes.memory.index import HybridMemoryIndex


def _record(rid: str, content: str) -> MemoryRecord:
    # No embedding: this is the lexical side alone, which is the case an
    # unindexed or freshly stored record is in.
    return MemoryRecord(id=rid, content=content, embedding=None)


@pytest.fixture
async def index():
    idx = HybridMemoryIndex(embedding_dim=4)
    await idx.add(_record("abuja", "The Abuja fit-out client pays net 30 and wants weekly progress photos."))
    await idx.add(_record("invoice-1", "Invoice 12 was sent to the client for the fit-out work in May."))
    await idx.add(_record("invoice-2", "The client asked for the invoice to be split across two months."))
    await idx.add(_record("photos", "Progress photos go in the shared folder every Friday."))
    return idx


async def test_the_record_naming_the_client_comes_first(index):
    results = await index.search(MemoryQuery(query="what did the Abuja client agree on the invoice", max_results=10))
    assert results, "the lexical side found nothing"
    assert results[0][0] == "abuja"


async def test_a_keyword_only_match_is_a_proportion_of_an_honest_ceiling(index):
    results = await index.search(MemoryQuery(query="Abuja fit-out", max_results=10))
    scores = dict(results)
    assert 0 < scores["abuja"] <= HybridMemoryIndex.KEYWORD_ONLY_SCORE
    # Records that share only "fit-out" score less than the one with the rare token.
    assert scores.get("invoice-1", 0) < scores["abuja"]


async def test_removing_a_record_removes_it_from_the_lexical_side(index):
    await index.remove("abuja")
    results = await index.search(MemoryQuery(query="Abuja", max_results=10))
    assert all(rid != "abuja" for rid, _ in results)

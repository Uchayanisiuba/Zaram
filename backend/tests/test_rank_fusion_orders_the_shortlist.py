"""The best lexical match is not cut by a pile of mediocre vector ones.

`CLAUDE.md` asks for reciprocal rank fusion and says exactly how far to take
it: *"take it for ordering. It does not answer membership or citation, and
wiring it into either would reintroduce the defect by a new route."* This is
that, and these tests are mostly about the second half.

**What was wrong.** `HybridMemoryIndex.search` built one number per record —
a cosine where the embedder found it, `0.4 × normalised BM25` where only the
lexical side did — then sorted and cut to `max_results` on it. Two scales,
one comparison. So the single best rare-token match in the Spine entered at
0.40 and could be dropped from beneath a pile of middling vector matches at
0.45, on **the one query type BM25 was added for**: an invoice number, a
client name, a reference. Exactly the rank-43 failure this codebase has
already paid for, in miniature.

**Why fusion rather than better weights.** A weight is a rule you must
remember; RRF is a rule you cannot break. Its output is on no source's scale,
so there is no blended magnitude that *could* be compared against a floor
measured as a cosine — which is how `MIN_RECALL_SCORE` got compared against a
ranking blend the first time.

**And what must not change.** The score each record carries out is still the
honest similarity. The citation floor is a cosine and has to keep being
compared against one; a fused value leaking into that field would be the
original defect wearing the fix's clothes. The last class below is the one
that would catch it.
"""

from __future__ import annotations

import asyncio

import pytest

from runtimes.memory.contracts import MemoryQuery, MemoryRecord
from runtimes.memory.index import HybridMemoryIndex

#: A tiny embedding space, so "similar" is something the test states rather
#: than something a model decides. Four dimensions, hand-written vectors.
DIM = 4


def record(rid: str, content: str, vector: list[float]) -> MemoryRecord:
    return MemoryRecord(id=rid, content=content, embedding=vector, tags=[])


@pytest.fixture
def index():
    """One rare-token record the embedder is bad at, and several the
    embedder likes moderately — the shape the defect needs."""
    idx = HybridMemoryIndex(embedding_dim=DIM)
    records = [
        # The answer. Its wording shares nothing with the query but the
        # reference, which is precisely why a dense embedding misses it.
        record("target", "Northwind agreed INV-2026-042 at the revised rate", [0, 0, 0, 1]),
        # Near-misses the embedder scores *moderately* and which answer
        # nothing. Moderately is the point: the first fixture made every one
        # of them a perfect cosine match, which is not the case fusion is
        # for — a record that is genuinely the best dense match deserves to
        # win, and the defect was never about that. These sit around 0.5,
        # above `KEYWORD_ONLY_SCORE` and below a real answer, which is
        # exactly the band that used to bury a lexical-only hit.
        *[
            record(
                f"filler{n}",
                f"a note about rates and agreements, number {n}",
                [1, 1 + n * 0.01, 0, 0],
            )
            for n in range(12)
        ],
    ]
    asyncio.run(idx.rebuild(records))
    return idx


def search(index, text: str, vector: list[float], limit: int):
    # The query vector travels in `metadata`, which is where
    # `VectorMemoryIndex.search` reads it from.
    return asyncio.run(
        index.search(
            MemoryQuery(
                query=text,
                max_results=limit,
                metadata={"query_embedding": vector},
            )
        )
    )


class TestTheRareTokenSurvivesTheCut:
    def test_it_is_returned_at_all(self, index):
        """The whole point of a lexical index beside the vectors."""
        found = search(index, "INV-2026-042", [1, 0, 0, 0], 5)
        assert "target" in {rid for rid, _ in found}

    def test_it_rises_from_last_to_near_the_top(self, index):
        """Ordering, which is the half RRF is allowed to decide.

        **What fusion does and does not promise.** The target is rank 1 on
        the lexical side and absent from the dense side, so it scores
        `1/(60+1)` — the same as whatever is rank 1 on the dense side, which
        is correct: both are the best answer according to one retriever, and
        a record that genuinely is the best dense match is not supposed to
        lose. What fusion removes is the *scale* comparison underneath, where
        a 0.40 lexical hit lost to twelve indistinguishable 0.5 vector hits
        because 0.4 < 0.5 — not because any of them was better.

        So the claim is the measurable one: by raw similarity it is last of
        thirteen; fused, it is in the first two.
        """
        found = search(index, "INV-2026-042", [1, 0, 0, 0], 13)
        order = [rid for rid, _ in found]
        assert "target" in order[:2], order

        # And the contrast, computed from the scores this same call returned
        # — so the "it would have been last" claim is measured here rather
        # than asserted from memory. This is the old sort, exactly.
        by_magnitude = [rid for rid, _ in sorted(found, key=lambda p: p[1], reverse=True)]
        assert by_magnitude[-1] == "target", (
            "the fixture no longer reproduces the defect: the target is not "
            "last by raw similarity, so this test proves nothing"
        )

    def test_a_tight_limit_keeps_it(self, index):
        """The truncation is the defect. With `max_results=3` the old sort
        cut on a magnitude that mixed two scales and the answer went."""
        found = search(index, "INV-2026-042", [1, 0, 0, 0], 3)
        assert "target" in {rid for rid, _ in found}


class TestTheScoreIsStillASimilarity:
    """The thing that must not change, and the one worth guarding hardest.

    `ExecutionEngine.MIN_RECALL_SCORE` is a cosine measured as a cosine. A
    fused value arriving in this field would be the three-times-paid-for
    defect by a new route — and it would be invisible, because a fused score
    is a small positive number that looks like a weak similarity.
    """

    def test_a_fused_value_never_reaches_the_score(self, index):
        found = search(index, "INV-2026-042", [1, 0, 0, 0], 13)
        scores = {rid: score for rid, score in found}
        # RRF with k=60 produces values around 1/61 ≈ 0.0164. Nothing here
        # may be in that neighbourhood, and the floor below already excludes
        # it — this asserts the shape rather than the exact number.
        assert all(score > 0.05 for score in scores.values())

    def test_a_lexical_only_hit_enters_at_its_own_honest_similarity(self, index):
        found = search(index, "INV-2026-042", [1, 0, 0, 0], 13)
        target = dict(found)["target"]
        assert 0 < target <= HybridMemoryIndex.KEYWORD_ONLY_SCORE

    def test_a_vector_hit_keeps_its_cosine(self, index):
        """Unchanged by fusion, which only decides where it sits."""
        found = search(index, "rates and agreements", [1, 0, 0, 0], 13)
        filler = dict(found).get("filler0")
        assert filler is not None
        assert filler > HybridMemoryIndex.KEYWORD_ONLY_SCORE


class TestTheOrderIsRepeatable:
    def test_the_same_query_gives_the_same_order(self, index):
        """Two records at the same rank in the one list that found them would
        otherwise come back in set order, which changes between runs and
        makes a recall measurement unrepeatable — the kind of instrument
        fault `CLAUDE.md` warns costs three measurement cycles."""
        first = [rid for rid, _ in search(index, "rates", [1, 0, 0, 0], 13)]
        for _ in range(4):
            assert [rid for rid, _ in search(index, "rates", [1, 0, 0, 0], 13)] == first


class TestFusionIsNotMembership:
    """It orders what the filters produced; it admits nothing.

    Membership is still the `> 0.05` similarity floor above it, on the honest
    number. A record fusion would like cannot enter on that liking.
    """

    def test_nothing_below_the_floor_is_admitted(self, index):
        found = search(index, "INV-2026-042", [0, 1, 0, 0], 50)
        assert all(score > 0.05 for _, score in found)

    def test_a_record_matching_neither_side_is_absent(self, index):
        found = search(index, "zzzznothing", [0, 0, 1, 0], 50)
        assert found == []

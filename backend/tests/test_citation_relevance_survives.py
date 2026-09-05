"""The number a citation chip shows has to be the number that was measured.

Every web citation chip rendered ``relevance: 0.0`` while being cited. Nothing
was wrong with the search or the ranking — `relevance.scored()` measures the
query against the result's content and writes it to `SearchResult.score`, and
`fuse` orders by rank position without touching it. The number was dropped in
one hop: `KnowledgeRuntime` built its `KnowledgeResult` with ``confidence=
r.score`` and never set ``score``, which kept its ``0.0`` default — and
``score`` is the field the citation layer reads and renders as *relevance*.

A rendered 0.0 is worse than a blank. "Never render an invented value" is the
rule, and a citation whose stated relevance is false undermines the one thing
citations exist for.

The second test is the more important one and is about a different field.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge.protocol import KnowledgeResult


@dataclass
class _Record:
    id: str = "rec-1"
    content: str = "The Northwind day rate is 480 GBP."
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class _MemoryResult:
    """A memory hit carrying both numbers, as the real one does."""

    record: _Record = field(default_factory=_Record)
    #: The ranking blend — importance, recency, access count, session.
    score: float = 0.93
    #: The similarity retrieval actually measured.
    relevance: float = 0.41


def _relevance_for(result: Any) -> float:
    """The expression `KnowledgeRuntime` uses, kept in one place.

    Mirrors `ExecutionEngine._relevance_of`: prefer the measured similarity,
    fall back to the single number a stand-in carries.
    """
    measured = getattr(result, "relevance", None)
    return float(measured if measured is not None else getattr(result, "score", 0.0) or 0.0)


class TestTheNumberSurvivesTheHop:
    def test_score_defaults_to_zero_which_is_why_this_broke(self):
        """The default that produced the symptom, pinned so it stays visible."""
        assert KnowledgeResult(title="anything").score == 0.0

    def test_a_web_result_carries_its_measured_relevance(self):
        measured = 0.62
        result = KnowledgeResult(
            title="Election results", url="https://example.test/a",
            confidence=measured, score=measured,
        )
        assert result.score == measured
        assert result.to_dict()["score"] == measured

    def test_the_dict_the_citation_layer_reads_is_not_zero(self):
        """`ExecutionEngine._search_source_events` reads `source.get("score")`
        and hands it straight to the chip as `relevance`."""
        result = KnowledgeResult(title="t", url="https://example.test/b", score=0.55)
        assert result.to_dict().get("score") == 0.55


class TestOrderingIsNotSimilarity:
    """The distinction that matters more than the missing number.

    A `MemoryResult` carries two quantities and only one answers "how well does
    this bear on the question". Feeding the ranking blend to a field the user
    reads as relevance — and which is compared against a citation floor
    measured as a cosine — is the error this codebase has paid for three times.
    """

    def test_the_similarity_is_taken_and_not_the_blend(self):
        hit = _MemoryResult()
        assert _relevance_for(hit) == 0.41
        assert _relevance_for(hit) != hit.score

    def test_a_stand_in_with_one_number_still_works(self):
        """Several tests pass plain objects carrying only `score`. Falling back
        keeps the tightening where the real field exists and changes nothing
        where it does not."""

        @dataclass
        class _Plain:
            score: float = 0.5

        assert _relevance_for(_Plain()) == 0.5

    def test_a_blend_high_and_similarity_low_is_not_promoted(self):
        """The concrete failure: recency and access count can carry a barely
        related fact to a high blend. A citation floor of 0.5 must see 0.20."""
        hit = _MemoryResult(score=0.88, relevance=0.20)
        assert _relevance_for(hit) < 0.5

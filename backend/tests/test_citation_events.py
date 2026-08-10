"""What a source event carries, and what decides whether it is cited.

Step 2 of the citation UI (`docs/UI-SPEC.md` → Citations). The frontend cannot
render what is not sent, and inferring a kind client-side would be the
fabrication rule in a different file — so the shape of these events is the
contract the rest of the feature is built on.

The thing under test is a *distinction*, not a threshold: recalled and cited are
two cuts on one number, and collapsing them is what produced a reply citing five
memories for a question that used one.
"""
from __future__ import annotations

import time

import pytest

from core.execution_engine import ExecutionEngine
from core.streaming_events import EventType, StreamEvent
from runtimes.memory.contracts import MemoryRecord, MemoryResult, MemoryType, Origin


def _result(content: str, relevance: float, **kwargs) -> MemoryResult:
    record = MemoryRecord(
        content=content,
        memory_type=MemoryType.SEMANTIC,
        created_at=time.time(),
        **kwargs,
    )
    # `score` deliberately set to something that would give the opposite
    # answer, so a test passing on `score` cannot pass by accident.
    return MemoryResult(record=record, score=0.99, relevance=relevance)


class _Engine(ExecutionEngine):
    """The emitters only. Booting a kernel to test a dataclass shape would make
    this a test of the kernel."""

    def __init__(self):  # noqa: D107 - deliberately does not call super()
        pass


class TestTheTwoThresholdsAreDifferentCuts:
    def test_recall_and_citation_are_not_the_same_number(self):
        """If these were equal the second threshold would not exist."""
        assert ExecutionEngine.MIN_CITATION_SCORE > ExecutionEngine.MIN_RECALL_SCORE, (
            "citation must be a *higher* cut than injection — otherwise every "
            "fact given to the model is also cited, which is the behaviour the "
            "second threshold was introduced to fix"
        )

    def test_a_fact_above_the_floor_but_below_the_citation_cut_is_sent_uncited(self):
        """Recalled, not cited — and still emitted.

        Dropping it would hide the gap between the two thresholds. The panel
        has a section for exactly this, and rule 2's spirit is that the user can
        see what the system used; a source silently withheld is the opposite.
        """
        between = (
            ExecutionEngine.MIN_RECALL_SCORE + ExecutionEngine.MIN_CITATION_SCORE
        ) / 2
        events = _Engine()._provenance_events([_result("a day rate", between)])

        assert len(events) == 1, "a recalled-but-uncited source was dropped entirely"
        assert events[0].data["cited"] is False
        assert events[0].data["number"] is None, (
            "an uncited source was given a citation number, which would put a "
            "gap in the numbering the user sees"
        )

    def test_a_fact_above_the_citation_cut_is_cited(self):
        events = _Engine()._provenance_events([_result("a day rate", 0.90)])
        assert events[0].data["cited"] is True

    def test_the_cut_is_on_relevance_and_never_on_the_ranking_blend(self):
        """The defect that shipped for the life of the product, in one line.

        `score` here is 0.99 and `relevance` is below the cut. A citation
        decided on the blend would cite this; a citation decided on similarity
        does not.
        """
        events = _Engine()._provenance_events([_result("unrelated", 0.20)])
        assert events[0].data["cited"] is False, (
            "cited on score 0.99 despite a relevance of 0.20 — the threshold is "
            "back on the ranking blend"
        )


class TestKind:
    def test_a_fact_from_a_users_file_is_a_document(self):
        events = _Engine()._provenance_events([
            _result("day rate is 425,000", 0.9, origin=Origin.USER_DOCUMENT,
                    metadata={"filename": "harbour-brief.pdf"}),
        ])
        assert events[0].data["kind"] == "document"
        assert events[0].data["title"] == "harbour-brief.pdf", (
            "a document citation must name the file the user recognises, not a "
            "snippet of its text"
        )

    def test_a_conversational_fact_is_a_memory(self):
        events = _Engine()._provenance_events([
            _result("I prefer short emails", 0.9, origin=Origin.CONVERSATION),
        ])
        assert events[0].data["kind"] == "memory"

    def test_a_web_result_is_always_cited_however_irrelevant(self):
        """Egress disclosure is not an attribution judgement.

        A relevance score is not a reason to stop telling someone what left
        their machine, so this must hold at a relevance far below the citation
        cut — and below the recall floor too.
        """
        events = _Engine()._search_provenance_events([
            {"title": "Something barely related", "url": "https://example.com",
             "snippet": "...", "score": 0.01},
        ])
        assert events[0].data["kind"] == "web"
        assert events[0].data["cited"] is True, (
            "a web source was withheld on relevance — bytes left the machine "
            "and that is always disclosed"
        )

    def test_the_provider_name_does_not_leak_into_kind(self):
        """The UI colours by egress, not by vendor."""
        events = _Engine()._search_provenance_events([
            {"title": "t", "url": "https://example.com", "provider": "tavily"},
        ])
        assert events[0].data["kind"] == "web"


class TestTheEventCarriesWhatThePanelNeeds:
    def test_an_excerpt_is_sent_and_is_longer_than_the_chip_title(self):
        """A citation without the passage cannot be checked, which is the only
        thing a citation is for."""
        long_fact = "The agreed day rate is 425,000 naira. " * 20
        events = _Engine()._provenance_events([_result(long_fact, 0.9)])
        data = events[0].data

        assert data["excerpt"]
        assert len(data["excerpt"]) > len(data["title"]), (
            "the excerpt is no longer than the chip title, so it adds no "
            "evidence the chip did not already show"
        )
        assert len(data["excerpt"]) <= ExecutionEngine.EXCERPT_CHARS

    def test_relevance_is_sent_so_the_panel_can_show_the_gap(self):
        events = _Engine()._provenance_events([_result("x", 0.73)])
        assert events[0].data["relevance"] == pytest.approx(0.73)

    def test_a_memory_carries_its_record_id_for_correct_and_forget(self):
        """The panel offers correction inline, which needs something to correct."""
        events = _Engine()._provenance_events([_result("x", 0.9)])
        assert events[0].data["record_id"]

    def test_an_absent_egress_row_is_absent_rather_than_invented(self):
        """A citation claiming an egress row that does not exist is worse than
        one admitting it cannot link — the link is the product's whole claim."""
        events = _Engine()._search_provenance_events([
            {"title": "t", "url": "https://example.com"},
        ])
        assert events[0].data["egress_id"] is None
        assert events[0].data["bytes_sent"] is None


class TestNumbering:
    def test_the_event_type_is_unchanged(self):
        """The transport contract other code already matches on."""
        event = StreamEvent.source("web", url="https://example.com", title="t")
        assert event.type == EventType.SOURCE

    def test_a_source_defaults_to_cited_with_no_number_until_stamped(self):
        """Numbers are assigned by the engine after dedupe, not by the emitter.

        Two emitters both producing numbers would double-count a source that
        recall and search each surfaced, and the user would see a reply citing
        1, 2 and 4.
        """
        event = StreamEvent.source("memory", url="memory:1", title="t")
        assert event.data["cited"] is True
        assert event.data["number"] is None

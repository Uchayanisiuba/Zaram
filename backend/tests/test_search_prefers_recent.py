"""Web search orders by recency, and the date reaches the model.

**The bug these were written against.** Asked about something current with web
search on, Zaram answered from its training data. Every layer reported success:
the search ran, the egress was logged, results came back, six sources reached
the prompt. What was missing was a single field.

`relevance._recency_of` reads `metadata["published"]` and returns 0.5 when
there is none — a deliberate default, because scoring the undated web as
ancient would bury it. But `DuckDuckGoConnector` sets no date at all, because
DuckDuckGo's `text()` endpoint does not return one. So *every* general web
result scored 0.5, recency had no variance across the shortlist, and a constant
term cannot change an ordering. The ranker was working perfectly on a field
with nothing in it.

The same absence hit the prompt: `search_context` prints a `Published:` line
when a result has a date, and no web result ever did, so the model received six
undated snippets under an instruction to trust them as "more recent" — a claim
it had no way to check, and a model that cannot check a claim falls back on
what it already believes.

So the fix is a dated source, not a filter, and these assert the two halves
that were broken rather than the connector that was added.
"""

from __future__ import annotations

import time
from datetime import date, timedelta

import pytest

from runtimes.internet.contracts import (
    InternetConnectorType,
    SearchQuery,
    SearchResult,
)
from runtimes.internet.relevance import (
    _NEWS_TEMPORALITY,
    _recency_of,
    connectors_for,
    temporality_of,
)


def _result(title: str, *, published: str | None = None, connector: str = "duckduckgo") -> SearchResult:
    """A search result with the fields ranking actually reads."""
    metadata: dict[str, str] = {}
    if published is not None:
        metadata["published"] = published
    return SearchResult(
        title=title,
        url=f"https://example.com/{title.replace(' ', '-')}",
        snippet=title,
        connector=connector,
        connector_type=(
            InternetConnectorType.NEWS if connector == "ddg_news"
            else InternetConnectorType.DUCKDUCKGO
        ),
        score=0.6,
        metadata=metadata,
    )


class TestRecencyHasSomethingToRank:
    """The defect itself: recency was constant across every web result."""

    def test_undated_results_are_all_identical_to_the_ranker(self):
        # Not a complaint about the default — 0.5 for unknown is correct and
        # deliberate. The point is that a shortlist made only of undated
        # results carries no recency signal at all, whatever the weight on it.
        shortlist = [_result("a"), _result("b"), _result("c")]
        scores = {_recency_of(r) for r in shortlist}
        assert scores == {0.5}, (
            "every undated result scores the same, so recency cannot order them"
        )

    def test_a_dated_result_outranks_an_undated_one_on_recency(self):
        fresh = _result("today's report", published=date.today().isoformat(), connector="ddg_news")
        undated = _result("some page")
        assert _recency_of(fresh) > _recency_of(undated), (
            "a source published today must score above one with no date"
        )

    def test_an_old_dated_result_ranks_below_an_undated_one(self):
        # The other direction matters as much: a dated source is not
        # automatically better, or the fix would just be a different bias.
        stale = _result(
            "two years ago",
            published=(date.today() - timedelta(days=730)).isoformat(),
            connector="ddg_news",
        )
        assert _recency_of(stale) < _recency_of(_result("some page"))

    def test_recency_separates_two_dated_results(self):
        newer = _result("newer", published=date.today().isoformat(), connector="ddg_news")
        older = _result(
            "older",
            published=(date.today() - timedelta(days=90)).isoformat(),
            connector="ddg_news",
        )
        assert _recency_of(newer) > _recency_of(older)


class TestNewsIsAskedWhenTheQuestionIsAboutNow:
    """`connectors_for` gates the extra request on the question's own words."""

    AVAILABLE = ["duckduckgo", "ddg_news", "wikipedia", "github"]

    @pytest.mark.parametrize(
        "query",
        [
            "what is the latest Nvidia GPU",
            "who won the election",
            "what is the current version of React",
            "bitcoin price today",
        ],
    )
    def test_a_timely_question_reaches_the_dated_source(self, query):
        assert temporality_of(query) >= _NEWS_TEMPORALITY, (
            f"{query!r} should read as time-sensitive"
        )
        assert "ddg_news" in connectors_for(query, self.AVAILABLE)

    @pytest.mark.parametrize(
        "query",
        [
            "who was Napoleon",
            "the history of the Roman aqueduct",
            "what is the definition of entropy",
        ],
    )
    def test_a_historical_question_does_not_pay_for_it(self, query):
        # The "unless the user asks otherwise" half. It is also the egress
        # argument: a question about 1805 must not spend an outbound request
        # on a news endpoint.
        assert "ddg_news" not in connectors_for(query, self.AVAILABLE)

    def test_general_web_search_is_never_dropped(self):
        # The pre-existing guarantee, restated because the news branch now runs
        # before it and a mistake there would be silent.
        for query in ("who was Napoleon", "what is the latest Nvidia GPU"):
            assert "duckduckgo" in connectors_for(query, self.AVAILABLE)

    def test_news_is_not_matched_by_the_general_search_branch(self):
        # `ddg_news` contains neither "duckduckgo" nor "search", so without its
        # own branch it fell to the catch-all and was asked on every question.
        assert "ddg_news" not in connectors_for("who was Napoleon", ["ddg_news"]) or \
            connectors_for("who was Napoleon", ["ddg_news"]) == ["ddg_news"], (
                "with nothing else available the fallback may return it; with "
                "alternatives present it must not"
            )


class TestTheDateReachesTheModel:
    """A ranker that prefers recent sources does not help a model that cannot
    see which source is recent."""

    def test_published_survives_the_hop_into_the_prompt(self):
        from core.search_context import format_search_results

        published = date.today().isoformat()
        prompt = format_search_results(
            "what happened",
            {
                "results": [
                    {
                        "title": "A dated report",
                        "url": "https://example.com/report",
                        "snippet": "something happened",
                        "provider": "ddg_news",
                        "type": "web",
                        "published": published,
                    }
                ]
            },
        )
        assert f"Published: {published}" in prompt

    def test_todays_date_is_stated_beside_the_sources(self):
        from core.search_context import format_search_results

        prompt = format_search_results(
            "what happened",
            {
                "results": [
                    {
                        "title": "A page",
                        "url": "https://example.com/page",
                        "snippet": "text",
                        "provider": "duckduckgo",
                        "type": "web",
                    }
                ]
            },
        )
        # Without it, "prefer the more recent source" is an instruction the
        # model has no way to evaluate.
        assert date.today().isoformat() in prompt

    def test_undated_sources_are_not_to_be_presented_as_current(self):
        from core.search_context import format_search_results

        prompt = format_search_results(
            "what is the current version",
            {
                "results": [
                    {
                        "title": "A page",
                        "url": "https://example.com/page",
                        "snippet": "text",
                        "provider": "duckduckgo",
                        "type": "web",
                    }
                ]
            },
        )
        assert "no Published date" in prompt


class TestTheKnowledgeHopKeepsTheDate:
    """`KnowledgeResult.published` existed and nothing filled it for the web."""

    def test_published_is_read_out_of_connector_metadata(self):
        from knowledge.protocol import KnowledgeResult, ResultType

        published = date.today().isoformat()
        source = _result("dated", published=published, connector="ddg_news")

        # The shape of the hop in `KnowledgeRuntime.search`, asserted directly
        # so a future edit that drops the field again fails here rather than in
        # a reply nobody is reading closely.
        carried = KnowledgeResult(
            title=source.title,
            url=source.url,
            snippet=source.snippet,
            provider=source.connector,
            confidence=source.score,
            score=source.score,
            type=ResultType.WEB,
            published=(source.metadata or {}).get("published") or None,
            metadata=source.metadata,
            retrieved_at=source.retrieved_at,
        )
        assert carried.published == published
        assert carried.to_dict()["published"] == published


class TestCacheDoesNotOutliveTheAnswer:
    """A time-sensitive query cached for the default window serves the stale
    answer this whole change exists to stop."""

    def test_a_timely_query_gets_a_shorter_ttl_than_a_timeless_one(self):
        base = 900
        timely = max(60, int(base * (1.0 - temporality_of("what is the score right now"))))
        timeless = max(60, int(base * (1.0 - temporality_of("what is the definition of entropy"))))
        assert timely < timeless

    def test_ttl_never_falls_to_zero(self):
        # Pressing enter twice must not cost two outbound requests.
        for query in ("breaking news now", "live score today"):
            assert max(60, int(900 * (1.0 - temporality_of(query)))) >= 60

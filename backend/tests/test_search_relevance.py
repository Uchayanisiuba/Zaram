"""Search results are chosen by what they say, not by where they came from.

The defect these were written against: `_rank_results` sorted on `r.score`,
which is a constant each connector stamps on every result it returns, then on
a second copy of the same source prior, then on retrieval time. **No part of
the live path compared the query to the result.** The order was therefore the
same for every question ever asked — Wikipedia, GitHub, DuckDuckGo — which is
the complete explanation for the reported failure of an election query
returning a GitHub repository.

The first test below reproduces that exact case and is the one to keep if the
rest are ever thought redundant.
"""

from __future__ import annotations

import time

import pytest

from runtimes.internet.contracts import InternetConnectorType, SearchResult
from runtimes.internet.relevance import (
    MIN_WEB_RELEVANCE,
    authority_of,
    connectors_for,
    fuse,
    relevance_of,
    relevant,
    scored,
    temporality_of,
)


def result(
    title: str,
    url: str,
    snippet: str = "",
    connector: str = "duckduckgo",
    score: float = 0.6,
    published: str | None = None,
) -> SearchResult:
    """A result shaped exactly as a connector returns one, constant and all."""
    return SearchResult(
        title=title,
        url=url,
        snippet=snippet,
        connector=connector,
        connector_type=InternetConnectorType.DUCKDUCKGO,
        score=score,
        metadata={"published": published} if published else {},
    )


class TestTheReportedFailure:
    """An election query must not come back with a GitHub repository."""

    QUERY = "who won the 2026 Nigerian presidential election"

    def test_the_junk_repo_scores_below_the_floor(self):
        junk = result(
            "awesome-election-tools",
            "https://github.com/someone/awesome-election-tools",
            "A curated list of open source tooling for developers.",
            connector="github",
            # GitHub's constant, which used to be the whole ranking signal and
            # beat DuckDuckGo's 0.6 for every query ever asked.
            score=0.7,
        )

        assert relevance_of(self.QUERY, junk.title, junk.snippet, junk.url) < MIN_WEB_RELEVANCE

    def test_the_real_answer_outranks_it_despite_the_lower_constant(self):
        junk = result(
            "awesome-election-tools",
            "https://github.com/someone/awesome-election-tools",
            "A curated list of open source tooling for developers.",
            connector="github",
            score=0.7,
        )
        real = result(
            "Nigeria presidential election 2026: full results",
            "https://www.reuters.com/world/africa/nigeria-presidential-election-2026-results",
            "Nigeria's 2026 presidential election was won by the candidate who "
            "took 18 of 36 states, the electoral commission said.",
            connector="duckduckgo",
            score=0.6,
        )

        kept = fuse(relevant(scored(self.QUERY, [junk, real])))

        assert kept, "the relevant result was dropped entirely"
        assert kept[0].url.startswith("https://www.reuters.com"), (
            "the repository outranked the answer — this is the original defect"
        )
        assert all("github.com" not in r.url for r in kept)

    def test_a_code_question_still_reaches_github(self):
        """The fix must not be a blanket demotion of a whole source.

        Refusing GitHub outright would trade one wrong answer for another, and
        is the reason this is a relevance change rather than an exclusion list.
        """
        repo = result(
            "requests: HTTP library for Python",
            "https://github.com/psf/requests",
            "A simple, yet elegant HTTP library for Python.",
            connector="github",
        )

        kept = relevant(scored("python requests http library", [repo]))

        assert kept, "a genuinely relevant repository was dropped"


class TestRelevanceIsAboutContent:
    def test_the_connector_constant_does_not_survive(self):
        """`score` after scoring is a measurement, not the stamp it arrived with."""
        page = result("Tea brewing times", "https://example.com/tea", "How long to steep tea.", score=0.9)

        [measured] = scored("tea brewing times", [page])

        assert measured.score != 0.9
        assert measured.metadata["relevance"] == pytest.approx(measured.score, abs=5e-5)

    def test_a_title_match_beats_a_snippet_match(self):
        titled = relevance_of("lease renewal notice", "Lease renewal notice periods", "General guidance.")
        buried = relevance_of("lease renewal notice", "General guidance", "Lease renewal notice periods.")

        assert titled > buried

    def test_stopwords_do_not_make_things_relevant(self):
        """The failure `_keyword_match` had three times before this file existed."""
        noise = relevance_of(
            "what is the state of the art in the field",
            "The of and is a the",
            "Is the of a the and is.",
        )

        assert noise < MIN_WEB_RELEVANCE

    def test_a_query_of_pure_stopwords_scores_nothing_rather_than_everything(self):
        assert relevance_of("what is the", "Anything at all", "Any text.") == 0.0

    def test_a_phrase_beats_the_same_words_scattered(self):
        together = relevance_of("general election", "The general election explained", "")
        apart = relevance_of("general election", "General advice on choosing an election lawyer", "")

        assert together > apart


class TestMembershipAndOrderAreSeparate:
    """`CLAUDE.md`'s most expensive recurring bug, guarded in the search path."""

    def test_authority_cannot_carry_an_irrelevant_result_into_the_shortlist(self):
        """A trusted domain still has to be about the question.

        This is the property a weighted blend cannot have. Under the old
        arithmetic a source prior was simply added, so enough trust bought
        membership outright.
        """
        trusted_but_wrong = result(
            "Cheese ripening in French caves",
            "https://www.nature.com/articles/cheese-ripening",
            "A study of microbial activity during affinage.",
        )

        assert authority_of(trusted_but_wrong.url) > 0.8
        assert relevant(scored("2026 Nigerian election results", [trusted_but_wrong])) == []

    def test_authority_orders_results_that_are_equally_relevant(self):
        """Which is what it is legitimately for."""
        query = "photosynthesis light reactions"
        text = "The light reactions of photosynthesis occur in the thylakoid membrane."
        farm = result("Photosynthesis light reactions", "https://content-farm.example/p", text)
        journal = result("Photosynthesis light reactions", "https://www.nature.com/p", text)

        ordered = fuse(scored(query, [farm, journal]))

        assert ordered[0].url.startswith("https://www.nature.com")

    def test_fusion_output_is_not_on_the_relevance_scale(self):
        """So nothing downstream can compare a fused order against the floor.

        The reason RRF was taken for ordering: it removes the bug class rather
        than guarding against it. `fuse` returns the results in an order and
        never writes a fused magnitude back onto `score`, which stays the
        measured relevance the floor is expressed in.
        """
        query = "quarterly revenue report"
        items = [
            result("Quarterly revenue report 2026", "https://example.com/a", "Revenue by quarter."),
            result("Quarterly revenue", "https://example.com/b", "Report of revenue."),
        ]

        measured = scored(query, items)
        for item in fuse(measured):
            assert item.score == pytest.approx(
                relevance_of(query, item.title, item.snippet, item.url), abs=1e-6
            )

    def test_nothing_relevant_returns_nothing_rather_than_the_least_bad(self):
        """An honest empty answer beats four irrelevant pages and an
        instruction telling the model to trust them over its own training."""
        junk = [
            result("Buy cheap shoes online", "https://shop.example/1", "Discount footwear."),
            result("Weather in Oslo", "https://weather.example/2", "Forecast for Norway."),
        ]

        assert relevant(scored("what were the payment terms in the Northwind contract", junk)) == []


class TestRecency:
    def test_an_undated_result_is_not_treated_as_ancient(self):
        """Most of the web is undated. Scoring unknown as old would bury
        exactly the pages a search returns for a current-events question."""
        query = "central bank interest rate decision"
        text = "The central bank held its interest rate decision steady."
        undated = result("Interest rate decision", "https://example.com/a", text)
        old = result(
            "Interest rate decision",
            "https://example.com/b",
            text,
            published=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - 400 * 86400)),
        )

        ordered = fuse(scored(query, [old, undated]))

        assert ordered[0].url.endswith("/a")


class TestTemporalSensitivity:
    """How much freshness matters is a property of the question.

    Recency used to be a fixed third of the ordering regardless of what was
    asked, which is wrong in both directions at once: an encyclopedic question
    does not want yesterday's blog post above Britannica, and "the latest GPU"
    wants precisely that.
    """

    def test_a_now_question_weights_freshness_heavily(self):
        assert temporality_of("what is the score right now") >= 0.9

    def test_a_latest_question_weights_it_high(self):
        assert temporality_of("what is the latest Nvidia GPU") >= 0.8

    def test_a_historical_question_barely_weights_it(self):
        assert temporality_of("who was Napoleon") <= 0.2

    def test_a_bare_year_reads_as_a_date_signal(self):
        """`content_tokens` drops bare digits, so this needs the raw text."""
        assert temporality_of("Nigerian presidential election 2026") >= 0.8

    def test_an_ordinary_question_sits_low_rather_than_mid(self):
        """Most questions are not about this week. Treating them as if they
        were is what makes a search product surface news for everything."""
        assert temporality_of("how do I brew tea") < 0.5

    def test_freshness_reorders_a_now_question_but_not_a_historical_one(self):
        fresh_text = "The latest model was announced with new hardware."
        old_stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - 900 * 86400))
        new_stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - 2 * 86400))

        old = result("Latest model announced", "https://a.example/1", fresh_text, published=old_stamp)
        new = result("Latest model announced", "https://b.example/2", fresh_text, published=new_stamp)

        timely = fuse(scored("latest model announced", [old, new]), query="latest model announced")
        assert timely[0].url.endswith("/2"), "a 'latest' question must prefer the newer page"


class TestDiversity:
    def test_one_domain_does_not_own_the_whole_answer(self):
        """Three results from one site is one source wearing three citations."""
        text = "Nigeria presidential election results by state."
        query = "Nigeria presidential election results"
        crowd = [
            result(f"Results part {n}", f"https://onesite.example/{n}", text)
            for n in range(1, 5)
        ]
        other = result("Election results", "https://reuters.com/x", text)

        ordered = fuse(scored(query, crowd + [other]), query=query)

        top_three_hosts = {r.url.split("/")[2] for r in ordered[:3]}
        assert len(top_three_hosts) > 1, "one domain took the entire shortlist"

    def test_demoted_results_are_moved_down_not_dropped(self):
        """They are still real evidence. Losing them would be a second bug."""
        text = "Some genuinely relevant text about quarterly revenue reports."
        query = "quarterly revenue reports"
        crowd = [
            result(f"Quarterly revenue reports {n}", f"https://onesite.example/{n}", text)
            for n in range(1, 6)
        ]

        assert len(fuse(scored(query, crowd), query=query)) == 5


class TestConnectorRouting:
    def test_an_ordinary_question_does_not_query_github(self):
        chosen = connectors_for(
            "who won the 2026 Nigerian presidential election",
            ["duckduckgo", "github", "wikipedia"],
        )

        assert "github" not in chosen
        assert "duckduckgo" in chosen

    def test_a_code_question_does(self):
        chosen = connectors_for("python asyncio library error", ["duckduckgo", "github", "wikipedia"])

        assert "github" in chosen

    def test_general_search_is_never_dropped(self):
        """A misclassification must cost a wider search, never an empty answer."""
        for query in ("", "the", "asdfghjkl", "python", "who won the election"):
            assert "duckduckgo" in connectors_for(query, ["duckduckgo", "github"])

"""Eligibility is a gate, never a ranking — and unknown is never no.

Two contracts, and both of them are rules wearing a new domain's clothes.

**The gate filters.** `CLAUDE.md` records a score built for ranking being used
to decide costing this codebase three separate bugs: a citation floor compared
against a ranking blend, a shortlist *selected* on that blend discarding the
best document in a 1,000-document corpus at rank 43, and a recall eval that
graded itself. Eligibility is the fourth domain that error can arrive in, and
it arrives with the highest cost yet — a grant somebody was never able to win
takes a fortnight of their work to find out about. So the gate returns a
verdict and there is no number anywhere in it that *could* be compared against
a threshold.

**Unknown is not no.** A criterion with no fact behind it becomes a question.
The tempting shortcut is to treat missing as failing, because it makes the
list shorter and tidier; it also hides opportunities on the basis of a fact
nobody was ever asked for, and the user never finds out it happened. A silent
exclusion is the failure mode with no symptom, which is why it gets its own
tests rather than a line in someone else's.
"""

from __future__ import annotations

from dataclasses import fields as dataclass_fields
from datetime import date

import pytest

from packs.opportunities import (
    Criterion,
    Feed,
    FeedKind,
    Opportunity,
    OpportunityKind,
    Profile,
    Requirement,
    Verdict,
    assess,
    eligible_only,
    missing_criteria,
    read_requirements,
)
from packs.opportunities.sources import (
    BUILT_IN_MAPS,
    GATEWAY_TO_RESEARCH_IS_AWARDED_FUNDING_NOT_OPEN_CALLS,
    from_json,
    from_rss,
    parse_date,
)
from packs.opportunities.tools import OpportunityTools


def an_opportunity(*requirements: Requirement, **kwargs) -> Opportunity:
    base = {
        "id": "opp-1",
        "kind": OpportunityKind.GRANT,
        "title": "A call for proposals",
        "organisation": "A Funder",
        "url": "https://example.org/call",
        "feed_id": "feed-1",
    }
    base.update(kwargs)
    return Opportunity(requirements=tuple(requirements), **base)


NEEDS_NONPROFIT = Requirement(
    criterion=Criterion.ORG_TYPE,
    values=("non-profit",),
    source="Open only to registered non-profit organisations.",
)

NEEDS_NIGERIA = Requirement(
    criterion=Criterion.COUNTRY,
    values=("nigeria",),
    source="Applicants must be based in Nigeria.",
)


class TestTheGateFilters:
    def test_a_missed_requirement_excludes_rather_than_scores(self):
        """The verdict is a verdict. There is no number to threshold."""
        report = assess(
            an_opportunity(NEEDS_NONPROFIT), Profile(org_type="sole-trader")
        )
        assert report.verdict is Verdict.INELIGIBLE
        assert report.blocking[0].source == NEEDS_NONPROFIT.source

    def test_nothing_in_the_report_is_a_score(self):
        """No float anywhere on the report or its findings.

        Asserted against the dataclass rather than by reading the code, so a
        `confidence` or `match` field added later fails here — which is the
        moment the three-times-paid-for error would be arriving in this
        domain, and the moment somebody would be tempted to compare it against
        a floor.
        """
        report = assess(an_opportunity(NEEDS_NONPROFIT), Profile(org_type="non-profit"))
        numeric = [
            name
            for obj in (report, *report.findings)
            for name, value in ((f.name, getattr(obj, f.name)) for f in dataclass_fields(obj))
            if isinstance(value, float)
        ]
        assert not numeric, f"the gate grew a score: {numeric}"

    def test_one_failure_settles_it_however_many_questions_remain(self):
        """Failure dominates uncertainty.

        There is no point asking somebody four questions to establish
        something already ruled out.
        """
        report = assess(
            an_opportunity(NEEDS_NONPROFIT, NEEDS_NIGERIA),
            Profile(org_type="sole-trader"),
        )
        assert report.verdict is Verdict.INELIGIBLE
        assert Criterion.COUNTRY in report.missing

    def test_an_exclusion_is_read_as_an_exclusion(self):
        excluded = Requirement(
            criterion=Criterion.COUNTRY,
            values=("united states",),
            source="Not open to applicants in the United States.",
            excludes=True,
        )
        assert assess(an_opportunity(excluded), Profile(country="United States")).verdict is Verdict.INELIGIBLE
        assert assess(an_opportunity(excluded), Profile(country="Nigeria")).verdict is Verdict.ELIGIBLE

    def test_matching_is_case_folded_but_never_fuzzy(self):
        """"Close enough" on an eligibility filter tells somebody they qualify
        for something they do not."""
        assert assess(an_opportunity(NEEDS_NIGERIA), Profile(country="NIGERIA")).verdict is Verdict.ELIGIBLE
        assert assess(an_opportunity(NEEDS_NIGERIA), Profile(country="Niger")).verdict is Verdict.INELIGIBLE

    def test_holding_one_of_several_values_is_enough(self):
        """Somebody may work in three sectors; collapsing that to one would
        exclude people who qualify twice."""
        sector = Requirement(
            criterion=Criterion.SECTOR,
            values=("health", "education"),
            source="Open to projects in health or education.",
        )
        report = assess(an_opportunity(sector), Profile(sectors=("education", "climate")))
        assert report.verdict is Verdict.ELIGIBLE


class TestUnknownIsNotNo:
    def test_a_missing_fact_is_a_question_not_an_exclusion(self):
        report = assess(an_opportunity(NEEDS_NONPROFIT), Profile())
        assert report.verdict is Verdict.UNKNOWN
        assert report.missing == (Criterion.ORG_TYPE,)
        assert not report.blocking

    def test_an_unknown_survives_the_shortlist(self):
        """The silent failure this whole file exists for: an opportunity
        dropped on a fact the user was never asked for, leaving no trace."""
        kept = eligible_only([an_opportunity(NEEDS_NONPROFIT)], Profile())
        assert len(kept) == 1

    def test_the_questions_are_gathered_once_for_the_whole_batch(self):
        """Asked once — "which country are you based in?" — not once per call."""
        batch = [
            an_opportunity(NEEDS_NIGERIA, id="a"),
            an_opportunity(NEEDS_NIGERIA, NEEDS_NONPROFIT, id="b"),
            an_opportunity(NEEDS_NONPROFIT, id="c"),
        ]
        assert missing_criteria(batch, Profile()) == (Criterion.COUNTRY, Criterion.ORG_TYPE)

    def test_nothing_read_is_not_reported_as_nothing_required(self):
        """"No requirement was read" and "there is no requirement" are
        different claims, and only the first is true. Rendering the second
        would be an invented value on a screen."""
        report = assess(an_opportunity(), Profile(country="Nigeria", org_type="non-profit"))
        assert report.verdict is Verdict.UNKNOWN
        assert report.checked == 0


class TestReadingCriteriaFindsFewAndInventsNone:
    def test_a_plain_eligibility_sentence_is_read_with_its_clause(self):
        found = read_requirements(
            "About the fund. We support work across the continent.\n"
            "Eligibility: open only to registered non-profit organisations based in Nigeria."
        )
        by = {r.criterion: r for r in found}
        assert by[Criterion.ORG_TYPE].values == ("non-profit",)
        assert by[Criterion.COUNTRY].values == ("nigeria",)
        assert "Eligibility" in by[Criterion.ORG_TYPE].source

    def test_a_sentence_that_is_not_about_eligibility_invents_nothing(self):
        """The main guard. Without it the country vocabulary turns "our
        offices are in Germany" into a residency requirement, and somebody
        stops being shown a grant they could have won."""
        assert read_requirements("Our offices are in Germany and France.") == ()
        assert read_requirements("The programme has funded students since 1998.") == ()

    def test_an_exclusion_is_not_read_as_a_requirement(self):
        found = read_requirements("This call is not open to applicants in the United States.")
        assert len(found) == 1
        assert found[0].excludes is True

    def test_a_repeated_rule_produces_one_requirement(self):
        found = read_requirements(
            "Eligibility: applicants must be based in Nigeria.\n"
            "Please note that you must be based in Nigeria to apply."
        )
        assert len([r for r in found if r.criterion is Criterion.COUNTRY]) == 1

    def test_the_clause_is_bounded(self):
        long_clause = "Eligibility: open only to non-profit bodies, " + ("and more terms " * 60)
        found = read_requirements(long_clause)
        assert found
        assert len(found[0].source) <= 301

    def test_empty_text_reads_nothing_rather_than_raising(self):
        assert read_requirements("") == ()
        assert read_requirements("   \n  ") == ()


class TestSourcesParseWithoutInventing:
    def test_a_field_map_pointed_at_a_missing_key_leaves_it_empty(self):
        """The behaviour that matters more than any schema. The built-in maps
        were written against no live response — see the module docstring — so
        what is proven here is that a wrong guess degrades instead of
        crashing."""
        feed = Feed(id="f", kind=FeedKind.JSON, label="A funder", target="https://x/y")
        payload = {"data": [{"opportunity_title": "A call", "opportunity_id": "42"}]}
        out = from_json(payload, feed, BUILT_IN_MAPS["grants_gov"])
        assert len(out) == 1
        assert out[0].title == "A call"
        assert out[0].organisation == ""
        assert out[0].closes is None

    def test_an_item_with_neither_title_nor_url_is_dropped(self):
        feed = Feed(id="f", kind=FeedKind.JSON, label="A funder", target="https://x/y")
        payload = {"data": [{"irrelevant": 1}, {"opportunity_title": "Real"}]}
        assert len(from_json(payload, feed, BUILT_IN_MAPS["grants_gov"])) == 1

    def test_a_relative_url_gets_its_prefix(self):
        feed = Feed(id="f", kind=FeedKind.JSON, label="A funder", target="https://x/y")
        payload = {"data": [{"opportunity_title": "A call", "opportunity_id": "42"}]}
        out = from_json(payload, feed, BUILT_IN_MAPS["grants_gov"])
        assert out[0].url.startswith("https://simpler.grants.gov/opportunity/")

    def test_rss_is_parsed_because_it_is_a_standard_rather_than_a_guess(self):
        feed = Feed(
            id="rss-1",
            kind=FeedKind.RSS,
            label="A board",
            target="https://example.org/feed",
            produces=OpportunityKind.JOB,
        )
        xml = """<?xml version="1.0"?><rss version="2.0"><channel>
          <item><title>Concept Artist</title><link>https://example.org/1</link>
          <description>Full time</description>
          <pubDate>Tue, 23 Sep 2026 10:00:00 +0000</pubDate></item>
        </channel></rss>"""
        out = from_rss(xml, feed)
        assert len(out) == 1
        assert out[0].title == "Concept Artist"
        assert out[0].kind is OpportunityKind.JOB
        assert out[0].posted == date(2026, 9, 23)

    def test_a_truncated_feed_does_not_stop_the_cycle(self):
        """The poller runs unattended. One funder serving broken XML must not
        be the reason nothing else gets read."""
        feed = Feed(id="f", kind=FeedKind.RSS, label="x", target="https://x/y")
        assert from_rss("<rss><channel><item>", feed) == []

    def test_a_date_is_read_or_refused_never_guessed(self):
        """A mis-read deadline is an invented commitment, which `obligations/`
        already names as worse than a missed one."""
        assert parse_date("2026-11-14") == date(2026, 11, 14)
        assert parse_date("2026-11-14T23:59:00Z") == date(2026, 11, 14)
        assert parse_date("14 November 2026") == date(2026, 11, 14)
        assert parse_date("rolling") is None
        assert parse_date("30 days after posting") is None
        assert parse_date("") is None
        assert parse_date(None) is None

    def test_the_gateway_to_research_warning_is_present(self):
        """A named constant so the next person to reach for GtR meets the
        comment before the endpoint: it lists *awarded* funding, not open
        calls, and an integration against it looks entirely reasonable while
        matching the user against grants that closed years ago."""
        assert GATEWAY_TO_RESEARCH_IS_AWARDED_FUNDING_NOT_OPEN_CALLS is True


class TestTheToolSurface:
    @pytest.fixture
    def tools(self):
        return OpportunityTools(lambda: Profile(country="Nigeria", org_type="sole-trader"))

    def test_there_is_no_apply_tool(self):
        """And there will not be one. The funders did not build submission
        endpoints, and rules 6, 9 and the mutative tier agree with them."""
        names = {t.name for t in OpportunityTools().list_tools()}
        assert "apply" not in names
        assert not any("submit" in n or "send" in n for n in names)

    def test_every_offered_tool_is_granted_and_listed(self):
        """Registering is not reaching. The two sets must agree, or a tool is
        described to the model and then refused when it is called."""
        tools = OpportunityTools()
        assert {t.name for t in tools.list_tools()} == tools.granted_tools()

    def test_check_eligibility_answers_with_a_sentence_not_a_number(self, tools):
        answer = tools.call_tool(
            "check_eligibility",
            {"text": "Eligibility: open only to registered non-profit organisations."},
        )
        assert answer["verdict"] == Verdict.INELIGIBLE.value
        assert "non-profit" in answer["summary"]
        assert answer["findings"][0]["source"]

    def test_the_tool_answers_from_the_profile_as_it_stands_now(self):
        """Resolved at call time. A snapshot taken at boot would be wrong the
        moment the user corrected a fact, which is rule 4's whole promise."""
        current = {"org_type": "sole-trader"}
        tools = OpportunityTools(lambda: Profile(org_type=current["org_type"]))
        text = "Eligibility: open only to registered non-profit organisations."

        assert tools.check_eligibility(text)["verdict"] == Verdict.INELIGIBLE.value
        current["org_type"] = "non-profit"
        assert tools.check_eligibility(text)["verdict"] == Verdict.ELIGIBLE.value

    def test_reading_nothing_says_so_rather_than_reporting_no_requirements(self, tools):
        answer = tools.call_tool("read_criteria", {"text": "We are a foundation in Lagos."})
        assert answer["found"] == 0
        assert "not the same as" in answer["note"]

    def test_empty_input_is_refused_rather_than_answered(self, tools):
        assert "error" in tools.call_tool("check_eligibility", {"text": "  "})
        assert "error" in tools.call_tool("read_criteria", {"text": ""})

    def test_an_unknown_tool_name_is_reported(self, tools):
        assert "error" in tools.call_tool("apply", {"text": "x"})

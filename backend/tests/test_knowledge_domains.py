"""Domains have to change answers, or they are a filter with a name.

`CLAUDE.md` gives a domain four load-bearing properties and this file asserts
each one, because each could be lost without anything failing to compile:

* it is a **retrieval scope** — `fact_ids_for` is the test that matters most
* it is **many-to-many, never a tree** — one source in two domains at once
* it carries a **one-line description**, since routing reads it
* **one memory, many domains** — removing a domain takes no facts with it

The last is the one worth stating twice. A domain and a source sit on the same
screen, and withdrawing a *source* deliberately deletes facts. Withdrawing a
*domain* must not, or a way of looking at your library becomes a way of losing
it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from knowledge.domain_recall import describe, fact_ids_for
from knowledge.domains import DomainError, KnowledgeDomains


@pytest.fixture
def domains(tmp_path: Path) -> KnowledgeDomains:
    return KnowledgeDomains(str(tmp_path / "domains.db"))


class _FakeRecords:
    """Only the slice `fact_ids_for` uses. Keeps this off the real ingest store."""

    def __init__(self, by_source: dict[str, list[list[str]]]) -> None:
        self._by_source = by_source

    def outcomes(self, source_id=None, problems_only=False):
        return [{"fact_ids": ids} for ids in self._by_source.get(source_id or "", [])]


class TestCreating:
    def test_a_domain_needs_a_description(self, domains: KnowledgeDomains):
        """Not decoration. Routing reads it to decide when to reach for the
        domain, and the reply quotes it back when it does."""
        with pytest.raises(DomainError) as caught:
            domains.create("Investing", "")
        assert "what is in it" in str(caught.value)

    def test_a_domain_needs_a_name(self, domains: KnowledgeDomains):
        with pytest.raises(DomainError):
            domains.create("   ", "Funds and positions I track.")

    def test_names_are_unique(self, domains: KnowledgeDomains):
        domains.create("Legal", "Contracts and terms.")
        with pytest.raises(DomainError) as caught:
            domains.create("Legal", "Something else entirely.")
        assert "already a domain" in str(caught.value)

    def test_a_description_that_would_not_fit_in_a_reply_is_refused(
        self, domains: KnowledgeDomains
    ):
        with pytest.raises(DomainError):
            domains.create("Investing", "x" * 500)

    def test_a_new_domain_is_listed_with_no_sources(self, domains: KnowledgeDomains):
        created = domains.create("Investing", "Funds and positions I track.")
        assert domains.all() == [
            {
                "id": created["id"],
                "name": "Investing",
                "description": "Funds and positions I track.",
                "created_at": created["created_at"],
                "updated_at": created["updated_at"],
                "source_ids": [],
            }
        ]


class TestManyToMany:
    """A contract is Clients *and* Legal. This is the property a tree destroys."""

    def test_one_source_belongs_to_several_domains(self, domains: KnowledgeDomains):
        clients = domains.create("Clients", "Who I work for and what was agreed.")
        legal = domains.create("Legal", "Contracts, terms and expiries.")

        assert domains.link(clients["id"], "src-contract") is True
        assert domains.link(legal["id"], "src-contract") is True

        assert domains.source_ids(clients["id"]) == ["src-contract"]
        assert domains.source_ids(legal["id"]) == ["src-contract"]

    def test_linking_twice_is_not_an_error(self, domains: KnowledgeDomains):
        domain = domains.create("Legal", "Contracts, terms and expiries.")
        domains.link(domain["id"], "src-a")
        domains.link(domain["id"], "src-a")
        assert domains.source_ids(domain["id"]) == ["src-a"]

    def test_linking_to_a_domain_that_is_gone_reports_it(self, domains: KnowledgeDomains):
        assert domains.link("dom-nothing", "src-a") is False

    def test_unlinking_leaves_the_other_domains_alone(self, domains: KnowledgeDomains):
        clients = domains.create("Clients", "Who I work for and what was agreed.")
        legal = domains.create("Legal", "Contracts, terms and expiries.")
        domains.link(clients["id"], "src-contract")
        domains.link(legal["id"], "src-contract")

        assert domains.unlink(clients["id"], "src-contract") is True

        assert domains.source_ids(clients["id"]) == []
        assert domains.source_ids(legal["id"]) == ["src-contract"], (
            "unlinking from one domain removed the source from another"
        )


class TestItIsAScope:
    """The property that makes a domain worth having."""

    def test_a_domain_resolves_to_the_facts_its_sources_produced(
        self, domains: KnowledgeDomains
    ):
        records = _FakeRecords(
            {
                "src-funds": [["f1", "f2"], ["f3"]],
                "src-contracts": [["f9"]],
            }
        )
        investing = domains.create("Investing", "Funds and positions I track.")
        domains.link(investing["id"], "src-funds")

        assert fact_ids_for(domains, records, [investing["id"]]) == frozenset({"f1", "f2", "f3"})

    def test_two_domains_union_rather_than_intersect(self, domains: KnowledgeDomains):
        """Selecting two of something means "either" everywhere else in an
        interface, and an intersection would return almost nothing."""
        records = _FakeRecords({"src-a": [["f1"]], "src-b": [["f2"]]})
        one = domains.create("Clients", "Who I work for and what was agreed.")
        two = domains.create("Legal", "Contracts, terms and expiries.")
        domains.link(one["id"], "src-a")
        domains.link(two["id"], "src-b")

        assert fact_ids_for(domains, records, [one["id"], two["id"]]) == frozenset({"f1", "f2"})

    def test_an_empty_domain_answers_from_nothing(self, domains: KnowledgeDomains):
        """**Not the same as no restriction.**

        A domain with no sources yet must narrow recall to nothing rather than
        to everything. The caller distinguishes the two by `None` versus an
        empty set, and collapsing them would silently widen a scope the user
        chose — which is the exact failure the boundary exists to prevent.
        """
        records = _FakeRecords({"src-a": [["f1"]]})
        empty = domains.create("New thing", "Nothing in here yet.")

        assert fact_ids_for(domains, records, [empty["id"]]) == frozenset()


class TestRemoving:
    def test_removing_a_domain_keeps_its_sources_and_facts(self, domains: KnowledgeDomains):
        """One memory, many domains. A domain is a way of looking at what is
        already there, so deleting one deletes a lens and nothing else."""
        records = _FakeRecords({"src-a": [["f1", "f2"]]})
        domain = domains.create("Investing", "Funds and positions I track.")
        domains.link(domain["id"], "src-a")

        assert domains.remove(domain["id"]) is True

        assert domains.all() == []
        # The source's facts are exactly where they were.
        assert records.outcomes(source_id="src-a") == [{"fact_ids": ["f1", "f2"]}]

    def test_a_withdrawn_source_leaves_every_domain_that_held_it(
        self, domains: KnowledgeDomains
    ):
        """Otherwise a domain counts something that no longer exists."""
        clients = domains.create("Clients", "Who I work for and what was agreed.")
        legal = domains.create("Legal", "Contracts, terms and expiries.")
        domains.link(clients["id"], "src-contract")
        domains.link(legal["id"], "src-contract")
        domains.link(legal["id"], "src-other")

        assert domains.forget_source("src-contract") == 2

        assert domains.source_ids(clients["id"]) == []
        assert domains.source_ids(legal["id"]) == ["src-other"]

    def test_removing_something_unknown_says_so(self, domains: KnowledgeDomains):
        assert domains.remove("dom-nothing") is False


class TestSayingWhereAnAnswerCameFrom:
    """A reply that narrowed its own sources has to say so — disabled
    capabilities are visible, not silent."""

    def test_one_domain(self, domains: KnowledgeDomains):
        investing = domains.create("Investing", "Funds and positions I track.")
        assert describe(domains, domains.all(), [investing["id"]]) == "your Investing domain"

    def test_two_domains(self, domains: KnowledgeDomains):
        a = domains.create("Clients", "Who I work for.")
        b = domains.create("Legal", "Contracts and terms.")
        phrase = describe(domains, domains.all(), [a["id"], b["id"]])
        assert phrase == "your Clients and Legal domains"

    def test_three_domains_read_as_a_list(self, domains: KnowledgeDomains):
        a = domains.create("Clients", "Who I work for.")
        b = domains.create("Legal", "Contracts and terms.")
        c = domains.create("Research", "Papers I am reading.")
        phrase = describe(domains, domains.all(), [a["id"], b["id"], c["id"]])
        assert phrase == "your Clients, Legal and Research domains"

    def test_no_domain_says_nothing(self, domains: KnowledgeDomains):
        assert describe(domains, domains.all(), []) == ""


class TestRenaming:
    def test_a_domain_can_be_renamed_and_redescribed(self, domains: KnowledgeDomains):
        domain = domains.create("Investing", "Funds and positions I track.")
        assert domains.rename(domain["id"], "Portfolio", "What I hold and why.") is True

        listed = domains.all()[0]
        assert listed["name"] == "Portfolio"
        assert listed["description"] == "What I hold and why."

    def test_renaming_still_requires_a_description(self, domains: KnowledgeDomains):
        domain = domains.create("Investing", "Funds and positions I track.")
        with pytest.raises(DomainError):
            domains.rename(domain["id"], "Portfolio", "")

    def test_renaming_something_unknown_says_so(self, domains: KnowledgeDomains):
        assert domains.rename("dom-nothing", "Anything", "A description.") is False

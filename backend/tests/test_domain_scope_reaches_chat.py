"""A question can be asked inside a knowledge domain, and the reply says so.

The domain machinery shipped complete, tested and unreachable: the scope was
proven at the retriever and nothing in the chat path ever passed `only_ids`.
These tests assert the *chain*, not the retriever — that part already has
`test_domain_narrows_recall.py`, and repeating it here would test the same
thing twice while leaving the gap that actually existed untested.

So what is asserted is the property that was missing: what `/chat` resolves and
hands down, and what it tells the user it did.
"""

from __future__ import annotations

import pytest

import main
from knowledge.domain_recall import describe, fact_ids_for


class _Domains:
    """The slice of `KnowledgeDomains` the resolver touches."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def all(self) -> list[dict]:
        return list(self._rows)

    def source_ids(self, domain_id: str) -> list[str]:
        for row in self._rows:
            if row["id"] == domain_id:
                return list(row.get("source_ids") or ())
        return []


class _Records:
    def __init__(self, by_source: dict[str, list[str]]) -> None:
        self._by_source = by_source

    def outcomes(self, source_id: str | None = None, problems_only: bool = False):
        return [{"fact_ids": list(self._by_source.get(source_id or "", ()))}]


class _Service:
    def __init__(self, records: _Records) -> None:
        self.records = records


@pytest.fixture
def wired(monkeypatch):
    """A resolver pointed at two domains, one of them empty."""
    domains = _Domains([
        {"id": "d-investing", "name": "Investing", "source_ids": ["s-funds"]},
        {"id": "d-empty", "name": "Reading", "source_ids": []},
    ])
    records = _Records({"s-funds": ["f1", "f2", "f3"]})
    monkeypatch.setattr(main, "knowledge_domains", domains, raising=False)
    monkeypatch.setattr(main, "ingest_service", _Service(records), raising=False)
    return domains, records


class TestWhatChatResolves:
    def test_no_domain_is_unrestricted(self, wired):
        """`None`, not an empty set. The two mean opposite things."""
        only_ids, notice = main._domain_scope([])
        assert only_ids is None
        assert notice == ""

    def test_a_domain_narrows_to_its_facts(self, wired):
        only_ids, _ = main._domain_scope(["d-investing"])
        assert only_ids == frozenset({"f1", "f2", "f3"})

    def test_an_empty_domain_is_an_empty_set_and_not_none(self, wired):
        """The distinction the whole chain is built to keep.

        `frozenset()` is falsy, so any hop testing truthiness would widen a
        domain holding nothing to the entire Spine — answering from everything
        at the exact moment the user asked for almost nothing.
        """
        only_ids, _ = main._domain_scope(["d-empty"])
        assert only_ids is not None
        assert only_ids == frozenset()

    def test_an_unknown_domain_narrows_rather_than_widens(self, wired):
        """A domain that cannot be resolved must not answer from everything.

        Failing open here is silent: the user picked a library, got an answer
        drawn from every file they own, and nothing on screen said so.
        """
        only_ids, notice = main._domain_scope(["d-does-not-exist"])
        assert only_ids == frozenset()
        assert "could not" in notice.lower()

    def test_a_broken_store_narrows_rather_than_widens(self, monkeypatch, wired):
        class _Exploding:
            def all(self):
                raise RuntimeError("domains.db is locked")

            def source_ids(self, domain_id):
                raise RuntimeError("domains.db is locked")

        monkeypatch.setattr(main, "knowledge_domains", _Exploding(), raising=False)
        only_ids, notice = main._domain_scope(["d-investing"])
        assert only_ids == frozenset()
        assert notice


class TestWhatTheUserIsTold:
    """Disabled capabilities are visible, not silent. A question answered
    inside one domain did not look at the rest, and has to say so."""

    def test_the_notice_names_the_domain(self, wired):
        _, notice = main._domain_scope(["d-investing"])
        assert "your Investing domain" in notice

    def test_the_notice_states_what_was_not_read(self, wired):
        _, notice = main._domain_scope(["d-investing"])
        assert "Nothing else" in notice

    def test_an_empty_domain_says_so_rather_than_answering_quietly(self, wired):
        """The case that otherwise looks like a plain bad answer.

        Without this the user gets a confident reply built on no files at all,
        with nothing explaining why — which reads as "it doesn't know my stuff"
        and is the most likely reason someone leaves.
        """
        _, notice = main._domain_scope(["d-empty"])
        assert "Nothing is indexed" in notice
        assert "your Reading domain" in notice

    def test_one_fact_is_not_called_facts(self, wired):
        records = _Records({"s-funds": ["only-one"]})
        main.ingest_service = _Service(records)
        _, notice = main._domain_scope(["d-investing"])
        assert "1 fact in scope" in notice


class TestTheChainAcceptsIt:
    """The hops that did not exist. Each of these was the reason the feature
    could not happen, and a signature type is what proves the wiring."""

    def test_chat_request_carries_domain_ids(self):
        assert main.ChatRequest(text="hi").domain_ids == []
        assert main.ChatRequest(text="hi", domain_ids=["d"]).domain_ids == ["d"]

    def test_router_and_engine_take_only_ids(self):
        import inspect

        from core.chat_router import ChatRouter
        from core.execution_engine import ExecutionEngine

        assert "only_ids" in inspect.signature(ChatRouter.route).parameters
        assert "only_ids" in inspect.signature(ExecutionEngine.execute).parameters
        assert "only_ids" in inspect.signature(ExecutionEngine._recall).parameters


class TestDescribe:
    def test_it_reads_the_rows_it_is_given(self):
        rows = [{"id": "a", "name": "Clients"}, {"id": "b", "name": "Legal"}]
        assert describe(rows, ["a"]) == "your Clients domain"
        assert describe(rows, ["a", "b"]) == "your Clients and Legal domains"

    def test_union_not_intersection(self):
        """Two domains means anything in either.

        An intersection would return almost nothing, since a document is rarely
        in every domain chosen — and "either" is what selecting two of something
        means everywhere else in an interface.
        """
        domains = _Domains([
            {"id": "a", "name": "A", "source_ids": ["s1"]},
            {"id": "b", "name": "B", "source_ids": ["s2"]},
        ])
        records = _Records({"s1": ["f1"], "s2": ["f2"]})
        assert fact_ids_for(domains, records, ["a", "b"]) == frozenset({"f1", "f2"})

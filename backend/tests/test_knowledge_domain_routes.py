"""Domains are reachable over HTTP, and withdrawing a source cleans up after it.

Same posture as the ingest route tests: every assertion goes in through a URL,
because this repository's most expensive failure is a feature that is complete,
tested and served by no route.

The last class is the one worth reading. A domain and a source sit on the same
screen and their delete buttons look alike, but one takes facts with it and the
other must not.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    from ingest.records import IngestRecords
    from ingest.service_api import IngestService
    from knowledge.domains import KnowledgeDomains

    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))

    main = importlib.import_module("main")
    monkeypatch.setattr(
        main, "ingest_service", IngestService(IngestRecords(str(tmp_path / "ingest.db")))
    )
    monkeypatch.setattr(
        main, "knowledge_domains", KnowledgeDomains(str(tmp_path / "domains.db"))
    )
    return TestClient(main.app)


def make(client, name: str, description: str):
    response = client.post("/knowledge/domains", json={"name": name, "description": description})
    assert response.status_code == 200, response.text
    return response.json()


class TestTheRoutes:
    def test_a_domain_is_created_and_listed(self, client):
        created = make(client, "Investing", "Funds and positions I track.")

        listed = client.get("/knowledge/domains").json()["domains"]
        assert [d["id"] for d in listed] == [created["id"]]
        assert listed[0]["description"] == "Funds and positions I track."

    def test_a_domain_without_a_description_is_refused_with_a_reason(self, client):
        response = client.post("/knowledge/domains", json={"name": "Investing"})
        assert response.status_code == 400
        # A reason a person can act on, not a schema error.
        assert "what is in it" in response.json()["detail"]

    def test_a_duplicate_name_is_refused(self, client):
        make(client, "Legal", "Contracts and terms.")
        response = client.post(
            "/knowledge/domains", json={"name": "Legal", "description": "Something else."}
        )
        assert response.status_code == 400
        assert "already a domain" in response.json()["detail"]

    def test_a_domain_can_be_renamed(self, client):
        created = make(client, "Investing", "Funds and positions I track.")
        response = client.put(
            f"/knowledge/domains/{created['id']}",
            json={"name": "Portfolio", "description": "What I hold and why."},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Portfolio"

    def test_renaming_something_unknown_is_a_404(self, client):
        response = client.put(
            "/knowledge/domains/dom-nothing",
            json={"name": "Anything", "description": "A description."},
        )
        assert response.status_code == 404

    def test_a_source_joins_and_leaves_a_domain(self, client):
        domain = make(client, "Legal", "Contracts and terms.")

        added = client.post(f"/knowledge/domains/{domain['id']}/sources/src-a").json()
        assert added["source_ids"] == ["src-a"]

        removed = client.delete(f"/knowledge/domains/{domain['id']}/sources/src-a").json()
        assert removed["source_ids"] == []

    def test_one_source_in_two_domains(self, client):
        """Many-to-many over HTTP. A contract is Clients *and* Legal."""
        clients = make(client, "Clients", "Who I work for and what was agreed.")
        legal = make(client, "Legal", "Contracts, terms and expiries.")

        client.post(f"/knowledge/domains/{clients['id']}/sources/src-contract")
        client.post(f"/knowledge/domains/{legal['id']}/sources/src-contract")

        listed = {d["name"]: d["source_ids"] for d in client.get("/knowledge/domains").json()["domains"]}
        assert listed == {"Clients": ["src-contract"], "Legal": ["src-contract"]}

    def test_adding_to_a_domain_that_is_gone_is_a_404(self, client):
        assert client.post("/knowledge/domains/dom-nothing/sources/src-a").status_code == 404


class TestDeletingADomainIsNotDeletingASource:
    """The two live on the same screen and their buttons look alike."""

    def test_removing_a_domain_keeps_the_source_and_its_facts(self, client, tmp_path):
        client.post(
            "/ingest/upload",
            files=[("files", ("brief.txt", b"A brief that should survive all this.", "text/plain"))],
        )
        source_id = client.get("/ingest/sources").json()["sources"][0]["id"]

        domain = make(client, "Clients", "Who I work for and what was agreed.")
        client.post(f"/knowledge/domains/{domain['id']}/sources/{source_id}")

        response = client.delete(f"/knowledge/domains/{domain['id']}")
        assert response.status_code == 200
        assert response.json()["facts_removed"] == 0

        # The source, its outcome and its file are all exactly as they were.
        assert client.get("/ingest/sources").json()["sources"][0]["id"] == source_id
        assert len(client.get("/ingest/outcomes").json()["outcomes"]) == 1
        assert (tmp_path / "uploads" / "brief.txt").exists()

    def test_withdrawing_a_source_removes_it_from_every_domain(self, client):
        """Otherwise a domain counts a source that no longer exists."""
        client.post(
            "/ingest/upload",
            files=[("files", ("brief.txt", b"A brief about the work at hand.", "text/plain"))],
        )
        source_id = client.get("/ingest/sources").json()["sources"][0]["id"]

        clients = make(client, "Clients", "Who I work for and what was agreed.")
        legal = make(client, "Legal", "Contracts, terms and expiries.")
        client.post(f"/knowledge/domains/{clients['id']}/sources/{source_id}")
        client.post(f"/knowledge/domains/{legal['id']}/sources/{source_id}")

        client.delete(f"/ingest/sources/{source_id}")

        listed = {d["name"]: d["source_ids"] for d in client.get("/knowledge/domains").json()["domains"]}
        assert listed == {"Clients": [], "Legal": []}, (
            "a withdrawn source is still listed inside a domain"
        )

    def test_removing_something_unknown_is_a_404(self, client):
        assert client.delete("/knowledge/domains/dom-nothing").status_code == 404

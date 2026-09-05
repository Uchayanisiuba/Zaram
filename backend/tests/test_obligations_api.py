"""Obligations through the real route.

`test_obligations_reach_the_store.py` grades the ingest seam and the store,
which is the right level for those claims and is exactly why it cannot see this
one. The precedent is `test_deck_api.py`: the `kind: "deck"` branch read a
field the request model did not have, every deck request came back as a 500,
and the exporter tests stayed green because none of them went through the wire.

**A capability reachable only from Python is not a capability the product has**
— which is the whole reason this feature needed wiring in the first place.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

INVOICE = (
    "Invoice INV-HARB-014 for Harbour Lane Studio.\n"
    "Issued 2 July 2026 in NGN.\n"
    "Payment terms: 30 days from the invoice date.\n"
    "Final delivery is 12 September 2026.\n"
)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import importlib

    monkeypatch = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("obligations-api")
    monkeypatch.setenv("ZARAM_OBLIGATIONS_DB", str(root / "obligations.db"))
    monkeypatch.setenv("ZARAM_INGEST_DB", str(root / "ingest.db"))
    monkeypatch.setenv("ZARAM_ARTIFACTS_DB", str(root / "artifacts.db"))
    monkeypatch.setenv("ZARAM_PROJECTS_DB", str(root / "projects.db"))
    monkeypatch.setenv("ZARAM_OUTPUT_DIR", str(root / "generated"))

    import main as main_module

    importlib.reload(main_module)

    docs = root / "docs"
    docs.mkdir()
    (docs / "invoice.txt").write_text(INVOICE, encoding="utf-8")
    main_module.ingest_service.scan(str(docs))

    with TestClient(main_module.app) as test_client:
        yield test_client

    monkeypatch.undo()
    importlib.reload(main_module)


def _live(client):
    response = client.get("/obligations")
    assert response.status_code == 200, response.text
    return response.json()


class TestReading:
    def test_the_route_returns_what_ingest_found(self, client):
        payload = _live(client)
        assert payload["obligations"], "no obligations reached the route"

    def test_every_obligation_carries_its_clause(self, client):
        # Rule 2. The clause is what makes a commitment checkable rather than
        # asserted, and it is the thing a user disputes against.
        obligations = _live(client)["obligations"]
        assert obligations
        for item in obligations:
            assert item["source_clause"]["text"].strip()
            assert item["source_document_id"]

    def test_an_undatable_clause_comes_back_as_a_question(self, client):
        # "30 days from the invoice date" with no issue date known. Asked, not
        # anchored to today.
        questions = _live(client)["questions"]
        assert questions
        assert all(q["question"].strip() for q in questions)
        assert all(q["clause"]["text"].strip() for q in questions)

    def test_one_obligation_is_addressable(self, client):
        first = _live(client)["obligations"][0]
        response = client.get(f"/obligations/{first['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == first["id"]

    def test_an_unknown_id_is_a_404_not_an_empty_record(self, client):
        assert client.get("/obligations/nope").status_code == 404


class TestCorrecting:
    """Rule 4, through the wire."""

    def test_a_correction_supersedes_and_changes_what_is_live(self, client):
        original = _live(client)["obligations"][0]

        response = client.post(
            f"/obligations/{original['id']}/correct", json={"due": "2026-11-05"}
        )
        assert response.status_code == 200, response.text
        corrected = response.json()
        assert corrected["due"] == "2026-11-05"
        assert corrected["id"] != original["id"]

        live = {o["id"] for o in _live(client)["obligations"]}
        assert corrected["id"] in live
        assert original["id"] not in live

        # And the superseded one is still readable, which is what makes the
        # correction auditable rather than a silent overwrite.
        assert client.get(f"/obligations/{original['id']}").status_code == 200

    def test_a_correction_cannot_rewrite_the_source_clause(self, client):
        # Not exposed on the request model at all: a correction says Zaram read
        # the sentence wrongly, not that the sentence was different.
        original = _live(client)["obligations"][0]
        response = client.post(
            f"/obligations/{original['id']}/correct",
            json={"summary": "Something else", "source_clause": {"text": "invented"}},
        )
        assert response.status_code == 200
        assert response.json()["source_clause"] == original["source_clause"]

    def test_direction_can_be_set_because_the_extractor_refuses_to_guess(self, client):
        original = _live(client)["obligations"][0]
        response = client.post(
            f"/obligations/{original['id']}/correct",
            json={"direction": "owed_to_user"},
        )
        assert response.status_code == 200
        assert response.json()["direction"] == "owed_to_user"

    def test_a_bad_date_is_refused_rather_than_coerced(self, client):
        original = _live(client)["obligations"][0]
        response = client.post(
            f"/obligations/{original['id']}/correct", json={"due": "the 5th"}
        )
        assert response.status_code == 400
        assert "ISO date" in response.text

    def test_a_bad_direction_names_the_permitted_values(self, client):
        original = _live(client)["obligations"][0]
        response = client.post(
            f"/obligations/{original['id']}/correct", json={"direction": "sideways"}
        )
        assert response.status_code == 400
        assert "owed_by_user" in response.text


class TestDismissing:
    def test_a_dismissed_obligation_leaves_the_live_list_and_stays_readable(self, client):
        original = _live(client)["obligations"][-1]

        assert client.post(f"/obligations/{original['id']}/dismiss").status_code == 200
        assert original["id"] not in {o["id"] for o in _live(client)["obligations"]}

        # Kept, not deleted: the next ingest of the same document must not
        # resurrect it, and the user is entitled to see what they dismissed.
        assert client.get(f"/obligations/{original['id']}").json()["status"] == "dismissed"

    def test_dismissed_ones_are_visible_when_asked_for(self, client):
        response = client.get("/obligations", params={"include_closed": True})
        assert response.status_code == 200
        assert any(o["status"] == "dismissed" for o in response.json()["obligations"])

    def test_dismissing_something_that_does_not_exist_is_a_404(self, client):
        assert client.post("/obligations/nope/dismiss").status_code == 404


class TestAnsweringAQuestion:
    """Rule 9's shape: ask rather than guess, and accept the answer here."""

    def test_supplying_the_anchor_produces_a_dated_commitment(self, client):
        question = _live(client)["questions"][0]
        response = client.post(
            f"/obligations/questions/{question['id']}/answer",
            json={"anchor": "2026-07-02"},
        )
        assert response.status_code == 200, response.text
        created = response.json()
        assert created["due"] == "2026-08-01"
        assert created["source_clause"]["text"].strip()

        # The question is closed rather than asked again.
        assert question["id"] not in {q["id"] for q in _live(client)["questions"]}

    def test_a_bad_anchor_is_refused(self, client):
        response = client.post(
            "/obligations/questions/anything/answer", json={"anchor": "last Tuesday"}
        )
        assert response.status_code == 400
        assert "ISO date" in response.text

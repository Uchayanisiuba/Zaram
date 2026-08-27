"""The session store over HTTP.

Against the **real** application object, not a private `FastAPI()` built here.
That distinction is the reason `tests/test_routes_are_mounted.py` exists:
`providers/api.py` was a complete router with a passing test file and no
`include_router`, so every path answered 404 on the running product while its
tests stayed green. A file that mounts its own router cannot see that.

These tests point at `main.app` and rebind the store to a temporary database,
so what is exercised is the wiring a user actually reaches.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from conversations import ConversationRecords
from conversations.api import set_records


@pytest.fixture()
def client(tmp_path):
    """The real app, with the store pointed at a temporary database.

    **`TestClient(app)` rather than `with TestClient(app)`, deliberately.** The
    context-manager form runs the lifespan events, which boots the whole kernel
    -- provider discovery, the Spine, a model preload -- once per test. Measured
    here: 23 s for a single test, and eleven errors when the suite ran them
    together. These routes need none of it. `test_routes_are_mounted.py` made
    the same choice for the same reason and says so: *"a test that boots the
    kernel would not be"* fast enough to run without thinking.
    """
    import main

    set_records(ConversationRecords(str(tmp_path / "conversations.db")))
    return TestClient(main.app)


def _start(client, **body) -> str:
    response = client.post("/conversations", json=body or {})
    assert response.status_code == 200, response.text
    return response.json()["id"]


class TestATranscriptRoundTrips:
    def test_a_new_conversation_comes_back_in_the_list(self, client):
        conversation_id = _start(client)

        listed = client.get("/conversations").json()

        assert [c["id"] for c in listed] == [conversation_id]

    def test_reading_one_brings_its_messages_with_it(self, client, tmp_path):
        """Messages arrive with the conversation rather than from a second
        route. A client that has to ask twice paints an empty thread while the
        second request is in flight."""
        import main  # noqa: F401

        from conversations.api import _records

        conversation_id = _start(client)
        records = _records()
        records.append(conversation_id, "user", "what is my day rate")
        records.append(
            conversation_id, "assistant", "400 a day.", model="gemma4:12b", locality="local"
        )

        body = client.get(f"/conversations/{conversation_id}").json()

        assert [m["text"] for m in body["messages"]] == [
            "what is my day rate",
            "400 a day.",
        ]
        assert body["messages"][1]["model"] == "gemma4:12b"
        assert body["messages"][1]["locality"] == "local"
        assert body["message_count"] == 2

    def test_renaming_takes(self, client):
        conversation_id = _start(client)

        response = client.patch(
            f"/conversations/{conversation_id}", json={"title": "Harbour Lane"}
        )

        assert response.status_code == 200
        assert response.json()["title"] == "Harbour Lane"


class TestScopeSurvivesTheWire:
    """``project_id`` absent and ``project_id=""`` are different questions, and
    a query string is exactly where that distinction gets flattened."""

    def test_omitting_the_scope_returns_everything(self, client):
        scoped = _start(client, project_id="harbour-lane")
        unscoped = _start(client)

        listed = client.get("/conversations").json()

        assert {c["id"] for c in listed} == {scoped, unscoped}

    def test_an_empty_scope_returns_only_the_unscoped(self, client):
        _start(client, project_id="harbour-lane")
        unscoped = _start(client)

        listed = client.get("/conversations", params={"project_id": ""}).json()

        assert [c["id"] for c in listed] == [unscoped]

    def test_a_named_scope_returns_only_that_project(self, client):
        scoped = _start(client, project_id="harbour-lane")
        _start(client)

        listed = client.get("/conversations", params={"project_id": "harbour-lane"}).json()

        assert [c["id"] for c in listed] == [scoped]


class TestDeletionSaysWhatItDidNotDo:
    def test_the_transcript_goes(self, client):
        conversation_id = _start(client)

        assert client.delete(f"/conversations/{conversation_id}").status_code == 200
        assert client.get(f"/conversations/{conversation_id}").status_code == 404

    def test_the_response_states_that_facts_are_untouched(self, client):
        """Rule 4 is about the *fact* and the answers built on it, and that
        machinery lives where the fact does. Deleting a transcript must not
        quietly widen into deleting memory — and must not leave the caller to
        assume either way."""
        conversation_id = _start(client)

        body = client.delete(f"/conversations/{conversation_id}").json()

        assert body["facts_removed"] == 0
        assert "Memory" in body["note"]


class TestTheHonestFailures:
    def test_reading_a_conversation_that_is_not_there_is_404(self, client):
        assert client.get("/conversations/conv_nothing").status_code == 404

    def test_deleting_one_that_is_not_there_is_404(self, client):
        assert client.delete("/conversations/conv_nothing").status_code == 404

    def test_renaming_one_that_is_not_there_is_404(self, client):
        response = client.patch("/conversations/conv_nothing", json={"title": "x"})

        assert response.status_code == 404

    def test_a_blank_title_is_a_bad_request_not_a_server_fault(self, client):
        conversation_id = _start(client)

        response = client.patch(f"/conversations/{conversation_id}", json={"title": "   "})

        assert response.status_code == 400
        assert "title" in response.json()["detail"].lower()
